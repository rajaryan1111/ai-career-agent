"""Tests for the matching engine: what it compares, what it refuses to invent, and how it ranks.

The fixtures in ``tests/matching_fixtures.py`` cover several industries, a sparse record and a listing
that states almost nothing. The assertions are about reasoning - which listing a person should look at
first, what is reported as unknown, and that no output reads like a forecast - rather than about a score
crossing a threshold, because a threshold is exactly the thing that would quietly turn a comparison into
a promise.
"""
from __future__ import annotations

import unittest
from dataclasses import replace

from career_agent.core import Availability, CandidateProfile, JobListing, evaluate_eligibility
from career_agent.matching import (
    DISCLAIMER, FORBIDDEN_CLAIMS, Band, FactorStatus, MatchWeights, Recommendation, assess,
    assessment_to_dict, describe_ranking, normalize_skill, rank,
)
from tests.matching_fixtures import (
    ALL_CASES, DESIGN, SILENT_LISTING, SKILLS_ONLY, SOFTWARE, SPARSE, case_by_domain, listing,
)


def claims_in(text: str) -> tuple[str, ...]:
    """The forecast-like phrases a piece of text contains, ignoring the disclaimer that denies them.

    The disclaimer is the one place these words belong - it says the assessment is *not* a probability -
    so the check is applied to everything a person reads apart from that sentence.
    """
    without_disclaimer = text.casefold().replace(DISCLAIMER.casefold(), " ")
    return tuple(phrase for phrase in FORBIDDEN_CLAIMS if phrase in without_disclaimer)


class IndustryFixtureTests(unittest.TestCase):
    """Every domain fixture ranks its intended listing first, with the reasons attached."""

    def test_each_industry_reviews_its_intended_listing_first(self):
        for case in ALL_CASES:
            with self.subTest(domain=case.domain):
                results = rank(case.profile, case.listings)
                self.assertTrue(results, f"{case.domain}: nothing was ranked at all")
                self.assertEqual(results[0].listing_id, case.expected_first, case.note)

    def test_no_assessment_output_reads_like_a_prediction(self):
        for case in ALL_CASES:
            with self.subTest(domain=case.domain):
                for result in rank(case.profile, case.listings, include_blocked=True):
                    lines = result.explanation_lines()
                    text = "\n".join(lines)
                    self.assertEqual(claims_in(text), (),
                                     f"{case.domain}: a forecast-like phrase appeared in {result.listing_id}")
                    self.assertIn(DISCLAIMER, lines,
                                  "every assessment must carry the disclaimer with it")

    def test_a_fully_known_strong_match_scores_high_and_says_what_it_compared(self):
        case = SOFTWARE
        result = assess(case.profile, case.listings[0])
        factors = {factor.name: factor for factor in result.factors}

        self.assertEqual(factors["skills"].status, FactorStatus.PASS)
        self.assertEqual(factors["experience"].status, FactorStatus.PASS)
        self.assertEqual(factors["qualification"].status, FactorStatus.PASS)
        self.assertEqual(factors["location"].status, FactorStatus.PASS)
        self.assertEqual(factors["work_mode"].status, FactorStatus.PASS)
        self.assertEqual(factors["role_type"].status, FactorStatus.PASS)
        self.assertEqual(result.coverage, 1.0, "every applicable factor had a recorded value")
        self.assertEqual(result.band, Band.STRONG)
        self.assertEqual(result.recommendation, Recommendation.REVIEW)
        self.assertEqual(result.missing_skills, ())

    def test_a_listing_with_the_same_skills_but_the_wrong_side_of_the_country_loses_that_factor(self):
        case = SOFTWARE
        elsewhere = replace(case.listings[0], location_text="Berlin, Germany")
        already_evaluated = evaluate_eligibility(case.profile, elsewhere)

        result = assess(case.profile, elsewhere, eligibility=already_evaluated)

        location = next(factor for factor in result.factors if factor.name == "location")
        self.assertEqual(location.status, FactorStatus.FAIL)
        self.assertIn("Berlin", location.explanation)
        self.assertIn("preferred places", location.explanation)

    def test_an_already_decided_eligibility_is_reused_rather_than_recomputed(self):
        """The desktop evaluates eligibility once and shows the same report in both places."""
        report = evaluate_eligibility(SOFTWARE.profile, SOFTWARE.listings[0])
        without = assess(SOFTWARE.profile, SOFTWARE.listings[0])

        with_report = assess(SOFTWARE.profile, SOFTWARE.listings[0], eligibility=report)

        self.assertEqual(with_report.eligibility, report.decision)
        self.assertEqual(with_report.eligibility, without.eligibility)

    def test_a_bare_decision_is_refused_because_it_would_lose_the_failing_requirement(self):
        report = evaluate_eligibility(SOFTWARE.profile, SOFTWARE.listings[0])

        with self.assertRaises(TypeError) as caught:
            assess(SOFTWARE.profile, SOFTWARE.listings[0], eligibility=report.decision)  # type: ignore[arg-type]

        self.assertIn("EligibilityReport", str(caught.exception))


