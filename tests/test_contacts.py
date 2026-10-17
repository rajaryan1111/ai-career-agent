"""Tests for the offline HR contact CSV preview: what it reads, refuses, flags and never prints.

Two properties matter more than the rest here, and they are the two the increment was scoped around:

* **Nothing about the file is written anywhere.** The source is opened read-only, no database is touched,
  no copy is made, and a refusal is a sentence rather than a partial import. Several tests below assert the
  file's bytes, its timestamp and its folder are exactly as they were after a read or a refusal.
* **No cell value from the file is printed or logged.** A report a person can paste into a bug report, a
  screenshot or a CI log must not carry an email address, a name or a company label, so the preview reports
  counts, flag names and line numbers instead. The privacy tests assert that directly, against values the
  fixtures are built from rather than against a wording.

Every fixture is synthetic and every address is on a reserved ``.invalid`` domain: no real contact list,
and no row of one, is used by this file. The private CSVs this was built for are deliberately not in this
repository, which is also why the column spellings below are invented examples of the documented contract
rather than the user's own export.
"""
from __future__ import annotations

import contextlib
import io
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_agent import __main__ as cli
from career_agent import contacts

#: The fixture's values, kept in one place so the privacy tests can assert every one of them is absent from
#: a report, a refusal and the log. Synthetic on purpose: an invented person on a reserved domain.
SAMPLE_EMAILS = ("first.contact@example.invalid", "SECOND.Contact@Example.Invalid",
                 "third.contact@example.invalid", "fourth@example.invalid")
SAMPLE_NAMES = ("Example Person One", "Example Person Two")
SAMPLE_COMPANIES = ("Example Employer One", "Example Employer Two")
ALL_SAMPLE_VALUES = SAMPLE_EMAILS + SAMPLE_NAMES + SAMPLE_COMPANIES

HEADER = "Email,Name,Company Label,Source Rows,Review Reason\r\n"


