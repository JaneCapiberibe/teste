"""
inject_login.py — pega o dashboard recém-gerado (dashboard_setor.html), injeta o
"guardião" de login + botão Sair, e monta a pasta ./public para publicação no GitHub Pages:
  public/index.html               (= login.html)
  public/login.html
  public/forgot.html
  public/dashboard_setor_17.html  (protegido)
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
    open('public/dashboard_setor_17.html', 'w', encoding='utf-8').write(html)
    shutil.copyfile('login.html', 'public/login.html')
    shutil.copyfile('login.html', 'public/index.html')   # entrada do site = login
    shutil.copyfile('forgot.html', 'public/forgot.html')
    print('  public/ pronto: index.html (login) + dashboard_setor_17.html (protegido)')

if __name__ == '__main__':
    main()
