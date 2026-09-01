# CLAUDE.md

Guia para trabalhar neste repositório — dashboard de bugs do setor de desenvolvimento.

## Pipeline

```
fetch_jira.py → sweep.json (+ jira_backlog.json, ni_assignee.json, sobra_live.json, impedimentos_live.json)
gen_data.py    → dash_data.json (lê sweep.json + inputs/*)
build_dash.py  → dashboard_setor.html (HTML estático, dados embutidos)
inject_login.py → adiciona a trava de login → public/index.html
```

`jira_backlog.json` ("método do Diego", em `fetch_jira.py`) **não é lido por `gen_data.py`** —
`d['tot_series']`/`d['evol_modulo']` calculam criados/concluídos direto do `sweep.json`
(`concluido_mes`), não desse arquivo. Ele existe só pra quem audita/consome fora deste
pipeline; ainda assim, "concluído" nele usa `concluido_mes` (changelog), nunca `updated`
(muda a cada edição tardia do card, vazando bugs pro mês errado — bug real já corrigido).

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

- **Não existe mais recorte BIM / Sem BIM no dashboard.** Esse corte (Todos/BIM/Sem BIM, com a
  classificação `_grupo`/`_BIM_KEYS`/`_INTERNO_KEYS`) existiu e chegou a alimentar os painéis de
  SLA e Previsibilidade do DEV, mas foi removido — os módulos "BIM" (produtos de time
  externo/PJ: OF Elétrico, OrçaBim, OF Hidráulico, OF Estrutural, OF BI) não têm mais um corte
  dedicado; os painéis de SLA/Previsibilidade voltaram a mostrar só o agregado geral
  (`d['previsibilidade']`, `d['severidade']`, `d['suporte_lag']`, sem indireção por grupo). Não
  reintroduza `d['recortes']`/`_grupo`/`_is_bim` "porque já existiu" — se precisar de um corte por
  módulo de novo, veja `d['mod_evol']` abaixo.

  **Evolução por módulo** (`d['evol_modulo']`, painel homônimo em `build_dash.py`) é o que
  substituiu aquele painel: para cada módulo, a mesma série `criados`/`concluidos`/`saldo`, pela
  **régua oficial** definida com o setor de dev (`evolucao_bugs.py` de referência, atualizada
  27/08/2026; exclusão de Cancelado Dev decidida em 01/09/2026 após levantamento de impacto —
  ver `levantamento_cancelado_dev.py`):
  - **Escopo**: só issuetype in (Bug Cliente, Bug QA, Bug Dev, Bug Backoffice).
  - **Fora de tudo** (nem criado nem concluído): resolução **Cancelado QA ou Cancelado Dev**,
    OU card ATUALMENTE parado no status IMPEDIMENTO PRODUTO ou Backlog (status atual, não o
    histórico — quem só passou por lá mas foi concluído/avançou conta normalmente). Backlog foi
    adicionado a pedido do setor: card ainda em Backlog não deve contar como "criado" na
    Evolução por módulo.
  - **Criado** = mês do campo `created`.
  - **Concluído** = mês da 1ª transição para "Em produção"/"Em Produção"; fallback: 1ª
    transição p/ "Done"/"Concluído"/"Concluido"; fallback final: mês de criação, pra card já
    terminal cujo changelog não tem a transição registrada. **Não** é `resolutiondate` —
    vazio em boa parte da base. Vem do campo `concluido_mes` (calculado em `fetch_jira.py` a
    partir do changelog de cada issue, puxado via `/changelog/bulkfetch`).
  - Saldo = acumulado criados−concluídos, começando em zero, só que por módulo em vez de
    agregado.
  A UI é comparativa (vários módulos ao mesmo tempo, uma métrica por vez, com "Todos"
  reproduzindo o agregado geral), com chips reaproveitados do padrão da "Tendência dos módulos"
  (`window.__emSel`, `emToggle`/`emSelectAll`/`emClearAll`, cor fixa por módulo via
  `trendColor`) — não duplique esse padrão de chip, estenda-o. Não volte pro método antigo
  (`resolutiondate`/só status atual) "porque já existiu" — essa é a régua combinada com o setor.

  **Não existe mais painel "Evolução histórica" separado.** Ele mostrava o mesmo agregado
  (`d['tot_series']`) que "Evolução por módulo" já reproduz exatamente selecionando "Todos" — foi
  removido para não duplicar a mesma informação em dois gráficos. `d['tot_series']` continua
  existindo em `gen_data.py` (usado pelo seletor de safra e outros KPIs), só a função `lineChart()`
  e o painel homônimo em `build_dash.py` foram removidos. Não reintroduza esse painel "porque já
  existiu" — se precisar do agregado geral, é "Todos" em Evolução por módulo.

- **Civil 3D não é separável.** Ele é um produto/integração externa (mesma família do BIM), mas no
  Jira é gravado como módulo **"Orçamento"** (interno) — não há campo próprio para isolá-lo. Não
  tente separá-lo por módulo; mantenha a nota existente no dashboard explicando essa limitação em
  vez de inventar uma heurística de texto para adivinhar quais bugs são Civil 3D.

## Antes de mexer em métricas

1. Confirme que a mudança usa `sweep` (base líquida), não `sweep_full`, a menos que o objetivo seja
   explicitamente mostrar os descartados.
2. Se a métrica precisa de um corte por módulo, veja se dá pra reaproveitar `d['evol_modulo']` (a
   régua oficial criaD/concD acima, por módulo) em vez de criar um cálculo novo do zero.
3. Se a métrica depende do CSV de Time-in-Status, lembre que ele é uma amostra **menor** que o
   total de bugs (nem todo card tem export de tempo em status) — trate a cobertura (`tis_n`) como
   um número à parte de `n` (total de bugs) e avise quando for pequena.
4. Depois de mudar `gen_data.py` e/ou `build_dash.py`, rode o pipeline localmente (ver
   `README.md` → "Rodar/testar localmente") e confira que `python build_dash.py` termina sem erro
   antes de subir a mudança.
