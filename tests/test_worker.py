"""Tests for the worker: claiming, running, recording, stopping, and recovering.

Time is injected rather than waited for, so every case here is deterministic: the clock is a mutable
value the test moves, and the loop is driven one tick at a time. Handlers are deliberately small fakes
- the real ones are tested where they live - which keeps this module about the engine's promises:
one occurrence runs once, an outcome is recorded exactly as it happened, and a stop leaves the task in
a state the next worker can pick up.
"""
from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career_agent.store import CareerStore, TaskRunConflict
from career_agent.tasks import (
    HandlerOutcome, HandlerResult, RunState, WorkerLeaseHeld, build_task,
)
from career_agent.worker import (
    MISSED_LOOKBACK_DAYS, HandlerRegistry, TaskContext, Worker, WorkerConfigurationError, WorkerSettings,
    missed_occurrences, worker_status,
)

UTC = timezone.utc
#: 2026-10-15 11:30 IST, half an hour before the default noon occurrence.
START = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)


def _event_line_count(database_path: Path) -> int:
    """How many event lines the application log holds for this database, or 0 when there is none."""
    from career_agent.event_log import log_path, read_lines

    path = log_path(database_path)
    return len(read_lines(database_path=database_path, limit=1000)) if path.exists() else 0


class WorkerTestCase(unittest.TestCase):
    """A database, a movable clock and a worker whose handlers are the test's own."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.database_path = Path(self._temp.name) / "career_agent.sqlite3"
        self.store = CareerStore(self.database_path)
        self.addCleanup(self.store.close)
        self.now = START
        self.registry = HandlerRegistry()
        self.outcomes = []

    def clock(self) -> datetime:
        return self.now

    def worker(self, *, worker_id: str = "w1", settings: WorkerSettings | None = None) -> Worker:
        # Timings are the test's, not the product's: the loop must not wait 15 seconds between ticks in
        # a test, and the stale window has to stay longer than the heartbeat for the settings to be valid.
        settings = settings or WorkerSettings(poll_seconds=0.01, heartbeat_seconds=0.05,
                                              stale_after_seconds=30)
        return Worker(
            self.store, worker_id=worker_id, registry=self.registry, settings=settings,
            clock=self.clock, on_outcome=self.outcomes.append,
        )

    def schedule(self, *, task_id: str = "discovery-run", kind: str = "discovery.run", **changes):
        """A stored task, due at its next occurrence; ``now`` defaults to the test clock."""
        fields = {
            "task_id": task_id, "name": task_id.replace("-", " ").title(), "kind": kind,
            "times": ("00:00", "12:00"), "timezone": "Asia/Kolkata",
        }
        fields.update(changes)
        return self.store.save_scheduled_task(build_task(**fields, now=self.now),  # type: ignore[arg-type]
                                              now=self.now)

    def register(self, kind: str, result=None, *, error: Exception | None = None,
                 advance: timedelta | None = None, description: str = "a test handler",
                 stop_first: bool = False) -> list[TaskContext]:
        """Register a handler that records its context and then behaves as the test asks."""
        seen: list[TaskContext] = []

        def handler(context: TaskContext) -> HandlerResult:
            seen.append(context)
            if error is not None:
                raise error
            if advance is not None:
                self.now = self.now + advance
            if stop_first:
                return HandlerResult(HandlerOutcome.STOPPED, "asked to stop")
            if result is None:
                return HandlerResult(HandlerOutcome.SUCCEEDED, "done")
            return result

        handler.description = description  # type: ignore[attr-defined]
        self.registry.register(kind, handler)
        return seen
    def due_task(self) -> datetime:
        """Move the clock to the next task's occurrence so something is due, and return the instant."""
        task = self.store.list_scheduled_tasks()[0]
        self.now = task.next_run_at
        return task.next_run_at


