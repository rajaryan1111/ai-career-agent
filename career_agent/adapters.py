"""The source-adapter framework: the shape an adapter must have, and the rules the app runs it under.

No adapter here reaches a network, and none of them can: every call goes through
:class:`AdapterRegistry`, which refuses any source whose discovery gate is closed, and the gate is closed
(:data:`career_agent.sources.SOURCE_QUALITY_GATE_PASSED` is ``False``). The framework exists so that when a
source is genuinely approved, the code around it is already written, reviewed and tested - not so that a
source can be switched on by editing a constant.

What the framework fixes, in one place:

**Capabilities are declared, not assumed.** :class:`SourceCapabilities` says what an adapter can do -
whether it can discover at all, whether it paginates, whether it needs credentials, what its documented
request limit is - and the registry refuses to treat an undeclared capability as available. Submission is
a separate declaration and is ``False`` for every adapter: this project never submits an application on
its own.

**Every request is bounded before it is made.** :class:`RequestBudget` caps how many requests one run may
issue and how quickly, and :func:`fetch_with_bounded_retries` retries *only* the outcomes the taxonomy
calls transient, a bounded number of times, with an injected sleeper so the waiting is testable rather
than real.

**A run's result says which of four things happened.** Success with results, a legitimate empty result,
a partial result, or a failure - and :class:`SourceHealth` keeps them apart, because "the source is down"
and "the source has nothing" lead to opposite decisions. An empty result is never recorded as a failure,
and a failure never closes a listing (:func:`career_agent.sources.may_evidence_closure`).

**Malformed records are reported, never silently dropped.** Normalisation validates each record against
what the domain model requires, keeps the record's own provenance, and returns a
:class:`NormalizationReport` whose ``rejected`` list names each record and why. A run that loses records
to a schema change is a run that must say so - that is what makes a source's health meaningful.

**Only what a source states is carried over.** List-valued facts (the skills a listing names) are taken
as given; the fields that would require *interpreting* the source's prose - eligibility scope, degree
disciplines, experience ranges, compensation - are deliberately left unset by the framework. Those must
come from a reviewed parser per source, because guessing them is how an app starts asserting eligibility
nobody stated.

**Deduplication is explicit and local.** Records are deduplicated within a source and then across sources
using the same canonical-identity rule the rest of the app uses
(:func:`career_agent.core.duplicate_key`), and the result reports which listings were merged into which,
so a person can see that two sources offered the same job rather than seeing it twice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping, Protocol, Sequence, runtime_checkable

from .core import JobListing, canonicalize_url, duplicate_key, deduplicate_listings
from .policy import ActionKind, GlobalPolicy, PolicySubject, evaluate_policy, no_authorisation
from .sources import (
    RunOutcome, discovery_gate, is_failure, is_partial, is_transient,
)

#: The largest page an adapter may be asked for. A limit is *always* sent, so "give me everything" cannot
#: be expressed, and a mistyped number cannot turn into an unbounded crawl.
MAX_PAGE_SIZE = 100

#: How many requests one run may issue before it stops and reports that it did. Small on purpose: the
#: first adapters are meant to fetch a page or two and let a person look at the result.
MAX_REQUESTS_PER_RUN = 5

#: The shortest gap between two requests from one adapter, in seconds. A source that documents a slower
#: rate than this needs a lower value here, not a comment in a wiki.
MIN_SECONDS_BETWEEN_REQUESTS = 2.0

#: How many times a transient outcome may be retried inside one run, and how long the first wait is.
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5.0


class AdapterError(RuntimeError):
    """A problem in the adapter framework itself (a misuse), not a source's failure."""


class SourceDisabled(AdapterError):
    """The source's discovery gate is closed, so no request may be made to it.

    Raised by :meth:`AdapterRegistry.execute` before an adapter is called. This is the framework's
    fail-closed behaviour, and it is the reason the app cannot accidentally reach a source whose
    permission review has not passed.
    """


class BudgetExhausted(AdapterError):
    """The run's request budget is used up: no further request may be issued."""


