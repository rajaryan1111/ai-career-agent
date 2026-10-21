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
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from xml.sax.saxutils import escape

from career_agent import (
    ApplicationStatus,
    ApplicationTracker,
    Availability,
    CandidateProfile,
    Decision,
    JobListing,
    evaluate_eligibility,
    is_allowed_tracker_transition,
    resume,
)
from career_agent.backup import BackupError, create_backup, validate_app_database
from career_agent.store import CareerStore, StoredRecordError, UnavailableStore

#: Fixed stamp so the pre-restore snapshot name in assertions does not depend on the clock.
RESTORE_STAMP = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


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


#: Options real Tk accepts for each widget class this module stubs. A stub refuses anything else, the
#: way Tk raises ``_tkinter.TclError: unknown option "-wraplength"``. Without this the stubs accepted
#: any keyword and a real crash (a wrapping option on ``ttk.Checkbutton``, which has none) survived a
#: green suite on every platform and only failed on macOS when the dialog was actually built.
TTK_FRAME_OPTIONS = frozenset({
    "borderwidth", "class", "cursor", "height", "padding", "relief", "style", "takefocus", "width",
})
TTK_LABEL_OPTIONS = frozenset({
    "anchor", "background", "class", "compound", "cursor", "font", "foreground", "image", "justify",
    "padding", "relief", "state", "style", "takefocus", "text", "textvariable", "underline", "width",
    "wraplength",
})
TTK_BUTTON_OPTIONS = frozenset({
    "class", "command", "compound", "cursor", "default", "image", "padding", "state", "style",
    "takefocus", "text", "textvariable", "underline", "width",
})
TTK_CHECKBUTTON_OPTIONS = frozenset({
    "class", "command", "compound", "cursor", "image", "offvalue", "onvalue", "padding", "state",
    "style", "takefocus", "text", "textvariable", "underline", "variable", "width",
})
TTK_SCROLLBAR_OPTIONS = frozenset({"class", "command", "cursor", "orient", "style", "takefocus"})
TTK_NOTEBOOK_OPTIONS = frozenset({"class", "cursor", "height", "padding", "style", "takefocus", "width"})
TTK_COMBOBOX_OPTIONS = frozenset({
    "class", "cursor", "exportselection", "font", "height", "invalidcommand", "justify", "postcommand",
    "state", "style", "takefocus", "textvariable", "validate", "validatecommand", "values", "width",
    "xscrollcommand",
})
TTK_ENTRY_OPTIONS = frozenset({
    "class", "cursor", "exportselection", "font", "invalidcommand", "justify", "show", "state",
    "style", "takefocus", "textvariable", "validate", "validatecommand", "width", "xscrollcommand",
})
TTK_TREEVIEW_OPTIONS = frozenset({
    "class", "columns", "cursor", "displaycolumns", "height", "padding", "selectmode", "show", "style",
    "takefocus", "xscrollcommand", "yscrollcommand",
})
CANVAS_OPTIONS = frozenset({
    "background", "bd", "bg", "borderwidth", "closeenough", "confine", "cursor", "height",
    "highlightbackground", "highlightcolor", "highlightthickness", "insertbackground", "relief",
    "scrollregion", "takefocus", "width", "xscrollcommand", "xscrollincrement", "yscrollcommand",
    "yscrollincrement",
})
TOPLEVEL_OPTIONS = frozenset({
    "background", "bd", "bg", "borderwidth", "class", "cursor", "height", "highlightbackground",
    "highlightcolor", "highlightthickness", "menu", "padx", "pady", "relief", "takefocus", "width",
})


class TclOptionError(Exception):
    """Stands in for the ``_tkinter.TclError`` real Tk raises for an option a widget does not have."""


class Widget:
    def __init__(self, *args, **kwargs):
        self.options = kwargs
        # The first positional argument is the parent widget in every real Tk constructor, so tests can
        # check where a widget was placed (inside the scrolling area, or in the fixed footer).
        self.master = args[0] if args else kwargs.get("master")
        self.destroyed = False

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

    def bind(self, sequence=None, func=None, add=None):
        # Real Tk keeps the handler per event sequence; recording it lets tests assert that the
        # keyboard paths (Escape to cancel, Return to save) are actually wired.
        self.bindings = getattr(self, "bindings", {})
        if sequence:
            self.bindings[sequence] = func
        return self

    def title(self, *args, **kwargs):
        self.title_text = args[0] if args else None
        return None

    def geometry(self, *args, **kwargs):
        self.requested_geometry = args[0] if args else None
        return None

    def minsize(self, *args, **kwargs):
        self.requested_minsize = args[:2]
        return None

    def protocol(self, handle=None, func=None, *args, **kwargs):
        # Real Tk runs this handler when the window is closed; recording it lets a test do the same.
        self.protocols = getattr(self, "protocols", {})
        if handle:
            self.protocols[handle] = func
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


class ValidatedWidget(Widget):
    """A stub that refuses options its real widget does not have (see ``TclOptionError``)."""

    allowed_options = frozenset()

    def __init__(self, *args, **kwargs):
        unknown = sorted(set(kwargs) - set(self.allowed_options) - {"master"})
        if unknown:
            listed = " ".join(f'-{name}' for name in unknown)
            raise TclOptionError(f"unknown option \"{listed}\"")
        super().__init__(*args, **kwargs)


class Frame(ValidatedWidget):
    allowed_options = TTK_FRAME_OPTIONS


class Notebook(ValidatedWidget):
    allowed_options = TTK_NOTEBOOK_OPTIONS


class Canvas(ValidatedWidget):
    """Canvas stand-in: keeps the scrolled child window and any scroll request a test caused."""

    allowed_options = CANVAS_OPTIONS
    created = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scrollregion = None
        self.window_widget = None
        self.window_anchor = None
        self.scroll_calls = []
        Canvas.created.append(self)

    def create_window(self, *args, **kwargs):
        self.window_widget = kwargs.get("window")
        self.window_anchor = kwargs.get("anchor")
        return "canvas-window-1"

    def bbox(self, *args, **kwargs):
        return (0, 0, 800, 1200)

    def configure(self, *args, **kwargs):
        if "scrollregion" in kwargs:
            self.scrollregion = kwargs["scrollregion"]
        return None

    def itemconfigure(self, *args, **kwargs):
        return None

    def yview(self, *args, **kwargs):
        return (0.0, 1.0)

    def yview_scroll(self, number, what=None):
        self.scroll_calls.append((number, what))


class Tree(ValidatedWidget):
    allowed_options = TTK_TREEVIEW_OPTIONS

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
        self.messages = []

    def reset(self):
        self.calls = []
        self.messages = []

    def _record(self, kind, title, message, answer=True):
        self.calls.append((title, answer, kind))
        self.messages.append((kind, title, message))
        return answer

    def text(self, kind=None):
        """Every message body recorded so far, for the given dialog kind when one is named."""
        return "\n".join(body for call_kind, _title, body in self.messages if kind is None or call_kind == kind)

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
    """Remembers button commands: the most recent one, one per label, and every button created."""

    def __init__(self):
        self.command = None
        self.by_text = {}
        self.created = []

    def clear(self):
        self.command = None
        self.by_text = {}
        self.created = []

    def button(self, *args, **kwargs):
        if kwargs.get("command"):
            self.command = kwargs["command"]
            if kwargs.get("text"):
                self.by_text[kwargs["text"]] = kwargs["command"]
        widget = ValidatedWidget.__new__(Button)
        Button.__init__(widget, *args, **kwargs)
        self.created.append(widget)
        return widget


class Button(ValidatedWidget):
    allowed_options = TTK_BUTTON_OPTIONS

    @property
    def text(self):
        return self.options.get("text", "")


class Entry(ValidatedWidget):
    allowed_options = TTK_ENTRY_OPTIONS


class FileDialog:
    """Stands in for tkinter.filedialog; both dialogs return the configured path ("" = cancelled)."""

    def __init__(self):
        self.path = ""
        self.opened = None

    def asksaveasfilename(self, **kwargs):
        return self.path

    def askopenfilename(self, **kwargs):
        self.opened = self.path
        return self.path


class RecordingScrollbar(ValidatedWidget):
    """Scrollbar stand-in that records the thumb positions it was asked to show."""

    allowed_options = TTK_SCROLLBAR_OPTIONS
    created = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positions = []
        RecordingScrollbar.created.append(self)

    def set(self, first, last):
        self.positions.append((first, last))


class RecordingCombobox(ValidatedWidget):
    """Combobox stand-in that keeps every instance, so a test can read the offered values."""

    allowed_options = TTK_COMBOBOX_OPTIONS
    created = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        RecordingCombobox.created.append(self)

    @property
    def offered(self):
        """The values this chooser offered, as a list of status strings."""
        return list(self.options.get("values") or ())


class RecordingCheckbutton(ValidatedWidget):
    """Checkbutton stand-in; keeps every instance so a test can read or set its variable."""

    allowed_options = TTK_CHECKBUTTON_OPTIONS
    created = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        RecordingCheckbutton.created.append(self)

    @property
    def variable(self):
        return self.options.get("variable")

    @property
    def text(self):
        return self.options.get("text", "")


class RecordingLabel(ValidatedWidget):
    """Label stand-in that keeps every instance, so a test can read what a dialog displayed."""

    allowed_options = TTK_LABEL_OPTIONS
    created = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        RecordingLabel.created.append(self)

    @property
    def text(self):
        return self.options.get("text", "")


