"""
Lista os cards do PEM lançados em 2026 com assignee = Henry Américo, a pedido da Jane
(follow-up da extração histórica). Mesma lógica/definição já validada (STATUS_CONCLUIDO =
Concluído/Done/Concluido, fallback de Marketing e Lançamento). Só leitura — não altera nada.
"""
import json, sys, requests

sys.path.insert(0, '.')
import fetch_jira as fj

HEAD = fj._auth_headers()
BASE = fj.BASE

FIELDS = ['issuetype', 'status', 'resolution', 'created', 'assignee', 'summary', 'customfield_10065']
STATUS_CONCLUIDO = ('Concluído', 'Done', 'Concluido')
ALVO = 'Henry Américo'


def fetch_all_full(jql):
    url = f'{BASE}/rest/api/3/search/jql'
    out, token = [], None
    while True:
        body = {'jql': jql, 'fields': FIELDS, 'maxResults': 100}
        if token:
            body['nextPageToken'] = token
        r = requests.post(url, headers=HEAD, data=json.dumps(body), timeout=60)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get('issues', []))
        token = data.get('nextPageToken')
        if not token:
            break
    return out


issues = fetch_all_full('project = PEM ORDER BY created ASC')
ids = [i['id'] for i in issues]
changelogs, iniciais, _ = fj.fetch_changelogs(ids)


def data_lancado(i):
    ep = fj._first_to_epoch(changelogs.get(i['id']) or [], 'Marketing e Lançamento')
    if ep is None:
        ep = fj._first_to_epoch(changelogs.get(i['id']) or [], STATUS_CONCLUIDO)
    return fj._epoch_iso(ep) if ep is not None else None


print(f'Cards do PEM lançados em 2026 com assignee = "{ALVO}":\n')
achados = []
for i in issues:
    f = i['fields']
    if (f.get('resolution') or {}).get('name') == "Won't Do":
        continue
    a = (f.get('assignee') or {}).get('displayName')
    if a != ALVO:
        continue
    d = data_lancado(i)
    if not d or d[:4] != '2026':
        continue
    mods = [m.get('value') for m in (f.get('customfield_10065') or []) if isinstance(m, dict)]
    achados.append((i['key'], f.get('summary', ''), (f.get('issuetype') or {}).get('name'),
                     (f.get('status') or {}).get('name'), d, ', '.join(mods) or '(sem módulo)'))

achados.sort(key=lambda t: t[4])
for key, summary, tipo, status, data, mods in achados:
    print(f'{key}  [{tipo}]  lançado em {data[:10]}  |  módulo: {mods}')
    print(f'    {summary}')
    print(f'    status atual: {status}')
    print()

print(f'TOTAL: {len(achados)} cards')
