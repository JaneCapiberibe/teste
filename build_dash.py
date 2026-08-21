import json, base64, io
d=json.load(open('dash_data.json'))
_LOGO_PATH='inputs/logo.png'
LOGO='data:image/png;base64,'+base64.b64encode(open(_LOGO_PATH,'rb').read()).decode()
# versão para o MODO ESCURO: texto navy -> branco, marca azul mantida (alpha preservado p/ anti-serrilhado)
def _logo_dark():
    try:
        from PIL import Image
        im=Image.open(_LOGO_PATH).convert('RGBA'); px=im.load(); w,h=im.size
        for y in range(h):
            for x in range(w):
                r,g,b,a=px[x,y]
                if a==0: continue
                is_blue = b>110 and (b-r)>50 and (b-g)>30
                if not is_blue: px[x,y]=(255,255,255,a)   # navy/preto -> branco
        buf=io.BytesIO(); im.save(buf,'PNG')
        return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return LOGO
LOGO_DARK=_logo_dark()

DATA=json.dumps(d,ensure_ascii=False)

html = r'''<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard do Setor de Desenvolvimento — OrçaFascio</title>
<!-- Ícones embutidos como SVG inline (sem CDN) para renderizar em qualquer ambiente, inclusive no painel de artifact -->
<style>
@import url('https://fonts.googleapis.com/css2?family=Pathway+Extreme:opsz,wght@8..144,300;8..144,400;8..144,600;8..144,700;8..144,800&display=swap');
/* --- overrides defensivos: nossos componentes vencem o Bootstrap (nomes .card/.badge/.alert colidem) --- */
.card{display:block!important}
.dash-badge,.badge{line-height:1.4}
/* --- ícone de seção (motif do sistema) --- */
.sec-ico{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:7px;background:rgba(0,95,232,.12);color:var(--brand-blue);margin-right:10px;font-size:13px;vertical-align:middle}
h2{display:flex;align-items:center}
h2 .info{margin-left:8px}
.kpi-ico{color:var(--brand-blue);margin-right:7px;width:15px;height:15px}
.ic{width:1em;height:1em;display:inline-block;vertical-align:-0.125em;flex:none}
.sec-ico .ic{width:15px;height:15px}
.safra-ico .ic{width:19px;height:19px}
.safra-caret .ic,.ic.safra-caret{width:12px;height:12px}
:root{
  color-scheme:light;
  --brand-navy:#04043A; --brand-blue:#005FE8;
  --surface-0:#eef1f6; --surface-1:#ffffff; --surface-2:#f3f5fa;
  --text-1:#04043A; --text-2:#454a63; --text-3:#8a8fa3; --line:#dde2ec;
  --s1:#005FE8; --s2:#eb6834; --s3:#1e9e5a; --s4:#f0a500; --s5:#e87ba4; --s8:#e2384d;
  --good:#1e9e5a; --warn:#f0a500; --bad:#e2384d;
}
:root[data-theme="dark"]{
  /* Dark theme seguindo Material Design / Apple HIG / Nielsen Norman:
     - base NÃO é preto puro nem azul saturado: grafite levemente frio (#12) → reduz vibração e cansaço visual
     - superfícies em elevação: quanto mais "alto" o elemento, mais claro (fundo < card < chip)
     - texto branco de alta ênfase a ~87-90% (não #fff puro) para baixar o contraste agressivo
     - azul da marca CLAREADO e dessaturado para acento (cores saturadas "vibram" no escuro) */
  color-scheme:dark;
  --brand-blue:#6fa8ff;
  --surface-0:#111218; --surface-1:#1a1c25; --surface-2:#252834;
  --text-1:#e9ebf2; --text-2:#b4b8c9; --text-3:#7f8497; --line:#2d3040;
  --s1:#6fa8ff; --s2:#f0915c; --s3:#46c98a; --s4:#ffcb5c; --s5:#e89bb8; --s8:#ff6b78;
  --good:#46c98a; --warn:#ffcb5c; --bad:#ff6b78;
}
:root[data-theme="dark"] .safra-bar{background:linear-gradient(90deg,rgba(111,168,255,.06),rgba(111,168,255,.10))}
:root[data-theme="dark"] .icon-btn.avatar{background:var(--brand-blue);color:#0e1017}
:root[data-theme="dark"] .sec-ico{background:rgba(111,168,255,.16)}
:root[data-theme="dark"] header{box-shadow:0 1px 0 rgba(255,255,255,.03)}
/* fundo claro fixo por padrão; modo escuro só pelo botão "alternar tema" */
*{box-sizing:border-box}
body{margin:0;background:var(--surface-0);color:var(--text-1);
  font-family:'Pathway Extreme',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:14px;line-height:1.45}
header{padding:18px 28px;border-bottom:3px solid var(--brand-blue);background:var(--surface-1);display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:18px}
.brand{display:flex;align-items:center;gap:20px}
.brand img{height:120px;width:auto;display:block}
.brand img.logo-dark{display:none}
:root[data-theme="dark"] .brand img.logo-light{display:none}
:root[data-theme="dark"] .brand img.logo-dark{display:block}
.brand .divider{width:1px;height:88px;background:var(--line)}
h1{font-size:20px;margin:0;color:var(--text-1);font-weight:700;letter-spacing:-.2px}
.sub{color:#454a63;font-size:12.5px;margin-top:3px}
main{max-width:1180px;margin:0 auto;padding:22px 18px 60px}
.toggle{border:1px solid var(--line);background:var(--surface-2);color:var(--text-2);border-radius:8px;padding:7px 12px;cursor:pointer;font-size:12px;font-family:inherit}
.hdr-actions{display:flex;align-items:center;gap:10px}
.icon-btn{position:relative;width:40px;height:40px;border:1px solid var(--line);background:var(--surface-2);color:var(--text-1);border-radius:50%;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;font-size:16px;transition:background .15s,border-color .15s}
.icon-btn:hover{background:rgba(0,95,232,.10);border-color:var(--brand-blue);color:var(--brand-blue)}
.icon-btn .badge{position:absolute;top:-3px;right:-3px;min-width:16px;height:16px;padding:0 4px;border-radius:9px;background:var(--danger,#e34948);color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;border:2px solid var(--surface-2);font-family:inherit;line-height:1}
.icon-btn.avatar{background:var(--brand-navy);color:#fff;font-weight:700;font-size:14px}
.icon-btn.avatar:hover{background:var(--brand-blue)}
.hdr-sep{width:1px;height:26px;background:var(--line);margin:0 2px}
.safra-bar{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-bottom:16px;padding:14px 18px;border-radius:12px;background:linear-gradient(90deg,rgba(4,4,58,.04),rgba(0,95,232,.06));border:1px solid var(--line);border-left:5px solid var(--brand-blue)}
.safra-left{display:flex;align-items:center;gap:13px}
.safra-ico{width:40px;height:40px;flex:0 0 40px;border-radius:10px;background:var(--brand-blue);color:#fff;display:flex;align-items:center;justify-content:center;font-size:17px;box-shadow:0 4px 12px rgba(0,95,232,.28)}
.safra-title{font-weight:700;color:var(--text-1);font-size:15px;display:flex;align-items:center;gap:8px}
.safra-tag{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--brand-blue);background:rgba(0,95,232,.13);padding:2px 8px;border-radius:20px}
.safra-hint{color:var(--text-3);font-size:11.5px;margin-top:2px}
.safra-ctrl{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.safra-select-wrap{position:relative;display:inline-flex;align-items:center}
.safra-select-wrap select{appearance:none;-webkit-appearance:none;border:1px solid var(--line);background:var(--surface-1);color:var(--text-1);border-radius:9px;padding:9px 34px 9px 14px;font-size:13.5px;font-weight:600;font-family:inherit;cursor:pointer;box-shadow:0 1px 3px rgba(4,4,58,.06);transition:border-color .15s,box-shadow .15s}
.safra-select-wrap select:hover,.safra-select-wrap select:focus{border-color:var(--brand-blue);box-shadow:0 0 0 3px rgba(0,95,232,.14);outline:none}
.safra-caret{position:absolute;right:13px;pointer-events:none;color:var(--brand-blue);font-size:11px}
.safra-mini{display:flex;gap:8px;flex-wrap:wrap}
.safra-chip{font-size:11.5px;color:var(--text-2);background:var(--surface-1);border:1px solid var(--line);border-radius:20px;padding:4px 11px}
.safra-chip b{color:var(--text-1);font-size:12.5px}
.safra-chip.ok{border-color:rgba(35,160,110,.35)}.safra-chip.ok b{color:#1e9a63}
.safra-chip.warn{border-color:rgba(245,166,35,.4)}.safra-chip.warn b{color:#d98a00}
.safra-pill{position:relative;display:inline-flex;align-items:center;margin-left:9px;vertical-align:middle}
.safra-pill .safra-caret{position:absolute;right:10px;color:var(--brand-blue)}
.safra-pill-sel{appearance:none;-webkit-appearance:none;border:1px solid rgba(0,95,232,.30);background:rgba(0,95,232,.10);color:var(--brand-blue);font-weight:700;border-radius:20px;padding:4px 28px 4px 13px;font-size:12px;font-family:inherit;cursor:pointer;transition:background .15s,border-color .15s}
.safra-pill-sel:hover,.safra-pill-sel:focus{background:rgba(0,95,232,.17);border-color:var(--brand-blue);outline:none}
.safra-prod{display:flex;gap:7px;flex-wrap:wrap;align-items:center}
.prodbtn{border:1px solid var(--line);background:var(--surface-1);color:var(--text-2);border-radius:20px;padding:6px 14px;font-size:12.5px;font-weight:600;font-family:inherit;cursor:pointer;transition:all .15s}
.prodbtn:hover{border-color:var(--brand-blue);color:var(--brand-blue)}
.prodbtn.on{background:var(--brand-blue);border-color:var(--brand-blue);color:#fff;box-shadow:0 2px 8px rgba(0,95,232,.25)}
.prod-banner{display:flex;align-items:flex-start;gap:10px;background:rgba(0,95,232,.06);border:1px solid var(--line);border-left:4px solid var(--brand-blue);border-radius:10px;padding:11px 14px;margin-bottom:16px;font-size:12.5px;color:var(--text-2)}
.prod-banner b{color:var(--brand-navy)}
.tag-per{display:inline-block;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--text-3);background:var(--surface-2);border:1px solid var(--line);padding:1px 6px;border-radius:20px;vertical-align:middle;margin-left:4px}
.note-c{background:var(--surface-2);border:1px solid var(--line);border-left:3px solid var(--s4);border-radius:9px;margin-top:12px;font-size:11.5px;color:var(--text-2);overflow:hidden;transition:box-shadow .18s,border-color .18s}
.note-c:hover{box-shadow:0 3px 14px rgba(4,4,58,.06)}
.note-c>summary{cursor:pointer;padding:9px 14px;font-weight:600;color:var(--text-2);list-style:none;display:flex;align-items:center;gap:9px;user-select:none;letter-spacing:.2px;transition:color .15s}
.note-c>summary:hover{color:var(--brand-navy)}
.note-c>summary::-webkit-details-marker{display:none}
.note-c>summary::before{content:'';width:6px;height:6px;border-right:2px solid var(--s4);border-bottom:2px solid var(--s4);border-radius:1px;transform:rotate(-45deg);transition:transform .2s ease;flex:none;margin-top:-1px}
.note-c[open]>summary::before{transform:rotate(45deg)}
.note-c[open]>summary{color:var(--brand-navy)}
.note-body{padding:2px 15px 13px 15px;line-height:1.55;animation:noteIn .18s ease}
@keyframes noteIn{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:none}}
.fila-break{margin-top:16px}
.fila-break-h{font-size:12px;font-weight:700;color:var(--brand-navy);margin-bottom:8px}
.fila-bar{display:flex;height:12px;border-radius:6px;overflow:hidden;background:var(--surface-2)}
.fila-bar>div{height:100%}
.fila-chips{display:flex;gap:14px;flex-wrap:wrap;margin-top:9px}
.fila-chip{font-size:11.5px;color:var(--text-2);display:inline-flex;align-items:center;gap:6px}
.fila-chip i{width:9px;height:9px;border-radius:2px;display:inline-block;flex:none}
.fila-chip b{color:var(--brand-navy)}
.imp-spot{margin-top:14px;border:1px solid var(--line);border-left:4px solid var(--bad);border-radius:10px;background:rgba(226,56,77,.05);padding:13px 16px}
.imp-h{font-size:13px;color:var(--brand-navy);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.imp-body{display:flex;align-items:center;gap:20px;margin-top:11px;flex-wrap:wrap}
.imp-big{font-size:38px;font-weight:800;color:var(--bad);line-height:1;flex:none}
.imp-split{display:flex;flex-direction:column;gap:7px}
.imp-item{font-size:12.5px;color:var(--text-2)}
.imp-item b{color:var(--brand-navy)}
.imp-item a,.imp-foot a{color:var(--brand-blue);text-decoration:none;font-weight:600;font-size:11.5px;margin-left:6px;white-space:nowrap}
.imp-item a:hover,.imp-foot a:hover{text-decoration:underline}
.imp-foot{font-size:11.5px;color:var(--text-3);margin-top:11px;border-top:1px solid var(--line);padding-top:9px}
.trend-chips{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:12px}
.trend-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--surface-1);color:var(--text-2);border-radius:20px;padding:4px 11px;font-size:11.5px;font-weight:600;font-family:inherit;cursor:pointer;transition:opacity .12s,background .12s,border-color .12s;opacity:.7}
.trend-chip i{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
.trend-chip:hover{opacity:1}
.trend-chip.on{color:#fff;opacity:1}
.trend-chip.on i{background:#fff!important}
.trend-chip.on b{color:#fff}
.mh-c{margin:0}
.mh-c>summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:700;color:var(--brand-navy);padding:10px 2px 8px;user-select:none;transition:color .15s}
.mh-c>summary:hover{color:var(--brand-navy)}
.mh-c>summary::-webkit-details-marker{display:none}
.mh-c>summary::before{content:'';width:6px;height:6px;border-right:2px solid var(--brand-blue);border-bottom:2px solid var(--brand-blue);transform:rotate(45deg);transition:transform .2s;flex:none;margin-bottom:2px}
.mh-c:not([open])>summary::before{transform:rotate(-45deg);margin-bottom:0}
.mh-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:6px 0 10px}
.mh-kpi{background:var(--surface-1);border:1px solid var(--line);border-radius:12px;padding:12px 14px;text-align:center}
.mh-kpi-lbl{font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--text-3)}
.mh-kpi-num{font-size:26px;font-weight:800;line-height:1.15;color:var(--text-1);margin:2px 0}
.mh-kpi-sub{font-size:11px;color:var(--text-2)}
@media(max-width:640px){.mh-kpis{grid-template-columns:1fr}}
.safra-chip.prod b{color:var(--brand-navy)}
.safra-chip.prod.prime{border-color:rgba(0,95,232,.35)}.safra-chip.prod.prime b{color:var(--brand-blue)}
.safra-chip.prod.novo{border-color:rgba(30,158,90,.35)}.safra-chip.prod.novo b{color:#1e9a63}
.safra-chip.prod.antigo{border-color:rgba(138,143,163,.5)}.safra-chip.prod.antigo b{color:var(--text-2)}
.info{display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:50%;background:var(--s1);color:#fff;font-size:10px;font-weight:700;cursor:help;margin-left:6px;position:relative;font-style:normal;vertical-align:middle;letter-spacing:0}
.info:hover::after{content:attr(data-tip);position:absolute;left:0;top:150%;width:300px;max-width:80vw;background:var(--brand-navy);color:#fff;padding:11px 13px;border-radius:9px;font-size:11.5px;font-weight:400;line-height:1.45;z-index:30;box-shadow:0 8px 26px rgba(4,4,58,.35);white-space:normal;text-align:left;text-transform:none}
.info:hover::before{content:"";position:absolute;left:5px;top:132%;border:6px solid transparent;border-bottom-color:var(--brand-navy);z-index:30}
.info.tl:hover::after{left:auto;right:0}
.info.tl:hover::before{left:auto;right:5px}
th .info{margin-left:4px}
h2{font-size:13px;letter-spacing:.3px;color:var(--s1);margin:32px 4px 12px;font-weight:700}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:13px}
.card{background:var(--surface-1);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpi-label{font-size:12px;color:var(--text-2);margin-bottom:8px}
.kpi-val{font-size:30px;font-weight:700;letter-spacing:-.5px}
.kpi-sub{font-size:12px;color:var(--text-3);margin-top:6px}
.na{color:var(--warn);font-weight:700;font-size:15px}
.alert{background:rgba(227,73,72,.10);border:1px solid var(--bad);border-left:5px solid var(--bad);border-radius:12px;padding:16px 18px;margin-bottom:6px}
.alert.ok{background:rgba(27,175,122,.10);border-color:var(--good);border-left-color:var(--good)}
.alert h3{margin:0 0 4px;font-size:16px;display:flex;align-items:center;gap:10px}
.alert .big{font-size:26px;font-weight:800;color:var(--bad)}
.alert.ok .big{color:var(--good)}
.alert table{margin-top:10px}
.alert td,.alert th{padding:5px 8px;font-size:12.5px}
.pill{font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;background:rgba(227,73,72,.16);color:var(--bad)}
.badge{display:inline-block;font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;letter-spacing:.3px}
.b-up{background:rgba(227,73,72,.14);color:var(--bad)} .b-down{background:rgba(27,175,122,.16);color:var(--good)} .b-flat{background:var(--surface-2);color:var(--text-3)}
.panel{background:var(--surface-1);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:14px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line)}
th{color:var(--text-2);font-size:11px;letter-spacing:.2px;cursor:pointer;user-select:none;font-weight:600}
th:hover{color:var(--text-1)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.heat{border-radius:5px;padding:2px 8px;font-variant-numeric:tabular-nums;display:inline-block;min-width:42px;text-align:right}
.note{background:var(--surface-2);border-left:3px solid var(--s4);border-radius:6px;padding:10px 13px;font-size:12px;color:var(--text-2);margin-top:12px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--text-2);margin:4px 0 10px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.dot{width:10px;height:10px;border-radius:3px;display:inline-block}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:820px){.grid2{grid-template-columns:1fr}}
.tt{position:fixed;pointer-events:none;background:var(--text-1);color:var(--surface-1);padding:6px 9px;border-radius:6px;font-size:12px;opacity:0;transition:opacity .1s;z-index:9;white-space:nowrap}
.bar-row{display:flex;align-items:center;gap:10px;margin:5px 0}
.bar-row .lbl{width:190px;font-size:12.5px;color:var(--text-2);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-track{flex:1;background:var(--surface-2);border-radius:5px;height:20px;position:relative}
.bar-fill{height:100%;border-radius:5px}
.bar-val{font-size:12px;color:var(--text-2);width:66px;font-variant-numeric:tabular-nums}
footer{max-width:1180px;margin:0 auto;padding:10px 18px 40px;color:var(--text-3);font-size:11.5px}
</style></head>
<body>
<header>
  <div class="brand">
    <img class="logo-light" src="__LOGO__" alt="OrçaFascio"/>
    <img class="logo-dark" src="__LOGO_DARK__" alt="OrçaFascio"/>
    <div class="divider"></div>
    <div><h1>Dashboard do Setor de Desenvolvimento</h1></div>
  </div>
  <div class="hdr-actions">
    <button class="icon-btn" title="Notificações" aria-label="Notificações"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg><span class="badge">3</span></button>
    <button class="icon-btn avatar" title="Perfil — Jane" aria-label="Perfil"><span>JC</span><span class="badge" style="background:#f5a623;border-color:var(--surface-2)">!</span></button>
    <div class="hdr-sep"></div>
    <button class="icon-btn" id="themeBtn" onclick="tgl()" title="Alternar tema (claro/escuro)" aria-label="Alternar tema"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M6.34 17.66l-1.41 1.41"/><path d="M19.07 4.93l-1.41 1.41"/></svg></button>
  </div>
</header>
<main id="app"></main>
<footer id="ft"></footer>
<div class="tt" id="tt"></div>

<script>
/* ============================================================
   DADOS — SUBSTITUA ESTE OBJETO A CADA MÊS.
   Estrutura: rvb (run/build), tot_series (criados/concluidos/backlog por mês),
   tabela_modulo (bugs, horas, mttr, tendência por módulo), custo_tipo,
   por_modulo, pm (produtos/melhorias), aloc_top, sentry.
   Quando o Google Drive estiver conectado, este bloco é regerado automaticamente.
   ============================================================ */
const DATA = __DATA__;
/* ==================== FIM DOS DADOS ==================== */

const tt=document.getElementById('tt');
function showTT(e,html){tt.innerHTML=html;tt.style.opacity=1;tt.style.left=(e.clientX+12)+'px';tt.style.top=(e.clientY+12)+'px';}
function hideTT(){tt.style.opacity=0;}
function tgl(){const r=document.documentElement;const cur=r.getAttribute('data-theme');const dark=cur? cur==='dark' : matchMedia('(prefers-color-scheme:dark)').matches;const nd=!dark;r.setAttribute('data-theme',nd?'dark':'light');const b=document.getElementById('themeBtn');if(b)b.innerHTML=svg(nd?'moon':'sun');render();}
const cs=()=>getComputedStyle(document.documentElement);
function col(v){return cs().getPropertyValue(v).trim();}

function ico(t,left){return '<span class="info'+(left?' tl':'')+'" data-tip="'+t+'" onclick="event.stopPropagation()">i</span>';}
function mesLbl(m){const [y,mo]=m.split('-');return ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'][+mo-1]+'/'+y.slice(2);}
/* ===== Ícones SVG inline (sem CDN — renderizam em qualquer lugar, inclusive no artifact) ===== */
const ICONS={
 'headset':'<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><rect x="2" y="14" width="4" height="6" rx="1"/><rect x="18" y="14" width="4" height="6" rx="1"/><path d="M20 18v1a3 3 0 0 1-3 3h-3"/>',
 'bell':'<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
 'sun':'<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M6.34 17.66l-1.41 1.41"/><path d="M19.07 4.93l-1.41 1.41"/>',
 'moon':'<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
 'calendar-days':'<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
 'chevron-down':'<path d="M6 9l6 6 6-6"/>',
 'scale-balanced':'<path d="M12 3v18"/><path d="M6 21h12"/><path d="M4 7h16"/><path d="M7 7l-3 6h6z"/><path d="M17 7l-3 6h6z"/>',
 'bullseye':'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
 'truck-fast':'<path d="M10 17h4V6H2v11h2"/><path d="M14 9h4l3 3v5h-3"/><circle cx="7" cy="17.5" r="2.2"/><circle cx="17" cy="17.5" r="2.2"/>',
 'rocket':'<path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.9 12.9 0 0 1 22 2c0 2.72-.78 7.5-6 11a22 22 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/><circle cx="15" cy="9" r="1"/>',
 'circle-check':'<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
 'triangle-exclamation':'<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h16.9a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
 'cube':'<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/>',
 'cubes':'<rect x="3" y="10" width="8" height="8" rx="1"/><rect x="13" y="10" width="8" height="8" rx="1"/><rect x="8" y="2.5" width="8" height="8" rx="1"/>',
 'filter':'<path d="M3 4h18l-7 8v6l-4 2v-8z"/>',
 'chart-line':'<path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/>',
 'coins':'<circle cx="9" cy="9" r="6"/><path d="M15 5.5a6 6 0 0 1 0 11"/><path d="M9 6.5v5"/><path d="M7.5 8h3"/>',
 'gauge-high':'<path d="M4 18a9 9 0 1 1 16 0"/><path d="M12 14l4-3"/><circle cx="12" cy="14" r="1.1"/>',
 'hourglass-half':'<path d="M6 2h12"/><path d="M6 22h12"/><path d="M6 2c0 5 6 5 6 10 0-5 6-5 6-10"/><path d="M6 22c0-5 6-5 6-10 0 5 6 5 6 10"/>',
 'layer-group':'<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/><path d="M3 17l9 5 9-5"/>',
 'users':'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
};
function svg(n,cls,st){return '<svg class="ic'+(cls?(' '+cls):'')+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'+(st?(' style="'+st+'"'):'')+'>'+(ICONS[n]||'')+'</svg>';}
function si(n){return '<span class="sec-ico">'+svg(n)+'</span>';}
window.__safra=null;
function curSafra(){return window.__safra || DATA.funil_default;}
function setSafra(v){window.__safra=v;render();}
function safraIdx(){return DATA.tot_series.findIndex(t=>t.mes===curSafra());}
// faixa de destaque da safra selecionada; xsFn=posição central do mês, slot=largura do mês
function safraBand(xsFn,slot,P,H){const i=safraIdx();if(i<0)return '';const x=xsFn(i);const w=slot*0.82;
  return `<rect x="${(x-w/2).toFixed(1)}" y="${P-6}" width="${w.toFixed(1)}" height="${(H-P-(P-6)).toFixed(1)}" fill="${col('--s1')}" opacity="0.12" rx="3"/>`;}
function safraSelector(){
  const p=(DATA.prod_por_mes&&DATA.prod_por_mes[curSafra()])||{};
  const opts=DATA.tot_series.map(x=>`<option value="${x.mes}" ${x.mes===curSafra()?'selected':''}>${mesLbl(x.mes)}${x.mes===DATA.mes_corrente?' (atual)':''}</option>`).join('');
  return `<div class="safra-bar">
    <div class="safra-left">
      <span class="safra-ico">${svg('calendar-days')}</span>
      <div class="safra-txt">
        <div class="safra-title">Safra em foco
          <span class="safra-pill" title="clique para trocar o mês">
            <select class="safra-pill-sel" onchange="setSafra(this.value)">${opts}</select>
            ${svg('chevron-down','safra-caret')}
          </span>
        </div>
        <div class="safra-hint">clique no mês para trocar a safra · o funil mostra esta safra e ela fica destacada em azul-claro nos gráficos</div>
      </div>
    </div>
  </div>`;
}
const PRODLBL={todos:'Todos',prime:'Prime',novo:'Orçafascio',antigo:'Orçafascio antigo'};
window.__produto='todos';
function curProduto(){return window.__produto||'todos';}
function setProduto(p){window.__produto=p;render();}
function heatColor(val,max,hue){ // hue: bad(red) scale for bugs/mttr
  const t=Math.min(1,val/max);
  const a=(0.08+0.30*t).toFixed(2);
  return `background:rgba(227,73,72,${a})`;
}

function donut(runPct,buildPct){
  const R=34,C=2*Math.PI*R, run=C*runPct/100;
  return `<svg viewBox="0 0 90 90" width="84" height="84" style="flex:none">
    <circle cx="45" cy="45" r="${R}" fill="none" stroke="${col('--s3')}" stroke-width="13"/>
    <circle cx="45" cy="45" r="${R}" fill="none" stroke="${col('--s2')}" stroke-width="13"
      stroke-dasharray="${run.toFixed(1)} ${(C-run).toFixed(1)}" transform="rotate(-90 45 45)" stroke-linecap="butt"/>
    <text x="45" y="42" text-anchor="middle" fill="${col('--text-1')}" font-size="17" font-weight="800">${runPct}%</text>
    <text x="45" y="57" text-anchor="middle" fill="${col('--text-3')}" font-size="9">Run</text></svg>`;
}
function donutN(segs){
  const R=32,C=2*Math.PI*R; const tot=segs.reduce((s,x)=>s+x.val,0)||1;
  let off=0, arcs='';
  segs.forEach(x=>{ const len=C*x.val/tot;
    arcs+=`<circle cx="45" cy="45" r="${R}" fill="none" stroke="${x.color}" stroke-width="13" stroke-dasharray="${len.toFixed(2)} ${(C-len).toFixed(2)}" stroke-dashoffset="${(-C*off).toFixed(2)}" transform="rotate(-90 45 45)" stroke-linecap="butt"/>`;
    off+=x.val/tot; });
  return `<svg viewBox="0 0 90 90" width="84" height="84" style="flex:none">${arcs}<text x="45" y="43" text-anchor="middle" fill="${col('--text-1')}" font-size="15" font-weight="800">${tot}</text><text x="45" y="55" text-anchor="middle" fill="${col('--text-3')}" font-size="8.5">bugs</text></svg>`;
}
function detColors(){return {Cliente:col('--s4'),QA:col('--good'),Dev:col('--brand-blue'),Backoffice:col('--text-3'),Outros:col('--text-3')};}
function detSegs(){const cm=detColors();return DATA.deteccao.itens.map(i=>({val:i.n,color:cm[i.tipo]||col('--text-3')}));}
function detLegend(){const cm=detColors();return DATA.deteccao.itens.map(i=>`<div><span class="dot" style="background:${cm[i.tipo]||col('--text-3')}"></span> ${i.tipo} <b>${i.pct}%</b> · ${i.n}</div>`).join('');}
function prevColor(p){return p>=70?'var(--good)':(p>=40?'var(--warn)':'var(--bad)');}
function kpiCards(){
  const rvb=DATA.rvb;
  const last=DATA.tot_series[DATA.tot_series.length-1];
  const s=DATA.tot_series.find(t=>t.mes===curSafra())||last; // safra selecionada
  const atual=s.mes===DATA.mes_corrente;
  const pv=DATA.previsibilidade;
  const det=DATA.deteccao;
  return `<div class="cards">
   <div class="card"><div class="kpi-label">${svg('filter','kpi-ico')}Detecção — onde o bug foi pego <span class="info" data-tip="Classificação por tipo de item do Jira: Cliente = bug que escapou e chegou à produção (o cliente sentiu); QA/Dev = bug barrado internamente antes do cliente; Backoffice = ferramenta interna. Quanto maior a fatia interna (QA+Dev), melhor — significa que a gente segura antes de virar problema do cliente. Base líquida, ao vivo do Jira.">i</span></div>
     <div style="display:flex;align-items:center;gap:14px;margin-top:2px">${donutN(detSegs())}
       <div style="font-size:12.5px;line-height:1.55">${detLegend()}</div></div>
     <div class="kpi-sub" style="margin-top:8px">${det.escape_pct}% escapou para o cliente · ${det.interno_pct}% barrado internamente.</div></div>
   <div class="card"><div class="kpi-label">${svg('bullseye','kpi-ico')}Previsibilidade do DEV — % dentro do SLA (Não Iniciado→Produção, p95) <span class="tag-per" title="considera todos os meses até a safra atual">acumulado</span><span class="info" data-tip="% de bugs cujo tempo de DESENVOLVIMENTO (do momento em que entram em 'Não Iniciado' até entrarem em 'Produção') coube no prazo do SLA da sua prioridade, medido em horas úteis. p95: os 5% mais lentos de cada prioridade são excluídos para tirar o efeito de outliers extremos. NÃO inclui o tempo de suporte (Produção → Concluído), que é o período em que o suporte fecha com o cliente — esse é medido à parte no bloco Prioridade & SLA.">i</span></div>
     <div class="kpi-val" style="color:${prevColor(pv.agregado)}">${pv.agregado}%</div>
     <div class="kpi-sub">${pv.ok} de ${pv.n} bugs dentro do prazo (p95 — excluídos os 5% mais lentos de cada prioridade, ${pv.excluidos} cards). Horas úteis, tempo em status validado. Não inclui o tempo de suporte pós-produção.</div></div>
   <div class="card"><div class="kpi-label">${svg('truck-fast','kpi-ico')}Taxa de entrega — safra ${mesLbl(s.mes)}${atual?' (em andamento)':''}<span class="info" data-tip="Dos bugs reais que ENTRARAM no mês selecionado, quantos % já foram entregues (estão em produção ou concluídos). É a régua de entrega do dev pela definição da empresa (mandar pra produção = concluído). Muda conforme o mês escolhido no seletor de safra.">i</span></div>
     <div class="kpi-val" style="color:${prevColor(s.pct_entrega)}">${s.pct_entrega}%</div>
     <div class="kpi-sub">${s.mes}: entregou ${s.entregues} de ${s.criados} bugs que entraram · ${s.abertos} ainda abertos dessa safra.${atual?' Mês corrente ainda em andamento — o número tende a subir.':''}</div></div>
  </div>`;
}
function slaSection(){
  const pv=DATA.previsibilidade, sev=DATA.severidade;
  const maxSev=Math.max(...sev.map(s=>s.n));
  const sevPal=[col('--s8'),col('--s2'),col('--s4'),col('--s1'),col('--s3'),col('--text-3')];
  const sevBars=sev.map((s,i)=>`<div class="bar-row"><div class="lbl">${s.nivel}</div>
     <div class="bar-track"><div class="bar-fill" style="width:${(s.n/maxSev*100).toFixed(1)}%;background:${sevPal[i]}"></div></div>
     <div class="bar-val">${s.n}</div></div>`).join('');
  const slaRows=pv.por_prio.map(p=>`<tr><td>${p.nivel}</td><td class="num">≤${p.sla}h</td>
     <td class="num">${p.n}</td>
     <td class="num" style="color:${prevColor(p.pct)};font-weight:700">${p.pct}%</td>
     <td class="num">${p.mttr}</td></tr>`).join('');
  return `<div class="grid2">
   <div class="panel"><div class="kpi-label" style="margin-bottom:10px">Bugs por severidade</div>${sevBars}
     <div class="note">Prioridade do card no Jira. "Sem prioridade" = cards em "Preencher Prioridade" — lacuna de triagem.</div></div>
   <div class="panel"><div class="kpi-label" style="margin-bottom:10px">Cumprimento de SLA por prioridade</div>
     <table><thead><tr><th>Nível ${ico('Nível de prioridade do bug no Jira (Muito alta a Muito baixa = Highest a Lowest).')}</th><th class="num">SLA ${ico('Prazo-alvo de resolução do desenvolvimento para aquela prioridade, em horas úteis, conforme a régua de SLA da empresa.')}</th><th class="num">Bugs ${ico('Quantidade de bugs resolvidos naquela prioridade que entraram no cálculo (já com o p95 aplicado, ou seja, sem os 5% mais lentos).')}</th><th class="num">Dentro do SLA ${ico('% desses bugs cujo tempo de desenvolvimento (Não Iniciado→Produção) coube no prazo do SLA da prioridade.',1)}</th><th class="num">Mediana dev (d.úteis) ${ico('Tempo mediano de desenvolvimento (Não Iniciado→Produção) da prioridade, em dias úteis (jornada de 8h). Mediana = valor do meio, menos sensível a extremos que a média.',1)}</th></tr></thead><tbody>${slaRows}</tbody></table>
     <div class="note"><b>Como ler:</b> % de bugs em que o <b>desenvolvimento</b> (Não Iniciado→Produção) coube no prazo da prioridade, em horas úteis — validado célula a célula contra o histórico real do Jira (Time in Status). SLA: Muito alta 8h, Alta 12h, Média 16h, Baixa 24h, Muito baixa 40h. <b>p95:</b> os 5% mais lentos de cada prioridade são excluídos para tirar o efeito de outliers extremos. <b>Mede o dev, não o "Concluído"</b> — o tempo entre Produção e o fechamento do suporte é medido à parte (mediana ${DATA.suporte_lag?DATA.suporte_lag.mediana_h:'—'}h úteis, ${DATA.suporte_lag?DATA.suporte_lag.n:0} cards). Mostra que o SLA antigo — criado sem embasamento — está apertado para a capacidade real; dado para recalibrar.</div></div>
  </div>`;
}

function lineChart(){
  // Combo IDÊNTICO à planilha do Diego: barras agrupadas (criados × concluídos) + linha do saldo.
  const S=(DATA.diego_series&&DATA.diego_series.length)?DATA.diego_series:DATA.tot_series;
  const kD=(DATA.diego_series&&DATA.diego_series.length)?'concluidos':'entregues';
  const kS=(DATA.diego_series&&DATA.diego_series.length)?'saldo':'acumulado';
  const W=1080,H=280,P=42, n=S.length;
  const gw=(W-2*P)/n;                 // largura do grupo (mês)
  const bw=Math.min(16, gw*0.34);     // largura de cada barra
  const cx=(i)=>P+(i+0.5)*gw;         // centro do grupo
  const maxY=Math.max(...S.map(d=>Math.max(d.criados,d[kD],d[kS])))*1.12;
  const ys=(v)=>H-P-(v/maxY)*(H-2*P);
  let grid='';
  for(let g=0;g<=4;g++){const yy=P+g*(H-2*P)/4;const val=Math.round(maxY*(1-g/4));grid+=`<line x1="${P}" y1="${yy}" x2="${W-P}" y2="${yy}" stroke="${col('--line')}" stroke-width="1"/><text x="${P-6}" y="${yy+4}" text-anchor="end" fill="${col('--text-3')}" font-size="10">${val}</text>`;}
  let xl='';S.forEach((d,i)=>{if(i%2===0||i===n-1)xl+=`<text x="${cx(i)}" y="${H-P+16}" text-anchor="middle" fill="${col('--text-3')}" font-size="9">${d.mes.slice(2)}</text>`;});
  // faixa do mês em foco
  const si=S.findIndex(d=>d.mes===curSafra());
  let band='';
  if(si>=0){const w=gw*0.9;band=`<rect x="${(cx(si)-w/2).toFixed(1)}" y="${P}" width="${w.toFixed(1)}" height="${H-2*P}" fill="${col('--s1')}" opacity="0.10"/>`;}
  // barras agrupadas
  let bars='';
  S.forEach((d,i)=>{
    const x1=cx(i)-bw-1.5, x2=cx(i)+1.5, yC=ys(d.criados), yD=ys(d[kD]);
    bars+=`<rect x="${x1.toFixed(1)}" y="${yC.toFixed(1)}" width="${bw.toFixed(1)}" height="${(H-P-yC).toFixed(1)}" fill="${col('--s2')}" rx="1.5"><title>${d.mes} · criados ${d.criados}</title></rect>`;
    bars+=`<rect x="${x2.toFixed(1)}" y="${yD.toFixed(1)}" width="${bw.toFixed(1)}" height="${(H-P-yD).toFixed(1)}" fill="${col('--s3')}" rx="1.5"><title>${d.mes} · concluídos ${d[kD]}</title></rect>`;
  });
  // linha do saldo (vermelha) + pontos com tooltip
  const lp=S.map((d,i)=>(i?'L':'M')+cx(i).toFixed(1)+' '+ys(d[kS]).toFixed(1)).join(' ');
  let dots='';S.forEach((d,i)=>{dots+=`<circle cx="${cx(i).toFixed(1)}" cy="${ys(d[kS]).toFixed(1)}" r="3.5" fill="${col('--bad')}" stroke="${col('--surface-1')}" stroke-width="1.5" data-i="${i}" class="pt"/>`;});
  return `<div class="legend"><span><i class="dot" style="background:var(--s2)"></i>Cards criados</span><span><i class="dot" style="background:var(--s3)"></i>Cards concluídos</span><span><i class="dot" style="background:var(--bad);border-radius:2px;width:14px;height:3px"></i>Quantos passaram p/ próximo mês</span></div>
  <svg viewBox="0 0 ${W} ${H}" width="100%">${band}${grid}${xl}${bars}
   <path d="${lp}" fill="none" stroke="${col('--bad')}" stroke-width="2.5"/>
   ${dots}</svg>`;
}

function escapeChart(){
  const S=DATA.det_series, meta=DATA.det_series_meta;
  const W=1080,H=260,P=42,n=S.length, gw=(W-2*P)/n, cx=(i)=>P+(i+0.5)*gw;
  const maxV=Math.max(10,...S.map(d=>d.escape)), maxY=Math.min(100,Math.ceil(maxV*1.2/10)*10);
  const ys=(v)=>H-P-(v/maxY)*(H-2*P);
  let grid='';for(let g=0;g<=4;g++){const yy=P+g*(H-2*P)/4,val=Math.round(maxY*(1-g/4));grid+=`<line x1="${P}" y1="${yy}" x2="${W-P}" y2="${yy}" stroke="${col('--line')}" stroke-width="1"/><text x="${P-6}" y="${yy+4}" text-anchor="end" fill="${col('--text-3')}" font-size="10">${val}%</text>`;}
  let xl='';S.forEach((d,i)=>{if(i%2===0||i===n-1)xl+=`<text x="${cx(i)}" y="${H-P+16}" text-anchor="middle" fill="${col('--text-3')}" font-size="9">${d.mes.slice(2)}</text>`;});
  const si2=S.findIndex(d=>d.mes===curSafra());let band='';
  if(si2>=0){const w=gw*0.9;band=`<rect x="${(cx(si2)-w/2).toFixed(1)}" y="${P}" width="${w.toFixed(1)}" height="${H-2*P}" fill="${col('--s1')}" opacity="0.10"/>`;}
  const my=ys(meta.media_fechadas);
  const avg=`<line x1="${P}" y1="${my.toFixed(1)}" x2="${W-P}" y2="${my.toFixed(1)}" stroke="${col('--text-3')}" stroke-width="1.3" stroke-dasharray="5 4"/><text x="${W-P}" y="${(my-5).toFixed(1)}" text-anchor="end" fill="${col('--text-3')}" font-size="10">média safras fechadas ${meta.media_fechadas}%</text>`;
  const lp=S.map((d,i)=>(i?'L':'M')+cx(i).toFixed(1)+' '+ys(d.escape).toFixed(1)).join(' ');
  let dots='';S.forEach((d,i)=>{const atual=d.mes===meta.mes_corrente;dots+=`<circle cx="${cx(i).toFixed(1)}" cy="${ys(d.escape).toFixed(1)}" r="3.5" fill="${col('--bad')}" stroke="${col('--surface-1')}" stroke-width="1.5" opacity="${atual?0.45:1}"><title>${d.mes} · ${d.escape}% escapou (${d.cliente} de ${d.total})</title></circle>`;});
  return `<div class="legend"><span><i class="dot" style="background:var(--bad);border-radius:2px;width:14px;height:3px"></i>% que escapou p/ o cliente</span><span><i class="dot" style="background:var(--text-3);border-radius:2px;width:14px;height:3px"></i>média das safras fechadas</span></div>
  <svg viewBox="0 0 ${W} ${H}" width="100%">${band}${grid}${xl}${avg}
   <path d="${lp}" fill="none" stroke="${col('--bad')}" stroke-width="2.5"/>
   ${dots}</svg>`;
}
// Evolução por módulo — mesmos dados e método da Evolução histórica (criados exclui Impedimento
// Produto e Cancelado QA; concluídos = resolvidos, exclui Cancelado QA; saldo = acumulado
// criados−concluídos mês a mês, começando em zero), só que por módulo em vez de agregado, com
// chips de módulo (mesmo padrão visual/mecânica da Tendência dos módulos: window.__*Mods Set,
// toggle por chip, cor fixa por módulo via trendColor) e um seletor de métrica, porque comparar
// vários módulos ao mesmo tempo em barras (como a Evolução histórica) não é legível — linhas sim.
window.__modEvolMods=null;
function modEvolMods(){if(!window.__modEvolMods)window.__modEvolMods=new Set(DATA.mod_evol.ordem.filter(m=>m!=='Não classificado').slice(0,6));return window.__modEvolMods;}
function modEvolToggle(m){const s=modEvolMods();if(s.has(m))s.delete(m);else s.add(m);document.getElementById('modevolwrap').innerHTML=moduleEvolChart();}
window.__modEvolMetric='criados';
const MODEVOL_LBL={criados:'Criados',concluidos:'Concluídos',saldo:'Saldo'};
function modEvolSetMetric(k){window.__modEvolMetric=k;document.getElementById('modevolwrap').innerHTML=moduleEvolChart();}
function moduleEvolChart(){
  const ME=DATA.mod_evol; if(!ME||!ME.ordem||!ME.ordem.length) return '<div class="note">Sem dados de evolução por módulo.</div>';
  const meses=ME.meses, n=meses.length, sel=modEvolMods(), metric=window.__modEvolMetric;
  const val=(m,i)=>{const s=(ME.por_modulo[m]||[])[i]; return s?s[metric]:0;};
  const metricBtns=Object.keys(MODEVOL_LBL).map(k=>`<button class="prodbtn${k===metric?' on':''}" onclick="modEvolSetMetric('${k}')">${MODEVOL_LBL[k]}</button>`).join('');
  const barra=`<div class="safra-prod" style="margin-bottom:8px">${metricBtns}</div>`;
  const chips=ME.ordem.map(m=>{const on=sel.has(m),c=trendColor(m),lv=val(m,n-1);
    return `<button class="trend-chip${on?' on':''}" ${on?`style="background:${c};border-color:${c}"`:''} onclick="modEvolToggle('${m}')"><i style="background:${c}"></i>${m}${on?` <b>${lv}</b>`:''}</button>`;}).join('');
  const series=ME.ordem.filter(m=>sel.has(m)).map(m=>({name:m,vals:meses.map((mm,i)=>val(m,i)),color:trendColor(m)}));
  if(!series.length) return barra+`<div class="trend-chips">${chips}</div><div class="note" style="margin-top:8px">Selecione ao menos um módulo acima para desenhar a evolução.</div>`;
  const W=1080,H=330,P=44;
  const xs=(i)=>P+i*(W-2*P)/(n-1);
  const allVals=series.flatMap(s=>s.vals);
  const minV=Math.min(0,...allVals), maxV=Math.max(4,...allVals)*1.12;
  const ys=(v)=>H-P-((v-minV)/(maxV-minV))*(H-2*P);
  const path=(vals)=>vals.map((v,i)=>(i?'L':'M')+xs(i).toFixed(1)+' '+ys(v).toFixed(1)).join(' ');
  let grid='';for(let g=0;g<=4;g++){const yy=P+g*(H-2*P)/4;const gv=Math.round(maxV-g*(maxV-minV)/4);grid+=`<line x1="${P}" y1="${yy}" x2="${W-P}" y2="${yy}" stroke="${col('--line')}"/><text x="${P-6}" y="${yy+4}" text-anchor="end" fill="${col('--text-3')}" font-size="10">${gv}</text>`;}
  let xl='';meses.forEach((m,i)=>{if(i%2===0||i===n-1)xl+=`<text x="${xs(i)}" y="${H-P+16}" text-anchor="middle" fill="${col('--text-3')}" font-size="9">${m.slice(2)}</text>`;});
  const band=safraBand((i)=>xs(i),(W-2*P)/(n-1),P,H);
  let zero='';if(minV<0){const y0=ys(0);zero=`<line x1="${P}" y1="${y0.toFixed(1)}" x2="${W-P}" y2="${y0.toFixed(1)}" stroke="${col('--text-3')}" stroke-width="1" stroke-dasharray="3 3"/>`;}
  const lines=series.map(s=>`<path d="${path(s.vals)}" fill="none" stroke="${s.color}" stroke-width="2.3" opacity="0.92"><title>${s.name}</title></path>`).join('');
  const dots=series.map(s=>`<circle cx="${xs(n-1)}" cy="${ys(s.vals[n-1])}" r="3.6" fill="${s.color}"/>`).join('');
  return barra+`<div class="trend-chips">${chips}</div>
    <svg viewBox="0 0 ${W} ${H}" width="100%">${band}${grid}${zero}${xl}${lines}${dots}</svg>
    <div class="note"><b>Como ler:</b> mesmos dados e método da Evolução histórica acima — <b>criados</b> exclui Impedimento Produto e Cancelado QA; <b>concluídos</b> = resolvidos no mês (exclui Cancelado QA); <b>saldo</b> = acumulado criados−concluídos mês a mês, por módulo, começando em zero — só que agora por módulo em vez de agregado. Escolha a métrica acima e ligue/desligue módulos nos chips para comparar tendências entre eles.</div>`;
}
window.__sobraStatus='Não Iniciado';
function sobraSetStatus(s){window.__sobraStatus=s;document.getElementById('sobrawrap').innerHTML=sobraChart();}
function sobraOptions(){return DATA.status_series.ordem.map(s=>`<option value="${s}" ${s===window.__sobraStatus?'selected':''}>${s}</option>`).join('');}
function sobraChart(){
  const SS=DATA.status_series, st=window.__sobraStatus, cur=DATA.taxa_sobra.mes_corrente;
  const meses=SS.meses, vals=SS.por_status[st]||meses.map(()=>0);
  const W=1080,H=250,P=44,n=meses.length;
  const maxY=Math.max(4,...vals)*1.15;
  const bw=(W-2*P)/n*0.62;
  const xs=(i)=>P+(i+0.5)*(W-2*P)/n;
  const ys=(v)=>H-P-(v/maxY)*(H-2*P);
  const step=Math.max(1,Math.ceil(maxY/4));
  let grid='';for(let g=0;g<=Math.ceil(maxY/step);g++){const val=g*step;const yy=ys(val);grid+=`<line x1="${P}" y1="${yy}" x2="${W-P}" y2="${yy}" stroke="${col('--line')}"/><text x="${P-6}" y="${yy+4}" text-anchor="end" fill="${col('--text-3')}" font-size="10">${val}</text>`;}
  let xl='';meses.forEach((m,i)=>{if(i%2===0||i===n-1)xl+=`<text x="${xs(i)}" y="${H-P+16}" text-anchor="middle" fill="${col('--text-3')}" font-size="9">${m.slice(2)}</text>`;});
  let bars='';meses.forEach((m,i)=>{
    const v=vals[i]; const y=ys(v); const parc=m===cur;
    if(v>0) bars+=`<rect x="${(xs(i)-bw/2).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${(H-P-y).toFixed(1)}" fill="${col('--s1')}" ${parc?'opacity="0.45"':''} rx="2"><title>${m}: ${v} card(s) em "${st}"</title></rect>`;
    bars+=`<text x="${xs(i).toFixed(1)}" y="${(y-4).toFixed(1)}" text-anchor="middle" font-size="10" font-weight="700" fill="${col('--text-1')}">${v}</text>`;
  });
  const tot=vals.reduce((a,b)=>a+b,0);
  const band=safraBand((i)=>xs(i),(W-2*P)/n,P,H);
  return `<div style="font-size:12px;color:var(--text-2);margin:2px 0 8px">Mostrando <b>${st}</b> — total de <b>${tot}</b> card(s) na série (por mês de criação). Barra clara = mês corrente; faixa azul = safra em foco.</div>
    <svg viewBox="0 0 ${W} ${H}" width="100%">${band}${grid}${xl}${bars}</svg>`;
}
const TREND_PAL=['#005FE8','#eb6834','#1e9e5a','#f0a500','#e87ba4','#e2384d','#7c5cff','#12a4b8','#b5651d','#8a8fa3','#c026d3','#0891b2'];
function trendColor(m){const i=DATA.mod_history.ordem.indexOf(m);return TREND_PAL[(i<0?0:i)%TREND_PAL.length];}
window.__trendMods=null;
function trendMods(){if(!window.__trendMods)window.__trendMods=new Set(DATA.mod_history.ordem.filter(m=>m!=='Não classificado').slice(0,6));return window.__trendMods;}
function trendToggle(m){const s=trendMods();if(s.has(m))s.delete(m);else s.add(m);document.getElementById('trendwrap').innerHTML=moduleTrendChart();}
function moduleTrendChart(){
  const MH=DATA.mod_history; if(!MH||!MH.ordem||!MH.ordem.length) return '<div class="note">Sem dados de histórico por módulo.</div>';
  const meses=MH.meses, n=meses.length, sel=trendMods();
  const chips=MH.ordem.map(m=>{const on=sel.has(m),c=trendColor(m),lv=(MH.por_modulo[m]||[])[n-1]??0;
    return `<button class="trend-chip${on?' on':''}" ${on?`style="background:${c};border-color:${c}"`:''} onclick="trendToggle('${m}')"><i style="background:${c}"></i>${m}${on?` <b>${lv}</b>`:''}</button>`;}).join('');
  const series=MH.ordem.filter(m=>sel.has(m)).map(m=>({name:m,vals:MH.por_modulo[m]||meses.map(()=>0),color:trendColor(m)}));
  if(!series.length) return `<div class="trend-chips">${chips}</div><div class="note" style="margin-top:8px">Selecione ao menos um módulo acima para desenhar a tendência.</div>`;
  const W=1080,H=330,P=44;
  const xs=(i)=>P+i*(W-2*P)/(n-1);
  const maxY=Math.max(4,...series.flatMap(s=>s.vals))*1.12;
  const ys=(v)=>H-P-(v/maxY)*(H-2*P);
  const path=(vals)=>vals.map((v,i)=>(i?'L':'M')+xs(i).toFixed(1)+' '+ys(v).toFixed(1)).join(' ');
  let grid='';for(let g=0;g<=4;g++){const yy=P+g*(H-2*P)/4;const val=Math.round(maxY*(1-g/4));grid+=`<line x1="${P}" y1="${yy}" x2="${W-P}" y2="${yy}" stroke="${col('--line')}"/><text x="${P-6}" y="${yy+4}" text-anchor="end" fill="${col('--text-3')}" font-size="10">${val}</text>`;}
  let xl='';meses.forEach((m,i)=>{if(i%2===0||i===n-1)xl+=`<text x="${xs(i)}" y="${H-P+16}" text-anchor="middle" fill="${col('--text-3')}" font-size="9">${m.slice(2)}</text>`;});
  const band=safraBand((i)=>xs(i),(W-2*P)/(n-1),P,H);
  const lines=series.map(s=>`<path d="${path(s.vals)}" fill="none" stroke="${s.color}" stroke-width="2.3" opacity="0.92"><title>${s.name}</title></path>`).join('');
  const dots=series.map(s=>`<circle cx="${xs(n-1)}" cy="${ys(s.vals[n-1])}" r="3.6" fill="${s.color}"/>`).join('');
  return `<div class="trend-chips">${chips}</div>
    <svg viewBox="0 0 ${W} ${H}" width="100%">${band}${grid}${xl}${lines}${dots}</svg>`;
}
function moduleTable(){
  const rows=DATA.tabela_modulo.slice();
  const maxBug=Math.max(...rows.map(r=>r.bugs));
  const maxMt=Math.max(...rows.map(r=>r.mttr||0));
  const bd={up:'b-up',down:'b-down',flat:'b-flat'};
  const badge={up:'▲ subindo',down:'▼ caindo',flat:'estável'};
  window.__sort=(k)=>{const asc=window.__sk===k?!window.__asc:false;window.__sk=k;window.__asc=asc;
    rows.sort((a,b)=>{let x=a[k],y=b[k];if(typeof x==='string'){return asc?x.localeCompare(y):y.localeCompare(x);}return asc?(x||0)-(y||0):(y||0)-(x||0);});
    document.getElementById('mtb').innerHTML=body(rows);};
  const body=(rs)=>rs.map(r=>`<tr>
     <td>${r.mod}</td>
     <td class="num"><span class="heat" style="${heatColor(r.bugs,maxBug)}">${r.bugs}</span></td>
     <td><span class="badge ${bd[r.trend]}">${badge[r.trend]}</span></td>
     <td class="num">${r.mttr!=null?`<span class="heat" style="${heatColor(r.mttr,maxMt)}">${r.mttr}</span>`:'—'}</td>
     <td class="num">${r.horas}</td></tr>`).join('');
  return `<table><thead><tr>
     <th onclick="__sort('mod')">Módulo ${ico('Módulo do sistema onde o bug ocorreu, pelo campo Módulo do card no Jira (dropdown de 20 valores). Não classificado = cards sem módulo preenchido (em geral do tipo Bug Backoffice).')}</th>
     <th class="num" onclick="__sort('bugs')">Bugs (volume) ▾ ${ico('Quantidade total de bugs registrados no módulo em todo o período coberto. Clique no cabeçalho para ordenar a tabela.')}</th>
     <th onclick="__sort('trend')">Tendência ${ico('Compara os bugs criados no último mês FECHADO (não o corrente, que está parcial) com a MÉDIA dos 3 meses anteriores do módulo. Acima de +15% = subindo (piorando, mais bugs entrando); abaixo de −15% = caindo (melhorando); entre −15% e +15% = estável. A janela de 3 meses suaviza o ruído de um mês atípico.')}</th>
     <th class="num" onclick="__sort('mttr')">MTTR (dias) ${ico('Mean Time To Repair — tempo médio para resolver o bug, em dias úteis entre a criação e a conclusão do card. Alto = bugs demoram a sair (velocidade), independente do volume. Inclui o tempo de suporte até o Concluído.',1)}</th>
     <th class="num" onclick="__sort('horas')">Esforço (h) ${ico('Soma das horas apontadas (Σ Tempo Gasto / worklog do Jira) nos bugs do módulo. Preenchido em ~64% dos cards, então é um piso, não o total real.',1)}</th></tr></thead>
     <tbody id="mtb">${body(rows)}</tbody></table>
     <div class="note"><b>Fonte e método:</b> volume, esforço e MTTR da aba "Base Atual" do Jira (base atual, ${DATA.meta.total_bugs_base_atual} bugs). MTTR = média de dias entre criação e resolução. Esforço = Σ Tempo Gasto (assumido em segundos → horas); preenchido em ~64% dos cards, portanto é piso, não total. Tendência = último mês vs média dos 3 anteriores (aba "Resumo por módulos", bugs criados).</div>`;
}

function barChart(obj,pal,unit){
  const entries=Object.entries(obj); const max=Math.max(...entries.map(e=>e[1]));
  return entries.map(([k,v],i)=>`<div class="bar-row"><div class="lbl">${k}</div>
     <div class="bar-track"><div class="bar-fill" style="width:${(v/max*100).toFixed(1)}%;background:${pal[i%pal.length]}"></div></div>
     <div class="bar-val">${v.toLocaleString('pt-BR')}${unit||''}</div></div>`).join('');
}

function custoModulo(){
  const rows=DATA.tabela_modulo.filter(r=>r.horas>0).slice(0,10);
  const obj={};rows.forEach(r=>obj[r.mod]=r.horas);
  return barChart(obj,[col('--s1')],'h');
}

function alertCard(){
  const a=DATA.alerta_parados; if(!a) return '';
  const ok=a.count===0;
  const rows=a.itens.map(i=>`<tr><td><b>${i.key}</b></td><td class="num"><span class="pill">${i.dias} dias úteis</span></td><td>${i.prio}</td><td>${i.mod}</td><td>${i.resp}</td></tr>`).join('');
  return `<div class="alert ${ok?'ok':''}">
    <h3>${svg(ok?'circle-check':'triangle-exclamation')} Cards parados em "Não Iniciado" &gt; ${a.limite} dias úteis <span class="big">${a.count}</span></h3>
    <div class="kpi-sub">Nenhum card deveria ficar parado tanto tempo. Snapshot ${a.snapshot} · ${a.total_nao_iniciado} cards em Não Iniciado no total.</div>
    ${ok?'':`<table><thead><tr><th>Card</th><th class="num">Parado há</th><th>Prioridade</th><th>Módulo</th><th>Responsável</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="kpi-sub" style="margin-top:8px">Ação de gestão: destravar ou reclassificar. Cards de prioridade alta parados violam o SLA (High = 16h úteis para definição).</div>`}
  </div>`;
}
function squadSection(){
  const S=DATA.squads; const maxL=Math.max(...S.filter(s=>s.bugs_por_pessoa).map(s=>s.bugs_por_pessoa));
  const badge=(r)=>r==='interno'?'<span class="badge b-flat" style="background:rgba(42,120,214,.14);color:var(--s1)">folha</span>':(r==='contratado'?'<span class="badge b-flat" style="background:rgba(235,104,52,.16);color:var(--s2)">contrato</span>':'<span class="badge b-flat">—</span>');
  const row=(s)=>`<tr>
    <td>${s.squad}</td><td>${badge(s.regime)}</td>
    <td class="num">${s.pessoas??'—'}</td>
    <td class="num"><span class="heat" style="${heatColor(s.bugs, Math.max(...S.map(x=>x.bugs)))}">${s.bugs}</span></td>
    <td class="num">${s.bugs_por_pessoa!=null?`<span class="heat" style="${heatColor(s.bugs_por_pessoa,maxL)}">${s.bugs_por_pessoa}</span>`:'—'}</td>
    <td class="num">${s.horas}</td>
    <td class="num">${s.mttr??'—'}</td>
    <td class="num" style="color:${s.sla!=null?prevColor(s.sla):'var(--text-3)'};font-weight:700">${s.sla!=null?s.sla+'%':'—'}</td></tr>`;
  const body=S.map(row).join('');
  return `<div class="panel"><table>
    <thead><tr><th>Squad ${ico('Time responsável pela manutenção do(s) módulo(s), pelo mapa de responsabilidade definido com a gestão.')}</th><th>Regime ${ico('Como o custo do squad é pago: folha = CLT (salário + encargos); contrato = prestador de serviço externo. Nunca custear módulo contratado com custo-hora da folha.')}</th><th class="num">Pessoas ${ico('Número de pessoas no squad. Em branco quando o headcount ainda não foi confirmado.')}</th><th class="num">Bugs ${ico('Total de bugs atribuídos aos módulos do squad.')}</th><th class="num">Bugs/pessoa ${ico('Bugs ÷ pessoas do squad — indicador de sobrecarga. Quanto maior, mais carga por cabeça.')}</th><th class="num">Esforço (h) ${ico('Soma das horas apontadas (worklog) nos bugs do squad. Piso, pois só ~64% dos cards têm apontamento.',1)}</th><th class="num">MTTR (d.úteis) ${ico('Tempo médio de resolução do squad, em dias úteis entre criação e conclusão do card.',1)}</th><th class="num">% SLA ${ico('% de bugs do squad resolvidos dentro do prazo do SLA da prioridade (criação→conclusão em horas úteis).',1)}</th></tr></thead>
    <tbody>${body}</tbody></table>
    <div class="note"><b>Carga × capacidade.</b> "Bugs/pessoa" é o indicador de sobrecarga (headcount do squad). <b>Folha</b> = custo sai de salário+encargos; <b>contrato</b> = custo é o valor do contrato de manutenção (a informar) — nunca custear módulo contratado com custo-hora da folha. Pessoas de TI e do produto OF CDE ainda sem headcount; "Não atribuído" reúne Chat de Suporte, Arquivos Públicos, OF BI e os Não classificado. Base: ${DATA.meta.total_bugs_base_atual} bugs.</div></div>`;
}
window.__mhMod=null;
function mhCurMod(){return window.__mhMod || DATA.mod_history.ordem[0];}
function mhSetMod(v){window.__mhMod=v;document.getElementById('mhwrap').innerHTML=moduleHistoryChart();}
function mhOptions(){const MH=DATA.mod_history,cur=mhCurMod();return MH.ordem.map(m=>`<option value="${m}" ${m===cur?'selected':''}>${m} (${MH.total_geral[m]})</option>`).join('');}
function moduleHistoryChart(){
  const MH=DATA.mod_history; if(!MH||!MH.ordem.length) return '<div class="note">Sem dados de histórico por módulo.</div>';
  const mod=mhCurMod();
  const meses=MH.meses, vals=MH.por_modulo[mod]||meses.map(()=>0);
  const W=1080,H=300,P=44,BW=(W-2*P)/meses.length*0.6;
  const maxY=Math.max(4,...vals)*1.12;
  const xs=(i)=>P+(i+0.5)*(W-2*P)/meses.length;
  const ys=(v)=>H-P-(v/maxY)*(H-2*P);
  const step=Math.max(1,Math.ceil(maxY/4));
  let grid='';for(let g=0;g<=Math.ceil(maxY/step);g++){const val=g*step;const yy=ys(val);grid+=`<line x1="${P}" y1="${yy}" x2="${W-P}" y2="${yy}" stroke="${col('--line')}"/><text x="${P-6}" y="${yy+4}" text-anchor="end" fill="${col('--text-3')}" font-size="10">${val}</text>`;}
  let xl='';meses.forEach((m,i)=>{if(i%2===0||i===meses.length-1)xl+=`<text x="${xs(i)}" y="${H-P+16}" text-anchor="middle" fill="${col('--text-3')}" font-size="9">${m.slice(2)}</text>`;});
  let bars='';meses.forEach((m,i)=>{const v=vals[i];const y=ys(v);
    if(v>0) bars+=`<rect x="${(xs(i)-BW/2).toFixed(1)}" y="${y.toFixed(1)}" width="${BW.toFixed(1)}" height="${(H-P-y).toFixed(1)}" fill="${col('--s1')}" rx="2"><title>${m}: ${v} bug(s)</title></rect>`;
    bars+=`<text x="${xs(i).toFixed(1)}" y="${(y-4).toFixed(1)}" text-anchor="middle" font-size="9.5" font-weight="700" fill="${col('--text-1')}">${v}</text>`;});
  const safra=curSafra(), iS=meses.indexOf(safra), valS=iS>=0?vals[iS]:0, atualMes=safra===DATA.mes_corrente;
  const fechados=vals.filter((v,i)=>meses[i]!==DATA.mes_corrente);
  const media=fechados.length?Math.round(fechados.reduce((a,b)=>a+b,0)/fechados.length):0;
  const totalG=MH.total_geral[mod]||vals.reduce((x,y)=>x+y,0);
  let cmp='';
  if(!atualMes && media){ if(valS>media) cmp=` <span style="color:var(--bad);font-weight:700">↑ acima da média</span>`; else if(valS<media) cmp=` <span style="color:var(--good);font-weight:700">↓ abaixo da média</span>`; else cmp=` <span style="color:var(--text-3)">na média</span>`; }
  return `<details class="mh-c" open><summary>Módulo
      <select class="toggle" style="padding:6px 10px;cursor:pointer;margin-left:4px" onchange="mhSetMod(this.value)" onmousedown="event.stopPropagation()" onclick="event.stopPropagation()">${mhOptions()}</select></summary>
      <div class="mh-kpis">
        <div class="mh-kpi"><div class="mh-kpi-lbl">safra ${mesLbl(safra)}</div><div class="mh-kpi-num">${valS}</div><div class="mh-kpi-sub">${atualMes?'em andamento':(cmp||'no mês')}</div></div>
        <div class="mh-kpi"><div class="mh-kpi-lbl">média / mês</div><div class="mh-kpi-num">${media}</div><div class="mh-kpi-sub">meses fechados</div></div>
        <div class="mh-kpi"><div class="mh-kpi-lbl">acumulado</div><div class="mh-kpi-num">${totalG}</div><div class="mh-kpi-sub">no período</div></div>
      </div>
      <div style="font-size:11px;color:var(--text-3);margin:0 0 6px">barras = bugs criados por mês · faixa azul = safra em foco</div>
      <svg viewBox="0 0 ${W} ${H}" width="100%">${safraBand((i)=>xs(i),(W-2*P)/meses.length,P,H)}${grid}${xl}${bars}</svg>
    </details>
    <details class="mh-c" open><summary>Ferramentas</summary>${modFeatures(mod)}</details>`;
}
function modFeatures(mod){
  const MF=DATA.mod_features&&DATA.mod_features[mod];
  if(!MF) return `<div class="note" style="margin-top:4px"><b>Detalhe por ferramenta:</b> ainda não mapeado para <b>${mod}</b>. O mapeamento começou pelo Orçamento (o de maior volume); os demais módulos entram conforme a gente refina o funil de classificação dos títulos.</div>`;
  const itens=MF.itens.filter(i=>i.ferramenta.indexOf('Outros')<0);
  const outros=MF.itens.find(i=>i.ferramenta.indexOf('Outros')>=0);
  const max=Math.max(...MF.itens.map(i=>i.n));
  const row=(it,gray)=>{const w=(it.n/max*100).toFixed(1);const c=gray?col('--text-3'):col('--s1');
    return `<div class="bar-row"><div class="lbl" style="width:230px">${it.ferramenta}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${w}%;background:${c}"></div></div>
      <div class="bar-val">${it.n} · ${Math.round(100*it.n/MF.total)}%</div></div>`;};
  return `<div style="margin-top:4px">
    <div class="kpi-label" style="font-size:13px;margin-bottom:4px">Ferramentas com mais cards abertos — onde focar um possível <b>refactory</b>
      <span class="info" data-tip="Classificação dos títulos dos bugs deste módulo contra o mapa de funcionalidades da OrçaFascio (funil de palavras-chave, refinado aos poucos). Mostra QUAL ferramenta dentro do módulo mais gerou cards — o alvo mais provável de dívida técnica. 'Outros' = títulos que ainda não casaram com nenhuma ferramenta do funil; cai conforme refinamos.">i</span></div>
    <div style="font-size:11.5px;color:var(--text-3);margin-bottom:10px">${MF.total} bugs reais classificados · heurística por título (aproximado)</div>
    ${itens.map(it=>row(it,false)).join('')}
    ${outros?row(outros,true):''}
    <div class="note" style="margin-top:12px"><b>Leitura para refactory:</b> ${itens.slice(0,3).map(i=>i.ferramenta+' ('+i.n+')').join(', ')} concentram a maior parte dos bugs — é onde o código provavelmente está mais frágil e onde a prevenção rende mais. "Outros" (${outros?outros.n:0}) são títulos ainda não mapeados; o funil vai ficando mais fiel conforme refinamos.</div></div>`;
}
function filaStatusColor(name){const n=name.toLowerCase();
  if(n.includes('não inici')) return col('--warn');
  if(n.includes('desenvolv')) return col('--s1');
  if(n.includes('qa')) return col('--s3');
  if(n.includes('impedimento')||n.includes('backlog')||n.includes('revert')) return col('--bad');
  return col('--text-3');}
function filaBreakdown(f){
  if(!f.fila_det||!f.fila_det.length) return '';
  const tot=f.fila_det.reduce((a,x)=>a+x[1],0)||1;
  const bar=f.fila_det.map(x=>`<div style="width:${(100*x[1]/tot).toFixed(1)}%;background:${filaStatusColor(x[0])}" title="${x[0]}: ${x[1]}"></div>`).join('');
  const chips=f.fila_det.map(x=>`<span class="fila-chip"><i style="background:${filaStatusColor(x[0])}"></i>${x[0]} <b>${x[1]}</b></span>`).join('');
  return `<div class="fila-break">
    <div class="fila-break-h">Composição da fila — ${f.fila} cards no pipeline</div>
    <div class="fila-bar">${bar}</div>
    <div class="fila-chips">${chips}</div></div>`;
}
function impedimentoSpotlight(){
  const im=DATA.impedimentos; if(!im||!im.total) return '';
  return `<div class="imp-spot">
    <div class="imp-h">${svg('triangle-exclamation','',' color:var(--bad);flex:none')}<b>Impedimentos — bloqueios que pedem desbloqueio</b><span class="tag-per" title="cards parados em impedimento hoje, somando todos os meses">atual · todos os meses</span></div>
    <div class="imp-body">
      <div class="imp-big">${im.total}</div>
      <div class="imp-split">
        <div class="imp-item"><b>${im.produto}</b> em <b>Impedimento Produto</b> — aguardando decisão de produto/negócio<a href="${im.url_produto}" target="_blank" rel="noopener">ver no Jira ↗</a></div>
        <div class="imp-item"><b>${im.dev}</b> em <b>Impedimento Dev</b> — travado por dependência técnica<a href="${im.url_dev}" target="_blank" rel="noopener">ver no Jira ↗</a></div>
      </div>
    </div>
  </div>`;
}
function funilPanel(){
  const f=(DATA.funil_por_mes&&DATA.funil_por_mes[curSafra()])||DATA.funil; if(!f) return '';
  const isCorrente=f.mes===DATA.mes_corrente;
  const step=(val,lbl,sub,c)=>`<div style="flex:1;min-width:120px;text-align:center">
     <div style="font-size:34px;font-weight:800;color:${c};letter-spacing:-1px">${val}</div>
     <div style="font-size:12.5px;color:var(--text-1);font-weight:600;margin-top:2px">${lbl}</div>
     <div style="font-size:11px;color:var(--text-3);margin-top:2px">${sub}</div></div>`;
  const arrow=(t)=>`<div style="align-self:center;text-align:center;color:var(--text-3);padding:0 4px"><div style="font-size:20px;line-height:1">→</div><div style="font-size:10px;white-space:nowrap">${t}</div></div>`;
  const sevTxt=f.sev.map(s=>`${s.nivel} ${s.n}`).join(' · ');
  const modTxt=f.mod_top.map(m=>`${m[0]} ${m[1]}`).join(' · ');
  const filaTxt=f.fila_det.length?f.fila_det.map(x=>`${x[1]} ${x[0].toLowerCase()}`).join(', '):'—';
  return `<div class="panel" style="border-left:5px solid var(--s1)">
    <div class="kpi-label" style="margin-bottom:14px;font-size:13px">Carga real que chegou ao desenvolvimento — safra de <b>${mesLbl(f.mes)}</b>${isCorrente?' (mês corrente, em andamento)':' (mês fechado)'}
      <span class="info" data-tip="O funil mostra a carga REAL do desenvolvimento no mês. Parte do total de bugs criados, remove os que o QA descartou (Cancelado QA — não eram defeito de produto), e o que sobra é o volume que efetivamente chegou ao dev. 'Entregues' = cards que o dev colocou em produção/concluiu; 'na fila' = o que ainda está no pipeline. É a leitura honesta de capacidade: mede o dev pelo que ele recebeu de verdade, não pelo volume bruto inflado por triagem.">i</span></div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:stretch">
      ${step(f.total,'bugs criados','entraram como bug',col('--text-2'))}
      ${arrow('−'+f.descartados_qa+' ('+f.pct_descarte+'%)')}
      ${step(f.dev,'chegaram ao dev','descartados os do QA',col('--s1'))}
      ${arrow('dev entregou')}
      ${step(f.entregues,'entregues','em produção/concluído',col('--good'))}
      ${arrow('restou')}
      ${step(f.fila,'na fila','ainda no pipeline',col('--warn'))}
    </div>
    ${filaBreakdown(f)}
    ${impedimentoSpotlight()}
    <div class="note" style="margin-top:16px"><b>Leitura de capacidade:</b> o dev recebeu de verdade <b>${f.dev}</b> bugs (não ${f.total} — ${f.descartados_qa} eram ruído de triagem que o QA barrou, ${f.pct_descarte}% do total). Desses ${f.dev}, entregou <b>${f.entregues} (${f.pct_entrega}%)</b> dentro do mês; a fila restante são ${f.fila} cards (${filaTxt}), a maior parte já adiantada. Velocidade: MTTR mediano de <b>${f.mttr_mediana} dias úteis</b> (média ${f.mttr_media}). Severidade do que chegou ao dev: ${sevTxt}. Concentração: ${modTxt}. Apontamento de horas em ${f.apont_cov[0]} de ${f.apont_cov[1]} cards. <b>O gargalo do mês não foi o desenvolvimento</b> — foi a triagem deixando ${f.pct_descarte}% de ruído entrar.</div></div>`;
}
function prodBanner(){
  const lbl=PRODLBL[curProduto()];
  return `<div class="prod-banner">${svg('filter','',' color:var(--brand-blue);flex:none;margin-top:1px')}
    <div><b>Visão por produto: ${lbl} · ${mesLbl(curSafra())}</b> — mostrando evolução, diagnóstico do mês, sobra por status, panorama e bugs por responsável. As seções de módulo, SLA, squad, custo e alerta ficam ocultas nesta visão (aparecem em <b>Todos</b>).
    <br><i>Obs.: o recorte por produto ainda não filtra os números abaixo — a classificação por produto está em construção (Prime já é módulo próprio; Orçafascio × Orçafascio antigo dependem do marcador na descrição). Por ora os valores são de todos os produtos.</i></div></div>`;
}
function responsavelPanel(){
  return `<h2>${si('users')}Bugs por responsável</h2>
   <div class="panel"><div class="kpi-label" style="margin-bottom:10px">Alocação — bugs por responsável (top 10)</div>
     ${barChart(Object.fromEntries(DATA.aloc_top),[col('--s1')])}
     <div class="note">"Sem responsável" é o maior balde — sinal de triagem/atribuição a melhorar, não de ociosidade. Enquadramento de sistema, não de pessoa.</div></div>`;
}
// transforma automaticamente as notas longas em blocos recolhíveis (fechados por padrão)
function collapsibleNotes(){
  document.querySelectorAll('#app .note').forEach(n=>{
    const txt=(n.textContent||'').trim();
    if(txt.length<150) return;                 // notas curtas ficam inline
    let label='Detalhes';
    if(/^Como ler/i.test(txt)) label='Como ler';
    else if(/^Fonte e método/i.test(txt)) label='Fonte e método';
    else if(/^Custo distribuído/i.test(txt)) label='Nota de custo';
    const d=document.createElement('details'); d.className='note-c';
    const s=document.createElement('summary'); s.textContent=label;
    const body=document.createElement('div'); body.className='note-body'; body.innerHTML=n.innerHTML;
    d.appendChild(s); d.appendChild(body);
    n.replaceWith(d);
  });
}
function render(){
  const isAll=curProduto()==='todos';
  document.getElementById('app').innerHTML=`
   ${safraSelector()}
   ${isAll?'':prodBanner()}
   <h2>${si('chart-line')}Evolução histórica — entradas × concluídos × saldo por mês <span class="info" data-tip="Idêntico à planilha do Diego (aba Resumo). Laranja = cards que ENTRARAM no mês (criados); verde = cards que SAÍRAM no mês (concluídos = Em produção ou Concluído); azul tracejado = SALDO que passou para o mês seguinte (início + criados − concluídos). Quando entra mais do que sai, o saldo sobe; quando sai mais, o saldo cai.">i</span></h2>
   <div class="panel">${lineChart()}
     <details class="note-c"><summary>Como ler este gráfico</summary><div class="note-body"><b>Como ler (mesma lógica da planilha do Diego):</b> a linha laranja é quanto <b>entrou</b> por mês (<b>cards criados</b>); a verde é quanto <b>saiu</b> no mês (<b>cards concluídos</b> — em produção ou concluído); a tracejada azul é o <b>saldo</b> que passou para o mês seguinte. As três se conectam: <b>saldo do mês = início + criados − concluídos</b>, e esse saldo vira o início do mês seguinte (começando em zero em jan/2025). Por isso, quando o laranja fica acima do verde, o azul <b>sobe</b> (entrou mais do que saiu); quando o verde supera o laranja, o azul <b>cai</b>. Hoje o saldo está em <b>${(DATA.diego_series&&DATA.diego_series.length?DATA.diego_series[DATA.diego_series.length-1].saldo:'—')}</b>. Regras do Diego: "criados" exclui os status <b>Impedimento Produto</b> e <b>Cancelado QA</b>; "concluídos" considera <b>Em produção</b> ou <b>Concluído</b> (fora Cancelado QA). <i>Fonte: aba "Resumo" da planilha do Diego — atualiza quando a planilha é atualizada.</i></div></details></div>
   <h2>${si('layer-group')}Evolução por módulo — criados × concluídos × saldo <span class="info" data-tip="Mesmos dados e método da Evolução histórica acima (criados exclui Impedimento Produto e Cancelado QA; concluídos = resolvidos, exclui Cancelado QA; saldo = acumulado criados−concluídos mês a mês), agora comparando módulos entre si em vez do agregado. Escolha a métrica (Criados/Concluídos/Saldo) e ligue/desligue módulos nos chips abaixo.">i</span></h2>
   <div class="panel"><div id="modevolwrap">${moduleEvolChart()}</div></div>
   <h2>${si('filter')}Diagnóstico do mês — funil de entrega do dev</h2>${funilPanel()}
   <h2>${si('hourglass-half')}Sobra por status — número de cards por mês <span class="info" data-tip="Explorador de status: escolha um status no seletor e o gráfico mostra, mês a mês (por mês de criação do card), quantos cards estão nesse status HOJE. Ex.: 'Não Iniciado' mostra o que sobrou sem começar; 'Impedimento Dev' mostra os travados; 'Done' mostra os entregues. Barra clara = mês corrente. Base líquida — exclui descartados pelo QA e Chat de Suporte.">i</span></h2>
   <div class="panel">
     <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
       <label style="font-size:12.5px;color:var(--text-2)">${svg('filter','',' margin-right:6px;color:var(--brand-blue)')}Filtrar por status:</label>
       <select class="toggle" style="padding:7px 11px;cursor:pointer" onchange="sobraSetStatus(this.value)">${sobraOptions()}</select>
     </div>
     <div id="sobrawrap">${sobraChart()}</div>
     <div class="note"><b>Como ler:</b> selecione um status no menu acima para ver, em cada mês, quantos cards daquela safra estão nele hoje. Cada barra traz o número exato; a barra clara é o mês corrente (ainda em andamento). Útil para: "Não Iniciado" = o que ficou sem começar; "Impedimento Produto/Dev" = onde estão os travados; "Em Desenvolvimento" = o que o time tem em mãos agora. Base líquida — exclui descartados pelo QA e o módulo Chat de Suporte.</div></div>
   <h2>${si('gauge-high')}Panorama do período</h2>${kpiCards()}
   <h2>${si('chart-line')}Detecção ao longo do tempo — escape rate mensal <span class="info" data-tip="% dos bugs criados em cada mês que vieram como 'Bug Cliente' (escaparam para produção). Por mês de criação, base líquida. Linha tracejada = média das safras fechadas. O mês corrente aparece esmaecido porque ainda está em andamento. Quanto MAIS BAIXA a linha, melhor — mais bugs barrados antes do cliente.">i</span></h2>
   <div class="panel"><div id="escwrap">${escapeChart()}</div>
     <div class="note"><b>Como ler:</b> cada ponto é o % dos bugs daquele mês que chegaram como Bug Cliente (escaparam). <b>Linha caindo = melhorando</b> — mais bugs barrados internamente (QA/Dev) antes do cliente. Mês corrente esmaecido, ainda em andamento. Base líquida, por mês de criação.</div></div>
   ${isAll?'':responsavelPanel()}
   ${isAll?`
   <h2>${si('cubes')}Qualidade por módulo</h2>
   <div class="panel">${moduleTable()}</div>
   <h2>${si('chart-line')}Tendência dos módulos — comparativo mensal (estilo bolsa) <span class="info" data-tip="Cada linha é um módulo: bugs criados por mês (líquido). Compara vários módulos ao mesmo tempo para ver quem está subindo (gerando mais bugs) ou descendo. Mostra os 6 módulos de maior volume + 'Outros' agrupado. Diferente da bolsa: aqui LINHA SUBINDO = mais bugs = PIOR.">i</span></h2>
   <div class="panel"><div id="trendwrap">${moduleTrendChart()}</div>
     <details class="note-c"><summary>Como ler</summary><div class="note-body"><b>Como ler:</b> clique nos <b>chips</b> acima para ligar/desligar cada módulo no gráfico. Cada linha é um <b>módulo</b> e mostra os bugs criados por mês (contagem líquida). É a visão "bolsa de valores" para comparar os módulos lado a lado e ver tendências — quem está <b>subindo</b> (gerando mais bugs) e quem está <b>descendo</b>. Aparecem os <b>6 módulos de maior volume</b> mais "Outros" (o resto somado, linha tracejada). Na legenda, o número é o valor do último mês e a setinha compara com o mês anterior. <b>Atenção à inversão da metáfora:</b> ao contrário da bolsa, aqui <b>linha subindo = mais bugs = pior</b> (por isso a seta de alta é vermelha). O mês corrente ainda está em andamento, então a última ponta tende a subir até fechar. Faixa azul-clara = safra em foco.</div></details></div>
   <h2>${si('layer-group')}Histórico evolutivo — bugs criados por módulo <span class="info" data-tip="Escolha um módulo no seletor e veja quantos bugs ele gerou em cada mês (por mês de criação). Isola o módulo para enxergar a tendência dele com clareza, sem o ruído dos outros. Contagem líquida (exclui Cancelado QA e Chat de Suporte).">i</span></h2>
   <div class="panel"><div id="mhwrap">${moduleHistoryChart()}</div>
     <div class="note"><b>Como ler:</b> selecione um <b>módulo</b> no menu para ver a evolução mensal de bugs criados só dele. Cada barra é um mês, com o número exato. Serve para acompanhar se um produto está gerando mais ou menos bugs ao longo do tempo. Contagem líquida — exclui os descartados pelo QA e o módulo Chat de Suporte, igual à Evolução histórica.</div></div>
   <h2>${si('triangle-exclamation')}Prioridade &amp; SLA</h2>${slaSection()}
   <h2>${si('users')}Carga por squad — folha × contrato</h2>${squadSection()}
   <h2>${si('coins')}Esforço e alocação — bugs</h2>
   <div class="grid2">
     <div class="panel"><div class="kpi-label" style="margin-bottom:10px">Esforço por módulo (top 10, horas)</div>
       ${custoModulo()}
       <div class="note"><b>Esforço distribuído (estimativa)</b>, em horas apontadas (Σ Tempo Gasto) só de bugs. Para virar R$: horas × custo-hora carregado — pendente das taxas de folha e de cada contrato. Cuidado: onde o apontamento é baixo, o esforço aparece subestimado.</div></div>
     <div class="panel"><div class="kpi-label" style="margin-bottom:10px">Alocação — bugs por responsável (top 10)</div>
       ${barChart(Object.fromEntries(DATA.aloc_top),[col('--s1')])}
       <div class="note">"Sem responsável" é o maior balde — sinal de triagem/atribuição a melhorar, não de ociosidade. Enquadramento de sistema, não de pessoa.</div></div>
   </div>
   <h2>${si('bell')}Alerta operacional</h2>${alertCard()}`:''}`;
  collapsibleNotes();
  document.querySelectorAll('.pt').forEach(c=>{c.addEventListener('mousemove',e=>{const SS=(DATA.diego_series&&DATA.diego_series.length)?DATA.diego_series:DATA.tot_series;const d=SS[e.target.dataset.i];const conc=(d.concluidos!==undefined)?d.concluidos:d.entregues;const sal=(d.saldo!==undefined)?d.saldo:d.acumulado;showTT(e,`<b>${d.mes}</b><br>entraram ${d.criados} · concluídos ${conc}<br>saldo p/ o próximo mês: ${sal}`);});c.addEventListener('mouseleave',hideTT);});
}
document.getElementById('ft').innerHTML='Gerado a partir de "Resumo bugs" (export Jira). Métricas marcadas N/D não têm dado de origem — ver notas. Custo sempre rotulado como estimativa distribuída. Substitua o objeto DATA no topo do arquivo para atualizar.';
render();
</script>
</body></html>'''

html=html.replace('__DATA__',DATA).replace('__PERIODO__',d['meta']['periodo']).replace('__NBUGS__',str(d['meta']['total_bugs_base_atual'])).replace('__LOGO_DARK__',LOGO_DARK).replace('__LOGO__',LOGO)
open('dashboard_setor.html','w').write(html)
print('escrito, tamanho KB:', round(len(html)/1024,1))
