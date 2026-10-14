"""Tests for career_agent.backup: verified local backup and restore.

Disposable temporary databases only — the per-user database of whoever runs the suite is never
touched, and no test makes a network request. Tests that assert POSIX mode bits are skipped where the
platform has no POSIX permissions. The desktop buttons are covered in tests/test_desktop_handlers.py;
widget rendering and macOS behaviour are not covered by any automated test in this repository.
"""
import io
import json
import os
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from career_agent import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, JobListing,
)
from career_agent import backup as backup_module
from career_agent.__main__ import main as cli_main
from career_agent.backup import (
    BackupError, automatic_backup_path, create_backup, restore_backup, suggested_backup_name,
    validate_app_database,
)
from career_agent.store import SCHEMA_TABLES, SCHEMA_TABLES_BY_VERSION, SCHEMA_VERSION, CareerStore

PROFILE = CandidateProfile(
    candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
    graduation_year=2027, experience_years=0.5, work_authorization="authorized_without_sponsorship",
    skills=frozenset({"Python", "RAG"}), preferred_work_modes=frozenset({"remote"}),
)

#: Fixed stamp so file names in assertions do not depend on the clock.
STAMP = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def sample_job(listing_id="j1", employer="Example Inc"):
    return JobListing(
        listing_id=listing_id, source_id="manual", source_name="Manual entry",
        source_listing_url=f"https://jobs.example/{listing_id}", employer_name=employer,
        role_title="AI Intern", availability_status=Availability.OPEN,
        employer_apply_url=None, canonical_requisition_id=None, location_text="Bengaluru",
        work_mode="remote", role_type="internship", eligibility_scope="restricted",
        eligible_countries=("India",), allowed_degree_disciplines=("ECE",),
        allowed_study_statuses=("undergraduate",), allowed_graduation_years=(2027,),
        allowed_work_authorizations=("authorized_without_sponsorship",),
        minimum_experience_years=0.0, maximum_experience_years=2.0,
        required_skills=frozenset({"Python"}), provenance_note="Official listing checked today.",
    )


def populate(path, *, job_ids=("j1",), with_profile=True):
    """Create a real database at ``path`` with the given listings plus a tracker row each."""
    with CareerStore(str(path)) as store:
        if with_profile:
            store.save_profile(PROFILE)
        for listing_id in job_ids:
            store.save_job(sample_job(listing_id))
            store.save_tracker(ApplicationTracker(listing_id))
    return Path(path)


def table_rows(path, table):
    connection = sqlite3.connect(str(path))
    try:
        rows = connection.execute(f"SELECT * FROM {table}").fetchall()
    finally:
        connection.close()
    return sorted(str(row) for row in rows)


def sidecars_of(path):
    path = Path(path)
    return sorted(
        candidate.name for candidate in path.parent.iterdir()
        if candidate.name.startswith(f"{path.name}-") or candidate.name.startswith(f".{path.name}.")
    )


