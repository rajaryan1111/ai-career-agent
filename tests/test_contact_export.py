"""Tests for the HR contact export: the format's own contract, and the file it writes.

``career_agent.contact_export`` is the only writer of the contact CSV, and this file is where the claims
that module makes are checked against real files: the columns and the version cell, the encoding and the
line endings to the byte, one row per stored contact, what a value holding a comma, a quote, a line ending
or a non-ASCII character becomes, what happens to a cell a spreadsheet would execute, what an empty list
and an oversized list do, and what the export never carries - a mark's reason, a disagreement's other
value, a provenance name, a timestamp.

Two things are checked from the same direction throughout: the file is read back through the *real* parser
this application ships (so "suitable for re-import" is a fact about these bytes rather than about a second
reading of the same rules), and the database is compared with its own counters before and after (so
"read-only" is a fact about the store rather than about a docstring). A third property is documented rather
than claimed away: the do-not-contact column is text in the file, and an import cannot apply it. That is
asserted here as the limitation it is, in ``ImportReadBackTests``.

Every fixture is synthetic, every address is on a reserved ``.invalid`` domain, and no real contact list is
used anywhere in this file.
"""
from __future__ import annotations

import csv
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_agent import contact_export, contacts as contacts_module
from career_agent.event_log import log_path
from career_agent.store import (
    SCHEMA_VERSION, CareerStore, ContactRecord, PrivateWriteError, StoredRecordError,
)

#: The fixture's values, held in one place so the tests that require a value to be *absent* can name them
#: all. Synthetic people on a reserved domain.
SAMPLE_EMAILS = ("first.contact@example.invalid", "SECOND.Contact@Example.Invalid",
                 "third.contact@example.invalid")
SAMPLE_NAMES = ("Sample Person One", "Sample Person Two", "Sample Person Three")
SAMPLE_COMPANIES = ("Sample Employer One", "Sample Employer Two")
SAMPLE_MARK_REASON = "synthetic note typed beside the mark"
SAMPLE_REVIEW_REASON = "synthetic note carried by the file"
ALL_SAMPLE_VALUES = SAMPLE_EMAILS + SAMPLE_NAMES + SAMPLE_COMPANIES

HEADER = "Email,Name,Company Label,Source Rows,Review Reason\r\n"

#: What the format writes, spelled out here as bytes rather than read from the module: a test that took the
#: header from the code it is testing would pass for any header the code happened to have.
DOCUMENTED_HEADER = b"Email,Name,Company,Do Not Contact,Export Format\r\n"
FORMAT_CELL = b"hr-contact-export/1"
FORMAT_CELL_TEXT = "hr-contact-export/1"


class ContactExportTestCase(unittest.TestCase):
    """A disposable database with synthetic contacts in it, and a folder to write exports into."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)

    def write(self, rows: str, name: str = "contacts.csv", *, header: str = HEADER) -> Path:
        path = self.folder / name
        path.write_bytes((header + rows).encode("utf-8"))
        return path

    def import_rows(self, rows: str, name: str = "contacts.csv", *,
                    observed_at: str | None = None) -> None:
        """Store a file through the real parser, which is what the window's own import does."""
        self.store.import_contacts(
            contacts_module.read_contact_csv(self.write(rows, name=name)), observed_at=observed_at)

    def two_contacts(self) -> None:
        self.import_rows(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,{SAMPLE_REVIEW_REASON}\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n")

    def export(self, name: str = "export.csv") -> tuple[Path, contact_export.ContactExportOutcome]:
        target = self.folder / name
        return target, contact_export.write_export(self.store, target)

    def exported_bytes(self, name: str = "export.csv") -> bytes:
        return self.folder.joinpath(name).read_bytes()

    @staticmethod
    def cells(data: bytes) -> list[list[str]]:
        """Every cell of a written file, decoded the way a reader that knows it is UTF-8 would."""
        return list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))

    def changes(self) -> int:
        return self.store._connection.total_changes

    def log_text(self) -> str:
        return log_path(self.database).read_text(encoding="utf-8")


