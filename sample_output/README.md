# Sample Output

These files were produced by running the canonical demo — see what the SDK
generates **before** you install anything:

```bash
python examples/sdk_demo.py
```

The scenario: a `checkout::test_pay` test fails because the payment API returns
`HTTP 500`. The offline engine diagnoses it as a **Backend** failure.

## Single-failure artifacts

| File | What it is |
|------|------------|
| [sample_report.md](sample_report.md) | Markdown failure-analysis report (root cause, confidence, owner, fix) |
| [sample_report.json](sample_report.json) | The same `AnalysisResult` as machine-readable JSON |
| [sample_report.html](sample_report.html) | Self-contained HTML report (no external assets) |
| [sample_bug_report.md](sample_bug_report.md) | Tracker-ready bug report (title, steps, expected/actual, suggested fix) |

## Run-history dashboard

The [reports/](reports/) folder is a full **Quality Portal** dashboard built
from one run:

| File | What it is |
|------|------------|
| [reports/index.html](reports/index.html) | Landing dashboard: quality score, build health, trends, run history |
| `reports/run_*/ai_report.html` | Per-run consolidated report |
| `reports/history.json`, `reports/knowledge_base.json` | Portal state (aggregated across runs) |

> Screenshots: this demo runs with no browser, so no screenshots are captured.
> When a real UI test fails, the adapter attaches a screenshot path and it
> appears in the HTML report and bug report.
