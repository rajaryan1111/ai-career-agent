"""Tests for the scheduler's storage: durable tasks, one run per occurrence, leases, and recovery.

These are the properties the background scheduler stands on, so they are tested against real files
rather than in memory: a claim that survives a restart is a claim written to disk, and two workers
racing is a second connection to the same database.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career_agent.store import (
    CareerStore, StoredRecordError, TaskRunConflict, SCHEMA_VERSION,
)
from career_agent.tasks import (
    RunState, ScheduledTask, TaskValidationError, WorkerLeaseHeld, build_task, slot_key,
)

UTC = timezone.utc
#: 2026-10-15 11:30 IST - thirty minutes before the default noon occurrence.
RUNTIME = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)


class SchedulerStoreTestCase(unittest.TestCase):
    """A temporary database per test, closed even when the test fails."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.directory = Path(self._temp.name)
        self.database_path = self.directory / "career_agent.sqlite3"
        self.addCleanup(self._temp.cleanup)
        self.store = CareerStore(self.database_path)
        self.addCleanup(self.store.close)

    def default_task(self, **changes) -> ScheduledTask:
        fields = {
            "task_id": "discovery-run", "name": "Scheduled discovery", "kind": "discovery.run",
            "times": ("00:00", "12:00"), "timezone": "Asia/Kolkata",
        }
        fields.update(changes)
        return build_task(**fields, now=RUNTIME)  # type: ignore[arg-type]


