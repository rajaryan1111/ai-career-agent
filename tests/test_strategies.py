"""Tests for versioned role strategies: the model's boundaries, the store's append-only promise.

Every strategy here is invented - a name, a role family, places and employers that exist only in this
file - because a strategy is the person's own statement of intent and a fixture must never carry one.
Every database is a disposable temporary file.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from career_agent import importer
from career_agent.backup import create_backup, restore_backup
from career_agent.core import Availability, CandidateProfile, JobListing
from career_agent.event_log import EVENTS, log_path
from career_agent.store import CareerStore, StoredRecordError, unreadable_stored_records
from career_agent.strategies import (
    CONTENT_FIELDS, MAX_ITEM_CHARS, MAX_NAME_CHARS, MAX_SET_ITEMS, RoleStrategy, StrategyError,
    new_strategy_id, strategy_from_payload, strategy_payload,
)

FULL_CONTENT = {
    "name": "Applied AI roles, Delhi NCR",
    "role_family": "Applied AI engineering",
    "title_synonyms": frozenset({"Applied AI Engineer", "GenAI Engineer", "LLM Engineer"}),
    "seniority": "mid",
    "locations": frozenset({"Delhi", "Bengaluru"}),
    "work_modes": frozenset({"hybrid", "remote"}),
    "employment_types": frozenset({"full-time"}),
    "compensation_min": 2_000_000.0,
    "compensation_max": 4_000_000.0,
    "compensation_currency": "INR",
    "required_skills": frozenset({"Python", "SQL"}),
    "excluded_role_titles": frozenset({"Sales Engineer"}),
    "excluded_employers": frozenset({"Example Employer"}),
    "preferred_skills": frozenset({"PyTorch"}),
}


def strategy(**overrides: object) -> RoleStrategy:
    """One invented strategy, valid by default, with any field replaced for a test."""
    content = {name: value for name, value in FULL_CONTENT.items()}
    content.update(overrides)
    return RoleStrategy(strategy_id=content.pop("strategy_id", new_strategy_id()),  # type: ignore[arg-type]
                        version=content.pop("version", 1), **content)  # type: ignore[arg-type]


class RoleStrategyModelTests(unittest.TestCase):
    """What one strategy is allowed to say, and what the constructor refuses."""

    def test_a_minimal_strategy_states_only_its_name_and_family(self):
        minimal = RoleStrategy(strategy_id=new_strategy_id(), version=1,
                               name="Backend roles", role_family="Backend engineering")
        self.assertEqual(minimal.title_synonyms, frozenset())
        self.assertIsNone(minimal.seniority)
        self.assertIsNone(minimal.compensation_min)
        self.assertEqual(minimal.locations, frozenset(), "an absent list is 'nothing stated'")

    def test_a_strategy_needs_a_name_and_a_role_family(self):
        for field_name, blank in (("name", ""), ("role_family", "   ")):
            with self.subTest(field=field_name):
                with self.assertRaises(StrategyError) as caught:
                    strategy(**{field_name: blank})
                self.assertIn("cannot be empty", str(caught.exception))

    def test_values_are_trimmed_and_bounded(self):
        trimmed = strategy(name="  Data roles  ", locations=frozenset({"  Pune  "}))
        self.assertEqual(trimmed.name, "Data roles")
        self.assertEqual(trimmed.locations, frozenset({"Pune"}))
        with self.assertRaises(StrategyError):
            strategy(name="n" * (MAX_NAME_CHARS + 1))
        with self.assertRaises(StrategyError):
            strategy(role_family="f" * (MAX_ITEM_CHARS + 1))
        with self.assertRaises(StrategyError):
            strategy(locations=frozenset({"x" * (MAX_ITEM_CHARS + 1)}))
        with self.assertRaises(StrategyError):
            strategy(locations=frozenset(str(index) for index in range(MAX_SET_ITEMS + 1)))

    def test_a_set_field_refuses_a_blob_an_empty_value_and_a_non_text_value(self):
        with self.assertRaises(StrategyError) as caught:
            strategy(title_synonyms="one, two, three")
        self.assertIn("separate values", str(caught.exception))
        with self.assertRaises(StrategyError):
            strategy(title_synonyms=frozenset({"  "}))
        with self.assertRaises(StrategyError):
            strategy(title_synonyms=frozenset({7}))

    def test_the_version_is_a_whole_number_starting_at_one(self):
        for bad in (0, -1, 2.5, True, "1"):
            with self.subTest(version=bad):
                with self.assertRaises(StrategyError):
                    strategy(version=bad)

    def test_a_strategy_identifier_cannot_be_blank_or_oversized(self):
        with self.assertRaises(StrategyError):
            strategy(strategy_id="   ")
        with self.assertRaises(StrategyError):
            strategy(strategy_id="s" * 65)

    def test_compensation_refuses_the_numbers_no_check_can_use(self):
        for bad in (float("nan"), float("inf"), float("-inf"), -1.0, True):
            with self.subTest(amount=bad):
                with self.assertRaises(StrategyError):
                    strategy(compensation_min=bad, compensation_currency="INR")
        with self.assertRaises(StrategyError) as caught:
            strategy(compensation_min="not a number", compensation_currency="INR")
        self.assertIn("not one", str(caught.exception))

    def test_a_compensation_bound_needs_its_currency_and_an_ordered_range(self):
        with self.assertRaises(StrategyError) as caught:
            strategy(compensation_min=1000.0, compensation_currency=None)
        self.assertIn("currency", str(caught.exception))
        with self.assertRaises(StrategyError):
            strategy(compensation_min=5000.0, compensation_max=1000.0, compensation_currency="INR")
        valid = strategy(compensation_min=1000.0, compensation_max=1000.0, compensation_currency="INR")
        self.assertEqual(valid.compensation_min, valid.compensation_max)

    def test_the_content_key_ignores_identity_and_set_order(self):
        first = strategy()
        same = RoleStrategy(strategy_id=new_strategy_id(), version=7,
                            **{name: getattr(first, name) for name in CONTENT_FIELDS})
        reordered = strategy(title_synonyms=frozenset(reversed(sorted(first.title_synonyms))))
        self.assertEqual(first.content_key(), same.content_key(),
                         "identity is not content: two versions of one statement match")
        self.assertEqual(first.content_key(), reordered.content_key())
        self.assertNotEqual(first.content_key(), strategy(name="A different search").content_key())


class StrategyPayloadTests(unittest.TestCase):
    """The stored form: content without identity, and a reader that refuses what it cannot use."""

    def test_a_payload_round_trips_every_field(self):
        original = strategy()
        payload = strategy_payload(original)
        restored = strategy_from_payload(original.strategy_id, original.version, payload)
        self.assertEqual(restored, original)
        self.assertNotIn(original.strategy_id, payload, "identity lives in the columns, not the payload")

    def test_the_payload_is_stable_json(self):
        self.assertEqual(strategy_payload(strategy(title_synonyms=frozenset({"a", "b"}))),
                         strategy_payload(strategy(title_synonyms=frozenset({"b", "a"}))))

    def test_a_damaged_payload_is_refused_as_itself(self):
        identifier = new_strategy_id()
        cases = {
            "not JSON at all": "readable JSON",
            json.dumps([]): "JSON object",
            json.dumps({"name": "x"}): "missing field(s)",
            json.dumps({**{name: getattr(strategy(), name) for name in CONTENT_FIELDS},
                        "extra": 1}, default=list, sort_keys=True): "does not know",
        }
        for payload, fragment in cases.items():
            with self.subTest(payload=payload[:40]):
                with self.assertRaises(StrategyError) as caught:
                    strategy_from_payload(identifier, 1, payload)
                self.assertIn(fragment, str(caught.exception))

    def test_a_payload_whose_set_field_is_not_a_list_is_refused(self):
        content = {name: getattr(strategy(), name) for name in CONTENT_FIELDS}
        payload = json.dumps({**content, "locations": "Delhi"}, default=list, sort_keys=True)
        with self.assertRaises(StrategyError) as caught:
            strategy_from_payload(new_strategy_id(), 1, payload)
        self.assertIn("list", str(caught.exception))


class RoleStrategyStoreTestCase(unittest.TestCase):
    """A disposable folder and a database in it, the way the contacts store tests hold one."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)

    def reopen(self) -> CareerStore:
        self.store.close()
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)
        return self.store

    def rows(self) -> int:
        return self.store._connection.execute(
            "SELECT COUNT(*) FROM role_strategy_version").fetchone()[0]

    def logged(self) -> str:
        return log_path(self.database).read_text(encoding="utf-8")


