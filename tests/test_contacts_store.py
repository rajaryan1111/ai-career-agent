"""Tests for storing an imported HR contact list: what is written, what deliberately is not, and why.

The parser in ``career_agent/contacts.py`` was shipped first and has its own tests; this file is about
what happens *after* a person decides to keep what they parsed. Four properties matter more than the rest,
and they are the ones the increment was scoped around:

* **Nothing is written until a person confirms it.** A plan is computed by reading the database and writes
  nothing - proved here with the connection's own change counter and the file's bytes, not with a message.
  A refused file, a cancelled preview and a declined confirmation all leave the counter where it was.
* **An import cannot overwrite what the stored record already says.** The address text, the name and the
  company a record holds are the first ones recorded; a later file that disagrees is kept beside the record
  as evidence, never merged into it.
* **A do-not-contact mark belongs to the person alone.** No import statement mentions the column, so it
  survives re-imports, contradicting files, a backup, a restore and a restart.
* **No contact value reaches a log or a printed summary.** The event carries counts; a summary carries
  counts, field names and reasons. Both are asserted against the fixture's own values rather than against
  any wording.

Every fixture is synthetic and every address is on a reserved ``.invalid`` domain: no real contact list,
and no row of one, is used by this file - and the private exports this was built for are deliberately not
in this repository.
"""
from __future__ import annotations

import logging
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_agent import contact_export, contacts as contacts_module
from career_agent.backup import create_backup, restore_backup, validate_app_database
from career_agent.contacts import ContactCsvMalformed, ContactSchemaError
from career_agent.event_log import EVENTS, log_path
from career_agent.store import (
    SCHEMA_TABLES_BY_VERSION, SCHEMA_VERSION, CareerStore, ContactConflictOrigin,
    ContactImportAction, StoredRecordError,
)

#: The fixture's values, kept in one place so the privacy tests can assert every one of them is absent from
#: a log, a summary and an event. Synthetic on purpose: invented people on a reserved domain.
SAMPLE_EMAILS = ("first.contact@example.invalid", "SECOND.Contact@Example.Invalid",
                 "third.contact@example.invalid", "fourth.contact@example.invalid")
SAMPLE_NAMES = ("Sample Person One", "Sample Person Two", "Sample Person Three")
SAMPLE_COMPANIES = ("Sample Employer One", "Sample Employer Two")
ALL_SAMPLE_VALUES = SAMPLE_EMAILS + SAMPLE_NAMES + SAMPLE_COMPANIES

HEADER = "Email,Name,Company Label,Source Rows,Review Reason\r\n"


class ContactStoreTestCase(unittest.TestCase):
    """A disposable folder, a database in it, and a way to write synthetic fixture files beside it."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)

    def write(self, rows: str, name: str = "contacts.csv", *, header: str = HEADER) -> Path:
        """Write a fixture file, so a test can point the real parser at it."""
        path = self.folder / name
        path.write_bytes((header + rows).encode("utf-8"))
        return path

    def parsed(self, rows: str, name: str = "contacts.csv", *, header: str = HEADER):
        """A real parse of a synthetic file: the object the window hands to the store."""
        return contacts_module.read_contact_csv(self.write(rows, name=name, header=header))

    def changes(self) -> int:
        """How many rows this connection has changed since it was opened: the store's change counter."""
        return self.store._connection.total_changes

    def reopen(self) -> CareerStore:
        """Close and reopen the store, the way a restart does."""
        self.store.close()
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)
        return self.store

    def keys(self) -> list:
        return [record.email_key for record in self.store.list_contacts()]


