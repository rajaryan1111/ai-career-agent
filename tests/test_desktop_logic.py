"""Tests for the Tk-free desktop logic (form mapping, save planning, path resolution).

These tests need no graphical display, so they run in headless CI. They verify the
pure functions only; they do not verify widget rendering.
"""
import tempfile
import unittest
from pathlib import Path

from career_agent import Availability, CandidateProfile, JobListing
from career_agent.desktop_logic import (
    DATABASE_FILE_NAME, HIGH_CONSEQUENCE_FIELDS, JobSaveMode, build_candidate_profile,
    build_job_listing, career_agent_data_root, default_database_path, form_values,
    job_form_values, plan_job_save, profile_form_values,
)


def job_form(**overrides):
    values = {
        "employer": "Example Inc", "title": "AI Intern", "source_name": "Manual entry",
        "source_url": "https://jobs.example/role/1", "apply_url": "",
        "requisition": "", "availability": "open", "scope": "restricted",
        "work_mode": "remote", "role_type": "internship", "location": "Bengaluru",
        "countries": "India", "degrees": "ECE, Computer Science",
        "study_statuses": "undergraduate", "graduation_years": "2027, 2028",
        "allowed_work_authorizations": "authorized_without_sponsorship",
        "min_exp": "0", "max_exp": "2", "required_skills": "Python, RAG",
        "provenance_note": "Official listing checked today.",
    }
    values.update(overrides)
    return values


def sample_job(**overrides):
    values = dict(
        listing_id="j1", source_id="manual", source_name="Manual entry",
        source_listing_url="https://jobs.example/role/1", employer_name="Example Inc",
        role_title="AI Intern", availability_status=Availability.OPEN,
        employer_apply_url="https://employer.example/apply/1",
        canonical_requisition_id="REQ-1", location_text="Bengaluru", work_mode="remote",
        role_type="internship", eligibility_scope="restricted", eligible_countries=("India",),
        allowed_degree_disciplines=("ECE",), allowed_study_statuses=("undergraduate",),
        allowed_graduation_years=(2027,), allowed_work_authorizations=("authorized_without_sponsorship",),
        minimum_experience_years=0.0, maximum_experience_years=2.0,
        required_skills=frozenset({"RAG", "Python"}), provenance_note="Official listing checked today.",
    )
    values.update(overrides)
    return JobListing(**values)


