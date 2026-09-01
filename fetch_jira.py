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

def _auth_headers():
    email = os.environ['JIRA_EMAIL']
    token_ = os.environ['JIRA_API_TOKEN']
    auth = 'Basic ' + base64.b64encode(f'{email}:{token_}'.encode()).decode()
    return {'Authorization': auth, 'Accept': 'application/json', 'Content-Type': 'application/json'}

def fetch_all():
    """Puxa todos os issues do projeto BUG, paginando com nextPageToken. O endpoint
    /search/jql NÃO aceita expand=changelog (dá 400 "Invalid request payload" mesmo com
    maxResults baixo) — o changelog é buscado à parte, em lote, por fetch_changelogs()."""
    HEAD = _auth_headers()
    url = f'{BASE}/rest/api/3/search/jql'
    out, token = [], None
    while True:
        body = {'jql': 'project = BUG ORDER BY created ASC', 'fields': FIELDS, 'maxResults': 100}
        if token:
            body['nextPageToken'] = token
        r = requests.post(url, headers=HEAD, data=json.dumps(body), timeout=60)
        if not r.ok:
            print(f'Jira respondeu {r.status_code}: {r.text[:2000]}')
        r.raise_for_status()
        data = r.json()
        out.extend(data.get('issues', []))
        token = data.get('nextPageToken')
        if not token:
            break
    return out

def fetch_changelogs(issue_ids):
    """Busca o histórico de status de todos os issues via o endpoint dedicado de changelog em
    lote (/changelog/bulkfetch) — usado pela régua oficial de Evolução por módulo (concluído =
    1ª entrada em "Em produção"). Se o endpoint falhar por qualquer motivo (ex.: mudança de
    contrato da API), avisa e devolve {} — o pipeline segue rodando sem essa régua (fica
    None/False pra todo mundo) em vez de derrubar o update inteiro."""
    HEAD = _auth_headers()
    url = f'{BASE}/rest/api/3/changelog/bulkfetch'
    ids = [i for i in issue_ids if i]
    out = {}
    try:
        BATCH = 200
        for i in range(0, len(ids), BATCH):
            batch = ids[i:i + BATCH]
            token = None
            while True:
                body = {'issueIdsOrKeys': batch}
                if token:
                    body['nextPageToken'] = token
                r = requests.post(url, headers=HEAD, data=json.dumps(body), timeout=60)
                if not r.ok:
                    print(f'changelog/bulkfetch respondeu {r.status_code}: {r.text[:2000]}')
                r.raise_for_status()
                data = r.json()
                for ic in data.get('issueChangeLogs', []):
                    iid = ic.get('issueId')
                    hist = ic.get('changeHistories') or ic.get('histories') or []
                    changes = []
                    for h in hist:
                        ep = _to_epoch(h.get('created'))
                        for item in h.get('items', []):
                            if item.get('field') == 'status':
                                changes.append((ep, item.get('toString')))
                    changes.sort(key=lambda x: x[0] if x[0] is not None else 0)
                    out[iid] = changes
                token = data.get('nextPageToken')
                if not token:
                    break
    except Exception as e:
        print(f'aviso: falha ao buscar changelog em lote ({e}) — seguindo sem concluido_mes '
              f'(a Evolução por módulo fica sem dado de concluídos até o próximo run).')
        return {}
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

# ---- RÉGUA OFICIAL de Evolução por módulo (definida com o setor de desenvolvimento,
# evolucao_bugs.py de referência — atualizada 27/08/2026) ----
# Concluído = mês da 1ª transição do card para "Em produção" (fallback: 1ª transição p/
# "Done"/"Concluído"; fallback final: mês de criação, se o card já está terminal mas o
# changelog não tem a transição registrada). NÃO é a resolutiondate — o Jira deixa esse
# campo vazio boa parte da base. Precisa do changelog (histórico de status) de cada issue.
# "Em produção"/"Done"/"Concluído" convivem com variações de grafia no changelog.
ST_PRODUCAO = ('Em produção', 'Em Produção')
ST_DONE = ('Done', 'Concluído', 'Concluido')
ST_IMP_PRODUTO = 'IMPEDIMENTO PRODUTO'
TZ_BR = datetime.timezone(datetime.timedelta(hours=-3))

def _to_epoch(dt):
    """Normaliza o 'created' de um item do changelog pra epoch (segundos, float) — o
    /changelog/bulkfetch devolve epoch millis (int), diferente do changelog clássico
    embutido no /search (string ISO). Aceita os dois formatos."""
    if dt is None:
        return None
    if isinstance(dt, (int, float)):
        return dt / 1000
    if isinstance(dt, str):
        try:
            return datetime.datetime.fromisoformat(dt).timestamp()
        except ValueError:
            return None
    return None

def _epoch_month(ep):
    if ep is None:
        return None
    return datetime.datetime.fromtimestamp(ep, tz=TZ_BR).strftime('%Y-%m')