class StoredContactTests(ContactStoreTestCase):
    """What one committed import leaves behind, read back through the store's own read path."""

    def test_a_new_file_is_stored_with_its_own_text_and_its_provenance(self):
        parsed = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},7,\r\n"
            f"{SAMPLE_EMAILS[2]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},9,\r\n"
        )

        outcome = self.store.import_contacts(parsed, observed_at="2026-10-16T09:00:00+00:00")

        self.assertEqual((outcome.added, outcome.updated, outcome.conflicts), (2, 0, 0))
        self.assertEqual(outcome.skipped_without_key, 0)
        stored = {record.email_key: record for record in self.store.list_contacts()}
        self.assertEqual(sorted(stored), ["first.contact@example.invalid", "third.contact@example.invalid"])
        first = stored["first.contact@example.invalid"]
        self.assertEqual(first.email, SAMPLE_EMAILS[0], "the file's own text is stored, not a rewrite of it")
        self.assertEqual(first.name, SAMPLE_NAMES[0])
        self.assertEqual(first.company, SAMPLE_COMPANIES[0])
        self.assertEqual(first.source_row, "7", "the file's own row value is kept for review")
        self.assertEqual(first.source_file, "contacts.csv", "provenance is the file's name")
        self.assertEqual(first.first_seen_at, "2026-10-16T09:00:00+00:00")
        self.assertEqual(first.last_seen_at, first.first_seen_at)
        self.assertEqual(first.seen_count, 1)
        self.assertFalse(first.suppressed)
        self.assertIsNone(first.suppressed_at)
        self.assertEqual(self.store.contact_record_counts(),
                         {"contacts": 2, "do_not_contact": 0, "with_review_flags": 0, "conflicts": 0})

    def test_the_key_is_trimmed_and_case_folded_and_case_is_not_a_second_contact(self):
        # The parser flags a second spelling of one address; the store must still hold one record, and the
        # text it keeps is the spelling the first file used.
        first = self.parsed(f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n")
        self.store.import_contacts(first)
        second = self.parsed(f"{SAMPLE_EMAILS[1].casefold()},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},2,\r\n")

        outcome = self.store.import_contacts(second)

        self.assertEqual((outcome.added, outcome.updated), (0, 1))
        self.assertEqual(self.keys(), [SAMPLE_EMAILS[1].casefold()])
        (record,) = self.store.list_contacts()
        self.assertEqual(record.email, SAMPLE_EMAILS[1], "the first spelling is what a person sees")
        self.assertEqual(record.seen_count, 2)

    def test_the_same_file_imported_twice_updates_one_record_and_adds_none(self):
        parsed = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[2]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n"
        )
        self.store.import_contacts(parsed, observed_at="2026-10-16T09:00:00+00:00")
        before = self.changes()

        outcome = self.store.import_contacts(parsed, observed_at="2026-10-16T10:00:00+00:00")

        self.assertEqual((outcome.added, outcome.updated, outcome.conflicts), (0, 2, 0))
        self.assertEqual(len(self.store.list_contacts()), 2, "a repeat must not duplicate a record")
        self.assertEqual(self.changes() - before, 2, "one update per key, and nothing else")
        for record in self.store.list_contacts():
            self.assertEqual(record.seen_count, 2)
            self.assertEqual(record.last_seen_at, "2026-10-16T10:00:00+00:00")

    def test_duplicate_rows_in_one_file_become_one_record_with_the_disagreement_kept(self):
        parsed = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[0].upper()},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[1]},2,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},3,\r\n"
        )

        outcome = self.store.import_contacts(parsed)

        self.assertEqual((outcome.added, outcome.conflicts), (1, 1), "one key, one new disagreement")
        (record,) = self.store.list_contacts()
        self.assertEqual(record.seen_count, 1)
        self.assertEqual(record.company, SAMPLE_COMPANIES[0], "the file's first answer is the one kept")
        self.assertEqual(set(record.review_flags), {"duplicate-key", "company-conflict"},
                         "the parser's own findings for this key are what the store keeps")
        (conflict,) = self.store.list_contact_conflicts()
        self.assertEqual(conflict.field, "company")
        self.assertEqual(conflict.kept_value, SAMPLE_COMPANIES[0])
        self.assertEqual(conflict.other_value, SAMPLE_COMPANIES[1])
        self.assertEqual(conflict.origin, ContactConflictOrigin.FILE)
        self.assertEqual(conflict.email_key, SAMPLE_EMAILS[0].casefold())

    def test_a_re_import_that_contradicts_a_name_keeps_the_stored_one_and_records_it(self):
        self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"))
        changed = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},4,\r\n")

        outcome = self.store.import_contacts(changed)

        self.assertEqual((outcome.added, outcome.updated, outcome.conflicts), (0, 1, 2))
        (record,) = self.store.list_contacts()
        self.assertEqual(record.name, SAMPLE_NAMES[0], "a file never rewrites a stored name")
        self.assertEqual(record.company, SAMPLE_COMPANIES[0], "nor a stored company label")
        self.assertEqual(record.source_row, "4", "provenance describes the import that last saw the key")
        conflicts = {(row.field, row.origin): (row.kept_value, row.other_value)
                     for row in self.store.list_contact_conflicts()}
        self.assertEqual(conflicts[("name", ContactConflictOrigin.STORED)], (SAMPLE_NAMES[0], SAMPLE_NAMES[1]))
        self.assertEqual(conflicts[("company", ContactConflictOrigin.STORED)],
                         (SAMPLE_COMPANIES[0], SAMPLE_COMPANIES[1]))

    def test_a_field_the_record_does_not_have_is_filled_in_without_becoming_a_disagreement(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},,,1,\r\n"))

        outcome = self.store.import_contacts(
            self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},2,\r\n"))

        self.assertEqual(outcome.conflicts, 0, "an empty column is an unknown, not a contradiction")
        (record,) = self.store.list_contacts()
        self.assertEqual(record.name, SAMPLE_NAMES[0])
        self.assertEqual(record.company, SAMPLE_COMPANIES[0])
        self.assertEqual(record.review_flags, (),
                         "the flags describe the most recent import, which filled the name in")
        self.assertEqual(self.store.list_contacts()[0].name, SAMPLE_NAMES[0])

    def test_the_same_disagreement_is_recorded_once_however_often_the_file_comes_back(self):
        contradictory = (
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},2,\r\n"
        )
        self.store.import_contacts(self.parsed(contradictory))
        self.assertEqual(len(self.store.list_contact_conflicts()), 1)

        outcome = self.store.import_contacts(self.parsed(contradictory))

        self.assertEqual(outcome.conflicts, 0, "the same question is not asked twice")
        self.assertEqual(len(self.store.list_contact_conflicts()), 1)
        self.assertEqual(len(self.store.list_contacts()), 1)

    def test_rows_without_an_email_key_are_counted_and_never_stored(self):
        parsed = self.parsed(
            f",{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"   ,{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},3,\r\n"
        )

        outcome = self.store.import_contacts(parsed)

        self.assertEqual((outcome.added, outcome.skipped_without_key), (1, 2))
        self.assertEqual(self.keys(), ["first.contact@example.invalid"],
                         "a row this application cannot identify must not be stored")

    def test_provenance_is_a_file_name_and_the_folder_is_never_stored(self):
        inside = self.folder / "export-folder"
        inside.mkdir()
        path = inside / "contacts.csv"
        path.write_bytes((HEADER + f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n").encode("utf-8"))

        self.store.import_contacts(contacts_module.read_contact_csv(path))

        (record,) = self.store.list_contacts()
        self.assertEqual(record.source_file, "contacts.csv")
        self.assertNotIn(os_separator(), record.source_file)
        self.assertNotIn(inside.name.encode("utf-8"), self.database.read_bytes(),
                         "a folder a person chose must not be written into the database")


def os_separator() -> str:
    """The one thing this module needs from ``os``, named so the privacy assertion reads plainly."""
    import os  # noqa: PLC0415 - one standard-library name, imported where it is used

    return os.sep


class NothingIsWrittenBeforeAConfirmationTests(ContactStoreTestCase):
    """Zero writes, proved with the connection's change counter rather than with a message."""

    def test_a_plan_reads_the_database_and_changes_nothing(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,1,\r\n"))
        before_bytes = self.database.read_bytes()
        before_changes = self.changes()

        plan = self.store.plan_contact_import(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,2,\r\n{SAMPLE_EMAILS[2]},{SAMPLE_NAMES[1]},,3,\r\n"))

        self.assertEqual((plan.added, plan.updated), (1, 1))
        self.assertEqual(self.changes(), before_changes, "planning must not write a row")
        self.assertEqual(self.database.read_bytes(), before_bytes, "planning must not touch the file")
        self.assertEqual(len(self.store.list_contacts()), 1)
        self.assertEqual(self.store.list_contact_conflicts(), ())

    def test_a_plan_that_is_never_confirmed_leaves_the_database_alone(self):
        before_bytes = self.database.read_bytes()
        before_changes = self.changes()

        plan = self.store.plan_contact_import(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"))
        self.assertEqual(plan.added, 1)  # the plan exists, and nothing was done with it

        self.assertEqual(self.changes(), before_changes)
        self.assertEqual(self.database.read_bytes(), before_bytes)
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)

    def test_a_file_the_parser_refuses_never_reaches_the_store(self):
        before_bytes = self.database.read_bytes()
        broken = self.folder / "broken.csv"
        broken.write_bytes(b"Email,Name\r\nsomeone@example.invalid,A Name,an-extra-field\r\n")

        with self.assertRaises(ContactCsvMalformed):
            contacts_module.read_contact_csv(broken)

        self.assertEqual(self.changes(), 0)
        self.assertEqual(self.database.read_bytes(), before_bytes)
        self.assertEqual(self.store.list_contacts(), ())

    def test_a_header_the_parser_refuses_never_reaches_the_store(self):
        no_email_column = self.folder / "no-email.csv"
        no_email_column.write_bytes(b"Name,Company Label\r\nSomeone,Somewhere\r\n")

        with self.assertRaises(ContactSchemaError):
            contacts_module.read_contact_csv(no_email_column)

        self.assertEqual(self.changes(), 0)
        self.assertEqual(self.store.list_contacts(), ())

    def test_a_privacy_leaking_header_is_not_a_disagreement(self):
        """A name column the file does not have is 'unchecked', and an empty answer is not a conflict."""
        parsed = self.parsed(f"{SAMPLE_EMAILS[0]},,,\r\n")

        plan = self.store.plan_contact_import(parsed)

        self.assertEqual(plan.conflicts, ())
        self.assertEqual(plan.entries[0].name, None)


class _FailingConnection:
    """The store's connection, with a chosen statement failing the way a storage error would.

    Injected by handing it to the store where the store keeps its own connection - the boundary every
    statement is written through - so the failure happens *underneath* the transaction and what is
    measured is the real rollback rather than a stubbed one. ``sqlite3.Connection`` cannot be patched
    (it is an immutable type) and patching a store method would exercise the stub instead of the
    transaction; this only ever makes SQLite itself refuse a statement.
    """

    def __init__(self, connection, *, fail_on: str, times: int = 0):
        self._connection = connection
        self._fail_on = fail_on
        self._remaining = times

    def execute(self, statement, *parameters):
        if str(statement).strip().startswith(self._fail_on):
            if self._remaining <= 0:
                raise sqlite3.OperationalError("disk I/O error")
            self._remaining -= 1
        return self._connection.execute(statement, *parameters)

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._connection.__exit__(exc_type, exc, tb)

    def __getattr__(self, name):
        return getattr(self._connection, name)


class WriteExactlyOnceTests(ContactStoreTestCase):
    """One confirmation writes one import, and a storage failure leaves none of it behind."""

    def test_a_confirmed_import_writes_each_row_once(self):
        parsed = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n"
        )
        before = self.changes()

        self.store.import_contacts(parsed)

        self.assertEqual(self.changes() - before, 2, "one insert per key and nothing else")
        self.assertEqual([record.seen_count for record in self.store.list_contacts()], [1, 1])
        self.assertEqual(log_path(self.database).read_text(encoding="utf-8").count("contacts.imported"), 1)

    def test_a_storage_failure_rolls_the_whole_import_back(self):
        parsed = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n"
        )
        # The parser groups rows that share a key, so a file that contradicts itself is how a conflict row
        # reaches the write loop: the contact rows are inserted first, and the failure happens after them.
        conflicting = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},2,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},3,\r\n"
        )
        failing = _FailingConnection(self.store._connection, fail_on="INSERT INTO hr_contact_conflict")
        with mock.patch.object(self.store, "_connection", failing):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.import_contacts(conflicting)

        self.assertEqual(self.store.list_contacts(), (), "a failed import must store nothing at all")
        self.assertEqual(self.store.list_contact_conflicts(), ())
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)
        connection = sqlite3.connect(str(self.database))
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM hr_contact").fetchone()[0], 0,
                             "the rollback must hold for a fresh connection, not just this one")
        finally:
            connection.close()
        # And the same file imports cleanly afterwards: the failure left no half-written state behind.
        outcome = self.store.import_contacts(conflicting)
        self.assertEqual((outcome.added, outcome.conflicts), (2, 1))

    def test_a_failure_in_the_middle_of_a_re_import_leaves_the_previous_state(self):
        self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[2]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n"))
        stored_before = self.store.get_contact(SAMPLE_EMAILS[0])
        # The first update of this import is allowed through and the second one fails: the rollback has to
        # undo a write that already happened, not merely a statement that never ran.
        failing = _FailingConnection(self.store._connection, fail_on="UPDATE hr_contact", times=1)
        changed = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},5,\r\n"
            f"{SAMPLE_EMAILS[2]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},6,\r\n"
        )
        with mock.patch.object(self.store, "_connection", failing):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.import_contacts(changed, observed_at="2026-10-16T11:00:00+00:00")

        self.assertEqual(self.store.get_contact(SAMPLE_EMAILS[0]), stored_before,
                         "the first update of a failed import must go back with it")
        self.assertEqual(self.keys(), [SAMPLE_EMAILS[0].casefold(), SAMPLE_EMAILS[2].casefold()])


