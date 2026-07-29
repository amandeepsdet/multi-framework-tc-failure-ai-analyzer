"""Centralised logging configuration.

Provides a single ``get_logger`` factory that writes to both the console and a
timestamped file under ``logs/``. Using one factory keeps log formatting
consistent across page objects, the API client, and tests.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

# logs/ lives at the project root regardless of where tests are invoked from.
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# One log file per test session, named with the start timestamp.
_LOG_FILE = _LOG_DIR / f"automation_{datetime.now():%Y%m%d_%H%M%S}.log"

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s"

_configured = False


def _configure_root() -> None:
    """Attach console + file handlers to the root logger exactly once."""
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(_FORMAT)

    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger wired to the shared console + file handlers."""
    _configure_root()
    return logging.getLogger(name)
