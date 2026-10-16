"""Where a stored profile fact came from, and whether a person has said it is right.

The rule this module exists to hold is one sentence long: **a value a machine produced is never verified
because it was written**. A résumé read on this device, a JSON file imported from another machine and a
person typing in the form all end up in the same ten profile fields, and after they do, nothing in the
stored record used to say which was which. These tests pin the answers:

* a fact read out of a document or imported from a file is recorded as exactly that, and is **unverified**
  until a person confirms it;
* a save only re-attributes the facts it actually changed, so merging reviewed résumé values into a form
  cannot silently turn every other fact into "the person typed this";
* a profile stored before this build recorded origins reads as *unknown*, which is the truthful answer,
  and never as the person's own words;
* the document a value was read from is kept by **name**, never by path.

The fixtures are synthetic and contain no real contact or candidate data, like every other fixture in this
suite.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_agent import store as store_module
from career_agent.core import (
    PROFILE_FACTS, REQUIRED_PROFILE_FACTS, CandidateProfile, FactSource, FactVerification,
    changed_profile_facts, document_name_only, missing_profile_facts,
    missing_required_profile_facts, profile_fact_values,
)
from career_agent.store import CareerStore, StoredRecordError

SYNTHETIC = CandidateProfile(
    candidate_country="India",
    degree_discipline="Electronics and Communication",
    study_status="graduate",
    graduation_year=2027,
    experience_years=1.5,
    work_authorization="citizen",
    skills=frozenset({"Python", "SQL"}),
)


class ProvenanceTestCase(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.database = Path(self._directory.name) / "career_agent.sqlite3"

    def open_store(self) -> CareerStore:
        store = CareerStore(self.database)
        self.addCleanup(store.close)
        return store


class TheFactVocabularyTests(unittest.TestCase):
    """One vocabulary for the ten facts, bound to the two places that already use it."""

    def test_the_fact_list_is_the_form_s_and_the_reviewer_s_own_keys(self):
        """A second spelling of the same facts is a second place for them to drift apart."""
        from career_agent import resume
        from career_agent.desktop_logic import profile_form_values

        self.assertEqual(tuple(key for key, _ in resume.PROFILE_FIELD_LABELS), PROFILE_FACTS)
        self.assertEqual(tuple(profile_form_values(SYNTHETIC)), PROFILE_FACTS)
        self.assertEqual(len(set(PROFILE_FACTS)), len(PROFILE_FACTS))

    def test_the_reviewer_s_resumable_fields_are_all_facts(self):
        from career_agent import resume

        self.assertEqual(sorted(set(resume.RESUMABLE_FIELD_KEYS) - set(PROFILE_FACTS)), [],
                         "a résumé can only propose values for facts this model knows")

    def test_the_required_facts_are_the_ones_eligibility_reads(self):
        """A setup flow asks for these first; the preference facts are choices, not requirements."""
        self.assertEqual(REQUIRED_PROFILE_FACTS,
                         ("country", "degree", "study_status", "graduation_year", "experience",
                          "work_authorization"))
        self.assertEqual(sorted(set(REQUIRED_PROFILE_FACTS) - set(PROFILE_FACTS)), [])

    def test_every_fact_a_listing_can_require_is_in_the_required_list(self):
        """The list is derived from the code that judges eligibility, so it is checked against it.

        ``evaluate_eligibility`` reads exactly these six profile fields. If a seventh check is added
        there without being added here, a setup flow would not know to ask for it.
        """
        import re

        source = (Path(__file__).resolve().parents[1] / "career_agent" / "core.py").read_text(
            encoding="utf-8")
        body = source[source.index("def evaluate_eligibility"):source.index("def score_relevance")]
        read = {
            name for name in re.findall(r"profile\.([a-z_]+)", body)
            if name not in {"skills", "preferred_locations", "preferred_work_modes", "preferred_role_types"}
        }
        fields = {
            "candidate_country": "country", "degree_discipline": "degree", "study_status": "study_status",
            "graduation_year": "graduation_year", "experience_years": "experience",
            "work_authorization": "work_authorization",
        }
        self.assertEqual({fields[name] for name in read}, set(REQUIRED_PROFILE_FACTS))


class MissingFactTests(unittest.TestCase):
    """What a future setup flow can ask for, and what it can ask *about*."""

    def test_a_profile_states_only_the_facts_it_actually_has(self):
        partial = CandidateProfile(candidate_country="India", skills=frozenset({"Python"}))

        self.assertEqual(missing_profile_facts(partial),
                         ("degree", "study_status", "graduation_year", "experience", "work_authorization",
                          "locations", "work_modes", "role_types"))
        self.assertEqual(missing_required_profile_facts(partial),
                         ("degree", "study_status", "graduation_year", "experience", "work_authorization"))

    def test_no_stored_profile_is_missing_every_required_fact(self):
        """The truthful answer, rather than an empty list a setup flow would read as "nothing to ask"."""
        self.assertEqual(missing_required_profile_facts(None), REQUIRED_PROFILE_FACTS)

    def test_an_empty_profile_states_nothing(self):
        self.assertEqual(missing_profile_facts(CandidateProfile()), PROFILE_FACTS)
        self.assertEqual(missing_required_profile_facts(CandidateProfile()), REQUIRED_PROFILE_FACTS)

    def test_a_values_spelling_is_not_a_different_fact(self):
        """Two orderings of the same skills are the same fact: comparison is on the value, not the text."""
        one = CandidateProfile(skills=frozenset({"SQL", "Python"}))
        other = CandidateProfile(skills=frozenset({"Python", "SQL"}))

        self.assertEqual(profile_fact_values(one), profile_fact_values(other))
        self.assertEqual(changed_profile_facts(one, other), ())
        self.assertEqual(missing_profile_facts(one)[0], "country")

    def test_a_zero_value_is_a_stated_fact(self):
        """``0`` experience and year ``0`` are values; only empty and absent mean unknown."""
        zero = CandidateProfile(experience_years=0, graduation_year=0)

        self.assertNotIn("experience", missing_profile_facts(zero))
        self.assertNotIn("graduation_year", missing_profile_facts(zero))


class DocumentNameTests(unittest.TestCase):
    """Provenance is a file's name. A folder in it is somebody's home directory."""

    def test_a_path_is_reduced_to_its_name_on_this_platform(self):
        self.assertEqual(document_name_only("/home/somebody/private/CV final.docx"), "CV final.docx")

    def test_a_windows_path_is_reduced_to_its_name_here_too(self):
        """The value must not depend on which platform recorded it."""
        self.assertEqual(document_name_only(r"C:\Users\somebody\Desktop\CV final.docx"), "CV final.docx")

    def test_a_path_that_names_a_folder_is_not_a_document_name(self):
        """The folder's last segment is not a document, so there is no name to record."""
        self.assertIsNone(document_name_only("/tmp/private/"))
        self.assertIsNone(document_name_only("C:\\Users\\somebody\\"))

    def test_nothing_is_not_a_name(self):
        for empty in (None, "", "   ", "/", "\\"):
            with self.subTest(value=empty):
                self.assertIsNone(document_name_only(empty))

    def test_an_unreasonably_long_name_is_refused_rather_than_cut(self):
        with self.assertRaises(ValueError):
            document_name_only("x" * 201 + ".docx")
        self.assertEqual(document_name_only("y" * 200), "y" * 200)


