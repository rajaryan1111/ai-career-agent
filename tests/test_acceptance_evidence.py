"""Tests for the written requirements a route must meet before it could ever be enabled.

This module is data, so the tests are about the properties that make the data worth having: every
named platform is covered, nothing is ready, a route cannot quietly drop a requirement, the four
capabilities stay independently gated, and the honest statement about circumvention is not just a
sentence in a README.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from career_agent.acceptance_evidence import (
    BASELINE, EVIDENCE_LABELS, EvidenceError, EvidenceKind, ROUTE_REQUIREMENTS, RouteRequirement,
    describe_all, describe_route, get_route, held_evidence, outstanding, route_is_ready,
)
from career_agent.sources import SOURCE_DECISIONS, enabled_discovery_sources


class CoverageTests(unittest.TestCase):
    def test_every_platform_the_roadmap_names_has_requirements(self):
        covered = {route.route_id for route in ROUTE_REQUIREMENTS}
        for route_id in ("linkedin", "unstop", "internshala", "naukri", "employer_site",
                         "ats_provider"):
            with self.subTest(route=route_id):
                self.assertIn(route_id, covered)

    def test_every_requirement_kind_has_a_label_somebody_could_act_on(self):
        for kind in EvidenceKind:
            with self.subTest(kind=kind):
                self.assertIn(kind, EVIDENCE_LABELS)
                self.assertGreater(len(EVIDENCE_LABELS[kind]), 40)

    def test_a_route_states_why_it_is_listed(self):
        for route in ROUTE_REQUIREMENTS:
            with self.subTest(route=route.route_id):
                self.assertTrue(route.notes.strip())
                self.assertTrue(route.capabilities)

    def test_a_near_miss_is_not_a_permission(self):
        self.assertIsNone(get_route("LinkedIn Jobs"))
        self.assertIsNone(get_route(""))
        self.assertIsNotNone(get_route("  LINKEDIN "))


class NothingIsReadyTests(unittest.TestCase):
    def test_no_evidence_is_held_for_any_route(self):
        for route in ROUTE_REQUIREMENTS:
            with self.subTest(route=route.route_id):
                self.assertEqual(held_evidence(route.route_id), ())

    def test_every_route_is_outstanding_on_everything(self):
        for route in ROUTE_REQUIREMENTS:
            with self.subTest(route=route.route_id):
                self.assertEqual(outstanding(route.route_id), route.kinds)
                self.assertFalse(route_is_ready(route.route_id))

    def test_an_unknown_route_raises_rather_than_reporting_nothing_outstanding(self):
        for call in (held_evidence, outstanding, describe_route):
            with self.subTest(call=call.__name__), self.assertRaises(EvidenceError):
                call("some-new-board")

    def test_a_route_may_add_requirements_but_never_drop_one(self):
        with self.assertRaises(EvidenceError):
            RouteRequirement(route_id="x", display_name="X", notes="n",
                             kinds=(EvidenceKind.PERMISSION_BASIS,))
        added = RouteRequirement(route_id="x", display_name="X", notes="n",
                                 kinds=BASELINE + (EvidenceKind.HUMAN_VERIFICATION,))
        self.assertIn(EvidenceKind.HUMAN_VERIFICATION, added.kinds)

    def test_a_route_without_a_reason_cannot_be_written_down(self):
        with self.assertRaises(EvidenceError):
            RouteRequirement(route_id="x", display_name="X", notes="   ")


class HonestyTests(unittest.TestCase):
    def test_circumvention_is_a_requirement_to_rule_out_not_a_hope(self):
        self.assertIn("no CAPTCHA solving", EVIDENCE_LABELS[EvidenceKind.NO_CIRCUMVENTION])
        self.assertIn("no OTP interception", EVIDENCE_LABELS[EvidenceKind.NO_CIRCUMVENTION])

    def test_a_permission_basis_cannot_be_inferred_from_silence(self):
        self.assertIn("never an inference from silence",
                      EVIDENCE_LABELS[EvidenceKind.PERMISSION_BASIS])

    def test_a_passing_test_suite_is_not_human_verification(self):
        self.assertIn("not a passing test suite",
                      EVIDENCE_LABELS[EvidenceKind.HUMAN_VERIFICATION])

    def test_the_summary_says_the_capabilities_are_gated_separately(self):
        text = "\n".join(describe_all())
        self.assertIn("independently gated", text)
        self.assertIn("0 are ready", text)

    def test_the_requirements_do_not_describe_any_source_as_enabled(self):
        self.assertEqual(enabled_discovery_sources(), (),
                         "writing down what evidence would be needed must not enable anything")
        reviewed = {decision.source_id for decision in SOURCE_DECISIONS}
        self.assertNotIn("linkedin", reviewed,
                         "a route with requirements is not a reviewed, selected source")

    def test_describing_a_route_lists_what_is_missing(self):
        lines = describe_route("internshala")
        text = "\n".join(lines)
        self.assertIn("Outstanding: 9 of 9", text)
        self.assertIn("submission", text)
        self.assertIn("no credential is stored by this project today", text)


class CommandTests(unittest.TestCase):
    def test_the_command_prints_the_routes_and_enables_nothing(self):
        result = subprocess.run(
            [sys.executable, "-m", "career_agent", "--acceptance-evidence"],
            capture_output=True, text=True, timeout=120,
            cwd=str(Path(__file__).resolve().parents[1]))
        self.assertEqual(result.returncode, 0, result.stderr)
        for expected in ("LinkedIn", "Naukri.com", "Unstop", "Internshala",
                         "0 are ready", "switches anything on"):
            with self.subTest(expected=expected):
                self.assertIn(expected, result.stdout)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
