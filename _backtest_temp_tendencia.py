"""
Backtest exploratório: Run-rate simples vs Regressão linear, pra decidir o método de
previsão de "Tendência dos módulos — comparativo ano a ano". NÃO faz parte do pipeline —
script standalone, só lê sweep.json (gerado por fetch_jira.py) e imprime os resultados.

Reaproveita a MESMA lógica de dias úteis/n-ésimo dia útil já usada em gen_data.py
(_mes_bounds/_nth_busday_cutoff/busdays) pra ficar consistente com o resto do dashboard.
"""
import json, re, datetime, statistics, collections
import numpy as np

def busdays(a, b):
    return int(np.busday_count(a, b))

def mn(m):
    return 'Não classificado' if not m else re.sub(r'^\d+\s*-\s*', '', str(m)).strip()

def pdt(s):
    if not s:
        return None
    return datetime.datetime.fromisoformat(s)

def mes_bounds(ym):
    y, mo = map(int, ym.split('-'))
    import calendar
    return datetime.date(y, mo, 1), datetime.date(y, mo, calendar.monthrange(y, mo)[1])

def nth_busday_cutoff(ym, n):
    ini, fim = mes_bounds(ym)
    if n <= 0:
        return ini - datetime.timedelta(days=1)
    d = ini
    while d <= fim:
        if busdays(d, d + datetime.timedelta(days=1)) == 1:
            n -= 1
            if n == 0:
                return d
        d += datetime.timedelta(days=1)
    return fim

# ---- carregar dados (mesma base de "Bug por módulo"/evol_modulo: sweep, só excluindo
# Cancelado QA — conforme especificado pelo usuário) ----
sweep_full = json.load(open('sweep.json'))
for x in sweep_full:
    x['c'] = pdt(x['created'])
    x['m'] = mn(x['modulo'])
sweep = [x for x in sweep_full if x['res'] != 'Cancelado QA']

cria_mod = collections.defaultdict(lambda: collections.Counter())
for x in sweep:
    if x['c']:
        cria_mod[x['m']][x['c'].strftime('%Y-%m')] += 1

meses = sorted({x['c'].strftime('%Y-%m') for x in sweep if x['c']})
TODAY = datetime.date.today()
cur_ym = str(TODAY)[:7]
closed_months = [m for m in meses if m < cur_ym]

print(f"Meses totais: {meses[0]} .. {meses[-1]} (n={len(meses)})")
print(f"Mês corrente (excluído, aberto): {cur_ym}")
print(f"Meses fechados: {closed_months[0]} .. {closed_months[-1]} (n={len(closed_months)})")

# ---- piso de volume: módulo entra no backtest se média de criados/mês (sobre os meses
# fechados) for >= PISO ----
PISO_MEDIA_MENSAL = 5
modulos_todos = sorted(cria_mod.keys())
medias = {mod: (sum(cria_mod[mod].get(m, 0) for m in closed_months) / len(closed_months))
          for mod in modulos_todos}
modulos_ok = sorted([m for m in modulos_todos if medias[m] >= PISO_MEDIA_MENSAL], key=lambda m: -medias[m])
print(f"\nMódulos com média >= {PISO_MEDIA_MENSAL} bugs/mês ({len(modulos_ok)} de {len(modulos_todos)}):")
for mod in modulos_ok:
    print(f"  {mod}: média {medias[mod]:.1f}/mês")

# ---- testável: precisa de 6 meses fechados anteriores pra regressão ----
if len(closed_months) < 7:
    print("\n!!! Não há meses fechados suficientes (precisa de pelo menos 7) — abortando.")
    raise SystemExit(1)
testaveis = closed_months[6:]
print(f"\nMeses testáveis (excluídos os primeiros 6 fechados, sem base p/ regressão): "
      f"{testaveis[0]} .. {testaveis[-1]} (n={len(testaveis)})")

CHECKPOINTS = [0.25, 0.50, 0.75]