class FormatContractTests(ContactExportTestCase):
    """What the file is: its bytes, its columns, its version cell and what a row holds."""

    def test_the_header_and_the_version_cell_are_the_documented_ones(self):
        self.two_contacts()

        target, outcome = self.export()

        raw = target.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "the file does not begin with a UTF-8 mark")
        self.assertTrue(raw[len(b"\xef\xbb\xbf"):].startswith(DOCUMENTED_HEADER),
                        f"the header row is {raw[:80]!r}")
        rows = self.cells(raw)
        self.assertEqual(rows[0], ["Email", "Name", "Company", "Do Not Contact", "Export Format"])
        self.assertEqual(len(rows), 3, "one header row and one row per stored contact")
        for row in rows[1:]:
            self.assertEqual(row[4], FORMAT_CELL_TEXT, "every row says which format it is")
            self.assertIn(row[3], ("yes", "no"), "the mark column is one of two literals")
        self.assertEqual((outcome.contacts, outcome.marked), (2, 0))
        self.assertEqual(outcome.bytes_written, len(raw), "the count reported is the file's own size")

    def test_each_row_holds_the_stored_address_name_and_company(self):
        self.two_contacts()

        self.export()

        rows = self.cells(self.exported_bytes())[1:]
        self.assertEqual([row[0] for row in rows], [SAMPLE_EMAILS[0], SAMPLE_EMAILS[1]])
        self.assertEqual([row[1] for row in rows], [SAMPLE_NAMES[0], SAMPLE_NAMES[1]])
        self.assertEqual([row[2] for row in rows], [SAMPLE_COMPANIES[0], SAMPLE_COMPANIES[1]])

    def test_the_mark_column_says_whether_each_contact_is_marked(self):
        self.two_contacts()
        self.store.set_contact_suppression(SAMPLE_EMAILS[1], note=SAMPLE_MARK_REASON)

        _, outcome = self.export()

        rows = self.cells(self.exported_bytes())[1:]
        self.assertEqual([row[3] for row in rows], ["no", "yes"])
        self.assertEqual(outcome.marked, 1)

    def test_the_bytes_are_utf8_crlf_and_the_same_twice(self):
        self.two_contacts()

        first_target, first = self.export(name="first.csv")
        second_target, _ = self.export(name="second.csv")

        raw = first_target.read_bytes()
        # CRLF everywhere and nowhere else: a bare LF would mean the line ending depends on the platform
        # that wrote the file, which is the one thing this format may not do.
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "the file holds a line ending that is not CRLF")
        self.assertEqual(raw, second_target.read_bytes(), "the same list exported twice is not the same file")
        self.assertEqual(first.bytes_written, len(raw))

    def test_one_row_per_stored_contact_however_many_times_a_key_was_imported(self):
        """The database holds one row per normalised key, so the file cannot hold a duplicate of one."""
        self.import_rows(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},2,\r\n")
        self.import_rows(f"  {SAMPLE_EMAILS[0]}  ,{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},3,\r\n",
                         name="again.csv")

        _, outcome = self.export()

        rows = self.cells(self.exported_bytes())[1:]
        self.assertEqual(len(rows), 1)
        self.assertEqual(len({row[0].strip().casefold() for row in rows}), len(rows),
                         "the file names one address more than once")
        self.assertEqual(outcome.contacts, 1)

    def test_an_empty_list_still_writes_the_documents_header(self):
        """A list with nothing in it is still a list: the file says what it would have held."""
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)

        target, outcome = self.export()

        self.assertEqual(outcome.contacts, 0)
        self.assertEqual(outcome.marked, 0)
        self.assertEqual(target.read_bytes()[len(b"\xef\xbb\xbf"):], DOCUMENTED_HEADER)
        read = contacts_module.read_contact_csv(target)
        self.assertEqual(read.rows, (), "the reader must accept a header-only file and find no rows")
        self.assertEqual(read.counts()["unique email keys"], 0)

    def test_the_address_text_is_exported_as_stored_including_its_case(self):
        self.import_rows(f"SECOND.Contact@Example.Invalid,{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},1,\r\n")

        self.export()

        row, = self.cells(self.exported_bytes())[1:]
        self.assertEqual(row[0], "SECOND.Contact@Example.Invalid",
                         "the key is normalised for matching, and the text the file wrote is not")

    def test_a_contact_this_build_cannot_decode_stops_the_export_instead_of_being_skipped(self):
        """A shorter list the person believes is whole is the worst outcome available, so it is not one."""
        self.two_contacts()
        self.store._connection.execute("UPDATE hr_contact SET email_key = '' WHERE contact_id = 1")
        self.store._connection.commit()

        with self.assertRaises(StoredRecordError):
            self.export()

        self.assertFalse((self.folder / "export.csv").exists(),
                         "a refused export must not leave a file holding the records it could read")


