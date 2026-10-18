"""Tests for the stored standing authorisation: append-only versions, revocation and what survives.

Nothing here enables a source, opens a gate or performs an external action. Every policy is invented
and every database is a disposable file in a temporary folder.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from career_agent.backup import create_backup, restore_backup
from career_agent.event_log import log_path
from career_agent.policy import (
    ActionKind, GlobalPolicy, PolicyError, evaluate_policy, no_authorisation,
)
from career_agent.store import SCHEMA_VERSION, CareerStore, StoredRecordError

NOON = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def a_policy(**overrides) -> GlobalPolicy:
    content = {
        "allowed": frozenset({("jobicy", ActionKind.DISCOVERY)}),
        "daily_limits": {ActionKind.DISCOVERY: 4},
        "quiet_hours": (22, 7),
    }
    content.update(overrides)
    return GlobalPolicy(**content)


class PolicyStoreTests(unittest.TestCase):
    """One authorisation, versioned append-only, readable afterwards."""

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
        return int(self.store._connection.execute(
            "SELECT COUNT(*) FROM policy_version").fetchone()[0])

    def logged(self) -> str:
        return log_path(self.database).read_text(encoding="utf-8")

    def test_the_schema_holds_the_authorisation_at_version_11(self):
        self.assertEqual(SCHEMA_VERSION, 11)
        self.assertEqual(
            self.store._connection.execute("PRAGMA user_version").fetchone()[0], 11)

    def test_a_file_with_no_policy_authorises_nothing(self):
        self.assertEqual(self.store.get_global_policy(), no_authorisation())
        self.assertEqual(self.store.policy_version_number(), 0)
        self.assertEqual(self.store.policy_versions(), ())
        self.assertEqual(self.rows(), 0, "reading an authorisation writes nothing")

    def test_an_authorisation_is_stored_as_version_one_and_read_back_whole(self):
        version = self.store.save_global_policy(a_policy())
        self.assertEqual(version, 1)
        self.assertEqual(self.store.get_global_policy(), a_policy())
        self.assertEqual(self.store.policy_version_number(), 1)

    def test_changing_the_authorisation_appends_a_version_and_keeps_the_old_one(self):
        self.store.save_global_policy(a_policy())
        second = self.store.save_global_policy(a_policy(daily_limits={ActionKind.DISCOVERY: 1}))
        self.assertEqual(second, 2)
        history = self.store.policy_versions()
        self.assertEqual([version for version, _policy in history], [1, 2])
        self.assertEqual(history[0][1].daily_limits[ActionKind.DISCOVERY], 4,
                         "the authorisation an action ran under must stay readable")
        self.assertEqual(self.store.get_global_policy().daily_limits[ActionKind.DISCOVERY], 1)

    def test_saving_the_same_authorisation_again_writes_no_version(self):
        self.store.save_global_policy(a_policy())
        before = self.store._connection.total_changes
        again = self.store.save_global_policy(a_policy())
        self.assertEqual(again, 1)
        self.assertEqual(self.rows(), 1, "a version that changed nothing claims a decision nobody made")
        self.assertEqual(self.store._connection.total_changes, before)

    def test_revoking_appends_a_version_that_authorises_nothing_and_keeps_the_history(self):
        self.store.save_global_policy(a_policy())
        version = self.store.revoke_global_policy(revoked_at="2026-10-20T12:00:00+00:00")
        self.assertEqual(version, 2)
        current = self.store.get_global_policy()
        self.assertEqual(current.revoked_at, "2026-10-20T12:00:00+00:00")
        self.assertEqual(current.allowed, a_policy().allowed,
                         "a revocation says what was withdrawn, it does not erase it")
        decision = evaluate_policy(current, source_id="jobicy", action=ActionKind.DISCOVERY,
                                   now=NOON, done_today=0, source_gate_allows=True)
        self.assertFalse(decision.allowed)
        self.assertIn("revoked", decision.describe())
        self.assertEqual(self.store.policy_versions()[0][1].revoked_at, None)

    def test_revoking_twice_writes_nothing_the_second_time(self):
        self.store.save_global_policy(a_policy())
        self.store.revoke_global_policy()
        before = self.store._connection.total_changes
        self.store.revoke_global_policy()
        self.assertEqual(self.rows(), 2)
        self.assertEqual(self.store._connection.total_changes, before)

    def test_granting_again_after_a_revocation_is_a_new_version(self):
        self.store.save_global_policy(a_policy())
        self.store.revoke_global_policy()
        version = self.store.save_global_policy(a_policy())
        self.assertEqual(version, 3)
        self.assertIsNone(self.store.get_global_policy().revoked_at)

    def test_an_authorisation_survives_a_restart(self):
        self.store.save_global_policy(a_policy())
        reopened = self.reopen()
        self.assertEqual(reopened.get_global_policy(), a_policy())
        self.assertEqual(reopened.policy_version_number(), 1)

    def test_an_authorisation_survives_a_backup_and_a_restore(self):
        self.store.save_global_policy(a_policy())
        backup = self.folder / "backup.sqlite3"
        create_backup(self.database, backup)
        self.store.revoke_global_policy()
        self.assertIsNotNone(self.store.get_global_policy().revoked_at)
        restore_backup(backup, self.database)
        reopened = self.reopen()
        self.assertIsNone(reopened.get_global_policy().revoked_at,
                          "the restored file holds the authorisation the backup held")
        self.assertEqual(reopened.policy_version_number(), 1)

    def test_a_damaged_row_is_reported_and_never_read_as_no_restrictions(self):
        self.store.save_global_policy(a_policy())
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE policy_version SET payload=? WHERE version=1",
                (json.dumps({"allowed": [["jobicy", "rule the world"]]}),))
        with self.assertRaises(StoredRecordError):
            self.store.get_global_policy()
        from career_agent.store import unreadable_stored_records
        self.assertTrue(any("policy_version" in line
                            for line in unreadable_stored_records(self.database)))

    def test_the_log_records_the_decision_without_describing_it(self):
        self.store.save_global_policy(a_policy())
        self.store.revoke_global_policy()
        written = self.logged()
        self.assertIn("policy.saved", written)
        self.assertIn("policy.revoked", written)
        self.assertIn("pairs=1", written)
        self.assertNotIn("jobicy", written,
                         "which sources somebody authorised is their decision, not an event detail")

    def test_the_json_export_does_not_carry_the_authorisation(self):
        from career_agent.importer import export_document

        self.store.save_global_policy(a_policy())
        document = export_document(self.store)
        self.assertEqual(document["format_version"], 2,
                         "the export format is unchanged by this table")
        self.assertNotIn("policy", json.dumps(document).lower(),
                         "the authorisation travels in a whole-database backup, not in an export "
                         "file somebody may share")

    def test_an_authorisation_is_refused_rather_than_coerced(self):
        for value in (None, "everything", {"allowed": []}):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                self.store.save_global_policy(value)  # type: ignore[arg-type]
        self.assertEqual(self.rows(), 0)


class PolicyMigrationTests(unittest.TestCase):
    """A database written before the authorisation existed stays readable, and gains it safely."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "legacy.sqlite3"

    def test_a_version_10_database_upgrades_and_authorises_nothing_until_asked(self):
        store = CareerStore(str(self.database))
        store.close()
        # Put the file back to schema 10 with the new table removed, the way a file written by the
        # previous build looks on disk.
        connection = sqlite3.connect(self.database)
        with connection:
            connection.execute("DROP TABLE policy_version")
            connection.execute("PRAGMA user_version = 10")
        connection.close()

        reopened = CareerStore(str(self.database))
        self.addCleanup(reopened.close)
        self.assertEqual(
            reopened._connection.execute("PRAGMA user_version").fetchone()[0], 11)
        self.assertEqual(reopened.get_global_policy(), no_authorisation(),
                         "an upgraded file authorises nothing until a person says otherwise")
        self.assertEqual(reopened.save_global_policy(a_policy()), 1)

    def test_the_step_is_re_runnable_and_keeps_what_is_there(self):
        store = CareerStore(str(self.database))
        store.save_global_policy(a_policy())
        from career_agent.store import _migration_to_v11

        _migration_to_v11(store._connection)  # the same step again, as a rerun would
        self.assertEqual(store.get_global_policy(), a_policy())
        self.assertEqual(store.policy_version_number(), 1)
        store.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