@dataclass(frozen=True)
class SourceCapabilities:
    """What an adapter declares it can do. Nothing is inferred from the adapter's own behaviour.

    ``submission`` is here so that the answer to "can this source apply for me?" is written down and
    reviewed per source: it is ``False`` everywhere in this build.
    """

    discovery: bool = False
    submission: bool = False
    pagination: bool = False
    requires_credentials: bool = False
    documented_request_limit: str = "not documented"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.submission:
            # The product decision is explicit (rules.md): no automated submission, ever, until a
            # separately authorised workflow exists. An adapter may not declare it.
            raise AdapterError(
                "No adapter may declare submission capability: applications are never submitted "
                "automatically by this application."
            )


@dataclass(frozen=True)
class AdapterRequest:
    """One bounded query: what to look for, how much of it, and where to continue from.

    Deliberately small. There is no "fetch everything" field, the page size is capped, and the query
    terms are bounded strings, so a request cannot be written that asks for an unbounded amount of
    somebody else's data.
    """

    terms: tuple[str, ...] = ()
    location: str | None = None
    page_size: int = 25
    page_token: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.page_size, bool) or not isinstance(self.page_size, int):
            raise AdapterError(f"The page size must be a whole number, not {self.page_size!r}.")
        if not 1 <= self.page_size <= MAX_PAGE_SIZE:
            raise AdapterError(f"The page size must be between 1 and {MAX_PAGE_SIZE}.")
        cleaned_terms: list[str] = []
        for term in self.terms:
            if not isinstance(term, str):
                raise AdapterError(f"A search term must be text, not {term!r}.")
            cleaned = " ".join(term.split())
            if len(cleaned) > 80:
                raise AdapterError("A search term must be at most 80 characters.")
            if cleaned:
                cleaned_terms.append(cleaned)
        object.__setattr__(self, "terms", tuple(cleaned_terms))
        if self.location is not None:
            cleaned = " ".join(str(self.location).split())
            if len(cleaned) > 80:
                raise AdapterError("A location must be at most 80 characters.")
            object.__setattr__(self, "location", cleaned or None)
        if self.page_token is not None and not isinstance(self.page_token, str):
            raise AdapterError("A page token must be text.")

    def summary(self) -> str:
        """A one-line description safe to store in a run record (no credentials, no URLs)."""
        parts = []
        if self.terms:
            parts.append("terms=" + " ".join(self.terms))
        if self.location:
            parts.append(f"location={self.location}")
        parts.append(f"page_size={self.page_size}")
        parts.append("first page" if not self.page_token else "continuation page")
        return "; ".join(parts)


@dataclass(frozen=True)
class AdapterProvenance:
    """Where a batch came from, and when - the part a person needs to judge it."""

    source_id: str
    source_name: str
    retrieved_at: datetime
    request_summary: str
    adapter_version: str = "1"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise AdapterError("A provenance record must carry the timezone of the moment it was made.")
        object.__setattr__(self, "retrieved_at", self.retrieved_at.astimezone(timezone.utc))

    def describe(self) -> str:
        """One line for a run record or a diagnostics view."""
        return (f"{self.source_name} ({self.source_id}) at {self.retrieved_at.isoformat()} "
                f"[{self.request_summary}]")


@dataclass(frozen=True)
class RejectedRecord:
    """A record the adapter returned that could not be turned into a listing, and why."""

    index: int
    reason: str
    identifier: str | None = None


@dataclass(frozen=True)
class NormalizationReport:
    """What normalisation kept, merged and rejected.

    Rejections are data, not noise: a source whose records stopped matching the model is unhealthy even
    when the transport worked, and the counts here are what let the health view say so.
    """

    accepted: tuple[JobListing, ...]
    rejected: tuple[RejectedRecord, ...]
    merged_within_source: tuple[tuple[str, str], ...] = ()  # (kept listing_id, dropped listing_id)
    merged_across_sources: tuple[tuple[str, str], ...] = ()

    @property
    def rejected_count(self) -> int:
        """How many records were dropped, so a health line can report it without iterating."""
        return len(self.rejected)


