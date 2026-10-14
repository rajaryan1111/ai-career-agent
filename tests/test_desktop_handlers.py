"""Handler-level regression tests for career_agent.desktop.

Tkinter is not guaranteed to be installed in headless CI, so this module installs a
minimal stub for the widget classes and dialogs the handlers touch, then imports and
exercises the real desktop module against real SQLite files in a temporary directory.

These tests verify handler decisions, validation messages, and database-error
handling. They do not verify rendering, theming, layout, or macOS behaviour; the
manual smoke-test checklist in research/ is still required before GUI acceptance.
"""
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from career_agent import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, Decision, JobListing,
    evaluate_eligibility,
)
from career_agent.store import CareerStore


class StringVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class BooleanVar:
    """Mirrors StringVar for the assertion checkbox; Tk is stubbed in headless CI."""

    def __init__(self, value=False):
        self.value = bool(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)


class Widget:
    def __init__(self, *args, **kwargs):
        self.options = kwargs

    def pack(self, *args, **kwargs):
        return self

    def grid(self, *args, **kwargs):
        return self

    def configure(self, *args, **kwargs):
        return self

    def rowconfigure(self, *args, **kwargs):
        return self

    def columnconfigure(self, *args, **kwargs):
        return self

    def heading(self, *args, **kwargs):
        return self

    def column(self, *args, **kwargs):
        return self

    def bind(self, *args, **kwargs):
        return self

    def title(self, *args, **kwargs):
        return None

    def geometry(self, *args, **kwargs):
        return None

    def minsize(self, *args, **kwargs):
        return None

    def protocol(self, *args, **kwargs):
        return None

    def add(self, *args, **kwargs):
        return None

    def transient(self, *args, **kwargs):
        return None

    def grab_set(self, *args, **kwargs):
        return None

    def insert(self, *args, **kwargs):
        return None

    def delete(self, *args, **kwargs):
        return None

    def destroy(self):
        self.destroyed = True