class ContactFileTestCase(unittest.TestCase):
    """A disposable folder, a fixture writer, and a way to run the real command line against it."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)

    def write(self, text: str, name: str = "contacts.csv") -> Path:
        """Write a fixture as UTF-8 bytes, so a test can control a byte-order mark exactly."""
        path = self.folder / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def write_bytes(self, data: bytes, name: str = "contacts.csv") -> Path:
        path = self.folder / name
        path.write_bytes(data)
        return path

    def write_sample(self, rows: str, name: str = "contacts.csv") -> Path:
        """A file with this module's documented header and the rows given, in the file's own order."""
        return self.write(HEADER + rows, name=name)

    def run_cli(self, *arguments: object) -> tuple[int, str, str]:
        """Run the real command with the real parser; return (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([str(argument) for argument in arguments])
        return code, out.getvalue(), err.getvalue()

    def folder_listing(self) -> list[str]:
        return sorted(path.name for path in self.folder.iterdir())


class ReadingTests(ContactFileTestCase):
    """What a readable file gives back: the source text, the key, and the mapping it used."""

    def test_a_utf8_bom_and_windows_line_endings_are_read_as_one_file(self):
        path = self.write_bytes(
            b"\xef\xbb\xbf" + (HEADER + "first.contact@example.invalid,Example Person One,"
                               "Example Employer One,101,\r\n").encode("utf-8")
        )

        read = contacts.read_contact_csv(path)

        self.assertEqual([header for header in read.headers][0], "Email",
                         "the byte-order mark must not become part of the first column's name")
        self.assertEqual(len(read.rows), 1)
        self.assertEqual(read.rows[0].email, "first.contact@example.invalid")

    def test_the_source_text_is_preserved_while_the_comparison_key_is_normalised(self):
        path = self.write_sample(
            "  First.Contact@Example.INVALID  ,Example Person One,Example Employer One,101,\r\n"
        )

        read = contacts.read_contact_csv(path)
        row = read.rows[0]

        self.assertEqual(row.email, "  First.Contact@Example.INVALID  ",
                         "the cell a person would be shown keeps its own spacing and case")
        self.assertEqual(row.key, "first.contact@example.invalid",
                         "the key is the email trimmed and case-folded, and nothing else")

    def test_the_same_file_read_twice_gives_the_same_result(self):
        path = self.write_sample("first.contact@example.invalid,Example Person One,"
                                 "Example Employer One,101,\r\n")

        self.assertEqual(contacts.read_contact_csv(path), contacts.read_contact_csv(path),
                         "reading must be deterministic - nothing here depends on the clock or an "
                         "iteration order that could differ between runs")

    def test_a_file_with_only_a_header_row_reads_as_no_rows(self):
        path = self.write(HEADER)

        read = contacts.read_contact_csv(path)

        self.assertEqual(read.rows, ())
        self.assertEqual(read.counts()["rows read"], 0)
        self.assertEqual(read.counts()["rows to review"], 0)

    def test_the_mapping_it_used_is_reported_for_every_field(self):
        path = self.write_sample("first.contact@example.invalid,Example Person One,"
                                 "Example Employer One,101,\r\n")

        report = "\n".join(contacts.read_contact_csv(path).describe())

        for header in ("Email", "Name", "Company Label"):
            self.assertIn(f"{header!r}", report, "the report must say which column each field came from")
        self.assertIn("proposed from the header row", report,
                      "a detected mapping must say that it was detected, not chosen by the person")

    def test_a_field_the_caller_pins_is_used_for_that_field(self):
        # Two columns could be the email address, which is exactly when a caller has to say which.
        path = self.write("Email,Email Key,Name\r\n"
                          "first.contact@example.invalid,FIRST.CONTACT@example.invalid,"
                          "Example Person One\r\n")

        with self.assertRaises(contacts.ContactSchemaError):
            contacts.read_contact_csv(path)
        read = contacts.read_contact_csv(path, columns={"email": "Email Key"})

        self.assertEqual(read.mapping.email, "Email Key")
        self.assertEqual(read.pinned, ("email",))
        self.assertEqual(read.rows[0].email, "FIRST.CONTACT@example.invalid")
        self.assertIn("pinned by you", "\n".join(read.describe()))

    def test_columns_that_could_not_be_matched_are_reported_as_unchecked(self):
        # Two name columns: neither is used, and the report says so rather than flagging every row.
        path = self.write("Email,Name,Names,Company Label\r\n"
                          "first.contact@example.invalid,Example Person One,One,Example Employer One\r\n")

        read = contacts.read_contact_csv(path)
        report = "\n".join(read.describe())

        self.assertIsNone(read.mapping.name)
        self.assertIn("name: not used, because 2 columns match", report)
        self.assertIn("names: not checked, because no single column was matched", report)
        self.assertNotIn(contacts.Flag.NAME_MISSING, read.rows[0].flags,
                         "a field that was not read cannot be reported as missing")


class RefusalTests(ContactFileTestCase):
    """Every way a file can be unusable, and the sentence a person gets instead of a traceback."""

    def refuse(self, path: Path, **kwargs) -> str:
        with self.assertRaises(contacts.ContactImportError) as caught:
            contacts.read_contact_csv(path, **kwargs)
        return str(caught.exception)

    def test_a_path_with_no_file_is_refused(self):
        message = self.refuse(self.folder / "nothing-here.csv")

        self.assertIn("no file at nothing-here.csv", message)

    def test_a_folder_is_refused(self):
        message = self.refuse(self.folder)

        self.assertIn("is a folder", message)

    def test_an_empty_file_is_refused(self):
        message = self.refuse(self.write_bytes(b""))

        self.assertIn("empty (0 bytes)", message)

    def test_a_file_with_no_header_row_is_refused(self):
        message = self.refuse(self.write("\r\n"))

        self.assertIn("no header row", message)

    def test_a_column_with_no_name_is_refused(self):
        message = self.refuse(self.write("Email,,Name\r\nfirst.contact@example.invalid,x,y\r\n"))

        self.assertIn("no name", message)

    def test_two_columns_differing_only_by_case_are_refused(self):
        message = self.refuse(self.write("Email,email\r\na@example.invalid,b@example.invalid\r\n"))

        self.assertIn("differ only in case or spacing", message)

    def test_a_file_without_an_email_column_is_refused_naming_its_columns(self):
        message = self.refuse(self.write("Who,Company\r\nExample Person One,Example Employer One\r\n"))

        self.assertIn("has no column this preview recognises as the email address", message)
        self.assertIn("'Who', 'Company'", message, "the person needs to see what the file does have")

    def test_two_email_columns_are_refused_rather_than_chosen_between(self):
        message = self.refuse(self.write("Email,Email Key\r\n"
                                         "a@example.invalid,a@example.invalid\r\n"))

        self.assertIn("2 columns that could hold the email address", message)
        self.assertIn("'Email', 'Email Key'", message)

    def test_a_pinned_column_the_file_does_not_have_is_refused(self):
        path = self.write_sample("first.contact@example.invalid,Example Person One,"
                                 "Example Employer One,101,\r\n")

        message = self.refuse(path, columns={"email": "Mail"})

        self.assertIn("has no column named 'Mail'", message)

    def test_pinning_an_unknown_field_is_refused(self):
        path = self.write_sample("first.contact@example.invalid,Example Person One,"
                                 "Example Employer One,101,\r\n")

        message = self.refuse(path, columns={"phone": "Email"})

        self.assertIn("is not a column this preview reads", message)

    def test_a_utf16_file_is_named_as_utf16(self):
        path = self.write_bytes("Email\r\n".encode("utf-16"))

        message = self.refuse(path)

        self.assertIn("looks like UTF-16 text", message)

    def test_a_file_that_is_not_utf8_is_refused_by_byte(self):
        path = self.write_bytes(b"Email,Name\r\nfirst.contact@example.invalid,\xff\xfe bad\r\n")

        message = self.refuse(path)

        self.assertIn("is not UTF-8 text", message)
        self.assertIn("byte", message)

    def test_a_record_with_more_fields_than_the_header_is_refused_by_line(self):
        path = self.write("Email,Name\r\nfirst.contact@example.invalid,Example Person One,extra\r\n")

        message = self.refuse(path)

        self.assertIn("more fields than its header row", message)
        self.assertIn("line 2", message)

    def test_a_cell_beyond_the_parsers_field_limit_is_a_refusal_not_a_crash(self):
        # The standard library's csv module refuses a field past its own limit; that must arrive as this
        # module's sentence rather than as an unexpected failure, because it is a property of the file.
        path = self.write("Email,Name\r\nfirst.contact@example.invalid," + "x" * 200_000 + "\r\n")

        message = self.refuse(path)

        self.assertIn("is not well-formed CSV", message)
        self.assertIn("field larger than field limit", message)

    def test_more_rows_than_the_limit_is_a_refusal_rather_than_a_truncated_report(self):
        path = self.write_sample(
            "first.contact@example.invalid,Example Person One,Example Employer One,101,\r\n"
            "second.contact@example.invalid,Example Person Two,Example Employer Two,102,\r\n"
        )

        with mock.patch.object(contacts, "MAX_CONTACT_ROWS", 1):
            message = self.refuse(path)

        self.assertIn("more than 1 rows", message)
        self.assertIn("Nothing was read past the limit", message)

    def test_a_file_over_the_size_limit_is_refused_before_it_is_read(self):
        path = self.write_sample("first.contact@example.invalid,Example Person One,"
                                 "Example Employer One,101,\r\n")

        with mock.patch.object(contacts, "MAX_CONTACT_CSV_BYTES", 10):
            message = self.refuse(path)

        self.assertIn("larger than the", message)

    def test_every_refusal_says_that_nothing_was_changed(self):
        unusable = {
            "empty": self.write_bytes(b"", name="empty.csv"),
            "no header": self.write("\r\n", name="no-header.csv"),
            "utf-16": self.write_bytes("Email\r\n".encode("utf-16"), name="utf-16.csv"),
            "wrong bytes": self.write_bytes(b"Email\r\n\xff\xfe\r\n", name="bytes.csv"),
            "no email column": self.write("Who,Company\r\nExample Person One,Example Employer One\r\n",
                                          name="who.csv"),
            "extra field": self.write("Email,Name\r\nfirst.contact@example.invalid,"
                                      "Example Person One,x\r\n", name="extra.csv"),
        }

        for label, path in unusable.items():
            with self.subTest(label=label):
                self.assertIn("nothing was", self.refuse(path).casefold(),
                              "a refusal must say for itself that the file was left alone")


class GroupingTests(ContactFileTestCase):
    """What "the same contact" means here, and what happens when a group disagrees with itself."""

    def test_keys_differing_only_by_case_and_surrounding_spaces_are_one_group(self):
        path = self.write_sample(
            "first.contact@example.invalid,Example Person One,Example Employer One,101,\r\n"
            "  FIRST.Contact@Example.Invalid  ,Example Person Two,Example Employer One,102,\r\n"
        )

        read = contacts.read_contact_csv(path)

        self.assertEqual(len(read.groups), 1)
        self.assertEqual(len(read.groups[0].rows), 2)
        self.assertEqual(read.counts()["keys shared by more than one row"], 1)
        self.assertEqual(read.counts()["rows sharing a key"], 2)

    def test_every_row_of_a_shared_key_is_flagged(self):
        path = self.write_sample(
            "first.contact@example.invalid,Example Person One,Example Employer One,101,\r\n"
            "first.contact@example.invalid,Example Person Two,Example Employer One,102,\r\n"
        )

        read = contacts.read_contact_csv(path)

        for row in read.rows:
            self.assertIn(contacts.Flag.DUPLICATE_KEY, row.flags,
                          "a shared email key is the whole reason the row needs a person")

    def test_company_labels_that_disagree_are_kept_in_the_file_s_order_and_flagged(self):
        path = self.write_sample(
            "first.contact@example.invalid,Example Person One,Example Employer Two,101,\r\n"
            "first.contact@example.invalid,Example Person One,Example Employer One,102,\r\n"
        )

        read = contacts.read_contact_csv(path)

        self.assertEqual(read.groups[0].companies, ("Example Employer Two", "Example Employer One"),
                         "both labels survive, in the order the file lists them, and neither is chosen")
        self.assertTrue(read.groups[0].conflicts)
        for row in read.rows:
            self.assertIn(contacts.Flag.COMPANY_CONFLICT, row.flags)
        self.assertNotIn(";", read.groups[0].companies[0],
                         "a label is never rewritten into a combination of the two")

    def test_a_group_that_agrees_about_the_company_is_not_flagged(self):
        path = self.write_sample(
            "first.contact@example.invalid,Example Person One,Example Employer One,101,\r\n"
            "First.Contact@Example.invalid,Example Person Two,Example Employer One,102,\r\n"
        )

        read = contacts.read_contact_csv(path)

        for row in read.rows:
            self.assertNotIn(contacts.Flag.COMPANY_CONFLICT, row.flags)

    def test_a_row_with_no_email_is_not_grouped_with_anything(self):
        path = self.write_sample(
            ",Example Person One,Example Employer One,101,\r\n"
            "first.contact@example.invalid,Example Person Two,Example Employer One,102,\r\n"
        )

        read = contacts.read_contact_csv(path)

        self.assertEqual(len(read.groups), 1)
        self.assertEqual([row.line for row in read.rows_without_key], [2])
        self.assertIsNone(read.rows[0].key)
        self.assertIn(contacts.Flag.EMAIL_MISSING, read.rows[0].flags)

    def test_the_source_values_are_never_rewritten(self):
        path = self.write_sample(
            "First.Contact@Example.INVALID ,Example Person One,Example Employer One,101,duplicate\r\n"
        )

        row = contacts.read_contact_csv(path).rows[0]

        self.assertEqual(row.email, "First.Contact@Example.INVALID ")
        self.assertEqual(row.name, "Example Person One")
        self.assertEqual(row.company, "Example Employer One")
        self.assertEqual(row.source_row, "101")
        self.assertEqual(row.recorded_reasons, "duplicate")

    def test_two_files_are_read_independently(self):
        first = self.write_sample("first.contact@example.invalid,Example Person One,"
                                  "Example Employer One,101,\r\n", name="one.csv")
        second = self.write_sample("second.contact@example.invalid,Example Person Two,"
                                   "Example Employer Two,102,\r\n", name="two.csv")

        reads = contacts.read_contact_csvs([first, second])

        self.assertEqual([read.file_name for read in reads], ["one.csv", "two.csv"])
        self.assertEqual([len(read.groups) for read in reads], [1, 1],
                         "each file is reported on its own; nothing here merges them")


class FlagTests(ContactFileTestCase):
    """Each flag, and the fact that it is a question about text rather than a verdict on a person."""

    def test_an_empty_email_is_flagged_as_missing_and_not_as_a_syntax_problem(self):
        path = self.write_sample(",Example Person One,Example Employer One,101,\r\n")

        row = contacts.read_contact_csv(path).rows[0]

        self.assertEqual(row.flags, (contacts.Flag.EMAIL_MISSING,),
                         "an empty cell is missing, not malformed - the two ask different questions")

    def test_a_missing_name_is_flagged_when_a_name_column_was_matched(self):
        path = self.write_sample("first.contact@example.invalid,,Example Employer One,101,\r\n")

        row = contacts.read_contact_csv(path).rows[0]

        self.assertIn(contacts.Flag.NAME_MISSING, row.flags)

    def test_addresses_that_do_not_look_like_addresses_are_flagged(self):
        # A leading hyphen in the local part is *not* here: it is legal in an address, and flagging it
        # would be this module pretending to know a rule that does not exist.
        suspicious = (
            "not-an-address", "two@@example.invalid", "a@example.invalid,b@example.invalid",
            "space in@example.invalid", "trailing@example.invalid.", "@example.invalid",
            "leading@", "no.domain@localhost", "no-tld@example.1", "double..dot@example.invalid",
            "user@-example.invalid", "user@example-.invalid",
        )

        for address in suspicious:
            with self.subTest(address=address):
                # Quoted, so a value that holds a comma reaches the cell as one value instead of
                # splitting into extra fields - that is the file's problem, not this check's.
                path = self.write_sample(f'"{address}",Example Person One,Example Employer One,101,\r\n')
                row = contacts.read_contact_csv(path).rows[0]
                self.assertIn(contacts.Flag.EMAIL_SYNTAX, row.flags)
                self.assertEqual(row.email, address, "the value is flagged, never changed")

    def test_addresses_that_look_like_addresses_are_not_flagged(self):
        reasonable = (
            "first.contact@example.invalid", "first+applications@example.invalid",
            "first_contact@example.invalid", "first-contact@sub.example.invalid",
            "FIRST.CONTACT@EXAMPLE.INVALID", "first@sub.example.invalid", "a1@ex-ample.invalid",
        )

        for address in reasonable:
            with self.subTest(address=address):
                path = self.write_sample(f"{address},Example Person One,Example Employer One,101,\r\n")
                row = contacts.read_contact_csv(path).rows[0]
                self.assertNotIn(contacts.Flag.EMAIL_SYNTAX, row.flags)

    def test_a_review_note_already_in_the_file_makes_a_row_worth_reviewing(self):
        # Nothing is wrong with this row; the person who compiled the file said to look at it.
        path = self.write_sample("first.contact@example.invalid,Example Person One,"
                                 "Example Employer One,101,check with the person who sent this list\r\n")

        read = contacts.read_contact_csv(path)

        self.assertEqual(read.rows[0].flags, ())
        self.assertTrue(read.needs_review(read.rows[0]))
        self.assertEqual(read.counts()["rows with a review note already in the file"], 1)
        self.assertEqual(read.counts()["rows to review"], 1)

    def test_the_counts_account_for_every_row(self):
        path = self.write_sample(
            "first.contact@example.invalid,Example Person One,Example Employer One,101,\r\n"
            "first.contact@example.invalid,,Example Employer Two,102,\r\n"
            "second.contact@example.invalid,Example Person Two,Example Employer One,103,look at this\r\n"
            ",Example Person Two,,\r\n"
            "not-an-address,,Example Employer One,105,\r\n"
        )

        read = contacts.read_contact_csv(path)
        counts = read.counts()

        self.assertEqual(counts["rows read"], len(read.rows))
        self.assertEqual(counts["rows with an email key"] + len(read.rows_without_key),
                         counts["rows read"])
        self.assertEqual(counts["unique email keys"], len(read.groups))
        self.assertEqual(counts["rows sharing a key"],
                         sum(len(group.rows) for group in read.groups if len(group.rows) > 1))
        self.assertEqual(counts["rows to review"], len(read.rows_to_review()))
        self.assertEqual(sum(1 for row in read.rows if not row.flags and not row.recorded_reasons.strip()),
                         counts["rows read"] - counts["rows to review"])

    def test_the_counts_are_numbers_and_never_values(self):
        path = self.write_sample("first.contact@example.invalid,Example Person One,"
                                 "Example Employer One,101,\r\n")

        counts = contacts.read_contact_csv(path).counts()

        for name, value in counts.items():
            self.assertIsInstance(value, int, f"{name} must be a count")
            self.assertIsInstance(name, str)


class PrivacyTests(ContactFileTestCase):
    """The promise the increment is judged on: the file is read, and nothing about it leaves the process."""

    def sample(self) -> Path:
        return self.write_sample(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},101,\r\n"
            f"{SAMPLE_EMAILS[1]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},102,duplicate\r\n"
            f"not-an-address,,{SAMPLE_COMPANIES[0]},103,\r\n"
        )

    def test_the_report_contains_no_contact_value(self):
        report = "\n".join(contacts.read_contact_csv(self.sample()).describe())

        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, report, f"the report printed {value!r}")
            self.assertNotIn(value.casefold(), report.casefold(),
                             f"the report printed a differently-cased {value!r}")

    def test_a_refusal_contains_no_contact_value(self):
        # A record with one field too many is refused, and the refusal names the line, not the row.
        path = self.write(HEADER + f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},101,,"
                                   f"extra\r\n")

        with self.assertRaises(contacts.ContactImportError) as caught:
            contacts.read_contact_csv(path)

        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, str(caught.exception))

    def test_nothing_is_logged_while_a_file_is_read(self):
        records: list[logging.LogRecord] = []

        class Recorder(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = Recorder()
        root = logging.getLogger()
        root.addHandler(handler)
        self.addCleanup(root.removeHandler, handler)

        read = contacts.read_contact_csv(self.sample())
        report = "\n".join(read.describe())

        self.assertEqual(records, [], "reading a contact file must not write a log record at all")
        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, report)

    def test_the_file_is_not_modified_and_nothing_is_written_beside_it(self):
        path = self.sample()
        before_bytes = path.read_bytes()
        before_stat = path.stat()
        listing_before = self.folder_listing()

        read = contacts.read_contact_csv(path)
        report = "\n".join(read.describe())

        self.assertEqual(path.read_bytes(), before_bytes, "the source file's bytes changed")
        self.assertEqual(path.stat().st_mtime_ns, before_stat.st_mtime_ns, "the source file was touched")
        self.assertEqual(os.stat(path).st_size, before_stat.st_size)
        self.assertEqual(self.folder_listing(), listing_before,
                         "a read must not leave a database, a snapshot, a cache or a temporary file")
        self.assertIn("Nothing was written", report)

    def test_the_report_says_what_it_checked_and_what_it_cannot(self):
        report = "\n".join(contacts.read_contact_csv(self.sample()).describe())

        self.assertIn("heuristic", report)
        for not_claimable in ("whether a mailbox exists or is reachable",
                              "whether anybody agreed to be contacted"):
            self.assertIn(not_claimable, report,
                          "the report must not let a syntax check read as a permission to contact")


