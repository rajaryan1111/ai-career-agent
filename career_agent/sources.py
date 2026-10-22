"""Job-source adapter contract with an explicit permission gate.

No adapter in this build performs network access. Every candidate source is
declared with its documented access method, permission evidence, capability
set, and support status. Discovery stays closed until the source-quality gate
is opened by recorded evidence, which has not happened for any provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Protocol, Sequence

from .core import JobListing

# Flipping this requires recorded permission evidence for at least one source;
# see research/source-quality-gate-assessment-2026-10-14.md.
SOURCE_QUALITY_GATE_PASSED = False


class SourceStatus(str, Enum):
    SUPPORTED = "supported"
    EXPERIMENTAL = "experimental"
    AWAITING_VERIFICATION = "awaiting_verification"
    BLOCKED = "blocked"
    DISABLED = "disabled"


class SourceCapability(str, Enum):
    DISCOVERY = "discovery"
    SUBMISSION = "submission"


class DiscoveryOutcome(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    TRANSIENT_ERROR = "transient_error"
    SCHEMA_ERROR = "schema_error"


ENABLED_STATUSES = frozenset({SourceStatus.SUPPORTED, SourceStatus.EXPERIMENTAL})


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
    outcome: DiscoveryOutcome
    listings: tuple[JobListing, ...]
    message: str
    retrieved_at: str
    attempts: int = 1
    duplicates_suppressed: int = 0

    @property
    def ok(self) -> bool:
        return self.outcome in {DiscoveryOutcome.OK, DiscoveryOutcome.EMPTY}


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff; providers enforce their own quotas too."""

    attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 5.0

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("A retry policy needs at least one attempt.")
        if self.attempts > 5:
            raise ValueError("A retry policy allows at most 5 attempts.")
        if self.base_delay < 0 or self.max_delay < 0:
            raise ValueError("Retry delays cannot be negative.")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay cannot be smaller than base_delay.")

    def delay_for(self, attempt: int) -> float:
        """Delay before retry ``attempt`` (1-based), capped by ``max_delay``."""
        if attempt < 1:
            raise ValueError("Attempt numbers start at 1.")
        return min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)


class SourceAdapter(Protocol):
    declaration: SourceDeclaration

    def discover(self, request: DiscoveryRequest) -> Sequence[JobListing]:
        """Return observed listings; raise for transport/schema failures."""


class SourceSchemaError(RuntimeError):
    """Raised by an adapter when the payload shape is wrong; never retried."""


class RateLimitExceeded(RuntimeError):
    """Raised locally before an adapter would exceed its declared budget."""


class RateLimiter:
    """In-memory per-adapter budget; providers still enforce their own quotas."""

    def __init__(self, per_minute: int, *, clock=time.monotonic) -> None:
        if per_minute <= 0:
            raise ValueError("A rate limit must be positive.")
        self.per_minute = per_minute
        self._clock = clock
        self._calls: list[float] = []

    def acquire(self) -> None:
        now = self._clock()
        self._calls = [stamp for stamp in self._calls if now - stamp < 60.0]
        if len(self._calls) >= self.per_minute:
            raise RateLimitExceeded(
                f"Local rate limit reached ({self.per_minute} requests per minute)."
            )
        self._calls.append(now)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
)


def quality_gate_open() -> bool:
    """Read the gate at call time so tests and reviews can exercise both states."""
    return SOURCE_QUALITY_GATE_PASSED


def enabled_discovery_sources(
    declarations: Sequence[SourceDeclaration] = CANDIDATE_SOURCES,
) -> tuple[SourceDeclaration, ...]:
    return tuple(
        item for item in declarations
        if item.enabled and SourceCapability.DISCOVERY in item.capabilities
    )


def discovery_available() -> bool:
    return quality_gate_open() and bool(enabled_discovery_sources())