class FormMappingTests(unittest.TestCase):
    def test_form_values_reads_objects_exposing_get(self):
        class Variable:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        self.assertEqual(form_values({"a": Variable("x"), "b": Variable("y")}), {"a": "x", "b": "y"})

    def test_build_job_listing_requires_employer_title_and_source_url(self):
        for overrides in ({"employer": "  "}, {"title": ""}, {"source_url": ""}):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, "required"):
                    build_job_listing(job_form(**overrides), listing_id="new-id")

    def test_build_job_listing_requires_http_urls(self):
        with self.assertRaisesRegex(ValueError, "Source listing URL must start with"):
            build_job_listing(job_form(source_url="jobs.example/1"), listing_id="new-id")
        with self.assertRaisesRegex(ValueError, "Employer apply URL must start with"):
            build_job_listing(job_form(apply_url="employer.example/apply"), listing_id="new-id")

    def test_graduation_year_uses_shared_validation_message(self):
        for value in ("2027.0", "cohort 2027", "twenty twenty seven"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Graduation year must be a whole number") as caught:
                    build_job_listing(job_form(graduation_years=value), listing_id="new-id")
                self.assertNotIn("invalid literal", str(caught.exception))

    def test_experience_range_and_sign_are_validated(self):
        with self.assertRaisesRegex(ValueError, "Minimum experience cannot exceed maximum experience"):
            build_job_listing(job_form(min_exp="5", max_exp="1"), listing_id="new-id")
        with self.assertRaisesRegex(ValueError, "Minimum experience cannot be negative"):
            build_job_listing(job_form(min_exp="-1"), listing_id="new-id")
        with self.assertRaisesRegex(ValueError, "Maximum experience must be a number"):
            build_job_listing(job_form(max_exp="lots"), listing_id="new-id")

    def test_availability_must_be_a_known_status(self):
        with self.assertRaisesRegex(ValueError, "Availability must be one of"):
            build_job_listing(job_form(availability="probably open"), listing_id="new-id")

    def test_blank_availability_and_scope_default_to_unknown(self):
        job = build_job_listing(job_form(availability="", scope=""), listing_id="new-id")
        self.assertEqual(job.availability_status, Availability.UNKNOWN)
        self.assertEqual(job.eligibility_scope, "unknown")

    def test_job_form_round_trip_is_lossless(self):
        original = sample_job()
        rebuilt = build_job_listing(job_form_values(original), listing_id=original.listing_id)
        self.assertEqual(rebuilt, original)

    def test_profile_round_trip_is_lossless(self):
        original = CandidateProfile(
            candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
            graduation_year=2027, experience_years=0.5,
            work_authorization="authorized_without_sponsorship",
            skills=frozenset({"Python", "RAG"}), preferred_locations=frozenset({"Bengaluru"}),
            preferred_work_modes=frozenset({"remote"}), preferred_role_types=frozenset({"internship"}),
        )
        self.assertEqual(build_candidate_profile(profile_form_values(original)), original)

    def test_profile_validation_messages_are_the_shared_ones(self):
        with self.assertRaisesRegex(ValueError, "Graduation year must be a whole number"):
            build_candidate_profile({"graduation_year": "final year"})
        with self.assertRaisesRegex(ValueError, "Experience must be a number"):
            build_candidate_profile({"experience": "four years"})


class JobSavePlanTests(unittest.TestCase):
    def test_new_mode_always_uses_a_fresh_listing_id(self):
        job, plan = plan_job_save(
            job_form(), mode=JobSaveMode.NEW, new_listing_id="fresh-id", selected_job_id="selected-id"
        )
        self.assertEqual(job.listing_id, "fresh-id")
        self.assertFalse(plan.is_edit)
        self.assertFalse(plan.needs_update_confirmation)

    def test_edit_mode_preserves_listing_identity(self):
        job, plan = plan_job_save(
            job_form(), mode=JobSaveMode.EDIT, new_listing_id="fresh-id", selected_job_id="selected-id"
        )
        self.assertEqual(job.listing_id, "selected-id")
        self.assertTrue(plan.is_edit)

    def test_edit_mode_requires_a_selected_listing(self):
        with self.assertRaisesRegex(ValueError, "Select a saved listing before editing"):
            plan_job_save(job_form(), mode=JobSaveMode.EDIT, new_listing_id="fresh-id", selected_job_id=None)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown job save mode"):
            plan_job_save(job_form(), mode="overwrite", new_listing_id="fresh-id")

    def test_edit_reports_only_eligibility_relevant_changes(self):
        baseline = job_form_values(sample_job())
        _, plan = plan_job_save(
            job_form(**{**baseline, "countries": "United States", "source_name": "Other source"}),
            mode=JobSaveMode.EDIT, new_listing_id="fresh-id", selected_job_id="j1", baseline=baseline,
        )
        self.assertEqual(plan.changed_consequential_fields, ("countries",))
        self.assertTrue(plan.needs_update_confirmation)
        self.assertIn("allowed countries", plan.update_confirmation_message())
        self.assertNotIn("source_name", plan.changed_consequential_fields)

    def test_edit_that_keeps_high_consequence_fields_unchanged_needs_no_confirmation(self):
        baseline = job_form_values(sample_job())
        _, plan = plan_job_save(
            job_form(**{**baseline, "source_name": "Manual entry (rechecked)", "required_skills": "Python"}),
            mode=JobSaveMode.EDIT, new_listing_id="fresh-id", selected_job_id="j1", baseline=baseline,
        )
        self.assertEqual(plan.changed_consequential_fields, ())
        self.assertFalse(plan.needs_update_confirmation)

    def test_availability_evidence_is_treated_as_high_consequence(self):
        baseline = job_form_values(sample_job())
        _, plan = plan_job_save(
            job_form(**{**baseline, "provenance_note": "Rechecked on a later date."}),
            mode=JobSaveMode.EDIT, new_listing_id="fresh-id", selected_job_id="j1", baseline=baseline,
        )
        self.assertEqual(plan.changed_consequential_fields, ("provenance_note",))
        self.assertTrue(plan.needs_update_confirmation)

    def test_high_consequence_fields_all_exist_in_the_form(self):
        form_keys = set(job_form_values(sample_job()))
        self.assertTrue(set(HIGH_CONSEQUENCE_FIELDS) <= form_keys)


class DatabasePathTests(unittest.TestCase):
    def test_data_root_per_operating_system(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.assertEqual(
                career_agent_data_root(system="Darwin", environ={}, home=home),
                home / "Library" / "Application Support",
            )
            self.assertEqual(
                career_agent_data_root(system="Windows", environ={}, home=home),
                home / "AppData" / "Local",
            )
            self.assertEqual(
                career_agent_data_root(system="Linux", environ={}, home=home),
                home / ".local" / "share",
            )

    def test_environment_overrides_are_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            local_app_data = Path(directory) / "localappdata"
            xdg = Path(directory) / "xdg"
            self.assertEqual(
                career_agent_data_root(system="Windows", environ={"LOCALAPPDATA": str(local_app_data)}, home=home),
                local_app_data,
            )
            self.assertEqual(
                career_agent_data_root(system="Linux", environ={"XDG_DATA_HOME": str(xdg)}, home=home),
                xdg,
            )

    def test_default_database_path_is_outside_the_repository_and_creates_its_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            expected_folder_name = {"Darwin": "AI Career Agent", "Windows": "AI Career Agent", "Linux": "ai-career-agent"}
            for system in ("Darwin", "Windows", "Linux"):
                with self.subTest(system=system):
                    path = default_database_path(system=system, environ={}, home=home)
                    self.assertEqual(path.name, DATABASE_FILE_NAME)
                    self.assertEqual(path.parent.name, expected_folder_name[system])
                    self.assertTrue(path.parent.is_dir())
                    self.assertTrue(str(path).startswith(str(home)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
