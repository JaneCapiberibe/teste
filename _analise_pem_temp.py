"""
EXTRAÇÃO COMPLETA — projeto PEM (Produtos e Melhoria), 2024-2026, a pedido da Jane.

Só extrai e analisa — não escreve em sweep.json/dash_data.json nem em nenhum arquivo do
pipeline. Reaproveita fetch_jira.py (_auth_headers/BASE/fetch_changelogs/_first_to_epoch/
_epoch_iso), sem duplicar lógica de autenticação/changelog. Arquivo e workflow são temporários.

Puxa TODOS os issues do PEM (sem recorte de data — diferente do levantamento de schema
anterior, que usou só ~365 dias de amostra), com changelog completo, pra cobrir 2024/2025/2026
de verdade.
"""
import json, sys, collections, statistics, datetime, requests

sys.path.insert(0, '.')
import fetch_jira as fj

HEAD = fj._auth_headers()
BASE = fj.BASE

FIELDS = ['issuetype', 'status', 'resolution', 'created', 'assignee', 'summary',
          'customfield_10065', 'customfield_10066', 'customfield_10067', 'customfield_10073']

NAO_DEV_CONHECIDOS = {'Giovanna', 'Renato Canever'}

# CONFIRMADO via diagnóstico real (30/09/2026): "Concluído" NUNCA aparece como destino de
# transição no changelog do PEM inteiro — só "Done" (97 ocorrências). Mesmo fenômeno já
# documentado no BUG (rename de status não migrado no histórico: o changelog guarda o nome QUE
# EXISTIA no momento da transição, "Concluído" é só o nome atual do status). Mesma equivalência
# já usada em ST_ENTREGUE_FUNIL (gen_data.py) — reaproveitada aqui, não uma regra nova.
STATUS_CONCLUIDO = ('Concluído', 'Done', 'Concluido')


def linha(c='='):
    print(c * 84)


def fetch_all_full(jql):
    url = f'{BASE}/rest/api/3/search/jql'
    out, token = [], None
    while True:
        body = {'jql': jql, 'fields': FIELDS, 'maxResults': 100}
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


def modulos_de(f):
    mod = f.get('customfield_10065')
    if not mod:
        return []
    return [m.get('value') for m in mod if isinstance(m, dict) and m.get('value')]


def tem_origem_cliente(f):
    return bool(f.get('customfield_10066')) or bool(f.get('customfield_10067'))


linha()
print('EXTRAÇÃO — project = PEM, TODOS os issues (sem recorte de data)')
linha()
issues = fetch_all_full('project = PEM ORDER BY created ASC')
n_total = len(issues)
print(f'total de issues no projeto: {n_total}')

datas_criacao = [i['fields']['created'] for i in issues if i['fields'].get('created')]
data_mais_antiga = min(datas_criacao) if datas_criacao else None
print(f'card mais antigo (created): {data_mais_antiga}')
print('(ou seja: histórico é confiável a partir desse ponto — qualquer ano anterior a isso '
      'simplesmente não tem card nenhum, não é falta de cobertura da extração)')

print('\nBuscando changelog completo de todos os issues...')
ids = [i['id'] for i in issues]
changelogs, iniciais, _ = fj.fetch_changelogs(ids)
print(f'{sum(1 for iid in ids if changelogs.get(iid))}/{n_total} issues com changelog de status.')

by_id = {i['id']: i for i in issues}


def primeira_transicao(iid, status_nome):
    return fj._first_to_epoch(changelogs.get(iid) or [], status_nome)


# ==============================================================================
# DIAGNÓSTICO — "Concluído" nunca aparece como destino de transição? Suspeita de rename de
# status (mesmo problema já documentado no BUG: workflow criado em inglês, renomeado depois —
# o esquema do PEM tem "Selected for Development" ao lado de nomes em português, o que é
# exatamente esse padrão). Confirma com dado real antes de aplicar qualquer fallback.
# ==============================================================================
linha()
print('DIAGNÓSTICO — "Concluído" aparece no changelog como destino de transição?')
linha()
destinos_vistos = collections.Counter()
for i in issues:
    for _, to in (changelogs.get(i['id']) or []):
        destinos_vistos[to] += 1