class RecordingToplevel(ValidatedWidget):
    """Toplevel stand-in that keeps every dialog, so a test can read its bindings and size."""

    allowed_options = TOPLEVEL_OPTIONS
    created = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        RecordingToplevel.created.append(self)


CONFIG = {}
BUTTONS = ButtonRegistry()
MESSAGES = MessageRecorder()
FILEDIALOG = FileDialog()

_tkinter = types.ModuleType("tkinter")
_tkinter.Tk = Widget
_tkinter.Toplevel = Widget
_tkinter.Text = Widget  # a permissive stub: the text widget has a long option list of its own
_tkinter.Canvas = Canvas
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
    Frame=Frame, Label=RecordingLabel, Notebook=Notebook, Combobox=RecordingCombobox, Entry=Entry,
    Treeview=Tree, Checkbutton=RecordingCheckbutton, Scrollbar=RecordingScrollbar,
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
        RecordingCombobox.created = []
        RecordingCheckbutton.created = []
        RecordingLabel.created = []
        RecordingScrollbar.created = []
        RecordingToplevel.created = []
        Canvas.created = []
        FILEDIALOG.path = ""
        FILEDIALOG.opened = None

    def make_app(self, *, with_profile=False):
        """Build a real CareerAgentApp instance with stub widgets instead of a Tk root."""
        app = desktop.CareerAgentApp.__new__(desktop.CareerAgentApp)
        app.root = Widget()
        app.store = self.store
        self.addCleanup(self._close_store_the_handler_replaced, app)
        # The real __init__ resolves this before any handler runs, so the double must too.
        app.db_path = Path(self.store.database_path)
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
        app.data_tab = Widget()
        selected_tabs = []
        app.tabs = types.SimpleNamespace(select=lambda tab: selected_tabs.append(tab), selected_tabs=selected_tabs)
        app._refresh_jobs = lambda: None
        app._refresh_tracker = lambda: None
        app._evaluate = lambda: None
        app._report = lambda text: None
        app.job_vars = {key: StringVar(value) for key, value in job_form_values(sample_job()).items()}
        app.profile_vars = {key: StringVar(value) for key, value in profile_form_values(PROFILE).items()}
        app.notification_manager = desktop.NotificationManager()
        if with_profile:
            self.store.save_profile(PROFILE)
        return app

    def fill_job_form(self, app, values):
        for key, value in values.items():
            app.job_vars[key].set(value)

    def _close_store_the_handler_replaced(self, app):
        """Close a connection a handler opened in place of the fixture's own store.

        Restoring the database closes the fixture's connection and gives the app a new store. Closing
        only the fixture's store left that new connection to the garbage collector, which is exactly
        what raises ``ResourceWarning: unclosed database`` on the interpreters that report it, so
        whatever the app holds when the test ends is closed here. Closing is idempotent, so a store
        the handler left alone (or already closed) is unaffected.
        """
        store = getattr(app, "store", None)
        if store is not None and store is not self.store:
            store.close()

    def make_app_with_real_handlers(self, *names):
        """Build the double with the named handlers bound to the real methods.

        ``make_app`` replaces the refresh/report handlers with no-ops so most tests can ignore them;
        a test that inspects what a list actually rendered must bind the real method instead.
        """
        app = self.make_app()
        for name in names:
            if name in app.__dict__:
                delattr(app, name)
        return app

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
        # Phase 5 policy check blocks failed eligibility
        self.assertIn("Cannot shortlist", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"))


class WindowShutdownTests(HandlerTestCase):
    """Closing the window: the store is closed, the window is destroyed, nothing is written.

    These build the app through its real ``__init__`` against the stub widgets, so the
    ``WM_DELETE_WINDOW`` registration and the store the app owns are the real ones. Rendering and
    macOS behaviour are still only checked by the manual smoke-test checklist; what is checked here
    is what the application object does when the window manager tells it to close.
    """

    def build_app(self):
        """Construct the real application object with its own disposable database."""
        database = Path(self._directory.name) / "shutdown.sqlite3"
        root = Widget()
        app = desktop.CareerAgentApp(root, database_path=str(database))
        self.addCleanup(app.store.close)  # idempotent, so it is safe after a test already closed it
        return app, root, database

    def test_the_window_manager_close_handler_closes_the_store_and_destroys_the_window(self):
        app, root, _database = self.build_app()
        handler = root.protocols["WM_DELETE_WINDOW"]

        self.assertEqual(handler, app.close, "the window's close button must run the real close")
        handler()

        self.assertTrue(root.destroyed)
        with self.assertRaises(sqlite3.ProgrammingError):
            app.store.get_profile()

    def test_closing_the_window_does_not_save_unsaved_form_edits(self):
        app, _root, database = self.build_app()
        self.assertIsNone(app.store.get_profile())
        app.profile_vars["country"].set("Somewhere that was never saved")
        app.profile_vars["experience"].set("7")
        app.profile_vars["skills"].set("Python, RAG")

        app.close()

        reopened = CareerStore(str(database))
        self.addCleanup(reopened.close)
        self.assertIsNone(reopened.get_profile(), "closing must not write the form's unsaved values")

    def test_closing_the_window_is_not_an_application_action(self):
        """No dialog, status claim, or message may appear when the window closes."""
        app, _root, _database = self.build_app()

        app.close()

        self.assertEqual(MESSAGES.titles(), [])
        self.assertEqual(MESSAGES.titles("showerror"), [])


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

    def withdrawn_record(self, listing_id="j2"):
        """Store a withdrawn record for ``listing_id`` and return it."""
        self.store.save_job(sample_job(listing_id=listing_id, source_listing_url=f"https://jobs.example/role/{listing_id}"))
        reach_status(self.store, ApplicationStatus.SHORTLISTED, listing_id=listing_id)
        with CareerStore(self.store.database_path) as seeding:
            seeding.save_tracker(
                seeding.get_tracker(listing_id).transition(ApplicationStatus.WITHDRAWN, evidence="Candidate withdrew")
            )
        withdrawn = self.store.get_tracker(listing_id)
        self.assertIs(withdrawn.status, ApplicationStatus.WITHDRAWN)
        return withdrawn

    def test_a_withdrawn_record_is_offered_no_further_status(self):
        """Withdrawal is terminal, so the status chooser must not be able to request a move out of it.

        The refusal moved earlier than before: instead of letting the person pick an impossible
        target and rejecting it afterwards, the dialog is not offered at all for a terminal record.
        The row is still untouched, ``save_tracker`` is still never called, and the domain still
        refuses every forced transition — nothing about the safeguard was relaxed.
        """
        withdrawn = self.withdrawn_record()
        app = self.make_app()
        app.tracker_tree.selected = ("j2",)

        with mock.patch.object(
            self.store, "save_tracker", side_effect=AssertionError("a terminal record must not be written")
        ):
            app._update_status()

        self.assertIn("No further status", MESSAGES.titles())
        self.assertNotIn("Invalid status change", MESSAGES.titles())
        self.assertIn("Nothing was changed", MESSAGES.text("showinfo"))
        self.assertEqual(RecordingCombobox.created, [], "a terminal record must not get a status chooser")
        self.assertEqual(self.store.get_tracker("j2"), withdrawn)
        self.assertEqual(self.store.get_tracker("j2").status_evidence, "Candidate withdrew")

        # The domain refusal is unchanged and is what actually protects the record.
        for target in (status for status in ApplicationStatus if status is not ApplicationStatus.WITHDRAWN):
            with self.subTest(target=target.value):
                self.assertFalse(is_allowed_tracker_transition(ApplicationStatus.WITHDRAWN, target))
                with self.assertRaises(ValueError):
                    withdrawn.transition(target, evidence="attempt out of a terminal state")

    def test_a_terminal_record_keeps_its_note_and_is_never_rewritten(self):
        """A withdrawn record keeps its note, and the terminal record is never rewritten."""
        withdrawn = self.withdrawn_record()
        app = self.make_app()
        app.tracker_tree.selected = ("j2",)

        with mock.patch.object(
            self.store, "save_tracker", side_effect=AssertionError("a terminal record must not be written")
        ):
            app._update_status()

        stored = self.store.get_tracker("j2")
        self.assertEqual(stored, withdrawn)
        self.assertEqual(stored.status_evidence, "Candidate withdrew")

    def test_reapplying_the_current_status_is_still_reported_as_a_no_op(self):
        """Re-applying a status is an idempotent no-op whose supplied note is never stored."""
        self.store.save_job(sample_job(listing_id="j2", source_listing_url="https://jobs.example/role/2"))
        reach_status(self.store, ApplicationStatus.SHORTLISTED, listing_id="j2")
        before = self.store.get_tracker("j2")
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog("j2")
        status_var.set("shortlisted")
        evidence_var.set("replacement note that must not be stored")
        apply()
        self.assertIn("No change", MESSAGES.titles())
        self.assertNotIn("Invalid status change", MESSAGES.titles())
        self.assertIn("Nothing was saved", app.status.get())
        self.assertEqual(self.store.get_tracker("j2"), before)
        self.assertNotEqual(self.store.get_tracker("j2").status_evidence, "replacement note that must not be stored")


#: A permitted walk from ``discovered`` to each status, used to build records for the choice tests.
#: Every step is a transition the domain permits, so the fixtures are built the way the app builds
#: records instead of writing statuses straight into the table.
_STATUS_PATHS = {
    ApplicationStatus.DISCOVERED: (),
    ApplicationStatus.SHORTLISTED: (ApplicationStatus.SHORTLISTED,),
    ApplicationStatus.PREPARED: (ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED),
    ApplicationStatus.AWAITING_USER: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER),
    ApplicationStatus.SUBMISSION_ATTEMPTED: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED),
    ApplicationStatus.SUBMITTED_UNVERIFIED: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.SUBMITTED_UNVERIFIED),
    ApplicationStatus.CONFIRMED: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.CONFIRMED),
    ApplicationStatus.RESPONSE_RECEIVED: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.CONFIRMED, ApplicationStatus.RESPONSE_RECEIVED),
    ApplicationStatus.INTERVIEW: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.CONFIRMED,
        ApplicationStatus.RESPONSE_RECEIVED, ApplicationStatus.INTERVIEW),
    ApplicationStatus.REJECTED_BY_EMPLOYER: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.CONFIRMED,
        ApplicationStatus.REJECTED_BY_EMPLOYER),
    ApplicationStatus.UNKNOWN_STATUS: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.UNKNOWN_STATUS),
    ApplicationStatus.FAILED: (
        ApplicationStatus.SHORTLISTED, ApplicationStatus.PREPARED, ApplicationStatus.AWAITING_USER,
        ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.FAILED),
    ApplicationStatus.WITHDRAWN: (ApplicationStatus.SHORTLISTED, ApplicationStatus.WITHDRAWN),
}


