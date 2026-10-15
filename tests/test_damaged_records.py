"""What happens when a database holds a record this build cannot read.

A record can become unreadable without the file being damaged as a database: a status written by a later
version, a hand-edited value, or a payload from a build that knew fields this one does not. SQLite is happy
with all of them, so a structural check - can the file be opened, do the references resolve - passes while
every read path refuses the row.

The properties tested here are the ones a person would be harmed by if they were wrong:

* ``--doctor`` says "no problems found" only when the app could actually read the data, because a report that
  clears a file the app refuses is worse than no report at all;
* a read-only report refuses such a record in one clear sentence with a documented exit status, instead of
  reporting it as an unexpected failure with a traceback;
* nothing is repaired, rewritten or migrated by either - the file is byte-for-byte what it was, so a
  verified backup still restores over it;
* and the export can still take the data out of the app, marking the part this build cannot label.

Every fixture here is invented and every database is disposable.
"""
from __future__ import annotations

import contextlib
import io
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest import mock
from datetime import date, timedelta
from pathlib import Path

import career_agent.__main__ as cli
from career_agent.core import (
    ActivityKind, ApplicationActivity, ApplicationStatus, ApplicationTracker, Availability, CandidateProfile,
    InterviewStage, JobListing,
)
from career_agent.store import (
    SCHEMA_VERSION, CareerStore, TrackerStatusError, unreadable_stored_records,
)

UNKNOWN_STATUS = "sent-somewhere"


class DisposableDatabaseTestCase(unittest.TestCase):
    """A temporary folder and a database built record by record; everything in it is invented."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.today = date.today()

    def run_cli(self, *arguments: object) -> tuple[int, str, str]:
        """Run the real parser and the real command; return (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*(str(argument) for argument in arguments), "--database", str(self.database)])
        return code, out.getvalue(), err.getvalue()

    def write_one_of_every_record(self, listing_id: str = "j1") -> None:
        """Store one record of every kind the read paths decode, so a healthy file reports nothing."""
        with CareerStore(self.database) as store:
            store.save_job(JobListing(listing_id, "fixture", "Fixture",
                                      f"https://jobs.example.invalid/{listing_id}", "Sandbox Systems",
                                      "Data Engineer", availability_status=Availability.OPEN))
            store.save_tracker(ApplicationTracker(listing_id).with_follow_up(
                self.today + timedelta(days=3), note="ask about the panel"))
            store.add_activity(listing_id, ApplicationActivity(
                ActivityKind.APPLIED, self.today, "sent the form through the employer's own site"))
            store.add_preparation(listing_id, "Re-read the job description", due_on=self.today)
            store.record_interview(listing_id, InterviewStage.SCREENING, self.today + timedelta(days=6))
            store.add_work_history("Sandbox Systems", "Data Intern", date(2024, 6, 1), is_current=True)
            store.add_education("Sandbox Institute", "B.Tech")

    def damage_status(self, listing_id: str = "j1") -> None:
        """Write a status value no version of this application knows, exactly as a later build might."""
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("UPDATE application_tracker SET status=? WHERE listing_id=?",
                               (UNKNOWN_STATUS, listing_id))
            connection.commit()
        finally:
            connection.close()

    def bytes_of_database(self) -> bytes:
        return self.database.read_bytes()