class BackupTestCase(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = Path(self._directory.name)

    def mode_of(self, path):
        return Path(path).stat().st_mode & 0o777

    def assert_no_leftovers(self, path, *, ignore=()):
        """The operation must not leave staging, rollback or partial files behind."""
        leftovers = [
            candidate.name for candidate in Path(path).parent.iterdir()
            if (".partial" in candidate.name or "rollback" in candidate.name) and candidate.name not in ignore
        ]
        self.assertEqual(leftovers, [], "a temporary file was left behind")


class BackupCreationTests(BackupTestCase):
    def test_a_backup_holds_the_profile_jobs_and_tracker_history(self):
        live = populate(self.directory / "career_agent.sqlite3", job_ids=("j1", "j2"))
        destination = self.directory / "chosen-backup.sqlite3"

        info = create_backup(live, destination)

        self.assertEqual(info.job_count, 2)
        self.assertEqual(info.tracker_count, 2)
        self.assertTrue(info.profile_present)
        self.assertEqual(info.schema_version, SCHEMA_VERSION)
        self.assertEqual(table_rows(destination, "candidate_profile"), table_rows(live, "candidate_profile"))
        self.assertEqual(table_rows(destination, "job_listings"), table_rows(live, "job_listings"))
        self.assertEqual(table_rows(destination, "application_tracker"), table_rows(live, "application_tracker"))
        self.assert_no_leftovers(destination)

    def test_the_backup_is_readable_after_the_source_is_gone(self):
        """A backup is only useful if it stands alone: no side files, no source database."""
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "standalone.sqlite3"
        create_backup(live, destination)
        moved = self.directory / "elsewhere" / destination.name
        moved.parent.mkdir()
        destination.rename(moved)

        reopened = CareerStore(str(moved))
        self.addCleanup(reopened.close)
        self.assertEqual([job.listing_id for job in reopened.list_jobs()], ["j1"])
        self.assertEqual(reopened.get_profile().degree_discipline, "ECE")

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_a_backup_is_owner_only_regardless_of_the_process_umask(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "private-backup.sqlite3"
        previous = os.umask(0o000)  # the most permissive umask: bits cannot be relied on
        try:
            create_backup(live, destination)
        finally:
            os.umask(previous)

        self.assertEqual(self.mode_of(destination), 0o600)

    def test_a_backup_has_no_sqlite_side_files_and_uses_the_classic_format(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "single-file.sqlite3"

        create_backup(live, destination)

        self.assertEqual(sidecars_of(destination), [])
        header = destination.read_bytes()[:20]
        self.assertEqual((header[18], header[19]), (1, 1), "the backup must be a classic single-file database")

    def test_a_backup_of_a_wal_database_keeps_the_rows_that_live_in_the_wal(self):
        """A plain file copy loses them; the backup must not."""
        live = populate(self.directory / "career_agent.sqlite3")
        connection = sqlite3.connect(str(live))
        self.addCleanup(connection.close)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("INSERT INTO job_listings VALUES (?, ?, ?, ?, ?)",
                           ("wal-only", json.dumps({}), "key", "2026-01-01", "2026-01-01"))
        connection.commit()
        self.assertTrue((self.directory / "career_agent.sqlite3-wal").exists(), "precondition")

        info = create_backup(live, self.directory / "wal-backup.sqlite3")

        self.assertEqual(info.job_count, 2, "the row committed into the -wal file must be in the backup")
        self.assertEqual(sidecars_of(self.directory / "wal-backup.sqlite3"), [])

    def test_an_existing_backup_is_refused_and_left_byte_identical(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "existing.sqlite3"
        destination.write_bytes(b"an older backup the user still needs")
        before = destination.read_bytes()

        with self.assertRaises(BackupError) as caught:
            create_backup(live, destination)

        self.assertIn("already exists", str(caught.exception))
        self.assertIn("never overwritten", str(caught.exception))
        self.assertEqual(destination.read_bytes(), before)
        self.assert_no_leftovers(destination)

    def test_a_symbolic_link_destination_is_refused_and_leaves_its_target_alone(self):
        live = populate(self.directory / "career_agent.sqlite3")
        victim = self.directory / "unrelated-file.json"
        victim.write_text("a private file that must survive", encoding="utf-8")
        link = self.directory / "link-backup.sqlite3"
        try:
            os.symlink(victim, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links are unavailable here: {exc}")

        with self.assertRaises(BackupError) as caught:
            create_backup(live, link)

        self.assertIn("symbolic link", str(caught.exception))
        self.assertEqual(victim.read_text(encoding="utf-8"), "a private file that must survive")
        self.assertTrue(link.is_symlink(), "the link itself must be left alone")

    def test_a_dangling_symbolic_link_is_refused(self):
        live = populate(self.directory / "career_agent.sqlite3")
        link = self.directory / "dangling.sqlite3"
        try:
            os.symlink(self.directory / "does-not-exist.sqlite3", link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links are unavailable here: {exc}")

        with self.assertRaises(BackupError) as caught:
            create_backup(live, link)

        self.assertIn("symbolic link", str(caught.exception))
        self.assertFalse((self.directory / "does-not-exist.sqlite3").exists())

    def test_a_folder_or_a_missing_folder_is_refused_with_a_useful_message(self):
        live = populate(self.directory / "career_agent.sqlite3")
        with self.assertRaises(BackupError) as caught:
            create_backup(live, self.directory)
        self.assertIn("folder", str(caught.exception))

        with self.assertRaises(BackupError) as caught:
            create_backup(live, self.directory / "absent" / "backup.sqlite3")
        self.assertIn("does not exist", str(caught.exception))

    def test_a_missing_or_empty_database_is_refused(self):
        with self.assertRaises(BackupError) as caught:
            create_backup(self.directory / "absent.sqlite3", self.directory / "backup.sqlite3")
        self.assertIn("no database", str(caught.exception).lower())

        empty = self.directory / "empty.sqlite3"
        empty.write_bytes(b"")
        with self.assertRaises(BackupError) as caught:
            create_backup(empty, self.directory / "backup.sqlite3")
        self.assertIn("empty", str(caught.exception))

    def test_a_database_that_is_not_readable_is_refused_and_writes_nothing(self):
        live = self.directory / "career_agent.sqlite3"
        live.write_text("this is not a database", encoding="utf-8")
        destination = self.directory / "backup.sqlite3"

        with self.assertRaises(BackupError) as caught:
            create_backup(live, destination)

        self.assertIn("not a database", str(caught.exception))
        self.assertFalse(destination.exists())

    def test_a_backup_is_refused_while_another_connection_holds_the_database(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "backup.sqlite3"
        holder = sqlite3.connect(str(live), isolation_level=None)
        self.addCleanup(holder.close)
        holder.execute("BEGIN")
        holder.execute("SELECT count(*) FROM job_listings").fetchone()

        with mock.patch.object(backup_module, "LOCK_TIMEOUT_SECONDS", 0.2):
            with self.assertRaises(BackupError) as caught:
                create_backup(live, destination)

        self.assertIn("in use", str(caught.exception))
        self.assertFalse(destination.exists(), "a refused backup must not leave a file behind")

    def test_a_backup_that_does_not_verify_is_removed_and_reported_as_a_failure(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "unverified.sqlite3"

        with mock.patch.object(
            backup_module, "validate_app_database",
            side_effect=lambda path: (_ for _ in ()).throw(BackupError("simulated verification failure"))
            if Path(path) == destination else validate_app_database(path),
        ):
            with self.assertRaises(BackupError) as caught:
                create_backup(live, destination)

        self.assertIn("did not verify", str(caught.exception))
        self.assertFalse(destination.exists(), "an unverified backup must not survive on disk")
        self.assert_no_leftovers(destination)

    def test_a_failure_to_protect_the_new_file_leaves_nothing_behind(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "unprotected.sqlite3"

        with mock.patch("career_agent.store.os.fchmod", side_effect=OSError("operation not permitted")):
            with self.assertRaises(BackupError) as caught:
                create_backup(live, destination)

        self.assertIn("nothing was written", str(caught.exception))
        self.assertFalse(destination.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_a_filesystem_that_ignores_the_mode_leaves_no_backup(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "sloppy.sqlite3"
        fake_stat = os.stat(self.directory)
        unreadable = type(fake_stat)(os.stat_result((stat.S_IFREG | 0o644, *(fake_stat[i] for i in range(1, 10)))))

        with mock.patch.object(os, "lstat", return_value=unreadable):
            with self.assertRaises(BackupError) as caught:
                create_backup(live, destination)

        self.assertIn("owner-only", str(caught.exception))
        self.assertFalse(destination.exists(), "candidate data must not be left readable")


class BackupValidationTests(BackupTestCase):
    """The checks that run before anything local is replaced."""

    def test_a_healthy_database_is_described_accurately(self):
        live = populate(self.directory / "career_agent.sqlite3", job_ids=("j1", "j2"))

        info = validate_app_database(live)

        self.assertEqual((info.job_count, info.tracker_count, info.profile_present), (2, 2, True))
        self.assertIn("2 jobs", info.summary())
        self.assertEqual(info.foreign_key_violations, 0)

    def test_validation_does_not_modify_the_file_or_create_side_files(self):
        live = populate(self.directory / "career_agent.sqlite3")
        before = live.read_bytes()
        mode_before = self.mode_of(live)
        # The application's own log folder sits beside the database (the store writes one line per
        # event), so "nothing appeared" is measured against what was already there, and every
        # neighbour's contents and mode are checked as well rather than only their names.
        neighbours = {
            path.name: (path.read_bytes(), self.mode_of(path))
            for path in self.directory.iterdir() if path.is_file() and path != live
        }

        validate_app_database(live)

        self.assertEqual(live.read_bytes(), before)
        self.assertEqual(self.mode_of(live), mode_before)
        self.assertEqual(
            {path.name for path in self.directory.iterdir() if path.name != live.name},
            set(neighbours) | {"logs"},
        )
        for name, (contents, mode) in neighbours.items():
            self.assertEqual((self.directory / name).read_bytes(), contents, f"{name} was rewritten")
            self.assertEqual(self.mode_of(self.directory / name), mode, f"{name} changed mode")

    def test_a_non_database_file_is_refused(self):
        target = self.directory / "not-a-database.sqlite3"
        target.write_text("plain text", encoding="utf-8")
        with self.assertRaises(BackupError) as caught:
            validate_app_database(target)
        self.assertIn("not a database", str(caught.exception))

    def test_a_truncated_database_is_refused(self):
        live = populate(self.directory / "career_agent.sqlite3")
        connection = sqlite3.connect(str(live))
        try:
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        finally:
            # ``with connection`` manages the transaction, not the connection: it never closes, so the
            # connection stayed open until the garbage collector ran (an "unclosed database"
            # ResourceWarning on interpreters that report it). Read the page size, then close here.
            connection.close()
        truncated = self.directory / "truncated.sqlite3"
        truncated.write_bytes(live.read_bytes()[: page_size * 2])  # valid header, missing pages

        with self.assertRaises(BackupError) as caught:
            validate_app_database(truncated)

        self.assertIn("not a database this app can read", str(caught.exception))

    def test_a_database_that_fails_its_integrity_check_is_refused(self):
        """The full-scan check must gate a restore even when SQLite can otherwise open the file."""
        live = populate(self.directory / "career_agent.sqlite3")
        real_connect = sqlite3.connect

        class _Verdict:
            def fetchone(self):
                return ("*** in database main ***\nPage 3 is never used",)

        class _DamagedConnection:
            """Behaves like an openable database whose integrity check reports problems."""

            def __init__(self, connection):
                self._connection = connection

            def execute(self, statement, *parameters):
                if "integrity_check" in statement:
                    return _Verdict()
                return self._connection.execute(statement, *parameters)

            def close(self):
                self._connection.close()

        with mock.patch.object(
            backup_module.sqlite3, "connect",
            side_effect=lambda *args, **kwargs: _DamagedConnection(real_connect(*args, **kwargs)),
        ):
            with self.assertRaises(BackupError) as caught:
                validate_app_database(live)

        self.assertIn("integrity check", str(caught.exception))
        self.assertIn("damaged", str(caught.exception))

    def test_an_empty_or_missing_file_is_refused(self):
        empty = self.directory / "empty.sqlite3"
        empty.write_bytes(b"")
        with self.assertRaises(BackupError) as caught:
            validate_app_database(empty)
        self.assertIn("empty", str(caught.exception))

        with self.assertRaises(BackupError) as caught:
            validate_app_database(self.directory / "absent.sqlite3")
        self.assertIn("no file found", str(caught.exception).lower())

    def test_a_symbolic_link_is_refused_in_preference_to_a_link_target(self):
        target = self.directory / "real.sqlite3"
        populate(target)
        link = self.directory / "link.sqlite3"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links are unavailable here: {exc}")

        with self.assertRaises(BackupError) as caught:
            validate_app_database(link)

        self.assertIn("symbolic link", str(caught.exception))

    def test_a_newer_schema_version_is_refused_without_downgrading(self):
        newer = self.directory / "newer.sqlite3"
        populate(newer)
        connection = sqlite3.connect(str(newer))
        connection.execute("PRAGMA user_version = 99")
        connection.commit()
        connection.close()

        with self.assertRaises(BackupError) as caught:
            validate_app_database(newer)

        message = str(caught.exception)
        self.assertIn("newer than this app supports", message)
        self.assertIn("no downgrade", message)
        connection = sqlite3.connect(str(newer))
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99, "the file must not be modified")
        connection.close()

    def test_an_unknown_schema_version_is_refused_rather_than_adopted(self):
        """A file with tables and no recorded schema version is somebody else's database."""
        foreign = self.directory / "foreign.sqlite3"
        connection = sqlite3.connect(str(foreign))
        connection.execute("CREATE TABLE something_else (value TEXT)")
        connection.commit()
        connection.close()

        with self.assertRaises(BackupError) as caught:
            validate_app_database(foreign)

        message = str(caught.exception)
        self.assertIn("does not recognise", message)
        self.assertIn("version 0", message)
        connection = sqlite3.connect(str(foreign))
        self.assertEqual(
            {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")},
            {"something_else"}, "the file must not be modified")
        connection.close()

    def test_a_backup_written_by_an_earlier_schema_version_is_accepted(self):
        """Restoring an older backup is the documented recovery path, so it must not be refused.

        The file is validated against the tables of the version it records, and the version it
        records is what decides that: the current schema's tables are not required of it, because an
        older build never wrote them.
        """
        older = self.directory / "older.sqlite3"
        connection = sqlite3.connect(str(older))
        for statement in (
            "CREATE TABLE candidate_profile (profile_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)",
            "CREATE TABLE job_listings (listing_id TEXT PRIMARY KEY, payload TEXT NOT NULL, duplicate_key TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL)",
            "CREATE TABLE application_tracker (listing_id TEXT PRIMARY KEY REFERENCES job_listings(listing_id) ON DELETE CASCADE, status TEXT NOT NULL, status_evidence TEXT, candidate_confirmed INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)",
            f"PRAGMA user_version = {min(SCHEMA_TABLES_BY_VERSION)}",
        ):
            connection.execute(statement)
        connection.commit()
        connection.close()

        info = validate_app_database(older)

        oldest = min(SCHEMA_TABLES_BY_VERSION)
        self.assertEqual(info.schema_version, oldest)
        self.assertIsNone(info.activity_count, "a schema without an activity log must not report an empty one")
        self.assertNotIn("activity", info.summary())

    def test_an_older_backup_missing_a_table_of_its_own_version_is_refused(self):
        """The version-aware check is not a blanket acceptance: the tables it does claim are required."""
        older = self.directory / "older-partial.sqlite3"
        connection = sqlite3.connect(str(older))
        connection.execute(
            "CREATE TABLE candidate_profile (profile_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
        connection.execute(f"PRAGMA user_version = {min(SCHEMA_TABLES_BY_VERSION)}")
        connection.commit()
        connection.close()

        with self.assertRaises(BackupError) as caught:
            validate_app_database(older)

        message = str(caught.exception)
        self.assertIn("records schema version", message)
        self.assertIn("job_listings", message)

    def test_a_database_missing_a_required_table_is_refused(self):
        partial = self.directory / "partial.sqlite3"
        connection = sqlite3.connect(str(partial))
        connection.executescript(
            "CREATE TABLE candidate_profile (profile_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL);"
        )
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
        connection.close()

        with self.assertRaises(BackupError) as caught:
            validate_app_database(partial)

        self.assertIn("missing the expected table", str(caught.exception))
        self.assertIn("job_listings", str(caught.exception))

    def test_the_required_table_list_matches_the_real_schema(self):
        """If the schema grows, this fails until the backup contract is updated deliberately."""
        live = populate(self.directory / "career_agent.sqlite3")
        connection = sqlite3.connect(str(live))
        try:
            tables = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
        finally:
            connection.close()
        self.assertEqual(tables, set(SCHEMA_TABLES))
        newest = max(SCHEMA_TABLES_BY_VERSION)
        self.assertEqual(newest, SCHEMA_VERSION, "the newest table list must describe the current schema")
        for version, names in sorted(SCHEMA_TABLES_BY_VERSION.items()):
            if version == min(SCHEMA_TABLES_BY_VERSION):
                continue
            previous = SCHEMA_TABLES_BY_VERSION[version - 1]
            self.assertTrue(set(previous) < set(names), f"schema {version} must only add tables")


class RestoreTests(BackupTestCase):
    def prepare(self, *, job_ids=("j1",)):
        live = populate(self.directory / "career_agent.sqlite3", job_ids=job_ids)
        chosen = self.directory / "chosen-backup.sqlite3"
        create_backup(live, chosen, timestamp=STAMP)
        return live, chosen

    def test_a_restore_replaces_profile_jobs_and_tracker_and_reopens_cleanly(self):
        live, chosen = self.prepare()
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("added-after-backup"))
            store.save_tracker(ApplicationTracker("added-after-backup"))

        result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertEqual(result.info.job_count, 1)
        self.assertEqual(result.restored_from, chosen)
        self.assertEqual(result.database_path, live)
        self.assert_no_leftovers(live)
        with CareerStore(str(live)) as store:  # close and reopen: the data must persist exactly
            self.assertEqual(table_rows(live, "candidate_profile"), table_rows(chosen, "candidate_profile"))
            self.assertEqual(table_rows(live, "job_listings"), table_rows(chosen, "job_listings"))
            self.assertEqual(table_rows(live, "application_tracker"), table_rows(chosen, "application_tracker"))
            self.assertEqual([job.listing_id for job in store.list_jobs()], ["j1"])
            self.assertEqual(store.get_profile().degree_discipline, "ECE")
            self.assertEqual(store.get_tracker("j1").status, ApplicationStatus.DISCOVERED)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_the_restored_database_and_the_previous_database_copy_are_owner_only(self):
        live, chosen = self.prepare()

        result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertEqual(self.mode_of(live), 0o600)
        self.assertIsNotNone(result.pre_restore_backup)
        self.assertEqual(self.mode_of(result.pre_restore_backup), 0o600)

    def test_the_current_database_is_preserved_as_a_verified_backup_first(self):
        live, chosen = self.prepare()
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("only-in-the-current-database"))

        result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertTrue(result.pre_restore_verified)
        self.assertEqual(result.pre_restore_backup, automatic_backup_path(live, STAMP))
        preserved = validate_app_database(result.pre_restore_backup)
        self.assertEqual(preserved.job_count, 2, "the copy must hold the state that was replaced")

    def test_the_chosen_backup_file_is_never_modified(self):
        live, chosen = self.prepare()
        before = chosen.read_bytes()
        mode_before = self.mode_of(chosen)

        restore_backup(chosen, live, timestamp=STAMP)

        self.assertEqual(chosen.read_bytes(), before, "restoring must not consume or alter the backup")
        self.assertEqual(self.mode_of(chosen), mode_before)

    def test_a_restore_over_a_database_that_cannot_be_read_keeps_an_unverified_copy(self):
        live, chosen = self.prepare()
        live.write_text("the database is no longer readable", encoding="utf-8")

        result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertFalse(result.pre_restore_verified, "an unreadable database cannot be verified")
        self.assertEqual(result.pre_restore_backup.read_text(encoding="utf-8"), "the database is no longer readable")
        with CareerStore(str(live)) as store:
            self.assertEqual([job.listing_id for job in store.list_jobs()], ["j1"])

    def test_a_restore_into_a_folder_with_no_database_yet_works_and_reports_no_snapshot(self):
        live, chosen = self.prepare()
        live.unlink()

        result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertIsNone(result.pre_restore_backup)
        self.assertEqual(result.info.job_count, 1)

    def test_a_corrupt_backup_is_refused_and_the_current_database_is_untouched(self):
        live, _chosen = self.prepare()
        corrupt = self.directory / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a database at all")
        before = live.read_bytes()

        with self.assertRaises(BackupError) as caught:
            restore_backup(corrupt, live, timestamp=STAMP)

        self.assertIn("not a database", str(caught.exception))
        self.assertEqual(live.read_bytes(), before)
        self.assert_no_leftovers(live)

    def test_a_second_restore_in_the_same_second_keeps_its_own_copy(self):
        """Two restores inside one second must both work, each keeping its own pre-restore copy.

        The automatic snapshot name is timestamped to the second. The second same-second restore used
        to be refused with "the current database could not be preserved", which described the wrong
        problem: the only obstacle was that the first restore had already used that second's name.
        """
        live, chosen = self.prepare()
        first = restore_backup(chosen, live, timestamp=STAMP)
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("changed-again"))

        second = restore_backup(chosen, live, timestamp=STAMP)

        self.assertNotEqual(first.pre_restore_backup, second.pre_restore_backup)
        self.assertEqual(validate_app_database(first.pre_restore_backup).job_count, 1)
        self.assertEqual(validate_app_database(second.pre_restore_backup).job_count, 2,
                         "the second restore must keep the data it actually replaced")
        self.assertEqual(validate_app_database(live).job_count, 1)
        self.assert_no_leftovers(live)

    def test_a_symbolic_link_where_the_database_is_expected_is_refused_untouched(self):
        """A link in place of the live database must not be replaced, and its target must not change.

        Restoring "through" a link would replace whatever the link points at - which may be a file the
        user never chose - so the restore must refuse and name the link.
        """
        live, chosen = self.prepare()
        real = self.directory / "real.sqlite3"
        populate(real, job_ids=("kept",))
        link = self.directory / "linked.sqlite3"
        os.symlink(real, link)
        before = real.read_bytes()

        with self.assertRaises(BackupError) as caught:
            restore_backup(chosen, link, timestamp=STAMP)

        self.assertIn("symbolic link", str(caught.exception))
        self.assertTrue(link.is_symlink(), "the restore must not replace the link with a file")
        self.assertEqual(real.read_bytes(), before, "the link's target must be untouched")
        self.assertEqual(validate_app_database(real).job_count, 1)
        self.assertEqual(validate_app_database(live).job_count, 1)
        self.assert_no_leftovers(live)

    def test_a_folder_where_the_database_is_expected_is_refused_with_a_clear_message(self):
        """Pointing a file dialog at the application's data folder must not create anything."""
        live, chosen = self.prepare()
        folder = self.directory / "the-data-folder.sqlite3"
        folder.mkdir()

        with self.assertRaises(BackupError) as caught:
            restore_backup(chosen, folder, timestamp=STAMP)

        message = str(caught.exception)
        self.assertIn("is a folder, not a database file", message)
        self.assertNotIn("could not be preserved", message)
        self.assertEqual(list(folder.iterdir()), [], "nothing may be created inside the folder")
        self.assertTrue(folder.is_dir())
        self.assertEqual(validate_app_database(live).job_count, 1)
        self.assert_no_leftovers(live)

    def test_an_incompatible_backup_is_refused_and_the_current_database_is_untouched(self):
        live, _chosen = self.prepare()
        newer = self.directory / "newer.sqlite3"
        populate(newer, job_ids=("other",))
        connection = sqlite3.connect(str(newer))
        connection.execute("PRAGMA user_version = 99")
        connection.commit()
        connection.close()
        before = live.read_bytes()

        with self.assertRaises(BackupError) as caught:
            restore_backup(newer, live, timestamp=STAMP)

        self.assertIn("newer than this app supports", str(caught.exception))
        self.assertEqual(live.read_bytes(), before)

    def test_a_restore_is_refused_while_another_connection_holds_the_database(self):
        live, chosen = self.prepare()
        holder = sqlite3.connect(str(live), isolation_level=None)
        self.addCleanup(holder.close)
        holder.execute("BEGIN")
        holder.execute("SELECT count(*) FROM job_listings").fetchone()
        before = live.read_bytes()

        with mock.patch.object(backup_module, "LOCK_TIMEOUT_SECONDS", 0.2):
            with self.assertRaises(BackupError) as caught:
                restore_backup(chosen, live, timestamp=STAMP)

        self.assertIn("in use", str(caught.exception))
        self.assertEqual(live.read_bytes(), before)
        self.assert_no_leftovers(live)

    def test_a_restore_is_refused_while_another_connection_write_locks_the_database(self):
        """Busy must not be mistaken for "unreadable and therefore safe to copy raw"."""
        live, chosen = self.prepare()
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("must-survive"))
        before = live.read_bytes()
        holder = sqlite3.connect(str(live), isolation_level=None)
        self.addCleanup(holder.close)
        holder.execute("BEGIN EXCLUSIVE")

        with mock.patch.object(backup_module, "LOCK_TIMEOUT_SECONDS", 0.2):
            with self.assertRaises(BackupError) as caught:
                restore_backup(chosen, live, timestamp=STAMP)

        self.assertIn("in use", str(caught.exception).lower())
        self.assertEqual(live.read_bytes(), before)
        self.assertFalse(automatic_backup_path(live, STAMP).exists(), "no raw copy may be taken while busy")
        self.assert_no_leftovers(live)
        holder.execute("ROLLBACK")
        with CareerStore(str(live)) as store:
            self.assertEqual(len(store.list_jobs()), 2, "the current database is still the one in use")

    def test_a_write_attempted_during_the_swap_is_refused_rather_than_silently_discarded(self):
        """The window between the last readiness check and ``os.replace`` is the one that loses data.

        Reproduced before this change: a second connection could begin *and commit* a transaction
        inside that window; the commit reported success, and the replacement then discarded the file
        holding it, so the write disappeared with no error anywhere. The swap now holds the database's
        exclusive lock, so a competing writer is refused ("database is locked") instead of winning and
        being erased. The restore itself still succeeds.
        """
        live, chosen = self.prepare()
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("added-after-backup"))
        real_replace = backup_module.os.replace
        outcomes = []

        def replace_while_a_writer_tries(source, destination):
            writer = sqlite3.connect(str(live), isolation_level=None, timeout=0.2)
            try:
                writer.execute("BEGIN IMMEDIATE")
                writer.execute("UPDATE application_tracker SET status='shortlisted' WHERE listing_id='j1'")
                writer.execute("COMMIT")
                outcomes.append("accepted")
            except sqlite3.Error as exc:
                outcomes.append(f"refused: {exc}")
            finally:
                writer.close()
            return real_replace(source, destination)

        with mock.patch.object(backup_module.os, "replace", replace_while_a_writer_tries):
            result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertEqual(len(outcomes), 1, "the writer must have been attempted exactly once")
        self.assertTrue(outcomes[0].startswith("refused"),
                        f"the competing write was not refused, so it was silently discarded: {outcomes[0]}")
        self.assertEqual(result.info.job_count, 1)
        self.assert_no_leftovers(live)
        with CareerStore(str(live)) as store:
            self.assertEqual([job.listing_id for job in store.list_jobs()], ["j1"])
            self.assertEqual(store.get_tracker("j1").status, ApplicationStatus.DISCOVERED,
                             "the restored row, not the discarded write")

    def test_where_the_platform_cannot_replace_an_open_file_the_guard_is_released_before_the_swap(self):
        """The guard cannot be held across the swap on Windows: its own handle blocks the replacement.

        SQLite opens its database files without ``FILE_SHARE_DELETE``, so ``os.replace`` on a database
        this process is holding open fails with a sharing violation there - which would break every
        restore. The guard is therefore released immediately before the swap on such a platform, and
        this test pins that: inside the replacement the database must be writable again, and the
        restore must still complete. The counterpart test above pins the opposite on a platform where
        the guard can be kept, so neither behaviour can regress into the other unnoticed.
        """
        live, chosen = self.prepare()
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("added-after-backup"))
        real_replace = backup_module.os.replace
        unlocked_during_the_swap = []

        def replace_after_probing_the_lock(source, destination):
            probe = sqlite3.connect(str(live), isolation_level=None, timeout=0.2)
            try:
                probe.execute("BEGIN IMMEDIATE")  # only possible if no guard is still held
                probe.execute("ROLLBACK")
                unlocked_during_the_swap.append(True)
            except sqlite3.Error as exc:
                unlocked_during_the_swap.append(f"still locked: {exc}")
            finally:
                probe.close()
            return real_replace(source, destination)

        with mock.patch.object(backup_module, "_CAN_REPLACE_AN_OPEN_FILE", False), \
                mock.patch.object(backup_module.os, "replace", replace_after_probing_the_lock):
            result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertEqual(unlocked_during_the_swap, [True],
                         "the guard must be released before the replacement on such a platform")
        self.assertEqual(result.info.job_count, 1)
        self.assert_no_leftovers(live)
        with CareerStore(str(live)) as store:
            self.assertEqual([job.listing_id for job in store.list_jobs()], ["j1"])

    def test_an_idle_connection_is_not_detected_and_sqlite_refuses_its_next_write(self):
        """Documents the limit of the coordination rather than claiming what it cannot establish.

        A connection that is open but idle holds **no** SQLite lock, so no check in this module can
        find it and the restore is not refused (refusing here would be a claim the code cannot
        support). What is verified is the resulting behaviour: the restore proceeds, the idle
        connection keeps the view it had before the swap, and its next write is refused by SQLite
        itself (``SQLITE_READONLY``) rather than silently landing in a file nobody can see again.
        """
        live, chosen = self.prepare()
        idle = sqlite3.connect(str(live), isolation_level=None)
        self.addCleanup(idle.close)
        rows_before = idle.execute("SELECT listing_id FROM job_listings ORDER BY listing_id").fetchall()

        result = restore_backup(chosen, live, timestamp=STAMP)  # not refused: an idle connection is invisible

        self.assertEqual(result.info.job_count, 1)
        self.assertEqual(idle.execute("SELECT listing_id FROM job_listings ORDER BY listing_id").fetchall(),
                         rows_before, "the idle connection keeps its own view of the replaced file")
        with self.assertRaises(sqlite3.OperationalError) as caught:
            idle.execute("UPDATE application_tracker SET status='shortlisted' WHERE listing_id='j1'")
        self.assertIn("readonly", str(caught.exception).lower(),
                      "SQLite itself refuses the stale connection, which is the honest guarantee here")
        with CareerStore(str(live)) as store:
            self.assertEqual(store.get_tracker("j1").status, ApplicationStatus.DISCOVERED)

    def test_a_restore_is_refused_when_the_current_database_cannot_be_preserved(self):
        live, chosen = self.prepare()
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("must-survive"))
        before = live.read_bytes()

        with mock.patch.object(backup_module, "create_backup", side_effect=BackupError("simulated failure")):
            with self.assertRaises(BackupError) as caught:
                restore_backup(chosen, live, timestamp=STAMP)

        self.assertIn("could not be preserved", str(caught.exception))
        self.assertEqual(live.read_bytes(), before)
        self.assert_no_leftovers(live)

    def test_a_failed_replacement_leaves_the_current_database_in_place(self):
        live, chosen = self.prepare()
        before = live.read_bytes()

        with mock.patch.object(backup_module.os, "replace", side_effect=OSError(13, "Permission denied")):
            with self.assertRaises(BackupError) as caught:
                restore_backup(chosen, live, timestamp=STAMP)

        self.assertIn("could not be replaced", str(caught.exception))
        self.assertEqual(live.read_bytes(), before)
        self.assert_no_leftovers(live)

    def test_a_failed_post_install_check_puts_the_previous_database_back(self):
        live, chosen = self.prepare()
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("only-in-the-current-database"))
        before_rows = table_rows(live, "job_listings")
        real_validate = backup_module.validate_app_database
        live_reads = {"count": 0}

        def failing_final_check(path):
            if Path(path) == live:
                live_reads["count"] += 1
                if live_reads["count"] == 3:  # readability pre-check, snapshot source, post-install re-read
                    raise BackupError("simulated corruption after the swap")
            return real_validate(path)

        with mock.patch.object(backup_module, "validate_app_database", side_effect=failing_final_check):
            with self.assertRaises(BackupError) as caught:
                restore_backup(chosen, live, timestamp=STAMP)

        message = str(caught.exception)
        self.assertIn("could not be confirmed usable", message)
        self.assertIn("was put back", message)
        # The database is copied back through SQLite, so compare what it holds, not its page layout.
        self.assertEqual(table_rows(live, "job_listings"), before_rows)
        self.assertIn("only-in-the-current-database", " ".join(table_rows(live, "job_listings")))
        self.assertEqual(len(table_rows(live, "job_listings")), 2, "the previous database must be back")
        self.assert_no_leftovers(live)
        self.assertTrue(automatic_backup_path(live, STAMP).exists(), "the snapshot must be kept for the user")
        validate_app_database(automatic_backup_path(live, STAMP))

    def test_stale_wal_side_files_do_not_survive_a_restore(self):
        """A stale -wal replayed onto a replaced database silently discards the restored data.

        The database here is left in exactly that state: a writer commits in WAL format and is killed
        before SQLite can checkpoint, so ``-wal``/``-shm`` remain beside the main file.
        """
        live, chosen = self.prepare()
        writer = subprocess.run(
            [sys.executable, "-c", (
                "import os, sqlite3, sys\n"
                "conn = sqlite3.connect(sys.argv[1])\n"
                "conn.execute('PRAGMA journal_mode=WAL')\n"
                "conn.execute(\"INSERT INTO job_listings VALUES ('in-the-wal', '{}', 'k', '2026-01-01', '2026-01-01')\")\n"
                "conn.commit()\n"
                "print('committed', flush=True)\n"
                "os._exit(9)\n"      # no clean close: the -wal file is left holding committed rows
            ), str(live)],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]),
        )
        self.assertEqual(writer.stdout.strip(), "committed", writer.stderr)
        self.assertTrue((self.directory / "career_agent.sqlite3-wal").exists(), "precondition: a -wal is present")

        result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertFalse((self.directory / "career_agent.sqlite3-wal").exists(), "no stale -wal may survive")
        self.assertFalse((self.directory / "career_agent.sqlite3-shm").exists(), "no stale -shm may survive")
        with CareerStore(str(live)) as store:
            self.assertEqual([job.listing_id for job in store.list_jobs()], ["j1"], "the restored data must survive")
        # The rows that only existed in the -wal file are preserved in the snapshot, not silently lost.
        self.assertTrue(result.pre_restore_verified, "a WAL database must still yield a verified snapshot")
        self.assertEqual(validate_app_database(result.pre_restore_backup).job_count, 2)

    def test_stale_side_files_never_survive_a_restore_and_are_preserved_in_the_snapshot(self):
        """A stale side file beside the *new* database is the corruption this guards against."""
        live, chosen = self.prepare()
        live.write_text("this database cannot be read, so its side files are kept verbatim")
        stale = {suffix: f"stale {suffix} left by another tool".encode() for suffix in ("-journal", "-wal", "-shm")}
        for suffix, payload in stale.items():
            Path(f"{live}{suffix}").write_bytes(payload)

        result = restore_backup(chosen, live, timestamp=STAMP)

        for suffix in stale:
            self.assertFalse(Path(f"{live}{suffix}").exists(), f"a stale {suffix} must not survive the swap")
        self.assertFalse(result.pre_restore_verified)
        self.assertIsNotNone(result.pre_restore_backup)
        for suffix, payload in stale.items():
            preserved = Path(f"{result.pre_restore_backup}{suffix}")
            self.assertTrue(preserved.exists(), f"the {suffix} bytes must be preserved, not discarded")
            self.assertEqual(preserved.read_bytes(), payload)
        with CareerStore(str(live)) as store:
            self.assertEqual([job.listing_id for job in store.list_jobs()], ["j1"])

    def test_an_opener_before_the_side_files_are_removed_never_sees_the_old_rows(self):
        """The ordering (snapshot, swap, then remove) must not expose the previous database's rows.

        The snapshot needs the old side files, so they can only be removed after the replacement - and
        that leaves an instant in which the new main file sits beside the old database's ``-wal``. An
        opener arriving exactly there must still see the restored data, never a row that only existed
        in the previous database. What delivered that in this run is SQLite itself: the stale ``-wal``
        records a change counter that no longer matches the replaced file, so SQLite discards it
        (measured during the review; ``test_stale_wal_side_files_do_not_survive_a_restore`` covers the
        removal this module is responsible for). The test is kept as a guard on the ordering: if a
        future change removes the side files before the snapshot, or stops removing them, this is where
        it should surface.
        """
        live, chosen = self.prepare()
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("added-after-backup"))
        writer = subprocess.run(
            [sys.executable, "-c", (
                "import os, sqlite3, sys\n"
                "conn = sqlite3.connect(sys.argv[1])\n"
                "conn.execute('PRAGMA journal_mode=WAL')\n"
                "conn.execute(\"INSERT INTO job_listings VALUES ('in-the-wal', '{}', 'k', '2026-01-01', '2026-01-01')\")\n"
                "conn.commit()\n"
                "print('committed', flush=True)\n"
                "os._exit(9)\n"
            ), str(live)],
            capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]),
        )
        self.assertEqual(writer.stdout.strip(), "committed", writer.stderr)
        self.assertTrue((self.directory / "career_agent.sqlite3-wal").exists(), "precondition: a -wal is present")
        seen = {}
        real_remove = backup_module._remove_sidecars

        def remove_after_a_concurrent_opener_looks(database_path):
            opener = sqlite3.connect(str(database_path))
            try:
                seen["rows"] = sorted(row[0] for row in opener.execute("SELECT listing_id FROM job_listings"))
            finally:
                opener.close()
            return real_remove(database_path)

        with mock.patch.object(backup_module, "_remove_sidecars", remove_after_a_concurrent_opener_looks):
            result = restore_backup(chosen, live, timestamp=STAMP)

        self.assertEqual(seen.get("rows"), ["j1"],
                         "an opener in that window saw rows that do not exist in the restored database")
        self.assertNotIn("in-the-wal", seen.get("rows") or [])
        self.assertEqual(result.info.job_count, 1)
        self.assert_no_leftovers(live)

    def test_side_file_cleanup_removes_and_reports_every_side_file(self):
        live = populate(self.directory / "career_agent.sqlite3")
        sidecars = [Path(f"{live}{suffix}") for suffix in ("-journal", "-wal", "-shm")]
        for path in sidecars:
            path.write_bytes(b"stale")

        removed = backup_module._remove_sidecars(live)

        self.assertEqual(set(removed), set(sidecars))
        for path in sidecars:
            self.assertFalse(path.exists())
        self.assertEqual(backup_module._remove_sidecars(live), (), "nothing left to remove")

    def test_a_backup_with_dangling_tracker_rows_is_still_restorable(self):
        """The anomaly is reported, not hidden, and does not block recovery."""
        live, _chosen = self.prepare()
        foreign = self.directory / "dangling.sqlite3"
        populate(foreign)
        connection = sqlite3.connect(str(foreign))
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO application_tracker VALUES ('missing-listing', 'discovered', NULL, 0, '2026-01-01')"
        )
        connection.commit()
        connection.close()
        info = validate_app_database(foreign)
        self.assertEqual(info.foreign_key_violations, 1)

        result = restore_backup(foreign, live, timestamp=STAMP)

        self.assertEqual(result.info.job_count, 1)