class NothingInventedTests(unittest.TestCase):
    """Missing values stay missing, and silence is never scored as agreement."""

    def test_a_listing_that_states_no_skills_has_no_skills_score_at_all(self):
        result = assess(SILENT_LISTING.profile, SILENT_LISTING.listings[0])
        skills = next(factor for factor in result.factors if factor.name == "skills")

        self.assertEqual(skills.status, FactorStatus.NOT_APPLICABLE)
        self.assertIsNone(skills.score, "silence is not a perfect score and not a zero")
        self.assertIn("does not state required skills", skills.explanation)

    def test_a_profile_with_no_recorded_skills_is_unknown_not_failing(self):
        result = assess(CandidateProfile(candidate_country="India"), SOFTWARE.listings[0])
        skills = next(factor for factor in result.factors if factor.name == "skills")

        self.assertEqual(skills.status, FactorStatus.UNKNOWN)
        self.assertIsNone(skills.score)
        self.assertIn("nothing could be compared", skills.explanation)
        self.assertIn("skills", result.unknown_inputs)

    def test_a_missing_location_requirement_is_unknown_rather_than_a_match(self):
        result = assess(SOFTWARE.profile, replace(SOFTWARE.listings[0], location_text=None))
        location = next(factor for factor in result.factors if factor.name == "location")

        self.assertEqual(location.status, FactorStatus.UNKNOWN)
        self.assertIsNone(location.score)

    def test_nothing_is_inferred_about_compensation(self):
        """The domain model records no pay, so the engine must not pretend to compare any."""
        result = assess(SOFTWARE.profile, SOFTWARE.listings[0], weights=MatchWeights())

        self.assertNotIn("compensation", [factor.name for factor in result.factors])
        self.assertNotIn("salary", " ".join(result.explanation_lines()).casefold())

    def test_a_perfect_match_on_one_known_factor_is_still_not_enough_information(self):
        """The coverage floor, which is the rule that stops a small sample looking like a good fit."""
        result = assess(SKILLS_ONLY.profile, SKILLS_ONLY.listings[0])
        skills = next(factor for factor in result.factors if factor.name == "skills")

        self.assertEqual(skills.status, FactorStatus.PASS)
        self.assertEqual(skills.score, 1.0, "the one thing that could be compared matched perfectly")
        self.assertGreater(result.score, 0.99)
        self.assertLess(result.coverage, 0.5)
        self.assertEqual(result.band, Band.INSUFFICIENT,
                         "a perfect score over a fraction of the picture is not a strong overlap")
        self.assertIn(result.recommendation,
                      (Recommendation.NEEDS_INFORMATION, Recommendation.ELIGIBILITY_UNKNOWN),
                      "the reading is 'not enough information'; eligibility is undecided for the same "
                      "reason, and neither is a recommendation to apply")
        self.assertNotEqual(result.band, Band.STRONG)
        self.assertNotEqual(result.recommendation, Recommendation.REVIEW)

    def test_the_boundary_of_the_strong_reading_is_where_the_module_says_it_is(self):
        """Two thirds of the applicable weight known, not one half: a bare majority is not 'strong'."""
        from career_agent.matching import COVERAGE_FLOOR_FOR_COMPARISON, COVERAGE_FOR_STRONG

        half_known = assess(DESIGN.profile, DESIGN.listings[0])
        self.assertAlmostEqual(half_known.coverage, 0.5, places=6)
        self.assertEqual(half_known.score, 1.0)
        self.assertEqual(half_known.band, Band.MODERATE,
                         "everything known agrees, but only half the picture is known")
        self.assertLess(COVERAGE_FLOOR_FOR_COMPARISON, COVERAGE_FOR_STRONG)

    def test_a_sparse_record_cannot_produce_a_confident_band(self):
        result = assess(SPARSE.profile, SPARSE.listings[0])

        self.assertEqual(result.coverage, 0.0)
        self.assertIsNone(result.score)
        self.assertEqual(result.band, Band.INSUFFICIENT)
        self.assertEqual(result.recommendation, Recommendation.NEEDS_INFORMATION)
        self.assertIn("Not recorded, so not compared", " ".join(result.explanation_lines()))

    def test_a_listing_stating_nothing_compared_is_never_described_as_strong(self):
        for case in (SILENT_LISTING, SPARSE):
            with self.subTest(domain=case.domain):
                result = rank(case.profile, case.listings)[0]
                self.assertNotEqual(result.band, Band.STRONG)
                self.assertNotEqual(result.recommendation, Recommendation.REVIEW)


