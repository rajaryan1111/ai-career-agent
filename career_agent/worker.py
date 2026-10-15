"""The local worker: it takes what is due, runs the handler for it, and records what happened.

Design boundaries, stated before the code:

**In-process and cooperative, not a daemon that can kill things.** A handler runs on the worker's own
thread, and it is given a deadline and told when to stop (:class:`TaskContext`). Nothing here pretends
to be able to interrupt a Python function that has decided not to return: a handler that ignores its
deadline keeps running until it returns, and the *run* is still recorded as timed out, because the work
did not finish inside the time it was given. Handlers shipped with the application are short and check
:meth:`TaskContext.should_stop`, and the documentation says so plainly - a scheduler that claimed it
could cancel arbitrary work would be lying to whoever relied on it.

**The outcome is decided by what happened, never by what a handler says about itself.** A handler that
raises is ``FAILED``; one that says it succeeded after its deadline passed is ``TIMED_OUT``; one that
returns something which is not a :class:`~career_agent.tasks.HandlerResult` is ``FAILED`` - a handler
cannot turn an error into a success by describing it as one, and returning nothing is not a success.

**One occurrence, one attempt, at a time.** Every execution starts from a claim taken by the store
(``claim_due_run``), whose uniqueness constraint is what stops a restart or a second process from
running the same occurrence twice. The worker never executes anything it has not claimed, and it
finishes only the run it claimed.

**Stopping is a state, not a crash.** A stop request lets the current handler wind up, records the
attempt honestly (``INTERRUPTED`` when it stopped early because it was asked to, or its own outcome
when it managed to finish inside its deadline), releases the lease, and leaves the task's bookkeeping
consistent so the next worker can retry the occurrence it owes.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol, runtime_checkable

from .store import CareerStore, TaskRunConflict
from .tasks import (
    HandlerOutcome, HandlerResult, RunState, ScheduledTask, TaskRun, WorkerLease, WorkerLeaseHeld,
    clean_detail, next_run_after, validate_utc_instant,
)

#: How often the loop looks for due work by default. Short enough that a run at 00:00 starts at 00:00,
#: long enough to cost nothing while the person works.
DEFAULT_POLL_SECONDS = 15.0

#: How often a worker refreshes its lease and the heartbeat of any attempt it is running.
DEFAULT_HEARTBEAT_SECONDS = 10.0

#: How long without a heartbeat before another worker may treat this one as gone. Deliberately several
#: times the heartbeat interval, so a slow tick is not mistaken for a dead process - the cost of being
#: wrong in that direction is two workers, and being wrong in the other direction is a task that never
#: runs again.
DEFAULT_STALE_AFTER_SECONDS = 120.0

#: How many attempts one tick will execute before returning to the caller. A backlog of due tasks is
#: worked through over successive ticks rather than in one long burst, so a stop request, a heartbeat
#: and the person's view of the app stay responsive.
MAX_RUNS_PER_TICK = 4

#: How far back the missed-occurrence report looks. The report answers "what did the schedule walk
#: past while nothing was running?", and an unbounded window would answer it with a list nobody reads;
#: a bounded window says what it is bounded to instead of pretending to remember everything.
MISSED_LOOKBACK_DAYS = 7

#: The most run rows and the most occurrences examined per task while building that report, so a task
#: with a dense schedule cannot turn a status read into an unbounded scan.
_RUNS_EXAMINED_PER_TASK = 200
_MAX_OCCURRENCES_PER_TASK = 200


class WorkerConfigurationError(ValueError):
    """The worker's settings do not describe something it can run safely."""


