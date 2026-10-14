import os
import sqlite3
import stat
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from datetime import date

from career_agent import ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, JobListing
from career_agent.core import ActivityKind, ApplicationActivity
import career_agent.store as store_module
from career_agent.core import duplicate_key
from career_agent.backup import BackupError, validate_app_database
from career_agent.store import (
    SCHEMA_TABLES_BY_VERSION, SCHEMA_VERSION, CareerStore, PrivateWriteError, SchemaMigrationError,
    SchemaTooNewError, SchemaUpgradeRefused, StaleTrackerRecord, StoredRecordError, TrackerStatusError,
    UnrecognisedDatabaseError, create_private_file, require_owner_only, write_private_text_file,
)

#: A fixed, clearly local timestamp so a test never depends on the clock.
_TIMESTAMP = "2026-01-01T00:00:00+00:00"


def sample_job(listing_id="j1", **overrides):
    """A minimal saved listing; only the fields a test is about are overridden."""
    values = dict(
        listing_id=listing_id, source_id="manual", source_name="Manual entry",
        source_listing_url=f"https://jobs.example/role/{listing_id}", employer_name="Example",
        role_title="AI Intern", availability_status=Availability.OPEN,
    )
    values.update(overrides)
    return JobListing(**values)

#: Permitted path used by tests that need an already-advanced record.
_PATH_TO_SUBMISSION = (
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.PREPARED,
    ApplicationStatus.AWAITING_USER,
    ApplicationStatus.SUBMISSION_ATTEMPTED,
)
CONFIRMATION_EVIDENCE = "Employer confirmation email"


def reach_status(store, target, listing_id="j1", *, evidence=None):
    """Advance a tracker from ``discovered`` to ``target`` through permitted transitions.

    Test scaffolding only: it saves the initial record and then moves one permitted step at
    a time, so tests exercise the same path the application uses instead of writing an
    arbitrary first status.
    """
    tracker = ApplicationTracker(listing_id)
    store.save_tracker(tracker)
    if target is ApplicationStatus.DISCOVERED:
        return tracker
    for status in _PATH_TO_SUBMISSION:
        tracker = tracker.transition(status)
        store.save_tracker(tracker)
        if status is target:
            return tracker
    if target is ApplicationStatus.CONFIRMED:
        tracker = tracker.transition(
            ApplicationStatus.CONFIRMED, evidence=evidence or CONFIRMATION_EVIDENCE, candidate_confirmed=True
        )
        store.save_tracker(tracker)
        return tracker
    raise AssertionError(f"reach_status does not support {target}")


class CareerStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = CareerStore(":memory:")
        self.job = JobListing(
            listing_id="j1", source_id="s1", source_name="test",
            source_listing_url="https://jobs.example/role/1", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN,
            employer_apply_url="https://employer.example/apply/1", eligibility_scope="restricted",
            eligible_countries=("India",), allowed_work_authorizations=("authorized_without_sponsorship",), allowed_degree_disciplines=("ECE",),
            allowed_study_statuses=("undergraduate",), allowed_graduation_years=(2027,),
            required_skills=frozenset({"Python", "RAG"}), provenance_note="Manually checked test listing.",
        )

    def tearDown(self):
        self.store.close()

    def test_profile_round_trip_and_delete(self):
        profile = CandidateProfile(candidate_country="India", degree_discipline="ECE", skills=frozenset({"Python", "RAG"}))
        self.assertIsNone(self.store.get_profile())
        self.store.save_profile(profile)
        self.assertEqual(self.store.get_profile(), profile)
        self.assertTrue(self.store.delete_profile())
        self.assertIsNone(self.store.get_profile())
        self.assertFalse(self.store.delete_profile())

    def test_legacy_job_payload_defaults_new_authorization_field(self):
        import json
        payload = json.dumps({
            "listing_id": "legacy", "source_id": "manual", "source_name": "Manual",
            "source_listing_url": "https://jobs.example/legacy", "employer_name": "Example",
            "role_title": "Legacy role", "availability_status": "unknown",
        })
        loaded = self.store._decode_job(payload)
        self.assertIsNone(loaded.allowed_work_authorizations)
        self.assertEqual(loaded.eligible_countries, ())

    def test_job_round_trip_keeps_source_and_apply_urls_separate(self):
        self.store.save_job(self.job, observed_at="2026-10-14T00:00:00+00:00")
        loaded = self.store.get_job("j1")
        self.assertEqual(loaded, self.job)
        self.assertNotEqual(loaded.source_listing_url, loaded.employer_apply_url)

    def test_upsert_preserves_first_seen_and_updates_listing(self):
        self.store.save_job(self.job, observed_at="2026-10-14T00:00:00+00:00")
        updated = JobListing(**{**self.job.__dict__, "role_title": "AI/ML Intern"})
        self.store.save_job(updated, observed_at="2026-10-15T00:00:00+00:00")
        self.assertEqual(self.store.get_job("j1").role_title, "AI/ML Intern")
        row = self.store._connection.execute("SELECT first_seen_at, last_seen_at FROM job_listings WHERE listing_id='j1'").fetchone()
        self.assertEqual(row["first_seen_at"], "2026-10-14T00:00:00+00:00")
        self.assertEqual(row["last_seen_at"], "2026-10-15T00:00:00+00:00")

    def test_status_filter_does_not_treat_unknown_as_open(self):
        self.store.save_job(self.job)
        unknown = JobListing(**{**self.job.__dict__, "listing_id": "j2", "availability_status": Availability.UNKNOWN})
        self.store.save_job(unknown)
        self.assertEqual([j.listing_id for j in self.store.list_jobs(status=Availability.OPEN)], ["j1"])
        self.assertEqual([j.listing_id for j in self.store.list_jobs(status=Availability.UNKNOWN)], ["j2"])

    def test_tracker_requires_existing_job(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.DISCOVERED)
        with self.assertRaises(ValueError):
            self.store.save_tracker(tracker)
        self.store.save_job(self.job)
        self.store.save_tracker(tracker)
        self.assertEqual(self.store.get_tracker("j1"), tracker)

    def test_deleting_job_cascades_tracker(self):
        self.store.save_job(self.job)
        self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.DISCOVERED))
        self.assertTrue(self.store.delete_job("j1"))
        self.assertIsNone(self.store.get_tracker("j1"))

    def test_confirmation_evidence_and_flag_persist(self):
        self.store.save_job(self.job)
        saved = reach_status(self.store, ApplicationStatus.CONFIRMED)
        self.assertEqual(self.store.get_tracker("j1"), saved)
        self.assertEqual(saved.status_evidence, CONFIRMATION_EVIDENCE)
        self.assertTrue(saved.candidate_confirmed)

    def test_duplicate_group_uses_conservative_key(self):
        self.store.save_job(self.job)
        duplicate = JobListing(**{**self.job.__dict__, "listing_id": "j2", "source_id": "s2", "source_listing_url": "https://jobs.example/role/1?utm_source=feed"})
        self.store.save_job(duplicate)
        self.assertEqual({j.listing_id for j in self.store.find_duplicate_group(self.job)}, {"j1", "j2"})


