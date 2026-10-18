"""Tests for the Tk-free desktop logic (form mapping, save planning, path resolution).

These tests need no graphical display, so they run in headless CI. They verify the
pure functions only; they do not verify widget rendering.
"""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from career_agent import Availability, CandidateProfile, JobListing
from career_agent.core import ActivityKind
from types import SimpleNamespace

from career_agent import sources
from career_agent.acceptance_evidence import ROUTE_REQUIREMENTS, EvidenceKind
from career_agent.suppression import SuppressionReason
from career_agent import desktop_logic as logic
from career_agent.desktop_logic import (
    ACTIVITY_KIND_CHOICES, DATABASE_FILE_NAME, HIGH_CONSEQUENCE_FIELDS, TIMESTAMP_NOT_RECORDED,
    JobSaveMode, activity_form_values, build_activity,
    build_candidate_profile, build_job_listing, career_agent_data_root, default_database_path,
    format_stored_timestamp, form_values, job_form_values, plan_job_save, profile_fields_not_matching,
    profile_form_values,
)


class ActivityFormTests(unittest.TestCase):
    """Turning the dialog's strings into an entry, without guessing at anything the person typed."""

    def test_the_defaults_are_a_neutral_kind_and_today(self):
        values = activity_form_values(today=date(2026, 10, 15))

        self.assertEqual(values["kind"], "note", "a neutral default cannot be saved as a claim by accident")
        self.assertEqual(values["occurred_on"], "2026-10-15")
        self.assertEqual(values["detail"], "")

    def test_the_offered_kinds_are_the_domain_kinds_in_order(self):
        self.assertEqual(ACTIVITY_KIND_CHOICES, ("applied", "response", "interview", "assessment",
                                                 "follow-up", "note"))

    def test_a_complete_form_becomes_an_entry_with_the_detail_trimmed(self):
        entry = build_activity({"kind": "applied", "occurred_on": "2026-10-12",
                                "detail": "  Sent through the employer portal.  "})

        self.assertIs(entry.kind, ActivityKind.APPLIED)
        self.assertEqual(entry.occurred_on, date(2026, 10, 12))
        self.assertEqual(entry.detail, "Sent through the employer portal.")

    def test_only_the_documented_date_shape_is_accepted(self):
        """``date.fromisoformat`` also reads basic and ISO-week forms; this field promises one shape."""
        for raw in ("20261012", "2026-W41-1", "12/10/2026", "2026-2-30", "2026-13-01"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError) as caught:
                    build_activity({"kind": "note", "occurred_on": raw, "detail": "x"})
                self.assertIn("YYYY-MM-DD", str(caught.exception))

    def test_an_impossible_calendar_date_is_named_as_such(self):
        with self.assertRaises(ValueError) as caught:
            build_activity({"kind": "note", "occurred_on": "2026-02-30", "detail": "x"})

        self.assertIn("not a real calendar date", str(caught.exception))

    def test_a_missing_date_is_refused_rather_than_defaulted(self):
        with self.assertRaises(ValueError) as caught:
            build_activity({"kind": "note", "occurred_on": "  ", "detail": "x"})

        self.assertIn("Give the entry a date", str(caught.exception))

    def test_an_unknown_kind_lists_what_may_be_chosen(self):
        with self.assertRaises(ValueError) as caught:
            build_activity({"kind": "sent", "occurred_on": "2026-10-12", "detail": "x"})

        message = str(caught.exception)
        for choice in ACTIVITY_KIND_CHOICES:
            self.assertIn(choice, message)

    def test_a_blank_detail_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            build_activity({"kind": "note", "occurred_on": "2026-10-12", "detail": "   "})

        self.assertIn("Write what happened", str(caught.exception))


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


