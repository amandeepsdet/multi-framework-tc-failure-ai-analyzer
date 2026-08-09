"""AI execution report rendering (Markdown / JSON / HTML).

Produces the per-failure analysis report written to ``ai_reports/`` and the
HTML fragment embedded into the pytest-html report / attached to Allure. Also
renders the aggregate trend + release-readiness report.
"""

from __future__ import annotations

import html
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
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
    return "3.2.0"


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
            f"## Most Failing Components\n{_rows(trend.most_failing_components, 'component')}\n\n"
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


# =========================================================================== #
#  Consolidated per-execution AI dashboard                                     #
#                                                                              #
#  ONE run  ->  ONE report  ->  many failed test cases, each with its own AI   #
#  analysis. Presentation only: consumes the same FailureRecord /              #
#  AnalysisResult produced by the (unchanged) analysis engine.                 #
# =========================================================================== #

_DASHBOARD_FILE_STEM = "ai_failure_analysis"


def _git_commit() -> str:
    """Best-effort short git SHA for the run (never raises)."""
    env = os.getenv("GIT_COMMIT") or os.getenv("GITHUB_SHA") or os.getenv("CI_COMMIT_SHA")
    if env:
        return env[:10]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3, cwd=str(Path.cwd()),
        )
        if out.returncode == 0:
            return out.stdout.strip()[:10]
    except Exception:  # noqa: BLE001  # pragma: no cover
        pass
    return ""


# Dashboard-specific layout on top of the shared _REPORT_CSS component styles.
_DASHBOARD_CSS = """
.dash-shell{display:grid;grid-template-columns:308px minmax(0,1fr);gap:24px;align-items:start;max-width:1560px;margin:0 auto;padding:22px 24px 64px}
@media(max-width:1080px){.dash-shell{grid-template-columns:1fr}}
.dash-side{position:sticky;top:78px;display:flex;flex-direction:column;gap:14px;max-height:calc(100vh - 96px)}
@media(max-width:1080px){.dash-side{position:static;max-height:none}}
.dash-side .card{padding:13px 14px}
.side-title{display:flex;align-items:center;gap:8px;margin:0 0 10px;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.side-title svg{width:15px;height:15px}
.navlist{display:flex;flex-direction:column;gap:4px;overflow:auto;max-height:52vh;padding-right:2px}
.nav-item{display:grid;grid-template-columns:auto 1fr auto;gap:9px;align-items:center;padding:8px 9px;border-radius:9px;border:1px solid transparent;cursor:pointer;color:var(--text);text-decoration:none;transition:.14s}
.nav-item:hover{background:var(--accent-soft);border-color:var(--border);text-decoration:none}
.nav-item .st{width:9px;height:9px;border-radius:50%;flex:none}
.nav-item .nm{font-size:12.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nav-item .sub{grid-column:2;font-size:11px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nav-item .cf{font-size:11px;font-weight:800;font-family:var(--mono)}
.nav-empty{color:var(--muted);font-size:12.5px;padding:8px 4px}
.side-filter{display:flex;flex-direction:column;gap:9px}
.side-filter label{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;display:block;margin-bottom:3px}
.side-filter select,.side-filter input{width:100%;padding:7px 9px;border:1px solid var(--border);border-radius:8px;background:var(--panel);color:var(--text);font:inherit;font-size:12.5px}
.side-filter select:focus,.side-filter input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
/* main */
.dash-main{min-width:0;display:flex;flex-direction:column;gap:22px}
.exec-head{background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 10%,var(--panel)),var(--panel));border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:18px 20px}
.exec-head h1{margin:0;font-size:20px;letter-spacing:-.02em;display:flex;align-items:center;gap:10px}
.exec-head h1 .ic{width:32px;height:32px;display:grid;place-items:center;border-radius:9px;background:linear-gradient(135deg,#0969da,#8250df);color:#fff}
.exec-sub{color:var(--muted);font-size:13px;margin:6px 0 0}
.summary-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px 18px;margin-top:15px;padding-top:14px;border-top:1px solid var(--border-soft)}
.summary-grid .s-cell b{display:block;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:3px}
.summary-grid .s-cell span{font-size:13px;font-weight:600;word-break:break-word;font-family:var(--mono)}
.toc{display:flex;flex-wrap:wrap;gap:8px}
.toc a{display:inline-flex;align-items:center;gap:6px;padding:6px 11px;border:1px solid var(--border);border-radius:999px;background:var(--panel);font-size:12.5px;font-weight:600;color:var(--text)}
.toc a:hover{border-color:var(--red);color:var(--red);text-decoration:none;transform:translateY(-1px)}
.toc a .st{width:8px;height:8px;border-radius:50%}
.controls{display:flex;flex-wrap:wrap;gap:9px;align-items:center}
.controls .searchbar{margin:0;max-width:none;flex:1;min-width:220px}
/* failure section */
.fsec{background:var(--panel);border:1px solid var(--border);border-left:5px solid var(--sev,#cf222e);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;scroll-margin-top:78px}
.fsec>summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;padding:15px 18px;user-select:none}
.fsec>summary::-webkit-details-marker{display:none}
.fsec>summary .fx{width:34px;height:34px;flex:none;display:grid;place-items:center;border-radius:9px;background:var(--red-bg);color:var(--red)}
.fsec>summary .ft{min-width:0}
.fsec>summary .ft h3{margin:0;font-size:15px;letter-spacing:-.01em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fsec>summary .ft .fmeta{margin:5px 0 0;color:var(--muted);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fsec>summary .fbadges{display:flex;align-items:center;gap:7px;flex-wrap:wrap;justify-content:flex-end}
.fsec>summary .chev{transition:.2s;color:var(--muted)}
.fsec[open]>summary .chev{transform:rotate(90deg)}
.fsec-body{padding:0 18px 18px;border-top:1px solid var(--border-soft);display:grid;gap:18px;animation:slide .25s ease}
.fsec-body .sec-h{margin:16px 0 10px}
.fgrid{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px;align-items:start}
@media(max-width:820px){.fgrid{grid-template-columns:1fr}}
.fac{display:flex;gap:7px;flex-wrap:wrap}
.gallery-nav{position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.14);border:0;color:#fff;font-size:24px;padding:10px 16px;border-radius:10px;cursor:pointer;z-index:2}
.gallery-nav.prev{left:18px}.gallery-nav.next{right:18px}
.gallery-zoom{position:absolute;bottom:18px;left:50%;transform:translateX(-50%);display:flex;gap:8px;z-index:2}
.gallery-zoom button{background:rgba(255,255,255,.14);border:0;color:#fff;padding:8px 14px;border-radius:9px;cursor:pointer;font-size:13px;font-weight:600}
.modal img{transition:transform .18s ease}
.no-fail{background:var(--green-bg);border:1px solid color-mix(in srgb,var(--green) 30%,transparent);color:var(--green);border-radius:var(--radius);padding:26px;text-align:center;font-weight:700;font-size:16px;display:flex;align-items:center;justify-content:center;gap:10px}
.hidden{display:none!important}
.count-pill{background:var(--panel-2);border:1px solid var(--border);border-radius:999px;padding:1px 9px;font-size:11px;font-weight:800;color:var(--muted)}
"""

