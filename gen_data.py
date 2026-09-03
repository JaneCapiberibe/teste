import json, re, datetime, statistics, collections, csv, openpyxl
TODAY=datetime.date.today()
TZ_BR=datetime.timezone(datetime.timedelta(hours=-3))
AGORA_BR=datetime.datetime.now(tz=TZ_BR)
sweep=json.load(open('sweep.json'))
def pdt(s):
    if not s: return None
    return datetime.datetime.fromisoformat(s)  # handles offset
def mn(m): return 'Não classificado' if not m else re.sub(r'^\d+\s*-\s*','',str(m)).strip()
def busdays(a,b):
    import numpy as np
    return int(np.busday_count(a,b))
import numpy as np
def snapshot_arquivo(path):
    """Data em que `path` foi realmente atualizado pela última vez. Usa `git log` (a data do
    último commit que tocou o arquivo) em vez de os.path.getmtime — `actions/checkout` reseta o
    mtime de todo arquivo pro momento do checkout, então getmtime mostraria "hoje" em todo run
    do workflow, mesmo se o CSV não muda há meses. Cai pra getmtime só se não for um repo git."""
    import subprocess
    try:
        out=subprocess.run(['git','log','-1','--format=%ad','--date=short','--',path],
                            capture_output=True,text=True,timeout=5)
        if out.returncode==0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    try:
        import os as _os
        return datetime.date.fromtimestamp(_os.path.getmtime(path)).isoformat()
    except Exception:
        return None
NIVEL={'Highest':'Muito alta','High':'Alta','Medium':'Média','Low':'Baixa','Lowest':'Muito baixa'}
ORDER=['Highest','High','Medium','Low','Lowest']
SLA={'Highest':8,'High':12,'Medium':16,'Low':24,'Lowest':40}

for x in sweep:
    x['c']=pdt(x['created']); x['r']=pdt(x['resolved']); x['m']=mn(x['modulo'])
# REGRA: o módulo "Chat de Suporte" (Almai) foi aberto como bug, mas é MELHORIA — não conta como bug.
# Remove de toda a análise (dashboard, funil, evolução, etc.). Deveria estar no lado Build/PEM.
EXCLUI_MOD={'Chat de Suporte'}
chat_removidos=sum(1 for x in sweep if x['m'] in EXCLUI_MOD)
sweep=[x for x in sweep if x['m'] not in EXCLUI_MOD]
# REGRA: desconsiderar em toda a dashboard os cards descartados pelo QA (Cancelado QA).
# Mantemos a base completa em sweep_full só para o funil (que mostra o 141->98) e o indicador de descarte.
sweep_full=sweep
cancelado_total=sum(1 for x in sweep_full if x['res']=='Cancelado QA')
sweep=[x for x in sweep_full if x['res']!='Cancelado QA']
d={}
d['meta']={'total_bugs_base_atual':len(sweep),'total_com_descartados':len(sweep_full),'descartados_qa':cancelado_total,'chat_removidos':chat_removidos,'periodo':min(x['c'] for x in sweep).strftime('%Y-%m')+' a '+max(x['c'] for x in sweep).strftime('%Y-%m'),'snapshot':str(TODAY)}
# Data/hora em que o pipeline rodou de verdade (fetch_jira.py + gen_data.py rodam no mesmo job,
# em sequência — este timestamp é gerado logo depois do fetch, então reflete quando os dados do
# Jira foram puxados). Horário de Brasília (UTC-3 fixo — Brasil não observa horário de verão).
d['gerado_em']=AGORA_BR.strftime('%d/%m/%Y %H:%M')

# severidade
pc=collections.Counter(x['prio'] for x in sweep)
d['severidade']=[{'nivel':NIVEL[p],'n':pc.get(p,0)} for p in ORDER]
d['severidade'].append({'nivel':'Sem prioridade','n':pc.get('Preencher Prioridade',0)+pc.get(None,0)})

# DETECÇÃO — onde o bug foi pego (issuetype), POR SAFRA (mês de criação). DECISÃO DE
# 02/09/2026: volume BRUTO, sem nenhuma exclusão — usa sweep_full (inclui Cancelado QA,
# Cancelado Dev, e qualquer status, inclusive Impedimento Produto) — pra ser exatamente o
# mesmo universo do passo 1 ("bugs criados") do funil "Diagnóstico do mês" (build_funil, mais
# abaixo: crj=[x for x in sweep_full if x['c'] and x['c'].strftime('%Y-%m')==ref]), e os dois
# cards baterem sempre no mesmo total pro mesmo mês. Antes somava o histórico inteiro (sweep,
# já líquido) num total único fixo — agora um por safra, acompanhando o seletor de mês do
# Panorama (kpiCards em build_dash.py). d['deteccao'] (chave antiga) fica como fallback,
# apontando pro mês corrente, caso algo externo ainda dependa dela.
DET_ORDER=[('Bug Cliente','Cliente'),('Bug QA','QA'),('Bug Dev','Dev'),('Bug Backoffice','Backoffice')]
def _deteccao_de(cc):
    itens=[{'tipo':lbl,'n':cc.get(key,0)} for key,lbl in DET_ORDER]
    outros=sum(v for k,v in cc.items() if k not in dict(DET_ORDER))
    if outros: itens.append({'tipo':'Outros','n':outros})
    tot=sum(i['n'] for i in itens) or 1
    for i in itens: i['pct']=round(100*i['n']/tot)
    cli=cc.get('Bug Cliente',0)
    return {'itens':itens,'total':tot,'escape_pct':round(100*cli/tot),'interno_pct':round(100*(tot-cli)/tot)}
det_mes_bruto=collections.defaultdict(lambda:collections.Counter())
for x in sweep_full:
    if x['c']: det_mes_bruto[x['c'].strftime('%Y-%m')][x['itype']]+=1
d['deteccao_por_mes']={m:_deteccao_de(cc) for m,cc in det_mes_bruto.items()}
d['deteccao']=d['deteccao_por_mes'].get(str(TODAY)[:7]) or _deteccao_de(collections.Counter())

# tot_series mensal: criados (intake) vs entregues (da safra do mês).
# ENTREGUE (usado só por d['recortes'] abaixo — recorte BIM/Sem BIM, não renderizado no
# dashboard, ver CLAUDE.md) mantido como estava: só "Em produção" conta.
ENTREGUE={'Em produção'}
# ENTREGUE_TAXA — só para "Taxa de entrega — safra" (kpiCards). DECISÃO DE 01/09/2026: passa a
# contar status atual em {Em produção, Done, Concluído, Concluido} (antes só "Em produção");
# e exclui cards com resolution "Cancelado Dev" — sem isso, um card cancelado no próprio dev
# mas com status Done/Concluído inflava a taxa como se fosse entrega real. Cancelado QA já não
# precisa de checagem aqui: `sweep` já exclui essa resolução da base inteira (linha ~27).
ENTREGUE_TAXA={'Em produção','Done','Concluído','Concluido'}
cria=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'])
entr=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep
     if x['c'] and x['status'] in ENTREGUE_TAXA and x['res']!='Cancelado Dev')