@dataclass(frozen=True)
class AdapterResponse:
    """One adapter's answer for one request: its outcome, its records and its provenance."""

    outcome: RunOutcome
    provenance: AdapterProvenance
    records: tuple[Mapping[str, object], ...] = ()
    next_page_token: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, RunOutcome):
            raise AdapterError(f"An adapter outcome must be a RunOutcome, not {self.outcome!r}.")
        for record in self.records:
            if not isinstance(record, Mapping):
                raise AdapterError(
                    "An adapter must return mappings (plain records); the framework normalises them so "
                    "one source's object model cannot leak into the rest of the app."
                )
        if self.outcome in (RunOutcome.SUCCESS_WITH_RESULTS, RunOutcome.SUCCESS_EMPTY, RunOutcome.PARTIAL):
            if self.outcome is RunOutcome.SUCCESS_WITH_RESULTS and not self.records:
                # A "success with results" that carries none is a contradiction: it would let a broken
                # adapter look like a source that simply has nothing today.
                raise AdapterError(
                    "An adapter that reports success_with_results must return at least one record; use "
                    "success_empty when the source genuinely has nothing."
                )
            if self.outcome is RunOutcome.SUCCESS_EMPTY and self.records:
                raise AdapterError(
                    "An adapter that reports success_empty must not return records."
                )

    @property
    def is_complete(self) -> bool:
        """Whether this batch is authoritative (so an omitted listing may be treated as absent)."""
        from .sources import is_complete as _is_complete

        return _is_complete(self.outcome)


@runtime_checkable
class SourceAdapter(Protocol):
    """What a source adapter must provide.

    Small on purpose: an adapter fetches and reports; it does not decide whether it is allowed to run (the
    registry does), does not normalise into the domain model (the framework does, so every source gets the
    same validation), and does not persist anything.
    """

    source_id: str
    source_name: str

    @property
    def capabilities(self) -> SourceCapabilities:  # pragma: no cover - protocol
        ...

    def fetch(self, request: AdapterRequest) -> AdapterResponse:  # pragma: no cover - protocol
        ...


@dataclass
class RequestBudget:
    """The bound on one run's requests: how many, and how fast.

    Time is injected (``now``) so the pacing rule can be tested without waiting, and the budget is
    consumed *before* a request is issued - a request that fails still counted, because the point is to
    bound what leaves this machine, not to bound what succeeds.
    """

    max_requests: int = MAX_REQUESTS_PER_RUN
    min_interval_seconds: float = MIN_SECONDS_BETWEEN_REQUESTS
    issued: int = 0
    last_request_at: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.max_requests, bool) or not isinstance(self.max_requests, int) \
                or self.max_requests < 1:
            raise AdapterError("A request budget must allow at least one request.")
        if self.min_interval_seconds < 0:
            raise AdapterError("The minimum interval between requests cannot be negative.")

    @property
    def remaining(self) -> int:
        """How many requests this run may still issue."""
        return max(0, self.max_requests - self.issued)

    def allow(self, now: datetime) -> None:
        """Consume one request, or raise :class:`BudgetExhausted` saying which bound was reached."""
        if self.remaining <= 0:
            raise BudgetExhausted(
                f"This run has already issued its {self.max_requests} request(s); a run is bounded so it "
                "cannot keep asking a source for more. Start a new run to continue."
            )
        if self.last_request_at is not None and self.min_interval_seconds > 0:
            waited = (now - self.last_request_at).total_seconds()
            if waited < self.min_interval_seconds:
                raise BudgetExhausted(
                    f"This run asked for another page after {waited:.1f}s, and this source is limited to "
                    f"one request every {self.min_interval_seconds:g}s. Nothing was sent; try again later."
                )
        self.issued += 1
        self.last_request_at = now