_DASHBOARD_JS = r"""
(function(){
  var data={};
  try{data=JSON.parse(document.getElementById('ai-data').textContent);}catch(e){}
  var root=document.documentElement;
  var saved=null;try{saved=localStorage.getItem('aiqa-theme');}catch(e){}
  if(saved){root.setAttribute('data-theme',saved);}
  function toggleTheme(){var d=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',d);try{localStorage.setItem('aiqa-theme',d);}catch(e){}drawCharts();}
  var toast=document.getElementById('toast'),tt;
  function say(m){if(!toast)return;toast.textContent=m;toast.classList.add('on');clearTimeout(tt);tt=setTimeout(function(){toast.classList.remove('on');},1700);}
  function copyText(t,msg){t=t||'';if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(function(){say(msg||'Copied');},function(){fb(t);say(msg||'Copied');});}else{fb(t);say(msg||'Copied');}}
  function fb(t){var ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();try{document.execCommand('copy');}catch(e){}document.body.removeChild(ta);}
  function dl(name,content,type){var b=new Blob([content],{type:type});var u=URL.createObjectURL(b);var a=document.createElement('a');a.href=u;a.download=name;document.body.appendChild(a);a.click();document.body.removeChild(a);setTimeout(function(){URL.revokeObjectURL(u);},1000);say('Downloaded '+name);}
  function fail(id){return (data.failures&&data.failures[id])||{};}

  document.addEventListener('click',function(e){
    var c=e.target.closest('[data-copy]');
    if(c){e.preventDefault();e.stopPropagation();var sel=c.getAttribute('data-copy');var el=sel?document.querySelector(sel):null;copyText(el?el.innerText:c.getAttribute('data-copytext')||'','Copied to clipboard');return;}
    var t=e.target.closest('[data-action]');
    if(t){e.preventDefault();var a=t.getAttribute('data-action');
      if(a==='theme')toggleTheme();
      else if(a==='print')window.print();
      else if(a==='json')dl(data.stem+'.json',JSON.stringify(data.raw||{},null,2),'application/json');
      else if(a==='md')dl(data.stem+'.md',data.markdown||'','text/markdown');
      else if(a==='html')dl(data.stem+'.html','<!DOCTYPE html>\n'+document.documentElement.outerHTML,'text/html');
      else if(a==='expandAll')document.querySelectorAll('details.fsec').forEach(function(d){d.open=true;});
      else if(a==='collapseAll')document.querySelectorAll('details.fsec').forEach(function(d){d.open=false;});
      return;
    }
    var fb2=e.target.closest('[data-fail]');
    if(fb2){e.preventDefault();e.stopPropagation();var id=fb2.getAttribute('data-fail');var fmt=fb2.getAttribute('data-fmt');var f=fail(id);
      if(fmt==='copybug')copyText(f.bug||'','Bug report copied');
      else if(fmt==='md')dl((f.slug||id)+'_bug.md',f.bug||f.markdown||'','text/markdown');
      else if(fmt==='json')dl((f.slug||id)+'.json',JSON.stringify(f.json||{},null,2),'application/json');
      else if(fmt==='export')dl((f.slug||id)+'.json',JSON.stringify(f.json||{},null,2),'application/json');
      return;
    }
    var nav=e.target.closest('.nav-item,.toc a');
    if(nav&&nav.getAttribute('data-target')){e.preventDefault();var tgt=document.querySelector(nav.getAttribute('data-target'));if(tgt){tgt.open=true;tgt.scrollIntoView({behavior:'smooth',block:'start'});}return;}
    var shot=e.target.closest('[data-gallery]');
    if(shot){openGallery(shot.getAttribute('data-gallery'),parseInt(shot.getAttribute('data-idx')||'0',10));}
  });

  // ---- gallery modal (prev / next / zoom) ----
  var modal=document.getElementById('modal'),gImg=modal?modal.querySelector('img'):null,gList=[],gIdx=0,gZoom=1;
  function renderShot(){if(!gImg||!gList.length)return;gZoom=1;gImg.style.transform='scale(1)';gImg.src=gList[gIdx];}
  function openGallery(gid,idx){if(!modal)return;gList=(data.galleries&&data.galleries[gid])||[];if(!gList.length)return;gIdx=Math.max(0,Math.min(idx,gList.length-1));renderShot();modal.classList.add('on');}
  if(modal){
    modal.addEventListener('click',function(e){if(e.target===modal||e.target.classList.contains('x'))modal.classList.remove('on');});
    var pv=modal.querySelector('.prev'),nx=modal.querySelector('.next'),zi=modal.querySelector('[data-zoom="in"]'),zo=modal.querySelector('[data-zoom="out"]');
    if(pv)pv.addEventListener('click',function(e){e.stopPropagation();gIdx=(gIdx-1+gList.length)%gList.length;renderShot();});
    if(nx)nx.addEventListener('click',function(e){e.stopPropagation();gIdx=(gIdx+1)%gList.length;renderShot();});
    if(zi)zi.addEventListener('click',function(e){e.stopPropagation();gZoom=Math.min(gZoom+0.25,4);gImg.style.transform='scale('+gZoom+')';});
    if(zo)zo.addEventListener('click',function(e){e.stopPropagation();gZoom=Math.max(gZoom-0.25,0.5);gImg.style.transform='scale('+gZoom+')';});
  }
  document.addEventListener('keydown',function(e){if(!modal||!modal.classList.contains('on'))return;if(e.key==='Escape')modal.classList.remove('on');else if(e.key==='ArrowLeft'){gIdx=(gIdx-1+gList.length)%gList.length;renderShot();}else if(e.key==='ArrowRight'){gIdx=(gIdx+1)%gList.length;renderShot();}});

  // ---- per-section evidence search ----
  document.querySelectorAll('input[data-evsearch]').forEach(function(inp){
    inp.addEventListener('input',function(){var q=inp.value.toLowerCase();var scope=document.querySelector(inp.getAttribute('data-evsearch'));if(!scope)return;var vis=0;scope.querySelectorAll('.ev').forEach(function(it){var ok=it.textContent.toLowerCase().indexOf(q)>-1;it.style.display=ok?'':'none';if(ok)vis++;});});
  });

  // ---- global search + filters ----
  var q=document.getElementById('dashSearch');
  var sels=['fSeverity','fCategory','fOwner','fFramework','fConfidence','fStatus'].map(function(i){return document.getElementById(i);});
  function bucket(c){c=+c||0;return c>=85?'high':(c>=60?'medium':'low');}
  function applyFilters(){
    var term=(q&&q.value||'').toLowerCase();
    var fv={};sels.forEach(function(s){if(s)fv[s.id]=s.value;});
    var shown=0;
    document.querySelectorAll('details.fsec').forEach(function(d){
      var ok=true;
      if(term&&d.textContent.toLowerCase().indexOf(term)<0)ok=false;
      if(ok&&fv.fSeverity&&d.getAttribute('data-sev')!==fv.fSeverity)ok=false;
      if(ok&&fv.fCategory&&d.getAttribute('data-cat')!==fv.fCategory)ok=false;
      if(ok&&fv.fOwner&&d.getAttribute('data-owner')!==fv.fOwner)ok=false;
      if(ok&&fv.fFramework&&d.getAttribute('data-fw')!==fv.fFramework)ok=false;
      if(ok&&fv.fConfidence&&d.getAttribute('data-confbucket')!==fv.fConfidence)ok=false;
      if(ok&&fv.fStatus&&d.getAttribute('data-status')!==fv.fStatus)ok=false;
      d.classList.toggle('hidden',!ok);
      var fid=d.id;
      document.querySelectorAll('[data-fid="'+fid+'"]').forEach(function(x){x.classList.toggle('hidden',!ok);});
      if(ok)shown++;
    });
    var em=document.getElementById('noMatch');if(em)em.classList.toggle('hidden',shown>0||!document.querySelector('details.fsec'));
  }
  if(q)q.addEventListener('input',applyFilters);
  sels.forEach(function(s){if(s)s.addEventListener('change',applyFilters);});

  // ---- confidence rings ----
  document.querySelectorAll('.ring .fg').forEach(function(ring){var v=parseFloat(ring.getAttribute('data-v'))||0;var C=326.7;requestAnimationFrame(function(){setTimeout(function(){ring.style.strokeDashoffset=(C-C*v/100).toFixed(1);},120);});});

  // ---- charts ----
  var charts=[];
  function css(n){return getComputedStyle(root).getPropertyValue(n).trim();}
  function drawCharts(){
    if(typeof Chart==='undefined')return;
    Chart.defaults.font.family="'Inter','Segoe UI',sans-serif";Chart.defaults.font.size=11;
    charts.forEach(function(c){c.destroy();});charts=[];
    document.querySelectorAll('canvas[data-chart]').forEach(function(cv){
      var cfg;try{cfg=JSON.parse(cv.getAttribute('data-chart'));}catch(e){return;}
      var grid=css('--border-soft')||'#e6eaef',txt=css('--muted')||'#57606a';
      cfg.options=cfg.options||{};cfg.options.plugins=cfg.options.plugins||{};
      if(cfg.type!=='doughnut'){cfg.options.scales={x:{ticks:{color:txt},grid:{display:false}},y:{ticks:{color:txt,precision:0},grid:{color:grid},border:{display:false},beginAtZero:true}};}
      cfg.options.plugins.legend=cfg.type==='doughnut'?{labels:{color:txt,boxWidth:10,usePointStyle:true,font:{size:11}},position:'bottom'}:{display:false};
      cfg.options.plugins.tooltip={backgroundColor:'#1f2328',padding:10,cornerRadius:8,displayColors:true,boxPadding:4};
      cfg.options.responsive=true;cfg.options.maintainAspectRatio=false;cfg.options.animation={duration:650};
      try{charts.push(new Chart(cv,cfg));}catch(e){}
    });
  }
  if(typeof Chart!=='undefined'){drawCharts();}else{
    var s=document.createElement('script');s.src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
    s.onload=drawCharts;s.onerror=function(){document.querySelectorAll('[data-chartsec]').forEach(function(x){x.style.display='none';});};document.head.appendChild(s);
  }
})();
"""


