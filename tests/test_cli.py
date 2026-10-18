import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_agent import cli

try:
    from career_agent import desktop
except ImportError:  # Tkinter is not built into this interpreter.
    desktop = None


class ArgumentParsingTests(unittest.TestCase):
    def test_default_launch_has_no_database_override(self):
        self.assertIsNone(cli.build_arg_parser().parse_args([]).database)

    def test_explicit_database_is_parsed(self):
        args = cli.build_arg_parser().parse_args(["--database", "/tmp/suite.sqlite3"])
        self.assertEqual(args.database, "/tmp/suite.sqlite3")

    def test_help_lists_the_option_without_starting_the_app(self):
        with mock.patch.object(cli, "run") as run:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as raised:
                    cli.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--database", out.getvalue())
        run.assert_not_called()

    def test_version_is_reported_without_starting_the_app_or_a_database(self):
        from career_agent import __version__

        with mock.patch.object(cli, "run") as run:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as raised:
                    cli.main(["--version"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn(__version__, out.getvalue())
        run.assert_not_called()

    def test_missing_option_value_is_a_usage_error(self):
        with mock.patch.object(cli, "run") as run:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(["--database"])
        self.assertEqual(raised.exception.code, 2)
        run.assert_not_called()


class DatabasePathTests(unittest.TestCase):
    def test_none_keeps_the_per_user_default(self):
        self.assertIsNone(cli.resolve_database_path(None))

    def test_tilde_is_expanded(self):
        resolved = cli.resolve_database_path("~/career-agent-test.sqlite3")
        self.assertEqual(resolved, Path.home() / "career-agent-test.sqlite3")

    def test_missing_file_in_an_existing_folder_is_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            cli.check_database_path(Path(folder) / "new.sqlite3")

    def test_existing_file_is_allowed_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            existing = Path(folder) / "existing.sqlite3"
            existing.write_bytes(b"")
            cli.check_database_path(existing)
            self.assertEqual(existing.read_bytes(), b"")

    def test_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "directory, not a file"):
                cli.check_database_path(Path(folder))

    def test_missing_folder_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "missing" / "db.sqlite3"
            with self.assertRaisesRegex(ValueError, "folder does not exist"):
                cli.check_database_path(target)


class MainWiringTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def test_explicit_database_is_forwarded_unchanged(self):
        database = self.folder / "suite.sqlite3"
        with mock.patch.object(cli, "run", return_value=0) as run:
            code = cli.main(["--database", str(database)])
        self.assertEqual(code, 0)
        run.assert_called_once_with(database)

    def test_default_launch_forwards_no_override(self):
        with mock.patch.object(cli, "run", return_value=0) as run:
            code = cli.main([])
        self.assertEqual(code, 0)
        run.assert_called_once_with(None)

    def test_run_exit_code_is_propagated(self):
        with mock.patch.object(cli, "run", return_value=1):
            self.assertEqual(cli.main([]), 1)

    def test_invalid_path_returns_usage_error_without_starting_the_app(self):
        with mock.patch.object(cli, "run") as run, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["--database", str(self.folder)])
        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertIn("directory, not a file", err.getvalue())

    def test_missing_folder_returns_usage_error(self):
        target = self.folder / "missing" / "db.sqlite3"
        with mock.patch.object(cli, "run") as run, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["--database", str(target)])
        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertIn("folder does not exist", err.getvalue())


class FakeRoot:
    def __init__(self):
        self.mainloop_ran = False
        self.destroyed = False

    def mainloop(self):
        self.mainloop_ran = True

    def destroy(self):
        self.destroyed = True


@unittest.skipIf(desktop is None, "Tkinter is not available in this interpreter")
class DesktopEntryPointTests(unittest.TestCase):
    def test_explicit_database_reaches_the_application(self):
        root = FakeRoot()
        database = Path("/tmp/career-agent-cli-test.sqlite3")
        with mock.patch.object(desktop.tk, "Tk", return_value=root), \
                mock.patch.object(desktop, "CareerAgentApp") as app_class:
            code = desktop.run_desktop(database)
        self.assertEqual(code, 0)
        app_class.assert_called_once_with(root, database)
        self.assertTrue(root.mainloop_ran)
        self.assertFalse(root.destroyed)

    def test_default_launch_passes_no_override(self):
        root = FakeRoot()
        with mock.patch.object(desktop.tk, "Tk", return_value=root), \
                mock.patch.object(desktop, "CareerAgentApp") as app_class:
            code = desktop.run_desktop(None)
        self.assertEqual(code, 0)
        app_class.assert_called_once_with(root, None)
        self.assertTrue(root.mainloop_ran)

    def test_startup_failure_returns_nonzero_and_reports_it(self):
        root = FakeRoot()
        with mock.patch.object(desktop.tk, "Tk", return_value=root), \
                mock.patch.object(
                    desktop, "CareerAgentApp",
                    side_effect=sqlite3.OperationalError("unable to open database file"),
                ), \
                mock.patch.object(desktop.messagebox, "showerror") as showerror, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = desktop.run_desktop(Path("/tmp/unwritable.sqlite3"))
        self.assertEqual(code, 1)
        self.assertTrue(root.destroyed)
        showerror.assert_called_once()
        self.assertIn("unable to open database file", err.getvalue())

    def test_missing_display_returns_nonzero(self):
        with mock.patch.object(desktop.tk, "Tk", side_effect=desktop.tk.TclError("no display")), \
                mock.patch.object(desktop, "CareerAgentApp") as app_class, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = desktop.run_desktop(None)
        self.assertEqual(code, 1)
        app_class.assert_not_called()
        self.assertIn("could not open a display", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
