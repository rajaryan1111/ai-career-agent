"""Tests for the scheduled-task commands: ``--seed-tasks``, ``--worker-status`` and ``--worker``.

The command line is where a person meets the scheduler, so what is tested here is what they are told and
what actually happens to their database: seeding adds the defaults and leaves their choices alone,
status claims nothing, and the worker refuses to run beside another worker rather than doing the work
twice. The subscription-free parts of the loop (one due task, then a stop) are exercised through the
real command so the wiring is covered, not only the library underneath it.
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import career_agent.__main__ as cli
from career_agent.backup import automatic_backup_snapshots
from career_agent.handlers import BACKUP_TASK_ID, DISCOVERY_TASK_ID
from career_agent.store import SCHEMA_VERSION, CareerStore
from career_agent.tasks import RunState, build_task

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
IST = ZoneInfo("Asia/Kolkata")


class CliWorkerTestCase(unittest.TestCase):
    """A temporary folder; commands are invoked through the real ``main`` with captured output.

    The worker's loop is stopped by a stop event rather than by a signal, because a test process must
    not install a SIGINT handler over the test runner's: ``_stop_event_installed`` is the one piece that
    touches signals, and the tests that exercise the loop patch it.
    """

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        """Run the command line as the console script would, returning status, stdout and stderr."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*arguments, "--database", str(self.database)])
        return code, out.getvalue(), err.getvalue()

    def seeded_store(self) -> CareerStore:
        store = CareerStore(self.database)
        self.addCleanup(store.close)
        return store

    def make_due(self, task_id: str) -> datetime:
        """Move a task's next occurrence to now, so a worker has something to run immediately."""
        moment = datetime.now(timezone.utc).replace(microsecond=0)
        with CareerStore(self.database) as store:
            with store._connection:
                store._connection.execute(
                    "UPDATE scheduled_task SET next_run_at = ? WHERE task_id = ?",
                    (moment.isoformat(), task_id))
        return moment


class SeedTaskCommandTests(CliWorkerTestCase):
    """``--seed-tasks``: the defaults once, and never over a person's choices."""

    def test_seeding_creates_the_default_schedule_and_says_what_it_did(self) -> None:
        code, out, err = self.run_cli("--seed-tasks")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("created scheduled-discovery, daily-backup", out)
        self.assertIn("00:00, 12:00 Asia/Kolkata", out)
        self.assertIn("23:30 Asia/Kolkata", out)
        self.assertIn("--worker", out)
        with self.seeded_store() as store:
            self.assertEqual([task.task_id for task in store.list_scheduled_tasks()],
                             [BACKUP_TASK_ID, DISCOVERY_TASK_ID])

    def test_seeding_again_changes_nothing_and_says_so(self) -> None:
        self.run_cli("--seed-tasks")

        code, out, err = self.run_cli("--seed-tasks")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("left scheduled-discovery, daily-backup exactly as they were", out)

    def test_seeding_leaves_a_task_a_person_configured_exactly_as_it_is(self) -> None:
        self.run_cli("--seed-tasks")
        with self.seeded_store() as store:
            store.save_scheduled_task(build_task(
                DISCOVERY_TASK_ID, "My own schedule", "discovery.run", times=("09:15",),
                timezone="Europe/London", enabled=False))

        code, out, err = self.run_cli("--seed-tasks")

        self.assertEqual(code, cli.EXIT_OK, err)
        with self.seeded_store() as store:
            task = store.get_scheduled_task(DISCOVERY_TASK_ID)
            assert task is not None
            self.assertEqual(task.name, "My own schedule")
            self.assertEqual(task.times, ("09:15",))
            self.assertEqual(task.timezone, "Europe/London")
            self.assertFalse(task.enabled)
            self.assertIsNone(task.next_run_at, "a paused task must not be given a new run time")


class WorkerStatusCommandTests(CliWorkerTestCase):
    """``--worker-status``: read-only, and honest about a fresh installation."""

    def test_a_missing_database_is_reported_as_a_fresh_installation_not_a_failure(self) -> None:
        code, out, err = self.run_cli("--worker-status")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("No database yet", out)
        self.assertIn("--seed-tasks", out)
        self.assertFalse(self.database.exists(), "a read-only report must not create the database")

    def test_the_report_shows_tasks_and_states_that_it_changed_nothing(self) -> None:
        self.run_cli("--seed-tasks")

        code, out, err = self.run_cli("--worker-status")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("No worker holds the lease", out)
        self.assertIn("scheduled-discovery: Scheduled job discovery", out)
        self.assertIn("daily-backup: Daily database backup", out)
        self.assertIn("last never run", out)
        self.assertIn("read-only; nothing was claimed and nothing was run", out)
        with self.seeded_store() as store:
            self.assertIsNone(store.get_worker_lease())
            self.assertEqual(store.list_task_runs(), ())


