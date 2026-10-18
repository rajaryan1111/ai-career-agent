"""Tests for tailored artifacts: builders that only restate facts, and lineage that says what moved.

Every document, profile, history record and strategy in this module is invented. Nothing here opens a
network connection, sends anything anywhere, or touches a real file outside a disposable folder.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from career_agent.artifacts import (
    MAX_CONTENT_CHARS, ArtifactBasis, ArtifactError, ArtifactKind, BuiltArtifact, LineageReport,
    ListingFingerprint, StaleArtifactError, TailoredArtifact, capture_basis, cover_letter_document,
    export_artifact, lineage_status, new_artifact_id, plan_artifact, rebuild_artifact,
    require_current_artifact, store_planned_artifact, tailored_resume_document,
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
        self.assertIn("1.0 years of experience", built.content)
        self.assertIn("Intern at Example Systems", built.content)
        self.assertNotIn("Docker", built.content)

    def test_the_experience_sentence_says_what_the_number_counts(self):
        """It read "My profile states 1.0 of experience." until a screen could build one."""
        one = cover_letter_document(ArtifactBasis(facts={"experience": "1"}), STRATEGY, LISTING)
        self.assertIn("My profile states 1 year of experience.", one.content)
        several = cover_letter_document(ArtifactBasis(facts={"experience": "2.5"}), STRATEGY, LISTING)
        self.assertIn("My profile states 2.5 years of experience.", several.content)
        for built in (one, several):
            self.assertNotIn("states 1 of experience", built.content)
            self.assertNotIn("states 2.5 of experience", built.content)

    def test_the_cover_letter_reports_the_requirements_it_leaves_out(self):
        """A letter reported no gaps at all, so a screen could claim nothing was missing."""
        built = cover_letter_document(basis(), STRATEGY, LISTING)
        self.assertEqual(built.gaps, ("Docker",))
        self.assertNotIn("Docker", built.content)
        bare = RoleStrategy(strategy_id=new_strategy_id(), version=1, name="Any data role",
                            role_family="Data engineering")
        self.assertEqual(cover_letter_document(basis(), bare, LISTING).gaps, ())

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
        # A real change, so a second version is really written: a revision that repeats the stored
        # content writes nothing, which is what the strategy store promises.
        revised = self.store.revise_role_strategy(self.strategy.strategy_id, seniority="senior")
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


class RequireCurrentArtifactTests(unittest.TestCase):
    """The one gate any future caller must pass before an artifact is used, not just read.

    Reading an artifact back is history; *using* one - attaching it, sending it, building on it - is
    a claim that its sources still say what the document says. This gate is where that claim is
    checked, and a stale artifact is refused with the reason, never silently reused.
    """

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

    def test_a_current_artifact_is_returned_as_itself(self):
        from career_agent.artifacts import require_current_artifact
        self.assertEqual(require_current_artifact(self.store, self.artifact.artifact_id),
                         self.artifact)

    def test_an_artifact_whose_fact_changed_is_refused_with_the_fact_named(self):
        from career_agent.artifacts import StaleArtifactError, require_current_artifact
        self.store.save_profile(CandidateProfile(
            candidate_country="India", graduation_year=2027, experience_years=3.0,
            skills=frozenset({"Python", "SQL", "PyTorch"})))
        with self.assertRaises(StaleArtifactError) as caught:
            require_current_artifact(self.store, self.artifact.artifact_id)
        self.assertIn("experience", str(caught.exception))
        self.assertIn("experience", caught.exception.report.facts_changed)

    def test_an_artifact_under_a_superseded_strategy_version_is_refused(self):
        from career_agent.artifacts import StaleArtifactError, require_current_artifact
        self.store.revise_role_strategy(self.strategy.strategy_id, name=self.strategy.name,
                                        role_family=self.strategy.role_family, seniority="mid")
        with self.assertRaises(StaleArtifactError) as caught:
            require_current_artifact(self.store, self.artifact.artifact_id)
        self.assertIn("newer version", str(caught.exception))

    def test_an_artifact_missing_from_the_store_is_refused_as_missing(self):
        from career_agent.artifacts import ArtifactError, require_current_artifact
        with self.assertRaises(ArtifactError) as caught:
            require_current_artifact(self.store, "no-such-artifact")
        self.assertIn("no artifact", str(caught.exception))

    def test_a_stale_artifact_still_reads_back_after_the_refusal(self):
        """The gate refuses use, not history: the row is untouched by the check."""
        from career_agent.artifacts import require_current_artifact
        self.store.add_work_history("Another Example", "Engineer", date(2026, 6, 1))
        with self.assertRaises(ArtifactError):
            require_current_artifact(self.store, self.artifact.artifact_id)
        self.assertEqual(self.store.get_tailored_artifact(self.artifact.artifact_id), self.artifact)


class ArtifactCitationTests(unittest.TestCase):
    """An artifact names the document its facts were read from, and says so when that stops being true.

    The roadmap's rule is that a tailored document is traceable to the resume it came out of. The
    document name already lives beside each fact as provenance (schema 8); what makes it a *citation*
    is that the artifact's own basis keeps the name it was built under, so the claim can be checked
    later against what the store says now.
    """

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)
        self.store.save_job(LISTING)
        self.strategy = self.store.create_role_strategy(
            name=STRATEGY.name, role_family=STRATEGY.role_family, seniority=STRATEGY.seniority,
            required_skills=STRATEGY.required_skills, preferred_skills=STRATEGY.preferred_skills)

    def read_from_document(self, profile=PROFILE, document="resume-v1.docx"):
        """Save the profile the way the résumé reader does: values out of a named file."""
        return self.store.save_profile(profile, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                                       document_name=document)

    def save_one(self, captured):
        return self.store.new_tailored_artifact(
            listing_id=LISTING.listing_id, strategy=self.strategy,
            kind=ArtifactKind.TAILORED_RESUME,
            content="A tailored resume built from the stored facts.\n", basis=captured)

    def test_the_basis_cites_the_document_each_fact_was_read_from(self):
        self.read_from_document()
        captured = capture_basis(self.store)
        self.assertEqual(captured.fact_documents["skills"], "resume-v1.docx")
        self.assertEqual(captured.source_documents, ("resume-v1.docx",))

    def test_a_fact_the_person_typed_cites_no_document(self):
        self.store.save_profile(PROFILE)
        captured = capture_basis(self.store)
        self.assertEqual(captured.fact_documents, {},
                         "a typed value came out of no file, so naming one would be a fiction")
        self.assertEqual(captured.source_documents, ())

    def test_a_citation_names_a_fact_the_basis_states(self):
        with self.assertRaises(ArtifactError) as caught:
            ArtifactBasis(facts={"skills": "Python"}, fact_documents={"email": "resume.docx"})
        self.assertIn("email", str(caught.exception))

    def test_a_citation_is_a_file_name_and_never_a_folder(self):
        for name in ("/home/person/resume.docx", "C:\\Users\\person\\resume.docx", "  "):
            with self.subTest(name=name), self.assertRaises(ArtifactError):
                ArtifactBasis(facts={"skills": "Python"}, fact_documents={"skills": name})

    def test_the_citation_round_trips_through_the_stored_row(self):
        self.read_from_document()
        saved = self.save_one(capture_basis(self.store))
        loaded = self.store.get_tailored_artifact(saved.artifact_id)
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded.basis.fact_documents["skills"], "resume-v1.docx")
        self.assertEqual(loaded.source_documents, ("resume-v1.docx",))
        self.assertIn("resume-v1.docx", loaded.describe())

    def test_an_artifact_stored_before_citations_reads_back_and_stays_current(self):
        self.read_from_document()
        saved = self.save_one(capture_basis(self.store))
        legacy = {name: value for name, value in saved.basis.to_json().items()
                  if name != "documents"}
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE tailored_artifact SET fact_basis=? WHERE artifact_id=?",
                (json.dumps(legacy, sort_keys=True), saved.artifact_id))
        loaded = self.store.get_tailored_artifact(saved.artifact_id)
        self.assertEqual(loaded.basis.fact_documents, {})
        self.assertEqual(loaded.source_documents, ())
        self.assertTrue(lineage_status(self.store, loaded).is_current,
                        "a row that cites no document claims nothing about one, so nothing about it "
                        "can have become untrue")

    def test_a_fact_no_longer_read_from_the_cited_document_is_reported(self):
        self.read_from_document()
        saved = self.save_one(capture_basis(self.store))
        # The person clears the skills fact and types the same value straight back into the form: the
        # value the artifact states is what it was, but it no longer comes out of the cited résumé.
        self.store.save_profile(replace(PROFILE, skills=frozenset()))
        self.store.save_profile(PROFILE)
        report = lineage_status(self.store, saved)
        self.assertEqual(report.facts_changed, (), "the value is still what the artifact states")
        self.assertEqual(report.documents_changed, ("skills",))
        self.assertFalse(report.is_current)
        self.assertIn("resume-v1.docx", "; ".join(report.summary()))
        with self.assertRaises(StaleArtifactError) as caught:
            require_current_artifact(self.store, saved.artifact_id)
        self.assertIn("skills", str(caught.exception))

    def test_a_changed_value_is_reported_once_as_a_changed_fact(self):
        self.read_from_document()
        saved = self.save_one(capture_basis(self.store))
        self.read_from_document(replace(PROFILE, skills=frozenset({"Python"})), "resume-v2.docx")
        report = lineage_status(self.store, saved)
        self.assertEqual(report.facts_changed, ("skills",))
        self.assertEqual(report.documents_changed, (),
                         "the changed value is the headline; the citation is not a second complaint")

    def test_a_rebuilt_artifact_cites_the_document_it_was_rebuilt_from(self):
        self.read_from_document()
        stale = self.save_one(capture_basis(self.store))
        self.read_from_document(replace(PROFILE, skills=frozenset({"Python", "SQL"})),
                                "resume-v2.docx")
        rebuilt = self.save_one(capture_basis(self.store))
        # Origins are per fact, and a save only re-attributes the facts it changes, so the rebuilt
        # basis cites *both* résumés: the skills came out of the second one, everything else is
        # still what the first one said. Claiming a single source here would be the fiction.
        self.assertEqual(rebuilt.basis.fact_documents["skills"], "resume-v2.docx")
        self.assertEqual(rebuilt.source_documents, ("resume-v1.docx", "resume-v2.docx"))
        self.assertTrue(lineage_status(self.store, rebuilt).is_current)
        self.assertFalse(lineage_status(self.store, stale).is_current,
                         "the first artifact is still history, and still stale")
        self.assertEqual(self.store.get_tailored_artifact(stale.artifact_id).source_documents,
                         ("resume-v1.docx",), "an append-only row keeps the citation it was written with")

    def test_the_log_never_carries_the_cited_document_name(self):
        self.read_from_document(document="personal-cv-2026.docx")
        saved = self.save_one(capture_basis(self.store))
        from career_agent.event_log import log_path
        written = log_path(self.database).read_text(encoding="utf-8")
        self.assertIn(f"id={saved.artifact_id}", written)
        self.assertNotIn("personal-cv-2026.docx", written,
                         "the file somebody's résumé is called is their data, not an event detail")


class RebuildArtifactTests(unittest.TestCase):
    """Rebuilding a stale document: a new row from current facts, never an edit of the old one."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.store = CareerStore(str(self.database))
        self.addCleanup(self.store.close)
        self.store.save_job(LISTING)
        self.store.save_profile(PROFILE, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                                document_name="resume-v1.docx")
        self.strategy = self.store.create_role_strategy(
            name=STRATEGY.name, role_family=STRATEGY.role_family, seniority=STRATEGY.seniority,
            required_skills=STRATEGY.required_skills, preferred_skills=STRATEGY.preferred_skills)

    def save_one(self, kind=ArtifactKind.TAILORED_RESUME, content="A tailored resume.\n"):
        return self.store.new_tailored_artifact(
            listing_id=LISTING.listing_id, strategy=self.strategy, kind=kind, content=content,
            basis=capture_basis(self.store))

    def go_stale(self):
        """Change a stored fact, the way a person updating their profile would."""
        self.store.save_profile(replace(PROFILE, experience_years=2.0))

    def test_a_rebuild_appends_a_current_document_and_keeps_the_stale_one(self):
        stale = self.save_one()
        self.go_stale()
        self.assertFalse(lineage_status(self.store, stale).is_current)
        rebuilt = rebuild_artifact(self.store, stale.artifact_id)
        self.assertNotEqual(rebuilt.artifact.artifact_id, stale.artifact_id)
        self.assertEqual(rebuilt.replaced_artifact_id, stale.artifact_id)
        self.assertTrue(lineage_status(self.store, rebuilt.artifact).is_current)
        self.assertEqual(require_current_artifact(self.store, rebuilt.artifact.artifact_id),
                         rebuilt.artifact)
        stored = self.store.list_tailored_artifacts(listing_id=LISTING.listing_id)
        self.assertEqual(len(stored), 2, "the stale document is history, not something to overwrite")
        self.assertIsNotNone(self.store.get_tailored_artifact(stale.artifact_id))

    def test_a_rebuild_is_built_under_the_newest_strategy_version(self):
        stale = self.save_one()
        newer = self.store.revise_role_strategy(self.strategy.strategy_id,
                                                preferred_skills=frozenset({"PyTorch", "SQL"}))
        self.assertGreater(newer.version, stale.strategy_version)
        rebuilt = rebuild_artifact(self.store, stale.artifact_id)
        self.assertEqual(rebuilt.artifact.strategy_version, newer.version)
        self.assertTrue(lineage_status(self.store, rebuilt.artifact).is_current)

    def test_a_rebuild_reports_gaps_rather_than_inventing_the_missing_skill(self):
        stale = self.save_one()
        self.go_stale()
        rebuilt = rebuild_artifact(self.store, stale.artifact_id)
        self.assertIn("Docker", rebuilt.gaps,
                      "the strategy requires Docker and the profile does not state it")
        self.assertNotIn("Docker", rebuilt.artifact.content,
                         "a gap is reported to the person, never written into the document")

    def test_a_rebuilt_cover_letter_is_rebuilt_as_a_cover_letter(self):
        stale = self.save_one(kind=ArtifactKind.COVER_LETTER, content="Dear hiring team,\n")
        self.go_stale()
        rebuilt = rebuild_artifact(self.store, stale.artifact_id)
        self.assertEqual(rebuilt.artifact.kind, ArtifactKind.COVER_LETTER)
        self.assertIn(LISTING.employer_name, rebuilt.artifact.content)
        self.assertIn(LISTING.role_title, rebuilt.artifact.content)

    def test_screening_answers_are_not_rebuilt_by_a_machine(self):
        stale = self.save_one(kind=ArtifactKind.SCREENING_ANSWERS,
                              content="Q: Are you eligible? A: Yes, I am a citizen.\n")
        self.go_stale()
        with self.assertRaises(ArtifactError) as caught:
            rebuild_artifact(self.store, stale.artifact_id)
        self.assertIn("screening answers", str(caught.exception).lower())
        self.assertEqual(len(self.store.list_tailored_artifacts()), 1, "nothing was written")

    def test_rebuilding_something_that_is_not_stored_is_refused(self):
        with self.assertRaises(ArtifactError) as caught:
            rebuild_artifact(self.store, "0" * 32)
        self.assertIn("no artifact", str(caught.exception))

    def test_a_rebuild_cites_the_documents_the_facts_now_come_from(self):
        stale = self.save_one()
        self.store.save_profile(replace(PROFILE, experience_years=2.0),
                                source=FactSource.EXTRACTED_FROM_DOCUMENT,
                                document_name="resume-v2.docx")
        rebuilt = rebuild_artifact(self.store, stale.artifact_id)
        self.assertEqual(rebuilt.artifact.basis.fact_documents["experience"], "resume-v2.docx")
        self.assertEqual(self.store.get_tailored_artifact(stale.artifact_id)
                         .basis.fact_documents["experience"], "resume-v1.docx")

    def test_a_current_document_can_still_be_rebuilt_without_pretending_it_was_stale(self):
        current = self.save_one()
        rebuilt = rebuild_artifact(self.store, current.artifact_id)
        self.assertTrue(lineage_status(self.store, rebuilt.artifact).is_current)
        self.assertEqual(len(self.store.list_tailored_artifacts()), 2)


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