class TailoredDocumentTextTests(unittest.TestCase):
    """The sentences the Tailored documents tab puts in front of a person."""

    def test_a_document_built_from_named_files_cites_them(self):
        self.assertEqual(logic.artifact_citation_text(("resume-v1.docx", "resume-v2.docx")),
                         "resume-v1.docx, resume-v2.docx")

    def test_a_document_that_cites_nothing_says_so_rather_than_guessing(self):
        self.assertEqual(logic.artifact_citation_text(()), logic.ARTIFACT_NO_DOCUMENT)
        self.assertEqual(logic.artifact_citation_text(("",)), logic.ARTIFACT_NO_DOCUMENT)
        self.assertNotIn("unknown", logic.ARTIFACT_NO_DOCUMENT.lower())

    def test_the_state_of_a_stale_document_names_every_reason(self):
        text = logic.artifact_state_text(False, ("facts changed since this was built: experience",
                                                 "work history changed since this was built"))
        self.assertTrue(text.startswith("Rebuild before use"))
        self.assertIn("experience", text)
        self.assertIn("work history", text)

    def test_a_current_document_reads_as_current(self):
        self.assertEqual(logic.artifact_state_text(True, ("every source fact is unchanged",)),
                         "Current")

    def test_the_summary_counts_what_cannot_be_used_as_it_is(self):
        self.assertIn("No tailored document is stored yet", logic.artifact_summary_text(0, 0))
        self.assertIn("1 tailored document", logic.artifact_summary_text(1, 0))
        self.assertIn("every one still matches", logic.artifact_summary_text(2, 0))
        self.assertIn("1 needs rebuilding", logic.artifact_summary_text(3, 1))
        self.assertIn("2 need rebuilding", logic.artifact_summary_text(3, 2))

    def test_a_rebuild_names_both_documents_and_the_gaps_it_refused_to_invent(self):
        text = logic.artifact_rebuild_text("new123", "old456", ("Docker", "Kubernetes"))
        self.assertIn("new123", text)
        self.assertIn("old456", text)
        self.assertIn("kept as history", text)
        self.assertIn("Docker, Kubernetes", text)
        self.assertIn("does not claim them", text)

    def test_a_rebuild_with_no_gaps_claims_nothing_about_gaps(self):
        text = logic.artifact_rebuild_text("new123", "old456", ())
        self.assertNotIn("do not state", text)


class PolicyTextTests(unittest.TestCase):
    """The sentences the Permissions & limits tab puts in front of a person before they agree."""

    def policy(self, **overrides):
        from career_agent.policy import ActionKind, GlobalPolicy

        content = {
            "allowed": frozenset({("jobicy", ActionKind.DISCOVERY)}),
            "daily_limits": {ActionKind.DISCOVERY: 3},
        }
        content.update(overrides)
        return GlobalPolicy(**content)

    def test_nothing_authorised_says_so_and_says_what_else_is_off(self):
        from career_agent.policy import no_authorisation

        text = logic.policy_summary_text(no_authorisation(), 0)
        self.assertIn("Nothing is authorised", text)
        self.assertIn("every source is also switched off", text)

    def test_a_live_authorisation_names_its_version_and_keeps_the_caveat(self):
        text = logic.policy_summary_text(self.policy(), 2)
        self.assertIn("version 2", text)
        self.assertIn("1 permission", text)
        self.assertIn("still switched off", text,
                      "a summary that omits this implies permission is enough to make things run")

    def test_quiet_hours_are_stated_in_hours_a_person_reads(self):
        text = logic.policy_summary_text(self.policy(quiet_hours=(22, 7)), 3)
        self.assertIn("between 22:00 and 07:00", text)

    def test_a_stopped_or_withdrawn_authorisation_says_nothing_is_permitted(self):
        self.assertIn("everything is stopped",
                      logic.policy_summary_text(self.policy(stop_all=True), 4))
        withdrawn = logic.policy_summary_text(
            self.policy(revoked_at="2026-10-20T10:00:00+00:00"), 5)
        self.assertIn("withdrawn", withdrawn)
        self.assertIn("what was withdrawn", withdrawn)

    def test_a_row_shows_the_source_the_action_and_the_ceiling(self):
        rows = logic.policy_rows(self.policy())
        self.assertEqual(rows, (("jobicy", "look for jobs", "3 per day", "Permitted by you"),))

    def test_a_permission_without_a_ceiling_reads_as_refused_not_unlimited(self):
        rows = logic.policy_rows(self.policy(daily_limits={}))
        self.assertIn("none recorded", rows[0][2])
        self.assertIn("Refused", rows[0][3])

    def test_a_stopped_or_withdrawn_row_says_which_it_is(self):
        self.assertEqual(logic.policy_rows(self.policy(stop_all=True))[0][3], "Stopped")
        self.assertEqual(
            logic.policy_rows(self.policy(revoked_at="2026-10-20T10:00:00+00:00"))[0][3],
            "Withdrawn")

    def test_rows_are_ordered_so_the_same_authorisation_always_reads_the_same(self):
        from career_agent.policy import ActionKind

        policy = self.policy(
            allowed=frozenset({("b-source", ActionKind.DISCOVERY),
                               ("a-source", ActionKind.EMAIL_SEND),
                               ("a-source", ActionKind.DISCOVERY)}),
            daily_limits={ActionKind.DISCOVERY: 2, ActionKind.EMAIL_SEND: 1})
        self.assertEqual([row[0] for row in logic.policy_rows(policy)],
                         ["a-source", "a-source", "b-source"])

    def test_the_questions_state_what_is_written_and_what_is_kept(self):
        from career_agent.policy import ActionKind

        grant = logic.policy_grant_question("jobicy", ActionKind.EMAIL_SEND, 2)
        self.assertIn("at most 2 time(s) a day", grant)
        self.assertIn("withdrawn at any time", grant)
        removal = logic.policy_removal_question("jobicy", ActionKind.DISCOVERY)
        self.assertIn("kept", removal)
        withdrawal = logic.policy_revocation_question(2)
        self.assertIn("2 permissions", withdrawal)
        self.assertIn("Nothing is deleted", withdrawal)
        self.assertIn("1 permission", logic.policy_revocation_question(1))

    def test_the_stop_question_reads_differently_in_each_direction(self):
        self.assertIn("Stop everything now?", logic.policy_stop_question(True))
        self.assertIn("Allow actions again?", logic.policy_stop_question(False))
        self.assertIn("does not make anything run", logic.policy_stop_question(False))

    def test_a_refusal_is_reported_with_the_gate_that_also_refused(self):
        from career_agent.policy import ActionKind, evaluate_policy, no_authorisation
        from datetime import datetime, timezone

        decision = evaluate_policy(no_authorisation(), source_id="jobicy",
                                   action=ActionKind.DISCOVERY,
                                   now=datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
                                   done_today=0, source_gate_allows=False)
        text = logic.policy_decision_text(decision, gate_reason="the quality gate has not been passed")
        self.assertIn("Refused", text)
        self.assertIn("quality gate", text)


