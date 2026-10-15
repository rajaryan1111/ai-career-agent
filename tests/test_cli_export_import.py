"""Tests for ``--export-to`` and ``--import-from``: the round trip a person can run without a window.

What is tested here is the command-line contract rather than the module underneath it (that has its own
tests): that a dry run really is a dry run, that applying is what writes, that a second import adds
nothing, that neither command replaces a file or a record the person already has, and that the exit
status never says "fine" when something was refused.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

import career_agent.__main__ as cli
from career_agent.core import (
    ActivityKind, ApplicationActivity, ApplicationStatus, ApplicationTracker, Availability,
    CandidateProfile, JobListing,
)
from career_agent.store import CareerStore


class ExportImportCommandTests(unittest.TestCase):
    """Two disposable databases in a temporary folder; every record in them is invented."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.source = self.folder / "source.sqlite3"
        self.target = self.folder / "target.sqlite3"
        self.export = self.folder / "export.json"

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(arguments))
        return code, out.getvalue(), err.getvalue()

    def populate(self, database: Path, *, listing_id: str = "j1", status: ApplicationStatus | None = None,
                 days: int = 4) -> None:
        """A source database holding one invented application, ready to be exported."""
        with CareerStore(database) as store:
            store.save_profile(CandidateProfile(candidate_country="India", experience_years=2.5,
                                                skills=frozenset({"Python", "SQL"})))
            store.save_job(JobListing(listing_id, "fixture", "Fixture",
                                      f"https://jobs.example.invalid/{listing_id}", "Sandbox Systems",
                                      "Data Engineer", availability_status=Availability.OPEN,
                                      required_skills=frozenset({"Python"})))
            tracker = ApplicationTracker(listing_id)
            store.save_tracker(tracker)
            if status is not None:
                tracker = tracker.transition(status)
                store.save_tracker(tracker)
            store.save_tracker(tracker.with_follow_up(
                date.fromordinal(date.today().toordinal() + days), note="nudge the recruiter"))
            store.add_activity(listing_id, ApplicationActivity(ActivityKind.NOTE, date(2026, 10, 14),
                                                              "Recruiter called"))

    # ------------------------------------------------------------------ export
    def test_the_export_writes_a_readable_document_and_says_what_it_holds(self):
        self.populate(self.source)

        code, out, err = self.run_cli("--export-to", str(self.export), "--database", str(self.source))

        self.assertEqual(code, 0, err)
        self.assertIn("Wrote 1 listing(s)", out)
        self.assertIn("nothing was sent anywhere", out)
        document = json.loads(self.export.read_text(encoding="utf-8"))
        self.assertEqual(document["format_version"], 1)
        if os.name == "posix":
            self.assertEqual(self.export.stat().st_mode & 0o777, 0o600)

    def test_the_export_refuses_to_replace_an_existing_file(self):
        self.populate(self.source)
        self.export.write_text("the person's own file", encoding="utf-8")

        code, out, err = self.run_cli("--export-to", str(self.export), "--database", str(self.source))

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("already exists", err)
        self.assertEqual(self.export.read_text(encoding="utf-8"), "the person's own file")

    def test_there_is_nothing_to_export_without_a_database(self):
        code, out, err = self.run_cli("--export-to", str(self.export), "--database", str(self.source))

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("nothing to export", out)
        self.assertFalse(self.export.exists())

    # ------------------------------------------------------------------ import
    def test_a_dry_run_says_what_would_happen_and_writes_nothing(self):
        self.populate(self.source)
        self.run_cli("--export-to", str(self.export), "--database", str(self.source))
        with CareerStore(self.target):
            pass  # the target must exist; the command says so when it does not

        code, out, err = self.run_cli("--import-from", str(self.export), "--database", str(self.target))

        self.assertEqual(code, 0, err)
        self.assertIn("would be added", out)
        self.assertIn("Nothing was written. Run the same command with --yes", out)
        with CareerStore(self.target) as store:
            self.assertEqual(store.list_jobs(), ())
            self.assertIsNone(store.get_profile())

    def test_applying_the_same_file_twice_adds_nothing_the_second_time(self):
        self.populate(self.source)
        self.run_cli("--export-to", str(self.export), "--database", str(self.source))
        with CareerStore(self.target):
            pass

        first = self.run_cli("--import-from", str(self.export), "--yes", "--database", str(self.target))
        second = self.run_cli("--import-from", str(self.export), "--yes", "--database", str(self.target))

        self.assertEqual(first[0], 0, first[2])
        self.assertIn("added 1 listing(s)", first[1])
        self.assertEqual(second[0], 0, second[2])
        self.assertIn("left 1 already-stored listing(s) as they were", second[1])
        with CareerStore(self.target) as store:
            self.assertEqual(len(store.list_jobs()), 1)
            self.assertEqual(len(store.list_activity("j1")), 1)

    def test_the_import_carries_the_facts_the_follow_up_day_and_the_history(self):
        self.populate(self.source)
        self.run_cli("--export-to", str(self.export), "--database", str(self.source))
        with CareerStore(self.target):
            pass

        self.run_cli("--import-from", str(self.export), "--yes", "--database", str(self.target))

        with CareerStore(self.target) as store:
            listing = store.get_job("j1")
            assert listing is not None
            self.assertEqual(listing.required_skills, frozenset({"Python"}))
            tracker = store.get_tracker("j1")
            assert tracker is not None
            self.assertEqual(tracker.follow_up_on, date.fromordinal(date.today().toordinal() + 4))
            self.assertEqual(tracker.follow_up_note, "nudge the recruiter")
            self.assertEqual([entry.detail for entry in store.list_activity("j1")], ["Recruiter called"])
            self.assertEqual(store.get_profile().candidate_country, "India")

    def test_a_file_from_another_program_is_refused_with_a_non_zero_status(self):
        target = self.folder / "some-other-file.json"
        target.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
        with CareerStore(self.target):
            pass

        code, out, err = self.run_cli("--import-from", str(target), "--database", str(self.target))

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("format_version", err)

    def test_a_missing_export_file_is_refused(self):
        with CareerStore(self.target):
            pass

        code, out, err = self.run_cli("--import-from", str(self.folder / "nope.json"),
                                      "--database", str(self.target))

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("does not exist", err)

    def test_importing_into_a_missing_database_says_what_to_do_instead_of_creating_one(self):
        self.populate(self.source)
        self.run_cli("--export-to", str(self.export), "--database", str(self.source))

        code, out, err = self.run_cli("--import-from", str(self.export), "--database", str(self.target))

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("run the app or the commands once first", out)
        self.assertFalse(self.target.exists(), "an import must not silently create a database")

    def test_a_status_the_record_never_passed_through_is_reported_and_not_asserted(self):
        self.populate(self.source, status=ApplicationStatus.SHORTLISTED)
        self.run_cli("--export-to", str(self.export), "--database", str(self.source))
        with CareerStore(self.target):
            pass

        code, out, err = self.run_cli("--import-from", str(self.export), "--yes", "--database", str(self.target))

        self.assertEqual(code, 0, err)
        self.assertIn("which is NOT imported", out)
        with CareerStore(self.target) as store:
            tracker = store.get_tracker("j1")
            assert tracker is not None
            self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED)

    def test_the_commands_are_exclusive_with_the_other_actions(self):
        quiet = io.StringIO()
        for combination in (("--export-to", "a.json", "--worker-status"),
                            ("--import-from", "a.json", "--doctor")):
            with self.subTest(combination=combination):
                with contextlib.redirect_stderr(quiet), self.assertRaises(SystemExit) as caught:
                    cli.parse_arguments(list(combination))

                self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
