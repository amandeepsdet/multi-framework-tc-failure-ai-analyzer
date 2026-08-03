"""DashboardGenerator — renders the landing ``index.html`` portal.

Aggregates the whole run history into a single, self-contained, interactive
dashboard: overview KPIs, run-history table with search/filter, quality trends,
AI insights, release readiness, client-side run comparison and the knowledge
base. All run summaries are embedded as JSON so the portal works fully offline
(``file://``) with no server and no CDN.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .assets import BASE_CSS, THEME_JS
from .insights import AIInsightsEngine
from .knowledge_base import KnowledgeEntry
from .models import ExecutionRun, utc_now_iso
from .trends import TrendAnalyzer


class DashboardGenerator:
    """Builds and writes ``index.html`` from the run history."""

    def generate(
        self,
        runs: list[ExecutionRun],
        *,
        knowledge: Iterable[KnowledgeEntry] = (),
        output_path: Path | str,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        trend = TrendAnalyzer().analyze(runs).to_dict()
        insights = AIInsightsEngine().insights(runs)
        summaries = [r.to_summary_dict() for r in runs]
        kb = [self._kb_row(e) for e in knowledge]

        data = {
            "runs": summaries,
            "trend": trend,
            "insights": insights,
            "knowledge": kb,
            "generated": utc_now_iso(),
        }
        html = self._html(data)
        output_path.write_text(html, encoding="utf-8")
        return output_path

    @staticmethod
    def _kb_row(e: KnowledgeEntry) -> dict[str, Any]:
        return {
            "test_name": e.test_name,
            "category": e.category,
            "owner": e.owner,
            "occurrences": e.occurrences,
            "avg_confidence": e.avg_confidence,
            "last_seen": e.last_seen,
            "fix": e.most_successful_fix,
        }

    def _html(self, data: dict[str, Any]) -> str:
        payload = json.dumps(data, ensure_ascii=False)
        return f"""<!DOCTYPE html>
<html lang="en" data-theme="light"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIQA · Quality Intelligence Dashboard</title>
<style>{BASE_CSS}</style></head><body>
<div class="app">
<aside class="side">
  <div class="brand"><span class="dot"></span> Quality Intelligence</div>
  <input id="globalSearch" class="input" placeholder="Search all executions…"
    oninput="renderTable()" style="margin-bottom:12px">
  <a class="nav-item" onclick="jump('overview')">Overview</a>
  <a class="nav-item" onclick="jump('readiness')">Release Readiness</a>
  <a class="nav-item" onclick="jump('trends')">Quality Trends</a>
  <a class="nav-item" onclick="jump('insights')">AI Insights</a>
  <a class="nav-item" onclick="jump('compare')">Run Comparison</a>
  <a class="nav-item" onclick="jump('history')">Execution History</a>
  <a class="nav-item" onclick="jump('knowledge')">Knowledge Base</a>
  <button class="btn" style="margin-top:14px;width:100%" onclick="toggleTheme()">Toggle Theme</button>