class Tree(Widget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = ()
        self.inserted = ()
        self.selected = ()
        self.children = ()

    def selection(self):
        return self.selected

    def selection_set(self, selection):
        # Real Tk accepts either one item id or a sequence; a bare string is one item.
        self.selected = (selection,) if isinstance(selection, str) else tuple(selection)

    def delete(self, item):
        self.rows = tuple(row for row in self.rows if row != item)

    def selection_remove(self, selection):
        self.selected = ()

    def get_children(self):
        return self.children

    def insert(self, parent, index, iid=None, values=None):
        self.rows += (iid,)
        self.inserted += ((iid, values),)
        return iid


class MessageRecorder:
    """Records dialog calls; ``askyesno`` answers come from ``CONFIG`` by dialog title."""

    def __init__(self):
        self.calls = []

    def reset(self):
        self.calls = []

    def _record(self, kind, title, message, answer=True):
        self.calls.append((title, answer, kind))
        return answer

    def showinfo(self, title, message, **kwargs):
        return self._record("showinfo", title, message)

    def showwarning(self, title, message, **kwargs):
        return self._record("showwarning", title, message)

    def showerror(self, title, message, **kwargs):
        return self._record("showerror", title, message)

    def askyesno(self, title, message, **kwargs):
        return self._record("askyesno", title, message, CONFIG.get(title, True))

    def titles(self, kind=None):
        return [title for title, _answer, call_kind in self.calls if kind is None or kind == call_kind]


class ButtonRegistry:
    """Remembers the command of the most recently created button."""

    def __init__(self):
        self.command = None

    def clear(self):
        self.command = None

    def button(self, *args, **kwargs):
        if kwargs.get("command"):
            self.command = kwargs["command"]
        return Widget(**kwargs)


class FileDialog:
    def __init__(self):
        self.path = ""

    def asksaveasfilename(self, **kwargs):
        return self.path


CONFIG = {}
BUTTONS = ButtonRegistry()
MESSAGES = MessageRecorder()
FILEDIALOG = FileDialog()

_tkinter = types.ModuleType("tkinter")
_tkinter.Tk = Widget
_tkinter.Toplevel = Widget
_tkinter.Text = Widget
_tkinter.StringVar = StringVar
_tkinter.BooleanVar = BooleanVar
_tkinter.BOTH = "both"
_tkinter.END = "end"
_tkinter.LEFT = "left"
_tkinter.W = "w"
_tkinter.X = "x"
_tkinter.filedialog = FILEDIALOG
_tkinter.messagebox = MESSAGES
_tkinter.ttk = types.SimpleNamespace(
    Frame=Widget, Label=Widget, Notebook=Widget, Combobox=Widget, Entry=Widget, Treeview=Tree,
    Checkbutton=Widget, Button=BUTTONS.button,
)

_ORIGINAL_TKINTER = sys.modules.get("tkinter")
sys.modules["tkinter"] = _tkinter

from career_agent import desktop  # noqa: E402  (imported after the stub is installed)
from career_agent.desktop_logic import job_form_values, profile_form_values  # noqa: E402


def tearDownModule():
    """Restore the real (or absent) tkinter entry; the desktop module keeps the stub references."""
    if _ORIGINAL_TKINTER is None:
        sys.modules.pop("tkinter", None)
    else:
        sys.modules["tkinter"] = _ORIGINAL_TKINTER


PROFILE = CandidateProfile(
    candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
    graduation_year=2027, experience_years=0.5, work_authorization="authorized_without_sponsorship",
    skills=frozenset({"Python", "RAG"}), preferred_work_modes=frozenset({"remote"}),
)


def sample_job(**overrides):
    values = dict(
        listing_id="j1", source_id="manual", source_name="Manual entry",
        source_listing_url="https://jobs.example/role/1", employer_name="Example Inc",
        role_title="AI Intern", availability_status=Availability.OPEN,
        employer_apply_url=None, canonical_requisition_id=None, location_text="Bengaluru",
        work_mode="remote", role_type="internship", eligibility_scope="restricted",
        eligible_countries=("India",), allowed_degree_disciplines=("ECE",),
        allowed_study_statuses=("undergraduate",), allowed_graduation_years=(2027,),
        allowed_work_authorizations=("authorized_without_sponsorship",),
        minimum_experience_years=0.0, maximum_experience_years=2.0,
        required_skills=frozenset({"Python"}), provenance_note="Official listing checked today.",
    )
    values.update(overrides)
    return JobListing(**values)


#: Permitted path used by tests that need an already-advanced tracker record.
_PATH_TO_SUBMISSION = (
    ApplicationStatus.SHORTLISTED,
    ApplicationStatus.PREPARED,
    ApplicationStatus.AWAITING_USER,
    ApplicationStatus.SUBMISSION_ATTEMPTED,
)


def reach_status(store, target, listing_id="j1", *, evidence=None):
    """Advance a tracker from discovered to ``target`` through permitted transitions (test scaffolding)."""
    tracker = ApplicationTracker(listing_id)
    store.save_tracker(tracker)
    if target is ApplicationStatus.DISCOVERED:
        return tracker
    for status in _PATH_TO_SUBMISSION:
        tracker = tracker.transition(status)
        store.save_tracker(tracker)
        if status is target:
            return tracker
    if target is ApplicationStatus.CONFIRMED:
        tracker = tracker.transition(
            ApplicationStatus.CONFIRMED,
            evidence=evidence or "Employer confirmation email",
            candidate_confirmed=True,
        )
        store.save_tracker(tracker)
        return tracker
    raise AssertionError(f"reach_status does not support {target}")


class HandlerTestCase(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.store = CareerStore(str(Path(self._directory.name) / "handlers.sqlite3"))
        self.addCleanup(self.store.close)
        CONFIG.clear()
        MESSAGES.reset()
        BUTTONS.clear()
        FILEDIALOG.path = ""

    def make_app(self, *, with_profile=False):
        """Build a real CareerAgentApp instance with stub widgets instead of a Tk root."""
        app = desktop.CareerAgentApp.__new__(desktop.CareerAgentApp)
        app.root = Widget()
        app.store = self.store
        app.status = StringVar()
        app.job_mode = StringVar()
        app.selected_job_id = None
        app.job_save_mode = desktop.JobSaveMode.NEW
        app.job_edit_baseline = None
        app.jobs_tree = Tree()
        app.tracker_tree = Tree()
        app.profile_tab = Widget()
        app.jobs_tab = Widget()
        app.tracker_tab = Widget()
        selected_tabs = []
        app.tabs = types.SimpleNamespace(select=lambda tab: selected_tabs.append(tab), selected_tabs=selected_tabs)
        app._refresh_jobs = lambda: None
        app._refresh_tracker = lambda: None
        app._evaluate = lambda: None
        app._report = lambda text: None
        app.job_vars = {key: StringVar(value) for key, value in job_form_values(sample_job()).items()}
        app.profile_vars = {key: StringVar(value) for key, value in profile_form_values(PROFILE).items()}
        if with_profile:
            self.store.save_profile(PROFILE)
        return app

    def fill_job_form(self, app, values):
        for key, value in values.items():
            app.job_vars[key].set(value)

    def open_status_dialog(self, listing_id="j1"):
        """Run the real handler and return the dialog's variables plus its save button command.

        Returns ``(app, status_var, evidence_var, confirmed_assertion, apply)``. The assertion
        variable models the checkbox: it starts unchecked, so only tests that explicitly assert a
        real confirmation can record one.
        """
        app = self.make_app()
        app.tracker_tree.selected = (listing_id,)
        created = []
        original_stringvar = desktop.tk.StringVar
        original_booleanvar = desktop.tk.BooleanVar

        def recording(variable_class):
            def factory(*args, **kwargs):
                variable = variable_class(*args, **kwargs)
                created.append(variable)
                return variable

            return factory

        desktop.tk.StringVar = recording(original_stringvar)
        desktop.tk.BooleanVar = recording(original_booleanvar)
        self.addCleanup(setattr, desktop.tk, "StringVar", original_stringvar)
        self.addCleanup(setattr, desktop.tk, "BooleanVar", original_booleanvar)
        app._update_status()
        return app, created[0], created[1], created[2], BUTTONS.command


class StartupPathTests(unittest.TestCase):
    """The window construction path runs with stub widgets; rendering is still unverified."""

    def test_window_construction_and_refresh_paths_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            app = desktop.CareerAgentApp(Widget(), database_path=Path(directory) / "startup.sqlite3")
        self.assertTrue(app.job_save_mode is desktop.JobSaveMode.NEW)
        self.assertIn("New listing", app.job_mode.get())
        self.assertEqual(app.job_vars["availability"].get(), "unknown")
        self.assertEqual(app.job_vars["scope"].get(), "unknown")
        self.assertEqual(app.db_path.name, "startup.sqlite3")
        app.close()
        self.assertTrue(app.root.destroyed)


class NewJobSaveTests(HandlerTestCase):
    def test_new_job_does_not_overwrite_the_selected_listing(self):
        saved = sample_job()
        self.store.save_job(saved)
        app = self.make_app()
        app.jobs_tree.selected = ("j1",)
        app._select_job()
        self.assertTrue(app.job_save_mode is desktop.JobSaveMode.EDIT)

        app._begin_new_job()
        self.assertTrue(app.job_save_mode is desktop.JobSaveMode.NEW)
        self.assertIsNone(app.selected_job_id)
        self.fill_job_form(app, {**job_form_values(sample_job()), "employer": "Another Company",
                                 "title": "Data Intern", "source_url": "https://jobs.example/role/2"})
        app._save_job()

        listings = {job.listing_id: job for job in self.store.list_jobs()}
        self.assertEqual(len(listings), 2)
        self.assertEqual(listings["j1"], saved)
        new_job = next(job for job in listings.values() if job.listing_id != "j1")
        self.assertEqual(new_job.employer_name, "Another Company")
        self.assertIn("Saved", app.status.get())

    def test_new_job_matching_an_existing_url_asks_before_saving_a_second_observation(self):
        self.store.save_job(sample_job())
        app = self.make_app()
        CONFIG["Possible duplicate"] = False
        app._save_job()
        self.assertEqual(len(self.store.list_jobs()), 1)
        self.assertIn("Possible duplicate", MESSAGES.titles())

        MESSAGES.reset()
        CONFIG["Possible duplicate"] = True
        app._save_job()
        self.assertEqual(len(self.store.list_jobs()), 2)
        self.assertEqual(len(self.store.find_duplicate_group(sample_job())), 2)

    def test_each_new_job_gets_its_own_identity(self):
        app = self.make_app()
        app._begin_new_job()
        self.fill_job_form(app, job_form_values(sample_job()))
        app._save_job()
        first_id = app.selected_job_id
        second_url = "https://jobs.example/role/3"

        app._begin_new_job()
        self.fill_job_form(app, {**job_form_values(sample_job()), "source_url": second_url})
        app._save_job()

        saved = {job.listing_id: job for job in self.store.list_jobs()}
        self.assertEqual(len(saved), 2)
        self.assertNotEqual(app.selected_job_id, first_id)
        self.assertIn(app.selected_job_id, saved)
        self.assertEqual(saved[first_id].source_listing_url, "https://jobs.example/role/1")
        self.assertEqual(saved[app.selected_job_id].source_listing_url, second_url)

    def test_new_mode_creates_missing_tracker_rows_and_keeps_existing_ones(self):
        app = self.make_app()
        app._begin_new_job()
        self.fill_job_form(app, job_form_values(sample_job()))
        app._save_job()
        listing_id = app.selected_job_id
        self.assertEqual(self.store.get_tracker(listing_id).status, ApplicationStatus.DISCOVERED)

        self.store.save_tracker(ApplicationTracker(listing_id, ApplicationStatus.SHORTLISTED))
        app._save_job()
        self.assertEqual(self.store.get_tracker(listing_id).status, ApplicationStatus.SHORTLISTED)


class EditJobSaveTests(HandlerTestCase):
    def test_selecting_a_job_switches_to_edit_mode_and_fills_the_form(self):
        self.store.save_job(sample_job())
        app = self.make_app()
        app.jobs_tree.selected = ("j1",)
        app._select_job()
        self.assertEqual(app.selected_job_id, "j1")
        self.assertTrue(app.job_save_mode is desktop.JobSaveMode.EDIT)
        self.assertEqual(app.job_vars["employer"].get(), "Example Inc")
        self.assertEqual(app.job_vars["countries"].get(), "India")
        self.assertIn("Editing", app.job_mode.get())

    def test_edit_keeps_identity_and_asks_before_an_eligibility_relevant_change(self):
        self.store.save_job(sample_job())
        tracker = reach_status(self.store, ApplicationStatus.SHORTLISTED)
        app = self.make_app()
        app.jobs_tree.selected = ("j1",)
        app._select_job()
        app.job_vars["countries"].set("United States")

        CONFIG["Update saved listing"] = False
        app._save_job()
        self.assertEqual(self.store.get_job("j1").eligible_countries, ("India",))
        self.assertEqual(app.status.get(), "")
        self.assertIn("Update saved listing", MESSAGES.titles())

        MESSAGES.reset()
        CONFIG["Update saved listing"] = True
        app._save_job()
        updated = self.store.get_job("j1")
        self.assertEqual(updated.listing_id, "j1")
        self.assertEqual(updated.eligible_countries, ("United States",))
        self.assertEqual(updated.employer_name, "Example Inc")
        self.assertEqual(self.store.get_tracker("j1"), tracker)
        self.assertEqual(len(self.store.list_jobs()), 1)

    def test_edit_without_a_consequential_change_saves_without_a_prompt(self):
        self.store.save_job(sample_job())
        app = self.make_app()
        app.jobs_tree.selected = ("j1",)
        app._select_job()
        app.job_vars["source_name"].set("Manual entry (rechecked)")
        app._save_job()
        self.assertEqual(self.store.get_job("j1").source_name, "Manual entry (rechecked)")
        self.assertNotIn("Update saved listing", MESSAGES.titles())
        self.assertIn("Saved", app.status.get())

    def test_edit_reports_a_changed_availability_note_as_consequential(self):
        self.store.save_job(sample_job())
        app = self.make_app()
        app.jobs_tree.selected = ("j1",)
        app._select_job()
        app.job_vars["provenance_note"].set("Rechecked on a later date.")
        CONFIG["Update saved listing"] = False
        app._save_job()
        self.assertEqual(self.store.get_job("j1").provenance_note, "Official listing checked today.")
        self.assertIn("Update saved listing", MESSAGES.titles())

    def test_edit_of_an_existing_listing_without_a_job_selection_is_refused(self):
        app = self.make_app()
        app.job_save_mode = desktop.JobSaveMode.EDIT
        app.selected_job_id = None
        app._save_job()
        self.assertIn("Cannot save job", MESSAGES.titles())
        self.assertEqual(self.store.list_jobs(), ())


class SelectedJobReportTests(HandlerTestCase):
    """The report pane must not echo credentials held in rows saved before URL validation existed."""

    def test_selected_job_report_redacts_stored_credentials_without_rewriting_the_record(self):
        legacy = sample_job(
            source_listing_url="https://user:pass@jobs.example/role/1?token=abcdef",
            employer_apply_url="https://jobs.example/apply/1#sig=deadbeef",
            provenance_note="Checked https://jobs.example/role/1?api_key=abcd",
        )
        self.store.save_job(legacy)
        app = self.make_app()
        reports = []
        app._report = reports.append
        app.jobs_tree.selected = ("j1",)

        app._select_job()

        self.assertEqual(len(reports), 1)
        report = reports[0]
        for secret in ("pass@", "abcdef", "deadbeef", "api_key=abcd"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, report)
        self.assertIn("***@jobs.example", report)
        # Redaction is display-only: the stored row is untouched...
        self.assertEqual(self.store.get_job("j1"), legacy)
        # ...and the edit form still shows the stored value so the candidate can correct it themselves.
        self.assertEqual(app.job_vars["source_url"].get(), legacy.source_listing_url)


class DatabaseErrorTests(HandlerTestCase):
    def closed_store_app(self):
        app = self.make_app(with_profile=True)
        app.store.close()  # later reads and writes raise real sqlite3 errors
        return app

    def test_save_job_reports_a_database_error_without_claiming_success(self):
        app = self.closed_store_app()
        app._begin_new_job()
        self.fill_job_form(app, job_form_values(sample_job()))
        app._save_job()
        self.assertIn("Job not saved", MESSAGES.titles())
        self.assertNotIn("Saved", app.status.get())
        self.assertIn("local database error", app.status.get())

    def test_save_profile_reports_a_database_error_without_claiming_success(self):
        app = self.closed_store_app()
        app._save_profile()
        self.assertIn("Profile not saved", MESSAGES.titles())
        self.assertNotIn("saved locally", app.status.get())

    def test_failed_job_save_preserves_existing_data(self):
        self.store.save_job(sample_job())
        app = self.closed_store_app()
        app._begin_new_job()
        self.fill_job_form(app, {**job_form_values(sample_job()), "source_url": "https://jobs.example/role/9"})
        app._save_job()
        reopened = CareerStore(self.store.database_path)
        self.addCleanup(reopened.close)
        self.assertEqual([job.listing_id for job in reopened.list_jobs()], ["j1"])

    def test_shortlist_reports_a_database_error_without_claiming_success(self):
        self.store.save_job(sample_job())
        self.store.save_profile(PROFILE)
        app = self.make_app()
        app.selected_job_id = "j1"
        with mock.patch.object(self.store, "save_tracker",
                               side_effect=sqlite3.OperationalError("attempt to write a readonly database")):
            app._shortlist()
        self.assertIn("Shortlist not saved", MESSAGES.titles())
        self.assertNotIn("shortlisted", app.status.get())
        self.assertIsNone(self.store.get_tracker("j1"))

    def test_shortlist_still_blocks_ineligible_jobs(self):
        self.store.save_job(sample_job(eligible_countries=("United States",)))
        self.store.save_profile(PROFILE)
        app = self.make_app()
        app.selected_job_id = "j1"
        app._shortlist()
        self.assertIn("Not eligible to shortlist", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"))


class MissingTrackerRowTests(HandlerTestCase):
    """A job without a tracker row: a refused change must not create one, a valid one must."""

    def test_shortlist_creates_the_initial_record_first(self):
        self.store.save_job(sample_job())
        self.store.save_profile(PROFILE)
        self.assertIsNone(self.store.get_tracker("j1"))
        app = self.make_app()
        app.selected_job_id = "j1"
        app._shortlist()
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.SHORTLISTED)
        self.assertFalse(stored.candidate_confirmed)
        self.assertNotIn("Not eligible to shortlist", MESSAGES.titles())

    def test_valid_initial_state_creates_the_record_at_discovered(self):
        self.store.save_job(sample_job())
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("discovered")
        apply()
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.DISCOVERED)
        self.assertIsNone(stored.status_evidence)
        self.assertFalse(stored.candidate_confirmed)
        self.assertNotIn("Invalid status change", MESSAGES.titles())
        self.assertIn("record created at discovered", app.status.get())

    def test_valid_transition_from_a_new_record_is_created_then_advanced(self):
        self.store.save_job(sample_job())
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("shortlisted")
        apply()
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.SHORTLISTED)
        self.assertFalse(stored.candidate_confirmed)
        self.assertNotIn("Invalid status change", MESSAGES.titles())
        self.assertIn("updated to shortlisted", app.status.get())

    def test_invalid_initial_jump_creates_no_record(self):
        self.store.save_job(sample_job())
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("interview")
        evidence_var.set("pretend invite")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"))
        self.assertNotIn("updated", app.status.get())

    def test_invalid_initial_confirmed_creates_no_record(self):
        self.store.save_job(sample_job())
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("fabricated confirmation")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"))
        self.assertNotIn("updated", app.status.get())

    def test_other_invalid_initial_states_create_no_record(self):
        # From the permitted initial status only "shortlisted" and "withdrawn" are allowed,
        # so these targets must be refused without creating a row.
        for status in ("prepared", "awaiting_user", "submission_attempted", "submitted_unverified",
                       "response_received", "failed"):
            with self.subTest(status=status):
                directory = tempfile.TemporaryDirectory()
                self.addCleanup(directory.cleanup)
                store = CareerStore(str(Path(directory.name) / f"{status}.sqlite3"))
                self.addCleanup(store.close)
                store.save_job(sample_job())
                self.store = store
                MESSAGES.reset()
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
                status_var.set(status)
                apply()
                self.assertIn("Invalid status change", MESSAGES.titles())
                self.assertIsNone(store.get_tracker("j1"))

    def test_refused_change_leaves_the_file_backed_database_without_a_row(self):
        """Re-read the database from disk: a refused change must not persist anything."""
        self.store.close()
        reopened = CareerStore(self.store.database_path)
        self.addCleanup(reopened.close)
        reopened.save_job(sample_job())
        self.store = reopened
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("interview")
        apply()
        from_disk = CareerStore(self.store.database_path)
        self.addCleanup(from_disk.close)
        self.assertIsNone(from_disk.get_tracker("j1"))





    def test_partial_write_after_a_valid_action_is_reported_and_leaves_a_truthful_row(self):
        """Documented behavior: creating and advancing a new record is two writes, not one transaction.

        The first write creates the record at the permitted initial status and the second applies
        the transition. If the second fails, the handler reports failure and no success message,
        and the database holds the truthful ``discovered`` row rather than a fabricated status.
        This test demonstrates that behavior; it does not claim atomicity for the pair.
        """
        self.store.save_job(sample_job())
        real_save = self.store.save_tracker
        calls = []

        def failing_second_write(tracker):
            calls.append(tracker.status)
            if len(calls) == 2:
                raise sqlite3.OperationalError("database is locked")
            return real_save(tracker)

        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        with mock.patch.object(self.store, "save_tracker", side_effect=failing_second_write):
            status_var.set("shortlisted")
            apply()
        self.assertEqual(calls, [ApplicationStatus.DISCOVERED, ApplicationStatus.SHORTLISTED])
        self.assertIn("Status not saved", MESSAGES.titles())
        self.assertNotIn("updated", app.status.get())
        from_disk = CareerStore(self.store.database_path)
        self.addCleanup(from_disk.close)
        persisted = from_disk.get_tracker("j1")
        self.assertIsNotNone(persisted, "the first (truthful) write should be present")
        self.assertEqual(persisted.status, ApplicationStatus.DISCOVERED)
        self.assertIsNone(persisted.status_evidence)


