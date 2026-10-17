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
    FactSource,
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
        # The candidate's own history travels as top-level arrays: it belongs to the person, not to a job.
        self.assertIn("work_history", document)
        self.assertIn("education", document)

    def test_a_version_one_file_still_imports_its_listings_and_profile(self):
        """The promise of a wire format: a file written before this feature is not stranded.

        Version 1 has no history arrays at all. It must read, and it must not invent records the file never
        contained - an import that fabricates employment history is worse than one that refuses the file.
        """
        _, document = self.export_file()
        del document["work_history"], document["education"]
        document["format_version"] = 1
        older = self.folder / "version-1.json"
        older.write_text(json.dumps(document), encoding="utf-8")

        with self.target_store() as store:
            parsed = importer.read_export(older)
            plan = importer.plan_import(store, parsed, source=older.name)
            outcome = importer.apply_import(store, parsed, source=older.name)

            self.assertEqual(plan.new_work_history, ())
            self.assertEqual(plan.new_education, ())
            self.assertEqual(store.list_work_history(), ())
            self.assertEqual(store.list_education(), ())
            self.assertEqual(store.get_profile().candidate_country, "India")
            self.assertIsNotNone(store.get_job("j1"))

        self.assertIn("imported the profile", outcome.describe())

    def test_an_unknown_format_version_is_refused_with_the_number_it_holds(self):
        _, document = self.export_file()
        document["format_version"] = 99
        ahead = self.folder / "from-the-future.json"
        ahead.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(importer.ImportRefused) as caught:
            importer.read_export(ahead)

        message = str(caught.exception)
        self.assertIn("99", message)
        self.assertIn("2", message, "the refusal names the versions this build does read")

    def test_the_history_round_trips_with_every_field_intact(self):
        with self.source_store() as store:
            store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1), is_current=True,
                                   employment_type="full_time", summary="built the pipeline")
            store.add_work_history("Old Co", "Analyst", date(2020, 1, 6), end_date=date(2023, 3, 31))
            store.add_education("IIT Delhi", "B.Tech", discipline="ECE", start_date=date(2015, 8, 1),
                                completion_date=date(2019, 5, 31))
            store.add_education("Coursera", "Specialisation", is_ongoing=True)
            path = self.folder / "history.json"
            importer.write_export(store, path)
            document = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual([record["job_title"] for record in document["work_history"]],
                             ["Data Engineer", "Analyst"], "the export keeps the CV order")
            self.assertEqual(document["work_history"][0]["is_current"], True)
            self.assertIsNone(document["work_history"][0]["end_date"])
            self.assertEqual(document["education"][0]["is_ongoing"], True)

            with self.target_store() as target:
                importer.apply_import(target, document, source=path.name)
                roles = target.list_work_history()
                study = target.list_education()

        self.assertEqual([(role.employer, role.job_title, role.start_date, role.end_date, role.is_current)
                          for role in roles],
                         [("Sandbox Systems", "Data Engineer", date(2023, 4, 1), None, True),
                          ("Old Co", "Analyst", date(2020, 1, 6), date(2023, 3, 31), False)])
        self.assertEqual(roles[0].employment_type.value, "full_time")
        self.assertEqual(roles[0].summary, "built the pipeline")
        self.assertEqual([(entry.institution, entry.qualification, entry.discipline, entry.is_ongoing)
                          for entry in study],
                         [("Coursera", "Specialisation", None, True),
                          ("IIT Delhi", "B.Tech", "ECE", False)])
        self.assertEqual(study[1].completion_date, date(2019, 5, 31))

    def test_an_unrecognised_employment_type_in_a_file_becomes_unknown_rather_than_refusing_the_record(self):
        """The person's employer and dates are still true even when the label is not one this build knows."""
        _, document = self.export_file()
        document["work_history"] = [{
            "employer": "Sandbox Systems", "job_title": "Data Engineer", "employment_type": "gig-economy",
            "start_date": "2024-01-01", "end_date": None, "is_current": True, "summary": None,
        }]

        with self.target_store() as store:
            outcome = importer.apply_import(store, document, source="export.json")
            stored = store.list_work_history()

        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].employment_type.value, "unknown")
        self.assertEqual(stored[0].job_title, "Data Engineer")
        self.assertIn("added 1 employment record", outcome.describe())

    def test_a_record_with_an_impossible_period_is_rejected_and_the_rest_still_imports(self):
        """One bad record must not take a person's whole file with it, and the good ones must land."""
        _, document = self.export_file()
        document["work_history"] = [
            {"employer": "Sandbox Systems", "job_title": "Data Engineer", "employment_type": "full_time",
             "start_date": "2024-01-01", "end_date": None, "is_current": True, "summary": None},
            {"employer": "Bad Co", "job_title": "Analyst", "employment_type": "full_time",
             "start_date": "2020-01-01", "end_date": "2019-01-01", "is_current": False, "summary": None},
        ]

        with self.target_store() as store:
            plan = importer.plan_import(store, document, source="export.json")
            self.assertEqual(len(plan.new_work_history), 1)
            self.assertEqual(len(plan.rejected), 1)
            outcome = importer.apply_import(store, document, source="export.json")
            stored = store.list_work_history()

        self.assertEqual([role.employer for role in stored], ["Sandbox Systems"])
        self.assertIn("Bad Co", outcome.describe() + str(plan.describe()))

    def test_a_record_the_store_refuses_at_write_time_is_reported_rather_than_crashing_the_import(self):
        """The plan and the write must agree about what is valid; when they cannot, say so."""
        _, document = self.export_file()
        document["education"] = [
            {"institution": "IIT Delhi", "qualification": "B.Tech", "discipline": "ECE",
             "start_date": "2015-08-01", "completion_date": "2019-05-31", "is_ongoing": False},
            {"institution": "IIT Delhi", "qualification": "B.Tech", "discipline": "ECE",
             "start_date": "2015-08-01", "completion_date": "2019-05-31", "is_ongoing": False},
        ]

        with self.target_store() as store:
            outcome = importer.apply_import(store, document, source="export.json")
            stored = store.list_education()

        self.assertEqual(len(stored), 1, "the duplicate is written once")
        text = outcome.describe()
        self.assertIn("added 1 education record(s)", text)
        self.assertIn("skipped 1 unusable record(s)", text,
                      "the record the write refused is counted among the skipped, not hidden")

    def test_a_file_full_of_bad_records_imports_no_history_at_all_and_says_so(self):
        _, document = self.export_file()
        document["work_history"] = [
            {"employer": "", "job_title": "Analyst", "start_date": "2020-01-01", "is_current": False},
            {"employer": "X", "job_title": "Y", "start_date": "not a date", "is_current": False},
        ]

        with self.target_store() as store:
            outcome = importer.apply_import(store, document, source="export.json")

            self.assertEqual(store.list_work_history(), (), "no partial writes from a rejected batch")

        text = outcome.describe()
        self.assertIn("skipped 2 unusable record(s)", text)
        self.assertNotIn("employment record", text, "nothing was added, so nothing is claimed")

    def test_an_import_never_mixes_a_files_history_into_records_that_are_already_here(self):
        """All or nothing: two half-CVs in one list would be a record of nobody."""
        _, document = self.export_file()
        document["work_history"] = [
            {"employer": "From The File", "job_title": "Engineer", "employment_type": "full_time",
             "start_date": "2019-01-01", "end_date": "2021-01-01", "is_current": False, "summary": None},
        ]

        with self.target_store() as store:
            store.add_work_history("Already Here", "Analyst", date(2024, 1, 1), is_current=True)
            plan = importer.plan_import(store, document, source="export.json")
            outcome = importer.apply_import(store, document, source="export.json")
            stored = store.list_work_history()

        self.assertEqual([role.employer for role in stored], ["Already Here"],
                         "the stored record wins and the file's copy is not added beside it")
        self.assertTrue(plan.kept_local_history)
        self.assertEqual(plan.kept_history_counts, (1, 0))
        text = " ".join(plan.describe())
        self.assertIn("delete those records first", text)
        self.assertIn("kept", outcome.describe() + text)

    def test_the_import_reports_how_many_records_it_would_add_before_adding_them(self):
        _, document = self.export_file()
        document["work_history"] = [
            {"employer": "Sandbox Systems", "job_title": "Data Engineer", "employment_type": "full_time",
             "start_date": "2024-01-01", "end_date": None, "is_current": True, "summary": None},
        ]
        document["education"] = [
            {"institution": "IIT Delhi", "qualification": "B.Tech", "discipline": None,
             "start_date": None, "completion_date": None, "is_ongoing": True},
        ]

        with self.target_store() as store:
            plan = importer.plan_import(store, document, source="export.json")
            text = " ".join(plan.describe())

            self.assertEqual(store.list_work_history(), (), "planning writes nothing")
            self.assertEqual(plan.adds_anything, True)

        self.assertIn("Employment history: 1 record(s) would be added (Data Engineer at Sandbox Systems)",
                      text)
        self.assertIn("Education: 1 record(s) would be added (B.Tech at IIT Delhi)", text)
        self.assertIn("Nothing has been written yet", text)

    def test_an_import_whose_history_records_are_identical_to_the_stored_ones_adds_nothing_twice(self):
        with self.source_store() as store:
            store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1), is_current=True)
            path = self.folder / "history.json"
            importer.write_export(store, path)
            document = json.loads(path.read_text(encoding="utf-8"))

            with self.target_store() as target:
                importer.apply_import(target, document, source=path.name)
                second = importer.plan_import(target, document, source=path.name)
                importer.apply_import(target, document, source=path.name)
                roles = target.list_work_history()

        self.assertEqual(len(roles), 1, "importing the same file twice does not duplicate a role")
        self.assertFalse(second.adds_anything)

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

    def test_a_partial_profile_without_country_or_skills_round_trips_and_stays_unconfirmed(self):
        partial = CandidateProfile(degree_discipline="ECE")
        with self.source_store() as source:
            source.save_profile(partial)
            document = importer.export_document(source)

        self.assertEqual(document["format_version"], 2)
        self.assertIsNone(document["profile"]["candidate_country"])
        self.assertEqual(document["profile"]["skills"], [])

        with self.target_store() as target:
            plan = importer.plan_import(target, document, source="partial.json")
            outcome = importer.apply_import(target, document, source="partial.json",
                                            document_name="partial.json")

            self.assertEqual(plan.new_profiles, (partial,))
            self.assertTrue(outcome.added_profile)
            self.assertEqual(target.get_profile(), partial)
            self.assertEqual(importer.export_document(target)["profile"], document["profile"])
            origins = target.get_profile_fact_provenance()

        self.assertEqual([entry.fact for entry in origins], ["degree"])
        self.assertTrue(all(entry.source is FactSource.IMPORTED_FROM_FILE for entry in origins))
        self.assertTrue(all(not entry.is_confirmed for entry in origins))

    def test_an_invalid_profile_shape_is_still_rejected(self):
        _, document = self.export_file()
        document["profile"] = ["not a stored profile"]

        with self.target_store() as store:
            plan = importer.plan_import(store, document, source="invalid.json")

            self.assertEqual(plan.new_profiles, ())
            self.assertEqual(plan.rejected[0].identifier, "the profile in the file")
            self.assertIn("list", plan.rejected[0].reason)
            self.assertIsNone(store.get_profile(), "a refused profile must not be written")

    def test_the_export_carries_no_trace_of_where_a_fact_came_from(self):
        """Version 2 is a promise to files already on somebody's disk: the format does not change here.

        Provenance is this application's bookkeeping about a fact, not part of the fact, and it lives in
        its own table - so a profile that has origins recorded exports exactly like one that does not.
        """
        plain = CandidateProfile(candidate_country="India", skills=frozenset({"Python", "SQL"}))
        with self.source_store() as store:
            store.save_profile(plain)
            _, without_origins = self.export_file(profile=False)
            document = importer.export_document(store)
            store.save_profile(plain, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                               document_name="CV final.docx")
            _, with_origins = self.export_file(profile=False)
            after = importer.export_document(store)

        self.assertEqual(after["format_version"], 2)
        self.assertEqual(sorted(after["profile"]), sorted(without_origins["profile"]),
                         "recording an origin adds no field to the exported profile")
        self.assertEqual(sorted(after), sorted(document))
        blob = json.dumps(after)
        # ``provenance_note`` is a listing's own long-standing field, so the check is for the provenance
        # vocabulary this build added, not for the word.
        for leaked in ("profile_fact_provenance", "extracted_from_document", "user_confirmed",
                       "document_name", "CV final.docx"):
            with self.subTest(leaked=leaked):
                self.assertNotIn(leaked, blob)
        self.assertEqual(after["profile"], with_origins["profile"])

    def test_an_imported_profile_is_recorded_as_imported_and_unverified(self):
        """A file another machine wrote is evidence of where facts came from, not that they are right."""
        path, document = self.export_file()
        with self.target_store() as store:
            importer.apply_import(store, document, source=str(path), document_name=path.name)

            origins = {entry.fact: entry for entry in store.get_profile_fact_provenance()}

        self.assertEqual(list(origins), ["country", "experience", "work_authorization", "skills"],
                         "one entry per fact the imported profile states, in the profile's own order")
        self.assertTrue(all(entry.source is FactSource.IMPORTED_FROM_FILE
                            for entry in origins.values()))
        self.assertTrue(all(not entry.is_confirmed for entry in origins.values()),
                        "importing a file confirms nothing")
        self.assertTrue(all(entry.document_name == path.name for entry in origins.values()),
                        "the file is remembered by name")

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

    def test_a_file_record_that_reuses_a_stored_identifier_is_refused_rather_than_written_over(self):
        # Two exports can name different listings with the same identifier: identity for linking is
        # ``duplicate_key`` (the URL here), while the row is keyed by ``listing_id`` and ``save_job`` is an
        # upsert. So a record that matched no stored identity but reused a stored identifier used to
        # overwrite the stored listing - facts and all - while the report said "Nothing was replaced".
        with self.source_store() as store:
            store.save_job(job("j1", url="https://jobs.example.invalid/from-the-file",
                               employer="From The File", role="Data Engineer"))
            source = self.folder / "file.json"
            importer.write_export(store, source)
        document = json.loads(source.read_text(encoding="utf-8"))
        with self.target_store() as store:
            store.save_job(job("j1", url="https://jobs.example.invalid/mine", employer="My Own Employer"))
            before = store.get_job("j1")

            plan = importer.plan_import(store, document, source=str(source))
            outcome = importer.apply_import(store, document, source=str(source))
            after = store.get_job("j1")

        self.assertEqual(plan.new_jobs, (), "a stored identifier must not be planned as a new listing")
        self.assertEqual(outcome.added_jobs, 0)
        self.assertEqual(after, before, "the stored listing was replaced by the file's copy")
        self.assertEqual(after.employer_name, "My Own Employer")
        self.assertEqual(after.source_listing_url, "https://jobs.example.invalid/mine")
        self.assertTrue(
            any("j1" == rejection.identifier and "identifier" in rejection.reason
                for rejection in plan.rejected),
            plan.rejected,
        )

    def test_two_records_in_one_file_with_the_same_identifier_do_not_overwrite_each_other(self):
        # The same clash inside a single file: both records have a different identity, so both were
        # planned - and the second overwrote the first, while the count said two listings were added.
        with self.source_store() as store:
            store.save_job(job("j1", url="https://jobs.example.invalid/first", employer="First Employer"))
            source = self.folder / "file.json"
            importer.write_export(store, source)
        document = json.loads(source.read_text(encoding="utf-8"))
        second = dict(document["jobs"][0])
        second["source_listing_url"] = "https://jobs.example.invalid/second"
        second["employer_name"] = "Second Employer"
        document["jobs"] = [document["jobs"][0], second]

        with self.target_store() as store:
            outcome = importer.apply_import(store, document, source=str(source))
            stored = store.list_jobs()

        self.assertEqual([item.listing_id for item in stored], ["j1"])
        self.assertEqual(stored[0].employer_name, "First Employer",
                         "the first record in the file is the one that is stored")
        self.assertEqual(outcome.added_jobs, 1,
                         "the report must count the listings that are really there, not the records read")

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
