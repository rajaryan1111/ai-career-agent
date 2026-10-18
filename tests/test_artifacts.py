"""Tests for tailored artifacts: builders that only restate facts, and lineage that says what moved.

Every document, profile, history record and strategy in this module is invented. Nothing here opens a
network connection, sends anything anywhere, or touches a real file outside a disposable folder.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from career_agent.artifacts import (
    MAX_CONTENT_CHARS, ArtifactBasis, ArtifactError, ArtifactKind, BuiltArtifact, LineageReport,
    TailoredArtifact, capture_basis, cover_letter_document, lineage_status, new_artifact_id,
    tailored_resume_document,
)
from career_agent.backup import create_backup, restore_backup
from career_agent.core import (
    Availability, CandidateProfile, EducationEntry, EmploymentType, FactSource, JobListing,
    WorkHistoryEntry,
)
from career_agent.store import CareerStore, StoredRecordError
from career_agent.strategies import RoleStrategy, new_strategy_id

PROFILE = CandidateProfile(
    candidate_country="India", degree_discipline="ECE", graduation_year=2027,
    experience_years=1.0, work_authorization="citizen",
    skills=frozenset({"Python", "SQL", "PyTorch"}),
    preferred_locations=frozenset({"Delhi"}),
)

STRATEGY = RoleStrategy(
    strategy_id=new_strategy_id(), version=1, name="Applied AI roles, Delhi NCR",
    role_family="Applied AI engineering", title_synonyms=frozenset({"GenAI Engineer"}),
    seniority="early", locations=frozenset({"Delhi", "Bengaluru"}), work_modes=frozenset({"hybrid"}),
    employment_types=frozenset({"full-time"}), required_skills=frozenset({"Python", "Docker"}),
    excluded_employers=frozenset({"Blocked Employer"}), preferred_skills=frozenset({"PyTorch"}),
)

LISTING = JobListing(
    listing_id="j1", source_id="manual", source_name="Manual entry",
    source_listing_url="https://jobs.example.invalid/role/1", employer_name="Example Employer",
    role_title="GenAI Engineer", availability_status=Availability.OPEN,
    required_skills=frozenset({"Python", "Docker"}), location_text="Delhi, India", work_mode="hybrid",
)

WORK = (WorkHistoryEntry(employer="Example Systems", job_title="Intern",
                         start_date=date(2026, 1, 1), is_current=True,
                         employment_type=EmploymentType.INTERNSHIP, summary="Built data pipelines"),)
EDUCATION = (EducationEntry(institution="Example Institute", qualification="B.Tech",
                            discipline="ECE", start_date=date(2023, 8, 1)),)


def basis(**overrides) -> ArtifactBasis:
    """The basis the tests build from: the profile's rendered facts, nothing confirmed."""
    from career_agent.core import profile_fact_values
    facts = {name: value for name, value in profile_fact_values(PROFILE).items() if value}
    return ArtifactBasis(facts=facts, unconfirmed_facts=frozenset(facts), work=WORK, education=EDUCATION)


class ArtifactBasisTests(unittest.TestCase):
    """What a basis may hold: the profile's own facts, and nothing unanchored."""

    def test_a_basis_holds_only_known_facts_with_non_empty_values(self):
        with self.assertRaises(ArtifactError):
            ArtifactBasis(facts={"not_a_fact": "yes"})
        with self.assertRaises(ArtifactError):
            ArtifactBasis(facts={"skills": "   "})
        with self.assertRaises(ArtifactError):
            ArtifactBasis(facts={"skills": 7})

    def test_an_unconfirmed_fact_must_be_a_stated_fact(self):
        with self.assertRaises(ArtifactError) as caught:
            ArtifactBasis(facts={"skills": "Python"}, unconfirmed_facts=frozenset({"skills", "country"}))
        self.assertIn("country", str(caught.exception))

    def test_a_basis_round_trips_through_its_stored_form(self):
        restored = ArtifactBasis.from_json(basis().to_json())
        self.assertEqual(restored.facts, basis().facts)
        self.assertEqual(restored.unconfirmed_facts, basis().unconfirmed_facts)
        self.assertEqual(restored.work, basis().work)
        self.assertEqual(restored.education, basis().education)

    def test_a_damaged_stored_basis_is_refused_as_itself(self):
        for payload in ([], {"facts": [], "work": [], "education": []},
                        {"facts": {}, "unconfirmed": "skills", "work": [], "education": []},
                        {"facts": {}, "work": [7], "education": []}):
            with self.subTest(payload=payload):
                with self.assertRaises(ArtifactError):
                    ArtifactBasis.from_json(payload)