# SOBRA = cards que terminaram o mês SEM serem iniciados (status atual "Não Iniciado").
naoini=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'] and x['status']=='Não Iniciado')
# ACUMULADO = "Cards no Início" (saldo rolante) — RÉGUA OFICIAL definida com o setor de dev
# (ver evolucao_bugs.py / régua atualizada 27/08/2026), SEMPRE ao vivo a partir do sweep:
#   ESCOPO ...... só os 4 tipos de bug de verdade: issuetype in BUG_TYPES.
#   FORA DE TUDO  (nem criado, nem concluído): resolução Cancelado QA ou Cancelado Dev
#                 (decisão de gestão de 01/09/2026, após levantamento mostrando ~1,3% do
#                 volume total mas concentrado nos últimos meses — ver
#                 levantamento_cancelado_dev.py), OU card ATUALMENTE parado no status
#                 "IMPEDIMENTO PRODUTO" ou "Backlog" (ainda não entrou no fluxo de dev).
#                 Quem só PASSOU por um desses status mas já avançou (ou foi concluído)
#                 conta normalmente — o corte é pelo status atual.
#   CRIADO ...... mês do campo "created".
#   CONCLUÍDO ... mês da 1ª transição para "Em produção"/"Em Produção" (fallback: 1ª transição
#                 p/ "Done"/"Concluído"/"Concluido"; fallback final: mês de criação, pra card
#                 já terminal cujo changelog não tem a transição registrada). NÃO é
#                 resolutiondate — vazio em boa parte da base. Precisa do changelog do Jira
#                 (campo concluido_mes, calculado em fetch_jira.py).
#   início(mês) = início(anterior) + criados(anterior) − concluídos(anterior), começando em 0.
# sweep_full = chat-free e inclui os Cancelado QA/Dev (necessário pra separar as contagens).
BUG_TYPES={'Bug Cliente','Bug QA','Bug Dev','Bug Backoffice'}
RES_EXCLUI_ACUM={'Cancelado QA','Cancelado Dev'}
STATUS_EXCLUI_ACUM={'IMPEDIMENTO PRODUTO','Backlog'}
def _elegivel_evol(x):
    return x['itype'] in BUG_TYPES and x['res'] not in RES_EXCLUI_ACUM and x['status'] not in STATUS_EXCLUI_ACUM
def _mes_concluido(x):
    return x.get('concluido_mes')
criaD=collections.Counter(); concD=collections.Counter()
# keys por mês (mesmo critério de criaD/concD) — usadas p/ o clique na barra abrir a lista exata
# desses cards no Jira (key in (...)), sem depender de refazer o JQL/filtro na mão.
criaD_keys=collections.defaultdict(list); concD_keys=collections.defaultdict(list)
for x in sweep_full:
    if not _elegivel_evol(x): continue
    if x['c']:
        m=x['c'].strftime('%Y-%m'); criaD[m]+=1; criaD_keys[m].append(x['key'])
    mc=_mes_concluido(x)
    if mc:
        concD[mc]+=1; concD_keys[mc].append(x['key'])
meses=sorted(cria)
import os
# Backlog acumulado, RÉGUA OFICIAL, SEMPRE ao vivo a partir do sweep (criaD/concD acima) — não
# depende mais de jira_backlog.json nem da planilha do Diego. É o mesmo método usado em
# d['evol_modulo'] (por módulo), de propósito: "Todos" na Evolução por módulo tem que somar
# EXATAMENTE os números daqui (backlog_criados/backlog_concluidos/acumulado), senão os dois
# gráficos divergem mesmo mostrando "o mesmo modelo".
#   acumulado (F) = início + D - E, rolando mês a mês (o F de um mês é o início do próximo)
ts=[]; inicio=0
for m in meses:
    cc=cria.get(m,0); ee=entr.get(m,0); ni=naoini.get(m,0)
    dd=criaD.get(m,0); ff=concD.get(m,0)
    acum = inicio + dd - ff
    ts.append({'mes':m,'criados':cc,'entregues':ee,'abertos':cc-ee,
               'acumulado':acum,
               'backlog_criados':dd,
               'backlog_concluidos':ff,
               'backlog_criados_keys':criaD_keys.get(m,[]),
               'backlog_concluidos_keys':concD_keys.get(m,[]),
               'nao_iniciado':ni,
               'pct_entrega':round(100*ee/cc) if cc else 0,
               'taxa_sobra':round(100*ni/cc) if cc else 0})
    inicio = acum
d['acum_fonte']="Jira ao vivo · régua oficial (concluído = 1ª entrada em Em produção — mesmo cálculo usado em Bug por módulo)"
d['tot_series']=ts
d['jira_base']='https://orcafascio.atlassian.net'

# Divisão da safra por PRODUTO: Prime (módulo próprio) · Orçafascio (novo) · Orçafascio antigo.
# Prime = módulo 'Prime'. "antigo" vem de marcador na descrição (contagens em antigo_por_mes.json,
# geradas por fetch_produto.py). "novo" = criados do mês − Prime − antigo.
prime_c=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'] and x['m']=='Prime')
antigo_c=collections.Counter()
if os.path.exists('inputs/antigo_por_mes.json'):
    antigo_c=collections.Counter(json.load(open('inputs/antigo_por_mes.json')))
prod={}
for m in meses:
    tot=cria.get(m,0); pr=prime_c.get(m,0); an=antigo_c.get(m,0)
    prod[m]={'prime':pr,'antigo':an,'novo':max(0,tot-pr-an),'total':tot}
d['prod_por_mes']=prod
d['produto_antigo_pronto']=bool(antigo_c)
# ---- SÉRIE POR STATUS (para o filtro/seletor da Sobra) ----
# Somente os status que compõem a sobra/aberto no dev (mesma régua do acumulado). Os 5 nomes
# conferidos byte a byte contra um export real do Jira (inputs/suporte_list.csv, cabeçalho):
# "Não Iniciado", "Em Desenvolvimento", "IMPEDIMENTO DEV" e "Revert" aparecem lá exatamente
# assim. "IMPEDIMENTO PRODUTO" não é uma coluna desse CSV (ele só rastreia status com tempo em
# status medido no fluxo principal) — mas é o mesmo literal já usado e validado contra dado ao
# vivo do Jira em vários outros pontos do pipeline (STATUS_EXCLUI_ACUM acima, impedimentos_live.json
# em fetch_jira.py, régua oficial em evolucao_bugs.py), régua definida com o setor de dev.
STATUS_ORDER=['Não Iniciado','Em Desenvolvimento','IMPEDIMENTO DEV','IMPEDIMENTO PRODUTO','Revert']
presentes=[s for s in STATUS_ORDER if any(x['status']==s for x in sweep)]
por_status={}
por_status_keys={}
for s in presentes:
    cnt=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'] and x['status']==s)
    por_status[s]=[cnt.get(m,0) for m in meses]
    keys_m=collections.defaultdict(list)
    for x in sweep:
        if x['c'] and x['status']==s: keys_m[x['c'].strftime('%Y-%m')].append(x['key'])
    por_status_keys[s]=[keys_m.get(m,[]) for m in meses]