def build_record_at(store, status, listing_id):
    """Store a listing whose tracker record reaches ``status`` through permitted transitions."""
    store.save_job(sample_job(listing_id=listing_id, source_listing_url=f"https://jobs.example/role/{listing_id}"))
    tracker = ApplicationTracker(listing_id)
    store.save_tracker(tracker)
    for step in _STATUS_PATHS[status]:
        tracker = tracker.transition(
            step,
            evidence="Employer confirmation email" if step is ApplicationStatus.CONFIRMED else None,
            candidate_confirmed=True if step is ApplicationStatus.CONFIRMED else None,
        )
        store.save_tracker(tracker)
    return tracker


class TrackerStatusChoiceTests(HandlerTestCase):
    """The dialog offers exactly the statuses the record may move to, and no others.

    The expected set is recomputed from ``is_allowed_tracker_transition`` — the rule the storage
    layer enforces — rather than from a second hand-written table, so the interface and the domain
    cannot drift apart without a test failing.
    """

    def run_status_handler(self, listing_id):
        """Run the real handler with recording widgets; return ``(app, offered values or None)``.

        ``None`` means no status chooser was created at all, which is what a terminal status gets.
        """
        app = self.make_app()
        app.tracker_tree.selected = (listing_id,)
        RecordingCombobox.created = []
        RecordingToplevel.created = []
        with mock.patch.object(desktop.ttk, "Combobox", RecordingCombobox), \
                mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._update_status()
        if not RecordingCombobox.created:
            return app, None
        self.assertEqual(len(RecordingCombobox.created), 1, "expected a single status chooser")
        return app, RecordingCombobox.created[0].offered

    def assert_offers_only_permitted_statuses(self, listing_id, current):
        """Require the choices (or the absence of choices) to match what the state machine permits."""
        permitted = {status.value for status in ApplicationStatus if is_allowed_tracker_transition(current, status)}
        app, offered = self.run_status_handler(listing_id)
        if len(permitted) == 1:  # a terminal status permits no move at all
            self.assertIsNone(offered, "a terminal record must not be offered a status chooser")
            self.assertIn("No further status", MESSAGES.titles())
            return None
        self.assertEqual(set(offered), permitted, "the chooser must offer exactly the permitted statuses")
        self.assertIn(current.value, offered, "re-applying the current status must stay possible")
        self.assertEqual(len(offered), len(set(offered)), "no option may be listed twice")
        return offered

    def test_a_record_without_a_tracker_row_offers_only_the_initial_status_and_its_moves(self):
        self.store.save_job(sample_job())
        offered = self.assert_offers_only_permitted_statuses("j1", ApplicationStatus.DISCOVERED)
        self.assertEqual(offered, ["discovered", "shortlisted", "withdrawn"])
        self.assertIsNone(self.store.get_tracker("j1"), "opening the dialog must not create a record")

    def test_every_stored_status_is_offered_only_its_permitted_moves(self):
        for index, status in enumerate(ApplicationStatus):
            listing_id = f"job-{index}"
            with self.subTest(status=status.value):
                build_record_at(self.store, status, listing_id)
                self.assert_offers_only_permitted_statuses(listing_id, status)

    def test_impossible_targets_are_never_offered(self):
        self.store.save_job(sample_job())
        _app, offered = self.run_status_handler("j1")
        for impossible in ("confirmed", "interview", "rejected_by_employer", "response_received",
                           "submission_attempted", "submitted_unverified", "unknown_status", "failed",
                           "awaiting_user", "prepared"):
            self.assertNotIn(impossible, offered, f"{impossible} cannot be applied to this record")

    def test_a_confirmed_record_may_still_be_offered_its_recorded_next_steps(self):
        build_record_at(self.store, ApplicationStatus.CONFIRMED, "j1")
        offered = self.assert_offers_only_permitted_statuses("j1", ApplicationStatus.CONFIRMED)
        self.assertIsNotNone(offered)
        self.assertIn("interview", offered)
        self.assertIn("withdrawn", offered)
        self.assertEqual(offered.count("confirmed"), 1, "an option must not be listed twice")

    def test_the_dialog_offers_keyboard_dismissal_and_saving(self):
        self.store.save_job(sample_job())
        self.run_status_handler("j1")

        dialog = RecordingToplevel.created[0]
        self.assertIn("<Escape>", dialog.bindings, "the dialog must be cancellable from the keyboard")
        self.assertIn("<Return>", dialog.bindings, "the dialog must be confirmable from the keyboard")
        self.assertTrue(callable(dialog.bindings["<Escape>"]))
        self.assertTrue(callable(dialog.bindings["<Return>"]))

    def test_an_unexpected_failure_never_reports_success(self):
        self.store.save_job(sample_job())
        app, status_var, evidence_var, assertion, apply = self.open_status_dialog()
        status_var.set("shortlisted")
        with mock.patch.object(self.store, "save_tracker", side_effect=RuntimeError("disk on fire")):
            apply()

        self.assertIn("Status not saved", MESSAGES.titles())
        self.assertNotIn("updated", app.status.get())
        self.assertIn("nothing was saved", MESSAGES.text("showerror").lower())
        self.assertIsNone(self.store.get_tracker("j1"), "a failed write must not create a record")


class UnrecognisedStoredStatusTests(HandlerTestCase):
    """A stored status this version does not know is surfaced honestly and never rewritten.

    The row is written with the standard library, which is what a database from another build or an
    older version looks like from here. Every case checks that reading it cannot break a view and
    that nothing about it is silently repaired, reinterpreted, or discarded.
    """

    def store_legacy_status(self, value="ghost_status", listing_id="j1"):
        """Store a listing with a status string this build does not recognise."""
        self.store.save_job(sample_job(listing_id=listing_id, source_listing_url=f"https://jobs.example/role/{listing_id}"))
        reach_status(self.store, ApplicationStatus.SHORTLISTED, listing_id=listing_id)
        connection = sqlite3.connect(self.store.database_path)
        try:
            with connection:
                connection.execute(
                    "UPDATE application_tracker SET status=? WHERE listing_id=?", (value, listing_id)
                )
        finally:
            connection.close()

    def stored_status(self, listing_id="j1"):
        connection = sqlite3.connect(self.store.database_path)
        try:
            return connection.execute(
                "SELECT status, status_evidence, candidate_confirmed FROM application_tracker WHERE listing_id=?",
                (listing_id,),
            ).fetchone()
        finally:
            connection.close()

    def test_both_lists_render_the_stored_value_without_crashing(self):
        self.store_legacy_status()
        app = self.make_app_with_real_handlers("_refresh_jobs", "_refresh_tracker")

        app._refresh_jobs()
        app._refresh_tracker()

        jobs_row = dict(zip(("employer", "role", "availability", "status", "source", "observed"),
                            app.jobs_tree.inserted[-1][1]))
        self.assertIn("ghost_status", jobs_row["status"])
        self.assertIn("not recognised", jobs_row["status"])
        tracker_row = dict(zip(("employer", "role", "status", "saved", "evidence"),
                               app.tracker_tree.inserted[-1][1]))
        self.assertIn("ghost_status", tracker_row["status"])
        self.assertEqual(self.stored_status()[0], "ghost_status", "rendering must not rewrite the row")

    def test_the_status_dialog_refuses_and_explains_instead_of_guessing(self):
        self.store_legacy_status()
        app = self.make_app()
        app.tracker_tree.selected = ("j1",)
        before = self.stored_status()

        with mock.patch.object(
            self.store, "save_tracker", side_effect=AssertionError("an unknown status must not be written")
        ), mock.patch.object(desktop.ttk, "Combobox", RecordingCombobox):
            app._update_status()

        self.assertIn("Status not recognised", MESSAGES.titles())
        self.assertIn("ghost_status", MESSAGES.text("showerror"))
        self.assertEqual(RecordingCombobox.created, [], "no chooser may be offered from an unknown state")
        self.assertEqual(self.stored_status(), before)

    def test_saving_a_listing_leaves_an_unrecognised_status_alone(self):
        self.store_legacy_status()
        app = self.make_app()
        app.jobs_tree.selected = ("j1",)
        app._select_job()
        self.fill_job_form(app, {**job_form_values(sample_job()), "location": "Pune"})

        app._save_job()

        self.assertIn("Pune", self.store.get_job("j1").location_text, "the listing edit must still save")
        self.assertEqual(self.stored_status()[0], "ghost_status")
        self.assertNotIn("Cannot save job", MESSAGES.titles())

    def test_shortlisting_is_refused_from_an_unrecognised_status(self):
        self.store_legacy_status()
        self.store.save_profile(PROFILE)
        app = self.make_app()
        app.selected_job_id = "j1"
        before = self.stored_status()

        app._shortlist()

        self.assertIn("Cannot shortlist", MESSAGES.titles())
        self.assertEqual(self.stored_status(), before)

    def test_the_export_carries_the_value_verbatim_and_marks_it(self):
        self.store_legacy_status()
        destination = Path(self._directory.name) / "export-legacy.json"
        FILEDIALOG.path = str(destination)
        app = self.make_app()

        app._export()

        payload = json.loads(destination.read_text(encoding="utf-8"))
        tracker = payload["jobs"][0]["application_tracker"]
        self.assertEqual(tracker["status"], "ghost_status")
        self.assertIs(tracker["status_recognised"], False)
        self.assertEqual(tracker["status_evidence"], self.stored_status()[1])

    def test_a_recognised_export_is_unchanged_by_the_marker(self):
        self.store.save_job(sample_job())
        reach_status(self.store, ApplicationStatus.SHORTLISTED)
        destination = Path(self._directory.name) / "export-known.json"
        FILEDIALOG.path = str(destination)
        app = self.make_app()

        app._export()

        tracker = json.loads(destination.read_text(encoding="utf-8"))["jobs"][0]["application_tracker"]
        self.assertEqual(tracker["status"], "shortlisted")
        self.assertNotIn("status_recognised", tracker)


