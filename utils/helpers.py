"""Reusable helper utilities: screenshots, numeric parsing, polling, and ranges.

These functions are intentionally UI/API agnostic so they can be shared by page
objects, tests, and the API client without introducing duplication.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable, TypeVar

from utils.logger import get_logger

logger = get_logger("utils.helpers")

_SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "screenshots"
_SCREENSHOT_DIR.mkdir(exist_ok=True)

T = TypeVar("T")


def screenshot_path(name: str) -> str:
    """Return an absolute path under screenshots/ for the given logical name."""
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return str(_SCREENSHOT_DIR / f"{safe}.png")


def extract_number(text: str | None) -> float | None:
    """Extract the first numeric value from a widget string.

    Handles values such as ``"73 %"``, ``"-12.5 C"`` or ``"Battery: 88%"``.
    Returns ``None`` when no number is present.
    """
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group()) if match else None


def in_range(value: float | None, bounds: tuple[float, float]) -> bool:
    """Return True when ``value`` is a number within the inclusive ``bounds``."""
    if value is None:
        return False
    low, high = bounds
    return low <= value <= high


def poll_until(
    action: Callable[[], T],
    predicate: Callable[[T], bool],
    retries: int,
    interval_seconds: float,
    description: str = "condition",
) -> tuple[bool, T]:
    """Poll ``action`` until ``predicate`` passes or retries are exhausted.

    This is the framework's single retry primitive, used both for live
    telemetry refresh checks (UI) and eventual-consistency API reads. It never
    sleeps on the final attempt so total wait time stays predictable.

    Returns a ``(success, last_result)`` tuple so callers can report the last
    observed value even when the predicate never became true.
    """
    last_result: T = action()
    for attempt in range(1, retries + 1):
        last_result = action() if attempt > 1 else last_result
        if predicate(last_result):
            logger.info("Polling '%s' satisfied on attempt %d/%d", description, attempt, retries)
            return True, last_result
        logger.info(
            "Polling '%s' not satisfied (attempt %d/%d); last=%r",
            description,
            attempt,
            retries,
            last_result,
        )
        if attempt < retries:
            time.sleep(interval_seconds)
    return False, last_result
