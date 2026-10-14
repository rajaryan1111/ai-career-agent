"""The application's own event log: what it records, what it must never record, and its bounds.

The log exists so that "what did this application do, and when?" has an answer that does not depend on
someone remembering. That makes three properties worth testing rather than assuming:

* **only events, never content** — the tests here save a job, a profile and an activity through the
  real store and then read the log: the identifiers appear, the employer name, the profile's skills and
  the entry's text do not;
* **bounded** — a long-running installation must not accumulate a log forever, so rotation is checked
  by size, by the number of files kept, and by which events survive;
* **never in the way** — a log that cannot be written (a read-only folder, a database that is not a
  file) reports ``None`` instead of raising, because refusing to save a job because a log line failed
  would be the wrong trade every time.

The log lives beside the database it describes, so every test here works inside a temporary directory
and no test can see or write the candidate's own log.
"""
from __future__ import annotations

import ast
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from career_agent import event_log
from career_agent.core import (
    ActivityKind, ApplicationActivity, ApplicationTracker, Availability, CandidateProfile, JobListing,
)
from career_agent.event_log import (
    EVENTS, LOG_FILE_NAME, MAX_DETAIL_LENGTH, MAX_LOG_BYTES, PREVIOUS_LOG_FILE_NAME, describe_line,
    log_path, read_lines, record_event,
)
from career_agent.store import CareerStore

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime(2026, 10, 15, 9, 30, tzinfo=timezone.utc)


def sample_job(listing_id: str = "j1") -> JobListing:
    return JobListing(
        listing_id=listing_id, source_id="manual", source_name="Manual entry",
        source_listing_url=f"https://jobs.example/{listing_id}", employer_name="Confidential Employer Ltd",
        role_title="AI Intern", availability_status=Availability.OPEN,
    )


PROFILE = CandidateProfile(
    candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
    graduation_year=2027, experience_years=0.5, work_authorization="authorized_without_sponsorship",
    skills=frozenset({"Kubernetes-Operator-Skill"}), preferred_work_modes=frozenset({"remote"}),
)


def event_names(path: Path) -> list[str]:
    """The event name of every line, read the way the documentation says to read it.

    The rule is deliberately positional: the timestamp and name come first and ``detail=`` is always
    the last field, so a detail cannot impersonate a second event. Splitting on the first ``" event="``
    is what a support reader does, and testing through that rule is what makes it a rule.
    """
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        _, _, rest = line.partition(" event=")
        names.append(rest.split(" ", 1)[0])
    return names


