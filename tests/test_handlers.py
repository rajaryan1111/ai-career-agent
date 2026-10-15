"""Tests for the handlers the application registers: what a scheduled task actually does.

The backup handler is exercised against a real database file and a real snapshot, and the discovery
handler against the closed source-quality gate - the two cases that decide whether a scheduled run is
useful or a lie: one writes and verifies a file, the other refuses and says exactly why.
"""
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career_agent.backup import automatic_backup_path, automatic_backup_snapshots, validate_app_database
from career_agent.handlers import (
    BACKUP_TASK_ID, DISCOVERY_TASK_ID, MAX_AUTOMATIC_SNAPSHOTS, backup_snapshot,
    default_registry, default_tasks, describe_default_handlers, discovery_run, seed_default_tasks,
)
from career_agent.sources import SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources
from career_agent.store import CareerStore
from career_agent.tasks import DEFAULT_TIMEZONE, HandlerOutcome, RunState, build_task
from career_agent.worker import TaskContext, Worker, WorkerSettings
import career_agent.handlers as handlers_module

UTC = timezone.utc
#: 2026-10-15 11:30 IST.
START = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)


class HandlerTestCase(unittest.TestCase):
    """A temporary database (with a real file) and a context to hand to a handler."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.directory = Path(self._temp.name)
        self.database_path = self.directory / "career_agent.sqlite3"
        self.store = CareerStore(self.database_path)
        self.addCleanup(self.store.close)
        self.now = START

    def context(self, *, task=None, slot_at=None, timeout_seconds=300, attempt=1) -> TaskContext:
        task = task or build_task("task", "A task", "backup.snapshot", now=self.now)
        slot = slot_at or self.now
        return TaskContext(
            task=task, slot_at=slot, attempt=attempt, started_at=self.now,
            deadline=self.now + timedelta(seconds=timeout_seconds),
            database_path=str(self.database_path), _now=lambda: self.now,
        )


class RegistryTests(HandlerTestCase):
    """The built-in kinds are registered and described, not implied."""

    def test_the_two_built_in_kinds_are_registered_with_descriptions(self):
        registry = default_registry()

        self.assertEqual(registry.kinds(), ("backup.snapshot", "discovery.run"))
        for kind in registry.kinds():
            self.assertTrue(registry.get(kind).description.strip())

    def test_the_description_lines_name_the_kinds(self):
        lines = describe_default_handlers()

        self.assertEqual(len(lines), 2)
        self.assertTrue(any(line.startswith("backup.snapshot:") for line in lines))
        self.assertTrue(any(line.startswith("discovery.run:") for line in lines))


class BackupSnapshotTests(HandlerTestCase):
    """A scheduled snapshot is a real, verified file - or a refusal that names the reason."""

    def test_a_snapshot_is_written_verified_and_named_after_the_occurrence(self):
        result = backup_snapshot(self.context(task=build_task(
            "daily", "Daily backup", "backup.snapshot", times=("23:30",), now=self.now)))

        self.assertEqual(result.outcome, HandlerOutcome.SUCCEEDED)
        snapshot = automatic_backup_path(self.database_path, self.now)
        self.assertTrue(snapshot.is_file(), result.detail)
        self.assertIn(snapshot.name, result.detail)
        info = validate_app_database(snapshot)
        self.assertEqual(info.schema_version, 3)
        if os.name == "posix":  # owner-only where the platform has modes to check
            self.assertEqual(stat.S_IMODE(snapshot.stat().st_mode), 0o600)

    def test_a_snapshot_of_a_database_with_rows_says_what_it_holds(self):
        with self.store._connection:  # a job row, so the count in the detail is not always zero
            self.store._connection.execute(
                """INSERT INTO job_listings(listing_id, payload, duplicate_key, first_seen_at, last_seen_at)
                   VALUES ('j1', '{}', 'dk1', ?, ?)""", (self.now.isoformat(), self.now.isoformat()))

        result = backup_snapshot(self.context())

        self.assertIn("1 job", result.detail)

    def test_there_is_nothing_to_back_up_before_a_database_exists(self):
        self.store.close()
        self.database_path.unlink()

        result = backup_snapshot(self.context())

        self.assertEqual(result.outcome, HandlerOutcome.REFUSED)
        self.assertIn("no database file", result.detail)
        self.assertEqual(automatic_backup_snapshots(self.database_path), ())

    def test_the_handler_refuses_at_the_cap_rather_than_filling_the_folder(self):
        for index in range(2):
            (self.directory / f"career_agent.sqlite3.backup-2026101{index}T000000Z").write_bytes(b"x")
        original = handlers_module.MAX_AUTOMATIC_SNAPSHOTS
        handlers_module.MAX_AUTOMATIC_SNAPSHOTS = 2
        self.addCleanup(setattr, handlers_module, "MAX_AUTOMATIC_SNAPSHOTS", original)

        result = backup_snapshot(self.context())

        self.assertEqual(result.outcome, HandlerOutcome.REFUSED)
        self.assertIn("2 automatic snapshots", result.detail)
        self.assertIn("move or delete", result.detail)
        self.assertEqual(len(automatic_backup_snapshots(self.database_path)), 2,
                         "a refusal must not have deleted or added anything")

    def test_only_this_databases_automatic_snapshots_are_counted(self):
        wanted = self.directory / "career_agent.sqlite3.backup-20261015T000000Z"
        wanted.write_bytes(b"x")
        (self.directory / "other.sqlite3.backup-20261015T000000Z").write_bytes(b"x")
        (self.directory / "career_agent.sqlite3").write_bytes(b"x")
        (self.directory / "notes.backup-today.txt").write_bytes(b"x")

        self.assertEqual(automatic_backup_snapshots(self.database_path), (wanted,))

    def test_the_cap_is_a_positive_number_of_snapshots(self):
        self.assertGreater(MAX_AUTOMATIC_SNAPSHOTS, 1)
        self.assertIsInstance(MAX_AUTOMATIC_SNAPSHOTS, int)


class DiscoveryHandlerTests(HandlerTestCase):
    """The scheduled discovery run refuses while the gate is closed, and touches no network."""

    def test_the_gate_is_still_closed_and_no_source_is_enabled(self):
        self.assertFalse(SOURCE_QUALITY_GATE_PASSED,
                         "this test documents the state the handler's refusal is based on")
        self.assertEqual(enabled_discovery_sources(), ())

    def test_the_run_refuses_and_names_the_gate_rather_than_inventing_a_result(self):
        result = discovery_run(self.context())

        self.assertEqual(result.outcome, HandlerOutcome.REFUSED)
        self.assertIn("source-quality gate", result.detail)
        self.assertIn("nothing was sent or fetched", result.detail)
        self.assertIn("not a failure", result.detail, "a refusal is a decision, not a malfunction")

    def test_the_refusal_holds_even_with_the_gate_open_because_no_adapter_exists(self):
        original = handlers_module.SOURCE_QUALITY_GATE_PASSED
        handlers_module.SOURCE_QUALITY_GATE_PASSED = True
        handlers_module.enabled_discovery_sources = lambda **kwargs: ("an-enabled-source",)
        self.addCleanup(setattr, handlers_module, "SOURCE_QUALITY_GATE_PASSED", original)
        self.addCleanup(setattr, handlers_module, "enabled_discovery_sources",
                        enabled_discovery_sources)

        result = discovery_run(self.context())

        self.assertEqual(result.outcome, HandlerOutcome.REFUSED,
                         "no live adapter exists, so even an open gate cannot produce a run")
        self.assertIn("no source adapter is implemented", result.detail)


class DefaultTaskTests(HandlerTestCase):
    """What a fresh installation is scheduled to do."""

    def test_the_defaults_are_the_product_cadence_and_a_daily_backup(self):
        tasks = default_tasks(now=self.now)

        self.assertEqual([task.task_id for task in tasks], [DISCOVERY_TASK_ID, BACKUP_TASK_ID])
        discovery, backup = tasks
        self.assertEqual(discovery.times, ("00:00", "12:00"))
        self.assertEqual(backup.times, ("23:30",))
        for task in tasks:
            self.assertEqual(task.timezone, DEFAULT_TIMEZONE)
            self.assertTrue(task.enabled)
            self.assertIsNotNone(task.next_run_at)

    def test_seeding_creates_the_tasks_once_and_never_overwrites_a_persons_choices(self):
        first = seed_default_tasks(self.store, now=self.now)
        again = seed_default_tasks(self.store, now=self.now)
        self.store.save_scheduled_task(
            build_task(DISCOVERY_TASK_ID, "Renamed", "discovery.run", times=("01:00",),
                       enabled=False, now=self.now), now=self.now)
        third = seed_default_tasks(self.store, now=self.now)
        discovery = self.store.get_scheduled_task(DISCOVERY_TASK_ID)
        assert discovery is not None

        self.assertEqual(first.created, (DISCOVERY_TASK_ID, BACKUP_TASK_ID))
        self.assertEqual(first.kept, ())
        self.assertEqual(again.created, ())
        self.assertEqual(again.kept, (DISCOVERY_TASK_ID, BACKUP_TASK_ID))
        self.assertEqual(third.created, ())
        self.assertEqual(discovery.times, ("01:00",), "a person's times stay as they set them")
        self.assertEqual(discovery.name, "Renamed")
        self.assertFalse(discovery.enabled, "a task the person paused stays paused")
        self.assertEqual(len(third.tasks), 2)

    def test_the_seed_outcome_says_what_it_did(self):
        first = seed_default_tasks(self.store, now=self.now)
        again = seed_default_tasks(self.store, now=self.now)

        self.assertIn("created", first.describe())
        self.assertIn("left", again.describe())


class ScheduledRunTests(HandlerTestCase):
    """The handlers through the real worker: a snapshot is written, a gated run is refused and kept."""

    def worker(self) -> Worker:
        return Worker(self.store, worker_id="w1", registry=default_registry(),
                      settings=WorkerSettings(poll_seconds=0.01, heartbeat_seconds=0.05,
                                              stale_after_seconds=30),
                      clock=lambda: self.now)

    def due(self, task_id: str) -> datetime:
        """Move the clock to a task's occurrence and return it."""
        task = self.store.get_scheduled_task(task_id)
        assert task is not None and task.next_run_at is not None
        self.now = task.next_run_at
        return self.now

    def disable(self, task_id: str) -> None:
        """Pause one seeded task, so a test about the other one is about the other one."""
        existing = self.store.get_scheduled_task(task_id)
        assert existing is not None
        self.store.save_scheduled_task(existing.with_definition(enabled=False), now=self.now)

    def test_a_due_backup_task_writes_one_verified_snapshot(self):
        seed_default_tasks(self.store, now=self.now)
        self.disable(DISCOVERY_TASK_ID)
        slot = self.due(BACKUP_TASK_ID)

        executed = self.worker().tick(now=self.now)
        task = self.store.get_scheduled_task(BACKUP_TASK_ID)
        assert task is not None

        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0].state, RunState.SUCCEEDED)
        self.assertEqual(executed[0].slot_at, slot)
        self.assertTrue((self.directory / f"career_agent.sqlite3.backup-"
                                          f"{slot.strftime('%Y%m%dT%H%M%SZ')}").is_file())
        self.assertEqual(task.last_outcome, RunState.SUCCEEDED)

    def test_a_due_discovery_task_is_refused_and_not_tried_again(self):
        seed_default_tasks(self.store, now=self.now)
        self.due(DISCOVERY_TASK_ID)

        executed = self.worker().tick(now=self.now)
        task = self.store.get_scheduled_task(DISCOVERY_TASK_ID)
        assert task is not None

        self.assertEqual(executed[0].state, RunState.REFUSED)
        self.assertIn("source-quality gate", executed[0].detail)
        self.assertEqual(task.consecutive_failures, 0)
        self.assertIsNone(task.pending_slot_at, "a refusal must not be retried")
        self.assertGreater(task.next_run_at, self.now)
        self.assertEqual(automatic_backup_snapshots(self.database_path), (),
                         "the discovery task must not have written a backup")

    def test_the_history_reads_as_a_sequence_a_person_can_follow(self):
        seed_default_tasks(self.store, now=self.now)
        worker = self.worker()
        self.due(DISCOVERY_TASK_ID)
        worker.tick(now=self.now)
        # The discovery task is due again at 12:00 before the backup's 23:30, so it is paused here:
        # this test is about the order two different outcomes appear in, not about the backlog.
        self.disable(DISCOVERY_TASK_ID)
        self.due(BACKUP_TASK_ID)
        worker.tick(now=self.now)

        runs = self.store.list_task_runs()

        self.assertEqual([(run.task_id, run.state) for run in runs],
                         [(BACKUP_TASK_ID, RunState.SUCCEEDED),
                          (DISCOVERY_TASK_ID, RunState.REFUSED)])


if __name__ == "__main__":  # pragma: no cover - convenience for running this file alone
    unittest.main()