class SchemaTests(SchedulerStoreTestCase):
    """The new tables are part of the schema contract, and the upgrade keeps the data."""

    def test_a_new_database_is_created_at_the_current_version_with_the_task_tables(self):
        version = self.store._connection.execute("PRAGMA user_version").fetchone()[0]
        names = {row[0] for row in
                 self.store._connection.execute(
                     "SELECT name FROM sqlite_master WHERE type = 'table'")}

        self.assertEqual(version, SCHEMA_VERSION)
        self.assertEqual(SCHEMA_VERSION, 8)
        for table in ("scheduled_task", "task_run", "worker_lease"):
            self.assertIn(table, names)

    def test_a_database_from_the_previous_version_upgrades_and_keeps_its_rows(self):
        older = self.directory / "older.sqlite3"
        connection = sqlite3.connect(str(older))
        try:
            connection.execute(
                """CREATE TABLE candidate_profile (
                       profile_id INTEGER PRIMARY KEY CHECK (profile_id = 1),
                       payload TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            connection.execute(
                """CREATE TABLE job_listings (
                       listing_id TEXT PRIMARY KEY, payload TEXT NOT NULL, duplicate_key TEXT NOT NULL,
                       first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL)""")
            connection.execute(
                """CREATE TABLE application_tracker (
                       listing_id TEXT PRIMARY KEY REFERENCES job_listings(listing_id) ON DELETE CASCADE,
                       status TEXT NOT NULL, status_evidence TEXT,
                       candidate_confirmed INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)""")
            connection.execute(
                """CREATE TABLE application_activity (
                       activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                       listing_id TEXT NOT NULL REFERENCES job_listings(listing_id) ON DELETE CASCADE,
                       occurred_on TEXT NOT NULL, recorded_at TEXT NOT NULL, kind TEXT NOT NULL,
                       detail TEXT NOT NULL)""")
            connection.execute(
                """INSERT INTO job_listings(listing_id, payload, duplicate_key, first_seen_at, last_seen_at)
                   VALUES ('j1', '{}', 'dk1', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')""")
            connection.execute("PRAGMA user_version = 2")
            connection.commit()
        finally:
            connection.close()

        with CareerStore(older) as upgraded:
            jobs = upgraded._connection.execute("SELECT listing_id FROM job_listings").fetchall()
            version = upgraded._connection.execute("PRAGMA user_version").fetchone()[0]
            task = upgraded.save_scheduled_task(self.default_task(), now=RUNTIME)

        self.assertEqual(version, SCHEMA_VERSION)
        self.assertEqual([row[0] for row in jobs], ["j1"], "the existing row must survive the upgrade")
        self.assertEqual(task.task_id, "discovery-run")
        # The upgrade is a schema change to a database somebody was using, so it was copied first.
        snapshots = list(self.directory.glob("older.sqlite3.backup-*"))
        self.assertEqual(len(snapshots), 1, f"expected one pre-upgrade copy, found {snapshots}")


class TaskDefinitionStorageTests(SchedulerStoreTestCase):
    """What storing a definition does, and what it deliberately does not do."""

    def test_a_new_task_is_due_at_the_next_occurrence_and_reads_back(self):
        stored = self.store.save_scheduled_task(self.default_task(), now=RUNTIME)

        self.assertEqual(stored.next_run_at, datetime(2026, 10, 15, 6, 30, tzinfo=UTC))
        self.assertTrue(stored.enabled)
        self.assertEqual(stored.consecutive_failures, 0)
        self.assertIsNone(stored.last_outcome)
        self.assertEqual(self.store.get_scheduled_task("discovery-run"), stored)

    def test_editing_a_task_that_is_already_due_does_not_move_or_skip_its_occurrence(self):
        stored = self.store.save_scheduled_task(self.default_task(), now=RUNTIME)

        # A person edits the name and the limits five minutes after the occurrence was due but before
        # it has run. Renaming a task must not silently skip the run it owes.
        later = stored.next_run_at + timedelta(minutes=5)
        again = self.store.save_scheduled_task(
            self.default_task(name="Discovery (renamed)", timeout_seconds=600, max_attempts=2),
            now=later)

        self.assertEqual(again.next_run_at, stored.next_run_at)
        self.assertEqual(again.name, "Discovery (renamed)")
        self.assertEqual(again.timeout_seconds, 600)
        self.assertTrue(self.store.next_due_task(later) is not None, "the task is still due")
        claimed = self.store.claim_due_run(worker_id="w1", now=later)
        self.assertIsNotNone(claimed, "the occurrence that was due is still runnable")
        self.assertEqual(claimed.slot_at, stored.next_run_at)

    def test_changing_the_times_recomputes_the_occurrence_and_drops_a_held_retry(self):
        stored = self.store.save_scheduled_task(self.default_task(max_attempts=3), now=RUNTIME)
        claim = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)
        assert claim is not None
        self.store.finish_run(claim.run_id, RunState.FAILED, error="reader failed", now=stored.next_run_at)
        held = self.store.get_scheduled_task("discovery-run")
        assert held is not None
        self.assertTrue(held.retry_pending, "a failure with attempts left holds the occurrence")

        changed = self.store.save_scheduled_task(
            self.default_task(times=("03:00", "15:00"), max_attempts=3), now=stored.next_run_at)

        self.assertIsNone(changed.pending_slot_at, "the occurrence it owed belonged to the old schedule")
        self.assertEqual(changed.next_run_at, datetime(2026, 10, 15, 9, 30, tzinfo=UTC),
                         "03:00 IST on 15 October")
        self.assertEqual(changed.last_outcome, RunState.FAILED,
                         "the failure stays visible; changing a schedule does not erase history")

    def test_disabling_pauses_without_losing_the_occurrence_and_enabling_does_not_replay_it(self):
        stored = self.store.save_scheduled_task(self.default_task(), now=RUNTIME)
        claim = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)
        assert claim is not None
        self.store.finish_run(claim.run_id, RunState.FAILED, now=stored.next_run_at)

        paused = self.store.save_scheduled_task(self.default_task(enabled=False), now=stored.next_run_at)
        self.assertIsNone(paused.next_run_at)
        self.assertIsNotNone(paused.pending_slot_at, "the owed occurrence is kept while paused")
        self.assertIsNone(self.store.next_due_task(stored.next_run_at + timedelta(days=3)))

        resumed = self.store.save_scheduled_task(self.default_task(), now=stored.next_run_at + timedelta(days=3))
        self.assertIsNotNone(resumed.next_run_at)
        self.assertGreater(resumed.next_run_at, stored.next_run_at + timedelta(days=2),
                           "resuming schedules the next occurrence from now, not the missed ones")
        self.assertIsNone(resumed.pending_slot_at)

    def test_tasks_are_listed_in_a_stable_order_and_can_be_removed_with_their_history(self):
        first = self.store.save_scheduled_task(self.default_task(), now=RUNTIME)
        second = self.store.save_scheduled_task(
            self.default_task(task_id="backup-daily", name="Daily backup", kind="backup.snapshot"),
            now=RUNTIME)

        self.assertEqual([task.task_id for task in self.store.list_scheduled_tasks()],
                         ["backup-daily", "discovery-run"])

        claim = self.store.claim_due_run(worker_id="w1", now=first.next_run_at)
        assert claim is not None and second is not None
        self.store.finish_run(claim.run_id, RunState.SUCCEEDED, now=first.next_run_at)

        self.assertTrue(self.store.delete_scheduled_task("discovery-run"))
        self.assertFalse(self.store.delete_scheduled_task("discovery-run"))
        self.assertEqual(self.store.list_task_runs(task_id="discovery-run"), (),
                         "a deleted task takes its run history with it")


