"""Background tasks: what is scheduled, when it should run, and what happened when it did.

This module is the domain half of the local scheduler, and it holds no SQLite code and no network
code: a task definition and its schedule (:class:`ScheduledTask`), the arithmetic that turns a
schedule into the next instant it should run (:func:`next_run_after`), the identity of one scheduled
occurrence (:func:`slot_key`), how a failure is retried (:func:`retry_delay_seconds` and
:func:`plan_after_run`), and the states a run moves through (:class:`RunState`). Persistence and the
claiming of work live in :mod:`career_agent.store`; the loop that executes handlers lives in
:mod:`career_agent.worker`.

Three decisions are worth stating plainly, because they are the difference between a scheduler that
can be trusted with a person's machine and one that cannot:

**A run is identified by its scheduled instant, not by when it happened.** Every occurrence of a task
gets a *slot* - the UTC instant the schedule says it was due - and the run that serves it is keyed by
``(task, slot, attempt)``. A process that restarts, a clock that jumps, or a retry after a crash
therefore cannot silently produce a second run for the same occurrence, and cannot lose one either:
the scheduled occurrence exists independently of any process that might serve it.

**Times are wall-clock times in a named zone, and a DST gap is skipped rather than moved.** ``00:00``
and ``12:00`` in ``Asia/Kolkata`` mean those times on the person's clock - that is the whole point of
the default (:data:`DEFAULT_TIMEZONE`, and the cadence confirmed for this product). The arithmetic
below works in the task's own zone and converts to UTC only for storage, so a machine whose own clock
zone differs from the task's cannot move the run. When a local time does not exist on a given day
(the spring-forward gap), that occurrence is skipped for that day instead of being moved to a
neighbouring time: running a job an hour earlier or later than the person chose would be a silent
change to their schedule. When a local time occurs twice (the autumn overlap), the first occurrence is
used and the second is not - the same rule that keeps one occurrence per day, which is what stops a
daily task from running twice that day.

**Retries are bounded, spread out, and belong to the same occurrence.** An attempt that fails is
retried with exponential backoff up to the task's attempt limit; once the attempts are used up the
task goes back to its ordinary schedule, and the failure stays in the run history rather than being
retried forever or disappearing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, time as clock_time, timedelta, timezone
from enum import Enum
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: The cadence this product is built around: midnight and noon on the person's clock. The timezone is
#: named rather than taken from the machine, so the schedule does not move when the machine does.
DEFAULT_SCHEDULE_TIMES = ("00:00", "12:00")
DEFAULT_TIMEZONE = "Asia/Kolkata"

#: Bounds. A task that asks for more than these is refused at the boundary rather than clamped
#: silently, because a schedule the person did not choose is worse than an error message.
MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 3600
MIN_ATTEMPTS = 1
MAX_ATTEMPTS = 5
MAX_BACKOFF_SECONDS = 3600

#: How many days ahead :func:`next_run_after` will look for an occurrence before giving up. A daily
#: schedule with any time in it always has an occurrence within a day or two (a DST gap can skip one
#: day for a time that falls inside the gap); the cap only exists so a caller cannot loop forever.
_MAX_DAYS_AHEAD = 8

#: The UTC tzinfo under a name no parameter shadows. ``build_task`` takes a parameter called
#: ``timezone`` (the task's zone name, a string), which hides the ``datetime.timezone`` class inside
#: that function - so ``timezone.utc`` there is an attribute lookup on a string, and the first thing it
#: broke was reading the clock.
_UTC = timezone.utc

_TIME_PATTERN = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")

#: One line of run detail or error text, kept short and single-line. The database and the event log
#: both show these, so a multi-line or unbounded value would let a handler reshape a log line.
MAX_DETAIL_LENGTH = 300


class TaskValidationError(ValueError):
    """A task definition is not something this build can schedule.

    Raised at the storage boundary and wherever a task is built by hand, so a bad schedule is a
    message rather than a task that quietly never runs. Nothing is stored when this is raised.
    """


class RunState(str, Enum):
    """Where one attempt of one occurrence is.

    The distinction that matters is between the states that are somebody's problem and the states that
    are not. ``REFUSED`` means the action was deliberately not performed - a rule said no, which is
    the scheduler working correctly (a closed source-quality gate, for instance); ``FAILED`` and
    ``TIMED_OUT`` mean the attempt was carried out and did not work; ``INTERRUPTED`` means no result
    was observed at all, because the process stopped while the attempt was in flight. Reporting a
    refusal as a failure, or an interruption as a success, would each be a lie about what happened.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    REFUSED = "refused"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    INTERRUPTED = "interrupted"

    @property
    def is_terminal(self) -> bool:
        """Whether this state ends the attempt (nothing will change it again)."""
        return self not in (RunState.PENDING, RunState.RUNNING)

    @property
    def counts_as_failure(self) -> bool:
        """Whether this outcome should count against the task's attempt budget.

        A refusal does not: the rule that refused it will refuse it again, so retrying would only
        repeat a decision, and counting it would eventually disable a task that is behaving exactly as
        designed. An interruption does, because an attempt that never finished is an attempt that has
        not yet had its chance.
        """
        return self in (RunState.FAILED, RunState.TIMED_OUT, RunState.INTERRUPTED)


