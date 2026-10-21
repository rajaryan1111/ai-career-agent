"""Phase 5: Reporting module.

Distinguishes confirmed facts, inferred facts, missing information, and recommendations.
Provides actionable explanations for unknown or failed requirements.
Avoids claiming that an application was submitted or confirmed without evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .core import (
    CandidateProfile,
    Decision,
    JobListing,
    explain_eligibility,
)


class ReportType(str, Enum):
    """Type of eligibility report."""
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    MISSING = "missing"
    RECOMMENDATION = "recommendation"


@dataclass(frozen=True)
class EligibilityInsight:
    """A single insight about a requirement's status."""
    requirement: str
    decision: Decision
    evidence: Any
    provenance: str  # "user_entered", "imported", "inferred", "verified", "unknown"
    reason: str
    is_confirmed: bool  # Whether this is confirmed evidence
    verification_required: bool
    confidence: str  # "high" | "medium" | "low"


@dataclass(frozen=True)
class EligibilitySummary:
    """Summary of eligibility evaluation with fact/inference/missing distinction."""
    overall_decision: Decision
    confirmed_facts: tuple[EligibilityInsight, ...]
    inferred_facts: tuple[EligibilityInsight, ...]
    missing_requirements: tuple[str, ...]
    recommendations: tuple[str, ...]
    summary: str
    requires_followup: bool


def build_eligibility_insights(
    profile: CandidateProfile,
    job: JobListing,
) -> EligibilitySummary:
    """Build a detailed eligibility summary with fact/inference/missing distinction.

    Returns a structured summary that distinguish:
    - Confirmed facts (verified evidence)
    - Inferred facts (based on available but unconfirmed data)
    - Missing information (gaps that prevent evaluation)
    - Recommendations (actionable next steps)
    """
    report = explain_eligibility(profile, job)

    requirements = report.get("requirements", {})
    overall = Decision(report["overall_decision"])
    missing = report.get("missing_requirements", ())

    confirmed_facts: list[EligibilityInsight] = []
    inferred_facts: list[EligibilityInsight] = []

    for req_name, req_data in requirements.items():
        decision = Decision(req_data["decision"])
        evidence = req_data.get("evidence")
        provenance = req_data.get("provenance", "unknown")
        reason = req_data.get("reason", "")
        verification_required = req_data.get("verification_required", False)
        confidence = req_data.get("confidence", "low")

        is_confirmed = (decision == Decision.PASS and
                         provenance in ("verified", "user_entered") and
                         not verification_required)

        insight = EligibilityInsight(
            requirement=req_name,
            decision=decision,
            evidence=evidence,
            provenance=provenance,
            reason=reason,
            is_confirmed=is_confirmed,
            verification_required=verification_required,
            confidence=confidence,
        )

        if is_confirmed:
            confirmed_facts.append(insight)
        elif provenance == "inferred":
            inferred_facts.append(insight)

    # Determine recommendations based on the evaluation
    recommendations: list[str] = []

    if overall == Decision.FAIL:
        recommendations.append("Do not proceed - eligibility requirements not met")
        if missing:
            recommendations.append("Provide missing information before re-evaluating")
    elif overall == Decision.UNKNOWN:
        if missing:
            recommendations.append("Supply missing information to determine eligibility")
        else:
            recommendations.append("Eligibility cannot be determined with current information")
    elif overall == Decision.PASS:
        recommendations.append("Candidate appears eligible - review before proceeding")
        if any(not insight.is_confirmed for insight in confirmed_facts + inferred_facts):
            recommendations.append("Verify evidence quality before final confirmation")

    # Build summary string
    summary_parts = [f"Overall: {overall.value}"]
    if confirmed_facts:
        summary_parts.append(f"{len(confirmed_facts)} confirmed fact(s)")
    if inferred_facts:
        summary_parts.append(f"{len(inferred_facts)} inferred fact(s)")
    if missing:
        summary_parts.append(f"{len(missing)} missing requirement(s)")
    summary = " | ".join(summary_parts)

    return EligibilitySummary(
        overall_decision=overall,
        confirmed_facts=tuple(confirmed_facts),
        inferred_facts=tuple(inferred_facts),
        missing_requirements=missing,
        recommendations=tuple(recommendations),
        summary=summary,
        requires_followup=bool(missing or overall in (Decision.UNKNOWN, Decision.FAIL)),
    )
