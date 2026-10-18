"""Building a first tailored document, and writing it out.

Everything about lineage was enforced on documents that only Python could create: the builders had
no caller, and `rebuild_artifact` could only rebuild something already stored. These tests cover the
path that makes a *first* one - look at what would be used, store exactly that, write it to a file -
and they are mostly about the ways that path could quietly lie: a document stored under a strategy
that moved while it was being read, a second identical copy, a stale document exported as if it were
current, and an export landing on top of the résumé it was built from.
"""
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest import mock

from career_agent.artifacts import (
    ArtifactError, ArtifactKind, StaleArtifactError, capture_basis, export_artifact,
    export_provenance, lineage_status, plan_artifact, store_planned_artifact,
)
from career_agent.core import (
    Availability, CandidateProfile, EmploymentType, FactSource, JobListing,
)
from career_agent.store import CareerStore

PROFILE = CandidateProfile(
    candidate_country="India", degree_discipline="ECE", graduation_year=2027,
    experience_years=1.0, work_authorization="citizen",
    skills=frozenset({"Python", "SQL", "PyTorch"}),
    preferred_locations=frozenset({"Delhi"}),
)

LISTING = JobListing(
    listing_id="j1", source_id="manual", source_name="Manual entry",
    source_listing_url="https://jobs.example.invalid/role/1", employer_name="Example Employer",
    role_title="GenAI Engineer", availability_status=Availability.OPEN,
    required_skills=frozenset({"Python", "Docker"}), location_text="Delhi, India",
    work_mode="hybrid",
)


class BuildTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        self.store = CareerStore(self.root / "build.sqlite3")
        self.addCleanup(self.store.close)
        self.store.save_profile(PROFILE, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                                document_name="example-resume.docx")
        self.store.save_job(LISTING)
        self.store.add_work_history("Example Systems", "Intern", date(2026, 1, 1),
                                    is_current=True,
                                    employment_type=EmploymentType.INTERNSHIP,
                                    summary="Built data pipelines")
        self.store.add_education("Example Institute", "B.Tech", discipline="ECE",
                                 start_date=date(2023, 8, 1))
        self.strategy = self.store.create_role_strategy(
            name="Applied AI roles, Delhi NCR", role_family="Applied AI engineering",
            seniority="early", locations=frozenset({"Delhi"}),
            work_modes=frozenset({"hybrid"}), employment_types=frozenset({"full-time"}),
            required_skills=frozenset({"Python", "Docker"}),
            preferred_skills=frozenset({"PyTorch"}))

    def plan(self, kind: ArtifactKind = ArtifactKind.TAILORED_RESUME, **overrides):
        return plan_artifact(
            self.store, listing_id=overrides.get("listing_id", "j1"),
            strategy_id=overrides.get("strategy_id", self.strategy.strategy_id), kind=kind)


class PlanningTests(BuildTestCase):
    def test_a_plan_says_what_would_be_used_and_writes_nothing(self):
        before = self.store._connection.total_changes
        plan = self.plan()
        self.assertEqual(plan.listing_id, "j1")
        self.assertEqual(plan.strategy_version, 1)
        self.assertIn("Python", plan.content)
        self.assertEqual(self.store._connection.total_changes, before)
        self.assertEqual(self.store.list_tailored_artifacts(), ())

    def test_the_plan_reports_the_requirements_the_profile_does_not_state(self):
        plan = self.plan()
        self.assertIn("Docker", " ".join(plan.gaps))
        described = "\n".join(plan.describe())
        self.assertIn("do not state", described)
        self.assertNotIn("Docker", plan.content,
                         "the document claimed a skill the saved facts do not state")

    def test_the_plan_names_the_documents_the_facts_were_read_from(self):
        plan = self.plan()
        described = "\n".join(plan.describe())
        self.assertIn("example-resume.docx", described)
        self.assertIn("Still unconfirmed:", described)

    def test_a_listing_or_strategy_that_is_not_stored_is_refused(self):
        with self.assertRaises(ArtifactError) as caught:
            self.plan(listing_id="nope")
        self.assertIn("not stored", str(caught.exception))
        with self.assertRaises(ArtifactError) as caught:
            self.plan(strategy_id="strategy-nope")
        self.assertIn("no preferences to follow", str(caught.exception))

    def test_screening_answers_are_refused_rather_than_generated(self):
        with self.assertRaises(ArtifactError) as caught:
            self.plan(ArtifactKind.SCREENING_ANSWERS)
        self.assertIn("written by the person", str(caught.exception))

    def test_a_profile_that_is_not_saved_yet_is_refused(self):
        empty = CareerStore(self.root / "empty.sqlite3")
        self.addCleanup(empty.close)
        empty.save_job(LISTING)
        strategy = empty.create_role_strategy(
            name="Applied AI roles", role_family="Applied AI engineering")
        with self.assertRaises(ArtifactError) as caught:
            plan_artifact(empty, listing_id="j1", strategy_id=strategy.strategy_id,
                          kind=ArtifactKind.TAILORED_RESUME)
        self.assertIn("no profile is saved yet", str(caught.exception))

    def test_a_cover_letter_is_planned_from_the_listing_as_well(self):
        plan = self.plan(ArtifactKind.COVER_LETTER)
        self.assertIn("Example Employer", plan.content)
        self.assertEqual(plan.kind, ArtifactKind.COVER_LETTER)


