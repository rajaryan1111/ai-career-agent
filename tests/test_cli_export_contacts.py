"""Tests for ``--export-contacts-to``: the command a person can run without a window.

What is tested here is the command-line contract rather than the format underneath it (that has its own
tests): that the file is written where it was asked for and says what it holds, that an existing path is
refused rather than replaced - there is no dialog here to confirm an overwrite with - that a refused list
leaves no file and no half-list behind, that the exit status never says "fine" when something was refused,
and that the database is only ever read. The suppression sentence is asserted too: it is the one claim a
person has to read before they rely on the file, and the command must not out-say the format.
"""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

import career_agent.__main__ as cli
from career_agent import contact_export, contacts as contacts_module
from career_agent.store import SCHEMA_VERSION, CareerStore

#: Synthetic people on a reserved domain, and the fixture the CLI is pointed at.
SAMPLE_EMAILS = ("first.contact@example.invalid", "second.contact@example.invalid")
SAMPLE_NAMES = ("Sample Person One", "Sample Person Two")
SAMPLE_COMPANIES = ("Sample Employer One", "Sample Employer Two")
SAMPLE_MARK_REASON = "synthetic note typed beside the mark"
ALL_SAMPLE_VALUES = SAMPLE_EMAILS + SAMPLE_NAMES + SAMPLE_COMPANIES

HEADER = "Email,Name,Company Label,Source Rows,Review Reason\r\n"