print('Todos os valores "to" (destino) vistos no changelog de status do projeto inteiro:')
for to, c in destinos_vistos.most_common():
    print(f'  {to!r}: {c}')

print('\nCards com status ATUAL "Concluído" cujo changelog eu tenho, e o que aparece nele:')
cnt_diag = 0
for i in issues:
    if (i['fields'].get('status') or {}).get('name') != 'Concluído':
        continue
    chg = changelogs.get(i['id'])
    if not chg:
        continue
    destinos = [to for _, to in chg]
    tem_concluido_no_chg = any(s in destinos for s in STATUS_CONCLUIDO)
    if not tem_concluido_no_chg and cnt_diag < 8:
        print(f'  {i["key"]}: status atual=Concluído, mas changelog NÃO tem {STATUS_CONCLUIDO} '
              f'como destino — destinos reais: {destinos}  |  inicial: {iniciais.get(i["id"])}')
        cnt_diag += 1
if cnt_diag == 0:
    print(f'  (nenhum card com essa divergência — {STATUS_CONCLUIDO} bate certinho no changelog)')
print(f'\n=> CONFIRMADO: "Done" é o nome antigo de "Concluído" (rename de status não migrado no '
      f'histórico, mesmo fenômeno do BUG). Todo cálculo abaixo usa STATUS_CONCLUIDO={STATUS_CONCLUIDO}, '
      f'não só o literal "Concluído".')


# ==============================================================================
# DEFINIÇÃO DE "LANÇADO" — Concluído × Marketing e Lançamento
# ==============================================================================
linha()
print('DEFINIÇÃO DE "LANÇADO" — investigação Concluído × Marketing e Lançamento')
linha()

chegou_concluido = []
chegou_marketing = []
for i in issues:
    iid = i['id']
    ep_c = primeira_transicao(iid, STATUS_CONCLUIDO)
    ep_m = primeira_transicao(iid, 'Marketing e Lançamento')
    if ep_c is not None:
        chegou_concluido.append((i, ep_c))
    if ep_m is not None:
        chegou_marketing.append((i, ep_m))

set_c = {i['key'] for i, _ in chegou_concluido}
set_m = {i['key'] for i, _ in chegou_marketing}
so_c = set_c - set_m
so_m = set_m - set_c
ambos = set_c & set_m

print(f'Cards que já passaram por "Concluído" (algum momento): {len(set_c)}')
print(f'Cards que já passaram por "Marketing e Lançamento" (algum momento): {len(set_m)}')
print(f'  só Concluído (nunca chegou em Marketing e Lançamento): {len(so_c)}')
print(f'  só Marketing e Lançamento (nunca chegou em Concluído): {len(so_m)}')
print(f'  passaram pelos DOIS: {len(ambos)}')

antes_concl = antes_mkt = mesmo_instante = 0
exemplos_ordem = []
for i, ep_c in chegou_concluido:
    key = i['key']
    if key not in ambos:
        continue
    ep_m = dict((ii['key'], ep) for ii, ep in chegou_marketing)[key]
    if ep_c < ep_m:
        antes_concl += 1
        ordem = 'Concluído -> Marketing e Lançamento'
    elif ep_m < ep_c:
        antes_mkt += 1
        ordem = 'Marketing e Lançamento -> Concluído'
    else:
        mesmo_instante += 1
        ordem = '(mesmo instante)'
    if len(exemplos_ordem) < 6:
        exemplos_ordem.append((key, i['fields'].get('summary', '')[:60], ordem,
                                fj._epoch_iso(ep_c), fj._epoch_iso(ep_m)))