</aside>
<main class="main">
  <div class="topbar">
    <div><h1>Quality Intelligence Dashboard</h1>
      <p class="sub" id="generated"></p></div>
  </div>

  <section id="overview"><h2>Overview</h2><div class="grid kpis" id="kpis"></div></section>
  <section id="readiness"><h2>Release Readiness</h2><div id="readinessCard"></div></section>
  <section id="trends"><h2>Quality Trends (last 10 runs)</h2><div class="grid cards" id="trendCards"></div></section>
  <section id="insights"><h2>Recent AI Insights</h2><div class="card" id="insightsCard"></div></section>

  <section id="compare"><h2>Run Comparison</h2>
    <div class="card">
      <div class="filters">
        <select id="cmpA" class="input" style="max-width:220px"></select>
        <select id="cmpB" class="input" style="max-width:220px"></select>
        <button class="btn primary" onclick="renderComparison()">Compare</button>
      </div>
      <div id="cmpResult"></div>
    </div>
  </section>

  <section id="history"><h2>Execution History</h2>
    <div class="filters">
      <input id="fSearch" class="input" style="max-width:220px" placeholder="Filter table…" oninput="renderTable()">
      <select id="fFramework" class="input" onchange="renderTable()"></select>
      <select id="fEnv" class="input" onchange="renderTable()"></select>
      <select id="fHealth" class="input" onchange="renderTable()"></select>
      <select id="fReadiness" class="input" onchange="renderTable()"></select>
    </div>
    <div class="table-wrap"><table id="historyTable">
      <thead><tr>
        <th>Run ID</th><th>Date</th><th>Framework</th><th>Env</th><th>Browser</th>
        <th>Total</th><th>Pass</th><th>Fail</th><th>Skip</th><th>Duration</th>
        <th>Avg Conf</th><th>Quality</th><th>Health</th><th>Actions</th>
      </tr></thead><tbody id="historyBody"></tbody>
    </table></div>
  </section>

  <section id="knowledge"><h2>AI Knowledge Base — Top Recurring Failures</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Test</th><th>Category</th><th>Owner</th><th>Occurrences</th>
        <th>Avg Conf</th><th>Last Seen</th><th>Best Known Fix</th></tr></thead>
      <tbody id="kbBody"></tbody>
    </table></div>
  </section>

  <div class="footer">Generated by AIQA · Quality Intelligence Platform</div>
</main>
</div>
<script id="aiqa-data" type="application/json">{payload}</script>
<script>{THEME_JS}</script>
<script>{_DASHBOARD_JS}</script>
</body></html>
"""


_DASHBOARD_JS = r"""
var DATA = JSON.parse(document.getElementById('aiqa-data').textContent || '{}');
var RUNS = DATA.runs || [];
function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':String(s));return d.innerHTML;}
function healthClass(h){return h==='Healthy'?'b-ok':h==='Warning'?'b-warn':'b-bad';}
function readyClass(r){return r==='READY'?'b-ok':r==='AT RISK'?'b-warn':'b-bad';}
function bandClass(b){return (b==='Excellent'||b==='Good')?'b-ok':b==='Warning'?'b-warn':'b-bad';}
function jump(id){var el=document.getElementById(id);if(el)el.scrollIntoView({behavior:'smooth',block:'start'});}

function latest(){return RUNS.length?RUNS[RUNS.length-1]:null;}

function renderKpis(){
  var el=document.getElementById('kpis'); var r=latest();
  if(!r){el.innerHTML="<div class='card'>No executions recorded yet.</div>";return;}
  var totalRuns=RUNS.length;
  var totalTests=RUNS.reduce(function(a,x){return a+(x.total||0);},0);
  var totalFail=RUNS.reduce(function(a,x){return a+(x.failed||0);},0);
  var avgPass=Math.round(RUNS.reduce(function(a,x){return a+(x.pass_rate||0);},0)/totalRuns);
  function kpi(l,v,s){return "<div class='card kpi'><div class='label'>"+esc(l)+"</div><div class='value'>"+esc(v)+(s?" <small>"+esc(s)+"</small>":"")+"</div></div>";}
  el.innerHTML=[
    kpi('Latest Pass Rate',Math.round(r.pass_rate),'%'),
    kpi('Latest Quality',r.quality_score,'/100'),
    kpi('Build Health',r.build_health),
    kpi('Open Critical',r.critical||0),
    kpi('Total Runs',totalRuns),
    kpi('Total Tests',totalTests),
    kpi('Total Failures',totalFail),
    kpi('Avg Pass Rate',avgPass,'%')
  ].join('');
}

