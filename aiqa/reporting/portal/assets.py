"""Shared, self-contained CSS/JS for the portal (no external/CDN assets).

Keeping the markup styling here lets both the per-run report and the landing
dashboard share one professional, responsive, dark/light theme.
"""

from __future__ import annotations

BASE_CSS = """
:root{
  --bg:#f4f6fb; --surface:#ffffff; --surface-2:#f8fafc; --border:#e2e8f0;
  --text:#0f172a; --muted:#64748b; --primary:#4f46e5; --primary-2:#6366f1;
  --ok:#16a34a; --warn:#d97706; --bad:#dc2626; --info:#0891b2;
  --shadow:0 1px 3px rgba(15,23,42,.08),0 1px 2px rgba(15,23,42,.04);
  --radius:14px;
}
html[data-theme='dark']{
  --bg:#0b1120; --surface:#111827; --surface-2:#0f172a; --border:#1f2937;
  --text:#e5e7eb; --muted:#94a3b8; --primary:#818cf8; --primary-2:#a5b4fc;
  --shadow:0 1px 3px rgba(0,0,0,.5);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:'Segoe UI',system-ui,-apple-system,Arial,sans-serif;font-size:14px;line-height:1.5}
a{color:var(--primary);text-decoration:none}
a:hover{text-decoration:underline}
.app{display:flex;min-height:100vh}
.side{width:290px;flex:0 0 290px;background:var(--surface);border-right:1px solid var(--border);
  position:sticky;top:0;height:100vh;overflow-y:auto;padding:18px 14px}
.main{flex:1;min-width:0;padding:22px 28px;max-width:1500px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;margin-bottom:16px}
.brand .dot{width:12px;height:12px;border-radius:3px;background:linear-gradient(135deg,var(--primary),var(--primary-2))}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:26px 0 12px;display:flex;align-items:center;gap:8px}
.sub{color:var(--muted);margin:0 0 18px}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.btn{border:1px solid var(--border);background:var(--surface);color:var(--text);
  padding:7px 12px;border-radius:9px;cursor:pointer;font-size:13px}
.btn:hover{border-color:var(--primary)}
.btn.primary{background:var(--primary);color:#fff;border-color:var(--primary)}
.grid{display:grid;gap:16px}
.kpis{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}
.cards{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:16px;box-shadow:var(--shadow)}
.kpi .label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.kpi .value{font-size:28px;font-weight:700;margin-top:6px}
.kpi .value small{font-size:14px;color:var(--muted);font-weight:500}
.badge{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:999px;
  font-size:12px;font-weight:600;border:1px solid transparent}
.b-ok{background:rgba(22,163,74,.12);color:var(--ok);border-color:rgba(22,163,74,.3)}
.b-warn{background:rgba(217,119,6,.12);color:var(--warn);border-color:rgba(217,119,6,.3)}
.b-bad{background:rgba(220,38,38,.12);color:var(--bad);border-color:rgba(220,38,38,.3)}
.b-info{background:rgba(8,145,178,.12);color:var(--info);border-color:rgba(8,145,178,.3)}
.b-muted{background:var(--surface-2);color:var(--muted);border-color:var(--border)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}
th{color:var(--muted);font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.03em;
  position:sticky;top:0;background:var(--surface);cursor:pointer}
tbody tr:hover{background:var(--surface-2)}
.table-wrap{overflow:auto;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface)}
.input{width:100%;padding:8px 11px;border:1px solid var(--border);border-radius:9px;
  background:var(--surface);color:var(--text);font-size:13px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
.filters select,.filters input{padding:7px 10px;border:1px solid var(--border);border-radius:9px;
  background:var(--surface);color:var(--text);font-size:13px}
.nav-item{display:block;padding:9px 11px;border-radius:9px;color:var(--text);cursor:pointer;
  border:1px solid transparent;margin-bottom:4px}
.nav-item:hover{background:var(--surface-2);text-decoration:none}
.nav-item .meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px}
.nav-item .tname{font-weight:600;font-size:13px}
.accordion{border:1px solid var(--border);border-radius:var(--radius);margin-bottom:14px;
  background:var(--surface);overflow:hidden}
.accordion>.head{padding:14px 16px;cursor:pointer;display:flex;justify-content:space-between;
  align-items:center;gap:10px}
.accordion>.head:hover{background:var(--surface-2)}
.accordion>.body{padding:0 16px 16px;display:none}
.accordion.open>.body{display:block}
.meta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.meta-grid .m{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:9px 11px}
.meta-grid .m .k{color:var(--muted);font-size:11px;text-transform:uppercase}
.meta-grid .m .v{font-weight:600;margin-top:3px;white-space:normal;word-break:break-word}
pre{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:12px;
  overflow:auto;font-size:12px;white-space:pre-wrap;word-break:break-word}
ul.clean{margin:8px 0;padding-left:18px}
ul.clean li{margin:4px 0}
.progress{height:10px;border-radius:999px;background:var(--surface-2);overflow:hidden;border:1px solid var(--border)}
.progress>span{display:block;height:100%;background:linear-gradient(90deg,var(--ok),#4ade80)}
.gauge{font-size:34px;font-weight:800}
.muted{color:var(--muted)}
.right{text-align:right}
.chip-row{display:flex;gap:6px;flex-wrap:wrap}
.hidden{display:none!important}
canvas{max-width:100%}
.bar-chart{display:flex;flex-direction:column;gap:8px}
.bar-chart .row{display:grid;grid-template-columns:120px 1fr 44px;align-items:center;gap:8px;font-size:12px}
.bar-chart .track{background:var(--surface-2);border-radius:999px;height:14px;overflow:hidden;border:1px solid var(--border)}
.bar-chart .fill{height:100%;background:linear-gradient(90deg,var(--primary),var(--primary-2))}
.spark{display:flex;align-items:flex-end;gap:3px;height:60px}
.spark .b{flex:1;background:linear-gradient(180deg,var(--primary),var(--primary-2));border-radius:3px 3px 0 0;min-height:2px}
.footer{margin-top:30px;color:var(--muted);font-size:12px;text-align:center}
"""

THEME_JS = """
(function(){
  var key='aiqa-theme';
  var saved=localStorage.getItem(key);
  if(saved) document.documentElement.setAttribute('data-theme',saved);
  window.toggleTheme=function(){
    var cur=document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark';
    document.documentElement.setAttribute('data-theme',cur);
    localStorage.setItem(key,cur);
  };
})();
window.toggleAccordion=function(el){el.parentElement.classList.toggle('open');};
window.copyText=function(id,btn){
  var node=document.getElementById(id);if(!node)return;
  var t=node.innerText||node.textContent;
  navigator.clipboard.writeText(t).then(function(){
    if(btn){var o=btn.textContent;btn.textContent='Copied';setTimeout(function(){btn.textContent=o;},1200);}
  });
};
window.downloadText=function(id,filename){
  var node=document.getElementById(id);if(!node)return;
  var blob=new Blob([node.innerText||node.textContent],{type:'text/plain'});
  var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;a.click();
};
"""
