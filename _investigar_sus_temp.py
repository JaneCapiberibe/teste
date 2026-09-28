"""
LEVANTAMENTO DE SCHEMA — projeto SUS ("Sustentação"), a pedido da Jane.

Só investiga — não escreve em sweep.json/dash_data.json nem em nenhum arquivo do pipeline.
Mesmo padrão do levantamento já feito pro BACKOFFICE (21/09/2026): reaproveita
fetch_jira.py (_auth_headers/BASE/FIELDS/fetch_all/fetch_changelogs), sem duplicar
lógica de autenticação/paginação.

Arquivo e workflow são temporários — removidos depois que a Jane decidir o que puxar.
"""
import json, os, collections, requests, sys
sys.path.insert(0, '.')
import fetch_jira as fj

JQL = 'project = SUS AND created >= -180d'
HEAD = fj._auth_headers()
BASE = fj.BASE


def get_json(path, params=None):
    r = requests.get(f'{BASE}{path}', headers=HEAD, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def linha(): print('=' * 78)


linha()
print('0) PROJETO SUS — metadados + esquema de workflow (statuses possíveis por tipo)')
linha()
try:
    proj = get_json('/rest/api/3/project/SUS')
    print('nome:', proj.get('name'), '| key:', proj.get('key'), '| tipo:', proj.get('projectTypeKey'),
          '| estilo:', proj.get('style'))
except Exception as e:
    print('erro ao buscar /rest/api/3/project/SUS:', e)

try:
    statuses_meta = get_json('/rest/api/3/project/SUS/statuses')
    print('\nPor issue type, os status QUE EXISTEM NO WORKFLOW (não é contagem de uso real):')
    for it in statuses_meta:
        nomes = ', '.join(s['name'] for s in it['statuses'])
        print(f"  {it['name']}: {nomes}")
except Exception as e:
    print('erro ao buscar /rest/api/3/project/SUS/statuses:', e)

linha()
print(f'1) AMOSTRA — issues de SUS criados nos últimos ~180 dias ({JQL!r})')
print('   (campos conhecidos — mesma whitelist FIELDS já usada em BUG/BACKOFFICE)')
linha()
issues = fj.fetch_all(jql=JQL + ' ORDER BY created DESC')
n = len(issues)
print(f'total na amostra: {n}')

if not n:
    print('\nNENHUM issue retornado — parando aqui (ver credenciais/permissão/nome do projeto).')
    sys.exit(0)

tipo_cnt = collections.Counter()
status_cnt = collections.Counter()
res_cnt = collections.Counter()
assignee_cnt = collections.Counter()
sem_assignee = 0
timespent_preenchido = 0
modulo_preenchido = 0
modulo_valores = collections.Counter()
assignees = set()

for i in issues:
    f = i['fields']
    tipo_cnt[(f.get('issuetype') or {}).get('name')] += 1
    status_cnt[(f.get('status') or {}).get('name')] += 1
    res = f.get('resolution')
    res_cnt[res.get('name') if res else '(vazio)'] += 1
    a = f.get('assignee')
    if a:
        dn = a.get('displayName') or '(sem nome)'
        assignees.add(dn)
        assignee_cnt[dn] += 1
    else:
        sem_assignee += 1
    ts = f.get('timespent') if f.get('timespent') is not None else f.get('aggregatetimespent')
    if ts:
        timespent_preenchido += 1
    mod = f.get('customfield_10073')
    if mod:
        modulo_preenchido += 1
        mv = mod.get('value') if isinstance(mod, dict) else mod
        modulo_valores[mv] += 1

print('\n--- (1) TIPOS DE ISSUE ---')
for k, v in tipo_cnt.most_common():
    print(f'  {k}: {v}')

print('\n--- (2) STATUS (uso real na amostra) ---')
for k, v in status_cnt.most_common():
    print(f'  {k}: {v}')
print('\nComparação com STATUS_ORDER/ST_ENTREGUE_FUNIL já usados em BUG (gen_data.py):')
conhecidos_bug = {'Não Iniciado', 'Em Desenvolvimento', 'IMPEDIMENTO DEV', 'IMPEDIMENTO PRODUTO',
                   'Revert', 'Backlog', 'Revisão QA', 'Aprovado QA', 'Reprovado QA', 'Merge Request',
                   'Em produção', 'Em Produção', 'Done', 'Concluído', 'Concluido'}
novos_status = [s for s in status_cnt if s not in conhecidos_bug]
iguais_status = [s for s in status_cnt if s in conhecidos_bug]
print(f'  nomes IGUAIS aos já vistos em BUG: {iguais_status or "(nenhum)"}')
print(f'  nomes NOVOS (não existem no workflow do BUG): {novos_status or "(nenhum)"}')

print('\n--- (4) RESOLUTION (uso real na amostra) ---')
for k, v in res_cnt.most_common():
    print(f'  {k}: {v}')
conhecidos_res = {'Cancelado QA', 'Cancelado Dev', 'Não Pode Reproduzir', 'Itens concluídos'}
novos_res = [r for r in res_cnt if r not in conhecidos_res and r != '(vazio)']
print(f'  valores de resolution que NÃO existem em BUG/BACKOFFICE: {novos_res or "(nenhum)"}')

print(f'\n--- (3) ASSIGNEE ---')
print(f'  preenchido: {n - sem_assignee}/{n}  |  sem responsável: {sem_assignee}/{n}')
print(f'  pessoas distintas em SUS (últimos 180d): {len(assignees)}')
for k, v in assignee_cnt.most_common():
    print(f'    {k}: {v}')

try:
    sweep = json.load(open('sweep.json')) if os.path.exists('sweep.json') else []
    sweep_bo = json.load(open('sweep_backoffice.json')) if os.path.exists('sweep_backoffice.json') else []
    conhecidos_assignee = ({x['assignee'] for x in sweep if x.get('assignee')} |
                            {x['assignee'] for x in sweep_bo if x.get('assignee')})
    comuns = assignees & conhecidos_assignee
    exclusivos = assignees - conhecidos_assignee
    print(f'\n  já aparecem em BUG e/ou BACKOFFICE: {len(comuns)} -> {sorted(comuns)}')
    print(f'  EXCLUSIVOS de SUS (não aparecem em BUG/BACKOFFICE): {len(exclusivos)} -> {sorted(exclusivos)}')
except Exception as e:
    print(f'  erro ao comparar com sweep.json/sweep_backoffice.json: {e}')

print(f'\n--- (5) TIMESPENT/AGGREGATETIMESPENT ---')
pct = 100 * timespent_preenchido / n
print(f'  preenchido em {timespent_preenchido}/{n} issues ({pct:.1f}%)')

print(f'\n--- (7) customfield_10073 ("Módulo" no BUG) ---')
print(f'  preenchido em {modulo_preenchido}/{n} issues de SUS')
if modulo_valores:
    print('  valores encontrados:')
    for k, v in modulo_valores.most_common(20):
        print(f'    {k}: {v}')

linha()
print('2) CHANGELOG — testando /changelog/bulkfetch (status + assignee) numa sub-amostra')
linha()
amostra_ids = [i['id'] for i in issues[:20]]
changelogs, iniciais, assignee_changelogs = fj.fetch_changelogs(amostra_ids)
com_changelog = sum(1 for iid in amostra_ids if changelogs.get(iid))
com_assignee_cl = sum(1 for iid in amostra_ids if assignee_changelogs.get(iid))
print(f'{com_changelog}/{len(amostra_ids)} issues da sub-amostra têm >=1 transição de STATUS no changelog')
print(f'{com_assignee_cl}/{len(amostra_ids)} issues da sub-amostra têm >=1 transição de ASSIGNEE no changelog (repasse)')
if amostra_ids:
    iid0 = amostra_ids[0]
    chave0 = next((i['key'] for i in issues if i['id'] == iid0), iid0)
    print(f'\nExemplo ({chave0}):')
    print('  status changes  :', changelogs.get(iid0))
    print('  assignee changes:', assignee_changelogs.get(iid0))

linha()
print('3) SCAN BRUTO DE CAMPOS (fields=*all) — pra achar campos específicos de sustentação')
linha()
body = {'jql': JQL, 'fields': ['*all'], 'maxResults': 50}
r = requests.post(f'{BASE}/rest/api/3/search/jql', headers=HEAD, data=json.dumps(body), timeout=60)
if not r.ok:
    print(f'Jira respondeu {r.status_code} em fields=*all: {r.text[:2000]}')
r.raise_for_status()
raw_issues = r.json().get('issues', [])
print(f'(amostra de {len(raw_issues)} issues, todos os campos)')

field_meta = get_json('/rest/api/3/field')
id2name = {fm['id']: fm['name'] for fm in field_meta}

JA_CONHECIDOS = set(fj.FIELDS) | {
    'summary', 'description', 'project', 'reporter', 'creator', 'labels', 'comment',
    'attachment', 'issuelinks', 'subtasks', 'fixVersions', 'versions', 'components',
    'duedate', 'worklog', 'watches', 'votes', 'parent', 'progress', 'workratio',
    'lastViewed', 'environment', 'security', 'issuerestriction', 'statuscategorychangedate',
}

presente = collections.Counter()
exemplo = {}
for ri in raw_issues:
    for fid, val in ri.get('fields', {}).items():
        if val in (None, [], {}):
            continue
        presente[fid] += 1
        if fid not in exemplo:
            exemplo[fid] = val

novos = sorted((fid for fid in presente if fid not in JA_CONHECIDOS), key=lambda f: -presente[f])
print(f'\nCampos preenchidos em >=1 issue da amostra, FORA da whitelist já usada em BUG/BACKOFFICE '
      f'({len(novos)} campo(s)):')
for fid in novos:
    nome = id2name.get(fid, '???')
    pct = 100 * presente[fid] / len(raw_issues) if raw_issues else 0
    ex_str = json.dumps(exemplo[fid], ensure_ascii=False)[:200]
    print(f'  {fid}  ({nome})  — preenchido em {presente[fid]}/{len(raw_issues)} ({pct:.0f}%)')
    print(f'      exemplo: {ex_str}')

linha()
print('FIM DO LEVANTAMENTO')
linha()