print(f'\nDos {len(ambos)} que passaram pelos dois:')
print(f'  Concluído ANTES de Marketing e Lançamento: {antes_concl}')
print(f'  Marketing e Lançamento ANTES de Concluído: {antes_mkt}')
print(f'  mesmo instante (mudança em lote): {mesmo_instante}')
print('\nExemplos reais (key, resumo, ordem, data Concluído, data Marketing e Lançamento):')
for key, resumo, ordem, dc, dm in exemplos_ordem:
    print(f'  {key} ({resumo}): {ordem}')
    print(f'      Concluído: {dc}  |  Marketing e Lançamento: {dm}')

print(f'\nExemplos de cards que só chegaram em "Concluído" (nunca "Marketing e Lançamento"):')
for i, ep_c in chegou_concluido[:3]:
    if i['key'] in so_c:
        print(f'  {i["key"]} ({i["fields"].get("summary","")[:60]}) — tipo: '
              f'{(i["fields"].get("issuetype") or {}).get("name")} — status atual: '
              f'{(i["fields"].get("status") or {}).get("name")}')

print(f'\nExemplos de cards que só chegaram em "Marketing e Lançamento" (nunca "Concluído"):')
cnt = 0
for i, ep_m in chegou_marketing:
    if i['key'] in so_m:
        print(f'  {i["key"]} ({i["fields"].get("summary","")[:60]}) — tipo: '
              f'{(i["fields"].get("issuetype") or {}).get("name")} — status atual: '
              f'{(i["fields"].get("status") or {}).get("name")}')
        cnt += 1
        if cnt >= 3:
            break

print('\n--- PROPOSTA (a confirmar com a Jane) ---')
print('  "lançado" = 1ª transição pra "Marketing e Lançamento"; PRA CARDS QUE NUNCA CHEGAM LÁ,')
print('  fallback pra 1ª transição pra "Concluído" (mesmo espírito do concluido_mes de BUG: ')
print('  usa o sinal mais forte disponível, sem deixar o card de fora só por falta do passo ideal).')
print('  Reporto os 3 recortes abaixo lado a lado pra você decidir:')
print('    (A) só Marketing e Lançamento (ignora quem não chegou lá)')
print('    (B) PROPOSTA — Marketing e Lançamento, fallback Concluído')
print('    (C) só Concluído (ignora Marketing e Lançamento)')


def data_lancado_A(i):
    ep = primeira_transicao(i['id'], 'Marketing e Lançamento')
    return fj._epoch_iso(ep) if ep is not None else None


def data_lancado_B(i):
    ep = primeira_transicao(i['id'], 'Marketing e Lançamento')
    if ep is None:
        ep = primeira_transicao(i['id'], STATUS_CONCLUIDO)
    return fj._epoch_iso(ep) if ep is not None else None


def data_lancado_C(i):
    ep = primeira_transicao(i['id'], STATUS_CONCLUIDO)
    return fj._epoch_iso(ep) if ep is not None else None


# ==============================================================================
# EXCLUSÃO Won't Do — confirmar com exemplos antes
# ==============================================================================
linha()
print('EXCLUSÃO — resolution == "Won\'t Do"')
linha()
wontdo = [i for i in issues if (i['fields'].get('resolution') or {}).get('name') == "Won't Do"]
print(f'{len(wontdo)} card(s) com resolution "Won\'t Do":')
for i in wontdo[:5]:
    f = i['fields']
    print(f'  {i["key"]} ({f.get("summary","")[:70]}) — tipo: {(f.get("issuetype") or {}).get("name")} '
          f'— status atual: {(f.get("status") or {}).get("name")}')
print('=> Cards com decisão explícita de "não vamos fazer" — mesmo espírito de Cancelado QA/Dev '
      '(não é trabalho real entregue). Excluídos das contagens abaixo.')

issues_validos = [i for i in issues if (i['fields'].get('resolution') or {}).get('name') != "Won't Do"]


# ==============================================================================
# 1) VOLUME LANÇADO — 2024/2025/2026
# ==============================================================================
linha()
print('1) VOLUME LANÇADO POR ANO E TIPO (3 definições lado a lado)')
linha()