d['status_series']={'meses':meses,'ordem':presentes,'por_status':por_status,'por_status_keys':por_status_keys}
# override AO VIVO da sobra por status (contagens JQL de hoje) — ver sobra_live.json
# 'full': substitui a série INTEIRA de cada status pelo mapa {mês:qtd} ao vivo (zera os demais meses).
if os.path.exists('sobra_live.json'):
    sl=json.load(open('sobra_live.json'))
    if 'full' in sl:
        for st,mp in sl['full'].items():
            if st in por_status:
                por_status[st]=[mp.get(m,0) for m in meses]
    else:  # modo antigo: override só de meses específicos
        for mm,vals in sl.items():
            if mm not in meses: continue
            idx=meses.index(mm)
            for st,v in vals.items():
                if st in por_status: por_status[st][idx]=v
# taxa de sobra média das safras FECHADAS (exclui o mês corrente, ainda em andamento)
cur_ym=str(TODAY)[:7]
fech=[t for t in ts if t['mes']<cur_ym]
ult6=fech[-6:]
d['taxa_sobra']={'media_fechadas':round(statistics.mean([t['taxa_sobra'] for t in ult6])) if ult6 else 0,
                 'mes_corrente':cur_ym,
                 'ult_fechada':fech[-1] if fech else None}

# DETECÇÃO ao longo do tempo — escape rate mensal (Bug Cliente ÷ total criado no mês, base líquida, por mês de criação)
det_mes=collections.defaultdict(lambda:collections.Counter())
for x in sweep:
    if x['c']: det_mes[x['c'].strftime('%Y-%m')][x['itype']]+=1
det_series=[]
for m in meses:
    cc=det_mes[m]; tot=sum(cc.values()); cli=cc.get('Bug Cliente',0)
    det_series.append({'mes':m,'total':tot,'cliente':cli,'qa':cc.get('Bug QA',0),
        'dev':cc.get('Bug Dev',0),'bo':cc.get('Bug Backoffice',0),
        'escape':round(100*cli/tot) if tot else 0})
d['det_series']=det_series
_defech=[s for s in det_series if s['mes']<cur_ym and s['total']>0][-6:]
d['det_series_meta']={'media_fechadas':round(statistics.mean([s['escape'] for s in _defech])) if _defech else 0,
                      'mes_corrente':cur_ym}

# ---- RECORTES: BIM (externo) x Sem BIM (internos) ----
# Mapa ÚNICO módulo->grupo. "Internos" nunca é lista à parte: é o complemento de BIM.
# Comparação sem acento/caixa (typo/acentuação não fazem card vazar de grupo em silêncio).
import unicodedata as _ud
def _gk(s):
    s=(s or '').strip().lower()
    return ''.join(c for c in _ud.normalize('NFD',s) if _ud.category(c)!='Mn')
_BIM_KEYS={'of eletrico','orcabim','orcabim web','of hidraulico','of estrutural','of bi'}
_INTERNO_KEYS={'orcamento','bases de preco','gestao de base propria','sofia','arquivos publicos','cadastro',
 'administrar empresa','cadastro/administrar empresa','prime','chat de suporte','ti','medicao','diario de obras',
 'planejamento','compras','of manager','of cde','nao classificado'}
def _grupo(m):
    k=_gk(m)
    if k in _BIM_KEYS: return 'bim'
    if k in _INTERNO_KEYS: return 'interno'
    print(f"[AVISO recorte] módulo NÃO classificado como BIM/interno: {m!r} -> assumindo INTERNO. "
          f"Classifique em _BIM_KEYS/_INTERNO_KEYS no gen_data.")
    return 'interno'
# valida UMA vez sobre os módulos que existem (warnings saem aqui, não no loop por bug)
_bim_mods={m for m in {x['m'] for x in sweep} if _grupo(m)=='bim'}
_is_bim=lambda x: x['m'] in _bim_mods
def _rec_serie(pred):
    cri=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'] and pred(x))
    ent=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'] and pred(x) and x['status'] in ENTREGUE)
    dm=collections.defaultdict(lambda:collections.Counter())
    for x in sweep:
        if x['c'] and pred(x): dm[x['c'].strftime('%Y-%m')][x['itype']]+=1
    out=[]; saldo=0
    for m in meses:
        cc=cri.get(m,0); ee=ent.get(m,0); saldo+=cc-ee
        cm=dm[m]; tt=sum(cm.values()); cli=cm.get('Bug Cliente',0)
        out.append({'mes':m,'criados':cc,'entregues':ee,'saldo':saldo,'escape':round(100*cli/tt) if tt else 0})
    return out
def _rec_meta(pred):
    sub=[x for x in sweep if pred(x)]; n=len(sub)
    apo=sum(1 for x in sub if isinstance(x.get('timespent'),(int,float)) and x['timespent']>0)
    return {'n':n,'apont':round(100*apo/n) if n else 0}
d['recortes']={
 'todos':{'label':'Todos','serie':_rec_serie(lambda x:True),**_rec_meta(lambda x:True)},
 'bim':{'label':'BIM (externo)','serie':_rec_serie(_is_bim),**_rec_meta(_is_bim),'mods':sorted(_bim_mods)},
 'interno':{'label':'Sem BIM','serie':_rec_serie(lambda x:not _is_bim(x)),**_rec_meta(lambda x:not _is_bim(x))},
}
d['recorte_mes_corrente']=cur_ym

# ---- EVOLUÇÃO POR MÓDULO ----
# MESMA régua oficial usada em d['tot_series'] acima (_elegivel_evol/_mes_concluido) — só que
# por módulo em vez de agregado. Somando "Todos" os módulos aqui dá EXATAMENTE
# d['tot_series'][...]['backlog_criados']/['backlog_concluidos'] — não há painel separado pra esse
# agregado (foi removido); "Todos" aqui É o agregado geral.
_emc=collections.defaultdict(lambda:collections.Counter())
_eme=collections.defaultdict(lambda:collections.Counter())
_emck=collections.defaultdict(lambda:collections.defaultdict(list))
_emek=collections.defaultdict(lambda:collections.defaultdict(list))
for x in sweep_full:
    if not _elegivel_evol(x): continue
    if x['c']:
        m=x['c'].strftime('%Y-%m')
        _emc[x['m']][m]+=1
        _emck[x['m']][m].append(x['key'])
    mc=_mes_concluido(x)
    if mc:
        _eme[x['m']][mc]+=1
        _emek[x['m']][mc].append(x['key'])