class TheFormatsOwnClaimsTests(unittest.TestCase):
    """The sentences the format module owns, asserted as the claims they are.

    ``MARK_COLUMN_LIMITATION`` is shared by the window and the command line, and the tests around this one
    prove that both *use* it. That only means they agree - so what the sentence itself says is asserted
    here, against its substance rather than against its identity. A one-line version of it passed every
    other test in this file, which is what this class exists to prevent.
    """

    def test_the_mark_limitation_names_the_column_and_says_what_an_import_cannot_do(self):
        claim = contact_export.MARK_COLUMN_LIMITATION
        self.assertIn('"Do Not Contact"', claim, "the sentence does not name the column it is about")
        self.assertIn("cannot set or clear", claim,
                      "the sentence does not say what an import of the file cannot do")
        self.assertIn("read the column", claim,
                      "the sentence does not say what to do with the column instead")

    def test_the_format_identifies_itself_in_one_cell_of_every_row(self):
        self.assertEqual(contact_export.CONTACT_EXPORT_FORMAT, "hr-contact-export/1")
        self.assertEqual(contact_export.CONTACT_EXPORT_FORMAT,
                         f"{contact_export.CONTACT_EXPORT_FORMAT_NAME}/"
                         f"{contact_export.CONTACT_EXPORT_FORMAT_VERSION}")
        self.assertIn("Export Format", contact_export.CONTACT_EXPORT_HEADERS,
                      "the column that states the version is not one of the documented headers")

    def test_the_headers_are_the_documented_five_in_the_documented_order(self):
        self.assertEqual(contact_export.CONTACT_EXPORT_HEADERS,
                         ("Email", "Name", "Company", "Do Not Contact", "Export Format"))

    def test_the_mark_column_has_two_literals_and_no_empty_cell(self):
        self.assertEqual((contact_export.DO_NOT_CONTACT_YES, contact_export.DO_NOT_CONTACT_NO),
                         ("yes", "no"))