# resultados[metodo][modulo][checkpoint] = lista de (erro_abs, erro_pct_ou_None)
resultados = {
    'runrate': collections.defaultdict(lambda: collections.defaultdict(list)),
    'regressao': collections.defaultdict(lambda: collections.defaultdict(list)),
}
mape_excluidos = 0  # (module,month,checkpoint) com real_final==0, MAPE indefinido

for ym in testaveis:
    idx = closed_months.index(ym)
    training_months = closed_months[idx - 6:idx]
    assert len(training_months) == 6
    ini, fim = mes_bounds(ym)
    total_dias_uteis = busdays(ini, fim + datetime.timedelta(days=1))

    for mod in modulos_ok:
        real_final = cria_mod[mod].get(ym, 0)

        # regressão: ajusta sobre os 6 meses de treino, prevê x=6 (não usa dado parcial do mês em teste)
        train_y = [cria_mod[mod].get(mh, 0) for mh in training_months]
        train_x = list(range(6))
        a, b = np.polyfit(train_x, train_y, 1)
        proj_regressao = a * 6 + b
        proj_regressao = max(0.0, proj_regressao)  # não faz sentido prever negativo

        for frac in CHECKPOINTS:
            n = max(1, round(frac * total_dias_uteis))
            cutoff = nth_busday_cutoff(ym, n)
            criados_ate_agora = sum(
                1 for x in sweep
                if x['m'] == mod and x['c'] and x['c'].strftime('%Y-%m') == ym and x['c'].date() <= cutoff
            )
            proj_runrate = (criados_ate_agora / n) * total_dias_uteis

            for metodo, proj in (('runrate', proj_runrate), ('regressao', proj_regressao)):
                erro_abs = abs(proj - real_final)
                erro_pct = (erro_abs / real_final * 100) if real_final > 0 else None
                if real_final == 0 and metodo == 'runrate':
                    mape_excluidos += 1
                resultados[metodo][mod][frac].append((erro_abs, erro_pct, ym))

# ---- agregação: MAE/MAPE por módulo x checkpoint, por módulo geral, por checkpoint geral, geral total ----
def agrega(lista):
    abs_vals = [e[0] for e in lista]
    pct_vals = [e[1] for e in lista if e[1] is not None]
    mae = statistics.mean(abs_vals) if abs_vals else None
    mape = statistics.mean(pct_vals) if pct_vals else None
    return mae, mape, len(abs_vals), len(lista) - len(pct_vals)

print("\n" + "=" * 100)
print("TABELA: módulo × checkpoint × MAE/MAPE de cada método")
print("=" * 100)
header = f"{'Módulo':<22} {'Chk':>4} | {'Run-rate MAE':>13} {'MAPE%':>8} | {'Regressão MAE':>14} {'MAPE%':>8} | {'n':>4}"
print(header)
print("-" * len(header))
for mod in modulos_ok:
    for frac in CHECKPOINTS:
        rr = resultados['runrate'][mod][frac]
        rg = resultados['regressao'][mod][frac]
        mae_rr, mape_rr, n_rr, _ = agrega(rr)
        mae_rg, mape_rg, n_rg, _ = agrega(rg)
        chk_lbl = f"{int(frac*100)}%"
        print(f"{mod:<22} {chk_lbl:>4} | {mae_rr:>13.2f} {mape_rr if mape_rr is None else round(mape_rr,1):>8} | "
              f"{mae_rg:>14.2f} {mape_rg if mape_rg is None else round(mape_rg,1):>8} | {n_rr:>4}")

print("\n" + "=" * 100)
print("RESUMO POR MÓDULO (todos os checkpoints juntos)")
print("=" * 100)
for mod in modulos_ok:
    todos_rr = [e for frac in CHECKPOINTS for e in resultados['runrate'][mod][frac]]
    todos_rg = [e for frac in CHECKPOINTS for e in resultados['regressao'][mod][frac]]
    mae_rr, mape_rr, n, _ = agrega(todos_rr)
    mae_rg, mape_rg, _, _ = agrega(todos_rg)
    vencedor = 'Run-rate' if mae_rr < mae_rg else 'Regressão'
    print(f"{mod:<22} n={n:<4} Run-rate MAE={mae_rr:.2f} MAPE={mape_rr:.1f}%  |  "
          f"Regressão MAE={mae_rg:.2f} MAPE={mape_rg:.1f}%  |  vence por MAE: {vencedor}")

