"""The email and calendar commands: drafts and previews that change nothing, and a mock that says so.

Every test here runs the real command line against a disposable database in a temporary folder, and the
applications in it are invented. The properties worth this file's length are the ones a person could be
harmed by: that a draft never becomes a send, that a preview never becomes a file, that asking twice never
performs anything twice, and that the database is byte-for-byte unchanged by any of it.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import career_agent.__main__ as cli
from career_agent import integrations
from career_agent.core import ApplicationStatus, ApplicationTracker, Availability, JobListing
from career_agent.store import CareerStore


class IntegrationCommandTestCase(unittest.TestCase):
    """A temporary folder, a disposable database, and a command runner that captures output."""

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

    def add_application(self, listing_id: str = "j1", *, days: int | None = 3,
                        role: str = "Data Engineer", employer: str = "Sandbox Systems",
                        note: str | None = "ask about the panel") -> None:
        """Store one application, optionally with a follow-up day relative to today."""
        with CareerStore(self.database) as store:
            store.save_job(JobListing(listing_id, "fixture", "Fixture",
                                      f"https://jobs.example.invalid/{listing_id}", employer, role,
                                      availability_status=Availability.UNKNOWN))
            tracker = ApplicationTracker(listing_id)
            if days is not None:
                tracker = tracker.with_follow_up(self.today + timedelta(days=days), note=note)
            store.save_tracker(tracker)

    def fingerprint(self) -> tuple[int, str] | None:
        """The database file's size and digest, so "nothing was written" can be checked rather than assumed."""
        if not self.database.exists():
            return None
        payload = self.database.read_bytes()
        return len(payload), hashlib.sha256(payload).hexdigest()

    def stored_tracker(self, listing_id: str = "j1") -> ApplicationTracker:
        with CareerStore(self.database) as store:
            return store.get_tracker(listing_id)

    def folder_entries(self) -> set[str]:
        return {item.name for item in self.folder.iterdir()}


class IntegrationStatusCommandTests(IntegrationCommandTestCase):
    """The status report answers the question without touching anything."""

    def test_it_lists_the_state_the_mock_and_every_condition_for_enabling_a_provider(self):
        code, out, err = self.run_cli("--integration-status")

        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("Integration state: nothing is enabled", out)
        self.assertIn("local-mock", out)
        for name, _reason in integrations.ENABLEMENT_REQUIREMENTS:
            with self.subTest(requirement=name):
                self.assertIn(name, out)
        self.assertIn("nothing was sent, nothing was created", out)

    def test_it_creates_no_database_and_touches_no_file(self):
        before = self.folder_entries()

        code, _out, _err = self.run_cli("--integration-status")

        self.assertEqual(code, 0)
        self.assertIsNone(self.fingerprint())
        self.assertEqual(self.folder_entries(), before)


class CalendarExportPreviewTests(IntegrationCommandTestCase):
    """The preview describes the local file, and writes nothing at all."""

    def test_it_lists_the_events_the_export_would_contain_and_writes_nothing(self):
        self.add_application("j1", days=3)
        self.add_application("j2", days=-1, role="QA Engineer", note=None)
        before = self.fingerprint()

        code, out, err = self.run_cli("--preview-calendar-export")

        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("2 event(s) would be written", out)
        self.assertIn("Follow up: Data Engineer at Sandbox Systems", out)
        self.assertIn(f"follow-up-j1-{(self.today + timedelta(days=3)).strftime('%Y%m%d')}"
                      "@ai-career-agent.local", out)
        self.assertIn("Nothing was written by this command", out)
        self.assertEqual(self.fingerprint(), before, "a preview must not change the database")
        self.assertEqual([item for item in self.folder.iterdir() if item.suffix == ".ics"], [])

    def test_the_preview_names_exactly_the_events_the_export_then_writes(self):
        self.add_application("j1", days=3)
        _code, out, _err = self.run_cli("--preview-calendar-export")
        target = self.folder / "reminders.ics"

        code, _written, err = self.run_cli("--calendar-to", str(target))

        self.assertEqual(code, 0, err)
        document = target.read_text(encoding="utf-8")
        uids = [line for line in out.splitlines() if "follow-up-j1-" in line]
        self.assertEqual(len(uids), 1)
        uid = uids[0].split("[", 1)[1].rstrip("]")
        self.assertIn(f"UID:{uid}", document)
        self.assertIn("SUMMARY:Follow up: Data Engineer at Sandbox Systems", document)
        self.assertNotIn("ATTENDEE", document)
        self.assertNotIn("ORGANIZER", document)

    def test_no_follow_up_days_means_a_refusal_and_nothing_written(self):
        self.add_application("j1", days=None)

        code, out, err = self.run_cli("--preview-calendar-export")

        self.assertEqual(code, 2)
        self.assertEqual(err, "", "a refusal that is a state of the data is not an error message")
        self.assertIn("No follow-up days are recorded", out)
        self.assertIn("Nothing was written", out)

    def test_no_database_means_a_refusal_and_no_database_is_created(self):
        code, out, _err = self.run_cli("--preview-calendar-export")

        self.assertEqual(code, 2)
        self.assertIn("No database yet", out)
        self.assertIsNone(self.fingerprint())