def _result(declaration: SourceDeclaration, outcome: DiscoveryOutcome, message: str,
            listings: Sequence[JobListing] = (), *, attempts: int = 1,
            duplicates_suppressed: int = 0) -> DiscoveryResult:
    return DiscoveryResult(
        declaration.source_id, outcome, tuple(listings), message, _now(),
        attempts, duplicates_suppressed,
    )


def deduplicate_observations(
    listings: Sequence[JobListing],
) -> tuple[tuple[JobListing, ...], int]:
    """Collapse repeated observations of one job, keeping the first seen."""
    from .core import duplicate_key

    seen: set[str] = set()
    unique: list[JobListing] = []
    for listing in listings:
        key = duplicate_key(listing)
        if key in seen:
            continue
        seen.add(key)
        unique.append(listing)
    return tuple(unique), len(listings) - len(unique)


def run_discovery(
    adapter: SourceAdapter,
    request: DiscoveryRequest,
    *,
    limiter: RateLimiter | None = None,
    retry: RetryPolicy | None = None,
    sleep=time.sleep,
) -> DiscoveryResult:
    """Run one adapter behind the permission gate and report typed outcomes.

    Refusals never call the adapter, so a closed gate cannot cause network
    access. Transport and schema failures stay distinct from a valid empty run,
    and retries are bounded by ``retry`` with injectable sleep for tests.
    """
    declaration = adapter.declaration
    if not quality_gate_open():
        return _result(
            declaration, DiscoveryOutcome.BLOCKED,
            "The source-quality gate is closed; discovery is disabled.",
        )
    if not declaration.enabled:
        return _result(
            declaration, DiscoveryOutcome.BLOCKED,
            f"Source status is {declaration.status.value}; it is not enabled.",
        )
    if SourceCapability.DISCOVERY not in declaration.capabilities:
        return _result(
            declaration, DiscoveryOutcome.BLOCKED,
            "This adapter does not declare discovery capability.",
        )
    if limiter is not None:
        try:
            limiter.acquire()
        except RateLimitExceeded as exc:
            return _result(declaration, DiscoveryOutcome.RATE_LIMITED, str(exc))

    attempts_allowed = retry.attempts if retry is not None else 1
    for attempt in range(1, attempts_allowed + 1):
        try:
            observed = tuple(adapter.discover(request))
            break
        except SourceSchemaError as exc:
            return _result(
                declaration, DiscoveryOutcome.SCHEMA_ERROR,
                f"The source payload was not understood: {exc}", attempts=attempt,
            )
        except TimeoutError:
            failure = DiscoveryOutcome.TIMEOUT
            failure_message = "The source timed out."
        except Exception as exc:  # Adapters must not leak transport details into the UI.
            failure = DiscoveryOutcome.TRANSIENT_ERROR
            failure_message = f"The source failed: {type(exc).__name__}."
        else:  # pragma: no cover - defensive; the loop always breaks or returns
            failure = None
        if attempt == attempts_allowed:
            return _result(
                declaration, failure,
                f"{failure_message} Gave up after {attempt} attempt(s).",
                attempts=attempt,
            )
        if retry is not None:
            sleep(retry.delay_for(attempt))
    else:  # pragma: no cover - the loop returns on the final attempt
        return _result(declaration, DiscoveryOutcome.TRANSIENT_ERROR, "No attempt was made.")

    if not all(isinstance(item, JobListing) for item in observed):
        return _result(
            declaration, DiscoveryOutcome.SCHEMA_ERROR,
            "The source returned records that are not listings.", attempts=attempt,
        )
    unique, suppressed = deduplicate_observations(observed)
    if not unique:
        return _result(
            declaration, DiscoveryOutcome.EMPTY,
            "The source returned no listings; this is a valid empty result.",
            attempts=attempt,
        )
    message = f"Observed {len(unique)} listing(s)."
    if suppressed:
        message += f" Suppressed {suppressed} duplicate observation(s)."
    return _result(
        declaration, DiscoveryOutcome.OK, message, unique,
        attempts=attempt, duplicates_suppressed=suppressed,
    )
