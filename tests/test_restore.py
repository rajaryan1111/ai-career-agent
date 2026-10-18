import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from career_agent import (
    ApplicationStatus, Availability, CandidateProfile, ExportFormatError, JobListing,
    RestoreError, build_export_payload, load_export, restore_export, restore_export_file,
    restore_from_backup, validate_export, write_export,
)
from career_agent.export import MAX_BACKUP_BYTES
from career_agent.store import CareerStore


def sample_profile():
    return CandidateProfile(
        candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
        graduation_year=2027, experience_years=0.5, work_authorization="authorized_without_sponsorship",
        skills=frozenset({"Python", "RAG"}), preferred_work_modes=frozenset({"remote"}),
        preferred_locations=frozenset({"Bengaluru"}), preferred_role_types=frozenset({"internship"}),
    )


def sample_job(listing_id="j1", availability=Availability.OPEN, url="https://jobs.example/role/1"):
    return JobListing(
        listing_id=listing_id, source_id="manual", source_name="Manual",
        source_listing_url=url, employer_name="Example", role_title="AI Intern",
        availability_status=availability, employer_apply_url="https://employer.example/apply/1",
        canonical_requisition_id="req-1", location_text="Remote", work_mode="remote",
        role_type="internship", eligibility_scope="restricted", eligible_countries=("India",),
        allowed_degree_disciplines=("ECE",), allowed_study_statuses=("undergraduate",),
        allowed_graduation_years=(2027,), minimum_experience_years=0.0, maximum_experience_years=2.0,
        required_skills=frozenset({"Python", "RAG"}), provenance_note="Checked official listing.",
        allowed_work_authorizations=("authorized_without_sponsorship",),
    )


def seed(store):
    store.save_profile(sample_profile())
    store.save_job(sample_job(), observed_at="2026-10-01T00:00:00+00:00")
    tracker = store.start_application("j1")
    for status in (
        ApplicationStatus.SHORTLISTED,
        ApplicationStatus.PREPARED,
        ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED,
    ):
        tracker = store.save_tracker(tracker.transition(status))
    tracker = store.save_tracker(
        tracker.transition(
            ApplicationStatus.CONFIRMED,
            evidence="Employer confirmation page shown",
            candidate_confirmed=True,
        )
    )
    tracker = store.save_tracker(tracker.transition(ApplicationStatus.RESPONSE_RECEIVED))
    store.save_tracker(tracker.transition(ApplicationStatus.WITHDRAWN))
    store.save_tracker(store.start_application("j1").transition(ApplicationStatus.SHORTLISTED))
    store.save_job(
        sample_job("j2", Availability.UNKNOWN, "https://jobs.example/role/2"),
        observed_at="2026-10-02T00:00:00+00:00",
    )


def snapshot(store):
    jobs = []
    attempts = []
    events = []
    for job in store.list_jobs():
        jobs.append((job, store.job_timestamps(job.listing_id)))
        for attempt in store.list_attempts(job.listing_id):
            attempts.append((attempt, store.attempt_updated_at(job.listing_id, attempt.attempt_number)))
            events.extend(
                (event.listing_id, event.attempt_number, event.from_status, event.to_status,
                 event.evidence, event.candidate_confirmed, event.recorded_at)
                for event in store.list_events(job.listing_id, attempt.attempt_number)
            )
    return {"profile": store.get_profile(), "jobs": jobs, "attempts": attempts, "events": events}


class BackupRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.source_path = Path(self.folder.name) / "source.sqlite3"
        self.source = CareerStore(self.source_path)
        self.addCleanup(self.source.close)
        seed(self.source)
        self.payload = build_export_payload(self.source)

    def target(self, name="target.sqlite3"):
        store = CareerStore(Path(self.folder.name) / name)
        self.addCleanup(store.close)
        return store

    def test_round_trip_preserves_everything_supported(self):
        target = self.target()
        summary = restore_export(target, self.payload)
        self.assertEqual(snapshot(target), snapshot(self.source))
        self.assertEqual(summary["jobs"], 2)
        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(summary["events"], 10)
        self.assertFalse(summary["replaced"])
        self.assertEqual(target.get_tracker("j1", 1).status, ApplicationStatus.WITHDRAWN)
        self.assertEqual(target.get_tracker("j1", 1).status_evidence, "Employer confirmation page shown")
        self.assertEqual(target.get_tracker("j1", 2).status, ApplicationStatus.SHORTLISTED)
        self.assertEqual(target.job_timestamps("j1"), ("2026-10-01T00:00:00+00:00", "2026-10-01T00:00:00+00:00"))

    def test_reexport_matches_the_original_payload(self):
        target = self.target()
        restore_export(target, self.payload)
        again = build_export_payload(target)
        original = deepcopy(self.payload)
        self.assertIsInstance(again.pop("exported_at"), str)
        original.pop("exported_at")
        self.assertEqual(again, original)

    def test_restore_into_non_empty_database_requires_replace_and_changes_nothing(self):
        target = self.target()
        target.save_profile(sample_profile())
        target.save_job(sample_job("other", url="https://jobs.example/other"))
        before = snapshot(target)
        with self.assertRaises(ExportFormatError):
            restore_export(target, self.payload)
        self.assertEqual(snapshot(target), before)

    def test_replace_restore_removes_existing_records(self):
        target = self.target()
        target.save_profile(sample_profile())
        target.save_job(sample_job("other", url="https://jobs.example/other"))
        target.start_application("other")
        summary = restore_export(target, self.payload, replace=True)
        self.assertEqual(summary["replaced"], 1)
        self.assertIsNone(target.get_job("other"))
        self.assertEqual([job.listing_id for job in target.list_jobs()], ["j1", "j2"])
        self.assertEqual(snapshot(target), snapshot(self.source))

    def test_repeated_restore_is_deterministic(self):
        target = self.target()
        restore_export(target, self.payload)
        first = snapshot(target)
        with self.assertRaises(ExportFormatError):
            restore_export(target, self.payload)
        self.assertEqual(snapshot(target), first)
        restore_export(target, self.payload, replace=True)
        self.assertEqual(snapshot(target), first)

    def test_write_and_load_round_trip(self):
        path = Path(self.folder.name) / "backup.json"
        written = write_export(self.source, path)
        loaded = load_export(path)
        self.assertEqual(loaded, written)
        target = self.target("file-target.sqlite3")
        summary = restore_export_file(target, path)
        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(snapshot(target), snapshot(self.source))

    def test_v2_backup_restores_with_documented_defaults(self):
        legacy = deepcopy(self.payload)
        legacy["format_version"] = 2
        legacy.pop("schema_version")
        legacy.pop("exported_at")
        for job in legacy["jobs"]:
            job.pop("first_seen_at")
            job.pop("last_seen_at")
            for attempt in job["application_attempts"]:
                attempt.pop("revision")
                attempt.pop("updated_at")
        target = self.target("v2-target.sqlite3")
        restore_export(target, legacy)
        self.assertEqual(target.get_tracker("j1", 1).revision, 0)
        self.assertEqual(target.get_tracker("j1", 1).status_evidence, "Employer confirmation page shown")
        self.assertEqual(len(target.list_events("j1", 1)), len(self.source.list_events("j1", 1)))


class BackupValidationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        source = CareerStore(Path(self.folder.name) / "source.sqlite3")
        self.addCleanup(source.close)
        seed(source)
        self.payload = build_export_payload(source)

    def assert_invalid(self, payload, message=None):
        with self.assertRaises(ExportFormatError) as caught:
            validate_export(payload)
        if message:
            self.assertIn(message, str(caught.exception))

    def attempt(self, payload, listing_index=0, attempt_index=0):
        return payload["jobs"][listing_index]["application_attempts"][attempt_index]

    def test_unsupported_format_version(self):
        payload = deepcopy(self.payload)
        payload["format_version"] = 4
        self.assert_invalid(payload, "Unsupported backup format version")

    def test_unsupported_schema_version(self):
        payload = deepcopy(self.payload)
        payload["schema_version"] = 3
        self.assert_invalid(payload, "Unsupported database schema version")

    def test_missing_jobs_list(self):
        payload = deepcopy(self.payload)
        payload.pop("jobs")
        self.assert_invalid(payload, "jobs list")

    def test_missing_required_job_field(self):
        payload = deepcopy(self.payload)
        payload["jobs"][0].pop("employer_name")
        self.assert_invalid(payload, "employer_name")

    def test_unknown_field_is_rejected(self):
        payload = deepcopy(self.payload)
        payload["jobs"][0]["unexpected"] = "value"
        self.assert_invalid(payload, "unsupported field")

    def test_unknown_job_status_is_rejected(self):
        payload = deepcopy(self.payload)
        payload["jobs"][0]["availability_status"] = "bogus"
        self.assert_invalid(payload, "availability_status")

    def test_unknown_application_status_is_rejected(self):
        payload = deepcopy(self.payload)
        self.attempt(payload)["status"] = "bogus"
        self.assert_invalid(payload, "unknown application status")

    def test_duplicate_listing_id_is_rejected(self):
        payload = deepcopy(self.payload)
        payload["jobs"].append(deepcopy(payload["jobs"][0]))
        self.assert_invalid(payload, "Duplicate listing_id")

    def test_duplicate_attempt_number_is_rejected(self):
        payload = deepcopy(self.payload)
        job = payload["jobs"][0]
        job["application_attempts"].append(deepcopy(job["application_attempts"][0]))
        with self.assertRaises(ExportFormatError) as caught:
            validate_export(payload)
        self.assertIn("duplicate attempt_number", str(caught.exception))

    def test_confirmed_attempt_without_evidence_is_rejected(self):
        payload = deepcopy(self.payload)
        attempt = self.attempt(payload)
        attempt["status"] = "confirmed"
        attempt["status_evidence"] = None
        self.assert_invalid(payload, "confirmed attempt requires evidence")

    def test_invalid_transition_in_history_is_rejected(self):
        payload = deepcopy(self.payload)
        events = self.attempt(payload)["application_events"]
        events[2]["to_status"] = "interview"
        self.assert_invalid(payload, "invalid transition")

    def test_broken_status_chain_is_rejected(self):
        payload = deepcopy(self.payload)
        events = self.attempt(payload)["application_events"]
        events[2]["from_status"] = "interview"
        self.assert_invalid(payload, "source status does not match")

    def test_history_ending_in_a_different_status_is_rejected(self):
        payload = deepcopy(self.payload)
        attempt = self.attempt(payload)
        attempt["status"] = "interview"
        self.assert_invalid(payload, "history ends at")

    def test_confirmation_event_without_evidence_is_rejected(self):
        payload = deepcopy(self.payload)
        events = self.attempt(payload)["application_events"]
        confirmation = next(event for event in events if event["to_status"] == "confirmed")
        confirmation["evidence"] = None
        self.assert_invalid(payload, "confirmation event requires evidence")

    def test_history_without_events_but_nonzero_revision_is_rejected(self):
        payload = deepcopy(self.payload)
        attempt = self.attempt(payload)
        attempt["application_events"] = []
        self.assert_invalid(payload, "no event history")

    def test_missing_event_timestamp_is_rejected(self):
        payload = deepcopy(self.payload)
        self.attempt(payload)["application_events"][0].pop("recorded_at")
        self.assert_invalid(payload, "recorded_at")

    def test_empty_optional_evidence_is_rejected(self):
        payload = deepcopy(self.payload)
        self.attempt(payload)["application_events"][0]["evidence"] = "   "
        self.assert_invalid(payload, "must not be blank")


class BackupFileTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "backup.json"

    def test_empty_file_is_rejected(self):
        self.path.write_text("", encoding="utf-8")
        with self.assertRaises(ExportFormatError):
            load_export(self.path)

    def test_invalid_json_is_rejected(self):
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ExportFormatError) as caught:
            load_export(self.path)
        self.assertIn("not valid JSON", str(caught.exception))

    def test_invalid_encoding_is_rejected(self):
        self.path.write_bytes(b"\xff\xfe\x00broken")
        with self.assertRaises(ExportFormatError) as caught:
            load_export(self.path)
        self.assertIn("UTF-8", str(caught.exception))

    def test_non_object_root_is_rejected(self):
        self.path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(ExportFormatError):
            load_export(self.path)

    def test_oversized_file_is_rejected(self):
        self.path.write_bytes(b"{}")
        with mock.patch("career_agent.export.MAX_BACKUP_BYTES", 1):
            with self.assertRaises(ExportFormatError) as caught:
                load_export(self.path)
        self.assertIn("safety limit", str(caught.exception))
        self.assertGreater(MAX_BACKUP_BYTES, 1)

    def test_missing_file_is_rejected(self):
        with self.assertRaises(ExportFormatError):
            load_export(Path(self.folder.name) / "missing.json")


class RestoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        source = CareerStore(Path(self.folder.name) / "source.sqlite3")
        self.addCleanup(source.close)
        seed(source)
        self.payload = build_export_payload(source)

    def blocked_target(self, name="blocked.sqlite3", *, seed_target=True):
        store = CareerStore(Path(self.folder.name) / name)
        self.addCleanup(store.close)
        if seed_target:
            store.save_profile(sample_profile())
            store.save_job(sample_job("original", url="https://jobs.example/original"))
            store.start_application("original")
        store._connection.execute(
            """CREATE TRIGGER fail_import_events BEFORE INSERT ON application_events
               WHEN NEW.listing_id = 'j1'
               BEGIN SELECT RAISE(ABORT, 'simulated import failure'); END"""
        )
        store._connection.commit()
        return store

    def test_failed_replace_restore_rolls_back_and_keeps_original_database(self):
        target = self.blocked_target()
        before = snapshot(target)
        with self.assertRaises(RestoreError):
            restore_export(target, self.payload, replace=True)
        self.assertEqual(snapshot(target), before)
        self.assertIsNotNone(target.get_job("original"))
        self.assertEqual(target.list_jobs()[0].listing_id, "original")

    def test_failed_restore_into_empty_database_leaves_it_empty(self):
        target = self.blocked_target("empty-target.sqlite3", seed_target=False)
        with self.assertRaises(RestoreError):
            restore_export(target, self.payload)
        self.assertFalse(target.has_data())

    def test_database_remains_usable_after_a_failed_restore(self):
        target = self.blocked_target()
        with self.assertRaises(RestoreError):
            restore_export(target, self.payload, replace=True)
        target.save_job(sample_job("after-failure", url="https://jobs.example/after"))
        started = target.start_application("after-failure")
        saved = target.save_tracker(started.transition(ApplicationStatus.SHORTLISTED))
        self.assertEqual(saved.status, ApplicationStatus.SHORTLISTED)


