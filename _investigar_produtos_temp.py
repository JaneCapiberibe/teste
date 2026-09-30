"""
LEVANTAMENTO DE SCHEMA — projeto(s) de "Produtos e Melhoria", a pedido da Jane.

Diferente dos levantamentos anteriores (BACKOFFICE, SUS — Kanbans exclusivos de dev, mesmo
workflow do BUG), este projeto é COMPARTILHADO com o time de Produto e a chave/estrutura não
são conhecidas de antemão. Passo 0 lista os projetos do Jira e escolhe candidato(s) por
palavra-chave; passos 1-2 investigam a estrutura de cada candidato encontrado.

Só investiga — não escreve em sweep.json/dash_data.json nem em nenhum arquivo do pipeline.
Reaproveita fetch_jira.py (_auth_headers/BASE/FIELDS/fetch_all/fetch_changelogs), sem duplicar
lógica de autenticação/paginação. Arquivo e workflow são temporários.
"""
import json, os, sys, collections, requests

sys.path.insert(0, '.')
import fetch_jira as fj

HEAD = fj._auth_headers()
BASE = fj.BASE

JANELA_DIAS = 365  # amostra pra investigar estrutura — mais larga que SUS (180d) porque um
                    # board de produto pode ter ciclo mais lento (discovery/priorização).

KEYWORDS = ['produt', 'melhor', 'feature', 'discovery', 'ideia', 'roadmap']

# status já conhecidos do workflow de dev (BUG/BACKOFFICE/SUS — idêntico nos três, confirmado
# nos levantamentos anteriores) — usado como "régua" pra separar status de produto (desconhecidos)
# de status de dev (já mapeados) na hipótese do passo 1c.
STATUS_DEV_CONHECIDOS = {
    'Não Iniciado', 'Backlog', 'Em Desenvolvimento', 'Revisão QA', 'Aprovado QA', 'Reprovado QA',
    'Merge Request', 'IMPEDIMENTO DEV', 'IMPEDIMENTO PRODUTO', 'Revert',
    'Em produção', 'Em Produção', 'Done', 'Concluído', 'Concluido',
}


