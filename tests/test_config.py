"""Where the app keeps its data, and the ``--doctor`` report that answers the same question.

Two halves, because one behaviour is worth testing twice:

* ``tests/config`` — :mod:`career_agent.config` decides the database path from an explicit path, an
  environment setting, or the platform default, and *never* touches the filesystem while doing it.
  The tests inject the environment, home directory and platform so each rule is checked without being
  on that platform and without reading the machine running the tests.
* ``DoctorCommandTests`` — the command line front end, exercised through the real parser: the exit
  code, the text, and what is left on disk afterwards. The doctor is the report someone runs when the
  app will not open, so it must be read-only even when the file it inspects is damaged.

Every path used here is inside a temporary directory. No test can see or write the candidate's own
database, and no test writes to the machine's real per-user data folder.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from career_agent import __main__ as cli
from career_agent.config import (
    DATABASE_ENV, SOURCE_COMMAND_LINE, SOURCE_DEFAULT, SOURCE_ENVIRONMENT, database_path_for_run,
    describe_settings, resolve_settings,
)
from career_agent.event_log import LOG_FILE_NAME
from career_agent.desktop_logic import (
    CAREER_AGENT_HOME_ENV, DATABASE_FILE_NAME, default_data_folder,
)
from career_agent.backup import validate_app_database
from career_agent.core import Availability, JobListing
from career_agent.store import SCHEMA_VERSION, CareerStore

#: A path that is absolute on the platform running these tests. ``/srv`` is not one on Windows, where a
#: path without a drive is relative, and the rules under test are about absolute paths being honoured.
ABSOLUTE = Path(Path.cwd().anchor)


def sample_job(listing_id: str = "j1") -> JobListing:
    return JobListing(
        listing_id=listing_id, source_id="manual", source_name="Manual entry",
        source_listing_url=f"https://jobs.example/{listing_id}", employer_name="Example Inc",
        role_title="AI Intern", availability_status=Availability.OPEN,
    )

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SettingsTests(unittest.TestCase):
    """The three rules, and what happens when a setting cannot be used as given."""

    def setUp(self) -> None:
        self.home = Path("/home/example")
        self.environ = {"HOME": str(self.home)}

    def test_an_explicit_path_wins_over_the_environment(self) -> None:
        settings = resolve_settings(
            database_path=ABSOLUTE / "tmp" / "named.sqlite3",
            environ={**self.environ, DATABASE_ENV: str(ABSOLUTE / "tmp" / "from-environment.sqlite3")},
            home=self.home, system="Linux",
        )
        self.assertEqual(settings.database_path, ABSOLUTE / "tmp" / "named.sqlite3")
        self.assertEqual(settings.database_source, SOURCE_COMMAND_LINE)
        self.assertEqual(settings.notes, ())

    def test_an_absolute_environment_path_is_used(self) -> None:
        settings = resolve_settings(
            environ={**self.environ, DATABASE_ENV: str(ABSOLUTE / "tmp" / "from-environment.sqlite3")},
            home=self.home, system="Linux",
        )
        self.assertEqual(settings.database_path, ABSOLUTE / "tmp" / "from-environment.sqlite3")
        self.assertEqual(settings.database_source, SOURCE_ENVIRONMENT)
        self.assertFalse(settings.uses_default_location)

    def test_a_relative_environment_path_is_ignored_and_explained(self) -> None:
        settings = resolve_settings(
            environ={**self.environ, DATABASE_ENV: "data/career.sqlite3"},
            home=self.home, system="Linux",
        )
        self.assertEqual(settings.database_source, SOURCE_DEFAULT)
        self.assertEqual(settings.database_path, settings.default_data_folder / DATABASE_FILE_NAME)
        self.assertTrue(settings.uses_default_location)
        self.assertEqual(len(settings.notes), 1)
        self.assertIn(DATABASE_ENV, settings.notes[0])
        self.assertIn("absolute", self.notes_text(settings))

    def notes_text(self, settings) -> str:
        return "\n".join(settings.notes)

    def test_a_blank_environment_path_is_treated_as_unset(self) -> None:
        settings = resolve_settings(
            environ={**self.environ, DATABASE_ENV: "   "}, home=self.home, system="Linux",
        )
        self.assertEqual(settings.database_source, SOURCE_DEFAULT)
        self.assertEqual(settings.notes, ())

    def test_the_default_is_the_platform_data_folder(self) -> None:
        settings = resolve_settings(environ=self.environ, home=self.home, system="Linux")
        self.assertEqual(settings.default_data_folder, default_data_folder(
            system="Linux", environ=self.environ, home=self.home))
        self.assertEqual(
            settings.database_path, self.home / ".local" / "share" / "ai-career-agent" / DATABASE_FILE_NAME,
        )

    def test_an_absolute_home_override_moves_both_the_folder_and_the_database(self) -> None:
        settings = resolve_settings(
            environ={**self.environ, CAREER_AGENT_HOME_ENV: str(ABSOLUTE / "srv" / "career")},
            home=self.home, system="Linux",
        )
        moved = ABSOLUTE / "srv" / "career" / "ai-career-agent"
        self.assertEqual(settings.default_data_folder, moved)
        self.assertEqual(settings.database_path, moved / DATABASE_FILE_NAME)

    def test_a_relative_home_override_is_ignored_and_explained(self) -> None:
        settings = resolve_settings(
            environ={**self.environ, CAREER_AGENT_HOME_ENV: "career-data"},
            home=self.home, system="Linux",
        )
        self.assertEqual(settings.default_data_folder, self.home / ".local" / "share" / "ai-career-agent")
        self.assertEqual(len(settings.notes), 1)
        self.assertIn(CAREER_AGENT_HOME_ENV, settings.notes[0])

    def test_resolving_settings_creates_nothing(self) -> None:
        """Choosing a path must not have side effects; the doctor relies on that."""
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace) / "not-created-yet"
            settings = resolve_settings(
                environ={"XDG_DATA_HOME": str(root)}, home=self.home, system="Linux",
            )
            self.assertEqual(settings.database_path.parent, root / "ai-career-agent")
            self.assertFalse(root.exists(), "resolving settings created a directory")

    def test_a_tilde_path_is_expanded(self) -> None:
        settings = resolve_settings(
            database_path="~/career/own.sqlite3", environ=self.environ, home=self.home, system="Linux",
        )
        self.assertFalse(str(settings.database_path).startswith("~"))
        self.assertTrue(settings.database_path.is_absolute())

    def test_describe_settings_names_the_path_its_source_and_the_folder(self) -> None:
        settings = resolve_settings(
            environ={**self.environ, DATABASE_ENV: "relative.sqlite3"}, home=self.home, system="Linux",
        )
        lines = describe_settings(settings)
        text = "\n".join(lines)
        self.assertIn(str(settings.database_path), text)
        self.assertIn(SOURCE_DEFAULT, text)
        self.assertIn(str(settings.default_data_folder), text)
        self.assertIn(CAREER_AGENT_HOME_ENV, text, "the default line should say how to move the folder")
        self.assertIn(DATABASE_ENV, text, "an ignored setting must be explained")


class DatabasePathForRunTests(unittest.TestCase):
    """The one entry point the window and the command line share, including its single side effect."""

    def test_the_default_folder_is_created_so_a_first_run_can_open_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            home = Path(workspace) / "home"
            home.mkdir()
            chosen = database_path_for_run(environ={"XDG_DATA_HOME": workspace}, home=home, system="Linux")
            self.assertEqual(chosen, Path(workspace) / "ai-career-agent" / DATABASE_FILE_NAME)
            self.assertTrue(chosen.parent.is_dir(), "the default folder was not created")
            self.assertFalse(chosen.exists(), "choosing a path must not create the database itself")

    def test_a_named_path_is_used_as_given_and_no_folder_is_created_for_it(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            named = Path(workspace) / "not-there" / "mine.sqlite3"
            chosen = database_path_for_run(named, environ={"XDG_DATA_HOME": workspace}, system="Linux")
            self.assertEqual(chosen, named)
            self.assertFalse(named.parent.exists(), "a named path created folders of its own")


class DoctorCommandTests(unittest.TestCase):
    """``--doctor`` on the command line: exit code, wording, and a file system left untouched."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.home = Path(self._temporary.name) / "home"
        self.home.mkdir()
        self.home_override = Path(self._temporary.name) / "data"

    def run_doctor(self, *arguments: str, environ: dict[str, str] | None = None):
        """Run the real parser and the real command; return (exit code, stdout, stderr)."""
        out, err = StringIO(), StringIO()
        environment = {"CAREER_AGENT_HOME": str(self.home_override)} if environ is None else environ
        with mock.patch.dict(os.environ, environment, clear=False), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                code = cli.main(["--doctor", *arguments])
            except SystemExit as exit_request:  # argparse refuses a bad argument list this way
                code = int(exit_request.code or 0)
        return code, out.getvalue(), err.getvalue()

    @property
    def default_database(self) -> Path:
        """Where the application itself would keep its database under this environment override.

        Resolved by the module that decides it rather than spelled out here: the folder is
        ``AI Career Agent`` on macOS and Windows and ``ai-career-agent`` elsewhere, so a test that
        spells the name out can only pass on the platform it was written on. That is precisely how this
        property failed the first time the suite ran on macOS and on Windows.
        """
        return resolve_settings(environ={"CAREER_AGENT_HOME": str(self.home_override)},
                                home=self.home).database_path

    def test_the_expected_path_is_the_one_the_application_resolves(self) -> None:
        """The check above is only meaningful if the test and the app agree on where the file goes.

        On Linux they did, because the folder name there matched the string this test used to spell out.
        On macOS and Windows the application uses ``AI Career Agent`` and the test did not, so the doctor
        looked in an empty folder and six tests reported failures that were the test's own.
        """
        with mock.patch.dict(os.environ, {"CAREER_AGENT_HOME": str(self.home_override)}):
            expected = resolve_settings().database_path
        self.assertEqual(self.default_database, expected)

    def test_a_missing_database_is_reported_as_not_created_yet(self) -> None:
        code, out, _ = self.run_doctor()
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("No problems found", out)
        self.assertIn("creates it on first run", out)
        self.assertIn(str(self.default_database), out)
        self.assertFalse(self.default_database.exists(), "the doctor created a database")
        self.assertFalse(self.home_override.exists(), "the doctor created the data folder")
        self.assertFalse(
            (self.default_database.parent / "logs").exists(), "the doctor created a logs folder",
        )

    def test_a_readable_database_is_summarised(self) -> None:
        self.default_database.parent.mkdir(parents=True)
        with CareerStore(str(self.default_database)):
            pass
        code, out, _ = self.run_doctor()
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn(f"schema version {SCHEMA_VERSION}", out)
        self.assertIn("0 jobs", out)
        self.assertIn(f"Python {sys.version_info.major}.{sys.version_info.minor}", out)

    def test_an_older_schema_is_reported_as_updated_on_the_next_open(self) -> None:
        self.default_database.parent.mkdir(parents=True)
        with CareerStore(str(self.default_database)):
            pass
        out = StringIO()
        with mock.patch.dict(os.environ, {"CAREER_AGENT_HOME": str(self.home_override)}), \
                mock.patch.object(cli, "SCHEMA_VERSION", SCHEMA_VERSION + 1), redirect_stdout(out):
            code = cli.main(["--doctor"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn(
            f"written by schema version {SCHEMA_VERSION}; opening the app updates it to version "
            f"{SCHEMA_VERSION + 1}", out.getvalue(),
        )

    def test_a_newer_schema_is_reported_as_a_problem(self) -> None:
        self.default_database.parent.mkdir(parents=True)
        with CareerStore(str(self.default_database)):
            pass
        connection = sqlite3.connect(str(self.default_database))
        try:
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
            connection.commit()
        finally:
            connection.close()
        code, out, _ = self.run_doctor()
        self.assertEqual(code, cli.EXIT_PROBLEM_FOUND)
        self.assertIn("newer than this app supports", out)
        self.assertIn("Nothing was changed", out)

    def test_a_damaged_database_is_reported_without_being_changed(self) -> None:
        self.default_database.parent.mkdir(parents=True)
        self.default_database.write_bytes(b"this is not a database")
        before = self.default_database.read_bytes()
        code, out, _ = self.run_doctor()
        self.assertEqual(code, cli.EXIT_PROBLEM_FOUND)
        self.assertIn("could not be read", out)
        self.assertIn("The app gives the same message", out)
        self.assertEqual(self.default_database.read_bytes(), before, "the doctor changed the file")
        self.assertFalse((self.default_database.parent / "logs").exists())

    def test_an_empty_file_is_reported_as_a_problem(self) -> None:
        self.default_database.parent.mkdir(parents=True)
        self.default_database.touch()
        code, out, _ = self.run_doctor()
        self.assertEqual(code, cli.EXIT_PROBLEM_FOUND)
        self.assertIn("empty (0 bytes)", out)

    @unittest.skipIf(os.name == "posix" and os.geteuid() == 0, "root ignores directory permissions")
    @unittest.skipUnless(os.name == "posix", "POSIX directory permissions")
    def test_an_unwritable_data_folder_is_reported(self) -> None:
        self.home_override.mkdir()
        os.chmod(self.home_override, 0o500)  # read + execute, no write
        self.addCleanup(os.chmod, self.home_override, 0o700)
        code, out, _ = self.run_doctor()
        self.assertEqual(code, cli.EXIT_PROBLEM_FOUND)
        self.assertIn("is not writable", out)
        self.assertFalse(self.default_database.parent.exists(), "the doctor created the data folder")

    def test_the_doctor_reports_the_event_log_and_the_last_event(self) -> None:
        """Someone asking "what has this app been doing?" must be able to find the answer."""
        self.default_database.parent.mkdir(parents=True)
        with CareerStore(str(self.default_database)) as store:
            store.save_job(sample_job())

        code, out, _ = self.run_doctor()

        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("Event log:", out)
        self.assertIn(LOG_FILE_NAME, out)
        self.assertIn("last event:", out)
        self.assertIn("event=job.saved detail=id=j1", out)

    def test_the_doctor_says_when_nothing_has_been_recorded_yet(self) -> None:
        self.default_database.parent.mkdir(parents=True)
        with CareerStore(str(self.default_database)):
            pass
        (self.default_database.parent / "logs" / LOG_FILE_NAME).unlink()

        code, out, _ = self.run_doctor()

        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("nothing recorded yet", out)

    def test_an_explicit_database_path_overrides_the_environment(self) -> None:
        elsewhere = Path(self._temporary.name) / "chosen.sqlite3"
        elsewhere.parent.mkdir(parents=True, exist_ok=True)
        with CareerStore(str(elsewhere)):
            pass
        code, out, _ = self.run_doctor("--database", str(elsewhere))
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn(f"chosen by {SOURCE_COMMAND_LINE}", out)
        self.assertIn(str(elsewhere), out)

    def test_the_doctor_refuses_to_share_the_command_line_with_backup(self) -> None:
        target = Path(self._temporary.name) / "should-not-exist.sqlite3"
        code, _, err = self.run_doctor("--backup-to", str(target))
        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("not allowed with argument", err)
        self.assertFalse(target.exists(), "a refused command line wrote a file")

    def test_backup_follows_the_same_database_rules(self) -> None:
        """A backup must name the file the app would open, including when the setting chooses it."""
        database = Path(self._temporary.name) / "from-setting.sqlite3"
        with CareerStore(str(database)):
            pass
        target = Path(self._temporary.name) / "backup.sqlite3"
        out = StringIO()
        with mock.patch.dict(os.environ, {DATABASE_ENV: str(database)}), redirect_stdout(out):
            code = cli.main(["--backup-to", str(target)])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn(f"Backup written and verified: {target}", out.getvalue())
        self.assertTrue(target.is_file())
        self.assertEqual(validate_app_database(target).schema_version, SCHEMA_VERSION)

    def test_the_doctor_does_not_need_the_gui_toolkit(self) -> None:
        """The report exists for the case where the window cannot open, so it must not import Tk."""
        script = (
            "import sys\n"
            "from career_agent.__main__ import main\n"
            "main(['--doctor', '--database', sys.argv[1]])\n"
            "print('tkinter loaded:', 'tkinter' in sys.modules)\n"
        )
        database = Path(self._temporary.name) / "subprocess.sqlite3"
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script, str(database)],
            cwd=str(REPOSITORY_ROOT), capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("tkinter loaded: False", completed.stdout)
        self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()