class BuilderTests(unittest.TestCase):
    """The builders arrange stated facts and never invent a claim."""

    def test_the_resume_states_only_skills_the_profile_states(self):
        built = tailored_resume_document(basis(), STRATEGY)
        self.assertIsInstance(built, BuiltArtifact)
        self.assertIn("PyTorch, Python", built.content,
                      "required first, preferred next, both stated (rendered sorted)")
        self.assertIn("SQL", built.content)
        self.assertIn("Experience", built.content)
        self.assertIn("Example Systems", built.content)
        self.assertNotIn("Docker", built.content, "a required skill the profile does not state is a gap")

    def test_the_resume_reports_gaps_instead_of_hiding_or_inventing(self):
        built = tailored_resume_document(basis(), STRATEGY)
        self.assertEqual(built.gaps, ("Docker",))

    def test_a_strategy_without_required_skills_reports_no_gaps(self):
        bare = RoleStrategy(strategy_id=new_strategy_id(), version=1, name="Any data role",
                            role_family="Data engineering")
        self.assertEqual(tailored_resume_document(basis(), bare).gaps, ())

    def test_the_cover_letter_names_the_listing_and_states_only_stated_facts(self):
        built = cover_letter_document(basis(), STRATEGY, LISTING)
        self.assertIn("Example Employer", built.content)
        self.assertIn("GenAI Engineer", built.content)
        self.assertIn("PyTorch, Python", built.content)
        self.assertIn("1.0 of experience", built.content)
        self.assertIn("Intern at Example Systems", built.content)
        self.assertNotIn("Docker", built.content)

    def test_a_profile_that_states_no_experience_produces_no_experience_sentence(self):
        quiet = ArtifactBasis(facts={"skills": "Python"}, work=(), education=())
        built = cover_letter_document(quiet, STRATEGY, LISTING)
        self.assertNotIn("experience", built.content)
        resume = tailored_resume_document(quiet, STRATEGY)
        self.assertNotIn("Experience", resume.content, "an empty history is silence, not a section")

    def test_skill_comparison_is_case_insensitive_and_keeps_the_profile_spelling(self):
        facts = {"skills": "python"}
        built = tailored_resume_document(ArtifactBasis(facts=facts), STRATEGY)
        self.assertIn("python", built.content)
        self.assertNotIn("Python, ", built.content.replace("python", "PYTHON"), "no invented casing")

    def test_the_content_is_bounded(self):
        """A document over the limit is refused where it is built, not when it is read back."""
        with self.assertRaises(ArtifactError) as caught:
            TailoredArtifact(
                artifact_id=new_artifact_id(), listing_id="j1", strategy_id=new_strategy_id(),
                strategy_version=1, kind=ArtifactKind.TAILORED_RESUME,
                content="x" * (MAX_CONTENT_CHARS + 1))
        self.assertIn("over the", str(caught.exception))
        with self.assertRaises(ArtifactError):
            TailoredArtifact(
                artifact_id=new_artifact_id(), listing_id="j1", strategy_id=new_strategy_id(),
                strategy_version=1, kind=ArtifactKind.TAILORED_RESUME, content="   ")


