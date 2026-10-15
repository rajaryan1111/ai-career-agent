"""Tests for the handlers the application registers: what a scheduled task actually does.

The backup handler is exercised against a real database file and a real snapshot, and the discovery
handler against the closed source-quality gate - the two cases that decide whether a scheduled run is
useful or a lie: one writes and verifies a file, the other refuses and says exactly why.
"""
from __future__ import annotations

import os
import socket
import stat
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from career_agent.backup import automatic_backup_path, automatic_backup_snapshots, validate_app_database
from career_agent.handlers import (
    BACKUP_TASK_ID, DIGEST_NAMES_AT_MOST, DISCOVERY_TASK_ID, FOLLOW_UP_DIGEST_TIMES, FOLLOW_UP_TASK_ID,
    MAX_AUTOMATIC_SNAPSHOTS, backup_snapshot, default_registry, default_tasks,
    describe_default_handlers, discovery_run, follow_up_digest, seed_default_tasks,
)
from career_agent.sources import SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources
from career_agent.core import ApplicationStatus, ApplicationTracker, Availability, JobListing
from career_agent.store import SCHEMA_VERSION, CareerStore
from career_agent.tasks import DEFAULT_TIMEZONE, HandlerOutcome, RunState, build_task
from career_agent.worker import TaskContext, Worker, WorkerSettings
import career_agent.handlers as handlers_module
import career_agent.tasks as tasks_module

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

    def test_the_built_in_kinds_are_registered_with_descriptions(self):
        registry = default_registry()

        self.assertEqual(registry.kinds(), ("backup.snapshot", "discovery.run", "followup.digest"))
        for kind in registry.kinds():
            self.assertTrue(registry.get(kind).description.strip())

    def test_the_description_lines_name_the_kinds(self):
        lines = describe_default_handlers()

        self.assertEqual(len(lines), len(default_registry().kinds()))
        for kind in default_registry().kinds():
            self.assertTrue(any(line.startswith(f"{kind}:") for line in lines),
                            f"{kind} must be described where the others are")

    def test_every_registered_kind_has_a_default_task_or_is_deliberately_not_scheduled(self):
        """A kind nobody schedules is a feature nobody gets; each one is either seeded or explained."""
        registered = set(default_registry().kinds())
        scheduled = {task.kind for task in default_tasks(now=self.now)}

        self.assertTrue(scheduled <= registered,
                        "a default task must name a kind that exists")
        self.assertEqual(registered - scheduled, set(),
                         "every registered kind is scheduled for a fresh installation")


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
        self.assertEqual(info.schema_version, SCHEMA_VERSION)
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