function renderReadiness(){
  var r=latest(); var el=document.getElementById('readinessCard');
  if(!r){el.innerHTML='';return;}
  el.innerHTML="<div class='card'><div class='chip-row'>"+
    "<span class='badge "+readyClass(r.release_readiness)+"'>"+esc(r.release_readiness)+"</span>"+
    "<span class='badge "+bandClass(r.quality_band)+"'>Quality: "+esc(r.quality_band)+" ("+r.quality_score+")</span>"+
    "<span class='badge "+healthClass(r.build_health)+"'>Build: "+esc(r.build_health)+"</span>"+
    "</div><p class='muted' style='margin-top:10px'>Latest run "+esc(r.run_id)+
    " · "+r.failed+" failure(s), "+ (r.critical||0)+" critical, "+(r.security||0)+" security.</p></div>";
}

function spark(title,arr,suffix){
  arr=arr||[]; var max=Math.max.apply(null,arr.concat([1]));
  var bars=arr.map(function(v){var h=Math.round(100*v/max);return "<div class='b' style='height:"+h+"%' title='"+v+"'></div>";}).join('');
  var last=arr.length?arr[arr.length-1]:0;
  return "<div class='card'><h2 style='margin-top:0'>"+esc(title)+" <span class='muted' style='font-weight:400'>· now "+esc(last)+(suffix||'')+"</span></h2><div class='spark'>"+bars+"</div></div>";
}

function renderTrends(){
  var t=DATA.trend||{}; var el=document.getElementById('trendCards');
  el.innerHTML=[
    spark('Pass Rate',t.pass_rate,'%'),
    spark('Failure Count',t.failure_count,''),
    spark('Quality Score',t.quality_score,''),
    spark('Avg Confidence',t.avg_confidence,'%'),
    spark('Critical Failures',t.critical,''),
    spark('Duration (s)',t.duration_s,'s')
  ].join('');
}

function renderInsights(){
  var el=document.getElementById('insightsCard'); var ins=DATA.insights||[];
  if(!ins.length){el.innerHTML="<span class='muted'>No insights yet — run more executions to build trends.</span>";return;}
  el.innerHTML="<ul class='clean'>"+ins.map(function(i){return "<li>"+esc(i)+"</li>";}).join('')+"</ul>";
}

function fillSelect(id,vals,label){
  var s=document.getElementById(id); if(!s)return;
  s.innerHTML="<option value=''>"+label+"</option>"+vals.map(function(v){return "<option>"+esc(v)+"</option>";}).join('');
}
function uniq(key){var set={};RUNS.forEach(function(r){if(r[key])set[r[key]]=1;});return Object.keys(set).sort();}

function passesFilters(r){
  var q=(document.getElementById('fSearch').value||'').toLowerCase();
  var g=(document.getElementById('globalSearch').value||'').toLowerCase();
  var fw=document.getElementById('fFramework').value;
  var env=document.getElementById('fEnv').value;
  var health=document.getElementById('fHealth').value;
  var ready=document.getElementById('fReadiness').value;
  if(fw&&r.framework!==fw)return false;
  if(env&&r.environment!==env)return false;
  if(health&&r.build_health!==health)return false;
  if(ready&&r.release_readiness!==ready)return false;
  var hay=JSON.stringify(r).toLowerCase();
  if(q&&hay.indexOf(q)<0)return false;
  if(g&&hay.indexOf(g)<0)return false;
  return true;
}

function renderTable(){
  var body=document.getElementById('historyBody');
  var rows=RUNS.slice().reverse().filter(passesFilters);
  if(!rows.length){body.innerHTML="<tr><td colspan='14' class='muted'>No matching executions.</td></tr>";return;}
  body.innerHTML=rows.map(function(r){
    var date=(r.started||'').replace('T',' ').slice(0,19);
    var view="<a class='btn' href='"+esc(r.report_rel||'#')+"' target='_blank'>View</a>";
    var dl="<a class='btn' href='"+esc((r.run_id||'')+'/report.json')+"' download>Download</a>";
    return "<tr>"+
      "<td>"+esc(r.run_id)+"</td>"+
      "<td>"+esc(date)+"</td>"+
      "<td>"+esc(r.framework||'n/a')+"</td>"+
      "<td>"+esc(r.environment||'n/a')+"</td>"+
      "<td>"+esc(r.browser||'n/a')+"</td>"+
      "<td>"+r.total+"</td><td>"+r.passed+"</td><td>"+r.failed+"</td><td>"+r.skipped+"</td>"+
      "<td>"+Math.round(r.duration_s||0)+"s</td>"+
      "<td>"+Math.round(r.avg_confidence||0)+"%</td>"+
      "<td><span class='badge "+bandClass(r.quality_band)+"'>"+r.quality_score+"</span></td>"+
      "<td><span class='badge "+healthClass(r.build_health)+"'>"+esc(r.build_health)+"</span></td>"+
      "<td class='chip-row'>"+view+" "+dl+"</td>"+
      "</tr>";
  }).join('');
}