class SkillComparisonTests(unittest.TestCase):
    """Skill comparison: spelling is folded, meaning is not."""

    def test_case_and_separators_are_the_only_things_folded(self):
        self.assertEqual(normalize_skill("Power-BI"), normalize_skill("power_bi"))
        self.assertEqual(normalize_skill("  VHDL "), "vhdl")
        self.assertNotEqual(normalize_skill("VHDL"), normalize_skill("Verilog"))
        self.assertNotEqual(normalize_skill("ML"), normalize_skill("Machine Learning"))
        self.assertIsNone(normalize_skill("   "))

    def test_missing_skills_are_reported_with_the_listings_own_spelling(self):
        job = replace(SOFTWARE.listings[0], required_skills=frozenset({"PYTHON", "Apache Airflow"}))
        result = assess(SOFTWARE.profile, job)

        self.assertEqual(result.missing_skills, ("Apache Airflow",),
                         "the listing's spelling is shown, not this module's folded form")
        self.assertEqual(result.skill_matches, ("PYTHON",))

    def test_an_alias_table_is_used_only_when_the_caller_supplies_one(self):
        job = replace(SOFTWARE.listings[0], required_skills=frozenset({"Postgres"}))

        without = assess(SOFTWARE.profile, job)
        with_aliases = assess(SOFTWARE.profile, job, skill_aliases={"postgres": "PostgreSQL"})

        self.assertEqual(without.missing_skills, ("Postgres",),
                         "no equivalence is invented by default")
        self.assertEqual(with_aliases.missing_skills, ())
        self.assertEqual(with_aliases.skill_matches, ("Postgres",))

    def test_a_partial_skill_match_scores_the_share_that_is_covered(self):
        job = replace(SOFTWARE.listings[0],
                      required_skills=frozenset({"Python", "SQL", "Kubernetes", "Terraform"}))
        skills = next(factor for factor in assess(SOFTWARE.profile, job).factors if factor.name == "skills")

        self.assertEqual(skills.status, FactorStatus.PARTIAL)
        self.assertEqual(skills.score, 0.5)
        self.assertIn("2 of 4", skills.explanation)