class CommandLineTests(ContactFileTestCase):
    """The command a person runs: what it prints, what it refuses, and what it never opens."""

    def sample(self) -> Path:
        return self.write_sample(
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[0]},{SAMPLE_COMPANIES[0]},101,\r\n"
            f"{SAMPLE_EMAILS[0]},{SAMPLE_NAMES[1]},{SAMPLE_COMPANIES[1]},102,duplicate\r\n"
            f"not-an-address,,{SAMPLE_COMPANIES[0]},103,\r\n"
        )

    def test_the_command_reports_counts_and_writes_nothing(self):
        path = self.sample()
        before = path.read_bytes()

        code, out, err = self.run_cli("--preview-contact-csv", path)

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertEqual(err, "", "a successful preview has nothing to complain about")
        self.assertIn("HR contact CSV preview", out)
        self.assertIn("unique email keys: 2", out)
        self.assertIn("rows flagged duplicate-key: 2", out)
        self.assertIn("rows flagged company-conflict: 2", out)
        self.assertIn("first lines to review:", out)
        self.assertIn("did not import, store, match, draft, send or submit anything", out)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.folder_listing(), ["contacts.csv"],
                         "the command must not create a database or any other file beside the source")
        for value in ALL_SAMPLE_VALUES:
            self.assertNotIn(value, out, f"the command printed {value!r}")
            self.assertNotIn(value.casefold(), out.casefold())

    def test_the_command_refuses_a_file_it_cannot_read_with_an_empty_report_stream(self):
        path = self.write_bytes(b"Email,Name\r\n\xff\xfe\r\n")

        code, out, err = self.run_cli("--preview-contact-csv", path)

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertEqual(out, "", "a command that refused has no report to begin")
        self.assertIn("REFUSED", err)
        self.assertIn("is not UTF-8 text", err)

    def test_the_command_opens_no_database(self):
        # The pointed-at database is a text file named like one, which every database command refuses.
        broken = self.write_bytes(b"SQLite format 3\x00not a database", name="broken.sqlite3")
        path = self.sample()

        code, out, err = self.run_cli("--database", broken, "--preview-contact-csv", path)

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("opened no database", out)
        self.assertEqual(broken.read_bytes(), b"SQLite format 3\x00not a database")

    def test_the_command_reads_the_column_the_person_names(self):
        path = self.write("Email,Email Key,Name\r\n"
                          "first.contact@example.invalid,FIRST.CONTACT@example.invalid,"
                          "Example Person One\r\n")

        code, out, err = self.run_cli("--preview-contact-csv", path, "--contact-email-column",
                                      "Email Key")

        self.assertEqual(code, cli.EXIT_OK, err)
        self.assertIn("'Email Key'", out)
        self.assertIn("pinned by you", out)

    def test_a_column_option_without_the_command_is_refused(self):
        code, out, err = self.run_cli("--contact-email-column", "Email")

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertEqual(out, "")
        self.assertIn("--contact-email-column only means something with --preview-contact-csv", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
