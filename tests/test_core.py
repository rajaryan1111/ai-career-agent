import unittest

from career_agent import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile,
    Decision, JobListing, canonicalize_url, deduplicate_listings,
    evaluate_eligibility, score_relevance, job_to_public_dict,
)


def sample_profile(**overrides):
    values = dict(
        candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
        graduation_year=2027, experience_years=0.5, skills=frozenset({"Python", "RAG"}),
        preferred_work_modes=frozenset({"remote"}), preferred_role_types=frozenset({"internship"}),
    )
    values.update(overrides)
    return CandidateProfile(**values)


def sample_job(**overrides):
    values = dict(
        listing_id="j1", source_id="s1", source_name="Test source",
        source_listing_url="https://jobs.example/role/1", employer_name="Example Inc",
        role_title="AI Intern", availability_status=Availability.OPEN,
        eligibility_scope="restricted", eligible_countries=("India",),
        allowed_degree_disciplines=("ECE", "Computer Science"),
        allowed_study_statuses=("undergraduate",), allowed_graduation_years=(2027, 2028),
        minimum_experience_years=0, required_skills=frozenset({"Python", "LangChain"}),
        work_mode="remote", role_type="internship",
    )
    values.update(overrides)
    return JobListing(**values)


class EligibilityTests(unittest.TestCase):
    def test_all_explicit_requirements_pass(self):
        report = evaluate_eligibility(sample_profile(), sample_job())
        self.assertEqual(report.decision, Decision.PASS)
        self.assertTrue(report.can_be_ranked_as_eligible)

    def test_unknown_country_never_passes(self):
        report = evaluate_eligibility(sample_profile(), sample_job(eligibility_scope="unknown", eligible_countries=()))
        self.assertEqual(report.decision, Decision.UNKNOWN)
        self.assertFalse(report.can_be_ranked_as_eligible)

    def test_country_outside_explicit_list_fails(self):
        report = evaluate_eligibility(sample_profile(candidate_country="India"), sample_job(eligible_countries=("United States",)))
        self.assertEqual(report.decision, Decision.FAIL)
        self.assertIn("country", {r.requirement for r in report.failed_requirements})

    def test_unknown_degree_does_not_default_to_pass(self):
        report = evaluate_eligibility(sample_profile(degree_discipline=None), sample_job())
        self.assertEqual(report.decision, Decision.UNKNOWN)

    def test_related_degree_is_not_fuzzy_matched(self):
        report = evaluate_eligibility(sample_profile(degree_discipline="Electronics and Communication Engineering"), sample_job())
        self.assertEqual(report.decision, Decision.FAIL)

    def test_closed_listing_fails_even_if_candidate_matches(self):
        report = evaluate_eligibility(sample_profile(), sample_job(availability_status=Availability.CLOSED))
        self.assertEqual(report.decision, Decision.FAIL)

    def test_unknown_availability_stays_unknown(self):
        report = evaluate_eligibility(sample_profile(), sample_job(availability_status=Availability.UNKNOWN))
        self.assertEqual(report.decision, Decision.UNKNOWN)

    def test_experience_minimum_enforced(self):
        report = evaluate_eligibility(sample_profile(experience_years=0), sample_job(minimum_experience_years=1))
        self.assertEqual(report.decision, Decision.FAIL)

    def test_worldwide_only_passes_when_explicitly_stated(self):
        report = evaluate_eligibility(sample_profile(), sample_job(eligibility_scope="worldwide", eligible_countries=()))
        self.assertEqual(report.decision, Decision.PASS)

    def test_work_authorization_unknown_is_not_a_pass(self):
        job = sample_job(allowed_work_authorizations=("authorized_without_sponsorship",))
        report = evaluate_eligibility(sample_profile(work_authorization=None), job)
        self.assertEqual(report.decision, Decision.UNKNOWN)
        self.assertIn("work_authorization", {r.requirement for r in report.unknown_requirements})

    def test_work_authorization_requires_exact_explicit_match(self):
        job = sample_job(allowed_work_authorizations=("authorized_without_sponsorship",))
        matching = evaluate_eligibility(sample_profile(work_authorization="authorized_without_sponsorship"), job)
        mismatch = evaluate_eligibility(sample_profile(work_authorization="sponsorship_required"), job)
        self.assertEqual(matching.decision, Decision.PASS)
        self.assertEqual(mismatch.decision, Decision.FAIL)


class MatchingAndDedupTests(unittest.TestCase):
    def test_relevance_is_explainable_and_not_probability(self):
        result = score_relevance(sample_profile(), sample_job())
        self.assertEqual(result["matched_skills"], ["python"])
        self.assertEqual(result["missing_required_skills"], ["langchain"])
        self.assertIn("not a hiring probability", result["note"])

    def test_url_canonicalization_removes_tracking_and_fragment(self):
        self.assertEqual(
            canonicalize_url("HTTPS://Jobs.Example:443/role/1/?utm_source=x&b=2#apply"),
            "https://jobs.example/role/1?b=2",
        )

    def test_same_canonical_url_deduplicates(self):
        a = sample_job(source_listing_url="https://jobs.example/role/1?utm_source=feed")
        b = sample_job(listing_id="j2", source_id="s2", source_listing_url="https://jobs.example/role/1#apply")
        self.assertEqual(len(deduplicate_listings([a, b])), 1)

    def test_different_requisition_ids_are_not_merged(self):
        a = sample_job(canonical_requisition_id="req-1", source_listing_url="https://jobs.example/careers")
        b = sample_job(listing_id="j2", canonical_requisition_id="req-2", source_listing_url="https://jobs.example/careers")
        self.assertEqual(len(deduplicate_listings([a, b])), 2)

    def test_apply_url_does_not_replace_source_url(self):
        job = sample_job(employer_apply_url="https://employer.example/apply/1")
        payload = job_to_public_dict(job)
        self.assertEqual(payload["source_listing_url"], "https://jobs.example/role/1")
        self.assertEqual(payload["employer_apply_url"], "https://employer.example/apply/1")


class ApplicationTrackerTests(unittest.TestCase):
    def test_cannot_confirm_without_evidence(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED)
        with self.assertRaises(ValueError):
            tracker.transition(ApplicationStatus.CONFIRMED)

    def test_submission_attempt_is_not_confirmation(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.AWAITING_USER)
        attempted = tracker.transition(ApplicationStatus.SUBMISSION_ATTEMPTED)
        self.assertEqual(attempted.status, ApplicationStatus.SUBMISSION_ATTEMPTED)

    def test_confirmation_requires_valid_transition_and_evidence(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED)
        confirmed = tracker.transition(ApplicationStatus.CONFIRMED, evidence="Employer confirmation page shown")
        self.assertEqual(confirmed.status, ApplicationStatus.CONFIRMED)
        self.assertEqual(confirmed.status_evidence, "Employer confirmation page shown")

    def test_confirmation_flag_survives_later_status_transitions(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED)
        confirmed = tracker.transition(ApplicationStatus.CONFIRMED, evidence="Employer confirmation page shown", candidate_confirmed=True)
        response = confirmed.transition(ApplicationStatus.RESPONSE_RECEIVED, evidence="Employer email received")
        self.assertTrue(response.candidate_confirmed)
        self.assertEqual(response.status_evidence, "Employer email received")

    def test_invalid_transition_is_rejected(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.DISCOVERED)
        with self.assertRaises(ValueError):
            tracker.transition(ApplicationStatus.CONFIRMED, evidence="confirmation")


if __name__ == "__main__":
    unittest.main(verbosity=2)
