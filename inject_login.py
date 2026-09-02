"""
inject_login.py — pega o dashboard recém-gerado (dashboard_setor.html), injeta o
"guardião" de login + botão Sair, e monta a pasta ./public para publicação no GitHub Pages:
  public/index.html               (= login.html, gerado a partir de login_template.html)
  public/login.html               (idem)
  public/forgot.html
  public/dashboard_setor_<versao>.html  (protegido)

VERSIONAMENTO AUTOMÁTICO (decisão de 02/09/2026, substitui o bump manual "_17"/"_18"/"_19"):
o dashboard publicado é servido sempre com o mesmo nome de arquivo, sem cache-busting nenhum
(?v=, ETag, etc.) — o GitHub Pages/CDN ou o próprio navegador de quem já visitou o site podem
continuar servindo uma cópia antiga indefinidamente, mesmo com o pipeline rodando e publicando
dado novo. Antes disso exigia alguém lembrar de incrementar um número à mão em DOIS lugares
(aqui e em login.html) — e mais de uma vez só um dos dois foi atualizado, quebrando o
redirecionamento ou deixando o navegador preso na versão velha.

Agora o identificador de versão (`get_versao()` abaixo) é gerado sozinho a cada execução, sem
digitar nada: usa o hash curto do commit do Git — primeiro via GITHUB_SHA (variável de ambiente
que o GitHub Actions já injeta automaticamente em todo job, sem precisar rodar `git` nem
depender de profundidade de checkout), com fallback pra `git rev-parse --short HEAD` (rodar
local, fora do Actions) e fallback final pra timestamp (`AAAAMMDDHHMMSS`) se nem git estiver
disponível. Hash de commit foi escolhido em vez de timestamp puro como método PRINCIPAL por dois
motivos: (1) idempotência — re-rodar o pipeline no mesmo commit (ex.: workflow_dispatch manual
sem nenhuma mudança de código) gera a MESMA URL, em vez de invalidar cache à toa a cada run;
(2) rastreabilidade — o nome do arquivo publicado já diz de qual commit ele veio, útil pra
depurar "qual versão está no ar". O timestamp só entra como último recurso, quando nem GITHUB_SHA
nem `git` estão disponíveis.

login.html deixou de ser um arquivo estático commitado — login_template.html (no repo, é onde
se edita a lista de usuários) tem um placeholder `__DASH_FILENAME__` no lugar do nome do
arquivo; este script substitui o placeholder pelo nome real do dashboard gerado NESTA mesma
execução, então os dois nascem sempre sincronizados — não tem mais "esquecer de atualizar um
dos dois".
"""
import os, shutil, subprocess, datetime

GUARD = ('<script>(function(){try{var k="of_dash_auth";'
         'if(!(sessionStorage.getItem(k)||localStorage.getItem(k))){location.replace("login.html");}}'
         'catch(e){location.replace("login.html");}})();</script>')
LOGOUT = ('<div style="position:fixed;bottom:16px;right:16px;z-index:99999">'
          '<button onclick="try{sessionStorage.removeItem(\'of_dash_auth\');localStorage.removeItem(\'of_dash_auth\')}catch(e){};location.replace(\'login.html\')" '
          'style="background:#04043A;color:#fff;border:0;border-radius:9px;padding:8px 14px;'
          'font:600 12.5px \'Segoe UI\',system-ui,sans-serif;cursor:pointer;box-shadow:0 6px 18px rgba(4,4,58,.28)">Sair</button></div>')

def get_versao():
    """Identificador de versão pro nome do dashboard publicado — ver nota de versionamento
    automático no topo do arquivo. GITHUB_SHA (padrão, sempre presente em runs do Actions) >
    `git rev-parse --short HEAD` (rodando local) > timestamp (fallback final)."""
    sha = os.environ.get('GITHUB_SHA')
    if sha:
        return sha[:7]
    try:
        out = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                              capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')

def main():
    versao = get_versao()
    dash_filename = f'dashboard_setor_{versao}.html'

    html = open('dashboard_setor.html', encoding='utf-8').read()
    i = html.find('<head>')
    html = (html[:i+6] + GUARD + html[i+6:]) if i >= 0 else GUARD + html
    j = html.rfind('</body>')
    html = (html[:j] + LOGOUT + html[j:]) if j >= 0 else html + LOGOUT

    login_html = open('login_template.html', encoding='utf-8').read().replace('__DASH_FILENAME__', dash_filename)

    os.makedirs('public', exist_ok=True)
    open(f'public/{dash_filename}', 'w', encoding='utf-8').write(html)
    open('public/login.html', 'w', encoding='utf-8').write(login_html)
    open('public/index.html', 'w', encoding='utf-8').write(login_html)   # entrada do site = login
    shutil.copyfile('forgot.html', 'public/forgot.html')
    print(f'  versão gerada: {versao}')
    print(f'  public/ pronto: index.html (login) + {dash_filename} (protegido)')

if __name__ == '__main__':
    main()