class RoleStrategyStoreTests(RoleStrategyStoreTestCase):
    """The append-only promise: what a write does, what a revision does, and what neither invents."""

    def test_a_new_strategy_is_stored_as_version_one(self):
        created = self.store.create_role_strategy(**FULL_CONTENT)
        self.assertEqual(created.version, 1)
        self.assertEqual(self.store.get_role_strategy(created.strategy_id), created)
        self.assertEqual(self.rows(), 1)

    def test_an_invalid_strategy_is_refused_before_anything_is_written(self):
        before = self.store._connection.total_changes
        with self.assertRaises(StrategyError):
            self.store.create_role_strategy(**{**FULL_CONTENT, "name": ""})
        self.assertEqual(self.rows(), 0)
        self.assertEqual(self.store._connection.total_changes, before, "a refusal writes nothing")

    def test_a_revision_appends_a_version_and_never_rewrites_the_old_one(self):
        first = self.store.create_role_strategy(**FULL_CONTENT)
        second = self.store.revise_role_strategy(
            first.strategy_id, **{**FULL_CONTENT, "locations": frozenset({"Mumbai"})})

        self.assertEqual(second.version, 2)
        self.assertEqual(second.strategy_id, first.strategy_id)
        self.assertEqual(self.store.get_role_strategy(first.strategy_id), second,
                         "the newest version is the one a reader gets by default")
        self.assertEqual(self.store.get_role_strategy(first.strategy_id, version=1), first,
                         "version 1 still says exactly what it said")
        self.assertEqual(self.store.role_strategy_versions(first.strategy_id), (first, second))

    def test_a_revision_that_changes_nothing_writes_no_version(self):
        first = self.store.create_role_strategy(**FULL_CONTENT)
        before = self.store._connection.total_changes
        # The same content in a different set order is the same statement.
        again = self.store.revise_role_strategy(
            first.strategy_id,
            **{**FULL_CONTENT, "title_synonyms": frozenset(reversed(sorted(FULL_CONTENT["title_synonyms"])))})
        self.assertEqual(again, first)
        self.assertEqual(again.version, 1)
        self.assertEqual(self.rows(), 1, "a version that changed nothing is a claim that something did")
        self.assertEqual(self.store._connection.total_changes, before)

    def test_revising_a_strategy_that_is_not_stored_is_refused(self):
        with self.assertRaises(StrategyError) as caught:
            self.store.revise_role_strategy(new_strategy_id(), **FULL_CONTENT)
        self.assertIn("nothing to revise", str(caught.exception))
        self.assertEqual(self.rows(), 0)

    def test_the_list_holds_the_newest_version_of_every_strategy_in_name_order(self):
        first = self.store.create_role_strategy(**FULL_CONTENT)
        self.store.revise_role_strategy(first.strategy_id, **{**FULL_CONTENT, "seniority": "senior"})
        second = self.store.create_role_strategy(name="Backend roles", role_family="Backend engineering")
        listed = self.store.list_role_strategies()
        self.assertEqual([item.name for item in listed], [FULL_CONTENT["name"], "Backend roles"],
                         "by name: 'Applied…' sorts before 'Backend…'")
        self.assertEqual(listed[0].version, 2, "the revised strategy lists at its newest version")
        self.assertEqual(listed[1].version, 1)
        self.assertEqual(self.rows(), 3)

    def test_getting_a_strategy_that_is_not_stored_reads_as_absent(self):
        self.assertIsNone(self.store.get_role_strategy(new_strategy_id()))
        self.assertEqual(self.store.list_role_strategies(), ())
        self.assertEqual(self.store.role_strategy_versions(new_strategy_id()), ())

    def test_deleting_a_strategy_removes_every_version_of_it_and_nothing_else(self):
        doomed = self.store.create_role_strategy(**FULL_CONTENT)
        self.store.revise_role_strategy(doomed.strategy_id, **{**FULL_CONTENT, "seniority": "senior"})
        kept = self.store.create_role_strategy(name="Backend roles", role_family="Backend engineering")

        self.assertEqual(self.store.delete_role_strategy(doomed.strategy_id), 2)
        self.assertIsNone(self.store.get_role_strategy(doomed.strategy_id))
        self.assertEqual(self.store.list_role_strategies(), (kept,))

    def test_deleting_a_strategy_that_is_not_stored_changes_nothing_and_says_so(self):
        before = self.store._connection.total_changes
        self.assertEqual(self.store.delete_role_strategy(new_strategy_id()), 0)
        self.assertEqual(self.store._connection.total_changes, before)
        self.assertNotIn("strategy.deleted", self.logged())

    def test_versions_survive_a_restart(self):
        first = self.store.create_role_strategy(**FULL_CONTENT)
        second = self.store.revise_role_strategy(first.strategy_id, **{**FULL_CONTENT,
                                                                       "seniority": "senior"})
        reopened = self.reopen()
        self.assertEqual(reopened.role_strategy_versions(first.strategy_id), (first, second))
        self.assertEqual(reopened.get_role_strategy(first.strategy_id), second)

    def test_strategies_survive_a_backup_and_a_restore(self):
        created = self.store.create_role_strategy(**FULL_CONTENT)
        self.store.revise_role_strategy(created.strategy_id, **{**FULL_CONTENT, "seniority": "senior"})
        backup = self.folder / "backup.sqlite3"
        create_backup(self.database, backup)

        # A restore over a database whose strategies were deleted must bring every version back.
        self.store.delete_role_strategy(created.strategy_id)
        self.assertEqual(self.store.list_role_strategies(), ())
        restore_backup(backup, self.database)
        reopened = self.reopen()
        restored = reopened.get_role_strategy(created.strategy_id)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.version, 2)
        self.assertEqual(len(reopened.role_strategy_versions(created.strategy_id)), 2)

    def test_a_damaged_row_is_reported_as_itself_not_read_as_absent(self):
        created = self.store.create_role_strategy(**FULL_CONTENT)
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE role_strategy_version SET payload='not json' WHERE strategy_id=?",
                (created.strategy_id,))
        with self.assertRaises(StoredRecordError):
            self.store.get_role_strategy(created.strategy_id)
        problems = unreadable_stored_records(self.database)
        self.assertTrue(any("role_strategy_version" in line for line in problems),
                        "the doctor reads the strategy rows through the same decoder")

    def test_the_log_carries_the_identifier_and_the_version_and_never_the_content(self):
        created = self.store.create_role_strategy(**FULL_CONTENT)
        self.store.revise_role_strategy(created.strategy_id, **{**FULL_CONTENT, "seniority": "senior"})
        self.store.delete_role_strategy(created.strategy_id)
        written = self.logged()
        for name in ("strategy.created", "strategy.revised", "strategy.deleted"):
            self.assertIn(name, EVENTS)
            self.assertIn(name, written)
        self.assertIn(f"id={created.strategy_id} version=2", written)
        for value in (FULL_CONTENT["name"], FULL_CONTENT["role_family"], "Example Employer",
                      "Sales Engineer", "senior", "Delhi", "INR"):
            self.assertNotIn(str(value), written,
                             "a strategy's content is the person's data and stays out of the log")

    def test_the_json_export_does_not_carry_strategies_and_stays_version_two(self):
        """The version-2 contract is the profile, the listings and the person's own history.

        A strategy is configuration, not a candidate fact: the whole-database backup is what carries
        it, exactly as it carries the imported contact list. If a future format adds strategies, that
        is a deliberate version bump - this test is where that decision has to be made out loud.
        """
        created = self.store.create_role_strategy(**FULL_CONTENT)
        self.store.save_profile(CandidateProfile(candidate_country="India"))
        from career_agent.artifacts import ArtifactBasis, ArtifactKind
        self.store.save_job(JobListing(
            "j1", "manual", "Manual entry", "https://jobs.example.invalid/role/1",
            "Example Employer", "Role", availability_status=Availability.OPEN))
        self.store.new_tailored_artifact(
            listing_id="j1", strategy=created, kind=ArtifactKind.COVER_LETTER,
            content="A letter that must not travel in the JSON export.\n",
            basis=ArtifactBasis(facts={"skills": "Python"}))
        document = importer.export_document(self.store)
        self.assertEqual(document["format_version"], 2)
        rendered = json.dumps(document)
        self.assertNotIn("role_strateg", rendered)
        self.assertNotIn(created.strategy_id, rendered)
        self.assertNotIn("tailored_artifact", rendered)
        self.assertNotIn("fact_basis", rendered)
        self.assertNotIn("must not travel", rendered,
                         "an artifact's content is the person's writing and stays in the backup")


if __name__ == "__main__":
    unittest.main()