class RegistryTests(WorkerTestCase):
    """What this worker can execute, stated rather than assumed."""

    def test_a_kind_can_only_be_registered_once_unless_replacing_is_intended(self):
        self.register("k.one")
        with self.assertRaises(WorkerConfigurationError):
            self.register("k.one")
        self.registry.register("k.one", lambda context: HandlerResult(HandlerOutcome.REFUSED), replace=True)
        self.assertEqual(self.registry.kinds(), ("k.one",))

    def test_registration_refuses_what_it_cannot_execute(self):
        with self.assertRaises(WorkerConfigurationError):
            self.registry.register("", lambda context: None)
        with self.assertRaises(WorkerConfigurationError):
            self.registry.register("k.one", "not callable")  # type: ignore[arg-type]

    def test_describe_lists_every_kind_with_its_description(self):
        self.register("k.one", description="checks one thing")
        self.register("k.two", description="checks another")

        self.assertEqual(self.registry.kinds(), ("k.one", "k.two"))
        self.assertEqual(self.registry.describe(), ("k.one: checks one thing", "k.two: checks another"))

    def test_an_unregistered_kind_is_reported_as_such(self):
        self.assertIsNone(self.registry.get("k.unknown"))


class SettingsTests(WorkerTestCase):
    """Timings that would make the worker lie about its own health are refused."""

    def test_a_stale_threshold_close_to_the_heartbeat_is_refused(self):
        with self.assertRaises(WorkerConfigurationError) as caught:
            WorkerSettings(heartbeat_seconds=10, stale_after_seconds=20)

        self.assertIn("twice", str(caught.exception))

    def test_impossible_timings_are_refused(self):
        for changes in ({"poll_seconds": 0}, {"heartbeat_seconds": -1},
                        {"stale_after_seconds": 0}, {"max_runs_per_tick": 0}):
            with self.subTest(changes=changes):
                with self.assertRaises(WorkerConfigurationError):
                    WorkerSettings(**changes)  # type: ignore[arg-type]

    def test_a_worker_needs_an_id(self):
        with self.assertRaises(WorkerConfigurationError):
            Worker(self.store, worker_id="  ")