class CommandLineTests(BackupTestCase):
    """The headless path exists for the case the window cannot open: a database that cannot be read."""

    def run_cli(self, arguments):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli_main(arguments)
        return code, out.getvalue(), err.getvalue()

    def test_backup_reports_the_verified_file_and_the_contents(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "cli-backup.sqlite3"

        code, out, err = self.run_cli(["--database", str(live), "--backup-to", str(destination)])

        self.assertEqual(code, 0, err)
        self.assertIn("written and verified", out)
        self.assertIn("1 job", out)
        self.assertTrue(destination.exists())

    def test_backup_refuses_to_overwrite_and_says_so(self):
        live = populate(self.directory / "career_agent.sqlite3")
        destination = self.directory / "taken.sqlite3"
        destination.write_text("older backup", encoding="utf-8")

        code, _out, err = self.run_cli(["--database", str(live), "--backup-to", str(destination)])

        self.assertEqual(code, 2)
        self.assertIn("REFUSED", err)
        self.assertEqual(destination.read_text(encoding="utf-8"), "older backup")

    def test_restore_without_confirmation_is_refused_and_changes_nothing(self):
        live = populate(self.directory / "career_agent.sqlite3")
        chosen = self.directory / "chosen-backup.sqlite3"
        create_backup(live, chosen, timestamp=STAMP)
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("added-later"))
        before = live.read_bytes()

        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            code, out, err = self.run_cli(["--database", str(live), "--restore-from", str(chosen)])

        self.assertEqual(code, 2)
        self.assertIn("REFUSED", err)
        self.assertIn("Cancelled", out)
        self.assertEqual(live.read_bytes(), before)

    def test_restore_with_confirmation_replaces_the_database_and_keeps_the_previous_one(self):
        live = populate(self.directory / "career_agent.sqlite3")
        chosen = self.directory / "chosen-backup.sqlite3"
        create_backup(live, chosen, timestamp=STAMP)
        with CareerStore(str(live)) as store:
            store.save_job(sample_job("added-later"))

        code, out, err = self.run_cli(["--database", str(live), "--restore-from", str(chosen), "--yes"])

        self.assertEqual(code, 0, err)
        self.assertIn("Previous database kept as a verified copy", out)
        with CareerStore(str(live)) as store:
            self.assertEqual([job.listing_id for job in store.list_jobs()], ["j1"])

    def test_restore_refuses_a_corrupt_file_with_a_clear_message(self):
        live = populate(self.directory / "career_agent.sqlite3")
        corrupt = self.directory / "corrupt.sqlite3"
        corrupt.write_text("nope", encoding="utf-8")

        code, _out, err = self.run_cli(["--database", str(live), "--restore-from", str(corrupt), "--yes"])

        self.assertEqual(code, 2)
        self.assertIn("REFUSED", err)
        self.assertIn("not a database", err)

    def test_the_two_actions_cannot_be_combined(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_cli(["--backup-to", "a.sqlite3", "--restore-from", "b.sqlite3"])
        self.assertEqual(caught.exception.code, 2)

    def test_suggested_names_are_timestamped_and_distinct(self):
        self.assertTrue(suggested_backup_name(STAMP).startswith("career_agent-backup-20261014T120000Z"))
        self.assertNotEqual(suggested_backup_name(STAMP), suggested_backup_name(datetime(2026, 10, 14, 12, 0, 1, tzinfo=timezone.utc)))


class RepositoryHygieneTests(BackupTestCase):
    """Candidate data must not be able to reach source control, by accident or otherwise."""

    def check_ignored(self, name):
        repository = Path(__file__).resolve().parents[1]
        if not (repository / ".git").exists():
            self.skipTest("not a git working tree")
        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", name], cwd=str(repository),
                capture_output=True, text=True,
            )
        except FileNotFoundError:
            self.skipTest("git is not installed")
        if result.returncode not in (0, 1):
            self.skipTest(f"git check-ignore is unavailable here: {result.stderr.strip()}")
        return result.returncode == 0

    def test_every_file_this_module_writes_is_ignored_by_git(self):
        database = Path("career_agent.sqlite3")
        names = [
            suggested_backup_name(STAMP),
            automatic_backup_path(database, STAMP).name,
            f".{database.name}.restore-20261014T120000Z.partial",
            f"{database.name}-wal",
            f"{database.name}-journal",
            f"{database.name}-shm",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(self.check_ignored(name), f"{name} would be committable by accident")

    def test_an_ordinary_repository_file_is_not_ignored(self):
        if not self.check_ignored("career_agent-backup-20261014T120000Z.sqlite3"):
            self.skipTest("git ignore rules are unavailable here")
        self.assertFalse(self.check_ignored("README.md"), "the ignore rules must stay narrow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
