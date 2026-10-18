"""The claims this project refuses to make, checked rather than trusted.

Documentation drifts. These tests pin the three statements that would be most damaging to get wrong:
that laptop-off operation is not claimed, that the sync boundary is described as the hazard it is,
and that no credential is stored anywhere - the last one checked against the schema and the package,
not against a sentence.
"""
from __future__ import annotations

import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from career_agent.store import CareerStore

ROOT = Path(__file__).resolve().parents[1]
_RAW_README = (ROOT / "README.md").read_text(encoding="utf-8")
#: Line breaks are formatting, not meaning: a phrase re-wrapped across two lines is the same
#: claim, and a test that fails on re-wrapping teaches people to stop editing the README.
README = " ".join(_RAW_README.split())

#: Words that would mean a credential is being kept. ``token`` covers API and mailbox tokens alike.
CREDENTIAL_WORDS = ("password", "passwd", "secret", "api_key", "apikey", "access_token",
                    "refresh_token", "credential")


class ClaimTests(unittest.TestCase):
    def test_always_on_operation_is_refused_in_writing(self):
        self.assertIn("Laptop-off operation is not available", README)
        self.assertIn("there is no service unit", README)

    def test_the_evidence_an_always_on_claim_would_need_is_written_down(self):
        section = README[README.index("## Syncing, credentials"):README.index("## Audit research data")]
        for required in ("deployed worker", "tested storage boundary", "recorded run",
                         "recovery behaviour"):
            with self.subTest(required=required):
                self.assertIn(required, section)

    def test_the_sync_hazard_is_described_rather_than_hinted(self):
        section = README[README.index("## Syncing, credentials"):README.index("## Audit research data")]
        self.assertIn("can be corrupted by the sync service", section)
        self.assertIn("not a distributed lock", section)
        self.assertIn("refused by design", section)

    def test_the_supported_ways_to_move_data_are_named(self):
        section = README[README.index("## Syncing, credentials"):README.index("## Audit research data")]
        for flag in ("--backup", "--restore", "--export-json", "--import-json"):
            with self.subTest(flag=flag):
                self.assertIn(flag, section)


class NoCredentialTests(unittest.TestCase):
    def test_no_column_in_the_schema_is_credential_shaped(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CareerStore(str(Path(directory) / "schema.sqlite3"))
            self.addCleanup(store.close)
            tables = [row["name"] for row in store._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                for column in store._connection.execute(f"PRAGMA table_info({table})"):
                    name = str(column["name"]).casefold()
                    for word in CREDENTIAL_WORDS:
                        with self.subTest(table=table, column=name, word=word):
                            self.assertNotIn(word, name)

    def test_no_module_in_the_package_reads_or_writes_a_credential_store(self):
        for module in sorted((ROOT / "career_agent").glob("*.py")):
            text = module.read_text(encoding="utf-8")
            for forbidden in ("import keyring", "getpass.getpass", "os.environ['PASSWORD']"):
                with self.subTest(module=module.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, text)

    def test_a_credential_shaped_assignment_does_not_appear_in_the_package(self):
        pattern = re.compile(r"^\s*(password|api_key|access_token|secret)\s*=\s*['\"]",
                             re.IGNORECASE | re.MULTILINE)
        for module in sorted((ROOT / "career_agent").glob("*.py")):
            with self.subTest(module=module.name):
                self.assertIsNone(pattern.search(module.read_text(encoding="utf-8")))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