class ClaimTests(SchedulerStoreTestCase):
    """Claiming: one occurrence, one run, whoever asks."""

    def test_nothing_is_claimed_while_no_task_is_due(self):
        stored = self.store.save_scheduled_task(self.default_task(), now=RUNTIME)

        self.assertIsNone(self.store.next_due_task(RUNTIME))
        self.assertIsNone(self.store.claim_due_run(worker_id="w1", now=RUNTIME))

        self.assertEqual(self.store.running_runs(), ())
        self.assertEqual(self.store.get_scheduled_task("discovery-run").next_run_at, stored.next_run_at)

    def test_a_due_task_is_claimed_once_with_the_instant_the_schedule_named(self):
        stored = self.store.save_scheduled_task(self.default_task(), now=RUNTIME)

        claimed = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)

        assert claimed is not None
        self.assertEqual(claimed.state, RunState.RUNNING)
        self.assertEqual(claimed.attempt, 1)
        self.assertEqual(claimed.slot_at, stored.next_run_at)
        self.assertEqual(claimed.slot_key, slot_key("discovery-run", stored.next_run_at))
        self.assertEqual(claimed.worker_id, "w1")
        self.assertEqual(self.store.running_runs(worker_id="w1"), (claimed,))

    def test_a_second_worker_is_told_nothing_was_claimed_rather_than_given_the_run(self):
        stored = self.store.save_scheduled_task(self.default_task(), now=RUNTIME)
        other = CareerStore(self.database_path)
        self.addCleanup(other.close)
        first = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)

        second = other.claim_due_run(worker_id="w2", now=stored.next_run_at)

        self.assertIsNotNone(first)
        self.assertIsNone(second, "an occurrence that is already claimed is not claimed twice")
        self.assertEqual(other.running_runs(), (first,))

    def test_the_earliest_due_task_is_the_one_claimed(self):
        late = self.store.save_scheduled_task(
            self.default_task(task_id="late", times=("15:00",), name="Late", kind="k.late"),
            now=RUNTIME)
        self.store.save_scheduled_task(
            self.default_task(task_id="early", times=("12:00",), name="Early", kind="k.early"),
            now=RUNTIME)

        claimed = self.store.claim_due_run(worker_id="w1", now=late.next_run_at)

        assert claimed is not None
        self.assertEqual(claimed.task_id, "early", "the earliest due task goes first")
        self.assertLess(claimed.slot_at, late.next_run_at)

    def test_a_claim_needs_a_named_worker(self):
        with self.assertRaises(ValueError):
            self.store.claim_due_run(worker_id="   ", now=RUNTIME)