class LocalRecordTimeDisplayTests(HandlerTestCase):
    """Lists and the detail pane show real stored times, never presented as source dates."""

    def test_the_detail_report_labels_local_times_and_reports_missing_source_dates(self):
        self.store.save_job(sample_job(), observed_at="2026-10-14T09:15:00+00:00")
        app = self.make_app()
        reports = []
        app._report = reports.append
        app.jobs_tree.selected = ("j1",)

        app._select_job()

        text = reports[-1]
        self.assertIn("Local record times", text)
        self.assertIn("first noted 2026-10-14 09:15:00 UTC", text)
        self.assertIn("last saved 2026-10-14 09:15:00 UTC", text)
        self.assertIn("Source publication or update date: not provided", text)

    def test_a_later_save_moves_the_last_time_shown_and_keeps_the_first(self):
        self.store.save_job(sample_job(), observed_at="2026-10-14T09:15:00+00:00")
        self.store.save_job(sample_job(), observed_at="2026-10-15T11:45:00+00:00")
        app = self.make_app()
        reports = []
        app._report = reports.append
        app.jobs_tree.selected = ("j1",)

        app._select_job()

        text = reports[-1]
        self.assertIn("first noted 2026-10-14 09:15:00 UTC", text)
        self.assertIn("last saved 2026-10-15 11:45:00 UTC", text)

    def test_the_jobs_list_shows_the_last_time_this_app_saved_the_record(self):
        self.store.save_job(sample_job(), observed_at="2026-10-14T09:15:00+00:00")
        app = self.make_app_with_real_handlers("_refresh_jobs", "_refresh_tracker")

        app._refresh_jobs()

        row = dict(zip(("employer", "role", "availability", "status", "source", "observed"),
                       app.jobs_tree.inserted[-1][1]))
        self.assertEqual(row["observed"], "2026-10-14 09:15:00 UTC")

    def test_the_tracker_list_shows_when_the_status_was_last_saved_locally(self):
        from datetime import datetime, timezone
        build_record_at(self.store, ApplicationStatus.SHORTLISTED, "j1")
        app = self.make_app_with_real_handlers("_refresh_jobs", "_refresh_tracker")

        app._refresh_tracker()

        row = dict(zip(("employer", "role", "status", "saved", "evidence"),
                       app.tracker_tree.inserted[-1][1]))
        self.assertEqual(row["status"], "shortlisted")
        parsed = datetime.fromisoformat(row["saved"].replace(" UTC", "+00:00"))
        self.assertLess(abs((parsed - datetime.now(timezone.utc)).total_seconds()), 120)

    def test_a_listing_without_a_tracker_record_shows_no_status_time(self):
        self.store.save_job(sample_job())
        app = self.make_app_with_real_handlers("_refresh_jobs", "_refresh_tracker")

        app._refresh_tracker()
        row = dict(zip(("employer", "role", "status", "saved", "evidence"), app.tracker_tree.inserted[-1][1]))
        self.assertEqual(row["status"], "discovered")
        self.assertEqual(row["saved"], "not recorded")

    def test_an_unusable_stored_timestamp_is_labelled_and_breaks_nothing(self):
        self.store.save_job(sample_job())
        connection = sqlite3.connect(self.store.database_path)
        try:
            with connection:
                connection.execute("UPDATE job_listings SET last_seen_at='whenever' WHERE listing_id='j1'")
        finally:
            connection.close()
        app = self.make_app_with_real_handlers("_refresh_jobs", "_refresh_tracker")

        app._refresh_jobs()

        row = dict(zip(("employer", "role", "availability", "status", "source", "observed"),
                       app.jobs_tree.inserted[-1][1]))
        self.assertEqual(row["observed"], "whenever (unrecognised timestamp format)")