_emtot={md:sum(_emc[md].values()) for md in _emc}
_emordem=sorted(_emtot, key=lambda md:-_emtot[md])
d['evol_modulo']={'meses':meses,'ordem':_emordem,
  'por_modulo':{md:{'criados':[_emc[md].get(m,0) for m in meses],
                    'concluidos':[_eme[md].get(m,0) for m in meses],
                    'criados_keys':[_emck[md].get(m,[]) for m in meses],
                    'concluidos_keys':[_emek[md].get(m,[]) for m in meses]} for md in _emordem}}

# por modulo: bugs, horas, mttr, trend
mods=collections.defaultdict(lambda:{'bugs':0,'seg':0.0,'mttr':[]})
cria_mod=collections.defaultdict(lambda:collections.Counter())
for x in sweep:
    m=x['m']; mm=mods[m]; mm['bugs']+=1
    if isinstance(x['timespent'],(int,float)): mm['seg']+=x['timespent']
    if x['c'] and x['r']: mm['mttr'].append(busdays(x['c'].date(),x['r'].date()))
    if x['c']: cria_mod[m][x['c'].strftime('%Y-%m')]+=1
last3=meses[-5:-2]; lastm=meses[-2]   # compara o último mês FECHADO (não o corrente parcial) com os 3 anteriores
tab=[]
for m,mm in mods.items():
    vals=cria_mod[m]; base=statistics.mean([vals.get(x,0) for x in last3]) if last3 else 0
    lv=vals.get(lastm,0)
    tr='up' if lv>base*1.15 else ('down' if lv<base*0.85 else 'flat')
    tab.append({'mod':m,'bugs':mm['bugs'],'horas':round(mm['seg']/3600,1),
                'mttr':round(statistics.median(mm['mttr']),1) if mm['mttr'] else None,'trend':tr})
tab.sort(key=lambda t:-t['bugs'])
d['tabela_modulo']=tab

# esforço por módulo (gráfico "Esforço por módulo", custoModulo() em build_dash.py) — POR
# SAFRA (mês de criação do card, mesmo recorte do seletor "Safra em foco" — muda junto com
# ele, como os demais painéis que usam curSafra()/DATA.*_por_mes no front-end), e só de cards
# ATIVOS: exclui quem está parado em IMPEDIMENTO DEV/PRODUTO (esforço represado, não reflete
# ritmo atual) e quem foi cancelado no dev (esforço que não vira entrega). Cálculo separado de
# tab/tabela_modulo acima, que soma TODOS os cards de TODO o período (usado pela tabela
# "Módulo" — colunas Bugs/Tendência/MTTR/Esforço continuam somando tudo, sem essa exclusão nem
# recorte por safra).
STATUS_EXCLUI_ESFORCO={'IMPEDIMENTO DEV','IMPEDIMENTO PRODUTO'}
def _esforco_modulo(cards):
    seg=collections.defaultdict(float)
    for x in cards:
        if x['status'] in STATUS_EXCLUI_ESFORCO or x['res']=='Cancelado Dev': continue
        if isinstance(x['timespent'],(int,float)): seg[x['m']]+=x['timespent']
    lista=[{'mod':m,'horas':round(s/3600,1)} for m,s in seg.items()]
    lista.sort(key=lambda t:-t['horas'])
    return lista[:10]
d['esforco_modulo_ativo']=_esforco_modulo(sweep)   # todo o período — fallback se a safra selecionada não tiver dado
sweep_por_mes=collections.defaultdict(list)
for x in sweep:
    if x['c']: sweep_por_mes[x['c'].strftime('%Y-%m')].append(x)
d['esforco_modulo_por_mes']={m:_esforco_modulo(sweep_por_mes[m]) for m in meses}

# alerta parados: status Não Iniciado > 5 dias úteis
asg=json.load(open('ni_assignee.json'))
ni=[]
for x in sweep:
    if x['status']!='Não Iniciado' or not x['c']: continue
    bd=busdays(x['c'].date(),TODAY)
    ni.append({'key':x['key'],'dias':bd,'prio':x['prio'] or '—','mod':x['m'],'resp':asg.get(x['key'],'Sem responsável'),
               'url':f"{d['jira_base']}/browse/{x['key']}"})
ni.sort(key=lambda t:-t['dias'])
par=[a for a in ni if a['dias']>5]
d['alerta_parados']={'limite':5,'snapshot':str(TODAY),'total_nao_iniciado':len(ni),'count':len(par),'itens':par}

# squads
SQUAD={'Orçamento':('Orçamento','interno',6),'Bases de Preço':('Orçamento','interno',6),'Gestão de Base Própria':('Orçamento','interno',6),'Sofia':('Orçamento','interno',6),'Cadastro/Administrar Empresa':('Backoffice','interno',2),'Prime':('Prime','interno',3),'TI':('TI','interno',None),'Medição':('Paulo (contrato)','contratado',2),'Diario de Obras':('Paulo (contrato)','contratado',2),'Planejamento':('Paulo (contrato)','contratado',2),'Compras':('Paulo (contrato)','contratado',2),'OF Manager':('Paulo (contrato)','contratado',2),'OF CDE':('OF CDE (contrato)','contratado',None),'OF Elétrico':('Ramoon (contrato)','contratado',1),'OrçaBim':('Edson (contrato)','contratado',1),'OF Hidraulico':('Matheus (contrato)','contratado',1),'OF Estrutural':('Matheus (contrato)','contratado',1),'Chat de Suporte':('Outros (interno)','interno',None),'Arquivos Públicos':('Outros (interno)','interno',None),'OF BI':('Outros (interno)','interno',None)}
sq=collections.defaultdict(lambda:{'bugs':0,'seg':0.0,'mttr':[],'sn':0,'sok':0,'reg':'—','p':None})
for x in sweep:
    nome,reg,ppl=SQUAD.get(x['m'],('Não atribuído','—',None))
    s=sq[nome]; s['reg']=reg; s['p']=ppl; s['bugs']+=1
    if isinstance(x['timespent'],(int,float)): s['seg']+=x['timespent']
    if x['c'] and x['r']:
        s['mttr'].append(busdays(x['c'].date(),x['r'].date()))
        if x['prio'] in SLA:
            s['sn']+=1
            if busdays(x['c'].date(),x['r'].date())*8<=SLA[x['prio']]: s['sok']+=1
sqs=[]
for nome,s in sq.items():
    sqs.append({'squad':nome,'regime':s['reg'],'pessoas':s['p'],'bugs':s['bugs'],'horas':round(s['seg']/3600),
        'mttr':round(statistics.mean(s['mttr']),1) if s['mttr'] else None,
        'sla':round(100*s['sok']/s['sn']) if s['sn'] else None,
        'bugs_por_pessoa':round(s['bugs']/s['p']) if s['p'] else None})