class DraftFollowUpCommandTests(IntegrationCommandTestCase):
    """A draft is text: it is printed, optionally saved locally, and never sent."""

    def test_the_draft_is_printed_in_full_with_the_missing_address_marked(self):
        self.add_application("j1", days=3)
        before = self.fingerprint()

        code, out, err = self.run_cli("--draft-follow-up", "j1")

        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("Subject: Following up on my application: Data Engineer at Sandbox Systems", out)
        self.assertIn("To: NOT SUPPLIED", out)
        self.assertIn("Status: DRAFT ONLY", out)
        self.assertIn("ask about the panel", out)
        self.assertIn("Missing, and not guessed:", out)
        self.assertIn("Nothing was attempted", out)
        self.assertIn("Operation id: email-", out)
        self.assertEqual(self.fingerprint(), before, "a draft must not change the database")

    def test_a_supplied_address_is_used_and_the_draft_says_nothing_was_sent(self):
        self.add_application("j1", days=3)

        code, out, err = self.run_cli("--draft-follow-up", "j1", "--recipient", "hiring@sandbox.example")

        self.assertEqual(code, 0, err)
        self.assertIn("To: hiring@sandbox.example", out)
        self.assertNotIn("Missing, and not guessed:", out)
        self.assertIn("nothing has been sent", out)

    def test_an_address_that_is_visibly_wrong_is_refused_and_nothing_is_saved(self):
        self.add_application("j1", days=3)
        target = self.folder / "draft.txt"

        code, _out, err = self.run_cli("--draft-follow-up", "j1", "--recipient", "hiring at example",
                                       "--save-draft", str(target))

        self.assertEqual(code, 2)
        self.assertIn("contains a space", err)
        self.assertIn("Nothing was written", err)
        self.assertFalse(target.exists())

    def test_an_unknown_listing_is_refused(self):
        self.add_application("j1", days=3)

        code, _out, err = self.run_cli("--draft-follow-up", "nope")

        self.assertEqual(code, 2)
        self.assertIn("No application is stored with listing id nope", err)

    def test_an_application_without_a_follow_up_day_is_refused_rather_than_given_today(self):
        self.add_application("j1", days=None)

        code, out, err = self.run_cli("--draft-follow-up", "j1")

        self.assertEqual(code, 2)
        self.assertIn("no follow-up day recorded, and this command will not invent one", err)
        self.assertNotIn(self.today.isoformat(), out)

    def test_deleting_the_listing_removes_its_tracker_so_there_is_no_reminder_left_to_draft_from(self):
        """The store's foreign key means a reminder without its listing cannot exist through normal use."""
        self.add_application("j1", days=3)
        with CareerStore(self.database) as store:
            store.delete_job("j1")

        code, _out, err = self.run_cli("--draft-follow-up", "j1")

        self.assertEqual(code, 2)
        self.assertIn("No application is stored with listing id j1", err)

    def test_a_reminder_whose_listing_is_missing_is_refused_rather_than_written_from_nothing(self):
        """Defensive: the store refuses this state, so it is checked against a store that hands it back.

        If a future import, restore or migration ever produced a follow-up day with no listing, the draft
        must be refused with the reason - not built from a role and an employer that no longer exist.
        """
        day = self.today + timedelta(days=2)

        class TrackerOnlyStore:
            def get_tracker(self, _listing_id):
                return ApplicationTracker("j1").with_follow_up(day)

            def get_job(self, _listing_id):
                return None

        reminder, problem = cli._reminder_for_listing(TrackerOnlyStore(), "j1", self.today)

        self.assertIsNone(reminder)
        self.assertIn("no longer stored", problem)
        self.assertIn("no role or employer to write from", problem)

    def test_saving_the_draft_writes_an_owner_only_text_file_and_changes_no_record(self):
        self.add_application("j1", days=3)
        target = self.folder / "draft.txt"
        before = self.fingerprint()

        code, out, err = self.run_cli("--draft-follow-up", "j1", "--save-draft", str(target))

        self.assertEqual(code, 0, err)
        self.assertTrue(target.exists())
        if os.name == "posix":  # owner-only where the platform has modes to check
            self.assertEqual(target.stat().st_mode & 0o077, 0, "a draft holds a private message")
        text = target.read_text(encoding="utf-8")
        self.assertIn("Status: DRAFT ONLY", text)
        self.assertIn("Data Engineer", text)
        self.assertIn("not a message that was sent", out)
        self.assertEqual(self.fingerprint(), before)

    def test_an_existing_draft_file_is_never_replaced(self):
        self.add_application("j1", days=3)
        target = self.folder / "draft.txt"
        target.write_text("something the person wrote first", encoding="utf-8")

        code, _out, err = self.run_cli("--draft-follow-up", "j1", "--save-draft", str(target))

        self.assertEqual(code, 2)
        self.assertIn("already exists", err)
        self.assertEqual(target.read_text(encoding="utf-8"), "something the person wrote first")

    def test_no_database_means_a_refusal_and_nothing_is_written(self):
        code, out, _err = self.run_cli("--draft-follow-up", "j1")

        self.assertEqual(code, 2)
        self.assertIn("No database yet", out)
        self.assertIsNone(self.fingerprint())

    # ------------------------------------------------------------------ the local mock, when it is named

    def test_the_mock_records_the_operation_locally_and_contacts_nothing(self):
        self.add_application("j1", days=3)
        ledger = self.folder / "ledger.json"

        code, out, err = self.run_cli("--draft-follow-up", "j1", "--recipient", "hiring@sandbox.example",
                                      "--mock-ledger", str(ledger))

        self.assertEqual(code, 0, err)
        self.assertIn("[completed]", out)
        self.assertIn("No email was sent", out)
        if os.name == "posix":  # owner-only where the platform has modes to check
            self.assertEqual(ledger.stat().st_mode & 0o077, 0)
        recorded = json.loads(ledger.read_text(encoding="utf-8"))
        self.assertEqual(recorded["ledger_version"], integrations.LEDGER_VERSION)
        self.assertEqual(len(recorded["operations"]), 1)
        self.assertEqual(recorded["operations"][0]["target"], "hiring@sandbox.example")

    def test_asking_twice_records_one_operation_and_reports_the_repeat(self):
        self.add_application("j1", days=3)
        ledger = self.folder / "ledger.json"
        arguments = ("--draft-follow-up", "j1", "--recipient", "hiring@sandbox.example",
                     "--mock-ledger", str(ledger))

        first = self.run_cli(*arguments)
        second = self.run_cli(*arguments)

        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(second[0], 0, second[2])
        self.assertIn("[completed]", first[1])
        self.assertIn("[duplicate]", second[1])
        self.assertIn("nothing was sent or created twice", second[1])
        self.assertEqual(len(json.loads(ledger.read_text(encoding="utf-8"))["operations"]), 1)

    def test_a_draft_without_an_address_is_refused_by_the_mock_and_recorded_nowhere(self):
        self.add_application("j1", days=3)
        ledger = self.folder / "ledger.json"

        code, out, err = self.run_cli("--draft-follow-up", "j1", "--mock-ledger", str(ledger))

        self.assertEqual(code, 2)
        self.assertIn("[invalid]", out)
        self.assertIn("recipient", out)
        self.assertIn("not performed (invalid)", err)
        self.assertIn("no file was written", err,
                      "a refusal after saving nothing must not say a draft was written")
        self.assertFalse(ledger.exists(), "nothing was performed, so there was nothing to record")

    def test_a_saved_draft_that_the_mock_refuses_says_which_file_was_written(self):
        """The other state: the person asked for a file, the file exists, and the message names it."""
        self.add_application("j1", days=3)
        target = self.folder / "follow-up.txt"
        ledger = self.folder / "ledger.json"

        code, out, err = self.run_cli("--draft-follow-up", "j1", "--save-draft", str(target),
                                      "--mock-ledger", str(ledger))

        self.assertEqual(code, 2)
        self.assertIn("[invalid]", out)
        self.assertIn("not performed (invalid)", err)
        self.assertIn(str(target), err, "the message must name the file that was written")
        self.assertTrue(target.is_file())
        self.assertIn("DRAFT ONLY", target.read_text(encoding="utf-8"))
        self.assertFalse(ledger.exists())

    def test_a_ledger_that_cannot_be_read_stops_the_command_and_says_why(self):
        self.add_application("j1", days=3)
        ledger = self.folder / "ledger.json"
        ledger.write_text("{ not json", encoding="utf-8")

        code, _out, err = self.run_cli("--draft-follow-up", "j1", "--mock-ledger", str(ledger))

        self.assertEqual(code, 2)
        self.assertIn("cannot establish what it has already done", err)
        self.assertEqual(ledger.read_text(encoding="utf-8"), "{ not json", "the damaged file is left alone")


