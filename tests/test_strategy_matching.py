"""Tests for strategy-aware assessment: the person's statement of intent applied to ranking.

Every profile, listing and strategy here is invented. The property under test is the one the
roadmap demands of matching: the strategy's hard statements act as **gates before ranking**, its
preferences act as **explainable factors**, and nothing is inferred from silence.
"""
from __future__ import annotations

import unittest

from career_agent.core import (
    Availability, CandidateProfile, JobListing,
)
from career_agent.core import evaluate_eligibility
from career_agent.matching import (
    Band, FactorStatus, Recommendation, assess, assess_for_strategy, evaluate_strategy_eligibility,
    rank_for_strategy,
)
from career_agent.strategies import RoleStrategy, new_strategy_id

PROFILE = CandidateProfile(
    candidate_country="India", degree_discipline="CSE", graduation_year=2026,
    experience_years=2.0, work_authorization="citizen",
    skills=frozenset({"Python", "SQL", "FastAPI", "Docker"}),
    preferred_locations=frozenset({"Delhi"}), preferred_work_modes=frozenset({"hybrid"}),
    preferred_role_types=frozenset({"Backend"}),
)

STRATEGY = RoleStrategy(
    strategy_id=new_strategy_id(), version=1, name="Backend roles, north India",
    role_family="Backend engineering", title_synonyms=frozenset({"Backend Engineer"}),
    seniority="mid", locations=frozenset({"Delhi", "Noida"}), work_modes=frozenset({"hybrid", "remote"}),
    employment_types=frozenset({"full-time"}), required_skills=frozenset({"Python", "Docker"}),
    excluded_role_titles=frozenset({"Sales Engineer"}),
    excluded_employers=frozenset({"Blocked Employer"}),
    preferred_skills=frozenset({"FastAPI"}),
)


def listing(listing_id="j1", *, employer="Example Employer", role="Backend Engineer",
            skills=("Python", "PostgreSQL"), location="Delhi, India", work_mode="hybrid") -> JobListing:
    return JobListing(
        listing_id=listing_id, source_id="manual", source_name="Manual entry",
        source_listing_url=f"https://jobs.example.invalid/{listing_id}", employer_name=employer,
        role_title=role, availability_status=Availability.OPEN, required_skills=frozenset(skills),
        location_text=location, work_mode=work_mode, eligibility_scope="worldwide")


class StrategyEligibilityTests(unittest.TestCase):
    """The strategy's hard statements, decided before any fit score exists."""

    def test_a_clean_listing_passes_with_its_reasons_named(self):
        report = evaluate_strategy_eligibility(PROFILE, listing(), STRATEGY)
        self.assertEqual(report.decision.value, "pass")
        named = {result.requirement for result in report.requirements}
        self.assertIn("an employer your strategy has not excluded", named)
        self.assertIn("a role title your strategy has not excluded", named)
        self.assertIn("the skills your strategy requires", named)

    def test_an_excluded_employer_fails_by_name(self):
        report = evaluate_strategy_eligibility(PROFILE, listing(employer="Blocked Employer Ltd"),
                                               STRATEGY)
        self.assertEqual(report.decision.value, "fail")
        failed = report.failed_requirements[0]
        self.assertEqual(failed.requirement, "an employer your strategy has not excluded")
        self.assertIn("Blocked Employer", failed.explanation)

    def test_an_excluded_role_title_fails(self):
        report = evaluate_strategy_eligibility(PROFILE, listing(role="Senior Sales Engineer"), STRATEGY)
        self.assertEqual(report.decision.value, "fail")
        failed = report.failed_requirements[0]
        self.assertEqual(failed.requirement, "a role title your strategy has not excluded")
        self.assertIn("rules out Sales Engineer", failed.explanation)
        self.assertIn("Senior Sales Engineer", failed.explanation)

    def test_a_title_that_merely_contains_an_excluded_word_is_not_excluded(self):
        """Exclusion is phrase-level: 'Sales Engineer' must not block 'Aerospace Systems Engineer'."""
        report = evaluate_strategy_eligibility(
            PROFILE, listing(role="Aerospace Systems Engineer"), STRATEGY)
        self.assertNotEqual(report.decision.value, "fail")

    def test_a_required_skill_your_profile_does_not_state_fails(self):
        lacking = CandidateProfile(
            candidate_country="India", graduation_year=2026, experience_years=2.0,
            skills=frozenset({"Python"}), preferred_locations=frozenset({"Delhi"}))
        report = evaluate_strategy_eligibility(lacking, listing(), STRATEGY)
        self.assertEqual(report.decision.value, "fail")
        self.assertIn("Docker", report.failed_requirements[0].explanation)

    def test_silence_about_skills_is_not_a_pass(self):
        quiet = CandidateProfile(candidate_country="India", preferred_locations=frozenset({"Delhi"}))
        report = evaluate_strategy_eligibility(quiet, listing(), STRATEGY)
        self.assertEqual(report.decision.value, "fail",
                         "the strategy says these skills are required; a silent profile has none of them")

    def test_an_empty_strategy_declares_no_gates_and_no_preferences(self):
        bare = RoleStrategy(strategy_id=new_strategy_id(), version=1, name="Anything data",
                            role_family="Data engineering")
        report = evaluate_strategy_eligibility(PROFILE, listing(), bare)
        self.assertEqual(report.decision.value, "pass")
        self.assertEqual([result.decision for result in report.requirements],
                         ["pass", "pass", "pass"])