class SavingRecordsWhereFactsCameFromTests(ProvenanceTestCase):
    """What a write records, and - just as important - what it refuses to claim."""

    def test_typing_a_profile_records_the_facts_as_the_person_s_and_unverified(self):
        """The person supplied the value; whether it is *right* is a claim they have not made yet."""
        store = self.open_store()

        recorded = store.save_profile(SYNTHETIC)

        self.assertEqual(recorded, tuple(fact for fact in PROFILE_FACTS
                                         if profile_fact_values(SYNTHETIC)[fact]))
        origins = {entry.fact: entry for entry in store.get_profile_fact_provenance()}
        self.assertEqual(set(origins), set(recorded))
        self.assertTrue(all(entry.source is FactSource.USER_ENTERED for entry in origins.values()))
        self.assertTrue(all(entry.verification is FactVerification.UNVERIFIED
                            for entry in origins.values()))
        self.assertTrue(all(not entry.is_confirmed for entry in origins.values()))
        self.assertTrue(all(entry.document_name is None for entry in origins.values()),
                        "a value the person typed names no document")

    def test_a_stored_fact_is_listed_in_the_profile_s_own_order(self):
        store = self.open_store()
        store.save_profile(CandidateProfile(skills=frozenset({"Python"}), candidate_country="India"))

        self.assertEqual([entry.fact for entry in store.get_profile_fact_provenance()],
                         ["country", "skills"])

    def test_a_fact_with_no_value_has_no_origin(self):
        """A fact the profile does not state has nothing an origin could describe."""
        store = self.open_store()
        store.save_profile(CandidateProfile(candidate_country="India"))

        self.assertEqual([entry.fact for entry in store.get_profile_fact_provenance()], ["country"])

    def test_saving_the_same_values_again_re_attributes_nothing(self):
        """A re-save is not a new claim about where the values came from."""
        store = self.open_store()
        store.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                           document_name="CV.docx")
        before = store.get_profile_fact_provenance()

        self.assertEqual(store.save_profile(SYNTHETIC), ())
        self.assertEqual(store.get_profile_fact_provenance(), before)

    def test_only_the_fact_that_changed_is_re_attributed(self):
        """This is what stops a save from turning a whole CV's worth of facts into the person's own."""
        store = self.open_store()
        store.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT, document_name="CV.docx")
        edited = CandidateProfile(
            candidate_country="Canada", degree_discipline=SYNTHETIC.degree_discipline,
            study_status=SYNTHETIC.study_status, graduation_year=SYNTHETIC.graduation_year,
            experience_years=SYNTHETIC.experience_years,
            work_authorization=SYNTHETIC.work_authorization, skills=SYNTHETIC.skills,
        )

        self.assertEqual(store.save_profile(edited), ("country",))

        origins = {entry.fact: entry for entry in store.get_profile_fact_provenance()}
        self.assertEqual(origins["country"].source, FactSource.USER_ENTERED,
                         "the fact the person changed is theirs")
        self.assertEqual(origins["skills"].source, FactSource.EXTRACTED_FROM_DOCUMENT,
                         "an untouched fact keeps where it actually came from")
        self.assertEqual(origins["skills"].document_name, "CV.docx")

    def test_a_document_write_records_the_name_and_never_the_folder(self):
        store = self.open_store()

        store.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                           document_name="/home/somebody/private/CV final.docx")

        entries = store.get_profile_fact_provenance()
        self.assertTrue(all(entry.document_name == "CV final.docx" for entry in entries))
        stored = self.database.read_bytes()
        self.assertNotIn(b"somebody", stored, "no folder reaches the database")
        self.assertNotIn(b"/home", stored)

    def test_an_imported_profile_is_recorded_as_imported_and_unverified(self):
        store = self.open_store()

        store.save_profile(SYNTHETIC, source=FactSource.IMPORTED_FROM_FILE, document_name="export.json")

        self.assertTrue(all(entry.source is FactSource.IMPORTED_FROM_FILE
                            for entry in store.get_profile_fact_provenance()))
        self.assertTrue(all(not entry.is_confirmed for entry in store.get_profile_fact_provenance()),
                        "a file another machine wrote is not the person confirming anything")

    def test_a_write_cannot_claim_the_origin_is_unknown(self):
        store = self.open_store()

        with self.assertRaises(ValueError):
            store.save_profile(SYNTHETIC, source=FactSource.UNKNOWN)

        self.assertIsNone(store.get_profile(), "a refused write stores nothing at all")

    def test_a_document_write_without_a_name_is_refused(self):
        """The one source whose whole point is naming the document cannot claim to have none."""
        store = self.open_store()

        for missing in (None, "", "   "):
            with self.subTest(name=missing):
                with self.assertRaises(ValueError):
                    store.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                                       document_name=missing)

        self.assertIsNone(store.get_profile())

    def test_a_write_that_is_not_a_document_may_not_name_one(self):
        store = self.open_store()

        with self.assertRaises(ValueError):
            store.save_profile(SYNTHETIC, source=FactSource.USER_ENTERED, document_name="CV.docx")

        self.assertIsNone(store.get_profile())

    def test_clearing_a_fact_removes_its_origin_with_it(self):
        """An origin for a value that is not there is a claim about nothing."""
        store = self.open_store()
        store.save_profile(SYNTHETIC)
        self.assertIn("country", {entry.fact for entry in store.get_profile_fact_provenance()})

        store.save_profile(CandidateProfile(skills=SYNTHETIC.skills))

        self.assertEqual([entry.fact for entry in store.get_profile_fact_provenance()], ["skills"])
        rows = store._connection.execute(
            "SELECT fact FROM profile_fact_provenance ORDER BY fact").fetchall()
        self.assertEqual([row[0] for row in rows], ["skills"],
                         "the row is deleted, not left describing a value that is gone")

    def test_the_profile_and_its_origins_are_written_in_one_transaction(self):
        """A failure part way must not leave a value stored with the origin of the value it replaced.

        The failure is a real one - a trigger standing in for a full disk - rather than a patched
        connection object, so what is tested is the transaction this store actually opens.
        """
        store = self.open_store()
        store.save_profile(CandidateProfile(candidate_country="India"))
        self._refuse_origin_writes(store)
        changed = CandidateProfile(candidate_country="Canada")

        with self.assertRaises(sqlite3.Error):
            store.save_profile(changed, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                              document_name="CV.docx")

        self.assertEqual(store.get_profile(), CandidateProfile(candidate_country="India"),
                         "the refused write changed no value")
        origins = {entry.fact: entry for entry in store.get_profile_fact_provenance()}
        self.assertEqual(origins["country"].source, FactSource.USER_ENTERED,
                         "and no origin was replaced either")

    @staticmethod
    def _refuse_origin_writes(store) -> None:
        """Make any write to the origin table fail, the way a full disk would."""
        with store._connection:
            for event in ("INSERT", "UPDATE"):
                store._connection.execute(
                    f"""CREATE TRIGGER refuse_origin_{event.lower()}
                        BEFORE {event} ON profile_fact_provenance
                        BEGIN SELECT RAISE(ABORT, 'disk is full'); END"""
                )