class SuppressionTests(ContactStoreTestCase):
    """The do-not-contact mark is the person's own, and nothing in an import can clear it."""

    def test_the_mark_survives_a_re_import_of_the_same_file(self):
        parsed = self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n")
        self.store.import_contacts(parsed)
        marked = self.store.set_contact_suppression(SAMPLE_EMAILS[0], note="asked me not to write again")

        self.store.import_contacts(parsed)

        record = self.store.get_contact(SAMPLE_EMAILS[0])
        self.assertTrue(record.suppressed)
        self.assertEqual(record.suppressed_at, marked.suppressed_at)
        self.assertEqual(record.suppressed_note, "asked me not to write again")
        self.assertEqual(record.seen_count, 2, "the import still did its own work")
        self.assertEqual(len(self.store.list_contacts(suppressed=True)), 1)
        self.assertEqual(self.store.contact_record_counts()["do_not_contact"], 1)

    def test_the_mark_survives_a_file_that_contradicts_the_record(self):
        self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"))
        self.store.set_contact_suppression(SAMPLE_EMAILS[0])

        outcome = self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[2]},{SAMPLE_COMPANIES[1]},2,\r\n"))

        self.assertEqual(outcome.conflicts, 2)
        record = self.store.get_contact(SAMPLE_EMAILS[0])
        self.assertTrue(record.suppressed, "a contradicting file must not clear a do-not-contact mark")
        self.assertEqual(record.name, SAMPLE_NAMES[0])
        self.assertEqual(outcome.suppressed, 1, "the outcome says the mark was left alone")

    def test_the_mark_survives_a_restart(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,1,\r\n"))
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note="do not contact")

        reopened = self.reopen()

        record = reopened.get_contact(SAMPLE_EMAILS[0])
        self.assertTrue(record.suppressed)
        self.assertEqual(record.suppressed_note, "do not contact")

    def test_the_mark_survives_a_backup_and_a_restore(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,1,\r\n"))
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note="opt-out recorded by hand")
        self.store.close()
        chosen = self.folder / "chosen-backup.sqlite3"
        create_backup(self.database, chosen)

        # The live database loses the mark, so a restore that works is the only way it comes back.
        restored_from = "the live copy after the restore"
        reopened = CareerStore(str(self.database))
        reopened.set_contact_suppression(SAMPLE_EMAILS[0], suppressed=False)
        self.assertFalse(reopened.get_contact(SAMPLE_EMAILS[0]).suppressed)
        reopened.close()
        validate_app_database(chosen)
        restore_backup(chosen, self.database)

        after = CareerStore(str(self.database))
        self.addCleanup(after.close)
        record = after.get_contact(SAMPLE_EMAILS[0])
        self.assertTrue(record.suppressed, f"the mark must be in the backup that {restored_from} restored")
        self.assertEqual(record.suppressed_note, "opt-out recorded by hand")
        self.assertEqual(after.contact_record_counts()["do_not_contact"], 1)

    def test_clearing_the_mark_is_the_only_way_it_goes_away(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,1,\r\n"))
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note="not wanted")

        record = self.store.set_contact_suppression(SAMPLE_EMAILS[0], suppressed=False)

        self.assertFalse(record.suppressed)
        self.assertIsNone(record.suppressed_at, "a cleared mark leaves no day behind that claims otherwise")
        self.assertIsNone(record.suppressed_note, "nor a reason that no longer applies")

    def test_marking_an_address_that_was_never_imported_is_refused_without_a_write(self):
        before = self.changes()

        with self.assertRaises(ValueError) as caught:
            self.store.set_contact_suppression("nobody@example.invalid", note="not in the list")

        self.assertIn("nothing was changed", str(caught.exception))
        self.assertEqual(self.changes(), before)
        self.assertEqual(self.store.list_contacts(), ())

    def test_the_mark_is_normalised_the_same_way_the_key_is(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[0]},,1,\r\n"))

        marked = self.store.set_contact_suppression(SAMPLE_EMAILS[1].upper())

        self.assertTrue(marked.suppressed)
        self.assertEqual(marked.email_key, SAMPLE_EMAILS[1].casefold())