class HandlerOutcome(str, Enum):
    """What a handler is allowed to say happened.

    A handler cannot report success by returning nothing: it returns one of these, and a handler that
    stops early because it was asked to stop reports ``STOPPED``. That is the difference between
    "finished the work" and "gave up when told to", and the run history keeps them apart. Anything a
    handler raises becomes ``FAILED`` with the exception text, so a handler cannot turn an error into
    a success by describing it as one.
    """

    SUCCEEDED = "succeeded"
    REFUSED = "refused"
    STOPPED = "stopped"


@dataclass(frozen=True)
class HandlerResult:
    """What a handler returns: an outcome plus one line a person can read."""

    outcome: HandlerOutcome
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, HandlerOutcome):
            raise TaskValidationError("A handler result must carry a HandlerOutcome.")
        object.__setattr__(self, "detail", clean_detail(self.detail))


def clean_detail(value: object) -> str:
    """One bounded single-line piece of text, safe to store and to show in a log line.

    Control characters (including newlines) become spaces and the result is capped, so a handler's
    message cannot forge a second log line or grow a database row without bound. The same treatment
    the event log applies is applied here first, at the point the text enters the task tables.
    """
    text = "" if value is None else str(value)
    flattened = " ".join(part for part in text.split())
    if len(flattened) > MAX_DETAIL_LENGTH:
        flattened = flattened[:MAX_DETAIL_LENGTH].rstrip() + "... (truncated)"
    return flattened


def parse_time(value: str) -> clock_time:
    """``"HH:MM"`` (24-hour) as a :class:`datetime.time`, or a message saying what was wrong."""
    if not isinstance(value, str) or not _TIME_PATTERN.match(value):
        raise TaskValidationError(
            f"{value!r} is not a time of day. Use 24-hour HH:MM, for example 00:00 or 12:00."
        )
    return clock_time(int(value[:2]), int(value[3:]))


def zone_for(name: str) -> ZoneInfo:
    """The named zone, or a message naming the problem.

    A missing zone database is a real possibility on Windows, where the standard library has no copy
    of the tzdata rules: the message says so and names the fix rather than falling back to UTC, which
    would move every scheduled run without telling anyone.
    """
    if not isinstance(name, str) or not name.strip():
        raise TaskValidationError("A task needs a timezone name, for example Asia/Kolkata.")
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TaskValidationError(
            f"The timezone {name!r} is not available on this machine, so the task cannot be "
            "scheduled. Use an IANA name such as Asia/Kolkata; on Windows the timezone database comes "
            "from the tzdata package (pip install tzdata)."
        ) from exc


