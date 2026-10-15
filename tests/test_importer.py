"""Tests for the export/import module: what the format is, what an import refuses, what it will not do.

The two properties that matter most here are the ones a recovery tool is judged by: an import must never
overwrite something the person already has in a way they did not choose, and a file this app did not
write must be refused *before* anything is read into the database. Everything else - the plan, the counts,
the linked-listing report - exists so the person can see which of those two happened.

Every database in this module is a disposable temporary file, and every record in it is invented.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from career_agent import importer
from career_agent.core import (
    ActivityKind, ApplicationActivity, ApplicationStatus, ApplicationTracker, Availability,
    CandidateProfile, JobListing,
)
from career_agent.store import CareerStore

STAMP = date(2026, 10, 15)


def job(listing_id: str = "j1", *, url: str | None = None, employer: str = "Sandbox Systems",
        role: str = "Data Engineer") -> JobListing:
    """An invented listing on a reserved example host, so nothing here can point at a real posting."""
    return JobListing(listing_id, "fixture", "Fixture",
                      url or f"https://jobs.example.invalid/{listing_id}", employer, role,
                      availability_status=Availability.OPEN,
                      required_skills=frozenset({"Python", "SQL"}), location_text="Pune, India",
                      work_mode="hybrid")


class ImportTestCase(unittest.TestCase):
    """A source database (exported from) and a target database (imported into), both disposable."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.source_path = self.folder / "source.sqlite3"
        self.target_path = self.folder / "target.sqlite3"

    def source_store(self) -> CareerStore:
        store = CareerStore(self.source_path)
        self.addCleanup(store.close)
        return store

    def target_store(self) -> CareerStore:
        store = CareerStore(self.target_path)
        self.addCleanup(store.close)
        return store

    def export_file(self, *, profile: bool = True, days: int | None = 5, status: ApplicationStatus | None = None,
                    activity: bool = True, name: str = "export.json") -> tuple[Path, dict]:
        """Write an export from an invented source database and return the path and the document."""
        with self.source_store() as store:
            if profile:
                store.save_profile(CandidateProfile(candidate_country="India", experience_years=3.0,
                                                    work_authorization="citizen",
                                                    skills=frozenset({"Python", "SQL"})))
            store.save_job(job())
            store.save_tracker(ApplicationTracker("j1"))
            if status is not None:
                store.save_tracker(ApplicationTracker("j1").transition(status))
                store.save_tracker(store.get_tracker("j1").with_follow_up(
                    date.fromordinal(STAMP.toordinal() + (days or 0)), note="ask about the panel"))
            elif days is not None:
                store.save_tracker(ApplicationTracker("j1", follow_up_on=date.fromordinal(
                    STAMP.toordinal() + days), follow_up_note="ask about the panel"))
            if activity:
                store.add_activity("j1", ApplicationActivity(ActivityKind.NOTE, date(2026, 10, 14),
                                                             "Recruiter called"))
            target = self.folder / name
            importer.write_export(store, target)
        return target, json.loads(target.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ the format
    def test_the_export_carries_the_profile_the_listing_the_record_and_the_history(self):
        _, document = self.export_file()

        self.assertEqual(document["format_version"], importer.EXPORT_FORMAT_VERSION)
        self.assertEqual(document["profile"]["candidate_country"], "India")
        self.assertEqual(len(document["jobs"]), 1)
        record = document["jobs"][0]
        self.assertEqual(record["listing_id"], "j1")
        self.assertEqual(record["required_skills"], ["Python", "SQL"])
        self.assertEqual(record["application_tracker"]["status"], "discovered")
        self.assertEqual(len(record["activity"]), 1)
        self.assertIn("privacy_note", document)

    def test_the_exported_file_is_owner_only(self):
        path, _ = self.export_file()

        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_an_export_of_an_empty_database_is_still_a_valid_document(self):
        with self.target_store() as store:
            document = importer.export_document(store)

        self.assertEqual(document["jobs"], [])
        self.assertIsNone(document["profile"])

    # ------------------------------------------------------------------ refusals, before anything is read
    def test_a_missing_file_is_refused_with_the_path(self):
        with self.assertRaises(importer.ImportRefused) as caught:
            importer.read_export(self.folder / "nothing-here.json")

        self.assertIn("does not exist", str(caught.exception))

    def test_a_folder_is_refused(self):
        with self.assertRaises(importer.ImportRefused):
            importer.read_export(self.folder)

    def test_something_that_is_not_json_is_refused_with_the_position(self):
        target = self.folder / "notes.txt"
        target.write_text("this is not JSON at all", encoding="utf-8")

        with self.assertRaises(importer.ImportRefused) as caught:
            importer.read_export(target)

        self.assertIn("not valid JSON", str(caught.exception))
        self.assertIn("line 1", str(caught.exception))

    def test_a_json_document_that_is_not_an_export_is_refused(self):
        target = self.folder / "other.json"
        target.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

        with self.assertRaises(importer.ImportRefused) as caught:
            importer.read_export(target)

        self.assertIn("format_version", str(caught.exception))

    def test_a_newer_format_version_is_refused_with_both_numbers(self):
        target = self.folder / "future.json"
        target.write_text(json.dumps({"format_version": importer.EXPORT_FORMAT_VERSION + 1, "jobs": []}),
                          encoding="utf-8")

        with self.assertRaises(importer.ImportRefused) as caught:
            importer.read_export(target)

        self.assertIn(str(importer.EXPORT_FORMAT_VERSION + 1), str(caught.exception))
        self.assertIn(str(importer.EXPORT_FORMAT_VERSION), str(caught.exception))

    def test_a_refused_file_leaves_the_target_database_untouched(self):
        target = self.folder / "bad.json"
        target.write_text("[]", encoding="utf-8")
        with self.target_store() as store:
            before = len(store.list_jobs())

            with self.assertRaises(importer.ImportRefused):
                document = importer.read_export(target)
                importer.apply_import(store, document, source=str(target))

            self.assertEqual(len(store.list_jobs()), before)

    # ------------------------------------------------------------------ the plan
    def test_the_plan_says_what_would_be_added_without_adding_it(self):
        path, document = self.export_file()
        with self.target_store() as store:
            plan = importer.plan_import(store, document, source=str(path))

            self.assertTrue(plan.adds_anything)
            self.assertEqual([item.listing_id for item in plan.new_jobs], ["j1"])
            self.assertEqual(len(plan.new_profiles), 1)
            self.assertEqual(store.list_jobs(), (), "planning must write nothing")

    def test_a_stored_profile_is_kept_and_the_plan_says_why(self):
        path, document = self.export_file()
        with self.target_store() as store:
            store.save_profile(CandidateProfile(candidate_country="Canada",
                                                skills=frozenset({"Go"})))

            plan = importer.plan_import(store, document, source=str(path))

            self.assertTrue(plan.kept_local_profile)
            self.assertEqual(plan.new_profiles, ())
            self.assertIn("your stored profile is kept", "\n".join(plan.describe()))
            importer.apply_import(store, document, source=str(path))
            self.assertEqual(store.get_profile().candidate_country, "Canada",
                             "the person's own facts were not replaced by the file's")

    def test_a_listing_already_stored_is_linked_and_its_row_is_left_alone(self):
        path, document = self.export_file()
        with self.target_store() as store:
            store.save_job(job(employer="My own edit"))
            before = store.get_record_times("j1")

            plan = importer.plan_import(store, document, source=str(path))
            outcome = importer.apply_import(store, document, source=str(path))

            self.assertEqual(plan.new_jobs, ())
            self.assertEqual(plan.linked_jobs, ("j1",))
            self.assertEqual(plan.linked_as, (("j1", "j1"),))
            self.assertEqual(outcome.added_jobs, 0)
            self.assertEqual(store.get_job("j1").employer_name, "My own edit")
            self.assertEqual(store.get_record_times("j1"), before,
                             "first_seen_at must not move because a file mentioned the listing")

    def test_a_status_later_than_the_first_is_reported_rather_than_asserted(self):
        path, document = self.export_file(status=ApplicationStatus.SHORTLISTED)
        with self.target_store() as store:
            plan = importer.plan_import(store, document, source=str(path))

            self.assertEqual(plan.trackers_at_initial_status, ("j1",),
                             "the application itself is created; only the status is refused")
            self.assertEqual(plan.trackers_without_status,
                             (("j1", ApplicationStatus.SHORTLISTED.value),))
            text = "\n".join(plan.describe())
            self.assertIn("which is NOT imported", text)
            self.assertIn("shortlisted", text)

            importer.apply_import(store, document, source=str(path))

            tracker = store.get_tracker("j1")
            assert tracker is not None
            self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED,
                             "a record this app never advanced starts at the initial status")
            self.assertEqual(tracker.follow_up_on, date.fromordinal(STAMP.toordinal() + 5),
                             "the plan and the history still come across")

    def test_a_confirmed_record_in_a_file_cannot_arrive_as_confirmed(self):
        """The evidence floor is not relaxed for imports: this path must not create a confirmation."""
        with self.source_store() as source:
            source.save_job(job())
            # A real path to a confirmation, walked through the state machine the app enforces:
            # shortlist, mark it prepared, claim the attempt (unverified), then confirm with evidence.
            tracker = ApplicationTracker("j1")
            source.save_tracker(tracker)  # a new record must exist at the initial status first
            for step in (ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED,
                         ApplicationStatus.AWAITING_USER, ApplicationStatus.SUBMISSION_ATTEMPTED,
                         ApplicationStatus.SUBMITTED_UNVERIFIED):
                tracker = tracker.transition(step)
                source.save_tracker(tracker)
            confirmed = tracker.transition(ApplicationStatus.CONFIRMED,
                                           evidence="Employer portal shows Application Received",
                                           candidate_confirmed=True)
            source.save_tracker(confirmed)
            path = self.folder / "confirmed.json"
            importer.write_export(source, path)
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["jobs"][0]["application_tracker"]["status"], "confirmed")
        self.assertTrue(document["jobs"][0]["application_tracker"]["candidate_confirmed"])

        with self.target_store() as store:
            importer.apply_import(store, document, source=str(path))

            tracker = store.get_tracker("j1")
            assert tracker is not None
            self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED)
            self.assertFalse(tracker.candidate_confirmed,
                             "an import may not create a confirmation the local app never observed")

    def test_the_same_application_twice_in_one_file_is_reported_not_duplicated(self):
        path, document = self.export_file()
        duplicate = dict(document["jobs"][0])
        duplicate["listing_id"] = "j1-copy"
        document["jobs"].append(duplicate)
        with self.target_store() as store:
            plan = importer.plan_import(store, document, source=str(path))
            outcome = importer.apply_import(store, document, source=str(path))

            self.assertEqual(len(plan.new_jobs), 1)
            self.assertEqual(len(plan.rejected), 1)
            self.assertIn("the same application", plan.rejected[0].reason)
            self.assertEqual(outcome.added_jobs, 1)

    def test_a_record_missing_a_required_field_is_reported_with_the_field(self):
        path, document = self.export_file()
        document["jobs"][0]["role_title"] = ""
        with self.target_store() as store:
            plan = importer.plan_import(store, document, source=str(path))

            self.assertEqual(plan.new_jobs, ())
            self.assertIn("role_title", plan.rejected[0].reason)

    def test_a_record_that_is_not_an_object_is_reported_by_index(self):
        path, document = self.export_file()
        document["jobs"].append("not a record")
        with self.target_store() as store:
            plan = importer.plan_import(store, document, source=str(path))

            self.assertEqual(plan.rejected[0].identifier, "record 1")

    def test_a_follow_up_day_that_is_not_a_day_is_reported_and_not_imported(self):
        path, document = self.export_file()
        document["jobs"][0]["application_tracker"]["follow_up_on"] = "next tuesday"
        with self.target_store() as store:
            plan = importer.plan_import(store, document, source=str(path))
            importer.apply_import(store, document, source=str(path))

            self.assertEqual(plan.follow_ups, ())
            self.assertIn("not a YYYY-MM-DD date", plan.rejected[0].reason)
            tracker = store.get_tracker("j1")
            assert tracker is not None
            self.assertIsNone(tracker.follow_up_on)

    def test_an_history_entry_this_build_cannot_read_is_skipped_and_counted(self):
        path, document = self.export_file()
        document["jobs"][0]["activity"].append({"kind": "invented_kind", "occurred_on": "2026-10-14",
                                                "detail": "?"})
        with self.target_store() as store:
            plan = importer.plan_import(store, document, source=str(path))
            outcome = importer.apply_import(store, document, source=str(path))

            self.assertEqual(outcome.activity_added, 1, "the readable entry still arrives")
            self.assertEqual(len(store.list_activity("j1")), 1)
            self.assertIn("cannot be read", plan.rejected[0].reason)

    # ------------------------------------------------------------------ applying
    def test_an_applied_import_reproduces_what_the_file_held(self):
        path, document = self.export_file()
        with self.target_store() as store:
            outcome = importer.apply_import(store, document, source=str(path))

            self.assertEqual(outcome.added_jobs, 1)
            self.assertTrue(outcome.added_profile)
            self.assertEqual(outcome.follow_ups_imported, 1)
            self.assertEqual(outcome.activity_added, 1)
            listing = store.get_job("j1")
            assert listing is not None
            self.assertEqual(listing.role_title, "Data Engineer")
            self.assertEqual(listing.required_skills, frozenset({"Python", "SQL"}))
            self.assertEqual(listing.source_listing_url, "https://jobs.example.invalid/j1")
            tracker = store.get_tracker("j1")
            assert tracker is not None
            self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED)
            self.assertEqual(tracker.follow_up_note, "ask about the panel")
            entries = store.list_activity("j1")
            self.assertEqual([(entry.kind, entry.detail) for entry in entries],
                             [(ActivityKind.NOTE, "Recruiter called")])

    def test_importing_the_same_file_twice_adds_nothing_the_second_time(self):
        path, document = self.export_file()
        with self.target_store() as store:
            first = importer.apply_import(store, document, source=str(path))
            second = importer.apply_import(store, document, source=str(path))

            self.assertEqual(first.added_jobs, 1)
            self.assertEqual(second.added_jobs, 0)
            self.assertEqual(second.activity_added, 0, "history is not appended twice")
            self.assertEqual(len(store.list_jobs()), 1)
            self.assertEqual(len(store.list_activity("j1")), 1)

    def test_an_activity_entry_is_matched_on_the_day_the_kind_and_the_text(self):
        """The recorded-at instant differs between machines; the claim does not."""
        path, document = self.export_file()
        with self.target_store() as store:
            store.save_job(job())
            store.save_tracker(ApplicationTracker("j1"))
            store.add_activity("j1", ApplicationActivity(ActivityKind.NOTE, date(2026, 10, 14),
                                                        "Recruiter called"))
            outcome = importer.apply_import(store, document, source=str(path))

            self.assertEqual(outcome.activity_added, 0)
            self.assertEqual(len(store.list_activity("j1")), 1)

    def test_an_import_round_trip_through_the_desktop_format_is_a_fixed_point(self):
        """Export, import into an empty database, export again: the two documents agree."""
        path, first = self.export_file()
        with self.target_store() as store:
            importer.apply_import(store, first, source=str(path))
            second = importer.export_document(store)

        self.assertEqual(first["profile"], second["profile"])
        self.assertEqual(len(first["jobs"]), len(second["jobs"]))
        for before, after in zip(first["jobs"], second["jobs"]):
            for key in ("listing_id", "employer_name", "role_title", "required_skills",
                        "source_listing_url", "location_text", "work_mode"):
                self.assertEqual(before[key], after[key], key)
            # The entries are compared on what the person claimed - the day, the kind and the text -
            # because ``recorded_at`` is when *this* database wrote the row, and the second document was
            # written after the import. Comparing it would be comparing two clocks, not two records.
            self.assertEqual(
                [(entry["kind"], entry["occurred_on"], entry["detail"]) for entry in before["activity"]],
                [(entry["kind"], entry["occurred_on"], entry["detail"]) for entry in after["activity"]])


if __name__ == "__main__":
    unittest.main()
