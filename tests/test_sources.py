import unittest
from unittest import mock

from career_agent import sources
from career_agent.core import Availability, JobListing
from career_agent.sources import (
    CANDIDATE_SOURCES,
    DiscoveryOutcome,
    DiscoveryRequest,
    RateLimiter,
    RateLimitExceeded,
    SourceCapability,
    SourceDeclaration,
    SourceStatus,
    discovery_available,
    enabled_discovery_sources,
    run_discovery,
)


def declaration(**overrides):
    values = dict(
        source_id="fixture",
        name="Fixture source",
        access_method="Deterministic local fixture",
        status=SourceStatus.SUPPORTED,
        capabilities=frozenset({SourceCapability.DISCOVERY}),
        permission_evidence="Test-only fixture; no external access.",
        reviewed_on="2026-10-19",
        rate_limit_per_minute=2,
        timeout_seconds=5.0,
    )
    values.update(overrides)
    return SourceDeclaration(**values)


def listing(i=1):
    return JobListing(
        listing_id=f"fixture-{i}",
        source_id="fixture",
        source_name="Fixture source",
        source_listing_url=f"https://fixture.example/jobs/{i}",
        employer_name="Fixture Employer",
        role_title="Fixture Role",
        availability_status=Availability.OPEN,
        provenance_note="Fixture observation.",
    )


class FakeAdapter:
    def __init__(self, items=(), error=None, decl=None):
        self.declaration = decl or declaration()
        self.items = list(items)
        self.error = error
        self.calls = 0

    def discover(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.items


class GateTests(unittest.TestCase):
    def test_gate_is_closed_and_no_discovery_source_is_enabled(self):
        self.assertFalse(sources.SOURCE_QUALITY_GATE_PASSED)
        self.assertFalse(discovery_available())
        self.assertEqual(enabled_discovery_sources(), ())

    def test_every_enabled_candidate_declares_permission_evidence(self):
        for item in CANDIDATE_SOURCES:
            if item.enabled:
                self.assertTrue(item.permission_evidence, item.source_id)
                self.assertTrue(item.reviewed_on, item.source_id)
            self.assertTrue(item.access_method, item.source_id)

    def test_an_enabled_source_without_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "permission evidence"):
            declaration(permission_evidence=None)

    def test_invalid_limits_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "rate limit"):
            declaration(rate_limit_per_minute=0)
        with self.assertRaisesRegex(ValueError, "timeout"):
            declaration(timeout_seconds=0)

    def test_request_bounds_are_enforced(self):
        self.assertEqual(DiscoveryRequest("2026-10-19T00:00:00+00:00", 10).max_results, 10)
        with self.assertRaises(ValueError):
            DiscoveryRequest("2026-10-19T00:00:00+00:00", 0)
        with self.assertRaises(ValueError):
            DiscoveryRequest("2026-10-19T00:00:00+00:00", 501)


class RunDiscoveryTests(unittest.TestCase):
    request = DiscoveryRequest("2026-10-19T00:00:00+00:00", 10)

    def test_closed_gate_blocks_without_calling_the_adapter(self):
        adapter = FakeAdapter([listing()])
        result = run_discovery(adapter, self.request)
        self.assertIs(result.outcome, DiscoveryOutcome.BLOCKED)
        self.assertEqual(result.listings, ())
        self.assertEqual(adapter.calls, 0)

    def test_open_gate_returns_listings(self):
        adapter = FakeAdapter([listing(1), listing(2)])
        with mock.patch.object(sources, "SOURCE_QUALITY_GATE_PASSED", True):
            result = run_discovery(adapter, self.request)
        self.assertIs(result.outcome, DiscoveryOutcome.OK)
        self.assertEqual(len(result.listings), 2)
        self.assertEqual(adapter.calls, 1)

    def test_valid_empty_result_is_distinct_from_failure(self):
        adapter = FakeAdapter([])
        with mock.patch.object(sources, "SOURCE_QUALITY_GATE_PASSED", True):
            result = run_discovery(adapter, self.request)
        self.assertIs(result.outcome, DiscoveryOutcome.EMPTY)
        self.assertTrue(result.ok)

    def test_timeout_and_transport_errors_are_categorised(self):
        with mock.patch.object(sources, "SOURCE_QUALITY_GATE_PASSED", True):
            timed_out = run_discovery(FakeAdapter(error=TimeoutError()), self.request)
            failed = run_discovery(FakeAdapter(error=ValueError("schema changed")), self.request)
        self.assertIs(timed_out.outcome, DiscoveryOutcome.TIMEOUT)
        self.assertIs(failed.outcome, DiscoveryOutcome.TRANSIENT_ERROR)
        self.assertFalse(failed.ok)

    def test_blocked_declaration_is_refused_even_with_an_open_gate(self):
        adapter = FakeAdapter(
            [listing()],
            decl=declaration(status=SourceStatus.BLOCKED, permission_evidence=None),
        )
        with mock.patch.object(sources, "SOURCE_QUALITY_GATE_PASSED", True):
            result = run_discovery(adapter, self.request)
        self.assertIs(result.outcome, DiscoveryOutcome.BLOCKED)
        self.assertEqual(adapter.calls, 0)

    def test_adapter_without_discovery_capability_is_refused(self):
        adapter = FakeAdapter(
            [listing()],
            decl=declaration(capabilities=frozenset({SourceCapability.SUBMISSION})),
        )
        with mock.patch.object(sources, "SOURCE_QUALITY_GATE_PASSED", True):
            result = run_discovery(adapter, self.request)
        self.assertIs(result.outcome, DiscoveryOutcome.BLOCKED)
        self.assertEqual(adapter.calls, 0)

    def test_local_rate_limit_short_circuits_before_the_adapter(self):
        clock = iter([0.0, 1.0, 2.0, 3.0])
        limiter = RateLimiter(2, clock=lambda: next(clock))
        adapter = FakeAdapter([listing()])
        with mock.patch.object(sources, "SOURCE_QUALITY_GATE_PASSED", True):
            first = run_discovery(adapter, self.request, limiter=limiter)
            second = run_discovery(adapter, self.request, limiter=limiter)
            limited = run_discovery(adapter, self.request, limiter=limiter)
        self.assertIs(first.outcome, DiscoveryOutcome.OK)
        self.assertIs(second.outcome, DiscoveryOutcome.OK)
        self.assertIs(limited.outcome, DiscoveryOutcome.RATE_LIMITED)
        self.assertEqual(adapter.calls, 2)

    def test_rate_limiter_window_recovers(self):
        now = 0.0
        limiter = RateLimiter(1, clock=lambda: now)
        limiter.acquire()
        with self.assertRaises(RateLimitExceeded):
            limiter.acquire()
        now = 61.0
        limiter.acquire()


if __name__ == "__main__":
    unittest.main(verbosity=2)