class ContactPlanTests(ContactStoreTestCase):
    """The plan is what a person is shown and confirms: counts and reasons, never a value."""

    def test_the_plan_says_what_will_be_added_updated_and_disagreed_about(self):
        self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"))
        plan = self.store.plan_contact_import(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},2,\r\n"
            f"{SAMPLE_EMAILS[2]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},3,\r\n"
            f",{SAMPLE_NAMES[2]},{SAMPLE_COMPANIES[1]},4,\r\n"
        ))

        self.assertEqual(plan.source_file, "contacts.csv")
        self.assertEqual((plan.added, plan.updated, len(plan.conflicts)), (1, 1, 1))
        self.assertEqual(plan.skipped_without_key, 1)
        self.assertEqual(plan.keys_in_file, 2)
        self.assertEqual(plan.rows_read, 3)
        self.assertEqual([entry.action for entry in plan.entries],
                         [ContactImportAction.UPDATED, ContactImportAction.ADDED])
        self.assertEqual(plan.entries[0].name, SAMPLE_NAMES[0], "the plan shows the name that will be stored")
        self.assertEqual(plan.entries[1].name, SAMPLE_NAMES[1])
        counts = plan.counts()
        self.assertEqual(counts["contacts to add"], 1)
        self.assertEqual(counts["contacts already stored, to be updated"], 1)
        self.assertEqual(counts["new disagreements that will be kept for review"], 1)
        self.assertEqual(counts["rows with no email key, which cannot be stored"], 1)

    def test_a_plan_for_an_empty_file_is_a_plan_to_do_nothing(self):
        parsed = self.parsed("")

        plan = self.store.plan_contact_import(parsed)

        self.assertEqual((plan.added, plan.updated, len(plan.conflicts)), (0, 0, 0))
        self.assertEqual(plan.entries, ())

    def test_a_plan_reports_a_key_that_is_already_marked_do_not_contact(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,1,\r\n"))
        self.store.set_contact_suppression(SAMPLE_EMAILS[0])

        plan = self.store.plan_contact_import(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,2,\r\n"))

        self.assertTrue(plan.entries[0].suppressed)
        self.assertEqual(plan.suppressed, 1)
        self.assertIn("never clears a do-not-contact mark", " ".join(plan.describe()))

    def test_the_entry_text_is_the_person_s_own_row_for_the_private_screen(self):
        plan = self.store.plan_contact_import(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"))

        self.assertEqual(plan.entries[0].describe_values(),
                         f"{SAMPLE_NAMES[0]} | {SAMPLE_EMAILS[0]} | {SAMPLE_COMPANIES[0]}")


class ContactPrivacyTests(ContactStoreTestCase):
    """No contact value reaches the log, an event detail, a printed summary or the logging module."""

    def setUp(self):
        super().setUp()
        self.parsed_file = self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,review this one\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n"
        )

    def log_text(self) -> str:
        return log_path(self.database).read_text(encoding="utf-8")

    def test_the_event_carries_counts_and_no_contact_value(self):
        outcome = self.store.import_contacts(self.parsed_file)

        written = self.log_text()
        self.assertIn("event=contacts.imported", written)
        self.assertIn(f"added={outcome.added} updated={outcome.updated}", written)
        for value in ALL_SAMPLE_VALUES + ("contacts.csv", "review this one"):
            self.assertNotIn(value, written, f"{value!r} must not reach the event log")

    def test_the_imported_event_is_part_of_the_declared_vocabulary(self):
        self.assertIn("contacts.imported", EVENTS)

    def test_a_change_to_the_mark_records_the_flag_and_nothing_else(self):
        """The one screen that writes this column writes one line about it: a flag, never a reason or a row."""
        self.store.import_contacts(self.parsed_file)
        reason = "a reason the log must never carry"

        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note=reason)
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], suppressed=False)

        written = self.log_text()
        marks = [line for line in written.splitlines() if "event=contacts.suppressed" in line]
        self.assertEqual(len(marks), 2, "one line per change to the mark, and no line for a read")
        self.assertEqual([line.rsplit("detail=", 1)[-1].strip() for line in marks],
                         ["suppressed=true", "suppressed=false"])
        for value in ALL_SAMPLE_VALUES + (reason, "contacts.csv"):
            self.assertNotIn(value, written, f"{value!r} must not reach the event log")

    def test_a_printed_summary_carries_counts_and_no_contact_value(self):
        plan = self.store.plan_contact_import(self.parsed_file)
        outcome = self.store.import_contacts(self.parsed_file)

        printed = "\n".join(plan.describe()) + "\n" + outcome.describe()
        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, printed, f"{value!r} must not reach a summary a person can paste")
        for key in (record.email_key for record in self.store.list_contacts()):
            self.assertNotIn(key, printed, "not even the comparison key may be printed")
        self.assertIn("2 contact(s) added", printed)
        self.assertIn("nothing has been written yet", printed)

    def test_nothing_emitted_through_the_logging_module_carries_a_contact_value(self):
        seen: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: seen.append(record.getMessage())  # noqa: E731 - one line, one job
        root = logging.getLogger()
        root.addHandler(handler)
        self.addCleanup(root.removeHandler, handler)

        self.store.import_contacts(self.parsed_file)

        joined = "\n".join(seen)
        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, joined)

    def test_the_parser_s_preview_never_prints_a_value_either(self):
        """The review text the window shows is the parser's, and it is safe to paste as it stands."""
        printed = "\n".join(self.parsed_file.describe())

        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, printed)


