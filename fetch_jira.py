"""
fetch_jira.py — puxa TODOS os bugs do Jira (projeto BUG) via API REST e gera os
arquivos que o pipeline consome: sweep.json + jira_backlog.json + impedimentos_live.json
+ sobra_live.json + ni_assignee.json.

Credenciais via variáveis de ambiente (segredos do GitHub Actions):
  JIRA_BASE_URL   ex.: https://orcafascio.atlassian.net
  JIRA_EMAIL      seu e-mail do Atlassian
  JIRA_API_TOKEN  token de API (id.atlassian.com/manage-profile/security/api-tokens)
"""
import os, json, base64, datetime, collections, urllib.parse, time
import requests

BASE = os.environ.get('JIRA_BASE_URL', 'https://orcafascio.atlassian.net').rstrip('/')

FIELDS = ['status', 'priority', 'resolution', 'created', 'updated', 'resolutiondate',
          'timespent', 'aggregatetimespent', 'issuetype', 'assignee', 'customfield_10073']

def fetch_all():
    """Puxa todos os issues do projeto BUG, paginando com nextPageToken."""
    email = os.environ['JIRA_EMAIL']
    token_ = os.environ['JIRA_API_TOKEN']
    auth = 'Basic ' + base64.b64encode(f'{email}:{token_}'.encode()).decode()
    HEAD = {'Authorization': auth, 'Accept': 'application/json', 'Content-Type': 'application/json'}
    url = f'{BASE}/rest/api/3/search/jql'
    out, token = [], None
    while True:
        body = {'jql': 'project = BUG ORDER BY created ASC', 'fields': FIELDS, 'maxResults': 100}
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

def fetch_all_com_retentativa(tentativas=3, espera_s=15):
    """Chama fetch_all() com retentativas. O projeto BUG tem centenas de issues — uma resposta
    200 com 0 issues é sinal de instabilidade transitória da API do Jira (ou credencial/permissão
    ruim), nunca de que o projeto ficou vazio de verdade. Sem isso, um blip momentâneo já derrubou
    o pipeline (gen_data.py crasha mais na frente com um ValueError sem contexto)."""
    issues = []
    for tentativa in range(1, tentativas + 1):
        issues = fetch_all()
        if issues:
            return issues
        print(f'aviso: tentativa {tentativa}/{tentativas} do Jira voltou com 0 issues.')
        if tentativa < tentativas:
            time.sleep(espera_s)
    return issues

def norm(issue):
    f = issue.get('fields', {})
    def name(x): return (x or {}).get('value') if isinstance(x, dict) and 'value' in (x or {}) else ((x or {}).get('name') if isinstance(x, dict) else None)
    mod = f.get('customfield_10073')
    assignee = (f.get('assignee') or {}).get('displayName') or 'Sem responsável'
    return {
        'key': issue.get('key'),
        'status': name(f.get('status')),
        'prio': name(f.get('priority')),
        'itype': name(f.get('issuetype')),
        'res': name(f.get('resolution')),
        'created': f.get('created'),
        'resolved': f.get('resolutiondate'),
        'updated': f.get('updated'),
        'timespent': f.get('timespent') if f.get('timespent') is not None else f.get('aggregatetimespent'),
        'modulo': (mod or {}).get('value') if isinstance(mod, dict) else mod,
        'assignee': assignee,
    }

def mm(iso):
    return iso[:7] if iso else None  # 'YYYY-MM'

CHAT = 'Chat de Suporte'
def modclean(m):
    import re
    return 'Não classificado' if not m else re.sub(r'^\d+\s*-\s*', '', str(m)).strip()

