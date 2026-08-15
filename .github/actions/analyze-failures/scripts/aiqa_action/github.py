"""GitHub side-effects: action outputs, Job Summary, and PR comment upsert.

Uses only the standard library (``urllib``) and the ``GITHUB_TOKEN`` — no PAT,
no third-party SDK. Network failures are non-fatal: publishing analysis must
never mask the original test result.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .render import COMMENT_MARKER

# An injectable "do an HTTP request and return parsed JSON + status" callable,
# so the comment logic can be unit-tested without touching the network.
HttpFn = Callable[[str, str, dict[str, str], bytes | None], tuple[int, Any]]


def _escape_multiline(value: str) -> str:
    """GITHUB_OUTPUT needs a heredoc for multi-line values; we keep values single-line."""
    return value.replace("\r", " ").replace("\n", " ")


def write_outputs(outputs: dict[str, str], path: str | None = None) -> None:
    path = path or os.getenv("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for key, value in outputs.items():
            fh.write(f"{key}={_escape_multiline(str(value))}\n")


def write_step_summary(markdown: str, path: str | None = None) -> None:
    path = path or os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(markdown.rstrip() + "\n")


def find_existing_comment(
    comments: list[dict[str, Any]], marker: str = COMMENT_MARKER
) -> int | None:
    """Return the id of the first comment containing ``marker``, else None."""
    for c in comments or []:
        if marker in (c.get("body") or ""):
            return c.get("id")
    return None


def _default_http() -> HttpFn:
    def _http(
        method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, Any]:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (github api only)
                payload = resp.read().decode("utf-8") or "null"
                return resp.status, json.loads(payload)
        except urllib.error.HTTPError as exc:
            return exc.code, {"error": exc.reason}
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            return 0, {"error": str(exc)}

    return _http


def upsert_pr_comment(
    body: str,
    *,
    token: str,
    repo: str,
    pr_number: int,
    api_url: str = "https://api.github.com",
    marker: str = COMMENT_MARKER,
    http: HttpFn | None = None,
) -> tuple[bool, str]:
    """Create or update the single AIQA comment on a PR. Returns (ok, action)."""
    if not token:
        return False, "missing-token"
    if not repo or not pr_number:
        return False, "missing-pr-context"

    http = http or _default_http()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "aiqa-action",
        "Content-Type": "application/json",
    }

    list_url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments?per_page=100"
    status, comments = http("GET", list_url, headers, None)
    existing_id = find_existing_comment(comments if isinstance(comments, list) else [], marker)

    payload = json.dumps({"body": body}).encode("utf-8")
    if existing_id is not None:
        edit_url = f"{api_url}/repos/{repo}/issues/comments/{existing_id}"
        status, _ = http("PATCH", edit_url, headers, payload)
        return (200 <= status < 300), "updated"

    create_url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments"
    status, _ = http("POST", create_url, headers, payload)
    return (200 <= status < 300), "created"


def pr_number_from_event(event_path: str | None = None) -> int:
    """Extract the PR number from the GitHub event payload, if any."""
    event_path = event_path or os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not Path(event_path).exists():
        return 0
    try:
        data = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    pr = data.get("pull_request") or {}
    number = pr.get("number") or data.get("number") or 0
    try:
        return int(number)
    except (TypeError, ValueError):
        return 0