class ListingLineageTests(unittest.TestCase):
    """A document is written *for a job*, so the job it was written for is part of its lineage.

    The hole this closes: before schema 16 an artifact row named its listing but kept nothing about
    what that listing said, so a cover letter addressed to one employer still read as "Current"
    after the employer was renamed, and could be exported. Every test here is one sentence of the
    rule - what makes a document stale, what deliberately does not, and what happens to a document
    stored before any of this was recorded.
    """

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.store = CareerStore(str(self.folder / "career_agent.sqlite3"))
        self.addCleanup(self.store.close)
        self.store.save_job(LISTING)
        self.store.save_profile(PROFILE, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                                document_name="resume.docx")
        self.strategy = self.store.create_role_strategy(
            name=STRATEGY.name, role_family=STRATEGY.role_family,
            required_skills=STRATEGY.required_skills, preferred_skills=STRATEGY.preferred_skills)

    def build(self, kind=ArtifactKind.COVER_LETTER):
        """The whole public path: look at what would be used, then store exactly that."""
        plan = plan_artifact(self.store, listing_id=LISTING.listing_id,
                             strategy_id=self.strategy.strategy_id, kind=kind)
        return store_planned_artifact(self.store, plan)

    def edit_listing(self, **changes):
        self.store.save_job(replace(LISTING, **changes))

    # ---------------------------------------------------------------- what is recorded, and when

    def test_a_stored_document_records_the_listing_it_was_written_for(self):
        stored = self.build()

        fingerprint = stored.listing_fingerprint
        self.assertIsNotNone(fingerprint, "the document kept no record of the job it was written for")
        self.assertEqual(fingerprint.employer, "Example Employer")
        self.assertEqual(fingerprint.role_title, "GenAI Engineer")
        self.assertEqual(fingerprint.required_skills, ("Docker", "Python"))
        self.assertEqual(self.store.get_tailored_artifact(stored.artifact_id).listing_fingerprint,
                         fingerprint, "what was returned is not what was stored")
        report = lineage_status(self.store, stored)
        self.assertTrue(report.is_current)
        self.assertTrue(report.listing_recorded)
        self.assertTrue(report.listing_verifiable)

    def test_the_record_holds_nothing_but_the_three_fields_a_document_uses(self):
        """No résumé text, no candidate facts, no listing fields the document never reads."""
        stored = self.build()
        row = self.store._connection.execute(
            "SELECT listing_fingerprint FROM tailored_artifact WHERE artifact_id=?",
            (stored.artifact_id,)).fetchone()[0]
        payload = json.loads(row)

        self.assertEqual(set(payload), {"employer", "role_title", "required_skills", "digest"})
        self.assertNotIn("India", row, "a candidate fact reached the listing record")
        self.assertNotIn("resume.docx", row, "the source document reached the listing record")
        self.assertNotIn(LISTING.source_listing_url, row, "a field no document reads was recorded")

    # ---------------------------------------------------------------- what makes a document stale

    def test_renaming_the_employer_makes_the_document_stale_and_names_both_names(self):
        stored = self.build()
        self.edit_listing(employer_name="Renamed Corp")

        report = lineage_status(self.store, stored)

        self.assertFalse(report.is_current, "a letter addressed to another employer read as current")
        self.assertTrue(report.listing_verifiable, "this one can be checked; it is simply out of date")
        self.assertEqual(report.listing_changes,
                         ("the employer is now 'Renamed Corp', not 'Example Employer'",))
        self.assertIn("the listing this was written for changed", "; ".join(report.summary()))

    def test_changing_the_role_title_makes_the_document_stale(self):
        stored = self.build()
        self.edit_listing(role_title="Machine Learning Engineer")

        report = lineage_status(self.store, stored)

        self.assertFalse(report.is_current)
        self.assertEqual(report.listing_changes,
                         ("the role is now 'Machine Learning Engineer', not 'GenAI Engineer'",))

    def test_changing_the_required_skills_makes_the_document_stale(self):
        stored = self.build()
        self.edit_listing(required_skills=frozenset({"Python", "Kubernetes"}))

        report = lineage_status(self.store, stored)

        self.assertFalse(report.is_current)
        self.assertEqual(report.listing_changes, ("the skills the listing asks for changed",))

    def test_fields_no_document_reads_are_not_drift(self):
        """A source URL, an availability flag and a provenance note move nothing a document says."""
        stored = self.build()
        self.edit_listing(source_listing_url="https://jobs.example.invalid/role/1?utm=newsletter",
                          availability_status=Availability.UNKNOWN,
                          provenance_note="re-read from the careers page on 18 October")

        report = lineage_status(self.store, stored)

        self.assertEqual(report.listing_changes, ())
        self.assertTrue(report.is_current,
                        "touching a field no document reads made a good document unusable")

    def test_resaving_the_same_listing_is_not_a_change(self):
        stored = self.build()
        self.store.save_job(LISTING)

        self.assertTrue(lineage_status(self.store, stored).is_current)

    def test_the_skill_order_a_listing_is_saved_with_does_not_matter(self):
        """Required skills are a set; two readings of the same set are the same fingerprint."""
        first = ListingFingerprint.from_listing(replace(LISTING, required_skills=frozenset({"Python", "Docker"})))
        second = ListingFingerprint.from_listing(replace(LISTING, required_skills=frozenset({"Docker", "Python"})))

        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.changes_against(second), ())

    # ------------------------------------------------------------ a stale document cannot be used

    def test_a_document_whose_listing_moved_is_refused_and_not_written_out(self):
        stored = self.build()
        self.edit_listing(employer_name="Renamed Corp")
        target = self.folder / "cover-letter.txt"

        with self.assertRaises(StaleArtifactError) as caught:
            export_artifact(self.store, stored.artifact_id, target)

        self.assertIn("the employer is now 'Renamed Corp'", str(caught.exception))
        self.assertFalse(target.exists(), "a document written for another employer was written out")
        with self.assertRaises(StaleArtifactError):
            require_current_artifact(self.store, stored.artifact_id)

    def test_rebuilding_writes_the_current_listing_and_keeps_the_old_record_intact(self):
        stored = self.build()
        self.edit_listing(employer_name="Renamed Corp")

        rebuilt = rebuild_artifact(self.store, stored.artifact_id)

        self.assertTrue(lineage_status(self.store, rebuilt.artifact).is_current)
        self.assertEqual(rebuilt.artifact.listing_fingerprint.employer, "Renamed Corp")
        self.assertIn("Renamed Corp", rebuilt.artifact.content,
                      "the rebuilt letter is addressed to the employer as it stands now")
        kept = self.store.get_tailored_artifact(stored.artifact_id)
        self.assertEqual(kept.content, stored.content, "the old document was changed by a rebuild")
        self.assertEqual(kept.listing_fingerprint.employer, "Example Employer",
                         "history was rewritten: the old record no longer says what it was built for")
        self.assertFalse(lineage_status(self.store, kept).is_current,
                         "the old document stopped being stale when a new one was built")

    # ------------------------------------------------------- a document nobody can check any more

    def legacy_row(self) -> TailoredArtifact:
        """A row as schema 15 left it: everything recorded except the listing it was written for."""
        stored = self.build()
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE tailored_artifact SET listing_fingerprint=NULL WHERE artifact_id=?",
                (stored.artifact_id,))
        return self.store.get_tailored_artifact(stored.artifact_id)

    def test_a_document_stored_before_schema_16_is_never_reported_as_current(self):
        legacy = self.legacy_row()

        self.assertIsNone(legacy.listing_fingerprint)
        report = lineage_status(self.store, legacy)

        self.assertFalse(report.is_current, "a document nobody can check was reported as current")
        self.assertFalse(report.listing_recorded)
        self.assertFalse(report.listing_verifiable)
        self.assertEqual(report.listing_changes, (), "nothing was invented about what it was built for")
        self.assertIn("cannot be checked", "; ".join(report.summary()))

    def test_a_document_that_cannot_be_checked_is_not_written_out(self):
        legacy = self.legacy_row()
        target = self.folder / "legacy.txt"

        with self.assertRaises(StaleArtifactError) as caught:
            export_artifact(self.store, legacy.artifact_id, target)

        self.assertIn("cannot be checked", str(caught.exception))
        self.assertIn("the new document will record what it was written for", str(caught.exception))
        self.assertFalse(target.exists())

    def test_rebuilding_a_legacy_document_produces_one_that_can_be_checked(self):
        legacy = self.legacy_row()

        rebuilt = rebuild_artifact(self.store, legacy.artifact_id)

        self.assertIsNotNone(rebuilt.artifact.listing_fingerprint)
        self.assertTrue(lineage_status(self.store, rebuilt.artifact).is_current)
        self.assertIsNone(self.store.get_tailored_artifact(legacy.artifact_id).listing_fingerprint,
                          "the old row was back-filled with a listing nobody recorded for it")

    def test_a_listing_that_is_gone_is_reported_as_gone_rather_than_as_current(self):
        """Deleting a listing cascades to its documents, so this is the state a damaged file reaches."""
        stored = self.build()
        orphan = replace(stored, listing_id="no-such-listing")

        report = lineage_status(self.store, orphan)

        self.assertTrue(report.listing_missing)
        self.assertFalse(report.listing_verifiable)
        self.assertFalse(report.is_current)
        self.assertIn("no longer stored", "; ".join(report.summary()))

    # ------------------------------------------------------------------ the record is checkable

    def test_a_fingerprint_edited_in_the_database_is_reported_as_damage(self):
        """The digest is what makes the record evidence; a row that fails it is never believed."""
        stored = self.build()
        tampered = dict(json.loads(self.store._connection.execute(
            "SELECT listing_fingerprint FROM tailored_artifact WHERE artifact_id=?",
            (stored.artifact_id,)).fetchone()[0]))
        tampered["employer"] = "Somebody Else Ltd"
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE tailored_artifact SET listing_fingerprint=? WHERE artifact_id=?",
                (json.dumps(tampered), stored.artifact_id))

        with self.assertRaises(StoredRecordError) as caught:
            self.store.get_tailored_artifact(stored.artifact_id)

        self.assertIn("does not match its own digest", str(caught.exception))

    def test_a_document_cannot_be_filed_under_a_listing_it_was_not_written_for(self):
        """The store is the last gate: a row is only written where the listing still agrees."""
        written_for = ListingFingerprint(employer="Another Employer", role_title="GenAI Engineer",
                                         required_skills=("Docker", "Python"))
        artifact = TailoredArtifact(
            artifact_id=new_artifact_id(), listing_id=LISTING.listing_id,
            strategy_id=self.strategy.strategy_id, strategy_version=self.strategy.version,
            kind=ArtifactKind.COVER_LETTER, content="Dear Another Employer,\n",
            basis=capture_basis(self.store), listing_fingerprint=written_for)

        with self.assertRaises(ArtifactError) as caught:
            self.store.save_tailored_artifact(artifact)

        self.assertIn("is not what this document was written for", str(caught.exception))
        self.assertEqual(self.store.list_tailored_artifacts(), (), "the refused row was stored anyway")



if __name__ == "__main__":
    unittest.main()
