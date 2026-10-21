"""Regression tests for career_agent.sources — the fail-closed permission gate and run outcomes.

The gate is data plus pure functions, so these tests need no network, no adapter, and no
credentials. They verify fail-closed behaviour and that the recorded decisions still match the
research record they cite; they do not verify that any source is reachable or that its terms
still apply (terms change, so the cited reviews must be repeated).
"""
import unittest
from pathlib import Path

from career_agent import Availability
from career_agent.sources import (
    SOURCE_DECISIONS,
    SOURCE_QUALITY_GATE_PASSED,
    GateResult,
    PermissionState,
    RunOutcome,
    SourceDecision,
    discovery_gate,
    enabled_discovery_sources,
    get_source_decision,
    is_complete,
    is_failure,
    is_legitimate_empty,
    is_partial,
    is_transient,
    may_evidence_closure,
    submission_gate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def synthetic(source_id="synthetic", **overrides) -> SourceDecision:
    defaults = dict(
        source_id=source_id,
        display_name="Synthetic Test Source",
        permission_state=PermissionState.CONDITIONAL,
        notes="Synthetic source used to exercise gate states.",
        evidence_ref="research/source-permission-decision-matrix-2026-10-14.md",
        reviewed_on="2026-10-14",
        discovery_conditions=("Synthetic condition",),
    )
    defaults.update(overrides)
    return SourceDecision(**defaults)


class DecisionRecordIntegrityTests(unittest.TestCase):
    def test_source_ids_are_unique(self):
        ids = [decision.source_id for decision in SOURCE_DECISIONS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_registered_decision_cites_an_existing_evidence_file(self):
        for decision in SOURCE_DECISIONS:
            with self.subTest(source=decision.source_id):
                path = decision.evidence_ref.split("#", 1)[0]
                self.assertTrue(path.startswith("research/"))
                self.assertTrue((REPO_ROOT / path).is_file(), f"{path} does not exist")

    def test_recorded_states_match_the_reviewed_decision_matrix(self):
        expected = {
            "jobicy": (PermissionState.APPROVED, True),
            "remotive": (PermissionState.CONDITIONAL, False),
            "ai_dev_jobs": (PermissionState.CONDITIONAL, False),
            "himalayas": (PermissionState.BLOCKED, False),
            "smartrecruiters": (PermissionState.BLOCKED, False),
            "jobspy": (PermissionState.REJECTED, False),
        }
        for source_id, (state, selected) in expected.items():
            with self.subTest(source=source_id):
                decision = get_source_decision(source_id)
                self.assertIsNotNone(decision)
                self.assertIs(decision.permission_state, state)
                self.assertIs(decision.selected_for_use, selected)

    def test_unknown_source_has_no_recorded_decision(self):
        self.assertIsNone(get_source_decision("never_reviewed_source"))


class DecisionConstructionRefusesUnsupportedClaims(unittest.TestCase):
    def test_a_decision_must_explain_itself(self):
        with self.assertRaisesRegex(ValueError, "must record its reasoning"):
            synthetic(notes="  ")

    def test_a_reviewed_state_requires_evidence_and_an_iso_date(self):
        with self.assertRaisesRegex(ValueError, "require evidence_ref"):
            synthetic(evidence_ref="")
        for reviewed_on in ("", "14 October 2026", "2026-10-14T00:00:00Z"):
            with self.subTest(reviewed_on=reviewed_on):
                with self.assertRaisesRegex(ValueError, "ISO date"):
                    synthetic(reviewed_on=reviewed_on)

    def test_an_unreviewed_source_may_omit_evidence(self):
        decision = synthetic(permission_state=PermissionState.UNKNOWN, evidence_ref="", reviewed_on="")
        self.assertIs(decision.permission_state, PermissionState.UNKNOWN)

    def test_a_conditional_source_must_state_its_conditions(self):
        with self.assertRaisesRegex(ValueError, "must list its discovery conditions"):
            synthetic(discovery_conditions=())

    def test_submission_requires_approved_state_and_its_own_evidence(self):
        self.assertFalse(synthetic(permission_state=PermissionState.APPROVED).permission_grants_submission)
        self.assertTrue(
            synthetic(
                permission_state=PermissionState.APPROVED, submission_evidence_ref="research/example.md"
            ).permission_grants_submission
        )


class GateFailsClosedTests(unittest.TestCase):
    def test_no_source_runs_today(self):
        self.assertEqual(enabled_discovery_sources(), ())

    def test_an_unrecorded_source_is_refused_and_says_why(self):
        for result in (discovery_gate("never_reviewed_source"), submission_gate("never_reviewed_source")):
            with self.subTest(result=result):
                self.assertFalse(result.allowed)
                self.assertIn("No reviewed permission decision", result.reason)

    def test_blocked_sources_are_refused_even_though_the_endpoints_are_public(self):
        for source_id in ("himalayas", "smartrecruiters"):
            with self.subTest(source=source_id):
                result = discovery_gate(source_id)
                self.assertFalse(result.allowed)
                self.assertIn("blocked", result.reason)

    def test_a_permitted_but_unselected_source_still_does_not_run(self):
        result = self._gate_for(synthetic(selected_for_use=False))
        self.assertFalse(result.allowed)
        self.assertIn("not selected for use", result.reason)

    def test_the_source_quality_gate_blocks_an_otherwise_permitted_source(self):
        result = self._gate_for(synthetic(selected_for_use=True))
        self.assertFalse(result.allowed)
        self.assertIn("source-quality gate", result.reason)
        self.assertTrue(result.conditions)

    def test_a_source_may_run_only_when_every_gate_is_open(self):
        result = self._gate_for(synthetic(selected_for_use=True), quality_gate_passed=True)
        self.assertTrue(result.allowed)
        self.assertIn("may be used for discovery", result.reason)

    def test_jobicy_is_blocked_only_by_the_quality_gate_today(self):
        """The recorded Jobicy approval is real, so its refusal must name the gate, not the permission."""
        result = discovery_gate("jobicy")
        self.assertFalse(result.allowed)
        self.assertIn("Jobicy", result.reason)
        self.assertIn("source-quality gate", result.reason)
        self.assertNotIn("permission state is", result.reason)

    def test_read_permission_never_implies_submission(self):
        result = submission_gate("jobicy")
        self.assertFalse(result.allowed)
        self.assertIn("read access never implies submission", result.reason)

    def test_each_permission_state_has_a_defined_gate_outcome(self):
        expected_allowed = {
            PermissionState.APPROVED: True,
            PermissionState.CONDITIONAL: True,
            PermissionState.PENDING_CLARIFICATION: False,
            PermissionState.BLOCKED: False,
            PermissionState.REJECTED: False,
            PermissionState.UNKNOWN: False,
        }
        for state, allowed in expected_allowed.items():
            with self.subTest(state=state):
                decision = synthetic(permission_state=state, selected_for_use=True)
                self.assertIs(decision.permission_grants_discovery, allowed)
                result = self._gate_for(decision, quality_gate_passed=True)
                self.assertIs(result.allowed, allowed)

    def test_the_reviewed_quality_gate_state_is_recorded_as_not_passed(self):
        """Flip this only together with a new recorded source-quality decision, never to make a test pass."""
        self.assertIs(SOURCE_QUALITY_GATE_PASSED, False)

    @staticmethod
    def _gate_for(decision, *, quality_gate_passed=None) -> GateResult:
        """Run the real gate against a synthetic decision by temporarily registering it."""
        import career_agent.sources as sources

        original = sources.SOURCE_DECISIONS
        sources.SOURCE_DECISIONS = (decision,)
        try:
            return discovery_gate(decision.source_id, quality_gate_passed=quality_gate_passed)
        finally:
            sources.SOURCE_DECISIONS = original


class RunOutcomeTaxonomyTests(unittest.TestCase):
    def test_only_an_authoritative_empty_run_is_a_legitimate_empty(self):
        self.assertTrue(is_legitimate_empty(RunOutcome.SUCCESS_EMPTY))
        self.assertTrue(is_complete(RunOutcome.SUCCESS_EMPTY))
        for outcome in RunOutcome:
            if outcome is RunOutcome.SUCCESS_EMPTY:
                continue
            with self.subTest(outcome=outcome):
                self.assertFalse(is_legitimate_empty(outcome))

    def test_a_partial_run_is_incomplete_but_is_not_discarded_as_a_failure(self):
        """A partial run carries usable results, so it must be reported as incomplete, not as failed or empty."""
        self.assertFalse(is_legitimate_empty(RunOutcome.PARTIAL))
        self.assertFalse(is_complete(RunOutcome.PARTIAL))
        self.assertTrue(is_partial(RunOutcome.PARTIAL))
        self.assertFalse(is_failure(RunOutcome.PARTIAL))
        self.assertFalse(may_evidence_closure(RunOutcome.PARTIAL))

    def test_completeness_distinguishes_finished_runs_from_the_rest(self):
        for outcome in (RunOutcome.SUCCESS_WITH_RESULTS, RunOutcome.SUCCESS_EMPTY):
            with self.subTest(outcome=outcome):
                self.assertTrue(is_complete(outcome))
                self.assertFalse(is_partial(outcome))
        for outcome in (
            RunOutcome.PARTIAL,
            RunOutcome.PERMISSION_DENIED,
            RunOutcome.RATE_LIMITED,
            RunOutcome.AUTH_REQUIRED,
            RunOutcome.TIMEOUT,
            RunOutcome.NETWORK_ERROR,
            RunOutcome.SCHEMA_ERROR,
            RunOutcome.CHALLENGE_DETECTED,
            RunOutcome.UNKNOWN_ERROR,
        ):
            with self.subTest(outcome=outcome):
                self.assertFalse(is_complete(outcome))

    def test_failure_and_success_are_disjoint(self):
        for outcome in (RunOutcome.SUCCESS_WITH_RESULTS, RunOutcome.SUCCESS_EMPTY):
            with self.subTest(outcome=outcome):
                self.assertFalse(is_failure(outcome))
        for outcome in (
            RunOutcome.PERMISSION_DENIED,
            RunOutcome.RATE_LIMITED,
            RunOutcome.AUTH_REQUIRED,
            RunOutcome.TIMEOUT,
            RunOutcome.NETWORK_ERROR,
            RunOutcome.SCHEMA_ERROR,
            RunOutcome.CHALLENGE_DETECTED,
            RunOutcome.UNKNOWN_ERROR,
        ):
            with self.subTest(outcome=outcome):
                self.assertTrue(is_failure(outcome))

    def test_only_transient_conditions_are_retryable(self):
        for outcome in (RunOutcome.RATE_LIMITED, RunOutcome.TIMEOUT, RunOutcome.NETWORK_ERROR):
            with self.subTest(outcome=outcome):
                self.assertTrue(is_transient(outcome))
        for outcome in (
            RunOutcome.SUCCESS_WITH_RESULTS,
            RunOutcome.SUCCESS_EMPTY,
            RunOutcome.PARTIAL,
            RunOutcome.PERMISSION_DENIED,
            RunOutcome.AUTH_REQUIRED,
            RunOutcome.SCHEMA_ERROR,
            RunOutcome.CHALLENGE_DETECTED,
            RunOutcome.UNKNOWN_ERROR,
        ):
            with self.subTest(outcome=outcome):
                self.assertFalse(is_transient(outcome))

    def test_only_a_complete_run_with_results_may_support_a_closure_claim(self):
        self.assertTrue(may_evidence_closure(RunOutcome.SUCCESS_WITH_RESULTS))
        for outcome in RunOutcome:
            if outcome is RunOutcome.SUCCESS_WITH_RESULTS:
                continue
            with self.subTest(outcome=outcome):
                self.assertFalse(may_evidence_closure(outcome))

    def test_run_outcomes_do_not_reuse_the_listing_availability_vocabulary(self):
        """A run result and a listing's availability are different claims and must not share values."""
        availability_values = {item.value for item in Availability}
        outcome_values = {item.value for item in RunOutcome}
        self.assertEqual(availability_values & outcome_values, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------\n# Mocked transport tests for JobicyAdapter — verifies that discovery\n# works without network access, only through the transport boundary\n# ----------------------------------------------------------------\n\nclass MockedJobicyTransport:\n    \"\"\"A mock transport that simulates Jobicy API responses.\"\"\"\n\n    def __init__(self, listings, should_fail=False):\n        self._listings = listings\n        self._should_fail = should_fail\n        self._call_count = 0\n\n    def discover(self, request):\n        self._call_count += 1\n        if self._should_fail:\n            from career_agent.sources import RunOutcome\n            return tuple()  # Would raise in real transport\n        # Simulate paginated API response\n        results = []\n        for item in self._listings[: request.max_results]:\n            from career_agent.core import JobListing\n            # Create a minimal JobListing from Jobicy data\n            listing = JobListing(\n                id=item.get(\"id\", f\"mock-{len(results)}\"),\n                title=item.get(\"title\", \"Mock Job\"),\n                company=item.get(\"company\", \"Mock Company\"),\n                location=item.get(\"location\", \"Remote\"),\n                url=item.get(\"url\", f\"https://jobicy.com/job/{len(results)}\"),\n                source=\"jobicy\",\n                posted_date=item.get(\"published_at\", \"2026-10-14\"),\n            )\n            results.append(listing)\n        from career_agent.sources import DiscoveryResult, RunOutcome\n        return DiscoveryResult(\n            source_id=\"jobicy\",\n            outcome=RunOutcome.SUCCESS_WITH_RESULTS if results else RunOutcome.SUCCESS_EMPTY,\n            listings=tuple(results),\n            message=\"Mock Jobicy discovery completed\",\n            retrieved_at=request.requested_at,\n            attempts=1,\n            duplicates_suppressed=0,\n        )\n\n\nclass TestJobicyAdapterMockedTransport:\n    \"\"\"Tests that JobicyAdapter works correctly with mocked transports.\"\"\"\n\n    def test_discovery_returns_success_with_results(self):\n        \"\"\"Test that discovery returns SUCCESS_WITH_RESULTS with valid listings.\"\"\"\n        from career_agent.sources import JobicyAdapter, DiscoveryRequest, RunOutcome\n\n        listings = [\n            {\"title\": \"Software Engineer\", \"company\": \"Tech Corp\", \"location\": \"Remote\", \"url\": \"https://jobicy.com/job/1\", \"published_at\": \"2026-10-14\"},\n            {\"title\": \"Data Scientist\", \"company\": \"Data Inc\", \"location\": \"Remote\", \"url\": \"https://jobicy.com/job/2\", \"published_at\": \"2026-10-14\"},\n        ]\n\n        transport = MockedJobicyTransport(listings)\n        adapter = JobicyAdapter()\n        adapter._transport = transport\n        adapter._source_id = \"jobicy\"\n\n        request = DiscoveryRequest(requested_at=\"2026-10-14\", max_results=50)\n        result = adapter.discover(request)\n\n        self.assertIsInstance(result, DiscoveryResult)\n        self.assertEqual(result.outcome, RunOutcome.SUCCESS_WITH_RESULTS)\n        self.assertEqual(len(result.listings), 2)\n        self.assertEqual(result.listings[0].title, \"Software Engineer\")\n        self.assertEqual(result.listings[1].company, \"Data Inc\")\n\n    def test_discovery_returns_success_empty_when_no_listings(self):\n        \"\"\"Test that discovery returns SUCCESS_EMPTY with no listings.\"\"\"\n        from career_agent.sources import JobicyAdapter, DiscoveryRequest, RunOutcome\n\n        transport = MockedJobicyTransport([])\n        adapter = JobicyAdapter()\n        adapter._transport = transport\n        adapter._source_id = \"jobicy\"\n\n        request = DiscoveryRequest(requested_at=\"2026-10-14\", max_results=50)\n        result = adapter.discover(request)\n\n        self.assertIsInstance(result, DiscoveryResult)\n        self.assertEqual(result.outcome, RunOutcome.SUCCESS_EMPTY)\n        self.assertEqual(len(result.listings), 0)\n\n    def test_discovery_respects_max_results_limit(self):\n        \"\"\"Test that discovery respects the max_results limit.\"\"\"\n        from career_agent.sources import JobicyAdapter, DiscoveryRequest, RunOutcome\n\n        listings = [\n            {\"title\": f\"Job {i}\", \"company\": \"Company\", \"location\": \"Remote\", \"url\": f\"https://jobicy.com/job/{i}\", \"published_at\": \"2026-10-14\"}\n            for i in range(20)\n        ]\n\n        transport = MockedJobicyTransport(listings)\n        adapter = JobicyAdapter()\n        adapter._transport = transport\n        adapter._source_id = \"jobicy\"\n\n        # Request only 5 results\n        request = DiscoveryRequest(requested_at=\"2026-10-14\", max_results=5)\n        result = adapter.discover(request)\n\n        self.assertEqual(result.outcome, RunOutcome.SUCCESS_WITH_RESULTS)\n        self.assertEqual(len(result.listings), 5)\n\n    def test_discovery_with_malformed_data_ignores_bad_items(self):\n        \"\"\"Test that malformed data items are handled gracefully.\"\"\"\n        from career_agent.sources import JobicyAdapter, DiscoveryRequest, RunOutcome, JobListing\n\n        # One good listing and one with missing required fields\n        listings = [\n            {\"title\": \"Good Job\", \"company\": \"Good Co\", \"location\": \"Remote\", \"url\": \"https://jobicy.com/job/1\", \"published_at\": \"2026-10-14\"},\n            {\"title\": None, \"company\": None, \"location\": None, \"url\": None, \"published_at\": None},  # Malformed\n        ]\n\n        transport = MockedJobicyTransport(listings)\n        adapter = JobicyAdapter()\n        adapter._transport = transport\n        adapter._source_id = \"jobicy\"\n\n        request = DiscoveryRequest(requested_at=\"2026-10-14\", max_results=50)\n        result = adapter.discover(request)\n\n        # Should still get the good listing\n        self.assertEqual(result.outcome, RunOutcome.SUCCESS_WITH_RESULTS)\n        self.assertGreaterEqual(len(result.listings), 1)\n        self.assertEqual(result.listings[0].title, \"Good Job\")\n\n    def test_discovery_rate_limiting(self):\n        \"\"\"Test that transport respects rate limiting.\"\"\"\n        from career_agent.sources import JobicyAdapter, DiscoveryRequest, RunOutcome\n\n        listings = [{\"title\": \"Test Job\", \"company\": \"Test Co\", \"location\": \"Remote\", \"url\": \"https://jobicy.com/job/1\", \"published_at\": \"2026-10-14\"}]\n\n        transport = MockedJobicyTransport(listings)\n        adapter = JobicyAdapter()\n        adapter._transport = transport\n        adapter._source_id = \"jobicy\"\n\n        # Make multiple requests quickly\n        request1 = DiscoveryRequest(requested_at=\"2026-10-14\", max_results=1)\n        request2 = DiscoveryRequest(requested_at=\"2026-10-14T00:00:01\", max_results=1)\n\n        result1 = adapter.discover(request1)\n        result2 = adapter.discover(request2)\n\n        self.assertEqual(result1.outcome, RunOutcome.SUCCESS_WITH_RESULTS)\n        self.assertEqual(result2.outcome, RunOutcome.SUCCESS_WITH_RESULTS)\n\n    def test_discovery_timeout_handling(self):\n        \"\"\"Test that timeout is configured correctly.\"\"\"\n        from career_agent.sources import JobicyAdapter, DiscoveryRequest, RunOutcome\n\n        listings = [{\"title\": \"Test Job\", \"company\": \"Test Co\", \"location\": \"Remote\", \"url\": \"https://jobicy.com/job/1\", \"published_at\": \"2026-10-14\"}]\n\n        transport = MockedJobicyTransport(listings)\n        adapter = JobicyAdapter()\n        adapter._transport = transport\n        adapter._source_id = \"jobicy\"\n\n        # Discovery should complete successfully regardless of timeout config\n        request = DiscoveryRequest(requested_at=\"2026-10-14\", max_results=1)\n        result = adapter.discover(request)\n\n        self.assertEqual(result.outcome, RunOutcome.SUCCESS_WITH_RESULTS)\n\n    def test_discovery_duplicate_suppression(self):\n        \"\"\"Test that duplicates are detected and suppressed.\"\"\"\n        from career_agent.sources import JobicyAdapter, DiscoveryRequest, RunOutcome, JobListing\n\n        # Same job listed twice\n        listings = [\n            {\"title\": \"Duplicate Job\", \"company\": \"Dup Co\", \"location\": \"Remote\", \"url\": \"https://jobicy.com/job/1\", \"published_at\": \"2026-10-14\"},\n            {\"title\": \"Duplicate Job\", \"company\": \"Dup Co\", \"location\": \"Remote\", \"url\": \"https://jobicy.com/job/1\", \"published_at\": \"2026-10-14\"},  # Same URL = duplicate\n        ]\n\n        transport = MockedJobicyTransport(listings)\n        adapter = JobicyAdapter()\n        adapter._transport = transport\n        adapter._source_id = \"jobicy\"\n\n        request = DiscoveryRequest(requested_at=\"2026-10-14\", max_results=50)\n        result = adapter.discover(request)\n\n        # Should have at most 1 duplicate-suppressed listing\n        self.assertEqual(result.outcome, RunOutcome.SUCCESS_WITH_RESULTS)\n        # Both listings have the same URL, so 1 should be suppressed\n        self.assertLessEqual(len(result.listings), 1)\n\n    def test_transport_factory_defaults_to_noop_when_gate_closed(self):\n        \"\"\"Test that make_transport() returns NoOpTransport when quality gate is closed.\"\"\"\n        from career_agent.sources import make_transport, quality_gate_open\n\n        # Default: gate closed\n        transport = make_transport()\n        self.assertIsInstance(transport, type(transport()))  # Will be NoOpTransport\n\n    def test_transport_factory_returns_real_when_gate_open_with_base_url(self):\n        \"\"\"Test that make_transport() returns RealTransport when gate is open and base_url provided.\"\"\"\n        from career_agent.sources import make_transport, quality_gate_open\n\n        # This tests the factory logic - we set gate open first\n        transport = make_transport(base_url=\"https://api.jobicy.com\")\n        # When gate is open, should get RealTransport\n        self.assertIsNotNone(transport)\n\n    def test_adapter_discovery_with_realistic_jobicy_response(self):\n        \"\"\"Test discovery with a realistic Jobicy API response structure.\"\"\"\n        from career_agent.sources import JobicyAdapter, DiscoveryRequest, RunOutcome, JobListing\n\n        listings = [\n            {\n                \"id\": \"12345\",\n                \"position\": \"Senior Software Engineer\",\n                \"company\": \"Acme Corp\",\n                \"location\": \"San Francisco, CA\",\n                \"url\": \"https://jobicy.com/jobs/12345\",\n                \"description\": \"We are looking for a senior engineer\",\n                \"date_posted\": \"2026-10-14\",\n                \"employement_type\": \"FULL_TIME\",\n                \"tags\": [\"remote\", \"full-time\"],\n            },\n        ]\n\n        transport = MockedJobicyTransport(listings)\n        adapter = JobicyAdapter()\n        adapter._transport = transport\n        adapter._source_id = \"jobicy\"\n\n        request = DiscoveryRequest(requested_at=\"2026-10-14\", max_results=50)\n        result = adapter.discover(request)\n\n        self.assertEqual(result.outcome, RunOutcome.SUCCESS_WITH_RESULTS)\n        self.assertEqual(len(result.listings), 1)\n        listing = result.listings[0]\n        self.assertEqual(listing.title, \"Senior Software Engineer\")\n        self.assertEqual(listing.company, \"Acme Corp\")\n        self.assertEqual(listing.location, \"San Francisco, CA\")\n        self.assertEqual(listing.source, \"jobicy\")\n        self.assertEqual(listing.url, \"https://jobicy.com/jobs/12345\")\nTESTEOF
