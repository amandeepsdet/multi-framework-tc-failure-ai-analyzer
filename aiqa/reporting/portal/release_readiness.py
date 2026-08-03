"""Release-readiness assessment.

Single responsibility: decide whether a build is safe to release given its
failure profile, and explain the decision. No I/O, no framework knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

READY = "READY"
AT_RISK = "AT RISK"
NOT_READY = "NOT READY"


@dataclass
class ReleaseReadiness:
    status: str = NOT_READY
    reasons: list[str] = field(default_factory=list)
    recommendation: str = ""


class ReleaseReadinessEngine:
    """Derives a READY / AT RISK / NOT READY verdict with rationale."""

    MIN_PASS_RATE_READY = 95.0
    MIN_PASS_RATE_RISK = 85.0
    MIN_QUALITY_READY = 80

    def assess(
        self,
        *,
        pass_rate: float,
        quality_score: int,
        critical: int = 0,
        security: int = 0,
        regressions: int = 0,
    ) -> ReleaseReadiness:
        blockers: list[str] = []
        risks: list[str] = []

        if critical > 0:
            blockers.append(f"{critical} critical failure(s) present")
        if security > 0:
            blockers.append(f"{security} security-related failure(s) present")
        if pass_rate < self.MIN_PASS_RATE_RISK:
            blockers.append(f"Pass rate {pass_rate:.0f}% is below the {self.MIN_PASS_RATE_RISK:.0f}% floor")

        if regressions > 0:
            risks.append(f"{regressions} regression(s) versus the previous run")
        if pass_rate < self.MIN_PASS_RATE_READY:
            risks.append(f"Pass rate {pass_rate:.0f}% is below the {self.MIN_PASS_RATE_READY:.0f}% release target")
        if quality_score < self.MIN_QUALITY_READY:
            risks.append(f"Quality score {quality_score} is below the target of {self.MIN_QUALITY_READY}")

        if blockers:
            status = NOT_READY
            reasons = blockers + risks
            recommendation = "Do not release. Resolve blocking failures and re-run the suite."
        elif risks:
            status = AT_RISK
            reasons = risks
            recommendation = "Release only with sign-off. Investigate risks and confirm no new regressions."
        else:
            status = READY
            reasons = ["No critical or security failures; pass rate and quality targets met."]
            recommendation = "Safe to release."

        return ReleaseReadiness(status=status, reasons=reasons, recommendation=recommendation)