class ExperienceAndQualificationTests(unittest.TestCase):
    """Range comparisons report both sides, and a range is not a requirement about a person's worth."""

    def experience_factor(self, job: JobListing, profile: CandidateProfile):
        return next(factor for factor in assess(profile, job).factors if factor.name == "experience")

    def test_below_the_stated_minimum_is_a_failure_with_the_gap(self):
        factor = self.experience_factor(SOFTWARE.listings[2], SOFTWARE.profile)

        self.assertEqual(factor.status, FactorStatus.FAIL)
        self.assertIn("at least 10", factor.explanation)
        self.assertIn("short", factor.explanation)

    def test_above_the_stated_maximum_is_reported_as_beyond_the_range_not_as_a_match(self):
        job = replace(SOFTWARE.listings[0], minimum_experience_years=0.0, maximum_experience_years=0.0)
        factor = self.experience_factor(job, SOFTWARE.profile)

        self.assertEqual(factor.status, FactorStatus.PARTIAL)
        self.assertIn("at most 0", factor.explanation)

    def test_a_listing_with_no_range_compares_nothing(self):
        job = replace(SOFTWARE.listings[0], minimum_experience_years=None, maximum_experience_years=None)
        factor = self.experience_factor(job, SOFTWARE.profile)

        self.assertEqual(factor.status, FactorStatus.NOT_APPLICABLE)
        self.assertIsNone(factor.score)

    def test_a_non_finite_experience_value_never_passes_a_requirement(self):
        """The same rule the eligibility checker enforces: ``nan`` cannot satisfy a minimum."""
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value):
                profile = replace(SOFTWARE.profile, experience_years=value)
                factor = self.experience_factor(SOFTWARE.listings[0], profile)

                self.assertEqual(factor.status, FactorStatus.UNKNOWN)
                self.assertIsNone(factor.score)
                self.assertIn("not a usable number", factor.explanation)

    def test_a_qualification_requirement_the_profile_contradicts_is_a_failure_not_a_pass(self):
        job = replace(SOFTWARE.listings[0], allowed_degree_disciplines=("Mechanical Engineering",),
                      allowed_study_statuses=None, allowed_graduation_years=None)
        factor = next(factor for factor in assess(SOFTWARE.profile, job).factors
                      if factor.name == "qualification")

        self.assertEqual(factor.status, FactorStatus.FAIL)
        self.assertIn("not matching", factor.explanation)
        self.assertIn("Mechanical Engineering", factor.explanation)

    def test_a_qualification_requirement_nothing_is_recorded_against_is_unknown(self):
        job = replace(SOFTWARE.listings[0], allowed_degree_disciplines=("Computer Science",),
                      allowed_study_statuses=("undergraduate",), allowed_graduation_years=(2027,))
        unknown_profile = replace(SOFTWARE.profile, degree_discipline=None, study_status=None,
                                  graduation_year=None)

        factor = next(factor for factor in assess(unknown_profile, job).factors
                      if factor.name == "qualification")

        self.assertEqual(factor.status, FactorStatus.UNKNOWN)
        self.assertIsNone(factor.score)
        self.assertIn("nothing could be compared", factor.explanation)

    def test_a_partly_recorded_qualification_reports_both_halves(self):
        job = replace(SOFTWARE.listings[0], allowed_degree_disciplines=("Mechanical Engineering",))
        factor = next(factor for factor in assess(SOFTWARE.profile, job).factors
                      if factor.name == "qualification")

        self.assertEqual(factor.status, FactorStatus.PARTIAL,
                         "the discipline does not match while the study status and year do")
        self.assertIn("not matching: degree discipline", factor.explanation)

    def test_a_listing_that_names_no_qualification_compares_nothing(self):
        job = replace(SOFTWARE.listings[0], allowed_degree_disciplines=None,
                      allowed_study_statuses=None, allowed_graduation_years=None)
        factor = next(factor for factor in assess(SOFTWARE.profile, job).factors
                      if factor.name == "qualification")

        self.assertEqual(factor.status, FactorStatus.NOT_APPLICABLE)


class WeightTests(unittest.TestCase):
    """Weights are the person's priorities, and changing them changes the order predictably."""

    def test_weights_must_be_numbers_and_not_all_zero(self):
        with self.assertRaises(ValueError):
            MatchWeights(skills=True)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            MatchWeights(skills=-1)
        with self.assertRaises(ValueError):
            MatchWeights(skills=0, experience=0, qualification=0, location=0, work_mode=0, role_type=0)

    def test_a_zero_weight_removes_a_factor_from_the_score_entirely(self):
        job = replace(SOFTWARE.listings[0], location_text="Berlin, Germany")
        balanced = assess(SOFTWARE.profile, job)
        ignore_location = assess(SOFTWARE.profile, job,
                                 weights=MatchWeights(location=0.0))

        self.assertGreater(ignore_location.score, balanced.score,
                           "a factor weighted zero must not hold the score down")
        self.assertEqual([factor.name for factor in ignore_location.factors],
                         [factor.name for factor in balanced.factors],
                         "the factor is still reported, just not counted")
        self.assertIn("weights:", ignore_location.weights.describe())
        self.assertNotIn("location", ignore_location.weights.describe())

    def test_priorities_can_change_which_listing_is_reviewed_first(self):
        strong_skills_far_away = replace(SOFTWARE.listings[0], listing_id="far",
                                         location_text="Pune, India")
        weak_skills_nearby = replace(SOFTWARE.listings[1], listing_id="near",
                                     location_text="Bengaluru, India")
        listings = (strong_skills_far_away, weak_skills_nearby)

        skills_first = rank(SOFTWARE.profile, listings)[0].listing_id
        location_first = rank(SOFTWARE.profile, listings,
                              weights=MatchWeights(skills=0.0, experience=0.0, qualification=0.0,
                                                   location=10.0, work_mode=1.0, role_type=1.0))[0].listing_id

        self.assertEqual(skills_first, "far")
        self.assertEqual(location_first, "near",
                         "when location is the priority, the nearby listing is the one to look at")