class ShortlistEligibilityMessageTests(HandlerTestCase):
    """Locks the shortlist wording verified on macOS: unknown eligibility cannot be shortlisted."""

    def test_shortlist_reports_unknown_eligibility_and_changes_nothing(self):
        self.store.save_job(sample_job(availability_status=Availability.UNKNOWN))
        self.store.save_profile(PROFILE)
        app = self.make_app()
        app.selected_job_id = "j1"
        app._shortlist()
        # Phase 5 policy check blocks unknown eligibility
        self.assertIn("Cannot shortlist", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"), "a blocked shortlist must not create a record")

    def test_shortlist_reports_failed_eligibility_and_changes_nothing(self):
        self.store.save_job(sample_job(eligible_countries=("United States",)))
        self.store.save_profile(PROFILE)
        app = self.make_app()
        app.selected_job_id = "j1"
        app._shortlist()
        # Phase 5 policy check blocks failed eligibility
        self.assertIn("Cannot shortlist", MESSAGES.titles())
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

        self.assertEqual(len(reports), 2)  # Main eligibility report + follow-up reminder
        report = reports[0]
        # Phase 5 integration: output now includes strategy recommendation, inferred/missing facts, and policy check
        self.assertIn("ELIGIBILITY: PASS", report)
        self.assertIn("Recommendation: strong_pass", report)
        self.assertIn("Confidence: medium", report)
        self.assertIn("Verification required: False", report)
        self.assertIn("Inferred facts:", report)
        self.assertIn("Missing requirements:", report)
        self.assertIn("Overall: pass", report)
        self.assertIn("Recommendations:", report)
        self.assertIn("Policy: conditional", report)
        self.assertIn("requires explicit user authorization", report)
        # Old format check preserved for backward compatibility reference
        self.assertIn("Skill overlap:", report)
        # Second report is the follow-up reminder
        self.assertIn("Follow-up reminder:", reports[1])
        # Status line preserved
        self.assertEqual(self.app.status.get(), f"Eligibility for {job.role_title}: pass (strong_pass).")

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
                # Phase 5 policy check now provides more detailed messaging
                self.assertIn("Cannot shortlist", MESSAGES.titles())
                # The policy check blocks unknown/fail eligibility
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


class DatabaseBackupHandlerTests(HandlerTestCase):
    """The Data safety tab: a backup is verified, owner-only and never overwrites anything.

    These run the real handlers with the stubbed dialogs against disposable databases. They verify
    handler decisions and messages, not widget rendering or macOS behaviour.
    """

    def setUp(self):
        super().setUp()
        self.store.save_profile(PROFILE)
        self.store.save_job(sample_job())
        self.destination = Path(self._directory.name) / "backup.sqlite3"
        FILEDIALOG.path = str(self.destination)
        self.app = self.make_app(with_profile=True)

    def test_backup_writes_a_verified_owner_only_copy_and_reports_it(self):
        self.app._backup_database()

        self.assertTrue(self.destination.is_file())
        if os.name == "posix":
            self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)
        info = validate_app_database(self.destination)
        self.assertEqual((info.job_count, info.tracker_count, info.profile_present), (1, 0, True))
        self.assertIn("Backup verified", MESSAGES.titles())
        self.assertIn("Backup verified", self.app.status.get())

    def test_backup_is_cancelled_without_writing_anything(self):
        FILEDIALOG.path = ""  # the user closed the save dialog

        self.app._backup_database()

        self.assertEqual([path.name for path in Path(self._directory.name).iterdir()], ["handlers.sqlite3"])
        self.assertEqual(MESSAGES.calls, [])
        self.assertIn("cancelled", self.app.status.get())

    def test_backup_refuses_an_existing_file_and_leaves_it_alone(self):
        self.destination.write_text("an older backup the user still needs", encoding="utf-8")

        self.app._backup_database()

        self.assertIn("Backup not created", MESSAGES.titles())
        self.assertEqual(self.destination.read_text(encoding="utf-8"), "an older backup the user still needs")

    def test_backup_refuses_a_symbolic_link_destination(self):
        victim = Path(self._directory.name) / "victim.txt"
        victim.write_text("must survive", encoding="utf-8")
        try:
            FILEDIALOG.path = str(victim)
            link = Path(self._directory.name) / "link.sqlite3"
            os.symlink(victim, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symbolic links are unavailable here: {exc}")
        FILEDIALOG.path = str(link)

        self.app._backup_database()

        self.assertIn("Backup not created", MESSAGES.titles())
        self.assertEqual(victim.read_text(encoding="utf-8"), "must survive")

    def test_a_backup_that_cannot_be_made_is_reported_and_claims_no_success(self):
        FILEDIALOG.path = str(Path(self._directory.name) / "absent" / "backup.sqlite3")

        self.app._backup_database()

        self.assertIn("Backup not created", MESSAGES.titles())
        self.assertNotIn("Backup verified", MESSAGES.titles())
        self.assertIn("nothing was written", self.app.status.get())


class DatabaseRestoreHandlerTests(HandlerTestCase):
    """Restoring replaces candidate data, so it must confirm, validate and reopen deliberately."""

    def setUp(self):
        super().setUp()
        self.store.save_profile(PROFILE)
        self.store.save_job(sample_job(listing_id="j1"))
        self.chosen = Path(self._directory.name) / "chosen-backup.sqlite3"
        create_backup(Path(self.store.database_path), self.chosen, timestamp=RESTORE_STAMP)
        self.store.save_job(sample_job(listing_id="j2"))
        self.store.save_job(sample_job(listing_id="j3"))
        FILEDIALOG.path = str(self.chosen)
        self.app = self.make_app(with_profile=True)

    def listing_ids(self):
        with CareerStore(self.app.db_path) as store:
            return [job.listing_id for job in store.list_jobs()]

    def test_cancelling_the_file_dialog_changes_nothing(self):
        FILEDIALOG.path = ""

        self.app._restore_database()

        self.assertEqual(self.listing_ids(), ["j1", "j2", "j3"])
        self.assertEqual(MESSAGES.calls, [])
        self.assertIn("cancelled", self.app.status.get())

    def test_cancelling_the_confirmation_changes_nothing_and_keeps_the_connection_open(self):
        CONFIG["Replace the local database?"] = False

        self.app._restore_database()

        self.assertEqual(self.listing_ids(), ["j1", "j2", "j3"])
        self.assertNotIn("Restore complete", MESSAGES.titles())
        self.assertIs(self.app.store, self.store, "a cancelled restore must not close the connection")
        self.assertEqual(self.store.list_jobs()[0].listing_id, "j1", "the existing connection still works")

    def test_an_incompatible_file_is_refused_before_the_confirmation_is_even_asked(self):
        corrupt = Path(self._directory.name) / "corrupt.sqlite3"
        corrupt.write_text("not a database", encoding="utf-8")
        FILEDIALOG.path = str(corrupt)

        self.app._restore_database()

        self.assertIn("Backup cannot be used", MESSAGES.titles())
        self.assertNotIn("Replace the local database?", MESSAGES.titles())
        self.assertEqual(self.listing_ids(), ["j1", "j2", "j3"])

    def test_confirming_restores_the_data_reopens_the_database_and_reports_it(self):
        self.app._restore_database()

        self.assertEqual(self.listing_ids(), ["j1"])
        self.assertIsNot(self.app.store, self.store, "the app must reconnect to the restored file")
        self.assertEqual([job.listing_id for job in self.app.store.list_jobs()], ["j1"])
        self.assertIn("Restore complete", MESSAGES.titles())
        self.assertIn("Restored from", self.app.status.get())
        # The handler uses the clock, so find the copy it made rather than assuming its name.
        previous = sorted(Path(self._directory.name).glob(f"{Path(self.app.db_path).name}.backup-*"))
        self.assertEqual(len(previous), 1, "exactly one previous-database copy must be kept")
        self.assertEqual(validate_app_database(previous[0]).job_count, 3, "the copy must hold what was replaced")

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_the_restored_database_is_owner_only(self):
        self.app._restore_database()

        self.assertEqual(Path(self.app.db_path).stat().st_mode & 0o777, 0o600)

    def test_a_failed_restore_reopens_the_database_and_says_so(self):
        with mock.patch("career_agent.desktop.restore_backup", side_effect=BackupError("simulated failure")):
            self.app._restore_database()

        self.assertIn("Restore failed", MESSAGES.titles())
        self.assertNotIn("Restore complete", MESSAGES.titles())
        self.assertEqual(self.listing_ids(), ["j1", "j2", "j3"], "the data must be what it was")
        self.assertEqual([job.listing_id for job in self.app.store.list_jobs()], ["j1", "j2", "j3"])
        self.assertIn("Restore failed", self.app.status.get())

    def test_the_fixture_closes_the_store_a_restore_gave_the_app(self):
        """A restore replaces the app's store, and that replacement must be closed, not collected.

        Closing only the fixture's own store left the new connection to the garbage collector: that
        is the ``ResourceWarning: unclosed database`` reported from macOS, and it also kept the
        database file open for an unpredictable time on every platform.
        """
        self.app._restore_database()
        replacement = self.app.store
        self.assertIsNot(replacement, self.store, "the handler must have opened a new connection")

        self._close_store_the_handler_replaced(self.app)

        with self.assertRaises(sqlite3.ProgrammingError):
            replacement.list_jobs()  # SQLite refuses to work on a closed connection

    def test_a_restore_whose_database_cannot_be_reopened_is_not_reported_as_complete(self):
        """A restore that replaced the file but cannot be used must not claim success.

        Reproduced before this test existed: the app reported ``Restore complete``, kept the status
        line ``Restored from ...``, and left the *closed* connection as its store, so the next action
        raised ``ProgrammingError: Cannot operate on a closed database`` out of a Tk callback.
        """
        with mock.patch.object(desktop, "CareerStore", side_effect=sqlite3.OperationalError("simulated refusal")):
            self.app._restore_database()

        self.assertNotIn("Restore complete", MESSAGES.titles(), "a failed reopen is not a completed restore")
        self.assertIn("Database unavailable", MESSAGES.titles())
        self.assertTrue(any("cannot be opened" in title for title in MESSAGES.titles()),
                        f"no dialog said the restored database could not be opened: {MESSAGES.titles()}")
        error_text = MESSAGES.text("showerror")
        self.assertIn("nothing in this window can read or write candidate data", error_text)
        self.assertIn(str(self.chosen), MESSAGES.text("showinfo") + MESSAGES.text("showerror"))
        self.assertNotIn("Restored from", self.app.status.get())
        self.assertIn("could not be opened", self.app.status.get())
        self.assertIn("Restart", self.app.status.get())
        # The file was really replaced; only the connection failed. The backup of the old database is
        # named in the message so the person can find it.
        self.assertEqual(self.listing_ids(), ["j1"])
        self.assertIn("preserved at", MESSAGES.text("showerror"))

    def test_the_store_a_failed_reopen_installed_refuses_clearly_instead_of_raising(self):
        """The window must stay usable enough to explain itself, and ``close()`` must still be safe."""
        with mock.patch.object(desktop, "CareerStore", side_effect=sqlite3.OperationalError("simulated refusal")):
            self.app._restore_database()

        self.assertIsInstance(self.app.store, UnavailableStore)
        for handler in ("_refresh_jobs", "_refresh_tracker", "_select_job", "_evaluate", "_load_profile"):
            self.app.__dict__.pop(handler, None)  # bind the real handler, not the fixture's no-op
        export_target = Path(self._directory.name) / "export.json"
        FILEDIALOG.path = str(export_target)
        for handler in ("_refresh_jobs", "_refresh_tracker", "_select_job", "_evaluate", "_load_profile", "_export"):
            with self.subTest(handler=handler):
                MESSAGES.reset()
                self.app.status.set("")
                getattr(self.app, handler)()
        self.assertIn("could not be read", self.app.status.get())
        self.assertIn("Local database unavailable", MESSAGES.titles())
        self.assertFalse(export_target.exists(), "an export from an unusable database must write nothing")
        self.app.close()  # must not raise: the guard object has no connection to close

    def test_a_refresh_after_a_failed_reopen_reports_instead_of_raising_a_raw_sqlite_error(self):
        """The concrete defect: a Tk callback must never surface ``ProgrammingError`` to the user."""
        with mock.patch.object(desktop, "CareerStore", side_effect=sqlite3.OperationalError("simulated refusal")):
            self.app._restore_database()

        app = self.app
        app.__dict__.pop("_refresh_jobs", None)
        app.tracker_tree.selected = ()

        app._refresh_jobs()  # the real handler, which must handle the failure itself

        self.assertIn("Local database unavailable", MESSAGES.titles())
        self.assertIn("nothing was changed", self.app.status.get())

    def test_a_failed_restore_that_leaves_nothing_open_says_the_app_must_be_restarted(self):
        with mock.patch("career_agent.desktop.restore_backup", side_effect=BackupError("simulated failure")), \
                mock.patch.object(desktop, "CareerStore", side_effect=sqlite3.OperationalError("simulated refusal")):
            self.app._restore_database()

        self.assertIn("Restore failed", MESSAGES.titles())
        self.assertNotIn("Restore complete", MESSAGES.titles())
        self.assertIn("could not reopen", MESSAGES.text("showerror"))
        self.assertIn("Restart the app", self.app.status.get())
        self.assertIsInstance(self.app.store, UnavailableStore)
        for handler in ("_refresh_jobs", "_refresh_tracker", "_evaluate", "_load_profile"):
            self.app.__dict__.pop(handler, None)
        for handler in ("_refresh_jobs", "_refresh_tracker", "_evaluate", "_load_profile"):
            with self.subTest(handler=handler):
                getattr(self.app, handler)()  # must not raise

    def test_a_backup_with_dangling_tracker_rows_is_reported_in_the_confirmation(self):
        foreign = Path(self._directory.name) / "dangling.sqlite3"
        create_backup(Path(self.store.database_path), foreign, timestamp=RESTORE_STAMP)
        connection = sqlite3.connect(str(foreign))
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("INSERT INTO application_tracker VALUES ('missing', 'discovered', NULL, 0, '2026-01-01')")
        connection.commit()
        connection.close()
        FILEDIALOG.path = str(foreign)
        CONFIG["Replace the local database?"] = False

        self.app._restore_database()

        self.assertIn("Replace the local database?", MESSAGES.titles())


DOCX_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_paragraph(text):
    """One paragraph of a synthetic DOCX body."""
    return f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"


def docx_table(rows):
    """One table of a synthetic DOCX body; each row is a sequence of cell strings."""
    body = "".join(
        "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{escape(cell)}</w:t></w:r></w:p></w:tc>" for cell in row) + "</w:tr>"
        for row in rows
    )
    return f"<w:tbl>{body}</w:tbl>"