sqs.sort(key=lambda t:-t['bugs'])
d['squads']=sqs

# cancelado QA
d['cancelado_qa']=cancelado_total

# ---- do xlsx: PEM(build side), aloc ----
wb=openpyxl.load_workbook('inputs/Resumo_bugs.xlsx',data_only=True)
# Série do Diego (aba "Resumo") — para o gráfico de evolução ficar IDÊNTICO à planilha dele.
d['diego_series']=[]
try:
    for r_ in list(wb['Resumo'].iter_rows(values_only=True))[1:]:
        mv=r_[0]
        if isinstance(mv,datetime.datetime): mv=mv.strftime('%Y-%m')
        if not (isinstance(mv,str) and re.match(r'^\d{4}-\d{2}$',mv)): continue
        d['diego_series'].append({'mes':mv,'inicio':int(r_[2] or 0),'criados':int(r_[3] or 0),
                                  'concluidos':int(r_[4] or 0),'saldo':int(r_[5] or 0)})
except Exception as e:
    print('aviso: aba Resumo do Diego não lida:',e)
pem=[x for x in list(wb['ProdutoMelhorias'].iter_rows(values_only=True))[1:] if x[1]]
build_seg=sum(x[14] for x in pem if isinstance(x[14],(int,float)))
run_seg=sum(x['timespent'] for x in sweep if isinstance(x['timespent'],(int,float)))
d['rvb']={'run_h':round(run_seg/3600),'build_h':round(build_seg/3600),
          'run_pct':round(100*run_seg/(run_seg+build_seg)),'build_pct':round(100*build_seg/(run_seg+build_seg))}
d['custo_tipo']={'Correção de bug (Run)':d['rvb']['run_h'],'Produtos+Melhorias (Build)':d['rvb']['build_h']}
# alocação por responsável (card "Alocação — bugs por responsável", dentro de "Esforço e
# alocação — bugs", e responsavelPanel() na visão por produto). DECISÃO DE 03/09/2026: alinhado
# com a régua de "Bug por módulo" (_elegivel_evol/_mes_concluido, evol_modulo acima) — primeira
# versão contava concluído por COORTE de criação (status atual dos bugs criados na safra); a
# validação contra Jira real mostrou que isso é uma população diferente de "Bug por módulo"
# (que conta por MÊS DE CONCLUSÃO — concluido_mes — não importa quando o card foi criado), e as
# somas não batiam (ex.: ago/2026: 53 pela coorte vs 75 por "Bug por módulo"). Agora usa a
# MESMA base (sweep_full + _elegivel_evol, que já exclui Cancelado QA/Dev e status atual em
# IMPEDIMENTO PRODUTO/Backlog) e o MESMO mês de conclusão (concluido_mes) — a soma de todos os
# responsáveis num mês bate exatamente com d['tot_series'][mes]['backlog_concluidos'] (o número
# de concluídos de "Bug por módulo"/Todos naquele mês). % = fatia de cada responsável sobre o
# total de concluídos do mês (não mais "sobre chegaram ao dev" — não fazia sentido comparar
# coortes diferentes).
concD_por_mes=collections.defaultdict(list)
for x in sweep_full:
    if not _elegivel_evol(x): continue
    mc=_mes_concluido(x)
    if mc: concD_por_mes[mc].append(x)
aloc_por_mes={}
for mes in meses:
    cards=concD_por_mes[mes]
    total=len(cards)
    cc=collections.Counter((x.get('assignee') or 'Sem responsável') for x in cards)
    aloc_por_mes[mes]=[{'resp':r,'n':n,'pct':round(100*n/total) if total else 0} for r,n in cc.most_common(10)]
d['aloc_por_mes']=aloc_por_mes

# ---- previsibilidade (dev) + suporte do CSV ----
def _h(s):
    s=(s or '').strip()
    if s in ('','-'): return 0.0
    return sum(int(v)*{'M':720,'w':168,'d':24,'h':1,'m':1/60}[u] for v,u in re.findall(r'(\d+)\s*([Mwdhm])',s))
DEV=['Não Iniciado','Em Desenvolvimento','Revisão QA','Aprovado QA','IMPEDIMENTO DEV','Não Aprovado','Reprovado QA','Revert']
prio_live={x['key']:x['prio'] for x in sweep}
by=collections.defaultdict(list); lag=[]
for r_ in csv.DictReader(open('inputs/suporte_list.csv',encoding='utf-8-sig')):
    dev=sum(_h(r_.get(c,'')) for c in DEV); prod=_h(r_.get('Em produção',''))
    if prod>0: lag.append(prod)
    p=prio_live.get(r_['Key'])
    if p not in SLA: continue
    by[p].append(dev)
# p95: remove os 5% mais lentos de cada prioridade antes de medir o cumprimento do SLA
pr=[]; tn=tk=0; total_bruto=0
for p in ORDER:
    if p not in by: continue
    devs=sorted(by[p]); total_bruto+=len(devs)
    keep=int(round(len(devs)*0.95)) or len(devs)
    kept=devs[:keep]                     # mantém os 95% mais rápidos
    ok=sum(1 for x in kept if x<=SLA[p]); n=len(kept)
    tn+=n; tk+=ok
    pr.append({'nivel':NIVEL[p],'sla':SLA[p],'n':n,'ok':ok,'pct':round(100*ok/n),
               'mttr':round(statistics.median(kept)/8,1)})
d['previsibilidade']={'agregado':round(100*tk/tn),'ok':tk,'n':tn,'metodo':'dev-p95','excluidos':total_bruto-tn,'por_prio':pr,
    'snapshot':snapshot_arquivo('inputs/suporte_list.csv')}
d['suporte_lag']={'n':len(lag),'mediana_h':round(statistics.median(lag),1),'media_h':round(statistics.mean(lag),1)}

