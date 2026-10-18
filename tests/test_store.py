import json
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from career_agent import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, JobListing,
    StaleApplicationError,
)
from career_agent.store import CareerStore, _SCHEMA_VERSION


def sample_job(listing_id="j1", **overrides):
    values = dict(
        listing_id=listing_id, source_id="s1", source_name="test",
        source_listing_url="https://jobs.example/role/1", employer_name="Example",
        role_title="AI Intern", availability_status=Availability.OPEN,
        employer_apply_url="https://employer.example/apply/1", eligibility_scope="restricted",
        eligible_countries=("India",), allowed_work_authorizations=("authorized_without_sponsorship",),
        allowed_degree_disciplines=("ECE",), allowed_study_statuses=("undergraduate",),
        allowed_graduation_years=(2027,), required_skills=frozenset({"Python", "RAG"}),
        provenance_note="Manually checked test listing.",
    )
    values.update(overrides)
    return JobListing(**values)


class CareerStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = CareerStore(":memory:")
        self.job = sample_job()

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

    def test_duplicate_group_uses_conservative_key(self):
        self.store.save_job(self.job)
        duplicate = JobListing(**{**self.job.__dict__, "listing_id": "j2", "source_id": "s2", "source_listing_url": "https://jobs.example/role/1?utm_source=feed"})
        self.store.save_job(duplicate)
        self.assertEqual({j.listing_id for j in self.store.find_duplicate_group(self.job)}, {"j1", "j2"})

    def test_saving_a_job_does_not_fabricate_a_tracker(self):
        """C7: a job with no stored attempt must read back as absent, not as discovered."""
        self.store.save_job(self.job)
        self.assertIsNone(self.store.get_tracker("j1"))
        self.assertEqual(self.store.list_attempts("j1"), ())