class _ExecFailure:
    """Lightweight holder for one analysed failure within an execution."""

    __slots__ = ("nodeid", "record", "analysis", "bug_markdown")

    def __init__(self, nodeid: str, record: FailureRecord, analysis: AnalysisResult, bug_markdown: str = "") -> None:
        self.nodeid = nodeid
        self.record = record
        self.analysis = analysis
        self.bug_markdown = bug_markdown


class ExecutionReportBuilder:
    """Accumulate every result of a single run and render ONE consolidated report.

    Lifecycle::

        begin()  ->  add_failure()/add_success()/add_skipped()  ->  finish()

    ``finish`` writes ``reports/ai_failure_analysis.{html,json,md}`` exactly once
    (idempotent), so it is safe even if multiple pytest hook sites call it.
    Presentation only — no new analysis is performed here.
    """

    def __init__(self, cfg: AIConfig = ai_config, report_gen: "ReportGenerator | None" = None) -> None:
        self.cfg = cfg
        self.report_gen = report_gen or ReportGenerator(cfg)
        self._reset()

    # ----------------------------------------------------------- lifecycle
    def _reset(self) -> None:
        self.failures: list[_ExecFailure] = []
        self.passed: list[str] = []
        self.skipped: list[str] = []
        self._seen: set[str] = set()
        self.start_ts: datetime | None = None
        self.finish_ts: datetime | None = None
        self.run_name: str = ""
        self.env: dict[str, str] = {}
        self._finished: bool = False
        self._paths: dict[str, Path] = {}

    def begin(self, *, run_name: str = "", environment: str = "") -> None:
        self._reset()
        self.start_ts = datetime.now(timezone.utc)
        stamp = self.start_ts.strftime("%Y-%m-%d %H:%M:%S UTC")
        self.run_name = run_name or f"Test Execution — {stamp}"
        self.env = self._collect_env(environment)

    def add_failure(
        self, record: FailureRecord, analysis: AnalysisResult, *, nodeid: str = "", bug_markdown: str = ""
    ) -> None:
        key = nodeid or record.test_name
        if key in self._seen:
            return
        self._seen.add(key)
        self.failures.append(_ExecFailure(key, record, analysis, bug_markdown))

    def add_success(self, nodeid: str) -> None:
        if nodeid in self._seen:
            return
        self._seen.add(nodeid)
        self.passed.append(nodeid)

    def add_skipped(self, nodeid: str) -> None:
        if nodeid in self._seen:
            return
        self._seen.add(nodeid)
        self.skipped.append(nodeid)

    def finish(self) -> dict[str, Path]:
        if self._finished:
            return self._paths
        self.finish_ts = datetime.now(timezone.utc)
        self._finished = True
        self._paths = self._render()
        return self._paths

    @property
    def has_data(self) -> bool:
        return bool(self._seen)

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _collect_env(environment: str) -> dict[str, str]:
        return {
            "framework": "multi-framework-tc-failure-ai-analyzer",
            "environment": environment or os.getenv("TEST_ENV", "") or os.getenv("ENVIRONMENT", "") or "local",
            "os": platform.platform(),
            "python": platform.python_version(),
            "package": _package_version(),
            "commit": _git_commit(),
        }

    def _duration_s(self) -> float:
        if self.start_ts and self.finish_ts:
            return max(0.0, (self.finish_ts - self.start_ts).total_seconds())
        return 0.0

    def _browser(self) -> str:
        for f in self.failures:
            if f.record.metadata.browser:
                return f.record.metadata.browser
        return ""

    def _counts(self) -> dict[str, Any]:
        total = len(self._seen)
        failed = len(self.failures)
        passed = len(self.passed)
        skipped = len(self.skipped)
        sev_count = {"Blocker": 0, "Critical": 0, "Major": 0, "Minor": 0, "Trivial": 0}
        confs: list[int] = []
        cats: set[str] = set()
        owners: set[str] = set()
        for f in self.failures:
            sev_count[f.analysis.severity.value] = sev_count.get(f.analysis.severity.value, 0) + 1
            confs.append(int(f.analysis.confidence))
            cats.add(f.analysis.category.value)
            if f.analysis.owner:
                owners.add(f.analysis.owner)
        avg_conf = round(sum(confs) / len(confs)) if confs else 0
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": round((passed / total) * 100) if total else 100,
            "critical": sev_count["Blocker"] + sev_count["Critical"],
            "high": sev_count["Major"],
            "medium": sev_count["Minor"],
            "low": sev_count["Trivial"],
            "avg_confidence": avg_conf,
            "unique_categories": len(cats),
            "unique_owners": len(owners),
            "severity_breakdown": sev_count,
        }

    @staticmethod
    def _slug(text: str, n: int = 60) -> str:
        return ("".join(c if c.isalnum() else "_" for c in (text or "test")).strip("_"))[:n] or "test"

    # -------------------------------------------------------------- render
    def _render(self) -> dict[str, Path]:
        self.cfg.dashboard_dir.mkdir(parents=True, exist_ok=True)
        html_doc, payload = self._render_html()
        variants = {
            "html": html_doc,
            "json": json.dumps(payload, indent=2, ensure_ascii=False),
            "md": self._render_markdown(),
        }
        paths: dict[str, Path] = {}
        for ext, content in variants.items():
            path = self.cfg.dashboard_dir / f"{_DASHBOARD_FILE_STEM}.{ext}"
            try:
                path.write_text(content, encoding="utf-8")
                paths[ext] = path
            except OSError as exc:  # pragma: no cover
                logger.warning("Could not write consolidated report %s: %s", path, exc)
        logger.info(
            "Consolidated AI report written to %s (%d failed / %d total)",
            paths.get("html", self.cfg.dashboard_dir),
            len(self.failures),
            len(self._seen),
        )
        return paths

    def _render_markdown(self) -> str:
        c = self._counts()
        gen = (self.finish_ts or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            f"# AI Failure Analysis — {self.run_name}",
            "",
            "## Execution Summary",
            f"- **Framework:** {self.env.get('framework')}",
            f"- **Environment:** {self.env.get('environment')}",
            f"- **Browser:** {self._browser() or 'n/a'}",
            f"- **OS:** {self.env.get('os')}",
            f"- **Python:** {self.env.get('python')}",
            f"- **Package Version:** v{self.env.get('package')}",
            f"- **Commit:** {self.env.get('commit') or 'n/a'}",
            f"- **Total Tests:** {c['total']}",
            f"- **Passed:** {c['passed']}",
            f"- **Failed:** {c['failed']}",
            f"- **Skipped:** {c['skipped']}",
            f"- **Pass Rate:** {c['pass_rate']}%",
            f"- **Execution Duration:** {self._duration_s():.2f}s",
            f"- **Average Confidence:** {c['avg_confidence']}%",
            f"- **Generation Time:** {gen}",
            "",
        ]
        if not self.failures:
            lines.append("_No failures analysed — all tests passed._")
            return "\n".join(lines)
        lines.append("## Failed Tests")
        lines.append("")
        for i, f in enumerate(self.failures, 1):
            lines.append(f"{i}. ❌ **{f.record.test_name}** — {f.analysis.category.value} "
                         f"({f.analysis.severity.value}, {f.analysis.confidence}%)")
        lines.append("")
        for f in self.failures:
            lines.append("---")
            lines.append("")
            lines.append(self.report_gen.to_markdown(f.record, f.analysis))
            lines.append("")
        return "\n".join(lines)

    # ---- HTML ----
    def _render_html(self) -> tuple[str, dict[str, Any]]:
        esc = html.escape
        ic = _ICONS
        c = self._counts()
        gen = (self.finish_ts or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S UTC")
        pkg = self.env.get("package", _package_version())

        # ---------- header + execution summary ----------
        def scell(label: str, value: str) -> str:
            return f"<div class='s-cell'><b>{esc(label)}</b><span>{esc(value or 'n/a')}</span></div>"

        summary_cells = "".join([
            scell("Run Name", self.run_name),
            scell("Framework", self.env.get("framework", "")),
            scell("Environment", self.env.get("environment", "")),
            scell("Browser", self._browser()),
            scell("Operating System", self.env.get("os", "")),
            scell("Python", self.env.get("python", "")),
            scell("Package", f"v{pkg}"),
            scell("Commit", self.env.get("commit", "")),
            scell("Total Tests", str(c["total"])),
            scell("Passed", str(c["passed"])),
            scell("Failed", str(c["failed"])),
            scell("Skipped", str(c["skipped"])),
            scell("Pass Rate", f"{c['pass_rate']}%"),
            scell("Execution Duration", f"{self._duration_s():.2f}s"),
            scell("AI Engine", self.cfg.provider),
            scell("Generation Time", gen),
        ])
        exec_head = (
            "<div class='exec-head'><h1><span class='ic'>" + ic["robot"] + "</span>"
            + esc(self.run_name) + "</h1>"
            "<p class='exec-sub'>Consolidated AI failure-analysis dashboard for this test execution — "
            "one report covering every failed test case.</p>"
            "<div class='summary-grid'>" + summary_cells + "</div></div>"
        )

        # ---------- KPI dashboard ----------
        def kpi(icon_key: str, label: str, value: str, desc: str, color: str) -> str:
            return (
                f"<div class='kpi' style='border-left-color:{color}'>"
                f"<div class='k-top'>{ic.get(icon_key, '')}{esc(label)}</div>"
                f"<div class='k-val' style='color:{color}'>{esc(value)}</div>"
                f"<div class='k-desc'>{esc(desc)}</div></div>"
            )

        kpis = "".join([
            kpi("chip", "Total Tests", str(c["total"]), "Executed this run", "#0969da"),
            kpi("check", "Passed", str(c["passed"]), f"{c['pass_rate']}% pass rate", "#1a7f37"),
            kpi("warning", "Failed", str(c["failed"]), "Analysed by AI", "#cf222e"),
            kpi("clock", "Skipped", str(c["skipped"]), "Not executed", "#8b949e"),
            kpi("warning", "Critical Failures", str(c["critical"]), "Blocker + Critical", "#b30000"),
            kpi("warning", "High", str(c["high"]), "Major severity", "#bc4c00"),
            kpi("warning", "Medium", str(c["medium"]), "Minor severity", "#9a6700"),
            kpi("warning", "Low", str(c["low"]), "Trivial severity", "#0969da"),
            kpi("gauge", "Avg Confidence", f"{c['avg_confidence']}%", "Across failures", "#8250df"),
            kpi("tag", "Categories", str(c["unique_categories"]), "Distinct root causes", "#bc4c00"),
            kpi("user", "Owners", str(c["unique_owners"]), "Teams to route", "#1a7f37"),
        ])
        kpi_sec = "<section><div class='kpis'>" + kpis + "</div></section>"

        # ---------- charts ----------
        charts_sec = self._charts_html(c)

        # ---------- failure sections + nav + toc ----------
        nav_items: list[str] = []
        toc_items: list[str] = []
        sections: list[str] = []
        payload_failures: dict[str, Any] = {}
        galleries: dict[str, list[str]] = {}
        owners_set: list[str] = []
        cats_set: list[str] = []
        fw_set: list[str] = []

        for idx, f in enumerate(self.failures, 1):
            fid = f"f{idx}"
            built = self._failure_section(f, fid, idx)
            nav_items.append(built["nav"])
            toc_items.append(built["toc"])
            sections.append(built["section"])
            payload_failures[fid] = built["payload"]
            if built["gallery"]:
                galleries[fid] = built["gallery"]
            if f.analysis.owner and f.analysis.owner not in owners_set:
                owners_set.append(f.analysis.owner)
            if f.analysis.category.value not in cats_set:
                cats_set.append(f.analysis.category.value)
            fw = f.record.metadata.framework_version or "unknown"
            if fw not in fw_set:
                fw_set.append(fw)

        if self.failures:
            toc = (
                "<section><h2 class='sec-h'><span class='si'>" + ic["flow"] + "</span>Failure Navigator"
                "<span class='count-pill' style='margin-left:8px'>" + str(len(self.failures)) + "</span></h2>"
                "<div class='card'><div class='toc'>" + "".join(toc_items) + "</div></div></section>"
            )
            main_sections = (
                "<section><h2 class='sec-h'><span class='si'>" + ic["bug"] + "</span>Failure Analysis</h2>"
                + "".join(sections)
                + "<div id='noMatch' class='empty hidden'>No failures match your search / filters.</div></section>"
            )
        else:
            toc = ""
            main_sections = (
                "<div class='no-fail'>" + ic["check"] + "All executed tests passed — no AI failure analysis required.</div>"
            )

        # ---------- left sidebar ----------
        def opts(values: list[str]) -> str:
            return "".join(f"<option value='{esc(v)}'>{esc(v)}</option>" for v in values)

        sev_values = [s for s in ("Blocker", "Critical", "Major", "Minor", "Trivial")
                      if self._counts()["severity_breakdown"].get(s)]
        sidebar = (
            "<aside class='dash-side'>"
            "<div class='card'>"
            "<div class='side-title'>" + ic["bug"] + "Failed Tests <span class='count-pill' style='margin-left:auto'>"
            + str(len(self.failures)) + "</span></div>"
            "<div class='navlist'>"
            + ("".join(nav_items) if nav_items else "<div class='nav-empty'>No failures 🎉</div>")
            + "</div></div>"
            "<div class='card side-filter'>"
            "<div class='side-title'>" + ic["search"] + "Filters</div>"
            "<div><label>Severity</label><select id='fSeverity'><option value=''>All</option>" + opts(sev_values) + "</select></div>"
            "<div><label>Category</label><select id='fCategory'><option value=''>All</option>" + opts(cats_set) + "</select></div>"
            "<div><label>Owner</label><select id='fOwner'><option value=''>All</option>" + opts(owners_set) + "</select></div>"
            "<div><label>Framework</label><select id='fFramework'><option value=''>All</option>" + opts(fw_set) + "</select></div>"
            "<div><label>Confidence</label><select id='fConfidence'><option value=''>All</option>"
            "<option value='high'>High (85%+)</option><option value='medium'>Medium (60-84%)</option><option value='low'>Low (&lt;60%)</option></select></div>"
            "<div><label>Status</label><select id='fStatus'><option value=''>All</option><option value='failed'>Failed</option></select></div>"
            "</div></aside>"
        )

        # ---------- toolbar / controls ----------
        toolbar = (
            "<div class='toolbar'>"
            "<button class='btn' data-action='expandAll' type='button'>" + ic["search"] + "Expand All</button>"
            "<button class='btn' data-action='collapseAll' type='button'>" + ic["tag"] + "Collapse All</button>"
            "<button class='btn' data-action='html' type='button'>" + ic["download"] + "Export Report</button>"
            "<button class='btn' data-action='json' type='button'>" + ic["code"] + "JSON</button>"
            "<button class='btn' data-action='md' type='button'>" + ic["doc"] + "Markdown</button>"
            "<button class='btn' data-action='print' type='button'>" + ic["print"] + "Print</button>"
            "<button class='btn icon' id='themeBtn' data-action='theme' type='button' aria-label='Toggle theme'>"
            + ic["moon"] + "</button>"
            "</div>"
        )
        controls = (
            "<section><div class='controls'>"
            "<div class='searchbar'>" + ic["search"] +
            "<input id='dashSearch' type='search' placeholder='Search test, root cause, evidence, owner, exception…' "
            "aria-label='Global search'></div>" + toolbar + "</div></section>"
        )

        header = (
            "<header class='top'><div class='top-in'><div class='top-row'>"
            "<div class='brand'><span class='ic'>" + ic["robot"] + "</span>AI Failure Analysis Dashboard</div>"
            + ("<span class='badge fail'>" + ic["warning"] + str(len(self.failures)) + " FAILED</span>"
               if self.failures else "<span class='badge' style='background:var(--green-bg);color:var(--green)'>"
               + ic["check"] + "ALL PASSED</span>")
            + "<div class='spacer'></div>"
            "<span class='chip'>" + ic["chip"] + "Total&nbsp;<b>" + str(c["total"]) + "</b></span>"
            "<span class='chip'>" + ic["gauge"] + "Pass&nbsp;<b>" + str(c["pass_rate"]) + "%</b></span>"
            "</div></div></header>"
        )

        # ---------- data island ----------
        payload = self._json_payload(c, gen, payload_failures)
        island = {
            "stem": _DASHBOARD_FILE_STEM,
            "markdown": self._render_markdown(),
            "failures": {
                fid: {
                    "slug": pf["slug"], "bug": pf["bug"], "markdown": pf["markdown"], "json": pf["json"],
                } for fid, pf in payload_failures.items()
            },
            "galleries": galleries,
            "raw": payload,
        }
        data_json = json.dumps(island, ensure_ascii=False).replace("<", "\\u003c")

        modal = (
            "<div class='modal' id='modal' role='dialog' aria-modal='true'>"
            "<button class='x' aria-label='Close'>&times;</button>"
            "<button class='gallery-nav prev' aria-label='Previous'>&#8249;</button>"
            "<button class='gallery-nav next' aria-label='Next'>&#8250;</button>"
            "<img src='' alt='Screenshot'>"
            "<div class='gallery-zoom'><button data-zoom='out' type='button'>&minus; Zoom</button>"
            "<button data-zoom='in' type='button'>+ Zoom</button></div></div>"
        )

        body = (
            header + controls +
            "<div class='dash-shell'>" + sidebar +
            "<div class='dash-main'>" + exec_head + kpi_sec + charts_sec + toc + main_sections +
            "<footer><div class='fl'>" + ic["robot"] +
            "Generated by <b>&nbsp;multi-framework-tc-failure-ai-analyzer</b>&nbsp;· v" + esc(pkg) +
            "&nbsp;· " + esc(gen) + "</div><div class='fl'>"
            "<a href='https://github.com/amandeepsdet/multi-framework-tc-failure-ai-analyzer' target='_blank' rel='noopener'>" + ic["git"] + "GitHub</a>"
            "</div></footer></div></div>"
            + modal +
            "<div class='toast' id='toast' role='status' aria-live='polite'></div>"
            f"<script id='ai-data' type='application/json'>{data_json}</script>"
            f"<script>{_DASHBOARD_JS}</script>"
        )

        doc = (
            "<!DOCTYPE html><html lang='en' data-theme='light'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>AI Failure Analysis — {esc(self.run_name)}</title>"
            "<link rel='preconnect' href='https://fonts.googleapis.com'>"
            "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap' rel='stylesheet'>"
            f"<style>{_REPORT_CSS}{_DASHBOARD_CSS}</style></head><body>"
            + body + "</body></html>"
        )
        return doc, payload

    def _json_payload(self, c: dict[str, Any], gen: str, payload_failures: dict[str, Any]) -> dict[str, Any]:
        return {
            "run": {
                "run_name": self.run_name,
                "framework": self.env.get("framework"),
                "environment": self.env.get("environment"),
                "browser": self._browser(),
                "os": self.env.get("os"),
                "python": self.env.get("python"),
                "package_version": self.env.get("package"),
                "commit": self.env.get("commit"),
                "ai_engine": self.cfg.provider,
                "started": self.start_ts.isoformat() if self.start_ts else None,
                "finished": self.finish_ts.isoformat() if self.finish_ts else None,
                "duration_s": round(self._duration_s(), 3),
                "generated": gen,
            },
            "summary": {k: v for k, v in c.items() if k != "severity_breakdown"},
            "severity_breakdown": c["severity_breakdown"],
            "failures": [pf["json"] for pf in payload_failures.values()],
            "passed": self.passed,
            "skipped": self.skipped,
        }

    def _charts_html(self, c: dict[str, Any]) -> str:
        ic = _ICONS
        if not self.failures:
            return ""
        cat_counts: dict[str, int] = {}
        owner_counts: dict[str, int] = {}
        conf_buckets = {"High (85%+)": 0, "Medium (60-84%)": 0, "Low (<60%)": 0}
        for f in self.failures:
            cat_counts[f.analysis.category.value] = cat_counts.get(f.analysis.category.value, 0) + 1
            owner = f.analysis.owner or "Unassigned"
            owner_counts[owner] = owner_counts.get(owner, 0) + 1
            cf = int(f.analysis.confidence)
            conf_buckets["High (85%+)" if cf >= 85 else "Medium (60-84%)" if cf >= 60 else "Low (<60%)"] += 1
        sev = c["severity_breakdown"]
        sev_labels = [s for s in ("Blocker", "Critical", "Major", "Minor", "Trivial") if sev.get(s)]
        sev_colors = {"Blocker": "#b30000", "Critical": "#cf222e", "Major": "#bc4c00", "Minor": "#9a6700", "Trivial": "#0969da"}
        palette = ["#4c9be8", "#8b7ff0", "#3fb6a8", "#f0a35e", "#e86a8f", "#6ac26a", "#c99bf0", "#f0c95e"]

        def doughnut(labels: list[str], values: list[int], colors: list[str]) -> str:
            return json.dumps({
                "type": "doughnut",
                "data": {"labels": labels, "datasets": [{"data": values, "backgroundColor": colors, "borderWidth": 0, "hoverOffset": 4}]},
                "options": {"cutout": "62%"},
            })

        def bar(labels: list[str], values: list[int], color: Any) -> str:
            return json.dumps({
                "type": "bar",
                "data": {"labels": labels, "datasets": [{"label": "Count", "data": values,
                         "backgroundColor": color, "borderRadius": 7, "maxBarThickness": 44}]},
                "options": {"plugins": {"legend": {"display": False}}},
            })

        cat_chart = doughnut(list(cat_counts.keys()), list(cat_counts.values()), palette[: len(cat_counts)])
        sev_chart = doughnut(sev_labels, [sev[s] for s in sev_labels], [sev_colors[s] for s in sev_labels])
        conf_chart = bar(list(conf_buckets.keys()), list(conf_buckets.values()), ["#1a7f37", "#9a6700", "#cf222e"])
        owner_chart = bar(list(owner_counts.keys()), list(owner_counts.values()), palette[: len(owner_counts)])

        def card(title: str, icon_key: str, chart: str, color: str) -> str:
            return (
                "<div class='card' style='border-left:4px solid " + color + "'>"
                "<div class='k-top'>" + ic.get(icon_key, "") + html.escape(title) + "</div>"
                "<div class='chartbox'><canvas data-chart='" + html.escape(chart) + "'></canvas></div></div>"
            )

        return (
            "<section data-chartsec><h2 class='sec-h'><span class='si'>" + ic["gauge"] + "</span>Execution Insights</h2>"
            "<div class='kpis'>"
            + card("Failure Categories", "tag", cat_chart, "#4c9be8")
            + card("Severity Distribution", "warning", sev_chart, "#cf222e")
            + card("Confidence Distribution", "gauge", conf_chart, "#8250df")
            + card("Owner Distribution", "user", owner_chart, "#1a7f37")
            + "</div></section>"
        )

    # ---- one failure section (isolated) ----
    def _failure_section(self, f: _ExecFailure, fid: str, idx: int) -> dict[str, Any]:
        esc = html.escape
        ic = _ICONS
        a, r = f.analysis, f.record
        m, ev = r.metadata, r.evidence
        sev = a.severity.value
        sev_color, sev_bg, sev_label, priority = _severity_meta(sev)
        conf = int(a.confidence)
        conf_color = _confidence_color(conf)
        conf_bucket = "high" if conf >= 85 else "medium" if conf >= 60 else "low"
        slug = self._slug(r.test_name)
        _uid = {"n": 0}

        def nid() -> str:
            _uid["n"] += 1
            return f"{fid}c{_uid['n']}"

        def code_block(text: str, max_h: str = "") -> str:
            cid = nid()
            style = f" style='max-height:{max_h}'" if max_h else ""
            return (
                "<div class='codewrap'>"
                f"<button class='btn copy-btn' data-copy='#{cid}' type='button'>{ic['copy']}Copy</button>"
                f"<pre class='code' id='{cid}'{style}>{esc(text)}</pre></div>"
            )

        def acc(icon_key: str, title: str, count: str, inner: str, is_open: bool = False) -> str:
            cnt = f"<span class='tag-count'>{esc(count)}</span>" if count else ""
            return (
                f"<details class='ev'{' open' if is_open else ''}>"
                f"<summary><span class='ei'>{ic.get(icon_key, '')}</span>{esc(title)}{cnt}"
                f"<span class='chev'>&#8250;</span></summary>"
                f"<div class='ev-body'>{inner}</div></details>"
            )

        exec_time = f"{m.execution_time_s:.2f}s" if m.execution_time_s is not None else ""
        commit = (m.git_commit or "")[:10]
        actual = ev.exception_message or ev.assertion_message or a.root_cause or r.failure

        # ring
        ring = (
            "<div class='ring' role='img' aria-label='Confidence " + str(conf) + " percent'>"
            "<svg viewBox='0 0 118 118'><circle class='bg' cx='59' cy='59' r='52'></circle>"
            f"<circle class='fg' cx='59' cy='59' r='52' data-v='{conf}' style='--ring:{conf_color}'></circle></svg>"
            f"<div class='num' style='color:{conf_color}'>{conf}%<small>CONFIDENCE</small></div></div>"
        )

        rc_badges = "".join([
            f"<span class='pill' style='background:{sev_bg};color:{sev_color};border-color:{sev_color}'>{ic['warning']}{esc(sev_label)} · {esc(sev)}</span>",
            f"<span class='pill' style='background:var(--accent-soft);color:var(--accent)'>{ic['tag']}{esc(a.category.value)}</span>",
            f"<span class='pill' style='background:var(--accent-soft);color:var(--accent)'>{ic['user']}{esc(a.owner or 'Unassigned')}</span>",
            f"<span class='pill' style='background:var(--accent-soft);color:var(--accent)'>{ic['brain']}{esc(a.source)}</span>",
        ])
        root_cause = (
            "<h4 class='sec-h'><span class='si'>" + ic["warning"] + "</span>AI Summary &amp; Root Cause</h4>"
            f"<div class='card rc' style='--sev:{sev_color}'>{ring}"
            "<div class='rc-body'><h2>" + esc(a.root_cause or "Root cause not determined") + "</h2>"
            f"<p>{esc(a.reasoning)}</p><div class='rc-badges'>{rc_badges}</div>"
            "<div class='rc-fix'>" + ic["bulb"] + "<span><b>Suggested fix:</b> "
            + esc(a.recommended_fix or "n/a") + "</span></div></div></div>"
        )

        # evidence accordions
        ev_cards: list[str] = []
        if a.evidence:
            inner = "<ul style='margin:6px 0 0;padding-left:18px'>" + "".join(
                f"<li>{esc(str(x))}</li>" for x in a.evidence
            ) + "</ul>"
            ev_cards.append(acc("brain", "AI Evidence Signals", str(len(a.evidence)), inner, True))
        if ev.exception_type or ev.exception_message:
            ev_cards.append(acc("warning", "Exception", ev.exception_type or "",
                                code_block(f"{ev.exception_type}: {ev.exception_message}".strip(": "))))
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
            ev_cards.append(acc("network", "Network Requests", str(len(ev.network)),
                                "<div class='tbl-wrap'><table class='data'><thead><tr><th>Method</th><th>URL</th>"
                                "<th>Status</th><th>Duration</th></tr></thead><tbody>" + rows + "</tbody></table></div>"))
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
        evsearch_scope = f"#{fid}ev"
        evidence_sec = (
            "<h4 class='sec-h'><span class='si'>" + ic["search"] + "</span>Evidence</h4>"
            "<div class='searchbar'>" + ic["search"] +
            f"<input type='search' placeholder='Search evidence…' data-evsearch='{evsearch_scope}' aria-label='Search evidence'></div>"
            f"<div id='{fid}ev'>" + "".join(ev_cards) + "</div>"
        )

        # screenshots
        gallery: list[str] = []
        screenshots_sec = ""
        if ev.screenshot:
            gallery.append(ev.screenshot)
            src = esc(ev.screenshot)
            screenshots_sec = (
                "<h4 class='sec-h'><span class='si'>" + ic["camera"] + "</span>Screenshots</h4>"
                "<div class='shots'><div class='shot' data-gallery='" + fid + "' data-idx='0' tabindex='0' role='button' "
                "aria-label='Open screenshot gallery'><img src='" + src + "' alt='Failure screenshot' "
                "onerror=\"this.closest('.shot').style.display='none'\">"
                "<div class='cap'>Click to open gallery · zoom · prev / next</div></div></div>"
            )

        # suggested fix
        prevent = f"Add a regression guard for this {a.category.value} scenario and alert when similar signals recur in future runs."
        why = (f"Directly targets the {a.category.value.lower()} root cause: {a.root_cause}"
               if a.root_cause else f"Directly targets the {a.category.value.lower()} failure class.")
        fix_sec = (
            "<h4 class='sec-h'><span class='si'>" + ic["bulb"] + "</span>Suggested Fix &amp; Prevention</h4>"
            "<div class='card rec'><div class='rec-head'><span class='rec-ic'>" + ic["bulb"] + "</span>"
            "<div><h3>Recommended Fix</h3><p class='rec-primary'>"
            + esc(a.recommended_fix or "No specific fix recommended.") + "</p></div></div>"
            "<div class='rec-grid'>"
            "<div><b>Why this works</b><p>" + esc(why) + "</p></div>"
            "<div><b>Preventive action</b><p>" + esc(prevent) + "</p></div>"
            "</div></div>"
        )

        # bug report
        bug_title = f"[{sev_label}] {r.test_name} — {a.category.value}"
        bug_env_parts = [p for p in [m.environment, m.browser, m.os, m.framework_version,
                         (f"Python {m.python_version}" if m.python_version else "")] if p]
        bug_env_full = " · ".join(bug_env_parts)
        bug_steps = [f"Execute test: {r.test_name}", "Observe the reported failure below"]
        bug_md = f.bug_markdown or ReportGenerator._bug_markdown(
            bug_title, a, r, actual, bug_env_full, priority, sev_label, bug_steps
        )
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
            f"<tr><td>Suggested Fix</td><td>{esc(a.recommended_fix)}</td></tr>"
            "</table>"
        )
        bug_sec = (
            "<h4 class='sec-h'><span class='si'>" + ic["bug"] + "</span>Generated Bug Report"
            "<span class='fac' style='margin-left:auto'>"
            f"<button class='btn' data-fail='{fid}' data-fmt='copybug' type='button'>{ic['copy']}Copy Bug</button>"
            f"<button class='btn' data-fail='{fid}' data-fmt='md' type='button'>{ic['doc']}Markdown</button>"
            f"<button class='btn' data-fail='{fid}' data-fmt='json' type='button'>{ic['code']}JSON</button>"
            "</span></h4><div class='card'>" + bug_grid + "</div>"
        )

        # similar failures
        similar_sec = ""
        if a.similar_failures:
            sim_rows = ""
            for s in a.similar_failures:
                name = esc(str(s.get("test_name", "?")))
                cat = esc(str(s.get("category", "?")))
                sim = int(s.get("similarity", 0) or 0)
                sconf = s.get("confidence")
                sconf_txt = f"{sconf}%" if sconf is not None else "—"
                sim_rows += (
                    "<tr><td class='mono'>" + name + "</td>"
                    "<td><div style='display:flex;align-items:center;gap:8px'><div class='simbar'>"
                    f"<span style='width:{sim}%'></span></div>{sim}%</div></td>"
                    f"<td>{cat}</td><td>{esc(sconf_txt)}</td></tr>"
                )
            similar_sec = (
                "<h4 class='sec-h'><span class='si'>" + ic["history"] + "</span>Similar Failures</h4>"
                "<div class='tbl-wrap'><table class='data'><thead><tr><th>Test</th><th>Similarity</th>"
                "<th>Category</th><th>Confidence</th></tr></thead><tbody>" + sim_rows + "</tbody></table></div>"
            )

        # timeline
        tl_time = (r.timestamp or "").replace("T", " ")[:19]
        timeline_sec = (
            "<h4 class='sec-h'><span class='si'>" + ic["flow"] + "</span>Failure Timeline</h4>"
            "<div class='card timeline'>"
            "<div class='tl'><span class='dot'></span><div><h4>Test Started</h4><p>" + esc(r.test_name) + "</p></div></div>"
            "<div class='tl'><span class='dot'></span><div><h4>Execution</h4><p>" + esc(m.environment or "Test steps executed") + (f" · {exec_time}" if exec_time else "") + "</p></div></div>"
            "<div class='tl fail'><span class='dot'></span><div><h4>Failure Detected</h4><p>" + esc((ev.exception_type + ": " if ev.exception_type else "") + (actual or "")) + "</p></div></div>"
            "<div class='tl ai'><span class='dot'></span><div><h4>AI Analysis</h4><p>" + esc(a.category.value) + f" · {conf}% · via " + esc(a.source) + "</p></div></div>"
            "<div class='tl done'><span class='dot'></span><div><h4>Report Generated</h4><p>" + esc(tl_time or "just now") + "</p></div></div>"
            "</div>"
        )

        # metadata sidebar (per-failure)
        def mrow(label: str, value: str) -> str:
            if not value:
                return ""
            return f"<div class='meta-row'><span class='l'>{esc(label)}</span><span class='v'>{esc(value)}</span></div>"

        meta_card = (
            "<div class='card'><h3>" + ic["chip"] + "Execution Metadata</h3>"
            + mrow("Test", r.test_name)
            + mrow("Framework", m.framework_version)
            + mrow("Browser", m.browser)
            + mrow("Environment", m.environment)
            + mrow("Operating System", m.os)
            + mrow("Python", m.python_version)
            + mrow("Commit", commit)
            + mrow("Execution Time", exec_time)
            + mrow("Timestamp", tl_time)
            + mrow("Record ID", (r.record_id or "")[:18])
            + "</div>"
        )

        left_col = root_cause + evidence_sec + screenshots_sec + fix_sec + bug_sec + similar_sec
        right_col = "<aside class='side'>" + meta_card + timeline_sec + "</aside>"

        # summary line for the collapsible header
        fmeta = " · ".join(p for p in [a.category.value, a.owner or "Unassigned",
                            (exec_time or ""), (m.browser or "")] if p)
        header_badges = (
            f"<span class='pill' style='background:{sev_bg};color:{sev_color}'>{esc(sev_label)}</span>"
            f"<span class='pill' style='background:var(--accent-soft);color:var(--accent)'>{ic['gauge']}{conf}%</span>"
            f"<span class='chev'>{ic['tag'] and ''}&#8250;</span>"
        )

        section = (
            f"<details class='fsec' id='{fid}' style='--sev:{sev_color}' "
            f"data-sev='{esc(sev)}' data-cat='{esc(a.category.value)}' data-owner='{esc(a.owner or 'Unassigned')}' "
            f"data-fw='{esc(m.framework_version or 'unknown')}' data-confbucket='{conf_bucket}' data-status='failed'>"
            "<summary><span class='fx'>" + ic["bug"] + "</span>"
            f"<div class='ft'><h3>TC-{idx:02d} · {esc(r.test_name)}</h3>"
            f"<p class='fmeta'>{esc(fmeta)}</p></div>"
            f"<div class='fbadges'>{header_badges}</div></summary>"
            "<div class='fsec-body'><div class='fgrid'><div>" + left_col + "</div>" + right_col + "</div></div>"
            "</details>"
        )

        # nav + toc
        nav = (
            f"<a class='nav-item' data-fid='{fid}' data-target='#{fid}'>"
            f"<span class='st' style='background:{sev_color}'></span>"
            f"<span class='nm'>{esc(r.test_name)}</span>"
            f"<span class='cf' style='color:{conf_color}'>{conf}%</span>"
            f"<span class='sub'>{esc(a.category.value)} · {esc(sev_label)}</span></a>"
        )
        toc = (
            f"<a data-fid='{fid}' data-target='#{fid}'>"
            f"<span class='st' style='background:{sev_color}'></span>{esc(r.test_name)}</a>"
        )

        payload = {
            "nodeid": f.nodeid,
            "test_name": r.test_name,
            "category": a.category.value,
            "severity": sev,
            "confidence": conf,
            "owner": a.owner,
            "root_cause": a.root_cause,
            "record": r.to_dict(),
            "analysis": a.to_dict(),
        }
        return {
            "nav": nav, "toc": toc, "section": section, "gallery": gallery,
            "payload": {"slug": slug, "bug": bug_md, "markdown": self.report_gen.to_markdown(r, a), "json": payload},
        }


# Module-level singleton so that multiple pytest hook sites (the packaged
# plugin and a project's own conftest) all feed and finalise the *same* report.
_EXECUTION_BUILDER: "ExecutionReportBuilder | None" = None


def get_execution_builder(cfg: AIConfig = ai_config) -> "ExecutionReportBuilder":
    """Return the shared per-run consolidated-report builder (creating it once)."""
    global _EXECUTION_BUILDER
    if _EXECUTION_BUILDER is None:
        _EXECUTION_BUILDER = ExecutionReportBuilder(cfg)
    return _EXECUTION_BUILDER
