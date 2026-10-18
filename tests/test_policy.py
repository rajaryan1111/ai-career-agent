"""Tests for the one authorisation a person gives once: the central policy, checked before any side effect.

Nothing here opens a network connection, sends anything, or enables a source. Every policy, source id
and clock in this module is invented, and the real source gates - which are closed - are what the
policy is composed with.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from career_agent.policy import (
    ActionKind, GlobalPolicy, PolicyError, evaluate_policy, no_authorisation,
)

#: Noon UTC on a Tuesday: outside any quiet hours used below unless a test says otherwise.
NOON = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def authorised(**overrides) -> GlobalPolicy:
    """A policy that authorises discovery on one source, with room under its limit."""
    content = {
        "allowed": frozenset({("jobicy", ActionKind.DISCOVERY)}),
        "daily_limits": {ActionKind.DISCOVERY: 2},
    }
    content.update(overrides)
    return GlobalPolicy(**content)


class PolicyModelTests(unittest.TestCase):
    """What a stored authorisation may say at all."""

    def test_the_default_policy_authorises_nothing(self):
        policy = no_authorisation()
        self.assertEqual(policy.allowed, frozenset())
        self.assertFalse(policy.authorises("jobicy", ActionKind.DISCOVERY))
        self.assertTrue(policy.is_empty)

    def test_an_action_must_be_one_this_application_knows(self):
        with self.assertRaises(PolicyError) as caught:
            GlobalPolicy(allowed=frozenset({("jobicy", "take over the world")}))
        self.assertIn("take over the world", str(caught.exception))

    def test_a_pair_names_a_source_and_an_action(self):
        for pair in (("", ActionKind.DISCOVERY), ("   ", ActionKind.EMAIL_SEND)):
            with self.subTest(pair=pair), self.assertRaises(PolicyError):
                GlobalPolicy(allowed=frozenset({pair}))

    def test_a_daily_limit_is_a_whole_number_of_actions(self):
        for limit in (-1, 1.5, True):
            with self.subTest(limit=limit), self.assertRaises(PolicyError):
                GlobalPolicy(allowed=frozenset({("jobicy", ActionKind.DISCOVERY)}),
                             daily_limits={ActionKind.DISCOVERY: limit})

    def test_quiet_hours_are_two_hours_of_the_day(self):
        for hours in ((-1, 6), (0, 24), (6,), (6, 6)):
            with self.subTest(hours=hours), self.assertRaises(PolicyError):
                GlobalPolicy(quiet_hours=hours)

    def test_a_policy_is_frozen_so_a_caller_cannot_widen_it_in_passing(self):
        policy = authorised()
        with self.assertRaises(Exception):
            policy.allowed = frozenset()  # type: ignore[misc]


class PolicyDecisionTests(unittest.TestCase):
    """The decision itself: allowed only when every condition says so, refused with the reason."""

    def decide(self, policy=None, *, action=ActionKind.DISCOVERY, source_id="jobicy",
               now=NOON, done_today=0, gate_allows=True):
        return evaluate_policy(
            policy if policy is not None else authorised(),
            source_id=source_id, action=action, now=now, done_today=done_today,
            source_gate_allows=gate_allows)

    def test_an_authorised_action_inside_every_limit_is_allowed(self):
        decision = self.decide()
        self.assertTrue(decision.allowed)
        self.assertIn("authorised", decision.describe())
        self.assertEqual(decision.refusals, ())

    def test_nothing_is_authorised_by_an_empty_policy(self):
        decision = self.decide(no_authorisation())
        self.assertFalse(decision.allowed)
        self.assertIn("no standing authorisation", decision.describe())

    def test_an_action_the_policy_does_not_name_is_refused(self):
        decision = self.decide(action=ActionKind.EMAIL_SEND)
        self.assertFalse(decision.allowed)
        self.assertIn("email", decision.describe())

    def test_a_source_the_policy_does_not_name_is_refused(self):
        decision = self.decide(source_id="some-other-board")
        self.assertFalse(decision.allowed)
        self.assertIn("some-other-board", decision.describe())

    def test_stopping_everything_refuses_even_an_authorised_action(self):
        decision = self.decide(authorised(stop_all=True))
        self.assertFalse(decision.allowed)
        self.assertIn("stopped", decision.describe())

    def test_a_revoked_policy_authorises_nothing_and_says_when_it_was_revoked(self):
        decision = self.decide(authorised(revoked_at="2026-10-19T08:00:00+00:00"))
        self.assertFalse(decision.allowed)
        self.assertIn("revoked", decision.describe())
        self.assertIn("2026-10-19", decision.describe())

    def test_the_policy_cannot_open_what_the_source_gate_keeps_closed(self):
        decision = self.decide(gate_allows=False)
        self.assertFalse(decision.allowed)
        self.assertIn("source's own gate", decision.describe())

    def test_the_daily_limit_is_a_ceiling_not_a_suggestion(self):
        self.assertTrue(self.decide(done_today=1).allowed)
        at_the_limit = self.decide(done_today=2)
        self.assertFalse(at_the_limit.allowed)
        self.assertIn("2", at_the_limit.describe())
        self.assertFalse(self.decide(done_today=3).allowed)

    def test_an_action_with_no_recorded_limit_is_refused_rather_than_unlimited(self):
        policy = authorised(allowed=frozenset({("jobicy", ActionKind.DISCOVERY),
                                               ("jobicy", ActionKind.SUBMISSION)}))
        decision = self.decide(policy, action=ActionKind.SUBMISSION)
        self.assertFalse(decision.allowed)
        self.assertIn("no daily limit", decision.describe())

    def test_a_limit_of_zero_means_none_today(self):
        policy = authorised(daily_limits={ActionKind.DISCOVERY: 0})
        self.assertFalse(self.decide(policy).allowed)

    def test_quiet_hours_refuse_the_action_while_they_last(self):
        policy = authorised(quiet_hours=(22, 7))
        night = datetime(2026, 10, 20, 23, 30, tzinfo=timezone.utc)
        early = datetime(2026, 10, 21, 6, 59, tzinfo=timezone.utc)
        for moment in (night, early):
            with self.subTest(moment=moment):
                decision = self.decide(policy, now=moment)
                self.assertFalse(decision.allowed)
                self.assertIn("quiet hours", decision.describe())
        self.assertTrue(self.decide(policy, now=NOON).allowed)

    def test_quiet_hours_inside_one_day_are_read_the_same_way(self):
        policy = authorised(quiet_hours=(9, 17))
        self.assertFalse(self.decide(policy, now=NOON).allowed)
        self.assertTrue(
            self.decide(policy, now=datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)).allowed)

    def test_every_reason_an_action_is_refused_is_reported_not_only_the_first(self):
        policy = authorised(quiet_hours=(9, 17), stop_all=True)
        decision = self.decide(policy, now=NOON, done_today=9, gate_allows=False)
        self.assertFalse(decision.allowed)
        self.assertGreaterEqual(len(decision.refusals), 4,
                                f"only {decision.refusals} were reported")

    def test_a_decision_needs_an_instant_that_knows_its_own_zone(self):
        with self.assertRaises(PolicyError):
            self.decide(now=datetime(2026, 10, 20, 12, 0))

    def test_a_count_of_what_has_already_run_cannot_be_negative_or_invented(self):
        for done in (-1, 1.5, "two"):
            with self.subTest(done=done), self.assertRaises(PolicyError):
                self.decide(done_today=done)

    def test_an_unknown_action_is_refused_rather_than_guessed(self):
        with self.assertRaises(PolicyError):
            self.decide(action="post on social media")


class PolicyIsNotAnEnablerTests(unittest.TestCase):
    """The property that matters most: this module never opens anything on its own."""

    def test_the_real_source_gates_are_closed_and_the_policy_does_not_change_that(self):
        from career_agent.sources import (
            SOURCE_QUALITY_GATE_PASSED, discovery_gate, enabled_discovery_sources,
        )

        self.assertFalse(SOURCE_QUALITY_GATE_PASSED)
        self.assertEqual(enabled_discovery_sources(), ())
        everything = GlobalPolicy(
            allowed=frozenset({("jobicy", ActionKind.DISCOVERY),
                               ("jobicy", ActionKind.SUBMISSION),
                               ("jobicy", ActionKind.EMAIL_SEND),
                               ("jobicy", ActionKind.INBOX_READ)}),
            daily_limits={kind: 100 for kind in ActionKind})
        for action in ActionKind:
            with self.subTest(action=action):
                decision = evaluate_policy(
                    everything, source_id="jobicy", action=action, now=NOON, done_today=0,
                    source_gate_allows=discovery_gate("jobicy").allowed)
                self.assertFalse(decision.allowed,
                                 "a policy that authorises everything still cannot open a closed gate")

    def test_the_module_performs_no_side_effect_of_its_own(self):
        import inspect

        from career_agent import policy as policy_module

        source = inspect.getsource(policy_module)
        for forbidden in ("requests", "urllib", "smtplib", "imaplib", "socket", "subprocess"):
            self.assertNotIn(forbidden, source,
                             f"the policy module must not be able to {forbidden}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
