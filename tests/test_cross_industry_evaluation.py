"""Tests for the Phase 4 cross-industry evaluation corpus and its harness.

The corpus is an artefact a person reviews and the harness is the thing that measures with it, so both are
tested here: the corpus must stay well-formed, synthetic and fully ranked, and the harness must keep
reporting zero hard-eligibility violations, run its stated extraction rules in both directions, and let the
documented non-coverage rules stay documented rather than quietly becoming inferred values.

This is not a second copy of the matching tests: those assert reasoning about individual factors, while
these assert that the *measurement* over seven occupation groups stays available and honest.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts.evaluate_cross_industry import (
    DEFAULT_CORPUS, PROPOSED_THRESHOLDS, CorpusError, load_corpus, summarise,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class CorpusIntegrityTests(unittest.TestCase):
    """The corpus is the standard being measured against, so a broken one must never look like a pass."""

    @classmethod
    def setUpClass(cls):
        cls.path = REPOSITORY_ROOT / DEFAULT_CORPUS
        cls.corpus = load_corpus(cls.path)

    def test_it_covers_the_occupation_groups_phase_4_names(self):
        domains = {group["id"] for group in self.corpus["groups"]}
        self.assertEqual(
            domains,
            {"software-data", "vlsi-embedded", "mechanical", "civil", "product-design",
             "business-analysis", "laboratory-biotech"},
        )

    def test_every_group_states_a_complete_review_order(self):
        """A rank that is missing or repeated would make "which should be opened first" ambiguous."""
        for group in self.corpus["groups"]:
            with self.subTest(group=group["id"]):
                ranks = sorted(listing["review_rank"] for listing in group["listings"])
                self.assertEqual(ranks, list(range(1, len(group["listings"]) + 1)))
                self.assertGreaterEqual(len(group["listings"]), 3)

    def test_every_value_is_synthetic_and_unreachable(self):
        """Privacy is a property of the corpus, not a promise: check the URLs and the contact details."""
        text = self.path.read_text(encoding="utf-8")
        for forbidden in ("@gmail.com", "@yahoo.", "@outlook.", "@hotmail."):
            self.assertNotIn(forbidden, text, "a real mailbox domain must never appear in the corpus")
        for url in re.findall(r"https?://[^\s\"]+", text):
            self.assertRegex(url, r"^https://(jobs|www)\.example(\.com)?/", f"unreachable host expected, got {url}")
        for group in self.corpus["groups"]:
            for listing in group["listings"]:
                self.assertIn("(synthetic)", listing["employer_name"])
        self.assertIn("invented", self.corpus["privacy_note"])
        self.assertIn("reserved example domains", self.corpus["privacy_note"])

    def test_a_malformed_corpus_is_refused_rather_than_measured(self):
        for name, payload in (
            ("not JSON at all", "{oops"),
            ("no groups", json.dumps({"corpus_version": 1})),
            ("a group missing its listings", json.dumps({"groups": [{"id": "x", "label": "X", "profile": {}, "resume": {}}]})),
        ):
            with self.subTest(case=name):
                temporary = REPOSITORY_ROOT / "tests" / f".corpus-{name.split()[0]}.json"
                temporary.write_text("{\"groups\": []}" if name == "not JSON at all" else payload, encoding="utf-8")
                self.addCleanup(temporary.unlink)
                with self.assertRaises(CorpusError):
                    load_corpus(temporary)


class MeasurementTests(unittest.TestCase):
    """What the harness measures, and the rules it must keep measuring in both directions."""

    @classmethod
    def setUpClass(cls):
        cls.report = summarise(load_corpus(REPOSITORY_ROOT / DEFAULT_CORPUS))

    def test_no_listing_the_rules_block_is_ever_offered(self):
        """The one number that must be zero, checked independently of the ranking."""
        self.assertEqual(self.report["violations"], [])
        self.assertEqual(self.report["measurements"]["hard_eligibility_violations"]["count"], 0)
        self.assertEqual(PROPOSED_THRESHOLDS["hard_eligibility_violations"], 0)

    def test_every_group_offers_a_listing_and_blocked_ones_are_named(self):
        for group in self.report["groups"]:
            with self.subTest(group=group["id"]):
                self.assertTrue(group["engine_order"], "a group with no offered listing means nothing was ranked")
                self.assertEqual(len(group["blocked"]), 1, "each group has exactly one ineligible listing")

    def test_the_engine_agrees_with_the_reviewed_order_and_the_number_is_stated(self):
        """The measurement is reported with its denominator; it is not asserted to be perfect forever."""
        agreement = self.report["measurements"]["top_ranked_agreement"]
        self.assertEqual(agreement["groups"], 7)
        self.assertGreaterEqual(
            agreement["value"], PROPOSED_THRESHOLDS["top_ranked_precision"],
            "on this corpus the engine must clear the threshold phases.md proposes, or the shortfall is a finding",
        )

    def test_the_documented_extraction_rules_still_hold_in_both_directions(self):
        checks = {check["name"]: check for check in self.report["rule_checks"]}
        self.assertEqual(len(checks), 3)
        self.assertTrue(checks["a labelled country line yields the country"]["proposed"])
        self.assertTrue(checks["a labelled location line yields the country"]["proposed"])
        self.assertFalse(
            checks["a bare city line does not yield a country"]["proposed"],
            "the conservative country rule is deliberate: inferring it would let a city decide eligibility",
        )
        for check in self.report["rule_checks"]:
            self.assertTrue(check["pass"], f"{check['name']}: {check}")

    def test_documented_non_coverage_is_counted_separately_from_accuracy(self):
        """A value the extractor does not claim must not be able to inflate the accuracy figure."""
        accuracy = self.report["measurements"]["critical_field_extraction_accuracy"]
        documented = self.report["measurements"]["documented_non_coverage"]
        self.assertGreater(documented["count"], 0, "the corpus records values outside what is claimed")
        self.assertEqual(documented["rules_holding"], documented["count"])
        self.assertEqual(accuracy["checks"], sum(len(item["checks"]) for item in self.report["resumes"]))
        self.assertEqual(
            accuracy["passed"], sum(len(item["checks"]) for item in self.report["resumes"]),
            "on this corpus every stated value is extracted; a miss is a finding to report, not to hide",
        )

    def test_compensation_is_never_compared_because_the_model_has_no_such_field(self):
        for group in self.report["groups"]:
            with self.subTest(group=group["id"]):
                self.assertFalse(group["group_compares_compensation"])

    def test_the_report_states_what_it_does_not_establish(self):
        caveats = " ".join(self.report["caveats"]).casefold()
        self.assertIn("synthetic", caveats)
        self.assertIn("not with hiring outcomes", caveats)
        self.assertIn("seven résumés", caveats)


if __name__ == "__main__":
    unittest.main()