def validate_times(values: Iterable[str]) -> tuple[str, ...]:
    """Validate a schedule's times; return them parsed, de-duplicated and in clock order.

    De-duplicating is deliberate: two identical entries would otherwise mean two attempts at the same
    instant, which reads as a retry but is not one.
    """
    if isinstance(values, str):
        raise TaskValidationError(
            "A schedule's times must be a sequence of HH:MM values, not a single string."
        )
    seen: set[str] = set()
    for value in values:
        parse_time(value)  # raises with the offending value named
        seen.add(value)
    if not seen:
        raise TaskValidationError(
            "A task needs at least one time of day, for example 00:00 and 12:00."
        )
    return tuple(sorted(seen))


def _validate_identifier(value: str, *, noun: str, pattern: re.Pattern[str], example: str) -> str:
    if not isinstance(value, str) or not pattern.match(value):
        raise TaskValidationError(
            f"{noun} {value!r} is not usable. Use lower-case letters, digits, dots, dashes or "
            f"underscores, starting with a letter or digit, up to 64 characters (for example {example})."
        )
    return value


def _validate_bounded_int(value: object, *, noun: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TaskValidationError(f"{noun} must be a whole number, not {value!r}.")
    if not low <= value <= high:
        raise TaskValidationError(f"{noun} must be between {low} and {high}, not {value}.")
    return value


def validate_utc_instant(value: datetime | None, *, noun: str) -> datetime | None:
    """An aware instant, normalised to UTC; ``None`` stays ``None``.

    A naive datetime is refused rather than assumed to be UTC: a stored instant with no zone is how a
    schedule written on one machine starts running at the wrong time on another.
    """
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TaskValidationError(f"{noun} must be a datetime, not {value!r}.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise TaskValidationError(
            f"{noun} must carry a timezone offset; a value without one cannot be scheduled. "
            f"Use datetime.now(timezone.utc) or an aware datetime converted with astimezone()."
        )
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ScheduledTask:
    """One task definition: what to run, and when on whose clock.

    The definition fields are what a person sets; the bookkeeping fields (``next_run_at`` and the
    ``pending_*`` pair, ``last_*``, ``consecutive_failures``) are what the scheduler maintains. They
    live in one object because they are stored in one row, and they are separated in this docstring
    because only the first group may be set by hand.
    """

    task_id: str
    name: str
    kind: str
    times: tuple[str, ...]
    timezone: str = DEFAULT_TIMEZONE
    enabled: bool = True
    timeout_seconds: int = 300
    max_attempts: int = 3
    retry_backoff_seconds: int = 60
    next_run_at: datetime | None = None
    pending_slot_at: datetime | None = None
    pending_attempt: int | None = None
    last_run_at: datetime | None = None
    last_outcome: RunState | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _validate_identifier(
            self.task_id, noun="A task id", pattern=_IDENTIFIER_PATTERN, example="discovery-run"))
        if not isinstance(self.name, str) or not self.name.strip():
            raise TaskValidationError("A task needs a name to show in the scheduler.")
        if len(self.name) > 120:
            raise TaskValidationError("A task name must be at most 120 characters.")
        object.__setattr__(self, "kind", _validate_identifier(
            self.kind, noun="A task kind", pattern=_KIND_PATTERN, example="backup.snapshot"))
        object.__setattr__(self, "times", validate_times(self.times))
        zone_for(self.timezone)
        if not isinstance(self.enabled, bool):
            raise TaskValidationError("enabled must be True or False.")
        object.__setattr__(self, "timeout_seconds", _validate_bounded_int(
            self.timeout_seconds, noun="The timeout in seconds",
            low=MIN_TIMEOUT_SECONDS, high=MAX_TIMEOUT_SECONDS))
        object.__setattr__(self, "max_attempts", _validate_bounded_int(
            self.max_attempts, noun="The number of attempts", low=MIN_ATTEMPTS, high=MAX_ATTEMPTS))
        object.__setattr__(self, "retry_backoff_seconds", _validate_bounded_int(
            self.retry_backoff_seconds, noun="The retry delay in seconds",
            low=0, high=MAX_BACKOFF_SECONDS))
        object.__setattr__(self, "consecutive_failures", _validate_bounded_int(
            self.consecutive_failures, noun="The consecutive-failure count", low=0, high=1_000_000))
        for noun, value in (("next_run_at", self.next_run_at),
                            ("pending_slot_at", self.pending_slot_at),
                            ("last_run_at", self.last_run_at),
                            ("created_at", self.created_at),
                            ("updated_at", self.updated_at)):
            object.__setattr__(self, noun, validate_utc_instant(value, noun=f"the task's {noun}"))
        if self.pending_slot_at is None:
            object.__setattr__(self, "pending_attempt", None)
        else:
            attempt = self.pending_attempt
            if attempt is None:
                raise TaskValidationError(
                    "A task with an unfinished occurrence must record which attempt is next."
                )
            object.__setattr__(self, "pending_attempt", _validate_bounded_int(
                attempt, noun="The pending attempt number", low=1, high=MAX_ATTEMPTS))
        if self.last_outcome is not None and not isinstance(self.last_outcome, RunState):
            try:
                object.__setattr__(self, "last_outcome", RunState(self.last_outcome))
            except ValueError as exc:
                raise TaskValidationError(
                    f"{self.last_outcome!r} is not an outcome this build recognises."
                ) from exc
        if self.last_outcome is not None and not self.last_outcome.is_terminal:
            raise TaskValidationError(
                f"A task's last outcome must be a finished one, not {self.last_outcome.value!r}."
            )
        object.__setattr__(self, "last_error", clean_detail(self.last_error) or None)

    @property
    def zone(self) -> ZoneInfo:
        """The task's zone, resolved on demand (the name is what is stored)."""
        return zone_for(self.timezone)

    @property
    def retry_pending(self) -> bool:
        """Whether the task is holding a scheduled occurrence that still has attempts left."""
        return self.pending_slot_at is not None

    def with_definition(self, **changes: object) -> "ScheduledTask":
        """A copy with definition fields changed and the bookkeeping recomputed by the caller."""
        return replace(self, **changes)