# ---- FUNIL DE ENTREGA DO DEV — para CADA mês (safra) ----
# RÉGUA DO FUNIL — só deste painel (build_funil/funilPanel), NÃO usada em mais nenhum
# lugar do dashboard (não mexe em ENTREGUE/d['tot_series'] acima, nem em evolucao_bugs.py):
#   1. Criados ....... TODOS os bugs criados no mês (sem excluir por resolução/status/tipo
#                       de issue nesta etapa — mas sweep_full já não tem Chat de Suporte,
#                       igual em toda a análise, então esse módulo continua fora).
#   2. Cancelados dev  segmento próprio: dos que passaram pelo QA (não Cancelado QA), quantos
#                       têm resolution == "Cancelado Dev" — DECISÃO DE 02/09/2026: agora sai
#                       ANTES de "chegaram ao dev" (não depois), pra "chegaram ao dev" já vir
#                       líquido de cancelamento — igual à régua oficial (Evolução por módulo/
#                       evolucao_bugs.py), que sempre excluiu Cancelado Dev de "criados".
#                       Antes esse card contava em "chegaram ao dev" e só saía no passo
#                       seguinte — o que fazia esse painel divergir da régua oficial no mesmo
#                       mês (achado ao comparar Diagnóstico do mês vs Evolução por módulo).
#   3. Chegaram ao dev  criados − Cancelado QA − Cancelado Dev.
#   4. Entregues ..... status ATUAL em ST_ENTREGUE_FUNIL (Em produção/Em Produção/Done/
#                       Concluído/Concluido) — mais amplo que o ENTREGUE usado acima em
#                       d['tot_series'] (só "Em produção"); intencional, só pra este painel.
#   5. Na fila/pipeline  o resto: chegaram ao dev, não entregues — inclui Backlog e todas as
#                       colunas de status ativas. Por safra: cada mês roda isolado (crj = só
#                       cards criados naquele mês).
ST_ENTREGUE_FUNIL={'Em produção','Em Produção','Done','Concluído','Concluido'}
def build_funil(ref):
    crj=[x for x in sweep_full if x['c'] and x['c'].strftime('%Y-%m')==ref]
    disc=[x for x in crj if x['res']=='Cancelado QA']
    pos_qa=[x for x in crj if x['res']!='Cancelado QA']
    canc_dev=[x for x in pos_qa if x['res']=='Cancelado Dev']
    dev=[x for x in pos_qa if x['res']!='Cancelado Dev']
    entregues=[x for x in dev if x['status'] in ST_ENTREGUE_FUNIL]
    fila=[x for x in dev if x['status'] not in ST_ENTREGUE_FUNIL]
    fila_det=sorted(collections.Counter(x['status'] for x in fila).items(),key=lambda t:-t[1])
    # keys por status da fila (mesmo critério de fila_det acima) — usadas pro clique em
    # "Composição da fila" abrir a lista exata desses cards no Jira, mesmo padrão de
    # criaD_keys/concD_keys (Bug por módulo) e por_status_keys (Sobra por status).
    fila_det_keys=collections.defaultdict(list)
    for x in fila: fila_det_keys[x['status']].append(x['key'])
    sevd=collections.Counter(x['prio'] for x in dev)
    sev_ord=[{'nivel':NIVEL[p],'n':sevd.get(p,0)} for p in ORDER if sevd.get(p,0)]
    modd=collections.Counter(x['m'] for x in dev).most_common(5)
    # DETECÇÃO do mês — TODOS os cards da safra (inclusive os descartados pelo QA), por tipo do
    # Jira: Cliente = escapou p/ produção; QA/Dev = barrado interno; Backoffice = ferramenta interna.
    # Mesmo DET_ORDER de d['deteccao_por_mes'] (card "Detecção" do Panorama) — cálculo local e
    # independente aqui, não reaproveita esse dict (mudança isolada por prompt anterior).
    itc=collections.Counter(x['itype'] for x in crj)
    det_itens=[{'tipo':lbl,'n':itc.get(key,0)} for key,lbl in DET_ORDER]
    det_outros=sum(v for k,v in itc.items() if k not in dict(DET_ORDER))
    if det_outros: det_itens.append({'tipo':'Outros','n':det_outros})
    det_tot=sum(i['n'] for i in det_itens) or 1
    for i in det_itens: i['pct']=round(100*i['n']/det_tot)
    mt=[busdays(x['c'].date(),x['r'].date()) for x in dev if x['c'] and x['r']]
    napont=sum(1 for x in dev if isinstance(x['timespent'],(int,float)) and x['timespent'])
    return {'mes':ref,'total':len(crj),'descartados_qa':len(disc),'dev':len(dev),
        'cancelados_dev':len(canc_dev),
        'entregues':len(entregues),'fila':len(fila),'fila_det':fila_det,'fila_det_keys':dict(fila_det_keys),
        'pct_descarte':round(100*len(disc)/len(crj)) if crj else 0,
        'pct_entrega':round(100*len(entregues)/len(dev)) if dev else 0,
        'sev':sev_ord,'mod_top':modd,'detc':det_itens,
        'mttr_mediana':round(statistics.median(mt),1) if mt else None,
        'mttr_media':round(statistics.mean(mt),1) if mt else None,
        'apont_cov':[napont,len(dev)]}
cur_m=str(TODAY)[:7]
mkeys=sorted({x['c'].strftime('%Y-%m') for x in sweep_full if x['c']})
ref=cur_m if cur_m in mkeys else max(mkeys)   # safra do mês corrente
d['funil']=build_funil(ref)
d['funil_por_mes']={m:build_funil(m) for m in mkeys}
# override AO VIVO do funil do mês corrente (contagens JQL do Jira de hoje) — ver funil_live.json / fetch_funil.py
if os.path.exists('funil_live.json'):
    fl=json.load(open('funil_live.json'))
    for m,ov in fl.items():
        base=d['funil_por_mes'].get(m,{})
        base.update(ov)                 # mantém campos não sobrescritos; aplica os ao vivo
        d['funil_por_mes'][m]=base
        if m==ref: d['funil']=base
d['funil_default']=ref; d['mes_corrente']=cur_m
# Spotlight de impedimentos (bloqueios atuais, todos os meses) — ao vivo do Jira, ver impedimentos_live.json
if os.path.exists('impedimentos_live.json'):
    d['impedimentos']=json.load(open('impedimentos_live.json'))

# ---- HISTÓRICO POR MÓDULO (criados bruto por módulo por mês) ----
cellh=collections.defaultdict(lambda:collections.Counter()); toth=collections.Counter()
for x in sweep:
    if not x['c']: continue
    mm=x['c'].strftime('%Y-%m'); cellh[x['m']][mm]+=1; toth[x['m']]+=1
mesesh=sorted({k for c in cellh.values() for k in c})
toph=[m for m,_ in toth.most_common(8)]
serh=[{'mod':mod,'serie':[cellh[mod].get(k,0) for k in mesesh]} for mod in toph]
outrosh=[sum(cellh[mod].get(k,0) for mod in cellh if mod not in toph) for k in mesesh]
if any(outrosh): serh.append({'mod':'Outros','serie':outrosh})
# por_modulo: série de TODOS os módulos (para o explorador/seletor), ordenado por volume
ordem_mods=[m for m,_ in toth.most_common()]
por_modulo={mod:[cellh[mod].get(k,0) for k in mesesh] for mod in ordem_mods}
d['mod_history']={'meses':mesesh,'series':serh,'totais':{m:toth[m] for m in toph},
                  'por_modulo':por_modulo,'ordem':ordem_mods,'total_geral':{m:toth[m] for m in ordem_mods}}