class TrackerUpdateTests(HandlerTestCase):
    def setUp(self):
        super().setUp()
        self.store.save_job(sample_job())
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)

    def test_confirmation_still_requires_evidence(self):
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("   ")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SUBMISSION_ATTEMPTED)

    def test_confirmation_with_evidence_is_saved(self):
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("Employer portal shows Application Received (2026-10-14)")
        assertion.set(True)
        apply()
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.CONFIRMED)
        self.assertEqual(stored.status_evidence, "Employer portal shows Application Received (2026-10-14)")
        self.assertTrue(stored.candidate_confirmed)
        self.assertIn("updated to confirmed", app.status.get())

    def test_confirmation_without_the_explicit_assertion_is_refused_and_writes_nothing(self):
        """The status dialog must never set candidate_confirmed on the candidate's behalf."""
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("Employer portal shows Application Received (2026-10-14)")
        self.assertFalse(assertion.get(), "the assertion must start unticked")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertNotIn("updated", app.status.get())
        stored = self.store.get_tracker("j1")
        self.assertIs(stored.status, ApplicationStatus.SUBMISSION_ATTEMPTED)
        self.assertIsNone(stored.status_evidence)
        self.assertFalse(stored.candidate_confirmed)

    def test_assertion_with_instruction_text_is_refused_and_writes_nothing(self):
        """Regression for the smoke-test record: guidance text must not become proof of confirmation."""
        for text in (
            "A confirmed application requires evidence. An attempt or timeout is not proof.",
            "Evidence / note (required to confirm)",
            "Confirm with a meaningful evidence note, then move it to response_received or interview.",
            "todo",
            "   ",
        ):
            with self.subTest(text=text[:40]):
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
                status_var.set("confirmed")
                evidence_var.set(text)
                assertion.set(True)
                apply()
                self.assertIn("Invalid status change", MESSAGES.titles())
                stored = self.store.get_tracker("j1")
                self.assertIs(stored.status, ApplicationStatus.SUBMISSION_ATTEMPTED)
                self.assertIsNone(stored.status_evidence)
                self.assertFalse(stored.candidate_confirmed)
                MESSAGES.reset()

    def test_the_assertion_cannot_be_used_with_a_non_confirmation_status(self):
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("submitted_unverified")
        evidence_var.set("Submitted through the employer portal")
        assertion.set(True)
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        stored = self.store.get_tracker("j1")
        self.assertIs(stored.status, ApplicationStatus.SUBMISSION_ATTEMPTED)
        self.assertFalse(stored.candidate_confirmed)

    def test_unchecked_assertion_still_allows_the_ordinary_forward_path(self):
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("submitted_unverified")
        evidence_var.set("Submitted through the employer portal")
        apply()
        self.assertIn("updated to submitted_unverified", app.status.get())
        stored = self.store.get_tracker("j1")
        self.assertIs(stored.status, ApplicationStatus.SUBMITTED_UNVERIFIED)
        self.assertFalse(stored.candidate_confirmed)

    def test_gui_can_withdraw_a_mistaken_confirmation_but_keeps_the_confirmation_flag(self):
        """Documents why a separate, backed-up correction exists.

        The supported forward path can stop pursuing a mistaken confirmation, and the evidence is
        revised honestly, but the dialog deliberately never clears an existing confirmation flag on
        its own. Correcting the flag itself is an explicit, backed-up action
        (see ``scripts/correct_tracker_record.py``) so the change is auditable.
        """
        # Walk the real dialog path: submit unverified, then confirm with the assertion ticked.
        _, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("submitted_unverified")
        evidence_var.set("Submitted through the employer portal")
        apply()
        _, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("Employer portal shows Application Received (2026-10-14)")
        assertion.set(True)
        apply()
        self.assertIs(self.store.get_tracker("j1").status, ApplicationStatus.CONFIRMED)

        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("withdrawn")
        evidence_var.set("Fictional smoke-test record: no application was ever submitted")
        apply()
        stored = self.store.get_tracker("j1")
        self.assertIs(stored.status, ApplicationStatus.WITHDRAWN)
        self.assertEqual(stored.status_evidence, "Fictional smoke-test record: no application was ever submitted")
        self.assertTrue(stored.candidate_confirmed, "the dialog does not silently clear a stored flag")

    def test_no_op_transition_does_not_claim_success_and_keeps_the_old_evidence(self):
        advanced = self.store.get_tracker("j1").transition(
            ApplicationStatus.CONFIRMED, evidence="original evidence", candidate_confirmed=True
        )
        self.store.save_tracker(advanced)
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("replacement evidence that must not be stored")
        assertion.set(True)
        apply()
        self.assertIn("No change", MESSAGES.titles())
        self.assertNotIn("updated", app.status.get())
        self.assertIn("Nothing was saved", app.status.get())
        self.assertEqual(self.store.get_tracker("j1").status_evidence, "original evidence")

    def test_evidence_can_be_revised_by_moving_the_status_forward(self):
        _, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("Employer portal shows Application Received (2026-10-14)")
        assertion.set(True)
        apply()
        MESSAGES.reset()
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("response_received")
        evidence_var.set("Employer replied with a screening request")
        apply()
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.RESPONSE_RECEIVED)
        self.assertEqual(stored.status_evidence, "Employer replied with a screening request")
        self.assertTrue(stored.candidate_confirmed)

    def test_invalid_status_selection_is_reported(self):
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SUBMISSION_ATTEMPTED)

    def test_invalid_jump_is_reported(self):
        self.store.save_job(sample_job(listing_id="j2", source_listing_url="https://jobs.example/role/2"))
        self.store.save_tracker(ApplicationTracker("j2", ApplicationStatus.DISCOVERED))
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog("j2")
        status_var.set("interview")
        evidence_var.set("pretend invite")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        stored = self.store.get_tracker("j2")
        self.assertEqual(stored.status, ApplicationStatus.DISCOVERED)
        self.assertIsNone(stored.status_evidence)
        self.assertFalse(stored.candidate_confirmed)
        self.assertNotIn("updated", app.status.get())

    def test_invalid_jump_leaves_an_advanced_record_untouched(self):
        """A refused change must not modify status, evidence, or the confirmation flag."""
        before = self.store.get_tracker("j1")
        self.assertEqual(before.status, ApplicationStatus.SUBMISSION_ATTEMPTED)
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("interview")
        evidence_var.set("pretend invite")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        after = self.store.get_tracker("j1")
        self.assertEqual(after, before)
        self.assertNotIn("updated", app.status.get())

    def test_database_error_is_reported_without_claiming_success(self):
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("Employer portal shows Application Received (2026-10-14)")
        assertion.set(True)
        with mock.patch.object(self.store, "save_tracker", side_effect=sqlite3.OperationalError("database is locked")):
            apply()
        self.assertIn("Status not saved", MESSAGES.titles())
        self.assertNotIn("updated", app.status.get())
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SUBMISSION_ATTEMPTED)


