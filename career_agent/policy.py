from __future__ import annotations

from typing import Optional

"""Phase 5: Policy module.

Makes blocked, permitted, and uncertain actions distinguishable.
Keeps authorization requirements explicit.
Ensures external actions cannot be triggered merely because a recommendation exists.
"""


from dataclasses import dataclass
from enum import Enum

from .core import Decision
from .matching import MatchStrategy, Recommendation


class ActionStatus(str, Enum):
    """Status of an action relative to policy constraints."""
    PERMITTED = "permitted"
    BLOCKED = "blocked"
    UNCERTAIN = "uncertain"
    CONDITIONAL = "conditional"


class AuthorizationError(ValueError):
    """Raised when an action violates policy constraints."""


@dataclass(frozen=True)
class PolicyCheck:
    """Result of a policy check for an action."""
    action: str  # Description of the action being checked
    status: ActionStatus
    reason: str  # Human-readable explanation
    requires_auth: bool  # Whether explicit authorization is needed
    blocking_issue: Optional[str] = None  # Specific policy issue if blocked


def check_policy(
    action: str,
    eligibility: MatchStrategy,
    *,
    user_authorized: bool = False,
    has_credentials: bool = False,
) -> PolicyCheck:
    """Check whether an action is permitted by policy given eligibility state.

    Rules:
    - FAIL eligibility -> BLOCKED (cannot apply or proceed)
    - UNKNOWN eligibility with missing requirements -> UNCERTAIN (needs more info)
    - PASS eligibility -> PERMITTED if user authorized, otherwise CONDITIONAL
    - Recommendation matters: even with PASS eligibility, certain actions
      require explicit user consent
    """
    if eligibility.overall_decision == Decision.FAIL:
        return PolicyCheck(
            action=action,
            status=ActionStatus.BLOCKED,
            reason=f"Eligibility failed: {eligibility.summary}",
            requires_auth=False,
            blocking_issue="eligibility_failed",
        )

    if eligibility.overall_decision == Decision.UNKNOWN:
        return PolicyCheck(
            action=action,
            status=ActionStatus.UNCERTAIN,
            reason=f"Eligibility uncertain: {eligibility.summary}",
            requires_auth=False,
            blocking_issue="missing_evidence",
        )

    # PASS eligibility - check recommendation and authorization
    if eligibility.recommendation == Recommendation.FAIL:
        return PolicyCheck(
            action=action,
            status=ActionStatus.BLOCKED,
            reason=f"Recommendation: {eligibility.summary}",
            requires_auth=False,
            blocking_issue="recommendation_fail",
        )

    if eligibility.recommendation in (Recommendation.STRONG_PASS, Recommendation.MODERATE_PASS):
        if user_authorized and has_credentials:
            return PolicyCheck(
                action=action,
                status=ActionStatus.PERMITTED,
                reason=f"Action permitted: {eligibility.summary}",
                requires_auth=True,
            )
        else:
            return PolicyCheck(
                action=action,
                status=ActionStatus.CONDITIONAL,
                reason=f"Action conditional: {eligibility.summary}\nRequires explicit user authorization.",
                requires_auth=True,
                blocking_issue="requires_auth",
            )

    # Default for other recommendation levels
    return PolicyCheck(
        action=action,
        status=ActionStatus.UNCERTAIN,
        reason=f"Action uncertain: {eligibility.summary}",
        requires_auth=False,
    )