def slot_key(task_id: str, slot_at: datetime) -> str:
    """The stable name of one scheduled occurrence: the task plus the instant it was due.

    This is the idempotency key. Two workers, a retry after a crash, and a restart all arrive at the
    same string for the same occurrence, and the database's uniqueness constraint on
    ``(task, slot, attempt)`` is what turns that into "exactly one run per occurrence and attempt".
    """
    return f"{task_id}@{validate_utc_instant(slot_at, noun='A slot instant').isoformat()}"


def next_run_after(
    task: ScheduledTask | Mapping[str, object], now: datetime, *, inclusive: bool = False,
) -> datetime | None:
    """The first occurrence strictly after ``now`` (or at ``now`` when ``inclusive``), in UTC.

    The search happens in the task's zone and each candidate is converted to UTC before it is compared,
    so a machine in another zone, a machine whose clock has just been corrected, or a task scheduled
    for a zone that is currently in a DST transition all resolve to the same instant. Candidates that
    do not exist on their local day (the spring-forward gap) are skipped, and for a local time that
    occurs twice the first occurrence is the one returned - see the module docstring for why.
    """
    if isinstance(task, Mapping):
        times = validate_times(task["times"])  # type: ignore[arg-type]
        zone = zone_for(str(task["timezone"]))
    else:
        times = task.times
        zone = task.zone
    moment = validate_utc_instant(now, noun="The reference time")
    assert moment is not None  # validate_utc_instant only returns None for None input
    day = moment.astimezone(zone).date()
    for offset in range(_MAX_DAYS_AHEAD):
        for candidate in _occurrences_on(day + timedelta(days=offset), times, zone):
            if candidate > moment or (inclusive and candidate == moment):
                return candidate
    return None


def _occurrences_on(day: date, times: tuple[str, ...], zone: ZoneInfo) -> tuple[datetime, ...]:
    """The instants on ``day`` in ``zone`` that match ``times``, in order, gaps skipped."""
    found: list[datetime] = []
    for value in times:
        wanted = parse_time(value)
        candidate = datetime.combine(day, wanted, tzinfo=zone)
        # A local time inside the spring-forward gap is not a real time on that day. Python still
        # builds a datetime for it (with the offset it would have had), so it is checked by asking
        # what the clock reads at that instant; a gap produces a different reading.
        if candidate.astimezone(timezone.utc).astimezone(zone).timetz().replace(tzinfo=None) != wanted:
            continue
        found.append(candidate.astimezone(timezone.utc))
    return tuple(sorted(found))


