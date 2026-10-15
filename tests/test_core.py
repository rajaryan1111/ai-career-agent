import unittest
from datetime import date, datetime

from career_agent import (
    INITIAL_APPLICATION_STATUS, ApplicationStatus, ApplicationTracker, Availability, CandidateProfile,
    Decision, JobListing, canonicalize_url, deduplicate_listings,
    evaluate_eligibility, is_allowed_tracker_transition, score_relevance, job_to_public_dict,
    is_substantive_confirmation_evidence, require_confirmation_evidence, selectable_tracker_statuses,
)
from career_agent.core import (
    EducationEntry, EmploymentType, WorkHistoryEntry, months_covered_by,
    ACTIVITY_KIND_LABELS, MAX_ACTIVITY_DETAIL_LENGTH, ActivityKind, ApplicationActivity,
)


class ActivityEntryTests(unittest.TestCase):
    """An activity entry is the person's own dated record; it is not proof and not a status."""

    def test_the_kind_labels_describe_the_entry_without_overclaiming(self):
        self.assertEqual(ACTIVITY_KIND_LABELS[ActivityKind.APPLIED], "I applied")
        self.assertEqual(set(ACTIVITY_KIND_LABELS), set(ActivityKind))
        for kind, label in ACTIVITY_KIND_LABELS.items():
            with self.subTest(kind=kind):
                self.assertTrue(label.strip())
        # The employer's half of the story is described as a reply, never as an outcome.
        self.assertIn("replied", ACTIVITY_KIND_LABELS[ActivityKind.RESPONSE])

    def test_detail_is_trimmed_and_blank_text_is_refused(self):
        entry = ApplicationActivity(ActivityKind.NOTE, date(2026, 10, 12), "  Called the recruiter.  ")

        self.assertEqual(entry.detail, "Called the recruiter.")
        for text in ("", "   ", "\n\t"):
            with self.subTest(text=repr(text)):
                with self.assertRaises(ValueError) as caught:
                    ApplicationActivity(ActivityKind.NOTE, date(2026, 10, 12), text)
                self.assertIn("Write what happened", str(caught.exception))

    def test_an_over_long_detail_is_refused_with_the_limit_named(self):
        with self.assertRaises(ValueError) as caught:
            ApplicationActivity(ActivityKind.NOTE, date(2026, 10, 12),
                                "x" * (MAX_ACTIVITY_DETAIL_LENGTH + 1))

        message = str(caught.exception)
        self.assertIn(str(MAX_ACTIVITY_DETAIL_LENGTH), message)
        self.assertIn(str(MAX_ACTIVITY_DETAIL_LENGTH + 1), message)
        # Exactly at the limit is allowed: the bound is a limit, not an off-by-one.
        self.assertEqual(
            len(ApplicationActivity(ActivityKind.NOTE, date(2026, 10, 12), "x" * MAX_ACTIVITY_DETAIL_LENGTH).detail),
            MAX_ACTIVITY_DETAIL_LENGTH,
        )

    def test_a_date_that_cannot_be_real_is_refused(self):
        for value in (date(2202, 1, 1), date(1899, 12, 31)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as caught:
                    ApplicationActivity(ActivityKind.NOTE, value, "Applied.")
                self.assertIn("real calendar date", str(caught.exception))

    def test_a_datetime_is_not_accepted_where_a_date_is_meant(self):
        """``datetime`` is a subclass of ``date``; an entry dated to the minute is not what is stored."""
        with self.assertRaises(ValueError) as caught:
            ApplicationActivity(ActivityKind.NOTE, datetime(2026, 10, 12, 9, 30), "Applied.")

        self.assertIn("YYYY-MM-DD", str(caught.exception))

    def test_a_future_date_is_allowed_because_an_interview_can_be_scheduled(self):
        entry = ApplicationActivity(ActivityKind.INTERVIEW, date(2099, 6, 1), "Interview scheduled.")

        self.assertEqual(entry.occurred_on, date(2099, 6, 1))

    def test_a_plain_string_kind_is_normalised_to_the_enum(self):
        entry = ApplicationActivity("follow-up", date(2026, 10, 12), "Chased the recruiter.")

        self.assertIs(entry.kind, ActivityKind.FOLLOW_UP)
        self.assertEqual(entry.label, "I followed up")

    def test_an_unknown_kind_is_refused_by_name(self):
        with self.assertRaises(ValueError) as caught:
            ApplicationActivity("sent", date(2026, 10, 12), "Applied.")

        self.assertIn("sent", str(caught.exception))


def requirement(report, name):
    """Return the single requirement result called ``name``."""
    return next(result for result in report.requirements if result.requirement == name)


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
        work_mode="remote", role_type="internship", provenance_note="Manual test fixture: checked official listing today.",
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

    def test_open_status_without_evidence_note_stays_unknown(self):
        report = evaluate_eligibility(sample_profile(), sample_job(provenance_note=None))
        self.assertEqual(report.decision, Decision.UNKNOWN)
        self.assertIn("availability", {r.requirement for r in report.unknown_requirements})

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


    def test_a_non_finite_experience_value_is_never_a_pass(self):
        """``nan`` is false against every bound, so an unguarded range check used to pass it.

        The desktop form refuses to store ``nan`` or ``inf`` at all; this covers the value arriving
        some other way (an older row, a hand-edited database, a future importer) and proves the
        eligibility gate stays fail-closed for it.
        """
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(candidate_experience=value):
                report = evaluate_eligibility(
                    sample_profile(experience_years=value), sample_job(minimum_experience_years=5)
                )
                self.assertEqual(report.decision, Decision.UNKNOWN)
                self.assertFalse(report.can_be_ranked_as_eligible)
                self.assertIn("experience_years", {r.requirement for r in report.unknown_requirements})

    def test_a_non_finite_job_experience_bound_is_never_a_pass(self):
        for bound in (float("nan"), float("inf")):
            with self.subTest(bound=bound):
                report = evaluate_eligibility(
                    sample_profile(experience_years=0), sample_job(minimum_experience_years=bound)
                )
                self.assertEqual(report.decision, Decision.UNKNOWN)
                self.assertFalse(report.can_be_ranked_as_eligible)

    def test_an_ordinary_experience_range_still_passes_and_still_fails(self):
        # The guard above must not turn a normal range into "unknown".
        self.assertEqual(
            evaluate_eligibility(sample_profile(experience_years=1), sample_job(minimum_experience_years=1, maximum_experience_years=2)).decision,
            Decision.PASS,
        )
        self.assertEqual(
            evaluate_eligibility(sample_profile(experience_years=3), sample_job(minimum_experience_years=1, maximum_experience_years=2)).decision,
            Decision.FAIL,
        )
        self.assertEqual(
            evaluate_eligibility(sample_profile(experience_years=0), sample_job(minimum_experience_years=1)).decision,
            Decision.FAIL,
        )


class RequirementNormalizationTests(unittest.TestCase):
    """Formatting differences must not change a hard requirement's decision."""

    def test_degree_discipline_ignores_case_and_surrounding_whitespace(self):
        report = evaluate_eligibility(
            sample_profile(degree_discipline="  ece "), sample_job(allowed_degree_disciplines=("ECE",))
        )
        self.assertEqual(requirement(report, "degree_discipline").decision, Decision.PASS)

    def test_study_status_ignores_case(self):
        report = evaluate_eligibility(
            sample_profile(study_status="Undergraduate"), sample_job(allowed_study_statuses=("undergraduate",))
        )
        self.assertEqual(requirement(report, "study_status").decision, Decision.PASS)

    def test_work_authorization_ignores_case_and_word_separators(self):
        job = sample_job(allowed_work_authorizations=("authorized_without_sponsorship",))
        for candidate_value in ("authorized_without_sponsorship", "Authorized Without Sponsorship", " AUTHORIZED_Without_Sponsorship "):
            with self.subTest(candidate_value=candidate_value):
                report = evaluate_eligibility(sample_profile(work_authorization=candidate_value), job)
                self.assertEqual(requirement(report, "work_authorization").decision, Decision.PASS)

    def test_genuinely_different_values_still_fail(self):
        cases = [
            ("degree_discipline", sample_profile(degree_discipline="Mechanical Engineering"),
             sample_job(allowed_degree_disciplines=("ECE", "Computer Science"))),
            ("study_status", sample_profile(study_status="graduate"),
             sample_job(allowed_study_statuses=("undergraduate",))),
            ("work_authorization", sample_profile(work_authorization="sponsorship_required"),
             sample_job(allowed_work_authorizations=("authorized_without_sponsorship",))),
            ("graduation_year", sample_profile(graduation_year=2026),
             sample_job(allowed_graduation_years=(2027, 2028))),
        ]
        for name, profile, job in cases:
            with self.subTest(requirement=name):
                report = evaluate_eligibility(profile, job)
                self.assertEqual(requirement(report, name).decision, Decision.FAIL)
                self.assertEqual(report.decision, Decision.FAIL)

    def test_missing_values_stay_unknown_after_normalization(self):
        blank_report = evaluate_eligibility(
            sample_profile(degree_discipline="   "), sample_job(allowed_degree_disciplines=("ECE",))
        )
        self.assertEqual(requirement(blank_report, "degree_discipline").decision, Decision.UNKNOWN)

        missing_report = evaluate_eligibility(
            sample_profile(study_status=None), sample_job(allowed_study_statuses=("undergraduate",))
        )
        self.assertEqual(requirement(missing_report, "study_status").decision, Decision.UNKNOWN)

        no_listing_requirement = evaluate_eligibility(sample_profile(), sample_job(allowed_study_statuses=None))
        self.assertEqual(requirement(no_listing_requirement, "study_status").decision, Decision.UNKNOWN)

    def test_normalization_never_produces_a_pass_from_an_unlisted_requirement(self):
        report = evaluate_eligibility(
            sample_profile(degree_discipline="ECE"), sample_job(allowed_degree_disciplines=None)
        )
        self.assertNotEqual(report.decision, Decision.PASS)
        self.assertEqual(requirement(report, "degree_discipline").decision, Decision.UNKNOWN)


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
        self.assertEqual(payload["allowed_work_authorizations"], None)
        self.assertEqual(payload["provenance_note"], "Manual test fixture: checked official listing today.")


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

    def test_confirmation_refuses_this_projects_own_instruction_text(self):
        """The smoke-test failure mode: paste the app's guidance and it must not read as proof."""
        guidance_texts = (
            "A confirmed application requires evidence. An attempt or timeout is not proof.",
            "Confirmation requires evidence; a click or attempted submission is not proof.",
            "Evidence / note (required to confirm)",
            "Confirm with a meaningful evidence note, then move it to response_received or interview.",
            "To revise the evidence, move the status forward with a meaningful note, "
            "or keep the existing record as it is.",
        )
        for text in guidance_texts:
            with self.subTest(text=text[:40]):
                tracker = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED)
                with self.assertRaises(ValueError) as caught:
                    tracker.transition(ApplicationStatus.CONFIRMED, evidence=text, candidate_confirmed=True)
                self.assertIn("instruction or a placeholder", str(caught.exception))
                self.assertIs(tracker.status, ApplicationStatus.SUBMISSION_ATTEMPTED)
                self.assertIsNone(tracker.status_evidence)
                self.assertFalse(tracker.candidate_confirmed)

    def test_confirmation_refuses_whitespace_placeholders_and_template_markers(self):
        for text in ("   ", "\t\n", "n/a", "TODO", "tbd", "yes", "placeholder", "<your evidence here>",
                     "This is a test", "just testing", "sample", "lorem ipsum"):
            with self.subTest(text=text):
                tracker = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED)
                with self.assertRaises(ValueError):
                    tracker.transition(ApplicationStatus.CONFIRMED, evidence=text)

    def test_realistic_confirmation_notes_are_not_refused(self):
        """The evidence floor must stay narrow: ordinary observations must still be recordable."""
        for text in (
            "Employer portal shows Application Received on 2026-10-14",
            "Recruiter email acknowledged the application (thread ref ABC-123)",
            "Confirmation email received; saved a screenshot locally",
            # contains the word "evidence" but is an observation, not a bare placeholder value
            "Portal shows the posting requires evidence of degree completion when applying",
            # contains "test" as a word but is not the bare placeholder
            "Employer replied: no online test is required for this internship",
        ):
            with self.subTest(text=text[:40]):
                confirmed = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED).transition(
                    ApplicationStatus.CONFIRMED, evidence=text, candidate_confirmed=True
                )
                self.assertIs(confirmed.status, ApplicationStatus.CONFIRMED)
                self.assertEqual(confirmed.status_evidence, text)

    def test_evidence_floor_is_a_shared_helper_over_plain_values(self):
        cases = (
            ("Employer portal shows Application Received", True),
            ("A confirmed application requires evidence.", False),
            ("", False),
            (None, False),
            ("   ", False),
            ("todo", False),
            ("<placeholder>", False),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertIs(is_substantive_confirmation_evidence(text), expected)
        self.assertEqual(require_confirmation_evidence("  Received  "), "Received")

    def test_confirmation_flag_survives_later_status_transitions(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED)
        confirmed = tracker.transition(ApplicationStatus.CONFIRMED, evidence="Employer confirmation page shown", candidate_confirmed=True)
        response = confirmed.transition(ApplicationStatus.RESPONSE_RECEIVED, evidence="Employer email received")
        self.assertTrue(response.candidate_confirmed)
        self.assertEqual(response.status_evidence, "Employer email received")

    def test_withdrawn_is_terminal_and_cannot_be_un_withdrawn(self):
        withdrawn = ApplicationTracker("j1", ApplicationStatus.WITHDRAWN, "Candidate withdrew", False)
        for status in ApplicationStatus:
            with self.subTest(status=status.value):
                if status is ApplicationStatus.WITHDRAWN:
                    continue
                self.assertFalse(is_allowed_tracker_transition(ApplicationStatus.WITHDRAWN, status))
                with self.assertRaisesRegex(ValueError, "Invalid application transition"):
                    withdrawn.transition(status, evidence="Employer portal shows Application Received")
        # Re-applying the same status remains an idempotent no-op.
        self.assertIs(withdrawn.transition(ApplicationStatus.WITHDRAWN), withdrawn)
        self.assertEqual(withdrawn.status_evidence, "Candidate withdrew")

    def test_every_route_to_confirmed_applies_the_same_evidence_floor(self):
        """No predecessor may reach a confirmation with instruction text or a placeholder."""
        predecessors = (
            ApplicationStatus.SUBMISSION_ATTEMPTED,
            ApplicationStatus.SUBMITTED_UNVERIFIED,
            ApplicationStatus.UNKNOWN_STATUS,
        )
        refused = (
            None, "", "   ", "todo", "n/a", "yes", "test", "<your evidence here>",
            "A confirmed application requires evidence. An attempt or timeout is not proof.",
            "Evidence / note (required to confirm)",
        )
        for predecessor in predecessors:
            for text in refused:
                with self.subTest(predecessor=predecessor.value, text=str(text)[:30]):
                    tracker = ApplicationTracker("j1", predecessor, "earlier note", False)
                    with self.assertRaises(ValueError):
                        tracker.transition(ApplicationStatus.CONFIRMED, evidence=text, candidate_confirmed=True)
                    self.assertIs(tracker.status, predecessor)
                    self.assertEqual(tracker.status_evidence, "earlier note")
                    self.assertFalse(tracker.candidate_confirmed)

        accepted = "Employer portal shows Application Received on 2026-10-14"
        for predecessor in predecessors:
            with self.subTest(predecessor=predecessor.value):
                confirmed = ApplicationTracker("j1", predecessor, "earlier note", False).transition(
                    ApplicationStatus.CONFIRMED, evidence=accepted, candidate_confirmed=True
                )
                self.assertIs(confirmed.status, ApplicationStatus.CONFIRMED)
                self.assertEqual(confirmed.status_evidence, accepted)
                self.assertTrue(confirmed.candidate_confirmed)

    def test_the_evidence_floor_never_asserts_confirmation_on_its_own(self):
        """A valid transition still records only what the caller passed: the flag is never invented."""
        tracker = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED)
        confirmed = tracker.transition(ApplicationStatus.CONFIRMED, evidence="Employer portal shows Application Received")
        self.assertFalse(confirmed.candidate_confirmed, "the domain must not claim a confirmation nobody made")

    def test_invalid_transition_is_rejected(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.DISCOVERED)
        with self.assertRaises(ValueError):
            tracker.transition(ApplicationStatus.CONFIRMED, evidence="confirmation")

    def test_no_op_transition_returns_the_tracker_unchanged(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "original evidence", True)
        unchanged = tracker.transition(ApplicationStatus.CONFIRMED, evidence="replacement evidence")
        self.assertIs(unchanged, tracker)
        self.assertEqual(unchanged.status_evidence, "original evidence")

    def test_transition_carries_the_new_status_and_evidence(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.SUBMISSION_ATTEMPTED, "attempt recorded", False)
        updated = tracker.transition(ApplicationStatus.CONFIRMED, evidence="Employer confirmation page", candidate_confirmed=True)
        self.assertEqual(updated.status, ApplicationStatus.CONFIRMED)
        self.assertEqual(updated.status_evidence, "Employer confirmation page")
        self.assertTrue(updated.candidate_confirmed)

    def test_is_allowed_tracker_transition_matches_the_state_machine(self):
        self.assertTrue(is_allowed_tracker_transition(ApplicationStatus.DISCOVERED, ApplicationStatus.SHORTLISTED))
        self.assertTrue(is_allowed_tracker_transition(ApplicationStatus.FAILED, ApplicationStatus.AWAITING_USER))
        self.assertTrue(is_allowed_tracker_transition(ApplicationStatus.CONFIRMED, ApplicationStatus.CONFIRMED))
        self.assertFalse(is_allowed_tracker_transition(ApplicationStatus.DISCOVERED, ApplicationStatus.CONFIRMED))
        self.assertFalse(is_allowed_tracker_transition(ApplicationStatus.WITHDRAWN, ApplicationStatus.SHORTLISTED))
        self.assertFalse(is_allowed_tracker_transition(ApplicationStatus.INTERVIEW, ApplicationStatus.DISCOVERED))