class PreferenceMismatchTests(unittest.TestCase):
    """A listing that contradicts a recorded preference is a failure, not a neutral unknown."""

    def test_a_work_mode_the_person_ruled_out_is_scored_as_a_mismatch(self):
        profile = replace(SOFTWARE.profile, preferred_work_modes=frozenset({"remote"}))
        onsite = replace(SOFTWARE.listings[0], work_mode="onsite")
        remote = replace(SOFTWARE.listings[0], work_mode="remote")

        onsite_factor = next(factor for factor in assess(profile, onsite).factors
                             if factor.name == "work_mode")
        remote_result = assess(profile, remote)

        self.assertEqual(onsite_factor.status, FactorStatus.FAIL)
        self.assertEqual(onsite_factor.score, 0.0)
        self.assertIn("onsite", onsite_factor.explanation)
        self.assertIn("not among your preferred", onsite_factor.explanation)
        self.assertLess(assess(profile, onsite).score, remote_result.score,
                        "a mismatch must lower the reading, not leave it unchanged")

    def test_a_role_type_the_person_ruled_out_is_scored_as_a_mismatch(self):
        profile = replace(SOFTWARE.profile, preferred_role_types=frozenset({"internship"}))
        permanent = replace(SOFTWARE.listings[0], role_type="full_time")

        factor = next(factor for factor in assess(profile, permanent).factors
                      if factor.name == "role_type")

        self.assertEqual(factor.status, FactorStatus.FAIL)
        self.assertEqual(factor.score, 0.0)
        self.assertIn("full_time", factor.explanation)
        self.assertIn("internship", factor.explanation, "the preference is shown beside the listing")

    def test_a_listing_that_states_none_of_these_is_unknown_rather_than_a_mismatch(self):
        job = replace(SOFTWARE.listings[0], work_mode=None, role_type=None)

        statuses = {factor.name: factor.status for factor in assess(SOFTWARE.profile, job).factors}

        self.assertEqual(statuses["work_mode"], FactorStatus.UNKNOWN)
        self.assertEqual(statuses["role_type"], FactorStatus.UNKNOWN)


class EligibilityGateTests(unittest.TestCase):
    """Overlap never overrules eligibility, and an undecided case is not rounded to a yes."""

    def test_a_failing_requirement_blocks_the_recommendation_but_keeps_the_comparison(self):
        job = replace(SOFTWARE.listings[0], eligible_countries=("Germany",))
        result = assess(SOFTWARE.profile, job)

        self.assertEqual(result.eligibility.value, "fail")
        self.assertEqual(result.recommendation, Recommendation.BLOCKED)
        self.assertIsNotNone(result.score, "the comparison is still shown: blocking is not hiding")
        self.assertIn("not recommended", " ".join(result.notes))
        self.assertIn("country", " ".join(result.notes),
                      "the failing requirement is named, so the refusal can be checked")

    def test_an_undecided_eligibility_is_reported_as_undecided(self):
        job = replace(SOFTWARE.listings[0], availability_status=Availability.UNKNOWN,
                      required_skills=frozenset())
        result = assess(SOFTWARE.profile, job)

        self.assertEqual(result.eligibility.value, "unknown")
        self.assertEqual(result.recommendation, Recommendation.ELIGIBILITY_UNKNOWN)
        self.assertIn("could not be decided", " ".join(result.notes))

    def test_blocked_listings_are_excluded_from_the_default_order_but_available_on_request(self):
        blocked = replace(SOFTWARE.listings[0], listing_id="blocked", eligible_countries=("Germany",))
        listings = (*SOFTWARE.listings, blocked)

        default = rank(SOFTWARE.profile, listings)
        everything = rank(SOFTWARE.profile, listings, include_blocked=True)

        self.assertNotIn("blocked", [result.listing_id for result in default])
        self.assertIn("blocked", [result.listing_id for result in everything])
        blocked_result = next(item for item in everything if item.listing_id == "blocked")
        self.assertEqual(blocked_result.recommendation, Recommendation.BLOCKED)
        self.assertIsNotNone(blocked_result.score, "excluding it from the order does not hide it")


