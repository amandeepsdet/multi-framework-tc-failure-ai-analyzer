"""Artifact discovery: turn test-run artifacts into :class:`FailureContext`s.

This is the action's *adapter-selection / evidence-collection* layer. It reuses
the SDK's public :class:`FailureContextBuilder` and :class:`GenericAdapter` — it
does **not** analyse anything. Supported inputs (any subset may be present):

* **JUnit / xUnit XML** — the universal format emitted by pytest, Selenium,
  Playwright (``--reporter=junit``) and Robot Framework (``--xunit``).
* **Generic JSON** — either a serialized ``FailureContext`` or a list of them.
* **Playwright JSON** reporter output (``results.json``).
* **Robot Framework** ``output.xml``.

Nearby screenshots / logs / traces are associated with a failure on a
best-effort basis (by test-name similarity). Parsing never raises on malformed
input; problems are collected as warnings.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiqa import FailureContext, FailureContextBuilder
from aiqa.adapters import GenericAdapter

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_LOG_EXT = {".log", ".txt"}
_TRACE_EXT = {".zip", ".trace"}


@dataclass
class DiscoveryResult:
    contexts: list[FailureContext] = field(default_factory=list)
    passed: int = 0
    skipped: int = 0
    failed: int = 0
    total: int = 0
    detected_framework: str = ""
    warnings: list[str] = field(default_factory=list)
    artifacts_found: bool = False

    @property
    def has_failures(self) -> bool:
        return bool(self.contexts)


def discover_failures(report_path: str | Path, framework: str = "auto") -> DiscoveryResult:
    """Discover failures under ``report_path`` and build contexts for each."""
    root = Path(report_path)
    result = DiscoveryResult(detected_framework=framework)

    if not root.exists():
        result.warnings.append(f"Report path does not exist: {root}")
        return result

    files = _list_files(root)
    result.artifacts_found = bool(files)
    if not files:
        result.warnings.append(f"Report path is empty: {root}")
        return result

    detected = framework if framework != "auto" else _detect_framework(files)
    result.detected_framework = detected or "generic"

    junit_files = [f for f in files if _looks_like_junit(f)]
    robot_files = [f for f in files if f.name.lower() == "output.xml" and _looks_like_robot(f)]
    pw_files = [f for f in files if _looks_like_playwright_json(f)]
    generic_files = [
        f
        for f in files
        if f.suffix.lower() == ".json"
        and f not in pw_files
        and _looks_like_failure_json(f)
    ]

    media = [f for f in files if f.suffix.lower() in _IMAGE_EXT]
    logs = [f for f in files if f.suffix.lower() in _LOG_EXT]
    traces = [f for f in files if f.suffix.lower() in _TRACE_EXT]

    for f in junit_files:
        _parse_junit(f, result, detected, media, logs, traces)
    for f in robot_files:
        _parse_robot(f, result, media, logs)
    for f in pw_files:
        _parse_playwright(f, result, media, traces)
    for f in generic_files:
        _parse_generic(f, result, detected)

    result.failed = len(result.contexts)
    if result.total < result.failed + result.passed + result.skipped:
        result.total = result.failed + result.passed + result.skipped
    return result


# --------------------------------------------------------------------------- #
# Detection helpers
# --------------------------------------------------------------------------- #
def _list_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return [p for p in sorted(root.rglob("*")) if p.is_file()]


def _detect_framework(files: list[Path]) -> str:
    names = {f.name.lower() for f in files}
    if any(f.name.lower() == "output.xml" and _looks_like_robot(f) for f in files):
        return "robotframework"
    if any(_looks_like_playwright_json(f) for f in files):
        return "playwright"
    if any(_looks_like_junit(f) for f in files):
        return "pytest"
    if any(f.suffix.lower() == ".json" for f in files):
        return "generic"
    if "output.xml" in names:
        return "robotframework"
    return "generic"


def _read_text(path: Path, limit: int = 5_000_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _looks_like_junit(path: Path) -> bool:
    if path.suffix.lower() != ".xml":
        return False
    head = _read_text(path, 4000)
    return "<testsuite" in head or "<testsuites" in head


def _looks_like_robot(path: Path) -> bool:
    head = _read_text(path, 2000)
    return "<robot" in head


def _looks_like_playwright_json(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return False
    head = _read_text(path, 4000)
    return '"suites"' in head and ('"specs"' in head or '"config"' in head)


def _looks_like_failure_json(path: Path) -> bool:
    head = _read_text(path, 4000)
    return any(k in head for k in ('"exception"', '"metadata"', '"test_name"', '"failures"'))


# --------------------------------------------------------------------------- #
# Evidence association
# --------------------------------------------------------------------------- #
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _match_media(test_name: str, media: list[Path]) -> str | None:
    slug = _slug(test_name)
    if not slug:
        return None
    for m in media:
        if _slug(m.stem) and _slug(m.stem) in slug or slug in _slug(m.stem):
            return str(m)
    return None


def _match_logs(test_name: str, logs: list[Path]) -> list[str]:
    slug = _slug(test_name)
    out: list[str] = []
    for lg in logs:
        if slug and (_slug(lg.stem) in slug or slug in _slug(lg.stem)):
            text = _read_text(lg, 20000)
            if text:
                out.append(text)
    return out


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #
def _split_type_message(message: str) -> tuple[str, str]:
    """JUnit failure messages are often 'ExceptionType: detail'."""
    if not message:
        return "", ""
    if ":" in message:
        head, _, tail = message.partition(":")
        head = head.strip()
        if re.fullmatch(r"[A-Za-z_][\w.]*(Error|Exception|Failure|AssertionError)?", head):
            return head, tail.strip()
    return "", message.strip()


def _build_context(
    *,
    test_name: str,
    suite: str,
    framework: str,
    exc_type: str,
    message: str,
    stacktrace: str,
    media: list[Path],
    logs: list[Path],
    traces: list[Path],
) -> FailureContext:
    builder = (
        FailureContextBuilder()
        .with_test(test_name, suite=suite, framework=framework)
        .with_exception_text(type=exc_type, message=message, stacktrace=stacktrace)
        .with_assertion(message)
    )
    shot = _match_media(test_name, media)
    if shot:
        builder.with_screenshot(shot)
    matched_logs = _match_logs(test_name, logs)
    if matched_logs:
        builder.with_logs(matched_logs)
    trace = _match_media(test_name, traces) if traces else None
    if trace:
        builder.with_artifact("trace", trace)
    return builder.build()


def _parse_junit(
    path: Path,
    result: DiscoveryResult,
    framework: str,
    media: list[Path],
    logs: list[Path],
    traces: list[Path],
) -> None:
    try:
        root = ET.fromstring(_read_text(path))
    except ET.ParseError as exc:
        result.warnings.append(f"Could not parse JUnit XML {path.name}: {exc}")
        return

    suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
    fw = "pytest" if framework in ("auto", "generic") else framework
    for suite in suites:
        suite_name = suite.get("name", "")
        for case in suite.iter("testcase"):
            result.total += 1
            classname = case.get("classname", "")
            name = case.get("name", "test")
            test_name = f"{classname}::{name}" if classname else name
            failure = case.find("failure")
            error = case.find("error")
            node = failure if failure is not None else error
            if case.find("skipped") is not None:
                result.skipped += 1
                continue
            if node is None:
                result.passed += 1
                continue
            raw_msg = node.get("message", "") or ""
            body = (node.text or "").strip()
            exc_type, message = _split_type_message(raw_msg)
            if not message:
                message = raw_msg or (body.splitlines()[0] if body else "Test failed")
            result.contexts.append(
                _build_context(
                    test_name=test_name,
                    suite=suite_name,
                    framework=fw,
                    exc_type=exc_type or node.get("type", ""),
                    message=message,
                    stacktrace=body,
                    media=media,
                    logs=logs,
                    traces=traces,
                )
            )


def _parse_robot(
    path: Path, result: DiscoveryResult, media: list[Path], logs: list[Path]
) -> None:
    try:
        root = ET.fromstring(_read_text(path))
    except ET.ParseError as exc:
        result.warnings.append(f"Could not parse Robot output {path.name}: {exc}")
        return
    for test in root.iter("test"):
        result.total += 1
        status = test.find("status")
        state = status.get("status", "") if status is not None else ""
        name = test.get("name", "test")
        if state == "PASS":
            result.passed += 1
            continue
        if state == "SKIP":
            result.skipped += 1
            continue
        message = (status.text or "").strip() if status is not None else ""
        result.contexts.append(
            _build_context(
                test_name=name,
                suite="",
                framework="robotframework",
                exc_type="",
                message=message or "Keyword failed",
                stacktrace=message,
                media=media,
                logs=logs,
                traces=[],
            )
        )


def _parse_playwright(
    path: Path, result: DiscoveryResult, media: list[Path], traces: list[Path]
) -> None:
    try:
        data = json.loads(_read_text(path))
    except (json.JSONDecodeError, ValueError) as exc:
        result.warnings.append(f"Could not parse Playwright JSON {path.name}: {exc}")
        return

    def walk(suite: dict[str, Any], prefix: str) -> None:
        title = suite.get("title", "")
        scope = f"{prefix} > {title}".strip(" >") if title else prefix
        for spec in suite.get("specs", []) or []:
            for test in spec.get("tests", []) or []:
                result.total += 1
                results = test.get("results", []) or []
                status = (results[-1].get("status") if results else spec.get("ok")) or ""
                spec_title = spec.get("title", "test")
                test_name = f"{scope} > {spec_title}".strip(" >")
                if spec.get("ok") and status not in ("failed", "timedOut", "interrupted"):
                    result.passed += 1
                    continue
                err = {}
                for r in results:
                    if r.get("error"):
                        err = r["error"]
                        break
                message = (err.get("message") or "Test failed").strip()
                exc_type, msg = _split_type_message(message.splitlines()[0] if message else "")
                result.contexts.append(
                    _build_context(
                        test_name=test_name,
                        suite=title,
                        framework="playwright",
                        exc_type=exc_type,
                        message=msg or message,
                        stacktrace=err.get("stack", "") or "",
                        media=media,
                        logs=[],
                        traces=traces,
                    )
                )
        for child in suite.get("suites", []) or []:
            walk(child, scope)

    for suite in data.get("suites", []) or []:
        walk(suite, "")


def _parse_generic(path: Path, result: DiscoveryResult, framework: str) -> None:
    try:
        data = json.loads(_read_text(path))
    except (json.JSONDecodeError, ValueError) as exc:
        result.warnings.append(f"Could not parse JSON {path.name}: {exc}")
        return

    adapter = GenericAdapter()
    payloads: list[dict[str, Any]] = []
    if isinstance(data, list):
        payloads = [d for d in data if isinstance(d, dict)]
    elif isinstance(data, dict) and isinstance(data.get("failures"), list):
        payloads = [d for d in data["failures"] if isinstance(d, dict)]
    elif isinstance(data, dict):
        payloads = [data]

    for payload in payloads:
        result.total += 1
        try:
            ctx = adapter.collect_failure_context(payload)
        except (TypeError, ValueError, KeyError) as exc:
            result.warnings.append(f"Skipped a JSON failure in {path.name}: {exc}")
            continue
        if framework not in ("auto", "generic") and not ctx.metadata.framework:
            ctx.metadata.framework = framework
        result.contexts.append(ctx)
