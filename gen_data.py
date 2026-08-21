import json, re, datetime, statistics, collections, csv, openpyxl
TODAY=datetime.date.fromisoformat("2026-08-12")
sweep=json.load(open('sweep.json'))
def pdt(s):
    if not s: return None
    return datetime.datetime.fromisoformat(s)  # handles offset
def mn(m): return 'Não classificado' if not m else re.sub(r'^\d+\s*-\s*','',str(m)).strip()
def busdays(a,b):
    import numpy as np
    return int(np.busday_count(a,b))
import numpy as np
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
if not sweep:
    raise RuntimeError(
        "sweep.json não tem nenhum bug válido depois dos filtros (base líquida ficou vazia). "
        "Isso não é esperado — a base tem centenas de bugs. Provável causa: fetch_jira.py rodou "
        "com 0 issues do Jira (confira o log do passo 'Puxar do Jira') ou sweep.json está "
        "corrompido/vazio. Não dá pra gerar o dashboard sem dados reais do Jira."
    )
d={}
d['meta']={'total_bugs_base_atual':len(sweep),'total_com_descartados':len(sweep_full),'descartados_qa':cancelado_total,'chat_removidos':chat_removidos,'periodo':min(x['c'] for x in sweep).strftime('%Y-%m')+' a '+max(x['c'] for x in sweep).strftime('%Y-%m'),'snapshot':str(TODAY)}

# severidade
pc=collections.Counter(x['prio'] for x in sweep)
d['severidade']=[{'nivel':NIVEL[p],'n':pc.get(p,0)} for p in ORDER]
d['severidade'].append({'nivel':'Sem prioridade','n':pc.get('Preencher Prioridade',0)+pc.get(None,0)})

# DETECÇÃO — onde o bug foi pego (issuetype). Cliente = escapou p/ produção; QA/Dev = barrado interno.
# Visão geral de qualidade de entrega, ao vivo do Jira (sem campo novo).
DET_ORDER=[('Bug Cliente','Cliente'),('Bug QA','QA'),('Bug Dev','Dev'),('Bug Backoffice','Backoffice')]
itc=collections.Counter(x['itype'] for x in sweep)
det_itens=[{'tipo':lbl,'n':itc.get(key,0)} for key,lbl in DET_ORDER]
det_outros=sum(v for k,v in itc.items() if k not in dict(DET_ORDER))
if det_outros: det_itens.append({'tipo':'Outros','n':det_outros})
det_tot=sum(i['n'] for i in det_itens) or 1
for i in det_itens: i['pct']=round(100*i['n']/det_tot)
cliente_n=itc.get('Bug Cliente',0)
d['deteccao']={'itens':det_itens,'total':det_tot,
               'escape_pct':round(100*cliente_n/det_tot),
               'interno_pct':round(100*(det_tot-cliente_n)/det_tot)}

