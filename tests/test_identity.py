"""Tests for cross-source job identity: what counts as proof, and what is left unknown.

Every listing here is synthetic and local. Nothing in this module or its tests contacts a source.
"""
from __future__ import annotations

import unittest

from career_agent.core import Availability, JobListing
from career_agent.identity import (
    BASIS_APPLY_URL, BASIS_LISTING_URL, BASIS_REQUISITION, IdentityError, IdentityVerdict,
    compare_listings, group_by_identity, identity_key, identity_keys, possible_duplicates,
)


def listing(listing_id="l1", *, source_id="jobicy", employer="Example Employer",
            role="GenAI Engineer", url="https://jobs.example.invalid/listing/1",
            apply_url=None, requisition=None, location="Delhi, India") -> JobListing:
    return JobListing(
        listing_id=listing_id, source_id=source_id, source_name=source_id.title(),
        source_listing_url=url, employer_name=employer, role_title=role,
        availability_status=Availability.OPEN, employer_apply_url=apply_url,
        canonical_requisition_id=requisition, location_text=location)


class IdentityKeyTests(unittest.TestCase):
    """The key is shared only where there is evidence, and tied to the source where there is not."""

    def test_a_requisition_id_makes_the_key_shared_across_sources(self):
        first = listing("a", source_id="jobicy", requisition="REQ-42")
        second = listing("b", source_id="elsewhere", requisition=" req-42 ",
                         url="https://other.invalid/jobs/9")
        self.assertEqual(identity_key(first), identity_key(second))

    def test_two_spellings_of_an_id_are_not_merged_by_the_key(self):
        first = listing("a", requisition="REQ-42")
        second = listing("b", requisition="REQ 42", url="https://other.invalid/jobs/9")
        self.assertNotEqual(identity_key(first), identity_key(second),
                            "an identifier is opaque; punctuation is not normalised away")

    def test_two_spellings_of_an_id_are_reported_as_unknown_rather_than_different(self):
        decision = compare_listings(
            listing("a", requisition="REQ-42"),
            listing("b", requisition="REQ 42", url="https://other.invalid/jobs/9"))
        self.assertIs(decision.verdict, IdentityVerdict.UNKNOWN)
        self.assertIn("two spellings", decision.reason)

    def test_the_same_requisition_at_a_different_employer_is_a_different_job(self):
        first = listing("a", employer="Example Employer", requisition="REQ-42")
        second = listing("b", employer="Another Employer", requisition="REQ-42",
                         url="https://other.invalid/jobs/9")
        self.assertNotEqual(identity_key(first), identity_key(second))

    def test_a_shared_employer_page_is_evidence_when_there_is_no_requisition(self):
        first = listing("a", source_id="jobicy", apply_url="https://careers.example.invalid/job/7")
        second = listing("b", source_id="elsewhere", url="https://other.invalid/jobs/9",
                         apply_url="https://careers.example.invalid/job/7/")
        self.assertEqual(identity_key(first), identity_key(second))

    def test_the_same_listing_page_reached_twice_is_one_job(self):
        first = listing("a", source_id="jobicy")
        second = listing("b", source_id="elsewhere")
        self.assertEqual(identity_key(first), identity_key(second))

    def test_without_evidence_the_key_stays_tied_to_its_source(self):
        first = listing("a", source_id="jobicy", url="")
        second = listing("b", source_id="elsewhere", url="")
        self.assertNotEqual(identity_key(first), identity_key(second))
        self.assertTrue(identity_key(first).startswith("source:jobicy:"))

    def test_only_a_listing_can_be_given_a_key(self):
        with self.assertRaises(IdentityError):
            identity_key("the one at that startup")  # type: ignore[arg-type]