class ReadingOriginsTests(ProvenanceTestCase):
    """Reading tells the truth about a profile nothing is known about, and writes nothing."""

    def test_a_profile_stored_before_origins_were_recorded_reads_as_unknown(self):
        """The v7 build recorded no origins; this one must not claim the person typed those values."""
        store = self.open_store()
        payload = ('{"candidate_country": "India", "degree_discipline": null, '
                   '"experience_years": null, "graduation_year": 2027, "preferred_locations": [], '
                   '"preferred_role_types": [], "preferred_work_modes": [], "skills": ["Python"], '
                   '"study_status": null, "work_authorization": null}')
        with store._connection:
            store._connection.execute(
                "INSERT INTO candidate_profile(profile_id, payload, updated_at) VALUES (1, ?, ?)",
                (payload, "2026-10-01T00:00:00+00:00"))

        origins = store.get_profile_fact_provenance()

        self.assertEqual([entry.fact for entry in origins], ["country", "graduation_year", "skills"])
        self.assertTrue(all(entry.source is FactSource.UNKNOWN for entry in origins))
        self.assertTrue(all(not entry.is_confirmed for entry in origins))
        rows = store._connection.execute("SELECT count(*) FROM profile_fact_provenance").fetchone()[0]
        self.assertEqual(rows, 0, "reading a profile records nothing")

    def test_reading_origins_repeats_the_same_answer(self):
        """Two reads of one database agree, so a screen cannot show a different story each time."""
        store = self.open_store()
        store.save_profile(SYNTHETIC)

        self.assertEqual(store.get_profile_fact_provenance(), store.get_profile_fact_provenance())

    def test_no_stored_profile_has_no_origins(self):
        self.assertEqual(self.open_store().get_profile_fact_provenance(), ())

    def test_a_stored_origin_this_build_cannot_use_is_reported_not_guessed(self):
        """A hand-edited or foreign row is refused like any other unreadable record."""
        store = self.open_store()
        store.save_profile(CandidateProfile(candidate_country="India"))

        for column, value in (("source", "telepathy"), ("verification", "probably")):
            with self.subTest(column=column):
                with store._connection:
                    store._connection.execute(
                        f"UPDATE profile_fact_provenance SET {column}=? WHERE fact='country'", (value,))
                with self.assertRaises(StoredRecordError) as caught:
                    store.get_profile_fact_provenance()
                self.assertNotIn(value, str(caught.exception),
                                 "the unreadable value is named as a field, not quoted")
                with store._connection:
                    store._connection.execute(
                        f"UPDATE profile_fact_provenance SET {column}=? WHERE fact='country'",
                        (FactSource.USER_ENTERED.value if column == "source"
                         else FactVerification.UNVERIFIED.value,))

        self.assertEqual(len(store.get_profile_fact_provenance()), 1)

    def test_an_origin_for_a_fact_that_does_not_exist_is_refused(self):
        store = self.open_store()
        store.save_profile(CandidateProfile(candidate_country="India"))
        with store._connection:
            store._connection.execute(
                """INSERT INTO profile_fact_provenance(fact, source, verification, recorded_at)
                   VALUES ('favourite_colour', 'user_entered', 'unverified', '2026-10-16T00:00:00+00:00')""")

        with self.assertRaises(StoredRecordError):
            store.get_profile_fact_provenance()


