"""Acceptance evidence that is actually recorded, rather than described.

Until now this project could say what a route would need before it could be switched on, but it had
nowhere to put the answer: ``held_evidence()`` returned nothing for every route, by construction.
These tests cover the table that holds it, and they are mostly about the ways a record like this
goes wrong - evidence with nothing to check, evidence quietly overwritten, a withdrawal with no
reason given, a route that looks ready because a stored row nobody can read was counted as proof,
and the worst one: recording evidence switching something on.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from career_agent import acceptance_evidence, sources
from career_agent import store as store_module
from career_agent.acceptance_evidence import (
    EVIDENCE_TITLES, ROUTE_REQUIREMENTS, EvidenceError, EvidenceKind, describe_all, describe_route,
    held_evidence, outstanding, route_is_ready,
)
from career_agent.event_log import log_path
from career_agent.store import CareerStore, StoredRecordError


class EvidenceStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        self.store = CareerStore(self.root / "evidence.sqlite3")
        self.addCleanup(self.store.close)

    def record(self, route: str = "ats_provider", kind: object = EvidenceKind.TERMS_REVIEW,
               reference: str = "research/source-permission-decision-matrix-2026-10-14.md#ats",
               note: str = "read the automation clauses end to end") -> object:
        return self.store.record_route_evidence(route, kind, reference=reference, note=note)


class RecordingTests(EvidenceStoreTestCase):
    def test_a_recorded_requirement_is_held_and_survives_a_reopen(self) -> None:
        entry = self.record()
        self.assertEqual(entry.route_id, "ats_provider")
        self.assertEqual(entry.kind, EvidenceKind.TERMS_REVIEW)
        self.assertTrue(entry.recorded_at)
        self.store.close()
        reopened = CareerStore(self.root / "evidence.sqlite3")
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.held_evidence_kinds("ats_provider"), (EvidenceKind.TERMS_REVIEW,))
        self.assertEqual(len(reopened.list_route_evidence("ats_provider")), 1)

    def test_held_evidence_is_returned_in_the_routes_own_requirement_order(self) -> None:
        route = next(item for item in ROUTE_REQUIREMENTS if item.route_id == "linkedin")
        for kind in reversed(route.kinds[:4]):
            self.record(route="linkedin", kind=kind, note=f"checked {kind.value}")
        self.assertEqual(self.store.held_evidence_kinds("linkedin"), route.kinds[:4])

    def test_evidence_is_recorded_per_route_and_never_spreads(self) -> None:
        self.record(route="unstop")
        self.assertEqual(self.store.held_evidence_kinds("unstop"), (EvidenceKind.TERMS_REVIEW,))
        for other in ("linkedin", "naukri", "internshala", "employer_site", "ats_provider"):
            with self.subTest(route=other):
                self.assertEqual(self.store.held_evidence_kinds(other), ())

    def test_the_event_log_records_the_route_and_the_kind_but_not_what_was_typed(self) -> None:
        self.record(reference="https://example.invalid/legal/terms?token=private",
                    note="spoke to Dana Patel on the partner desk")
        text = log_path(Path(self.store.database_path)).read_text(encoding="utf-8")
        self.assertIn("evidence.recorded", text)
        self.assertIn("route=ats_provider", text)
        self.assertIn("kind=terms_review", text)
        self.assertNotIn("Dana Patel", text)
        self.assertNotIn("token=private", text)

    def test_evidence_held_by_route_answers_for_every_known_route(self) -> None:
        self.record(route="naukri")
        held = self.store.evidence_held_by_route()
        self.assertEqual(set(held), {route.route_id for route in ROUTE_REQUIREMENTS})
        self.assertEqual(held["naukri"], (EvidenceKind.TERMS_REVIEW,))
        self.assertEqual(held["linkedin"], ())


class RefusalTests(EvidenceStoreTestCase):
    def test_an_unknown_route_is_refused(self) -> None:
        with self.assertRaises(EvidenceError) as caught:
            self.record(route="indeed")
        self.assertIn("not a route", str(caught.exception))

    def test_every_route_requires_every_kind_today_so_none_can_be_skipped(self) -> None:
        for route in ROUTE_REQUIREMENTS:
            with self.subTest(route=route.route_id):
                self.assertEqual(set(route.kinds), set(EvidenceKind))

    def test_a_kind_a_route_does_not_require_is_refused(self) -> None:
        """No route can drop a baseline requirement today, so this guard is tested with a stand-in.

        It stays in the code because the baseline is a decision, not a law: if a route is ever
        written with its own narrower list, recording evidence outside that list would prove
        nothing about it, and silently accepting the row would make it look readier than it is.
        """
        narrow = SimpleNamespace(route_id="narrow_route", display_name="A narrower route",
                                 kinds=(EvidenceKind.TERMS_REVIEW,))
        lookup = {"narrow_route": narrow}
        with mock.patch.object(store_module, "get_route",
                               lambda route_id: lookup.get(str(route_id).strip(),
                                                           acceptance_evidence.get_route(route_id))):
            self.record(route="narrow_route", note="their terms permit a read-only feed")
            with self.assertRaises(EvidenceError) as caught:
                self.record(route="narrow_route", kind=EvidenceKind.RATE_LIMITS,
                            note="they publish no limit at all")
        self.assertIn("does not list", str(caught.exception))

    def test_a_kind_this_build_does_not_know_is_refused(self) -> None:
        with self.assertRaises(EvidenceError) as caught:
            self.record(kind="looks_fine_to_me")
        self.assertIn("not a kind", str(caught.exception))

    def test_evidence_with_nothing_to_check_is_refused(self) -> None:
        for reference in ("", "   ", "ok"):
            with self.subTest(reference=reference):
                with self.assertRaises(EvidenceError) as caught:
                    self.record(reference=reference)
                self.assertIn("reference", str(caught.exception))
        self.assertEqual(self.store.held_evidence_kinds("ats_provider"), ())

    def test_evidence_with_no_note_of_what_was_checked_is_refused(self) -> None:
        for note in ("", "fine", "did it"):
            with self.subTest(note=note):
                with self.assertRaises(EvidenceError) as caught:
                    self.record(note=note)
                self.assertIn("what was actually checked", str(caught.exception))
        self.assertEqual(self.store.held_evidence_kinds("ats_provider"), ())

    def test_recording_the_same_requirement_twice_is_refused_rather_than_overwritten(self) -> None:
        first = self.record(reference="first-reference.md", note="the first reading, in full")
        with self.assertRaises(EvidenceError) as caught:
            self.record(reference="second-reference.md", note="a different reading entirely")
        self.assertIn("already recorded", str(caught.exception))
        self.assertIn("Withdraw that record first", str(caught.exception))
        held = self.store.list_route_evidence("ats_provider")
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0].reference, first.reference)
        self.assertEqual(held[0].note, "the first reading, in full")

    def test_a_refused_record_writes_nothing_at_all(self) -> None:
        before = self.store._connection.total_changes
        for attempt in (lambda: self.record(reference="x"), lambda: self.record(note="x"),
                        lambda: self.record(route="indeed")):
            with self.assertRaises(EvidenceError):
                attempt()
        self.assertEqual(self.store._connection.total_changes, before)


class WithdrawalTests(EvidenceStoreTestCase):
    def test_withdrawing_needs_a_reason(self) -> None:
        self.record()
        with self.assertRaises(EvidenceError) as caught:
            self.store.withdraw_route_evidence("ats_provider", EvidenceKind.TERMS_REVIEW, note="no")
        self.assertIn("short reason", str(caught.exception))
        self.assertEqual(self.store.held_evidence_kinds("ats_provider"), (EvidenceKind.TERMS_REVIEW,))

    def test_withdrawing_removes_exactly_one_row_and_is_logged(self) -> None:
        self.record()
        self.record(kind=EvidenceKind.RATE_LIMITS, note="their documented limit is 60 a minute")
        removed = self.store.withdraw_route_evidence(
            "ats_provider", EvidenceKind.TERMS_REVIEW, note="their terms changed in October")
        self.assertTrue(removed)
        self.assertEqual(self.store.held_evidence_kinds("ats_provider"), (EvidenceKind.RATE_LIMITS,))
        text = log_path(Path(self.store.database_path)).read_text(encoding="utf-8")
        self.assertIn("evidence.withdrawn", text)
        self.assertNotIn("their terms changed in October", text)

    def test_withdrawing_what_was_never_recorded_reports_false_and_logs_nothing(self) -> None:
        self.assertFalse(self.store.withdraw_route_evidence(
            "ats_provider", EvidenceKind.TERMS_REVIEW, note="tidying up"))
        self.assertNotIn("evidence.withdrawn", log_path(Path(self.store.database_path)).read_text(encoding="utf-8"))

    def test_a_withdrawn_requirement_can_be_recorded_again(self) -> None:
        self.record(reference="old-terms.md", note="the reading from July")
        self.store.withdraw_route_evidence("ats_provider", EvidenceKind.TERMS_REVIEW,
                                           note="superseded in October")
        again = self.record(reference="new-terms.md", note="the reading from October")
        self.assertEqual(again.reference, "new-terms.md")
        self.assertEqual(len(self.store.list_route_evidence("ats_provider")), 1)


class ReadinessTests(EvidenceStoreTestCase):
    def fill(self, route_id: str) -> None:
        route = next(item for item in ROUTE_REQUIREMENTS if item.route_id == route_id)
        for kind in route.kinds:
            self.record(route=route_id, kind=kind, reference=f"evidence/{route_id}-{kind.value}.md",
                        note=f"checked {EVIDENCE_TITLES[kind].lower()}")

    def test_a_route_is_outstanding_until_every_requirement_is_recorded(self) -> None:
        route = next(item for item in ROUTE_REQUIREMENTS if item.route_id == "unstop")
        self.assertEqual(len(outstanding("unstop", held=self.store.held_evidence_kinds("unstop"))),
                         len(route.kinds))
        self.record(route="unstop", kind=route.kinds[0], note="checked the first requirement")
        held = self.store.held_evidence_kinds("unstop")
        self.assertEqual(len(outstanding("unstop", held=held)), len(route.kinds) - 1)
        self.assertNotIn(route.kinds[0], outstanding("unstop", held=held))
        self.assertFalse(route_is_ready("unstop", held=held))

    def test_a_fully_evidenced_route_reads_as_ready_and_still_enables_nothing(self) -> None:
        self.fill("ats_provider")
        held = self.store.held_evidence_kinds("ats_provider")
        self.assertEqual(outstanding("ats_provider", held=held), ())
        self.assertTrue(route_is_ready("ats_provider", held=held))
        # The point of the whole exercise: a ready route is not a running one.
        self.assertFalse(sources.SOURCE_QUALITY_GATE_PASSED)
        self.assertEqual(sources.enabled_discovery_sources(), ())
        for source_id in ("jobicy", "remotive", "linkedin"):
            with self.subTest(source_id=source_id):
                self.assertFalse(sources.discovery_gate(source_id).allowed)
                self.assertFalse(sources.submission_gate(source_id).allowed)

    def test_the_written_requirements_are_unchanged_by_what_a_person_records(self) -> None:
        self.fill("naukri")
        self.assertEqual(held_evidence("naukri"), ())
        self.assertEqual(len(outstanding("naukri")), len(
            next(item for item in ROUTE_REQUIREMENTS if item.route_id == "naukri").kinds))
        self.assertIn("0 are ready", "\n".join(describe_all()))

    def test_the_description_counts_what_is_held_when_it_is_given_the_evidence(self) -> None:
        self.record(route="internshala", note="read their automation policy")
        held = {route.route_id: self.store.held_evidence_kinds(route.route_id)
                for route in ROUTE_REQUIREMENTS}
        lines = "\n".join(describe_route("internshala", held=held["internshala"]))
        route = next(item for item in ROUTE_REQUIREMENTS if item.route_id == "internshala")
        self.assertIn(f"Outstanding: {len(route.kinds) - 1} of {len(route.kinds)}", lines)
        self.assertNotIn("terms of service and robots policy", lines)
        self.assertIn("0 are ready", "\n".join(describe_all(held_by_route=held)))

    def test_a_stored_kind_this_build_cannot_read_never_counts_as_proof(self) -> None:
        self.record()
        self.store._connection.execute(
            "INSERT INTO route_evidence (route_id, kind, recorded_at, reference, note) "
            "VALUES (?, ?, ?, ?, ?)",
            ("ats_provider", "approved_by_someone", "2026-10-18T09:00:00+00:00", "ref.md", "fine"))
        self.store._connection.commit()
        self.assertEqual(self.store.held_evidence_kinds("ats_provider"), (EvidenceKind.TERMS_REVIEW,))
        self.assertFalse(route_is_ready("ats_provider",
                                        held=self.store.held_evidence_kinds("ats_provider")))
        with self.assertRaises(StoredRecordError) as caught:
            self.store.list_route_evidence("ats_provider")
        self.assertIn("counts for nothing", str(caught.exception))


class OlderFileTests(EvidenceStoreTestCase):
    def test_an_older_schema_is_migrated_and_keeps_what_was_there(self) -> None:
        path = self.root / "older.sqlite3"
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA user_version = 14")
        connection.commit()
        connection.close()
        store = CareerStore(path)
        self.addCleanup(store.close)
        self.assertEqual(store.held_evidence_kinds("linkedin"), ())
        entry = store.record_route_evidence(
            "linkedin", EvidenceKind.NO_CIRCUMVENTION, reference="career_agent/sources.py",
            note="no captcha solving anywhere in this build")
        self.assertEqual(entry.kind, EvidenceKind.NO_CIRCUMVENTION)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
