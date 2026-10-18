"""Conditions on *which* jobs may be acted on: roles, places, attachments and follow-ups.

The standing authorisation already said which source may be used for which action, how many times a
day, and when to stay quiet. These are the remaining conditions a person would actually write down -
"only engineering roles", "only in India", "never attach anything but the PDF", "one follow-up per
job" - and the rule that makes them worth having is the same one as everywhere else here: a
condition with nothing to check it against refuses, rather than being skipped.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from career_agent.integrations import (
    COUNT_FROM_RECORDS, EmailDraft, LocalMockIntegration, guarded_dispatch,
)
from career_agent.policy import (
    ActionKind, GlobalPolicy, PolicyError, PolicySubject, evaluate_policy, policy_from_payload,
    policy_payload,
)
from career_agent.store import CareerStore

NOON = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def conditional(**conditions) -> GlobalPolicy:
    """An authorisation that permits the action, so only the conditions can refuse it."""
    return GlobalPolicy(
        allowed=frozenset({("jobicy", ActionKind.EMAIL_SEND)}),
        daily_limits={ActionKind.EMAIL_SEND: 5}, **conditions)


def decide(policy: GlobalPolicy, subject: PolicySubject | None = None):
    return evaluate_policy(policy, source_id="jobicy", action=ActionKind.EMAIL_SEND, now=NOON,
                           done_today=0, source_gate_allows=True, subject=subject)


class ModelTests(unittest.TestCase):
    def test_an_authorisation_without_conditions_still_decides_without_a_subject(self):
        self.assertTrue(decide(conditional()).allowed,
                        "conditions nobody set must not become a new way to refuse everything")

    def test_terms_are_folded_once_at_the_edge(self):
        policy = conditional(role_terms={" Engineer ", "ENGINEER", "analyst"})
        self.assertEqual(policy.role_terms, frozenset({"engineer", "analyst"}))

    def test_an_attachment_rule_is_stored_as_a_file_ending(self):
        self.assertEqual(conditional(allowed_attachments={"pdf", ".DOCX"}).allowed_attachments,
                         frozenset({".pdf", ".docx"}))

    def test_a_string_is_not_a_collection_of_terms(self):
        with self.assertRaises(PolicyError):
            conditional(role_terms="engineer")

    def test_an_empty_term_is_refused_rather_than_ignored(self):
        with self.assertRaises(PolicyError):
            conditional(locations={"India", "  "})

    def test_a_follow_up_limit_is_a_whole_number(self):
        for limit in (-1, 1.5, True):
            with self.subTest(limit=limit), self.assertRaises(PolicyError):
                conditional(follow_up_limit=limit)

    def test_conditions_are_part_of_what_the_authorisation_is(self):
        loose = conditional()
        tight = conditional(role_terms={"engineer"})
        self.assertNotEqual(loose.content_key(), tight.content_key(),
                            "a tightened authorisation is a different authorisation")

    def test_conditions_survive_the_stored_form(self):
        policy = conditional(role_terms={"engineer"}, locations={"india"},
                             allowed_attachments={".pdf"}, follow_up_limit=1)
        self.assertEqual(policy_from_payload(policy_payload(policy)), policy)

    def test_a_stored_condition_of_the_wrong_shape_is_refused(self):
        for payload in ('{"role_terms": "engineer"}', '{"follow_up_limit": "one"}'):
            with self.subTest(payload=payload), self.assertRaises(PolicyError):
                policy_from_payload(payload)


class EnforcementTests(unittest.TestCase):
    def test_a_condition_with_nothing_to_check_refuses(self):
        decision = decide(conditional(role_terms={"engineer"}))
        self.assertFalse(decision.allowed)
        self.assertIn("nothing described the job", decision.refusals[0])

    def test_a_role_that_matches_is_permitted_and_one_that_does_not_is_refused(self):
        policy = conditional(role_terms={"engineer"})
        self.assertTrue(decide(policy, PolicySubject(role_title="Senior Backend Engineer")).allowed)
        refused = decide(policy, PolicySubject(role_title="Pastry Chef"))
        self.assertFalse(refused.allowed)
        self.assertIn("matches none of the roles you authorised", refused.refusals[0])

    def test_a_role_condition_with_no_title_to_check_refuses(self):
        decision = decide(conditional(role_terms={"engineer"}), PolicySubject(role_title=""))
        self.assertFalse(decision.allowed)
        self.assertIn("carries no role title", decision.refusals[0])

    def test_a_place_is_matched_inside_the_location_as_written(self):
        policy = conditional(locations={"india"})
        self.assertTrue(decide(policy, PolicySubject(location="Bengaluru, India")).allowed)
        self.assertFalse(decide(policy, PolicySubject(location="Paris, France")).allowed)

    def test_nothing_may_be_attached_until_a_rule_says_what_may(self):
        decision = decide(conditional(role_terms={"engineer"}),
                          PolicySubject(role_title="Engineer", attachments=("resume.pdf",)))
        self.assertFalse(decision.allowed)
        self.assertIn("nothing may be attached", decision.refusals[0])

    def test_an_attachment_rule_permits_its_kind_and_nothing_else(self):
        policy = conditional(allowed_attachments={".pdf"})
        self.assertTrue(decide(policy, PolicySubject(attachments=("tailored-resume.PDF",))).allowed,
                        "the rule is about the kind of file, not about how it is spelled")
        refused = decide(policy, PolicySubject(attachments=("notes.exe",)))
        self.assertFalse(refused.allowed)
        self.assertIn("not a kind of file you authorised", refused.refusals[0])

    def test_a_follow_up_limit_needs_a_count_and_then_enforces_it(self):
        policy = conditional(follow_up_limit=1)
        self.assertFalse(decide(policy, PolicySubject()).allowed)
        self.assertIn("nobody counted", decide(policy, PolicySubject()).refusals[0])
        self.assertTrue(decide(policy, PolicySubject(follow_ups_so_far=0)).allowed)
        self.assertFalse(decide(policy, PolicySubject(follow_ups_so_far=1)).allowed)

    def test_every_failed_condition_is_reported_together(self):
        policy = conditional(role_terms={"engineer"}, locations={"india"},
                             allowed_attachments={".pdf"}, follow_up_limit=1)
        decision = decide(policy, PolicySubject(role_title="Chef", location="Paris",
                                                attachments=("notes.exe",), follow_ups_so_far=4))
        self.assertEqual(len(decision.refusals), 4,
                         "somebody fixing one condition should learn about the other three now")

    def test_conditions_cannot_open_what_the_rest_of_the_policy_shut(self):
        policy = conditional(role_terms={"engineer"})
        subject = PolicySubject(role_title="Engineer")
        decision = evaluate_policy(policy, source_id="jobicy", action=ActionKind.EMAIL_SEND,
                                   now=NOON, done_today=0, source_gate_allows=False,
                                   subject=subject)
        self.assertFalse(decision.allowed)
        self.assertIn("gate", decision.refusals[0])

    def test_a_subject_with_a_nonsense_count_is_refused_at_construction(self):
        with self.assertRaises(PolicyError):
            PolicySubject(follow_ups_so_far=-1)


class WiringTests(unittest.TestCase):
    """The conditions reach the one door that can send, and the count comes from the records."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.store = CareerStore(str(Path(self._temporary.name) / "conditions.sqlite3"))
        self.addCleanup(self.store.close)
        self.ledger = LocalMockIntegration()

    def draft(self, subject_line: str = "Hello", listing_id: str = "j1") -> EmailDraft:
        return EmailDraft(subject=subject_line, body="A short note about the role.",
                          listing_id=listing_id, recipient="someone@example.com")

    def dispatch(self, policy, *, identity="job:1", subject=None, draft=None):
        return guarded_dispatch(
            self.store, self.ledger, draft or self.draft(), identity_key=identity, policy=policy,
            source_id="jobicy", now=NOON, done_today=COUNT_FROM_RECORDS, source_gate_allows=True,
            subject=subject)

    def test_a_role_condition_refuses_the_send_and_sends_nothing(self):
        result = self.dispatch(conditional(role_terms={"engineer"}),
                               subject=PolicySubject(role_title="Pastry Chef"))
        self.assertFalse(result.performed)
        self.assertIn("matches none of the roles you authorised", result.detail + result.message)
        self.assertEqual(len(self.ledger.ledger.records()), 0)

    def test_the_follow_up_count_is_taken_from_the_records_when_nobody_passes_one(self):
        policy = conditional(follow_up_limit=1)
        first = self.dispatch(policy)
        self.assertTrue(first.performed, "nothing has gone to this job yet")
        second = self.dispatch(policy, draft=self.draft("Hello again", listing_id="j1b"))
        self.assertFalse(second.performed, "one follow-up per job means one")
        self.assertEqual(len(self.ledger.ledger.records()), 1)

    def test_a_permitted_subject_still_reaches_the_local_ledger_only(self):
        result = self.dispatch(
            conditional(role_terms={"engineer"}, locations={"india"},
                        allowed_attachments={".pdf"}),
            subject=PolicySubject(role_title="Backend Engineer", location="Pune, India",
                                  attachments=("tailored-resume.pdf",)))
        self.assertTrue(result.performed)
        self.assertEqual(len(self.ledger.ledger.records()), 1,
                         "the local stand-in is the only thing that ever receives anything here")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
