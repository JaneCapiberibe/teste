"""
inject_login.py — pega o dashboard recém-gerado (dashboard_setor.html), injeta o
"guardião" de login + botão Sair, e monta a pasta ./public para publicação no GitHub Pages:
  public/index.html               (= login.html)
  public/login.html
  public/forgot.html
  public/dashboard_setor_19.html  (protegido)

NOTA SOBRE CACHE (achado em 02/09/2026): o dashboard publicado sempre foi servido com esse
mesmo nome de arquivo, sem cache-busting nenhum (?v=, ETag, etc.) — o GitHub Pages/CDN ou o
próprio navegador de quem já visitou o site podem continuar servindo uma cópia antiga
indefinidamente, mesmo com o pipeline rodando e publicando dado novo (foi exatamente o que
aconteceu: usuária viu números velhos mesmo após o run de "Atualizar dashboard" terminar com
sucesso). O "_18" no nome é o mecanismo de cache-busting: força os navegadores a buscar uma
URL nova, nunca vista, ignorando qualquer cópia em cache. Se isso acontecer de novo (usuária
relata que o dashboard "não atualizou visualmente" mesmo com o pipeline verde), o fix é
simplesmente incrementar esse número aqui E em login.html (const DASH), não investigar
gen_data.py/build_dash.py de novo — o dado já está certo, só o navegador está com cache velho.
"""
import os, shutil

GUARD = ('<script>(function(){try{var k="of_dash_auth";'
         'if(!(sessionStorage.getItem(k)||localStorage.getItem(k))){location.replace("login.html");}}'
         'catch(e){location.replace("login.html");}})();</script>')
LOGOUT = ('<div style="position:fixed;bottom:16px;right:16px;z-index:99999">'
          '<button onclick="try{sessionStorage.removeItem(\'of_dash_auth\');localStorage.removeItem(\'of_dash_auth\')}catch(e){};location.replace(\'login.html\')" '
          'style="background:#04043A;color:#fff;border:0;border-radius:9px;padding:8px 14px;'
          'font:600 12.5px \'Segoe UI\',system-ui,sans-serif;cursor:pointer;box-shadow:0 6px 18px rgba(4,4,58,.28)">Sair</button></div>')

def main():
    html = open('dashboard_setor.html', encoding='utf-8').read()
    i = html.find('<head>')
    html = (html[:i+6] + GUARD + html[i+6:]) if i >= 0 else GUARD + html
    j = html.rfind('</body>')
    html = (html[:j] + LOGOUT + html[j:]) if j >= 0 else html + LOGOUT

    os.makedirs('public', exist_ok=True)
    open('public/dashboard_setor_19.html', 'w', encoding='utf-8').write(html)
    shutil.copyfile('login.html', 'public/login.html')
    shutil.copyfile('login.html', 'public/index.html')   # entrada do site = login
    shutil.copyfile('forgot.html', 'public/forgot.html')
    print('  public/ pronto: index.html (login) + dashboard_setor_19.html (protegido)')

if __name__ == '__main__':
    main()