class TrackerInvariantTests(unittest.TestCase):
    """The store must not persist states the domain state machine would reject."""

    def setUp(self):
        self.store = CareerStore(":memory:")
        self.job = JobListing(
            listing_id="j1", source_id="s1", source_name="test",
            source_listing_url="https://jobs.example/role/1", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN,
        )
        self.store.save_job(self.job)

    def tearDown(self):
        self.store.close()

    def test_confirmation_without_evidence_is_refused(self):
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED))
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "   "))
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SUBMISSION_ATTEMPTED)
        self.assertFalse(self.store.get_tracker("j1").candidate_confirmed)

    def test_confirmation_with_evidence_is_accepted(self):
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)
        stored = self.store.get_tracker("j1")
        confirmed = stored.transition(ApplicationStatus.CONFIRMED, evidence="Employer confirmation email", candidate_confirmed=True)
        self.store.save_tracker(confirmed)
        self.assertEqual(self.store.get_tracker("j1"), confirmed)
        self.assertTrue(self.store.get_tracker("j1").candidate_confirmed)

    def test_storage_boundary_refuses_instruction_text_even_when_core_is_bypassed(self):
        """Writing straight to storage must not be able to store guidance as proof of confirmation."""
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)
        guidance = "A confirmed application requires evidence. An attempt or timeout is not proof."
        with self.assertRaisesRegex(ValueError, "instruction or a placeholder"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, guidance, True))
        for text in ("n/a", "   ", "<your evidence here>"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, text, True))
        unchanged = self.store.get_tracker("j1")
        self.assertEqual(unchanged.status, ApplicationStatus.SUBMISSION_ATTEMPTED)
        self.assertIsNone(unchanged.status_evidence)
        self.assertFalse(unchanged.candidate_confirmed)

    def test_a_smoke_test_shaped_record_stays_readable_and_correctable(self):
        """A database written by an earlier build must remain readable, and be recoverable honestly.

        Reproduces the reported smoke-test row: a fictional job confirmed with the app's own
        instruction text and the confirmation flag set. Reading it must never fail, confirming it
        again must stay a no-op, and the supported correction is withdrawing it with a truthful
        note while dropping the unearned confirmation flag. The row is corrected, never deleted.
        """
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)
        guidance = "Evidence / note (required to confirm)"
        connection = self.store._connection
        with connection:
            connection.execute(
                "UPDATE application_tracker SET status=?, status_evidence=?, candidate_confirmed=1 WHERE listing_id=?",
                (ApplicationStatus.CONFIRMED.value, guidance, "j1"),
            )
        legacy = self.store.get_tracker("j1")
        self.assertIs(legacy.status, ApplicationStatus.CONFIRMED)
        self.assertEqual(legacy.status_evidence, guidance)
        self.assertTrue(legacy.candidate_confirmed)

        # Re-applying the stored status is still a no-op: the misleading evidence is not "edited" in place.
        self.assertIs(legacy.transition(ApplicationStatus.CONFIRMED, evidence="replacement"), legacy)

        corrected = legacy.transition(
            ApplicationStatus.WITHDRAWN,
            evidence="Fictional smoke-test record: no application was ever submitted; the earlier "
                     "confirmed state was a testing error and is not evidence of an application.",
            candidate_confirmed=False,
        )
        self.store.save_tracker(corrected)
        stored = self.store.get_tracker("j1")
        self.assertIs(stored.status, ApplicationStatus.WITHDRAWN)
        self.assertFalse(stored.candidate_confirmed)
        self.assertIn("no application was ever submitted", stored.status_evidence)
        self.assertEqual(len(self.store.list_jobs()), 1, "correction must not delete the listing")
        with self.assertRaisesRegex(ValueError, "Invalid application transition"):
            stored.transition(ApplicationStatus.SUBMITTED_UNVERIFIED, evidence="undo")

    def test_a_correction_can_keep_a_genuine_confirmation_flag(self):
        """Dropping the flag is an explicit choice; a real confirmation is not erased by withdrawing."""
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)
        confirmed = self.store.get_tracker("j1").transition(
            ApplicationStatus.CONFIRMED, evidence=CONFIRMATION_EVIDENCE, candidate_confirmed=True
        )
        self.store.save_tracker(confirmed)
        withdrawn = confirmed.transition(ApplicationStatus.WITHDRAWN, evidence="Candidate withdrew after confirming")
        self.store.save_tracker(withdrawn)
        stored = self.store.get_tracker("j1")
        self.assertIs(stored.status, ApplicationStatus.WITHDRAWN)
        self.assertTrue(stored.candidate_confirmed)

    def test_correction_survives_close_and_reopen(self):
        """The corrected row must be durable on disk, not only in the open connection.

        This class uses an in-memory database, so the durability check builds its own
        file-backed store rather than relying on ``self.store``.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "correction.sqlite3")
            with CareerStore(path) as store:
                store.save_job(self.job)
                reach_status(store, ApplicationStatus.SUBMISSION_ATTEMPTED)
                # Seed the row an earlier build could have written (placeholder evidence, flag set)
                # directly, because the current write path correctly refuses to create it.
                with store._connection:
                    store._connection.execute(
                        "UPDATE application_tracker SET status=?, status_evidence=?, candidate_confirmed=1 "
                        "WHERE listing_id=?",
                        (ApplicationStatus.CONFIRMED.value, "TODO", "j1"),
                    )
                corrected = store.get_tracker("j1").transition(
                    ApplicationStatus.WITHDRAWN,
                    evidence="Fictional smoke-test record: nothing was submitted; the confirmation was a testing error.",
                    candidate_confirmed=False,
                )
                store.save_tracker(corrected)
            with CareerStore(path) as reopened:
                stored = reopened.get_tracker("j1")
                self.assertIs(stored.status, ApplicationStatus.WITHDRAWN)
                self.assertFalse(stored.candidate_confirmed)
                self.assertIn("nothing was submitted", stored.status_evidence)
                self.assertEqual(len(reopened.list_jobs()), 1, "the listing must still be present")

    def test_initial_status_must_be_discovered(self):
        for status in (
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.SUBMISSION_ATTEMPTED,
            ApplicationStatus.SUBMITTED_UNVERIFIED,
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.WITHDRAWN,
        ):
            with self.subTest(status=status.value):
                with self.assertRaisesRegex(ValueError, "must start at discovered"):
                    self.store.save_tracker(ApplicationTracker("j1", status, "invented history"))
        with self.assertRaisesRegex(ValueError, "must start at discovered"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "fabricated confirmation", True))
        self.assertIsNone(self.store.get_tracker("j1"))

    def test_initial_status_discovered_is_accepted(self):
        self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.DISCOVERED))
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.DISCOVERED)
        self.assertEqual(stored.status_evidence, None)
        self.assertFalse(stored.candidate_confirmed)

    def test_initial_record_cannot_claim_confirmation(self):
        with self.assertRaisesRegex(ValueError, "cannot claim candidate confirmation"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.DISCOVERED, "note", True))
        self.assertIsNone(self.store.get_tracker("j1"))

    def test_confirmation_flag_cannot_appear_before_confirmation(self):
        cases = (
            (ApplicationStatus.DISCOVERED, ApplicationStatus.SHORTLISTED),
            (ApplicationStatus.DISCOVERED, ApplicationStatus.WITHDRAWN),
            (ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED),
            (ApplicationStatus.AWAITING_USER, ApplicationStatus.SUBMISSION_ATTEMPTED),
            (ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.SUBMITTED_UNVERIFIED),
        )
        for current, next_status in cases:
            with self.subTest(current=current.value, next=next_status.value):
                store = CareerStore(":memory:")
                self.addCleanup(store.close)
                store.save_job(self.job)
                stored = reach_status(store, current)
                self.assertFalse(stored.candidate_confirmed, "test scaffolding must not confirm the record")
                with self.assertRaisesRegex(ValueError, "cannot be true before a confirmation is recorded"):
                    store.save_tracker(ApplicationTracker("j1", next_status, "unearned confirmation", True))
                unchanged = store.get_tracker("j1")
                self.assertEqual(unchanged.status, current)
                self.assertFalse(unchanged.candidate_confirmed)

    def test_confirmation_flag_is_preserved_after_a_real_confirmation(self):
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)
        confirmed = self.store.get_tracker("j1").transition(
            ApplicationStatus.CONFIRMED, evidence=CONFIRMATION_EVIDENCE, candidate_confirmed=True
        )
        self.store.save_tracker(confirmed)
        interviewed = confirmed.transition(ApplicationStatus.INTERVIEW, evidence="Invite received")
        self.store.save_tracker(interviewed)
        withdrawn = interviewed.transition(ApplicationStatus.WITHDRAWN, evidence="Candidate withdrew")
        self.store.save_tracker(withdrawn)
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.WITHDRAWN)
        self.assertTrue(stored.candidate_confirmed)

    def _raw_row(self, listing_id="j1"):
        """Read the stored row directly, including the write timestamp."""
        return self.store._connection.execute(
            "SELECT status, status_evidence, candidate_confirmed, updated_at FROM application_tracker "
            "WHERE listing_id=?",
            (listing_id,),
        ).fetchone()

    def test_every_placeholder_evidence_form_is_refused_at_the_storage_boundary(self):
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)
        before = self._raw_row()
        for text in (None, "", "   ", "\t\n", "n/a", "N/A", "todo", "TBD", "test", "testing",
                     "placeholder", "yes", "evidence", "<your evidence here>",
                     "This is a test", "just testing", "sample text",
                     "A confirmed application requires evidence. An attempt or timeout is not proof."):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    self.store.save_tracker(
                        ApplicationTracker("j1", ApplicationStatus.CONFIRMED, text, True)
                    )
        self.assertEqual(self._raw_row(), before, "a refused write must not touch the row")

    def test_evidence_that_reads_as_a_real_observation_is_accepted_at_the_boundary(self):
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)
        for text in (
            "Employer portal shows Application Received on 2026-10-14",
            "Recruiter email acknowledged the application (thread ref ABC-123)",
        ):
            with self.subTest(text=text[:40]):
                self.store.save_tracker(
                    ApplicationTracker("j1", ApplicationStatus.CONFIRMED, text, True)
                )
                stored = self.store.get_tracker("j1")
                self.assertIs(stored.status, ApplicationStatus.CONFIRMED)
                self.assertEqual(stored.status_evidence, text)
                self.assertTrue(stored.candidate_confirmed)
                # Reset so the next case starts from the same permitted predecessor.
                with self.store._connection:
                    self.store._connection.execute(
                        "UPDATE application_tracker SET status=?, status_evidence=NULL, candidate_confirmed=0 "
                        "WHERE listing_id=?",
                        (ApplicationStatus.SUBMISSION_ATTEMPTED.value, "j1"),
                    )

    def test_a_withdrawn_record_is_terminal_at_the_storage_boundary(self):
        reach_status(self.store, ApplicationStatus.SHORTLISTED)
        self.store.save_tracker(
            self.store.get_tracker("j1").transition(ApplicationStatus.WITHDRAWN, evidence="Candidate withdrew")
        )
        before = self._raw_row()
        self.assertIs(self.store.get_tracker("j1").status, ApplicationStatus.WITHDRAWN)
        for status in (ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED,
                       ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.SUBMITTED_UNVERIFIED,
                       ApplicationStatus.CONFIRMED, ApplicationStatus.RESPONSE_RECEIVED,
                       ApplicationStatus.INTERVIEW, ApplicationStatus.DISCOVERED):
            with self.subTest(status=status.value):
                with self.assertRaises(ValueError):
                    self.store.save_tracker(
                        ApplicationTracker("j1", status, "Employer portal shows Application Received", True)
                    )
        self.assertEqual(self._raw_row(), before, "a terminal record must not move")
        # Re-applying the same status stays an idempotent no-op, not an error.
        self.store.save_tracker(self.store.get_tracker("j1"))
        self.assertEqual(self._raw_row(), before)

    def test_status_jump_is_refused_and_the_stored_row_is_unchanged(self):
        self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.DISCOVERED))
        with self.assertRaisesRegex(ValueError, "Invalid application transition: discovered -> interview"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.INTERVIEW, "unconfirmed invite"))
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.DISCOVERED)

    def test_permitted_transitions_and_idempotent_resaves_are_accepted(self):
        self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.DISCOVERED))
        self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.SHORTLISTED))
        self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.SHORTLISTED))
        self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.PREPARED))
        saved = self.store.get_tracker("j1")
        self.assertEqual(saved.status, ApplicationStatus.PREPARED)

    def test_rows_created_by_an_earlier_build_stay_usable(self):
        self.store.save_job(self.job)
        # Simulate a row written by a build that did not validate the first write.
        self.store._connection.execute(
            "INSERT INTO application_tracker(listing_id, status, status_evidence, candidate_confirmed, updated_at)"
            " VALUES ('j1', 'shortlisted', NULL, 0, '2026-10-01T00:00:00+00:00')"
        )
        self.store._connection.commit()
        legacy = self.store.get_tracker("j1")
        self.assertEqual(legacy.status, ApplicationStatus.SHORTLISTED)

        prepared = legacy.transition(ApplicationStatus.PREPARED)
        self.store.save_tracker(prepared)
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.PREPARED)

        with self.assertRaisesRegex(ValueError, "Invalid application transition"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "unsubstantiated"))
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.PREPARED)

    def test_legacy_confirmed_row_keeps_its_flag_as_it_advances(self):
        self.store.save_job(self.job)
        self.store._connection.execute(
            "INSERT INTO application_tracker(listing_id, status, status_evidence, candidate_confirmed, updated_at)"
            " VALUES ('j1', 'confirmed', 'Employer email from an earlier build', 1, '2026-10-01T00:00:00+00:00')"
        )
        self.store._connection.commit()
        legacy = self.store.get_tracker("j1")
        self.assertTrue(legacy.candidate_confirmed)

        response = legacy.transition(ApplicationStatus.RESPONSE_RECEIVED, evidence="Screening request received")
        self.store.save_tracker(response)
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.RESPONSE_RECEIVED)
        self.assertTrue(stored.candidate_confirmed)

    def test_backwards_state_change_is_refused(self):
        reach_status(self.store, ApplicationStatus.CONFIRMED)
        with self.assertRaisesRegex(ValueError, "Invalid application transition"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.DISCOVERED))
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.CONFIRMED)


class ConditionalTrackerWriteTests(unittest.TestCase):
    """``save_tracker(..., expected=...)``: a compare-and-set read at the storage boundary.

    Used by callers that read a row, decide something about it, and write later
    (``scripts/correct_tracker_record.py``). The transition rules alone cannot catch a record that
    moved on, because a forward move usually leaves the intended transition permitted.
    """

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "conditional.sqlite3"
        self.store = CareerStore(str(self.path))
        self.addCleanup(self.store.close)
        self.store.save_job(sample_job())

    def test_an_expectation_that_matches_writes_and_is_visible_to_another_connection_at_once(self):
        """The conditional write must be committed before it is treated as done.

        A conditional UPDATE left open inside the store's transaction is invisible to every other
        connection - including the read-only check that verifies a correction afterwards - so the
        write has to be durable the moment the call returns.
        """
        self.store.save_tracker(ApplicationTracker("j1"))
        expected = self.store.get_tracker_raw("j1")
        corrected = ApplicationTracker("j1").transition(
            ApplicationStatus.SHORTLISTED, evidence="Reviewed by hand")

        with mock.patch("career_agent.store._now", return_value=_TIMESTAMP):
            self.store.save_tracker(corrected, expected=expected)

        reader = sqlite3.connect(str(self.path))
        self.addCleanup(reader.close)
        row = reader.execute(
            "SELECT status, status_evidence, updated_at FROM application_tracker WHERE listing_id='j1'"
        ).fetchone()
        self.assertEqual(row[0], ApplicationStatus.SHORTLISTED.value)
        self.assertEqual(row[1], "Reviewed by hand")
        self.assertEqual(row[2], _TIMESTAMP, "the write timestamp must be the one this write used")

    def test_a_record_that_moved_on_is_refused_and_the_newer_row_is_kept(self):
        self.store.save_tracker(ApplicationTracker("j1"))
        expected = self.store.get_tracker_raw("j1")
        # Another writer advances the record after the caller read it.
        moved_on = ApplicationTracker("j1").transition(ApplicationStatus.SHORTLISTED)
        self.store.save_tracker(moved_on)

        with self.assertRaises(StaleTrackerRecord) as caught:
            self.store.save_tracker(ApplicationTracker("j1").transition(ApplicationStatus.WITHDRAWN),
                                    expected=expected)

        self.assertIn("changed after it was read", str(caught.exception))
        self.assertIn("nothing was changed", str(caught.exception))
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SHORTLISTED,
                         "the newer status must win")
        self.assertIsInstance(caught.exception, ValueError, "callers treat validation failures as ValueError")

    def test_newer_evidence_or_a_newer_confirmation_is_not_overwritten_even_at_the_same_status(self):
        """The comparison covers every field the caller decided from, not just the status."""
        reach_status(self.store, ApplicationStatus.CONFIRMED, evidence="First confirmation")
        expected = self.store.get_tracker_raw("j1")

        # The same status, but the evidence and the flag now describe a different, real confirmation.
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE application_tracker SET status_evidence=?, candidate_confirmed=1 WHERE listing_id='j1'",
                ("Second, more specific confirmation",),
            )

        with self.assertRaises(StaleTrackerRecord):
            self.store.save_tracker(ApplicationTracker("j1").transition(
                ApplicationStatus.WITHDRAWN, candidate_confirmed=True), expected=expected)

        row = self.store.get_tracker_raw("j1")
        self.assertEqual(row["status_evidence"], "Second, more specific confirmation")
        self.assertEqual(row["status"], ApplicationStatus.CONFIRMED.value)

    def test_a_missing_note_and_a_stored_null_are_the_same_expectation(self):
        """An absent note is stored as NULL, so a caller that read it as ``None`` must still match."""
        self.store.save_tracker(ApplicationTracker("j1"))
        expected = self.store.get_tracker_raw("j1")
        self.assertIsNone(expected["status_evidence"])

        self.store.save_tracker(ApplicationTracker("j1").transition(ApplicationStatus.SHORTLISTED),
                                expected=expected)

        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SHORTLISTED)

    def test_a_deleted_row_is_refused_rather_than_recreated_by_a_conditional_write(self):
        """Two independent rules refuse this, and both are checked.

        The state machine refuses to create a record in any state but the first one, and the
        conditional update matches no row. Whichever fires, the row must not come back from an
        expectation that was read before it was deleted.
        """
        self.store.save_tracker(ApplicationTracker("j1"))
        expected = self.store.get_tracker_raw("j1")
        with self.store._connection:
            self.store._connection.execute("DELETE FROM application_tracker WHERE listing_id='j1'")

        with self.assertRaises(ValueError):
            self.store.save_tracker(ApplicationTracker("j1").transition(ApplicationStatus.SHORTLISTED),
                                    expected=expected)

        self.assertIsNone(self.store.get_tracker_raw("j1"), "a conditional write never inserts")

    def test_a_conditional_write_still_enforces_the_transition_rules(self):
        """The new option must not become a way around the invariants enforced for every write."""
        self.store.save_tracker(ApplicationTracker("j1"))
        expected = self.store.get_tracker_raw("j1")

        with self.assertRaises(ValueError) as caught:
            # discovered -> confirmed directly is not a permitted transition.
            self.store.save_tracker(
                ApplicationTracker("j1").transition(ApplicationStatus.CONFIRMED,
                                                    evidence="Invented", candidate_confirmed=True),
                expected=expected)

        self.assertNotIsInstance(caught.exception, StaleTrackerRecord,
                                 "this is a rule refusal, not a staleness refusal")
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.DISCOVERED)


class DurabilityTests(unittest.TestCase):
    """File-backed persistence and error surfaces (the shipped alpha uses a real file, not :memory:)."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "career_agent.sqlite3"

    def _job(self):
        return JobListing(
            listing_id="j1", source_id="manual", source_name="Manual",
            source_listing_url="https://jobs.example/role/1", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN,
            employer_apply_url="https://employer.example/apply/1", eligibility_scope="restricted",
            eligible_countries=("India",), provenance_note="Checked the official listing.",
        )

    def test_state_survives_close_and_reopen(self):
        profile = CandidateProfile(candidate_country="India", degree_discipline="ECE",
                                  graduation_year=2027, skills=frozenset({"Python"}))
        store = CareerStore(self.path)
        store.save_profile(profile)
        store.save_job(self._job())
        reach_status(store, ApplicationStatus.CONFIRMED, evidence="Employer email")
        store.close()

        reopened = CareerStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get_profile(), profile)
        self.assertEqual(reopened.get_job("j1"), self._job())
        tracker = reopened.get_tracker("j1")
        self.assertEqual(tracker.status, ApplicationStatus.CONFIRMED)
        self.assertEqual(tracker.status_evidence, "Employer email")
        self.assertTrue(tracker.candidate_confirmed)
        version = reopened._connection.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version, SCHEMA_VERSION)

    def test_deletion_survives_close_and_reopen(self):
        store = CareerStore(self.path)
        store.save_job(self._job())
        store.save_tracker(ApplicationTracker("j1", ApplicationStatus.DISCOVERED))
        store.delete_job("j1")
        store.close()
        reopened = CareerStore(self.path)
        self.addCleanup(reopened.close)
        self.assertIsNone(reopened.get_job("j1"))
        self.assertIsNone(reopened.get_tracker("j1"))

    def test_reopening_an_existing_database_does_not_reset_it(self):
        store = CareerStore(self.path)
        store.save_job(self._job())
        store.close()
        for _ in range(2):
            reopened = CareerStore(self.path)
            self.assertEqual(len(reopened.list_jobs()), 1)
            self.assertEqual(reopened._connection.execute("PRAGMA user_version").fetchone()[0],
                             SCHEMA_VERSION)
            reopened.close()

    def test_newer_schema_is_refused_instead_of_overwritten(self):
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA user_version = 99")
        connection.commit()
        connection.close()
        with self.assertRaises(RuntimeError):
            CareerStore(self.path)

    def test_unopenable_path_raises_a_sqlite_error(self):
        missing_parent = Path(self._directory.name) / "absent-directory" / "career_agent.sqlite3"
        with self.assertRaises(sqlite3.Error):
            CareerStore(missing_parent)


