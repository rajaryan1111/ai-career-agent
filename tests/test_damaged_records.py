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
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import career_agent.__main__ as cli
from career_agent.core import (
    ActivityKind, ApplicationActivity, ApplicationStatus, ApplicationTracker, Availability, InterviewStage,
    JobListing,
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

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        """Run the real parser and the real command; return (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*arguments, "--database", str(self.database)])
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


if __name__ == "__main__":
    unittest.main()