ANOS = ['2024', '2025', '2026']


def tabela_volume(fn_data):
    tab = collections.defaultdict(lambda: collections.Counter())
    for i in issues_validos:
        d = fn_data(i)
        if not d:
            continue
        ano = d[:4]
        tipo = (i['fields'].get('issuetype') or {}).get('name')
        tab[ano][tipo] += 1
        tab[ano]['TOTAL'] += 1
    return tab


for nome, fn in [('(A) só Marketing e Lançamento', data_lancado_A),
                  ('(B) PROPOSTA: Mkt+Lançamento c/ fallback Concluído', data_lancado_B),
                  ('(C) só Concluído', data_lancado_C)]:
    print(f'\n--- {nome} ---')
    tab = tabela_volume(fn)
    for ano in ANOS + sorted(set(tab) - set(ANOS)):
        if ano not in tab:
            continue
        c = tab[ano]
        print(f'  {ano}: TOTAL={c["TOTAL"]}  |  Melhoria={c.get("Melhoria",0)}  '
              f'Nova função={c.get("Nova função",0)}  Epic={c.get("Epic",0)}')

print(f'\nAVISO DE COBERTURA: card mais antigo do projeto é de {data_mais_antiga} — se isso cair '
      f'dentro de 2024, o ano de 2024 pode estar incompleto (não por limite da extração, que '
      f'agora pegou TODO o histórico do projeto, mas porque o projeto pode ter começado a ser '
      f'usado de verdade só em algum ponto de 2024).')


# ==============================================================================
# 2) LANÇAMENTOS POR MÓDULO
# ==============================================================================
linha()
print('2) LANÇAMENTOS POR MÓDULO (customfield_10065), por ano — usando a definição (B) proposta')
linha()
mod_ano = collections.defaultdict(lambda: collections.Counter())
sem_modulo_ano = collections.Counter()
for i in issues_validos:
    d = data_lancado_B(i)
    if not d:
        continue
    ano = d[:4]
    mods = modulos_de(i['fields'])
    if not mods:
        sem_modulo_ano[ano] += 1
        continue
    for m in mods:
        mod_ano[ano][m] += 1

for ano in ANOS:
    print(f'\n{ano}:')
    for m, c in mod_ano[ano].most_common():
        print(f'  {m}: {c}')
    print(f'  (sem módulo preenchido): {sem_modulo_ano.get(ano,0)}')


# ==============================================================================
# 3) EVOLUÇÃO MENSAL 2024-2026 — usando definição (B)
# ==============================================================================
linha()
print('3) EVOLUÇÃO MENSAL (Jan/24 até hoje) — total e por tipo, definição (B)')
linha()
mensal = collections.defaultdict(lambda: collections.Counter())
for i in issues_validos:
    d = data_lancado_B(i)
    if not d:
        continue
    ym = d[:7]
    tipo = (i['fields'].get('issuetype') or {}).get('name')
    mensal[ym]['TOTAL'] += 1
    mensal[ym][tipo] += 1

for ym in sorted(mensal):
    c = mensal[ym]
    print(f'  {ym}: TOTAL={c["TOTAL"]:3d}  Melhoria={c.get("Melhoria",0):2d}  '
          f'Nova função={c.get("Nova função",0):2d}  Epic={c.get("Epic",0):2d}')


# ==============================================================================
# 4) RANKING "QUEM SUBIU MAIS FEATURE"
# ==============================================================================
linha()
print('4) RANKING POR ASSIGNEE — definição (B), por ano')
linha()

flagged = collections.defaultdict(list)
for i in issues_validos:
    d = data_lancado_B(i)
    if not d:
        continue
    a = (i['fields'].get('assignee') or {}).get('displayName')
    if a in NAO_DEV_CONHECIDOS:
        flagged[a].append((i['key'], (i['fields'].get('issuetype') or {}).get('name'), d[:4]))