class ConfirmingAFactTests(ProvenanceTestCase):
    """The only thing that makes a fact confirmed is a person doing it."""

    def test_confirming_a_fact_marks_it_and_keeps_where_it_came_from(self):
        store = self.open_store()
        store.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT, document_name="CV.docx")

        confirmed = store.confirm_profile_fact("country")

        self.assertTrue(confirmed.is_confirmed)
        self.assertEqual(confirmed.verification, FactVerification.USER_CONFIRMED)
        self.assertEqual(confirmed.source, FactSource.EXTRACTED_FROM_DOCUMENT,
                         "a fact read out of a document is still a fact read out of a document")
        self.assertEqual(confirmed.document_name, "CV.docx")
        self.assertIsNotNone(confirmed.confirmed_at)
        self.assertEqual(store.get_profile(), SYNTHETIC, "confirming changes no stored value")

    def test_confirming_twice_changes_nothing_not_even_the_timestamp(self):
        store = self.open_store()
        store.save_profile(SYNTHETIC)

        first = store.confirm_profile_fact("country")
        second = store.confirm_profile_fact("country")

        self.assertEqual(first, second)

    def test_confirming_one_fact_confirms_no_other(self):
        store = self.open_store()
        store.save_profile(SYNTHETIC)

        store.confirm_profile_fact("country")

        origins = {entry.fact: entry for entry in store.get_profile_fact_provenance()}
        self.assertTrue(origins["country"].is_confirmed)
        self.assertEqual([fact for fact, entry in origins.items() if entry.is_confirmed], ["country"])

    def test_a_fact_the_profile_does_not_state_cannot_be_confirmed(self):
        """Confirming nothing would put a row in the database describing a value that is not there."""
        store = self.open_store()
        store.save_profile(CandidateProfile(candidate_country="India"))

        with self.assertRaises(ValueError):
            store.confirm_profile_fact("skills")

        self.assertEqual([entry.fact for entry in store.get_profile_fact_provenance()], ["country"])

    def test_a_field_that_is_not_a_fact_is_refused(self):
        store = self.open_store()
        store.save_profile(SYNTHETIC)

        with self.assertRaises(ValueError):
            store.confirm_profile_fact("password")

    def test_there_is_nothing_to_confirm_without_a_stored_profile(self):
        with self.assertRaises(ValueError):
            self.open_store().confirm_profile_fact("country")

    def test_a_confirmed_fact_that_is_edited_becomes_unconfirmed_again(self):
        """The confirmation was about the value; a different value has not been confirmed by anybody."""
        store = self.open_store()
        store.save_profile(SYNTHETIC)
        store.confirm_profile_fact("country")

        store.save_profile(CandidateProfile(
            candidate_country="Canada", degree_discipline=SYNTHETIC.degree_discipline,
            study_status=SYNTHETIC.study_status, graduation_year=SYNTHETIC.graduation_year,
            experience_years=SYNTHETIC.experience_years,
            work_authorization=SYNTHETIC.work_authorization, skills=SYNTHETIC.skills))

        origins = {entry.fact: entry for entry in store.get_profile_fact_provenance()}
        self.assertFalse(origins["country"].is_confirmed)
        self.assertIsNone(origins["country"].confirmed_at,
                          "the old confirmation is cleared with the value it was about")

    def test_deleting_the_profile_deletes_every_origin_with_it(self):
        """An origin row is a statement about personal data; "delete my profile" takes it too.

        Asserted on the rows, which is what this application promises: the origin table holds nothing, and
        no profile is stored. The *bytes* a deleted row occupied are not asserted absent - SQLite does not
        scrub the pages a deleted row came from, ``research/threat-model-2026-10-16.md`` says so plainly,
        and ``--forget-local-data`` is the path that removes the file itself. An assertion on the raw file
        would have been a promise this project deliberately does not make (and, as the four
        cross-platform CI legs showed, one that only held on Linux).
        """
        store = self.open_store()
        store.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT, document_name="CV.docx")

        self.assertTrue(store.delete_profile())

        self.assertEqual(store.get_profile_fact_provenance(), ())
        rows = store._connection.execute("SELECT count(*) FROM profile_fact_provenance").fetchone()[0]
        self.assertEqual(rows, 0, "no row is left describing data that is gone")
        self.assertIsNone(store.get_profile(), "the profile it described is gone too")