class ValueEncodingTests(ContactExportTestCase):
    """What a value becomes in the file, and what the shipped parser reads back out of it."""

    def test_a_name_holding_a_comma_a_quote_and_a_line_ending_survives_the_round_trip(self):
        awkward = 'Sample, "Quoted"\nPerson'
        self.import_rows(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n")
        self.store._connection.execute("UPDATE hr_contact SET name = ? WHERE email_key = ?",
                                       (awkward, SAMPLE_EMAILS[0]))
        self.store._connection.commit()

        target, _ = self.export()

        raw = target.read_bytes()
        self.assertIn(b'"Sample, ""Quoted""\nPerson"', raw,
                      "a cell holding a comma, a quote and a line ending must be quoted and doubled")
        read = contacts_module.read_contact_csv(target)
        self.assertEqual(read.rows[0].name, awkward, "the parser no longer reads the value the file holds")

    def test_non_ascii_text_is_written_as_utf8_and_reads_back_unchanged(self):
        name = "Zo\u00eb \u00c5ngstr\u00f6m \u2014 \u00dcn\u00efcode"
        self.import_rows(f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n")
        self.store._connection.execute("UPDATE hr_contact SET name = ? WHERE email_key = ?",
                                       (name, SAMPLE_EMAILS[0]))
        self.store._connection.commit()

        target, _ = self.export()

        # The bytes are UTF-8, not an escape sequence and not the platform's older code page, and the mark
        # at the start of the file is what tells a spreadsheet to read them that way.
        self.assertIn(name.encode("utf-8"), target.read_bytes())
        self.assertNotIn("\\u00eb".encode("ascii"), target.read_bytes())
        self.assertEqual(contacts_module.read_contact_csv(target).rows[0].name, name)

    def test_a_cell_a_spreadsheet_would_execute_is_written_with_a_leading_apostrophe(self):
        dangerous = ("=SUM(A1:A9)", "+1+1", "-2+3", "@SUM(A1)")
        self.import_rows(
            "".join(f"contact{index}@example.invalid,{value},Employer,{index},\r\n"
                    for index, value in enumerate(dangerous, start=1)))

        target, _ = self.export()

        rows = self.cells(target.read_bytes())[1:]
        self.assertEqual([row[1] for row in rows], [f"'{value}" for value in dangerous],
                         "a cell that would start a formula is not written with the guard")
        # The guard is the price of the file being safe to open in a spreadsheet, and it is visible to
        # this application's own reader: the apostrophe is the first character of the value.
        read = contacts_module.read_contact_csv(target)
        self.assertEqual([row.name for row in read.rows], [f"'{value}" for value in dangerous])

    def test_ordinary_values_are_written_exactly_as_they_are_stored(self):
        ordinary = ("Sample-Person One", "Sample Person (Two)", "Employer & Co.", "O'Brien")
        self.import_rows(
            "".join(f"ordinary{index}@example.invalid,{value},Employer,{index},\r\n"
                    for index, value in enumerate(ordinary, start=1)))

        self.export()

        rows = self.cells(self.exported_bytes())[1:]
        self.assertEqual([row[1] for row in rows], list(ordinary),
                         "the guard must only ever touch a cell a spreadsheet would execute")

    def test_a_contact_without_a_name_or_a_company_writes_empty_cells(self):
        self.import_rows(f"{SAMPLE_EMAILS[0]},,,\r\n")

        target, _ = self.export()

        row, = self.cells(target.read_bytes())[1:]
        self.assertEqual(row, [SAMPLE_EMAILS[0], "", "", "no", FORMAT_CELL_TEXT])
        read = contacts_module.read_contact_csv(target)
        self.assertEqual(read.rows[0].name, "")
        self.assertEqual(read.rows[0].company, "")


class PrivacyTests(ContactExportTestCase):
    """What the file must not hold, asserted against the fixture's own values rather than a wording."""

    def _everything_in_the_database(self) -> None:
        self.import_rows(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},7,{SAMPLE_REVIEW_REASON}\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},8,\r\n",
            observed_at="2026-10-16T09:00:00+00:00")
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note=SAMPLE_MARK_REASON)
        # A disagreement of both kinds, so the export has evidence beside it to leave behind.
        self.import_rows(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[2]},{SAMPLE_COMPANIES[0]},9,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},10,\r\n",
            name="later-list.csv")

    def test_the_file_holds_no_mark_reason_no_disagreement_and_no_provenance(self):
        self._everything_in_the_database()
        conflict_values = {
            conflict.other_value for conflict in self.store.list_contact_conflicts()
        } | {conflict.kept_value for conflict in self.store.list_contact_conflicts()}

        target, _ = self.export()

        raw = target.read_bytes()
        forbidden = [SAMPLE_MARK_REASON, SAMPLE_REVIEW_REASON, "contacts.csv", "later-list.csv",
                     "2026-10-16T09:00:00+00:00", "Source Rows", "Review Reason", "conflict_id",
                     "contact_id", "seen_count"]
        # What the disagreement is *about* is subtracted from what must be absent: the address is the list,
        # and the name and company the record holds are the record. Every value that arrived from the other
        # side - the evidence - is what must never be in the file.
        stored_values = {value for record in self.store.list_contacts()
                         for value in (record.email, record.email_key, record.name, record.company)
                         if value}
        for value in forbidden:
            self.assertNotIn(value.encode("utf-8"), raw, f"{value!r} reached the exported file")
        for value in conflict_values - stored_values:
            self.assertNotIn(value.encode("utf-8"), raw,
                             f"the other side of a disagreement ({value!r}) reached the exported file")

    def test_the_export_module_writes_nothing_to_the_activity_log(self):
        """The module writes no event at all: whether an export is recorded is its callers' decision."""
        self._everything_in_the_database()
        self._everything_in_the_database()
        before = self.log_text()

        self.export()

        self.assertEqual(self.log_text(), before, "the export module wrote a line to the activity log")
        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, self.log_text(), f"{value!r} reached the activity log")