class ActivityLogTests(unittest.TestCase):
    """The append-only history: stored as written, order preserved, and separate from the status."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "career_agent.sqlite3"
        self.store = CareerStore(self.path)
        self.addCleanup(self.store.close)
        self.store.save_job(JobListing(
            listing_id="j1", source_id="manual", source_name="Manual entry",
            source_listing_url="https://jobs.example/role/1", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN,
        ))

    def entry(self, kind=ActivityKind.APPLIED, day=12, detail="Applied through the portal."):
        return ApplicationActivity(kind, date(2026, 10, day), detail)

    def test_an_entry_is_stored_and_read_back_with_both_dates(self):
        activity_id = self.store.add_activity("j1", self.entry())

        stored, = self.store.list_activity("j1")
        self.assertEqual(stored.activity_id, activity_id)
        self.assertIs(stored.kind, ActivityKind.APPLIED)
        self.assertEqual(stored.occurred_on, date(2026, 10, 12))
        self.assertEqual(stored.detail, "Applied through the portal.")
        self.assertIsNotNone(stored.recorded_at, "when this app wrote the row is recorded separately")

    def test_entries_are_returned_oldest_first_regardless_of_the_order_written(self):
        later = self.store.add_activity("j1", self.entry(kind=ActivityKind.RESPONSE, day=20, detail="They replied."))
        earlier = self.store.add_activity("j1", self.entry(day=12))

        self.assertEqual([entry.activity_id for entry in self.store.list_activity("j1")], [earlier, later])
        self.assertEqual([entry.occurred_on for entry in self.store.list_activity("j1")],
                         [date(2026, 10, 12), date(2026, 10, 20)])

    def test_logging_an_application_never_changes_the_tracker(self):
        """The reason the log exists beside the tracker rather than inside it.

        An entry saying an application was sent is the person's own note. It must not create a tracker
        record, set a status, or count as the evidence a confirmation requires.
        """
        self.store.add_activity("j1", self.entry())

        self.assertIsNone(self.store.get_tracker("j1"), "no tracker row may be created by an entry")
        self.assertIsNone(self.store.get_tracker_raw("j1"))

    def test_an_entry_is_not_evidence_for_a_confirmation(self):
        """The log says what the person did; a confirmation is a claim about the employer.

        An "I applied" entry is exactly the kind of note someone might expect to double as proof, so
        the storage boundary is where it must be refused: confirmation still needs substantive,
        deliberately supplied evidence and the person's own assertion.
        """
        self.store.add_activity("j1", self.entry(kind=ActivityKind.APPLIED, detail="Sent it through the portal."))
        self.store.save_tracker(ApplicationTracker("j1"))

        with self.assertRaises(ValueError) as caught:
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED))

        self.assertIn("evidence", str(caught.exception))
        stored = self.store.get_tracker("j1")
        self.assertIs(stored.status, ApplicationStatus.DISCOVERED, "the log must not move the status")
        self.assertFalse(stored.candidate_confirmed)

    def test_an_entry_for_an_unsaved_listing_is_refused_and_writes_nothing(self):
        with self.assertRaises(ValueError) as caught:
            self.store.add_activity("not-saved", self.entry())

        self.assertIn("Save the job listing first", str(caught.exception))
        self.assertEqual(self.store.list_activity("not-saved"), ())

    def test_the_storage_boundary_re_validates_what_it_is_given(self):
        """The rule holds at the database, not only in the dialog that normally builds the value."""
        with self.assertRaises(ValueError):
            self.store.add_activity("j1", ApplicationActivity(
                ActivityKind.NOTE, date(2026, 10, 12), "x" * 5000))
        with self.assertRaises(ValueError) as caught:
            self.store.add_activity("j1", "not an entry")

        self.assertIn("ApplicationActivity", str(caught.exception))
        self.assertEqual(self.store.list_activity("j1"), ())

    def test_entries_survive_a_close_and_reopen(self):
        self.store.add_activity("j1", self.entry())
        self.store.close()

        reopened = CareerStore(self.path)
        self.addCleanup(reopened.close)
        stored, = reopened.list_activity("j1")
        self.assertEqual(stored.detail, "Applied through the portal.")

    def test_deleting_one_entry_leaves_the_others(self):
        first = self.store.add_activity("j1", self.entry())
        self.store.add_activity("j1", self.entry(kind=ActivityKind.NOTE, day=13, detail="Called them."))

        self.assertTrue(self.store.delete_activity(first))

        remaining, = self.store.list_activity("j1")
        self.assertEqual(remaining.detail, "Called them.")

    def test_deleting_an_entry_that_is_not_there_reports_false(self):
        first = self.store.add_activity("j1", self.entry())
        self.assertTrue(self.store.delete_activity(first))

        self.assertFalse(self.store.delete_activity(first), "a no-op must not be reported as a deletion")
        self.assertFalse(self.store.delete_activity(9999))

    def test_deleting_the_listing_removes_its_history(self):
        self.store.add_activity("j1", self.entry())

        self.assertTrue(self.store.delete_job("j1"))

        self.assertEqual(self.store.list_activity("j1"), ())
        self.assertEqual(self.store._connection.execute(
            "SELECT count(*) FROM application_activity").fetchone()[0], 0,
            "the foreign key must cascade rather than leave orphaned history")

    def test_a_row_this_version_cannot_read_is_refused_by_name_and_the_raw_read_still_works(self):
        """A view must not crash on a value a later version wrote, and the export must still carry it."""
        self.store.add_activity("j1", self.entry())
        self.store._connection.execute("UPDATE application_activity SET kind = 'teleported'")
        self.store._connection.commit()

        with self.assertRaises(StoredRecordError) as caught:
            self.store.list_activity("j1")
        self.assertIn("teleported", str(caught.exception))
        raw, = self.store.list_activity_raw("j1")
        self.assertEqual(raw["kind"], "teleported")
        self.assertEqual(raw["detail"], "Applied through the portal.")

    def test_a_stored_date_that_is_not_a_date_is_refused_by_name(self):
        self.store.add_activity("j1", self.entry())
        self.store._connection.execute("UPDATE application_activity SET occurred_on = 'last Tuesday'")
        self.store._connection.commit()

        with self.assertRaises(StoredRecordError) as caught:
            self.store.list_activity("j1")

        self.assertIn("last Tuesday", str(caught.exception))


class SchemaMigrationTests(unittest.TestCase):
    """The schema contract: one recorded step at a time, and a failure that changes nothing.

    The version-1 fixture is built by running the real first step alone, so it is the schema this
    application actually shipped rather than a hand-copied approximation of it.
    """

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "career_agent.sqlite3"

    def _open_at_version(self, version):
        """A store whose schema stops at ``version`` (the older schema, built by the real steps)."""
        steps = tuple(step for step in store_module._MIGRATIONS if step[0] <= version)
        with mock.patch.object(store_module, "_MIGRATIONS", steps):
            store = CareerStore(self.path)
        self.addCleanup(store.close)
        return store

    def _job(self, listing_id="j1"):
        return JobListing(
            listing_id=listing_id, source_id="manual", source_name="Manual entry",
            source_listing_url=f"https://jobs.example/role/{listing_id}", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN,
        )

    def test_a_fresh_database_records_the_current_schema_version(self):
        """The literal is pinned on purpose: bumping the schema is a deliberate act with a step."""
        store = CareerStore(self.path)
        self.addCleanup(store.close)

        self.assertEqual(SCHEMA_VERSION, 3)
        self.assertEqual(store._connection.execute("PRAGMA user_version").fetchone()[0], 3)
        tables = {
            row[0] for row in store._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        }
        self.assertEqual(tables, set(SCHEMA_TABLES_BY_VERSION[3]))

    def test_the_migration_list_describes_every_version_up_to_the_current_one(self):
        steps = store_module._MIGRATIONS

        self.assertEqual([step[0] for step in steps], list(range(1, SCHEMA_VERSION + 1)))
        for version, description, apply_migration in steps:
            with self.subTest(version=version):
                self.assertTrue(description.strip(), "a step with no description cannot be reported")
                self.assertTrue(callable(apply_migration))
                self.assertIn(version, SCHEMA_TABLES_BY_VERSION)
        self.assertEqual(max(SCHEMA_TABLES_BY_VERSION), SCHEMA_VERSION)

    def test_a_version_one_database_is_updated_when_it_is_opened(self):
        older = self._open_at_version(1)
        older.save_job(self._job())
        profile = CandidateProfile(candidate_country="India", degree_discipline="ECE", graduation_year=2027)
        older.save_profile(profile)
        older._connection.execute("PRAGMA user_version = 1")
        older._connection.commit()
        older.close()

        upgraded = CareerStore(self.path)
        self.addCleanup(upgraded.close)

        self.assertEqual(upgraded._connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
        self.assertEqual(upgraded.get_job("j1"), self._job(), "the existing rows must survive the update")
        self.assertEqual(upgraded.get_profile(), profile)
        self.assertIn("application_activity", {
            row[0] for row in upgraded._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        })

    def test_reopening_an_already_current_database_runs_no_step(self):
        CareerStore(self.path).close()
        calls = []
        steps = tuple(
            (target, description, lambda connection, target=target: calls.append(target))
            for target, description, _ in store_module._MIGRATIONS
        )
        with mock.patch.object(store_module, "_MIGRATIONS", steps):
            store = CareerStore(self.path)
        self.addCleanup(store.close)

        self.assertEqual(calls, [], "an up-to-date database must not be migrated again")

    def test_a_failed_step_leaves_the_version_and_the_structure_untouched(self):
        """The reason steps run statement-by-statement inside one explicit transaction.

        ``executescript`` would commit the transaction it finds before running its script, and the
        sqlite3 module's implicit transaction covers data-modifying statements only, so a partly
        applied step could not be rolled back. This holds the property directly: the table the step
        created before failing must not survive, and the recorded version must not move.
        """
        def failing_step(connection):
            connection.execute("CREATE TABLE half_applied (value TEXT)")
            connection.execute("CREATE INDEX idx_half ON half_applied(value)")
            raise sqlite3.OperationalError("no such table: missing_thing")

        with mock.patch.object(store_module, "_MIGRATIONS",
                               ((1, "create the base tables", store_module._migration_to_v1),
                                (2, "a step that fails", failing_step))):
            with self.assertRaises(SchemaMigrationError) as caught:
                CareerStore(self.path)

        error = caught.exception
        self.assertEqual((error.target_version, error.from_version, error.observed_version), (2, 1, 1))
        self.assertIn("still at schema version 1", str(error))
        self.assertIn("no such table: missing_thing", str(error))
        connection = sqlite3.connect(str(self.path))
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertNotIn("half_applied", {
                row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }, "a rolled-back step must leave no object behind")
        finally:
            connection.close()
        reopened = CareerStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get_job("j1"), None, "the database is still usable after the failure")

    def test_a_later_step_failing_keeps_the_earlier_one_applied(self):
        """Each step commits on its own, so a database stops at the last version that succeeded."""
        def failing_step(connection):
            raise sqlite3.OperationalError("disk I/O error")

        with mock.patch.object(store_module, "_MIGRATIONS",
                               ((1, "create the base tables", store_module._migration_to_v1),
                                (2, "a step that fails", failing_step))):
            with self.assertRaises(SchemaMigrationError) as caught:
                CareerStore(self.path)

        self.assertEqual(caught.exception.from_version, 1)
        reopened = CareerStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened._connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    def test_a_database_that_cannot_be_read_back_says_so_instead_of_claiming_nothing_changed(self):
        """The failure message is re-read from the file; the reassuring half is not assumed."""
        def failing_step(connection):
            raise sqlite3.OperationalError("disk I/O error")

        with mock.patch.object(store_module, "_MIGRATIONS", ((2, "a step that fails", failing_step),)), \
                mock.patch.object(CareerStore, "_roll_back_step", lambda self: None):
            with self.assertRaises(SchemaMigrationError) as caught:
                CareerStore(self.path)

        message = str(caught.exception)
        self.assertIn("could not be read back", message)
        self.assertIn("Restore a verified backup", message)
        self.assertNotIn("still at schema version", message)

    def test_a_partly_applied_database_is_not_reported_as_unchanged(self):
        """If the version moved, the message must say the step may have been applied in part."""
        older = self._open_at_version(1)
        older._connection.execute("PRAGMA user_version = 1")
        older._connection.commit()
        older.close()

        def failing_step(connection):
            raise sqlite3.OperationalError("disk I/O error")

        with mock.patch.object(store_module, "_MIGRATIONS", ((2, "a step that fails", failing_step),)), \
                mock.patch.object(CareerStore, "_roll_back_step", lambda self: 2):
            with self.assertRaises(SchemaMigrationError) as caught:
                CareerStore(self.path)

        message = str(caught.exception)
        self.assertIn("now records schema version 2 rather than 1", message)
        self.assertIn("may have been applied only in part", message)
        self.assertNotIn("still at schema version", message)

    def test_a_newer_schema_is_refused_by_type_and_leaves_the_file_alone(self):
        connection = sqlite3.connect(str(self.path))
        connection.execute("PRAGMA user_version = 99")
        connection.commit()
        connection.close()
        before = self.path.read_bytes()

        with self.assertRaises(SchemaTooNewError) as caught:
            CareerStore(self.path)

        self.assertEqual((caught.exception.version, caught.exception.supported), (99, SCHEMA_VERSION))
        self.assertEqual(self.path.read_bytes(), before, "the refused file must be byte-identical")

    def test_a_file_holding_tables_but_no_version_is_refused_by_type_and_left_alone(self):
        """Adopting it would add this application's tables to somebody else's file."""
        connection = sqlite3.connect(str(self.path))
        connection.execute("CREATE TABLE someone_elses (value TEXT)")
        connection.commit()
        connection.close()
        before = self.path.read_bytes()

        with self.assertRaises(UnrecognisedDatabaseError) as caught:
            CareerStore(self.path)

        self.assertIn("records schema version 0", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), before)
        connection = sqlite3.connect(str(self.path))
        self.assertNotIn("job_listings", {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        })
        connection.close()

    def test_an_empty_file_is_treated_as_a_new_database(self):
        self.path.write_bytes(b"")

        store = CareerStore(self.path)
        self.addCleanup(store.close)

        self.assertEqual(store._connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)


class PreUpgradeSnapshotTests(unittest.TestCase):
    """An update never starts without a verified copy of what it is about to change.

    The steps themselves are transactional (see ``SchemaMigrationTests``), but a rollback is not a
    backup: a step that is applied, committed and only then found to be wrong cannot be undone by the
    transaction that applied it, and a disk that fills mid-copy is beyond a transaction's reach. These
    tests pin the copy, and pin the refusal when the copy cannot be written.
    """

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.folder = Path(self._directory.name)
        self.path = self.folder / "career_agent.sqlite3"

    def _job(self, listing_id="kept"):
        return JobListing(
            listing_id=listing_id, source_id="manual", source_name="Manual entry",
            source_listing_url=f"https://jobs.example/role/{listing_id}", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN,
        )

    def _build_version_one_database(self, listing_ids=("kept",)):
        """A real version-1 database holding rows, built by the real first step alone."""
        steps = tuple(step for step in store_module._MIGRATIONS if step[0] == 1)
        with mock.patch.object(store_module, "_MIGRATIONS", steps):
            with CareerStore(self.path) as store:
                for listing_id in listing_ids:
                    store.save_job(self._job(listing_id))
        return self.snapshots()

    def snapshots(self):
        """Every pre-upgrade copy in the folder, recognised by the name ``backup`` writes."""
        return sorted(path for path in self.folder.iterdir() if ".backup-" in path.name)

    def test_updating_an_older_database_keeps_a_verified_copy_of_it(self):
        self._build_version_one_database(("kept", "also-kept"))

        with CareerStore(self.path) as store:
            listing_ids = [job.listing_id for job in store.list_jobs()]

        copies = self.snapshots()
        self.assertEqual(len(copies), 1, "one update, one copy")
        info = validate_app_database(copies[0])
        self.assertEqual(info.schema_version, 1, "the copy holds the version the update started from")
        self.assertEqual(info.job_count, 2, "the copy holds the rows the update was about to change")
        self.assertEqual(listing_ids, ["also-kept", "kept"])
        self.assertEqual(validate_app_database(self.path).schema_version, SCHEMA_VERSION)
        self.assertIn(
            f"event=database.upgrade_snapshot detail=version=1 file={copies[0].name}",
            (self.folder / "logs" / "application.log").read_text(encoding="utf-8"),
            "the log says which file holds the copy",
        )
        self.assertIn("event=backup.written", (self.folder / "logs" / "application.log").read_text(encoding="utf-8"))

    def test_a_brand_new_database_is_not_copied(self):
        with CareerStore(self.path):
            pass

        self.assertEqual(self.snapshots(), [], "a new file has nothing to preserve")

    def test_a_database_that_is_already_current_is_not_copied(self):
        with CareerStore(self.path):
            pass
        with CareerStore(self.path):
            pass

        self.assertEqual(self.snapshots(), [], "opening a current database is not an update")

    def test_the_update_does_not_start_when_the_copy_cannot_be_written(self):
        self._build_version_one_database()
        before = self.path.read_bytes()

        def refuse(*args, **kwargs):
            raise BackupError("simulated: the safety copy could not be written")

        with mock.patch("career_agent.backup.create_backup", refuse):
            with self.assertRaises(SchemaUpgradeRefused) as caught:
                CareerStore(self.path)

        self.assertIn("still at schema version 1", str(caught.exception))
        self.assertIn("Nothing was changed", str(caught.exception))
        self.assertEqual(self.path.read_bytes(), before, "the file must be untouched")
        self.assertEqual(validate_app_database(self.path).schema_version, 1)
        self.assertEqual(self.snapshots(), [], "no half-written copy may be left behind")
        self.assertNotIn("event=database.migrated detail=from=1 to=2",
                         (self.folder / "logs" / "application.log").read_text(encoding="utf-8"))

    def test_a_step_that_fails_leaves_the_copy_available_and_the_data_intact(self):
        """The moment the copy matters most is the moment the update goes wrong."""
        self._build_version_one_database()

        def broken_step(connection):
            connection.execute("CREATE TABLE half_applied (value TEXT)")
            raise RuntimeError("simulated failure inside the step")

        with mock.patch.object(store_module, "_MIGRATIONS", store_module._MIGRATIONS[:1] + (
            (2, "a step that fails", broken_step),
        )):
            with self.assertRaises(SchemaMigrationError):
                CareerStore(self.path)

        copies = self.snapshots()
        self.assertEqual(len(copies), 1, "the copy the failed attempt took is kept, not discarded")
        self.assertEqual(validate_app_database(copies[0]).job_count, 1)
        self.assertEqual(validate_app_database(copies[0]).schema_version, 1)
        self.assertEqual(validate_app_database(self.path).schema_version, 1)

        # A later attempt takes its own copy of the state it sees, even within the same second: a copy
        # describes the database at the moment it was made, so an older one is never reused for it.
        with CareerStore(self.path) as store:
            self.assertEqual([job.listing_id for job in store.list_jobs()], ["kept"])

        all_copies = self.snapshots()
        self.assertEqual(len(all_copies), 2)
        for copy in all_copies:
            self.assertEqual(validate_app_database(copy).schema_version, 1)
        self.assertEqual(validate_app_database(self.path).schema_version, SCHEMA_VERSION)


class DatabaseFilePermissionTests(unittest.TestCase):
    """Owner-only database permissions are a best-effort hardening, never a correctness guarantee."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.path = Path(self._directory.name) / "permissions.sqlite3"

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_database_file_is_created_owner_only(self):
        store = CareerStore(self.path)
        self.addCleanup(store.close)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_owner_only_database_reopens_and_keeps_its_data(self):
        job = JobListing(
            listing_id="perm1", source_id="manual", source_name="Manual entry",
            source_listing_url="https://jobs.example/role/perm1", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN,
        )
        with CareerStore(self.path) as store:
            store.save_job(job, observed_at="2026-10-14T00:00:00+00:00")
        with CareerStore(self.path) as reopened:
            self.assertEqual(reopened.get_job("perm1"), job)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_a_platform_that_refuses_the_mode_change_still_gets_a_working_database(self):
        with mock.patch("career_agent.store.os.chmod", side_effect=OSError("mode changes unsupported")):
            with CareerStore(self.path) as store:
                self.assertEqual(store.list_jobs(), ())

    def test_in_memory_databases_are_unaffected(self):
        with CareerStore(":memory:") as store:
            self.assertEqual(store.list_jobs(), ())


