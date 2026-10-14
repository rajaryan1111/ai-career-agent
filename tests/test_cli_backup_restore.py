"""The two database commands the command line offers, exercised through the real parser.

``career_agent/__main__.py`` documents why these commands exist: the situation that needs a restore
most — a database the application cannot read — is also the situation in which the window cannot be
opened, so the commands must work headless and must never need the GUI toolkit. That promise is only
worth anything if it is checked where a user meets it: the argument list, the exit code, the text on
stdout/stderr, and the state of the files afterwards.

``tests/test_backup.py`` proves the backup module itself; this module proves the front end does not
change what that module guarantees. Every database here is created inside a temporary directory, so no
test can see or write the candidate's own database, and the destructive restore cases run against
disposable copies only.
"""
from __future__ import annotations

import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from career_agent import __main__ as cli
from career_agent.backup import validate_app_database
from career_agent.config import DATABASE_ENV
from career_agent.core import ApplicationTracker, Availability, CandidateProfile, JobListing
import career_agent.store as store_module
from career_agent.store import SCHEMA_VERSION, CareerStore

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

PROFILE = CandidateProfile(
    candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
    graduation_year=2027, experience_years=0.5, work_authorization="authorized_without_sponsorship",
    skills=frozenset({"Python"}), preferred_work_modes=frozenset({"remote"}),
)


def listing(listing_id: str) -> JobListing:
    return JobListing(
        listing_id=listing_id, source_id="manual", source_name="Manual entry",
        source_listing_url=f"https://jobs.example/{listing_id}", employer_name="Example Inc",
        role_title="AI Intern", availability_status=Availability.OPEN, employer_apply_url=None,
        canonical_requisition_id=None, location_text="Bengaluru", work_mode="remote",
        role_type="internship", eligibility_scope="restricted", eligible_countries=("India",),
        allowed_degree_disciplines=("ECE",), allowed_study_statuses=("undergraduate",),
        allowed_graduation_years=(2027,), allowed_work_authorizations=("authorized_without_sponsorship",),
        minimum_experience_years=0.0, maximum_experience_years=2.0,
        required_skills=frozenset({"Python"}), provenance_note="Official listing checked today.",
    )


def populate(path, *, listing_ids=("j1",)):
    """Create a real database at ``path`` with a profile, listings, and one tracker row each."""
    with CareerStore(str(path)) as store:
        store.save_profile(PROFILE)
        for listing_id in listing_ids:
            store.save_job(listing(listing_id))
            store.save_tracker(ApplicationTracker(listing_id))
    return Path(path)


def row_counts(path) -> tuple[int, int, int]:
    """Profile rows, listing rows, tracker rows — read straight from the file, not through the store."""
    connection = sqlite3.connect(str(path))
    try:
        return tuple(
            int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            for table in ("candidate_profile", "job_listings", "application_tracker")
        )
    finally:
        connection.close()


class FakeTerminal:
    """A stdin that claims to be a terminal and answers the confirmation prompt once."""

    def __init__(self, answer: str):
        self.answer = answer

    def isatty(self) -> bool:
        return True

    def readline(self, *args) -> str:
        answer, self.answer = self.answer, ""
        return answer