@dataclass(frozen=True)
class WorkerSettings:
    """Timings for the loop, validated so an unsafe combination cannot be configured silently."""

    poll_seconds: float = DEFAULT_POLL_SECONDS
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS
    max_runs_per_tick: int = MAX_RUNS_PER_TICK

    def __post_init__(self) -> None:
        for noun, value in (("poll_seconds", self.poll_seconds),
                            ("heartbeat_seconds", self.heartbeat_seconds),
                            ("stale_after_seconds", self.stale_after_seconds)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise WorkerConfigurationError(f"{noun} must be a positive number of seconds.")
        if isinstance(self.max_runs_per_tick, bool) or not isinstance(self.max_runs_per_tick, int) \
                or self.max_runs_per_tick < 1:
            raise WorkerConfigurationError("max_runs_per_tick must be a positive whole number.")
        if self.stale_after_seconds <= self.heartbeat_seconds * 2:
            raise WorkerConfigurationError(
                "stale_after_seconds must be more than twice heartbeat_seconds, otherwise a healthy "
                "worker's own attempts would be recovered as if it had died."
            )


@dataclass(frozen=True)
class TaskContext:
    """What a handler is given: the occurrence it serves, and how to behave while serving it."""

    task: ScheduledTask
    slot_at: datetime
    attempt: int
    started_at: datetime
    deadline: datetime
    database_path: str
    _stop_requested: Callable[[], bool] = field(repr=False, default=lambda: False)
    _now: Callable[[], datetime] = field(repr=False, default=lambda: datetime.now(timezone.utc))

    def should_stop(self) -> bool:
        """Whether the worker is shutting down or this attempt has run out of time.

        A handler that takes more than a moment must ask this between steps and return
        :attr:`~career_agent.tasks.HandlerOutcome.STOPPED` when it is true. That is the only way an
        attempt ends early without being recorded as a failure of the task: stopping was asked for, and
        the run history should say so rather than blaming the work.
        """
        return self._stop_requested()

    def seconds_left(self, now: datetime | None = None) -> float:
        """How much of the attempt's time is left; negative once the deadline has passed."""
        moment = now or self._now()
        return (self.deadline - moment).total_seconds()

    def overdue(self, now: datetime | None = None) -> bool:
        """Whether the deadline has passed - the handler may finish, but not claim success."""
        return self.seconds_left(now) <= 0

    @property
    def database_folder(self) -> str:
        """The folder the database lives in, for a handler that needs somewhere to write."""
        return os.path.dirname(self.database_path) or "."


@runtime_checkable
class Handler(Protocol):
    """What a registered handler must look like.

    A plain callable is accepted; the attributes below are what the scheduler uses to describe a task's
    kind to a person, and both are optional - an unregistered kind is reported as such rather than
    silently skipped.
    """

    description: str  #: one line shown in the task list and in ``--worker-status``

    def __call__(self, context: TaskContext) -> HandlerResult:  # pragma: no cover - protocol
        ...


class HandlerRegistry:
    """The kinds this worker can execute, and the function each one runs.

    Registration is explicit and refusals are loud: executing a task whose kind is unknown is recorded
    as a failed attempt naming the kind, never as a success and never as "nothing to do".
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, kind: str, handler: Handler, *, replace: bool = False) -> None:
        """Add a handler for ``kind``. Re-registering needs ``replace=True``, so a wiring mistake shows."""
        if not isinstance(kind, str) or not kind.strip():
            raise WorkerConfigurationError("A handler needs the kind of task it serves.")
        name = kind.strip()
        if not callable(handler):
            raise WorkerConfigurationError(f"The handler for {name} is not callable.")
        if name in self._handlers and not replace:
            raise WorkerConfigurationError(
                f"A handler for {name} is already registered; pass replace=True to override it."
            )
        self._handlers[name] = handler

    def get(self, kind: str) -> Handler | None:
        """The handler for a kind, or ``None`` when this worker cannot execute it."""
        return self._handlers.get(str(kind).strip())

    def kinds(self) -> tuple[str, ...]:
        """Every registered kind, in a stable order."""
        return tuple(sorted(self._handlers))

    def describe(self) -> tuple[str, ...]:
        """One line per kind, for a status report a person reads."""
        lines = []
        for kind in self.kinds():
            handler = self._handlers[kind]
            description = getattr(handler, "description", "") or ""
            lines.append(f"{kind}: {description}".rstrip(": ").rstrip())
        return tuple(lines)


@dataclass(frozen=True)
class MissedOccurrence:
    """One scheduled instant the schedule walked past with nothing recorded for it.

    "Missed" is a claim about the records, not about what anybody should do: the instant is due, an
    occurrence of that task's own schedule, no attempt row exists for it, no retry owes it, and it is not
    the occurrence the next claim will take - the scheduler plans a run from the instant the previous one
    finished, so an occurrence like this is one nothing will come back to. Nothing here runs it,
    re-plans it or deletes it: seeing what was missed is the whole job, and the laptop-off limitation it
    exposes is stated rather than papered over.
    """

    task_id: str
    name: str
    slot_at: datetime

    def describe(self) -> str:
        return f"{self.task_id} ({self.name}) at {self.slot_at.isoformat()}"


def _occurrences_between(task: ScheduledTask, start: datetime, end: datetime) -> tuple[datetime, ...]:
    """The task's own occurrences from ``start`` to ``end`` inclusive, bounded per task.

    Uses the same :func:`~career_agent.tasks.next_run_after` the scheduler books with, so a day the
    zone skips or repeats an hour is enumerated exactly the way it was booked rather than by a second
    implementation that could disagree with the first.
    """
    found: list[datetime] = []
    cursor = start
    inclusive = True
    while len(found) < _MAX_OCCURRENCES_PER_TASK:
        candidate = next_run_after(task, cursor, inclusive=inclusive)
        if candidate is None or candidate > end:
            break
        found.append(candidate)
        cursor = candidate
        inclusive = False
    return tuple(found)


def missed_occurrences(store: CareerStore, *, now: datetime | None = None,
                       lookback_days: int = MISSED_LOOKBACK_DAYS) -> tuple[MissedOccurrence, ...]:
    """What the schedule walked past while nothing ran, oldest first. Reads; changes nothing.

    The window is the last ``lookback_days`` days, cut off at each task's own creation, and a task that
    is paused is not examined at all: nothing was expected of it. An occurrence counts as missed when it
    is due, no attempt row exists for that instant (any state counts - a refusal, a failure and an
    interruption were all attempts) and no retry is owed for it either.

    The occurrence at ``next_run_at`` is deliberately left out, and the reason is how the scheduler
    plans: a claim takes that instant, and the run after it is planned from the *next* instant after the
    process finished (:func:`~career_agent.tasks.plan_after_run`), so every other occurrence between it
    and now is one nothing will ever come back to. Overdue work and missed work are therefore different
    things and this function reports only the second: the first is the ``(due now)`` marker on the status
    line above, and it will be attempted the moment a worker starts.
    """
    moment = validate_utc_instant(now, noun="The reference time") or datetime.now(timezone.utc)
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or lookback_days < 1:
        raise ValueError("The look-back window must be a positive whole number of days.")
    window_start = moment - timedelta(days=lookback_days)
    found: list[MissedOccurrence] = []
    for task in store.list_scheduled_tasks():
        if not task.enabled:
            continue
        start = max(window_start, task.created_at) if task.created_at else window_start
        if moment < start:
            continue
        attempted = {run.slot_at for run in store.list_task_runs(
            task_id=task.task_id, limit=_RUNS_EXAMINED_PER_TASK)}
        for slot in _occurrences_between(task, start, moment):
            if slot in attempted or slot == task.pending_slot_at or slot == task.next_run_at:
                continue
            found.append(MissedOccurrence(task.task_id, task.name, slot))
    found.sort(key=lambda missed: (missed.slot_at, missed.task_id))
    return tuple(found)


@dataclass(frozen=True)
class WorkerStatus:
    """A read-only answer to \"what is scheduled here, and what has it been doing?\"."""

    worker_id: str | None
    lease: WorkerLease | None
    running: tuple[TaskRun, ...]
    #: The next task the schedule will reach, whether or not it is due yet - "when does the next run
    #: happen?" is a question about the schedule, and answering it with "nothing is due" would be
    #: technically true and useless.
    next_task: ScheduledTask | None
    recent_runs: tuple[TaskRun, ...]
    checked_at: datetime
    #: Occurrences the schedule walked past with no attempt recorded. Defaulted so a caller that builds
    #: a status by hand keeps working; the one constructor that matters, :func:`worker_status`, fills it.
    missed: tuple[MissedOccurrence, ...] = ()

    def describe(self, *, now: datetime | None = None) -> tuple[str, ...]:
        """Lines for the command line: lease, attempts in progress, next due, recent outcomes."""
        moment = validate_utc_instant(now, noun="The reference time") or self.checked_at
        lines: list[str] = []
        if self.lease is None:
            lines.append("No worker holds the lease for this database, so nothing is scheduled to run.")
        else:
            age = (moment - self.lease.heartbeat_at).total_seconds()
            lines.append(
                f"Worker {self.lease.worker_id} holds the lease; last heartbeat {int(age)}s ago "
                f"(at {self.lease.heartbeat_at.isoformat()})."
            )
        if self.running:
            for run in self.running:
                lines.append(
                    f"In progress: {run.task_id} attempt {run.attempt} since "
                    f"{run.started_at.isoformat() if run.started_at else 'an unrecorded time'}."
                )
        else:
            lines.append("No attempt is in progress.")
        if self.next_task is None or self.next_task.next_run_at is None:
            lines.append("No task is scheduled to run.")
        else:
            due = self.next_task.next_run_at
            marker = " (due now)" if due <= moment else ""
            lines.append(
                f"Next: {self.next_task.task_id} ({self.next_task.name}) at "
                f"{due.isoformat()}{marker}."
            )
        if self.recent_runs:
            lines.append("Recent attempts:")
            for run in self.recent_runs[:5]:
                seconds = run.duration_seconds
                timing = f"{seconds:.1f}s" if seconds is not None else "no duration recorded"
                outcome = run.state.value
                detail = f" - {run.detail}" if run.detail else ""
                error = f" - error: {run.error}" if run.error else ""
                lines.append(f"  {run.task_id} attempt {run.attempt}: {outcome} ({timing}){detail}{error}")
        else:
            lines.append("No attempt has been recorded yet.")
        if self.missed:
            lines.append(
                f"Missed while nothing was running ({len(self.missed)} occurrence(s) in the last "
                f"{MISSED_LOOKBACK_DAYS} days):"
            )
            for missed in self.missed[:5]:
                lines.append(f"  {missed.describe()}")
            if len(self.missed) > 5:
                lines.append(f"  ... and {len(self.missed) - 5} more")
            lines.append(
                "Nothing is catching up on these: a worker that is not running cannot run what it "
                "missed, and this report only lists them."
            )
        else:
            lines.append(
                f"No scheduled occurrence was missed in the last {MISSED_LOOKBACK_DAYS} days."
            )
        return tuple(lines)


def worker_status(store: CareerStore, *, now: datetime | None = None,
                  worker_id: str | None = None) -> WorkerStatus:
    """Read the scheduler's state without taking the lease and without claiming anything."""
    moment = validate_utc_instant(now, noun="The reference time") or datetime.now(timezone.utc)
    upcoming = [task for task in store.list_scheduled_tasks()
                if task.enabled and task.next_run_at is not None]
    upcoming.sort(key=lambda task: (task.next_run_at, task.task_id))  # type: ignore[arg-type,return-value]
    return WorkerStatus(
        worker_id=worker_id,
        lease=store.get_worker_lease(),
        running=store.running_runs(),
        next_task=upcoming[0] if upcoming else None,
        recent_runs=store.list_task_runs(limit=5),
        checked_at=moment,
        missed=missed_occurrences(store, now=moment),
    )


class Worker:
    """Executes what the store says is due, one claim at a time.

    The worker holds the database's lease while it runs: taking it is what says "this process is the
    scheduler for this database", and it is released on the way out - including when a stop is
    requested mid-attempt - so restarting after a crash is an ordinary case rather than a special one.
    """

    def __init__(
        self, store: CareerStore, *, worker_id: str, registry: HandlerRegistry | None = None,
        settings: WorkerSettings | None = None, clock: Callable[[], datetime] | None = None,
        on_outcome: Callable[[TaskRun], None] | None = None,
    ) -> None:
        name = str(worker_id).strip()
        if not name:
            raise WorkerConfigurationError("A worker needs an id, so a lease can name its holder.")
        self.store = store
        self.worker_id = name
        self.registry = registry or HandlerRegistry()
        self.settings = settings or WorkerSettings()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._on_outcome = on_outcome
        self._stop = threading.Event()
        self._lease: WorkerLease | None = None

    # ------------------------------------------------------------------ lifecycle
    @property
    def stop_requested(self) -> bool:
        """Whether a stop has been asked for (by a signal, the command line, or a caller)."""
        return self._stop.is_set()

    @property
    def lease(self) -> WorkerLease | None:
        """The lease this worker holds, or ``None`` before it starts or after it releases it."""
        return self._lease

    def request_stop(self) -> None:
        """Ask the loop to stop after the attempt in progress has wound up.

        Safe to call from a signal handler or another thread: it only sets an event. A handler sees it
        through :meth:`TaskContext.should_stop`, and the loop stops between ticks.
        """
        self._stop.set()

    def acquire_lease(self, *, now: datetime | None = None) -> WorkerLease:
        """Take (or refresh) this database's lease, or raise :class:`WorkerLeaseHeld`.

        Raises rather than waiting: a second scheduler started by mistake should stop and say so, not
        sit in a loop hoping the other one goes away.
        """
        moment = now or self._clock()
        lease = self.store.acquire_worker_lease(
            self.worker_id, now=moment,
            stale_before=moment - timedelta(seconds=self.settings.stale_after_seconds))
        self._lease = lease
        return lease

    def release_lease(self) -> bool:
        """Give up the lease if this worker holds it; returns whether it did."""
        released = self.store.release_worker_lease(self.worker_id)
        self._lease = None
        return released

    # ------------------------------------------------------------------ the loop
    def run(self, *, max_ticks: int | None = None, stop_event: threading.Event | None = None) -> int:
        """Run until asked to stop (or ``max_ticks`` ticks have happened); return the tick count.

        ``stop_event`` lets the caller own the signal handling: the loop stops when either that event is
        set or :meth:`request_stop` is called. The lease is always released on the way out, including
        when a tick or a handler raises, so a crash cannot leave the database looking busy.
        """
        if max_ticks is not None and (isinstance(max_ticks, bool) or max_ticks < 0):
            raise WorkerConfigurationError("max_ticks must be zero or a positive whole number.")
        self.acquire_lease()
        ticks = 0
        try:
            while True:
                if self.stop_requested or (stop_event is not None and stop_event.is_set()):
                    break
                if max_ticks is not None and ticks >= max_ticks:
                    break
                self.tick()
                ticks += 1
                if max_ticks is not None and ticks >= max_ticks:
                    break
                self._sleep(self.settings.poll_seconds, stop_event)
        finally:
            self.release_lease()
        return ticks

    def _sleep(self, seconds: float, stop_event: threading.Event | None) -> None:
        """Wait between ticks, but wake immediately when a stop is requested."""
        if stop_event is not None:
            if stop_event.wait(seconds):
                return
        self._stop.wait(seconds)

    def tick(self, *, now: datetime | None = None) -> tuple[TaskRun, ...]:
        """One pass: keep the lease alive, recover dead attempts, then run what is due."""
        moment = now or self._clock()
        if self._lease is not None:
            refreshed = self.store.heartbeat_worker_lease(self.worker_id, now=moment)
            if refreshed is None:
                # The lease is gone - another worker took it over, or somebody removed it. Continuing
                # would mean two schedulers again, which is exactly what the lease exists to prevent.
                raise WorkerLeaseHeld(self.store.get_worker_lease() or WorkerLease(
                    lease_name="scheduler", worker_id="an unknown worker", acquired_at=moment,
                    heartbeat_at=moment))
            self._lease = refreshed
        self.store.recover_stale_runs(
            moment - timedelta(seconds=self.settings.stale_after_seconds), now=moment)
        executed: list[TaskRun] = []
        for _ in range(self.settings.max_runs_per_tick):
            if self.stop_requested:
                break
            claimed = self.store.claim_due_run(worker_id=self.worker_id, now=moment)
            if claimed is None:
                break
            executed.append(self.execute(claimed, now=moment))
        return tuple(executed)

    # ------------------------------------------------------------------ one attempt
    def execute(self, run: TaskRun, *, now: datetime | None = None) -> TaskRun:
        """Run the handler for a claimed attempt and record the outcome. Never raises for a failure.

        The only exceptions that escape are the ones that mean the *record* could not be written
        (:class:`~career_agent.store.TaskRunConflict`), because those mean somebody else owns this run
        and this worker must stop rather than keep working on something it no longer holds.
        """
        moment = now or self._clock()
        task = self.store.get_scheduled_task(run.task_id)
        if task is None:
            # The task vanished between the claim and the attempt. Deleting a task deletes its run
            # history too, so this means the database and this worker disagree about what exists -
            # something a retry or a guess would only make worse. It is raised rather than recorded,
            # because the run it would be recorded against is not something this worker still holds.
            raise TaskRunConflict(
                f"Run {run.run_id} was claimed for task {run.task_id!r}, which is no longer stored. "
                "Nothing was executed; the worker stopped instead of guessing what the task was."
            )
        deadline = moment + timedelta(seconds=task.timeout_seconds)
        context = TaskContext(
            task=task, slot_at=run.slot_at, attempt=run.attempt, started_at=moment,
            deadline=deadline, database_path=self.store.database_path,
            _stop_requested=lambda: self.stop_requested or self._clock() >= deadline,
            _now=self._clock,
        )
        state, detail, error = self._call_handler(task, context, deadline)
        updated = self.store.finish_run(run.run_id, state, detail=detail, error=error,
                                        worker_id=self.worker_id, now=self._clock())
        if self._on_outcome is not None:
            self._on_outcome(updated)
        return updated

    def _call_handler(self, task: ScheduledTask, context: TaskContext,
                      deadline: datetime) -> tuple[RunState, str, str | None]:
        """Invoke the handler for a task's kind and translate whatever happens into a run state.

        Every path a handler can take is decided here, in one place, so "the handler says it worked" is
        never the same statement as "the work was done inside the time it was given".
        """
        handler = self.registry.get(task.kind)
        if handler is None:
            return (RunState.FAILED, "no handler is registered for this kind of task",
                    f"No handler is registered for kind {task.kind!r}, so this task cannot run. "
                    f"Registered kinds: {', '.join(self.registry.kinds()) or 'none'}.")
        try:
            result = handler(context)
        except Exception as exc:  # noqa: BLE001 - a handler's failure is data, not a crash
            # The exception is the outcome; it is recorded with its type and text so the run history
            # says what went wrong rather than only that something did.
            return (RunState.FAILED, "the handler raised an error",
                    f"{type(exc).__name__}: {clean_detail(exc)}")
        if not isinstance(result, HandlerResult):
            return (RunState.FAILED, "the handler returned something that is not a result",
                    f"The handler for {task.kind} returned {type(result).__name__} instead of a "
                    "HandlerResult; an outcome has to be stated explicitly.")
        if result.outcome is HandlerOutcome.SUCCEEDED:
            if self._clock() >= deadline:
                return (RunState.TIMED_OUT,
                        f"the handler finished after its {task.timeout_seconds}s deadline",
                        f"The handler reported success after its deadline had passed, so the attempt is "
                        f"recorded as timed out rather than successful.")
            return (RunState.SUCCEEDED, result.detail, None)
        if result.outcome is HandlerOutcome.REFUSED:
            # A refusal is a decision, not work, so it stays a refusal even if it arrives late.
            return (RunState.REFUSED, result.detail, None)
        # STOPPED: the handler was asked to stop, or it gave itself up. Which of the two it was is the
        # difference between an attempt that ran out of time and one that was interrupted on purpose,
        # and the run history keeps them apart.
        if self._clock() >= deadline:
            return (RunState.TIMED_OUT, result.detail or "the handler stopped at its deadline",
                    f"The handler did not finish inside its {task.timeout_seconds}s deadline.")
        return (RunState.INTERRUPTED, result.detail or "the handler stopped when asked to", None)


def describe_registry(registry: HandlerRegistry | None = None) -> tuple[str, ...]:
    """One line per registered kind, for a status report."""
    return (registry or HandlerRegistry()).describe()