# override AO VIVO do mês corrente no histórico por módulo (bugs criados por módulo) — ver modhist_live.json
# modhist_live.json  -> substitui a COLUNA INTEIRA do mês (todos os módulos) pelo valor ao vivo.
# modhist_patch.json -> patch CIRÚRGICO de células (mês,módulo) específicas, sem tocar nos demais
#   módulos daquele mês. Usado para corrigir meses fechados divergentes vs Jira ao vivo
#   (ex.: card reclassificado depois do snapshot). Formato: {"2026-07":{"Cadastro/Administrar Empresa":5}}
_mh_changed=False
if os.path.exists('modhist_live.json'):
    ml=json.load(open('modhist_live.json'))
    MHd=d['mod_history']; meses_h=MHd['meses']
    for mmes,mp in ml.items():
        if mmes not in meses_h: continue
        idxh=meses_h.index(mmes)
        for mod in MHd['por_modulo']:
            MHd['por_modulo'][mod][idxh]=mp.get(mod,0)      # módulo fora do mapa no mês = 0
    _mh_changed=True
if os.path.exists('modhist_patch.json'):
    mpatch=json.load(open('modhist_patch.json'))
    MHd=d['mod_history']; meses_h=MHd['meses']
    for mmes,cells in mpatch.items():
        if mmes not in meses_h or not isinstance(cells,dict): continue
        idxh=meses_h.index(mmes)
        for mod,val in cells.items():
            if mod in MHd['por_modulo']: MHd['por_modulo'][mod][idxh]=val
    _mh_changed=True
if _mh_changed:
    MHd=d['mod_history']; meses_h=MHd['meses']
    # recomputa totais e reordena por volume
    tg={mod:sum(v) for mod,v in MHd['por_modulo'].items()}
    MHd['total_geral']=tg
    MHd['ordem']=[m for m,_ in sorted(tg.items(),key=lambda t:-t[1])]
    top8=MHd['ordem'][:8]
    MHd['series']=[{'mod':mod,'serie':MHd['por_modulo'][mod]} for mod in top8]
    outros=[sum(MHd['por_modulo'][mod][i] for mod in MHd['por_modulo'] if mod not in top8) for i in range(len(meses_h))]
    if any(outros): MHd['series'].append({'mod':'Outros','serie':outros})
    MHd['totais']={mod:tg[mod] for mod in top8}

# ---- DETALHE POR FERRAMENTA (funil de títulos) — começa por Orçamento ----
import unicodedata
def _norm(s):
    s=(s or '').lower()
    return ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
# funil por módulo: rótulo -> palavras-chave (ordem = prioridade). Refinar aos poucos.
FUNIL_MOD={'Orçamento':[
 ('Base própria / Sincronização',['base propria','sincroniz']),
 ('Composições',['composic']),
 ('Insumos',['insumo']),
 ('Importação (Excel/PDF/Analítico)',['importac','importar','importa ','planilha excel','via excel','importador','analitico']),
 ('Relatórios / Curva ABC',['relatori','curva abc','proposta','pregao','exportar','sintetic']),
 ('Bases oficiais (SINAPI/SBC/…)',['sinapi','sicro',' sbc','orse','iopes','seinfra','setop','emop','embasa','caern','sudecap','agetop','siurb','stabile','derpr','caema','agesul','sedop','base oficial']),
 ('Etapas / EAP',['etapa','eap']),
 ('Quantitativos / Memória de cálculo',['quantitativ','quantidade','memoria de calculo','itemiza','coeficiente','formula']),
 ('BDI',['bdi']),('Encargos sociais',['encargo']),('Cronograma',['cronograma']),
 ('Itens, tags & categorias',['substituir it','recuperar it','excluir it','exclusao de it','inserir it','mover it','deletar it','desfazer substitui',' tag','categor','selecao de categ','favorit']),
 ('Criação / edição do orçamento',['criar orcamento','novo orcamento','criar orament','editar orcamento','excluir orcamento','mover orcamento','restaurar orcamento','copiar orcamento',' pasta',' fit','permissao','modelo novo']),
 ('Cópia / Versões do orçamento',['copia','duplicar','versao']),
 ('Cadastro de cliente / CNPJ',['cliente','cnpj']),
 ('Integração Civil 3D / BIM',['civil 3d','orcabim','pipenetwork','revit']),
 ('Preços & valores',['preco','valor','ajuste de preco']),
 ('Erro técnico (stack trace)',['nomethoderror','typeerror','bigdecimal','undefined method',"can't convert",'nilclass','argumenterror','nameerror']),
 ('UI / telas / textos',['layout','tela ','gramatica','caixa de aviso','escrita da palavra','botao','tooltip','mensagem']),
]}
# --- Funis de ferramenta dos demais módulos (títulos puxados AO VIVO do Jira, em mod_titles/*.json) ---
# Regra igual à do Orçamento: primeira palavra-chave que casa vence (ordem = prioridade).
# Palavras-chave em minúsculo e SEM acento (o _norm remove acentos).
FUNIL_MOD.update({
 'Bases de Preço':[
  ('Base própria / Gestão de base',['base propria','composicao propria','composicoes proprias','gestao de base','base own','proprios','propria','proprio']),
  ('Importação / Exportação de planilha',['importa','planilha','exportar','exportacao','export ','baixar composic']),
  ('Busca de composições',['busca','buscar','pesquisar','pesquisa','localizar','autocompletar','caracteres','filtro','passar as pagina','passar de pagina','paginas','pesquisa de composic']),
  ('Cópia de composição',['copiar','copia','duplic']),
  ('Insumos',['insumo']),
  ('Relatório / Caderno técnico',['relatorio','caderno tecnico','extracao','extrair']),
  ('Descrição / Unidade / Tipificação',['descricao','unidade','tipificacao','categoriza','modelo','constante']),
  ('Bases oficiais (SINAPI/SETOP/…)',['sinapi','sicro','sbc','orse','iopes','seinfra','setop','emop','embasa','caern','sudecap','agetop','siurb','derpr','der-pr','caema','sedop','cdhu',' sco','fde','cpos','agesul','stabile']),
  ('Preço / valor divergente',['divergencia','valor','preco','zerad','invertid','diferenca','undefined','consumo','onerad','desonerad']),
  ('SOFIA (IA)',['sofia']),
  ('Erro técnico (500 / stack)',['erro 500','500','502','nomethod','typeerror','undefined method','nilclass','nameerror','argumenterror','solr','sentry','gem ','backup','delete em development']),
  ('Composições (geral)',['composic']),
 ],
 'Cadastro/Administrar Empresa':[
  ('E-mail (duplicado / cadastro / troca)',['duplicad','duplicidade','mesmo e-mail','mesmo email','dois cadastros','troca de e-mail','troca de email','cadastro de e-mail','cadastro de e-mails','e-mail nao cadastrado','email nao cadastrado']),
  ('Login / acesso',['login','logar','acessar','acesso','entrar','nao consegue acess']),
  ('Ativação / senha / convite',['ativacao','ativar','redefinicao','senha','link de','convite','importacao de usuario','importado','email de confirmac','email de ativac','link de ativac','nao esta sendo enviado','nao envia']),
  ('Licença / módulos / permissões',['licenca','modulo','plugin','permiss','of medicao','of eletrico','teste','estudantil','vencimento']),
  ('CRM / Backoffice / Vendas / Marketing',['crm','backoffice','vendas','marketing','lead','sdr','rodizio','banner','campanha','webinar','csm','proposta','boleto','cobranca','gerencianet','pagamento']),
  ('Usuário: excluir / cadastrar',['excluir usuario','excluir o usuario','cadastrar','cadastro de usuario','excluir usurario','adicionar usuario','novo usuario','usuarios']),
  ('Empresa (show / editar / dados)',['empresa','show da empresa','movimentacoes','observac','tipos de empresa','relatorio']),
  ('Erro técnico (500 / stack)',['erro 500','500','nomethod','typeerror','nameerror','nilclass','payload','orquestrador','send_email','referencia']),
  ('UI / home / telas',['home','tela','banner','botao','modal','responsiv','opacidade','visual']),
 ],
 'Medição':[
  ('Relatório fotográfico / armazenamento',['fotografic','armazenamento','imagen','foto','mb ']),
  ('Aprovação / fiscal / empreiteiro',['fiscal','empreiteiro','aprovad','aprovac','convite','enviar medicao','juntar a obra']),
  ('Importação (orçamento / itens / planilha)',['importa','importar','vincular','planilha']),
  ('Relatório / Curva ABC / exportar',['relatorio','curva abc','extrair','exportar']),
  ('Cálculo / valor divergente',['divergencia','valor','calculo','quantidade','quantitativ','percentu','saldo','coeficiente','executad','aditivo','centavos','preco']),
  ('Criar / acessar medição (erro)',['criar','acessar','erro 500','500','nao e possivel','nao consegue','trava','editar']),
  ('Cadastro / licença / manager',['cadastr','manager','modulo','licenca']),
 ],
 'Diario de Obras':[
  ('Relatório do diário',['relatorio']),
  ('Foto / imagem',['foto','imagem','fotografic']),
  ('Observação',['observac']),
  ('Aplicativo (mobile / iOS)',['aplicativo','app ','ios','mobile']),
  ('Aprovação / fiscal',['fiscal','aprovar','aprovad']),
  ('Tarefas / movimentação de material',['tarefa','movimentac','material']),
  ('Criar / editar / excluir diário',['criar','editar','excluir','deletar','adicionar','nao e possivel','erro 500','500','pagina','busca']),
 ],
 'Planejamento':[
  ('Carregar / abrir / criar planejamento',['carregar','carregando','abrir','criar','acessar','entrar','nao encontrado','erro 500','500','atualizando','so fica','nao carrega','nao abre','nao e criado','nao e possivel acessar','extracao']),
  ('Relatório / Cronograma físico financeiro',['relatorio','cronograma','histograma','xslx','xlsx','pdf']),
  ('Diagrama de rede / caminho crítico / linha de base',['diagrama','rede','caminho critico','linha de base']),
  ('Atividade (ativar / mover / redefinir)',['atividade','ativadade',' atv','redefinir','posicao','caixa de atv']),
  ('Cálculo (dias / quantitativos / produção)',['calculo','dias','quantitativ','producao','produtividade','composic','valor','multiplicad','divisao de etapas','negativo']),
  ('Copiar estrutura',['copia','estrutura']),
 ],
})
TITLE_FILES={'Orçamento':'inputs/orc_titles.json',
 'Bases de Preço':'inputs/mod_titles/bases.json',
 'Cadastro/Administrar Empresa':'inputs/mod_titles/cadastro.json',
 'Medição':'inputs/mod_titles/medicao.json',
 'Diario de Obras':'inputs/mod_titles/diario.json',
 'Planejamento':'inputs/mod_titles/planejamento.json'}