class DamagedContactRecordTests(ContactStoreTestCase):
    """A hand-edited row is refused by type instead of being read as something it is not."""

    def test_a_row_without_a_key_is_refused_by_the_decoder(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,1,\r\n"))
        self.store.close()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute(
                "INSERT INTO hr_contact(email_key, email, source_file, first_seen_at, last_seen_at) "
                "VALUES ('', 'nobody@example.invalid', 'by hand', '2026-01-01T00:00:00+00:00', "
                "'2026-01-01T00:00:00+00:00')")
            connection.commit()
        finally:
            connection.close()

        store = CareerStore(str(self.database))
        self.addCleanup(store.close)

        with self.assertRaises(StoredRecordError) as caught:
            store.list_contacts()

        self.assertIn("no email key", str(caught.exception))

    def test_a_mark_that_is_not_zero_or_one_is_refused_by_the_decoder(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,1,\r\n"))
        self.store.close()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("UPDATE hr_contact SET suppressed = 5")
            connection.commit()
        finally:
            connection.close()

        store = CareerStore(str(self.database))
        self.addCleanup(store.close)

        with self.assertRaises(StoredRecordError) as caught:
            store.get_contact(SAMPLE_EMAILS[0])

        self.assertIn("do-not-contact mark", str(caught.exception))

    def test_a_disagreement_with_an_unknown_origin_is_refused_by_the_decoder(self):
        self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},2,\r\n"))
        self.store.close()
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("UPDATE hr_contact_conflict SET origin = 'somewhere-else'")
            connection.commit()
        finally:
            connection.close()

        store = CareerStore(str(self.database))
        self.addCleanup(store.close)

        with self.assertRaises(StoredRecordError) as caught:
            store.list_contact_conflicts()

        self.assertIn("origin", str(caught.exception))


class ContactSchemaTests(ContactStoreTestCase):
    """The contact tables are part of the schema contract, and they are usable the moment they exist."""

    def test_a_fresh_database_holds_the_contact_tables_of_the_current_schema(self):
        tables = {
            row[0] for row in self.store._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        }
        self.assertEqual(tables, set(SCHEMA_TABLES_BY_VERSION[SCHEMA_VERSION]))
        self.assertEqual(self.store._connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(self.store.contact_record_counts(),
                         {"contacts": 0, "do_not_contact": 0, "with_review_flags": 0, "conflicts": 0})

    def test_deleting_a_contact_takes_its_evidence_with_it(self):
        self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},2,\r\n"))
        self.assertEqual(len(self.store.list_contact_conflicts()), 1)

        with self.store._connection:
            self.store._connection.execute("DELETE FROM hr_contact")

        self.assertEqual(self.store.list_contact_conflicts(), (),
                         "evidence about a key that no longer exists is nothing a person can act on")

    def test_the_backup_validator_accepts_a_database_holding_contacts(self):
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},,1,\r\n"))
        self.store.close()
        chosen = self.folder / "with-contacts.sqlite3"

        info = create_backup(self.database, chosen)

        self.assertEqual(info.schema_version, SCHEMA_VERSION)
        # The copy is read back through the same store, so "the backup carries the contact list" is a
        # property of the file rather than a claim about the call that produced it.
        copied = CareerStore(str(chosen))
        self.addCleanup(copied.close)
        self.assertEqual([record.email_key for record in copied.list_contacts()],
                         ["first.contact@example.invalid"])
        self.assertEqual(copied.contact_record_counts()["contacts"], 1)