class CaptureBasisTests(unittest.TestCase):
    """What the store holds right now, as a basis."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.store = CareerStore(str(self.folder / "career_agent.sqlite3"))
        self.addCleanup(self.store.close)

    def test_capture_refuses_to_invent_a_basis_without_a_profile(self):
        with self.assertRaises(ArtifactError) as caught:
            capture_basis(self.store)
        self.assertIn("no profile is saved", str(caught.exception))

    def test_capture_takes_the_stated_facts_and_the_history(self):
        self.store.save_profile(PROFILE)
        self.store.add_work_history("Example Systems", "Intern", date(2026, 1, 1), is_current=True,
                                    employment_type=EmploymentType.INTERNSHIP,
                                    summary="Built data pipelines")
        self.store.add_education("Example Institute", "B.Tech", discipline="ECE",
                                 start_date=date(2023, 8, 1))
        captured = capture_basis(self.store)
        self.assertEqual(captured.facts["skills"], "PyTorch, Python, SQL")
        self.assertEqual(captured.unconfirmed_facts, frozenset(captured.facts),
                         "nothing is confirmed until a person confirms it")
        self.assertEqual(len(captured.work), 1)
        self.assertEqual(len(captured.education), 1)

    def test_a_confirmed_fact_is_not_marked_unconfirmed(self):
        self.store.save_profile(PROFILE)
        self.store.confirm_profile_fact("skills")
        captured = capture_basis(self.store)
        self.assertEqual(captured.unconfirmed_facts, frozenset(captured.facts) - {"skills"})


class ArtifactStoreTests(unittest.TestCase):
    """Append-only artifact rows whose lineage resolves at write time."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)
        self.store.save_job(LISTING)
        self.store.save_profile(PROFILE)
        # History on the record, so a saved artifact's basis round-trips dates and enums through JSON.
        self.store.add_work_history("Example Systems", "Intern", date(2026, 1, 1), is_current=True,
                                    employment_type=EmploymentType.INTERNSHIP,
                                    summary="Built data pipelines")
        self.store.add_education("Example Institute", "B.Tech", discipline="ECE",
                                 start_date=date(2023, 8, 1))
        self.strategy = self.store.create_role_strategy(
            name=STRATEGY.name, role_family=STRATEGY.role_family, seniority=STRATEGY.seniority,
            required_skills=STRATEGY.required_skills, preferred_skills=STRATEGY.preferred_skills)

    def save_one(self, **overrides) -> object:
        return self.store.new_tailored_artifact(
            listing_id=overrides.get("listing_id", LISTING.listing_id),
            strategy=overrides.get("strategy", self.strategy),
            kind=overrides.get("kind", ArtifactKind.TAILORED_RESUME),
            content=overrides.get("content", "A tailored resume built from the stored facts.\n"),
            basis=overrides.get("basis", capture_basis(self.store)))

    def test_a_saved_artifact_reads_back_whole(self):
        saved = self.save_one()
        loaded = self.store.get_tailored_artifact(saved.artifact_id)
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded.basis.facts["skills"], "PyTorch, Python, SQL")
        # The history came back as records, not as the JSON text it travelled as.
        self.assertEqual(loaded.basis.work, saved.basis.work)
        self.assertEqual(loaded.basis.work[0].employer, "Example Systems")
        self.assertEqual(loaded.basis.work[0].start_date, date(2026, 1, 1))
        self.assertEqual(loaded.basis.education, saved.basis.education)

    def test_a_artifact_cannot_be_filed_without_its_listing(self):
        with self.assertRaises(ArtifactError) as caught:
            self.save_one(listing_id="no-such-listing")
        self.assertIn("no listing", str(caught.exception))
        self.assertEqual(self.store.list_tailored_artifacts(), (), "the refusal stored nothing")

    def test_an_artifact_cannot_reference_a_strategy_version_that_is_not_stored(self):
        missing = RoleStrategy(strategy_id=new_strategy_id(), version=1, name="Ghost strategy",
                               role_family="Data engineering")
        with self.assertRaises(ArtifactError) as caught:
            self.save_one(strategy=missing)
        self.assertIn("lineage", str(caught.exception))

    def test_artifacts_are_append_only(self):
        saved = self.save_one()
        with self.assertRaises(ArtifactError) as caught:
            self.store.save_tailored_artifact(saved)
        self.assertIn("append-only", str(caught.exception))
        self.assertEqual(len(self.store.list_tailored_artifacts()), 1)

    def test_listing_filters_and_newest_first_order(self):
        first = self.save_one()
        revised = self.store.revise_role_strategy(self.strategy.strategy_id, name=self.strategy.name,
                                                  role_family=self.strategy.role_family)
        second = self.save_one(strategy=revised, content="Second build.\n")
        other_listing = JobListing(
            listing_id="j2", source_id="manual", source_name="Manual entry",
            source_listing_url="https://jobs.example.invalid/role/2", employer_name="Example Employer",
            role_title="Data Engineer", availability_status=Availability.OPEN)
        self.store.save_job(other_listing)
        self.save_one(listing_id="j2")

        listed = self.store.list_tailored_artifacts()
        self.assertEqual(len(listed), 3)
        self.assertEqual(listed[0].listing_id, "j2",
                         "the newest row first (same-second writes tie-break by insertion order)")
        self.assertEqual([item.artifact_id for item in listed[1:]],
                         [second.artifact_id, first.artifact_id])
        self.assertEqual(len(self.store.list_tailored_artifacts(listing_id="j2")), 1)
        self.assertEqual(len(self.store.list_tailored_artifacts(listing_id="j1")), 2)
        # A revision keeps the strategy's identity: every version's artifacts share the id, so the
        # filter is by strategy, and the version is on the rows for a lineage report to read.
        self.assertEqual(len(self.store.list_tailored_artifacts(strategy_id=revised.strategy_id)), 3)
        self.assertEqual({item.strategy_version for item in
                          self.store.list_tailored_artifacts(strategy_id=revised.strategy_id)}, {1, 2})
        self.assertEqual(self.store.list_tailored_artifacts(strategy_id=new_strategy_id()), ())
        self.assertEqual(len(self.store.list_tailored_artifacts(kind=ArtifactKind.TAILORED_RESUME)), 3)
        self.assertEqual(self.store.list_tailored_artifacts(kind=ArtifactKind.COVER_LETTER), ())

    def test_deleting_an_artifact_removes_one_row(self):
        saved = self.save_one()
        self.assertEqual(self.store.delete_tailored_artifact(saved.artifact_id), 1)
        self.assertIsNone(self.store.get_tailored_artifact(saved.artifact_id))
        self.assertEqual(self.store.delete_tailored_artifact(saved.artifact_id), 0,
                         "deleting nothing removes nothing")

    def test_artifacts_survive_a_restart_and_a_backup_restore(self):
        saved = self.save_one()
        self.store.close()
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)
        self.assertEqual(self.store.get_tailored_artifact(saved.artifact_id), saved)

        backup = self.folder / "backup.sqlite3"
        create_backup(self.database, backup)
        self.store.delete_tailored_artifact(saved.artifact_id)
        restore_backup(backup, self.database)
        self.store.close()
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)
        self.assertIsNotNone(self.store.get_tailored_artifact(saved.artifact_id))

    def test_deleting_a_listing_removes_its_artifacts(self):
        saved = self.save_one()
        self.store.delete_job(LISTING.listing_id)
        self.assertEqual(self.store.list_tailored_artifacts(), (),
                         "the per-listing cascade this schema declares everywhere")

    def test_a_damaged_artifact_row_is_reported_by_the_doctor(self):
        saved = self.save_one()
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE tailored_artifact SET artifact_kind='poetry' WHERE artifact_id=?",
                (saved.artifact_id,))
        with self.assertRaises(StoredRecordError):
            self.store.get_tailored_artifact(saved.artifact_id)
        from career_agent.store import unreadable_stored_records
        self.assertTrue(any("tailored_artifact" in line
                            for line in unreadable_stored_records(self.database)))

    def test_the_log_carries_the_identifier_and_never_the_content(self):
        saved = self.save_one(content="Confidential tailored text about Example Employer.\n")
        from career_agent.event_log import log_path
        written = log_path(self.database).read_text(encoding="utf-8")
        self.assertIn("artifact.saved", written)
        self.assertIn(f"id={saved.artifact_id}", written)
        self.assertNotIn("Confidential tailored text", written)
        self.assertNotIn("Example Employer", written)