print("\n" + "=" * 100)
print("RESUMO POR CHECKPOINT (todos os módulos juntos)")
print("=" * 100)
for frac in CHECKPOINTS:
    todos_rr = [e for mod in modulos_ok for e in resultados['runrate'][mod][frac]]
    todos_rg = [e for mod in modulos_ok for e in resultados['regressao'][mod][frac]]
    mae_rr, mape_rr, n, _ = agrega(todos_rr)
    mae_rg, mape_rg, _, _ = agrega(todos_rg)
    vencedor = 'Run-rate' if mae_rr < mae_rg else 'Regressão'
    print(f"{int(frac*100)}% do mês  n={n:<5} Run-rate MAE={mae_rr:.2f} MAPE={mape_rr:.1f}%  |  "
          f"Regressão MAE={mae_rg:.2f} MAPE={mape_rg:.1f}%  |  vence por MAE: {vencedor}")

print("\n" + "=" * 100)
print("RESUMO GERAL (todos os módulos, todos os checkpoints)")
print("=" * 100)
todos_rr = [e for mod in modulos_ok for frac in CHECKPOINTS for e in resultados['runrate'][mod][frac]]
todos_rg = [e for mod in modulos_ok for frac in CHECKPOINTS for e in resultados['regressao'][mod][frac]]
mae_rr, mape_rr, n, exc_rr = agrega(todos_rr)
mae_rg, mape_rg, _, exc_rg = agrega(todos_rg)
print(f"n = {n} combinações (módulo x mês testável x checkpoint)")
print(f"Run-rate  : MAE = {mae_rr:.2f} bugs | MAPE = {mape_rr:.1f}% (excluídos {exc_rr} casos com real=0)")
print(f"Regressão : MAE = {mae_rg:.2f} bugs | MAPE = {mape_rg:.1f}% (excluídos {exc_rg} casos com real=0)")
if mae_rr < mae_rg:
    dif = (mae_rg - mae_rr) / mae_rg * 100
    print(f"\n>>> VENCEDOR POR MAE: Run-rate simples (erro {dif:.1f}% menor que a Regressão)")
else:
    dif = (mae_rr - mae_rg) / mae_rr * 100
    print(f"\n>>> VENCEDOR POR MAE: Regressão linear (erro {dif:.1f}% menor que o Run-rate)")
if mape_rr is not None and mape_rg is not None:
    if mape_rr < mape_rg:
        print(f">>> VENCEDOR POR MAPE: Run-rate simples ({mape_rr:.1f}% vs {mape_rg:.1f}%)")
    else:
        print(f">>> VENCEDOR POR MAPE: Regressão linear ({mape_rg:.1f}% vs {mape_rr:.1f}%)")

# dump JSON pra eu poder reanalisar sem rodar de novo
detalhe = {}
for mod in modulos_ok:
    detalhe[mod] = {}
    for frac in CHECKPOINTS:
        mae_rr, mape_rr, n_rr, _ = agrega(resultados['runrate'][mod][frac])
        mae_rg, mape_rg, n_rg, _ = agrega(resultados['regressao'][mod][frac])
        detalhe[mod][f"{int(frac*100)}%"] = {
            'runrate': {'mae': mae_rr, 'mape': mape_rr},
            'regressao': {'mae': mae_rg, 'mape': mape_rg},
            'n': n_rr,
        }
out = {
    'meses_testaveis': testaveis,
    'modulos_ok': modulos_ok,
    'medias_modulo': medias,
    'detalhe_modulo_x_checkpoint': detalhe,
    'resumo_geral': {
        'runrate': {'mae': mae_rr, 'mape': mape_rr, 'n': n},
        'regressao': {'mae': mae_rg, 'mape': mape_rg, 'n': n},
    },
}
json.dump(out, open('backtest_resultado.json', 'w'), ensure_ascii=False, indent=2)
print("\nResumo salvo em backtest_resultado.json")