class FollowUpDigestTests(HandlerTestCase):
    """The scheduled reminder: it reports what is due, and it writes nothing at all.

    The occurrence used is 2026-10-15 09:00 Asia/Kolkata (03:30 UTC), which is the day the digest is
    about. The handler must derive that day from the *occurrence*, not from this machine's clock, or a
    laptop that was asleep would be told the wrong day when it finally runs.
    """

    SLOT = datetime(2026, 10, 15, 3, 30, tzinfo=UTC)
    TODAY = date(2026, 10, 15)

    def digest_context(self, *, slot_at=None) -> TaskContext:
        task = build_task(FOLLOW_UP_TASK_ID, "Daily follow-up reminders", "followup.digest",
                          times=FOLLOW_UP_DIGEST_TIMES, now=self.now)
        return self.context(task=task, slot_at=slot_at or self.SLOT)

    def add_application(self, listing_id: str, *, days: int | None, role: str = "Data Engineer",
                        note: str | None = None) -> None:
        self.store.save_job(JobListing(listing_id, "fixture", "Fixture",
                                       f"https://jobs.example.invalid/{listing_id}", "Sandbox Systems",
                                       role, availability_status=Availability.UNKNOWN))
        self.store.save_tracker(ApplicationTracker(listing_id))
        if days is not None:
            self.store.save_tracker(ApplicationTracker(listing_id).with_follow_up(
                self.TODAY + timedelta(days=days), note=note))

    def test_nothing_due_is_a_success_that_says_so_and_names_nobody(self):
        """The schedule ran and did its whole job; "nothing to chase" is not an empty result.

        The reminder five days out is *not* named. A digest that listed it would be telling somebody to
        chase an application they deliberately planned to leave alone until next week.
        """
        self.add_application("j1", days=5, role="Later Role")

        result = follow_up_digest(self.digest_context())

        self.assertEqual(result.outcome, HandlerOutcome.SUCCEEDED)
        self.assertIn("none are due yet", result.detail)
        self.assertNotIn("Later Role", result.detail)
        self.assertNotIn("due today", result.detail)
        self.assertNotIn("overdue", result.detail)

    def test_a_record_with_no_day_at_all_is_reported_as_nothing_recorded(self):
        self.add_application("j1", days=None)

        result = follow_up_digest(self.digest_context())

        self.assertEqual(result.outcome, HandlerOutcome.SUCCEEDED)
        self.assertIn("No follow-ups are recorded", result.detail)

    def test_due_and_overdue_follow_ups_are_named_with_their_day(self):
        self.add_application("j1", days=-2, role="Data Engineer", note="ask about the panel")
        self.add_application("j2", days=0, role="QA Engineer")

        result = follow_up_digest(self.digest_context())

        self.assertEqual(result.outcome, HandlerOutcome.SUCCEEDED)
        self.assertIn("1 overdue", result.detail)
        self.assertIn("1 due today", result.detail)
        self.assertIn("Data Engineer", result.detail)
        self.assertIn("QA Engineer", result.detail)
        self.assertIn("2026-10-13", result.detail, "the day itself is in the record")

    def test_a_long_list_is_summarised_rather_than_pasted_whole(self):
        for index in range(DIGEST_NAMES_AT_MOST + 3):
            self.add_application(f"j{index}", days=-1, role=f"Role {index}")

        result = follow_up_digest(self.digest_context())

        self.assertIn("(3 more not named here)", result.detail)
        self.assertIn("(checked for 2026-10-15)", result.detail)
        self.assertLessEqual(len(result.detail), tasks_module.MAX_DETAIL_LENGTH + len("... (truncated)"),
                             "a run record is a bounded line, not a report")

    def test_the_digest_changes_no_application_and_writes_no_entry(self):
        self.add_application("j1", days=-1)

        follow_up_digest(self.digest_context())

        tracker = self.store.get_tracker("j1")
        assert tracker is not None
        self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED)
        self.assertIsNone(tracker.status_evidence)
        self.assertFalse(tracker.candidate_confirmed)
        self.assertEqual(self.store.list_activity("j1"), ())
        self.assertEqual([run.detail for run in self.store.list_task_runs()], [],
                         "the handler writes nothing; the worker records the attempt, not the handler")

    def test_the_day_reported_is_the_occurrence_day_not_the_wall_clock(self):
        """A digest claimed late still reports the day it was due for, on the workspace's clock."""
        self.add_application("j1", days=-1)

        # The same occurrence, expressed in two zones: the day it is about does not move.
        ist = ZoneInfo("Asia/Kolkata")
        as_ist = follow_up_digest(self.digest_context(slot_at=self.SLOT.astimezone(ist)))
        as_utc = follow_up_digest(self.digest_context(slot_at=self.SLOT))

        self.assertEqual(as_ist.detail, as_utc.detail)
        self.assertIn("checked for 2026-10-15", as_ist.detail)

    def test_a_database_that_is_not_there_is_a_refusal_not_a_crash(self):
        self.store.close()
        self.database_path.unlink()

        result = follow_up_digest(self.digest_context())

        self.assertEqual(result.outcome, HandlerOutcome.REFUSED)
        self.assertIn("no database file", result.detail)

    def test_the_digest_reaches_no_network(self):
        """No socket is opened anywhere in the handler: it reads one local file and returns a line."""
        self.add_application("j1", days=0)
        opened = []
        real_socket = socket.socket

        def spy(*args, **kwargs):
            opened.append(args)
            return real_socket(*args, **kwargs)

        with mock.patch.object(socket, "socket", spy):
            result = follow_up_digest(self.digest_context())

        self.assertEqual(result.outcome, HandlerOutcome.SUCCEEDED)
        self.assertEqual(opened, [], "the scheduled reminder must not open a socket")