class ReadOnlyTests(ContactExportTestCase):
    """The export changes nothing in the database, measured with the database's own counters."""

    def test_contacts_marks_and_disagreements_are_exactly_as_they_were(self):
        self.import_rows(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,{SAMPLE_REVIEW_REASON}\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n",
            observed_at="2026-10-16T09:00:00+00:00")
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note=SAMPLE_MARK_REASON)
        self.import_rows(f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[0]},3,\r\n",
                         name="later-list.csv")
        records_before = self.store.list_contacts()
        conflicts_before = self.store.list_contact_conflicts()
        counts_before = self.store.contact_record_counts()
        before = self.changes()

        self.export()

        self.assertEqual(self.changes(), before, "an export wrote to the database")
        self.assertEqual(self.store.list_contacts(), records_before,
                         "an export changed a stored contact")
        self.assertEqual(self.store.list_contact_conflicts(), conflicts_before,
                         "an export changed a recorded disagreement")
        self.assertEqual(self.store.contact_record_counts(), counts_before)
        marked = self.store.get_contact(SAMPLE_EMAILS[0])
        self.assertTrue(marked.suppressed)
        self.assertEqual(marked.suppressed_note, SAMPLE_MARK_REASON)
        self.assertIsNotNone(marked.suppressed_at)
        self.assertEqual(self.store._connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION,
                         "an export is not a schema change")

    def test_the_export_is_still_read_only_after_a_restart(self):
        """The database a restart opens is the one the export wrote into: unchanged, and sound."""
        self.two_contacts()
        self.store.set_contact_suppression(SAMPLE_EMAILS[1], note=SAMPLE_MARK_REASON)
        records_before = self.store.list_contacts()

        self.export()
        self.store.close()
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)

        self.assertEqual(self.store.list_contacts(), records_before)
        self.assertEqual(self.store.contact_record_counts()["do_not_contact"], 1)
        self.assertEqual(list(self.store._connection.execute("PRAGMA foreign_key_check").fetchall()), [])