class SelectableTrackerStatusTests(unittest.TestCase):
    """The chooser's vocabulary is derived from the state machine, not maintained beside it.

    The expected set is recomputed here from ``is_allowed_tracker_transition`` — the rule the storage
    layer enforces — rather than from a second hand-written table, so the UI and the domain cannot
    drift apart without a test failing.
    """

    def permitted(self, current):
        return {status for status in ApplicationStatus if is_allowed_tracker_transition(current, status)}

    def test_offered_statuses_are_exactly_the_permitted_ones_for_every_status(self):
        for current in ApplicationStatus:
            with self.subTest(current=current.value):
                offered = selectable_tracker_statuses(current)
                self.assertEqual(set(offered), self.permitted(current))
                self.assertIn(current, offered, "re-applying the current status must stay possible")

    def test_nothing_outside_the_domain_vocabulary_is_offered(self):
        for current in ApplicationStatus:
            with self.subTest(current=current.value):
                for status in selectable_tracker_statuses(current):
                    self.assertIsInstance(status, ApplicationStatus)

    def test_the_order_is_stable_and_follows_the_declaration_order(self):
        for current in ApplicationStatus:
            with self.subTest(current=current.value):
                offered = selectable_tracker_statuses(current)
                self.assertEqual(list(offered), sorted(offered, key=lambda status: list(ApplicationStatus).index(status)))

    def test_a_new_record_offers_only_the_initial_status_and_its_permitted_moves(self):
        self.assertEqual(
            tuple(status.value for status in selectable_tracker_statuses(INITIAL_APPLICATION_STATUS)),
            ("discovered", "shortlisted", "withdrawn"),
        )

    def test_terminal_statuses_offer_only_themselves(self):
        for current in (ApplicationStatus.WITHDRAWN, ApplicationStatus.REJECTED_BY_EMPLOYER):
            with self.subTest(current=current.value):
                self.assertEqual(selectable_tracker_statuses(current), (current,))

    def test_no_status_is_offered_that_the_state_machine_would_refuse(self):
        # The property that matters: a choice presented by the interface must be applicable.
        for current in ApplicationStatus:
            for offered in selectable_tracker_statuses(current):
                with self.subTest(current=current.value, offered=offered.value):
                    tracker = ApplicationTracker("j1", current, None, False)
                    if offered is current:
                        continue  # no-ops keep the record as it is, so they cannot be validated here
                    self.assertTrue(is_allowed_tracker_transition(current, offered))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class WorkHistoryEntryTests(unittest.TestCase):
    """The employment record: what it refuses, what it leaves unknown, and what it never claims."""

    def test_a_current_role_reads_as_present_and_needs_no_end_date(self):
        role = WorkHistoryEntry("Sandbox Systems", "Data Engineer", date(2023, 4, 1), is_current=True,
                                employment_type="full_time")

        self.assertEqual(role.period, "2023-04-01 - present")
        self.assertEqual(role.employment_type_label, "Full time")
        self.assertFalse(role.is_current is None)

    def test_an_ended_role_with_no_recorded_end_date_says_so(self):
        role = WorkHistoryEntry("Old Co", "Analyst", date(2020, 1, 6))

        self.assertEqual(role.period, "2020-01-06 - end date not recorded")
        self.assertNotIn("present", role.period)

    def test_an_end_before_a_start_is_refused_naming_both_dates(self):
        with self.assertRaises(ValueError) as caught:
            WorkHistoryEntry("X", "Y", date(2024, 5, 1), end_date=date(2023, 1, 1))

        message = str(caught.exception)
        self.assertIn("2023-01-01", message)
        self.assertIn("2024-05-01", message)

    def test_a_current_role_with_an_end_date_is_refused_rather_than_resolved(self):
        with self.assertRaises(ValueError) as caught:
            WorkHistoryEntry("X", "Y", date(2024, 1, 1), end_date=date(2025, 1, 1), is_current=True)

        self.assertIn("current role", str(caught.exception))
        self.assertIn("2025-01-01", str(caught.exception))

    def test_the_same_day_start_and_end_is_allowed(self):
        """A one-day contract is unusual, not impossible: the rule is order, not duration."""
        role = WorkHistoryEntry("X", "Y", date(2024, 1, 1), end_date=date(2024, 1, 1))

        self.assertEqual(role.end_date, date(2024, 1, 1))

    def test_empty_required_text_is_refused_with_the_field_named(self):
        for kwargs, noun in (({"employer": "  ", "job_title": "Y"}, "employer"),
                             ({"employer": "X", "job_title": ""}, "job title")):
            with self.subTest(noun=noun), self.assertRaises(ValueError) as caught:
                WorkHistoryEntry(start_date=date(2024, 1, 1), **kwargs)
            self.assertIn(noun, str(caught.exception))

    def test_text_is_trimmed_and_inner_whitespace_collapsed(self):
        role = WorkHistoryEntry("  Sandbox   Systems ", "  Data    Engineer ", date(2024, 1, 1))

        self.assertEqual(role.employer, "Sandbox Systems")
        self.assertEqual(role.job_title, "Data Engineer")

    def test_an_over_long_field_is_refused_with_its_limit(self):
        with self.assertRaises(ValueError) as caught:
            WorkHistoryEntry("X" * 201, "Y", date(2024, 1, 1))

        self.assertIn("200", str(caught.exception))

    def test_a_summary_is_optional_and_blank_becomes_absent(self):
        self.assertIsNone(WorkHistoryEntry("X", "Y", date(2024, 1, 1), summary="   ").summary)
        self.assertEqual(WorkHistoryEntry("X", "Y", date(2024, 1, 1), summary=" built things ").summary,
                         "built things")

    def test_a_mistyped_year_is_refused_where_it_is_typed(self):
        with self.assertRaises(ValueError):
            WorkHistoryEntry("X", "Y", date(202, 1, 1))

    def test_a_datetime_is_not_a_start_date(self):
        with self.assertRaises(ValueError):
            WorkHistoryEntry("X", "Y", datetime(2024, 1, 1, 9, 0))

    def test_an_unknown_employment_type_is_refused(self):
        with self.assertRaises(ValueError):
            WorkHistoryEntry("X", "Y", date(2024, 1, 1), employment_type="freelancing-on-the-side")

    def test_the_current_flag_must_be_a_bool(self):
        with self.assertRaises(ValueError):
            WorkHistoryEntry("X", "Y", date(2024, 1, 1), is_current="yes")

    def test_months_covered_counts_a_current_role_up_to_the_day_given(self):
        role = WorkHistoryEntry("X", "Y", date(2024, 1, 15), is_current=True)

        self.assertEqual(role.months_covered(today=date(2024, 1, 15)), 0)
        self.assertEqual(role.months_covered(today=date(2024, 2, 14)), 0)
        self.assertEqual(role.months_covered(today=date(2024, 2, 15)), 1)
        self.assertEqual(role.months_covered(today=date(2026, 1, 15)), 24)

    def test_a_current_role_needs_a_day_to_measure_up_to(self):
        with self.assertRaises(ValueError):
            WorkHistoryEntry("X", "Y", date(2024, 1, 1), is_current=True).months_covered()

    def test_an_ended_role_with_no_end_date_reports_no_duration_rather_than_todays(self):
        """Counting it to today would claim the person is still there. Zero *known* months is the truth."""
        role = WorkHistoryEntry("X", "Y", date(2020, 1, 1))

        self.assertEqual(role.months_covered(today=date(2026, 1, 1)), 0)

    def test_an_ended_role_counts_its_own_period_even_when_today_is_given(self):
        role = WorkHistoryEntry("X", "Y", date(2020, 1, 1), end_date=date(2021, 1, 1))

        self.assertEqual(role.months_covered(today=date(2026, 1, 1)), 12)


