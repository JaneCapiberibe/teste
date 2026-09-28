"""
VALIDAÇÃO — módulo Desenvolvedores somando project=SUS (além de BUG+BACKOFFICE).

Roda gen_data.py duas vezes: uma vez SEM sweep_sus.json (ANTES = BUG+BACKOFFICE, o estado
publicado hoje) e uma vez COM ele (DEPOIS = BUG+BACKOFFICE+SUS), e compara os 4 números
principais + Ciclo de vida de um desenvolvedor específico, lado a lado — exatamente o que a
Jane pediu pra validar antes de subir. Não altera nenhum arquivo do dashboard; usa fetch_jira.py/
gen_data.py como estão nesta branch.
"""
import json, os, shutil, subprocess, sys

DEV = 'Mauricio Ribeiro'


def rodar_gen_data():
    subprocess.run([sys.executable, 'gen_data.py'], check=True)
    return json.load(open('dash_data.json'))


def snapshot(d, dev):
    D = d['devs']
    if dev not in D['pessoas']:
        return None
    mj = D['pessoas'][dev]['metrics_jira']
    cur = d['mes_corrente']
    k = mj['kpi_por_mes'].get(cur, {})
    cv = (mj.get('ciclo_vida') or {}).get(cur, {'n': 0, 'cards': []})
    return {
        'concluidos': k.get('concluidos'),
        'esforco_h': k.get('esforco_h'),
        'mttr': k.get('mttr'),
        'mttr_n': k.get('mttr_n'),
        'em_dev_agora': mj.get('em_dev_agora'),
        'ciclo_vida_n': cv.get('n'),
        'ciclo_vida_cards': [(c['key'], c.get('origem'), c['status']) for c in cv.get('cards', [])],
    }


tem_sus = os.path.exists('sweep_sus.json')
if not tem_sus:
    print('AVISO: sweep_sus.json não existe (fetch de SUS falhou ou voltou 0 issues) — '
          'ANTES e DEPOIS vão ficar idênticos.')
else:
    shutil.move('sweep_sus.json', 'sweep_sus.json.bak')

print('Rodando gen_data.py SEM SUS (ANTES = BUG + BACKOFFICE)...')
d_antes = rodar_gen_data()
antes = snapshot(d_antes, DEV)

if tem_sus:
    shutil.move('sweep_sus.json.bak', 'sweep_sus.json')
print('Rodando gen_data.py COM SUS (DEPOIS = BUG + BACKOFFICE + SUS)...')
d_depois = rodar_gen_data()
depois = snapshot(d_depois, DEV)

print()
print('=' * 78)
print(f'{DEV} — safra em foco: {d_depois["mes_corrente"]}')
print('=' * 78)

if antes is None or depois is None:
    print(f'"{DEV}" não encontrado em d["devs"]["pessoas"] — abortando comparação.')
    sys.exit(1)

campos = [
    ('Concluídos', 'concluidos'),
    ('Esforço (h)', 'esforco_h'),
    ('MTTR pessoal (dias)', 'mttr'),
    ('MTTR — n amostras', 'mttr_n'),
    ('Em desenvolvimento agora', 'em_dev_agora'),
    ('Ciclo de vida — n cards', 'ciclo_vida_n'),
]
print(f'{"":28s} {"ANTES (BUG+BACKOFFICE)":24s} {"DEPOIS (+SUS)":24s}')
for label, campo in campos:
    print(f'{label:28s} {str(antes[campo]):24s} {str(depois[campo]):24s}')

print()
print('--- Ciclo de vida ANTES (BUG + BACKOFFICE) ---')
for k, o, s in antes['ciclo_vida_cards']:
    print(f'  {k}  [{o}]  {s}')

print()
print('--- Ciclo de vida DEPOIS (BUG + BACKOFFICE + SUS) ---')
for k, o, s in depois['ciclo_vida_cards']:
    print(f'  {k}  [{o}]  {s}')

keys_antes = {k for k, o, s in antes['ciclo_vida_cards']}
keys_depois = {k for k, o, s in depois['ciclo_vida_cards']}
so_depois = keys_depois - keys_antes
so_antes = keys_antes - keys_depois

print()
print(f'Cards NOVOS no Ciclo de vida (só aparecem DEPOIS): {sorted(so_depois) or "(nenhum)"}')
print(f'Cards que SUMIRAM (só apareciam ANTES): {sorted(so_antes) or "(nenhum)"}')

origem_novos = {k: o for k, o, s in depois['ciclo_vida_cards'] if k in so_depois}
todos_sus = all(o == 'SUS' for o in origem_novos.values())
print(f'Origem de cada card novo: {origem_novos}')
print(f'Todos os cards novos são de origem SUS? {"SIM" if todos_sus else "NÃO — ALERTA"}')

print()
print('=' * 78)
print('CHECAGEM DE CONSISTÊNCIA')
print('=' * 78)
ok = True
if so_antes:
    ok = False
    print('ALERTA: card sumiu do Ciclo de vida ao ligar SUS — não deveria acontecer '
          '(só estamos somando uma fonte nova, nunca removendo cards existentes).')
for label, campo in [('concluidos', 'concluidos'), ('esforco_h', 'esforco_h'), ('ciclo_vida_n', 'ciclo_vida_n')]:
    a, dd = antes[campo], depois[campo]
    if a is not None and dd is not None and dd < a:
        ok = False
        print(f'ALERTA: {label} DEPOIS ({dd}) < ANTES ({a}) — inesperado, só devíamos ganhar cards.')
if not todos_sus and origem_novos:
    ok = False
print()
print('RESULTADO:', 'CONSISTENTE' if ok else 'HÁ DIVERGÊNCIA — ver alertas acima')
