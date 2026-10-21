"""Phase 5: Scheduler module.

Implements reliable scheduling for the AI Career Agent desktop application.

Provides timezone-aware scheduling, missed-run recovery, duplicate prevention,
and bounded retries for job application workflows.

Does not pretend that jobs run when the application is closed unless a
verified external worker exists.
"""

from __future__ import annotations

import calendar
import time
import zoneinfo
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from .store import CareerStore


class SchedulerStatus(str, Enum):
    """Status of a scheduled job execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _expand_cron_field(
    expr: str,
    low: int,
    high: int,
    names: tuple[str, ...] | None = None,
) -> set[int]:
    """Expand one cron-style field into the set of matching values.

    Supports literal values, ``*``/``?``, ranges ``a-b``, steps ``*/n``
    and ``a-b/n``, comma-separated lists, and (when ``names`` is given)
    names such as ``jan``/``mon`` matched case-insensitively. Reverse
    (wrapping) ranges like ``6-1`` cover Saturday through Monday, and the
    standard cron numbering applies to weekday fields:
    0 and 7 mean Sunday, 1 Monday ... 6 Saturday.
    """
    span = high - low + 1
    values: set[int] = set()

    for part in expr.split(","):
        part = part.strip().lower()
        if part in ("*", "?", ""):
            values.update(range(low, high + 1))
            continue

        # Named value (jan/mon), optionally at the start of a range
        if names is not None and part[0].isalpha():
            stem = part.split("-", 1)[0].split("/", 1)[0]
            stem = stem.rstrip("*?")
            if stem in names:
                offset = names.index(stem)
                part = part.replace(stem, str(low + offset), 1)
            else:
                raise ValueError(f"unknown cron name {stem!r} in field {expr!r}")

        range_part = part
        if "/" in part:
            range_part, _, step_part = part.partition("/")
            try:
                step = int(step_part)
            except ValueError as exc:
                raise ValueError(f"invalid cron step in field {expr!r}") from exc
            if step <= 0:
                raise ValueError(f"cron step must be positive: {expr!r}")
        else:
            step = 1

        if range_part in ("*", "?", ""):
            values.update(range(low, high + 1, step))
        elif "-" in range_part:
            raw_low, _, raw_high = range_part.partition("-")
            try:
                field_low = int(raw_low)
                field_high = int(raw_high)
            except ValueError as exc:
                raise ValueError(f"invalid cron range in field {expr!r}") from exc
            if field_low > field_high:
                # Wrapping range: iterate up to the end plus one full cycle
                stops = range(field_low, field_high + span + 1, step)
                mapped = (v % span for v in stops)
            else:
                mapped = (v for v in range(field_low, field_high + 1, step))
            values.update(mapped)
        else:
            try:
                values.add(int(range_part))
            except ValueError as exc:
                raise ValueError(f"invalid cron field value {range_part!r} ({expr!r})") from exc

    # Normalize cron weekday convention 7 == Sunday == 0 (weekday fields
    # only: their low bound is 0; month fields keep 7 valid)
    if names is not None and low == 0 and 7 in values:
        values.discard(7)
        values.add(0)

    for value in values:
        if not low <= value <= high:
            raise ValueError(
                f"cron value {value} out of range {low}-{high} (field {expr!r})"
            )
    if not values:
        raise ValueError(f"cron field matches no values: {expr!r}")
    return values


def compute_next_run(
    cron_expression: str,
    timezone_name: str,
    after: datetime,
) -> datetime:
    """Compute the next run time for a cron expression in a named timezone.

    *after* may be naive (treated as UTC) or timezone-aware: the value is
    converted into the schedule's timezone, the next matching local time is
    found, and the result is returned as an aware UTC datetime.

    Raises ValueError for invalid cron expressions, unknown timezones, or
    expressions that match nothing within two years of scrolling forward.
    """
    fields = cron_expression.split()
    if len(fields) != 5:
        raise ValueError(
            f"cron expression must have 5 fields (minute hour day month weekday): {cron_expression!r}"
        )
    minute_f, hour_f, day_f, month_f, weekday_f = fields
    minutes = _expand_cron_field(minute_f, 0, 59)
    hours = _expand_cron_field(hour_f, 0, 23)
    if day_f not in ("*", "?") or weekday_f not in ("*", "?"):
        # Standard cron semantics: when BOTH day-of-month and day-of-week
        # are restricted, a match on either one satisfies the schedule.
        days = None if day_f == "*" or day_f == "?" else _expand_cron_field(day_f, 1, 31)
        weekdays = (
            None if weekday_f == "*" or weekday_f == "?"
            else _expand_cron_field(weekday_f, 0, 6, names=("sun", "mon", "tue", "wed", "thu", "fri", "sat"))
        )
    else:
        days = None
        weekdays = None
    months = _expand_cron_field(month_f, 1, 12, names=("jan", "feb", "mar", "apr", "may", "jun",
                                                      "jul", "aug", "sep", "oct", "nov", "dec"))

    try:
        zone = zoneinfo.ZoneInfo(timezone_name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown timezone: {timezone_name!r}") from exc

    local_after = after.astimezone(zone) if after.tzinfo is not None else after.replace(tzinfo=zone).astimezone(zone)
    candidate = local_after.replace(second=0, microsecond=0) + timedelta(minutes=1)

    limit = local_after + timedelta(days=732)  # two years of scrolling
    while candidate <= limit:
        if candidate.month not in months:
            # Jump to the first day of the next matching month
            year = candidate.year
            month = candidate.month
            while True:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                if month in months:
                    break
            candidate = candidate.replace(year=year, month=month, day=1, hour=0, minute=0)
            continue
        # Convert Python weekday (Mon=0..Sun=6) to cron numbering
        # (Sun=0, Mon=1..Sat=6)
        cron_dow = (candidate.weekday() + 1) % 7
        if days is not None and weekdays is not None:
            if candidate.day not in days and cron_dow not in weekdays:
                candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
                continue
        elif days is not None:
            if candidate.day not in days:
                candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
                continue
        elif weekdays is not None:
            if cron_dow not in weekdays:
                candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
                continue
        if candidate.hour not in hours:
            candidate = candidate.replace(minute=0) + timedelta(hours=1)
            continue
        if candidate.minute not in minutes:
            candidate += timedelta(minutes=1)
            continue

        # Validate this candidate against month/day length (e.g. Feb 30)
        max_day = calendar.monthrange(candidate.year, candidate.month)[1]
        if candidate.day <= max_day:
            # Handle skipped local times near DST transitions: a wall-clock
            # time that does not exist (e.g. 02:30 in spring forward) never
            # materialises, so the expected instant is the same instant as
            # 03:30 local. Emulate by re-checking the offset after localize.
            aware = candidate.replace(tzinfo=zone)
            utc_result = aware.astimezone(timezone.utc)
            # Detect skipped local times near DST transitions (e.g. 02:30
            # during spring forward): localize-then-roundtrip shifts the
            # wall clock, meaning the local time never materialised.
            roundtrip = utc_result.astimezone(zone)
            if roundtrip.replace(tzinfo=None) == candidate.replace(tzinfo=None):
                return utc_result
            # Skipped local time: fast-forward to the next valid minute,
            # keeping the candidate timezone-aware (never naive).
            candidate = roundtrip.replace(tzinfo=None).replace(tzinfo=zone) + timedelta(minutes=1)
            continue
        candidate = candidate.replace(day=1, hour=0, minute=0) + timedelta(days=max_day)
        continue
    raise ValueError(f"no matching time within two years of {local_after.isoformat()}")


@dataclass
class ScheduleDefinition:
    """A definition of when and how to run a scheduled job."""

    id: str  # Unique schedule identifier
    name: str  # Human-readable name
    job_listing_id: str  # Associated job listing
    cron_expression: str  # Cron-style schedule expression (5 fields, no seconds)
    timezone: str  # IANA timezone name (e.g., "America/New_York")
    enabled: bool = True
    created_at: str | None = None
    last_run_at: str | None = None
    next_run_at: str | None = None
    max_retries: int = 3
    description: str | None = None


@dataclass
class RunRecord:
    """A record of a single scheduled run execution."""

    id: str  # Unique run identifier
    schedule_id: str  # Associated schedule definition
    status: SchedulerStatus
    started_at: str  # ISO format when execution started
    completed_at: str | None = None  # ISO format when execution completed
    exit_code: int | None = None
    error_message: str | None = None
    output: str | None = None  # Any output from the execution
    retry_count: int = 0  # How many retries attempted


class SchedulerEngine:
    """Core scheduling engine that manages job execution scheduling and tracking.

    This engine provides:
    - Timezone-aware scheduling using cron-style expressions
    - Persisted run state for restart recovery
    - Prevention of overlapping duplicate executions
    - Bounded retries with exponential backoff
    - Missed-run detection and recovery
    """

    def __init__(self, store: CareerStore) -> None:
        self._store = store
        self._running: set[str] = set()  # Track currently running schedule IDs

    def schedule_job(self, definition: ScheduleDefinition) -> None:
        """Schedule a job for execution based on a ScheduleDefinition.

        Persists the schedule definition and schedules the next run.
        """
        now = _now()
        definition.created_at = now
        definition.last_run_at = None
        definition.next_run_at = self._compute_next_run(definition)

        self._store.save_schedule_definition(definition)

    def _compute_next_run(self, definition: ScheduleDefinition) -> str | None:
        """Compute and persist the next run time for a schedule definition.

        Uses the schedule's cron_expression and timezone. When the cron
        expression or timezone is invalid, the schedule is disabled and the
        error recorded in the description so the failure is observable
        instead of silently never running again.
        """
        try:
            next_run = compute_next_run(
                definition.cron_expression,
                definition.timezone,
                datetime.fromisoformat(_now()),
            )
        except ValueError as exc:
            definition.enabled = False
            definition.description = (
                f"disabled: invalid schedule ({exc}); job_listing_id="
                f"{definition.job_listing_id}"
            )
            return None
        return next_run.isoformat()

    def check_due_runs(self) -> tuple[RunRecord, ...]:
        """Check for due runs and return any that should execute.

        This method:
        1. Finds schedules due for execution
        2. Checks for overlapping runs (prevents duplicates)
        3. Returns run records for due schedules
        """
        schedules = self._store.list_schedule_definitions()
        now = _now()
        results: list[RunRecord] = []

        for schedule in schedules:
            if not schedule.enabled:
                continue

            # Check if it's time to run. An update here must never move
            # next_run_at forward: polling repeatedly must not postpone a
            # cron schedule (that is the "wait forever" bug).
            if schedule.next_run_at is None or now < schedule.next_run_at:
                if not schedule.enabled:
                    continue
                if schedule.next_run_at is None:
                    # Recover an interrupted definition whose next_run was
                    # lost or never computed
                    schedule.next_run_at = self._compute_next_run(schedule)
                    self._store.save_schedule_definition(schedule)
                continue

            # Check for overlapping runs
            if schedule.id in self._running:
                # Already running, skip without moving next_run_at
                continue

            # Create run record
            run_id = f"run_{schedule.id}_{int(time.time())}"
            run = RunRecord(
                id=run_id,
                schedule_id=schedule.id,
                status=SchedulerStatus.RUNNING,
                started_at=now,
            )

            # Mark as running
            self._running.add(schedule.id)

            # Save the run record
            self._store.save_run_record(run)

            # Update schedule's last_run_at and compute next run
            schedule.last_run_at = now
            schedule.next_run_at = self._compute_next_run(schedule)
            self._store.save_schedule_definition(schedule)

            results.append(run)

        return tuple(results)

    def complete_run(self, run_id: str, status: SchedulerStatus = SchedulerStatus.COMPLETED,
                     exit_code: int | None = None, error_message: str | None = None,
                     output: str | None = None, retry_count: int | None = None) -> None:
        """Mark a run as complete and handle retry logic.

        If the run failed and retries remain, schedule a retry.
        """
        run = self._store.get_run_record(run_id)
        if run is None:
            return

        run.status = status
        run.completed_at = _now()
        if exit_code is not None:
            run.exit_code = exit_code
        if error_message is not None:
            run.error_message = error_message
        if output is not None:
            run.output = output
        if retry_count is not None:
            run.retry_count = retry_count

        self._store.save_run_record(run)

        # Release the schedule immediately on any terminal state so the
        # next due run (or retry) can be picked up. Previously a failed run
        # stayed in self._running forever, wedging the schedule.
        self._running.discard(run.schedule_id)

        # Handle retry logic: a failed run whose retries are not exhausted
        # creates a new pending run record. The caller drives execution, so
        # no run is left "running" unowned.
        schedule = self._store.get_schedule_definition(run.schedule_id)
        if (
            schedule is not None
            and run.status is SchedulerStatus.FAILED
            and run.retry_count < schedule.max_retries
        ):
            run.retry_count += 1
            self._store.save_run_record(run)

            new_run_id = f"run_{schedule.id}_retry_{run.retry_count}_{int(time.time())}"
            delay = min(
                2.0 ** (run.retry_count - 1),
                300.0,
            )
            retry_time = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
            new_run = RunRecord(
                id=new_run_id,
                schedule_id=schedule.id,
                status=SchedulerStatus.PENDING,
                started_at=retry_time,
            )
            self._store.save_run_record(new_run)

    def cancel_run(self, run_id: str) -> None:
        """Cancel a running job execution."""
        run = self._store.get_run_record(run_id)
        if run is None:
            return

        run.status = SchedulerStatus.CANCELLED
        run.completed_at = _now()
        self._store.save_run_record(run)

        # Remove from running set
        schedule = self._store.get_schedule_definition(run.schedule_id)
        if schedule is not None and run.schedule_id in self._running:
            self._running.discard(run.schedule_id)

    def get_pending_runs(self) -> tuple[RunRecord, ...]:
        """Get all runs that need attention.

        Includes pending/failed runs (retryable) and runs still marked
        RUNNING, which after a restart means they were interrupted and
        should be re-driven or explicitly cancelled by the caller.
        """
        runs = self._store.list_run_records()
        return tuple(
            run for run in runs
            if run.status in (SchedulerStatus.PENDING, SchedulerStatus.FAILED, SchedulerStatus.RUNNING)
        )

    def get_schedule(self, schedule_id: str) -> ScheduleDefinition | None:
        """Get a schedule definition by ID."""
        return self._store.get_schedule_definition(schedule_id)

    def list_schedules(self) -> tuple[ScheduleDefinition, ...]:
        """List all schedule definitions."""
        return self._store.list_schedule_definitions()


def _now() -> str:
    """Return the current UTC time as an ISO format string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