def get_json(path, params=None):
    r = requests.get(f'{BASE}{path}', headers=HEAD, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def linha(c='='):
    print(c * 78)


def contar_issues(jql):
    """Tenta o endpoint clássico (barato, só total). Se não existir/estiver desligado nesta
    instância, cai pra paginar /search/jql pedindo só 'key' (mais caro, mas funciona sempre)."""
    try:
        r = requests.get(f'{BASE}/rest/api/3/search', headers=HEAD,
                          params={'jql': jql, 'maxResults': 0}, timeout=60)
        if r.ok and 'total' in r.json():
            return r.json()['total']
    except Exception:
        pass
    issues = fj.fetch_all(jql=jql)
    return len(issues)


# ==============================================================================
# PASSO 0 — listar projetos e identificar candidato(s)
# ==============================================================================
linha()
print('PASSO 0 — projetos disponíveis no Jira')
linha()

projetos = []
start = 0
while True:
    data = get_json('/rest/api/3/project/search', params={'startAt': start, 'maxResults': 50,
                                                            'expand': 'description'})
    projetos.extend(data.get('values', []))
    if data.get('isLast', True):
        break
    start += 50

print(f'{len(projetos)} projeto(s) no total.\n')

candidatos = []
for p in projetos:
    nome = p.get('name', '')
    chave = p.get('key', '')
    desc = p.get('description') or ''
    alvo = f'{nome} {chave} {desc}'.lower()
    if any(kw in alvo for kw in KEYWORDS):
        candidatos.append(p)

print('Todos os projetos (nome — key — tipo):')
for p in sorted(projetos, key=lambda x: x.get('key', '')):
    marca = '  <<< CANDIDATO' if p in candidatos else ''
    print(f"  {p.get('key',''):10s} {p.get('name',''):40s} {p.get('projectTypeKey','')}{marca}")

print()
print(f'{len(candidatos)} candidato(s) por palavra-chave ({KEYWORDS}):')
for p in candidatos:
    key = p['key']
    n = contar_issues(f'project = {key}')
    print(f"  {key} — {p.get('name')}")
    print(f"    descrição: {p.get('description') or '(sem descrição)'}")
    print(f"    tipo: {p.get('projectTypeKey')} | estilo: {p.get('style')}")
    print(f"    issues (total, sem filtro de data): {n}")
    print()

if not candidatos:
    print('NENHUM candidato encontrado por palavra-chave — ver lista completa de projetos acima '
          'pra escolher manualmente. Parando aqui (passos 1-2 não têm o que investigar).')
    sys.exit(0)

if len(candidatos) > 3:
    print(f'Mais de 3 candidatos plausíveis ({len(candidatos)}) — listados acima pra confirmação '
          'antes de aprofundar. Parando aqui.')
    sys.exit(0)


# ==============================================================================
# PASSOS 1-2 — estrutura de cada candidato
# ==============================================================================
field_meta = get_json('/rest/api/3/field')
id2name = {fm['id']: fm['name'] for fm in field_meta}

# assignees já conhecidos (BUG/BACKOFFICE/SUS) pra comparação do passo 2a
conhecidos_assignee = set()
for fname in ('sweep.json', 'sweep_backoffice.json', 'sweep_sus.json'):
    if os.path.exists(fname):
        for x in json.load(open(fname)):
            if x.get('assignee'):
                conhecidos_assignee.add(x['assignee'])

JA_CONHECIDOS_FIELDS = set(fj.FIELDS) | {
    'summary', 'description', 'project', 'reporter', 'creator', 'labels', 'comment',
    'attachment', 'issuelinks', 'subtasks', 'fixVersions', 'versions', 'components',
    'duedate', 'worklog', 'watches', 'votes', 'parent', 'progress', 'workratio',
    'lastViewed', 'environment', 'security', 'issuerestriction', 'statuscategorychangedate',
}


def investigar_projeto(key, nome):
    linha()
    print(f'PROJETO {key} — {nome}')
    linha()

    try:
        statuses_meta = get_json(f'/rest/api/3/project/{key}/statuses')
        print('\n--- (1a) Esquema de workflow — status POSSÍVEIS por issue type ---')
        for it in statuses_meta:
            nomes = ', '.join(s['name'] for s in it['statuses'])
            print(f"  {it['name']}: {nomes}")
    except Exception as e:
        print(f'erro ao buscar /project/{key}/statuses: {e}')

    jql = f'project = {key} AND created >= -{JANELA_DIAS}d'
    print(f"\n--- Amostra: issues de {key} criados nos últimos ~{JANELA_DIAS} dias ---")
    issues = fj.fetch_all(jql=jql + ' ORDER BY created DESC')
    n = len(issues)
    print(f'total na amostra: {n}')
    if not n:
        print('NENHUM issue na janela — projeto pode ter baixíssima atividade recente. '
              'Pulando o resto da investigação deste projeto.')
        return

    tipo_cnt = collections.Counter()
    status_cnt = collections.Counter()
    res_cnt = collections.Counter()
    assignee_cnt = collections.Counter()
    reporter_cnt = collections.Counter()
    sem_assignee = 0
    timespent_preenchido = 0
    modulo_preenchido = 0
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
        rep = f.get('reporter')
        if rep:
            reporter_cnt[rep.get('displayName') or '(sem nome)'] += 1
        ts = f.get('timespent') if f.get('timespent') is not None else f.get('aggregatetimespent')
        if ts:
            timespent_preenchido += 1
        mod = f.get('customfield_10073')
        if mod:
            modulo_preenchido += 1

    print('\n--- (1a) TIPOS DE ISSUE (uso real na amostra) ---')
    for k, v in tipo_cnt.most_common():
        print(f'  {k}: {v}')

    print('\n--- (1b) STATUS (uso real na amostra) ---')
    for k, v in status_cnt.most_common():
        fase = 'DEV (já conhecido)' if k in STATUS_DEV_CONHECIDOS else 'DESCONHECIDO (produto?)'
        print(f'  {k}: {v}  [{fase}]')

    # (1c) hipótese: um fluxo só (produto -> dev) ou dois grupos sem relação?
    # Busca changelog de TODA a amostra e verifica, por issue, quais "fases" (DEV vs
    # DESCONHECIDO/produto) aparecem no histórico completo (status inicial + todas as
    # transições) — não só o status atual.
    print('\n--- (1c) Hipótese de fluxo (changelog completo da amostra) ---')
    ids = [i['id'] for i in issues]
    changelogs, iniciais, _ = fj.fetch_changelogs(ids)
    so_dev = so_prod = ambas = 0
    tipo_x_fase = collections.defaultdict(lambda: collections.Counter())
    exemplos_cruzam = []
    for i in issues:
        iid = i['id']
        f = i['fields']
        status_atual = (f.get('status') or {}).get('name')
        tipo = (f.get('issuetype') or {}).get('name')
        hist_status = {iniciais.get(iid)} if iniciais.get(iid) else set()
        hist_status.add(status_atual)
        for _, to in (changelogs.get(iid) or []):
            hist_status.add(to)
        hist_status.discard(None)
        fases = {('DEV' if s in STATUS_DEV_CONHECIDOS else 'PRODUTO') for s in hist_status}
        if fases == {'DEV'}:
            so_dev += 1
            tipo_x_fase[tipo]['só DEV'] += 1
        elif fases == {'PRODUTO'}:
            so_prod += 1
            tipo_x_fase[tipo]['só PRODUTO'] += 1
        else:
            ambas += 1
            tipo_x_fase[tipo]['cruzou as duas'] += 1
            if len(exemplos_cruzam) < 5:
                exemplos_cruzam.append((i['key'], tipo, sorted(hist_status)))

    print(f'  Cards cujo histórico de status passou só por status DEV: {so_dev}/{n}')
    print(f'  Cards cujo histórico de status passou só por status DESCONHECIDO/produto: {so_prod}/{n}')
    print(f'  Cards cujo histórico CRUZOU as duas fases (produto -> dev, no mesmo card): {ambas}/{n}')
    print('\n  Quebra por issue type:')
    for tipo, cnt in tipo_x_fase.items():
        print(f'    {tipo}: {dict(cnt)}')
    if exemplos_cruzam:
        print('\n  Exemplos de cards que cruzaram as duas fases (key, tipo, status visitados):')
        for k, t, hs in exemplos_cruzam:
            print(f'    {k} ({t}): {hs}')
    if ambas / n > 0.3:
        print('\n  => EVIDÊNCIA aponta pra "um fluxo só": muitos cards passam de status de '
              'produto pra status de dev dentro do MESMO card.')
    elif ambas / n < 0.05:
        print('\n  => EVIDÊNCIA aponta pra "dois grupos sem relação direta": quase nenhum card '
              'cruza as duas fases — produto e dev parecem trabalhar populações DIFERENTES de '
              'cards dentro do mesmo projeto.')
    else:
        print('\n  => Resultado MISTO — nem claramente um fluxo único, nem claramente dois '
              'grupos isolados. Ver exemplos acima.')

    print('\n--- (2a) ASSIGNEE ---')
    print(f'  preenchido: {n - sem_assignee}/{n}  |  sem responsável: {sem_assignee}/{n}')
    print(f'  pessoas distintas: {len(assignees)}')
    for k, v in assignee_cnt.most_common(30):
        print(f'    {k}: {v}')
    comuns = assignees & conhecidos_assignee
    exclusivos = assignees - conhecidos_assignee
    print(f'  já conhecidas de BUG/BACKOFFICE/SUS: {len(comuns)} -> {sorted(comuns)}')
    print(f'  NOVAS (não aparecem em BUG/BACKOFFICE/SUS — possíveis PMs/produto): '
          f'{len(exclusivos)} -> {sorted(exclusivos)}')
    print(f'\n  REPORTER (pra comparar com assignee — pode ser quem abriu vs quem executa):')
    for k, v in reporter_cnt.most_common(15):
        marca = ' (também é assignee de algum card)' if k in assignees else ''
        print(f'    {k}: {v}{marca}')

    print(f'\n--- (2b) RESOLUTION ---')
    for k, v in res_cnt.most_common():
        print(f'  {k}: {v}')

    print(f'\n--- (2c) TIMESPENT/AGGREGATETIMESPENT ---')
    pct = 100 * timespent_preenchido / n
    print(f'  preenchido em {timespent_preenchido}/{n} ({pct:.1f}%)')

    print(f'\n--- (2d) CHANGELOG ---')
    com_changelog = sum(1 for iid in ids if changelogs.get(iid))
    print(f'  {com_changelog}/{n} issues da amostra têm >=1 transição de status no changelog '
          f'(mesmo endpoint /changelog/bulkfetch já usado em BUG/BACKOFFICE/SUS)')

    print(f'\n--- (2e) customfield_10073 ("Módulo" do BUG) ---')
    print(f'  preenchido em {modulo_preenchido}/{n} issues')

    print(f'\n--- (2f) SCAN BRUTO DE CAMPOS (fields=*all) — priorização/RICE/OKR/story points/etc ---')
    body = {'jql': jql, 'fields': ['*all'], 'maxResults': 50}
    r = requests.post(f'{BASE}/rest/api/3/search/jql', headers=HEAD, data=json.dumps(body), timeout=60)
    r.raise_for_status()
    raw_issues = r.json().get('issues', [])
    presente = collections.Counter()
    exemplo = {}
    for ri in raw_issues:
        for fid, val in ri.get('fields', {}).items():
            if val in (None, [], {}):
                continue
            presente[fid] += 1
            if fid not in exemplo:
                exemplo[fid] = val
    novos = sorted((fid for fid in presente if fid not in JA_CONHECIDOS_FIELDS), key=lambda f: -presente[f])
    print(f'  (amostra de {len(raw_issues)} issues) — {len(novos)} campo(s) fora da whitelist BUG/BACKOFFICE/SUS:')
    for fid in novos:
        nome_campo = id2name.get(fid, '???')
        pct2 = 100 * presente[fid] / len(raw_issues) if raw_issues else 0
        ex_str = json.dumps(exemplo[fid], ensure_ascii=False)[:200]
        print(f'    {fid}  ({nome_campo})  — {presente[fid]}/{len(raw_issues)} ({pct2:.0f}%)')
        print(f'        exemplo: {ex_str}')


for p in candidatos:
    investigar_projeto(p['key'], p.get('name', ''))

linha()
print('FIM DO LEVANTAMENTO')
linha()