class StoringTests(BuildTestCase):
    def test_storing_a_plan_writes_exactly_what_was_planned_with_its_lineage(self):
        plan = self.plan()
        artifact = store_planned_artifact(self.store, plan)
        self.assertEqual(artifact.content, plan.content)
        self.assertEqual(artifact.strategy_id, self.strategy.strategy_id)
        self.assertEqual(artifact.strategy_version, 1)
        self.assertEqual(artifact.listing_id, "j1")
        self.assertEqual(artifact.basis, plan.basis)
        self.assertTrue(artifact.created_at)
        stored = self.store.get_tailored_artifact(artifact.artifact_id)
        self.assertEqual(stored.content, plan.content)
        self.assertTrue(lineage_status(self.store, stored).is_current)

    def test_a_strategy_that_moved_while_the_document_was_read_is_refused(self):
        plan = self.plan()
        self.store.revise_role_strategy(
            self.strategy.strategy_id, name=self.strategy.name,
            role_family=self.strategy.role_family,
            required_skills=frozenset({"Python", "Docker", "Kubernetes"}))
        with self.assertRaises(ArtifactError) as caught:
            store_planned_artifact(self.store, plan)
        self.assertIn("moved to version 2", str(caught.exception))
        self.assertEqual(self.store.list_tailored_artifacts(), ())

    def test_facts_that_changed_while_the_document_was_read_are_refused(self):
        plan = self.plan()
        self.store.save_profile(
            replace(PROFILE, skills=frozenset({"Python", "SQL", "PyTorch", "Docker"})),
            source=FactSource.EXTRACTED_FROM_DOCUMENT, document_name="example-resume.docx")
        with self.assertRaises(ArtifactError) as caught:
            store_planned_artifact(self.store, plan)
        self.assertIn("facts changed while", str(caught.exception))
        self.assertEqual(self.store.list_tailored_artifacts(), ())

    def test_a_listing_deleted_while_the_document_was_read_is_refused(self):
        plan = self.plan()
        self.store.delete_job("j1")
        with self.assertRaises(ArtifactError) as caught:
            store_planned_artifact(self.store, plan)
        self.assertIn("no longer stored", str(caught.exception))

    def test_an_identical_document_is_reported_rather_than_stored_twice(self):
        first = store_planned_artifact(self.store, self.plan())
        again = self.plan()
        self.assertEqual(again.duplicate_of, first.artifact_id)
        with self.assertRaises(ArtifactError) as caught:
            store_planned_artifact(self.store, again)
        self.assertIn(first.artifact_id, str(caught.exception))
        self.assertEqual(len(self.store.list_tailored_artifacts()), 1)

    def test_a_new_strategy_version_makes_a_second_document_history_not_a_duplicate(self):
        first = store_planned_artifact(self.store, self.plan())
        self.store.revise_role_strategy(
            self.strategy.strategy_id, name=self.strategy.name,
            role_family=self.strategy.role_family,
            required_skills=frozenset({"Python", "SQL"}))
        second = store_planned_artifact(self.store, self.plan())
        self.assertNotEqual(second.artifact_id, first.artifact_id)
        self.assertEqual(second.strategy_version, 2)
        self.assertEqual(len(self.store.list_tailored_artifacts()), 2)
        self.assertIsNotNone(self.store.get_tailored_artifact(first.artifact_id),
                             "the first document stopped being history")

    def test_the_original_profile_and_resume_facts_are_untouched_by_a_build(self):
        before = capture_basis(self.store)
        store_planned_artifact(self.store, self.plan())
        self.assertEqual(capture_basis(self.store), before)
        self.assertEqual(self.store.get_profile(), PROFILE)