class StrategyAssessmentTests(unittest.TestCase):
    """Gates block; preferences rank; every line says which strategy statement produced it."""

    def test_the_score_combines_the_profile_and_strategy_factors(self):
        base = assess(PROFILE, listing())
        combined = assess_for_strategy(PROFILE, listing(), STRATEGY)
        # Three factors, not four: the listing domain model has no employment-type field, so the
        # strategy's employment types are recorded but not compared - the same honest limitation as
        # compensation, and the factor set says so instead of inventing a comparison.
        self.assertEqual(len(combined.factors), len(base.factors) + 3)
        names = {factor.name for factor in combined.factors}
        self.assertEqual(names - {factor.name for factor in base.factors},
                         {"strategy_locations", "strategy_work_mode", "strategy_preferred_skills"})

    def test_a_strategy_location_match_scores_above_the_base(self):
        near = assess_for_strategy(PROFILE, listing(), STRATEGY)
        far = assess_for_strategy(PROFILE, listing(location="Chennai, India"), STRATEGY)
        self.assertGreater(near.score, far.score)
        location_factor = {factor.name: factor for factor in near.factors}["strategy_locations"]
        self.assertEqual(location_factor.status, FactorStatus.PASS)
        self.assertIn("Delhi", location_factor.evidence or "")
        far_location = {factor.name: factor for factor in far.factors}["strategy_locations"]
        self.assertEqual(far_location.status, FactorStatus.FAIL)

    def test_a_listing_that_says_nothing_about_a_place_is_unknown_not_failing(self):
        blank = assess_for_strategy(PROFILE, listing(location=None), STRATEGY)
        factor = {factor.name: factor for factor in blank.factors}["strategy_locations"]
        self.assertEqual(factor.status, FactorStatus.UNKNOWN)
        self.assertIn("does not state", factor.explanation)

    def test_an_empty_preference_is_not_applicable_not_zero(self):
        narrow = RoleStrategy(strategy_id=new_strategy_id(), version=1, name="No places named",
                              role_family="Backend engineering", required_skills=frozenset({"Python"}))
        result = assess_for_strategy(PROFILE, listing(), narrow)
        factor = {factor.name: factor for factor in result.factors}["strategy_locations"]
        self.assertEqual(factor.status, FactorStatus.NOT_APPLICABLE)
        self.assertIn("names no", factor.explanation)

    def test_work_mode_factor(self):
        result = assess_for_strategy(PROFILE, listing(work_mode="on-site"), STRATEGY)
        by_name = {factor.name: factor for factor in result.factors}
        self.assertEqual(by_name["strategy_work_mode"].status, FactorStatus.FAIL)
        stated = assess_for_strategy(PROFILE, listing(work_mode=None), STRATEGY)
        by_name = {factor.name: factor for factor in stated.factors}
        self.assertEqual(by_name["strategy_work_mode"].status, FactorStatus.UNKNOWN)

    def test_preferred_skills_score_asks_for_all_and_reports_the_share(self):
        two = RoleStrategy(strategy_id=new_strategy_id(), version=1, name="Two skills preferred",
                           role_family="Backend engineering",
                           preferred_skills=frozenset({"FastAPI", "GraphQL"}))
        full = assess_for_strategy(PROFILE, listing(skills=("Python", "FastAPI", "GraphQL")), two)
        partial = assess_for_strategy(PROFILE, listing(skills=("Python", "SQL", "GraphQL")), two)
        none = assess_for_strategy(PROFILE, listing(skills=("Go",)), two)
        by_factor = {factor.name: factor for factor in full.factors}["strategy_preferred_skills"]
        self.assertEqual(by_factor.status, FactorStatus.PASS)
        self.assertGreater(full.score, none.score)
        self.assertEqual(
            {factor.name: factor for factor in none.factors}["strategy_preferred_skills"].status,
            FactorStatus.FAIL)
        self.assertGreater(full.score, partial.score, "asking for the preferred skill ranks higher")
        self.assertEqual({factor.name: factor for factor in partial.factors}
                         ["strategy_preferred_skills"].status, FactorStatus.PARTIAL)
        # With one preferred skill the share is 0 or 1: there is no partial to report, and saying
        # otherwise would be inventing a fraction the strategy never stated.
        single = assess_for_strategy(PROFILE, listing(skills=("Python", "SQL", "Kafka")), STRATEGY)
        self.assertEqual(
            {factor.name: factor for factor in single.factors}["strategy_preferred_skills"].status,
            FactorStatus.FAIL)

    def test_a_strategy_gate_blocks_before_ranking_and_names_why(self):
        blocked = assess_for_strategy(PROFILE, listing(employer="Blocked Employer"), STRATEGY)
        self.assertEqual(blocked.recommendation, Recommendation.BLOCKED)
        self.assertEqual(blocked.eligibility.value, "fail")
        self.assertTrue(any("Blocked Employer" in note for note in blocked.notes),
                        "the note names the strategy statement that blocked it")
        # The evidence is kept even for a blocked listing: the factors explain what would have matched.
        self.assertTrue(any(factor.name == "strategy_locations" for factor in blocked.factors))

    def test_a_profile_missing_a_required_skill_blocks_with_the_skill_named(self):
        lacking = CandidateProfile(
            candidate_country="India", graduation_year=2026, experience_years=2.0,
            skills=frozenset({"Python"}), preferred_locations=frozenset({"Delhi"}))
        result = assess_for_strategy(lacking, listing(), STRATEGY)
        self.assertEqual(result.recommendation, Recommendation.BLOCKED)
        self.assertTrue(any("Docker" in note for note in result.notes))

    def test_explainable_ranking_prefers_listings_matching_the_strategy(self):
        near = listing("near", skills=("Python", "FastAPI"), location="Noida, India")
        far = listing("far", skills=("Python",), location="Chennai, India", work_mode="on-site")
        ranked = rank_for_strategy(PROFILE, [far, near], STRATEGY)
        self.assertEqual([item.listing_id for item in ranked], ["near", "far"])

    def test_blocked_listings_stay_in_the_order_but_are_not_ranked_by_default(self):
        blocked = listing("blocked", employer="Blocked Employer")
        good = listing("good", skills=("Python", "FastAPI"))
        ranked = rank_for_strategy(PROFILE, [blocked, good], STRATEGY)
        self.assertEqual([item.listing_id for item in ranked], ["good"],
                         "a strategy exclusion keeps a listing out of the review order")
        everything = rank_for_strategy(PROFILE, [blocked, good], STRATEGY, include_blocked=True)
        self.assertEqual(len(everything), 2)
        self.assertEqual(everything[-1].recommendation, Recommendation.BLOCKED)

    def test_a_plain_assessment_is_unchanged_by_this_feature(self):
        """The existing path must behave exactly as before: strategies are opt-in per call."""
        from career_agent.matching import _weighted_summary  # noqa: F401  (existence check)
        result = assess(PROFILE, listing())
        self.assertEqual(result.eligibility, evaluate_eligibility(PROFILE, listing()).decision,
                         "the plain path decides eligibility exactly as it always did")
        self.assertEqual(len(result.factors), 6)
        self.assertFalse(any(factor.name.startswith("strategy_") for factor in result.factors))

    def test_the_ranking_disclaimer_and_order_are_stable_between_runs(self):
        jobs = [listing(f"j{index}", skills=("Python",), location=f"City {index}") for index in range(5)]
        first = rank_for_strategy(PROFILE, jobs, STRATEGY)
        second = rank_for_strategy(PROFILE, list(reversed(jobs)), STRATEGY)
        self.assertEqual([item.listing_id for item in first], [item.listing_id for item in second],
                         "the same data produces the same order whatever order it arrives in")


if __name__ == "__main__":
    unittest.main()