class PrivateFileWriteTests(unittest.TestCase):
    """Exported candidate data must reach disk owner-only, or not reach disk at all.

    Uses temporary directories only. Tests that assert real POSIX mode bits are skipped where the
    platform does not have POSIX permissions.
    """

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = Path(self._directory.name)
        self.secret = '{"degree_discipline": "ECE", "application_history": "confirmed 2026-10-14"}'

    def mode_of(self, path):
        return Path(path).stat().st_mode & 0o777

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_a_new_file_is_owner_only(self):
        target = self.directory / "export.json"
        write_private_text_file(target, self.secret)
        self.assertEqual(self.mode_of(target), 0o600)
        self.assertEqual(target.read_text(encoding="utf-8"), self.secret)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_the_protection_does_not_depend_on_the_process_umask(self):
        target = self.directory / "umask.json"
        previous = os.umask(0o000)  # the most permissive umask: mode bits cannot be relied on
        try:
            write_private_text_file(target, self.secret)
        finally:
            os.umask(previous)
        self.assertEqual(self.mode_of(target), 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_an_existing_permissive_file_is_tightened_not_left_readable(self):
        for initial in (0o644, 0o666, 0o777):
            with self.subTest(initial=oct(initial)):
                target = self.directory / f"existing-{initial:o}.json"
                target.write_text("old content", encoding="utf-8")
                os.chmod(target, initial)
                self.assertEqual(self.mode_of(target), initial, "precondition")
                write_private_text_file(target, self.secret)
                self.assertEqual(self.mode_of(target), 0o600)
                self.assertEqual(target.read_text(encoding="utf-8"), self.secret)

    def test_a_symbolic_link_destination_is_refused_and_its_target_is_untouched(self):
        victim = self.directory / "victim.txt"
        victim.write_text("ORIGINAL CONTENT THAT MUST SURVIVE", encoding="utf-8")
        victim_mode = self.mode_of(victim)
        link = self.directory / "link.json"
        try:
            os.symlink(victim, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links are unavailable here: {exc}")

        with self.assertRaises(PrivateWriteError) as caught:
            write_private_text_file(link, self.secret)

        self.assertIn("symbolic link", str(caught.exception))
        self.assertEqual(victim.read_text(encoding="utf-8"), "ORIGINAL CONTENT THAT MUST SURVIVE")
        self.assertEqual(self.mode_of(victim), victim_mode)
        self.assertTrue(link.is_symlink(), "the link itself must be left alone")

    def test_a_symbolic_link_is_refused_even_where_the_open_flag_is_unavailable(self):
        """The refusal must not depend on O_NOFOLLOW, which is POSIX-only.

        With the flag forced to 0 the open would follow the link, so this exercises the explicit
        pre-check that protects platforms without it.
        """
        victim = self.directory / "victim-flagless.txt"
        victim.write_text("ORIGINAL CONTENT THAT MUST SURVIVE", encoding="utf-8")
        link = self.directory / "flagless-link.json"
        try:
            os.symlink(victim, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links are unavailable here: {exc}")

        with mock.patch.object(os, "O_NOFOLLOW", 0):
            with self.assertRaises(PrivateWriteError) as caught:
                write_private_text_file(link, self.secret)

        self.assertIn("symbolic link", str(caught.exception))
        self.assertEqual(victim.read_text(encoding="utf-8"), "ORIGINAL CONTENT THAT MUST SURVIVE")

    def test_a_failure_to_apply_the_mode_writes_no_candidate_data(self):
        target = self.directory / "blocked.json"
        with mock.patch("career_agent.store.os.fchmod", side_effect=OSError("operation not permitted")):
            with self.assertRaises(PrivateWriteError) as caught:
                write_private_text_file(target, self.secret)
        self.assertIn("nothing was written", str(caught.exception))
        if target.exists():
            self.assertNotIn("ECE", target.read_text(encoding="utf-8"))

    def test_a_filesystem_that_ignores_the_mode_leaves_no_readable_export(self):
        """Verification catches a mount where chmod appears to succeed but does not apply."""
        target = self.directory / "sloppy-fs.json"
        fake_stat = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o644)
        with mock.patch("career_agent.store.os.lstat", return_value=fake_stat):
            with self.assertRaises(PrivateWriteError) as caught:
                write_private_text_file(target, self.secret)
        self.assertIn("owner-only", str(caught.exception))
        # The export contained real candidate data, so the failed attempt must not survive on disk.
        if target.exists():
            self.assertNotIn("ECE", target.read_text(encoding="utf-8"))

    def test_an_unwritable_destination_reports_a_useful_error(self):
        with self.assertRaises(PrivateWriteError) as caught:
            write_private_text_file(self.directory, self.secret)  # a directory, not a file
        self.assertIn("could not be opened for writing", str(caught.exception))

    def test_missing_parent_directory_reports_a_useful_error(self):
        with self.assertRaises(PrivateWriteError) as caught:
            write_private_text_file(self.directory / "absent" / "export.json", self.secret)
        self.assertIn("could not be opened for writing", str(caught.exception))

    def test_the_error_type_remains_an_oserror_for_existing_callers(self):
        self.assertTrue(issubclass(PrivateWriteError, OSError))

    def test_existing_database_helper_behaviour_is_unchanged(self):
        """The database path still uses the same non-fatal helper after the refactor."""
        database = self.directory / "unchanged.sqlite3"
        store = CareerStore(database)
        self.addCleanup(store.close)
        if os.name == "posix":
            self.assertEqual(self.mode_of(database), 0o600)
        with mock.patch("career_agent.store.os.chmod", side_effect=OSError("unsupported")):
            with CareerStore(database) as reopened:
                self.assertEqual(reopened.list_jobs(), ())



class PrivateFileCreationTests(unittest.TestCase):
    """The shared primitives the export and backup paths use must fail closed.

    ``create_private_file`` is what both callers build on, so its refusals carry the same guarantees:
    an existing file is never touched in exclusive mode, and a file this call created is never left
    behind unprotected.
    """

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.directory = Path(self._directory.name)

    def test_an_exclusive_open_refuses_an_existing_file_and_leaves_it_alone(self):
        existing = self.directory / "taken.sqlite3"
        existing.write_text("existing content", encoding="utf-8")

        with self.assertRaises(PrivateWriteError):
            create_private_file(existing, exclusive=True)

        self.assertEqual(existing.read_text(encoding="utf-8"), "existing content")

    def test_an_exclusive_open_that_cannot_secure_the_mode_removes_the_file_it_created(self):
        target = self.directory / "new.sqlite3"
        with mock.patch("career_agent.store.os.fchmod", side_effect=OSError("operation not permitted")):
            with self.assertRaises(PrivateWriteError) as caught:
                create_private_file(target, exclusive=True)

        self.assertIn("nothing was written", str(caught.exception))
        self.assertFalse(target.exists(), "the file this call created must not be left behind")

    def test_require_owner_only_reports_a_file_that_cannot_be_protected(self):
        target = self.directory / "unprotected.sqlite3"
        target.write_text("candidate data", encoding="utf-8")
        fake_mode = mock.Mock()
        fake_mode.st_mode = stat.S_IFREG | 0o644
        with mock.patch.object(os, "lstat", return_value=fake_mode), mock.patch.object(os, "unlink") as unlink:
            with self.assertRaises(PrivateWriteError) as caught:
                require_owner_only(target, noun="backup")

        self.assertIn("owner-only", str(caught.exception))
        unlink.assert_called_once()


class UnrecognisedStatusReadTests(unittest.TestCase):
    """A status this build does not know is reported as itself; it is never repaired or hidden.

    The value is written straight into the file with the standard library, which is what a database
    written by another version, an older build, or a hand edit looks like from here.
    """

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = CareerStore(str(Path(self.directory.name) / "legacy.sqlite3"))
        self.addCleanup(self.store.close)
        self.store.save_job(JobListing(
            listing_id="j1", source_id="s1", source_name="test",
            source_listing_url="https://jobs.example/role/1", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN, provenance_note="checked",
        ))
        reach_status(self.store, ApplicationStatus.SHORTLISTED)
        self.write_status("ghost_status")

    def write_status(self, value):
        """Store an arbitrary status string the way another tool or an older build would."""
        connection = sqlite3.connect(self.store.database_path)
        try:
            with connection:
                connection.execute(
                    "UPDATE application_tracker SET status=? WHERE listing_id='j1'", (value,)
                )
        finally:
            connection.close()

    def stored_row(self):
        connection = sqlite3.connect(self.store.database_path)
        try:
            return connection.execute(
                "SELECT listing_id, status, status_evidence, candidate_confirmed, updated_at "
                "FROM application_tracker WHERE listing_id='j1'"
            ).fetchone()
        finally:
            connection.close()

    def test_reading_the_raw_row_reports_the_stored_value(self):
        raw = self.store.get_tracker_raw("j1")
        self.assertEqual(raw["status"], "ghost_status")
        self.assertEqual(raw["candidate_confirmed"], False)
        self.assertTrue(raw["updated_at"])

    def test_reading_the_raw_row_never_rewrites_the_record(self):
        before = self.stored_row()
        for _ in range(3):
            self.store.get_tracker_raw("j1")
        self.assertEqual(self.stored_row(), before)

    def test_the_domain_read_raises_a_specific_error_that_names_the_stored_value(self):
        with self.assertRaises(TrackerStatusError) as caught:
            self.store.get_tracker("j1")

        self.assertIn("ghost_status", str(caught.exception))
        self.assertEqual(caught.exception.raw_value, "ghost_status")
        # It stays a ValueError, so existing refusal paths keep working unchanged.
        self.assertIsInstance(caught.exception, ValueError)
        self.assertEqual(self.stored_row()[1], "ghost_status", "a failed read must not repair the row")

    def test_a_listing_without_a_record_reads_as_none(self):
        self.assertIsNone(self.store.get_tracker_raw("missing"))
        self.assertIsNone(self.store.get_tracker("missing"))

    def test_a_recognised_status_still_reads_as_a_domain_object(self):
        self.write_status(ApplicationStatus.SHORTLISTED.value)
        tracker = self.store.get_tracker("j1")
        self.assertIs(tracker.status, ApplicationStatus.SHORTLISTED)
        self.assertEqual(self.store.get_tracker_raw("j1")["status"], "shortlisted")


class RecordTimeTests(unittest.TestCase):
    """The stored times are the app's own observations and must behave as such."""

    def setUp(self):
        self.store = CareerStore(":memory:")
        self.addCleanup(self.store.close)
        self.job = JobListing(
            listing_id="j1", source_id="s1", source_name="test",
            source_listing_url="https://jobs.example/role/1", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN, provenance_note="checked",
        )

    def test_a_new_record_has_the_same_first_and_last_time(self):
        self.store.save_job(self.job, observed_at="2026-10-14T10:00:00+00:00")
        times = self.store.get_record_times("j1")
        self.assertEqual(times, {
            "first_seen_at": "2026-10-14T10:00:00+00:00",
            "last_seen_at": "2026-10-14T10:00:00+00:00",
        })

    def test_a_later_save_moves_the_last_time_and_preserves_the_first(self):
        self.store.save_job(self.job, observed_at="2026-10-14T10:00:00+00:00")
        self.store.save_job(self.job, observed_at="2026-10-14T12:30:00+00:00")
        times = self.store.get_record_times("j1")
        self.assertEqual(times["first_seen_at"], "2026-10-14T10:00:00+00:00")
        self.assertEqual(times["last_seen_at"], "2026-10-14T12:30:00+00:00")

    def test_an_unknown_listing_has_no_record_times(self):
        self.assertIsNone(self.store.get_record_times("missing"))

    def test_reading_times_never_writes(self):
        self.store.save_job(self.job, observed_at="2026-10-14T10:00:00+00:00")
        before = self.store.get_record_times("j1")
        for _ in range(3):
            self.store.get_record_times("j1")
        self.assertEqual(self.store.get_record_times("j1"), before)

    def test_the_tracker_row_carries_a_local_write_time(self):
        self.store.save_job(self.job, observed_at="2026-10-14T10:00:00+00:00")
        reach_status(self.store, ApplicationStatus.DISCOVERED)
        raw = self.store.get_tracker_raw("j1")
        self.assertTrue(raw["updated_at"], "the tracker row records when the app last wrote it")


class UnreadableStoredRecordTests(unittest.TestCase):
    """A row a damaged or hand-edited database holds must be refused as itself, never as a crash.

    The payloads here are written directly, the way a damaged file or a manual edit would arrive, and
    then read back through the public API. Left alone, those shapes raise four different exception
    types (``KeyError``, ``TypeError``, ``AttributeError``, ``json.JSONDecodeError``), none of which a
    Tk callback or a list refresh catches, so one read of one bad row could take down a whole view.
    Nothing may be repaired, migrated, rewritten, or deleted: the stored payload is compared before and
    after every refused read, and rows that are fine stay readable.
    """

    def setUp(self):
        self.store = CareerStore(":memory:")
        self.addCleanup(self.store.close)

    def _stored_payload(self, table="candidate_profile", key="profile_id", value=1):
        return self.store._connection.execute(
            f"SELECT payload FROM {table} WHERE {key}=?", (value,)
        ).fetchone()["payload"]

    def write_profile_payload(self, payload):
        with self.store._connection:
            self.store._connection.execute(
                "INSERT INTO candidate_profile(profile_id, payload, updated_at) VALUES (1, ?, ?) "
                "ON CONFLICT(profile_id) DO UPDATE SET payload=excluded.payload",
                (payload, _TIMESTAMP),
            )
        return payload

    def write_job_payload(self, payload, listing_id="broken"):
        """Store a raw listing payload, keyed so a duplicate-group lookup finds this same row."""
        self.store.save_job(sample_job(listing_id="healthy"))
        with self.store._connection:
            self.store._connection.execute(
                "INSERT INTO job_listings(listing_id, payload, duplicate_key, first_seen_at, last_seen_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (listing_id, payload, duplicate_key(sample_job(listing_id=listing_id)), _TIMESTAMP, _TIMESTAMP),
            )
        return payload

    def test_the_refusal_is_a_value_error_so_existing_callers_keep_working(self):
        from career_agent import StoredRecordError as exported

        self.assertIs(exported, StoredRecordError)
        self.assertTrue(issubclass(StoredRecordError, ValueError))

    def test_a_profile_holding_a_field_this_version_does_not_know_is_refused(self):
        payload = self.write_profile_payload('{"candidate_country": "India", "nickname": "Ada"}')

        with self.assertRaises(StoredRecordError) as caught:
            self.store.get_profile()

        self.assertIn("candidate profile", str(caught.exception))
        self.assertIn("nickname", str(caught.exception))
        self.assertEqual(self._stored_payload(), payload, "a refused read must change nothing")

    def test_a_profile_payload_that_is_not_a_stored_record_is_refused(self):
        for payload in ("[]", '"career_agent.sqlite3"', "null", "3", "true"):
            with self.subTest(payload=payload):
                self.write_profile_payload(payload)

                with self.assertRaises(StoredRecordError):
                    self.store.get_profile()

                self.assertEqual(self._stored_payload(), payload)

    def test_damaged_profile_text_is_refused_instead_of_escaping_as_a_json_error(self):
        for payload in ('{"candidate_country": "Ind', "", "   ", "{'candidate_country': 'India'}"):
            with self.subTest(payload=payload):
                self.write_profile_payload(payload)

                with self.assertRaises(StoredRecordError) as caught:
                    self.store.get_profile()

                self.assertIn("not valid JSON", str(caught.exception))
                self.assertEqual(self._stored_payload(), payload)

    def test_skills_stored_as_a_string_are_refused_rather_than_split_into_letters(self):
        # frozenset("Python") is a set of six single characters: every later comparison would use
        # skills nobody stated, and the requirement checks would still report a confident answer.
        payload = self.write_profile_payload('{"candidate_country": "India", "skills": "Python"}')

        with self.assertRaises(StoredRecordError) as caught:
            self.store.get_profile()

        self.assertIn("skills", str(caught.exception))
        self.assertEqual(self._stored_payload(), payload)

    def test_an_ordinary_profile_still_reads_after_a_damaged_row_is_refused(self):
        profile = CandidateProfile(candidate_country="India", skills=frozenset({"Python", "RAG"}))
        self.store.save_profile(profile)
        good_payload = self._stored_payload()

        self.assertEqual(self.store.get_profile(), profile)
        self.write_profile_payload("{not json at all}")
        with self.assertRaises(StoredRecordError):
            self.store.get_profile()

        self.write_profile_payload(good_payload)
        self.assertEqual(self.store.get_profile(), profile)

    def test_a_listing_with_no_saved_availability_status_is_refused_on_every_read_path(self):
        payload = self.write_job_payload('{"listing_id": "broken", "employer_name": "Example"}')

        for read in (lambda: self.store.get_job("broken"),
                     self.store.list_jobs,
                     lambda: self.store.find_duplicate_group(sample_job(listing_id="broken"))):
            with self.subTest(read=read):
                with self.assertRaises(StoredRecordError) as caught:
                    read()
                self.assertIn("availability status", str(caught.exception))

        self.assertEqual(self._stored_payload("job_listings", "listing_id", "broken"), payload)

    def test_a_listing_whose_saved_status_is_unknown_to_this_version_is_refused(self):
        payload = self.write_job_payload('{"listing_id": "broken", "availability_status": "probably_open"}')

        with self.assertRaises(StoredRecordError) as caught:
            self.store.get_job("broken")

        self.assertIn("probably_open", str(caught.exception))
        self.assertEqual(self._stored_payload("job_listings", "listing_id", "broken"), payload)

    def test_a_listing_whose_required_skills_are_a_string_is_refused(self):
        self.write_job_payload('{"listing_id": "broken", "availability_status": "open", "required_skills": "Python"}')

        with self.assertRaises(StoredRecordError) as caught:
            self.store.list_jobs()

        self.assertIn("required_skills", str(caught.exception))

    def test_a_refused_listing_read_leaves_the_other_listings_readable(self):
        self.write_job_payload("{not json at all}")

        with self.assertRaises(StoredRecordError):
            self.store.list_jobs()

        self.assertIsNotNone(self.store.get_job("healthy"))
        self.assertEqual(self.store.get_job("healthy").listing_id, "healthy")


if __name__ == "__main__":
    unittest.main(verbosity=2)
