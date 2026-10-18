"""Source permission gate and run-outcome taxonomy — no adapters, no network, no I/O.

The project's source rules are hard gates: a source is never enabled because it is
technically reachable, its discovery and submission permissions are separate, and the
source-quality gate must pass before any adapter runs. Those rules lived only in prose
(``rules.md`` §4, ``prd.md`` §6, ``architecture.md`` §5, and the research decision matrix),
so this module encodes them as data plus pure functions that fail closed.

Relationship to the research record: ``research/job-source-audit-seed-2026-10-13.csv`` keeps
per-record observations (including free-text ``permission_status``) and stays the audit log.
This module holds only the *decision* for a named source with a pointer to its evidence, so
the gate cannot be bypassed by accident when the first adapter is written.

Nothing here contacts a network, reads credentials, or launches a browser. No adapter exists
yet; :func:`enabled_discovery_sources` therefore returns an empty tuple, and a test asserts it.

A source that is not registered here has not been reviewed, so both gates refuse it. That is
deliberate and covers the decision matrix row for direct employer career pages: a public page,
form, or Apply button is research evidence for human review, not permission to collect from it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

#: Set by the source-quality review, not by this module. While it is False no source may run,
#: regardless of its own permission state. See
#: ``research/source-quality-gate-assessment-2026-10-14.md`` (decision: NOT PASSED).
SOURCE_QUALITY_GATE_PASSED = False


class PermissionState(str, Enum):
    """Reviewed state of a source's terms for *this* project's intended use."""

    APPROVED = "approved"                        # reviewed and permitted, conditions documented
    CONDITIONAL = "conditional"                  # permitted only under the documented conditions
    PENDING_CLARIFICATION = "pending_clarification"  # ambiguity unresolved; stays disabled
    BLOCKED = "blocked"                          # reviewed terms forbid the intended use
    REJECTED = "rejected"                        # rejected on policy grounds (e.g. evasion)
    UNKNOWN = "unknown"                          # not reviewed yet


@dataclass(frozen=True)
class SourceDecision:
    """One reviewed source and the decision about it.

    Invariants enforced at construction (a malformed decision cannot be created):
    a decision must explain itself, every state except ``UNKNOWN`` must cite evidence and a
    review date in ISO form, and a conditional source must state its conditions.
    """

    source_id: str
    display_name: str
    permission_state: PermissionState
    notes: str
    evidence_ref: str = ""
    reviewed_on: str = ""
    discovery_conditions: tuple[str, ...] = ()
    submission_conditions: tuple[str, ...] = ()
    submission_evidence_ref: str = ""
    selected_for_use: bool = False

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.display_name.strip():
            raise ValueError("A source decision requires a non-empty source_id and display_name.")
        if not self.notes.strip():
            raise ValueError(f"{self.source_id}: every decision must record its reasoning in notes.")
        if self.permission_state is not PermissionState.UNKNOWN:
            if not self.evidence_ref.strip():
                raise ValueError(f"{self.source_id}: permission states other than unknown require evidence_ref.")
            try:
                date.fromisoformat(self.reviewed_on)
            except ValueError as exc:
                raise ValueError(f"{self.source_id}: reviewed_on must be an ISO date (YYYY-MM-DD).") from exc
        if self.permission_state is PermissionState.CONDITIONAL and not self.discovery_conditions:
            raise ValueError(f"{self.source_id}: a conditional source must list its discovery conditions.")

    @property
    def permission_grants_discovery(self) -> bool:
        """True when the reviewed terms permit discovery *in principle* (conditions may apply)."""
        return self.permission_state in {PermissionState.APPROVED, PermissionState.CONDITIONAL}

    @property
    def permission_grants_submission(self) -> bool:
        """True only for an approved source with submission-specific evidence.

        Discovery and submission are reviewed separately; no source in this project currently
        satisfies both, so submission stays closed by data rather than by intention.
        """
        return self.permission_state is PermissionState.APPROVED and bool(self.submission_evidence_ref.strip())


@dataclass(frozen=True)
class GateResult:
    """Outcome of a gate check, with a reason safe to show a user or write to a log."""

    allowed: bool
    reason: str
    conditions: tuple[str, ...] = ()


#: Recorded from research/source-permission-decision-matrix-2026-10-14.md ("Jobicy limited-prototype
#: conditions"); this adheres to condition 9, which forbids sending candidate data to the source.
_JOBICY_CONDITIONS = (
    "Use the public endpoint only; no paid/commercial, wallet-backed, or API-key endpoint without separate approval.",
    "Attribute Jobicy visibly as the source and retain the canonical Jobicy listing URL.",
    "Keep active, closed, and unknown distinct when the status endpoint is used; never convert unknown to closed.",
    "Respect the 7-day feed window: a listing absent from the feed is not evidence of closure.",
    "Poll at most once per hour (a few checks per day by default); cache conservatively and back off on throttling or errors.",
    "Treat all listing text as untrusted input; sanitize markup and never execute embedded scripts.",
    "Store provenance and observation time; re-verify the official employer page before presenting high-confidence claims.",
    "Keep remote work mode, applicant-country eligibility, and legal work authorization separate.",
    "Send no candidate resumes, profiles, or other personal data to the source API.",
    "The candidate stays in control of opening the employer page and submitting an application; never submit automatically.",
)

SOURCE_DECISIONS: tuple[SourceDecision, ...] = (
    SourceDecision(
        source_id="jobicy",
        display_name="Jobicy public Remote Jobs API",
        permission_state=PermissionState.APPROVED,
        notes=(
            "The reviewed matrix approves the public endpoint for a limited read-only prototype source without "
            "individual permission, subject to the ten conditions recorded here. It is the candidate for the first "
            "adapter but stays blocked by the source-quality gate, which has not passed, so nothing may run."
        ),
        evidence_ref="research/source-permission-decision-matrix-2026-10-14.md#jobicy-limited-prototype-conditions",
        reviewed_on="2026-10-14",
        discovery_conditions=_JOBICY_CONDITIONS,
        selected_for_use=True,
    ),
    SourceDecision(
        source_id="remotive",
        display_name="Remotive public jobs API",
        permission_state=PermissionState.CONDITIONAL,
        notes=(
            "Terms allow onward sharing when the Remotive listing is linked and Remotive is named, but the feed is "
            "delayed by 24 hours, submission to specified third-party job sites is prohibited, and the planned "
            "display and distribution model is not yet confirmed against current terms. Not selected for the first "
            "adapter."
        ),
        evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
        reviewed_on="2026-10-14",
        discovery_conditions=(
            "Link the canonical Remotive listing and name Remotive as the source.",
            "Account for the documented 24-hour feed delay; absence is not evidence of closure.",
            "Do not submit its listings to other job sites.",
            "Do not gate listing details behind account creation or email capture.",
            "Confirm the app's display and distribution model against current terms before any integration.",
        ),
        selected_for_use=False,
    ),
    SourceDecision(
        source_id="ai_dev_jobs",
        display_name="AI Dev Jobs API",
        permission_state=PermissionState.CONDITIONAL,
        notes=(
            "Reviewed terms describe anonymous public read endpoints with hourly throttles and permit API data in "
            "applications, but attribution, caching, redistribution and freshness details for a candidate-facing "
            "product are unsettled and the matrix defers integration pending operator clarification."
        ),
        evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
        reviewed_on="2026-10-14",
        discovery_conditions=(
            "Obtain written operator clarification on attribution, display, caching, and use in a candidate-facing product.",
            "Stay within the published hourly throttle; never scrape beyond published limits.",
            "Do not resell or redistribute listings as a standalone dataset.",
        ),
        selected_for_use=False,
    ),
    SourceDecision(
        source_id="himalayas",
        display_name="Himalayas public API",
        permission_state=PermissionState.BLOCKED,
        notes=(
            "Public API documentation contemplates integrations while the general terms broadly prohibit "
            "automated data gathering without prior written approval. Blocked pending written clarification."
        ),
        evidence_ref="research/himalayas-api-permission-terms-conflict-2026-10-13.md",
        reviewed_on="2026-10-13",
    ),
    SourceDecision(
        source_id="smartrecruiters",
        display_name="SmartRecruiters API",
        permission_state=PermissionState.BLOCKED,
        notes=(
            "Provider policy restricts autonomous and generative-AI workflows and no endorsed pathway is "
            "verified. Blocked pending an applicable endorsed pathway or written authorization."
        ),
        evidence_ref="research/smartrecruiters-api-policy-review-2026-10-13.md",
        reviewed_on="2026-10-13",
    ),
    SourceDecision(
        source_id="jobspy",
        display_name="JobSpy",
        permission_state=PermissionState.REJECTED,
        notes=(
            "Promotes proxy-based anti-blocking guidance, which conflicts with this project's non-evasion "
            "rule, and establishes no positive source permission."
        ),
        evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
        reviewed_on="2026-10-14",
    ),
)


def get_source_decision(source_id: str) -> SourceDecision | None:
    """Return the recorded decision for ``source_id``, or ``None`` when it was never reviewed."""
    return next((decision for decision in SOURCE_DECISIONS if decision.source_id == source_id), None)


def _quality_gate_open(quality_gate_passed: bool | None) -> bool:
    return SOURCE_QUALITY_GATE_PASSED if quality_gate_passed is None else quality_gate_passed


def _gate(decision: SourceDecision | None, source_id: str, *, quality_gate_passed: bool | None, submission: bool) -> GateResult:
    capability = "submission" if submission else "discovery"
    if decision is None:
        return GateResult(False, f"No reviewed permission decision exists for source '{source_id}'; unrecorded sources stay disabled.")
    grants = decision.permission_grants_submission if submission else decision.permission_grants_discovery
    if not grants:
        if submission and decision.permission_grants_discovery:
            return GateResult(
                False,
                f"{decision.display_name} has no approved, evidenced permission for {capability} "
                f"(state: {decision.permission_state.value}); read access never implies submission.",
            )
        return GateResult(
            False,
            f"{decision.display_name} permission state is {decision.permission_state.value}; "
            f"{capability} stays disabled.",
        )
    if not decision.selected_for_use:
        return GateResult(
            False,
            f"{decision.display_name} has a reviewed permission basis but is not selected for use; nothing runs yet.",
            decision.discovery_conditions if not submission else decision.submission_conditions,
        )
    if not _quality_gate_open(quality_gate_passed):
        return GateResult(
            False,
            f"{decision.display_name} is held back by the source-quality gate, which has not passed: no source may "
            "run even when its own permission is recorded.",
            decision.discovery_conditions if not submission else decision.submission_conditions,
        )
    return GateResult(
        True,
        f"{decision.display_name} may be used for {capability} under the documented conditions.",
        decision.discovery_conditions if not submission else decision.submission_conditions,
    )


def discovery_gate(source_id: str, *, quality_gate_passed: bool | None = None) -> GateResult:
    """Whether ``source_id`` may run read-only discovery now. Fails closed in every other case."""
    return _gate(get_source_decision(source_id), source_id, quality_gate_passed=quality_gate_passed, submission=False)


def submission_gate(source_id: str, *, quality_gate_passed: bool | None = None) -> GateResult:
    """Whether ``source_id`` may be used to submit an application now. Separate from discovery."""
    return _gate(get_source_decision(source_id), source_id, quality_gate_passed=quality_gate_passed, submission=True)


def enabled_discovery_sources(*, quality_gate_passed: bool | None = None) -> tuple[str, ...]:
    """Source ids currently permitted to run discovery. Empty until a source is selected and gated."""
    return tuple(
        decision.source_id
        for decision in SOURCE_DECISIONS
        if discovery_gate(decision.source_id, quality_gate_passed=quality_gate_passed).allowed
    )


class RunOutcome(str, Enum):
    """How a single source run ended.

    ``SUCCESS_EMPTY`` is a legitimate result and is never a failure; a listing omitted from a
    partial, filtered, or blocked run is not evidence that it closed. This is distinct from
    :class:`career_agent.core.Availability`, which describes a listing, not a run.
    """

    SUCCESS_WITH_RESULTS = "success_with_results"
    SUCCESS_EMPTY = "success_empty"
    PARTIAL = "partial"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    AUTH_REQUIRED = "auth_required"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    SCHEMA_ERROR = "schema_error"
    CHALLENGE_DETECTED = "challenge_detected"
    UNKNOWN_ERROR = "unknown_error"


#: Outcomes for a run that finished normally, so its result set is authoritative.
_COMPLETE_OUTCOMES = frozenset({RunOutcome.SUCCESS_WITH_RESULTS, RunOutcome.SUCCESS_EMPTY})
#: Outcomes a read-only discovery run may retry automatically: transient conditions only.
_TRANSIENT_OUTCOMES = frozenset({RunOutcome.RATE_LIMITED, RunOutcome.TIMEOUT, RunOutcome.NETWORK_ERROR})
_FAILURE_OUTCOMES = frozenset(
    {
        RunOutcome.PERMISSION_DENIED,
        RunOutcome.RATE_LIMITED,
        RunOutcome.AUTH_REQUIRED,
        RunOutcome.TIMEOUT,
        RunOutcome.NETWORK_ERROR,
        RunOutcome.SCHEMA_ERROR,
        RunOutcome.CHALLENGE_DETECTED,
        RunOutcome.UNKNOWN_ERROR,
    }
)


def is_complete(outcome: RunOutcome) -> bool:
    """True when the run finished normally, so its result set is authoritative.

    This — not ``not is_failure(...)`` — is the check for "may I trust the absence of a listing?".
    A partial run is neither complete nor a failure, and must be surfaced as an incomplete result.
    """
    return outcome in _COMPLETE_OUTCOMES


def is_partial(outcome: RunOutcome) -> bool:
    """True when the run returned some results but could not confirm completeness."""
    return outcome is RunOutcome.PARTIAL


def is_legitimate_empty(outcome: RunOutcome) -> bool:
    """True only for a completed run that authoritatively returned no listings."""
    return outcome is RunOutcome.SUCCESS_EMPTY


def is_failure(outcome: RunOutcome) -> bool:
    """True when the run failed, was blocked, was challenged, or produced unusable data.

    Partial runs are excluded deliberately: they carry usable results and are reported through
    :func:`is_partial` and :func:`is_complete` instead of being discarded as failures.
    """
    return outcome in _FAILURE_OUTCOMES


def is_transient(outcome: RunOutcome) -> bool:
    """True for outcomes worth a bounded retry.

    Retrying is only meaningful for idempotent read-only discovery. A non-idempotent action
    (submission) must never be retried automatically on any outcome, including these.
    """
    return outcome in _TRANSIENT_OUTCOMES


def may_evidence_closure(outcome: RunOutcome) -> bool:
    """True only for a complete successful run with results.

    Necessary but not sufficient: a listing may be marked closed only when the run was complete
    and a sufficiently complete, source-specific check supports it.
    """
    return outcome is RunOutcome.SUCCESS_WITH_RESULTS