class WhatsHappeningTextTests(unittest.TestCase):
    """The words the "What's happening" tab puts on screen, with no Tk anywhere near them."""

    def test_the_summary_is_the_report_s_own_headline_and_never_counts_again(self):
        quiet = logic.report_summary_text("Nothing from the last day needs you.", 0)
        self.assertEqual(quiet, "Nothing from the last day needs you.")
        busy = logic.report_summary_text("2 things from the last 7 days need you.", 2)
        self.assertTrue(busy.startswith("2 things from the last 7 days need you."))
        self.assertIn("listed below", busy)
        self.assertEqual(busy.count("need you"), 1,
                         "the window stated the same count twice, in its own words and the report's")

    def test_an_unknown_outcome_is_never_called_a_failure(self):
        self.assertEqual(logic.ATTEMPT_STATE_LABELS["unknown"], "outcome not established")
        self.assertEqual(logic.ATTEMPT_STATE_LABELS["failed"], "did not happen")
        self.assertNotEqual(logic.ATTEMPT_STATE_LABELS["unknown"],
                            logic.ATTEMPT_STATE_LABELS["failed"])

    def test_rows_carry_the_operation_id_a_person_would_search_a_provider_with(self):
        record = SimpleNamespace(operation_id="op-1", action="email_send", identity_key="job:1",
                                 started_at="2026-10-20T09:00:00+00:00",
                                 state=SimpleNamespace(value="unknown"))
        row = logic.attempt_rows([record])[0]
        self.assertEqual(row[0], "op-1")
        self.assertEqual(row[2], "job:1")
        self.assertEqual(row[4], "outcome not established")

    def test_the_detail_says_what_it_blocks_and_that_time_will_not_settle_it(self):
        empty = logic.attempt_detail_text(None)
        self.assertIn("time cannot settle", empty)
        record = SimpleNamespace(operation_id="op-1", action="email_send", identity_key="job:1",
                                 started_at="2026-10-20T09:00:00+00:00", detail="no reply",
                                 state=SimpleNamespace(value="unknown"))
        described = logic.attempt_detail_text(record)
        self.assertIn("no reply", described)
        self.assertIn("blocks any further attempt", described)

    def test_settling_without_evidence_is_refused_with_a_reason(self):
        self.assertIsNotNone(logic.reconciliation_refusal(""))
        self.assertIsNotNone(logic.reconciliation_refusal("  no "))
        self.assertIsNone(logic.reconciliation_refusal("checked the provider's log"))

    def test_the_question_quotes_the_evidence_and_says_it_lifts_the_block(self):
        asked = logic.reconciliation_question("op-1", "It did happen", " the log shows it ")
        self.assertIn("op-1", asked)
        self.assertIn("the log shows it", asked)
        self.assertIn("lifted", asked)

    def test_every_offered_outcome_is_one_the_store_can_record(self):
        from career_agent.attempts import AttemptState

        for value, label in logic.RECONCILIATION_CHOICES:
            with self.subTest(value=value):
                self.assertIsInstance(AttemptState(value), AttemptState)
                self.assertTrue(label.strip())
        self.assertNotIn("unknown", [value for value, _ in logic.RECONCILIATION_CHOICES],
                         "recording 'still unknown' would settle nothing and clear nothing")

    def test_the_notification_summary_names_the_quiet_window_it_obeys(self):
        text = logic.notification_summary_text("Every day from 09:00.", "No report is due.", (22, 7))
        self.assertIn("22:00-07:00", text)
        self.assertIn("standing authorisation", text)
        self.assertNotIn("22:00-07:00", logic.notification_summary_text("x", "y", None))

    def test_the_preference_question_says_what_it_cannot_do(self):
        asked = logic.notification_question("Every day", 9, "shown in this window")
        self.assertIn("no email", asked)
        self.assertIn("09:00", asked)
        self.assertIn("Stop preparing reports?",
                      logic.notification_question("No report, thanks", 9, "shown in this window"))

    def test_an_hour_is_read_strictly(self):
        self.assertEqual(logic.parse_notification_hour(" 9 "), 9)
        self.assertEqual(logic.parse_notification_hour("07:00"), 7)
        for value in ("", "half nine", "-1", "24", "9.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                logic.parse_notification_hour(value)


class DoNotContactTextTests(unittest.TestCase):
    """The words the do-not-contact panel puts on screen, with no Tk and no database."""

    def test_the_reasons_offered_are_the_suppression_module_s_own(self):
        from career_agent.suppression import REASON_LABELS

        offered = logic.suppression_reason_choices()
        self.assertEqual([value for value, _label in offered],
                         [reason.value for reason in REASON_LABELS])
        self.assertEqual([label for _value, label in offered], list(REASON_LABELS.values()))

    def test_a_row_says_a_note_exists_and_never_what_it_says(self):
        entry = SimpleNamespace(address="someone@example.invalid",
                                reason=SimpleNamespace(value="wrong_person"),
                                recorded_at="2026-10-18T09:00:00+00:00",
                                note="they told me on the phone")
        row = logic.suppression_rows([entry])[0]
        self.assertEqual(row[0], "someone@example.invalid")
        self.assertEqual(row[3], "a note is recorded")
        self.assertNotIn("phone", " ".join(row))
        blank = SimpleNamespace(address="x@example.invalid", reason=SimpleNamespace(value="x"),
                                recorded_at="", note="  ")
        self.assertEqual(logic.suppression_rows([blank])[0][3], "no note")

    def test_the_summary_reports_a_disagreement_between_the_two_records(self):
        agreed = logic.suppression_summary_text(2, 2, 0)
        self.assertIn("2 address(es)", agreed)
        self.assertNotIn("not on the list", agreed)
        disagreed = logic.suppression_summary_text(1, 2, 1)
        self.assertIn("1 marked contact(s) are not on the list", disagreed)
        self.assertIn("marking them again puts them on it", disagreed)

    def test_a_lift_needs_a_note_and_says_why(self):
        self.assertIsNone(logic.suppression_lift_refusal("they asked us to"))
        refusal = logic.suppression_lift_refusal(" no ")
        self.assertIsNotNone(refusal)
        self.assertIn("four", refusal)
        self.assertIn("nothing was changed", refusal)

    def test_the_mark_question_says_the_first_reason_wins_and_flags_a_permanent_one(self):
        asked = logic.suppression_mark_question(3, "they asked not to be contacted", True)
        self.assertIn("checks before anything may be sent", asked)
        self.assertIn("keeps the first reason", asked)
        self.assertIn("permanent", asked)
        self.assertIn("3 address(es)", asked)
        mild = logic.suppression_mark_question(0, "you decided not to write to them", False)
        self.assertNotIn("permanent", mild)

    def test_the_lift_question_is_honest_about_a_mark_that_is_not_on_the_list(self):
        absent = logic.suppression_lift_question("a@example.invalid", None, False)
        self.assertIn("not on the do-not-contact list", absent)
        present = logic.suppression_lift_question("a@example.invalid",
                                                  "they asked not to be contacted", True)
        self.assertIn("comes off the do-not-contact list", present)
        self.assertIn("not something time or an import may do", present)


class PolicyConditionTextTests(unittest.TestCase):
    """Reading what a person typed into the condition boxes, with no Tk and no policy value."""

    def test_terms_are_split_on_commas_and_never_folded_here(self):
        self.assertEqual(logic.parse_condition_terms(" engineer , Data ", noun="role conditions"),
                         ("engineer", "Data"))
        self.assertEqual(logic.parse_condition_terms("", noun="role conditions"), ())
        with self.assertRaises(ValueError):
            logic.parse_condition_terms("engineer, Engineer", noun="role conditions")

    def test_a_file_ending_is_read_as_one_and_anything_else_is_refused(self):
        self.assertEqual(logic.parse_attachment_kinds("pdf, .docx"), (".pdf", ".docx"))
        for value in ("my resume.pdf", "a b", "."):
            with self.subTest(value=value), self.assertRaises(ValueError):
                logic.parse_attachment_kinds(value)

    def test_a_follow_up_limit_is_a_whole_number_or_nothing(self):
        self.assertIsNone(logic.parse_follow_up_limit("  "))
        self.assertEqual(logic.parse_follow_up_limit("2"), 2)
        self.assertEqual(logic.parse_follow_up_limit("0"), 0)
        for value in ("-1", "two", "1.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                logic.parse_follow_up_limit(value)

    def test_half_a_quiet_window_is_refused_rather_than_guessed(self):
        self.assertIsNone(logic.parse_quiet_hours("", ""))
        self.assertEqual(logic.parse_quiet_hours("22:00", "7"), (22, 7))
        with self.assertRaises(ValueError) as refused:
            logic.parse_quiet_hours("22", "")
        self.assertIn("both ends", str(refused.exception))
        with self.assertRaises(ValueError) as same:
            logic.parse_quiet_hours("9", "09:00")
        self.assertIn("say nothing", str(same.exception))

    def test_the_summary_says_what_an_empty_attachment_rule_means(self):
        empty = logic.conditions_summary_text((), (), (), None, None)
        self.assertIn("no attachment rule is recorded, so nothing may be attached", empty)
        self.assertIn("no quiet hours are recorded", empty)
        full = logic.conditions_summary_text(("data",), ("remote",), (".pdf",), 2, (22, 7))
        self.assertIn("roles must mention: data", full)
        self.assertIn("at most 2 follow-up(s) per job", full)
        self.assertIn("quiet from 22:00 to 07:00", full)

    def test_what_changes_is_described_in_both_directions(self):
        before = {"role_terms": frozenset({"data"}), "locations": frozenset(),
                  "allowed_attachments": frozenset({".pdf"}), "follow_up_limit": 2,
                  "quiet_hours": (22, 7)}
        after = {"role_terms": frozenset(), "locations": frozenset({"remote"}),
                 "allowed_attachments": frozenset({".pdf"}), "follow_up_limit": None,
                 "quiet_hours": None}
        changes = logic.condition_changes(before, after)
        self.assertIn("roles must mention: data → nothing", changes)
        self.assertIn("places allowed: nothing → remote", changes)
        self.assertIn("follow-ups per job: 2 → nothing", changes)
        self.assertIn("quiet hours: 22:00-07:00 → nothing", changes)
        self.assertNotIn("attachments allowed", " ".join(changes),
                         "an unchanged condition was described as a change")
        self.assertEqual(logic.condition_changes(before, before), ())

    def test_the_question_says_a_condition_can_only_narrow(self):
        asked = logic.conditions_question(("places allowed: nothing → remote",), 3)
        self.assertIn("only narrow", asked)
        self.assertIn("version 4", asked)
        self.assertIn("refuses", asked)
        self.assertIn("nothing runs", asked)

    def test_terms_are_written_back_the_way_they_are_stored(self):
        self.assertEqual(logic.condition_terms_text(frozenset({"b", "a"})), "a, b")
        self.assertEqual(logic.condition_terms_text(()), "")


class SourceStatusTextTests(unittest.TestCase):
    """The words the window uses for "why is nothing being fetched?".

    A closed source has a reason, and the reason is the point: a tab that simply showed an empty
    list would be telling a person that nothing is available, when what is true is that this build
    has decided not to read anything until the evidence exists.
    """

    def test_every_reviewed_source_appears_with_both_gates_closed(self):
        rows = logic.source_rows()
        self.assertEqual(len(rows), len(sources.SOURCE_DECISIONS))
        self.assertEqual({row[0] for row in rows},
                         {decision.source_id for decision in sources.SOURCE_DECISIONS})
        for row in rows:
            with self.subTest(source=row[0]):
                self.assertEqual(row[3], "closed")
                self.assertEqual(row[4], "closed")

    def test_the_summary_counts_what_is_approved_separately_from_what_is_open(self):
        summary = logic.source_summary_text()
        self.assertIn("approved in principle", summary)
        self.assertIn("0 open for discovery right now", summary)
        self.assertIn("0 switched on", summary)
        self.assertIn("has not passed", summary)
        self.assertIn("including the approved ones", summary)

    def test_a_selected_source_carries_the_gates_own_reason_and_its_conditions(self):
        text = logic.source_detail_text("jobicy")
        self.assertIn("Jobicy", text)
        self.assertIn("Reviewed 2026-10-14", text)
        self.assertIn("Discovery: closed - ", text)
        self.assertIn("Submission: closed - ", text)
        self.assertIn("Conditions written into the review for reading it:", text)
        self.assertIn("research/source-permission-decision-matrix", text)

    def test_nothing_selected_and_an_unknown_source_both_say_so_rather_than_guess(self):
        for source_id in ("", "   ", "indeed", "LinkedIn Jobs"):
            with self.subTest(source_id=source_id):
                self.assertIn("Select a source", logic.source_detail_text(source_id))


class AcceptanceEvidenceTextTests(unittest.TestCase):
    """The words the window uses for "what would it take?".

    Held, missing and what each requirement means - and, in every one of these strings, that
    recording evidence is not the same act as switching something on.
    """

    def kinds(self, route_id):
        return next(route.kinds for route in ROUTE_REQUIREMENTS if route.route_id == route_id)

    def test_a_route_row_counts_what_is_recorded_against_what_is_required(self):
        rows = {row[0]: row for row in logic.evidence_route_rows({"naukri": self.kinds("naukri")[:2]})}
        self.assertEqual(len(rows), len(ROUTE_REQUIREMENTS))
        self.assertEqual(rows["naukri"][2], "2 of 9 recorded")
        self.assertEqual(rows["naukri"][3], "7 missing")
        self.assertEqual(rows["linkedin"][2], "0 of 9 recorded")

    def test_a_route_with_everything_recorded_reads_as_recorded_not_as_permitted(self):
        rows = {row[0]: row for row in logic.evidence_route_rows(
            {"employer_site": self.kinds("employer_site")})}
        self.assertEqual(rows["employer_site"][3], "every requirement recorded")
        self.assertNotIn("permitted", rows["employer_site"][3])
        self.assertNotIn("enabled", rows["employer_site"][3])

    def test_the_summary_says_what_recording_does_and_does_not_do(self):
        summary = logic.evidence_summary_text({"unstop": self.kinds("unstop")[:3]})
        self.assertIn("3 of 54", summary)
        self.assertIn("0 route(s) have all of theirs", summary)
        self.assertIn("opens no source", summary)
        self.assertIn("changes none of the gates", summary)

    def test_requirement_rows_mark_held_and_missing_and_date_only_what_is_held(self):
        record = SimpleNamespace(kind=EvidenceKind.TERMS_REVIEW,
                                 recorded_at="2026-10-18T09:30:00+05:30",
                                 reference="research/matrix.md", note="read it in full")
        rows = {row[0]: row for row in logic.evidence_kind_rows("linkedin", (record,))}
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows["terms_review"][2], "held")
        self.assertEqual(rows["terms_review"][3], "2026-10-18")
        self.assertEqual(rows["permission_basis"][2], "missing")
        self.assertEqual(rows["permission_basis"][3], "")

    def test_an_unknown_route_lists_nothing_rather_than_inventing_requirements(self):
        self.assertEqual(logic.evidence_kind_rows("indeed", ()), ())
        self.assertIn("Select a requirement",
                      logic.evidence_detail_text("indeed", EvidenceKind.TERMS_REVIEW, None))

    def test_a_missing_requirement_is_described_as_missing_not_as_failed(self):
        text = logic.evidence_detail_text("unstop", EvidenceKind.HUMAN_VERIFICATION, None)
        self.assertIn("A person verified one real run", text)
        self.assertIn("What this requires:", text)
        self.assertIn("Missing is the honest state", text)
        self.assertIn("it is not a failure", text)

    def test_a_held_requirement_shows_where_to_check_it_and_what_it_is_not(self):
        record = SimpleNamespace(kind=EvidenceKind.TERMS_REVIEW,
                                 recorded_at="2026-10-18T09:30:00+05:30",
                                 reference="https://example.invalid/terms",
                                 note="their clause 4 permits a read-only feed")
        text = logic.evidence_detail_text("unstop", EvidenceKind.TERMS_REVIEW, record)
        self.assertIn("Where to check it: https://example.invalid/terms", text)
        self.assertIn("their clause 4 permits a read-only feed", text)
        self.assertIn("not a permission granted by the route's owner", text)

    def test_the_recording_question_states_the_route_the_claim_and_the_limits(self):
        question = logic.evidence_record_question(
            "ats_provider", EvidenceKind.RATE_LIMITS, " https://example.invalid/limits ",
            " 60 requests a minute, documented ")
        self.assertIn("Stated rate and volume limits", question)
        self.assertIn("https://example.invalid/limits", question)
        self.assertIn("60 requests a minute, documented", question)
        self.assertIn("switches nothing on", question)
        self.assertIn("each still need their own", question)
        self.assertIn("withdraw it, with a reason", question)

    def test_the_withdrawal_question_says_what_goes_back_to_missing(self):
        question = logic.evidence_withdraw_question(
            "linkedin", EvidenceKind.TERMS_REVIEW, " their terms changed ")
        self.assertIn("Withdraw \"Terms and robots review\"", question)
        self.assertIn("their terms changed", question)
        self.assertIn("goes back to missing", question)
        self.assertIn("nothing was switched on by the record", question)


class DispatchTextTests(unittest.TestCase):
    """The sentences around the one guarded path out of this machine.

    The guard decides; these strings only have to describe it truthfully - in particular that the
    do-not-contact list is checked first, that an attempt is written down before it is made, and
    that "the provider accepted it" is not "it was delivered".
    """

    def contact(self, email, name="", suppressed=False):
        return SimpleNamespace(email=email, name=name, suppressed=suppressed)

    def test_only_stored_unsuppressed_contacts_are_offered_and_they_are_sorted(self):
        offered = logic.dispatch_recipient_choices([
            self.contact("zoe@example.invalid", "Zoe"),
            self.contact("amir@example.invalid", "Amir"),
            self.contact("blank@example.invalid", "", suppressed=True),
            self.contact("", "Nobody"),
        ])
        self.assertEqual(offered, ("Amir <amir@example.invalid>", "Zoe <zoe@example.invalid>"))

    def test_an_address_on_the_do_not_contact_list_is_not_offered_however_it_is_written(self):
        offered = logic.dispatch_recipient_choices(
            [self.contact("Amir@Example.invalid", "Amir")], ["  amir@example.invalid "])
        self.assertEqual(offered, ())

    def test_the_address_is_read_back_out_of_the_choice(self):
        self.assertEqual(logic.address_from_choice("Amir <amir@example.invalid>"),
                         "amir@example.invalid")
        self.assertEqual(logic.address_from_choice(" amir@example.invalid "),
                         "amir@example.invalid")
        self.assertEqual(logic.address_from_choice(""), "")

    def test_the_question_lists_the_checks_in_the_order_the_guard_applies_them(self):
        question = logic.dispatch_question("Acme", "AI Engineer", "hr@acme.invalid",
                                           integration_name="disabled")
        self.assertIn("hr@acme.invalid", question)
        self.assertIn("AI Engineer at Acme", question)
        order = [question.index(check) for check in logic.DISPATCH_CHECK_ORDER]
        self.assertEqual(order, sorted(order), "the checks are not listed in the guard's order")
        self.assertIn("do-not-contact", logic.DISPATCH_CHECK_ORDER[0])
        self.assertIn("written into your records as having an unknown outcome", question)
        self.assertIn("honest expectation is a refusal", question)

    def test_a_refusal_is_described_as_nothing_having_left_the_machine(self):
        text = logic.dispatch_result_text(
            "disabled", False, "Nothing was sent: this is not authorised.",
            integration_name="disabled")
        self.assertIn("Nothing was sent.", text)
        self.assertIn("Nothing left this machine", text)
        self.assertIn("written into your records with the reason", text)
        self.assertNotIn("delivered", text)

    def test_a_performed_dispatch_is_never_described_as_delivered_or_read(self):
        text = logic.dispatch_result_text(
            "completed", True, "The integration accepted it.", integration_name="local-mock")
        self.assertIn("the integration accepted it", text.casefold())
        self.assertIn("not that it was delivered", text)
        self.assertIn("not that anybody replied", text)
        self.assertIn("local-mock", text)

    def test_an_unknown_outcome_says_nothing_could_be_established(self):
        text = logic.dispatch_result_text("unknown", False, "It is not known what happened.",
                                          integration_name="disabled")
        self.assertIn("Nothing could be established", text)
        self.assertIn("separate permissions", text)


class SuppressionAddQuestionTests(unittest.TestCase):
    """The confirmation for listing an address that was never in anybody's contact file."""

    def test_the_question_names_the_address_and_the_reason(self):
        question = logic.suppression_add_question("someone@example.invalid",
                                                  SuppressionReason.BOUNCED_PERMANENTLY)
        self.assertIn("someone@example.invalid", question)
        self.assertIn("rejected mail permanently", question)
        self.assertIn("Nothing on this list expires", question)
        self.assertIn("does not have to be one of your stored contacts", question)

    def test_a_permanent_reason_says_so_and_a_milder_one_does_not(self):
        permanent = logic.suppression_add_question("a@example.invalid",
                                                   SuppressionReason.ASKED_TO_STOP)
        milder = logic.suppression_add_question("a@example.invalid",
                                                SuppressionReason.OUR_OWN_DECISION)
        self.assertIn("permanent in this application", permanent)
        self.assertNotIn("permanent in this application", milder)
        self.assertIn("no import can clear it", milder)

    def test_the_question_never_promises_that_anything_was_sent_or_stopped_elsewhere(self):
        question = logic.suppression_add_question("a@example.invalid",
                                                  SuppressionReason.WRONG_PERSON)
        self.assertIn("checked before any outbound action is attempted", question)
        self.assertNotIn("unsubscribe", question.casefold())


class BuildADocumentTextTests(unittest.TestCase):
    """The words around building a first document: what is offered, previewed, stored, written out.

    These sentences are the only description a person gets of a path that writes a file, so they
    are pinned here: that the choices carry their identifiers back, that the confirmation repeats
    what was previewed rather than summarising it, and that nothing anywhere promises a document
    went somewhere.
    """

    class Listing:
        def __init__(self, listing_id, role_title="GenAI Engineer", employer_name="Example Employer"):
            self.listing_id, self.role_title, self.employer_name = listing_id, role_title, employer_name

    class Strategy:
        def __init__(self, strategy_id, name="Applied AI roles", version=1):
            self.strategy_id, self.name, self.version = strategy_id, name, version

    def test_a_listing_choice_shows_the_role_and_carries_its_identifier(self):
        (choice,) = logic.artifact_listing_choices([self.Listing("j1")])
        self.assertIn("GenAI Engineer", choice)
        self.assertIn("Example Employer", choice)
        self.assertEqual(logic.artifact_id_from_choice(choice), "j1")

    def test_a_strategy_choice_shows_the_version_a_document_would_be_tied_to(self):
        (choice,) = logic.artifact_strategy_choices([self.Strategy("s1", version=3)])
        self.assertIn("version 3", choice)
        self.assertEqual(logic.artifact_id_from_choice(choice), "s1")

    def test_a_record_without_an_identifier_is_not_offered_at_all(self):
        self.assertEqual(logic.artifact_listing_choices([self.Listing("  ")]), ())
        self.assertEqual(logic.artifact_strategy_choices([self.Strategy("")]), ())
        self.assertEqual(logic.artifact_id_from_choice("a line with no identifier"), "")
        self.assertEqual(logic.artifact_id_from_choice(None), "")

    def test_an_unnamed_listing_is_still_offered_rather_than_silently_dropped(self):
        (choice,) = logic.artifact_listing_choices([self.Listing("j2", role_title="", employer_name="")])
        self.assertIn("untitled role", choice)
        self.assertIn("unnamed employer", choice)
        self.assertEqual(logic.artifact_id_from_choice(choice), "j2")

    def test_the_preamble_says_what_is_missing_rather_than_leaving_dead_controls(self):
        self.assertIn("Save your profile first", logic.artifact_build_preamble(3, 2, False))
        self.assertIn("Add a job listing and a role strategy",
                      logic.artifact_build_preamble(0, 0, True))
        self.assertIn("Add a job listing first", logic.artifact_build_preamble(0, 2, True))
        self.assertIn("Add a role strategy first", logic.artifact_build_preamble(2, 0, True))
        ready = logic.artifact_build_preamble(2, 2, True)
        self.assertIn("read what would be used before anything is stored", ready)

    def test_screening_answers_are_not_offered_as_something_to_build(self):
        self.assertEqual(logic.ARTIFACT_BUILD_KINDS, ("tailored_resume", "cover_letter"))
        self.assertNotIn("screening_answers", logic.ARTIFACT_BUILD_KINDS)

    def test_the_confirmation_repeats_the_preview_it_was_built_from(self):
        lines = ("Tailored resume for j1, under Applied AI roles version 1.",
                 "Facts it would use: skills.", "")
        question = logic.artifact_build_question(lines)
        self.assertIn("Store this document?", question)
        for line in lines[:2]:
            self.assertIn(line, question)
        self.assertIn("Nothing is sent anywhere", question)
        self.assertIn("original résumé file is not touched", question)
        self.assertEqual(logic.artifact_plan_text(lines), "\n".join(lines[:2]))
        self.assertEqual(logic.artifact_plan_text(()), "Nothing to preview.")

    def test_what_is_said_after_storing_names_the_document_and_the_gaps(self):
        plain = logic.artifact_built_text("artifact-1", ())
        self.assertIn("Stored as document artifact-1", plain)
        self.assertNotIn("do not state", plain)
        with_gaps = logic.artifact_built_text("artifact-1", ("Docker", ""))
        self.assertIn("do not state Docker", with_gaps)
        self.assertIn("does not claim them", with_gaps)
        self.assertNotIn("This listing also asks", with_gaps)
        both = logic.artifact_built_text("artifact-1", ("Docker",), ("Kubernetes", ""))
        self.assertIn("do not state Docker", both)
        self.assertIn("This listing also asks for Kubernetes", both)
        only_listing = logic.artifact_built_text("artifact-1", (), ("Kubernetes",))
        self.assertNotIn("does not claim them", only_listing)
        self.assertIn("do not state either", only_listing)

    def test_the_export_question_promises_that_an_existing_file_survives(self):
        question = logic.artifact_export_question("/tmp/tailored.txt", "artifact-1")
        self.assertIn("/tmp/tailored.txt", question)
        self.assertIn("artifact-1", question)
        self.assertIn("existing file is never written over", question)

    def test_the_export_report_counts_characters_and_claims_nothing_was_sent(self):
        self.assertIn("1 character)", logic.artifact_export_text("/tmp/a.txt", 1))
        written = logic.artifact_export_text("/tmp/a.txt", 2048)
        self.assertIn("2048 characters", written)
        self.assertIn("readable only by you", written)
        self.assertIn("nothing was sent anywhere", written)

    def test_a_refused_export_says_what_moved_and_what_to_do(self):
        refusal = logic.artifact_export_refusal_text(
            "artifact-1", ("the strategy moved to version 2", ""))
        self.assertIn("artifact-1", refusal)
        self.assertIn("the strategy moved to version 2", refusal)
        self.assertIn("Rebuild it from your current facts first", refusal)
        self.assertIn("no longer current", logic.artifact_export_refusal_text("artifact-1", ()))
