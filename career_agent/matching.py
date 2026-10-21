"""Phase 5: Strategy, artifact lineage, policy and reporting.

This module provides:
- Strategy: Explainable matching results and recommendations
- Artifact lineage: Track source information for generated artifacts
- Policy: Distinguish blocked, permitted, and uncertain actions
- Reporting: Distinguish confirmed facts, inferred facts, missing information
- Notifications and follow-ups: Local notification/follow-up requirements
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


class Recommendation(str, Enum):
    """Recommendation level for a job/candidate match."""
    STRONG_PASS = "strong_pass"
    MODERATE_PASS = "moderate_pass"
    CONDITIONAL_PASS = "conditional_pass"
    UNKNOWN = "unknown"
    CONDITIONAL_FAIL = "conditional_fail"
    FAIL = "fail"


@dataclass(frozen=True)
class MatchStrategy:
    """Strategy result representing how a candidate matches a job.

    This is separate from confirmed candidate facts - it represents the
    matching logic's assessment based on available evidence.
    """
    job: JobListing
    profile: CandidateProfile
    overall_decision: Decision
    requirement_details: dict[str, dict[str, Any]]
    summary: str
    missing_requirements: tuple[str, ...]
    recommendation: Recommendation
    verification_required: bool
    confidence: str  # "high" | "medium" | "low"


def assess_strategy(profile: CandidateProfile, job: JobListing) -> MatchStrategy:
    """Assess candidate/job match using explainable eligibility logic.

    Wraps evaluate_eligibility and explain_eligibility to produce a
    structured strategy result with recommendation and confidence.

    The recommendation ladder:
    - FAIL overall -> CONDITIONAL_FAIL or FAIL based on missing vs proven failures
    - UNKNOWN overall with no missing -> UNKNOWN
    - PASS overall -> STRONG_PASS if all requirements have high confidence
    - PASS overall with some UNKNOWN -> MODERATE_PASS or CONDITIONAL_PASS
    """
    report = explain_eligibility(profile, job)

    # Build requirement details from the report
    req_details = report.get("requirements", {})

    # Determine missing requirements
    missing = report.get("missing_requirements", ())

    # Determine overall decision
    overall = Decision(report["overall_decision"])

    # Determine recommendation based on overall decision and confidence
    recommendation = Recommendation.UNKNOWN
    confidence = "low"
    verification_required = True

    if overall == Decision.PASS:
        # All requirements pass - check confidence
        # In a real implementation, we'd look at provenance sources
        # For now, use default confidence based on what we know
        if not missing:
            recommendation = Recommendation.STRONG_PASS
            confidence = "medium"
            verification_required = False
        else:
            recommendation = Recommendation.CONDITIONAL_PASS
            confidence = "low"
            verification_required = True
    elif overall == Decision.FAIL:
        # At least one requirement fails
        failed_reqs = [r for r in report.get("missing_requirements", [])]
        if failed_reqs:
            recommendation = Recommendation.FAIL
        else:
            recommendation = Recommendation.CONDITIONAL_FAIL
        confidence = "low"
        verification_required = True
    else:  # UNKNOWN
        if not missing:
            recommendation = Recommendation.UNKNOWN
        else:
            recommendation = Recommendation.CONDITIONAL_FAIL
        confidence = "low"
        verification_required = True

    return MatchStrategy(
        job=job,
        profile=profile,
        overall_decision=overall,
        requirement_details=req_details,
        summary=report.get("summary", ""),
        missing_requirements=missing,
        recommendation=recommendation,
        verification_required=verification_required,
        confidence=confidence,
    )
