import sqlite3
import tempfile
import unittest
from pathlib import Path

from career_agent import ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, JobListing
from career_agent.store import CareerStore


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
        tracker = ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "Employer confirmation email", True)
        self.store.save_tracker(tracker)
        self.assertEqual(self.store.get_tracker("j1"), tracker)

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
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED))
        with self.assertRaisesRegex(ValueError, "requires evidence"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "   "))
        self.assertIsNone(self.store.get_tracker("j1"))

    def test_confirmation_with_evidence_is_accepted(self):
        tracker = ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "Employer confirmation email", True)
        self.store.save_tracker(tracker)
        self.assertEqual(self.store.get_tracker("j1"), tracker)

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

    def test_backwards_state_change_is_refused(self):
        self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "Employer email", True))
        with self.assertRaisesRegex(ValueError, "Invalid application transition"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.DISCOVERED))


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
        store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED, "Employer email", True))
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
