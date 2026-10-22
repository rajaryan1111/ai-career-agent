"""Unit tests for the eligibility-decision audit record and fingerprints."""
import unittest

from career_agent import (
    Availability, CandidateProfile, JobListing, build_decision,
    evaluate_eligibility, inputs_changed,
)
from career_agent.audit import (
    MAX_AUDIT_TEXT, is_fingerprint, job_fingerprint, profile_fingerprint,
    requirement_records, requirements_from_json, requirements_from_records,
    requirements_to_json,
)
from career_agent.core import ELIGIBILITY_RULE_VERSION


def sample_profile(**overrides):
    values = dict(
        candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
        graduation_year=2027, experience_years=0.5,
        work_authorization="authorized_without_sponsorship",
        skills=frozenset({"Python", "RAG"}), preferred_work_modes=frozenset({"remote"}),
        preferred_locations=frozenset({"Bengaluru"}), preferred_role_types=frozenset({"internship"}),
    )
    values.update(overrides)
    return CandidateProfile(**values)


def sample_job(**overrides):
    values = dict(
        listing_id="j1", source_id="manual", source_name="Manual",
        source_listing_url="https://jobs.example/role/1", employer_name="Example",
        role_title="AI Intern", availability_status=Availability.OPEN,
        eligibility_scope="restricted", eligible_countries=("India",),
        allowed_degree_disciplines=("ECE",), allowed_study_statuses=("undergraduate",),
        allowed_graduation_years=(2027,), minimum_experience_years=0.0,
        maximum_experience_years=2.0, required_skills=frozenset({"Python"}),
        provenance_note="Checked the official listing.",
        allowed_work_authorizations=("authorized_without_sponsorship",),
    )
    values.update(overrides)
    return JobListing(**values)


class RuleVersionTests(unittest.TestCase):
    def test_rule_version_is_a_dated_revision(self):
        self.assertRegex(ELIGIBILITY_RULE_VERSION, r"^\d{4}-\d{2}-\d{2}\.\d+$")

    def test_every_decision_records_the_current_rule_version(self):
        profile, job = sample_profile(), sample_job()
        decision = build_decision(profile, job, evaluate_eligibility(profile, job))
        self.assertEqual(decision.rule_version, ELIGIBILITY_RULE_VERSION)


class FingerprintTests(unittest.TestCase):
    def test_fingerprints_are_versioned_sha256_hex(self):
        self.assertTrue(is_fingerprint(job_fingerprint(sample_job())))
        self.assertTrue(is_fingerprint(profile_fingerprint(sample_profile())))
        self.assertFalse(is_fingerprint("md5:abc"))
        self.assertFalse(is_fingerprint("fp1:" + "z" * 64))
        self.assertFalse(is_fingerprint(None))

    def test_equal_inputs_produce_equal_fingerprints(self):
        self.assertEqual(job_fingerprint(sample_job()), job_fingerprint(sample_job()))
        self.assertEqual(profile_fingerprint(sample_profile()), profile_fingerprint(sample_profile()))

    def test_profile_absence_is_not_a_fingerprint(self):
        self.assertIsNone(profile_fingerprint(None))

    def test_eligibility_relevant_profile_change_changes_the_fingerprint(self):
        base = profile_fingerprint(sample_profile())
        for field, value in (
            ("candidate_country", "Canada"),
            ("degree_discipline", "Mechanical"),
            ("study_status", "graduated"),
            ("graduation_year", 2026),
            ("experience_years", 1.5),
            ("work_authorization", "requires_sponsorship"),
        ):
            with self.subTest(field=field):
                self.assertNotEqual(
                    base, profile_fingerprint(sample_profile(**{field: value})),
                )

    def test_relevance_only_profile_fields_do_not_change_the_fingerprint(self):
        base = profile_fingerprint(sample_profile())
        self.assertEqual(
            base,
            profile_fingerprint(sample_profile(
                skills=frozenset({"Figma"}),
                preferred_work_modes=frozenset({"onsite"}),
                preferred_locations=frozenset({"Pune"}),
                preferred_role_types=frozenset({"full_time"}),
            )),
        )

    def test_eligibility_relevant_job_change_changes_the_fingerprint(self):
        base = job_fingerprint(sample_job())
        for overrides in (
            {"availability_status": Availability.CLOSED},
            {"eligible_countries": ("Canada",)},
            {"eligibility_scope": "worldwide"},
            {"allowed_graduation_years": (2028,)},
            {"minimum_experience_years": 1.0},
            {"provenance_note": None},
            {"allowed_work_authorizations": ("requires_sponsorship",)},
        ):
            with self.subTest(overrides=overrides):
                self.assertNotEqual(base, job_fingerprint(sample_job(**overrides)))

    def test_required_skills_do_not_change_the_job_fingerprint(self):
        # Required skills feed relevance only; they never change hard eligibility.
        self.assertEqual(
            job_fingerprint(sample_job()),
            job_fingerprint(sample_job(required_skills=frozenset({"Figma"}))),
        )


