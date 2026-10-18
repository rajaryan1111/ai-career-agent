"""Tests for attempts with uncertain outcomes: write-ahead, no blind retries, reconciliation.

Nothing here sends anything. The integration under test is the local stand-in, which contacts
nothing, and every dispatch in this module is refused before it reaches even that, because no policy
permits it and no gate is open. What is being tested is the bookkeeping that would make a retry safe
if anything were ever permitted.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career_agent.attempts import (
    DEFAULT_STALE_AFTER, AttemptError, AttemptRecord, AttemptState, attempts_needing_reconciliation,
    may_attempt, reconciliation_summary, state_from_outcome,
)
from career_agent.event_log import log_path
from career_agent.integrations import (
    COUNT_FROM_RECORDS, DisabledIntegration, EmailDraft, LocalMockIntegration, Outcome,
    authorised_dispatch, guarded_dispatch,
)
from career_agent.policy import ActionKind, GlobalPolicy, evaluate_policy
from career_agent.store import CareerStore, StoredRecordError

NOON = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
IDENTITY = "requisition:example employer:req-42"
EMAIL = ActionKind.EMAIL_SEND.value


def record(operation_id="op-1", *, state=AttemptState.UNKNOWN, identity=IDENTITY, action=EMAIL,
           started="2026-10-20T09:00:00+00:00", settled=None) -> AttemptRecord:
    if state is not AttemptState.UNKNOWN and settled is None:
        settled = "2026-10-20T09:05:00+00:00"
    return AttemptRecord(operation_id=operation_id, identity_key=identity, action=action,
                         state=state, started_at=started, settled_at=settled)


class AttemptRecordTests(unittest.TestCase):
    """The record refuses to describe a state it cannot honestly be in."""

    def test_an_unknown_attempt_has_no_settled_time(self):
        with self.assertRaises(AttemptError):
            AttemptRecord(operation_id="op", identity_key=IDENTITY, action=EMAIL,
                          state=AttemptState.UNKNOWN, started_at="2026-10-20T09:00:00+00:00",
                          settled_at="2026-10-20T09:05:00+00:00")

    def test_a_settled_attempt_must_say_when(self):
        with self.assertRaises(AttemptError):
            AttemptRecord(operation_id="op", identity_key=IDENTITY, action=EMAIL,
                          state=AttemptState.PERFORMED, started_at="2026-10-20T09:00:00+00:00")

    def test_the_parts_that_identify_an_attempt_are_required(self):
        for missing in ("operation_id", "identity_key", "action", "started_at"):
            fields = {"operation_id": "op", "identity_key": IDENTITY, "action": EMAIL,
                      "started_at": "2026-10-20T09:00:00+00:00", "state": AttemptState.UNKNOWN}
            fields[missing] = "  "
            with self.subTest(missing=missing), self.assertRaises(AttemptError):
                AttemptRecord(**fields)

    def test_an_unknown_attempt_says_its_outcome_was_never_established(self):
        self.assertIn("never established", record().describe())


class RetryRuleTests(unittest.TestCase):
    """What a prior attempt permits, and what it forbids."""

    def test_nothing_recorded_means_a_first_attempt_is_allowed(self):
        decision = may_attempt((), identity_key=IDENTITY, action=EMAIL)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reasons, ())

    def test_an_unknown_outcome_blocks_the_next_attempt(self):
        decision = may_attempt((record("op-1"),), identity_key=IDENTITY, action=EMAIL)
        self.assertFalse(decision.allowed)
        self.assertIn("without an established outcome", decision.reasons[0])
        self.assertEqual(decision.blocking_operation_ids, ("op-1",))
        self.assertIn("Refused", decision.describe())

    def test_something_already_performed_is_not_retried_either(self):
        decision = may_attempt((record("op-1", state=AttemptState.PERFORMED),),
                               identity_key=IDENTITY, action=EMAIL)
        self.assertFalse(decision.allowed)
        self.assertIn("duplicate", decision.reasons[0])

    def test_a_known_failure_or_refusal_may_be_tried_again(self):
        for state in (AttemptState.FAILED, AttemptState.REFUSED):
            with self.subTest(state=state):
                decision = may_attempt((record("op-1", state=state),),
                                       identity_key=IDENTITY, action=EMAIL)
                self.assertTrue(decision.allowed)

    def test_every_blocking_reason_is_reported_not_only_the_first(self):
        decision = may_attempt(
            (record("op-1"), record("op-2", state=AttemptState.PERFORMED)),
            identity_key=IDENTITY, action=EMAIL)
        self.assertEqual(len(decision.reasons), 2)
        self.assertEqual(set(decision.blocking_operation_ids), {"op-1", "op-2"})

    def test_another_job_or_another_action_is_judged_on_its_own_record(self):
        history = (record("op-1"),)
        self.assertTrue(may_attempt(history, identity_key="listing:https://x.invalid/1",
                                    action=EMAIL).allowed)
        self.assertTrue(may_attempt(history, identity_key=IDENTITY,
                                    action=ActionKind.SUBMISSION.value).allowed)

    def test_a_blank_identity_or_action_is_a_programming_error(self):
        with self.assertRaises(AttemptError):
            may_attempt((), identity_key="  ", action=EMAIL)
        with self.assertRaises(AttemptError):
            may_attempt((), identity_key=IDENTITY, action="")


class OutcomeTranslationTests(unittest.TestCase):
    """What an integration reports, and what may honestly be recorded about it."""

    def test_a_completed_or_duplicate_dispatch_is_performed(self):
        self.assertIs(state_from_outcome("completed", performed=True), AttemptState.PERFORMED)
        self.assertIs(state_from_outcome("duplicate", performed=False), AttemptState.PERFORMED)

    def test_a_refusal_before_anything_was_tried_is_knowledge(self):
        for value in ("disabled", "invalid", "unsupported"):
            with self.subTest(value=value):
                self.assertIs(state_from_outcome(value, performed=False), AttemptState.REFUSED)

    def test_a_failed_dispatch_is_unknown_not_failed(self):
        self.assertIs(state_from_outcome("failed", performed=False), AttemptState.UNKNOWN,
                      "a failure mid-flight may still have arrived")

    def test_an_outcome_nobody_recognises_raises_rather_than_being_guessed(self):
        with self.assertRaises(AttemptError):
            state_from_outcome("probably fine", performed=False)


class StalenessTests(unittest.TestCase):
    """Age is a reason to look, never a reason to decide."""

    def test_an_old_unknown_attempt_is_listed_for_a_person_to_check(self):
        old = record("op-1", started=(NOON - timedelta(days=2)).isoformat())
        self.assertEqual(attempts_needing_reconciliation((old,), now=NOON), (old,))

    def test_a_fresh_unknown_attempt_is_not_hurried(self):
        fresh = record("op-1", started=(NOON - timedelta(minutes=5)).isoformat())
        self.assertEqual(attempts_needing_reconciliation((fresh,), now=NOON), ())

    def test_a_settled_attempt_is_never_listed(self):
        old = record("op-1", state=AttemptState.PERFORMED,
                     started=(NOON - timedelta(days=9)).isoformat())
        self.assertEqual(attempts_needing_reconciliation((old,), now=NOON), ())

    def test_the_threshold_is_configurable_and_the_default_is_hours_not_days(self):
        attempt = record("op-1", started=(NOON - timedelta(hours=2)).isoformat())
        self.assertEqual(attempts_needing_reconciliation((attempt,), now=NOON), ())
        self.assertEqual(
            attempts_needing_reconciliation((attempt,), now=NOON, stale_after=timedelta(hours=1)),
            (attempt,))
        self.assertEqual(DEFAULT_STALE_AFTER, timedelta(hours=6))

    def test_a_naive_moment_or_start_time_is_refused(self):
        with self.assertRaises(AttemptError):
            attempts_needing_reconciliation((record(),), now=datetime(2026, 10, 20, 12))
        naive = record("op-1", started="2026-10-20T09:00:00")
        with self.assertRaises(AttemptError):
            attempts_needing_reconciliation((naive,), now=NOON)

    def test_the_summary_counts_without_naming_anybody(self):
        line = reconciliation_summary((record("op-1"),
                                       record("op-2", state=AttemptState.PERFORMED)))
        self.assertIn("2 attempt(s)", line)
        self.assertIn("block further attempts", line)
        self.assertNotIn(IDENTITY, line)
        self.assertEqual(reconciliation_summary(()), "No attempt has been recorded.")


class StoredAttemptTests(unittest.TestCase):
    """The durable half: written before the act, idempotent, and never silently rewritten."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.database = Path(self._temporary.name) / "attempts.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)

    def begin(self, operation_id="op-1"):
        return self.store.begin_attempt(operation_id=operation_id, identity_key=IDENTITY,
                                        action=EMAIL)

    def test_an_attempt_is_written_as_unknown_before_anything_happens(self):
        attempt = self.begin()
        self.assertIs(attempt.state, AttemptState.UNKNOWN)
        self.assertIsNone(attempt.settled_at)
        self.assertEqual(self.store.unresolved_attempts(), (attempt,))

    def test_starting_the_same_operation_twice_writes_one_row(self):
        first = self.begin()
        before = self.store._connection.total_changes
        again = self.begin()
        self.assertEqual(again, first)
        self.assertEqual(self.store._connection.total_changes, before)
        self.assertEqual(len(self.store.list_attempts()), 1)

    def test_reusing_an_operation_id_for_another_job_is_refused(self):
        self.begin()
        with self.assertRaises(AttemptError):
            self.store.begin_attempt(operation_id="op-1", identity_key="listing:other",
                                     action=EMAIL)

    def test_settling_records_the_outcome_and_the_time(self):
        self.begin()
        settled = self.store.settle_attempt("op-1", state=AttemptState.PERFORMED, detail="sent")
        self.assertIs(settled.state, AttemptState.PERFORMED)
        self.assertTrue(settled.settled_at)
        self.assertEqual(self.store.unresolved_attempts(), ())

    def test_a_settled_outcome_is_not_rewritten(self):
        self.begin()
        self.store.settle_attempt("op-1", state=AttemptState.REFUSED, detail="no authorisation")
        with self.assertRaises(AttemptError):
            self.store.settle_attempt("op-1", state=AttemptState.PERFORMED, detail="actually fine")

    def test_settling_to_unknown_keeps_it_blocking_and_keeps_what_was_seen(self):
        self.begin()
        still = self.store.settle_attempt("op-1", state=AttemptState.UNKNOWN,
                                          detail="the connection dropped")
        self.assertIs(still.state, AttemptState.UNKNOWN)
        self.assertEqual(self.store.unresolved_attempts()[0].detail, "the connection dropped")
        self.assertFalse(may_attempt(self.store.list_attempts(), identity_key=IDENTITY,
                                     action=EMAIL).allowed)

    def test_settling_something_that_was_never_started_is_refused(self):
        with self.assertRaises(AttemptError):
            self.store.settle_attempt("op-never", state=AttemptState.PERFORMED)

    def test_reconciling_needs_evidence_and_keeps_it(self):
        self.begin()
        with self.assertRaises(AttemptError):
            self.store.reconcile_attempt("op-1", state=AttemptState.PERFORMED, evidence="  ")
        reconciled = self.store.reconcile_attempt(
            "op-1", state=AttemptState.PERFORMED,
            evidence="found it in the sent folder at 09:07")
        self.assertIs(reconciled.state, AttemptState.PERFORMED)
        self.assertIn("sent folder", reconciled.evidence)
        self.assertIn("sent folder", self.store.get_attempt("op-1").evidence)

    def test_reconciling_to_unknown_is_not_reconciliation(self):
        self.begin()
        with self.assertRaises(AttemptError):
            self.store.reconcile_attempt("op-1", state=AttemptState.UNKNOWN,
                                         evidence="still no idea")

    def test_a_reconciled_attempt_stops_blocking_the_next_one(self):
        self.begin()
        self.store.reconcile_attempt("op-1", state=AttemptState.FAILED,
                                     evidence="the provider shows no record of it")
        self.assertTrue(may_attempt(self.store.list_attempts(), identity_key=IDENTITY,
                                    action=EMAIL).allowed)

    def test_attempts_survive_a_restart_and_still_block(self):
        self.begin()
        self.store.close()
        reopened = CareerStore(str(self.database))
        self.addCleanup(reopened.close)
        self.assertFalse(may_attempt(reopened.list_attempts(), identity_key=IDENTITY,
                                     action=EMAIL).allowed)

    def test_a_damaged_row_is_reported_rather_than_read_as_nothing_attempted(self):
        self.begin()
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE action_attempt SET state='probably fine' WHERE operation_id='op-1'")
        with self.assertRaises(StoredRecordError):
            self.store.list_attempts()
        from career_agent.store import unreadable_stored_records

        self.assertTrue(any("action_attempt" in line
                            for line in unreadable_stored_records(self.database)))

    def test_the_log_records_the_action_and_the_state_and_nobody_s_name(self):
        self.begin()
        self.store.settle_attempt("op-1", state=AttemptState.REFUSED, detail="no authorisation")
        written = log_path(self.database).read_text(encoding="utf-8")
        self.assertIn("attempt.started", written)
        self.assertIn("attempt.settled", written)
        self.assertNotIn(IDENTITY, written, "a job identity is not an event detail")


