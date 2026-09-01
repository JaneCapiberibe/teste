"""
levantamento_cancelado_dev.py — LEVANTAMENTO INFORMATIVO, não faz parte do pipeline
(não é chamado por update.yml, não altera sweep.json/dash_data.json/etc).

Objetivo: quantificar o impacto de excluir resolution == "Cancelado Dev" da régua
oficial (mesmo escopo/regra de evolucao_bugs.py), para decisão de gestão. NÃO
altera o comportamento de evolucao_bugs.py nem de nenhum outro script do pipeline
— só lê o Jira e imprime uma tabela comparativa.

NOTA IMPORTANTE: evolucao_bugs.fetch_all() está quebrado (400 Bad Request —
expand=changelog não é aceito em /rest/api/3/search/jql, confirmado rodando de
verdade; o mesmo bug que já tinha sido corrigido em fetch_jira.py trocando pro
endpoint dedicado /changelog/bulkfetch). Como o pedido é explícito pra NÃO alterar
evolucao_bugs.py, este script busca os dados via fetch_jira.py (fetch_all_com_
retentativa/fetch_changelogs/norm — já testados, já produzem concluido_mes pela
MESMA régua: 1ª entrada em "Em produção", fallback "Done"/"Concluído", fallback
final mês de criação pra card terminal sem transição registrada). Único ajuste de
escopo: usa project=BUG (fetch_jira.py) em vez do JQL sem filtro de projeto de
evolucao_bugs.py — na prática os 4 tipos de bug só existem nesse projeto.

Mesma régua de "fora de tudo" de evolucao_bugs.py (Cancelado QA + card ATUALMENTE
em IMPEDIMENTO PRODUTO), mas SEM excluir Cancelado Dev — ele fica incluído no
baseline (como hoje) e é contado à parte para dar a comparação "com vs sem".

Uso: python levantamento_cancelado_dev.py (precisa de JIRA_BASE_URL, JIRA_EMAIL,
JIRA_API_TOKEN nas variáveis de ambiente — mesmos segredos do resto do pipeline).
"""
import collections
from evolucao_bugs import BUG_TYPES
from fetch_jira import fetch_all_com_retentativa, fetch_changelogs, norm

RES_FORA = ("Cancelado QA",)  # única exclusão de resolução no baseline (igual evolucao_bugs.py)
RES_DEV = "Cancelado Dev"
ST_IMP_PRODUTO = "IMPEDIMENTO PRODUTO"


def build_report(recs):
    criados = collections.Counter()
    concluidos = collections.Counter()
    criados_dev = collections.Counter()
    concluidos_dev = collections.Counter()
    dev_keys = []

    for r in recs:
        if r["itype"] not in BUG_TYPES:
            continue
        if r["res"] in RES_FORA:
            continue
        if r["status"] == ST_IMP_PRODUTO:
            continue

        is_dev = (r["res"] == RES_DEV)
        created = r["created"]
        if created:
            cm = created[:7]
            criados[cm] += 1
            if is_dev:
                criados_dev[cm] += 1
                dev_keys.append(r["key"])

        mes = r.get("concluido_mes")
        if mes:
            concluidos[mes] += 1
            if is_dev:
                concluidos_dev[mes] += 1

    meses = sorted(set(list(criados) + list(concluidos)))
    return meses, criados, concluidos, criados_dev, concluidos_dev, dev_keys


def main():
    print("evolucao_bugs.fetch_all() está quebrado (400 Bad Request em expand=changelog) — "
          "usando fetch_jira.py (project=BUG, changelog via bulkfetch) pra este levantamento.")
    print("Puxando do Jira...")
    issues = fetch_all_com_retentativa()
    print("Puxando changelog em lote...")
    changelogs = fetch_changelogs([i.get("id") for i in issues])
    recs = [norm(i, changelogs.get(i.get("id"))) for i in issues]

    meses, criados, concluidos, criados_dev, concluidos_dev, dev_keys = build_report(recs)

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
