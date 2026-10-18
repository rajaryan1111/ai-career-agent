"""Tests for the places the standing authorisation is actually consulted.

Two call sites can cause an external effect: running a discovery adapter, and dispatching an email
through an integration. Both are checked here, and both refuse today - the discovery gate is closed and
no integration is enabled - so the tests below prove the refusals, prove that a refusal performs nothing
at all, and prove that an authorisation cannot open anything that is shut.

Where a test needs to see what happens *after* the gate, it replaces the gate function with a stand-in
for the length of that test. That stand-in never touches the network: the adapter underneath it is a
recording fake, and the assertion is about which refusal was raised, not about any fetched data.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

from career_agent import adapters as adapters_module
from career_agent.adapters import (
    AdapterError, AdapterRegistry, AdapterRequest, FixtureAdapter, SourceDisabled,
)
from career_agent.integrations import (
    DisabledIntegration, EmailDraft, LocalMockIntegration, Outcome, authorised_dispatch,
)
from career_agent.policy import ActionKind, GlobalPolicy, PolicyError, no_authorisation
from career_agent.sources import GateResult, discovery_gate, enabled_discovery_sources

NOON = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
NIGHT = datetime(2026, 10, 20, 23, 30, tzinfo=timezone.utc)


def authorisation(action: ActionKind = ActionKind.DISCOVERY, *, limit: int = 3,
                  source_id: str = "recorder", **overrides) -> GlobalPolicy:
    content = {
        "allowed": frozenset({(source_id, action)}),
        "daily_limits": {action: limit},
    }
    content.update(overrides)
    return GlobalPolicy(**content)


def open_gate(source_id: str, **_ignored) -> GateResult:
    """A stand-in for the gate, so the step *after* the gate can be tested while the gate is shut."""
    return GateResult(allowed=True, reason="a stand-in used by this test only")


class AdapterAuthorisationTests(unittest.TestCase):
    """``AdapterRegistry.execute`` consults the authorisation immediately before the call."""

    def setUp(self):
        self.adapter = FixtureAdapter(source_id="recorder", source_name="Recorder")
        self.registry = AdapterRegistry()
        self.registry.register(self.adapter)
        self.request = AdapterRequest(terms=("python",), page_size=5)

    def test_the_real_gate_refuses_first_and_nothing_is_called(self):
        with self.assertRaises(SourceDisabled) as raised:
            self.registry.execute("recorder", self.request, policy=authorisation(), done_today=0)
        self.assertIn("is not permitted", str(raised.exception))
        self.assertEqual(self.adapter.calls, [], "a refusal must not reach the adapter")

    def test_without_an_authorisation_an_open_gate_still_refuses(self):
        with mock.patch.object(adapters_module, "discovery_gate", open_gate):
            with self.assertRaises(SourceDisabled) as raised:
                self.registry.execute("recorder", self.request, now=NOON)
        message = str(raised.exception)
        self.assertIn("is not authorised", message)
        self.assertIn("no standing authorisation for anything yet", message)
        self.assertEqual(self.adapter.calls, [])

    def test_an_authorisation_without_todays_count_refuses(self):
        with mock.patch.object(adapters_module, "discovery_gate", open_gate):
            with self.assertRaises(SourceDisabled) as raised:
                self.registry.execute("recorder", self.request, now=NOON,
                                      policy=authorisation(), done_today=None)
        self.assertIn("without a count of today's discovery runs", str(raised.exception))
        self.assertEqual(self.adapter.calls, [])

    def test_an_authorisation_for_another_source_refuses(self):
        with mock.patch.object(adapters_module, "discovery_gate", open_gate):
            with self.assertRaises(SourceDisabled):
                self.registry.execute("recorder", self.request, now=NOON,
                                      policy=authorisation(source_id="somewhere-else"), done_today=0)
        self.assertEqual(self.adapter.calls, [])

    def test_the_daily_limit_is_a_ceiling_at_the_call_site(self):
        with mock.patch.object(adapters_module, "discovery_gate", open_gate):
            self.registry.execute("recorder", self.request, now=NOON,
                                  policy=authorisation(limit=2), done_today=1)
            self.assertEqual(len(self.adapter.calls), 1)
            with self.assertRaises(SourceDisabled) as raised:
                self.registry.execute("recorder", self.request, now=NOON,
                                      policy=authorisation(limit=2), done_today=2)
        self.assertIn("2", str(raised.exception))
        self.assertEqual(len(self.adapter.calls), 1, "the run over the limit must not happen")

    def test_quiet_hours_refuse_at_the_call_site(self):
        policy = authorisation(quiet_hours=(22, 7))
        with mock.patch.object(adapters_module, "discovery_gate", open_gate):
            with self.assertRaises(SourceDisabled) as raised:
                self.registry.execute("recorder", self.request, now=NIGHT,
                                      policy=policy, done_today=0)
        self.assertIn("quiet hours", str(raised.exception))
        self.assertEqual(self.adapter.calls, [])

    def test_stop_all_refuses_at_the_call_site(self):
        policy = authorisation(stop_all=True)
        with mock.patch.object(adapters_module, "discovery_gate", open_gate):
            with self.assertRaises(SourceDisabled) as raised:
                self.registry.execute("recorder", self.request, now=NOON,
                                      policy=policy, done_today=0)
        self.assertIn("stopped", str(raised.exception))
        self.assertEqual(self.adapter.calls, [])

    def test_a_revoked_authorisation_refuses_at_the_call_site(self):
        policy = authorisation(revoked_at="2026-10-19T08:00:00+00:00")
        with mock.patch.object(adapters_module, "discovery_gate", open_gate):
            with self.assertRaises(SourceDisabled) as raised:
                self.registry.execute("recorder", self.request, now=NOON,
                                      policy=policy, done_today=0)
        self.assertIn("revoked", str(raised.exception))
        self.assertEqual(self.adapter.calls, [])

    def test_an_authorisation_permits_only_when_the_gate_already_did(self):
        """The composition, stated once: gate AND authorisation, never gate OR authorisation."""
        with self.assertRaises(SourceDisabled):
            self.registry.execute("recorder", self.request, now=NOON,
                                  policy=authorisation(), done_today=0)
        with mock.patch.object(adapters_module, "discovery_gate", open_gate):
            response = self.registry.execute("recorder", self.request, now=NOON,
                                             policy=authorisation(), done_today=0)
        self.assertEqual(response.provenance.source_id, "recorder")
        self.assertEqual(len(self.adapter.calls), 1)

    def test_a_missing_adapter_still_refuses_before_anything_else(self):
        with self.assertRaises(AdapterError) as raised:
            self.registry.execute("unknown", self.request,
                                  policy=authorisation(source_id="unknown"), done_today=0)
        self.assertIn("No adapter is registered", str(raised.exception))


class EmailAuthorisationTests(unittest.TestCase):
    """``authorised_dispatch`` is the only door an email may leave by, and today it never opens."""

    def setUp(self):
        self.draft = EmailDraft(subject="Following up", body="Thank you for your time.",
                                recipient="someone@example.com", operation_id="op-1")

    def dispatch(self, integration, **overrides):
        arguments = {
            "policy": authorisation(ActionKind.EMAIL_SEND, source_id="follow-ups"),
            "source_id": "follow-ups", "now": NOON, "done_today": 0, "source_gate_allows": True,
        }
        arguments.update(overrides)
        return authorised_dispatch(integration, self.draft, **arguments)

    def test_the_default_integration_refuses_even_when_authorised(self):
        result = self.dispatch(DisabledIntegration())
        self.assertIs(result.outcome, Outcome.DISABLED)
        self.assertFalse(result.performed)

    def test_no_authorisation_means_nothing_is_dispatched(self):
        ledger = LocalMockIntegration()
        result = self.dispatch(ledger, policy=None)
        self.assertIs(result.outcome, Outcome.DISABLED)
        self.assertFalse(result.performed)
        self.assertIn("not authorised", result.message)
        self.assertEqual(ledger.ledger.records(), ())

    def test_an_empty_authorisation_is_not_a_permissive_one(self):
        ledger = LocalMockIntegration()
        result = self.dispatch(ledger, policy=no_authorisation())
        self.assertFalse(result.performed)
        self.assertEqual(ledger.ledger.records(), ())

    def test_a_closed_source_gate_refuses_whatever_the_authorisation_says(self):
        ledger = LocalMockIntegration()
        result = self.dispatch(ledger, source_gate_allows=False)
        self.assertFalse(result.performed)
        self.assertIn("gate", result.message)
        self.assertEqual(ledger.ledger.records(), ())

    def test_a_missing_count_refuses_rather_than_assuming_zero(self):
        ledger = LocalMockIntegration()
        result = self.dispatch(ledger, done_today=None)
        self.assertFalse(result.performed)
        self.assertIn("not known", result.message)
        self.assertEqual(ledger.ledger.records(), ())

    def test_the_daily_limit_is_a_ceiling_for_messages_too(self):
        ledger = LocalMockIntegration()
        policy = authorisation(ActionKind.EMAIL_SEND, source_id="follow-ups", limit=1)
        self.assertTrue(self.dispatch(ledger, policy=policy, done_today=0).performed)
        blocked = self.dispatch(ledger, policy=policy, done_today=1)
        self.assertFalse(blocked.performed)
        self.assertEqual(len(ledger.ledger.records()), 1)

    def test_quiet_hours_and_stop_all_refuse_before_the_integration_is_touched(self):
        for name, overrides in (("quiet hours", {"quiet_hours": (22, 7)}), ("stop", {"stop_all": True})):
            with self.subTest(name):
                ledger = LocalMockIntegration()
                policy = authorisation(ActionKind.EMAIL_SEND, source_id="follow-ups", **overrides)
                result = self.dispatch(ledger, policy=policy, now=NIGHT)
                self.assertFalse(result.performed)
                self.assertEqual(ledger.ledger.records(), ())

    def test_an_operation_the_authorisation_cannot_name_is_refused_loudly(self):
        from career_agent.integrations import CalendarEventRequest

        from datetime import date

        request = CalendarEventRequest(title="Follow up", day=date(2026, 10, 21))
        with self.assertRaises(PolicyError):
            authorised_dispatch(LocalMockIntegration(), request, policy=authorisation(),
                                source_id="follow-ups", now=NOON, done_today=0,
                                source_gate_allows=True)


class NothingIsEnabledByThisWorkTests(unittest.TestCase):
    """The wiring exists; the switches stay off. Both halves are asserted, not assumed."""

    def test_no_discovery_source_is_enabled(self):
        self.assertEqual(enabled_discovery_sources(), ())

    def test_every_known_source_gate_is_closed(self):
        from career_agent.sources import SOURCE_DECISIONS

        for source in SOURCE_DECISIONS:
            with self.subTest(source.source_id):
                self.assertFalse(discovery_gate(source.source_id).allowed)

    def test_the_wiring_added_no_way_to_force_a_gate(self):
        import inspect

        signature = inspect.signature(AdapterRegistry.execute)
        self.assertNotIn("force", signature.parameters)
        self.assertNotIn("gate", signature.parameters)
        source = inspect.getsource(AdapterRegistry.execute)
        self.assertIn("source_gate_allows=gate.allowed", source,
                      "the gate's own answer is what the authorisation is composed with")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