class ExportContactsCommandTests(unittest.TestCase):
    """A disposable database with two synthetic contacts in it, and a folder to write into."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.export = self.folder / "contacts-export.csv"

    def populate(self, *, mark_first: bool = False) -> None:
        """Two stored contacts, read through the real parser, in a database of their own."""
        source = self.folder / "source.csv"
        source.write_bytes((HEADER + (
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},1,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},2,\r\n"
        )).encode("utf-8"))
        with CareerStore(self.database) as store:
            store.import_contacts(contacts_module.read_contact_csv(source))
            if mark_first:
                store.set_contact_suppression(SAMPLE_EMAILS[0], note=SAMPLE_MARK_REASON)

    def run_cli(self, *arguments: object) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([str(argument) for argument in arguments])
        return code, out.getvalue(), err.getvalue()

    def run_export(self, *extra: object) -> tuple[int, str, str]:
        return self.run_cli("--export-contacts-to", self.export, "--database", self.database, *extra)

    def log_text(self) -> str:
        from career_agent.event_log import log_path  # imported here: this file is otherwise store-free
        return log_path(self.database).read_text(encoding="utf-8")

    def test_the_command_writes_the_documented_file_and_says_what_it_holds(self):
        self.populate(mark_first=True)
        before = self.log_text()

        code, out, err = self.run_export()

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertEqual(err, "", "a successful export has nothing to complain about")
        self.assertIn("export the stored HR contact list", out)
        self.assertIn("Wrote 2 contact(s)", out)
        self.assertIn(contact_export.CONTACT_EXPORT_FORMAT, out)
        self.assertIn("1 of them marked do not contact", out)
        self.assertIn("read back and compared", out)
        # The file is written where it was asked for, and it is the format's file.
        self.assertTrue(self.export.is_file())
        self.assertTrue(self.export.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(self.export.read_bytes()[len(b"\xef\xbb\xbf"):].split(b"\r\n")[0],
                         b"Email,Name,Company,Do Not Contact,Export Format")
        read = contacts_module.read_contact_csv(self.export)
        self.assertEqual([row.name for row in read.rows], list(SAMPLE_NAMES))
        # Read-only, and nothing recorded about the export itself: opening the database is the store's
        # own line, and this command adds no event of its own - the window is where an export is recorded.
        self.assertNotIn("contacts.exported", self.log_text())
        self.assertNotIn("contacts.export.failed", self.log_text())
        self.assertNotIn("export.written", self.log_text())
        self.assertIn("event=database.opened", self.log_text(),
                      "precondition: the store's own open line is what the log holds after this command")
        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, self.log_text(), f"{value!r} reached the activity log")
        with CareerStore(self.database) as store:
            self.assertEqual(store.contact_record_counts()["contacts"], 2)
            self.assertEqual(store.get_contact(SAMPLE_EMAILS[0]).suppressed_note, SAMPLE_MARK_REASON)

    def test_the_command_says_the_mark_does_not_travel_with_the_file(self):
        """The one claim that must not be missing: the column is readable, and an import cannot apply it."""
        self.populate(mark_first=True)

        code, out, err = self.run_export()

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn(contact_export.MARK_COLUMN_LIMITATION, out)
        # The command shares the format's sentence, and the sentence has to carry the claim itself.
        self.assertIn('"Do Not Contact"', out)
        self.assertIn("cannot set or clear", out,
                      "the command's report never says an import cannot apply the mark")
        self.assertIn("read the column", out,
                      "the command's report never says what to do with the mark column instead")
        self.assertIn("rather than a backup", out,
                      "the command must say what the file is not, not only what it is")
        self.assertIn("Data safety", out,
                      "the command must say where the thing that does copy everything lives")
        self.assertIn("Nothing was sent anywhere", out)
        self.assertIn("database was not changed", out)

    def test_the_command_refuses_to_replace_an_existing_file(self):
        self.populate()
        self.export.write_text("a person's own file", encoding="utf-8")

        code, out, err = self.run_export()

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertEqual(out, "", "a command that refused has no report to begin")
        self.assertIn("already exists", err)
        self.assertEqual(self.export.read_text(encoding="utf-8"), "a person's own file",
                         "the refused export replaced the file it refused to replace")

    def test_no_database_no_list_and_nothing_created(self):
        missing = self.folder / "not-there.sqlite3"

        code, out, err = self.run_export()

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("No database yet", out)
        self.assertFalse(self.export.exists())
        self.assertFalse(self.folder.joinpath("absent").exists())
        self.assertNotIn("Wrote", out)

    def test_a_database_file_with_nothing_in_it_is_refused_rather_than_created(self):
        empty = self.folder / "empty.sqlite3"
        empty.write_bytes(b"")

        code, out, err = self.run_cli("--export-contacts-to", self.export, "--database", empty)

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("empty (0 bytes)", out)
        self.assertEqual(empty.read_bytes(), b"", "the command created a database instead of refusing")
        self.assertFalse(self.export.exists())

    def test_a_broken_database_is_refused_without_a_traceback(self):
        broken = self.folder / "broken.sqlite3"
        broken.write_bytes(b"SQLite format 3\x00not a database")

        code, out, err = self.run_cli("--export-contacts-to", self.export, "--database", broken)

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("REFUSED", err)
        self.assertIn("could not be read", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(broken.read_bytes(), b"SQLite format 3\x00not a database")
        self.assertFalse(self.export.exists(), "a refused export must not leave a file behind")

    def test_a_list_over_the_formats_limit_is_refused_and_writes_nothing(self):
        """The real refusal path, with the format's own reader limit lowered for the run."""
        self.populate()
        from career_agent import contacts as contacts_module_again  # noqa: PLC0415 - the same module

        original = contacts_module_again.MAX_CONTACT_CSV_BYTES
        try:
            contacts_module_again.MAX_CONTACT_CSV_BYTES = 100
            code, out, err = self.run_export()
        finally:
            contacts_module_again.MAX_CONTACT_CSV_BYTES = original

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertEqual(out, "", "a refusal must not print a report about a file that was not written")
        self.assertIn("REFUSED", err)
        self.assertIn("100 bytes", err)
        self.assertIn("Data safety", err)
        self.assertFalse(self.export.exists())

    def test_the_command_never_reports_success_for_a_folder_that_does_not_exist(self):
        self.populate()
        self.export = self.folder / "absent" / "contacts-export.csv"

        code, out, err = self.run_export()

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertEqual(out, "", "nothing was written, so there is no report to print")
        self.assertIn("could not be opened for writing", err)
        self.assertFalse((self.folder / "absent").exists())

    def test_the_report_carries_no_contact_value_and_no_mark_reason(self):
        self.populate(mark_first=True)

        code, out, err = self.run_export()

        self.assertEqual(code, cli.EXIT_OK, err)
        for value in ALL_SAMPLE_VALUES + (SAMPLE_MARK_REASON,):
            self.assertNotIn(value, out, f"the command printed {value!r}")
            self.assertNotIn(value, err, f"the command printed {value!r}")
            self.assertNotIn(value, self.log_text(), f"{value!r} reached the activity log")
        # The counts are what a shareable report is allowed to say, and the file's own name is the
        # person's choice of path in their own terminal - which is the one place it may appear.
        self.assertIn("2 contact(s)", out)
        self.assertNotIn("Wrote 2 contact(s) to", self.log_text())

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_the_written_file_is_owner_only(self):
        self.populate()

        self.run_export()

        self.assertEqual(self.export.stat().st_mode & 0o777, 0o600)

    def test_the_export_leaves_the_database_at_the_schema_it_opened(self):
        self.populate()

        self.run_export()

        with CareerStore(self.database) as store:
            self.assertEqual(store._connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)


if __name__ == "__main__":  # pragma: no cover - convenience for a single-module run
    unittest.main()