class WorkerCommandTests(CliWorkerTestCase):
    """``--worker``: it runs due work, stops when asked, and refuses to double up."""

    def test_it_refuses_while_another_worker_holds_the_lease(self) -> None:
        self.run_cli("--seed-tasks")
        with self.seeded_store() as store:
            store.acquire_worker_lease("another-worker")

        code, out, err = self.run_cli("--worker")

        self.assertEqual(code, cli.EXIT_ALREADY_RUNNING)
        self.assertIn("another-worker", err)
        self.assertIn("REFUSED", err)

    def test_it_runs_a_due_task_and_stops_when_the_stop_event_is_set(self) -> None:
        self.run_cli("--seed-tasks")
        self.make_due(BACKUP_TASK_ID)
        stop = threading.Event()
        real_tick = cli.Worker.tick

        def tick_and_stop(self, **kwargs):
            executed = real_tick(self, **kwargs)
            stop.set()  # stop after the first pass, exactly as Ctrl-C would
            return executed

        with mock.patch.object(cli, "_stop_event_installed", return_value=stop), \
                mock.patch.object(cli.Worker, "tick", tick_and_stop):
            code, out, err = self.run_cli("--worker", "--worker-id", "test-worker",
                                          "--poll-seconds", "0.05")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("backup.snapshot:", out)
        self.assertIn("source-quality gate has not passed", out)
        self.assertIn("daily-backup attempt 1: succeeded", out)
        self.assertIn("Worker stopped; its lease has been released.", out)

        with self.seeded_store() as store:
            runs = store.list_task_runs(task_id=BACKUP_TASK_ID)
            self.assertEqual([run.state for run in runs], [RunState.SUCCEEDED])
            self.assertEqual(runs[0].worker_id, "test-worker")
            self.assertIsNone(store.get_worker_lease(), "a stopped worker holds nothing")
        snapshots = automatic_backup_snapshots(self.database)
        self.assertEqual(len(snapshots), 1, f"expected one snapshot, found {snapshots}")

    def test_a_first_run_with_an_empty_database_adds_the_default_schedule(self) -> None:
        stop = threading.Event()
        stop.set()  # stop immediately: this test is about what starting sets up, not about running

        with mock.patch.object(cli, "_stop_event_installed", return_value=stop):
            code, out, err = self.run_cli("--worker")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("No database yet; the default schedule is being added", out)
        self.assertIn("created scheduled-discovery, daily-backup", out)
        with self.seeded_store() as store:
            self.assertEqual(len(store.list_scheduled_tasks()), 2)
            self.assertEqual(store.list_task_runs(), ())
            self.assertIsNone(store.get_worker_lease(), "a zero-tick worker leaves no lease behind")

    def test_the_worker_commands_do_not_need_the_gui_toolkit(self) -> None:
        """A scheduler on a headless machine or in a service must not need a display."""
        script = (
            "import sys\n"
            "from career_agent.__main__ import main\n"
            "main(['--seed-tasks', '--database', sys.argv[1]])\n"
            "main(['--worker-status', '--database', sys.argv[1]])\n"
            "print('tkinter loaded:', 'tkinter' in sys.modules)\n"
        )
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script, str(self.database)],
            cwd=str(REPOSITORY_ROOT), capture_output=True, text=True, check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("tkinter loaded: False", completed.stdout)


class ExistingDatabaseCommandTests(CliWorkerTestCase):
    """The commands that already existed keep working on a database with a schedule."""

    def test_doctor_reports_the_scheduled_tasks_and_still_changes_nothing(self) -> None:
        self.run_cli("--seed-tasks")
        before = {path.name: path.stat().st_size for path in self.folder.iterdir()}

        code, out, err = self.run_cli("--doctor")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn(f"schema version {SCHEMA_VERSION}", out)
        self.assertEqual({path.name: path.stat().st_size for path in self.folder.iterdir()}, before,
                         "a read-only report must not modify anything in the folder")

    def test_a_backup_taken_from_the_command_line_contains_the_schedule(self) -> None:
        self.run_cli("--seed-tasks")
        target = self.folder / "copy.sqlite3"

        code, out, err = self.run_cli("--backup-to", str(target))

        self.assertEqual(code, cli.EXIT_OK, err)
        with CareerStore(target) as store:
            self.assertEqual([task.task_id for task in store.list_scheduled_tasks()],
                             [BACKUP_TASK_ID, DISCOVERY_TASK_ID])


class ScheduleZoneTests(CliWorkerTestCase):
    """The stored schedule is the product's cadence, in the product's zone."""

    def test_the_default_tasks_are_due_at_midnight_and_noon_in_kolkata(self) -> None:
        self.run_cli("--seed-tasks")

        with self.seeded_store() as store:
            discovery = store.get_scheduled_task(DISCOVERY_TASK_ID)
            assert discovery is not None
            local = discovery.next_run_at.astimezone(IST)
            self.assertIn((local.hour, local.minute), ((0, 0), (12, 0)),
                          f"the next discovery run is at {local.isoformat()} local time")
            self.assertLess(discovery.next_run_at - datetime.now(timezone.utc), timedelta(days=1))


if __name__ == "__main__":  # pragma: no cover - convenience for running this file alone
    unittest.main()