def call_adapter(adapter: SourceAdapter, request: AdapterRequest, *, now: datetime | None = None,
                 budget: RequestBudget | None = None) -> AdapterResponse:
    """Ask an adapter for one page, translating its failures into the run-outcome taxonomy.

    Nothing is retried here and nothing is swallowed: an exception becomes an outcome that says what kind
    of failure it was, which is what the health view and the run records report. The adapter's own
    exception text is kept as the detail.
    """
    moment = now or datetime.now(timezone.utc)
    if budget is not None:
        budget.allow(moment)
    try:
        response = adapter.fetch(request)
    except TimeoutError as exc:
        return AdapterResponse(
            outcome=RunOutcome.TIMEOUT,
            provenance=_provenance(adapter, request, moment, notes="the request timed out"),
            detail=f"the source did not answer in time: {exc}",
        )
    except (PermissionError, LookupError) as exc:
        # ``PermissionError`` is a refusal to read this data at all; a lookup failure means the adapter
        # could not resolve a name it needs. Neither is a network hiccup and neither is retried.
        return AdapterResponse(
            outcome=RunOutcome.PERMISSION_DENIED,
            provenance=_provenance(adapter, request, moment, notes="the source refused the request"),
            detail=f"the source refused the request: {exc}",
        )
    except (ConnectionError, OSError) as exc:
        return AdapterResponse(
            outcome=RunOutcome.NETWORK_ERROR,
            provenance=_provenance(adapter, request, moment, notes="the connection failed"),
            detail=f"the connection failed: {exc}",
        )
    except ValueError as exc:
        # A response this adapter could not parse is a schema problem on the source's side, the category
        # the taxonomy exists to separate from a transport failure.
        return AdapterResponse(
            outcome=RunOutcome.SCHEMA_ERROR,
            provenance=_provenance(adapter, request, moment, notes="the response could not be read"),
            detail=f"the response could not be read: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 - an unexpected adapter failure is data, not a crash
        return AdapterResponse(
            outcome=RunOutcome.UNKNOWN_ERROR,
            provenance=_provenance(adapter, request, moment, notes="the adapter raised an unexpected error"),
            detail=f"{type(exc).__name__}: {exc}",
        )
    if not isinstance(response, AdapterResponse):
        return AdapterResponse(
            outcome=RunOutcome.SCHEMA_ERROR,
            provenance=_provenance(adapter, request, moment, notes="the adapter returned the wrong shape"),
            detail=(f"the adapter returned {type(response).__name__} instead of an AdapterResponse; the "
                    "framework cannot tell what happened, so it does not claim success."),
        )
    return response


def _provenance(adapter: SourceAdapter, request: AdapterRequest, moment: datetime,
                *, notes: str = "") -> AdapterProvenance:
    """A provenance record for an outcome the framework produced, not the adapter."""
    return AdapterProvenance(
        source_id=getattr(adapter, "source_id", "unknown"), source_name=getattr(adapter, "source_name", "unknown"),
        retrieved_at=moment, request_summary=request.summary(), notes=notes,
    )


def fetch_with_bounded_retries(
    adapter: SourceAdapter, request: AdapterRequest, *, budget: RequestBudget | None = None,
    now: Callable[[], datetime] | None = None, sleep: Callable[[float], None] | None = None,
    max_attempts: int = MAX_RETRY_ATTEMPTS, backoff_seconds: float = RETRY_BACKOFF_SECONDS,
) -> tuple[AdapterResponse, ...]:
    """Fetch one page, retrying only transient outcomes, a bounded number of times.

    Returns every attempt in order, so the caller can record what happened rather than only where it
    ended up. A permission refusal, a schema error or a challenge is *not* retried: repeating them would
    be exactly the behaviour this project refuses - hammering a source that already said no. Waiting is
    injected, so a test proves the backoff schedule without waiting for it.

    A :class:`BudgetExhausted` from the run's own budget *is* raised, deliberately: it is this framework
    refusing to send, not the source failing, and recording it as a source outcome would blame the source
    for our own bound. A caller running a batch is expected to catch it and finish the run as
    ``PARTIAL`` - the requests already made were made, and the run's report says how many.
    """
    clock = now or (lambda: datetime.now(timezone.utc))
    waiter = sleep or (lambda seconds: None)
    if max_attempts < 1:
        raise AdapterError("A bounded retry needs at least one attempt.")
    attempts: list[AdapterResponse] = []
    for attempt in range(1, max_attempts + 1):
        response = call_adapter(adapter, request, now=clock(), budget=budget)
        attempts.append(response)
        if not is_transient(response.outcome) or attempt == max_attempts:
            break
        waiter(backoff_seconds * (2 ** (attempt - 1)))
    return tuple(attempts)


# ---------------------------------------------------------------------------- normalisation

#: The listing fields an adapter's record must carry for the record to become a JobListing. Everything
#: else the domain model allows to be missing, and stays missing.
REQUIRED_RECORD_FIELDS = ("listing_id", "source_listing_url", "employer_name", "role_title")


def normalize_records(
    records: Iterable[Mapping[str, object]],
    provenance: AdapterProvenance,
    *,
    source_id: str,
    source_name: str,
) -> NormalizationReport:
    """Turn raw records into listings, keeping provenance and reporting every rejection.

    The rules are the domain model's own: the required fields must be present and non-empty, the source
    URL must be a real http(s) URL, and values are taken as they are - no employer name is guessed from a
    URL, no availability is assumed, and no experience is inferred from prose. A record that cannot be
    read is rejected with the reason and its index, never dropped quietly and never half-imported.
    """
    accepted: list[JobListing] = []
    rejected: list[RejectedRecord] = []
    for index, record in enumerate(records):
        identifier = _text(record.get("listing_id")) or _text(record.get("source_listing_url"))
        missing = [name for name in REQUIRED_RECORD_FIELDS if not _text(record.get(name))]
        if missing:
            rejected.append(RejectedRecord(
                index=index, identifier=identifier,
                reason="the record does not carry " + ", ".join(missing)))
            continue
        url = _text(record["source_listing_url"])
        try:
            canonical = _validated_url(url)
        except ValueError as exc:
            rejected.append(RejectedRecord(
                index=index, identifier=identifier,
                reason=f"its source URL is not a usable http(s) link ({exc})"))
            continue
        try:
            listing = JobListing(
                listing_id=_text(record["listing_id"]),
                source_id=source_id,
                source_name=source_name,
                source_listing_url=canonical,
                employer_name=_text(record["employer_name"]),
                role_title=_text(record["role_title"]),
                employer_apply_url=_optional_text(record.get("employer_apply_url")),
                canonical_requisition_id=_optional_text(record.get("canonical_requisition_id")),
                location_text=_optional_text(record.get("location_text")),
                work_mode=_optional_text(record.get("work_mode")),
                role_type=_optional_text(record.get("role_type")),
                required_skills=frozenset(_text_list(record.get("required_skills"))),
                provenance_note=f"retrieved {provenance.retrieved_at.isoformat()} "
                                f"({provenance.source_id}, {provenance.request_summary})",
            )
        except ValueError as exc:
            rejected.append(RejectedRecord(
                index=index, identifier=identifier,
                reason=f"it is not a listing this application can store ({exc})"))
            continue
        accepted.append(listing)
    within, merged_within = _deduplicate(accepted)
    return NormalizationReport(accepted=within, rejected=tuple(rejected),
                               merged_within_source=merged_within)


def _validated_url(url: str) -> str:
    """The canonical form of a source URL, or a :class:`ValueError` explaining why it is not one.

    The rest of the app sorts and compares URLs freely, so an adapter record that is not an http(s) link
    has to be stopped here - otherwise a file path or a fragment of prose would be stored as the place a
    listing came from.
    """
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if parts.scheme.casefold() not in ("http", "https") or not (parts.hostname or "").strip():
        raise ValueError(f"{url!r} is not an http(s) address with a host name")
    return canonicalize_url(url)


def _deduplicate(listings: Sequence[JobListing]) -> tuple[tuple[JobListing, ...], tuple[tuple[str, str], ...]]:
    """Keep one listing per canonical identity; report what was merged into what."""
    kept = deduplicate_listings(listings)
    representative = {duplicate_key(item): item for item in kept}
    merged = tuple(
        (representative[duplicate_key(item)].listing_id, item.listing_id)
        for item in listings if representative.get(duplicate_key(item)) not in (None, item)
    )
    return kept, merged


def merge_across_sources(
    batches: Mapping[str, Sequence[JobListing]],
) -> NormalizationReport:
    """Combine several sources' listings, keeping the first of each duplicate and reporting the merge.

    The first batch in the mapping's order wins, which makes the outcome deterministic; every duplicate is
    reported with the listing that was kept *and* the source it came from, so the merge is visible rather
    than silent. Nothing about the lost copy is discarded silently: the record of the merge is what tells a
    person that two sources offered the same job.
    """
    everything: list[JobListing] = []
    for listings in batches.values():
        everything.extend(listings)
    kept = deduplicate_listings(everything)
    kept_ids = {listing.listing_id for listing in kept}
    merged: list[tuple[str, str]] = []
    for listing in everything:
        if listing.listing_id in kept_ids:
            continue
        winner = next((item for item in kept if duplicate_key(item) == duplicate_key(listing)), None)
        if winner is not None:
            merged.append((f"{winner.listing_id} ({winner.source_id})",
                           f"{listing.listing_id} ({listing.source_id})"))
    return NormalizationReport(accepted=kept, rejected=(), merged_across_sources=tuple(merged))


def _text(value: object) -> str:
    """One non-empty string from a record, or ``""`` when the value is absent or blank."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _text_list(value: object) -> tuple[str, ...]:
    """A list of non-empty strings; a scalar string is accepted as a one-item list."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (_text(value),) if _text(value) else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(text for text in (_text(item) for item in value) if text)
    return ()


# ---------------------------------------------------------------------------- health

@dataclass(frozen=True)
class SourceHealth:
    """What the last runs of one source actually did.

    ``status`` is one of success, empty, partial, failed or disabled, and the four working states are kept
    apart on purpose: an empty result is a working source with nothing today, a partial result is a run
    that could not finish, and a disabled source has not run at all. Collapsing them is how a product ends
    up telling somebody their job search is fine when the source has been refused for a week.
    """

    source_id: str
    status: str
    last_outcome: RunOutcome | None
    last_run_at: datetime | None
    listing_count: int = 0
    rejected_count: int = 0
    detail: str = ""

    def describe(self) -> str:
        """One line a person can read, with the counts that make the status checkable."""
        when = self.last_run_at.isoformat() if self.last_run_at else "never"
        detail = f" - {self.detail}" if self.detail else ""
        return (f"{self.source_id}: {self.status}; last run {when}; {self.listing_count} listing(s), "
                f"{self.rejected_count} rejected{detail}")


def health_from_response(source_id: str, response: AdapterResponse, *,
                         report: NormalizationReport | None = None) -> SourceHealth:
    """Health from one run's response (and its normalisation, when there is one)."""
    if response.outcome is RunOutcome.SUCCESS_WITH_RESULTS:
        status = "success"
    elif response.outcome is RunOutcome.SUCCESS_EMPTY:
        status = "empty"
    elif is_partial(response.outcome):
        status = "partial"
    else:
        status = "failed"
    return SourceHealth(
        source_id=source_id, status=status, last_outcome=response.outcome,
        last_run_at=response.provenance.retrieved_at,
        listing_count=len(report.accepted) if report is not None else len(response.records),
        rejected_count=report.rejected_count if report is not None else 0,
        detail=response.detail,
    )


def disabled_health(source_id: str, reason: str) -> SourceHealth:
    """The health line for a source that is not permitted to run: nothing was tried, and it says so."""
    return SourceHealth(source_id=source_id, status="disabled", last_outcome=None, last_run_at=None,
                        detail=reason)


# ---------------------------------------------------------------------------- the registry

class AdapterRegistry:
    """The only sanctioned way to run an adapter, because it is where the gate is enforced.

    :meth:`execute` checks the source's discovery gate first and raises :class:`SourceDisabled` when it is
    closed, *before* the adapter is called. That is why no adapter in this build can reach a network: the
    gate is closed for every registered source. It also means the framework can be fully tested - with
    fixture adapters called directly - while the app's own path stays shut.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter, *, replace: bool = False) -> None:
        """Add an adapter for its source id; re-registering needs ``replace=True``, so typos show up."""
        source_id = getattr(adapter, "source_id", None)
        if not isinstance(source_id, str) or not source_id.strip():
            raise AdapterError("An adapter must name the source it serves.")
        if not callable(getattr(adapter, "fetch", None)):
            raise AdapterError(f"The adapter for {source_id} has no fetch method.")
        if source_id in self._adapters and not replace:
            raise AdapterError(f"An adapter for {source_id} is already registered.")
        self._adapters[source_id] = adapter

    def get(self, source_id: str) -> SourceAdapter | None:
        """The adapter for a source id, or ``None``."""
        return self._adapters.get(str(source_id))

    def source_ids(self) -> tuple[str, ...]:
        """Every registered source id, in a stable order."""
        return tuple(sorted(self._adapters))

    def capabilities(self, source_id: str) -> SourceCapabilities | None:
        """What the registered adapter for a source declares it can do."""
        adapter = self.get(source_id)
        return None if adapter is None else adapter.capabilities

    def execute(self, source_id: str, request: AdapterRequest, *,
                budget: RequestBudget | None = None, now: datetime | None = None,
                policy: GlobalPolicy | None = None, done_today: int | None = None,
                subject: PolicySubject | None = None) -> AdapterResponse:
        """Run one bounded request through the gate and the standing authorisation.

        Five refusals are possible, and each is raised rather than reported as a source outcome, because
        none of them is the source's fault:

        * no adapter is registered for that source id (a framework gap, not a source failure);
        * the registered adapter does not declare discovery capability;
        * the source's discovery gate is closed;
        * no standing authorisation was supplied, or the one supplied does not cover this source;
        * an authorisation was supplied without today's count, so its daily limit cannot be honoured.

        The authorisation is checked **immediately before the call**, after the gate, and it is checked
        with ``source_gate_allows`` set from the gate's own answer, so the two can only ever agree to
        permit - a policy cannot open a gate. The last two refusals are the fail-closed half: a caller
        that forgets the ``policy`` argument gets a refusal, never a run, and a caller that cannot say how
        many of today's actions already happened cannot be given a sixth one under a limit of five.

        There is deliberately **no parameter to open the gate here.** The recorded state is the only
        state this method consults, because - measured today - forcing
        :data:`career_agent.sources.SOURCE_QUALITY_GATE_PASSED` open would enable exactly one source
        (``jobicy``: approved and selected for use). The whole "nothing runs" property therefore rests on
        that one constant, and a bypass parameter in the adapter layer would make it two places to get
        wrong instead of one. The tests that exercise the gate machinery call
        :func:`career_agent.sources.discovery_gate` directly.
        """
        adapter = self.get(source_id)
        if adapter is None:
            raise AdapterError(
                f"No adapter is registered for {source_id}, so nothing could be fetched. Registered: "
                f"{', '.join(self.source_ids()) or 'none'}."
            )
        if not adapter.capabilities.discovery:
            raise SourceDisabled(
                f"The adapter for {source_id} does not declare discovery capability, so it was not run."
            )
        gate = discovery_gate(source_id)
        if not gate.allowed:
            raise SourceDisabled(
                f"Discovery for {source_id} is not permitted, so no request was made. {gate.reason}"
            )
        if policy is not None and done_today is None:
            raise SourceDisabled(
                f"Discovery for {source_id} is not authorised, so no request was made. An authorisation "
                f"was supplied without a count of today's discovery runs, and a daily limit cannot be "
                f"honoured without one."
            )
        moment = now or datetime.now(timezone.utc)
        decision = evaluate_policy(
            policy if policy is not None else no_authorisation(),
            source_id=source_id, action=ActionKind.DISCOVERY, now=moment,
            done_today=done_today or 0, source_gate_allows=gate.allowed, subject=subject)
        if not decision.allowed:
            raise SourceDisabled(
                f"Discovery for {source_id} is not authorised, so no request was made. "
                f"{decision.describe()}"
            )
        return call_adapter(adapter, request, now=now, budget=budget)

    def health(self, *, now: datetime | None = None) -> tuple[SourceHealth, ...]:
        """One health line per registered source, without running anything.

        Unregistered-but-known sources are the framework's blind spot by design: a source that is not in
        the registry has no adapter and therefore no runs to report.
        """
        moment = now or datetime.now(timezone.utc)
        lines: list[SourceHealth] = []
        for source_id in self.source_ids():
            gate = discovery_gate(source_id)
            if not gate.allowed:
                lines.append(disabled_health(source_id, gate.reason))
            else:
                lines.append(SourceHealth(
                    source_id=source_id, status="enabled", last_outcome=None,
                    last_run_at=moment, detail="permitted to run, but no run has been recorded yet"))
        return tuple(lines)


@dataclass(frozen=True)
class FixtureAdapter:
    """An adapter that replays fixed records: the shape a real one must have, with no network.

    It exists so the framework's own rules - validation, provenance, deduplication, retries, budgets - can
    be tested exactly, and so a future adapter has a working example to copy. It refuses to be used
    anywhere that looks live: every response is marked with the fixture's own provenance, and the registry
    still refuses to run it while the gate is closed.
    """

    source_id: str
    source_name: str
    records: tuple[Mapping[str, object], ...] = ()
    outcome: RunOutcome = RunOutcome.SUCCESS_WITH_RESULTS
    detail: str = ""
    next_page_token: str | None = None
    failure: str = ""  #: "timeout", "network", "permission", "schema" or "unexpected": raise instead
    capabilities: SourceCapabilities = field(default_factory=lambda: SourceCapabilities(discovery=True))
    calls: list[AdapterRequest] = field(default_factory=list, compare=False)

    def fetch(self, request: AdapterRequest) -> AdapterResponse:
        """Replay the configured answer, raising the configured failure when one is asked for."""
        self.calls.append(request)
        moment = datetime.now(timezone.utc)
        provenance = AdapterProvenance(
            source_id=self.source_id, source_name=self.source_name, retrieved_at=moment,
            request_summary=request.summary(), adapter_version="fixture",
            notes="synthetic fixture records; no network request was made",
        )
        if self.failure == "timeout":
            raise TimeoutError("the fixture was told to time out")
        if self.failure == "network":
            raise ConnectionError("the fixture was told to fail to connect")
        if self.failure == "permission":
            raise PermissionError("the fixture was told to refuse")
        if self.failure == "schema":
            raise ValueError("the fixture was told to return something unreadable")
        if self.failure == "unexpected":
            raise RuntimeError("the fixture was told to fail unexpectedly")
        if self.outcome is RunOutcome.SUCCESS_EMPTY:
            return AdapterResponse(outcome=self.outcome, provenance=provenance, detail=self.detail)
        if self.outcome is RunOutcome.SUCCESS_WITH_RESULTS and not self.records:
            # Keep the fixture honest about the framework's own rule rather than working around it.
            return AdapterResponse(outcome=RunOutcome.SUCCESS_EMPTY, provenance=provenance,
                                   detail=self.detail or "the fixture holds no records")
        return AdapterResponse(
            outcome=self.outcome, provenance=provenance, records=self.records,
            next_page_token=self.next_page_token, detail=self.detail,
        )


def default_registry() -> AdapterRegistry:
    """The adapters this build knows about: none.

    That is not an omission. Every source in :data:`career_agent.sources.SOURCE_DECISIONS` is either
    blocked, pending clarification or rejected, and the quality gate has not passed, so there is nothing
    an adapter could legally fetch. The framework is complete; the permissions are not.
    """
    return AdapterRegistry()