class RankingTests(unittest.TestCase):
    """The order is stable, explainable, and prefers the better-known listing over the barely-known one."""

    def test_a_listing_that_could_not_be_compared_never_outranks_one_that_was(self):
        thorough = SOFTWARE.listings[0]
        thin = replace(SOFTWARE.listings[0], listing_id="thin",
                       required_skills=frozenset(), minimum_experience_years=None,
                       maximum_experience_years=None, allowed_degree_disciplines=None,
                       allowed_study_statuses=None, allowed_graduation_years=None,
                       work_mode=None, role_type=None, location_text=None)

        order = rank(SOFTWARE.profile, (thin, thorough))

        self.assertEqual([result.listing_id for result in order], [thorough.listing_id, "thin"])
        self.assertLess(order[0].rank_key[0], order[1].rank_key[0],
                        "the two are in different groups of the order, not merely different numbers")

    def test_the_order_does_not_depend_on_the_order_the_listings_arrive_in(self):
        first = rank(SOFTWARE.profile, SOFTWARE.listings)
        second = rank(SOFTWARE.profile, tuple(reversed(SOFTWARE.listings)))

        self.assertEqual([result.listing_id for result in first],
                         [result.listing_id for result in second])

    def test_two_identical_listings_are_ordered_by_their_ids_so_the_result_is_stable(self):
        one = replace(SOFTWARE.listings[0], listing_id="a-copy")
        two = replace(SOFTWARE.listings[0], listing_id="b-copy")

        self.assertEqual([result.listing_id for result in rank(SOFTWARE.profile, (two, one))],
                         ["a-copy", "b-copy"])

    def test_the_ranking_lines_carry_the_number_and_the_caveat_together(self):
        lines = describe_ranking(rank(SOFTWARE.profile, SOFTWARE.listings))
        text = "\n".join(lines)

        self.assertIn("not a prediction", text)
        self.assertIn("of the applicable weight known", text)
        self.assertTrue(text.startswith(DISCLAIMER))

    def test_an_empty_list_of_listings_ranks_nothing_rather_than_failing(self):
        self.assertEqual(rank(SOFTWARE.profile, ()), ())


class ReportShapeTests(unittest.TestCase):
    """The assessment converts to plain data without losing what it refuses to claim."""

    def test_the_dict_carries_the_factors_the_unknowns_and_the_disclaimer(self):
        payload = assessment_to_dict(assess(DESIGN.profile, DESIGN.listings[0]))

        self.assertEqual(payload["listing_id"], "design-remote")
        self.assertEqual(payload["disclaimer"], DISCLAIMER)
        self.assertEqual(sorted(factor["name"] for factor in payload["factors"]),
                         ["experience", "location", "qualification", "role_type", "skills", "work_mode"])
        self.assertEqual(claims_in(str(payload)), ())

    def test_a_factor_that_could_not_be_compared_never_carries_a_score(self):
        payload = assessment_to_dict(assess(SPARSE.profile, SPARSE.listings[0]))

        for factor in payload["factors"]:
            if factor["status"] in ("unknown", "not_applicable"):
                self.assertIsNone(factor["score"])

    def test_every_case_names_a_recommendation_that_is_one_of_the_defined_ones(self):
        for case in ALL_CASES:
            for result in rank(case.profile, case.listings, include_blocked=True):
                with self.subTest(domain=case.domain, listing=result.listing_id):
                    self.assertIsInstance(result.recommendation, Recommendation)
                    self.assertRegex(result.rank_key[3], r"^[A-Za-z0-9._-]+$")


class NormalisationTests(unittest.TestCase):
    """Case and separator folding is the whole of the normalisation, stated as tests."""

    def test_location_folding_matches_the_words_that_are_there(self):
        profile = replace(SOFTWARE.profile, preferred_locations=frozenset({"bengaluru india"}))
        job = replace(SOFTWARE.listings[0], location_text="Bengaluru, India")
        factor = next(factor for factor in assess(profile, job).factors if factor.name == "location")

        self.assertEqual(factor.status, FactorStatus.PASS)

    def test_a_city_is_not_treated_as_its_country_or_the_other_way_round(self):
        profile = replace(SOFTWARE.profile, preferred_locations=frozenset({"India"}))
        job = replace(SOFTWARE.listings[0], location_text="Bengaluru, India")
        factor = next(factor for factor in assess(profile, job).factors if factor.name == "location")

        self.assertEqual(factor.status, FactorStatus.PASS,
                         "the listing text contains the preferred place, which is a word match")

        distant = replace(SOFTWARE.listings[0], location_text="Berlin, Germany")
        distant_factor = next(factor for factor in assess(profile, distant).factors
                              if factor.name == "location")
        self.assertEqual(distant_factor.status, FactorStatus.FAIL)


if __name__ == "__main__":  # pragma: no cover - convenience for running this file alone
    unittest.main()
