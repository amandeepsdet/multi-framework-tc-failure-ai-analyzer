"""Quality score calculation (0-100) with human-readable bands.

Single responsibility: turn raw execution statistics into a defensible quality
score and band. It knows nothing about HTML, storage, or frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityScore:
    value: int = 0
    band: str = "Poor"
    build_health: str = "Critical"
    factors: dict[str, Any] = field(default_factory=dict)


class QualityScoreCalculator:
    """Computes a 0-100 quality score from weighted execution factors."""

    # Penalties applied to the pass-rate baseline.
    PENALTY_CRITICAL = 8
    PENALTY_SECURITY = 10
    PENALTY_REGRESSION = 6
    PENALTY_FLAKY = 3
    PENALTY_BLOCKED = 1

    # Band thresholds (inclusive lower bounds).
    BAND_EXCELLENT = 90
    BAND_GOOD = 75
    BAND_WARNING = 50

    def score(
        self,
        *,
        pass_rate: float,
        critical: int = 0,
        security: int = 0,
        regressions: int = 0,
        flaky: int = 0,
        blocked: int = 0,
        avg_confidence: float = 0.0,
    ) -> QualityScore:
        base = float(pass_rate)
        penalties = {
            "critical": min(critical, 6) * self.PENALTY_CRITICAL,
            "security": min(security, 4) * self.PENALTY_SECURITY,
            "regressions": min(regressions, 6) * self.PENALTY_REGRESSION,
            "flaky": min(flaky, 6) * self.PENALTY_FLAKY,
            "blocked": min(blocked, 10) * self.PENALTY_BLOCKED,
        }
        # A confident diagnosis of *green* runs nudges the score up slightly;
        # confident diagnosis of failures should not inflate quality.
        confidence_bonus = round((avg_confidence / 100.0) * 2.0, 1) if pass_rate >= 100 else 0.0
        value = base - sum(penalties.values()) + confidence_bonus
        value = int(max(0, min(100, round(value))))

        band = self._band(value)
        health = self._health(value, critical, security)
        return QualityScore(
            value=value,
            band=band,
            build_health=health,
            factors={
                "pass_rate": round(base, 1),
                "penalties": penalties,
                "confidence_bonus": confidence_bonus,
                "critical": critical,
                "security": security,
                "regressions": regressions,
                "flaky": flaky,
                "blocked": blocked,
                "avg_confidence": round(avg_confidence, 1),
            },
        )

    def _band(self, value: int) -> str:
        if value >= self.BAND_EXCELLENT:
            return "Excellent"
        if value >= self.BAND_GOOD:
            return "Good"
        if value >= self.BAND_WARNING:
            return "Warning"
        return "Poor"

    def _health(self, value: int, critical: int, security: int) -> str:
        if critical > 0 or security > 0 or value < self.BAND_WARNING:
            return "Critical"
        if value < self.BAND_GOOD:
            return "Warning"
        return "Healthy"
