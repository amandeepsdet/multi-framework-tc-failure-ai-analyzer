"""AI execution report rendering (Markdown / JSON / HTML).

Produces the per-failure analysis report written to ``ai_reports/`` and the
HTML fragment embedded into the pytest-html report / attached to Allure. Also
renders the aggregate trend + release-readiness report.
"""

from __future__ import annotations

import html
import json
from importlib import metadata as _metadata
from pathlib import Path
from typing import Any

from ._logging import get_logger

from .ai_config import AIConfig, ai_config
from .models import AnalysisResult, FailureRecord
from .trend_analyzer import ReleaseReadiness, TrendReport

logger = get_logger("ai.report_generator")

_CONFIDENCE_COLORS = [(85, "#1a7f37"), (60, "#bf8700"), (0, "#cf222e")]


def _confidence_color(confidence: int) -> str:
    for threshold, color in _CONFIDENCE_COLORS:
        if confidence >= threshold:
            return color
    return "#cf222e"


# --------------------------------------------------------------------------- #
# Presentation assets for the standalone enterprise dashboard report.          #
# These affect PRESENTATION ONLY — no analysis logic or data model is touched. #
# --------------------------------------------------------------------------- #

# Severity value -> (accent colour, soft background, human label, priority)
_SEVERITY_META: dict[str, tuple[str, str, str, str]] = {
    "Blocker": ("#b30000", "#ffe3e3", "Blocker", "P0"),
    "Critical": ("#cf222e", "#ffebe9", "Critical", "P1"),
    "Major": ("#bc4c00", "#fff1e5", "High", "P2"),
    "Minor": ("#9a6700", "#fff8c5", "Medium", "P3"),
    "Trivial": ("#0969da", "#ddf4ff", "Low", "P4"),
}


def _severity_meta(severity: str) -> tuple[str, str, str, str]:
    return _SEVERITY_META.get(severity, ("#57606a", "#eaeef2", severity or "Info", "P3"))


def _package_version() -> str:
    for name in (
        "multi-framework-tc-failure-ai-analyzer",
        "playwright-tc-failure-ai-analyzer",
    ):
        try:
            return _metadata.version(name)
        except _metadata.PackageNotFoundError:
            continue
    return "3.0.0"


# Small inline SVG icon set (feather-style, stroke=currentColor). Presentation only.
_ICONS: dict[str, str] = {
    "robot": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="8" width="18" height="12" rx="2"/><path d="M12 8V4M8 2h8"/><circle cx="8.5" cy="14" r="1.4"/><circle cx="15.5" cy="14" r="1.4"/></svg>',
    "bug": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6a4 4 0 0 1 8 0M5 11h14M12 8v12M6 20a4 4 0 0 1-1-3v-2a7 7 0 0 1 14 0v2a4 4 0 0 1-1 3M4 9l2 2M20 9l-2 2M4 17l2-1M20 17l-2-1"/></svg>',
    "warning": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/></svg>',
    "search": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>',
    "code": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 8l-4 4 4 4M15 8l4 4-4 4"/></svg>',
    "shield": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/></svg>',
    "terminal": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/></svg>',
    "network": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></svg>',
    "camera": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h3l2-2h6l2 2h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.5"/></svg>',
    "brain": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 3 3 2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-3 3 2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/></svg>',
    "bulb": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10c.7.7 1 1.4 1 2h6c0-.6.3-1.3 1-2a6 6 0 0 0-4-10z"/></svg>',
    "clock": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    "check": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12l5 5L20 6"/></svg>',
    "copy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    "sun": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/></svg>',
    "moon": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/></svg>',
    "download": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 11l5 5 5-5M4 21h16"/></svg>',
    "print": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9V3h12v6M6 18H4a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2M6 14h12v7H6z"/></svg>',
    "user": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
    "tag": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l9-9 8 8-9 9z"/><circle cx="8" cy="8" r="1.4"/></svg>',
    "gauge": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 14l4-4"/></svg>',
    "git": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="9" r="2.5"/><path d="M6 8.5v7M18 11.5c0 3-4 2-8 4"/></svg>',
    "chip": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 3v2M14 3v2M10 19v2M14 19v2M3 10h2M3 14h2M19 10h2M19 14h2"/></svg>',
    "flow": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="19" r="2"/><path d="M12 7v10"/></svg>',
    "doc": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v4h4M9 13h6M9 17h6"/></svg>',
    "history": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>',
    "link": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>',
}