class ComparisonTests(unittest.TestCase):
    """Three verdicts, and the third is the one that keeps the application honest."""

    def test_two_records_of_one_requisition_are_the_same_job(self):
        decision = compare_listings(
            listing("a", source_id="jobicy", requisition="REQ-42"),
            listing("b", source_id="elsewhere", requisition="REQ-42",
                    url="https://other.invalid/jobs/9"))
        self.assertIs(decision.verdict, IdentityVerdict.SAME)
        self.assertEqual(decision.basis, BASIS_REQUISITION)
        self.assertTrue(decision.is_same)

    def test_two_requisitions_at_one_employer_are_two_jobs(self):
        decision = compare_listings(
            listing("a", requisition="REQ-42"),
            listing("b", requisition="REQ-43", url="https://other.invalid/jobs/9"))
        self.assertIs(decision.verdict, IdentityVerdict.DIFFERENT)
        self.assertIn("two requisition ids", decision.reason)

    def test_different_employers_are_different_jobs(self):
        decision = compare_listings(listing("a", employer="Example Employer"),
                                    listing("b", employer="Another Employer",
                                            url="https://other.invalid/jobs/9"))
        self.assertIs(decision.verdict, IdentityVerdict.DIFFERENT)

    def test_a_shared_employer_page_is_reported_as_the_basis(self):
        decision = compare_listings(
            listing("a", apply_url="https://careers.example.invalid/job/7"),
            listing("b", url="https://other.invalid/jobs/9",
                    apply_url="https://careers.example.invalid/job/7"))
        self.assertEqual(decision.basis, BASIS_APPLY_URL)

    def test_the_same_page_twice_is_reported_as_the_basis(self):
        decision = compare_listings(listing("a", source_id="jobicy"),
                                    listing("b", source_id="elsewhere"))
        self.assertEqual(decision.basis, BASIS_LISTING_URL)

    def test_the_same_title_at_the_same_employer_is_not_proof_of_anything(self):
        decision = compare_listings(
            listing("a", url="https://jobs.example.invalid/listing/1"),
            listing("b", url="https://jobs.example.invalid/listing/2"))
        self.assertIs(decision.verdict, IdentityVerdict.UNKNOWN,
                      "two openings on two teams would have been merged into one")
        self.assertIn("kept apart", decision.reason)
        self.assertFalse(decision.is_same)

    def test_an_unknown_verdict_is_never_treated_as_a_match(self):
        decision = compare_listings(listing("a", url=""), listing("b", url=""))
        self.assertIs(decision.verdict, IdentityVerdict.UNKNOWN)
        self.assertFalse(decision.is_same)
        self.assertIn("[unknown]", decision.describe())

    def test_only_listings_can_be_compared(self):
        with self.assertRaises(IdentityError):
            compare_listings(listing("a"), {"employer_name": "Example"})  # type: ignore[arg-type]


class GroupingTests(unittest.TestCase):
    """Grouping follows the keys, so a group is always backed by evidence."""

    def test_one_job_seen_on_two_sources_is_one_group_that_says_so(self):
        groups = group_by_identity([
            listing("a", source_id="jobicy", requisition="REQ-42"),
            listing("b", source_id="elsewhere", requisition="REQ-42",
                    url="https://other.invalid/jobs/9"),
        ])
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0].is_cross_source)
        self.assertEqual(groups[0].listing_ids, ("a", "b"))
        self.assertIn("jobicy", groups[0].describe())
        self.assertIn(BASIS_REQUISITION, groups[0].describe())

    def test_two_unproved_listings_stay_two_groups(self):
        groups = group_by_identity([
            listing("a", url="https://jobs.example.invalid/listing/1"),
            listing("b", url="https://jobs.example.invalid/listing/2"),
        ])
        self.assertEqual(len(groups), 2)
        self.assertFalse(any(group.is_cross_source for group in groups))

    def test_the_pairs_nobody_can_settle_are_reported_rather_than_merged(self):
        pairs = possible_duplicates([
            listing("a", url="https://jobs.example.invalid/listing/1"),
            listing("b", url="https://jobs.example.invalid/listing/2"),
        ])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][:2], ("a", "b"))
        self.assertIn("one opening or two", pairs[0][2])

    def test_a_proved_pair_is_not_reported_as_needing_a_look(self):
        self.assertEqual(possible_duplicates([
            listing("a", source_id="jobicy", requisition="REQ-42"),
            listing("b", source_id="elsewhere", requisition="REQ-42",
                    url="https://other.invalid/jobs/9"),
        ]), ())

    def test_listings_at_different_employers_are_not_offered_as_possible_duplicates(self):
        self.assertEqual(possible_duplicates([
            listing("a", employer="Example Employer"),
            listing("b", employer="Another Employer", url="https://other.invalid/jobs/9"),
        ]), ())

    def test_counting_identities_never_merges_what_grouping_would_not(self):
        keys = identity_keys([
            listing("a", source_id="jobicy", requisition="REQ-42"),
            listing("b", source_id="elsewhere", requisition="REQ-42",
                    url="https://other.invalid/jobs/9"),
            listing("c", url="https://jobs.example.invalid/listing/3"),
        ])
        self.assertEqual(len(keys), 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