class TrackerConfirmationRegressionTests(HandlerTestCase):
    """Confirmation-dialog regressions, driven through the real handler on temporary databases.

    Every case here goes through ``_update_status`` — the same code path the Mac smoke test used —
    with stub widgets and a disposable SQLite file. "Writes nothing" is proved two ways: the stored
    row is re-read from disk and compared field by field, and ``save_tracker`` is patched to fail if
    it is ever called, so a refusal that secretly wrote would fail the test rather than pass quietly.
    """

    def setUp(self):
        super().setUp()
        self.store.save_job(sample_job())
        reach_status(self.store, ApplicationStatus.SUBMISSION_ATTEMPTED)

    def stored_row(self):
        """Read the row straight from the database file, bypassing the store's own connection."""
        connection = sqlite3.connect(self.store.database_path)
        try:
            row = connection.execute(
                "SELECT listing_id, status, status_evidence, candidate_confirmed, updated_at "
                "FROM application_tracker WHERE listing_id=?",
                ("j1",),
            ).fetchone()
        finally:
            connection.close()
        return row

    def assert_apply_is_refused_without_writing(self, app, apply):
        """Run the dialog's save command; require a refusal, no write, and an unchanged row."""
        before = self.stored_row()
        self.assertIsNotNone(before)
        with mock.patch.object(
            self.store, "save_tracker", side_effect=AssertionError("a refused change must not write")
        ):
            apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertNotIn("updated", app.status.get())
        self.assertEqual(self.stored_row(), before, "a refused change must leave the row byte-identical")

    def test_empty_evidence_is_refused_without_writing(self):
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("")
        assertion.set(True)
        self.assert_apply_is_refused_without_writing(app, apply)

    def test_whitespace_only_evidence_is_refused_without_writing(self):
        for text in (" ", "   ", "\t", "\n", " \t\n "):
            with self.subTest(text=text):
                MESSAGES.reset()
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
                status_var.set("confirmed")
                evidence_var.set(text)
                assertion.set(True)
                self.assert_apply_is_refused_without_writing(app, apply)

    def test_the_applications_own_instruction_text_is_refused_without_writing(self):
        """The reported smoke-test failure mode, through the dialog the tester actually used."""
        for text in (
            "A confirmed application requires evidence. An attempt or timeout is not proof.",
            "Confirmation requires evidence; a click or attempted submission is not proof.",
            "Evidence / note (required to confirm)",
            "Confirm with a meaningful evidence note, then move it to response_received or interview.",
            "To revise the evidence, move the status forward with a meaningful note, "
            "or keep the existing record as it is.",
        ):
            with self.subTest(text=text[:40]):
                MESSAGES.reset()
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
                status_var.set("confirmed")
                evidence_var.set(text)
                assertion.set(True)
                self.assert_apply_is_refused_without_writing(app, apply)

    def test_placeholder_and_template_evidence_are_refused_without_writing(self):
        for text in ("n/a", "N/A", "todo", "TBD", "test", "testing", "placeholder", "yes",
                     "evidence", "<your evidence here>"):
            with self.subTest(text=text):
                MESSAGES.reset()
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
                status_var.set("confirmed")
                evidence_var.set(text)
                assertion.set(True)
                self.assert_apply_is_refused_without_writing(app, apply)

    def test_confirmed_without_the_explicit_assertion_is_refused_without_writing(self):
        for evidence in ("Employer portal shows Application Received (2026-10-14)", "", "n/a"):
            with self.subTest(evidence=evidence[:30]):
                MESSAGES.reset()
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
                status_var.set("confirmed")
                evidence_var.set(evidence)
                self.assertFalse(assertion.get(), "the assertion must start unticked")
                self.assert_apply_is_refused_without_writing(app, apply)

    def test_the_assertion_is_refused_with_every_other_status(self):
        """The checkbox claims a confirmation, so it may only accompany the confirmation status."""
        for status in ("shortlisted", "prepared", "awaiting_user", "submission_attempted",
                       "submitted_unverified", "response_received", "withdrawn", "discovered"):
            with self.subTest(status=status):
                MESSAGES.reset()
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
                status_var.set(status)
                evidence_var.set("Note supplied with a wrongly ticked assertion")
                assertion.set(True)
                self.assert_apply_is_refused_without_writing(app, apply)

    def test_a_valid_note_with_the_assertion_completes_the_permitted_workflow(self):
        """Walk the whole permitted path; the flag may only appear at the confirmation step."""
        self.store.save_job(sample_job(listing_id="j2", source_listing_url="https://jobs.example/role/2"))
        steps = (
            ("shortlisted", False),
            ("prepared", False),
            ("awaiting_user", False),
            ("submission_attempted", False),
            ("submitted_unverified", False),
        )
        MESSAGES.reset()
        for status, expected_flag in steps:
            app, status_var, evidence_var, assertion, apply = self.open_status_dialog("j2")
            status_var.set(status)
            evidence_var.set(f"Moved to {status} while testing the workflow")
            apply()
            stored = self.store.get_tracker("j2")
            self.assertIs(stored.status, ApplicationStatus(status))
            self.assertIs(stored.candidate_confirmed, expected_flag)
            self.assertNotIn("Invalid status change", MESSAGES.titles())

        app, status_var, evidence_var, assertion, apply = self.open_status_dialog("j2")
        status_var.set("confirmed")
        evidence_var.set("Employer portal shows Application Received (2026-10-14)")
        assertion.set(True)
        apply()
        confirmed = self.store.get_tracker("j2")
        self.assertIs(confirmed.status, ApplicationStatus.CONFIRMED)
        self.assertEqual(confirmed.status_evidence, "Employer portal shows Application Received (2026-10-14)")
        self.assertTrue(confirmed.candidate_confirmed)

        # The assertion is not needed again: later statuses keep the existing confirmation.
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog("j2")
        status_var.set("response_received")
        evidence_var.set("Recruiter replied with a screening request")
        apply()
        advanced = self.store.get_tracker("j2")
        self.assertIs(advanced.status, ApplicationStatus.RESPONSE_RECEIVED)
        self.assertTrue(advanced.candidate_confirmed)

    def test_a_failed_validation_never_changes_the_stored_tracker(self):
        """Every refusal category, checked against the row on disk."""
        refusals = (
            ("confirmed", "", False),
            ("confirmed", "   ", False),
            ("confirmed", "Employer portal shows Application Received", False),
            ("confirmed", "A confirmed application requires evidence. An attempt or timeout is not proof.", True),
            ("confirmed", "todo", True),
            ("interview", "pretend invite", False),
            ("shortlisted", "wrong direction", True),
            ("", "no status selected", False),
        )
        for status, evidence, assertion_value in refusals:
            with self.subTest(status=status, evidence=evidence[:30], assertion=assertion_value):
                MESSAGES.reset()
                before = self.stored_row()
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
                status_var.set(status)
                evidence_var.set(evidence)
                assertion.set(assertion_value)
                self.assert_apply_is_refused_without_writing(app, apply)
                self.assertEqual(self.stored_row(), before)

    def test_a_withdrawn_record_cannot_transition_anywhere(self):
        """Withdrawal is terminal: nothing may move out of it, in the UI or in storage."""
        self.store.save_job(sample_job(listing_id="j2", source_listing_url="https://jobs.example/role/2"))
        reach_status(self.store, ApplicationStatus.SHORTLISTED, listing_id="j2")
        with CareerStore(self.store.database_path) as seeding:
            seeding.save_tracker(
                seeding.get_tracker("j2").transition(ApplicationStatus.WITHDRAWN, evidence="Candidate withdrew")
            )
        withdrawn = self.store.get_tracker("j2")
        self.assertIs(withdrawn.status, ApplicationStatus.WITHDRAWN)

        for target in (status.value for status in ApplicationStatus if status is not ApplicationStatus.WITHDRAWN):
            with self.subTest(target=target):
                MESSAGES.reset()
                app, status_var, evidence_var, assertion, apply = self.open_status_dialog("j2")
                status_var.set(target)
                evidence_var.set("attempt out of a terminal state")
                apply()
                self.assertIn("Invalid status change", MESSAGES.titles())
                self.assertEqual(self.store.get_tracker("j2"), withdrawn)
                self.assertEqual(self.store.get_tracker("j2").status_evidence, "Candidate withdrew")

    def test_reapplying_withdrawn_is_reported_as_a_no_op(self):
        self.store.save_job(sample_job(listing_id="j2", source_listing_url="https://jobs.example/role/2"))
        reach_status(self.store, ApplicationStatus.SHORTLISTED, listing_id="j2")
        with CareerStore(self.store.database_path) as seeding:
            seeding.save_tracker(
                seeding.get_tracker("j2").transition(ApplicationStatus.WITHDRAWN, evidence="Candidate withdrew")
            )
        before = self.store.get_tracker("j2")
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog("j2")
        status_var.set("withdrawn")
        evidence_var.set("replacement note that must not be stored")
        apply()
        self.assertIn("No change", MESSAGES.titles())
        self.assertNotIn("Invalid status change", MESSAGES.titles())
        self.assertIn("Nothing was saved", app.status.get())
        self.assertEqual(self.store.get_tracker("j2"), before)


