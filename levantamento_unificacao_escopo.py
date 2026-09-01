"""
levantamento_unificacao_escopo.py — LEVANTAMENTO TEMPORÁRIO, não faz parte do pipeline
(não é chamado por update.yml, não altera sweep.json/dash_data.json/etc).

Objetivo: comparar criados/concluídos mês a mês ANTES (escopo antigo de evolucao_bugs.py —
issuetype in (Bug Cliente, Bug QA, Bug Dev, Bug Backoffice), QUALQUER projeto) vs DEPOIS
(escopo novo unificado — project = BUG, decisão de 01/09/2026), pra validar que a
divergência entre "Diagnóstico do mês" (que já usava o painel BUG via sweep) e a régua
oficial de evolucao_bugs.py desaparece com a unificação.

Mesma régua de inclusão/exclusão nos dois lados (a régua de evolucao_bugs.py, inalterada):
  - itype in BUG_TYPES
  - fora resolution "Cancelado QA"/"Cancelado Dev"
  - fora card ATUALMENTE parado em "IMPEDIMENTO PRODUTO"
  - criado = mês de `created`; concluído = concluido_mes (1ª entrada em "Em produção",
    fallback Done/Concluído, fallback final mês de criação) — mesmo campo que sweep.json.

Reaproveita fetch_all()/fetch_changelogs()/norm() de fetch_jira.py (mecanismo de busca já
testado e funcional — evolucao_bugs.fetch_all() está quebrado, 400 em expand=changelog no
/search/jql; o mesmo motivo que já tinha exigido esse workaround em
levantamento_cancelado_dev.py). fetch_all() agora aceita um `jql` opcional (generalizado
pra este levantamento) — sem mudar o comportamento padrão usado pelo pipeline real.
"""
import collections
from fetch_jira import fetch_all, fetch_changelogs, norm, BUG_TYPES

RES_FORA = ('Cancelado QA', 'Cancelado Dev')
ST_IMP_PRODUTO = 'IMPEDIMENTO PRODUTO'

_types = ",".join(f'"{t}"' for t in BUG_TYPES)
JQL_ANTIGO = f'issuetype in ({_types}) ORDER BY created ASC'
JQL_NOVO = 'project = BUG ORDER BY created ASC'


def elegivel(r):
    return r['itype'] in BUG_TYPES and r['res'] not in RES_FORA and r['status'] != ST_IMP_PRODUTO


def build(recs):
    criados = collections.Counter()
    concluidos = collections.Counter()
    for r in recs:
        if not elegivel(r):
            continue
        if r['created']:
            criados[r['created'][:7]] += 1
        if r.get('concluido_mes'):
            concluidos[r['concluido_mes']] += 1
    return criados, concluidos


def fetch_scope(jql, label):
    print(f'Buscando escopo {label} ({jql!r})...')
    issues = fetch_all(jql)
    print(f'  {len(issues)} issues — buscando changelog em lote...')
    changelogs = fetch_changelogs([i.get('id') for i in issues])
    return [norm(i, changelogs.get(i.get('id'))) for i in issues]


def main():
    recs_antigo = fetch_scope(JQL_ANTIGO, 'ANTIGO (issuetype, qualquer projeto)')
    recs_novo = fetch_scope(JQL_NOVO, 'NOVO (project = BUG)')

    cri_a, con_a = build(recs_antigo)
    cri_n, con_n = build(recs_novo)
    meses = sorted(set(list(cri_a) + list(con_a) + list(cri_n) + list(con_n)))

    print()
    hdr = f"{'mes':8} | {'cri_antes':>9} {'con_antes':>9} | {'cri_depois':>10} {'con_depois':>10}"
    print(hdr)
    print('-' * len(hdr))
    ta = tb = tc = td = 0
    for m in meses:
        a, b, c, d = cri_a.get(m, 0), con_a.get(m, 0), cri_n.get(m, 0), con_n.get(m, 0)
        marca = '  <-- diverge' if (a, b) != (c, d) else ''
        print(f"{m:8} | {a:9} {b:9} | {c:10} {d:10}{marca}")
        ta += a; tb += b; tc += c; td += d
    print('-' * len(hdr))
    print(f"{'TOTAL':8} | {ta:9} {tb:9} | {tc:10} {td:10}")


if __name__ == '__main__':
    main()
