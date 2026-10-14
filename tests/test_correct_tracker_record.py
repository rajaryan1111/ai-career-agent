"""Tests for scripts/correct_tracker_record.py — the safe local correction tool.

The tool exists so a mistaken tracker state can be made truthful without editing SQL by hand. These
tests build their own throwaway file-backed databases; they never touch a real user database and
make no network calls. They verify dry-run behavior, backups, refusal paths, and that the correction
is durable and does not touch anything else.
"""
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from career_agent import ApplicationStatus, ApplicationTracker, Availability, JobListing
from career_agent.backup import validate_app_database
from career_agent.store import CareerStore

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import correct_tracker_record as correction  # noqa: E402

LISTING_ID = "smoke-test-listing"
REASON = (
    "Fictional smoke-test record: no application was ever submitted, so the earlier confirmed "
    "state was a testing error and is not evidence of an application."
)


def build_database(directory: Path, *, confirmed_evidence: str = "TODO") -> Path:
    """Create a database shaped as reported: a fictional job left 'confirmed' by a smoke test."""
    path = directory / "career_agent.sqlite3"
    with CareerStore(str(path)) as store:
        store.save_job(JobListing(
            listing_id=LISTING_ID, source_id="manual", source_name="Manual entry",
            source_listing_url="https://example.com/jobs/ai-ml-intern",
            employer_name="Example Test Company", role_title="AI/ML Intern",
            availability_status=Availability.UNKNOWN, eligibility_scope="restricted",
            canonical_requisition_id="TEST-001",
        ))
        store.save_tracker(ApplicationTracker(LISTING_ID))
        for status in (
            ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
            ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.SUBMITTED_UNVERIFIED,
        ):
            tracker = store.get_tracker(LISTING_ID).transition(status)
            store.save_tracker(tracker)
        # The row an earlier build could have written, seeded directly because the current write
        # path correctly refuses to create it.
        with store._connection:
            store._connection.execute(
                "UPDATE application_tracker SET status=?, status_evidence=?, candidate_confirmed=1 "
                "WHERE listing_id=?",
                (ApplicationStatus.CONFIRMED.value, confirmed_evidence, LISTING_ID),
            )
    return path


def run(arguments) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = correction.main(arguments)
    return code, out.getvalue(), err.getvalue()