class RecordFollowUpCommandTests(IntegrationCommandTestCase):
    """Asking for a calendar event reports what actually happened, which by default is nothing."""

    def test_without_a_mock_it_refuses_with_the_disabled_reason_and_creates_nothing(self):
        self.add_application("j1", days=3)
        before = self.fingerprint()

        existing = self.folder_entries()

        code, out, err = self.run_cli("--record-follow-up", "j1")

        self.assertEqual(code, 2)
        self.assertIn("[disabled]", out)
        self.assertIn("Nothing was sent and nothing was created", out)
        self.assertIn("no calendar event was recorded (disabled)", err)
        self.assertEqual(self.fingerprint(), before)
        self.assertEqual(self.folder_entries(), existing)

    def test_an_all_day_event_is_recorded_by_the_mock_on_the_recorded_day(self):
        self.add_application("j1", days=3)
        ledger = self.folder / "ledger.json"

        code, out, err = self.run_cli("--record-follow-up", "j1", "--mock-ledger", str(ledger))

        self.assertEqual(code, 0, err)
        self.assertIn("2026", out)
        self.assertIn("(all day)", out)
        self.assertIn("Not recorded, and not invented:", out)
        self.assertIn("[completed]", out)
        self.assertIn("No calendar account was contacted", out)
        recorded = json.loads(ledger.read_text(encoding="utf-8"))["operations"]
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["kind"], "calendar")
        self.assertEqual(recorded[0]["target"], (self.today + timedelta(days=3)).isoformat())

    def test_a_repeat_of_the_same_event_records_one_operation(self):
        self.add_application("j1", days=3)
        ledger = self.folder / "ledger.json"
        arguments = ("--record-follow-up", "j1", "--mock-ledger", str(ledger))

        first = self.run_cli(*arguments)
        second = self.run_cli(*arguments)

        self.assertEqual((first[0], second[0]), (0, 0))
        self.assertIn("[duplicate]", second[1])
        self.assertEqual(len(json.loads(ledger.read_text(encoding="utf-8"))["operations"]), 1)

    def test_a_time_from_an_invitation_is_recorded_with_its_zone(self):
        self.add_application("j1", days=3)
        ledger = self.folder / "ledger.json"

        code, out, err = self.run_cli(
            "--record-follow-up", "j1", "--at", "10:30", "--minutes", "45", "--timezone", "Asia/Kolkata",
            "--mock-ledger", str(ledger))

        self.assertEqual(code, 0, err)
        self.assertIn("10:30 Asia/Kolkata for 45 minute(s)", out)
        self.assertNotIn("Not recorded, and not invented:", out)

    def test_a_time_without_a_zone_is_refused(self):
        self.add_application("j1", days=3)

        code, _out, err = self.run_cli("--record-follow-up", "j1", "--at", "10:30", "--minutes", "45")

        self.assertEqual(code, 2)
        self.assertIn("--timezone", err)
        self.assertIn("Nothing was created", err)

    def test_a_zone_without_a_time_is_refused(self):
        self.add_application("j1", days=3)

        code, _out, err = self.run_cli("--record-follow-up", "j1", "--timezone", "Asia/Kolkata")

        self.assertEqual(code, 2)
        self.assertIn("need --at", err)

    def test_a_time_that_is_not_a_time_is_refused(self):
        self.add_application("j1", days=3)

        code, _out, err = self.run_cli("--record-follow-up", "j1", "--at", "half past ten",
                                       "--minutes", "45", "--timezone", "Asia/Kolkata")

        self.assertEqual(code, 2)
        self.assertIn("is not a time of day", err)

    def test_an_unknown_timezone_is_refused(self):
        self.add_application("j1", days=3)

        code, _out, err = self.run_cli("--record-follow-up", "j1", "--at", "10:30", "--minutes", "45",
                                       "--timezone", "Mars/Olympus")

        self.assertEqual(code, 2)
        self.assertIn("Mars/Olympus", err)

    def test_minutes_that_is_not_a_number_is_refused(self):
        self.add_application("j1", days=3)

        code, _out, err = self.run_cli("--record-follow-up", "j1", "--at", "10:30", "--minutes", "ages",
                                       "--timezone", "Asia/Kolkata")

        self.assertEqual(code, 2)
        self.assertIn("whole number", err)

    def test_no_database_means_a_refusal(self):
        code, out, _err = self.run_cli("--record-follow-up", "j1")

        self.assertEqual(code, 2)
        self.assertIn("No database yet", out)