class EducationEntryTests(unittest.TestCase):
    """The education record: optional dates, and the two contradictions it refuses."""

    def test_a_completed_qualification_reads_as_a_period(self):
        entry = EducationEntry("IIT Delhi", "B.Tech", discipline="ECE", start_date=date(2015, 8, 1),
                              completion_date=date(2019, 5, 31))

        self.assertEqual(entry.period, "2015-08-01 - 2019-05-31")
        self.assertEqual(entry.label, "B.Tech - ECE")

    def test_ongoing_study_reads_as_ongoing(self):
        entry = EducationEntry("Coursera", "Specialisation", is_ongoing=True)

        self.assertEqual(entry.period, "start not recorded - ongoing")

    def test_a_qualification_with_no_dates_says_both_are_missing(self):
        entry = EducationEntry("Some College", "Diploma")

        self.assertEqual(entry.period, "start not recorded - completion not recorded")

    def test_completion_before_start_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            EducationEntry("X", "Y", start_date=date(2020, 1, 1), completion_date=date(2019, 1, 1))

        self.assertIn("before the start date", str(caught.exception))

    def test_ongoing_study_with_a_completion_date_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            EducationEntry("X", "Y", completion_date=date(2026, 1, 1), is_ongoing=True)

        self.assertIn("ongoing", str(caught.exception))

    def test_a_label_without_a_discipline_is_just_the_qualification(self):
        self.assertEqual(EducationEntry("X", "M.Sc").label, "M.Sc")

    def test_blank_discipline_becomes_absent(self):
        self.assertIsNone(EducationEntry("X", "Y", discipline="   ").discipline)

    def test_required_fields_are_enforced(self):
        with self.assertRaises(ValueError) as caught:
            EducationEntry("   ", "B.Tech")
        self.assertIn("institution", str(caught.exception))

        with self.assertRaises(ValueError) as caught_qualification:
            EducationEntry("IIT", "")
        self.assertIn("qualification", str(caught_qualification.exception))

    def test_a_mistyped_completion_year_is_refused(self):
        with self.assertRaises(ValueError):
            EducationEntry("X", "Y", completion_date=date(9999, 1, 1))


