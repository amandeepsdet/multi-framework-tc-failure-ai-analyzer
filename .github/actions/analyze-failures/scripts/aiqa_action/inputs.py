"""Parse and validate GitHub Action inputs from the environment.

GitHub composite actions expose ``with:`` inputs as ``INPUT_<NAME>`` environment
variables (upper-cased, dashes preserved by the runner as underscores are not —
the runner replaces spaces, so we normalise defensively). This module keeps the
mapping in one place, applies sensible defaults, and never echoes secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

# Values accepted as "true" for boolean inputs.
_TRUE = {"1", "true", "yes", "on"}

VALID_FRAMEWORKS = {"auto", "pytest", "playwright", "selenium", "robotframework", "generic"}
VALID_MODES = {"auto", "offline", "llm"}


def _get(env: Mapping[str, str], name: str, default: str = "") -> str:
    """Read an action input, tolerating both INPUT_NAME and INPUT_NAME-with-dash."""
    key = "INPUT_" + name.upper().replace("-", "_")
    if key in env:
        return env[key]
    alt = "INPUT_" + name.upper().replace("_", "-")
    return env.get(alt, default)


def _as_bool(value: str, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in _TRUE


@dataclass
class ActionInputs:
    report_path: str = "reports/"
    framework: str = "auto"
    output_path: str = "aiqa-report/"
    fail_on_error: bool = False
    post_comment: bool = True
    upload_artifact: bool = True
    llm_provider: str = "none"
    llm_api_key: str = ""
    analysis_mode: str = "auto"
    artifact_name: str = "aiqa-failure-analysis"
    warnings: list[str] = field(default_factory=list)

    @property
    def use_llm(self) -> bool:
        """Only send evidence to an external model when explicitly configured."""
        if self.analysis_mode == "offline":
            return False
        provider = (self.llm_provider or "none").strip().lower()
        if provider in ("", "none", "offline"):
            return False
        # A provider is set; require a key to actually go online.
        return bool(self.llm_api_key)


def load_inputs(env: Mapping[str, str] | None = None) -> ActionInputs:
    """Build :class:`ActionInputs` from the process environment (or a mapping)."""
    env = os.environ if env is None else env
    warnings: list[str] = []

    framework = (_get(env, "framework", "auto") or "auto").strip().lower()
    if framework not in VALID_FRAMEWORKS:
        warnings.append(
            f"Unknown framework '{framework}'; falling back to auto-detection."
        )
        framework = "auto"

    mode = (_get(env, "analysis-mode", "auto") or "auto").strip().lower()
    if mode not in VALID_MODES:
        warnings.append(f"Unknown analysis-mode '{mode}'; using 'auto'.")
        mode = "auto"

    inputs = ActionInputs(
        report_path=(_get(env, "report-path", "reports/") or "reports/").strip(),
        framework=framework,
        output_path=(_get(env, "output-path", "aiqa-report/") or "aiqa-report/").strip(),
        fail_on_error=_as_bool(_get(env, "fail-on-error", ""), False),
        post_comment=_as_bool(_get(env, "post-comment", ""), True),
        upload_artifact=_as_bool(_get(env, "upload-artifact", ""), True),
        llm_provider=(_get(env, "llm-provider", "none") or "none").strip(),
        llm_api_key=_get(env, "llm-api-key", "").strip(),
        analysis_mode=mode,
        artifact_name=(_get(env, "artifact-name", "aiqa-failure-analysis")
                       or "aiqa-failure-analysis").strip(),
        warnings=warnings,
    )
    return inputs
