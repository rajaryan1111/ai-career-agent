"""Handler-level regression tests for career_agent.desktop.

Tkinter is not guaranteed to be installed in headless CI, so this module installs a
minimal stub for the widget classes and dialogs the handlers touch, then imports and
exercises the real desktop module against real SQLite files in a temporary directory.

These tests verify handler decisions, validation messages, and database-error
handling. They do not verify rendering, theming, layout, or macOS behaviour; the
manual smoke-test checklist in research/ is still required before GUI acceptance.
"""
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from career_agent import ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, JobListing
from career_agent.store import CareerStore


class StringVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


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
        self.selected = ()
        self.children = ()

    def selection(self):
        return self.selected

    def selection_set(self, selection):
        self.selected = tuple(selection)

    def selection_remove(self, selection):
        self.selected = ()

    def get_children(self):
        return self.children

    def insert(self, parent, index, iid=None, values=None):
        self.rows += (iid,)
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
_tkinter.BOTH = "both"
_tkinter.END = "end"
_tkinter.LEFT = "left"
_tkinter.W = "w"
_tkinter.X = "x"
_tkinter.filedialog = FILEDIALOG
_tkinter.messagebox = MESSAGES
_tkinter.ttk = types.SimpleNamespace(
    Frame=Widget, Label=Widget, Notebook=Widget, Combobox=Widget, Entry=Widget, Treeview=Tree,
    Button=BUTTONS.button,
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
        app.tabs = types.SimpleNamespace(select=lambda *args: None)
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
        """Run the real handler and return the dialog's variables plus its save button command."""
        app = self.make_app()
        app.tracker_tree.selected = (listing_id,)
        created = []
        original = desktop.tk.StringVar

        def recording_stringvar(*args, **kwargs):
            variable = original(*args, **kwargs)
            created.append(variable)
            return variable

        desktop.tk.StringVar = recording_stringvar
        self.addCleanup(setattr, desktop.tk, "StringVar", original)
        app._update_status()
        return app, created[0], created[1], BUTTONS.command


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
        app, status_var, evidence_var, apply = self.open_status_dialog()
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
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("shortlisted")
        apply()
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.SHORTLISTED)
        self.assertFalse(stored.candidate_confirmed)
        self.assertNotIn("Invalid status change", MESSAGES.titles())
        self.assertIn("updated to shortlisted", app.status.get())

    def test_invalid_initial_jump_creates_no_record(self):
        self.store.save_job(sample_job())
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("interview")
        evidence_var.set("pretend invite")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"))
        self.assertNotIn("updated", app.status.get())

    def test_invalid_initial_confirmed_creates_no_record(self):
        self.store.save_job(sample_job())
        app, status_var, evidence_var, apply = self.open_status_dialog()
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
                app, status_var, evidence_var, apply = self.open_status_dialog()
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
        app, status_var, evidence_var, apply = self.open_status_dialog()
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

        app, status_var, evidence_var, apply = self.open_status_dialog()
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
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("   ")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SUBMISSION_ATTEMPTED)

    def test_confirmation_with_evidence_is_saved(self):
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("Employer confirmation page shown")
        apply()
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.CONFIRMED)
        self.assertEqual(stored.status_evidence, "Employer confirmation page shown")
        self.assertIn("updated to confirmed", app.status.get())

    def test_no_op_transition_does_not_claim_success_and_keeps_the_old_evidence(self):
        advanced = self.store.get_tracker("j1").transition(
            ApplicationStatus.CONFIRMED, evidence="original evidence", candidate_confirmed=True
        )
        self.store.save_tracker(advanced)
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("replacement evidence that must not be stored")
        apply()
        self.assertIn("No change", MESSAGES.titles())
        self.assertNotIn("updated", app.status.get())
        self.assertIn("Nothing was saved", app.status.get())
        self.assertEqual(self.store.get_tracker("j1").status_evidence, "original evidence")

    def test_evidence_can_be_revised_by_moving_the_status_forward(self):
        _, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("Employer confirmation page shown")
        apply()
        MESSAGES.reset()
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("response_received")
        evidence_var.set("Employer replied with a screening request")
        apply()
        stored = self.store.get_tracker("j1")
        self.assertEqual(stored.status, ApplicationStatus.RESPONSE_RECEIVED)
        self.assertEqual(stored.status_evidence, "Employer replied with a screening request")
        self.assertTrue(stored.candidate_confirmed)

    def test_invalid_status_selection_is_reported(self):
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SUBMISSION_ATTEMPTED)

    def test_invalid_jump_is_reported(self):
        self.store.save_job(sample_job(listing_id="j2", source_listing_url="https://jobs.example/role/2"))
        self.store.save_tracker(ApplicationTracker("j2", ApplicationStatus.DISCOVERED))
        app, status_var, evidence_var, apply = self.open_status_dialog("j2")
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
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("interview")
        evidence_var.set("pretend invite")
        apply()
        self.assertIn("Invalid status change", MESSAGES.titles())
        after = self.store.get_tracker("j1")
        self.assertEqual(after, before)
        self.assertNotIn("updated", app.status.get())

    def test_database_error_is_reported_without_claiming_success(self):
        app, status_var, evidence_var, apply = self.open_status_dialog()
        status_var.set("confirmed")
        evidence_var.set("Employer confirmation page shown")
        with mock.patch.object(self.store, "save_tracker", side_effect=sqlite3.OperationalError("database is locked")):
            apply()
        self.assertIn("Status not saved", MESSAGES.titles())
        self.assertNotIn("updated", app.status.get())
        self.assertEqual(self.store.get_tracker("j1").status, ApplicationStatus.SUBMISSION_ATTEMPTED)


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