class ExportTests(BuildTestCase):
    def build(self):
        return store_planned_artifact(self.store, self.plan())

    def test_an_exported_document_carries_its_provenance_above_the_text(self):
        artifact = self.build()
        target = self.root / "tailored.txt"
        export = export_artifact(self.store, artifact.artifact_id, target)
        written = target.read_text(encoding="utf-8")
        self.assertEqual(export.path, str(target))
        self.assertEqual(export.characters, len(written))
        self.assertIn(artifact.artifact_id, written)
        self.assertIn(f"version {artifact.strategy_version}", written)
        self.assertIn("nothing was sent anywhere", written)
        self.assertTrue(written.rstrip().endswith(artifact.content.rstrip()))
        for line in export_provenance(artifact):
            self.assertIn(line.splitlines()[0], written)

    def test_an_exported_file_is_owner_only(self):
        artifact = self.build()
        target = self.root / "private.txt"
        export_artifact(self.store, artifact.artifact_id, target)
        if os.name == "nt":  # pragma: no cover - POSIX permission bits only
            self.skipTest("file modes are not POSIX permission bits on this platform")
        mode = stat.S_IMODE(target.stat().st_mode)
        self.assertEqual(mode & 0o077, 0, f"the exported document is readable by others: {mode:o}")

    def test_an_existing_file_is_never_overwritten(self):
        artifact = self.build()
        original = self.root / "my-resume.txt"
        original.write_text("the candidate's own resume", encoding="utf-8")
        with self.assertRaises(ArtifactError) as caught:
            export_artifact(self.store, artifact.artifact_id, original)
        self.assertIn("already exists", str(caught.exception))
        self.assertEqual(original.read_text(encoding="utf-8"), "the candidate's own resume")

    def test_a_folder_that_does_not_exist_is_refused_and_writes_nothing(self):
        artifact = self.build()
        target = self.root / "no-such-folder" / "tailored.txt"
        with self.assertRaises(ArtifactError) as caught:
            export_artifact(self.store, artifact.artifact_id, target)
        self.assertIn("does not exist", str(caught.exception))
        self.assertFalse(target.exists())

    def test_a_stale_document_is_refused_with_the_reason_rather_than_exported(self):
        artifact = self.build()
        self.store.revise_role_strategy(
            self.strategy.strategy_id, name=self.strategy.name,
            role_family=self.strategy.role_family,
            required_skills=frozenset({"Python", "Rust"}))
        target = self.root / "stale.txt"
        with self.assertRaises(StaleArtifactError) as caught:
            export_artifact(self.store, artifact.artifact_id, target)
        self.assertIn("strategy", str(caught.exception).casefold())
        self.assertFalse(target.exists(), "a stale document was written out anyway")

    def test_a_write_that_fails_half_way_leaves_nothing_under_that_name(self):
        artifact = self.build()
        target = self.root / "interrupted.txt"
        with mock.patch("builtins.open", side_effect=OSError("no space left on device")):
            with self.assertRaises(ArtifactError) as caught:
                export_artifact(self.store, artifact.artifact_id, target)
        self.assertIn("no space left on device", str(caught.exception))
        self.assertFalse(target.exists(), "a truncated document was left behind")
        export_artifact(self.store, artifact.artifact_id, target)
        self.assertIn(artifact.artifact_id, target.read_text(encoding="utf-8"))

    def test_a_folder_named_as_the_destination_is_refused_and_survives(self):
        artifact = self.build()
        target = self.root / "documents"
        target.mkdir()
        with self.assertRaises(ArtifactError):
            export_artifact(self.store, artifact.artifact_id, target)
        self.assertTrue(target.is_dir())

    def test_an_unknown_document_is_refused(self):
        with self.assertRaises(ArtifactError):
            export_artifact(self.store, "artifact-nope", self.root / "nothing.txt")

    def test_exporting_twice_needs_two_names_and_leaves_both_files_intact(self):
        artifact = self.build()
        first, second = self.root / "one.txt", self.root / "two.txt"
        export_artifact(self.store, artifact.artifact_id, first)
        export_artifact(self.store, artifact.artifact_id, second)
        self.assertEqual(first.read_text(encoding="utf-8"),
                         second.read_text(encoding="utf-8"))
        with self.assertRaises(ArtifactError):
            export_artifact(self.store, artifact.artifact_id, first)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