class ClaimAndRunTests(WorkerTestCase):
    """One occurrence, one attempt, and the handler's own words in the record."""

    def test_a_due_occurrence_is_claimed_run_and_recorded_with_its_next_occurrence(self):
        self.schedule()
        seen = self.register("discovery.run")
        worker = self.worker()
        slot = self.due_task()

        executed = worker.tick(now=self.now)

        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0].state, RunState.SUCCEEDED)
        self.assertEqual(executed[0].detail, "done")
        self.assertEqual(executed[0].attempt, 1)
        self.assertEqual(executed[0].slot_at, slot)
        self.assertEqual(executed[0].worker_id, "w1")
        self.assertEqual(len(seen), 1, "the handler ran exactly once")
        self.assertEqual(seen[0].task.task_id, "discovery-run")
        self.assertEqual(seen[0].slot_at, slot)
        self.assertEqual(seen[0].attempt, 1)
        self.assertEqual(seen[0].database_path, str(self.database_path))
        self.assertEqual(seen[0].deadline, self.now + timedelta(seconds=300))
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None
        self.assertEqual(task.last_outcome, RunState.SUCCEEDED)
        self.assertEqual(task.next_run_at, datetime(2026, 10, 15, 18, 30, tzinfo=UTC))
        self.assertEqual([run.run_id for run in self.outcomes], [executed[0].run_id])

    def test_nothing_runs_while_nothing_is_due(self):
        self.schedule()
        self.register("discovery.run")
        worker = self.worker()

        self.assertEqual(worker.tick(now=START), ())
        self.assertEqual(self.store.list_task_runs(), (), "no attempt was recorded for a task not due")

    def test_a_disabled_task_is_never_claimed(self):
        self.schedule(enabled=False)
        self.register("discovery.run")

        self.assertEqual(self.worker().tick(now=self.now + timedelta(days=1)), ())
        self.assertEqual(self.outcomes, [])

    def test_at_most_the_configured_number_of_attempts_run_in_one_tick(self):
        for index in range(3):
            self.schedule(task_id=f"task-{index}", kind="k.one", times=("12:00",))
        self.register("k.one")
        worker = self.worker(settings=WorkerSettings(max_runs_per_tick=2))
        self.due_task()

        first = worker.tick(now=self.now)
        second = worker.tick(now=self.now)

        self.assertEqual(len(first), 2, "a backlog is worked through over ticks, not in one burst")
        self.assertEqual(len(second), 1)
        self.assertEqual(len(self.store.list_task_runs()), 3)

    def test_a_handler_that_refuses_is_recorded_as_a_refusal_and_not_retried(self):
        self.schedule(max_attempts=3, retry_backoff_seconds=60)
        self.register("discovery.run", HandlerResult(HandlerOutcome.REFUSED, "the source gate is closed"))
        worker = self.worker()
        self.due_task()

        executed = worker.tick(now=self.now)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual(executed[0].state, RunState.REFUSED)
        self.assertEqual(executed[0].detail, "the source gate is closed")
        self.assertIsNone(task.pending_slot_at, "a refusal is a decision, not an attempt to repeat")
        self.assertEqual(task.consecutive_failures, 0)

    def test_a_handler_that_raises_is_recorded_as_a_failure_with_its_error(self):
        self.schedule(max_attempts=3, retry_backoff_seconds=60)
        self.register("discovery.run", error=RuntimeError("the backup folder is not writable"))
        worker = self.worker()
        slot = self.due_task()

        executed = worker.tick(now=self.now)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual(executed[0].state, RunState.FAILED)
        self.assertIn("RuntimeError", executed[0].error)
        self.assertIn("not writable", executed[0].error)
        self.assertEqual(task.pending_slot_at, slot)
        self.assertEqual(task.pending_attempt, 2)
        self.assertEqual(task.next_run_at, self.now + timedelta(seconds=60))

    def test_a_handler_that_returns_nothing_has_not_succeeded(self):
        self.schedule()
        self.register("discovery.run", result="not a HandlerResult")  # type: ignore[arg-type]
        worker = self.worker()
        self.due_task()

        executed = worker.tick(now=self.now)

        self.assertEqual(executed[0].state, RunState.FAILED)
        self.assertIn("str", executed[0].error)
        self.assertIn("HandlerResult", executed[0].error)

    def test_a_task_whose_kind_has_no_handler_fails_and_says_what_is_registered(self):
        self.schedule(kind="k.unknown")
        self.register("k.registered")
        worker = self.worker()
        self.due_task()

        executed = worker.tick(now=self.now)

        self.assertEqual(executed[0].state, RunState.FAILED)
        self.assertIn("k.unknown", executed[0].error)
        self.assertIn("k.registered", executed[0].error)

    def test_an_attempt_that_finishes_after_its_deadline_is_timed_out_not_successful(self):
        self.schedule(timeout_seconds=30, max_attempts=2, retry_backoff_seconds=60)
        self.register("discovery.run", advance=timedelta(seconds=31))
        worker = self.worker()
        self.due_task()

        executed = worker.tick(now=self.now)

        self.assertEqual(executed[0].state, RunState.TIMED_OUT,
                         "claiming success after the deadline would promise a bound that was broken")
        self.assertIn("30s deadline", executed[0].detail)

    def test_a_handler_that_stops_at_its_deadline_is_timed_out(self):
        self.schedule(timeout_seconds=30)
        seen = self.register("discovery.run")

        def stopping(context: TaskContext) -> HandlerResult:
            seen.append(context)
            self.now = self.now + timedelta(seconds=30)
            return HandlerResult(HandlerOutcome.STOPPED, "ran out of time")

        self.registry.register("discovery.run", stopping, replace=True)
        worker = self.worker()
        self.due_task()

        executed = worker.tick(now=self.now)

        self.assertEqual(executed[0].state, RunState.TIMED_OUT)
        self.assertIn("deadline", executed[0].error)

    def test_a_handler_that_stops_because_it_was_asked_to_is_interrupted(self):
        self.schedule(max_attempts=3, retry_backoff_seconds=60)
        self.register("discovery.run", stop_first=True)
        worker = self.worker()
        slot = self.due_task()

        executed = worker.tick(now=self.now)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual(executed[0].state, RunState.INTERRUPTED)
        self.assertEqual(executed[0].detail, "asked to stop")
        self.assertIsNone(executed[0].error, "being asked to stop is not an error")
        self.assertEqual(task.pending_slot_at, slot, "the occurrence is still owed")

    def test_a_failed_attempt_is_retried_after_its_backoff_and_then_gives_up(self):
        self.schedule(max_attempts=2, retry_backoff_seconds=60)
        self.register("discovery.run", error=ValueError("first try failed"))
        worker = self.worker()
        slot = self.due_task()

        first = worker.tick(now=self.now)
        early = worker.tick(now=self.now + timedelta(seconds=30))
        second = worker.tick(now=self.now + timedelta(seconds=60))
        third = worker.tick(now=self.now + timedelta(seconds=120))
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual(first[0].state, RunState.FAILED)
        self.assertEqual(early, (), "the retry waits for its backoff")
        self.assertEqual(second[0].attempt, 2)
        self.assertEqual(second[0].slot_at, slot, "the retry serves the occurrence it owes")
        self.assertEqual(third, (), "attempts are exhausted, so the occurrence is given up on")
        self.assertIsNone(task.pending_slot_at)
        self.assertEqual(task.consecutive_failures, 2)
        self.assertEqual(task.next_run_at, datetime(2026, 10, 15, 18, 30, tzinfo=UTC),
                         "the next scheduled occurrence still runs")

    def test_a_run_whose_task_has_vanished_is_refused_rather_than_guessed_at(self):
        self.schedule()
        self.register("discovery.run")
        worker = self.worker()
        self.due_task()
        claimed = self.store.claim_due_run(worker_id="w1", now=self.now)
        assert claimed is not None
        original = self.store.get_scheduled_task

        self.store.get_scheduled_task = lambda task_id: None  # type: ignore[method-assign]
        self.addCleanup(setattr, self.store, "get_scheduled_task", original)

        with self.assertRaises(TaskRunConflict) as caught:
            worker.execute(claimed, now=self.now)
        self.assertIn("no longer", str(caught.exception))


