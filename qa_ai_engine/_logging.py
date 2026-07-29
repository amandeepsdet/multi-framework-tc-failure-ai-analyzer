"""Internal logging helper so the AI engine has **no hard dependency** on the
host automation framework.

When packaged as a standalone library and dropped into any Playwright/pytest
project, ``utils.logger`` will not exist. This shim transparently reuses the
host framework's ``utils.logger.get_logger`` when it is importable (preserving
its file handlers and formatting), and otherwise falls back to a self-contained
stdlib logger so the engine works anywhere with zero configuration.
"""

from __future__ import annotations

import logging
import os

try:  # Reuse the host framework's configured logger when available.
    from utils.logger import get_logger as _host_get_logger  # type: ignore
except Exception:  # noqa: BLE001 - standalone install: no host framework
    _host_get_logger = None


_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s"


def _standalone_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        logger.addHandler(handler)
        level = os.getenv("AI_LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level, logging.INFO))
        logger.propagate = False
    return logger


def get_logger(name: str = "qa_ai") -> logging.Logger:
    """Return a logger, delegating to the host framework if it is installed."""
    if _host_get_logger is not None:
        try:
            return _host_get_logger(name)
        except Exception:  # noqa: BLE001 - never let logging setup break a run
            pass
    return _standalone_logger(name)
