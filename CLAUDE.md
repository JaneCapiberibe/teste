# CLAUDE.md

Guia para trabalhar neste repositório — dashboard de bugs do setor de desenvolvimento.

## Pipeline

```
fetch_jira.py → sweep.json (+ jira_backlog.json, ni_assignee.json, sobra_live.json, impedimentos_live.json)
gen_data.py    → dash_data.json (lê sweep.json + inputs/*)
build_dash.py  → dashboard_setor.html (HTML estático, dados embutidos)
inject_login.py → adiciona a trava de login → public/index.html
```

Publicado via GitHub Actions (roda diário). Ver `README.md` para rodar localmente.

## Regras da casa (obrigatórias)

- **Jira é a fonte da verdade.** Toda métrica de bug vem do sweep (Jira, via `sweep.json`) ou do
  CSV de Time-in-Status (`inputs/suporte_list.csv`). **Nunca invente número** — se um dado não
  existe no Jira/CSV, não estimar “no olho”, deixar explícito que falta.

- **Base "líquida".** Toda métrica de bug exclui:
  - resolução **"Cancelado QA"** (descartado pelo QA, não é defeito de produto);
  - o módulo **"Chat de Suporte"** (foi aberto como bug mas é melhoria — pertence ao lado Build/PEM).

  `sweep` (em `gen_data.py`) já é a base líquida. `sweep_full` mantém tudo (cancelados incluídos)
  e só é usado onde isso é intencional (funil, indicador de descarte).

- **Recorte BIM / Sem BIM já existe — não crie um mecanismo novo.** Em `gen_data.py`, a função
  `_grupo` (com `_gk`, `_BIM_KEYS`, `_INTERNO_KEYS`) classifica cada módulo em `'bim'` ou
  `'interno'`. **"Sem BIM" é sempre o complemento de BIM** — nunca uma lista separada. Se aparecer
  um módulo não classificado, o build imprime `[AVISO recorte]` e assume `'interno'` até alguém
  adicionar o módulo em `_BIM_KEYS`/`_INTERNO_KEYS`.

  `d['recortes'] = {'todos': ..., 'bim': ..., 'interno': ...}` guarda, por grupo: a série mensal
  (criados/entregues/saldo/escape), a cobertura (`n` bugs, `apont` % apontamento, `tis_n` cards com
  Time-in-Status) e, desde a extensão de SLA/previsibilidade, também `severidade`,
  `previsibilidade` (SLA p95 por prioridade) `mttr_mediana` e `suporte_lag`. Qualquer painel novo
  que precise de um corte BIM/Sem BIM deve ler daqui — não recriar a classificação.

  Em `build_dash.py`, o controle Todos/BIM/Sem BIM vive em `window.__recorte` +
  `setRecorte(k)`. `setRecorte` re-renderiza todos os painéis que dependem do recorte
  (`#recwrap`, `#slawrap`, `#prevwrap`, ...) — ao adicionar um painel recortável, dê a ele um id e
  atualize-o dentro de `setRecorte`, em vez de duplicar a lógica de seleção.

  **Selo de cobertura:** `coberturaBadge(k)` é o único selo de amostra pequena (nº de bugs,
  apontamento, cards no Time-in-Status). Reaproveite-o em vez de escrever um aviso novo. Exemplo
  real: o recorte **BIM** tem só ~73 bugs, ~42% de apontamento e ~15 cards no Time-in-Status — é
  pouco, então qualquer variação mês a mês (ou de SLA/MTTR) nesse recorte é ruído, não tendência.
  Isso é esperado, não um bug nos dados.

- **Civil 3D não é separável.** Ele é um produto/integração externa (mesma família do BIM), mas no
  Jira é gravado como módulo **"Orçamento"** (interno) — não há campo próprio para isolá-lo. Não
  tente separá-lo por módulo; mantenha a nota existente no dashboard explicando essa limitação em
  vez de inventar uma heurística de texto para adivinhar quais bugs são Civil 3D.

## Antes de mexer em métricas

1. Confirme que a mudança usa `sweep` (base líquida), não `sweep_full`, a menos que o objetivo seja
   explicitamente mostrar os descartados.
2. Se a métrica precisa de recorte BIM/Sem BIM, adicione o cálculo dentro de
   `d['recortes'][grupo]` em `gen_data.py` (reaproveitando `_is_bim`/`_grupo`) — não crie um mapa
   de módulos paralelo.
3. Se a métrica depende do CSV de Time-in-Status, lembre que ele é uma amostra **menor** que o
   total de bugs (nem todo card tem export de tempo em status) — trate a cobertura (`tis_n`) como
   um número à parte de `n` (total de bugs) e avise quando for pequena.
4. Depois de mudar `gen_data.py` e/ou `build_dash.py`, rode o pipeline localmente (ver
   `README.md` → "Rodar/testar localmente") e confira que `python build_dash.py` termina sem erro
   antes de subir a mudança.