def retry_delay_seconds(task: ScheduledTask, attempt: int) -> int:
    """How long to wait before attempt ``attempt`` + 1, bounded by the task's own ceiling.

    Exponential, capped, and never longer than one hour even when the task asks for a long base delay:
    a task that has failed once should be retried soon enough that the person sees the outcome in the
    same session it was scheduled for, and the attempt limit is what stops the retrying.
    """
    _validate_bounded_int(attempt, noun="The attempt number", low=1, high=MAX_ATTEMPTS)
    if attempt >= task.max_attempts:
        return 0
    delay = task.retry_backoff_seconds * (2 ** (attempt - 1))
    return int(min(delay, MAX_BACKOFF_SECONDS))


@dataclass(frozen=True)
class ScheduleUpdate:
    """What finishing a run does to the task's bookkeeping."""

    next_run_at: datetime
    pending_slot_at: datetime | None
    pending_attempt: int | None
    consecutive_failures: int
    last_outcome: RunState


def plan_after_run(
    task: ScheduledTask, outcome: RunState, attempt: int, slot_at: datetime, now: datetime,
) -> ScheduleUpdate:
    """Decide the task's next state after one attempt finished.

    The rule, in one place so both the worker and crash recovery use it:

    * ``SUCCEEDED`` or ``REFUSED`` finishes the occurrence. The task returns to its ordinary schedule,
      and only a real failure counts towards disabling a task.
    * A failure with attempts left keeps the *same* occurrence (``pending_slot_at``) and comes back
      after :func:`retry_delay_seconds`, so a retry serves the scheduled instant it owes rather than
      replacing it with a later one.
    * A failure with no attempts left gives up on that occurrence, keeps the failure visible in the
      task's ``last_outcome``/``last_error`` and in the run history, and returns to the ordinary
      schedule - the next scheduled instant still runs, because one bad occurrence is not a reason to
      stop a task forever.
    """
    if not isinstance(outcome, RunState) or not outcome.is_terminal:
        raise TaskValidationError("Only a finished run can plan a task's next state.")
    moment = validate_utc_instant(now, noun="The reference time")
    assert moment is not None
    slot = validate_utc_instant(slot_at, noun="The scheduled instant")
    assert slot is not None
    failures = task.consecutive_failures + (1 if outcome.counts_as_failure else 0)
    if outcome.counts_as_failure and attempt < task.max_attempts:
        delay = retry_delay_seconds(task, attempt)
        return ScheduleUpdate(
            next_run_at=moment + timedelta(seconds=delay),
            pending_slot_at=slot,
            pending_attempt=attempt + 1,
            consecutive_failures=failures,
            last_outcome=outcome,
        )
    following = next_run_after(task, moment)
    if following is None:
        # A schedule with no times cannot exist (``validate_times`` refuses it), so this is unreachable
        # for a valid task; raising rather than storing a null keeps "next run" always answerable.
        raise TaskValidationError(
            f"No further run could be scheduled for task {task.task_id!r}; its schedule has no times."
        )
    return ScheduleUpdate(
        next_run_at=following,
        pending_slot_at=None,
        pending_attempt=None,
        consecutive_failures=failures,
        last_outcome=outcome,
    )


