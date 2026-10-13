import unittest

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
            required_skills=frozenset({"Python", "RAG"}),
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