class ContactDeletionTests(ContactStoreTestCase):
    """Deleting one contact: what goes with it, what never does, and what a failure leaves behind.

    The increment adds the first operation that removes a contact's own row, so the properties that matter
    are the ones a destructive action has to earn: exactly one record goes, the evidence the schema ties to
    it goes too, nothing else moves, a refusal or a failure changes nothing at all, and the one line this
    application writes about it is a count. Two facts are documented here rather than claimed away: the
    deletion is a change to *this* database (a backup written earlier still holds the record and restoring
    it brings the contact back), and the conflicts are removed by an explicit statement rather than only by
    the declared cascade.
    """

    def _with_evidence_and_a_neighbour(self) -> None:
        """Two contacts that each disagree with the file that supplied them: what these tests delete from.

        Both have one disagreement of their own, so a test can require that deleting one takes *its*
        evidence and leaves the other's - which a fixture where only the deleted contact had evidence could
        not distinguish from a deletion that removed every conflict row in the table. A real parse of a
        synthetic file, for the same reason the other classes use one: what a re-import records is the
        parser's grouping plus the store's comparison, and a hand-built object would test neither.
        """
        self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},2,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},3,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},4,\r\n"))

    def test_deleting_one_contact_removes_it_and_only_its_evidence(self):
        self._with_evidence_and_a_neighbour()
        self.store.set_contact_suppression(SAMPLE_EMAILS[1], note="second contact's own note")
        second_before = self.store.get_contact(SAMPLE_EMAILS[1])
        conflicts_before = self.store.list_contact_conflicts()
        self.assertEqual([conflict.email_key for conflict in conflicts_before],
                         [SAMPLE_EMAILS[0].strip().casefold(), SAMPLE_EMAILS[1].strip().casefold()],
                         "each contact has one disagreement of its own, so the deletion has something to "
                         "leave behind as well as something to remove")
        before = self.changes()

        outcome = self.store.delete_contact(SAMPLE_EMAILS[0])

        self.assertTrue(outcome.deleted)
        self.assertEqual(outcome.conflicts, 1, "the count is what the confirmation and the log are built from")
        # One row per statement: the conflict and the contact, and nothing else.
        self.assertEqual(self.changes() - before, 2,
                         "the deletion must touch exactly the contact row and its disagreement rows")
        self.assertIsNone(self.store.get_contact(SAMPLE_EMAILS[0]))
        self.assertEqual([conflict.email_key for conflict in self.store.list_contact_conflicts()],
                         [SAMPLE_EMAILS[1].strip().casefold()],
                         "the other contact's disagreement is not the one being deleted")
        # The contact that was not chosen is untouched, mark, note and all.
        self.assertEqual(self.store.get_contact(SAMPLE_EMAILS[1]), second_before)
        self.assertEqual(self.store.contact_record_counts()["contacts"], 1)

    def test_the_other_contacts_mark_survives_and_the_deleted_one_goes_with_its_record(self):
        self._with_evidence_and_a_neighbour()
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note="delete me")
        self.store.set_contact_suppression(SAMPLE_EMAILS[1], note="keep me")

        self.store.delete_contact(SAMPLE_EMAILS[0])

        kept = self.store.get_contact(SAMPLE_EMAILS[1])
        assert kept is not None
        self.assertTrue(kept.suppressed, "an unrelated do-not-contact mark is not this deletion's business")
        self.assertEqual(kept.suppressed_note, "keep me")
        self.assertIsNotNone(kept.suppressed_at)
        self.assertIsNone(self.store.get_contact(SAMPLE_EMAILS[0]),
                          "the deleted record's own mark goes with the record; it holds a suppressed flag")
        self.assertEqual(self.store.contact_record_counts()["do_not_contact"], 1)

    def test_deleting_an_address_the_store_does_not_hold_deletes_nothing(self):
        self._with_evidence_and_a_neighbour()
        before = self.changes()

        outcome = self.store.delete_contact(SAMPLE_EMAILS[2])

        self.assertFalse(outcome.deleted, "a delete that found nothing does not claim to have deleted")
        self.assertEqual(outcome.conflicts, 0)
        self.assertEqual(self.changes(), before, "and it writes nothing at all")
        self.assertEqual(len(self.store.list_contacts()), 2)
        self.assertEqual(len(self.store.list_contact_conflicts()), 2, "both disagreements are still there")
        self.assertNotIn("contacts.deleted", log_path(self.database).read_text(encoding="utf-8"),
                         "nothing was deleted, so there is no deletion to report")

    def test_the_address_is_normalised_the_way_every_other_contact_lookup_is(self):
        self._with_evidence_and_a_neighbour()

        outcome = self.store.delete_contact("  FIRST.Contact@Example.Invalid  ")

        self.assertTrue(outcome.deleted, "the key is trimmed and case-folded here as everywhere else")
        self.assertIsNone(self.store.get_contact(SAMPLE_EMAILS[0]))

    def test_a_failure_while_deleting_the_evidence_leaves_the_contact_and_the_evidence(self):
        self._with_evidence_and_a_neighbour()
        before = self.changes()
        failing = _FailingConnection(self.store._connection, fail_on="DELETE FROM hr_contact_conflict")

        with mock.patch.object(self.store, "_connection", failing):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.delete_contact(SAMPLE_EMAILS[0])

        self.assertEqual(self.changes(), before, "a failed deletion changes no row, not even the one it read")
        self.assertIsNotNone(self.store.get_contact(SAMPLE_EMAILS[0]))
        self.assertEqual([conflict.email_key for conflict in self.store.list_contact_conflicts()],
                         [SAMPLE_EMAILS[0].strip().casefold(), SAMPLE_EMAILS[1].strip().casefold()],
                         "both contacts keep their evidence when neither was deleted")
        # And the database is left usable: the rollback is not a half-open transaction.
        self.assertTrue(self.store.delete_contact(SAMPLE_EMAILS[0]).deleted)
        self.assertEqual([conflict.email_key for conflict in self.store.list_contact_conflicts()],
                         [SAMPLE_EMAILS[1].strip().casefold()])

    def test_a_failure_while_deleting_the_contact_leaves_its_evidence_where_it_was(self):
        """The second statement failing is the case an explicit cascade delete exists to keep whole."""
        self._with_evidence_and_a_neighbour()
        failing = _FailingConnection(self.store._connection, fail_on="DELETE FROM hr_contact WHERE")

        with mock.patch.object(self.store, "_connection", failing):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.delete_contact(SAMPLE_EMAILS[0])

        self.assertIsNotNone(self.store.get_contact(SAMPLE_EMAILS[0]))
        self.assertIn(SAMPLE_EMAILS[0].strip().casefold(),
                      [conflict.email_key for conflict in self.store.list_contact_conflicts()],
                      "a contact that is still here keeps the disagreements recorded about it")
        self.assertEqual(len(self.store.list_contact_conflicts()), 2)

    def test_the_evidence_is_deleted_by_name_and_not_only_by_the_declared_cascade(self):
        """The cascade is a second line of defence, not the thing this method relies on.

        Foreign keys are switched off for this test, which is the situation a future change - a pragma moved,
        a connection opened without it - would silently create. The conflicts still go, because the deletion
        removes them itself; relying on the cascade would leave orphans behind here while reporting success.
        """
        self._with_evidence_and_a_neighbour()
        self.store._connection.execute("PRAGMA foreign_keys = OFF")
        self.addCleanup(self.store._connection.execute, "PRAGMA foreign_keys = ON")

        outcome = self.store.delete_contact(SAMPLE_EMAILS[0])

        self.assertTrue(outcome.deleted)
        self.assertEqual([conflict.email_key for conflict in self.store.list_contact_conflicts()],
                         [SAMPLE_EMAILS[1].strip().casefold()],
                         "with the cascade off, an explicit delete is the only thing that removes the "
                         "deleted contact's evidence - and it removes nothing else")

    def test_the_declared_cascade_is_really_enabled_on_a_connection_that_writes(self):
        """The safety net is asserted where it lives, so the test above cannot pass for the wrong reason."""
        self.assertEqual(self.store._connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        declared = self.store._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='hr_contact_conflict'").fetchone()[0]
        self.assertIn("ON DELETE CASCADE", declared)
        self.assertIn("REFERENCES hr_contact(email_key)", declared)

    def test_a_deletion_leaves_no_orphan_evidence_and_a_sound_database(self):
        self._with_evidence_and_a_neighbour()

        self.store.delete_contact(SAMPLE_EMAILS[0])

        orphans = self.store._connection.execute(
            "SELECT COUNT(*) FROM hr_contact_conflict WHERE email_key NOT IN (SELECT email_key FROM hr_contact)"
        ).fetchone()[0]
        self.assertEqual(orphans, 0)
        self.assertEqual(list(self.store._connection.execute("PRAGMA foreign_key_check").fetchall()), [],
                         "the foreign-key check must find nothing to complain about")
        self.assertEqual(self.store._connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.store._connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION,
                         "deleting a record is not a schema change")

    def test_a_deletion_is_still_a_deletion_after_a_restart_and_a_backup_taken_afterwards(self):
        self._with_evidence_and_a_neighbour()
        self.store.delete_contact(SAMPLE_EMAILS[0])

        reopened = self.reopen()

        self.assertIsNone(reopened.get_contact(SAMPLE_EMAILS[0]), "a restart brings no record back")
        self.assertEqual([conflict.email_key for conflict in reopened.list_contact_conflicts()],
                         [SAMPLE_EMAILS[1].strip().casefold()],
                         "the deleted contact's evidence is gone and the other contact's is not")
        self.assertEqual([record.email_key for record in reopened.list_contacts()],
                         [SAMPLE_EMAILS[1].strip().casefold()])
        chosen = self.folder / "after-deletion.sqlite3"
        reopened.close()
        info = create_backup(self.database, chosen)
        self.addCleanup(lambda: CareerStore(str(chosen)).close())
        copy = CareerStore(str(chosen))
        try:
            self.assertEqual(info.schema_version, SCHEMA_VERSION)
            self.assertIsNone(copy.get_contact(SAMPLE_EMAILS[0]),
                              "a backup taken after the deletion does not hold the deleted record")
            self.assertEqual(copy.contact_record_counts()["conflicts"], 1,
                             "the backup holds the deletion as this database holds it: one contact and one "
                             "disagreement, and neither of them the deleted one")
        finally:
            copy.close()
        self.reopen()

    def test_a_backup_written_before_the_deletion_still_holds_the_record(self):
        """The honest limit of a per-record delete, asserted rather than left to a sentence.

        A restore replaces this database with the copy the person chose, so a copy made *before* the deletion
        brings the contact back. Deleting a record is not a claim about backups and exports at paths this
        application never knew, and the window says so before it asks.
        """
        self._with_evidence_and_a_neighbour()
        chosen = self.folder / "before-deletion.sqlite3"
        create_backup(self.database, chosen)

        self.store.delete_contact(SAMPLE_EMAILS[0])
        self.store.close()
        restore_backup(chosen, self.database)
        self.reopen()

        restored = self.store.get_contact(SAMPLE_EMAILS[0])
        self.assertIsNotNone(restored, "a restore replaces the database with the copy, deletions included")
        self.assertEqual(len(self.store.list_contact_conflicts()), 2,
                         "and the evidence recorded about it comes back with it")
        self.assertEqual(validate_app_database(self.database).schema_version, SCHEMA_VERSION)

    def test_the_event_carries_counts_and_no_contact_value(self):
        self._with_evidence_and_a_neighbour()

        self.store.delete_contact(SAMPLE_EMAILS[0])

        written = log_path(self.database).read_text(encoding="utf-8")
        self.assertIn("event=contacts.deleted", written)
        self.assertIn("detail=contacts=1 conflicts=1", written)
        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, written, f"{value!r} reached the activity log")
        for value in ("contacts.csv", SAMPLE_NAMES[0], SAMPLE_NAMES[1]):
            self.assertNotIn(value, written, f"{value!r} reached the activity log")
        # The vocabulary is one list, and this is the check that the new name is part of it.
        self.assertIn("contacts.deleted", EVENTS)