@dataclass(frozen=True)
class TaskRun:
    """One attempt at one scheduled occurrence, as stored."""

    run_id: str
    task_id: str
    slot_key: str
    slot_at: datetime
    attempt: int
    state: RunState
    timeout_seconds: int
    worker_id: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None
    detail: str = ""
    error: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.task_id, noun="A task id", pattern=_IDENTIFIER_PATTERN,
                             example="discovery-run")
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise TaskValidationError("A run needs an id.")
        if not isinstance(self.slot_key, str) or not self.slot_key.strip():
            raise TaskValidationError("A run needs the scheduled occurrence it serves.")
        object.__setattr__(self, "slot_at", validate_utc_instant(self.slot_at, noun="The scheduled instant"))
        object.__setattr__(self, "attempt", _validate_bounded_int(
            self.attempt, noun="The attempt number", low=1, high=MAX_ATTEMPTS))
        if not isinstance(self.state, RunState):
            try:
                object.__setattr__(self, "state", RunState(self.state))
            except ValueError as exc:
                raise TaskValidationError(
                    f"{self.state!r} is not a run state this build recognises."
                ) from exc
        object.__setattr__(self, "timeout_seconds", _validate_bounded_int(
            self.timeout_seconds, noun="The timeout in seconds",
            low=MIN_TIMEOUT_SECONDS, high=MAX_TIMEOUT_SECONDS))
        for noun in ("created_at", "started_at", "finished_at", "heartbeat_at"):
            object.__setattr__(self, noun, validate_utc_instant(getattr(self, noun), noun=f"the run's {noun}"))
        if self.worker_id is not None and (not isinstance(self.worker_id, str) or not self.worker_id.strip()):
            raise TaskValidationError("A run's worker id must be a non-empty name when it is set.")
        object.__setattr__(self, "detail", clean_detail(self.detail))
        object.__setattr__(self, "error", clean_detail(self.error) or None)

    @property
    def duration_seconds(self) -> float | None:
        """How long the attempt took, when both ends are known; ``None`` until it finishes."""
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


@dataclass(frozen=True)
class WorkerLease:
    """Proof that one worker owns the right to execute scheduled tasks for a database.

    Held for a named period and refreshed by a heartbeat. A worker that starts while another's lease is
    fresh refuses to run (two schedulers over one database would each run the other's work); a worker
    that starts while the lease is stale takes it over, because the previous holder is gone and the
    alternative is a database that can never be scheduled again.
    """

    lease_name: str
    worker_id: str
    acquired_at: datetime
    heartbeat_at: datetime

    def __post_init__(self) -> None:
        for noun in ("acquired_at", "heartbeat_at"):
            object.__setattr__(self, noun, validate_utc_instant(getattr(self, noun), noun=f"the lease's {noun}"))
        if not isinstance(self.worker_id, str) or not self.worker_id.strip():
            raise TaskValidationError("A worker lease must name the worker holding it.")


class WorkerLeaseHeld(RuntimeError):
    """Another worker holds the lease for this database, and its heartbeat is recent."""

    def __init__(self, lease: WorkerLease) -> None:
        self.lease = lease
        super().__init__(
            f"Another worker ({lease.worker_id}) is already scheduled for this database; its last "
            f"heartbeat was {lease.heartbeat_at.isoformat()}. Two schedulers over one database would "
            "each run the other's work, so this worker stopped instead. Stop the other worker, or wait "
            "until its heartbeat goes stale, and start this one again."
        )


def build_task(
    task_id: str, name: str, kind: str, *, times: Iterable[str] | None = None,
    timezone: str = DEFAULT_TIMEZONE, enabled: bool = True, timeout_seconds: int = 300,
    max_attempts: int = 3, retry_backoff_seconds: int = 60, now: datetime | None = None,
) -> ScheduledTask:
    """A scheduled task with its first occurrence computed from ``now`` (default: the real clock).

    Kept here rather than in the worker so that the desktop, the command line and the tests build a
    task the same way - and so that a task can be constructed and inspected without a database.
    """
    moment = validate_utc_instant(now or datetime.now(_UTC), noun="The reference time")
    assert moment is not None
    task = ScheduledTask(
        task_id=task_id, name=name, kind=kind,
        times=validate_times(DEFAULT_SCHEDULE_TIMES if times is None else times),
        timezone=timezone, enabled=enabled, timeout_seconds=timeout_seconds,
        max_attempts=max_attempts, retry_backoff_seconds=retry_backoff_seconds,
    )
    if not task.enabled:
        return task
    return replace(task, next_run_at=next_run_after(task, moment))