class EventLogFileTests(unittest.TestCase):
    """Writing, reading and bounding the file itself."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.log = log_path(database_path=self.database)

    def record(self, event: str, detail: str | None = None, **kwargs):
        return record_event(event, detail=detail, database_path=self.database, **kwargs)

    def test_one_event_is_one_line_carrying_a_timestamp_and_the_event_name(self) -> None:
        path = self.record("app.started", "version=0.1.0", timestamp=STAMP)

        self.assertEqual(path, self.log)
        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "2026-10-15T09:30:00+00:00 event=app.started detail=version=0.1.0")

    def test_events_accumulate_oldest_first(self) -> None:
        self.record("app.started", timestamp=STAMP)
        self.record("database.opened", "schema=2", timestamp=STAMP)
        self.record("job.saved", "id=j1", timestamp=STAMP)

        self.assertEqual(event_names(self.log), ["app.started", "database.opened", "job.saved"])
        self.assertIn("detail=id=j1", self.log.read_text(encoding="utf-8"))

    def test_appending_does_not_truncate_what_is_already_there(self) -> None:
        self.record("app.started", timestamp=STAMP)
        self.record("app.stopped", timestamp=STAMP)

        self.assertEqual(len(self.log.read_text(encoding="utf-8").splitlines()), 2)

    @unittest.skipUnless(os.name == "posix", "POSIX file permissions")
    def test_the_log_is_owner_only(self) -> None:
        self.record("app.started", timestamp=STAMP)

        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)

    def test_a_detail_cannot_forge_a_second_event_or_end_the_line_early(self) -> None:
        self.record("export.failed", "reason=first line\n2020-01-01T00:00:00+00:00 event=backup.written", timestamp=STAMP)
        self.record("export.failed", "reason=tab\tseparated", timestamp=STAMP)

        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2, "a newline in a detail must not create another line")
        self.assertEqual(event_names(self.log), ["export.failed", "export.failed"])
        self.assertTrue(all(not line.startswith("event=") for line in lines))

    def test_a_long_detail_is_capped_with_a_marker(self) -> None:
        self.record("export.failed", "reason=" + "x" * (MAX_DETAIL_LENGTH * 3), timestamp=STAMP)

        line = self.log.read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("(truncated)", line)
        self.assertLess(len(line), MAX_DETAIL_LENGTH + 100)

    def test_a_local_location_in_a_detail_is_redacted(self) -> None:
        home = str(Path.home())
        self.record("backup.refused", f"reason=there is no database at {home}/private/career.sqlite3", timestamp=STAMP)

        line = self.log.read_text(encoding="utf-8").splitlines()[0]
        self.assertNotIn(home, line, "a local location must not reach a file meant to be shareable")
        self.assertIn("no database at", line)

    def test_an_event_name_of_the_wrong_shape_is_a_programming_error(self) -> None:
        for name in ("Job.Saved", "jobsaved", "job..saved", "job.saved ", ""):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    describe_line(name)

    def test_every_event_name_used_in_the_shipped_code_is_declared(self) -> None:
        """One vocabulary in one place, checked against the source rather than trusted."""
        used: set[str] = set()
        for folder in ("career_agent", "scripts"):
            for path in sorted((REPOSITORY_ROOT / folder).glob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    called = node.func
                    name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
                    if name not in {"record_event", "describe_line", "_record", "_record_backup_event"}:
                        continue
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        used.add(node.args[0].value)

        self.assertTrue(used, "no events were found, so this check proves nothing")
        self.assertEqual(sorted(used - set(EVENTS)), [], "an event name is not in event_log.EVENTS")
        self.assertEqual(sorted(set(EVENTS) - used), [], "a declared event is never recorded; drop it or use it")

    def test_a_database_that_is_not_a_file_has_no_log(self) -> None:
        for location in (":memory:", "file:career?mode=memory&cache=shared"):
            with self.subTest(location=location):
                self.assertIsNone(record_event("app.started", database_path=location))
                self.assertEqual(read_lines(database_path=location), ())

    @unittest.skipIf(os.name == "posix" and os.geteuid() == 0, "root ignores directory permissions")
    @unittest.skipUnless(os.name == "posix", "POSIX directory permissions")
    def test_an_unwritable_folder_reports_failure_instead_of_raising(self) -> None:
        folder = self.folder / "readonly"
        folder.mkdir()
        os.chmod(folder, 0o500)
        self.addCleanup(os.chmod, folder, 0o700)

        self.assertIsNone(record_event("app.started", database_path=folder / "career_agent.sqlite3"))

    def test_no_log_folder_is_created_until_something_is_recorded(self) -> None:
        self.assertFalse((self.folder / "logs").exists())

        self.assertEqual(read_lines(database_path=self.database), ())
        self.assertFalse((self.folder / "logs").exists(), "reading must not create the log")

        self.record("app.started", timestamp=STAMP)
        self.assertTrue((self.folder / "logs" / LOG_FILE_NAME).is_file())


class EventLogRotationTests(unittest.TestCase):
    """The bound: a long-running installation must not accumulate a log forever."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.log = log_path(database_path=self.database)
        self.previous = log_path(database_path=self.database).with_name(PREVIOUS_LOG_FILE_NAME)

    def fill(self, marker: str, lines: int) -> None:
        for index in range(lines):
            record_event("job.saved", detail=f"{marker} id=j{index} " + "x" * 100,
                         database_path=self.database, timestamp=STAMP)

    def test_the_current_file_stays_within_its_bound_and_one_previous_file_is_kept(self) -> None:
        self.fill("first", 4000)  # each line is ~150 bytes, so this rotates several times

        self.assertTrue(self.log.is_file())
        self.assertIn("first", self.log.read_text(encoding="utf-8"))
        self.assertLessEqual(self.log.stat().st_size, MAX_LOG_BYTES)
        self.assertTrue(self.previous.is_file(), "rotation must keep the lines before the newest ones")
        self.assertLessEqual(self.previous.stat().st_size, MAX_LOG_BYTES)

    def test_rotation_happens_when_a_line_would_pass_the_bound_not_one_file_per_line(self) -> None:
        self.fill("first", 20)
        self.assertFalse(self.previous.exists(), "a small log must not be rotated at all")

        self.fill("second", 4000)
        self.assertTrue(self.previous.exists())
        self.assertEqual(
            sorted(path.name for path in (self.folder / "logs").iterdir()),
            sorted([LOG_FILE_NAME, PREVIOUS_LOG_FILE_NAME]),
            "exactly two files are kept, never one more per rotation",
        )

    def test_the_newest_events_are_the_ones_that_survive(self) -> None:
        self.fill("oldest", 4000)
        record_event("app.stopped", detail="marker=survivor", database_path=self.database, timestamp=STAMP)

        self.assertIn("marker=survivor", self.log.read_text(encoding="utf-8"))

    def test_a_reader_gets_the_most_recent_lines_oldest_first(self) -> None:
        for index in range(5):
            record_event("job.saved", detail=f"id=j{index}", database_path=self.database, timestamp=STAMP)

        lines = read_lines(database_path=self.database, limit=2)

        self.assertEqual(len(lines), 2)
        self.assertIn("id=j3", lines[0])
        self.assertIn("id=j4", lines[1])

    def test_a_reader_can_exclude_the_previous_file(self) -> None:
        self.fill("oldest", 4000)
        record_event("app.stopped", detail="marker=newest", database_path=self.database, timestamp=STAMP)

        current_only = read_lines(database_path=self.database, include_previous=False, limit=1000)

        self.assertTrue(current_only)
        self.assertTrue(all("marker=newest" in line or "x" in line for line in current_only))

    def test_a_damaged_log_is_reported_as_readable_text_rather_than_an_error(self) -> None:
        (self.folder / "logs").mkdir()
        self.log.write_bytes(b"\xff\xfe not utf-8 at all \x00\x01")

        lines = read_lines(database_path=self.database)

        self.assertIsInstance(lines, tuple)
        self.assertEqual(len(lines), 1)

    def test_reading_a_log_that_does_not_exist_is_empty_not_an_error(self) -> None:
        self.assertEqual(read_lines(database_path=self.database), ())
        self.assertEqual(read_lines(database_path=self.database, limit=0), ())