class FinishRunTests(SchedulerStoreTestCase):
    """Recording an outcome: once, by the worker that claimed it, and with the task moved on."""

    def claimed(self, **changes):
        stored = self.store.save_scheduled_task(self.default_task(**changes), now=RUNTIME)
        claimed = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)
        assert claimed is not None
        return stored, claimed

    def test_a_success_is_recorded_with_the_task_moving_to_its_next_occurrence(self):
        stored, claimed = self.claimed()

        finished = self.store.finish_run(claimed.run_id, RunState.SUCCEEDED, detail="nothing to do",
                                         worker_id="w1", now=stored.next_run_at + timedelta(seconds=2))
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual(finished.state, RunState.SUCCEEDED)
        self.assertEqual(finished.detail, "nothing to do")
        self.assertEqual(finished.duration_seconds, 2.0)
        self.assertEqual(task.last_outcome, RunState.SUCCEEDED)
        self.assertEqual(task.consecutive_failures, 0)
        self.assertIsNone(task.pending_slot_at)
        self.assertEqual(task.next_run_at, datetime(2026, 10, 15, 18, 30, tzinfo=UTC))

    def test_a_refusal_is_recorded_as_a_refusal_and_does_not_count_against_the_task(self):
        stored, claimed = self.claimed()

        finished = self.store.finish_run(claimed.run_id, RunState.REFUSED,
                                         detail="the source gate is closed", now=stored.next_run_at)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual(finished.state, RunState.REFUSED)
        self.assertEqual(task.last_outcome, RunState.REFUSED)
        self.assertEqual(task.consecutive_failures, 0,
                         "a rule that says no is not a malfunction of the task")

    def test_a_failure_with_attempts_left_comes_back_to_the_same_occurrence(self):
        stored, claimed = self.claimed(max_attempts=3, retry_backoff_seconds=60)
        moment = stored.next_run_at

        self.store.finish_run(claimed.run_id, RunState.FAILED, error="the disk was busy", now=moment)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual(task.pending_slot_at, moment)
        self.assertEqual(task.pending_attempt, 2)
        self.assertEqual(task.next_run_at, moment + timedelta(seconds=60))
        self.assertEqual(task.consecutive_failures, 1)
        self.assertEqual(task.last_error, "the disk was busy")
        self.assertIsNone(self.store.claim_due_run(worker_id="w1", now=moment + timedelta(seconds=30)),
                          "the retry waits for its backoff")

        retry = self.store.claim_due_run(worker_id="w1", now=task.next_run_at)
        assert retry is not None
        self.assertEqual(retry.attempt, 2)
        self.assertEqual(retry.slot_at, moment, "the retry serves the occurrence it owes")

    def test_the_last_attempt_at_failure_returns_the_task_to_its_schedule(self):
        stored, claimed = self.claimed(max_attempts=1)

        self.store.finish_run(claimed.run_id, RunState.FAILED, error="no luck", now=stored.next_run_at)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertIsNone(task.pending_slot_at)
        self.assertEqual(task.next_run_at, datetime(2026, 10, 15, 18, 30, tzinfo=UTC),
                         "the next scheduled occurrence still runs")
        self.assertEqual(task.last_outcome, RunState.FAILED)

    def test_a_timeout_is_its_own_outcome_in_the_history(self):
        stored, claimed = self.claimed()

        finished = self.store.finish_run(claimed.run_id, RunState.TIMED_OUT,
                                         detail="the handler did not finish in 300s", now=stored.next_run_at)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual(finished.state, RunState.TIMED_OUT)
        self.assertEqual(task.last_outcome, RunState.TIMED_OUT)
        self.assertEqual(task.consecutive_failures, 1, "a timed-out attempt did not do its work")

    def test_a_run_cannot_be_finished_twice_by_anyone(self):
        stored, claimed = self.claimed()
        self.store.finish_run(claimed.run_id, RunState.SUCCEEDED, now=stored.next_run_at)

        with self.assertRaises(TaskRunConflict) as caught:
            self.store.finish_run(claimed.run_id, RunState.FAILED, now=stored.next_run_at)

        self.assertIn("already finished as succeeded", str(caught.exception))
        self.assertEqual(self.store.get_task_run(claimed.run_id).state, RunState.SUCCEEDED)

    def test_only_the_worker_that_claimed_a_run_may_finish_it(self):
        stored, claimed = self.claimed()

        with self.assertRaises(TaskRunConflict) as caught:
            self.store.finish_run(claimed.run_id, RunState.SUCCEEDED, worker_id="w2",
                                  now=stored.next_run_at)

        self.assertIn("claimed by w1", str(caught.exception))
        self.assertEqual(self.store.get_task_run(claimed.run_id).state, RunState.RUNNING)

    def test_a_missing_run_and_an_unfinished_state_are_refused(self):
        with self.assertRaises(TaskRunConflict):
            self.store.finish_run("no-such-run", RunState.SUCCEEDED, now=RUNTIME)

        stored, claimed = self.claimed()
        for state in (RunState.RUNNING, RunState.PENDING):
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    self.store.finish_run(claimed.run_id, state, now=stored.next_run_at)

    def test_detail_and_error_text_is_stored_as_one_bounded_line(self):
        stored, claimed = self.claimed()

        finished = self.store.finish_run(
            claimed.run_id, RunState.FAILED, detail="line one\nline two",
            error="boom\r\n  again", now=stored.next_run_at)

        self.assertEqual(finished.detail, "line one line two")
        self.assertEqual(finished.error, "boom again")