class PersistenceTests(ProvenanceTestCase):
    """What is recorded survives a restart, a backup and a restore - or it is not a record."""

    def test_origins_survive_closing_and_reopening_the_database(self):
        store = self.open_store()
        store.save_profile(SYNTHETIC, source=FactSource.IMPORTED_FROM_FILE, document_name="export.json")
        store.confirm_profile_fact("skills")
        before = store.get_profile_fact_provenance()
        store.close()

        reopened = self.open_store()

        self.assertEqual(reopened.get_profile_fact_provenance(), before)

    def test_an_origin_stored_by_one_connection_is_read_by_another(self):
        """The row is in the file, not in the store object that wrote it."""
        writer = self.open_store()
        writer.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT, document_name="CV.docx")
        writer.confirm_profile_fact("country")

        reader = self.open_store()

        origins = {entry.fact: entry for entry in reader.get_profile_fact_provenance()}
        self.assertEqual(origins["country"].source, FactSource.EXTRACTED_FROM_DOCUMENT)
        self.assertTrue(origins["country"].is_confirmed)
        self.assertEqual(origins["skills"].source, FactSource.EXTRACTED_FROM_DOCUMENT)


class PrivacyTests(ProvenanceTestCase):
    """What the log and the error messages are allowed to carry."""

    def test_the_log_names_the_fact_and_the_origin_and_no_value(self):
        store = self.open_store()
        store.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT, document_name="CV.docx")
        store.confirm_profile_fact("country")

        log = (self.database.parent / "logs" / "application.log").read_text(encoding="utf-8")

        self.assertIn("event=profile.saved", log)
        self.assertIn("event=profile.fact_confirmed detail=fact=country", log)
        for value in ("India", "Electronics", "Python", "SQL", "citizen", "CV.docx"):
            with self.subTest(value=value):
                self.assertNotIn(value, log, "a stored value or document name must not reach the log")

    def test_an_origin_that_cannot_be_read_does_not_quote_the_document_it_names(self):
        store = self.open_store()
        store.save_profile(SYNTHETIC, source=FactSource.EXTRACTED_FROM_DOCUMENT,
                           document_name="somebody's private CV.docx")
        with store._connection:
            store._connection.execute(
                "UPDATE profile_fact_provenance SET source='telepathy' WHERE fact='country'")

        with self.assertRaises(StoredRecordError) as caught:
            store.get_profile_fact_provenance()

        self.assertNotIn("private CV", str(caught.exception))

    def test_the_saved_origin_row_carries_no_other_column(self):
        """The table is exactly as wide as the record it holds: no room for a copy of the value."""
        store = self.open_store()
        columns = [row["name"] for row in store._connection.execute(
            "SELECT name FROM pragma_table_info('profile_fact_provenance')")]
        self.assertEqual(columns, ["fact", "source", "verification", "document_name", "recorded_at",
                                   "confirmed_at"])


