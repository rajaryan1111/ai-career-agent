import unittest

from career_agent import (
    Availability,
    CandidateProfile,
    Decision,
    JobListing,
    Readiness,
    assess_readiness,
    build_application_draft,
)


def profile(**overrides):
    values = dict(
        candidate_country="India",
        degree_discipline="ECE",
        study_status="undergraduate",
        graduation_year=2027,
        experience_years=0.5,
        work_authorization="authorized_without_sponsorship",
        skills=frozenset({"Python", "RAG"}),
        preferred_work_modes=frozenset({"remote"}),
    )
    values.update(overrides)
    return CandidateProfile(**values)


def job(**overrides):
    values = dict(
        listing_id="j1",
        source_id="manual",
        source_name="Manual entry",
        source_listing_url="https://jobs.example/role/1",
        employer_name="Example",
        role_title="AI Intern",
        availability_status=Availability.OPEN,
        employer_apply_url="https://employer.example/apply/1",
        location_text="Remote",
        work_mode="remote",
        role_type="internship",
        eligibility_scope="restricted",
        eligible_countries=("India",),
        allowed_degree_disciplines=("ECE",),
        allowed_study_statuses=("undergraduate",),
        allowed_graduation_years=(2027,),
        minimum_experience_years=0.0,
        maximum_experience_years=2.0,
        required_skills=frozenset({"Python", "SQL"}),
        provenance_note="Checked the official listing today.",
    )
    values.update(overrides)
    return JobListing(**values)


class ReadinessTests(unittest.TestCase):
    def test_ready_when_eligibility_passes_and_apply_url_is_verified(self):
        report = assess_readiness(profile(), job())
        self.assertIs(report.decision, Readiness.READY)
        self.assertTrue(report.can_prepare)
        self.assertFalse(report.blockers)
        self.assertFalse(report.notes)
        self.assertEqual(report.eligibility.decision, Decision.PASS)

    def test_failed_eligibility_blocks_with_the_failing_requirement(self):
        report = assess_readiness(profile(), job(eligible_countries=("Germany",)))
        self.assertIs(report.decision, Readiness.BLOCKED)
        self.assertFalse(report.can_prepare)
        self.assertTrue(any("country" in blocker for blocker in report.blockers))
        self.assertTrue(any("Eligibility failed" in blocker for blocker in report.blockers))

    def test_unknown_eligibility_blocks_and_lists_missing_evidence(self):
        report = assess_readiness(profile(), job(provenance_note=None))
        self.assertIs(report.decision, Readiness.BLOCKED)
        self.assertTrue(any("availability" in blocker for blocker in report.blockers))
        self.assertTrue(any("UNKNOWN" in item.decision.value.upper() for item in report.items))

    def test_missing_application_url_needs_review_instead_of_inventing_one(self):
        report = assess_readiness(profile(), job(employer_apply_url=None))
        self.assertIs(report.decision, Readiness.NEEDS_REVIEW)
        self.assertFalse(report.can_prepare)
        self.assertTrue(any("application URL" in note for note in report.notes))
        self.assertFalse(report.blockers)

    def test_active_duplicate_observation_blocks_preparation(self):
        report = assess_readiness(
            profile(), job(), other_active_label="Example: AI Intern (shortlisted)"
        )
        self.assertIs(report.decision, Readiness.BLOCKED)
        self.assertTrue(any("active application" in blocker for blocker in report.blockers))

    def test_missing_candidate_facts_do_not_become_pass(self):
        report = assess_readiness(profile(candidate_country=None), job(eligibility_scope="worldwide"))
        self.assertIs(report.decision, Readiness.BLOCKED)
        self.assertTrue(any("country" in blocker for blocker in report.blockers))


class DraftTests(unittest.TestCase):
    def test_draft_uses_only_recorded_fields_and_marks_the_rest_unknown(self):
        draft = build_application_draft(profile(candidate_country=None, skills=frozenset()), job())
        fields = {field.label: field for field in draft.fields}
        self.assertIsNone(fields["Candidate country"].value)
        self.assertEqual(fields["Candidate country"].source, "not recorded")
        self.assertIsNone(fields["Recorded skills"].value)
        self.assertEqual(fields["Employer"].value, "Example")
        self.assertEqual(fields["Employer"].source, "listing")
        self.assertIn("AI Intern", draft.summary)
        self.assertIn("nothing has been submitted", draft.summary)
        self.assertNotIn("None", draft.summary)
        self.assertIn("No candidate skills are recorded.", draft.warnings)

    def test_draft_exposes_matched_and_missing_required_skills(self):
        draft = build_application_draft(profile(), job())
        fields = {field.label: field for field in draft.fields}
        self.assertEqual(fields["Matched required skills"].value, "python")
        self.assertEqual(fields["Required skills not recorded"].value, "sql")

    def test_draft_repeats_listing_evidence_without_adding_claims(self):
        draft = build_application_draft(profile(), job())
        fields = {field.label: field for field in draft.fields}
        self.assertEqual(fields["Availability evidence"].value, "Checked the official listing today.")
        self.assertIn("no answers, contact details, or qualifications were invented", draft.summary)
        self.assertNotIn("email", draft.summary.casefold())
        self.assertNotIn("phone", draft.summary.casefold())

    def test_draft_warns_when_the_application_destination_is_unknown(self):
        draft = build_application_draft(profile(), job(employer_apply_url=None))
        self.assertIn("Employer application URL is not recorded.", draft.warnings)
        fields = {field.label: field for field in draft.fields}
        self.assertIsNone(fields["Employer application URL"].value)

    def test_draft_reports_a_closed_listing_honestly(self):
        draft = build_application_draft(profile(), job(availability_status=Availability.CLOSED))
        fields = {field.label: field for field in draft.fields}
        self.assertEqual(fields["Availability"].value, "closed")
        self.assertIn("Eligibility: FAIL", draft.summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