function fillCompare(){
  var opts=RUNS.map(function(r){return "<option value='"+esc(r.run_id)+"'>"+esc(r.run_id)+"</option>";}).join('');
  var a=document.getElementById('cmpA'),b=document.getElementById('cmpB');
  a.innerHTML=opts;b.innerHTML=opts;
  if(RUNS.length>=2){a.selectedIndex=RUNS.length-2;b.selectedIndex=RUNS.length-1;}
}
function findRun(id){for(var i=0;i<RUNS.length;i++)if(RUNS[i].run_id===id)return RUNS[i];return null;}
function sigSet(r){var s={};(r.failures||[]).forEach(function(f){s[f.signature]=f;});return s;}

function renderComparison(){
  var A=findRun(document.getElementById('cmpA').value);
  var B=findRun(document.getElementById('cmpB').value);
  var el=document.getElementById('cmpResult');
  if(!A||!B){el.innerHTML='';return;}
  var sa=sigSet(A),sb=sigSet(B);
  var added=[],resolved=[],persist=[];
  Object.keys(sb).forEach(function(k){ (sa[k]?persist:added).push(sb[k]); });
  Object.keys(sa).forEach(function(k){ if(!sb[k])resolved.push(sa[k]); });
  function kpi(l,v){return "<div class='card kpi'><div class='label'>"+esc(l)+"</div><div class='value'>"+esc(v)+"</div></div>";}
  function sign(n){return (n>0?'+':'')+n;}
  el.innerHTML="<div class='grid kpis' style='margin-top:12px'>"+
    kpi('New Failures',added.length)+kpi('Resolved',resolved.length)+kpi('Persisting',persist.length)+
    kpi('Pass Rate Δ',sign(Math.round((B.pass_rate-A.pass_rate)))+' pts')+
    kpi('Quality Δ',sign(B.quality_score-A.quality_score))+
    kpi('Duration Δ',sign(Math.round(B.duration_s-A.duration_s))+'s')+
    "</div>";
}

function renderKb(){
  var body=document.getElementById('kbBody'); var kb=DATA.knowledge||[];
  if(!kb.length){body.innerHTML="<tr><td colspan='7' class='muted'>Knowledge base is empty.</td></tr>";return;}
  body.innerHTML=kb.map(function(e){
    return "<tr><td>"+esc(e.test_name)+"</td><td>"+esc(e.category)+"</td><td>"+esc(e.owner)+"</td>"+
      "<td>"+e.occurrences+"</td><td>"+Math.round(e.avg_confidence)+"%</td>"+
      "<td>"+esc((e.last_seen||'').replace('T',' ').slice(0,19))+"</td><td>"+esc(e.fix||'n/a')+"</td></tr>";
  }).join('');
}

(function init(){
  document.getElementById('generated').textContent='Generated '+(DATA.generated||'').replace('T',' ').slice(0,19)+' · '+RUNS.length+' execution(s)';
  fillSelect('fFramework',uniq('framework'),'All frameworks');
  fillSelect('fEnv',uniq('environment'),'All environments');
  fillSelect('fHealth',['Healthy','Warning','Critical'],'All health');
  fillSelect('fReadiness',['READY','AT RISK','NOT READY'],'All readiness');
  renderKpis();renderReadiness();renderTrends();renderInsights();
  fillCompare();renderComparison();renderTable();renderKb();
})();
"""