class HandEditedRecordTests(ProvenanceTestCase):
    """A row this build cannot read is reported as itself and never repaired."""

    def test_a_row_whose_fields_contradict_each_other_is_reported_as_damaged(self):
        """An origin that names a document *and* says the person typed it describes nothing."""
        store = self.open_store()
        store.save_profile(CandidateProfile(candidate_country="India"))
        with store._connection:
            store._connection.execute(
                "UPDATE profile_fact_provenance SET document_name='CV.docx' WHERE fact='country'")

        with self.assertRaises(StoredRecordError) as caught:
            store.get_profile_fact_provenance()

        self.assertIn("origin of the country fact", str(caught.exception))
        row = store._connection.execute(
            "SELECT source, document_name FROM profile_fact_provenance WHERE fact='country'").fetchone()
        self.assertEqual((row["source"], row["document_name"]), ("user_entered", "CV.docx"),
                         "nothing was repaired to make the record readable")

    def test_a_row_with_an_empty_recorded_time_is_refused_rather_than_given_one(self):
        """A blank where a timestamp belongs is a damaged row, not a row from the past."""
        store = self.open_store()
        store.save_profile(CandidateProfile(candidate_country="India"))
        with store._connection:
            store._connection.execute(
                "UPDATE profile_fact_provenance SET recorded_at='' WHERE fact='country'")

        with self.assertRaises(StoredRecordError) as caught:
            store.get_profile_fact_provenance()

        self.assertIn("recorded_at", str(caught.exception))
        row = store._connection.execute(
            "SELECT recorded_at FROM profile_fact_provenance WHERE fact='country'").fetchone()
        self.assertEqual(row["recorded_at"], "", "nothing was repaired to make the record readable")