class HeartbeatAndRecoveryTests(SchedulerStoreTestCase):
    """The difference between work in progress and work whose worker is gone."""

    def claimed(self, **changes):
        stored = self.store.save_scheduled_task(self.default_task(**changes), now=RUNTIME)
        claimed = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)
        assert claimed is not None
        return stored, claimed

    def test_a_heartbeat_touches_only_a_running_run_of_that_worker(self):
        stored, claimed = self.claimed()
        later = stored.next_run_at + timedelta(seconds=30)

        self.assertTrue(self.store.heartbeat_run(claimed.run_id, worker_id="w1", now=later))
        self.assertEqual(self.store.get_task_run(claimed.run_id).heartbeat_at, later)
        self.assertFalse(self.store.heartbeat_run(claimed.run_id, worker_id="w2", now=later),
                         "another worker's heartbeat must not look like this run's")

        self.store.finish_run(claimed.run_id, RunState.SUCCEEDED, now=later)
        self.assertFalse(self.store.heartbeat_run(claimed.run_id, worker_id="w1", now=later),
                         "a finished run is not in progress")

    def test_a_run_whose_worker_stopped_is_closed_and_the_occurrence_replanned(self):
        stored, claimed = self.claimed(max_attempts=2, retry_backoff_seconds=30)
        stale = stored.next_run_at + timedelta(seconds=1)

        recovered = self.store.recover_stale_runs(stale, now=stale)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None

        self.assertEqual([run.run_id for run in recovered], [claimed.run_id])
        self.assertEqual(recovered[0].state, RunState.INTERRUPTED)
        self.assertIn("no heartbeat", recovered[0].detail)
        self.assertEqual(task.pending_attempt, 2, "an interrupted attempt still gets its remaining try")
        self.assertEqual(task.next_run_at, stale + timedelta(seconds=30))

    def test_recovery_leaves_a_run_whose_heartbeat_is_fresh_alone(self):
        stored, claimed = self.claimed()
        fresh = stored.next_run_at + timedelta(seconds=5)
        self.store.heartbeat_run(claimed.run_id, worker_id="w1", now=fresh)

        recovered = self.store.recover_stale_runs(fresh - timedelta(seconds=10), now=fresh)

        self.assertEqual(recovered, ())
        self.assertEqual(self.store.get_task_run(claimed.run_id).state, RunState.RUNNING)

    def test_recovery_of_several_runs_is_complete_and_idempotent(self):
        stored = self.store.save_scheduled_task(self.default_task(max_attempts=3), now=RUNTIME)
        first = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)
        assert first is not None
        self.store.finish_run(first.run_id, RunState.FAILED, now=stored.next_run_at)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None
        second = self.store.claim_due_run(worker_id="w1", now=task.next_run_at)
        assert second is not None

        threshold = task.next_run_at + timedelta(seconds=1)
        recovered = self.store.recover_stale_runs(threshold, now=threshold)

        self.assertEqual([run.run_id for run in recovered], [second.run_id])
        self.assertEqual(self.store.recover_stale_runs(threshold, now=threshold), (),
                         "an interrupted run is not recovered twice")

    def test_a_recovered_run_cannot_be_finished_again_by_its_old_worker(self):
        stored, claimed = self.claimed()
        self.store.recover_stale_runs(stored.next_run_at + timedelta(seconds=1),
                                      now=stored.next_run_at + timedelta(seconds=1))

        with self.assertRaises(TaskRunConflict):
            self.store.finish_run(claimed.run_id, RunState.SUCCEEDED, worker_id="w1",
                                  now=stored.next_run_at + timedelta(seconds=2))