# tot_series mensal: criados (intake) vs entregues (da safra do mês, já em produção/concluído)
# "entregues" usa o status ATUAL do card (Em produção/Done/Concluído = dev entregou), pela
# régua da empresa ("mandar pra produção é o nosso concluído"). Assim o gráfico mostra, de cada
# safra mensal, quanto já foi entregue — e não o fechamento do suporte (que escorrega pro mês seguinte
# e fazia parecer que o time não entregava).
ENTREGUE={'Em produção','Done','Concluído','Concluido'}
cria=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'])
entr=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'] and x['status'] in ENTREGUE)
# SOBRA = cards que terminaram o mês SEM serem iniciados (status atual "Não Iniciado").
naoini=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'] and x['status']=='Não Iniciado')
# ACUMULADO = "Cards no Início" (saldo rolante), MÉTODO DIEGO / planilha Resumo:
#   início(mês) = início(anterior) + criados(anterior) − concluídos(anterior), começando em 0.
#   criados  = criados no mês, excluindo Cancelado QA e Impedimento Produto (coluna T da planilha).
#   concluídos = por mês de conclusão (data de resolução), sem cancelados (coluna S).
# sweep_full = chat-free e inclui cancelados (necessário para separar as duas contagens).
criaD=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep_full if x['c'] and x['res']!='Cancelado QA' and x['status']!='IMPEDIMENTO PRODUTO')
concD=collections.Counter(x['r'].strftime('%Y-%m') for x in sweep_full if x['r'] and x['res']!='Cancelado QA')
meses=sorted(cria)
import os
# Backlog acumulado no MÉTODO DO DIEGO, mas puxado AO VIVO do Jira (sem depender da planilha dele):
#   criados (D)  = criados no mês, status != IMPEDIMENTO PRODUTO, resolução != Cancelado QA, fora Chat de Suporte
#   concluídos (E) = cards em {Concluído/Done, Em produção}, fora Cancelado QA e Chat, pela data de ATUALIZAÇÃO
#   acumulado (F) = início + D - E, rolando mês a mês (o F de um mês é o início do próximo)
# jira_backlog.json é gerado por fetch_backlog.py (21 contagens JQL). Ver reference/fetch_backlog.py.
jb = json.load(open('jira_backlog.json')) if os.path.exists('jira_backlog.json') else {}
ts=[]; inicio=0
for m in meses:
    cc=cria.get(m,0); ee=entr.get(m,0); ni=naoini.get(m,0)
    b = jb.get(m)
    acum = b['acumulado'] if b else (inicio + criaD.get(m,0) - concD.get(m,0))  # fallback: mesmo método com o sweep
    ts.append({'mes':m,'criados':cc,'entregues':ee,'abertos':cc-ee,
               'acumulado':acum,
               'backlog_criados':(b['criados'] if b else criaD.get(m,0)),
               'backlog_concluidos':(b['concluidos'] if b else concD.get(m,0)),
               'nao_iniciado':ni,
               'pct_entrega':round(100*ee/cc) if cc else 0,
               'taxa_sobra':round(100*ni/cc) if cc else 0})
    inicio = acum
d['acum_fonte']="Jira ao vivo · método Diego (Concluído + Em produção, pela data de atualização)"
d['tot_series']=ts

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
# Somente os status que compõem a sobra/aberto no dev (mesma régua do acumulado).
STATUS_ORDER=['Não Iniciado','Em Desenvolvimento','IMPEDIMENTO DEV','IMPEDIMENTO PRODUTO','Revert']
presentes=[s for s in STATUS_ORDER if any(x['status']==s for x in sweep)]
por_status={}
for s in presentes:
    cnt=collections.Counter(x['c'].strftime('%Y-%m') for x in sweep if x['c'] and x['status']==s)
    por_status[s]=[cnt.get(m,0) for m in meses]
d['status_series']={'meses':meses,'ordem':presentes,'por_status':por_status}
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

# alerta parados: status Não Iniciado > 5 dias úteis
asg=json.load(open('ni_assignee.json'))
ni=[]
for x in sweep:
    if x['status']!='Não Iniciado' or not x['c']: continue
    bd=busdays(x['c'].date(),TODAY)
    ni.append({'key':x['key'],'dias':bd,'prio':x['prio'] or '—','mod':x['m'],'resp':asg.get(x['key'],'Sem responsável')})
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
# aloc from xlsx assignee
er=list(wb['Base Atualmódulos'].iter_rows(values_only=True))
al=collections.Counter((x[4] or 'Sem responsável') for x in er[1:] if x[1])
d['aloc_top']=al.most_common(10)

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
d['previsibilidade']={'agregado':round(100*tk/tn),'ok':tk,'n':tn,'metodo':'dev-p95','excluidos':total_bruto-tn,'por_prio':pr}
d['suporte_lag']={'n':len(lag),'mediana_h':round(statistics.median(lag),1),'media_h':round(statistics.mean(lag),1)}