def mark_zip_members_encrypted(data: bytes) -> bytes:
    """Set ZIP's encryption flag on every entry header, as a password-protected re-save looks."""
    patched = bytearray(data)
    for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        position = patched.find(signature)
        while position != -1:
            patched[position + offset:position + offset + 2] = (0x1).to_bytes(2, "little")
            position = patched.find(signature, position + 4)
    return bytes(patched)


def write_resume_docx(path, *, paragraphs=(), tables=()):
    """Write a minimal but structurally real DOCX; standard library only, synthetic content."""
    body = "".join(docx_paragraph(text) for text in paragraphs)
    body += "".join(docx_table(rows) for rows in tables)
    document = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        f'<w:document xmlns:w="{DOCX_NAMESPACE}"><w:body>{body}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", document)
    return Path(path)


#: A fictional candidate. Nothing in these fixtures belongs to a real person.
RESUME_LINES = (
    "Ada Placeholder",
    "ada.placeholder@example.invalid | +91 00000 00000 | Bengaluru",
    "Skills",
    "Python, SQL, Machine Learning",
    "Education",
    "B.Tech in Electronics and Communication Engineering, Example Institute of Technology, 2028",
)

#: Stands in for arbitrary prose from a document: it must never reach a message, the status line,
#: a dialog, or the database. A fragment of it is what the tests search for.
LONG_PROSE = (
    "This paragraph is a long unique marker standing in for arbitrary sentences from the document, "
    "and this application must not copy it into a message, a status line or the database."
)
PROSE_FRAGMENT = "long unique marker standing in"


