"""
levantamento_cancelado_dev.py — LEVANTAMENTO INFORMATIVO, não faz parte do pipeline
(não é chamado por update.yml, não altera sweep.json/dash_data.json/etc).

Objetivo: quantificar o impacto de excluir resolution == "Cancelado Dev" da régua
oficial (mesmo escopo/regra de evolucao_bugs.py), para decisão de gestão. NÃO
altera o comportamento de evolucao_bugs.py nem de nenhum outro script do pipeline
— só lê o Jira e imprime uma tabela comparativa.

Mesma régua de evolucao_bugs.py (BUG_TYPES, fora de tudo = Cancelado QA + card
ATUALMENTE em IMPEDIMENTO PRODUTO, concluído = 1ª entrada em "Em produção" com
fallback "Done"/"Concluído"), mas SEM excluir Cancelado Dev — ele fica incluído
no baseline (como hoje) e é contado à parte para dar a comparação "com vs sem".

Uso: python levantamento_cancelado_dev.py (precisa de JIRA_BASE_URL, JIRA_EMAIL,
JIRA_API_TOKEN nas variáveis de ambiente — mesmos segredos do resto do pipeline).
"""
import collections
from evolucao_bugs import fetch_all, BUG_TYPES, ST_PRODUCAO, ST_DONE, ST_IMP_PRODUTO, _histories, _first_to

RES_FORA = ("Cancelado QA",)  # única exclusão de resolução no baseline (igual evolucao_bugs.py)
RES_DEV = "Cancelado Dev"


def build_report(issues):
    criados = collections.Counter()
    concluidos = collections.Counter()
    criados_dev = collections.Counter()
    concluidos_dev = collections.Counter()
    dev_keys = []

    for iss in issues:
        f = iss.get("fields", {})
        itype = (f.get("issuetype") or {}).get("name")
        if itype not in BUG_TYPES:
            continue
        res = (f.get("resolution") or {}).get("name")
        if res in RES_FORA:
            continue
        status = (f.get("status") or {}).get("name")
        if status == ST_IMP_PRODUTO:
            continue

        created = f.get("created")
        changes = _histories(iss)
        is_dev = (res == RES_DEV)

        if created:
            cm = created[:7]
            criados[cm] += 1
            if is_dev:
                criados_dev[cm] += 1
                dev_keys.append(iss.get("key"))

        mes = _first_to(changes, ST_PRODUCAO)
        if not mes:
            mes = _first_to(changes, ST_DONE)
            if not mes and status in (ST_PRODUCAO + ST_DONE):
                mes = (created or "")[:7] or None
        if mes:
            concluidos[mes] += 1
            if is_dev:
                concluidos_dev[mes] += 1

    meses = sorted(set(list(criados) + list(concluidos)))
    return meses, criados, concluidos, criados_dev, concluidos_dev, dev_keys


def main():
    print("Puxando bugs do Jira (com changelog) — mesmo JQL/escopo de evolucao_bugs.py...")
    issues = fetch_all()
    meses, criados, concluidos, criados_dev, concluidos_dev, dev_keys = build_report(issues)

    print()
    print(f"Total de cards 'Cancelado Dev' no escopo (BUG_TYPES, fora Cancelado QA/Impedimento Produto): {len(dev_keys)}")
    print()
    hdr = f"{'mes':8} | {'criados':>7} {'concl':>6} | {'dev_cri':>7} {'dev_con':>7} | {'cri_sem_dev':>11} {'con_sem_dev':>11}"
    print(hdr)
    print("-" * len(hdr))
    tot = collections.Counter()
    for m in meses:
        c, k = criados.get(m, 0), concluidos.get(m, 0)
        cd, kd = criados_dev.get(m, 0), concluidos_dev.get(m, 0)
        print(f"{m:8} | {c:7} {k:6} | {cd:7} {kd:7} | {c - cd:11} {k - kd:11}")
        tot["c"] += c; tot["k"] += k; tot["cd"] += cd; tot["kd"] += kd
    print("-" * len(hdr))
    print(f"{'TOTAL':8} | {tot['c']:7} {tot['k']:6} | {tot['cd']:7} {tot['kd']:7} | "
          f"{tot['c']-tot['cd']:11} {tot['k']-tot['kd']:11}")
    print()
    print("Keys 'Cancelado Dev':", ", ".join(sorted(dev_keys)))


if __name__ == "__main__":
    main()