class RunHistoryTests(SchedulerStoreTestCase):
    """The history view: newest first, bounded, and per task when asked."""

    def test_history_is_newest_first_and_can_be_narrowed_to_one_task(self):
        stored = self.store.save_scheduled_task(self.default_task(max_attempts=3), now=RUNTIME)
        first = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)
        assert first is not None
        self.store.finish_run(first.run_id, RunState.SUCCEEDED, detail="first", now=stored.next_run_at)
        task = self.store.get_scheduled_task("discovery-run")
        assert task is not None
        second = self.store.claim_due_run(worker_id="w1", now=task.next_run_at)
        assert second is not None
        self.store.finish_run(second.run_id, RunState.SUCCEEDED, detail="second", now=task.next_run_at)
        self.store.save_scheduled_task(
            self.default_task(task_id="other", name="Other", kind="k.other"), now=RUNTIME)

        everything = self.store.list_task_runs()
        mine = self.store.list_task_runs(task_id="discovery-run", limit=1)

        self.assertEqual([run.detail for run in everything], ["second", "first"])
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].detail, "second")
        self.assertEqual(self.store.list_task_runs(task_id="other"), ())

    def test_the_history_limit_must_be_a_positive_whole_number(self):
        for limit in (0, -1, True, 2.5):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    self.store.list_task_runs(limit=limit)


class WorkerLeaseTests(SchedulerStoreTestCase):
    """One scheduler per database, with an honest way back when the holder died."""

    def test_the_first_worker_takes_the_lease_and_a_second_is_refused_while_it_is_fresh(self):
        lease = self.store.acquire_worker_lease("w1", now=RUNTIME)

        self.assertEqual(lease.worker_id, "w1")
        self.assertEqual(lease.acquired_at, RUNTIME)

        with self.assertRaises(WorkerLeaseHeld) as caught:
            self.store.acquire_worker_lease("w2", now=RUNTIME + timedelta(seconds=5),
                                            stale_before=RUNTIME)
        self.assertIn("w1", str(caught.exception))
        self.assertEqual(self.store.get_worker_lease().worker_id, "w1")

    def test_the_holder_refreshes_its_own_lease_and_a_second_connection_sees_it(self):
        self.store.acquire_worker_lease("w1", now=RUNTIME)
        other = CareerStore(self.database_path)
        self.addCleanup(other.close)

        refreshed = other.heartbeat_worker_lease("w1", now=RUNTIME + timedelta(seconds=30))

        assert refreshed is not None
        self.assertEqual(refreshed.heartbeat_at, RUNTIME + timedelta(seconds=30))
        self.assertEqual(refreshed.acquired_at, RUNTIME, "refreshing is not re-acquiring")
        self.assertIsNone(other.heartbeat_worker_lease("w2", now=RUNTIME + timedelta(seconds=30)),
                          "a worker that does not hold the lease cannot refresh it")

    def test_a_stale_lease_is_taken_over_rather_than_left_blocking_everything(self):
        self.store.acquire_worker_lease("w1", now=RUNTIME)

        taken = self.store.acquire_worker_lease("w2", now=RUNTIME + timedelta(minutes=10),
                                                stale_before=RUNTIME + timedelta(minutes=5))

        self.assertEqual(taken.worker_id, "w2")
        self.assertEqual(taken.acquired_at, RUNTIME + timedelta(minutes=10))
        self.assertFalse(self.store.release_worker_lease("w1"),
                         "the old holder cannot release a lease it no longer has")
        self.assertTrue(self.store.release_worker_lease("w2"))
        self.assertIsNone(self.store.get_worker_lease())

    def test_a_released_lease_can_be_taken_again(self):
        self.store.acquire_worker_lease("w1", now=RUNTIME)
        self.store.release_worker_lease("w1")

        again = self.store.acquire_worker_lease("w1", now=RUNTIME + timedelta(minutes=1))

        self.assertEqual(again.acquired_at, RUNTIME + timedelta(minutes=1))

    def test_a_lease_needs_a_named_worker(self):
        with self.assertRaises(ValueError):
            self.store.acquire_worker_lease("  ", now=RUNTIME)