class CorrectionTestCase(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = Path(self._directory.name)
        self.database = build_database(self.directory)

    def base_arguments(self, *extra):
        return [
            "--database", str(self.database),
            "--listing-id", LISTING_ID,
            "--to", ApplicationStatus.WITHDRAWN.value,
            "--reason", REASON,
            *extra,
        ]

    def read_row(self):
        return correction.read_row(self.database, LISTING_ID)

    def backups(self):
        return sorted(self.directory.glob(f"{self.database.name}.backup-*"))


class DryRunTests(CorrectionTestCase):
    def test_dry_run_reports_the_change_and_writes_nothing(self):
        code, output, _ = run(self.base_arguments("--clear-confirmation"))
        self.assertEqual(code, correction.EXIT_OK)
        self.assertIn("DRY RUN", output)
        self.assertIn("Nothing was written", output)
        self.assertEqual(self.backups(), [])
        row = self.read_row()
        self.assertEqual(row["status"], ApplicationStatus.CONFIRMED.value)
        self.assertEqual(row["status_evidence"], "TODO")
        self.assertEqual(row["candidate_confirmed"], 1)

    def test_dry_run_refuses_a_transition_the_state_machine_forbids(self):
        code, _, error = run([
            "--database", str(self.database), "--listing-id", LISTING_ID,
            "--to", ApplicationStatus.SUBMITTED_UNVERIFIED.value, "--reason", REASON,
        ])
        self.assertEqual(code, correction.EXIT_REFUSED)
        self.assertIn("does not permit", error)
        self.assertIn("Nothing was written", error)
        self.assertEqual(self.read_row()["status"], ApplicationStatus.CONFIRMED.value)

    def test_dry_run_refuses_a_record_that_is_already_in_the_target_state(self):
        code, _, error = run([
            "--database", str(self.database), "--listing-id", LISTING_ID,
            "--to", ApplicationStatus.CONFIRMED.value, "--reason", REASON,
        ])
        self.assertEqual(code, correction.EXIT_REFUSED)
        self.assertIn("already", error)


class RefusalTests(CorrectionTestCase):
    def test_a_placeholder_reason_is_refused(self):
        for reason in ("", "   ", "todo", "n/a", "A confirmed application requires evidence."):
            with self.subTest(reason=reason):
                code, _, error = run([
                    "--database", str(self.database), "--listing-id", LISTING_ID,
                    "--to", ApplicationStatus.WITHDRAWN.value, "--reason", reason,
                ])
                self.assertEqual(code, correction.EXIT_REFUSED)
                self.assertIn("Nothing was written", error)
                self.assertEqual(self.read_row()["status"], ApplicationStatus.CONFIRMED.value)

    def test_an_unknown_listing_id_is_refused(self):
        code, _, error = run([
            "--database", str(self.database), "--listing-id", "no-such-listing",
            "--to", ApplicationStatus.WITHDRAWN.value, "--reason", REASON,
        ])
        self.assertEqual(code, correction.EXIT_REFUSED)
        self.assertIn("No tracker row exists", error)
        self.assertEqual(self.backups(), [])

    def test_a_missing_database_is_refused(self):
        code, _, error = run([
            "--database", str(self.directory / "absent.sqlite3"), "--listing-id", LISTING_ID,
            "--to", ApplicationStatus.WITHDRAWN.value, "--reason", REASON,
        ])
        self.assertEqual(code, correction.EXIT_REFUSED)
        self.assertIn("Database not found", error)

    def test_confirming_through_this_tool_is_refused(self):
        """A confirmation must be recorded in the app, where the assertion is deliberate."""
        # The seeded record is already 'confirmed', which is exactly the state to refuse re-asserting.
        code, _, error = run([
            "--database", str(self.database), "--listing-id", LISTING_ID,
            "--to", ApplicationStatus.CONFIRMED.value, "--reason", REASON,
        ])
        self.assertEqual(code, correction.EXIT_REFUSED)
        self.assertIn("already", error)


class ApplyTests(CorrectionTestCase):
    def test_apply_writes_a_backup_then_the_corrected_record(self):
        code, output, _ = run(self.base_arguments("--clear-confirmation", "--apply"))
        self.assertEqual(code, correction.EXIT_OK)
        self.assertIn("Correction applied and verified", output)

        backups = self.backups()
        self.assertEqual(len(backups), 1, "exactly one backup must be written")

        row = self.read_row()
        self.assertEqual(row["status"], ApplicationStatus.WITHDRAWN.value)
        self.assertEqual(row["status_evidence"], REASON)
        self.assertEqual(row["candidate_confirmed"], 0)

        # The backup preserves the original, misleading state for the audit trail.
        original = correction.read_row(backups[0], LISTING_ID)
        self.assertEqual(original["status"], ApplicationStatus.CONFIRMED.value)
        self.assertEqual(original["status_evidence"], "TODO")
        self.assertEqual(original["candidate_confirmed"], 1)

    def test_apply_without_clearing_keeps_an_existing_confirmation_flag(self):
        code, _, _ = run(self.base_arguments("--apply"))
        self.assertEqual(code, correction.EXIT_OK)
        row = self.read_row()
        self.assertEqual(row["status"], ApplicationStatus.WITHDRAWN.value)
        self.assertEqual(row["candidate_confirmed"], 1, "the flag is only cleared when asked")

    def test_the_correction_does_not_touch_the_listing_or_other_rows(self):
        with CareerStore(str(self.database)) as store:
            store.save_job(JobListing(
                listing_id="other-listing", source_id="manual", source_name="Manual entry",
                source_listing_url="https://example.com/jobs/other", employer_name="Other Employer",
                role_title="Other Role", availability_status=Availability.UNKNOWN,
            ))
            store.save_tracker(ApplicationTracker("other-listing"))
        code, _, _ = run(self.base_arguments("--clear-confirmation", "--apply"))
        self.assertEqual(code, correction.EXIT_OK)

        self.assertEqual(len(self.read_row()), 5)
        with CareerStore(str(self.database)) as store:
            jobs = {job.listing_id for job in store.list_jobs()}
            other = store.get_tracker("other-listing")
        self.assertEqual(jobs, {LISTING_ID, "other-listing"})
        self.assertEqual(other, ApplicationTracker("other-listing"))

    def test_the_corrected_record_survives_reopening(self):
        run(self.base_arguments("--clear-confirmation", "--apply"))
        connection = sqlite3.connect(str(self.database))
        try:
            row = connection.execute(
                "SELECT status, status_evidence, candidate_confirmed FROM application_tracker WHERE listing_id=?",
                (LISTING_ID,),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row[0], ApplicationStatus.WITHDRAWN.value)
        self.assertEqual(row[1], REASON)
        self.assertEqual(row[2], 0)

    def test_the_corrected_record_is_terminal_and_cannot_be_reopened_backwards(self):
        run(self.base_arguments("--clear-confirmation", "--apply"))
        with CareerStore(str(self.database)) as store:
            stored = store.get_tracker(LISTING_ID)
            with self.assertRaises(ValueError):
                store.save_tracker(stored.transition(ApplicationStatus.SUBMITTED_UNVERIFIED, evidence="undo"))


    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_the_snapshot_written_before_a_change_is_owner_only(self):
        """The snapshot holds the whole database, so it must not be readable by other accounts."""
        code, _out, _err = run(self.apply_arguments())
        self.assertEqual(code, correction.EXIT_OK)
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_the_snapshot_is_verified_before_the_change_is_attempted(self):
        code, out, _err = run(self.apply_arguments())
        self.assertEqual(code, correction.EXIT_OK)
        self.assertIn("written and verified", out)
        snapshot = validate_app_database(self.backups()[0])
        self.assertEqual(snapshot.job_count, 1, "the snapshot must be a readable database with the listing")

    def test_an_existing_snapshot_is_never_overwritten(self):
        """A second run in the same second must refuse rather than destroy the earlier snapshot."""
        taken = self.directory / f"{self.database.name}.backup-taken"
        taken.write_text("an earlier snapshot that must survive", encoding="utf-8")
        with mock.patch.object(correction, "automatic_backup_path", return_value=taken):
            code, _out, err = run(self.apply_arguments())

        self.assertEqual(code, correction.EXIT_REFUSED)
        self.assertIn("already exists", err)
        self.assertEqual(taken.read_text(encoding="utf-8"), "an earlier snapshot that must survive")
        self.assertEqual(correction.read_row(self.database, LISTING_ID)["status"], "confirmed",
                         "a refused backup must leave the record untouched")

    def apply_arguments(self):
        """The arguments a real --apply correction uses (dry run unless --apply is present)."""
        return [
            "--database", str(self.database), "--listing-id", LISTING_ID, "--to", "withdrawn",
            "--reason", REASON, "--clear-confirmation", "--apply",
        ]


if __name__ == "__main__":
    unittest.main(verbosity=2)