class ContactExportReadBackTests(ContactStoreTestCase):
    """The export read back through the store: what an import of it does, and what it cannot do.

    ``tests/test_contact_export.py`` holds the format's own contract. What belongs here is the part that
    needs a database on both sides: that the file this application writes is a file this application can
    import, that importing it into a second database carries the list and nothing else, and that the
    do-not-contact column in it is text - a mark the person made is never applied, and never cleared, by
    any file. The last of those is the documented limitation of this format, asserted where it would fail
    if the import ever grew a statement for that column.
    """

    def _marked_list(self) -> Path:
        """Two contacts, one of them marked, exported to a file beside this test's database."""
        self.store.import_contacts(self.parsed(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n"))
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note="synthetic note beside the mark")
        return contact_export.write_export(self.store, self.folder / "export.csv").path

    def test_importing_the_export_into_another_database_carries_the_list(self):
        exported = self._marked_list()
        second = self.folder / "second.sqlite3"

        with CareerStore(str(second)) as other:
            outcome = other.import_contacts(contacts_module.read_contact_csv(exported))
            stored = {record.email_key: record for record in other.list_contacts()}

        self.assertEqual((outcome.added, outcome.updated, outcome.conflicts), (2, 0, 0))
        self.assertEqual(sorted(stored), sorted(
            [email.strip().casefold() for email in SAMPLE_EMAILS[:2]]))
        self.assertEqual(stored[SAMPLE_EMAILS[0].casefold()].name, SAMPLE_NAMES[0])
        self.assertEqual(stored[SAMPLE_EMAILS[1].casefold()].company, SAMPLE_COMPANIES[1])

    def test_the_marked_column_in_the_file_cannot_mark_or_unmark_anything(self):
        exported = self._marked_list()
        # The file says yes for the marked contact and no for the other, and a file cannot write either.
        text = exported.read_text(encoding="utf-8")
        self.assertIn(",yes,hr-contact-export/1", text)
        self.assertIn(",no,hr-contact-export/1", text)

        self.store.import_contacts(contacts_module.read_contact_csv(exported))

        marked = self.store.get_contact(SAMPLE_EMAILS[0])
        unmarked = self.store.get_contact(SAMPLE_EMAILS[1])
        assert marked is not None and unmarked is not None
        self.assertTrue(marked.suppressed, "a re-import cleared a mark the person made")
        self.assertEqual(marked.suppressed_note, "synthetic note beside the mark")
        self.assertFalse(unmarked.suppressed,
                         "a file set a do-not-contact mark: that column belongs to the person alone")
        self.assertEqual(self.store.contact_record_counts()["do_not_contact"], 1)

    def test_an_export_writes_no_line_about_itself_and_changes_no_row(self):
        """The module is read-only; whether an export is *reported* is the window's and the CLI's call."""
        self.store.import_contacts(self.parsed(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"))
        before = self.changes()
        logged = log_path(self.database).read_text(encoding="utf-8")

        contact_export.write_export(self.store, self.folder / "export.csv")

        self.assertEqual(self.changes(), before, "an export wrote to the database")
        self.assertEqual(log_path(self.database).read_text(encoding="utf-8"), logged,
                         "the export module wrote a line to the activity log")
        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, log_path(self.database).read_text(encoding="utf-8"),
                             f"{value!r} reached the activity log")


if __name__ == "__main__":  # pragma: no cover - convenience for a single-module run
    unittest.main()