class LineageTests(unittest.TestCase):
    """Lineage says what moved, and is current only when nothing did."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.store = CareerStore(str(self.folder / "career_agent.sqlite3"))
        self.addCleanup(self.store.close)
        self.store.save_job(LISTING)
        self.store.save_profile(PROFILE)
        self.strategy = self.store.create_role_strategy(
            name=STRATEGY.name, role_family=STRATEGY.role_family,
            required_skills=STRATEGY.required_skills, preferred_skills=STRATEGY.preferred_skills)
        self.artifact = self.store.new_tailored_artifact(
            listing_id=LISTING.listing_id, strategy=self.strategy,
            kind=ArtifactKind.TAILORED_RESUME,
            content="Built from the facts as they were.\n", basis=capture_basis(self.store))

    def test_an_untouched_world_reads_as_current(self):
        report = lineage_status(self.store, self.artifact)
        self.assertIsInstance(report, LineageReport)
        self.assertTrue(report.is_current)
        self.assertEqual(report.summary(), ("every source fact and the strategy version are unchanged",))

    def test_changing_a_fact_is_reported_by_name(self):
        self.store.save_profile(CandidateProfile(
            candidate_country="India", graduation_year=2027, experience_years=2.0,
            skills=frozenset({"Python", "SQL", "PyTorch"}),
            preferred_locations=frozenset({"Delhi"}),
        ))
        report = lineage_status(self.store, self.artifact)
        self.assertIn("experience", report.facts_changed)
        self.assertIn("work_authorization", report.facts_changed, "a dropped fact is a change")
        self.assertFalse(report.is_current)

    def test_confirming_a_fact_does_not_change_it_but_is_reported(self):
        self.store.confirm_profile_fact("skills")
        report = lineage_status(self.store, self.artifact)
        self.assertEqual(report.facts_changed, (), "a confirmation changes no value")
        self.assertIn("skills", report.facts_confirmed_since)
        self.assertFalse(report.is_current,
                         "the document was built when that fact was unconfirmed; that is worth saying")

    def test_a_changed_work_history_is_reported(self):
        self.store.add_work_history("Another Example", "Engineer", date(2026, 6, 1))
        report = lineage_status(self.store, self.artifact)
        self.assertTrue(report.work_changed)
        self.assertFalse(report.is_current)

    def test_a_newer_strategy_version_is_reported_and_the_old_one_still_resolves(self):
        self.store.revise_role_strategy(self.strategy.strategy_id, name=self.strategy.name,
                                        role_family=self.strategy.role_family, seniority="mid")
        report = lineage_status(self.store, self.artifact)
        self.assertFalse(report.strategy_version_current)
        self.assertIn("newer version", report.summary()[0])
        # Append-only strategies mean the old version is still exactly what it said it was.
        self.assertEqual(
            self.store.get_role_strategy(self.strategy.strategy_id,
                                         version=self.artifact.strategy_version).version, 1)

    def test_resaving_unchanged_values_changes_nothing(self):
        self.store.save_profile(PROFILE)
        self.store.save_profile(PROFILE, source=FactSource.USER_ENTERED)
        report = lineage_status(self.store, self.artifact)
        self.assertTrue(report.is_current, "re-saving the same facts is not a change")


if __name__ == "__main__":
    unittest.main()