class CommandLineTestCase(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.directory = Path(self._temporary.name)
        self.database = populate(self.directory / "career_agent.sqlite3", listing_ids=("j1", "j2"))

    def run_command(self, arguments, *, stdin=None):
        """Run the real entry point in-process and capture what a terminal would show."""
        out, err = io.StringIO(), io.StringIO()
        patched = mock.patch.object(sys, "stdin", stdin) if stdin is not None else mock.patch.object(
            sys, "stdin", io.StringIO("")
        )
        with patched, redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--database", str(self.database), *arguments])
        return code, out.getvalue(), err.getvalue()


class ExitCodeTests(unittest.TestCase):
    """The codes the docstring and the smoke-test checklist quote must not drift."""

    def test_the_documented_exit_codes_are_unchanged(self):
        self.assertEqual(cli.EXIT_OK, 0)
        self.assertEqual(cli.EXIT_REFUSED, 2)
        self.assertEqual(cli.EXIT_UNEXPECTED, 3)

    def test_the_refused_code_differs_from_argparses_own_code(self):
        """A refusal by this program is 2 only because argparse also uses 2 for a usage error.

        Both are non-zero, so a caller testing for success is still correct either way; this records
        the coincidence rather than leaving it to be discovered later.
        """
        parser = cli.parse_arguments
        with self.assertRaises(SystemExit) as caught, redirect_stderr(io.StringIO()):
            parser(["--backup-to", "x", "--restore-from", "y"])
        self.assertEqual(caught.exception.code, 2)


class BackupCommandTests(CommandLineTestCase):
    def test_the_backup_command_writes_a_verified_file_and_reports_it(self):
        destination = self.directory / "cli-backup.sqlite3"

        code, out, err = self.run_command(["--backup-to", str(destination)])

        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("Backup written and verified", out)
        self.assertIn(str(destination), out)
        self.assertIn("2 jobs", out)
        self.assertIn("profile saved", out)
        info = validate_app_database(destination)
        self.assertEqual(info.job_count, 2)
        self.assertEqual(info.tracker_count, 2)
        self.assertTrue(info.profile_present)

    def test_the_backup_command_refuses_an_existing_file_and_changes_nothing(self):
        destination = self.directory / "already-there.sqlite3"
        destination.write_bytes(b"a file the user already has")
        before = destination.read_bytes()

        code, out, err = self.run_command(["--backup-to", str(destination)])

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertEqual(out, "")
        self.assertIn("REFUSED", err)
        self.assertIn("No backup was created.", err)
        self.assertEqual(destination.read_bytes(), before)

    def test_the_backup_command_refuses_a_missing_database_and_creates_nothing(self):
        destination = self.directory / "never-written.sqlite3"
        out_buffer, err_buffer = io.StringIO(), io.StringIO()
        with redirect_stdout(out_buffer), redirect_stderr(err_buffer):
            code = cli.main(["--database", str(self.directory / "absent.sqlite3"),
                             "--backup-to", str(destination)])

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("REFUSED", err_buffer.getvalue())
        self.assertFalse(destination.exists(), "a refused backup must not leave a file behind")

    def test_the_backup_command_uses_the_database_it_was_given(self):
        """An explicit --database must win, and the database named by the setting must not be used.

        The setting is pointed at a different database that holds different rows, so the backup's own
        contents say which file was read: a backup taken from the setting's file would carry its
        single listing instead of the two in the file named on the command line.
        """
        from_the_setting = populate(self.directory / "from-the-setting.sqlite3", listing_ids=("other",))
        destination = self.directory / "explicit-only.sqlite3"

        with mock.patch.dict(os.environ, {DATABASE_ENV: str(from_the_setting)}):
            code, _out, _err = self.run_command(["--backup-to", str(destination)])

        self.assertEqual(code, cli.EXIT_OK)
        self.assertTrue(destination.is_file())
        self.assertEqual(
            row_counts(destination)[1], 2, "the backup must hold the database named on the command line",
        )
        self.assertNotEqual(row_counts(from_the_setting)[1], 2)


class RestoreConfirmationTests(CommandLineTestCase):
    def test_restoring_without_a_terminal_is_refused_and_changes_nothing(self):
        backup = self.directory / "chosen.sqlite3"
        self.run_command(["--backup-to", str(backup)])
        before = self.database.read_bytes()
        not_a_terminal = io.StringIO("restore\n")

        code, out, err = self.run_command(["--restore-from", str(backup)], stdin=not_a_terminal)

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("Cancelled. Nothing was changed.", out)
        self.assertIn("not a terminal", err)
        self.assertIn("--yes", err)
        self.assertEqual(self.database.read_bytes(), before, "the database must be byte-identical")
        self.assertEqual(not_a_terminal.getvalue(), "restore\n", "nothing may be read from a non-terminal")

    def test_an_answer_that_is_not_the_expected_word_changes_nothing(self):
        backup = self.directory / "chosen.sqlite3"
        self.run_command(["--backup-to", str(backup)])
        before = self.database.read_bytes()

        code, out, _err = self.run_command(
            ["--restore-from", str(backup)], stdin=FakeTerminal("yes, go ahead\n")
        )

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("Cancelled. Nothing was changed.", out)
        self.assertEqual(self.database.read_bytes(), before)

    def test_the_confirmation_prompt_names_both_files(self):
        backup = self.directory / "chosen.sqlite3"
        self.run_command(["--backup-to", str(backup)])

        _code, out, _err = self.run_command(
            ["--restore-from", str(backup)], stdin=FakeTerminal("restore\n")
        )

        self.assertIn(str(self.database), out)
        self.assertIn(str(backup), out)


class RestoreCommandTests(CommandLineTestCase):
    def test_a_confirmed_restore_replaces_the_database_and_reports_the_previous_copy(self):
        self.run_command(["--backup-to", str(self.directory / "snapshot.sqlite3")])
        with CareerStore(str(self.database)) as store:
            store.save_job(listing("added-after-the-backup"))
            store.save_tracker(ApplicationTracker("added-after-the-backup"))
        self.assertEqual(row_counts(self.database), (1, 3, 3))

        code, out, err = self.run_command(
            ["--restore-from", str(self.directory / "snapshot.sqlite3"), "--yes"]
        )

        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("Restored", out)
        self.assertIn("Previous database kept as a verified copy", out)
        self.assertEqual(row_counts(self.database), (1, 2, 2))
        self.assertEqual(validate_app_database(self.database).job_count, 2)
        preserved = [
            line.split(": ", 1)[1] for line in out.splitlines()
            if "Previous database kept as a verified copy: " in line
        ]
        self.assertEqual(len(preserved), 1)
        self.assertEqual(validate_app_database(preserved[0]).job_count, 3,
                         "the copy taken before the restore must hold what the restore replaced")

    def test_restoring_a_backup_from_an_earlier_schema_reports_the_update_it_will_need(self):
        """An older backup is a supported recovery path; the version it records must be visible.

        Restoring installs the file exactly as validated - it is not migrated here - so the report
        says what will happen the next time the app opens it instead of leaving an older version
        number unexplained. The restored data is checked, not just the message.
        """
        older = self.directory / "older-backup.sqlite3"
        steps = tuple(step for step in store_module._MIGRATIONS if step[0] == 1)
        with mock.patch.object(store_module, "_MIGRATIONS", steps):
            with CareerStore(str(older)) as store:
                store.save_job(listing("only-in-the-older-backup"))
                store.save_tracker(ApplicationTracker("only-in-the-older-backup"))

        code, out, err = self.run_command(["--restore-from", str(older), "--yes"])

        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("older schema (version 1)", out)
        self.assertIn(f"updates it to schema version {SCHEMA_VERSION}", out)
        self.assertEqual(validate_app_database(older).schema_version, 1,
                         "the chosen backup file itself is never migrated")
        self.assertEqual(validate_app_database(self.database).schema_version, 1,
                         "the installed file is the validated one, not a rewritten one")
        with CareerStore(str(self.database)) as upgraded:
            self.assertIsNotNone(upgraded.get_job("only-in-the-older-backup"))
            self.assertEqual(upgraded._connection.execute("PRAGMA user_version").fetchone()[0],
                             SCHEMA_VERSION)
        self.assertEqual(validate_app_database(self.database).schema_version, SCHEMA_VERSION,
                         "opening it with this build is what records the update")

    def test_restoring_a_current_backup_says_nothing_about_a_schema_update(self):
        self.run_command(["--backup-to", str(self.directory / "snapshot.sqlite3")])

        code, out, err = self.run_command(
            ["--restore-from", str(self.directory / "snapshot.sqlite3"), "--yes"])

        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(err, "")
        self.assertNotIn("older schema", out)

    def test_a_corrupt_backup_is_refused_and_the_database_is_untouched(self):
        corrupt = self.directory / "corrupt.sqlite3"
        corrupt.write_bytes(b"this is not a database\n" * 4)
        before = self.database.read_bytes()

        code, out, err = self.run_command(["--restore-from", str(corrupt), "--yes"])

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertEqual(out, "")
        self.assertIn("REFUSED", err)
        self.assertIn("The restore did not complete.", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_a_missing_backup_file_is_refused_and_the_database_is_untouched(self):
        before = self.database.read_bytes()

        code, _out, err = self.run_command(
            ["--restore-from", str(self.directory / "not-here.sqlite3"), "--yes"]
        )

        self.assertEqual(code, cli.EXIT_REFUSED)
        self.assertIn("REFUSED", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_the_two_database_actions_cannot_be_combined(self):
        before = self.database.read_bytes()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), mock.patch.object(sys, "stdin", io.StringIO("")):
            with self.assertRaises(SystemExit) as caught:
                cli.main(["--database", str(self.database),
                          "--backup-to", str(self.directory / "b.sqlite3"),
                          "--restore-from", str(self.directory / "r.sqlite3"), "--yes"])

        self.assertEqual(caught.exception.code, 2)
        self.assertIn("not allowed with", err.getvalue())
        self.assertFalse((self.directory / "b.sqlite3").exists())
        self.assertEqual(self.database.read_bytes(), before)


class HeadlessPromiseTests(unittest.TestCase):
    """The documented promise: the database commands work where the window cannot open."""

    def test_the_database_commands_do_not_import_the_desktop_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = populate(directory / "career_agent.sqlite3")
            destination = directory / "headless-backup.sqlite3"
            script = (
                "import sys\n"
                "from career_agent import __main__ as cli\n"
                f"code = cli.main(['--database', {str(database)!r}, '--backup-to', {str(destination)!r}])\n"
                "print('EXIT', code)\n"
                "print('DESKTOP_IMPORTED', 'career_agent.desktop' in sys.modules)\n"
            )

            result = subprocess.run(
                [sys.executable, "-c", script], cwd=REPOSITORY_ROOT, capture_output=True, text=True,
                timeout=120, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("EXIT 0", result.stdout)
            self.assertIn("DESKTOP_IMPORTED False", result.stdout)
            self.assertEqual(validate_app_database(destination).job_count, 1)


if __name__ == "__main__":
    unittest.main()