class ResumeImportHandlerTests(HandlerTestCase):
    """The review screen is the only route from a document to the profile, and it saves nothing first.

    The fixtures are synthetic DOCX files built in the test process. They exercise the real handler,
    the real parser and a real SQLite file; they do not verify rendering, and the manual checklist in
    research/ is still what covers the GUI itself.
    """

    def write_docx(self, name="ada-resume.docx", *, paragraphs=RESUME_LINES, tables=()):
        return write_resume_docx(Path(self._directory.name) / name, paragraphs=paragraphs, tables=tables)

    def import_resume(self, path, app=None):
        """Run the real import handler for the chosen file and return the app and the review dialog."""
        app = app or self.make_app()
        try:
            self.parsed = resume.parse_resume(path)
        except resume.ResumeImportError:
            self.parsed = None  # the handler must refuse the same file
        FILEDIALOG.path = str(path)
        RecordingToplevel.created = []
        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._import_resume()
        dialog = RecordingToplevel.created[0] if RecordingToplevel.created else None
        return app, dialog

    def shown_text(self):
        """Every string the review screen displayed: dialog labels and proposal checkbuttons."""
        labels = [label.text for label in RecordingLabel.created]
        buttons = [button.text for button in RecordingCheckbutton.created]
        return "\n".join(labels + buttons)

    def selection(self, key):
        """The checkbutton variable for a proposal key, matched by the label on the checkbox."""
        for proposal in self.parsed.proposals:
            if proposal.key != key:
                continue
            for button in RecordingCheckbutton.created:
                if button.text == proposal.label:
                    return button.variable
        raise AssertionError(f"no checkbutton was created for {key!r}")

    def labels_with(self, prefix):
        """Every dialog label whose text starts with ``prefix``."""
        return [label for label in RecordingLabel.created if label.text.startswith(prefix)]

    def test_a_cancelled_chooser_changes_nothing(self):
        self.store.save_profile(PROFILE)
        app = self.make_app()
        FILEDIALOG.path = ""

        app._import_resume()

        self.assertEqual(RecordingToplevel.created, [])
        self.assertEqual(MESSAGES.titles(), [])
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertIn("cancelled", app.status.get())

    def test_a_file_that_cannot_be_read_is_reported_without_changing_the_profile(self):
        refusal = Path(self._directory.name) / "resume.rtf"
        refusal.write_bytes(b"{\\rtf1 not a supported format}")
        self.store.save_profile(PROFILE)

        app, dialog = self.import_resume(refusal)

        self.assertIsNone(dialog, "no review screen may open for a file that was refused")
        self.assertIn("Resume not imported", MESSAGES.titles("showerror"))
        self.assertIn("not changed", MESSAGES.text("showerror"))
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertNotIn("Resume import saved", app.status.get())

    def test_the_review_screen_shows_every_proposal_before_anything_is_saved(self):
        self.store.save_profile(PROFILE)
        path = self.write_docx()

        app, dialog = self.import_resume(path)

        self.assertIsNotNone(dialog)
        self.assertTrue(self.parsed.proposals, "the fixture must produce proposals")
        shown = self.shown_text()
        for proposal in self.parsed.proposals:
            self.assertIn(proposal.value, shown, "the proposed value must be visible before saving")
            self.assertIn(proposal.evidence, shown, "the evidence for a proposal must be visible")
            self.assertIn(proposal.confidence.value, shown, "the confidence must be visible")
        self.assertEqual(self.store.get_profile(), PROFILE, "opening the review screen must not save")
        self.assertNotIn("Resume import result", MESSAGES.titles("showinfo"))

    def test_only_confident_proposals_start_selected(self):
        self.store.save_profile(PROFILE)
        path = self.write_docx()

        _app, dialog = self.import_resume(path)

        self.assertIsNotNone(dialog)
        confidences = {proposal.confidence for proposal in self.parsed.proposals}
        self.assertIn(resume.ProposalConfidence.NEEDS_REVIEW, confidences, "the fixture needs an uncertain value")
        checked = {proposal.key: self.selection(proposal.key).get() for proposal in self.parsed.proposals}
        self.assertEqual(
            checked,
            {proposal.key: proposal.confidence is resume.ProposalConfidence.CONFIDENT
             for proposal in self.parsed.proposals},
            "only a value the parser is confident about may start selected",
        )

    def test_an_uncertain_value_is_not_saved_unless_it_is_selected(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)
        CONFIG["Save these values?"] = True

        BUTTONS.by_text["Save selected values"]()

        # The document says 2028 and the saved profile says 2027; only a deliberate choice may move it.
        self.assertEqual(self.store.get_profile().graduation_year, PROFILE.graduation_year)
        self.assertIn("Resume import result", MESSAGES.titles("showinfo"))

    def test_accepted_values_are_saved_and_unselected_ones_keep_the_saved_profile(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)
        CONFIG["Save these values?"] = True
        self.selection("skills").set(False)          # confident, but the person says no
        self.selection("graduation_year").set(True)  # uncertain, but the person says yes

        BUTTONS.by_text["Save selected values"]()

        stored = self.store.get_profile()
        self.assertEqual(stored.graduation_year, 2028)
        self.assertEqual(stored.degree_discipline, "Electronics and Communication Engineering")
        self.assertEqual(set(stored.skills), set(PROFILE.skills), "an unselected value must keep the saved one")
        self.assertEqual(stored.candidate_country, PROFILE.candidate_country)
        self.assertEqual(stored.experience_years, PROFILE.experience_years)
        self.assertTrue(dialog.destroyed)
        self.assertIn("Not saved (not selected): Skills", MESSAGES.text("showinfo"))
        self.assertIn("Resume import result", MESSAGES.titles("showinfo"))
        self.assertIn("saved", app.status.get().lower())
        self.assertEqual(app.profile_vars["graduation_year"].get(), "2028")
        self.assertEqual(app.profile_vars["skills"].get(), desktop.profile_form_values(PROFILE)["skills"])

    def test_cancelling_the_review_changes_nothing(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)

        BUTTONS.by_text["Cancel"]()

        self.assertTrue(dialog.destroyed)
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertEqual(app.profile_vars["skills"].get(), desktop.profile_form_values(PROFILE)["skills"])
        self.assertIn("cancelled", app.status.get())
        self.assertEqual(MESSAGES.titles("showinfo"), [])

    def test_declining_the_confirmation_saves_nothing(self):
        self.store.save_profile(PROFILE)
        _app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)
        CONFIG["Save these values?"] = False

        BUTTONS.by_text["Save selected values"]()

        self.assertNotIn("Resume import result", MESSAGES.titles("showinfo"))
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertFalse(dialog.destroyed, "the review screen must stay open")

    def test_selecting_nothing_is_refused_without_saving(self):
        self.store.save_profile(PROFILE)
        _app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)
        for button in RecordingCheckbutton.created:
            button.variable.set(False)

        BUTTONS.by_text["Save selected values"]()

        self.assertIn("Nothing selected", MESSAGES.titles("showinfo"))
        self.assertNotIn("Resume import result", MESSAGES.titles("showinfo"))
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertFalse(dialog.destroyed)

    def test_a_value_that_fails_validation_is_refused_without_writing(self):
        self.store.save_profile(PROFILE)
        app = self.make_app()

        saved, message = app._apply_accepted_profile_values({"experience": "lots"})

        self.assertFalse(saved)
        self.assertIn("Nothing was saved", message)
        self.assertEqual(self.store.get_profile(), PROFILE)

    def test_a_save_that_fails_validation_never_reports_success(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)
        app.profile_vars["experience"].set("lots")

        BUTTONS.by_text["Save selected values"]()

        self.assertIn("Profile not saved", MESSAGES.titles("showerror"))
        self.assertNotIn("Resume import result", MESSAGES.titles("showinfo"))
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertFalse(dialog.destroyed)

    def test_a_database_failure_is_reported_and_the_previous_profile_survives(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)

        with mock.patch.object(
            self.store, "save_profile", side_effect=sqlite3.OperationalError("database is locked")
        ):
            BUTTONS.by_text["Save selected values"]()

        self.assertIn("Profile not saved", MESSAGES.titles("showerror"))
        self.assertIn("database is locked", MESSAGES.text("showerror"))
        self.assertNotIn("Resume import result", MESSAGES.titles("showinfo"))
        self.assertIn("nothing was saved", app.status.get().lower())
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertFalse(dialog.destroyed)

    def test_a_stored_profile_that_does_not_match_is_reported_as_failed(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)

        with mock.patch.object(
            self.store, "get_profile", return_value=CandidateProfile(skills=frozenset({"Rust"}))
        ):
            BUTTONS.by_text["Save selected values"]()

        self.assertIn("Profile not saved", MESSAGES.titles("showerror"))
        self.assertIn("does not match", MESSAGES.text("showerror"))
        self.assertNotIn("Resume import result", MESSAGES.titles("showinfo"))
        self.assertNotIn("Verified in the local database", MESSAGES.text())

    def test_missing_and_unsupported_values_are_reported_without_being_stored(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)

        shown = self.shown_text()
        self.assertIn("Not found in this document (your saved values are kept)", shown)
        self.assertIn("Country", shown)
        self.assertIn("Present in the document but not stored", shown)
        self.assertIn("ada.placeholder@example.invalid", shown, "an unmapped value is shown as informational")

        CONFIG["Save these values?"] = True
        BUTTONS.by_text["Save selected values"]()

        stored = repr(self.store.get_profile())
        self.assertNotIn("placeholder", stored, "a value the profile cannot store must not be written")
        self.assertNotIn("@", stored)

    def test_the_document_text_is_never_copied_into_a_message_the_status_or_the_profile(self):
        self.store.save_profile(PROFILE)
        path = self.write_docx(paragraphs=RESUME_LINES + (LONG_PROSE,))
        app, dialog = self.import_resume(path)
        self.assertIsNotNone(dialog)

        self.assertNotIn(PROSE_FRAGMENT, self.shown_text())
        CONFIG["Save these values?"] = True
        BUTTONS.by_text["Save selected values"]()

        form_after = {key: variable.get() for key, variable in app.profile_vars.items()}
        for blob in (MESSAGES.text(), app.status.get(), repr(self.store.get_profile()), repr(form_after)):
            self.assertNotIn(PROSE_FRAGMENT, blob)

    def test_the_review_screen_shows_the_file_name_but_not_the_folder(self):
        self.store.save_profile(PROFILE)
        _app, dialog = self.import_resume(self.write_docx(name="ada-resume.docx"))
        self.assertIsNotNone(dialog)

        shown = self.shown_text()
        self.assertIn("ada-resume.docx", shown)
        self.assertNotIn(self._directory.name, shown, "the folder a document lives in is not displayed")

    def test_the_selected_file_is_not_copied_or_modified(self):
        self.store.save_profile(PROFILE)
        path = self.write_docx(name="ada-resume.docx")
        before = path.read_bytes()

        _app, dialog = self.import_resume(path)
        self.assertIsNotNone(dialog)
        CONFIG["Save these values?"] = True
        BUTTONS.by_text["Save selected values"]()

        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(
            sorted(item.name for item in Path(self._directory.name).glob("*.docx")), ["ada-resume.docx"],
            "importing must not leave a copy of the document behind",
        )

    def test_table_text_is_read_locally_and_offered_like_paragraph_text(self):
        self.store.save_profile(PROFILE)
        path = self.write_docx(
            paragraphs=("Ada Placeholder", "Skills"),
            tables=((("Python", "SQL"), ("Machine Learning", "Git")),),
        )

        app, dialog = self.import_resume(path)

        self.assertIsNotNone(dialog)
        self.assertIn("Python, SQL, Machine Learning, Git", self.shown_text())
        self.assertEqual(self.store.get_profile(), PROFILE)

    def test_a_document_with_nothing_recognisable_still_reports_honestly(self):
        self.store.save_profile(PROFILE)
        _app, dialog = self.import_resume(self.write_docx(paragraphs=("A short note about nothing in particular.",)))
        self.assertIsNotNone(dialog)

        self.assertIn("No supported profile value was found", self.shown_text())

        BUTTONS.by_text["Save selected values"]()

        self.assertIn("Nothing selected", MESSAGES.titles("showinfo"))
        self.assertNotIn("Resume import result", MESSAGES.titles("showinfo"))
        self.assertEqual(self.store.get_profile(), PROFILE)

    def test_a_wrapping_option_on_a_checkbutton_is_refused_like_real_tk(self):
        """The macOS crash in one line: ttk.Checkbutton has no -wraplength, and Tk says so."""
        with self.assertRaises(TclOptionError) as caught:
            desktop.ttk.Checkbutton(Widget(), text="Skills", variable=desktop.tk.BooleanVar(), wraplength=720)

        self.assertIn("wraplength", str(caught.exception))

    def test_the_review_rows_pass_only_options_ttk_checkbutton_accepts(self):
        self.store.save_profile(PROFILE)

        _app, dialog = self.import_resume(self.write_docx())

        self.assertIsNotNone(dialog)
        self.assertTrue(RecordingCheckbutton.created, "the fixture must produce proposals")
        self.assertEqual(len(RecordingCheckbutton.created), len(self.parsed.proposals))
        for checkbox in RecordingCheckbutton.created:
            self.assertEqual(set(checkbox.options), {"text", "variable"}, "no wrapping option belongs here")
            self.assertLessEqual(set(checkbox.options), set(TTK_CHECKBUTTON_OPTIONS))

    def test_the_wrapping_labels_carry_the_value_and_the_review_state(self):
        self.store.save_profile(PROFILE)

        _app, dialog = self.import_resume(self.write_docx())

        self.assertIsNotNone(dialog)
        for proposal in self.parsed.proposals:
            value_labels = self.labels_with(f"{proposal.label}: ")
            self.assertTrue(value_labels, f"{proposal.label} needs a label showing its value")
            self.assertIn(proposal.value, value_labels[0].text)
            self.assertIn("wraplength", value_labels[0].options, "the value label is where wrapping belongs")
            self.assertLessEqual(set(value_labels[0].options), set(TTK_LABEL_OPTIONS))
            state_labels = [
                label for label in RecordingLabel.created
                if label.text.startswith(f"{proposal.confidence.value} · from: ")
                and proposal.evidence in label.text
            ]
            self.assertTrue(state_labels, f"{proposal.label} needs its evidence and confidence shown")
            self.assertIn("wraplength", state_labels[0].options)

    def test_the_review_dialog_scrolls_and_keeps_its_actions_out_of_the_scrolling_area(self):
        self.store.save_profile(PROFILE)

        _app, dialog = self.import_resume(self.write_docx())

        self.assertIsNotNone(dialog)
        self.assertEqual(len(Canvas.created), 1, "the proposals need exactly one scrollable area")
        canvas = Canvas.created[0]
        scrolled = canvas.window_widget
        self.assertIsNotNone(scrolled, "the canvas must hold the frame the proposals are built in")
        self.assertEqual(canvas.window_anchor, "nw")
        self.assertEqual(len(RecordingScrollbar.created), 1, "the scrolling area needs a scrollbar")
        self.assertIn("<Configure>", scrolled.bindings, "the scroll region must follow the content")
        self.assertIn("<Configure>", canvas.bindings, "the canvas must fit its content width")
        self.assertIn("<MouseWheel>", canvas.bindings, "the mouse wheel must scroll the proposals")
        for checkbox in RecordingCheckbutton.created:
            self.assertIs(checkbox.master.master, scrolled, "each proposal row lives in the scrolling area")

        actions = {button.text: button for button in BUTTONS.created if button.text}
        self.assertIn("Save selected values", actions)
        self.assertIn("Cancel", actions)
        self.assertIs(actions["Save selected values"].master, actions["Cancel"].master)
        self.assertIsNot(actions["Save selected values"].master, scrolled, "the actions must not scroll away")

    def test_the_review_dialog_opens_at_a_usable_size(self):
        self.store.save_profile(PROFILE)

        _app, dialog = self.import_resume(self.write_docx())

        self.assertIsNotNone(dialog)
        width, height = (int(part) for part in str(dialog.requested_geometry).split("x"))
        self.assertGreaterEqual(width, 640, "the dialog must be wide enough for wrapping prose")
        self.assertGreaterEqual(height, 480, "the dialog must be tall enough for several proposals")
        minimum_width, minimum_height = (int(part) for part in dialog.requested_minsize)
        self.assertLessEqual(minimum_width, width)
        self.assertLessEqual(minimum_height, height)

    def test_closing_the_review_window_changes_nothing(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)
        close_handler = dialog.protocols.get("WM_DELETE_WINDOW")
        self.assertTrue(callable(close_handler), "the window close button must be handled, not ignored")

        close_handler()

        self.assertTrue(dialog.destroyed)
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertIn("cancelled", app.status.get())
        self.assertEqual(MESSAGES.titles("showinfo"), [])

    def test_the_review_screen_offers_keyboard_cancel_and_confirm(self):
        self.store.save_profile(PROFILE)
        app, dialog = self.import_resume(self.write_docx())
        self.assertIsNotNone(dialog)

        self.assertIn("<Escape>", dialog.bindings, "the dialog must be cancellable from the keyboard")
        self.assertIn("<Return>", dialog.bindings, "the dialog must be confirmable from the keyboard")
        self.assertIn("Cancel", BUTTONS.by_text)
        self.assertIn("Save selected values", BUTTONS.by_text)

        dialog.bindings["<Escape>"](None)

        self.assertTrue(dialog.destroyed)
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertIn("cancelled", app.status.get(), "Escape must say what the Cancel button says")


    def test_a_password_protected_docx_is_reported_and_nothing_is_saved(self):
        path = Path(self._directory.name) / "protected.docx"
        write_resume_docx(path, paragraphs=RESUME_LINES)
        path.write_bytes(mark_zip_members_encrypted(path.read_bytes()))
        self.store.save_profile(PROFILE)
        app = self.make_app()

        app, dialog = self.import_resume(path, app)

        self.assertIsNone(dialog, "an unreadable file must not open the review window")
        self.assertIn("Resume not imported", MESSAGES.titles("showerror"))
        self.assertIn("password-protected", MESSAGES.text("showerror"))
        self.assertNotIn(str(self._directory.name), MESSAGES.text("showerror"))
        self.assertEqual(self.store.get_profile(), PROFILE, "nothing may be written")
        self.assertIn("profile was not changed", app.status.get())

    def test_an_unexpected_reader_failure_is_reported_rather_than_escaping_the_callback(self):
        path = Path(self._directory.name) / "resume.docx"
        write_resume_docx(path, paragraphs=RESUME_LINES)
        self.store.save_profile(PROFILE)
        app = self.make_app()
        FILEDIALOG.path = str(path)
        leaked = "Ada Placeholder and the rest of the document text"

        with mock.patch.object(
            desktop.resume, "parse_resume", side_effect=RuntimeError(f"{leaked} at {path}")
        ):
            app._import_resume()  # must not raise out of the callback

        self.assertIn("Resume not imported", MESSAGES.titles("showerror"))
        message = MESSAGES.text("showerror")
        self.assertIn("RuntimeError", message, "the failure type is named so it can be reported")
        self.assertNotIn(leaked, message, "an unexpected message may quote document text")
        self.assertNotIn(str(path), message)
        self.assertNotIn(str(self._directory.name), message)
        self.assertEqual(RecordingToplevel.created, [], "no review window may open")
        self.assertEqual(self.store.get_profile(), PROFILE)
        self.assertIn("profile was not changed", app.status.get())