class LoopTests(WorkerTestCase):
    """The loop: the lease, ticks, stopping, and what a stop leaves behind."""

    def test_running_the_loop_takes_the_lease_and_gives_it_back(self):
        self.schedule()
        self.register("discovery.run")
        worker = self.worker()

        ticks = worker.run(max_ticks=2)
        self.now = self.now + timedelta(minutes=1)

        self.assertEqual(ticks, 2)
        self.assertIsNone(worker.lease)
        self.assertIsNone(self.store.get_worker_lease(), "a stopped worker holds nothing")

    def test_a_second_worker_is_refused_while_the_first_holds_the_lease(self):
        first = self.worker(worker_id="w1")
        first.acquire_lease(now=self.now)
        second = self.worker(worker_id="w2")

        with self.assertRaises(WorkerLeaseHeld) as caught:
            second.run(max_ticks=1)

        self.assertIn("w1", str(caught.exception))
        self.assertEqual(self.store.get_worker_lease().worker_id, "w1")

    def test_the_lease_is_released_even_when_a_tick_raises(self):
        worker = self.worker()
        worker.acquire_lease(now=self.now)
        worker.tick = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]

        with self.assertRaises(RuntimeError):
            worker.run(max_ticks=1)

        self.assertIsNone(self.store.get_worker_lease())

    def test_a_stop_request_stops_the_loop_and_the_attempt_it_interrupted_is_recorded(self):
        self.schedule(max_attempts=3)
        worker = self.worker()

        def handler(context: TaskContext) -> HandlerResult:
            worker.request_stop()
            return HandlerResult(HandlerOutcome.STOPPED, "stopping as asked")

        self.registry.register("discovery.run", handler)
        self.due_task()

        ticks = worker.run(max_ticks=5)
        runs = self.store.list_task_runs()

        self.assertEqual(ticks, 1, "the loop stopped after the tick in which it was asked to")
        self.assertEqual(runs[0].state, RunState.INTERRUPTED)
        self.assertIsNone(self.store.get_worker_lease())

    def test_an_external_stop_event_ends_the_loop_without_ticks(self):
        self.schedule()
        worker = self.worker()
        stop = threading.Event()
        stop.set()

        ticks = worker.run(max_ticks=3, stop_event=stop)

        self.assertEqual(ticks, 0)
        self.assertEqual(self.store.list_task_runs(), ())
        self.assertIsNone(self.store.get_worker_lease())

    def test_each_tick_keeps_the_lease_alive(self):
        worker = self.worker()
        worker.acquire_lease(now=self.now)

        worker.tick(now=self.now + timedelta(seconds=10))

        self.assertEqual(self.store.get_worker_lease().heartbeat_at, self.now + timedelta(seconds=10))

    def test_a_worker_that_lost_its_lease_stops_instead_of_working_on(self):
        worker = self.worker(worker_id="w1")
        worker.acquire_lease(now=self.now)
        # Another worker takes over after this one's heartbeat went stale.
        stolen = self.now + timedelta(minutes=10)
        self.store.acquire_worker_lease("w2", now=stolen, stale_before=stolen - timedelta(minutes=5))

        with self.assertRaises(WorkerLeaseHeld) as caught:
            worker.tick(now=stolen + timedelta(seconds=1))

        self.assertIn("w2", str(caught.exception))

    def test_an_attempt_whose_worker_stopped_is_recovered_and_then_run_again(self):
        self.schedule(max_attempts=2, retry_backoff_seconds=60)
        self.register("discovery.run")
        worker = self.worker()
        slot = self.due_task()
        claimed = self.store.claim_due_run(worker_id="w1", now=self.now)
        assert claimed is not None
        worker.acquire_lease(now=self.now)

        # The clock jumps past the stale threshold: the attempt above can no longer be alive.
        later = self.now + timedelta(minutes=5)
        self.now = later
        worker.tick(now=later)
        recovered = self.store.get_task_run(claimed.run_id)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None and recovered is not None

        self.assertEqual(recovered.state, RunState.INTERRUPTED)
        self.assertEqual(task.pending_attempt, 2, "the interrupted attempt is owed another try")

        worker.tick(now=later + timedelta(seconds=60))
        runs = self.store.list_task_runs()

        self.assertEqual([run.state for run in runs], [RunState.SUCCEEDED, RunState.INTERRUPTED])
        self.assertEqual(runs[0].slot_at, slot, "the retry serves the occurrence it owes")
        self.assertEqual(runs[0].attempt, 2)

    def test_zero_ticks_is_a_valid_request(self):
        self.assertEqual(self.worker().run(max_ticks=0), 0)
        self.assertIsNone(self.store.get_worker_lease(), "a zero-tick run holds no lease afterwards")

    def test_a_negative_tick_limit_is_refused(self):
        with self.assertRaises(WorkerConfigurationError):
            self.worker().run(max_ticks=-1)