class MonthsCoveredTogetherTests(unittest.TestCase):
    """The one duration figure the app shows, and the ways an honest one differs from a sum."""

    def role(self, start, end=None, *, current=False):
        return WorkHistoryEntry("Employer", "Role", start, end_date=end, is_current=current)

    def test_two_roles_in_sequence_count_all_of_both(self):
        first = self.role(date(2020, 1, 1), date(2021, 1, 1))
        second = self.role(date(2021, 1, 1), date(2022, 1, 1))

        self.assertEqual(months_covered_by([first, second]), 24)

    def test_two_roles_at_once_are_not_added_together(self):
        """The reason this is not a sum: two part-time roles in the same year is one year, not two."""
        first = self.role(date(2020, 1, 1), date(2021, 1, 1))
        second = self.role(date(2020, 7, 1), date(2021, 7, 1))

        self.assertEqual(first.months_covered() + second.months_covered(), 24)
        self.assertEqual(months_covered_by([first, second]), 18)

    def test_a_gap_between_roles_is_not_counted(self):
        first = self.role(date(2020, 1, 1), date(2021, 1, 1))
        second = self.role(date(2022, 1, 1), date(2023, 1, 1))

        self.assertEqual(months_covered_by([first, second]), 24, "the year between them is not work")

    def test_a_role_with_no_recorded_end_contributes_nothing(self):
        self.assertEqual(months_covered_by([self.role(date(2020, 1, 1))]), 0)

    def test_a_current_role_counts_up_to_the_day_given(self):
        role = self.role(date(2024, 1, 15), current=True)

        self.assertEqual(months_covered_by([role], today=date(2026, 1, 15)), 24)

    def test_a_current_role_measured_without_a_day_is_refused_rather_than_guessed_at(self):
        with self.assertRaises(ValueError):
            months_covered_by([self.role(date(2024, 1, 15), current=True)])

    def test_no_records_cover_no_months(self):
        self.assertEqual(months_covered_by([]), 0)

    def test_a_one_day_role_covers_no_whole_month(self):
        self.assertEqual(months_covered_by([self.role(date(2024, 1, 1), date(2024, 1, 1))]), 0)

    def test_a_role_contained_inside_another_does_not_extend_the_span(self):
        outer = self.role(date(2018, 1, 1), date(2024, 1, 1))
        inner = self.role(date(2020, 1, 1), date(2021, 1, 1))

        self.assertEqual(months_covered_by([outer, inner]), 72)

    def test_the_order_of_the_records_does_not_change_the_answer(self):
        first = self.role(date(2020, 1, 1), date(2021, 1, 1))
        second = self.role(date(2020, 7, 1), date(2021, 7, 1))
        third = self.role(date(2023, 1, 1), date(2024, 1, 1))

        self.assertEqual(months_covered_by([first, second, third]),
                         months_covered_by([third, second, first]))