# Nestes módulos os títulos vieram AO VIVO do Jira (set autoritativo = total do gráfico);
# classificamos TODOS, sem interseção com o sweep de 12/08.
MODS_ALL_TITLES={'Bases de Preço','Cadastro/Administrar Empresa','Medição','Diario de Obras','Planejamento'}
def _stripref(n):
    n=re.sub(r'#?\s*\d{3,}\s*[-:]*','',n); n=re.sub(r'chat-\S+','',n)
    n=re.sub(r'whatsapp','',n); n=re.sub(r'versao antiga','',n); return n
d['mod_features']={}
mod_cards=[]  # card-a-card (p/ revisão humana em Excel): módulo, key, título, ferramenta sugerida
for modname,funil in FUNIL_MOD.items():
    fpath=TITLE_FILES.get(modname)
    try: titles=json.load(open(fpath))
    except Exception: continue
    swk={x['key']:x for x in sweep}  # já é líquido (sem cancelado e sem chat)
    allt = modname in MODS_ALL_TITLES
    cnt=collections.Counter(); nclass=0
    for k,t in titles.items():
        if not allt and k not in swk: continue   # Orçamento: só cards reais que seguem no módulo
        nclass+=1; n=_stripref(_norm(t)); rot='Outros (não classificado)'
        for r,kws in funil:
            if any(kw in n for kw in kws): rot=r; break
        cnt[rot]+=1
        if allt: mod_cards.append({'mod':modname,'key':k,'titulo':(t or '').strip(),'ferramenta':rot})
    itens=[{'ferramenta':r,'n':v} for r,v in cnt.most_common()]
    d['mod_features'][modname]={'itens':itens,'total':nclass,
        'outros':cnt.get('Outros (não classificado)',0)}

# catálogo de ferramentas válidas por módulo (p/ dropdown da revisão)
mod_funil_labels={m:[r for r,_ in FUNIL_MOD[m]]+['Outros (não classificado)'] for m in MODS_ALL_TITLES}
json.dump({'cards':mod_cards,'labels':mod_funil_labels},open('mod_cards.json','w'),ensure_ascii=False,indent=1)
json.dump(d,open('dash_data.json','w'),ensure_ascii=False)
print('OK. total bugs:',d['meta']['total_bugs_base_atual'])
print('status parados>5du:',d['alerta_parados']['count'],'| cancelado QA:',d['cancelado_qa'])
print('Run vs Build:',d['rvb']['run_pct'],'/',d['rvb']['build_pct'])
print('previsibilidade dev:',d['previsibilidade']['agregado'],'%')
print('top modulos:',[(t['mod'],t['bugs']) for t in d['tabela_modulo'][:5]])
print('meses tot_series:',d['tot_series'][0]['mes'],'->',d['tot_series'][-1]['mes'],'n=',len(d['tot_series']))