class ApplicationAttemptTests(unittest.TestCase):
    """Regression coverage for audit findings C1-C7."""

    def setUp(self):
        self.store = CareerStore(":memory:")
        self.store.save_job(sample_job())

    def tearDown(self):
        self.store.close()

    def attempt(self, listing_id="j1"):
        return self.store.start_application(listing_id)

    def walk_to_submission(self, listing_id="j1"):
        tracker = self.attempt(listing_id)
        for status in (
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.PREPARED,
            ApplicationStatus.AWAITING_USER,
            ApplicationStatus.SUBMISSION_ATTEMPTED,
        ):
            tracker = self.store.save_tracker(tracker.transition(status))
        return tracker

    def confirm(self, tracker, evidence="Employer confirmation page shown"):
        return self.store.save_tracker(
            tracker.transition(ApplicationStatus.CONFIRMED, evidence=evidence, candidate_confirmed=True)
        )

    # ---------------------------------------------------------------- C1

    def test_confirmation_evidence_survives_a_later_status_change(self):
        confirmed = self.confirm(self.walk_to_submission())
        response = self.store.save_tracker(confirmed.transition(ApplicationStatus.RESPONSE_RECEIVED))
        self.assertEqual(response.status, ApplicationStatus.RESPONSE_RECEIVED)
        self.assertEqual(response.status_evidence, "Employer confirmation page shown")
        self.assertTrue(response.candidate_confirmed)

    def test_store_carries_evidence_forward_if_caller_omits_it(self):
        confirmed = self.confirm(self.walk_to_submission())
        edited = ApplicationTracker(
            "j1", ApplicationStatus.RESPONSE_RECEIVED, None, True, confirmed.attempt_number, confirmed.revision,
        )
        response = self.store.save_tracker(edited)
        self.assertEqual(response.status_evidence, "Employer confirmation page shown")

    def test_event_history_keeps_the_evidence_each_event_recorded(self):
        confirmed = self.confirm(self.walk_to_submission())
        self.store.save_tracker(confirmed.transition(ApplicationStatus.RESPONSE_RECEIVED))
        events = self.store.list_events("j1")
        self.assertEqual(len(events), 7)  # attempt + 4 transitions + confirm + response
        confirmation = [e for e in events if e.to_status is ApplicationStatus.CONFIRMED]
        self.assertEqual(len(confirmation), 1)
        self.assertEqual(confirmation[0].evidence, "Employer confirmation page shown")
        self.assertTrue(confirmation[0].candidate_confirmed)
        self.assertEqual(events[-1].to_status, ApplicationStatus.RESPONSE_RECEIVED)
        self.assertEqual(events[-1].evidence, "Employer confirmation page shown")

    def test_history_and_evidence_survive_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "career.sqlite3"
            with CareerStore(path) as first:
                first.save_job(sample_job())
                tracker = first.start_application("j1")
                for status in (ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER):
                    tracker = first.save_tracker(tracker.transition(status))
                tracker = first.save_tracker(tracker.transition(ApplicationStatus.SUBMISSION_ATTEMPTED))
                tracker = first.save_tracker(
                    tracker.transition(
                        ApplicationStatus.CONFIRMED,
                        evidence="Employer confirmation page shown",
                        candidate_confirmed=True,
                    )
                )
            with CareerStore(path) as second:
                reloaded = second.get_tracker("j1")
                self.assertEqual(reloaded.status, ApplicationStatus.CONFIRMED)
                self.assertEqual(reloaded.status_evidence, "Employer confirmation page shown")
                self.assertEqual(len(second.list_events("j1")), 6)

    # ---------------------------------------------------------------- C2

    def test_withdrawal_then_reapplication_creates_a_new_attempt(self):
        first = self.confirm(self.walk_to_submission())
        withdrawn = self.store.save_tracker(first.transition(ApplicationStatus.WITHDRAWN))
        self.assertTrue(withdrawn.is_terminal)

        second = self.store.start_application("j1")
        self.assertEqual(second.attempt_number, 2)
        self.assertEqual(second.status, ApplicationStatus.DISCOVERED)
        self.assertIsNone(second.status_evidence)
        self.assertFalse(second.candidate_confirmed)

        preserved = self.store.get_tracker("j1", attempt_number=1)
        self.assertEqual(preserved.status, ApplicationStatus.WITHDRAWN)
        self.assertEqual(preserved.status_evidence, "Employer confirmation page shown")
        self.assertTrue(preserved.candidate_confirmed)

    def test_reapplication_does_not_copy_attempt_events(self):
        withdrawn = self.store.save_tracker(self.attempt().transition(ApplicationStatus.WITHDRAWN))
        self.assertEqual(withdrawn.attempt_number, 1)
        self.store.start_application("j1")
        self.assertEqual(len(self.store.list_events("j1", attempt_number=1)), 2)
        self.assertEqual(
            [(e.attempt_number, e.to_status, e.evidence) for e in self.store.list_events("j1", attempt_number=2)],
            [(2, ApplicationStatus.DISCOVERED, None)],
        )

    def test_reapplication_is_refused_while_an_attempt_is_active(self):
        self.attempt()
        with self.assertRaisesRegex(ValueError, "finish or withdraw"):
            self.store.start_application("j1")

    def test_repeated_reapplication_clicks_are_refused(self):
        self.store.save_tracker(self.attempt().transition(ApplicationStatus.WITHDRAWN))
        self.store.start_application("j1")
        with self.assertRaises(ValueError):
            self.store.start_application("j1")
        self.assertEqual(len(self.store.list_attempts("j1")), 2)

    def test_reapplication_is_refused_after_rejection(self):
        tracker = self.walk_to_submission()
        self.store.save_tracker(tracker.transition(ApplicationStatus.CONFIRMED, evidence="Employer email"))
        tracker = self.store.get_tracker("j1")
        self.store.save_tracker(tracker.transition(ApplicationStatus.REJECTED_BY_EMPLOYER))
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.store.start_application("j1")

    def test_reapplication_is_refused_when_the_listing_is_closed(self):
        self.store.save_tracker(self.attempt().transition(ApplicationStatus.WITHDRAWN))
        self.store.save_job(sample_job(availability_status=Availability.CLOSED))
        with self.assertRaisesRegex(ValueError, "closed"):
            self.store.start_application("j1")

    def test_shortlisting_the_second_attempt_is_allowed(self):
        self.store.save_tracker(self.attempt().transition(ApplicationStatus.WITHDRAWN))
        second = self.store.start_application("j1")
        shortlisted = self.store.save_tracker(second.transition(ApplicationStatus.SHORTLISTED))
        self.assertEqual((shortlisted.attempt_number, shortlisted.status), (2, ApplicationStatus.SHORTLISTED))

    def test_get_tracker_defaults_to_the_latest_attempt(self):
        self.store.save_tracker(self.attempt().transition(ApplicationStatus.WITHDRAWN))
        self.store.start_application("j1")
        self.assertEqual(self.store.get_tracker("j1").attempt_number, 2)
        self.assertEqual([t.attempt_number for t in self.store.list_attempts("j1")], [1, 2])

    # ---------------------------------------------------------------- C3

    def test_confirmed_cannot_be_inserted_without_evidence(self):
        with self.assertRaisesRegex(ValueError, "Confirmation requires evidence"):
            self.store.save_tracker(ApplicationTracker("j1", ApplicationStatus.CONFIRMED))

    def test_confirmed_cannot_be_reached_without_evidence(self):
        attempted = self.walk_to_submission()
        with self.assertRaisesRegex(ValueError, "Confirmation requires evidence"):
            self.store.save_tracker(
                ApplicationTracker("j1", ApplicationStatus.CONFIRMED, None, False, 1, attempted.revision)
            )

    def test_skipped_transition_cannot_be_persisted(self):
        tracker = self.attempt()
        skipped = ApplicationTracker("j1", ApplicationStatus.PREPARED, None, False, 1, tracker.revision)
        with self.assertRaisesRegex(ValueError, "Invalid application transition"):
            self.store.save_tracker(skipped)
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.DISCOVERED)

    def test_schema_rejects_unknown_status_text(self):
        self.attempt()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store._connection.execute(
                "UPDATE application_tracker SET status='bogus' WHERE listing_id='j1'"
            )

    def test_schema_rejects_confirmed_without_evidence(self):
        self.attempt()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store._connection.execute(
                "UPDATE application_tracker SET status='confirmed', status_evidence=NULL WHERE listing_id='j1'"
            )

    # ---------------------------------------------------------------- C4

    def test_duplicate_observation_cannot_be_shortlisted_twice(self):
        self.store.save_job(sample_job("j2", source_listing_url="https://jobs.example/role/1?utm_source=feed"))
        first = self.attempt("j1")
        self.store.save_tracker(first.transition(ApplicationStatus.SHORTLISTED))
        second = self.attempt("j2")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.store.save_tracker(second.transition(ApplicationStatus.SHORTLISTED))

    def test_discovered_duplicate_does_not_block_shortlisting(self):
        """A sibling observation that was never shortlisted is not an active application."""
        self.store.save_job(sample_job("j2", source_listing_url="https://jobs.example/role/1?utm_source=feed"))
        self.attempt("j2")
        first = self.attempt("j1")
        shortlisted = self.store.save_tracker(first.transition(ApplicationStatus.SHORTLISTED))
        self.assertEqual(shortlisted.status, ApplicationStatus.SHORTLISTED)
        self.assertEqual(self.store.get_tracker("j2").status, ApplicationStatus.DISCOVERED)

    def test_duplicate_guard_releases_after_withdrawal(self):
        self.store.save_job(sample_job("j2", source_listing_url="https://jobs.example/role/1?utm_source=feed"))
        first = self.store.save_tracker(self.attempt("j1").transition(ApplicationStatus.SHORTLISTED))
        self.store.save_tracker(first.transition(ApplicationStatus.WITHDRAWN))
        second = self.attempt("j2")
        shortlisted = self.store.save_tracker(second.transition(ApplicationStatus.SHORTLISTED))
        self.assertEqual(shortlisted.status, ApplicationStatus.SHORTLISTED)

    # ---------------------------------------------------------------- C5

    def test_stale_revision_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "career.sqlite3"
            with CareerStore(path) as first, CareerStore(path) as second:
                first.save_job(sample_job())
                first.start_application("j1")
                window_a = first.get_tracker("j1")
                window_b = second.get_tracker("j1")
                first.save_tracker(window_a.transition(ApplicationStatus.SHORTLISTED))
                with self.assertRaises(StaleApplicationError):
                    second.save_tracker(window_b.transition(ApplicationStatus.WITHDRAWN))
                self.assertEqual(first.get_tracker("j1").status, ApplicationStatus.SHORTLISTED)

    def test_reloading_after_a_conflict_allows_the_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "career.sqlite3"
            with CareerStore(path) as first, CareerStore(path) as second:
                first.save_job(sample_job())
                first.start_application("j1")
                stale = second.get_tracker("j1")
                first.save_tracker(first.get_tracker("j1").transition(ApplicationStatus.SHORTLISTED))
                with self.assertRaises(StaleApplicationError):
                    second.save_tracker(stale.transition(ApplicationStatus.WITHDRAWN))
                fresh = second.get_tracker("j1")
                saved = second.save_tracker(fresh.transition(ApplicationStatus.PREPARED))
                self.assertEqual(saved.status, ApplicationStatus.PREPARED)
                self.assertEqual(saved.revision, 2)

    # ---------------------------------------------------------------- C6

    def test_same_status_evidence_update_is_persisted_and_audited(self):
        confirmed = self.confirm(self.walk_to_submission())
        updated = self.store.save_tracker(
            confirmed.transition(ApplicationStatus.CONFIRMED, evidence="Offer letter received")
        )
        self.assertEqual(updated.status_evidence, "Offer letter received")
        self.assertEqual(updated.status, ApplicationStatus.CONFIRMED)
        self.assertEqual(self.store.get_tracker("j1").status_evidence, "Offer letter received")
        self.assertEqual(self.store.list_events("j1")[-1].evidence, "Offer letter received")

    def test_repeated_identical_save_is_a_noop(self):
        tracker = self.attempt()
        again = self.store.save_tracker(tracker)
        self.assertEqual(again.revision, tracker.revision)
        self.assertEqual(len(self.store.list_events("j1")), 1)

    # ------------------------------------------------------- history/cascade

    def test_deleting_the_job_removes_attempts_and_events(self):
        self.store.save_tracker(self.attempt().transition(ApplicationStatus.WITHDRAWN))
        self.store.start_application("j1")
        self.assertTrue(self.store.delete_job("j1"))
        self.assertEqual(self.store.list_attempts("j1"), ())
        self.assertEqual(self.store.list_events("j1"), ())


