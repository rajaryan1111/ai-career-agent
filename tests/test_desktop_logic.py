"""Tests for the Tk-free desktop logic (form mapping, save planning, path resolution).

These tests need no graphical display, so they run in headless CI. They verify the
pure functions only; they do not verify widget rendering.
"""
import tempfile
import unittest
from pathlib import Path

from career_agent import Availability, CandidateProfile, JobListing
from career_agent.desktop_logic import (
    DATABASE_FILE_NAME,
    HIGH_CONSEQUENCE_FIELDS,
    TIMESTAMP_NOT_RECORDED,
    JobSaveMode,
    build_candidate_profile,
    build_job_listing,
    career_agent_data_root,
    default_database_path,
    form_values,
    format_stored_timestamp,
    job_form_values,
    plan_job_save,
    profile_fields_not_matching,
    profile_form_values,
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

    def test_build_job_listing_refuses_credentialed_or_non_public_urls(self):
        for overrides, label in (
            ({"source_url": "https://user:pass@jobs.example/1"}, "Source listing URL"),
            ({"source_url": "http://localhost/1"}, "Source listing URL"),
            ({"source_url": "http://169.254.169.254/latest/meta-data/"}, "Source listing URL"),
            ({"source_url": "http://2130706433/"}, "Source listing URL"),
            ({"apply_url": "http://192.168.1.5/apply"}, "Employer apply URL"),
            ({"apply_url": "https://jobs.example:not-a-port/apply"}, "Employer apply URL"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, f"{label} must be a public web address"):
                    build_job_listing(job_form(**overrides), listing_id="new-id")

    def test_build_job_listing_still_accepts_a_plain_public_url(self):
        listing = build_job_listing(job_form(), listing_id="new-id")
        self.assertEqual(listing.source_listing_url, "https://jobs.example/role/1")

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

    def test_an_experience_range_that_is_not_a_real_number_is_refused(self):
        """A form is an entry point into an eligibility gate, so it refuses what cannot be compared.

        ``nan`` reached the listing before this was refused, and ``nan`` is false against every bound,
        so the range check fell through to "within the stated range" and passed a requirement nobody
        had satisfied.
        """
        for value in ("nan", "inf", "Infinity", "1e400"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "real, finite number"):
                    build_job_listing(job_form(min_exp=value), listing_id="new-id")
                with self.assertRaisesRegex(ValueError, "real, finite number"):
                    build_job_listing(job_form(min_exp="0", max_exp=value), listing_id="new-id")

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

    def test_a_profile_experience_value_that_is_not_a_real_number_is_refused(self):
        for value in ("nan", "NaN", "inf", "-inf", "1e400"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "real, finite number"):
                    build_candidate_profile({"experience": value})


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

    def test_a_relative_environment_override_is_ignored(self):
        # The XDG Base Directory Specification requires these variables to be absolute and says a
        # relative one "should" be considered invalid and ignored. Resolving it against the current
        # working directory would move the person's database - and so their profile - between
        # launches, so the documented per-user default is used instead.
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            self.assertEqual(
                career_agent_data_root(system="Linux", environ={"XDG_DATA_HOME": "relative/data"}, home=home),
                home / ".local" / "share",
            )
            self.assertEqual(
                career_agent_data_root(system="Windows", environ={"LOCALAPPDATA": "relative\\appdata"}, home=home),
                home / "AppData" / "Local",
            )
            self.assertEqual(
                career_agent_data_root(system="Linux", environ={"XDG_DATA_HOME": ""}, home=home),
                home / ".local" / "share",
            )

    def test_a_relative_override_never_reaches_the_database_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            path = default_database_path(system="Linux", environ={"XDG_DATA_HOME": "relative/data"}, home=home)

            self.assertEqual(path, home / ".local" / "share" / "ai-career-agent" / DATABASE_FILE_NAME)
            self.assertNotIn("relative", str(path))

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


class StoredTimestampFormattingTests(unittest.TestCase):
    """A stored instant is rendered exactly, or labelled honestly. It is never invented.

    The application writes UTC with an explicit offset. Values that arrive without an offset, or in a
    form this version cannot read, may come from another tool or another platform, so they are shown
    as they are stored with a plain label instead of being guessed at or silently dropped.
    """

    def test_a_missing_value_is_reported_as_not_recorded(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                self.assertEqual(format_stored_timestamp(value), TIMESTAMP_NOT_RECORDED)

    def test_a_missing_value_can_use_a_context_specific_fallback(self):
        self.assertEqual(format_stored_timestamp(None, fallback="no record yet"), "no record yet")

    def test_a_utc_instant_is_rendered_with_its_offset_made_explicit(self):
        self.assertEqual(format_stored_timestamp("2026-10-14T14:32:09+00:00"), "2026-10-14 14:32:09 UTC")

    def test_another_offset_is_converted_to_utc_rather_than_dropped(self):
        self.assertEqual(format_stored_timestamp("2026-10-14T20:02:09+05:30"), "2026-10-14 14:32:09 UTC")

    def test_a_zulu_suffix_is_accepted_on_every_supported_python(self):
        self.assertEqual(format_stored_timestamp("2026-10-14T14:32:09Z"), "2026-10-14 14:32:09 UTC")

    def test_a_naive_instant_is_shown_as_stored_with_a_timezone_label(self):
        self.assertEqual(
            format_stored_timestamp("2026-10-14T14:32:09"),
            "2026-10-14T14:32:09 (no timezone recorded)",
        )

    def test_an_unreadable_value_is_shown_as_stored_with_a_label(self):
        for value in ("yesterday", "2026-13-45T99:99:99+00:00", "nan"):
            with self.subTest(value=value):
                self.assertEqual(
                    format_stored_timestamp(value), f"{value} (unrecognised timestamp format)"
                )

    def test_surrounding_whitespace_never_changes_a_parsed_instant(self):
        self.assertEqual(format_stored_timestamp("  2026-10-14T14:32:09+00:00  "), "2026-10-14 14:32:09 UTC")

    def test_nothing_rendered_mentions_a_source_or_an_employer(self):
        # The helper describes local observation times only; wording that could be read as a source
        # publication or update date must never come from here.
        rendered = format_stored_timestamp("2026-10-14T14:32:09+00:00")
        for word in ("posted", "published", "updated by", "source", "employer"):
            self.assertNotIn(word, rendered.lower())


class ProfileReadBackComparisonTests(unittest.TestCase):
    """A save may only be reported as saved after the stored profile is compared with what was asked for.

    The comparison is semantic, because a form renders a multi-value field sorted and an integer field
    as text; a textual comparison would report a failure for a value that was stored correctly, and a
    false failure is as unhelpful as a false success.
    """

    def test_a_profile_holding_every_expected_value_matches(self):
        profile = CandidateProfile(
            candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
            graduation_year=2028, experience_years=0.5, work_authorization="authorized_without_sponsorship",
            skills=frozenset({"Python", "RAG"}), preferred_locations=frozenset({"Bengaluru"}),
            preferred_work_modes=frozenset({"remote"}), preferred_role_types=frozenset({"internship"}),
        )
        expected = {
            "country": "India", "degree": "ECE", "study_status": "undergraduate",
            "graduation_year": "2028", "experience": "0.5",
            "work_authorization": "authorized_without_sponsorship", "skills": "Python, RAG",
            "locations": "Bengaluru", "work_modes": "remote", "role_types": "internship",
        }

        self.assertEqual(profile_fields_not_matching(profile, expected), ())

    def test_a_text_field_is_compared_without_regard_to_case_or_spacing(self):
        profile = CandidateProfile(candidate_country="India")

        self.assertEqual(profile_fields_not_matching(profile, {"country": "  india "}), ())
        self.assertEqual(profile_fields_not_matching(profile, {"country": "Canada"}), ("country",))
        self.assertEqual(profile_fields_not_matching(profile, {"country": ""}), ("country",))

    def test_a_multi_value_field_is_compared_as_a_set(self):
        profile = CandidateProfile(skills=frozenset({"Python", "RAG"}))

        self.assertEqual(profile_fields_not_matching(profile, {"skills": "RAG, python"}), ())
        self.assertEqual(profile_fields_not_matching(profile, {"skills": "Python"}), ("skills",))

    def test_a_number_is_compared_as_a_number_not_as_text(self):
        profile = CandidateProfile(graduation_year=2028, experience_years=0.5)

        self.assertEqual(
            profile_fields_not_matching(profile, {"graduation_year": "2028", "experience": "0.50"}), ()
        )
        self.assertEqual(profile_fields_not_matching(profile, {"graduation_year": "2027"}), ("graduation_year",))
        self.assertEqual(profile_fields_not_matching(profile, {"experience": "1.5"}), ("experience",))

    def test_a_value_the_profile_does_not_hold_is_reported(self):
        profile = CandidateProfile()

        self.assertEqual(profile_fields_not_matching(profile, {"graduation_year": "2028"}), ("graduation_year",))
        self.assertEqual(profile_fields_not_matching(profile, {"experience": "lots"}), ("experience",))

    def test_one_mismatch_does_not_hide_the_others(self):
        profile = CandidateProfile(candidate_country="India", degree_discipline="ECE")

        self.assertEqual(
            profile_fields_not_matching(profile, {"country": "Canada", "degree": "ECE", "skills": "Python"}),
            ("country", "skills"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