_REPORT_CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#f6f8fa;--panel:#fff;--panel-2:#f9fafb;--border:#d0d7de;--border-soft:#e6eaef;
  --text:#1f2328;--muted:#57606a;--muted-2:#8b949e;--accent:#0969da;--accent-soft:#ddf4ff;
  --green:#1a7f37;--green-bg:#dafbe1;--amber:#9a6700;--amber-bg:#fff8c5;--red:#cf222e;--red-bg:#ffebe9;
  --shadow:0 1px 0 rgba(31,35,40,.04),0 1px 3px rgba(31,35,40,.08);
  --shadow-lg:0 10px 30px rgba(31,35,40,.14);--radius:14px;--radius-sm:9px;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
  --sans:'Inter',"Segoe UI",-apple-system,BlinkMacSystemFont,Arial,sans-serif;
}
[data-theme="dark"]{
  --bg:#0d1117;--panel:#161b22;--panel-2:#0d1117;--border:#30363d;--border-soft:#21262d;
  --text:#e6edf3;--muted:#8b949e;--muted-2:#6e7681;--accent:#2f81f7;--accent-soft:#0b2942;
  --green:#3fb950;--green-bg:#12261b;--amber:#d29922;--amber-bg:#2b2412;--red:#f85149;--red-bg:#2b1416;
  --shadow:0 1px 0 rgba(0,0,0,.3);--shadow-lg:0 10px 30px rgba(0,0,0,.5);
}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
svg{width:16px;height:16px;flex:none;vertical-align:middle}
.wrap{max-width:1400px;margin:0 auto;padding:0 24px 56px}
.grid{display:grid;grid-template-columns:1fr 320px;gap:24px;align-items:start}
@media(max-width:980px){.grid{grid-template-columns:1fr}}
/* header */
.top{position:sticky;top:0;z-index:40;background:color-mix(in srgb,var(--panel) 88%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--border);}
.top-in{max-width:1400px;margin:0 auto;padding:14px 24px}
.top-row{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:11px;font-weight:700;font-size:17px;letter-spacing:-.01em}
.brand .ic{width:30px;height:30px;display:grid;place-items:center;border-radius:9px;background:linear-gradient(135deg,#0969da,#8250df);color:#fff;box-shadow:var(--shadow)}
.brand .ic svg{width:17px;height:17px}
.spacer{flex:1}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:11px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border:1px solid var(--border);border-radius:999px;background:var(--panel);color:var(--muted);font-size:12px;font-weight:500;white-space:nowrap}
.chip svg{width:13px;height:13px;opacity:.8}
.chip b{color:var(--text);font-weight:600}
.badge{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:999px;font-weight:700;font-size:12.5px;letter-spacing:.02em}
.badge.fail{background:var(--red-bg);color:var(--red);border:1px solid color-mix(in srgb,var(--red) 30%,transparent)}
.btn{display:inline-flex;align-items:center;gap:7px;padding:7px 12px;border:1px solid var(--border);border-radius:9px;background:var(--panel);color:var(--text);font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;transition:.15s}
.btn svg{width:15px;height:15px}
.btn:hover{border-color:var(--accent);color:var(--accent);transform:translateY(-1px)}
.btn.icon{padding:8px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap}
/* sections */
section{margin-top:22px;animation:fade .5s ease both}
.sec-h{display:flex;align-items:center;gap:9px;margin:0 0 12px;font-size:15px;font-weight:700;letter-spacing:-.01em}
.sec-h .si{width:24px;height:24px;display:grid;place-items:center;border-radius:7px;background:var(--accent-soft);color:var(--accent)}
.sec-h .si svg{width:15px;height:15px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px 18px}
/* KPI */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.kpi{background:var(--panel);border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:var(--radius-sm);padding:13px 15px;box-shadow:var(--shadow);transition:.18s}
.kpi:hover{box-shadow:var(--shadow-lg);transform:translateY(-2px)}
.kpi .k-top{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.kpi .k-top svg{width:15px;height:15px}
.kpi .k-val{font-size:23px;font-weight:800;margin-top:8px;letter-spacing:-.02em;word-break:break-word}
.kpi .k-desc{color:var(--muted);font-size:12px;margin-top:3px}
/* root cause */
.rc{display:grid;grid-template-columns:auto 1fr;gap:20px;align-items:center;border-left:6px solid var(--sev,#57606a)}
@media(max-width:640px){.rc{grid-template-columns:1fr;text-align:center}}
.rc .rc-body h2{margin:0 0 7px;font-size:22px;line-height:1.3;letter-spacing:-.02em}
.rc .rc-body p{margin:0;color:var(--muted);font-size:14px}
.rc-badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:13px}
.rc-fix{display:flex;gap:8px;align-items:flex-start;margin-top:13px;padding-top:12px;border-top:1px solid var(--border-soft);font-size:13.5px;color:var(--muted)}
.rc-fix svg{color:var(--green);margin-top:3px;width:16px;height:16px}
.rc-fix b{color:var(--text)}
.pill{display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border-radius:999px;font-size:12px;font-weight:700;border:1px solid transparent}
.pill svg{width:13px;height:13px}
/* confidence ring */
.ring{--v:0;width:118px;height:118px;position:relative;display:grid;place-items:center}
.ring svg{transform:rotate(-90deg);width:118px;height:118px}
.ring .bg{fill:none;stroke:var(--border-soft);stroke-width:11}
.ring .fg{fill:none;stroke:var(--ring,#1a7f37);stroke-width:11;stroke-linecap:round;stroke-dasharray:326.7;stroke-dashoffset:326.7;transition:stroke-dashoffset 1.1s cubic-bezier(.4,0,.2,1)}
.ring .num{position:absolute;font-size:26px;font-weight:800;letter-spacing:-.02em}
.ring .num small{display:block;text-align:center;font-size:10.5px;font-weight:700;color:var(--muted);letter-spacing:.06em}
/* evidence */
.ev{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius-sm);margin-bottom:11px;overflow:hidden;box-shadow:var(--shadow)}
.ev>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:11px;padding:13px 15px;font-weight:600;user-select:none}
.ev>summary::-webkit-details-marker{display:none}
.ev>summary .ei{width:28px;height:28px;flex:none;display:grid;place-items:center;border-radius:8px;background:var(--accent-soft);color:var(--accent)}
.ev>summary .ei svg{width:15px;height:15px}
.ev>summary .chev{margin-left:auto;transition:.2s;color:var(--muted)}
.ev[open]>summary .chev{transform:rotate(90deg)}
.ev .tag-count{background:var(--panel-2);border:1px solid var(--border);color:var(--muted);border-radius:999px;padding:1px 9px;font-size:11px;font-weight:700}
.ev-body{padding:0 15px 15px;animation:slide .25s ease}
.codewrap{position:relative}
.copy-btn{position:absolute;top:8px;right:8px;z-index:2;padding:5px 9px;font-size:11.5px}
pre.code{margin:0;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:9px;padding:14px 15px;overflow:auto;font-family:var(--mono);font-size:12.5px;line-height:1.6;max-height:360px}
pre.code .k{color:#ff7b72}pre.code .s{color:#a5d6ff}pre.code .c{color:#8b949e}pre.code .n{color:#79c0ff}pre.code .f{color:#d2a8ff}
.kv{width:100%;border-collapse:collapse;font-size:12.5px}
.kv td{padding:7px 10px;border-bottom:1px solid var(--border-soft);vertical-align:top}
.kv td:first-child{color:var(--muted);font-weight:600;white-space:nowrap;width:150px}
.mono{font-family:var(--mono)}
.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
/* recommendation card */
.rec{border-left:4px solid var(--green)}
.rec-head{display:flex;gap:12px;align-items:flex-start}
.rec-ic{width:36px;height:36px;flex:none;display:grid;place-items:center;border-radius:9px;background:var(--green-bg);color:var(--green)}
.rec-ic svg{width:20px;height:20px}
.rec h3{margin:0 0 3px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--green)}
.rec-primary{margin:0;font-size:15.5px;font-weight:600;color:var(--text);line-height:1.5}
.rec-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px 22px;margin-top:16px;padding-top:15px;border-top:1px solid var(--border-soft)}
.rec-grid b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:5px}
.rec-grid p{margin:0;font-size:13px;line-height:1.55}
.rec-grid a{display:inline-flex;align-items:center;gap:6px;font-size:12.5px}
.rec-grid a svg{width:14px;height:14px}
/* screenshots */
.shots{display:flex;flex-wrap:wrap;gap:12px}
.shot{border:1px solid var(--border);border-radius:10px;overflow:hidden;cursor:zoom-in;width:200px;box-shadow:var(--shadow);transition:.18s}
.shot:hover{box-shadow:var(--shadow-lg);transform:translateY(-2px)}
.shot img{display:block;width:100%;height:130px;object-fit:cover}
.shot .cap{padding:7px 10px;font-size:11.5px;color:var(--muted)}
.modal{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.82);display:none;place-items:center;padding:30px}
.modal.on{display:grid}
.modal img{max-width:96vw;max-height:92vh;border-radius:8px;box-shadow:var(--shadow-lg)}
.modal .x{position:absolute;top:18px;right:22px;color:#fff;background:rgba(255,255,255,.12);border:0;border-radius:8px;padding:8px 12px;cursor:pointer;font-size:16px}
/* table */
.tbl-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow)}
table.data{width:100%;border-collapse:collapse;font-size:13px;min-width:520px}
table.data th{text-align:left;padding:11px 14px;background:var(--panel-2);color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--border)}
table.data td{padding:11px 14px;border-bottom:1px solid var(--border-soft)}
table.data tr.row{cursor:pointer}
table.data tr.row:hover{background:var(--accent-soft)}
table.data tr.detail td{background:var(--panel-2);color:var(--muted);font-size:12.5px}
.simbar{height:7px;border-radius:999px;background:var(--border-soft);overflow:hidden;min-width:90px}
.simbar span{display:block;height:100%;background:linear-gradient(90deg,#0969da,#8250df)}
/* timeline */
.timeline{position:relative;padding-left:8px}
.tl{position:relative;display:flex;gap:14px;padding:0 0 20px 22px;border-left:2px solid var(--border)}
.tl:last-child{border-left-color:transparent;padding-bottom:0}
.tl .dot{position:absolute;left:-9px;top:1px;width:16px;height:16px;border-radius:50%;background:var(--panel);border:3px solid var(--accent);box-shadow:var(--shadow)}
.tl.fail .dot{border-color:var(--red)}
.tl.ai .dot{border-color:#8250df}
.tl.done .dot{border-color:var(--green)}
.tl h4{margin:0;font-size:13.5px}
.tl p{margin:2px 0 0;color:var(--muted);font-size:12px}
/* sidebar */
.side{position:sticky;top:96px;display:flex;flex-direction:column;gap:16px}
@media(max-width:980px){.side{position:static}}
.side{gap:14px}
.side .card{padding:14px 15px}
.side h3{margin:0 0 10px;font-size:12.5px;display:flex;align-items:center;gap:8px;color:var(--text)}
.side h3 svg{width:15px;height:15px;color:var(--muted)}
.side .ring,.side .ring svg{width:104px;height:104px}
.side .ring .num{font-size:21px}
.side .ring .num small{font-size:9px}
.badge svg{width:14px;height:14px}
.meta-row{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid var(--border-soft);font-size:12.5px}
.meta-row:last-child{border-bottom:0}
.meta-row .l{color:var(--muted)}
.meta-row .v{font-weight:600;text-align:right;word-break:break-word;font-family:var(--mono);font-size:12px}
.chartbox{position:relative;height:170px}
/* search */
.searchbar{position:relative;margin-bottom:12px;max-width:340px}
.searchbar svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);width:15px;height:15px;color:var(--muted)}
.searchbar input{width:100%;padding:9px 12px 9px 34px;border:1px solid var(--border);border-radius:9px;background:var(--panel);color:var(--text);font:inherit;font-size:13px}
.searchbar input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.empty{color:var(--muted);font-size:13px;padding:10px 2px}
/* footer */
footer{margin-top:48px;border-top:1px solid var(--border);padding-top:22px;color:var(--muted);font-size:12.5px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}
footer .fl{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
footer a{display:inline-flex;align-items:center;gap:5px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:#1f2328;color:#fff;padding:10px 16px;border-radius:10px;font-size:13px;font-weight:600;opacity:0;pointer-events:none;transition:.25s;z-index:90;box-shadow:var(--shadow-lg)}
.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes slide{from{opacity:0}to{opacity:1}}
@media print{.top{position:static}.toolbar,.theme-t,.searchbar,.copy-btn{display:none!important}.ev[open]{page-break-inside:avoid}body{background:#fff}}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}
"""

_REPORT_JS = r"""
(function(){
  var data={};
  try{data=JSON.parse(document.getElementById('ai-data').textContent);}catch(e){}
  var root=document.documentElement;
  // theme
  var saved=null;try{saved=localStorage.getItem('aiqa-theme');}catch(e){}
  if(saved){root.setAttribute('data-theme',saved);}
  function toggleTheme(){var d=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',d);try{localStorage.setItem('aiqa-theme',d);}catch(e){}syncThemeIcon();drawCharts();}
  function syncThemeIcon(){var b=document.getElementById('themeBtn');if(!b)return;b.setAttribute('aria-label','Toggle theme');}
  // toast
  var toast=document.getElementById('toast'),tt;
  function say(m){if(!toast)return;toast.textContent=m;toast.classList.add('on');clearTimeout(tt);tt=setTimeout(function(){toast.classList.remove('on');},1600);}
  // copy
  function copyText(t,msg){if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(function(){say(msg||'Copied');},function(){fallbackCopy(t);say(msg||'Copied');});}else{fallbackCopy(t);say(msg||'Copied');}}
  function fallbackCopy(t){var ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();try{document.execCommand('copy');}catch(e){}document.body.removeChild(ta);}
  document.addEventListener('click',function(e){
    var c=e.target.closest('[data-copy]');
    if(c){e.preventDefault();e.stopPropagation();var sel=c.getAttribute('data-copy');var el=sel?document.querySelector(sel):null;copyText(el?el.innerText:c.getAttribute('data-copytext')||'','Copied to clipboard');return;}
    var t=e.target.closest('[data-action]');
    if(t){var a=t.getAttribute('data-action');
      if(a==='theme')toggleTheme();
      else if(a==='print')window.print();
      else if(a==='json')dl('analysis.json',JSON.stringify(data,null,2),'application/json');
      else if(a==='md')dl('analysis.md',data.markdown||'','text/markdown');
      else if(a==='html')dl((data.stem||'report')+'.html','<!DOCTYPE html>\n'+document.documentElement.outerHTML,'text/html');
      else if(a==='bug')copyText(data.bugReport||'','Bug report copied');
    }
    var row=e.target.closest('tr.row');
    if(row&&row.nextElementSibling&&row.nextElementSibling.classList.contains('detail')){row.nextElementSibling.style.display=row.nextElementSibling.style.display==='table-row'?'none':'table-row';}
    var shot=e.target.closest('[data-shot]');
    if(shot){openModal(shot.getAttribute('data-shot'));}
  });
  // modal
  var modal=document.getElementById('modal');
  function openModal(src){if(!modal)return;modal.querySelector('img').src=src;modal.classList.add('on');}
  if(modal){modal.addEventListener('click',function(){modal.classList.remove('on');});}
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&modal)modal.classList.remove('on');});
  // search filters
  function wireSearch(id,sel){var inp=document.getElementById(id);if(!inp)return;inp.addEventListener('input',function(){var q=inp.value.toLowerCase();var items=document.querySelectorAll(sel);var vis=0;items.forEach(function(it){var ok=it.textContent.toLowerCase().indexOf(q)>-1;it.style.display=ok?'':'none';if(ok)vis++;});var em=document.querySelector(inp.getAttribute('data-empty'));if(em)em.style.display=vis?'none':'block';});}
  wireSearch('searchEv','.ev');
  wireSearch('searchSim','#simBody tr.row');
  // confidence ring
  var ring=document.querySelector('.ring .fg');
  if(ring){var v=parseFloat(ring.getAttribute('data-v'))||0;var C=326.7;requestAnimationFrame(function(){setTimeout(function(){ring.style.strokeDashoffset=(C-C*v/100).toFixed(1);},120);});}
  // charts (optional, graceful if Chart.js unavailable)
  var charts=[];
  function css(n){return getComputedStyle(root).getPropertyValue(n).trim();}
  function drawCharts(){
    if(typeof Chart==='undefined')return;
    Chart.defaults.font.family="'Inter','Segoe UI',sans-serif";Chart.defaults.font.size=11;
    charts.forEach(function(c){c.destroy();});charts=[];
    document.querySelectorAll('canvas[data-chart]').forEach(function(cv){
      var cfg;try{cfg=JSON.parse(cv.getAttribute('data-chart'));}catch(e){return;}
      var grid=css('--border-soft')||'#e6eaef',txt=css('--muted')||'#57606a',panel=css('--panel')||'#fff';
      cfg.options=cfg.options||{};cfg.options.plugins=cfg.options.plugins||{};
      if(cfg.type!=='doughnut'){cfg.options.scales={x:{ticks:{color:txt},grid:{display:false}},y:{ticks:{color:txt,precision:0},grid:{color:grid},border:{display:false},beginAtZero:true}};}
      cfg.options.plugins.legend=cfg.type==='doughnut'?{labels:{color:txt,boxWidth:10,usePointStyle:true,font:{size:11}},position:'bottom'}:{display:false};
      cfg.options.plugins.tooltip={backgroundColor:'#1f2328',padding:10,cornerRadius:8,titleFont:{size:12},bodyFont:{size:12},displayColors:true,boxPadding:4};
      cfg.options.responsive=true;cfg.options.maintainAspectRatio=false;cfg.options.animation={duration:700};
      try{charts.push(new Chart(cv,cfg));}catch(e){}
    });
  }
  syncThemeIcon();
  if(typeof Chart!=='undefined'){drawCharts();}else{
    var s=document.createElement('script');s.src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
    s.onload=drawCharts;s.onerror=function(){document.querySelectorAll('[data-chartsec]').forEach(function(x){x.style.display='none';});};document.head.appendChild(s);
  }
  function dl(name,content,type){var b=new Blob([content],{type:type});var u=URL.createObjectURL(b);var a=document.createElement('a');a.href=u;a.download=name;document.body.appendChild(a);a.click();document.body.removeChild(a);setTimeout(function(){URL.revokeObjectURL(u);},1000);say('Downloaded '+name);}
})();
"""


class ReportGenerator:
    """Renders analysis and trend reports in multiple formats."""

    def __init__(self, cfg: AIConfig = ai_config) -> None:
        self.cfg = cfg

    # ---------------------------------------------------------- single failure
    def to_markdown(self, record: FailureRecord, analysis: AnalysisResult) -> str:
        evidence = "\n".join(f"- {e}" for e in analysis.evidence) or "- (none)"
        similar = (
            "\n".join(
                f"- {s.get('test_name', '?')} ({s.get('category', '?')}, "
                f"{s.get('similarity', 0)}% similar)"
                for s in analysis.similar_failures
            )
            or "- (none found)"
        )
        return (
            f"# AI Failure Analysis — {record.test_name}\n\n"
            f"- **Category:** {analysis.category.value}\n"
            f"- **Confidence:** {analysis.confidence}%\n"
            f"- **Severity:** {analysis.severity.value}\n"
            f"- **Likely Owner:** {analysis.owner}\n"
            f"- **Analysed by:** {analysis.source}\n"
            f"- **Timestamp:** {record.timestamp}\n\n"
            f"## Root Cause\n{analysis.root_cause}\n\n"
            f"## Evidence\n{evidence}\n\n"
            f"## Recommended Fix\n{analysis.recommended_fix}\n\n"
            f"## Reasoning\n{analysis.reasoning}\n\n"
            f"## Similar Past Failures\n{similar}\n"
        )

    def to_html(self, record: FailureRecord, analysis: AnalysisResult) -> str:
        """Compact self-contained HTML fragment for pytest-html / Allure."""
        esc = html.escape
        color = _confidence_color(analysis.confidence)
        evidence = "".join(f"<li>{esc(e)}</li>" for e in analysis.evidence)
        similar = "".join(
            f"<li>{esc(str(s.get('test_name', '?')))} — {esc(str(s.get('category', '?')))} "
            f"({s.get('similarity', 0)}%)</li>"
            for s in analysis.similar_failures
        )
        return (
            "<div class='ai-analysis' style='border:1px solid #d0d7de;border-radius:8px;"
            "padding:12px;margin:8px 0;font-family:sans-serif'>"
            "<h3 style='margin-top:0'>&#129504; AI Failure Analysis</h3>"
            f"<p><strong>Root Cause:</strong> {esc(analysis.root_cause)}</p>"
            f"<p><strong>Category:</strong> {esc(analysis.category.value)} &nbsp;|&nbsp; "
            f"<strong>Severity:</strong> {esc(analysis.severity.value)} &nbsp;|&nbsp; "
            f"<strong>Owner:</strong> {esc(analysis.owner)}</p>"
            f"<p><strong>Confidence:</strong> "
            f"<span style='color:{color};font-weight:bold'>{analysis.confidence}%</span> "
            f"<span style='color:#57606a'>(via {esc(analysis.source)})</span></p>"
            f"<p><strong>Evidence:</strong></p><ul>{evidence or '<li>(none)</li>'}</ul>"
            f"<p><strong>Suggested Fix:</strong> {esc(analysis.recommended_fix)}</p>"
            + (f"<p><strong>Similar Failures:</strong></p><ul>{similar}</ul>" if similar else "")
            + "</div>"
        )

    # ---------------------------------------------------- standalone dashboard
    def to_html_document(
        self, record: FailureRecord, analysis: AnalysisResult, stem: str = "report"
    ) -> str:
        """Full self-contained enterprise-dashboard HTML for the saved report.

        Presentation only — consumes the same ``FailureRecord`` / ``AnalysisResult``
        as every other renderer and computes no new analysis.
        """
        esc = html.escape
        a, r = analysis, record
        m, ev = r.metadata, r.evidence
        sev = a.severity.value
        sev_color, sev_bg, sev_label, priority = _severity_meta(sev)
        conf = int(a.confidence)
        conf_color = _confidence_color(conf)
        pkg = _package_version()
        ic = _ICONS
        _uid = {"n": 0}

        def nid() -> str:
            _uid["n"] += 1
            return f"c{_uid['n']}"

        def code_block(text: str, max_h: str = "") -> str:
            cid = nid()
            style = f" style='max-height:{max_h}'" if max_h else ""
            return (
                "<div class='codewrap'>"
                f"<button class='btn copy-btn' data-copy='#{cid}' type='button'>{ic['copy']}Copy</button>"
                f"<pre class='code' id='{cid}'{style}>{esc(text)}</pre></div>"
            )

        def chip(icon_key: str, label: str, value: str) -> str:
            if not value:
                return ""
            return f"<span class='chip'>{ic.get(icon_key, '')}{esc(label)}&nbsp;<b>{esc(value)}</b></span>"

        # ---- header chips
        exec_time = f"{m.execution_time_s:.2f}s" if m.execution_time_s is not None else ""
        commit = (m.git_commit or "")[:10]
        chips = "".join([
            chip("robot", "Test", r.test_name),
            chip("tag", "Category", a.category.value),
            chip("clock", "Time", exec_time),
            chip("chip", "Framework", m.framework_version),
            chip("network", "Browser", m.browser),
            chip("shield", "Env", m.environment),
            chip("terminal", "OS", m.os),
            chip("code", "Python", m.python_version),
            chip("git", "Commit", commit),
            chip("doc", "Package", f"v{pkg}"),
            chip("history", "Timestamp", (r.timestamp or "").replace("T", " ")[:19]),
        ])

        # ---- KPI cards
        def kpi(icon_key: str, label: str, value: str, desc: str, color: str) -> str:
            return (
                f"<div class='kpi' style='border-left-color:{color}'>"
                f"<div class='k-top'>{ic.get(icon_key, '')}{esc(label)}</div>"
                f"<div class='k-val' style='color:{color}'>{esc(value)}</div>"
                f"<div class='k-desc'>{esc(desc)}</div></div>"
            )

        kpis = "".join([
            kpi("warning", "Criticality", sev_label, f"Severity: {sev} · {priority}", sev_color),
            kpi("gauge", "Confidence", f"{conf}%", "Model certainty", conf_color),
            kpi("tag", "Category", a.category.value, "Root-cause class", "#8250df"),
            kpi("user", "Owner Team", a.owner or "Unassigned", "Suggested routing", "#0969da"),
            kpi("brain", "Analysed By", a.source, "Analysis engine", "#1a7f37"),
            kpi("search", "Evidence", str(len(a.evidence)), "Signals collected", "#bc4c00"),
        ])

        # ---- confidence ring
        ring = (
            "<div class='ring' role='img' aria-label='Confidence "
            f"{conf} percent'><svg viewBox='0 0 118 118'>"
            "<circle class='bg' cx='59' cy='59' r='52'></circle>"
            f"<circle class='fg' cx='59' cy='59' r='52' data-v='{conf}' "
            f"style='--ring:{conf_color}'></circle></svg>"
            f"<div class='num' style='color:{conf_color}'>{conf}%<small>CONFIDENCE</small></div></div>"
        )

        rc_badges = "".join([
            f"<span class='pill' style='background:{sev_bg};color:{sev_color};border-color:{sev_color}'>{ic['warning']}{esc(sev_label)} · {esc(sev)}</span>",
            f"<span class='pill' style='background:var(--accent-soft);color:var(--accent)'>{ic['tag']}{esc(a.category.value)}</span>",
            f"<span class='pill' style='background:var(--accent-soft);color:var(--accent)'>{ic['user']}{esc(a.owner or 'Unassigned')}</span>",
            f"<span class='pill' style='background:var(--accent-soft);color:var(--accent)'>{ic['brain']}{esc(a.source)}</span>",
        ])
        root_cause = (
            "<section><h2 class='sec-h'><span class='si'>" + ic["warning"] + "</span>Root Cause</h2>"
            f"<div class='card rc' style='--sev:{sev_color}'>{ring}"
            "<div class='rc-body'><h2>" + esc(a.root_cause or "Root cause not determined") + "</h2>"
            f"<p>{esc(a.reasoning)}</p><div class='rc-badges'>{rc_badges}</div>"
            "<div class='rc-fix'>" + ic["bulb"] + "<span><b>Suggested fix:</b> "
            + esc(a.recommended_fix or "n/a") + "</span></div>"
            "</div></div></section>"
        )

        # ---- evidence accordion
        def acc(icon_key: str, title: str, count: str, body: str, is_open: bool = False) -> str:
            cnt = f"<span class='tag-count'>{esc(count)}</span>" if count else ""
            return (
                f"<details class='ev'{' open' if is_open else ''}>"
                f"<summary><span class='ei'>{ic.get(icon_key, '')}</span>{esc(title)}{cnt}"
                f"<span class='chev'>{ic['tag'] and ''}&#8250;</span></summary>"
                f"<div class='ev-body'>{body}</div></details>"
            )

        ev_cards: list[str] = []
        if a.evidence:
            body = "<ul style='margin:6px 0 0;padding-left:18px'>" + "".join(
                f"<li>{esc(str(x))}</li>" for x in a.evidence
            ) + "</ul>"
            ev_cards.append(acc("brain", "AI Evidence Signals", str(len(a.evidence)), body, True))
        if ev.exception_type or ev.exception_message:
            body = code_block(f"{ev.exception_type}: {ev.exception_message}".strip(": "))
            ev_cards.append(acc("warning", "Exception", ev.exception_type or "", body))
        if ev.assertion_message:
            ev_cards.append(acc("check", "Assertion", "", code_block(ev.assertion_message)))
        if ev.stacktrace:
            ev_cards.append(acc("code", "Stacktrace", "", code_block(ev.stacktrace, "420px")))
        if ev.network:
            rows = "".join(
                "<tr><td class='mono'>" + esc(str(n.get("method", ""))) + "</td>"
                "<td class='mono' style='word-break:break-all'>" + esc(str(n.get("url", ""))) + "</td>"
                "<td class='mono'>" + esc(str(n.get("status", ""))) + "</td>"
                "<td class='mono'>" + (f"{n.get('duration_ms')}ms" if n.get("duration_ms") is not None else "") + "</td></tr>"
                for n in ev.network
            )
            body = (
                "<div class='tbl-wrap'><table class='data'><thead><tr><th>Method</th>"
                "<th>URL</th><th>Status</th><th>Duration</th></tr></thead><tbody>"
                + rows + "</tbody></table></div>"
            )
            ev_cards.append(acc("network", "Network Requests", str(len(ev.network)), body))
        if ev.api_responses:
            ev_cards.append(acc("network", "API Responses", str(len(ev.api_responses)),
                               code_block(json.dumps(ev.api_responses, indent=2, ensure_ascii=False), "360px")))
        if ev.console_logs:
            ev_cards.append(acc("terminal", "Console Logs", str(len(ev.console_logs)),
                               code_block(json.dumps(ev.console_logs, indent=2, ensure_ascii=False), "300px")))
        if ev.dom:
            dom = ev.dom if len(ev.dom) <= 6000 else ev.dom[:6000] + "\n… (truncated)"
            ev_cards.append(acc("code", "DOM Snapshot", f"{len(ev.dom)} chars", code_block(dom, "360px")))
        if not ev_cards:
            ev_cards.append("<div class='empty'>No raw evidence signals were captured for this failure.</div>")

        evidence_sec = (
            "<section><h2 class='sec-h'><span class='si'>" + ic["search"] + "</span>Evidence</h2>"
            "<div class='searchbar'>" + ic["search"] +
            "<input id='searchEv' type='search' placeholder='Search evidence…' "
            "data-empty='#evEmpty' aria-label='Search evidence'></div>"
            + "".join(ev_cards)
            + "<div id='evEmpty' class='empty' style='display:none'>No evidence matches your search.</div></section>"
        )

        # ---- screenshots
        screenshots_sec = ""
        if ev.screenshot:
            src = esc(ev.screenshot)
            screenshots_sec = (
                "<section><h2 class='sec-h'><span class='si'>" + ic["camera"] + "</span>Screenshots</h2>"
                "<div class='shots'><div class='shot' data-shot='" + src + "' tabindex='0' role='button' "
                "aria-label='Open screenshot'><img src='" + src + "' alt='Failure screenshot' "
                "onerror=\"this.closest('.shot').style.display='none'\">"
                "<div class='cap'>Failure screenshot — click to enlarge</div></div></div></section>"
            )

        # ---- suggested fix (professional recommendation card)
        _best_practice = {
            "Authentication": "Use a dedicated test identity, load credentials from a secure vault, and assert a 200 login before any protected call.",
            "Authorization": "Seed the correct role/permissions in test data and assert 403 handling explicitly.",
            "Locator": "Prefer role-based or data-testid selectors over brittle CSS/XPath, and rely on framework auto-waiting.",
            "Network": "Apply timeout/retry budgets, stub unstable endpoints, and assert on response status codes.",
            "Backend": "Add contract tests and health checks; surface server error bodies in the evidence payload.",
            "API": "Validate schema and status codes, and isolate flaky upstreams behind stubs.",
            "Performance": "Set explicit performance budgets and isolate slow dependencies from the assertion path.",
            "Flaky Test": "Replace timing races with deterministic waits and remove shared mutable state.",
        }
        why = (
            f"Directly targets the {a.category.value.lower()} root cause: {a.root_cause}"
            if a.root_cause else f"Directly targets the {a.category.value.lower()} failure class."
        )
        prevent = f"Add a regression guard for this {a.category.value} scenario and alert when similar signals recur in future runs."
        best = _best_practice.get(
            a.category.value,
            "Add a targeted regression test and monitor recurrence via the failure-history store.",
        )
        fix_sec = (
            "<section><h2 class='sec-h'><span class='si'>" + ic["bulb"] + "</span>Suggested Fix</h2>"
            "<div class='card rec'><div class='rec-head'><span class='rec-ic'>" + ic["bulb"] + "</span>"
            "<div><h3>Recommended Fix</h3><p class='rec-primary'>"
            + esc(a.recommended_fix or "No specific fix recommended.") + "</p></div></div>"
            "<div class='rec-grid'>"
            "<div><b>Why this works</b><p>" + esc(why) + "</p></div>"
            "<div><b>Preventive actions</b><p>" + esc(prevent) + "</p></div>"
            "<div><b>Best practice</b><p>" + esc(best) + "</p></div>"
            "<div><b>Related</b><p><a href='https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer#readme' "
            "target='_blank' rel='noopener'>" + ic["link"] + "Failure analysis guide</a></p></div>"
            "</div></div></section>"
        )

        # ---- bug report (built from available data; no new analysis)
        actual = ev.exception_message or ev.assertion_message or a.root_cause or r.failure
        bug_title = f"[{sev_label}] {r.test_name} — {a.category.value}"
        bug_steps = [f"Execute test: {r.test_name}", "Observe the reported failure below"]
        bug_env = m.environment or ""
        bug_env_parts = [p for p in [m.browser, m.os, m.framework_version, (f"Python {m.python_version}" if m.python_version else "")] if p]
        bug_env_full = (bug_env + (" · " if bug_env and bug_env_parts else "") + " · ".join(bug_env_parts)).strip(" ·")
        bug_grid = (
            "<table class='kv'>"
            f"<tr><td>Title</td><td><b>{esc(bug_title)}</b></td></tr>"
            f"<tr><td>Severity</td><td><span class='pill' style='background:{sev_bg};color:{sev_color}'>{esc(sev_label)} · {esc(sev)}</span></td></tr>"
            f"<tr><td>Priority</td><td>{esc(priority)}</td></tr>"
            f"<tr><td>Owner</td><td>{esc(a.owner or 'Unassigned')}</td></tr>"
            f"<tr><td>Category</td><td>{esc(a.category.value)}</td></tr>"
            f"<tr><td>Environment</td><td>{esc(bug_env_full or 'n/a')}</td></tr>"
            f"<tr><td>Description</td><td>{esc(a.root_cause or r.failure)}</td></tr>"
            f"<tr><td>Expected</td><td>Test completes successfully with no errors.</td></tr>"
            f"<tr><td>Actual</td><td>{esc(actual)}</td></tr>"
            f"<tr><td>Steps</td><td>" + "<br>".join(f"{i+1}. {esc(s)}" for i, s in enumerate(bug_steps)) + "</td></tr>"
            f"<tr><td>Suggested Fix</td><td>{esc(a.recommended_fix)}</td></tr>"
            "</table>"
        )
        bug_sec = (
            "<section><h2 class='sec-h'><span class='si'>" + ic["bug"] + "</span>Bug Report"
            "<button class='btn' data-action='bug' type='button' style='margin-left:auto'>" + ic["copy"] +
            "Copy Bug Report</button></h2><div class='card'>" + bug_grid + "</div></section>"
        )

        # ---- similar failures table
        sim_rows = ""
        for s in a.similar_failures:
            name = esc(str(s.get("test_name", "?")))
            cat = esc(str(s.get("category", "?")))
            sim = int(s.get("similarity", 0) or 0)
            sconf = s.get("confidence")
            sconf_txt = f"{sconf}%" if sconf is not None else "—"
            sim_rows += (
                "<tr class='row'><td class='mono'>" + name + "</td>"
                "<td><div style='display:flex;align-items:center;gap:8px'><div class='simbar'>"
                f"<span style='width:{sim}%'></span></div>{sim}%</div></td>"
                f"<td>{cat}</td><td>{esc(sconf_txt)}</td></tr>"
                "<tr class='detail' style='display:none'><td colspan='4'>"
                f"Historical match: <b>{name}</b> was classified as <b>{cat}</b> with {sim}% similarity.</td></tr>"
            )
        similar_sec = ""
        if a.similar_failures:
            similar_sec = (
                "<section><h2 class='sec-h'><span class='si'>" + ic["history"] + "</span>Similar Failures</h2>"
                "<div class='searchbar'>" + ic["search"] +
                "<input id='searchSim' type='search' placeholder='Search similar failures…' aria-label='Search similar failures'></div>"
                "<div class='tbl-wrap'><table class='data'><thead><tr><th>Test</th><th>Similarity</th>"
                "<th>Category</th><th>Confidence</th></tr></thead><tbody id='simBody'>"
                + sim_rows + "</tbody></table></div></section>"
            )

        # ---- timeline
        tl_time = (r.timestamp or "").replace("T", " ")[:19]
        timeline_sec = (
            "<section><h2 class='sec-h'><span class='si'>" + ic["flow"] + "</span>Failure Timeline</h2>"
            "<div class='card timeline'>"
            "<div class='tl'><span class='dot'></span><div><h4>Test Started</h4><p>" + esc(r.test_name) + "</p></div></div>"
            "<div class='tl'><span class='dot'></span><div><h4>Execution</h4><p>" + esc(m.environment or "Test steps executed") + (f" · {exec_time}" if exec_time else "") + "</p></div></div>"
            "<div class='tl fail'><span class='dot'></span><div><h4>Failure Detected</h4><p>" + esc((ev.exception_type + ": " if ev.exception_type else "") + (actual or "")) + "</p></div></div>"
            "<div class='tl ai'><span class='dot'></span><div><h4>AI Analysis</h4><p>" + esc(a.category.value) + f" · {conf}% confidence · via " + esc(a.source) + "</p></div></div>"
            "<div class='tl done'><span class='dot'></span><div><h4>Report Generated</h4><p>" + esc(tl_time or "just now") + "</p></div></div>"
            "</div></section>"
        )

        # ---- charts (optional enhancement)
        ev_counts = {
            "Network": len(ev.network),
            "API": len(ev.api_responses),
            "Console": len(ev.console_logs),
            "Signals": len(a.evidence),
        }
        ev_counts = {k: v for k, v in ev_counts.items() if v}
        bar_chart = json.dumps({
            "type": "bar",
            "data": {"labels": list(ev_counts.keys()) or ["Signals"],
                     "datasets": [{"label": "Evidence", "data": list(ev_counts.values()) or [len(a.evidence)],
                                   "backgroundColor": ["#4c9be8", "#8b7ff0", "#3fb6a8", "#f0a35e"],
                                   "borderRadius": 8, "maxBarThickness": 46}]},
            "options": {"plugins": {"legend": {"display": False}}},
        })
        conf_chart = json.dumps({
            "type": "doughnut",
            "data": {"labels": ["Confidence", "Uncertainty"],
                     "datasets": [{"data": [conf, 100 - conf],
                                   "backgroundColor": [conf_color, "rgba(140,148,158,.18)"],
                                   "borderWidth": 0, "hoverOffset": 4}]},
            "options": {"cutout": "74%"},
        })
        stats_rows = (
            f"<tr><td>Severity</td><td><b style='color:{sev_color}'>{esc(sev_label)}</b> · {esc(sev)}</td></tr>"
            f"<tr><td>Priority</td><td>{esc(priority)}</td></tr>"
            f"<tr><td>Category</td><td>{esc(a.category.value)}</td></tr>"
            f"<tr><td>Evidence signals</td><td>{len(a.evidence)}</td></tr>"
            f"<tr><td>Similar failures</td><td>{len(a.similar_failures)}</td></tr>"
        )
        charts_sec = (
            "<section data-chartsec><h2 class='sec-h'><span class='si'>" + ic["gauge"] + "</span>Insights</h2>"
            "<div class='kpis'>"
            "<div class='card' style='border-left:4px solid #4c9be8'><div class='k-top'>" + ic["search"] +
            "Evidence Distribution</div><div class='chartbox'><canvas data-chart='" + esc(bar_chart) + "'></canvas></div></div>"
            "<div class='card' style='border-left:4px solid " + conf_color + "'><div class='k-top'>" + ic["gauge"] +
            "Confidence Gauge</div><div class='chartbox'><canvas data-chart='" + esc(conf_chart) + "'></canvas></div></div>"
            "<div class='card' style='border-left:4px solid #8250df'><div class='k-top'>" + ic["tag"] +
            "Summary</div><table class='kv' style='margin-top:6px'>" + stats_rows + "</table></div>"
            "</div></section>"
        )

        # ---- sidebar (metadata)
        def mrow(label: str, value: str) -> str:
            if not value:
                return ""
            return f"<div class='meta-row'><span class='l'>{esc(label)}</span><span class='v'>{esc(value)}</span></div>"

        sidebar = (
            "<aside class='side'>"
            "<div class='card'><h3>" + ic["chip"] + "Execution Metadata</h3>"
            + mrow("Framework", m.framework_version)
            + mrow("Browser", m.browser)
            + mrow("Environment", m.environment)
            + mrow("Operating System", m.os)
            + mrow("Python", m.python_version)
            + mrow("Package", f"v{pkg}")
            + mrow("Commit", commit)
            + mrow("Execution Time", exec_time)
            + mrow("Timestamp", tl_time)
            + mrow("Record ID", (r.record_id or "")[:18])
            + "</div>"
            "<div class='card'><h3>" + ic["gauge"] + "Confidence</h3>"
            "<div style='display:grid;place-items:center;padding:6px 0'>" + ring + "</div></div>"
            "</aside>"
        )

        # ---- data island for export / copy
        data_payload = {
            "record": r.to_dict(),
            "analysis": a.to_dict(),
            "markdown": self.to_markdown(r, a),
            "bugReport": self._bug_markdown(bug_title, a, r, actual, bug_env_full, priority, sev_label, bug_steps),
            "stem": f"{stem}_analysis",
        }
        data_json = json.dumps(data_payload, ensure_ascii=False).replace("<", "\\u003c")

        toolbar = (
            "<div class='toolbar'>"
            "<button class='btn' data-action='html' type='button'>" + ic["download"] + "HTML</button>"
            "<button class='btn' data-action='json' type='button'>" + ic["code"] + "JSON</button>"
            "<button class='btn' data-action='md' type='button'>" + ic["doc"] + "Markdown</button>"
            "<button class='btn' data-action='print' type='button'>" + ic["print"] + "Print</button>"
            "<button class='btn icon theme-t' id='themeBtn' data-action='theme' type='button' "
            "aria-label='Toggle theme'>" + ic["moon"] + "</button>"
            "</div>"
        )

        header = (
            "<header class='top'><div class='top-in'><div class='top-row'>"
            "<div class='brand'><span class='ic'>" + ic["robot"] + "</span>AI Failure Analysis</div>"
            "<span class='badge fail'>" + ic["warning"] + "FAILED</span>"
            "<div class='spacer'></div>" + toolbar + "</div>"
            f"<div class='chips'>{chips}</div></div></header>"
        )

        body = (
            "<div class='wrap'>"
            "<section><div class='kpis'>" + kpis + "</div></section>"
            + root_cause
            + charts_sec
            + "<div class='grid'><div>"
            + evidence_sec + screenshots_sec + fix_sec + bug_sec + similar_sec + timeline_sec
            + "</div>" + sidebar + "</div>"
            "<footer><div class='fl'>" + ic["robot"] +
            "Generated by <b>&nbsp;multi-framework-tc-failure-ai-analyzer</b>&nbsp;· v" + esc(pkg) +
            "&nbsp;· " + esc(tl_time) + "</div><div class='fl'>"
            "<a href='https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer' target='_blank' rel='noopener'>" + ic["git"] + "GitHub</a>"
            "<a href='https://pypi.org/project/multi-framework-tc-failure-ai-analyzer/' target='_blank' rel='noopener'>" + ic["doc"] + "PyPI</a>"
            "</div></footer></div>"
        )

        return (
            "<!DOCTYPE html><html lang='en' data-theme='light'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>AI Failure Analysis — {esc(r.test_name)}</title>"
            "<link rel='preconnect' href='https://fonts.googleapis.com'>"
            "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap' rel='stylesheet'>"
            f"<style>{_REPORT_CSS}</style></head><body data-stem='{esc(stem)}_analysis'>"
            + header + body
            + "<div class='modal' id='modal' role='dialog' aria-modal='true'>"
            "<button class='x' aria-label='Close'>&times;</button><img src='' alt='Screenshot'></div>"
            "<div class='toast' id='toast' role='status' aria-live='polite'></div>"
            f"<script id='ai-data' type='application/json'>{data_json}</script>"
            f"<script>{_REPORT_JS}</script></body></html>"
        )

    @staticmethod
    def _bug_markdown(
        title: str, a: AnalysisResult, r: FailureRecord, actual: str,
        env: str, priority: str, sev_label: str, steps: list[str],
    ) -> str:
        step_lines = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
        return (
            f"# {title}\n\n"
            f"**Severity:** {sev_label} ({a.severity.value})  \n"
            f"**Priority:** {priority}  \n"
            f"**Owner:** {a.owner or 'Unassigned'}  \n"
            f"**Category:** {a.category.value}  \n"
            f"**Environment:** {env or 'n/a'}\n\n"
            f"## Description\n{a.root_cause or r.failure}\n\n"
            f"## Steps to Reproduce\n{step_lines}\n\n"
            f"## Expected\nTest completes successfully with no errors.\n\n"
            f"## Actual\n{actual}\n\n"
            f"## Suggested Fix\n{a.recommended_fix}\n"
        )

    def save(self, record: FailureRecord, analysis: AnalysisResult, stem: str) -> dict[str, Path]:
        self.cfg.reports_dir.mkdir(parents=True, exist_ok=True)
        variants = {
            "md": self.to_markdown(record, analysis),
            "json": json.dumps(
                {"record": record.to_dict(), "analysis": analysis.to_dict()},
                indent=2,
                ensure_ascii=False,
            ),
            "html": self.to_html_document(record, analysis, stem),
        }
        paths: dict[str, Path] = {}
        for ext, content in variants.items():
            path = self.cfg.reports_dir / f"{stem}_analysis.{ext}"
            try:
                path.write_text(content, encoding="utf-8")
                paths[ext] = path
            except OSError as exc:  # pragma: no cover
                logger.warning("Could not write analysis report %s: %s", path, exc)
        return paths

    # ---------------------------------------------------------- trend / release
    def trend_markdown(self, trend: TrendReport, readiness: ReleaseReadiness) -> str:
        def _rows(items: list[dict[str, Any]], key: str, count_key: str = "count") -> str:
            return "\n".join(f"- {i.get(key)} — {i.get(count_key)}" for i in items) or "- (none)"

        categories = "\n".join(f"- {k}: {v}" for k, v in trend.category_distribution.items()) or "- (none)"
        flaky = "\n".join(f"- {f.get('test')} ({f.get('confidence')}%)" for f in trend.flaky_tests) or "- (none)"
        return (
            "# AI Quality Trend & Release Readiness\n\n"
            f"## Release Readiness\n"
            f"- **Score:** {readiness.score}/100\n"
            f"- **Risk:** {readiness.risk}\n"
            f"- **Recommendation:** {readiness.recommendation}\n"
            + "".join(f"  - {r}\n" for r in readiness.rationale)
            + f"\n## Summary\n- Total failures analysed: {trend.total_failures}\n"
            f"- Average runtime: {trend.average_runtime_s or 'n/a'} s\n\n"
            f"## Failure Categories\n{categories}\n\n"
            f"## Most Common Failures\n{_rows(trend.most_common_failures, 'test')}\n\n"
            f"## Most Failing APIs\n{_rows(trend.most_failing_apis, 'endpoint')}\n\n"
            f"## Most Failing Widgets\n{_rows(trend.most_failing_widgets, 'widget')}\n\n"
            f"## Flaky Tests\n{flaky}\n\n"
            f"## Failure Trend (by day)\n"
            + ("\n".join(f"- {day}: {n}" for day, n in trend.failure_trend.items()) or "- (none)")
            + "\n"
        )

    def save_trend(self, trend: TrendReport, readiness: ReleaseReadiness, stem: str = "trend") -> dict[str, Path]:
        self.cfg.reports_dir.mkdir(parents=True, exist_ok=True)
        variants = {
            "md": self.trend_markdown(trend, readiness),
            "json": json.dumps(
                {"trend": trend.to_dict(), "release_readiness": readiness.to_dict()},
                indent=2,
                ensure_ascii=False,
            ),
        }
        paths: dict[str, Path] = {}
        for ext, content in variants.items():
            path = self.cfg.reports_dir / f"{stem}.{ext}"
            try:
                path.write_text(content, encoding="utf-8")
                paths[ext] = path
            except OSError as exc:  # pragma: no cover
                logger.warning("Could not write trend report %s: %s", path, exc)
        return paths