class OrphanOptionTests(IntegrationCommandTestCase):
    """An option given without its command is refused rather than silently ignored."""

    def test_options_are_refused_without_the_command_they_belong_to(self):
        for option, value, expected in (
            ("--recipient", "a@b.example", "--draft-follow-up"),
            ("--save-draft", "draft.txt", "--draft-follow-up"),
            ("--at", "10:30", "--record-follow-up"),
            ("--minutes", "30", "--record-follow-up"),
            ("--timezone", "Asia/Kolkata", "--record-follow-up"),
            ("--mock-ledger", "ledger.json", "--draft-follow-up or --record-follow-up"),
        ):
            with self.subTest(option=option):
                code, _out, err = self.run_cli(option, value)
                self.assertEqual(code, 2)
                self.assertIn(f"{option} only means something with {expected}", err)
                self.assertIn("Nothing was written.", err)

    def test_an_orphan_option_does_not_create_a_database_or_a_file(self):
        code, _out, _err = self.run_cli("--recipient", "a@b.example")

        self.assertEqual(code, 2)
        self.assertIsNone(self.fingerprint())
        self.assertEqual(self.folder_entries(), set())


class NoSideEffectTests(IntegrationCommandTestCase):
    """The read-only commands leave the records and the file system exactly as they found them."""

    def test_the_preview_and_the_draft_change_no_record_and_no_status(self):
        self.add_application("j1", days=2)
        before = self.fingerprint()
        before_tracker = self.stored_tracker()

        existing = self.folder_entries()

        self.run_cli("--preview-calendar-export")
        self.run_cli("--draft-follow-up", "j1")
        self.run_cli("--integration-status")

        after_tracker = self.stored_tracker()
        self.assertEqual(self.fingerprint(), before)
        self.assertIs(after_tracker.status, before_tracker.status)
        self.assertEqual(after_tracker.status, ApplicationStatus.DISCOVERED)
        self.assertEqual(after_tracker.follow_up_on, before_tracker.follow_up_on)
        self.assertEqual(self.folder_entries(), existing)
        self.assertEqual([item for item in self.folder.iterdir() if item.suffix == ".ics"], [])

    def test_the_mock_operation_changes_no_record_either(self):
        self.add_application("j1", days=2)
        before = self.fingerprint()
        before_tracker = self.stored_tracker()

        self.run_cli("--draft-follow-up", "j1", "--recipient", "hiring@sandbox.example",
                     "--mock-ledger", str(self.folder / "ledger.json"))
        self.run_cli("--record-follow-up", "j1", "--mock-ledger", str(self.folder / "ledger.json"))
        recorded = self.folder / "ledger.json"

        self.assertEqual(self.fingerprint(), before)
        after_tracker = self.stored_tracker()
        self.assertEqual(after_tracker.status, before_tracker.status)
        self.assertEqual(after_tracker.follow_up_on, before_tracker.follow_up_on)
        self.assertTrue(recorded.exists(), "the named ledger is the only new file this may create")
        self.assertEqual(len(json.loads(recorded.read_text(encoding="utf-8"))["operations"]), 2)


class TimezoneDatabaseTests(IntegrationCommandTestCase):
    """The date bounds and the timezone check are the ones the request itself enforces."""

    def test_a_follow_up_day_keeps_the_local_day_the_reminder_was_recorded_with(self):
        self.add_application("j1", days=0)

        code, out, err = self.run_cli("--preview-calendar-export")

        self.assertEqual(code, 0, err)
        self.assertIn(f"  {self.today.isoformat()}: Follow up: Data Engineer at Sandbox Systems", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
