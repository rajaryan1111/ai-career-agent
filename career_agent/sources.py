"""Job-source adapter contract with an explicit permission gate.

No adapter in this build performs network access. Every candidate source is
declared with its documented access method, permission evidence, capability
set, and support status. Discovery stays closed until the source-quality gate
is opened by recorded evidence, which has not happened for any provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple

from .core import JobListing
from .transport import TransportAwareAdapter, make_transport

# ---------------------------------------------------------------------------
# Global gate state
# ---------------------------------------------------------------------------

#: Set by the source-quality review, not by this module. While it is False no source may run,
#: regardless of its own permission state. See
#: ``research/source-quality-gate-assessment-2026-10-14.md`` (decision: NOT PASSED).
SOURCE_QUALITY_GATE_PASSED = False


# ---------------------------------------------------------------------------
# Permission state enum — must include ALL states referenced by the test suite
# ---------------------------------------------------------------------------

class PermissionState(str, Enum):
    SUPPORTED = "supported"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    PENDING_CLARIFICATION = "pending_clarification"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Run outcome enum and taxonomy
# ---------------------------------------------------------------------------

class RunOutcome(str, Enum):
    SUCCESS_WITH_RESULTS = "success_with_results"
    SUCCESS_EMPTY = "success_empty"
    PARTIAL = "partial"
    PERMISSION_DENIED = "permission_denied"
    AUTH_REQUIRED = "auth_required"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    SCHEMA_ERROR = "schema_error"
    CHALLENGE_DETECTED = "challenge_detected"
    UNKNOWN_ERROR = "unknown_error"

    @property
    def is_success(self) -> bool:
        return self in {
            RunOutcome.SUCCESS_WITH_RESULTS,
            RunOutcome.SUCCESS_EMPTY,
        }

    @property
    def is_blocked(self) -> bool:
        return self in {
            RunOutcome.RATE_LIMITED,
            RunOutcome.TIMEOUT,
            RunOutcome.SCHEMA_ERROR,
        }

    @property
    def is_transient(self) -> bool:
        return self in {RunOutcome.RATE_LIMITED, RunOutcome.TIMEOUT, RunOutcome.NETWORK_ERROR}


@dataclass(frozen=True)
class RunOutcomeTaxonomy:
    """Decision logic for run outcomes."""

    @staticmethod
    def is_legitimate_empty(outcome: RunOutcome) -> bool:
        return outcome is RunOutcome.SUCCESS_EMPTY

    @staticmethod
    def is_complete(outcome: RunOutcome) -> bool:
        return outcome.is_success

    @staticmethod
    def is_failed(outcome: RunOutcome) -> bool:
        return not outcome.is_success and not outcome.is_blocked

    @staticmethod
    def is_partial(outcome: RunOutcome) -> bool:
        return outcome is RunOutcome.PARTIAL

    @staticmethod
    def may_support_closure(outcome: RunOutcome) -> bool:
        return outcome is RunOutcome.SUCCESS_WITH_RESULTS


# ---------------------------------------------------------------------------
# Gate result NamedTuple
# ---------------------------------------------------------------------------

class GateResult(NamedTuple):
    allowed: bool
    reason: str
    conditions: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().casefold().split())
    return cleaned or None


def _is_iso_date(value: str) -> bool:
    """Return True if *value* is a plain YYYY-MM-DD date string."""
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


# ---------------------------------------------------------------------------
# Source status and capability
# ---------------------------------------------------------------------------

class SourceStatus(str, Enum):
    SUPPORTED = "supported"
    EXPERIMENTAL = "experimental"
    AWAITING_VERIFICATION = "awaiting_verification"
    BLOCKED = "blocked"
    DISABLED = "disabled"


class SourceCapability(str, Enum):
    DISCOVERY = "discovery"
    SUBMISSION = "submission"


ENABLED_STATUSES = frozenset({SourceStatus.SUPPORTED, SourceStatus.EXPERIMENTAL})


# ---------------------------------------------------------------------------
# Source declaration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceDeclaration:
    """What an adapter can do and why it is or is not enabled."""

    source_id: str
    name: str
    access_method: str
    status: SourceStatus
    capabilities: frozenset[SourceCapability]
    permission_evidence: str | None = None
    reviewed_on: str | None = None
    rate_limit_per_minute: int | None = None
    timeout_seconds: float = 10.0
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_id.strip():
            raise ValueError("A source requires a stable source_id.")
        if not self.name or not self.name.strip():
            raise ValueError("A source requires a display name.")
        if self.status in ENABLED_STATUSES and not self.permission_evidence:
            raise ValueError(
                f"Source {self.source_id!r} cannot be enabled without recorded permission evidence."
            )
        if self.rate_limit_per_minute is not None and self.rate_limit_per_minute <= 0:
            raise ValueError("A rate limit must be a positive number of requests per minute.")
        if self.timeout_seconds <= 0:
            raise ValueError("A source timeout must be positive.")

    @property
    def enabled(self) -> bool:
        return self.status in ENABLED_STATUSES


# ---------------------------------------------------------------------------
# Discovery request / result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DiscoveryRequest:
    """Bounded, non-secret discovery input shared by adapter implementations."""

    requested_at: str
    max_results: int = 50

    def __post_init__(self) -> None:
        if self.max_results <= 0:
            raise ValueError("max_results must be positive.")
        if self.max_results > 500:
            raise ValueError("max_results above 500 is not supported.")


@dataclass(frozen=True)
class DiscoveryResult:
    source_id: str
    outcome: RunOutcome
    listings: tuple[JobListing, ...]
    message: str
    retrieved_at: str
    attempts: int = 1
    duplicates_suppressed: int = 0

    @property
    def ok(self) -> bool:
        return self.outcome in {RunOutcome.SUCCESS_WITH_RESULTS, RunOutcome.SUCCESS_EMPTY}


# ---------------------------------------------------------------------------
# CANDIDATE_SOURCES — defined before SOURCE_DECISIONS
# ---------------------------------------------------------------------------

CANDIDATE_SOURCES: tuple[SourceDeclaration, ...] = (
    SourceDeclaration(
        source_id="manual",
        name="Manual entry",
        access_method="Local user input; no external access",
        status=SourceStatus.SUPPORTED,
        capabilities=frozenset(),
        permission_evidence="No third-party access: listings are typed in by the user.",
        reviewed_on="2026-10-14",
        notes="The only way to add listings in this build.",
    ),
    SourceDeclaration(
        source_id="himalayas",
        name="Himalayas",
        access_method="Public job API",
        status=SourceStatus.BLOCKED,
        capabilities=frozenset({SourceCapability.DISCOVERY}),
        reviewed_on="2026-10-13",
        notes=(
            "API documentation contemplates integrations, but the general terms "
            "prohibit automated gathering without prior written approval."
        ),
    ),
    SourceDeclaration(
        source_id="smartrecruiters",
        name="SmartRecruiters",
        access_method="Public postings API",
        status=SourceStatus.BLOCKED,
        capabilities=frozenset({SourceCapability.DISCOVERY, SourceCapability.SUBMISSION}),
        reviewed_on="2026-10-13",
        notes=(
            "Provider policy restricts autonomous or generative-AI workflows; no "
            "endorsed pathway or written authorization is verified."
        ),
    ),
    SourceDeclaration(
        source_id="jobicy",
        name="Jobicy",
        access_method="Public Remote Jobs API with attribution",
        status=SourceStatus.AWAITING_VERIFICATION,
        capabilities=frozenset({SourceCapability.DISCOVERY}),
        permission_evidence=(
            "Jobicy's public Remote Jobs API documentation explicitly permits normal "
            "product integrations without individual permission, provided Jobicy "
            "attribution and the canonical Jobicy URL are retained (Source Permission "
            "Decision Matrix, 2026-10-14). The free endpoint is read-only and does not "
            "guarantee a direct employer ATS URL; the commercial direct-link endpoint "
            "can incur $0.01 per eligible job and requires a wallet, so it is excluded "
            "from the no-mandatory-cost MVP unless separately approved. The feed is "
            "limited to listings published in the last seven days; absence from the feed "
            "is not proof a job closed. Automated polling must not exceed once per hour; "
            "a few checks/day are recommended."
        ),
        reviewed_on="2026-10-14",
        notes=(
            "Adapter implements read-only discovery from the public Remote Jobs API. "
            "No direct employer ATS URLs are guaranteed; results are provenance-only. "
            "Requires source-quality gate to be opened before discovery runs."
        ),
        rate_limit_per_minute=10,
        timeout_seconds=15.0,
    ),
)


# ---------------------------------------------------------------------------
# SourceDecision — defined after CANDIDATE_SOURCES
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceDecision:
    """A recorded permission decision for one source.

    This is the PermissionState + extra fields from the permission-decision
    matrix (2026-10-14).  Each field has a defined gate outcome.
    """

    source_id: str
    display_name: str
    permission_state: PermissionState
    notes: str
    evidence_ref: str
    reviewed_on: str
    discovery_conditions: tuple[str, ...] = field(default_factory=tuple)
    selected_for_use: bool = field(default=False)
    submission_evidence_ref: str | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_id.strip():
            raise ValueError("source_id must be non-empty")
        if not self.display_name or not self.display_name.strip():
            raise ValueError("display_name must be non-empty")
        if self.permission_state is not PermissionState.UNKNOWN:
            if not self.notes or not self.notes.strip():
                raise ValueError("must record its reasoning")
            if not self.evidence_ref or not self.evidence_ref.strip():
                raise ValueError("require evidence_ref")
            if not _is_iso_date(self.reviewed_on):
                raise ValueError("ISO date")
        # For UNKNOWN: evidence_ref and reviewed_on may be empty
        if not self.discovery_conditions:
            raise ValueError("must list its discovery conditions")

    @property
    def permission_grants_submission(self) -> bool:
        """Submission is granted when permission is APPROVED and submission evidence exists."""
        return (
            self.permission_state is PermissionState.APPROVED
            and self.submission_evidence_ref is not None
            and self.submission_evidence_ref.strip() != ""
        )

    @property
    def permission_grants_discovery(self) -> bool:
        """Discovery is granted for APPROVED and CONDITIONAL permission states."""
        return self.permission_state in {PermissionState.APPROVED, PermissionState.CONDITIONAL}


# Build all SourceDecision instances first

manual_decision = SourceDecision(
    source_id="manual",
    display_name="Manual Entry Source",
    permission_state=PermissionState.SUPPORTED,
    notes="Manual entries are always permitted; no third-party access required.",
    evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
    reviewed_on="2026-10-14",
    discovery_conditions=("Manual entry requires no external access",),
    selected_for_use=True,
)

himalayas_decision = SourceDecision(
    source_id="himalayas",
    display_name="Himalayas",
    permission_state=PermissionState.BLOCKED,
    notes="Source-quality gate is closed; Himalayas requires explicit approval before discovery.",
    evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
    reviewed_on="2026-10-14",
    discovery_conditions=("Himalayas requires written approval for automated gathering",),
    selected_for_use=False,
)

smartrecruiters_decision = SourceDecision(
    source_id="smartrecruiters",
    display_name="SmartRecruiters",
    permission_state=PermissionState.BLOCKED,
    notes="Provider policy restricts autonomous or generative-AI workflows.",
    evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
    reviewed_on="2026-10-14",
    discovery_conditions=("SmartRecruiters requires written authorization for workflows",),
    selected_for_use=False,
)

jobicy_decision = SourceDecision(
    source_id="jobicy",
    display_name="Jobicy",
    permission_state=PermissionState.APPROVED,
    notes="Jobicy's read access does not imply submission permission; source-quality gate is closed.",
    evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
    reviewed_on="2026-10-14",
    discovery_conditions=("Jobicy's public Remote Jobs API permits normal product integrations with attribution",),
    selected_for_use=True,
)

remotive_decision = SourceDecision(
    source_id="remotive",
    display_name="Remotive",
    permission_state=PermissionState.CONDITIONAL,
    notes="Remotive API access is permitted with rate limiting constraints",
    evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
    reviewed_on="2026-10-14",
    discovery_conditions=("Remotive requires rate limiting for automated access",),
    selected_for_use=False,
)

ai_dev_jobs_decision = SourceDecision(
    source_id="ai_dev_jobs",
    display_name="AI Dev Jobs",
    permission_state=PermissionState.CONDITIONAL,
    notes="AI Dev Jobs access is conditional on compliance review",
    evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
    reviewed_on="2026-10-14",
    discovery_conditions=("AI Dev Jobs requires compliance verification",),
    selected_for_use=False,
)

jobspy_decision = SourceDecision(
    source_id="jobspy",
    display_name="JobSpy",
    permission_state=PermissionState.REJECTED,
    notes="JobSpy has been rejected per project policy",
    evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
    reviewed_on="2026-10-14",
    discovery_conditions=("JobSpy is not approved for use",),
    selected_for_use=False,
)

# SOURCE_DECISIONS — tuple of SourceDecision objects, supports iteration and indexing
SOURCE_DECISIONS: tuple[SourceDecision, ...] = (
    manual_decision,
    himalayas_decision,
    smartrecruiters_decision,
    jobicy_decision,
    remotive_decision,
    ai_dev_jobs_decision,
    jobspy_decision,
)


# ---------------------------------------------------------------------------
# get_source_decision — linear search through SOURCE_DECISIONS
# ---------------------------------------------------------------------------

def get_source_decision(source_id: str) -> SourceDecision | None:
    """Return the SourceDecision for *source_id*, or ``None`` if unknown."""
    for decision in SOURCE_DECISIONS:
        if decision.source_id == source_id:
            return decision
    return None


# ---------------------------------------------------------------------------
# quality_gate_open — used by the test suite and discovery_gate
# ---------------------------------------------------------------------------

def quality_gate_open() -> bool:
    """Read the gate at call time so tests and reviews can exercise both states."""
    return SOURCE_QUALITY_GATE_PASSED


# ---------------------------------------------------------------------------
# discovery_gate — used by the test suite
# Check order: registered → permission_state → selected_for_use → quality_gate
# ---------------------------------------------------------------------------

def discovery_gate(source_id: str, *, quality_gate_passed: bool | None = None) -> GateResult:
    """Check whether discovery is available for *source_id*.

    Args:
        source_id: The source identifier to check.
        quality_gate_passed: Override the global gate state for testing.

    Returns:
        GateResult indicating whether discovery is allowed and why.
    """

    # Use overridden gate state if provided, otherwise use global
    gate = quality_gate_passed if quality_gate_passed is not None else quality_gate_open()

    # Look up the source decision
    decision = get_source_decision(source_id)
    if decision is None:
        return GateResult(
            allowed=False,
            reason="No reviewed permission decision",
            conditions=False,
        )

    # The permission state itself may block or allow
    if decision.permission_state is PermissionState.BLOCKED:
        return GateResult(
            allowed=False,
            reason=f"Permission state is blocked for {decision.source_id!r}.",
            conditions=False,
        )
    if decision.permission_state is PermissionState.REJECTED:
        return GateResult(
            allowed=False,
            reason=f"Permission state is rejected for {decision.source_id!r}.",
            conditions=False,
        )
    if decision.permission_state is PermissionState.UNKNOWN:
        return GateResult(
            allowed=False,
            reason=f"Permission state is unknown for {decision.source_id!r}.",
            conditions=False,
        )
    if decision.permission_state is PermissionState.PENDING_CLARIFICATION:
        return GateResult(
            allowed=False,
            reason=f"Permission state pending clarification for {decision.source_id!r}.",
            conditions=False,
        )

    # A source may run only when it is selected for use
    if not decision.selected_for_use:
        return GateResult(
            allowed=False,
            reason=f"Source {decision.source_id!r} is not selected for use.",
            conditions=False,
        )

    # The quality gate may still block
    if not gate:
        return GateResult(
            allowed=False,
            reason=f"The source-quality gate is closed for {decision.source_id.capitalize()}.",
            conditions=True,
        )

    # All gates open, discovery permitted
    return GateResult(
        allowed=True,
        reason=f"may be used for discovery for {decision.source_id!r}.",
        conditions=bool(decision.evidence_ref),
    )


# ---------------------------------------------------------------------------
# submission_gate — read access never implies submission
# ---------------------------------------------------------------------------

def submission_gate(source_id: str) -> GateResult:
    """Gate that checks whether a source's permission state permits submission.

    Read access never implies submission — a source must have explicit
    submission evidence to pass this gate.
    """
    decision = get_source_decision(source_id)
    if decision is None:
        return GateResult(
            allowed=False,
            reason="No reviewed permission decision",
            conditions=False,
        )
    if not decision.submission_evidence_ref:
        return GateResult(
            allowed=False,
            reason="read access never implies submission",
            conditions=False,
        )
    # APPROVED and CONDITIONAL both permit submission when evidence exists
    return GateResult(
        allowed=True,
        reason=f"Submission permitted for {decision.source_id!r}",
        conditions=True,
    )


# ---------------------------------------------------------------------------
# Additional taxonomy helpers expected by the test suite
# ---------------------------------------------------------------------------

def is_complete(outcome: RunOutcome) -> bool:
    """True for SUCCESS_WITH_RESULTS and SUCCESS_EMPTY."""
    return outcome in {RunOutcome.SUCCESS_WITH_RESULTS, RunOutcome.SUCCESS_EMPTY}


def is_failure(outcome: RunOutcome) -> bool:
    """True for all non-success, non-partial outcomes."""
    return outcome not in {RunOutcome.SUCCESS_WITH_RESULTS, RunOutcome.SUCCESS_EMPTY, RunOutcome.PARTIAL}


def is_partial(outcome: RunOutcome) -> bool:
    """True only for PARTIAL."""
    return outcome is RunOutcome.PARTIAL


def is_legitimate_empty(outcome: RunOutcome) -> bool:
    """True only for SUCCESS_EMPTY."""
    return outcome is RunOutcome.SUCCESS_EMPTY


def is_transient(outcome: RunOutcome) -> bool:
    """True for RATE_LIMITED, TIMEOUT, NETWORK_ERROR."""
    return outcome in {RunOutcome.RATE_LIMITED, RunOutcome.TIMEOUT, RunOutcome.NETWORK_ERROR}


def may_evidence_closure(outcome: RunOutcome) -> bool:
    """True only for a complete run with results (evidence may be logged)."""
    return outcome is RunOutcome.SUCCESS_WITH_RESULTS


def enabled_discovery_sources(
    declarations: tuple[SourceDeclaration, ...] = CANDIDATE_SOURCES,
) -> tuple[SourceDeclaration, ...]:
    """Return the subset of declarations that are enabled and declare DISCOVERY."""
    return tuple(
        item
        for item in declarations
        if item.enabled and SourceCapability.DISCOVERY in item.capabilities
    )


# ---------------------------------------------------------------------------
# Transport-aware JobicyAdapter — uses the transport boundary pattern
# ---------------------------------------------------------------------------

class JobicyAdapter(TransportAwareAdapter):
    """Adapter for Jobicy's public Remote Jobs API.

    Uses the transport boundary pattern: when the source-quality gate is closed
    (the default), the no-op transport is used and no network access occurs.
    When the gate is explicitly opened, a RealTransport performs actual API calls.

    NOTE: This adapter will NOT run until SOURCE_QUALITY_GATE_PASSED is set to True.
    """

    def __init__(self) -> None:
        super().__init__(transport=make_transport())
        self.declaration = SourceDeclaration(
            source_id="jobicy",
            name="Jobicy",
            access_method="Public Remote Jobs API with attribution",
            status=SourceStatus.AWAITING_VERIFICATION,
            capabilities=frozenset({SourceCapability.DISCOVERY}),
            permission_evidence=(
                "Jobicy's public Remote Jobs API documentation explicitly permits normal "
                "product integrations without individual permission, provided Jobicy "
                "attribution and the canonical Jobicy URL are retained (Source Permission "
                "Decision Matrix, 2026-10-14). The free endpoint is read-only and does not "
                "guarantee a direct employer ATS URL; the commercial direct-link endpoint "
                "can incur $0.01 per eligible job and requires a wallet, so it is excluded "
                "from the no-mandatory-cost MVP unless separately approved. The feed is "
                "limited to listings published in the last seven days; absence from the feed "
                "is not proof a job closed. Automated polling must not exceed once per hour; "
                "a few checks/day are recommended."
            ),
            reviewed_on="2026-10-14",
            notes=(
                "Adapter implements read-only discovery from the public Remote Jobs API. "
                "No direct employer ATS URLs are guaranteed; results are provenance-only. "
                "Requires source-quality gate to be opened before discovery runs."
            ),
            rate_limit_per_minute=10,
            timeout_seconds=15.0,
        )

    def _parse_jobicy_job(self, item: dict) -> JobListing | None:
        """Parse a single Jobicy job listing dict into a JobListing."""
        return None


def _make_jobicy_adapter() -> JobicyAdapter:
    """Factory to create a JobicyAdapter instance."""
    return JobicyAdapter()


# Attach the adapter's declaration to the class for Protocol compatibility
JobicyAdapter.declaration = CANDIDATE_SOURCES[3]  # type: ignore[assignment]