for nome in NAO_DEV_CONHECIDOS:
    if flagged[nome]:
        print(f'\nAVISO: {nome} (identificada como não-dev) aparece como assignee de '
              f'{len(flagged[nome])} item(ns) lançado(s) — NÃO excluída automaticamente, listada '
              f'abaixo pra você decidir se entra no ranking:')
        for key, tipo, ano in flagged[nome]:
            print(f'    {key} ({tipo}, {ano})')
    else:
        print(f'\n{nome}: nenhum item lançado como assignee — excluída do ranking normalmente.')

print('\n--- (4a) Ranking só "Nova função" lançada, por ano ---')
rank_a = collections.defaultdict(lambda: collections.Counter())
for i in issues_validos:
    if (i['fields'].get('issuetype') or {}).get('name') != 'Nova função':
        continue
    d = data_lancado_B(i)
    if not d:
        continue
    a = (i['fields'].get('assignee') or {}).get('displayName')
    if not a or a in NAO_DEV_CONHECIDOS:
        continue
    rank_a[d[:4]][a] += 1
for ano in ANOS:
    print(f'\n{ano}:')
    for a, c in rank_a[ano].most_common():
        print(f'  {a}: {c}')

print('\n--- (4b) Ranking TODOS os tipos lançados, por ano ---')
rank_b = collections.defaultdict(lambda: collections.Counter())
for i in issues_validos:
    d = data_lancado_B(i)
    if not d:
        continue
    a = (i['fields'].get('assignee') or {}).get('displayName')
    if not a or a in NAO_DEV_CONHECIDOS:
        continue
    rank_b[d[:4]][a] += 1
for ano in ANOS:
    print(f'\n{ano}:')
    for a, c in rank_b[ano].most_common():
        print(f'  {a}: {c}')


# ==============================================================================
# 5) OUTRAS INFORMAÇÕES
# ==============================================================================
linha()
print('5) OUTRAS INFORMAÇÕES')
linha()

print('\n--- (5a) Tempo médio "Aprovado Produto" -> lançamento (dias corridos), por tipo ---')
tempos = collections.defaultdict(list)
for i in issues_validos:
    d = data_lancado_B(i)
    if not d:
        continue
    ep_ap = primeira_transicao(i['id'], 'Aprovado Produto')
    if ep_ap is None:
        continue
    ep_lanc = primeira_transicao(i['id'], 'Marketing e Lançamento')
    if ep_lanc is None:
        ep_lanc = primeira_transicao(i['id'], STATUS_CONCLUIDO)
    if ep_lanc is None or ep_lanc < ep_ap:
        continue
    dias = (ep_lanc - ep_ap) / 86400
    tipo = (i['fields'].get('issuetype') or {}).get('name')
    tempos[tipo].append(dias)
for tipo, vals in tempos.items():
    print(f'  {tipo}: mediana={statistics.median(vals):.1f}d  média={statistics.mean(vals):.1f}d  n={len(vals)}')
if not tempos:
    print('  (nenhum card com as duas transições registradas — sem dado suficiente)')

print('\n--- (5b) Origem cliente identificável (customfield_10066/10067) — lançados ---')
com_cliente = sem_cliente = 0
exemplos_cliente = []
for i in issues_validos:
    d = data_lancado_B(i)
    if not d:
        continue
    if tem_origem_cliente(i['fields']):
        com_cliente += 1
        if len(exemplos_cliente) < 3:
            exemplos_cliente.append(i['key'])
    else:
        sem_cliente += 1
print(f'  com origem de cliente identificável: {com_cliente}')
print(f'  sem origem de cliente (iniciativa interna, aparente): {sem_cliente}')
print(f'  exemplos com cliente: {exemplos_cliente}')

print('\n--- (5c) Concentração por módulo (todos os anos juntos, definição B) ---')
mod_total = collections.Counter()
for ano in ANOS:
    mod_total.update(mod_ano[ano])
for m, c in mod_total.most_common():
    print(f'  {m}: {c}')

linha()
print('FIM DA EXTRAÇÃO')
linha()
