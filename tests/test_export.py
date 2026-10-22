import json
import tempfile
import unittest
from pathlib import Path

from career_agent import (
    ApplicationStatus, Availability, CandidateProfile, JobListing, build_decision,
    evaluate_eligibility,
)
from career_agent.export import FORMAT_VERSION, build_export_payload, write_export
from career_agent.store import CareerStore


def sample_profile():
    return CandidateProfile(
        candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
        graduation_year=2027, experience_years=0.5, skills=frozenset({"Python", "RAG"}),
        preferred_work_modes=frozenset({"remote"}),
    )


def sample_job():
    return JobListing(
        listing_id="j1", source_id="manual", source_name="Manual",
        source_listing_url="https://jobs.example/role/1", employer_name="Example",
        role_title="AI Intern", availability_status=Availability.OPEN,
        eligibility_scope="restricted", eligible_countries=("India",),
        required_skills=frozenset({"Python"}), provenance_note="Checked today.",
    )


def walk_to_confirmed(store):
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
    return store.save_tracker(tracker.transition(ApplicationStatus.RESPONSE_RECEIVED))


class ExportContractTests(unittest.TestCase):
    def test_format_v4_payload_is_json_serializable(self):
        with CareerStore(":memory:") as store:
            store.save_profile(sample_profile())
            store.save_job(sample_job(), observed_at="2026-10-01T00:00:00+00:00")
            store.start_application("j1")
            payload = build_export_payload(store)
            self.assertEqual(payload["format_version"], FORMAT_VERSION)
            self.assertEqual(payload["format_version"], 4)
            self.assertEqual(payload["schema_version"], 3)
            self.assertIn("exported_at", payload)
            self.assertEqual(payload["profile"]["skills"], ["Python", "RAG"])
            self.assertEqual(payload["profile"]["preferred_work_modes"], ["remote"])
            job = payload["jobs"][0]
            self.assertEqual(job["first_seen_at"], "2026-10-01T00:00:00+00:00")
            self.assertEqual(job["last_seen_at"], "2026-10-01T00:00:00+00:00")
            attempt = job["application_attempts"][0]
            self.assertEqual(attempt["attempt_number"], 1)
            self.assertEqual(attempt["revision"], 0)
            self.assertIn("updated_at", attempt)
            self.assertEqual(payload["jobs"][0]["eligibility_decisions"], [])
            json.dumps(payload)  # must not raise on frozensets/tuples

    def test_decisions_are_exported_without_candidate_values(self):
        with CareerStore(":memory:") as store:
            store.save_profile(CandidateProfile(
                candidate_country="India", skills=frozenset({"Kubernetes"}),
                preferred_locations=frozenset({"Bengaluru"}),
            ))
            store.save_job(sample_job())
            profile = store.get_profile()
            job = store.get_job("j1")
            decision = build_decision(
                profile, job, evaluate_eligibility(profile, job),
                decision_id="d1", evaluated_at="2026-10-22T09:00:00+00:00",
            )
            store.save_eligibility_decision(decision)
            payload = build_export_payload(store)
        records = payload["jobs"][0]["eligibility_decisions"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["decision_id"], "d1")
        self.assertEqual(records[0]["rule_version"], decision.rule_version)
        self.assertEqual(records[0]["outcome"], decision.outcome.value)
        self.assertTrue(records[0]["job_fingerprint"].startswith("fp1:"))
        self.assertEqual(records[0]["profile_fingerprint"], decision.profile_fingerprint)
        serialized = json.dumps(records)
        # No candidate facts are duplicated: the record keeps fingerprints, and the
        # trail carries job-side evidence only.
        self.assertNotIn("Kubernetes", serialized)
        self.assertNotIn("Bengaluru", serialized)
        self.assertNotIn("candidate_country", serialized)

    def test_attempts_and_events_are_preserved_per_attempt(self):
        with CareerStore(":memory:") as store:
            store.save_profile(sample_profile())
            store.save_job(sample_job())
            confirmed = walk_to_confirmed(store)
            store.save_tracker(confirmed.transition(ApplicationStatus.WITHDRAWN))
            store.start_application("j1")

            payload = build_export_payload(store)
            attempts = payload["jobs"][0]["application_attempts"]
            self.assertEqual([a["attempt_number"] for a in attempts], [1, 2])
            self.assertEqual(attempts[0]["status"], "withdrawn")
            self.assertEqual(attempts[0]["status_evidence"], "Employer confirmation page shown")
            self.assertGreater(attempts[0]["revision"], 0)
            self.assertIn("updated_at", attempts[0])
            confirmation = [e for e in attempts[0]["application_events"] if e["to_status"] == "confirmed"]
            self.assertEqual(len(confirmation), 1)
            self.assertEqual(confirmation[0]["evidence"], "Employer confirmation page shown")
            self.assertTrue(confirmation[0]["candidate_confirmed"])
            self.assertEqual(attempts[1]["status"], "discovered")
            self.assertIsNone(attempts[1]["status_evidence"])
            self.assertEqual(len(attempts[1]["application_events"]), 1)

    def test_write_export_round_trips_through_json(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "export.json"
            with CareerStore(":memory:") as store:
                store.save_profile(sample_profile())
                store.save_job(sample_job())
                walk_to_confirmed(store)
                written = write_export(store, destination)
            reloaded = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(reloaded, written)
            self.assertEqual(reloaded["jobs"][0]["application_attempts"][0]["status"], "response_received")


if __name__ == "__main__":
    unittest.main(verbosity=2)