class RestoreConfirmationTests(unittest.TestCase):
    """The interactive flow validates first, asks, and only then writes."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        source = CareerStore(Path(self.folder.name) / "source.sqlite3")
        self.addCleanup(source.close)
        seed(source)
        self.backup_path = Path(self.folder.name) / "backup.json"
        write_export(source, self.backup_path)

    def existing_target(self):
        store = CareerStore(Path(self.folder.name) / "target.sqlite3")
        self.addCleanup(store.close)
        store.save_profile(sample_profile())
        store.save_job(sample_job("kept", url="https://jobs.example/kept"))
        store.start_application("kept")
        return store

    def test_declining_confirmation_leaves_the_database_untouched(self):
        target = self.existing_target()
        before = snapshot(target)
        summary = restore_from_backup(target, self.backup_path, confirm=lambda counts: False)
        self.assertIsNone(summary)
        self.assertEqual(snapshot(target), before)
        self.assertIsNotNone(target.get_job("kept"))
        self.assertIsNone(target.get_job("j1"))
        target.save_job(sample_job("after-cancel", url="https://jobs.example/after"))
        self.assertIsNotNone(target.get_job("after-cancel"))

    def test_confirmation_receives_counts_and_restores_only_on_approval(self):
        target = self.existing_target()
        seen = []

        def confirm(counts):
            seen.append(dict(counts))
            return True

        summary = restore_from_backup(target, self.backup_path, confirm=confirm)
        self.assertEqual(seen, [{"profile": 1, "jobs": 2, "attempts": 2, "events": 10}])
        self.assertEqual(summary["jobs"], 2)
        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(summary["events"], 10)
        self.assertEqual(summary["replaced"], 1)
        self.assertIsNone(target.get_job("kept"))
        self.assertIsNotNone(target.get_job("j1"))
        self.assertEqual(
            [attempt.status for attempt in target.list_attempts("j1")],
            [ApplicationStatus.WITHDRAWN, ApplicationStatus.SHORTLISTED],
        )

    def test_empty_database_restores_without_asking(self):
        target = CareerStore(Path(self.folder.name) / "empty.sqlite3")
        self.addCleanup(target.close)

        def confirm(counts):  # pragma: no cover - must never run
            raise AssertionError("an empty database needs no confirmation")

        summary = restore_from_backup(target, self.backup_path, confirm=confirm)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["replaced"], 0)
        self.assertEqual(target.get_profile(), sample_profile())
        self.assertEqual(target.list_events("j1", 1)[0].to_status, ApplicationStatus.DISCOVERED)

    def test_missing_confirmation_refuses_to_replace_existing_data(self):
        target = self.existing_target()
        before = snapshot(target)
        with self.assertRaises(ExportFormatError):
            restore_from_backup(target, self.backup_path)
        self.assertEqual(snapshot(target), before)

    def test_invalid_backup_is_rejected_before_confirmation_is_asked(self):
        target = self.existing_target()
        before = snapshot(target)
        broken = Path(self.folder.name) / "broken.json"
        payload = self.payload_with_broken_history()
        broken.write_text(json.dumps(payload), encoding="utf-8")
        asked = []

        def confirm(counts):  # pragma: no cover - must never run
            asked.append(counts)
            return True

        with self.assertRaises(ExportFormatError):
            restore_from_backup(target, broken, confirm=confirm)
        self.assertEqual(asked, [])
        self.assertEqual(snapshot(target), before)

    def payload_with_broken_history(self):
        payload = json.loads(self.backup_path.read_text(encoding="utf-8"))
        attempt = payload["jobs"][0]["application_attempts"][0]
        attempt["status"] = "confirmed"
        attempt["status_evidence"] = "tampered"
        return payload


if __name__ == "__main__":
    unittest.main(verbosity=2)
