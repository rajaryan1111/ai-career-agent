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
from career_agent.store import SCHEMA_VERSION, PrivateWriteError, TrackerStatusError


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

    def test_a_failure_before_the_database_is_known_still_explains_itself(self):
        code, _out, err = self.run_cli([], ValueError("boom before any path is resolved"))

        self.assertEqual(code, cli.EXIT_UNEXPECTED)
        self.assertIn("COULD NOT START", err)


class TrackerStatusErrorExportTests(unittest.TestCase):
    """The error raised for an unrecognised stored status is part of the public surface."""

    def test_the_error_is_exported_and_is_a_value_error(self):
        from career_agent import TrackerStatusError as exported

        self.assertIs(exported, TrackerStatusError)
        self.assertTrue(issubclass(exported, ValueError))


if __name__ == "__main__":
    unittest.main(verbosity=2)
