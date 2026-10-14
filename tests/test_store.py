import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_agent import ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, JobListing
from career_agent.store import CareerStore

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
        self.assertEqual(version, 1)

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
            self.assertEqual(reopened._connection.execute("PRAGMA user_version").fetchone()[0], 1)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
