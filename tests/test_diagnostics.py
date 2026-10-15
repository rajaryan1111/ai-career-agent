"""Tests for version reporting and non-sensitive start-up diagnostics.

These run without any GUI toolkit: the version flag, the failure explanations, and the bounded local
note are all Tk-free on purpose, because the situation that needs them most is the one in which the
window cannot be opened. No candidate data is used anywhere in this module.
"""
import io
import os
import sqlite3
import stat
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from career_agent import __version__
from career_agent import __main__ as cli
from career_agent.diagnostics import (
    DIAGNOSTIC_FILE_NAME, MAX_DIAGNOSTIC_LENGTH, describe_startup_failure, diagnostic_log_path,
    record_startup_failure, redact_paths,
)
from career_agent.store import (
    SCHEMA_VERSION, CareerStore, PrivateWriteError, SchemaMigrationError, SchemaTooNewError,
    TrackerStatusError, UnrecognisedDatabaseError,
)


class VersionReportingTests(unittest.TestCase):
    """A source checkout must be able to say which version it is, with no packaging metadata."""

    def run_cli(self, arguments):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(arguments)
        return code, out.getvalue(), err.getvalue()

    def test_the_package_reports_a_version(self):
        self.assertIsInstance(__version__, str)
        self.assertTrue(__version__.strip())
        self.assertRegex(__version__, r"^\d+\.\d+")

    def test_the_version_flag_prints_the_version_and_exits_cleanly(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as caught:
                cli.parse_arguments(["--version"])

        self.assertEqual(caught.exception.code, 0)
        self.assertIn(__version__, out.getvalue())
        self.assertIn(str(SCHEMA_VERSION), out.getvalue(), "the schema version is part of the report")
        self.assertEqual(err.getvalue(), "")

    def test_the_help_still_lists_the_documented_actions(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as caught:
                cli.parse_arguments(["--help"])

        self.assertEqual(caught.exception.code, 0)
        text = out.getvalue()
        for flag in ("--version", "--backup-to", "--restore-from", "--database", "--yes"):
            self.assertIn(flag, text)

    def test_the_version_path_imports_no_gui_toolkit(self):
        """``--version`` must work where Tkinter is missing, as it is on many servers and CI images."""
        package_root = str(Path(__file__).resolve().parents[1])
        script = (
            "import contextlib, io, runpy, sys\n"
            "sys.modules['tkinter'] = None  # any attempt to import it now fails\n"
            "sys.argv = ['career_agent', '--version']\n"
            "buffer = io.StringIO()\n"
            "try:\n"
            "    with contextlib.redirect_stdout(buffer):\n"
            "        runpy.run_module('career_agent', run_name='__main__')\n"
            "except SystemExit as exit_code:\n"
            "    assert exit_code.code == 0, exit_code.code\n"
            "print('VERSION:', buffer.getvalue().strip())\n"
        )
        import subprocess

        result = subprocess.run(
            [sys.executable, "-c", script], cwd=package_root, capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VERSION:", result.stdout)
        self.assertIn(__version__, result.stdout)


class PathRedactionTests(unittest.TestCase):
    """Diagnostics must not carry filesystem locations, candidate data, or credentials."""

    def test_the_database_location_is_replaced_without_leaking_its_folder(self):
        database = Path("/home/someone/Library/Application Support/AI Career Agent/career_agent.sqlite3")
        text = f"unable to open database file: {database} (folder {database.parent})"

        redacted = redact_paths(text, database_path=database, home=Path("/home/someone"))

        self.assertNotIn("/home/someone", redacted)
        self.assertIn("<application data folder>", redacted)
        # The default database file name is a product name, not a location, so it stays readable.
        self.assertIn("career_agent.sqlite3", redacted)

    def test_the_home_folder_is_replaced_on_its_own(self):
        home = Path("/home/someone")

        redacted = redact_paths(f"could not write {home}/Documents/export.json", home=home)

        self.assertNotIn("/home/someone", redacted)
        self.assertIn("<home folder>", redacted)

    def test_a_user_chosen_file_name_is_replaced_too(self):
        database = Path("/tmp/throwaway/my-test-copy.sqlite3")

        redacted = redact_paths(str(database), database_path=database, home=Path("/home/someone"))

        self.assertNotIn("my-test-copy", redacted)
        self.assertIn("<database file>", redacted)

    def test_replacing_a_longer_path_first_leaves_no_fragment_of_it(self):
        # The home folder is a prefix of the database folder, so a naive replacement order would
        # leave "<home folder>/data/..." behind: a real location, partly hidden, is still a leak.
        database = Path("/srv/data/career_agent.sqlite3")

        redacted = redact_paths(f"cannot open {database}", database_path=database, home=Path("/srv"))

        self.assertNotIn("/srv", redacted)
        self.assertIn("<application data folder>", redacted)

    def test_text_without_paths_is_left_alone(self):
        self.assertEqual(redact_paths("file is not a database", home=Path("/home/someone")),
                         "file is not a database")

    def test_a_relative_database_file_does_not_replace_every_dot_in_the_message(self):
        # ``Path("db.sqlite3").parent`` is the current folder, and its text is the single character
        # ".": replacing that hid every dot in the explanation and left it unreadable, so a failure
        # reported with the ordinary ``--database db.sqlite3`` form could not be understood at all.
        redacted = redact_paths(
            "CareerStore: cannot open db.sqlite3. Schema version 2.0",
            database_path="db.sqlite3", home=Path("/home/someone"),
        )

        self.assertIn("Schema version 2.0", redacted)
        self.assertNotIn("db.sqlite3", redacted)
        self.assertIn("<database file>", redacted)

    def test_a_relative_folder_name_is_not_replaced_inside_ordinary_words(self):
        # A folder called "data" must be hidden where it is a path, and left alone where it is prose.
        # The sample text is built with the platform's own separator: what is compared is a rendered path,
        # and the module renders it the way the platform does - a forward slash is not a path separator on
        # Windows, where this test failed for that reason alone.
        relative_database = str(Path("data") / "db.sqlite3")
        untouched = "the data folder could not be used; data was not written"
        self.assertEqual(redact_paths(untouched, database_path=relative_database, home=Path("/home/someone")),
                         untouched)
        self.assertEqual(redact_paths(f"cannot open {relative_database}", database_path=relative_database,
                                      home=Path("/home/someone")),
                         "cannot open <database file>")

    def test_a_path_the_caller_names_is_redacted_when_it_is_supplied(self):
        # The command line can name a backup or a restore file; that location is the person's own, so
        # it must not survive into a note written to be safe to share.
        named = "/Volumes/Backup Drive/private/notes.sqlite3"

        redacted = redact_paths(f"cannot read {named}", home=Path("/home/someone"), extra_paths=[named])

        self.assertNotIn("Volumes", redacted)
        self.assertNotIn("notes.sqlite3", redacted)
        self.assertIn("<local path>", redacted)

    def test_an_unsupplied_absolute_path_is_hidden_rather_than_copied_into_a_note(self):
        # A caller cannot list every location an unexpected failure message might quote: an external
        # volume, a sync folder, another drive. The note this text ends up in is written to be safe to
        # share, so an absolute location is hidden wherever it appears, not only when the caller named
        # it. This supersedes an earlier, weaker rule that left unsupplied paths alone.
        cases = {
            "bare": ("cannot read /Volumes/Investor Backup/private/notes.sqlite3", "/Volumes"),
            "quoted with spaces": (
                "FileNotFoundError: [Errno 2] No such file or directory: "
                "'/Volumes/Investor Backup/private/notes.sqlite3'",
                "/Volumes",
            ),
            "windows drive": ('could not write "C:\\Users\\ada\\Documents\\export.json"', "C:\\Users"),
            "unc share": ("cannot open \\\\fileserver\\share\\notes\\x.sqlite3", "\\\\fileserver"),
            "system location": ("see /usr/lib/python3.11/zipfile.py for details", "/usr/lib"),
        }
        for label, (text, hidden) in cases.items():
            with self.subTest(shape=label):
                redacted = redact_paths(text, home=Path("/home/someone"))

                self.assertIn("<local path>", redacted)
                self.assertNotIn(hidden, redacted)
                self.assertNotIn("Investor", redacted)
                self.assertNotIn("notes.sqlite3", redacted)

    def test_redacting_a_location_keeps_the_sentence_around_it_readable(self):
        text = "cannot open /Volumes/Investor Backup/private/notes.sqlite3 on this machine."

        self.assertEqual(redact_paths(text, home=Path("/home/someone")),
                         "cannot open <local path> on this machine.")

    def test_a_relative_word_or_a_public_url_is_never_mistaken_for_a_location(self):
        # The narrow rule that makes the sweep safe: a location starts with a separator (an absolute
        # POSIX path, a drive letter, or a UNC prefix). Ordinary words, version numbers, relative file
        # names, and public addresses are not locations and must survive untouched, because rewriting
        # them would corrupt a diagnostic message this module cannot verify.
        text = (
            "version 2.0 of the schema is fine; data/resume.docx was not read and "
            "https://example.invalid/jobs/1?q=a/b still answers"
        )

        self.assertEqual(redact_paths(text, home=Path("/home/someone")), text)

class StartupFailureExplanationTests(unittest.TestCase):
    """The message shown when the window cannot open must be useful and must not leak."""

    database = Path("/home/someone/Library/Application Support/AI Career Agent/career_agent.sqlite3")

    def explain(self, exc):
        return describe_startup_failure(exc, database_path=self.database)

    def test_an_unreadable_database_is_explained_with_a_next_step(self):
        text = self.explain(sqlite3.DatabaseError("file is not a database"))

        self.assertIn("could not be read", text)
        self.assertIn("--restore-from", text, "the recovery command must be named")
        self.assertIn("was not modified", text)
        self.assertNotIn("/home/someone", text)

    def test_a_damaged_database_keeps_sqlites_own_words_without_the_path(self):
        text = self.explain(sqlite3.DatabaseError(f"database disk image is malformed in {self.database}"))

        self.assertIn("malformed", text)
        self.assertNotIn("/home/someone", text)
        self.assertIn("<application data folder>", text)

    def test_a_missing_folder_is_explained_as_a_missing_folder_not_a_damaged_database(self):
        """Reproduced before this test existed, from the macOS report and repeated here.

        Starting the app with a database path inside a folder that does not exist made SQLite report
        "unable to open database file", and the app answered "the local database could not be read ...
        it may be damaged" and advised renaming or restoring a file that was never there. Nothing was
        damaged and neither suggestion could work: the folder itself was missing.
        """
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "not-created-yet" / "career_agent.sqlite3"
            try:
                CareerStore(missing)
            except sqlite3.Error as exc:
                real_error = exc
            else:  # pragma: no cover - the precondition is that this open fails
                self.fail("the store must fail to open a database in a folder that does not exist")
            # Classified while the folder is still absent: the answer depends on the filesystem, so the
            # temporary directory must not be cleaned up first.
            message = describe_startup_failure(real_error, database_path=missing)

        self.assertIn("folder", message)
        self.assertIn("does not exist", message)
        self.assertIn("--database", message, "the message must name a next step that can work")
        self.assertNotIn("damaged", message, "nothing is damaged in this case")
        self.assertNotIn("--restore-from", message, "restoring would fail for the same reason")
        self.assertNotIn(str(missing), message, "the location must not be disclosed")
        self.assertNotIn("unable to open database file", message, "SQLite's own words are not helpful here")

    def test_a_path_that_is_a_folder_is_explained_as_a_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "this-is-a-folder"
            folder.mkdir()
            try:
                CareerStore(folder)
            except sqlite3.Error as exc:
                real_error = exc
            else:  # pragma: no cover - the precondition is that this open fails
                self.fail("the store must fail to open a folder as a database")
            message = describe_startup_failure(real_error, database_path=folder)

        self.assertIn("itself a folder", message)
        self.assertIn("--database", message)
        self.assertNotIn(str(folder), message)

    def test_a_database_file_that_is_present_but_unreadable_keeps_the_existing_message(self):
        """The new branch must not swallow the case it was not written for."""
        with tempfile.TemporaryDirectory() as directory:
            corrupt = Path(directory) / "corrupt.sqlite3"
            corrupt.write_text("this is not a database", encoding="utf-8")
            try:
                CareerStore(corrupt)
            except sqlite3.Error as exc:
                real_error = exc
            else:  # pragma: no cover - the precondition is that this open fails
                self.fail("the store must fail to open a file that is not a database")
            message = describe_startup_failure(real_error, database_path=corrupt)

        self.assertIn("could not be read", message)
        self.assertIn("--restore-from", message)
        self.assertIn("not a database", message, "SQLite's own words are still shown for this case")

    def test_an_open_failure_with_no_path_available_does_not_guess(self):
        message = describe_startup_failure(
            sqlite3.OperationalError("unable to open database file"), database_path=None
        )

        self.assertIn("could not be read", message, "without a path the honest answer is the general one")
        self.assertNotIn("does not exist", message, "no cause may be claimed that was not checked")

    def test_a_permission_failure_names_the_permission_not_the_location(self):
        text = self.explain(PermissionError(13, "Permission denied"))

        self.assertIn("permission was denied", text)
        self.assertIn("Nothing was uploaded", text)
        self.assertNotIn("/home/someone", text)

    def test_a_write_protection_failure_says_nothing_was_written(self):
        text = self.explain(PrivateWriteError("could not be restricted to owner-only"))

        self.assertIn("did not start", text)
        self.assertIn("Nothing was written", text)

    def test_a_disk_failure_is_reported_as_a_local_file_problem(self):
        text = self.explain(OSError(28, "No space left on device"))

        self.assertIn("local file operation failed", text)
        self.assertIn("No space left on device", text)

    def test_a_missing_tkinter_is_explained_without_a_traceback(self):
        text = self.explain(ModuleNotFoundError("No module named 'tkinter'"))

        self.assertIn("Tkinter", text)
        self.assertIn("--backup-to", text, "the headless alternative must be named")

    def test_no_display_is_explained_by_exception_name_alone(self):
        # Raised by Tk on a headless session; identified by name so this module never imports Tk.
        tcl_error = type("TclError", (Exception,), {})("no display name and no $DISPLAY environment variable")

        text = self.explain(tcl_error)

        self.assertIn("no display is available", text)
        self.assertNotIn("$DISPLAY", text)

    def test_a_database_from_a_newer_version_is_explained_as_an_update_not_damage(self):
        """The store refuses it by type; the message must not suggest the file is damaged."""
        text = self.explain(SchemaTooNewError(9, SCHEMA_VERSION))

        self.assertIn("newer version of this application", text)
        self.assertIn("Nothing was changed and no downgrade was attempted", text)
        self.assertIn("--restore-from", text, "the database commands must still be named")
        self.assertNotIn("damaged", text)

    def test_a_failed_schema_update_names_the_backup_as_the_recovery(self):
        failure = SchemaMigrationError(2, "add the application activity log", 1, 1,
                                       sqlite3.OperationalError("disk I/O error"))
        text = self.explain(failure)

        self.assertIn("could not be updated to the schema version", text)
        self.assertIn("still at schema version 1", text)
        self.assertIn("--restore-from", text)
        self.assertIn("still on disk exactly as it was", text)

    def test_a_file_that_is_not_this_application_is_explained_as_such(self):
        text = self.explain(UnrecognisedDatabaseError("tables but no schema version"))

        self.assertIn("not one this application created", text)
        self.assertIn("--database", text, "the flag that points the app elsewhere must be named")
        self.assertNotIn("/home/someone", text, "no location may be quoted back")

    def test_an_unexpected_failure_is_still_reported_plainly(self):
        text = self.explain(ValueError("something nobody predicted"))

        self.assertIn("ValueError", text)
        self.assertIn("something nobody predicted", text)
        self.assertIn("Nothing was uploaded", text)

    def test_a_long_message_is_bounded(self):
        text = self.explain(ValueError("x" * 5000))

        self.assertLessEqual(len(text), MAX_DIAGNOSTIC_LENGTH + 200, "the explanation must stay readable")

    def test_every_explanation_avoids_sensitive_wording(self):
        for exc in (sqlite3.DatabaseError("file is not a database"), PermissionError(13, "denied"),
                    OSError(28, "No space left on device"), ValueError("unexpected"),
                    ModuleNotFoundError("No module named 'tkinter'")):
            with self.subTest(exception=type(exc).__name__):
                text = self.explain(exc).lower()
                for word in ("password", "token", "api key", "credential", "secret"):
                    self.assertNotIn(word, text)
                self.assertNotIn("/home/someone", text)


class StartupDiagnosticNoteTests(unittest.TestCase):
    """The note kept for later diagnosis is bounded, owner-only, and free of coordinates."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data_folder = Path(self.directory.name) / "AI Career Agent"
        self.database = self.data_folder / "career_agent.sqlite3"

    def test_the_note_is_written_beside_the_local_data(self):
        path = record_startup_failure(sqlite3.DatabaseError("file is not a database"), data_folder=self.data_folder)

        self.assertEqual(path, self.data_folder / "logs" / DIAGNOSTIC_FILE_NAME)
        self.assertTrue(path.is_file())
        body = path.read_text(encoding="utf-8")
        self.assertIn("could not be read", body)
        self.assertIn("--restore-from", body)

    def test_the_note_is_owner_only_where_the_platform_supports_it(self):
        path = record_startup_failure(ValueError("boom"), data_folder=self.data_folder)

        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)
        self.assertTrue(path.is_file())

    def test_the_note_carries_no_filesystem_location_or_candidate_data(self):
        exc = sqlite3.DatabaseError(f"unable to open database file: {self.database}")

        path = record_startup_failure(exc, database_path=self.database, data_folder=self.data_folder)

        body = path.read_text(encoding="utf-8")
        self.assertNotIn(str(self.data_folder), body)
        self.assertNotIn(str(Path.home()), body)

    def test_writing_again_replaces_the_previous_note_instead_of_growing(self):
        first = record_startup_failure(ValueError("first failure"), data_folder=self.data_folder)

        second = record_startup_failure(ValueError("second failure"), data_folder=self.data_folder)

        self.assertEqual(first, second)
        body = second.read_text(encoding="utf-8")
        self.assertIn("second failure", body)
        self.assertNotIn("first failure", body)

    def test_the_note_carries_a_timestamp(self):
        stamp = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

        path = record_startup_failure(ValueError("boom"), data_folder=self.data_folder, timestamp=stamp)

        self.assertIn(stamp.isoformat(timespec="seconds"), path.read_text(encoding="utf-8"))

    def test_a_note_that_cannot_be_written_is_reported_as_missing_not_as_success(self):
        with mock.patch("career_agent.diagnostics.write_private_text_file",
                        side_effect=PrivateWriteError("no permission")):
            path = record_startup_failure(ValueError("boom"), data_folder=self.data_folder)

        self.assertIsNone(path, "a note that could not be written must never be reported as saved")

    def test_the_log_path_follows_the_database_when_no_folder_is_given(self):
        expected = self.data_folder / "logs" / DIAGNOSTIC_FILE_NAME

        self.assertEqual(diagnostic_log_path(self.database), expected)

    def test_the_default_location_is_the_per_user_data_folder(self):
        # No database and no folder given: the per-user application-data folder is used, and the
        # call itself must not create anything.
        path = diagnostic_log_path()

        self.assertEqual(path.name, DIAGNOSTIC_FILE_NAME)
        self.assertEqual(path.parent.name, "logs")


class CommandLineStartupFailureTests(unittest.TestCase):
    """The command line explains a start-up failure, sanitises it, and exits non-zero."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "career_agent.sqlite3"

    def run_cli(self, arguments, desktop_main):
        """Run the CLI with a stubbed desktop entry point that raises ``desktop_main``."""
        fake_module = types.ModuleType("career_agent.desktop")

        def failing_main(database_path=None):
            raise desktop_main

        fake_module.main = failing_main
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(sys.modules, {"career_agent.desktop": fake_module}):
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(arguments)
        return code, out.getvalue(), err.getvalue()

    def test_a_failure_to_start_is_explained_and_exits_with_the_unexpected_code(self):
        code, _out, err = self.run_cli(
            ["--database", str(self.database)], sqlite3.DatabaseError("file is not a database")
        )

        self.assertEqual(code, cli.EXIT_UNEXPECTED)
        self.assertIn("COULD NOT START", err)
        self.assertIn("--restore-from", err)
        self.assertNotIn("Traceback", err)
        self.assertNotIn(str(self.directory.name), err, "the note must not print local paths")

    def test_the_failure_is_kept_in_a_bounded_note_beside_the_database(self):
        self.run_cli(["--database", str(self.database)], ValueError("something unexpected"))

        note = self.database.parent / "logs" / DIAGNOSTIC_FILE_NAME
        self.assertTrue(note.is_file())
        self.assertIn("something unexpected", note.read_text(encoding="utf-8"))

    def test_a_file_the_person_named_on_the_command_line_stays_out_of_the_note(self):
        # An unexpected failure while restoring is reported through the start-up explanation, so the
        # file named on the command line must be redacted there as well: the note is written to be
        # safe to share, and where a person keeps their backups is theirs.
        named = Path(self.directory.name) / "private-backups" / "my-own-copy.sqlite3"

        out, err = io.StringIO(), io.StringIO()
        with mock.patch(
            "career_agent.__main__.restore_backup",
            side_effect=RuntimeError(f"unexpected failure while reading {named}"),
        ):
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["--database", str(self.database), "--restore-from", str(named), "--yes"])

        self.assertEqual(code, cli.EXIT_UNEXPECTED)
        self.assertNotIn("my-own-copy", err.getvalue())
        self.assertNotIn("private-backups", err.getvalue())
        note = self.database.parent / "logs" / DIAGNOSTIC_FILE_NAME
        self.assertTrue(note.is_file())
        written = note.read_text(encoding="utf-8")
        self.assertNotIn("my-own-copy", written)
        self.assertNotIn("private-backups", written)
        self.assertIn("<local path>", written)

    def test_a_location_quoted_inside_the_failure_message_never_reaches_the_note(self):
        # The person names one file on the command line, but the failure message itself may quote a
        # location from somewhere else on this machine (an external volume, a folder synced from
        # elsewhere). That text is copied into the note, which is written to be safe to share, so the
        # location must be hidden even though this command never named it.
        backup = Path(self.directory.name) / "chosen-copy.sqlite3"
        foreign = "/Volumes/Investor Backup/private/notes.sqlite3"
        out, err = io.StringIO(), io.StringIO()
        with mock.patch(
            "career_agent.__main__.restore_backup",
            side_effect=RuntimeError(f"cannot open {foreign} while reading the file"),
        ):
            with redirect_stdout(out), redirect_stderr(err):
                code = cli.main(["--database", str(self.database), "--restore-from", str(backup), "--yes"])

        self.assertEqual(code, cli.EXIT_UNEXPECTED)
        note = self.database.parent / "logs" / DIAGNOSTIC_FILE_NAME
        self.assertTrue(note.is_file())
        written = note.read_text(encoding="utf-8")
        self.assertNotIn("Investor", written)
        self.assertNotIn("Volumes", written)
        self.assertNotIn("notes.sqlite3", written)
        self.assertIn("<local path>", written)
        self.assertNotIn("Investor", err.getvalue())

    def test_a_failure_before_the_database_is_known_still_explains_itself(self):
        # With no --database there is nothing to place the note beside, so the note goes to the
        # application-data folder this machine would really use. The test redirects that resolution
        # into its own temporary directory: a test run must not write into the person's own folder
        # (and must not overwrite the note a real failure left there).
        redirected = Path(self.directory.name) / "application-data"
        with mock.patch("career_agent.desktop_logic.default_data_folder", return_value=redirected):
            code, _out, err = self.run_cli([], ValueError("boom before any path is resolved"))

        self.assertEqual(code, cli.EXIT_UNEXPECTED)
        self.assertIn("COULD NOT START", err)
        note = redirected / "logs" / DIAGNOSTIC_FILE_NAME
        self.assertTrue(note.is_file(), "the note must still be written, just not into the real folder")
        self.assertIn("boom before any path is resolved", note.read_text(encoding="utf-8"))


class TrackerStatusErrorExportTests(unittest.TestCase):
    """The error raised for an unrecognised stored status is part of the public surface."""

    def test_the_error_is_exported_and_is_a_value_error(self):
        from career_agent import TrackerStatusError as exported

        self.assertIs(exported, TrackerStatusError)
        self.assertTrue(issubclass(exported, ValueError))


if __name__ == "__main__":
    unittest.main(verbosity=2)