class StoreEventTests(unittest.TestCase):
    """What the store records for real writes, and what it must leave out."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.log = log_path(database_path=self.database)

    def open_store(self, version: int | None = None) -> CareerStore:
        """Open a store, optionally leaving the file at an older recorded schema version."""
        store = CareerStore(str(self.database))
        self.addCleanup(store.close)
        if version is not None:
            store._connection.execute(f"PRAGMA user_version = {version}")
            store._connection.commit()
        return store

    def test_a_new_database_records_the_steps_it_applied_and_that_it_opened(self) -> None:
        self.open_store()

        self.assertEqual(
            event_names(self.log),
            ["database.migrated", "database.migrated", "database.migrated", "database.opened"],
            "one line per step the new database needed, then the one that says it opened",
        )
        text = self.log.read_text(encoding="utf-8")
        self.assertIn("detail=from=0 to=1", text)
        self.assertIn("detail=from=1 to=2", text)
        self.assertIn("detail=from=2 to=3", text)

    def test_an_already_current_database_records_only_that_it_was_opened(self) -> None:
        self.open_store()
        self.log.unlink()

        self.open_store()

        self.assertEqual(event_names(self.log), ["database.opened"])

    def test_an_older_database_records_the_step_it_needed(self) -> None:
        store = self.open_store()
        store._connection.execute("PRAGMA user_version = 1")
        store._connection.commit()
        store.close()
        self.log.unlink()

        self.open_store()

        lines = self.log.read_text(encoding="utf-8")
        self.assertIn("event=database.migrated detail=from=1 to=2", lines)
        self.assertNotIn("from=0 to=1", lines)

    def test_saving_a_job_records_its_identifier_and_not_its_content(self) -> None:
        store = self.open_store()
        self.log.unlink()

        store.save_job(sample_job())

        text = self.log.read_text(encoding="utf-8")
        self.assertIn("event=job.saved detail=id=j1", text)
        self.assertNotIn("Confidential Employer", text)
        self.assertNotIn("jobs.example", text)
        self.assertNotIn("AI Intern", text)

    def test_saving_the_profile_records_no_values_at_all(self) -> None:
        store = self.open_store()
        self.log.unlink()

        store.save_profile(PROFILE)

        text = self.log.read_text(encoding="utf-8")
        self.assertIn("event=profile.saved", text)
        self.assertNotIn("Kubernetes-Operator-Skill", text)

    def test_a_tracker_change_and_an_activity_entry_are_recorded(self) -> None:
        store = self.open_store()
        store.save_job(sample_job())
        self.log.unlink()

        store.save_tracker(ApplicationTracker("j1"))
        entry_id = store.add_activity("j1", ApplicationActivity(
            kind=ActivityKind.INTERVIEW, occurred_on=date(2026, 10, 14), detail="Second round, 40 minutes.",
        ))

        text = self.log.read_text(encoding="utf-8")
        self.assertIn("event=tracker.saved detail=id=j1 status=discovered confirmed=0", text)
        self.assertIn("event=activity.added detail=id=j1 kind=interview", text)
        self.assertNotIn("Second round", text)

        self.log.unlink()
        store.delete_activity(entry_id)
        self.assertIn(f"event=activity.deleted detail=activity_id={entry_id}",
                      self.log.read_text(encoding="utf-8"))

    def test_a_deletion_that_removed_nothing_is_not_recorded_as_an_event(self) -> None:
        store = self.open_store()
        self.log.unlink()

        self.assertFalse(store.delete_job("never-saved"))
        self.assertFalse(store.delete_activity(999))

        self.assertFalse(self.log.exists(), "a no-op must not look like something happened")

    def test_a_refused_write_is_not_recorded_as_a_success(self) -> None:
        store = self.open_store()
        self.log.unlink()

        with self.assertRaises(ValueError):
            store.add_activity("never-saved", ApplicationActivity(
                kind=ActivityKind.NOTE, occurred_on=date(2026, 10, 14), detail="Nothing to attach this to.",
            ))

        self.assertFalse(self.log.exists(), "a refused write must not appear as an activity entry")

    def test_a_failed_schema_step_records_the_failure_rather_than_a_migration(self) -> None:
        def broken_step(connection) -> None:
            connection.execute("CREATE TABLE half_applied (value TEXT)")
            raise RuntimeError("simulated failure inside the step")

        with mock.patch.object(
            __import__("career_agent.store", fromlist=["store"]), "_MIGRATIONS",
            ((1, "create the base tables", __import__("career_agent.store", fromlist=["store"])._migration_to_v1),
             (2, "a step that fails", broken_step)),
        ):
            with self.assertRaises(__import__("career_agent.store", fromlist=["store"]).SchemaMigrationError):
                CareerStore(str(self.database))

        text = self.log.read_text(encoding="utf-8")
        self.assertIn("event=database.migration_failed detail=to=2 from=1", text)
        self.assertIn("event=database.migrated detail=from=0 to=1", text)
        self.assertNotIn("from=1 to=2", text)

    def test_a_startup_failure_is_recorded_in_the_sequence_not_only_in_the_overwritten_note(self) -> None:
        from career_agent import diagnostics
        from career_agent.store import SchemaTooNewError

        note = diagnostics.record_startup_failure(
            SchemaTooNewError(3, 2), database_path=self.database, timestamp=STAMP,
        )

        self.assertIsNotNone(note)
        self.assertIn("event=startup.failed detail=type=SchemaTooNewError",
                      self.log.read_text(encoding="utf-8"))

    def test_a_log_that_cannot_be_written_does_not_stop_a_save(self) -> None:
        """The point of the log is to explain a failure, never to cause one."""
        store = self.open_store()

        def refuse(*_args, **_kwargs):
            raise OSError("simulated: the log file could not be opened")

        with mock.patch.object(event_log, "append_private_text_file", refuse):
            store.save_job(sample_job("j-blocked"))

        self.assertEqual(store.get_job("j-blocked").listing_id, "j-blocked")


if __name__ == "__main__":
    unittest.main()