class MigrationTests(unittest.TestCase):
    V1_SCHEMA = """
        CREATE TABLE candidate_profile (
            profile_id INTEGER PRIMARY KEY CHECK (profile_id = 1),
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE job_listings (
            listing_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            duplicate_key TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE INDEX idx_job_duplicate_key ON job_listings(duplicate_key);
        CREATE TABLE application_tracker (
            listing_id TEXT PRIMARY KEY REFERENCES job_listings(listing_id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            status_evidence TEXT,
            candidate_confirmed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
    """

    def _v1_database(self, folder, *, status="confirmed", evidence="Legacy employer email", confirmed=1):
        path = Path(folder) / "v1.sqlite3"
        job = sample_job()
        payload = json.dumps({
            "listing_id": "j1", "source_id": "manual", "source_name": "Manual",
            "source_listing_url": "https://jobs.example/role/1", "employer_name": "Example",
            "role_title": "AI Intern", "availability_status": "open",
        })
        connection = sqlite3.connect(path)
        connection.executescript(self.V1_SCHEMA)
        connection.execute(
            "INSERT INTO job_listings VALUES (?, ?, ?, ?, ?)",
            ("j1", payload, "url:https://jobs.example/role/1", "2026-10-13T00:00:00+00:00", "2026-10-13T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO application_tracker VALUES (?, ?, ?, ?, ?)",
            ("j1", status, evidence, confirmed, "2026-10-13T00:00:00+00:00"),
        )
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        connection.close()
        return path

    def test_v1_tracker_becomes_attempt_one(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._v1_database(folder)
            with CareerStore(path) as store:
                migrated = store.get_tracker("j1")
                self.assertEqual(migrated.attempt_number, 1)
                self.assertEqual(migrated.revision, 0)
                self.assertEqual(migrated.status, ApplicationStatus.CONFIRMED)
                self.assertEqual(migrated.status_evidence, "Legacy employer email")
                self.assertTrue(migrated.candidate_confirmed)
                self.assertEqual(store._connection.execute("PRAGMA user_version").fetchone()[0], _SCHEMA_VERSION)
                # History before the migration is not invented.
                self.assertEqual(store.list_events("j1"), ())

    def test_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._v1_database(folder)
            for _ in range(3):
                with CareerStore(path) as store:
                    self.assertEqual(len(store.list_attempts("j1")), 1)
                    self.assertEqual(store.get_tracker("j1").revision, 0)

    def test_migration_accepts_withdrawn_legacy_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._v1_database(folder, status="withdrawn", evidence=None, confirmed=0)
            with CareerStore(path) as store:
                self.assertEqual(store.get_tracker("j1").status, ApplicationStatus.WITHDRAWN)

    def test_migration_refuses_invalid_legacy_status(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._v1_database(folder, status="bogus", evidence=None, confirmed=0)
            with self.assertRaisesRegex(RuntimeError, "schema-2 constraints"):
                CareerStore(path)

    def test_fresh_database_is_written_at_the_current_version(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fresh.sqlite3"
            with CareerStore(path) as store:
                self.assertEqual(store._connection.execute("PRAGMA user_version").fetchone()[0], _SCHEMA_VERSION)

    def test_future_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "future.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA user_version = 99")
            connection.commit()
            connection.close()
            with self.assertRaisesRegex(RuntimeError, "newer than supported"):
                CareerStore(path)


@unittest.skipUnless(os.name == "posix", "POSIX permissions are required for this check")
class DatabasePermissionTests(unittest.TestCase):
    def test_new_database_file_is_readable_only_by_its_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.sqlite3"
            with CareerStore(path) as store:
                store.save_profile(CandidateProfile(candidate_country="India"))
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(oct(mode), oct(0o600))

    def test_a_permissive_existing_database_is_tightened_on_open(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "loose.sqlite3"
            with CareerStore(path):
                pass
            os.chmod(path, 0o644)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
            with CareerStore(path):
                pass
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_in_memory_databases_are_unaffected(self):
        with CareerStore(":memory:") as store:
            store.save_profile(CandidateProfile(candidate_country="India"))
            self.assertTrue(store.has_data())


class DeleteAllDataTests(unittest.TestCase):
    def setUp(self):
        self.store = CareerStore(":memory:")
        self.addCleanup(self.store.close)

    def seed(self):
        self.store.save_profile(CandidateProfile(candidate_country="India", skills=frozenset({"Python"})))
        self.store.save_job(sample_job("j1"))
        tracker = self.store.start_application("j1")
        self.store.save_tracker(tracker.transition(ApplicationStatus.SHORTLISTED))

    def test_deletes_every_record_and_reports_counts(self):
        self.seed()
        counts = self.store.delete_all_data()
        self.assertEqual(counts, {"profile": 1, "jobs": 1, "attempts": 1, "events": 2})
        self.assertFalse(self.store.has_data())
        self.assertIsNone(self.store.get_profile())
        self.assertEqual(self.store.list_jobs(), ())
        self.assertEqual(self.store.list_attempts("j1"), ())
        self.assertEqual(self.store.list_events("j1"), ())

    def test_empty_database_is_a_safe_no_op(self):
        self.assertEqual(
            self.store.delete_all_data(),
            {"profile": 0, "jobs": 0, "attempts": 0, "events": 0},
        )

    def test_database_remains_usable_after_deletion(self):
        self.seed()
        self.store.delete_all_data()
        self.store.save_job(sample_job("j2"))
        started = self.store.start_application("j2")
        saved = self.store.save_tracker(started.transition(ApplicationStatus.SHORTLISTED))
        self.assertEqual(saved.status, ApplicationStatus.SHORTLISTED)
        self.assertEqual(self.store.list_events("j2")[-1].to_status, ApplicationStatus.SHORTLISTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