class StatusTests(WorkerTestCase):
    """The read-only report: what is scheduled, what is running, and what happened."""

    def test_a_database_with_no_worker_says_so(self):
        lines = worker_status(self.store, now=self.now).describe(now=self.now)

        self.assertIn("No worker holds the lease for this database, so nothing is scheduled to run.",
                      lines)
        self.assertIn("No attempt is in progress.", lines)
        self.assertIn("No attempt has been recorded yet.", lines)

    def test_the_report_names_the_lease_the_next_task_and_recent_outcomes(self):
        self.schedule()
        self.register("discovery.run")
        worker = self.worker()
        worker.acquire_lease(now=self.now)
        self.due_task()
        worker.tick(now=self.now)
        self.schedule(task_id="later-task", kind="k.other", times=("15:00",))

        status = worker_status(self.store, now=self.now + timedelta(seconds=30))
        lines = status.describe(now=self.now + timedelta(seconds=30))

        self.assertEqual(status.lease.worker_id, "w1")
        self.assertTrue(any("Worker w1 holds the lease" in line for line in lines))
        self.assertTrue(any("Recent attempts:" in line for line in lines))
        self.assertTrue(any("discovery-run attempt 1: succeeded" in line for line in lines))
        self.assertTrue(any("Next: later-task" in line for line in lines))
        self.assertFalse(any("(due now)" in line for line in lines),
                         "the next task is scheduled for 15:00 IST, which is not yet due")

    def test_an_overdue_task_is_marked_overdue_and_a_running_attempt_is_shown(self):
        self.schedule()
        self.register("discovery.run")
        worker = self.worker()
        slot = self.due_task()
        claimed = self.store.claim_due_run(worker_id="w1", now=slot)
        assert claimed is not None

        status = worker_status(self.store, now=slot + timedelta(minutes=5))
        lines = status.describe(now=slot + timedelta(minutes=5))

        self.assertEqual([run.run_id for run in status.running], [claimed.run_id])
        self.assertTrue(any("In progress: discovery-run attempt 1" in line for line in lines))
        self.assertTrue(any("(due now)" in line for line in lines),
                        "the occurrence is in the past and still the next one to serve")

    def test_an_occurrence_the_schedule_stepped_over_is_reported_with_its_instant(self):
        """The laptop-off case: a run finished, the process then did not, and the schedule moved on.

        The occurrence a worker will still claim is *not* in this list - that one is overdue, and the
        status line says so - so what is reported is exactly what nothing will ever come back to.
        """
        self.schedule(task_id="daily-backup", times=("23:30",))
        slot = self.due_task()
        claimed = self.store.claim_due_run(worker_id="w1", now=slot)
        self.store.finish_run(claimed.run_id, RunState.SUCCEEDED, detail="wrote one snapshot", now=slot)

        three_days_later = slot + timedelta(days=3, hours=1)
        missed = missed_occurrences(self.store, now=three_days_later)

        task = self.store.get_scheduled_task("daily-backup")
        self.assertEqual(task.next_run_at, slot + timedelta(days=1),
                         "the run plans the next occurrence from the instant the process finished")
        self.assertEqual([item.slot_at for item in missed],
                         [slot + timedelta(days=2), slot + timedelta(days=3)],
                         "the occurrences after the one a worker will still claim, and only those")
        self.assertEqual({item.task_id for item in missed}, {"daily-backup"})
        lines = worker_status(self.store, now=three_days_later).describe(now=three_days_later)
        self.assertTrue(any("(due now)" in line for line in lines), "and the status calls it overdue")
        self.assertTrue(any(line.startswith("Missed while nothing was running (2 occurrence(s)") for line
                            in lines), lines)
        self.assertTrue(any("Nothing is catching up on these" in line for line in lines))

    def test_an_attempt_of_any_state_is_not_a_missed_occurrence(self):
        """Refused, failed and interrupted are all attempts: the schedule reached them and acted."""
        made = []
        for state in (RunState.REFUSED, RunState.FAILED, RunState.INTERRUPTED):
            task_id = f"task-{state.value}"
            self.schedule(task_id=task_id, times=("23:30",))
            slot = self.store.get_scheduled_task(task_id).next_run_at
            self.now = slot
            claimed = self.store.claim_due_run(worker_id="w1", now=slot)
            self.store.finish_run(claimed.run_id, state, detail=state.value, now=slot)
            made.append((task_id, slot))

        later = made[0][1] + timedelta(days=3)
        reported = missed_occurrences(self.store, now=later)

        for task_id, slot in made:
            with self.subTest(task_id):
                self.assertNotIn((task_id, slot), [(item.task_id, item.slot_at) for item in reported],
                                 "the occurrence that produced a run row is never reported as missed")
        self.assertTrue(reported, "the later occurrences the process stepped over are still reported")

    def test_a_retry_that_is_owed_is_pending_rather_than_missed(self):
        """A failure with attempts left keeps the occurrence: it is owed, so it is not lost."""
        self.schedule(times=("23:30",), max_attempts=2)
        slot = self.due_task()
        claimed = self.store.claim_due_run(worker_id="w1", now=slot)
        self.store.finish_run(claimed.run_id, RunState.FAILED, error="boom", now=slot)
        task = self.store.get_scheduled_task("discovery-run")
        self.assertEqual(task.pending_slot_at, slot, "the occurrence is kept, not replaced")

        missed = missed_occurrences(self.store, now=task.next_run_at + timedelta(seconds=1))

        self.assertNotIn(slot, [item.slot_at for item in missed])

    def test_a_paused_task_is_not_accused_of_missing_anything(self):
        self.schedule(times=("23:30",))
        slot = self.due_task()
        self.store.save_scheduled_task(
            self.store.get_scheduled_task("discovery-run").with_definition(enabled=False))

        missed = missed_occurrences(self.store, now=slot + timedelta(days=5))

        self.assertEqual(missed, (), "nothing was expected of a paused task")

    def test_occurrences_from_before_the_task_existed_are_not_reported(self):
        """A task added this morning must not be blamed for the days before it was written."""
        self.now = START + timedelta(days=5)
        self.schedule(times=("23:30",))

        missed = missed_occurrences(self.store, now=self.now + timedelta(hours=2))

        task = self.store.get_scheduled_task("discovery-run")
        self.assertLess(task.created_at, task.next_run_at)
        self.assertEqual([item.slot_at for item in missed], [],
                         "the window starts at the task's own creation, and its first occurrence is next")

    def test_the_report_looks_back_a_bounded_window(self):
        """Thirty days of silence is answered with the window's worth, and the window is a real bound."""
        self.schedule(times=("00:00", "12:00"))
        self.now = START + timedelta(days=30)

        week = missed_occurrences(self.store, now=self.now)
        day = missed_occurrences(self.store, now=self.now, lookback_days=1)

        self.assertTrue(day, "the fixture must have something to report, or this proves nothing")
        self.assertLess(len(day), len(week), "a longer window looks further back")
        self.assertEqual([item.slot_at for item in week if item.slot_at >= self.now - timedelta(days=1)],
                         [item.slot_at for item in day],
                         "the short window is exactly the tail of the long one")
        self.assertGreaterEqual(week[0].slot_at, self.now - timedelta(days=MISSED_LOOKBACK_DAYS),
                                "nothing older than the window is reported")
        self.assertLessEqual(len(week), MISSED_LOOKBACK_DAYS * 2,
                             "two occurrences a day is the most this schedule can hold")

    def test_the_window_must_be_a_positive_number_of_whole_days(self):
        self.schedule()
        for value in (0, -1, 1.5, True):
            with self.subTest(value):
                with self.assertRaises(ValueError):
                    missed_occurrences(self.store, now=self.now, lookback_days=value)  # type: ignore[arg-type]

    def test_asking_what_was_missed_changes_nothing(self):
        """Reading the report is a read: no lease, no run row, no event, no bookkeeping moved."""
        self.schedule(times=("23:30",))
        slot = self.due_task()
        task_before = self.store.get_scheduled_task("discovery-run")
        lines_before = _event_line_count(self.database_path)

        missed = missed_occurrences(self.store, now=slot + timedelta(days=4))

        self.assertTrue(missed, "the fixture has something to report, or this proves nothing")
        self.assertEqual(self.store.list_task_runs(), ())
        self.assertIsNone(self.store.get_worker_lease())
        self.assertEqual(self.store.get_scheduled_task("discovery-run"), task_before)
        self.assertEqual(_event_line_count(self.database_path), lines_before,
                         "reading the report writes no event and takes no lease")

    def test_asking_for_the_status_claims_nothing(self):
        self.schedule()
        self.due_task()

        worker_status(self.store, now=self.now)

        self.assertEqual(self.store.list_task_runs(), ())
        self.assertIsNone(self.store.get_worker_lease())


if __name__ == "__main__":  # pragma: no cover - convenience for running this file alone
    unittest.main()