class ShortlistEligibilityMessageTests(HandlerTestCase):
    """Locks the shortlist wording verified on macOS: unknown eligibility cannot be shortlisted."""

    def test_shortlist_reports_unknown_eligibility_and_changes_nothing(self):
        self.store.save_job(sample_job(availability_status=Availability.UNKNOWN))
        self.store.save_profile(PROFILE)
        app = self.make_app()
        app.selected_job_id = "j1"
        app._shortlist()
        self.assertIn("Not eligible to shortlist", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"), "a blocked shortlist must not create a record")

    def test_shortlist_reports_failed_eligibility_and_changes_nothing(self):
        self.store.save_job(sample_job(eligible_countries=("United States",)))
        self.store.save_profile(PROFILE)
        app = self.make_app()
        app.selected_job_id = "j1"
        app._shortlist()
        self.assertIn("Not eligible to shortlist", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"))


class ExportPrivacyTests(HandlerTestCase):
    """The JSON export holds profile facts and application history, so it must be owner-only.

    Every case runs through the real ``_export`` handler with the stubbed file dialog and a
    disposable temporary directory; the user's own database is never involved.
    """

    def setUp(self):
        super().setUp()
        self.store.save_job(sample_job())
        self.store.save_profile(PROFILE)
        reach_status(self.store, ApplicationStatus.CONFIRMED, evidence="Employer portal shows Application Received")
        self.destination = Path(self._directory.name) / "export.json"
        FILEDIALOG.path = str(self.destination)
        self.app = self.make_app(with_profile=True)

    def exported(self):
        return json.loads(self.destination.read_text(encoding="utf-8"))

    def test_export_is_owner_only_and_keeps_the_existing_format_and_workflow(self):
        self.app._export()

        self.assertTrue(self.destination.is_file())
        if os.name == "posix":
            self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)
        payload = self.exported()
        # Format and workflow are preserved: same keys, version, privacy note and content.
        self.assertEqual(payload["format_version"], 1)
        self.assertIn("privacy_note", payload)
        self.assertEqual(payload["profile"]["degree_discipline"], "ECE")
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(payload["jobs"][0]["application_tracker"]["status"], "confirmed")
        self.assertIn("Export complete", MESSAGES.titles())
        self.assertIn("Exported 1 jobs", self.app.status.get())

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_export_tightens_a_pre_existing_permissive_file(self):
        self.destination.write_text("older export", encoding="utf-8")
        os.chmod(self.destination, 0o644)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o644, "precondition")

        self.app._export()

        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.exported()["profile"]["degree_discipline"], "ECE")

    def test_export_refuses_a_symlink_destination_without_touching_its_target(self):
        victim = Path(self._directory.name) / "victim.txt"
        victim.write_text("ORIGINAL CONTENT THAT MUST SURVIVE", encoding="utf-8")
        link = Path(self._directory.name) / "link.json"
        try:
            os.symlink(victim, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links are unavailable here: {exc}")
        FILEDIALOG.path = str(link)

        self.app._export()

        self.assertIn("Export not saved", MESSAGES.titles())
        self.assertNotIn("Export complete", MESSAGES.titles())
        self.assertIn("not saved", self.app.status.get())
        self.assertEqual(victim.read_text(encoding="utf-8"), "ORIGINAL CONTENT THAT MUST SURVIVE")
        self.assertNotIn("ECE", victim.read_text(encoding="utf-8"))

    def test_export_reports_failure_and_leaves_no_readable_candidate_data(self):
        with mock.patch("career_agent.store.os.fchmod", side_effect=OSError("operation not permitted")):
            self.app._export()

        self.assertIn("Export not saved", MESSAGES.titles())
        self.assertNotIn("Export complete", MESSAGES.titles())
        self.assertIn("not saved", self.app.status.get())
        if self.destination.exists():
            self.assertNotIn("ECE", self.destination.read_text(encoding="utf-8"))

    def test_cancelling_the_dialog_writes_nothing_and_says_nothing(self):
        FILEDIALOG.path = ""
        self.app._export()
        self.assertFalse(self.destination.exists())
        self.assertEqual(MESSAGES.titles(), [])
        self.assertNotIn("Exported", self.app.status.get())

    def test_an_unwritable_destination_is_reported_without_claiming_success(self):
        FILEDIALOG.path = str(Path(self._directory.name) / "absent-folder" / "export.json")
        self.app._export()
        self.assertIn("Export not saved", MESSAGES.titles())
        self.assertNotIn("Exported", self.app.status.get())


class StaleSelectionTests(HandlerTestCase):
    """A selection that no longer resolves must be reported, not used. Reproduces audit H1."""

    def setUp(self):
        super().setUp()
        self.store.save_job(sample_job())
        self.store.save_profile(PROFILE)
        self.app = self.make_app(with_profile=True)
        # HandlerTestCase.make_app stubs these so other tests never execute them; this class
        # exists to exercise the real handlers, so the stubs are removed here.
        del self.app._evaluate, self.app._refresh_jobs, self.app._refresh_tracker

    def select_missing_listing(self, app, listing_id="gone-listing"):
        """Simulate a listing removed outside the view: selected id points at nothing stored."""
        app.selected_job_id = listing_id
        app.jobs_tree.selected = (listing_id,)
        return listing_id

    def test_evaluate_with_a_stale_selection_reports_instead_of_crashing(self):
        listing_id = self.select_missing_listing(self.app)
        self.app._evaluate()
        self.assertIn("Listing not found", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker(listing_id))
        self.assertIsNone(self.app.selected_job_id, "the stale selection must be cleared")

    def test_evaluate_with_a_stale_selection_performs_no_writes(self):
        self.select_missing_listing(self.app)
        with mock.patch.object(
            self.store, "save_tracker", side_effect=AssertionError("a stale selection must not write")
        ):
            self.app._evaluate()
        self.assertIn("Listing not found", MESSAGES.titles())

    def test_shortlist_with_a_stale_selection_reports_and_creates_no_record(self):
        listing_id = self.select_missing_listing(self.app)
        with mock.patch.object(
            self.store, "save_tracker", side_effect=AssertionError("a stale selection must not write")
        ):
            self.app._shortlist()
        self.assertIn("Listing not found", MESSAGES.titles())
        self.assertNotIn("Not eligible to shortlist", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker(listing_id))

    def test_shortlist_with_a_stale_selection_still_refuses_after_a_fresh_selection(self):
        """The stale guard must not leave the app in a state where a later click misbehaves."""
        self.select_missing_listing(self.app)
        self.app._shortlist()
        self.assertIsNone(self.app.selected_job_id)

        self.app.selected_job_id = "j1"
        self.app.jobs_tree.selected = ("j1",)
        self.app._shortlist()
        stored = self.store.get_tracker("j1")
        self.assertIsNotNone(stored)
        self.assertIs(stored.status, ApplicationStatus.SHORTLISTED)

    def test_evaluate_with_no_selection_asks_the_user_to_select(self):
        self.app.selected_job_id = None
        self.app.jobs_tree.selected = ()
        self.app._evaluate()
        self.assertIn("Select a job", MESSAGES.titles())
        self.assertEqual(self.store.list_jobs()[0].listing_id, "j1")

    def test_shortlist_with_no_selection_asks_the_user_to_select(self):
        self.app.selected_job_id = None
        self.app.jobs_tree.selected = ()
        self.app._shortlist()
        self.assertIn("Select a job", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"))

    def test_evaluate_reports_the_real_decision_and_evidence_lines(self):
        job = self.store.get_job("j1")
        expected = evaluate_eligibility(PROFILE, job)
        reports = []
        self.app._report = reports.append
        self.app.selected_job_id = "j1"

        self.app._evaluate()

        self.assertEqual(len(reports), 1)
        report = reports[0]
        self.assertIn(f"ELIGIBILITY: {expected.decision.value.upper()}", report)
        self.assertIn("Only explicit PASS is eligible. UNKNOWN is not eligible.", report)
        self.assertIn("Skill overlap:", report)
        for item in expected.requirements:
            self.assertIn(f"[{item.decision.value.upper()}] {item.requirement}:", report)
        self.assertEqual(self.app.status.get(), f"Eligibility for {job.role_title}: {expected.decision.value}.")

    def test_evaluate_keeps_an_unproven_listing_unknown(self):
        """The behaviour the user saw on macOS: no availability evidence means UNKNOWN."""
        self.store.save_job(sample_job(availability_status=Availability.UNKNOWN))
        reports = []
        self.app._report = reports.append
        self.app.selected_job_id = "j1"

        self.app._evaluate()

        self.assertIn("ELIGIBILITY: UNKNOWN", reports[0])

    def test_evaluate_without_a_profile_asks_for_one(self):
        store = CareerStore(str(Path(self._directory.name) / "no-profile.sqlite3"))
        self.addCleanup(store.close)
        store.save_job(sample_job())
        app = self.make_app()
        app.store = store
        app.selected_job_id = "j1"
        del app._evaluate  # remove the stub so the real handler runs

        app._evaluate()

        self.assertIn("Profile required", MESSAGES.titles())
        self.assertEqual(app.tabs.selected_tabs, [app.profile_tab], "the profile tab must be shown")

    def test_shortlist_still_blocks_unknown_and_fail_eligibility(self):
        for label, job in (
            ("unknown", sample_job(availability_status=Availability.UNKNOWN)),
            ("fail", sample_job(eligible_countries=("United States",))),
        ):
            with self.subTest(eligibility=label):
                directory = tempfile.TemporaryDirectory()
                self.addCleanup(directory.cleanup)
                store = CareerStore(str(Path(directory.name) / f"{label}.sqlite3"))
                self.addCleanup(store.close)
                store.save_job(job)
                store.save_profile(PROFILE)
                MESSAGES.reset()
                app = self.make_app()
                app.store = store
                app.selected_job_id = "j1"
                app._shortlist()
                self.assertIn("Not eligible to shortlist", MESSAGES.titles())
                self.assertIsNone(store.get_tracker("j1"), f"{label} eligibility must not create a record")

    def test_shortlist_creates_the_record_only_for_explicit_eligibility_pass(self):
        job = self.store.get_job("j1")
        self.assertIs(evaluate_eligibility(PROFILE, job).decision, Decision.PASS, "fixture precondition")
        self.app.selected_job_id = "j1"

        self.app._shortlist()

        stored = self.store.get_tracker("j1")
        self.assertIsNotNone(stored)
        self.assertIs(stored.status, ApplicationStatus.SHORTLISTED)
        self.assertFalse(stored.candidate_confirmed)

    def test_deleting_the_selected_job_clears_the_selection_and_its_tracker(self):
        reach_status(self.store, ApplicationStatus.SHORTLISTED)
        self.app.selected_job_id = "j1"
        CONFIG["Delete job"] = True

        self.app._delete_job()

        self.assertIsNone(self.app.selected_job_id)
        self.assertEqual(self.store.list_jobs(), ())
        self.assertIsNone(self.store.get_tracker("j1"), "the tracker record must cascade with the job")
        self.assertIn("deleted locally", self.app.status.get())

    def test_deleting_a_missing_job_is_reported_without_claiming_success(self):
        self.select_missing_listing(self.app)
        CONFIG["Delete job"] = True

        self.app._delete_job()

        self.assertIn("nothing was deleted", self.app.status.get())
        self.assertEqual(len(self.store.list_jobs()), 1)

    def test_delete_database_error_leaves_data_intact(self):
        CONFIG["Delete job"] = True
        self.app.selected_job_id = "j1"
        self.app.jobs_tree.selected = ("j1",)
        with mock.patch.object(self.store, "delete_job", side_effect=sqlite3.OperationalError("database is locked")):
            self.app._delete_job()
        self.assertIn("Job not deleted", MESSAGES.titles())
        self.assertIn("not deleted", self.app.status.get())
        self.assertEqual(len(self.store.list_jobs()), 1)

    def test_refresh_lists_rebuild_from_the_database(self):
        reach_status(self.store, ApplicationStatus.SHORTLISTED)
        self.app.jobs_tree.rows = ()
        self.app.tracker_tree.rows = ()

        self.app._refresh_jobs()

        self.assertIn("j1", self.app.jobs_tree.rows)
        self.assertIn("j1", self.app.tracker_tree.rows)
        shown = dict(self.app.tracker_tree.inserted)["j1"]
        self.assertEqual(shown[0], "Example Inc")
        self.assertEqual(shown[2], "shortlisted", "the tracker tab shows the stored status")

    def test_selecting_a_tracker_row_syncs_the_job_selection(self):
        self.app.jobs_tree.children = ("j1",)
        self.app.tracker_tree.selected = ("j1",)

        self.app._select_tracker()

        self.assertEqual(self.app.selected_job_id, "j1")
        self.assertEqual(self.app.jobs_tree.selected, ("j1",))


class ProfileAndDeletionTests(HandlerTestCase):
    def test_profile_saves_and_validation_failures_are_reported(self):
        app = self.make_app()
        app._save_profile()
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertIn("saved locally", app.status.get())

        app.profile_vars["graduation_year"].set("final year")
        app._save_profile()
        self.assertIn("Invalid profile", MESSAGES.titles())
        self.assertEqual(self.store.get_profile(), PROFILE)

    def test_profile_delete_reports_when_nothing_was_deleted(self):
        app = self.make_app()
        CONFIG["Delete profile"] = True
        app._delete_profile()
        self.assertIn("nothing was deleted", app.status.get())

    def test_job_delete_reports_when_nothing_was_deleted(self):
        app = self.make_app()
        app.selected_job_id = "missing-listing"
        CONFIG["Delete job"] = True
        app._delete_job()
        self.assertIn("nothing was deleted", app.status.get())

    def test_job_delete_removes_the_tracker_row_and_returns_to_new_mode(self):
        self.store.save_job(sample_job())
        reach_status(self.store, ApplicationStatus.SHORTLISTED)
        app = self.make_app()
        app.selected_job_id = "j1"
        CONFIG["Delete job"] = True
        app._delete_job()
        self.assertIsNone(self.store.get_job("j1"))
        self.assertIsNone(self.store.get_tracker("j1"))
        self.assertTrue(app.job_save_mode is desktop.JobSaveMode.NEW)
        self.assertIsNone(app.selected_job_id)

    def test_export_writes_a_local_json_file_with_a_privacy_warning(self):
        self.store.save_job(sample_job())
        self.store.save_profile(PROFILE)
        reach_status(self.store, ApplicationStatus.CONFIRMED, evidence="Employer email")
        destination = Path(self._directory.name) / "export.json"
        FILEDIALOG.path = str(destination)
        app = self.make_app()
        app._export()
        payload = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(payload["format_version"], 1)
        self.assertEqual(payload["profile"]["candidate_country"], "India")
        self.assertEqual(payload["jobs"][0]["application_tracker"]["status_evidence"], "Employer email")
        self.assertIn("personal information", payload["privacy_note"])
        self.assertIn("Export complete", MESSAGES.titles())


if __name__ == "__main__":
    unittest.main(verbosity=2)