class DecisionRecordTests(unittest.TestCase):
    def test_decision_carries_outcome_fingerprints_and_trail(self):
        profile, job = sample_profile(), sample_job()
        report = evaluate_eligibility(profile, job)
        decision = build_decision(
            profile, job, report, decision_id="d1",
            evaluated_at="2026-10-22T10:00:00+00:00",
        )
        self.assertEqual(decision.decision_id, "d1")
        self.assertEqual(decision.listing_id, "j1")
        self.assertEqual(decision.evaluated_at, "2026-10-22T10:00:00+00:00")
        self.assertEqual(decision.outcome, report.decision)
        self.assertEqual(decision.requirements, report.requirements)
        self.assertEqual(decision.profile_fingerprint, profile_fingerprint(profile))
        self.assertEqual(decision.job_fingerprint, job_fingerprint(job))
        # The trail carries job-side evidence only; candidate facts stay out of it.
        trail = requirements_to_json(decision.requirements)
        self.assertNotIn("candidate_country", trail)
        self.assertNotIn("Bengaluru", trail)

    def test_inputs_changed_reports_profile_and_job_edits(self):
        profile, job = sample_profile(), sample_job()
        decision = build_decision(profile, job, evaluate_eligibility(profile, job))
        self.assertEqual(inputs_changed(decision, profile, job), ())
        self.assertEqual(
            inputs_changed(decision, sample_profile(candidate_country="Canada"), job),
            ("profile",),
        )
        self.assertEqual(
            inputs_changed(decision, profile, sample_job(eligible_countries=("Canada",))),
            ("job",),
        )
        self.assertEqual(
            inputs_changed(
                decision, sample_profile(graduation_year=2026), sample_job(availability_status=Availability.CLOSED),
            ),
            ("profile", "job"),
        )

    def test_changing_only_preferences_reports_no_change(self):
        profile, job = sample_profile(), sample_job()
        decision = build_decision(profile, job, evaluate_eligibility(profile, job))
        self.assertEqual(
            inputs_changed(decision, sample_profile(skills=frozenset({"Figma"})), job), (),
        )


class RequirementTrailTests(unittest.TestCase):
    def setUp(self):
        profile, job = sample_profile(), sample_job()
        self.report = evaluate_eligibility(profile, job)

    def test_round_trip_preserves_every_field(self):
        text = requirements_to_json(self.report.requirements)
        restored = requirements_from_json(text)
        self.assertEqual(restored, self.report.requirements)
        self.assertEqual(requirement_records(restored), requirement_records(self.report.requirements))

    def test_empty_trail_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            requirements_from_records([])

    def test_unknown_field_is_rejected(self):
        record = requirement_records(self.report.requirements)
        record[0]["candidate_value"] = "India"
        with self.assertRaisesRegex(ValueError, "unsupported field"):
            requirements_from_records(record)

    def test_unknown_decision_is_rejected(self):
        record = requirement_records(self.report.requirements)
        record[0]["decision"] = "maybe"
        with self.assertRaisesRegex(ValueError, "unknown decision"):
            requirements_from_records(record)

    def test_blank_and_oversized_text_is_rejected(self):
        record = requirement_records(self.report.requirements)
        blank = [dict(record[0], explanation="   ")] + record[1:]
        with self.assertRaisesRegex(ValueError, "must not be blank"):
            requirements_from_records(blank)
        oversized = [dict(record[0], explanation="x" * (MAX_AUDIT_TEXT + 1))] + record[1:]
        with self.assertRaisesRegex(ValueError, "character limit"):
            requirements_from_records(oversized)

    def test_invalid_json_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            requirements_from_json("{not json")

    def test_non_list_trail_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be a list"):
            requirements_from_records({"requirement": "availability"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