def _first_to(changes, status_names):
    """Mês (YYYY-MM) da 1ª transição PARA qualquer nome em `status_names` (string ou tupla).
    `changes` é uma lista de (epoch_segundos, status_destino) já ordenada por _to_epoch."""
    names = (status_names,) if isinstance(status_names, str) else tuple(status_names)
    for ep, to in changes:
        if to in names and ep:
            return _epoch_month(ep)
    return None

def _concluido_mes(status, created, changes):
    """Mês de conclusão pela régua oficial: 1ª entrada em produção; fallback 1ª entrada em
    Done/Concluído; fallback final: mês de criação, pra card já terminal cujo changelog não
    tem a transição registrada."""
    mes = _first_to(changes, ST_PRODUCAO)
    if not mes:
        mes = _first_to(changes, ST_DONE)
        if not mes and status in (ST_PRODUCAO + ST_DONE):
            mes = mm(created)
    return mes

def norm(issue, changes=None):
    f = issue.get('fields', {})
    def name(x): return (x or {}).get('value') if isinstance(x, dict) and 'value' in (x or {}) else ((x or {}).get('name') if isinstance(x, dict) else None)
    mod = f.get('customfield_10073')
    assignee = (f.get('assignee') or {}).get('displayName') or 'Sem responsável'
    status = name(f.get('status'))
    created = f.get('created')
    changes = changes or []
    return {
        'key': issue.get('key'),
        'status': status,
        'prio': name(f.get('priority')),
        'itype': name(f.get('issuetype')),
        'res': name(f.get('resolution')),
        'created': created,
        'resolved': f.get('resolutiondate'),
        'updated': f.get('updated'),
        'timespent': f.get('timespent') if f.get('timespent') is not None else f.get('aggregatetimespent'),
        'modulo': (mod or {}).get('value') if isinstance(mod, dict) else mod,
        'assignee': assignee,
        'concluido_mes': _concluido_mes(status, created, changes),
    }

def mm(iso):
    return iso[:7] if iso else None  # 'YYYY-MM'

CHAT = 'Chat de Suporte'
def modclean(m):
    import re
    return 'Não classificado' if not m else re.sub(r'^\d+\s*-\s*', '', str(m)).strip()

def build_outputs(recs):
    # 1) sweep.json (formato do gen_data)
    sweep = [{k: r[k] for k in ('key', 'status', 'prio', 'itype', 'res', 'created', 'resolved', 'timespent',
              'modulo', 'concluido_mes')} for r in recs]
    json.dump(sweep, open('sweep.json', 'w'), ensure_ascii=False)

    def ischat(r): return modclean(r['modulo']) == CHAT
    def cancel(r): return r['res'] == 'Cancelado QA'
    live = [r for r in recs if not ischat(r)]  # tira Chat de Suporte de tudo

    # 2) jira_backlog.json — método do Diego
    # "Concluído" usa concluido_mes (1ª entrada em "Em produção" via changelog — a mesma
    # régua oficial de evolucao_bugs.py/_concluido_mes acima), NUNCA `updated`. `updated`
    # muda a cada edição tardia do card (comentário, link, anexo, campo) mesmo muito depois
    # da conclusão real, o que vazava bugs pro mês da edição em vez do mês real de conclusão
    # (bug confirmado, ex.: card concluído em novembro reaparecendo como concluído em abril
    # só por causa de uma edição naquele mês).
    criados = collections.Counter()
    concl = collections.Counter()
    for r in live:
        if cancel(r):
            continue
        cm = mm(r['created'])
        if cm and r['status'] != 'IMPEDIMENTO PRODUTO':
            criados[cm] += 1
        if r['concluido_mes']:
            concl[r['concluido_mes']] += 1
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
    print('Puxando changelog (histórico de status) em lote...')
    changelogs = fetch_changelogs([i.get('id') for i in issues])
    recs = [norm(i, changelogs.get(i.get('id'))) for i in issues]

    # DIAGNÓSTICO TEMPORÁRIO — investigação pontual do BUG-1072 (relatado como ausente do
    # resultado do JQL/dashboard de jan/2026). Remover depois de investigado.
    _dbg_issue = next((i for i in issues if i.get('key') == 'BUG-1072'), None)
    print(f'  [diag BUG-1072] presente em issues(): {_dbg_issue is not None}')
    if _dbg_issue:
        _dbg_id = _dbg_issue.get('id')
        _dbg_chg = changelogs.get(_dbg_id)
        print(f'  [diag BUG-1072] id={_dbg_id} presente em changelogs(): {_dbg_id in changelogs} '
              f'| nº transições capturadas: {len(_dbg_chg) if _dbg_chg else 0}')
        if _dbg_chg:
            print(f'  [diag BUG-1072] transições: {_dbg_chg}')
        _dbg_rec = next((r for r in recs if r['key'] == 'BUG-1072'), None)
        print(f'  [diag BUG-1072] rec: status={_dbg_rec["status"]!r} itype={_dbg_rec["itype"]!r} '
              f'res={_dbg_rec["res"]!r} modulo={_dbg_rec["modulo"]!r} '
              f'concluido_mes={_dbg_rec["concluido_mes"]!r}')

    build_outputs(recs)
    print('OK — arquivos gerados.')