class UnreadableRecordScanTests(DisposableDatabaseTestCase):
    """The read-only sweep the doctor uses: it must see what the app would see, and change nothing."""

    def test_a_healthy_database_of_every_record_kind_reports_nothing(self) -> None:
        self.write_one_of_every_record()

        self.assertEqual(unreadable_stored_records(self.database), ())

    def test_a_status_this_version_does_not_know_is_reported_with_its_table_and_record(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()

        problems = unreadable_stored_records(self.database)

        self.assertEqual(len(problems), 1, problems)
        self.assertIn(UNKNOWN_STATUS, problems[0])
        self.assertIn("application_tracker", problems[0])
        self.assertIn("'j1'", problems[0], "the report must say which record it is")
        self.assertIn("was not changed", problems[0])

    def test_a_payload_this_version_cannot_use_is_reported_rather_than_raised(self) -> None:
        self.write_one_of_every_record()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("UPDATE job_listings SET payload=? WHERE listing_id='j1'", ('{"listing_id": "j1"}',))
            connection.commit()
        finally:
            connection.close()

        problems = unreadable_stored_records(self.database)

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("job listing", problems[0])
        self.assertIn("availability status", problems[0])

    def test_an_activity_kind_this_version_does_not_know_is_reported(self) -> None:
        self.write_one_of_every_record()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("UPDATE application_activity SET kind='teleported'")
            connection.commit()
        finally:
            connection.close()

        problems = unreadable_stored_records(self.database)

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("activity entry", problems[0])
        self.assertIn("application_activity", problems[0])

    def test_only_the_damaged_record_is_reported_when_the_rest_are_fine(self) -> None:
        self.write_one_of_every_record("j1")
        with CareerStore(self.database) as store:
            store.save_job(JobListing("j2", "fixture", "Fixture",
                                      "https://jobs.example.invalid/j2", "Sandbox Systems", "QA Engineer",
                                      availability_status=Availability.OPEN))
            store.save_tracker(ApplicationTracker("j2"))
        self.damage_status("j2")

        problems = unreadable_stored_records(self.database)

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("'j2'", problems[0])
        self.assertNotIn("'j1'", problems[0], "a healthy record must not be named")

    def test_a_missing_file_is_not_a_problem_and_is_not_created(self) -> None:
        missing = self.folder / "not_there.sqlite3"

        self.assertEqual(unreadable_stored_records(missing), ())
        self.assertFalse(missing.exists(), "the scan created the file it was asked to read")

    def test_the_sweep_changes_nothing_in_the_file(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()
        before = self.bytes_of_database()

        unreadable_stored_records(self.database)

        self.assertEqual(self.bytes_of_database(), before, "the scan wrote to the file")

    def test_an_older_schema_is_left_at_its_own_version(self) -> None:
        """The doctor promises never to change the file; reading its records must not upgrade it either."""
        self.write_one_of_every_record()
        self.damage_status()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("PRAGMA user_version = 5")
            connection.commit()
        finally:
            connection.close()
        before = self.bytes_of_database()

        unreadable_stored_records(self.database)

        connection = sqlite3.connect(str(self.database))
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(version, 5, "reading the records migrated the file")
        self.assertEqual(self.bytes_of_database(), before)

    def test_a_status_error_is_a_value_error_so_callers_can_handle_it_like_any_refusal(self) -> None:
        with CareerStore(self.database) as store:
            store.save_job(JobListing("j1", "fixture", "Fixture", "https://jobs.example.invalid/1",
                                      "Sandbox Systems", "Data Engineer", availability_status=Availability.OPEN))
            store.save_tracker(ApplicationTracker("j1"))
        self.damage_status()
        with self.assertRaises(TrackerStatusError) as raised:
            with CareerStore(self.database) as store:
                store.list_trackers()
        self.assertIsInstance(raised.exception, ValueError)


class DoctorOnDamagedRecordsTests(DisposableDatabaseTestCase):
    """``--doctor`` must answer the question it is asked: can this app read this data?"""

    def test_a_damaged_record_is_a_problem_and_the_record_is_named(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()

        code, out, _ = self.run_cli("--doctor")

        self.assertEqual(code, cli.EXIT_PROBLEM_FOUND)
        self.assertNotIn("No problems found", out)
        self.assertIn("PROBLEM", out)
        self.assertIn(UNKNOWN_STATUS, out)
        self.assertIn("application_tracker", out)
        self.assertIn("'j1'", out)

    def test_the_doctor_changes_nothing_while_reporting_it(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()
        before = self.bytes_of_database()

        code, _, _ = self.run_cli("--doctor")

        self.assertEqual(code, cli.EXIT_PROBLEM_FOUND)
        self.assertEqual(self.bytes_of_database(), before, "the doctor wrote to the database")

    def test_a_healthy_database_says_every_record_could_be_decoded(self) -> None:
        self.write_one_of_every_record()

        code, out, _ = self.run_cli("--doctor")

        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("Every stored record could be decoded by this version.", out)
        self.assertIn("No problems found", out)

    def test_an_older_schema_is_version_checked_first_and_never_upgraded_here(self) -> None:
        """A file an older build wrote is reported by version, not decoded into a false alarm.

        The two rules meet here: the doctor does not change the file, so it does not migrate it, so it does
        not read the records an upgrade would make readable. It says so instead of implying the data is
        fine - and the same file is decoded normally once the app has upgraded it, which the next test
        covers.
        """
        self.write_one_of_every_record()
        self.damage_status()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("PRAGMA user_version = 5")
            connection.commit()
        finally:
            connection.close()

        code, out, _ = self.run_cli("--doctor")

        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("written by schema version 5", out)
        self.assertIn("are not decoded here", out)
        connection = sqlite3.connect(str(self.database))
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 5)
        finally:
            connection.close()

    def test_the_same_file_is_reported_after_the_app_upgrades_it(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("PRAGMA user_version = 5")
            connection.commit()
        finally:
            connection.close()

        with CareerStore(self.database):  # opening the app is what migrates the file
            pass
        code, out, _ = self.run_cli("--doctor")

        self.assertEqual(code, cli.EXIT_PROBLEM_FOUND)
        self.assertIn(UNKNOWN_STATUS, out)
        connection = sqlite3.connect(str(self.database))
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        finally:
            connection.close()


class ReadOnlyReportsOnDamagedRecordsTests(DisposableDatabaseTestCase):
    """A report that reads the damaged record refuses it clearly; one that does not read it still runs."""

    #: Reports whose output depends on the tracker records, so a status this build cannot read stops them.
    REFUSING_COMMANDS = ("--analytics", "--follow-ups", "--next-actions")

    #: Reports that never decode the tracker records, so they are unaffected by an unknown status. Kept
    #: explicit rather than assumed: this is the difference the doctor used to hide.
    UNAFFECTED_COMMANDS = ("--history", "--interviews", "--worker-status")

    def test_each_report_that_reads_the_record_refuses_it_with_a_documented_status(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()
        before = self.bytes_of_database()

        for command in self.REFUSING_COMMANDS:
            with self.subTest(command=command):
                code, out, err = self.run_cli(command)
                self.assertEqual(code, cli.EXIT_REFUSED, f"{command} exited {code}")
                self.assertIn("REFUSED", err)
                self.assertIn(UNKNOWN_STATUS, err, "the message must name what could not be read")
                self.assertIn("--doctor", err, "the message must say how to find out which record it is")
                self.assertNotIn("Traceback", err)
                self.assertNotIn("Traceback", out)
                self.assertNotIn("COULD NOT START", err + out)
        self.assertEqual(self.bytes_of_database(), before, "a read-only report wrote to the database")

    def test_the_reports_that_do_not_read_the_record_still_run(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()

        for command in self.UNAFFECTED_COMMANDS:
            with self.subTest(command=command):
                code, out, err = self.run_cli(command)
                self.assertEqual(code, cli.EXIT_OK, f"{command} exited {code}: {err}")
                self.assertNotIn("Traceback", err)
                self.assertNotIn("REFUSED", err)

    def test_the_refusal_is_the_only_failure_and_the_report_says_nothing_was_changed(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()

        code, out, err = self.run_cli("--analytics")

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("Nothing was changed or repaired", err)
        # A refusal must not be dressed up as a report: no metric is printed after it.
        self.assertNotIn("Progress from this database", out.splitlines()[-1])


class EveryCommandThatReadsTheRecordTests(DisposableDatabaseTestCase):
    """The refusal has to be the same whichever command reaches the record first.

    The read-only reports word it themselves; the commands that write - a draft, a calendar file, an
    import - used to reach the same record through the failure handler, which describes a *start-up* that
    stopped and leaves a note beside the data. A readable database holding one unreadable row is not a
    start-up failure, and a command that never started a window must not say it did. Reproduced before this
    test existed, from the acceptance run on 2026-10-15: four of these commands exited 3 with
    "COULD NOT START ... the application did not start".
    """

    def assert_refused_cleanly(self, code: int, out: str, err: str, target: Path | None = None) -> None:
        self.assertEqual(code, cli.EXIT_REFUSED, f"exit {code}: {err}")
        self.assertIn("REFUSED", err)
        self.assertIn(UNKNOWN_STATUS, err, "the refusal must name what could not be read")
        self.assertIn("--doctor", err, "the refusal must say how to find which record it is")
        self.assertNotIn("COULD NOT START", err + out)
        self.assertNotIn("Traceback", err + out)
        if target is not None:
            self.assertFalse(target.exists(), f"{target.name} was written despite the refusal")
        note = self.database.parent / "logs" / "startup-diagnostics.log"
        self.assertFalse(note.exists(), "a refusal is not a start-up failure, so no start-up note is written")

    def test_the_writing_commands_refuse_the_record_the_same_way_the_reports_do(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()
        before = self.bytes_of_database()
        calendar = self.folder / "follow-ups.ics"
        draft = self.folder / "draft.txt"
        commands = (("--preview-calendar-export", None),
                    ("--calendar-to", calendar),
                    ("--draft-follow-up", "j1"),
                    ("--record-follow-up", "j1"))
        for command, value in commands:
            with self.subTest(command=command):
                target = draft if command == "--draft-follow-up" else value
                arguments = [command] if value is None else (command, value)
                if command == "--draft-follow-up":
                    arguments = (command, value, "--save-draft", str(draft))
                code, out, err = self.run_cli(*arguments)
                self.assert_refused_cleanly(code, out, err, target if isinstance(target, Path) else None)
        self.assertEqual(self.bytes_of_database(), before, "a refused command wrote to the database")

    def test_a_file_that_is_not_a_database_is_refused_by_those_commands_too(self) -> None:
        self.database.write_text("this is not a database", encoding="utf-8")
        before = self.bytes_of_database()

        code, out, err = self.run_cli("--preview-calendar-export")

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("could not be read", err)
        self.assertNotIn("COULD NOT START", err + out)
        self.assertEqual(self.bytes_of_database(), before)

    def rows_of_every_table(self) -> dict[str, list[tuple]]:
        """Every row of every table, so "nothing was written" can be checked as a fact rather than a claim."""
        connection = sqlite3.connect(str(self.database))
        connection.row_factory = sqlite3.Row
        try:
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
                    for table in tables}
        finally:
            connection.close()

    def test_an_import_into_a_database_with_an_unreadable_record_writes_nothing(self) -> None:
        """The refusal must come before the writing, not after half of it.

        An import carries a profile, listings, application records, a follow-up plan and history, and it is
        applied record by record. Applying it to a file that holds a record this build cannot read wrote the
        parts that came first and then refused - so the message "Nothing was changed or repaired" was
        printed over a database that had gained a profile, three employment records, two education records
        and a rewritten listing. Reproduced before this test existed, from the acceptance run on
        2026-10-15: the source below is the shape that reaches it, a file exported from this same database
        before one record became unreadable, which is what somebody restoring their own export would hold.
        """
        source_database = self.folder / "source.sqlite3"
        with CareerStore(source_database) as store:
            store.save_job(JobListing("j1", "fixture", "Fixture", "https://jobs.example.invalid/j1",
                                      "Sandbox Systems", "Data Engineer", availability_status=Availability.OPEN))
            store.save_tracker(ApplicationTracker("j1"))
            store.save_profile(CandidateProfile(candidate_country="India", degree_discipline="ECE",
                                                study_status="final_year", graduation_year=2027,
                                                experience_years=1.0, skills=frozenset({"Python"}),
                                                preferred_locations=frozenset({"Bengaluru"}),
                                                preferred_work_modes=frozenset({"hybrid"}),
                                                preferred_role_types=frozenset({"full_time"})))
            store.add_work_history("Sandbox Systems", "Data Intern", date(2024, 6, 1), is_current=True)
        source = self.folder / "source.json"
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--database", str(source_database), "--export-to", str(source)])
        self.assertEqual(code, cli.EXIT_OK, err.getvalue())

        self.write_one_of_every_record("j1")
        self.damage_status("j1")
        before_bytes = self.bytes_of_database()
        before_rows = self.rows_of_every_table()

        code, out, err = self.run_cli("--import-from", source, "--yes")

        self.assert_refused_cleanly(code, out, err)
        self.assertIn("application_tracker", err, "the refusal must name the table the record is in")
        self.assertEqual(self.rows_of_every_table(), before_rows,
                         "the refused import wrote rows into the database")
        self.assertEqual(self.bytes_of_database(), before_bytes,
                         "the refused import changed the file it refused to write to")

    def test_a_refused_calendar_write_leaves_no_ledger_behind(self) -> None:
        """A mock ledger records operations that happened; a refusal means none did."""
        self.write_one_of_every_record()
        self.damage_status()
        ledger = self.folder / "ledger.json"

        code, out, err = self.run_cli("--record-follow-up", "j1", "--mock-ledger", ledger)

        self.assert_refused_cleanly(code, out, err)
        self.assertFalse(ledger.exists(), "a refused operation was recorded in the mock ledger")

    def test_opening_the_window_still_reports_a_record_it_cannot_read_as_a_start_up_failure(self) -> None:
        """The one case that really is a start-up: the person asked for the window, not a command."""
        # ``mock.patch.dict`` puts ``sys.modules`` back exactly as it was, real module and all; the fake is
        # only needed while this one call runs, and any import a later test does must find the real one.
        fake_module = types.ModuleType("career_agent.desktop")

        def failing_main(database_path=None):
            raise TrackerStatusError(UNKNOWN_STATUS)

        fake_module.main = failing_main
        with mock.patch.dict(sys.modules, {"career_agent.desktop": fake_module}):
            code, out, err = self.run_cli()

        self.assertEqual(code, cli.EXIT_UNEXPECTED)
        self.assertIn("COULD NOT START", err)
        self.assertNotIn("REFUSED", err)


class NotADatabaseAtAllTests(DisposableDatabaseTestCase):
    """A file that cannot be read as a database is not described as a database holding a bad record.

    The two failures look alike from a distance and are not alike at all: one is a row this build cannot
    decode, the other is a file with no rows in it. Both are refused, and the refusal has to say which
    happened, because the first sends somebody to look at a record and the second sends them to look at the
    file. Reproduced before this test existed, from the acceptance run on 2026-10-15: only the record-level
    sentence was printed for both.
    """

    def write_garbage(self) -> None:
        self.database.write_text("this is not a database, it is a text file with a database name",
                                 encoding="utf-8")

    def test_a_file_that_is_not_a_database_is_reported_as_a_file_failure(self) -> None:
        self.write_garbage()
        before = self.bytes_of_database()

        code, out, err = self.run_cli("--analytics")

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("could not be read", err)
        self.assertIn("file is not a database", err, "SQLite's own words explain the file")
        self.assertNotIn(
            "holds a record this version cannot read", err,
            "a file with no records must not be described as holding an unreadable record",
        )
        self.assertNotIn("Traceback", err + out)
        self.assertEqual(self.bytes_of_database(), before, "the refused file was rewritten")

    def test_the_doctor_names_the_file_and_the_reason_on_the_same_input(self) -> None:
        self.write_garbage()

        code, out, _ = self.run_cli("--doctor")

        self.assertEqual(code, cli.EXIT_PROBLEM_FOUND)
        self.assertIn("file is not a database", out)
        self.assertIn("Nothing was changed", out)


class ExportOfDamagedRecordsTests(DisposableDatabaseTestCase):
    """An export must still be able to take the data out, and must not pretend to recognise it."""

    def test_the_export_marks_the_value_it_cannot_label_and_keeps_the_rest(self) -> None:
        self.write_one_of_every_record()
        self.damage_status()
        target = self.folder / "export.json"

        code, out, err = self.run_cli("--export-to", str(target))

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("Wrote 1 listing(s)", out)
        document = target.read_text(encoding="utf-8")
        self.assertIn(UNKNOWN_STATUS, document)
        self.assertIn('"status_recognised": false', document)
        self.assertIn("ask about the panel", document, "the follow-up note must travel with the record")


class WriteRefusalTests(DisposableDatabaseTestCase):
    """A database that cannot be *written* must not be described as one that cannot be read.

    Measured on 2026-10-15 against a valid database: at mode ``444``, or inside a folder the account cannot
    write to, a command that writes fails with SQLite's own "attempt to write a readonly database". The
    refusal used to say *"this database file could not be read, so nothing was reported"* and advise
    restoring a verified backup over the file. Nothing was ever written by mistake - failing was the
    correct outcome - but the explanation described a read for a write, sent the reader looking for damage
    that is not there, and recommended a restore that would fail in exactly the same way. Two minutes of
    looking at the wrong thing is the whole harm of a wrong sentence, and it is why the words are tested
    here rather than left to review.
    """

    def setUp(self) -> None:
        super().setUp()
        if os.name != "posix":
            self.skipTest("this is reproduced with file modes, which are not meaningful on this platform")
        if os.geteuid() == 0:
            self.skipTest("root ignores file modes, so a read-only file is not read-only for it")

    def make_the_file_read_only(self) -> bytes:
        """Store one record of every kind, then take the write permission away from the database file."""
        self.write_one_of_every_record()
        before = self.bytes_of_database()
        os.chmod(self.database, 0o444)
        self.addCleanup(os.chmod, self.database, 0o600)
        return before

    def test_a_write_to_a_read_only_file_is_not_reported_as_a_read_failure(self) -> None:
        before = self.make_the_file_read_only()

        code, out, err = self.run_cli("--seed-tasks")

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("could not be written", err)
        self.assertNotIn("could not be read", err)
        self.assertNotIn("COULD NOT START", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(self.bytes_of_database(), before,
                         "a refused write must leave the database byte-for-byte as it was")

    def test_the_write_permission_is_the_whole_problem(self) -> None:
        """Giving the permission back must be the entire fix, or the message is pointing at the wrong thing."""
        self.make_the_file_read_only()
        self.assertEqual(self.run_cli("--seed-tasks")[0], cli.EXIT_REFUSED)

        os.chmod(self.database, 0o600)
        code, out, err = self.run_cli("--seed-tasks")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertNotIn("could not be written", err)

    def test_a_database_in_a_folder_that_cannot_be_written_is_reported_as_a_write_failure(self) -> None:
        self.write_one_of_every_record()
        before = self.bytes_of_database()
        os.chmod(self.folder, 0o555)
        self.addCleanup(os.chmod, self.folder, 0o755)

        code, out, err = self.run_cli("--add-role", "Acme Analytics", "--title", "Data Analyst",
                                      "--start", "2026-01-05", "--current")

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("could not be written", err)
        self.assertNotIn("could not be read", err)
        self.assertEqual(self.bytes_of_database(), before)

    def test_the_classifier_does_not_capture_read_failures(self) -> None:
        """A read failure has to keep its own sentence: a damaged file must not be called read-only."""
        for message in (
            "attempt to write a readonly database",
            "unable to open database file",
            "database is locked",
            "read-only file system",
        ):
            with self.subTest(message=message):
                self.assertTrue(cli.looks_like_a_write_failure(message))

        for message in (
            "file is not a database",
            "no such table: application_tracker",
            "database disk image is malformed",
        ):
            with self.subTest(message=message):
                self.assertFalse(cli.looks_like_a_write_failure(message))


if __name__ == "__main__":
    unittest.main()