class FileSafetyTests(ContactExportTestCase):
    """The file's own safety: owner-only where the platform has it, never through a link, verified."""

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_the_written_file_is_owner_only_and_tightens_an_existing_one(self):
        self.two_contacts()
        target = self.folder / "existing.csv"
        target.write_text("an older export", encoding="utf-8")
        os.chmod(target, 0o644)

        contact_export.write_export(self.store, target)

        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_a_symbolic_link_destination_is_refused_and_its_target_is_untouched(self):
        self.two_contacts()
        victim = self.folder / "victim.txt"
        victim.write_text("ORIGINAL CONTENT THAT MUST SURVIVE", encoding="utf-8")
        link = self.folder / "link.csv"
        try:
            os.symlink(victim, link)
        except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform capability
            self.skipTest(f"symbolic links are unavailable here: {exc}")

        with self.assertRaises(PrivateWriteError):
            contact_export.write_export(self.store, link)

        self.assertEqual(victim.read_text(encoding="utf-8"), "ORIGINAL CONTENT THAT MUST SURVIVE")
        self.assertNotIn(SAMPLE_EMAILS[0], victim.read_text(encoding="utf-8"))

    def test_a_folder_that_does_not_exist_is_refused_without_claiming_anything(self):
        self.two_contacts()

        with self.assertRaises(PrivateWriteError) as caught:
            contact_export.write_export(self.store, self.folder / "absent" / "export.csv")

        self.assertIn("could not be opened for writing", str(caught.exception))
        self.assertFalse((self.folder / "absent").exists())

    def test_a_file_that_does_not_hold_what_was_written_is_not_reported_as_success(self):
        """The verification step, exercised by writing fewer bytes than the export built."""
        self.two_contacts()
        target = self.folder / "truncated.csv"

        def write_something_shorter(path, data):
            Path(path).write_bytes(data[: len(data) // 2])
            return Path(path)

        with mock.patch.object(contact_export, "write_private_bytes_file",
                               side_effect=write_something_shorter):
            with self.assertRaises(PrivateWriteError) as caught:
                contact_export.write_export(self.store, target)

        self.assertIn("did not hold what was written", str(caught.exception))
        self.assertIn("Nothing was exported", str(caught.exception))
        self.assertFalse(target.exists(), "a file that is not the export must not be left where it would "
                                          "be read as one")

    @unittest.skipUnless(os.name == "posix", "a filesystem refusing the file mode is a POSIX scenario")
    def test_a_file_that_cannot_be_kept_owner_only_is_refused_and_does_not_remain(self):
        self.two_contacts()
        target = self.folder / "unprotected.csv"

        with mock.patch("career_agent.store.os.fchmod", side_effect=OSError("operation not permitted")):
            with self.assertRaises(PrivateWriteError):
                contact_export.write_export(self.store, target)

        if target.exists():
            self.assertNotIn(SAMPLE_EMAILS[0], target.read_text(encoding="utf-8", errors="replace"),
                             "candidate data must not be left in a file this build could not protect")


class BoundedListTests(ContactExportTestCase):
    """A file this application could not read back is not an export, so it is refused before it exists."""

    @staticmethod
    def record(index: int) -> ContactRecord:
        return ContactRecord(
            contact_id=index, email_key=f"contact{index}@example.invalid",
            email=f"contact{index}@example.invalid", name="Sample Person", company="Sample Employer",
            review_flags=(), review_reason=None, source_row=None, source_file="contacts.csv",
            first_seen_at="2026-10-16T09:00:00+00:00", last_seen_at="2026-10-16T09:00:00+00:00",
            seen_count=1, suppressed=False, suppressed_at=None, suppressed_note=None)

    def test_a_list_over_the_readers_own_row_limit_is_refused_before_a_file_is_created(self):
        over_limit = contacts_module.MAX_CONTACT_ROWS + 1
        oversized = mock.Mock()
        oversized.list_contacts.return_value = tuple(self.record(index) for index in range(over_limit))
        target = self.folder / "too-many.csv"

        with self.assertRaises(contact_export.ContactExportRefused) as caught:
            contact_export.write_export(oversized, target)

        message = str(caught.exception)
        self.assertIn(f"{over_limit:,} contacts", message)
        self.assertIn(f"{contacts_module.MAX_CONTACT_ROWS:,} rows", message)
        self.assertIn("nothing was written", message)
        self.assertIn("Data safety", message, "the refusal must name the way to copy the whole database")
        self.assertFalse(target.exists())

    def test_a_file_over_the_readers_own_byte_limit_is_refused_without_a_file(self):
        self.two_contacts()
        target = self.folder / "too-large.csv"

        with mock.patch.object(contacts_module, "MAX_CONTACT_CSV_BYTES", 200):
            with self.assertRaises(contact_export.ContactExportRefused) as caught:
                contact_export.write_export(self.store, target)

        self.assertIn("200 bytes", str(caught.exception))
        self.assertFalse(target.exists())

    def test_an_empty_list_is_not_refused_by_either_limit(self):
        target, outcome = self.export(name="empty.csv")

        self.assertTrue(target.is_file())
        self.assertLess(outcome.bytes_written, contacts_module.MAX_CONTACT_CSV_BYTES)

    def test_a_large_but_bounded_list_is_written_and_reads_back(self):
        """Two thousand contacts: large enough to mean something, small enough to run everywhere."""
        total = 2000
        path = self.folder / "large.csv"
        path.write_bytes((HEADER + "".join(
            f"large{index}@example.invalid,Sample Person {index},Sample Employer,{index},\r\n"
            for index in range(total))).encode("utf-8"))

        self.store.import_contacts(contacts_module.read_contact_csv(path))

        target, outcome = self.export(name="large-export.csv")
        read = contacts_module.read_contact_csv(target)

        self.assertEqual(outcome.contacts, total)
        self.assertEqual(len(read.rows), total)
        self.assertEqual(read.counts()["unique email keys"], total)
        self.assertEqual(len(self.cells(target.read_bytes())), total + 1)
        self.assertLessEqual(outcome.bytes_written, contacts_module.MAX_CONTACT_CSV_BYTES)
        self.assertLessEqual(outcome.contacts, contacts_module.MAX_CONTACT_ROWS)


class ImportReadBackTests(ContactExportTestCase):
    """What importing the export does - including the one thing it deliberately cannot do.

    The export is written to be read by this application's own parser, and it is. What it is *not* is a
    file that can restore the do-not-contact state: the mark is a decision the person makes in the window
    that made it, no import statement mentions the column, and that limitation is asserted here as the
    documented one rather than left to a sentence. The same test proves the file cannot *clear* a mark
    either, which is the direction that would actually endanger somebody.
    """

    def test_the_export_is_read_by_the_parser_this_application_ships(self):
        self.two_contacts()
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note=SAMPLE_MARK_REASON)
        target, _ = self.export()

        read = contacts_module.read_contact_csv(target)

        self.assertEqual([row.key for row in read.rows],
                         [SAMPLE_EMAILS[0].casefold(), SAMPLE_EMAILS[1].casefold()])
        self.assertEqual([row.email for row in read.rows], list(SAMPLE_EMAILS[:2]))
        self.assertEqual([row.name for row in read.rows], list(SAMPLE_NAMES[:2]))
        report = "\n".join(read.describe())
        self.assertIn("File: export.csv", report)
        self.assertIn("read only, unchanged", report)
        # The two columns this format adds are not fields the parser has, and it says so rather than
        # guessing: the preview names both as unused, and reads the address, the name and the company.
        self.assertIn("not used: 2 column(s)", report)
        self.assertIn("'Do Not Contact'", report)
        self.assertIn("'Export Format'", report)
        # Nothing in the parser's own mapping points at either column this format adds: the mark is not a
        # field it has, and it does not quietly read one into a field that means something else.
        self.assertEqual(
            [read.mapping.named(field) for field in
             ("email", "name", "company", "source_row", "review_reason")],
            ["Email", "Name", "Company", None, None])

    def test_an_import_of_the_export_carries_the_list_and_not_the_marks(self):
        """The documented limitation, in one test: the file names the mark and cannot apply it."""
        self.two_contacts()
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note=SAMPLE_MARK_REASON)
        target, _ = self.export()
        rows = self.cells(target.read_bytes())[1:]
        self.assertEqual([row[3] for row in rows], ["yes", "no"], "precondition: the file names the marks")
        # Both directions are asked for: the marked row says yes, and the unmarked row is edited to say
        # yes, so an import that applied the column would mark everything and one that never touched it
        # would mark nothing.
        edited = target.read_bytes().replace(b",no," + FORMAT_CELL, b",yes," + FORMAT_CELL)
        self.assertNotEqual(edited, target.read_bytes(), "precondition: the fixture edit did nothing")
        target.write_bytes(edited)

        second = self.folder / "second-machine.sqlite3"
        with CareerStore(str(second)) as fresh:
            fresh.import_contacts(contacts_module.read_contact_csv(target))
            stored = {record.email_key: record for record in fresh.list_contacts()}

        self.assertEqual(sorted(stored), sorted([email.casefold() for email in SAMPLE_EMAILS[:2]]))
        self.assertEqual([record.suppressed for record in stored.values()], [False, False],
                         "an import applied a do-not-contact column: a file may not write that state")

    def test_an_import_of_the_export_cannot_clear_the_mark_either(self):
        """The direction that would endanger somebody: a file claiming 'no' must not unmark anyone."""
        self.two_contacts()
        self.store.set_contact_suppression(SAMPLE_EMAILS[0], note=SAMPLE_MARK_REASON)
        target, _ = self.export()
        target.write_bytes(target.read_bytes().replace(b",yes," + FORMAT_CELL, b",no," + FORMAT_CELL))

        self.store.import_contacts(contacts_module.read_contact_csv(target))

        marked = self.store.get_contact(SAMPLE_EMAILS[0])
        self.assertTrue(marked.suppressed, "an import cleared a do-not-contact mark")
        self.assertEqual(marked.suppressed_note, SAMPLE_MARK_REASON)
        self.assertEqual(self.store.contact_record_counts()["do_not_contact"], 1)

    def test_re_importing_the_export_into_its_own_database_adds_nothing_and_keeps_the_list(self):
        self.two_contacts()
        before = self.store.contact_record_counts()

        target, _ = self.export()
        outcome = self.store.import_contacts(contacts_module.read_contact_csv(target))

        self.assertEqual((outcome.added, outcome.updated, outcome.conflicts, outcome.skipped_without_key),
                         (0, 2, 0, 0), "a re-import of the export is not a second list")
        self.assertEqual(self.store.contact_record_counts(), before)


if __name__ == "__main__":  # pragma: no cover - convenience for a single-module run
    unittest.main()
