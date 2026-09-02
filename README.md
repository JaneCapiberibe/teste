# Dashboard do Setor — atualização diária automática (GitHub Actions)

Este repositório puxa os dados do Jira todo dia, reconstrói o dashboard e publica num
**link fixo** (GitHub Pages). Roda 100% na nuvem — **não depende do seu PC nem de abrir o Claude**.

## O que atualiza sozinho (todo dia)
Intake vs entregas, backlog acumulado (método Diego), severidade, qualidade e histórico por
módulo, ferramentas por módulo, sobra por status, impedimentos e responsáveis — tudo vindo do Jira.

## O que é snapshot (atualiza quando você reexporta)
Três seções vêm de exports que não estão no projeto BUG do Jira e ficam como arquivos fixos em
`inputs/`: **Build/Sentry** (`inputs/Resumo_bugs.xlsx`) e **tempo em status/previsibilidade**
(`inputs/suporte_list.csv`). Para atualizá-las, substitua esses dois arquivos no repositório.

---

## Configuração (uma vez só, ~10 min)

### 1. Criar o repositório
- No GitHub, crie um repositório novo (pode ser **privado**) e suba todos os arquivos deste pacote
  (mantendo as pastas `inputs/` e `.github/`).

### 2. Criar um token de API do Jira
- Acesse **https://id.atlassian.com/manage-profile/security/api-tokens** → **Create API token**.
- Dê um nome (ex.: "dashboard") e **copie o token** (só aparece uma vez).

### 3. Cadastrar os segredos no GitHub
No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Crie três:

| Nome | Valor |
|---|---|
| `JIRA_BASE_URL` | `https://orcafascio.atlassian.net` |
| `JIRA_EMAIL` | seu e-mail do Atlassian |
| `JIRA_API_TOKEN` | o token que você copiou no passo 2 |

### 4. Ligar o GitHub Pages
- **Settings → Pages → Build and deployment → Source: GitHub Actions**.

### 5. Rodar pela primeira vez
- Aba **Actions → "Atualizar dashboard (diário)" → Run workflow**.
- Ao terminar (uns 2 min), o link aparece em **Settings → Pages** (algo como
  `https://SEU-USUARIO.github.io/SEU-REPO/`). Esse é o link fixo para enviar aos avaliadores.

Depois disso, ele roda **sozinho todo dia** às 06:00 (horário de Brasília). Para mudar o horário,
edite o `cron` em `.github/workflows/update.yml`.

---

## Quem pode acessar (login)
A lista de usuários fica no topo do `login_template.html` (no `<script>`, `const USERS = [...]`)
— esse é o arquivo-fonte editável; `login.html` publicado é gerado a partir dele a cada deploy
(`inject_login.py`), não edite o publicado diretamente. Edite o template, faça commit, e o
próximo deploy publica. **Troque as senhas de exemplo.**

> Observação de segurança: o GitHub Pages deixa o link público — o login em HTML é uma trava leve
> (bom para avaliação). Para trava forte (página privada de verdade), dá para somar **Cloudflare
> Access** por cima depois.

## Rodar/testar localmente (opcional)
```
pip install -r requirements.txt
set JIRA_BASE_URL=https://orcafascio.atlassian.net   # (no Windows: use "set"; no Mac/Linux: "export")
set JIRA_EMAIL=voce@orcafascio.com
set JIRA_API_TOKEN=seu_token
python fetch_jira.py && python gen_data.py && python build_dash.py && python inject_login.py
```
O resultado fica em `public/` — abra `public/index.html`.
