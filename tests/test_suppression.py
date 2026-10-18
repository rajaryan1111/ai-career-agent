"""The do-not-contact list: the one record here that exists for somebody who is not the user.

These tests are mostly about what *cannot* happen - a suppression lost on restart, walked around by
capitalisation, overwritten with a softer reason, expired by a clock, or removed as a side effect of
something else - because those are the failures that would put a message in front of somebody who
asked not to receive one.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from career_agent.event_log import log_path
from career_agent.integrations import (
    COUNT_FROM_RECORDS, EmailDraft, LocalMockIntegration, Outcome, guarded_dispatch,
)
from career_agent.policy import ActionKind, GlobalPolicy
from career_agent.store import CareerStore, StoredRecordError
from career_agent.suppression import (
    PERMANENT_REASONS, REASON_LABELS, SuppressionEntry, SuppressionError, SuppressionReason,
    normalise_address, refusal_message,
)

NOON = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


class AddressTests(unittest.TestCase):
    def test_the_same_person_written_two_ways_is_one_address(self):
        self.assertEqual(normalise_address("  Someone@Example.COM "), "someone@example.com")

    def test_what_is_not_one_address_is_refused(self):
        for value in ("", "   ", "someone", "a@b@c", "@example.com", "someone@",
                      "some one@example.com"):
            with self.subTest(value=value), self.assertRaises(SuppressionError):
                normalise_address(value)

    def test_provider_conventions_are_not_guessed_at(self):
        self.assertNotEqual(normalise_address("a.b@gmail.com"), normalise_address("ab@gmail.com"))
        self.assertNotEqual(normalise_address("a+jobs@x.com"), normalise_address("a@x.com"))


class EntryTests(unittest.TestCase):
    def test_an_entry_knows_whether_this_application_may_ever_lift_it(self):
        asked = SuppressionEntry("a@b.com", SuppressionReason.ASKED_TO_STOP, "2026-10-20")
        bounced = SuppressionEntry("a@b.com", SuppressionReason.BOUNCED_PERMANENTLY, "2026-10-20")
        self.assertTrue(asked.is_permanent)
        self.assertFalse(bounced.is_permanent)
        self.assertEqual(PERMANENT_REASONS, frozenset({SuppressionReason.ASKED_TO_STOP}))

    def test_every_reason_can_be_read_by_a_person(self):
        for reason in SuppressionReason:
            with self.subTest(reason=reason):
                self.assertIn(reason, REASON_LABELS)

    def test_an_entry_records_when_and_refuses_a_reason_it_does_not_know(self):
        with self.assertRaises(SuppressionError):
            SuppressionEntry("a@b.com", SuppressionReason.ASKED_TO_STOP, "   ")
        with self.assertRaises(SuppressionError):
            SuppressionEntry("a@b.com", "stop", "2026-10-20")  # type: ignore[arg-type]

    def test_the_refusal_says_why_and_where_to_change_it(self):
        entry = SuppressionEntry("a@b.com", SuppressionReason.ASKED_TO_STOP, "2026-10-20")
        message = refusal_message(entry)
        self.assertIn("do-not-contact list", message)
        self.assertIn("they asked not to be contacted", message)
        self.assertIn("nothing about this attempt changes it", message)


class StoredTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.database = Path(self._temporary.name) / "suppression.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)

    def test_a_suppression_survives_a_restart(self):
        self.store.suppress_contact("HR@Example.com", reason=SuppressionReason.ASKED_TO_STOP,
                                    note="replied asking us to stop")
        self.store.close()
        reopened = CareerStore(str(self.database))
        self.addCleanup(reopened.close)
        self.assertTrue(reopened.is_suppressed("hr@example.com"))

    def test_the_first_reason_wins_and_cannot_be_softened(self):
        first = self.store.suppress_contact("a@b.com", reason=SuppressionReason.ASKED_TO_STOP,
                                            note="they asked")
        again = self.store.suppress_contact("a@b.com", reason=SuppressionReason.OUR_OWN_DECISION)
        self.assertEqual(again, first,
                         "a request to stop must not become something softer on a second write")
        self.assertEqual(len(self.store.list_suppressions()), 1)

    def test_capitalisation_cannot_walk_around_a_suppression(self):
        self.store.suppress_contact("a@b.com", reason=SuppressionReason.WRONG_PERSON)
        self.assertTrue(self.store.is_suppressed("  A@B.COM "))

    def test_an_address_that_is_not_one_is_refused_rather_than_stored(self):
        with self.assertRaises(SuppressionError):
            self.store.suppress_contact("not-an-address", reason=SuppressionReason.ASKED_TO_STOP)
        self.assertEqual(self.store.list_suppressions(), ())

    def test_lifting_one_needs_a_reason_written_down(self):
        self.store.suppress_contact("a@b.com", reason=SuppressionReason.BOUNCED_PERMANENTLY)
        with self.assertRaises(SuppressionError):
            self.store.lift_suppression("a@b.com", note="ok")
        self.assertTrue(self.store.is_suppressed("a@b.com"),
                        "a refused lift must leave the suppression in place")
        self.assertTrue(self.store.lift_suppression("a@b.com", note="the address was corrected"))
        self.assertFalse(self.store.is_suppressed("a@b.com"))

    def test_lifting_something_that_is_not_there_reports_so(self):
        self.assertFalse(self.store.lift_suppression("a@b.com", note="tidying up"))

    def test_a_reason_this_build_cannot_read_still_blocks(self):
        self.store.suppress_contact("a@b.com", reason=SuppressionReason.ASKED_TO_STOP)
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE contact_suppression SET reason='whatever' WHERE address='a@b.com'")
        self.assertTrue(self.store.is_suppressed("a@b.com"),
                        "an unreadable reason is still a no")
        with self.assertRaises(StoredRecordError):
            self.store.suppression_for("a@b.com")

    def test_the_event_log_records_the_act_and_not_the_person(self):
        self.store.suppress_contact("someone@example.com", reason=SuppressionReason.ASKED_TO_STOP,
                                    note="they replied asking us to stop")
        written = log_path(self.database).read_text(encoding="utf-8")
        self.assertIn("suppression.recorded", written)
        self.assertNotIn("someone@example.com", written)
        self.assertNotIn("they replied", written)

    def test_suppressions_are_listed_oldest_first(self):
        self.store.suppress_contact("a@b.com", reason=SuppressionReason.ASKED_TO_STOP,
                                    now="2026-10-01T09:00:00+00:00")
        self.store.suppress_contact("c@d.com", reason=SuppressionReason.WRONG_PERSON,
                                    now="2026-10-02T09:00:00+00:00")
        self.assertEqual([entry.address for entry in self.store.list_suppressions()],
                         ["a@b.com", "c@d.com"])


class EnforcementTests(unittest.TestCase):
    """The list is checked before the one door that could send, and before anything is written."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.store = CareerStore(str(Path(self._temporary.name) / "door.sqlite3"))
        self.addCleanup(self.store.close)
        self.ledger = LocalMockIntegration()
        self.policy = GlobalPolicy(allowed=frozenset({("jobicy", ActionKind.EMAIL_SEND)}),
                                   daily_limits={ActionKind.EMAIL_SEND: 5})

    def send(self, recipient: str, *, identity: str = "job:1"):
        draft = EmailDraft(subject="About the role", body="A short note about the role.",
                           listing_id="j1", recipient=recipient)
        return guarded_dispatch(
            self.store, self.ledger, draft, identity_key=identity, policy=self.policy,
            source_id="jobicy", now=NOON, done_today=COUNT_FROM_RECORDS, source_gate_allows=True)

    def test_a_suppressed_address_is_refused_and_nothing_is_recorded_as_attempted(self):
        self.store.suppress_contact("hr@example.com", reason=SuppressionReason.ASKED_TO_STOP,
                                    note="they asked")
        result = self.send("HR@Example.com")
        self.assertFalse(result.performed)
        self.assertIs(result.outcome, Outcome.DISABLED)
        self.assertIn("do-not-contact list", result.message)
        self.assertEqual(self.store.list_attempts(), (),
                         "nothing was attempted, so no attempt is written down")
        self.assertEqual(len(self.ledger.ledger.records()), 0)

    def test_the_block_is_logged_as_a_count_and_not_as_an_address(self):
        self.store.suppress_contact("hr@example.com", reason=SuppressionReason.ASKED_TO_STOP)
        self.send("hr@example.com")
        written = log_path(Path(self.store.database_path)).read_text(encoding="utf-8")
        self.assertIn("suppression.blocked", written)
        self.assertNotIn("hr@example.com", written)

    def test_an_address_that_is_not_suppressed_still_goes_through(self):
        self.store.suppress_contact("someone.else@example.com",
                                    reason=SuppressionReason.ASKED_TO_STOP)
        result = self.send("hr@example.com")
        self.assertTrue(result.performed)
        self.assertEqual(len(self.ledger.ledger.records()), 1)

    def test_suppressing_after_one_message_stops_the_next(self):
        first = self.send("hr@example.com", identity="job:1")
        self.assertTrue(first.performed)
        self.store.suppress_contact("hr@example.com", reason=SuppressionReason.ASKED_TO_STOP,
                                    note="they replied asking us to stop")
        second = self.send("hr@example.com", identity="job:2")
        self.assertFalse(second.performed)
        self.assertEqual(len(self.ledger.ledger.records()), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
