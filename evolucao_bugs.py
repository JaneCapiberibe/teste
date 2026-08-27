"""
evolucao_bugs.py — gera a série de EVOLUÇÃO HISTÓRICA DE BUGS da OrçaFascio
seguindo a REGRA MÁXIMA definida com o setor de desenvolvimento.

Saída: evolucao_bugs.json  (lista de {mes, criados, concluidos, passou_proximo_mes})

--------------------------------------------------------------------------------
RÉGUA OFICIAL (única para criados, concluídos e fila)
--------------------------------------------------------------------------------
ESCOPO ...... "tudo que for bug": issuetype in
              ("Bug Cliente", "Bug QA", "Bug Dev", "Bug Backoffice").
FORA DE TUDO  (nem criado, nem concluído):
              - resolution == "Cancelado QA"  (ÚNICA resolução excluída)
              - cards ATUALMENTE parados no status "IMPEDIMENTO PRODUTO" (estagnados).
                Quem apenas PASSOU por impedimento produto (dev ou produto) mas foi
                concluído CONTA normalmente — tem data de criação e de conclusão.
                (IMPEDIMENTO DEV também continua contando — é responsabilidade do time.)
              OBS: "Cancelado Dev" CONTA como criado e concluído (é fechamento real,
              inclui duplicatas resolvidas via card-mãe). Só "Cancelado QA" fica fora.
CRIADO ...... mês do campo "created".
CONCLUÍDO ... mês em que o card ENTROU em "Em produção" (1ª transição p/ esse status).
              Fallback p/ quem nunca passou por "Em produção": mês da 1ª entrada
              em "Done". (resolutiondate NÃO é usado — está vazio na base.)
FILA ........ "quantos passaram para o mês seguinte" = resíduo do fluxo:
              fila(mes) = fila(mes-1) + criados(mes) - concluidos(mes), início 0.

--------------------------------------------------------------------------------
Credenciais (variáveis de ambiente — mesmos segredos do fetch_jira.py):
  JIRA_BASE_URL   ex.: https://orcafascio.atlassian.net
  JIRA_EMAIL      e-mail do Atlassian
  JIRA_API_TOKEN  token de API
--------------------------------------------------------------------------------
Referência de validação (puxado via JQL em 26/08/2026 — para conferência):
  2025 criados:    105 60 73 64 85 73 57 68 69 62 59 30   (Σ 805)
  2025 concluidos:  69 61 74 39 90 69 71 72 78 64 51 36
  2026 criados:     38 47 63 92 78 63 96 58   (Σ 535)
  2026 concluidos:  30 33 52 110 70 64 92 75
  fila oscila entre 29 e 64; termina em 40.  (Σ 1340 criados, 1300 concluídos)
NB: a soma mensal pode divergir ~1% do total anual por transições exatamente na
    virada de mês — esperado e sem impacto na forma da curva.
"""
import os
import json
import base64
import datetime
import collections
import requests

BASE = os.environ.get("JIRA_BASE_URL", "https://orcafascio.atlassian.net").rstrip("/")

# --- Régua (constantes) ------------------------------------------------------
BUG_TYPES = ("Bug Cliente", "Bug QA", "Bug Dev", "Bug Backoffice")
RES_FORA = ("Cancelado QA",)  # só Cancelado QA fica fora; Cancelado Dev conta
# Nomes de status conforme aparecem no changelog (o Jira usa nomes de exibição;
# "Concluído" e "Done" convivem — tratamos ambos).
ST_PRODUCAO = ("Em produção", "Em Produção")
ST_DONE = ("Done", "Concluído", "Concluido")
ST_IMP_PRODUTO = "IMPEDIMENTO PRODUTO"

# JQL do universo: todos os bugs (qualquer projeto). Puxamos amplo e aplicamos a
# régua em Python lendo o changelog. O filtro de tipo já reduz o volume.
_types = ",".join(f'"{t}"' for t in BUG_TYPES)
JQL = f"issuetype in ({_types}) ORDER BY created ASC"


def _headers():
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]
    auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()
    return {"Authorization": auth, "Accept": "application/json",
            "Content-Type": "application/json"}


def fetch_all():
    """Puxa os bugs COM changelog, paginando via nextPageToken."""
    head = _headers()
    url = f"{BASE}/rest/api/3/search/jql"
    fields = ["status", "resolution", "created", "issuetype"]
    out, token = [], None
    while True:
        body = {"jql": JQL, "fields": fields, "expand": ["changelog"],
                "maxResults": 100}
        if token:
            body["nextPageToken"] = token
        r = requests.post(url, headers=head, data=json.dumps(body), timeout=90)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("issues", []))
        token = data.get("nextPageToken")
        if not token:
            break
    return out


def _histories(issue):
    """Todas as mudanças de status do card, como (datetime, status_destino)."""
    changes = []
    for h in issue.get("changelog", {}).get("histories", []):
        created = h.get("created")
        for item in h.get("items", []):
            if item.get("field") == "status":
                changes.append((created, item.get("toString")))
    changes.sort(key=lambda x: x[0] or "")
    return changes


def _first_to(changes, status_names):
    """Data (YYYY-MM) da 1ª transição PARA qualquer nome em `status_names`."""
    names = (status_names,) if isinstance(status_names, str) else tuple(status_names)
    for dt, to in changes:
        if to in names and dt:
            return dt[:7]
    return None


def build_series(issues):
    criados = collections.Counter()
    concluidos = collections.Counter()

    for iss in issues:
        f = iss.get("fields", {})
        itype = (f.get("issuetype") or {}).get("name")
        if itype not in BUG_TYPES:
            continue
        res = (f.get("resolution") or {}).get("name")
        if res in RES_FORA:
            continue
        status = (f.get("status") or {}).get("name")
        changes = _histories(iss)

        # Fora de tudo: apenas quem está ESTAGNADO em IMPEDIMENTO PRODUTO agora.
        # Quem passou por lá mas saiu (foi concluído) continua contando.
        if status == ST_IMP_PRODUTO:
            continue

        # CRIADO
        created = f.get("created")
        if created:
            criados[created[:7]] += 1

        # CONCLUÍDO: entrada em produção; fallback = entrada em Done/Concluído.
        mes = _first_to(changes, ST_PRODUCAO)
        if not mes:
            mes = _first_to(changes, ST_DONE)
            # fallback final: já está terminal mas sem transição registrada
            if not mes and status in (ST_PRODUCAO + ST_DONE):
                mes = (created or "")[:7] or None
        if mes:
            concluidos[mes] += 1

    meses = sorted(set(list(criados) + list(concluidos)))
    serie, fila = [], 0
    for m in meses:
        c = criados.get(m, 0)
        k = concluidos.get(m, 0)
        fila = fila + c - k
        serie.append({"mes": m, "criados": c, "concluidos": k,
                      "passou_proximo_mes": fila})
    return serie


def main():
    print("Puxando bugs do Jira (com changelog)...")
    issues = fetch_all()
    serie = build_series(issues)
    with open("evolucao_bugs.json", "w", encoding="utf-8") as fh:
        json.dump(serie, fh, ensure_ascii=False, indent=1)
    tot_c = sum(x["criados"] for x in serie)
    tot_k = sum(x["concluidos"] for x in serie)
    fim = serie[-1]["passou_proximo_mes"] if serie else 0
    print(f"OK — evolucao_bugs.json | meses: {len(serie)} | "
          f"criados: {tot_c} | concluidos: {tot_k} | fila fim: {fim}")


if __name__ == "__main__":
    main()