def build_outputs(recs):
    # 1) sweep.json (formato do gen_data)
    sweep = [{k: r[k] for k in ('key', 'status', 'prio', 'itype', 'res', 'created', 'resolved', 'timespent', 'modulo')} for r in recs]
    json.dump(sweep, open('sweep.json', 'w'), ensure_ascii=False)

    def ischat(r): return modclean(r['modulo']) == CHAT
    def cancel(r): return r['res'] == 'Cancelado QA'
    live = [r for r in recs if not ischat(r)]  # tira Chat de Suporte de tudo

    # 2) jira_backlog.json — método do Diego
    DONE = {'Done', 'Concluído', 'Concluido', 'Em produção', 'Em Produção'}
    criados = collections.Counter()
    concl = collections.Counter()
    for r in live:
        if cancel(r):
            continue
        cm = mm(r['created'])
        if cm and r['status'] != 'IMPEDIMENTO PRODUTO':
            criados[cm] += 1
        if r['status'] in DONE:
            um = mm(r['updated'])
            if um:
                concl[um] += 1
    meses = sorted(set(list(criados) + list(concl)))
    jb, inicio = {}, 0
    for m in meses:
        fim = inicio + criados.get(m, 0) - concl.get(m, 0)
        jb[m] = {'inicio': inicio, 'criados': criados.get(m, 0), 'concluidos': concl.get(m, 0), 'acumulado': fim}
        inicio = fim
    json.dump(jb, open('jira_backlog.json', 'w'), ensure_ascii=False, indent=1)

    # 3) impedimentos_live.json
    imp = [r for r in live if r['status'] in ('IMPEDIMENTO DEV', 'IMPEDIMENTO PRODUTO')]
    produto = sum(1 for r in imp if r['status'] == 'IMPEDIMENTO PRODUTO')
    dev = sum(1 for r in imp if r['status'] == 'IMPEDIMENTO DEV')
    def jql_url(jql): return f'{BASE}/issues?jql=' + urllib.parse.quote(jql)
    nochat = 'AND (customfield_10073 is EMPTY OR customfield_10073 != "Chat de Suporte")'
    json.dump({
        'total': len(imp), 'produto': produto, 'dev': dev,
        'snapshot': str(datetime.date.today()),
        'url_all': jql_url(f'project = BUG AND status in ("IMPEDIMENTO DEV","IMPEDIMENTO PRODUTO") {nochat}'),
        'url_produto': jql_url(f'project = BUG AND status = "IMPEDIMENTO PRODUTO" {nochat}'),
        'url_dev': jql_url(f'project = BUG AND status = "IMPEDIMENTO DEV" {nochat}'),
    }, open('impedimentos_live.json', 'w'), ensure_ascii=False, indent=1)

    # 4) sobra_live.json (modo 'full': status -> mês -> qtde, pelos cards ATUALMENTE no status)
    STAT = ['Não Iniciado', 'Em Desenvolvimento', 'IMPEDIMENTO DEV', 'IMPEDIMENTO PRODUTO', 'Revert']
    full = {s: collections.Counter() for s in STAT}
    for r in live:
        if cancel(r):
            continue
        if r['status'] in STAT:
            cm = mm(r['created'])
            if cm:
                full[r['status']][cm] += 1
    json.dump({'full': {s: dict(sorted(full[s].items())) for s in STAT if full[s]}},
              open('sobra_live.json', 'w'), ensure_ascii=False, indent=1)

    # 5) ni_assignee.json — responsável dos cards "Não Iniciado"
    ni = {r['key']: r['assignee'] for r in live if r['status'] == 'Não Iniciado' and not cancel(r)}
    json.dump(ni, open('ni_assignee.json', 'w'), ensure_ascii=False, indent=1)

    print(f'  issues: {len(recs)} | sweep: {len(sweep)} | backlog meses: {len(jb)} | '
          f'impedimentos: {len(imp)} | NI: {len(ni)}')

if __name__ == '__main__':
    print('Puxando do Jira...')
    issues = fetch_all_com_retentativa()
    if not issues:
        raise RuntimeError(
            'O Jira retornou 0 issues do projeto BUG mesmo após retentativas — isso não é '
            'esperado (a base tem centenas de bugs). Abortando SEM sobrescrever sweep.json/'
            'jira_backlog.json/etc. Prováveis causas: JIRA_BASE_URL, JIRA_EMAIL ou '
            'JIRA_API_TOKEN inválidos/expirados, ou perda de permissão de acesso ao projeto '
            'BUG. Confira os segredos em Settings > Secrets and variables > Actions.'
        )
    recs = [norm(i) for i in issues]
    build_outputs(recs)
    print('OK — arquivos gerados.')