class ADatabaseHeldAtAnOlderSchemaTests(ProvenanceTestCase):
    """The one case where a write has nowhere to put an origin, and says so instead of pretending."""

    def open_at_version(self, version: int) -> CareerStore:
        steps = tuple(step for step in store_module._MIGRATIONS if step[0] <= version)
        with mock.patch.object(store_module, "_MIGRATIONS", steps):
            store = CareerStore(self.database)
        self.addCleanup(store.close)
        return store

    def test_a_write_to_an_older_file_records_no_origin_and_claims_none(self):
        older = self.open_at_version(7)

        self.assertEqual(older.save_profile(SYNTHETIC), (),
                         "the return value reports what was recorded, which here is nothing")
        self.assertEqual(older.get_profile(), SYNTHETIC, "the profile itself is still written")

        log = (self.database.parent / "logs" / "application.log").read_text(encoding="utf-8")
        self.assertIn("this file predates schema 8", log)

    def test_an_older_file_refuses_to_confirm_a_fact_it_cannot_hold(self):
        older = self.open_at_version(7)
        older.save_profile(SYNTHETIC)

        with self.assertRaises(ValueError) as caught:
            older.confirm_profile_fact("country")

        self.assertIn("older", str(caught.exception))

    def test_upgrading_the_file_reads_the_stored_facts_as_unknown(self):
        older = self.open_at_version(7)
        older.save_profile(SYNTHETIC)
        older.close()

        upgraded = self.open_store()

        self.assertEqual(upgraded._connection.execute("PRAGMA user_version").fetchone()[0],
                         store_module.SCHEMA_VERSION)
        self.assertTrue(all(entry.source is FactSource.UNKNOWN
                            for entry in upgraded.get_profile_fact_provenance()))


if __name__ == "__main__":  # pragma: no cover - the suite runs the module through discovery
    unittest.main()