class GuardedDispatchTests(unittest.TestCase):
    """The dispatch door that keeps the record. Everything here is still refused."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.store = CareerStore(str(Path(self._temporary.name) / "dispatch.sqlite3"))
        self.addCleanup(self.store.close)
        self.draft = EmailDraft(subject="Following up", body="Thank you for your time.",
                                recipient="someone@example.invalid", operation_id="op-1")
        self.policy = GlobalPolicy(
            allowed=frozenset({("follow-ups", ActionKind.EMAIL_SEND)}),
            daily_limits={ActionKind.EMAIL_SEND: 2})

    def dispatch(self, integration, **overrides):
        arguments = {
            "identity_key": IDENTITY, "policy": self.policy, "source_id": "follow-ups",
            "now": NOON, "done_today": 0, "source_gate_allows": True,
        }
        arguments.update(overrides)
        return guarded_dispatch(self.store, integration, self.draft, **arguments)

    def test_the_attempt_is_recorded_even_though_the_dispatch_was_refused(self):
        result = self.dispatch(DisabledIntegration())
        self.assertFalse(result.performed)
        stored = self.store.get_attempt("op-1")
        self.assertIs(stored.state, AttemptState.REFUSED,
                      "a refusal is knowledge: nothing was attempted")
        self.assertTrue(may_attempt(self.store.list_attempts(), identity_key=IDENTITY,
                                    action=EMAIL).allowed)

    def test_a_performed_dispatch_blocks_a_second_one_for_the_same_job(self):
        ledger = LocalMockIntegration()
        first = self.dispatch(ledger)
        self.assertTrue(first.performed)
        self.assertIs(self.store.get_attempt("op-1").state, AttemptState.PERFORMED)
        second = EmailDraft(subject="Following up again", body="Just checking in.",
                            recipient="someone@example.invalid", operation_id="op-2")
        blocked = guarded_dispatch(self.store, ledger, second, identity_key=IDENTITY,
                                   policy=self.policy, source_id="follow-ups", now=NOON,
                                   done_today=1, source_gate_allows=True)
        self.assertIs(blocked.outcome, Outcome.INVALID)
        self.assertFalse(blocked.performed)
        self.assertIn("duplicate", blocked.message)
        self.assertEqual(len(ledger.ledger.records()), 1)
        self.assertIsNone(self.store.get_attempt("op-2"),
                          "a refused attempt that never ran is not written as one")

    def test_a_failed_dispatch_is_recorded_as_unknown_and_blocks_a_blind_retry(self):
        ledger = LocalMockIntegration(fail_operation_ids={"op-1": 5})
        result = self.dispatch(ledger, attempts=1)
        self.assertFalse(result.performed)
        self.assertIs(self.store.get_attempt("op-1").state, AttemptState.UNKNOWN)
        self.assertIn("could not be established", result.message)
        retry = EmailDraft(subject="Following up", body="Thank you for your time.",
                           recipient="someone@example.invalid", operation_id="op-3")
        blocked = guarded_dispatch(self.store, ledger, retry, identity_key=IDENTITY,
                                   policy=self.policy, source_id="follow-ups", now=NOON,
                                   done_today=0, source_gate_allows=True)
        self.assertFalse(blocked.performed)
        self.assertIn("reconcile", blocked.message)

    def test_reconciling_the_unknown_attempt_is_what_unblocks_it(self):
        ledger = LocalMockIntegration(fail_operation_ids={"op-1": 5})
        self.dispatch(ledger, attempts=1)
        self.store.reconcile_attempt("op-1", state=AttemptState.FAILED,
                                     evidence="nothing in the provider's log for that id")
        self.assertTrue(may_attempt(self.store.list_attempts(), identity_key=IDENTITY,
                                    action=EMAIL).allowed)

    def test_the_same_job_on_another_source_is_the_same_identity_and_is_blocked(self):
        """The cross-source point: one identity key, one application, whichever source found it."""
        ledger = LocalMockIntegration()
        self.dispatch(ledger)
        from career_agent.core import Availability, JobListing
        from career_agent.identity import identity_key

        elsewhere = JobListing(
            listing_id="b", source_id="elsewhere", source_name="Elsewhere",
            source_listing_url="https://other.invalid/jobs/9", employer_name="Example Employer",
            role_title="GenAI Engineer", availability_status=Availability.OPEN,
            canonical_requisition_id="REQ-42")
        second = EmailDraft(subject="Following up", body="Thank you.",
                            recipient="someone@example.invalid", operation_id="op-9")
        blocked = guarded_dispatch(self.store, ledger, second,
                                   identity_key=identity_key(elsewhere), policy=self.policy,
                                   source_id="follow-ups", now=NOON, done_today=1,
                                   source_gate_allows=True)
        self.assertEqual(identity_key(elsewhere), IDENTITY)
        self.assertFalse(blocked.performed)
        self.assertEqual(len(ledger.ledger.records()), 1)

    def test_an_identical_draft_derives_the_same_operation_id_and_is_not_sent_twice(self):
        ledger = LocalMockIntegration()
        first = EmailDraft(subject="Hello", body="Hello.", recipient="someone@example.invalid")
        again = EmailDraft(subject="Hello", body="Hello.", recipient="someone@example.invalid")
        self.assertEqual(first.operation_id, again.operation_id,
                         "the same message must not look like two operations")
        sent = guarded_dispatch(self.store, ledger, first, identity_key=IDENTITY,
                                policy=self.policy, source_id="follow-ups", now=NOON,
                                done_today=0, source_gate_allows=True)
        self.assertTrue(sent.performed)
        repeat = guarded_dispatch(self.store, ledger, again, identity_key=IDENTITY,
                                  policy=self.policy, source_id="follow-ups", now=NOON,
                                  done_today=1, source_gate_allows=True)
        self.assertFalse(repeat.performed)
        self.assertEqual(len(ledger.ledger.records()), 1)
        self.assertEqual(len(self.store.list_attempts()), 1)

    def test_a_request_whose_operation_id_was_emptied_is_refused_before_anything_is_written(self):
        # A draft derives its own id, so this state cannot be reached through the constructor; the
        # guard exists for a future request type that forgets one, and is exercised here directly.
        ledger = LocalMockIntegration()
        draft = EmailDraft(subject="Hello", body="Hello.", recipient="someone@example.invalid")
        object.__setattr__(draft, "operation_id", "")
        result = guarded_dispatch(self.store, ledger, draft, identity_key=IDENTITY,
                                  policy=self.policy, source_id="follow-ups", now=NOON,
                                  done_today=0, source_gate_allows=True)
        self.assertIs(result.outcome, Outcome.INVALID)
        self.assertEqual(self.store.list_attempts(), ())
        self.assertEqual(ledger.ledger.records(), ())

    def test_a_dispatch_without_an_identity_is_a_programming_error(self):
        with self.assertRaises(AttemptError):
            self.dispatch(LocalMockIntegration(), identity_key="   ")

    def test_the_policy_still_decides_and_a_closed_gate_still_refuses(self):
        ledger = LocalMockIntegration()
        result = self.dispatch(ledger, source_gate_allows=False)
        self.assertFalse(result.performed)
        self.assertEqual(ledger.ledger.records(), ())
        self.assertIs(self.store.get_attempt("op-1").state, AttemptState.REFUSED)
        self.assertEqual(
            authorised_dispatch(ledger, self.draft, policy=None, source_id="follow-ups", now=NOON,
                                done_today=0, source_gate_allows=True).performed, False)


class ActionSpellingTests(unittest.TestCase):
    """One action has one name, whoever is holding it.

    Regression: attempts were stored with ``str(ActionKind.DISCOVERY)`` - the literal text
    ``"ActionKind.DISCOVERY"`` - so an attempt recorded by a caller holding the enum could never be
    found by a caller passing ``"discovery"``. The duplicate block only works if the next caller
    finds the row, so this is the whole feature failing quietly, not a cosmetic difference.
    """

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.store = CareerStore(str(Path(self._temporary.name) / "spelling.sqlite3"))
        self.addCleanup(self.store.close)

    def test_an_enum_and_its_value_are_the_same_action(self):
        self.store.begin_attempt(operation_id="op-1", identity_key="job:1",
                                 action=ActionKind.DISCOVERY)
        stored = self.store.get_attempt("op-1")
        self.assertEqual(stored.action, "discovery",
                         "the stored name must be the one everybody else uses")
        self.assertEqual(len(self.store.list_attempts(action="discovery")), 1,
                         "a caller holding the string must find what the enum recorded")
        self.assertEqual(len(self.store.list_attempts(action=ActionKind.DISCOVERY)), 1)

    def test_reusing_an_id_across_the_two_spellings_is_still_the_same_attempt(self):
        first = self.store.begin_attempt(operation_id="op-1", identity_key="job:1",
                                         action=ActionKind.DISCOVERY)
        again = self.store.begin_attempt(operation_id="op-1", identity_key="job:1",
                                         action="discovery")
        self.assertEqual(first, again, "the same attempt, written one way and read the other")


class DailyCountTests(unittest.TestCase):
    """The count a daily limit needs, taken from rows rather than from memory."""

    MIDDAY = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.store = CareerStore(str(Path(self._temporary.name) / "counting.sqlite3"))
        self.addCleanup(self.store.close)

    def attempt(self, operation_id, *, action="discovery", at=None, state=None, detail="done"):
        record = self.store.begin_attempt(
            operation_id=operation_id, identity_key="job:1", action=action,
            now=(at or self.MIDDAY).isoformat())
        if state is not None:
            self.store.settle_attempt(operation_id, state=state, detail=detail)
        return record

    def test_nothing_recorded_is_nothing_done(self):
        self.assertEqual(self.store.actions_done_today("discovery", now=self.MIDDAY), 0)

    def test_a_refusal_does_not_spend_the_allowance_it_protected(self):
        self.attempt("op-1", state=AttemptState.REFUSED, detail="the gate is closed")
        self.assertEqual(self.store.actions_done_today("discovery", now=self.MIDDAY), 0)

    def test_an_unknown_outcome_counts_because_it_may_have_happened(self):
        self.attempt("op-1")
        self.assertEqual(self.store.actions_done_today("discovery", now=self.MIDDAY), 1)

    def test_performed_and_failed_both_count(self):
        self.attempt("op-1", state=AttemptState.PERFORMED)
        self.attempt("op-2", state=AttemptState.FAILED, detail="the server said no")
        self.assertEqual(self.store.actions_done_today("discovery", now=self.MIDDAY), 2)

    def test_each_action_has_its_own_allowance(self):
        self.attempt("op-1", action="discovery")
        self.attempt("op-2", action="email_send")
        self.assertEqual(self.store.actions_done_today("discovery", now=self.MIDDAY), 1)
        self.assertEqual(self.store.actions_done_today(ActionKind.EMAIL_SEND, now=self.MIDDAY), 1)

    def test_the_day_is_the_persons_day_not_yesterdays(self):
        self.attempt("op-1", at=self.MIDDAY - timedelta(days=1))
        self.attempt("op-2", at=self.MIDDAY)
        self.assertEqual(self.store.actions_done_today("discovery", now=self.MIDDAY), 1)

    def test_the_day_boundary_follows_the_timezone_of_the_moment(self):
        """The same two instants are one day apart in Delhi and the same day in UTC."""
        acted = datetime(2026, 10, 20, 18, 0, tzinfo=timezone.utc)   # 23:30 on the 20th in Delhi
        asked = datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc)   # 01:30 on the 21st in Delhi
        self.attempt("op-1", at=acted)
        delhi = timezone(timedelta(hours=5, minutes=30))
        self.assertEqual(self.store.actions_done_today("discovery", now=asked), 1,
                         "in UTC both instants fall on the 20th")
        self.assertEqual(
            self.store.actions_done_today("discovery", now=asked.astimezone(delhi)), 0,
            "past midnight where the person is, the allowance has reset")

    def test_a_moment_without_a_timezone_is_refused(self):
        with self.assertRaises(ValueError):
            self.store.actions_done_today("discovery", now=datetime(2026, 10, 20, 12, 0))

    def test_a_dispatch_can_count_for_itself_rather_than_being_told(self):
        """``COUNT_FROM_RECORDS`` closes the loop: the limit is enforced from durable rows."""
        ledger = LocalMockIntegration()
        policy = GlobalPolicy(allowed=frozenset({("jobicy", ActionKind.EMAIL_SEND)}),
                              daily_limits={ActionKind.EMAIL_SEND: 1})
        draft = EmailDraft(subject="Hello", body="A short note about the role.",
                           listing_id="j1", recipient="someone@example.com")
        first = guarded_dispatch(
            self.store, ledger, draft, identity_key="job:1", policy=policy, source_id="jobicy",
            now=self.MIDDAY, done_today=COUNT_FROM_RECORDS, source_gate_allows=True)
        self.assertTrue(first.performed,
                        "the first of an allowance of one is not refused for spending itself")
        self.assertEqual(self.store.actions_done_today(ActionKind.EMAIL_SEND, now=self.MIDDAY), 1)

        second = guarded_dispatch(
            self.store, ledger,
            EmailDraft(subject="Hello again", body="A note about a different role.",
                       listing_id="j2", recipient="someone.else@example.com"),
            identity_key="job:2",
            policy=policy, source_id="jobicy", now=self.MIDDAY, done_today=COUNT_FROM_RECORDS,
            source_gate_allows=True)
        self.assertFalse(second.performed, "one a day is one a day, counted from the records")
        self.assertIn("limit", second.message.lower())
        self.assertEqual(len(ledger.ledger.records()), 1,
                         "only the permitted one reached the local ledger")
        self.assertEqual(self.store.actions_done_today(ActionKind.EMAIL_SEND, now=self.MIDDAY), 1,
                         "the refusal did not consume the allowance it enforced")

    def test_the_count_feeds_a_real_limit(self):
        policy = GlobalPolicy(allowed=frozenset({("jobicy", ActionKind.DISCOVERY)}),
                              daily_limits={ActionKind.DISCOVERY: 1})
        self.attempt("op-1", state=AttemptState.PERFORMED)
        decision = evaluate_policy(
            policy, source_id="jobicy", action=ActionKind.DISCOVERY, now=self.MIDDAY,
            done_today=self.store.actions_done_today(ActionKind.DISCOVERY, now=self.MIDDAY),
            source_gate_allows=True)
        self.assertFalse(decision.allowed, "one a day means the second is refused")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
