"""Tests for the follow-up commands: the report, and the calendar file written for the person's own use.

The commands are the only place a follow-up can be *seen* without the window, so the properties tested
here are the ones a person would be harmed by if they were wrong: the report changes nothing, it never
says an application moved, the export is owner-only and refuses to overwrite a file that already exists,
and neither command invents follow-ups that were never recorded.
"""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

import career_agent.__main__ as cli
from career_agent.core import ApplicationStatus, ApplicationTracker, Availability, JobListing
from career_agent.store import CareerStore


class FollowUpCommandTests(unittest.TestCase):
    """A temporary folder and a disposable database; every application in it is invented."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.today = datetime.now().date()

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*arguments, "--database", str(self.database)])
        return code, out.getvalue(), err.getvalue()

    def add_application(self, listing_id: str, *, days: int | None, role: str = "Data Engineer",
                        note: str | None = None, employer: str = "Sandbox Systems") -> None:
        """Store one application, optionally with a follow-up day relative to today."""
        with CareerStore(self.database) as store:
            store.save_job(JobListing(listing_id, "fixture", "Fixture",
                                      f"https://jobs.example.invalid/{listing_id}", employer, role,
                                      availability_status=Availability.UNKNOWN))
            store.save_tracker(ApplicationTracker(listing_id))
            if days is not None:
                store.save_tracker(ApplicationTracker(listing_id).with_follow_up(
                    self.today + timedelta(days=days), note=note))

    def stored_status(self, listing_id: str) -> ApplicationStatus:
        with CareerStore(self.database) as store:
            return store.get_tracker(listing_id).status

    # ------------------------------------------------------------------ the report
    def test_the_report_lists_what_is_due_and_says_nothing_was_changed(self):
        self.add_application("j1", days=-2, role="Data Engineer", note="ask about the panel")
        self.add_application("j2", days=0, role="QA Engineer")
        self.add_application("j3", days=4, role="Designer")

        code, out, err = self.run_cli("--follow-ups")

        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("1 overdue", out)
        self.assertIn("1 due today", out)
        self.assertIn("Data Engineer", out)
        self.assertIn("ask about the panel", out)
        self.assertIn("in 4 day(s)", out)
        self.assertIn("no status was changed and nothing was sent", out)

    def test_the_report_says_the_day_it_used_is_the_local_one(self):
        self.add_application("j1", days=0)

        _, out, _ = self.run_cli("--follow-ups")

        self.assertIn(f"follow-ups for {self.today.isoformat()} (local day)", out)

    def test_the_report_changes_no_status(self):
        self.add_application("j1", days=-5)

        self.run_cli("--follow-ups")

        self.assertEqual(self.stored_status("j1"), ApplicationStatus.DISCOVERED)

    def test_a_record_with_no_day_recorded_is_not_invented_into_the_report(self):
        self.add_application("j1", days=None, role="Analyst")

        _, out, _ = self.run_cli("--follow-ups")

        self.assertIn("No follow-ups are recorded", out)
        self.assertNotIn("Analyst", out)

    def test_a_missing_database_is_a_fresh_installation_not_a_failure(self):
        code, out, err = self.run_cli("--follow-ups")

        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("No database yet", out)
        self.assertFalse(self.database.exists(), "a report must not create the database it reads")

    def test_a_follow_up_whose_listing_was_deleted_is_counted_not_hidden(self):
        """The listing is removed from under the tracker, which is what a partial delete looks like."""
        self.add_application("j1", days=-1)
        with CareerStore(self.database) as store:
            store._connection.execute("PRAGMA foreign_keys = OFF")
            store._connection.execute("DELETE FROM job_listings WHERE listing_id='j1'")
            store._connection.commit()

        code, out, _ = self.run_cli("--follow-ups")

        self.assertEqual(code, 0)
        self.assertIn("1 record(s) have a follow-up day but no listing stored any more", out)

    # ------------------------------------------------------------------ the calendar export
    def test_the_export_writes_an_owner_only_file_and_says_what_it_holds(self):
        self.add_application("j1", days=3, note="nudge the recruiter")
        target = self.folder / "follow-ups.ics"

        code, out, err = self.run_cli("--calendar-to", str(target))

        self.assertEqual(code, 0, err)
        self.assertTrue(target.is_file())
        self.assertIn("Wrote 1 reminder(s)", out)
        self.assertIn("Nothing was sent anywhere", out)
        if os.name == "posix":
            self.assertEqual(target.stat().st_mode & 0o777, 0o600,
                             "a file about somebody's job search is not for other accounts to read")
        text = target.read_text(encoding="utf-8")
        self.assertIn("BEGIN:VCALENDAR", text)
        self.assertIn("Follow up: Data Engineer at Sandbox Systems", text)

    def test_the_export_refuses_to_replace_a_file_that_already_exists(self):
        self.add_application("j1", days=3)
        target = self.folder / "follow-ups.ics"
        target.write_text("something the person already had", encoding="utf-8")

        code, out, err = self.run_cli("--calendar-to", str(target))

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("already exists", err)
        self.assertIn("career-agent-follow-ups-", err, "the refusal suggests a name")
        self.assertEqual(target.read_text(encoding="utf-8"), "something the person already had")

    def test_an_export_with_nothing_recorded_writes_no_file(self):
        self.add_application("j1", days=None)
        target = self.folder / "follow-ups.ics"

        code, out, err = self.run_cli("--calendar-to", str(target))

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("No follow-up days are recorded", out)
        self.assertEqual(err, "")
        self.assertFalse(target.exists())

    def test_the_export_needs_a_database_and_invents_nothing_without_one(self):
        target = self.folder / "follow-ups.ics"

        code, out, err = self.run_cli("--calendar-to", str(target))

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("Nothing was written", out)
        self.assertFalse(target.exists())

    def test_the_exported_file_lists_only_recorded_follow_ups(self):
        self.add_application("j1", days=1, role="Data Engineer")
        self.add_application("j2", days=None, role="Analyst")
        target = self.folder / "follow-ups.ics"

        self.run_cli("--calendar-to", str(target))

        text = target.read_text(encoding="utf-8")
        self.assertEqual(text.count("BEGIN:VEVENT"), 1)
        self.assertIn("Data Engineer", text)
        self.assertNotIn("Analyst", text)

    def test_the_commands_are_exclusive_with_the_other_actions(self):
        quiet = io.StringIO()
        for combination in (("--follow-ups", "--worker-status"), ("--calendar-to", "x.ics", "--doctor")):
            with self.subTest(combination=combination):
                with contextlib.redirect_stderr(quiet), self.assertRaises(SystemExit) as caught:
                    cli.parse_arguments(list(combination))

                self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