class StoredTaskIntegrityTests(SchedulerStoreTestCase):
    """A damaged task row is reported as itself, and is never repaired behind the person's back."""

    def test_an_unreadable_schedule_is_reported_as_the_record_it_is(self):
        self.store.save_scheduled_task(self.default_task(), now=RUNTIME)

        with self.store._connection:  # a hand-edited or damaged row, written directly on purpose
            self.store._connection.execute(
                "UPDATE scheduled_task SET schedule_times = ? WHERE task_id = ?",
                ("not json", "discovery-run"))

        with self.assertRaises(StoredRecordError) as caught:
            self.store.get_scheduled_task("discovery-run")
        self.assertIn("schedule is not readable", str(caught.exception))

    def test_a_schedule_that_is_not_a_list_of_times_is_reported_rather_than_guessed(self):
        self.store.save_scheduled_task(self.default_task(), now=RUNTIME)

        with self.store._connection:
            self.store._connection.execute(
                "UPDATE scheduled_task SET schedule_times = ? WHERE task_id = ?",
                (json.dumps("12:00"), "discovery-run"))

        with self.assertRaises(StoredRecordError) as caught:
            self.store.get_scheduled_task("discovery-run")
        self.assertIn("not a list of times", str(caught.exception))

    def test_a_run_state_this_version_does_not_know_is_reported(self):
        stored = self.store.save_scheduled_task(self.default_task(), now=RUNTIME)
        claimed = self.store.claim_due_run(worker_id="w1", now=stored.next_run_at)
        assert claimed is not None

        with self.store._connection:
            self.store._connection.execute(
                "UPDATE task_run SET state = 'teleported' WHERE run_id = ?", (claimed.run_id,))

        with self.assertRaises(StoredRecordError) as caught:
            self.store.get_task_run(claimed.run_id)
        self.assertIn("teleported", str(caught.exception))

    def test_a_task_definition_that_cannot_be_read_is_refused_with_its_reason(self):
        self.store.save_scheduled_task(self.default_task(), now=RUNTIME)

        with self.store._connection:
            self.store._connection.execute(
                "UPDATE scheduled_task SET timezone = 'Mars/Olympus_Mons' WHERE task_id = ?",
                ("discovery-run",))

        with self.assertRaises(StoredRecordError) as caught:
            self.store.get_scheduled_task("discovery-run")
        self.assertIn("could not be read as a task", str(caught.exception))


class SaveValidationTests(SchedulerStoreTestCase):
    """The storage boundary checks what it is given, not only what the caller believed."""

    def test_saving_something_that_is_not_a_task_is_refused(self):
        with self.assertRaises(ValueError):
            self.store.save_scheduled_task({"task_id": "t"})  # type: ignore[arg-type]

    def test_a_task_with_an_impossible_definition_is_refused_before_anything_is_written(self):
        with self.assertRaises(TaskValidationError):
            ScheduledTask(task_id="t", name="T", kind="k", times=("25:00",))

        self.assertEqual(self.store.list_scheduled_tasks(), (), "nothing was stored")


if __name__ == "__main__":  # pragma: no cover - convenience for running this file alone
    unittest.main()