# ---- severidade / previsibilidade (SLA) / MTTR / tempo de resposta do suporte, por RECORTE ----
# Mesmo recorte BIM/interno de d['recortes'] acima (mesma _grupo/_is_bim — não é um mecanismo novo).
# inputs/suporte_list.csv (Time-in-Status) é uma amostra MENOR que a base líquida de bugs: nem todo
# card tem export de tempo em status. Por isso guardamos os dois números (n de bugs do recorte E
# tis_n = cards com Time-in-Status) — o selo de cobertura do dashboard usa os dois para avisar
# quando a base do SLA/dev daquele recorte é pequena demais pra tirar conclusão.
def _rec_prev(pred):
    sub=[x for x in sweep if pred(x)]
    pcr=collections.Counter(x['prio'] for x in sub)
    sev_r=[{'nivel':NIVEL[p],'n':pcr.get(p,0)} for p in ORDER]
    sev_r.append({'nivel':'Sem prioridade','n':pcr.get('Preencher Prioridade',0)+pcr.get(None,0)})
    mt_r=[busdays(x['c'].date(),x['r'].date()) for x in sub if x['c'] and x['r']]
    keys_r={x['key'] for x in sub}
    by_r=collections.defaultdict(list); lag_r=[]; tis_n=0
    for r_ in csv.DictReader(open('inputs/suporte_list.csv',encoding='utf-8-sig')):
        if r_['Key'] not in keys_r: continue
        tis_n+=1
        dev_r=sum(_h(r_.get(c,'')) for c in DEV); prod_r=_h(r_.get('Em produção',''))
        if prod_r>0: lag_r.append(prod_r)
        p=prio_live.get(r_['Key'])
        if p not in SLA: continue
        by_r[p].append(dev_r)
    pr_r=[]; tn_r=tk_r=0; total_bruto_r=0
    for p in ORDER:
        if p not in by_r: continue
        devs=sorted(by_r[p]); total_bruto_r+=len(devs)
        keep=int(round(len(devs)*0.95)) or len(devs)
        kept=devs[:keep]
        ok=sum(1 for v in kept if v<=SLA[p]); n=len(kept)
        tn_r+=n; tk_r+=ok
        pr_r.append({'nivel':NIVEL[p],'sla':SLA[p],'n':n,'ok':ok,
                     'pct':round(100*ok/n) if n else 0,
                     'mttr':round(statistics.median(kept)/8,1) if kept else None})
    return {
        'severidade':sev_r,
        'mttr_mediana':round(statistics.median(mt_r),1) if mt_r else None,
        'previsibilidade':{'agregado':round(100*tk_r/tn_r) if tn_r else 0,'ok':tk_r,'n':tn_r,
                            'metodo':'dev-p95','excluidos':total_bruto_r-tn_r,'por_prio':pr_r},
        'suporte_lag':{'n':len(lag_r),'mediana_h':round(statistics.median(lag_r),1) if lag_r else 0,
                       'media_h':round(statistics.mean(lag_r),1) if lag_r else 0},
        'tis_n':tis_n,
    }
for _k,_pred in (('todos',lambda x:True),('bim',_is_bim),('interno',lambda x:not _is_bim(x))):
    d['recortes'][_k].update(_rec_prev(_pred))

# ---- FUNIL DE ENTREGA DO DEV — para CADA mês (safra) ----
ENTREGUE={'Em produção','Done','Concluído','Concluido'}
def build_funil(ref):
    crj=[x for x in sweep_full if x['c'] and x['c'].strftime('%Y-%m')==ref]
    disc=[x for x in crj if x['res']=='Cancelado QA']
    dev=[x for x in crj if x['res']!='Cancelado QA']
    entregues=[x for x in dev if x['status'] in ENTREGUE]
    fila=[x for x in dev if x['status'] not in ENTREGUE]
    fila_det=sorted(collections.Counter(x['status'] for x in fila).items(),key=lambda t:-t[1])
    sevd=collections.Counter(x['prio'] for x in dev)
    sev_ord=[{'nivel':NIVEL[p],'n':sevd.get(p,0)} for p in ORDER if sevd.get(p,0)]
    modd=collections.Counter(x['m'] for x in dev).most_common(5)
    mt=[busdays(x['c'].date(),x['r'].date()) for x in dev if x['c'] and x['r']]
    napont=sum(1 for x in dev if isinstance(x['timespent'],(int,float)) and x['timespent'])
    return {'mes':ref,'total':len(crj),'descartados_qa':len(disc),'dev':len(dev),
        'entregues':len(entregues),'fila':len(fila),'fila_det':fila_det,
        'pct_descarte':round(100*len(disc)/len(crj)) if crj else 0,
        'pct_entrega':round(100*len(entregues)/len(dev)) if dev else 0,
        'sev':sev_ord,'mod_top':modd,
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