class WindowConstructionTests(HandlerTestCase):
    """Every widget the real window builds must accept the options it is given.

    The macOS crash this covers happened while a widget was being constructed: ``ttk.Checkbutton`` was
    given ``-wraplength``, which Tk refuses at build time with ``unknown option "-wraplength"``. The
    stubs here refuse the same options real Tk refuses, so building the whole interface — and the
    review dialog, in the tests above — is a headless guard for that entire class of crash.
    """

    def build_window(self):
        root = RecordingToplevel()
        app = desktop.CareerAgentApp(root, database_path=Path(self._directory.name) / "window.sqlite3")
        self.addCleanup(app.store.close)
        return root, app

    def test_the_whole_window_and_every_tab_can_be_built(self):
        root, app = self.build_window()

        self.assertEqual(root.title_text, "AI Career Agent — Local Workspace")
        self.assertIn("WM_DELETE_WINDOW", root.protocols, "closing the window must be handled")
        self.assertIs(app.root, root)
        self.assertTrue(RecordingLabel.created, "the tabs must have been built")
        self.assertTrue(RecordingCombobox.created or app.jobs_tree.options, "the job form must exist")

    def test_building_the_window_offers_every_tab(self):
        _root, app = self.build_window()

        self.assertTrue(hasattr(app, "profile_tab") and hasattr(app, "jobs_tab"))
        self.assertTrue(hasattr(app, "tracker_tab") and hasattr(app, "data_tab"))
        self.assertEqual(app.profile_vars["skills"].get(), "", "a fresh window starts with an empty profile")


class UnreadableStoredRecordTests(HandlerTestCase):
    """A damaged or hand-edited row must be reported, never escape a Tk callback as a traceback.

    ``career_agent.store`` refuses such a row with a named ``StoredRecordError``, but a refusal still
    has to be *handled*: a Tk callback that lets one escape prints a traceback to stderr and leaves the
    window in an undefined state, and the person is told nothing. Every case here writes the payload the
    way damage or a manual edit would (directly, through the standard library) and then runs the real
    handler, checking the message shown and that nothing was written, repaired, or half-rendered.
    """

    def corrupt_profile(self, payload='{"candidate_country": "India", "nickname": "Ada"}'):
        self.store.save_profile(PROFILE)
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE candidate_profile SET payload=? WHERE profile_id=1", (payload,)
            )
        return payload

    def stored_profile_payload(self):
        return self.store._connection.execute(
            "SELECT payload FROM candidate_profile WHERE profile_id=1"
        ).fetchone()["payload"]

    def corrupt_listing(self, listing_id="j1", payload=None):
        self.store.save_job(sample_job(listing_id=listing_id))
        raw = payload or '{"listing_id": "%s", "employer_name": "Example Inc"}' % listing_id
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE job_listings SET payload=? WHERE listing_id=?", (raw, listing_id)
            )
        return raw

    def test_the_profile_view_reports_it_and_changes_nothing(self):
        payload = self.corrupt_profile()
        app = self.make_app_with_real_handlers("_load_profile")

        app._load_profile()

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertNotIn("Traceback", MESSAGES.text("showerror"))
        self.assertIn("nickname", MESSAGES.text("showerror"))
        self.assertIn("nothing was changed", app.status.get())
        self.assertEqual(self.stored_profile_payload(), payload, "a refused read must not rewrite the row")

    def test_the_jobs_list_reports_it_instead_of_breaking_the_refresh(self):
        self.corrupt_listing()
        app = self.make_app_with_real_handlers("_refresh_jobs", "_refresh_tracker")

        app._refresh_jobs()  # must not raise: a Tk callback has no caller to catch it

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertIn("nothing was changed", app.status.get())
        self.assertEqual(len(app.jobs_tree.inserted), 0, "no half-rendered list is shown for a refused read")

    def test_the_tracker_view_reports_it_instead_of_breaking_the_refresh(self):
        self.corrupt_listing()
        app = self.make_app_with_real_handlers("_refresh_tracker")

        app._refresh_tracker()

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertEqual(len(app.tracker_tree.inserted), 0)

    def test_selecting_an_unreadable_listing_reports_it_and_keeps_the_view_defined(self):
        self.corrupt_listing()
        app = self.make_app_with_real_handlers("_select_job")
        app.jobs_tree.selected = ("j1",)

        app._select_job()

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertIsNone(app.selected_job_id, "an unreadable row must not become the selection")
        self.assertEqual(app.job_save_mode, desktop.JobSaveMode.NEW)

    def test_evaluating_an_unreadable_listing_refuses_without_writing_a_tracker_row(self):
        self.corrupt_listing()
        app = self.make_app_with_real_handlers("_evaluate")
        app.jobs_tree.selected = ("j1",)

        app._evaluate()

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertIsNone(self.store.get_tracker_raw("j1"), "a refused evaluation must store nothing")

    def test_shortlisting_an_unreadable_listing_refuses_without_writing_a_tracker_row(self):
        self.corrupt_listing()
        app = self.make_app()
        app.jobs_tree.selected = ("j1",)

        app._shortlist()

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertIsNone(self.store.get_tracker_raw("j1"))

    def test_export_reports_it_and_writes_no_file(self):
        self.corrupt_profile()
        destination = Path(self._directory.name) / "export.json"
        FILEDIALOG.path = str(destination)
        app = self.make_app()

        app._export()

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertNotIn("Export complete", MESSAGES.titles())
        self.assertFalse(destination.exists(), "a refused export must not leave a file behind")
        self.assertNotIn("ECE", destination.read_text(encoding="utf-8") if destination.exists() else "")

    def test_a_resume_save_whose_read_back_fails_is_not_reported_as_saved(self):
        self.store.save_profile(PROFILE)
        app = self.make_app()
        error = StoredRecordError("candidate profile", "it holds field(s) this version cannot use")

        with mock.patch.object(self.store, "get_profile", side_effect=error):
            saved, message = app._apply_accepted_profile_values({"experience": "1"})

        self.assertFalse(saved)
        self.assertNotIn("Verified in the local database", message)
        # The write itself succeeded, so the message must not claim nothing was saved: it says the
        # values were written but could not be verified, and points at where to check.
        self.assertIn("written to the local database", message)
        self.assertIn("unconfirmed", message)
        self.assertIn("Profile tab", message)
        self.assertNotIn("Traceback", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