class DigestThroughTheWorkerTests(HandlerTestCase):
    """The digest as a person actually gets it: a scheduled task, run by the worker, recorded.

    The other tests call the handler directly; this one proves the wiring - that the seeded kind runs
    through the real registry, that its one line lands in the run history, and that a run changes no
    candidate data.
    """

    def test_the_seeded_digest_runs_through_the_worker_and_lands_in_the_history(self):
        self.store.save_job(JobListing("j1", "fixture", "Fixture", "https://jobs.example.invalid/1",
                                       "Sandbox Systems", "Data Engineer",
                                       availability_status=Availability.UNKNOWN))
        self.store.save_tracker(ApplicationTracker("j1"))
        # Seeded a minute before the digest's 09:00 IST occurrence, on the day the follow-up is due.
        slot = datetime(2026, 10, 12, 3, 29, tzinfo=UTC)
        due_at = datetime(2026, 10, 12, 3, 30, tzinfo=UTC)
        self.store.save_tracker(ApplicationTracker("j1").with_follow_up(date(2026, 10, 12),
                                                                       note="ask about the panel"))
        seeded = seed_default_tasks(self.store, now=slot)
        self.assertIn(FOLLOW_UP_TASK_ID, seeded.created)
        # Only the digest is due, so the claim cannot land on another task.
        for task in self.store.list_scheduled_tasks():
            if task.task_id != FOLLOW_UP_TASK_ID:
                self.store.save_scheduled_task(task.with_definition(enabled=False), now=slot)

        worker = Worker(self.store, worker_id="test-worker", registry=default_registry(),
                        settings=WorkerSettings(poll_seconds=0.01, heartbeat_seconds=0.05,
                                                stale_after_seconds=30),
                        clock=lambda: due_at, on_outcome=lambda outcome: None)
        executed = worker.tick(now=due_at)

        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0].task_id, FOLLOW_UP_TASK_ID)
        self.assertEqual(executed[0].state, RunState.SUCCEEDED)
        self.assertIn("due today", executed[0].detail)
        self.assertIn("Data Engineer", executed[0].detail)
        self.assertIn("2026-10-12", executed[0].detail, "the day is the occurrence's day")
        tracker = self.store.get_tracker("j1")
        assert tracker is not None
        self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED)
        self.assertEqual(self.store.list_activity("j1"), (),
                         "a reminder is not an activity entry; only the person writes those")


class DefaultTaskTests(HandlerTestCase):
    """What a fresh installation is scheduled to do."""

    def test_the_defaults_are_the_product_cadence_and_a_daily_backup(self):
        tasks = default_tasks(now=self.now)

        self.assertEqual([task.task_id for task in tasks],
                         [DISCOVERY_TASK_ID, BACKUP_TASK_ID, FOLLOW_UP_TASK_ID])
        discovery, backup, digest = tasks
        self.assertEqual(discovery.times, ("00:00", "12:00"))
        self.assertEqual(backup.times, ("23:30",))
        self.assertEqual(digest.times, FOLLOW_UP_DIGEST_TIMES,
                         "the reminder about today arrives near the start of today")
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

        self.assertEqual(first.created, (DISCOVERY_TASK_ID, BACKUP_TASK_ID, FOLLOW_UP_TASK_ID))
        self.assertEqual(first.kept, ())
        self.assertEqual(again.created, ())
        self.assertEqual(again.kept, (DISCOVERY_TASK_ID, BACKUP_TASK_ID, FOLLOW_UP_TASK_ID))
        self.assertEqual(third.created, ())
        self.assertEqual(discovery.times, ("01:00",), "a person's times stay as they set them")
        self.assertEqual(discovery.name, "Renamed")
        self.assertFalse(discovery.enabled, "a task the person paused stays paused")
        self.assertEqual(len(third.tasks), len(default_tasks(now=self.now)))

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
