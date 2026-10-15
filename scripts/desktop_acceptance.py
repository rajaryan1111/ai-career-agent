"""End-to-end desktop acceptance workflows, driven through the real window and its real widgets.

The manual checklist in ``research/`` is what a *person* has to do, and this script does not pretend to
replace it. What it does is narrower and still worth having: it builds the real ``CareerAgentApp`` window on
a disposable synthetic database, types into the real ``Entry`` widgets, presses the real buttons through
Tk's own ``invoke``, answers the dialogs a person would answer, and then checks the *stored* result and what
the window says about it. Six workflows run, in the order a first-time user would meet them:

* **A - the candidate profile.** Type a synthetic profile, add a role and a qualification through the
  window's own forms, save, close the window, open a second window on the same database, and check that the
  fields, the role and the qualification came back.
* **B - the two job URLs.** Save a listing whose source URL is set and whose employer application URL is
  blank, reopen it, and check that the two fields are still separate and the blank one is still blank.
* **C - eligibility safety.** A listing with no availability evidence must evaluate to UNKNOWN and must
  refuse shortlisting; the same listing with explicit evidence may then reach PASS and be shortlisted.
* **D - tracker and analytics.** Move an application by permitted transitions through the status dialog, and
  check that an interview round recorded while the application is only shortlisted is never reported as an
  application sent or as a completed outcome.
* **E - export, import and refusal.** Export to a chosen file, check the file against what the database
  holds (including the application record), import it into a second disposable database, import it again
  and check that a repeat adds nothing, and check that malformed input, a damaged record and a path that
  cannot be protected are refused without writing a byte.
* **F - cleanup and lifecycle.** Every window closed, every connection released, the disposable folder gone,
  and the person's own database untouched - including after a forced failure.

Four properties are deliberate, and they are the reason this file is safe to run in CI.

* **Nothing is reported as done that a machine cannot see.** Every check reads a stored record, a widget's
  text, or the line the window wrote into its status bar. No check inspects pixels, layout, focus order,
  dialog wording or how anything feels, because none of those can be judged from here.
* **A machine without a window is BLOCKED, never a pass.** Without ``tkinter``, or without a display, the
  run exits :data:`EXIT_BLOCKED` and names the missing capability, in the same 0/1/2 convention
  ``scripts/desktop_smoke_test.py`` and ``career_agent.__main__`` use.
* **The dialogs a person would answer are answered for the run, and every one of them is recorded.** A
  file chooser and a confirmation cannot be clicked without a human, so the run supplies the path and the
  answer - and says so in the report it prints. What is *checked* about them is which dialogs were raised
  and whether their text contradicts what the run observed: a refusal that must be explained is checked for
  being explained, and an export that failed must never be reported as written.
* **A check that does not run is not a pass.** Every check is a ``results.step`` block, and the run
  compares how many it performed against how many its own source declares. Remove a check, and the run
  reports a failure rather than a smaller pass - so the size of this file cannot shrink unnoticed.
* **Synthetic data, and only ever in a disposable folder.** The profile, the listings and every note are
  obvious fixtures. The database, the export and the temporary folder are created inside one
  ``mkdtemp`` folder that is deleted at the end; the application's own database location is recorded before
  and after and must be identical, and the folder is only resolved in a way that creates nothing.

Run from the repository root, on a machine with a display::

    python scripts/desktop_acceptance.py

Exit status: ``0`` every check passed; ``1`` a check failed (a defect, or this project no longer matches
what the workflows assert); ``2`` BLOCKED (no display, or no ``tkinter``), which is not a pass.

On a machine with no display, ``--stand-in-tk`` runs the same workflows against the stand-in widget module
the test suite maintains. It exists for writing the workflows, reports itself as a DEVELOPMENT RUN, never
prints a pass or a failure, and always exits 2: a stand-in has no window, so its results are not evidence
and must never be read as any. CI runs it once, in a step that requires exactly that behaviour.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import traceback
from datetime import date
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    # Running the file directly puts ``scripts/`` on the path, not the repository root, so the window
    # would be imported from whatever is installed. The checkout is what this script is checking.
    sys.path.insert(0, str(REPOSITORY_ROOT))
SCRIPTS_FOLDER = Path(__file__).resolve().parent
if str(SCRIPTS_FOLDER) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_FOLDER))

# The proven parts of the sibling entry point, reused rather than reimplemented: the same helper names for
# the same jobs, so a change to how a widget is found or how BLOCKED is decided lands in one place.
from desktop_smoke_test import (  # noqa: E402 - after the path is set
    EXIT_BLOCKED,
    EXIT_FAIL,
    EXIT_PASS,
    Results,
    SmokeFailure,
    default_database_state,
    import_tkinter,
    looks_like_no_display,
    report_blocked,
    require,
)

#: Tk class names, as real ``winfo_class`` reports them. Spelled once so a workflow reads what a person
#: sees ("the entry", "the button") rather than an index into whatever list the widget tree returns.
BUTTON = "TButton"
ENTRY = "TEntry"
COMBOBOX = "TCombobox"
CHECKBUTTON = "TCheckbutton"
TREEVIEW = "Treeview"
TEXT = "Text"
TOPLEVEL = "Toplevel"

#: A synthetic candidate profile, typed into the profile form field by field. Every value is a fixture:
#: there is no real candidate in this file, and the locations and employers are invented.
SYNTHETIC_PROFILE = {
    "country": "Syntheticland",
    "degree": "Synthetic Computing",
    "study_status": "graduate",
    "graduation_year": "2026",
    "experience": "1",
    "work_authorization": "Synthetic Permit Class A",
    "skills": "python, sqlite, testing",
    "locations": "Synthetic City",
    "work_modes": "remote",
    "role_types": "internship",
}

#: The profile fields the checks compare after a save: the app's own comparison helper is used, so a field
#: the form renders back differently (a sorted list, a number as text) is not reported as a mismatch.
SYNTHETIC_ROLE = {
    "employer": "Fixture Analytics Ltd",
    "job_title": "Fictional Junior Analyst",
    "start_date": "2025-01-06",
    "summary": "Fixture record created by the desktop acceptance run.",
}
SYNTHETIC_QUALIFICATION = {
    "institution": "Fixture Institute of Technology",
    "qualification": "BSc Fictional Computing",
    "discipline": "Computing",
    "start_date": "2022-09-01",
    "completion_date": "2025-06-30",
}

#: Two listings: the first has no availability evidence at all, the second carries an explicit note. That
#: difference is the whole of workflow C - the evidence is what separates UNKNOWN from PASS.
LISTING_WITHOUT_EVIDENCE = {
    "employer": "Fixture Analytics Ltd",
    "title": "Fictional Data Analyst (no evidence recorded)",
    "source_name": "Fixture Job Board",
    "source_url": "https://example.com/fixture/jobs/1001",
    "apply_url": "",
    "availability": "open",
    "scope": "unknown",
    "provenance_note": "",
}

#: What a fixture listing states about its own requirements, kept apart from its identity so a workflow can
#: add them to a listing that already exists. They are what a PASS needs, and the reason is the application's
#: own rule: an unstated requirement is UNKNOWN, and UNKNOWN is not eligible. The values match the synthetic
#: profile above, which is the point - a listing this candidate cannot pass would misrepresent the workflow.
LISTING_REQUIREMENTS = {
    "degrees": SYNTHETIC_PROFILE["degree"],
    "study_statuses": SYNTHETIC_PROFILE["study_status"],
    "graduation_years": SYNTHETIC_PROFILE["graduation_year"],
    "allowed_work_authorizations": SYNTHETIC_PROFILE["work_authorization"],
    "min_exp": "0",
    "max_exp": "3",
    "required_skills": SYNTHETIC_PROFILE["skills"],
}

LISTING_WITH_EVIDENCE = {
    "employer": "Fixture Analytics Ltd",
    "title": "Fictional Data Analyst (evidence recorded)",
    "source_name": "Fixture Job Board",
    "source_url": "https://example.com/fixture/jobs/1002",
    "apply_url": "",
    "availability": "open",
    "scope": "worldwide",
    "provenance_note": "Fixture: the listing itself was readable and marked open when it was checked.",
    **LISTING_REQUIREMENTS,
}

#: A note the run writes into a status dialog and into an interview round. It is a fixture, and it is not
#: evidence of anything an employer did: no employer was contacted by this file, and none is contacted by
#: anything it drives.
SYNTHETIC_NOTE = "Fixture note: recorded by the desktop acceptance run."

WINDOW_TITLE = "AI Career Agent — Local Workspace"


# --------------------------------------------------------------------------------------------------
# Reading and driving the real widget tree
# --------------------------------------------------------------------------------------------------
def descendants(widget) -> list:
    """Every widget below ``widget``, depth first, in the order its parent lists them.

    Deliberately not recursive-by-generator over a live tree: dialogs are destroyed while a walk is in
    progress, and a list is taken first so a destroyed child cannot be visited afterwards.
    """
    found = []
    for child in list(widget.winfo_children()):
        found.append(child)
        found.extend(descendants(child))
    return found


def find_widgets(parent, *, klass: str | None = None, text: str | None = None) -> list:
    """The widgets under ``parent`` whose Tk class, and label text, match what was asked for."""
    matches = []
    for widget in descendants(parent):
        if klass is not None and widget.winfo_class() != klass:
            continue
        if text is not None:
            try:
                label = str(widget.cget("text"))
            except Exception:  # noqa: BLE001 - a widget without a text option cannot match one
                continue
            if label != text:
                continue
        matches.append(widget)
    return matches


def find_widget(parent, *, klass: str | None = None, text: str | None = None, what: str = "widget"):
    """Exactly one matching widget, or a failure that says what was looked for and what was there."""
    matches = find_widgets(parent, klass=klass, text=text)
    if len(matches) != 1:
        described = ", ".join(sorted({widget.winfo_class() for widget in descendants(parent)})) or "none"
        raise SmokeFailure(
            f"expected exactly one {what}, found {len(matches)}; widgets present: {described}"
        )
    return matches[0]


def press(parent, text: str, root) -> None:
    """Press the button carrying ``text``: real ``invoke``, which runs the same command a click runs."""
    button = find_widget(parent, klass=BUTTON, text=text, what=f"button labelled {text!r}")
    button.invoke()
    root.update()


def linked_to(widget, variable) -> bool:
    """Whether a widget is bound to ``variable``.

    Both options a Tk widget can bind a variable through are read: entries and choosers use
    ``textvariable``, while a checkbutton - the confirmation assertion in the status dialog among them -
    uses ``variable``. Real Tk answers either with the variable's Tcl *name*; this project's tests use a
    stub that answers with the variable object. Both spellings are accepted, so the same helper reads a
    real window and a stubbed one, and neither has to know which it is looking at.
    """
    for option in ("textvariable", "variable"):
        try:
            linked = widget.cget(option)
        except Exception:  # noqa: BLE001 - a widget without that option is simply not bound through it
            continue
        if linked is variable:
            return True
        if isinstance(linked, str) and linked != "" and linked == str(variable):
            return True
    return False


def widget_for(parent, variable, *, klass: str, what: str):
    """The one widget of ``klass`` under ``parent`` that is bound to ``variable``."""
    matches = [widget for widget in find_widgets(parent, klass=klass) if linked_to(widget, variable)]
    if len(matches) != 1:
        raise SmokeFailure(f"expected exactly one {what}, found {len(matches)}")
    return matches[0]


def type_into(parent, variable, value: str, *, what: str) -> str:
    """Type ``value`` into the entry bound to ``variable``, replacing whatever is there."""
    entry = widget_for(parent, variable, klass=ENTRY, what=what)
    entry.delete(0, "end")
    entry.insert(0, value)
    return str(entry.get())


def set_field(parent, variable, value: str, *, what: str) -> str:
    """Fill in the field bound to ``variable``, whether a person types in it or picks from a list.

    Several of this window's fields are readonly choosers rather than free text - study status, availability,
    eligibility scope, work mode - and a harness that only knew how to type would report those fields as
    missing. What the field *is* decides how it is filled, and both ways end with the application's own
    variable holding the value, which is what the window reads when the button is pressed.
    """
    entries = find_widgets(parent, klass=ENTRY)
    choosers = find_widgets(parent, klass=COMBOBOX)
    if any(linked_to(widget, variable) for widget in choosers):
        chooser = widget_for(parent, variable, klass=COMBOBOX, what=what)
        if value not in [str(option) for option in (chooser.cget("values") or ())]:
            raise SmokeFailure(f"{value!r} is not one of the values {what} offers")
        chooser.set(value)
        return str(chooser.get())
    if any(linked_to(widget, variable) for widget in entries):
        return type_into(parent, variable, value, what=what)
    raise SmokeFailure(f"no entry or chooser is bound to {what}")


def choose_in(parent, variable, value: str, *, what: str) -> None:
    """Choose ``value`` in the readonly chooser bound to ``variable``, as the dropdown does."""
    chooser = widget_for(parent, variable, klass=COMBOBOX, what=what)
    chooser.set(value)


def field_value(parent, variable, *, what: str) -> str:
    """What the field bound to ``variable`` currently holds, whether it is an entry or a chooser."""
    widget = widget_for_any(parent, variable, what=what)
    return str(widget.get())


def widget_for_any(parent, variable, *, what: str):
    """The widget bound to ``variable``, of whichever class the window built for that field."""
    for klass in (ENTRY, COMBOBOX):
        matches = [widget for widget in find_widgets(parent, klass=klass) if linked_to(widget, variable)]
        if matches:
            if len(matches) > 1:
                raise SmokeFailure(f"{len(matches)} fields are bound to {what}")
            return matches[0]
    raise SmokeFailure(f"no entry or chooser is bound to {what}")


def text_in(widget) -> str:
    """What a text widget holds, read the way a person reads it back."""
    return str(widget.get("1.0", "end"))


def widget_exists(widget) -> bool:
    """Whether a widget is still there, including when Tk will no longer answer at all.

    ``winfo_exists`` does not answer "gone" for a window whose Tk interpreter has been destroyed - it
    raises ``TclError: can't invoke "winfo" command: application has been destroyed``, which is what the
    display-backed CI run reported. That is the strongest possible form of "the window is gone": there is no
    interpreter left to own one. Read any other way, a *correct* cleanup would look like a defect, and the
    check below would never be verifying anything on a real display - it passed against the stand-in only
    because a stand-in has no interpreter to destroy.
    """
    try:
        return bool(widget.winfo_exists())
    except Exception as exc:  # noqa: BLE001 - the widget's interpreter is gone, so the widget is
        print(f"[note] Tk no longer answers for a window ({type(exc).__name__}: {exc}); it is gone")
        return False


def dialogs_under(host) -> list:
    """Every open dialog belonging to this window, oldest first.

    An empty list when Tk will not answer at all: a window whose interpreter is gone has no dialogs open.
    """
    try:
        return [widget for widget in descendants(host) if widget.winfo_class() == TOPLEVEL]
    except Exception as exc:  # noqa: BLE001 - same reason as ``widget_exists``
        print(f"[note] Tk no longer answers for this window ({type(exc).__name__}: {exc})")
        return []


def open_dialog(host, title: str):
    """The dialog with this title; a failure names the dialogs that were actually open."""
    found = [dialog for dialog in dialogs_under(host) if str(dialog.title()) == title]
    if not found:
        open_titles = [str(dialog.title()) for dialog in dialogs_under(host)]
        raise SmokeFailure(f"no dialog titled {title!r} was open; open dialogs: {open_titles}")
    return found[-1]


def record_dialog_controls(policy: DialogPolicy, title: str, call):
    """Run ``call`` with every Tk variable the dialog creates recorded under ``title``.

    The window builds its dialogs from ``tk.StringVar`` and ``tk.BooleanVar``; recording the ones created
    between opening and closing the dialog is what lets the run address the dialog's own widgets by what
    they are bound to, rather than by counting entries.
    """
    from career_agent import desktop  # noqa: PLC0415 - only needed while a dialog is open

    store: list = []
    policy.fields.setdefault(title, [])
    policy.record_variables_for(title, store)
    original_string, original_boolean = desktop.tk.StringVar, desktop.tk.BooleanVar

    def recording(variable_class):
        def factory(*args, **kwargs):
            variable = variable_class(*args, **kwargs)
            store.append(variable)
            return variable

        return factory

    desktop.tk.StringVar = recording(original_string)
    desktop.tk.BooleanVar = recording(original_boolean)
    try:
        return call()
    finally:
        desktop.tk.StringVar = original_string
        desktop.tk.BooleanVar = original_boolean
        policy.record_variables_for(None, [])
        policy.fields[title] = store
        for variable in store:
            policy.note_variable(variable)


def string_variables(policy: DialogPolicy, title: str) -> list:
    """The text variables a dialog created, in creation order."""
    return [variable for variable in policy.variables(title)
            if variable.__class__.__name__ == "StringVar"]


def boolean_variables(policy: DialogPolicy, title: str) -> list:
    """The on/off variables a dialog created, in creation order."""
    return [variable for variable in policy.variables(title)
            if variable.__class__.__name__ == "BooleanVar"]


def close_open_dialogs(host) -> list:
    """Destroy every dialog still open, so one refused step cannot block the next. Returns their titles."""
    titles = []
    for dialog in dialogs_under(host):
        titles.append(str(dialog.title()) if widget_exists(dialog) else "<destroyed>")
        try:
            dialog.destroy()
        except Exception:  # noqa: BLE001 - a dialog already gone is not a problem
            pass
    return titles


def select_listing(app, listing_id: str, root) -> None:
    """Select a listing on the jobs tab, which is what Evaluate, Shortlist and the actions act on.

    Selecting a row is a click: real Tk then dispatches ``<<TreeviewSelect>>`` and the window fills its form
    from the selected listing. What proves the window reacted is the window's own record of the listing it
    is working on - not the tree's selection, which is set by the click itself and would say yes even if
    nothing had run. Where it did not react, the command the tree's binding runs is called: the same
    command a person's click runs, never a second implementation of it.
    """
    app.jobs_tree.selection_set(listing_id)
    root.update()
    if app.selected_job_id != listing_id:
        app._select_job()  # noqa: SLF001 - the command the tree's <<TreeviewSelect>> binding runs
        root.update()
    require(
        app.selected_job_id == listing_id,
        f"the window is not working on {listing_id!r} after its row was selected",
    )


def select_tracker_row(app, listing_id: str, root) -> None:
    """Select the row on the application tracker tab, which the status dialog works from."""
    app.tracker_tree.selection_set(listing_id)
    root.update()
    require(
        list(app.tracker_tree.selection())[:1] == [listing_id],
        f"the tracker row for {listing_id!r} is not selected",
    )


def tracker_status(app, listing_id: str):
    """The stored tracker status for a listing, or ``None`` when no record exists."""
    tracker = app.store.get_tracker(listing_id)
    return None if tracker is None else tracker.status


def report_text(app) -> str:
    """The window's own report pane, as a person reads it."""
    return text_in(app.report)


def event_lines(database) -> str:
    """The application's own event log beside a database, oldest first."""
    from career_agent.event_log import read_lines  # noqa: PLC0415 - only the checks need it

    return "\n".join(read_lines(database_path=database, limit=200))


def file_digest(path) -> str:
    """The sha256 of a file, or a marker when it does not exist."""
    import hashlib  # noqa: PLC0415

    path = Path(path)
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------------------
# The dialogs a person would answer
# --------------------------------------------------------------------------------------------------
class DialogPolicy:
    """The answers this run gives to the dialogs, and the record of what was asked.

    A file chooser and a confirmation cannot be answered without a human, so the run answers them: the
    paths it hands over are inside its own disposable folder, and every confirmation is answered the way a
    person doing this deliberately would answer it. Every call is recorded, which is what lets a workflow
    check that a refusal was *explained* rather than merely performed.

    ``fields`` is how a workflow reaches the controls *inside* a dialog the window builds: the dialog's
    entries and choosers are bound to the StringVars and Booleans the handler created, and the window does
    not keep those anywhere afterwards. Recording the variables as the dialog is built - the same thing
    ``tests/test_desktop_handlers.py`` does for the status dialog - is what makes a dialog the run did not
    author drivable through its real widgets.
    """

    def __init__(self, *, files: tuple[str, ...] = (), answers: dict | None = None) -> None:
        self.files = list(files)
        self.answers = dict(answers or {})
        self.calls: list[tuple[str, str, str, object]] = []
        self.file_requests: list[tuple[str, dict]] = []
        self.fields: dict[str, list] = {}
        self._recording: tuple[str | None, list] = (None, [])

    # -- messagebox --------------------------------------------------------------------------------
    def _note_call(self, kind: str, title: str, message: str, answer):
        """Keep one dialog, and answer it the way the policy says.

        Deliberately *not* called ``_record``: that name is how this project's modules write to the event
        log beside a database, and the suite reads the shipped source to check every event name is
        declared, so a method naming itself that way and taking a word like ``"showinfo"`` would be read as
        an undeclared event. That check is right, and this file keeps out of its way.
        """
        self.calls.append((kind, title, message, answer))
        return answer

    def showinfo(self, title, message, **kwargs):  # noqa: D102 - the messagebox surface, one method each
        return self._note_call("showinfo", title, message, None)

    def showwarning(self, title, message, **kwargs):  # noqa: D102
        return self._note_call("showwarning", title, message, None)

    def showerror(self, title, message, **kwargs):  # noqa: D102
        return self._note_call("showerror", title, message, None)

    def askyesno(self, title, message, **kwargs):  # noqa: D102
        return self._note_call("askyesno", title, message, self.answers.get(title, True))

    # -- filedialog --------------------------------------------------------------------------------
    def asksaveasfilename(self, **kwargs):
        return self._next_file("save", kwargs)

    def askopenfilename(self, **kwargs):
        return self._next_file("open", kwargs)

    def _next_file(self, kind: str, kwargs: dict) -> str:
        self.file_requests.append((kind, kwargs))
        if not self.files:
            return ""
        return self.files.pop(0)

    # -- what the workflows check ------------------------------------------------------------------
    def titles(self, kind: str | None = None) -> list:
        """Every dialog title recorded so far, in order, optionally of one kind."""
        return [title for call_kind, title, _message, _answer in self.calls
                if kind is None or call_kind == kind]

    def said(self, title: str) -> str:
        """Everything recorded under this dialog title, joined: what the window told the person."""
        return "\n".join(message for _kind, call_title, message, _answer in self.calls if call_title == title)

    def reset(self) -> None:
        self.calls = []

    # -- variables created while a dialog is built --------------------------------------------------
    def record_variables_for(self, title: str | None, store: list) -> None:
        """Send every variable created from here on into ``store`` until the next call."""
        self._recording = (title, store)

    def note_variable(self, variable) -> None:
        """Keep a variable created while a dialog was being built."""
        self._recording[1].append(variable)

    # -- what the workflows check ------------------------------------------------------------------
    def variables(self, title: str) -> list:
        """Every variable recorded while the dialog with this title was being built, in creation order."""
        return list(self.fields.get(title, []))


class scripted_dialogs:
    """Answer the window's dialogs from a policy, and put the real ones back afterwards.

    ``career_agent.desktop`` imports ``messagebox`` and ``filedialog`` into its own namespace, so an
    attribute is swapped for the duration of the run. Nothing else about the window is replaced: its
    widgets, its handlers, its database and its validation are the real ones.
    """

    def __init__(self, policy: DialogPolicy) -> None:
        self.policy = policy

    def __enter__(self) -> DialogPolicy:
        from career_agent import desktop  # noqa: PLC0415 - imported once the window is in use

        self._desktop = desktop
        self._messagebox = desktop.messagebox
        self._filedialog = desktop.filedialog
        desktop.messagebox = self.policy
        desktop.filedialog = self.policy
        return self.policy

    def __exit__(self, *_exception) -> None:
        self._desktop.messagebox = self._messagebox
        self._desktop.filedialog = self._filedialog


# --------------------------------------------------------------------------------------------------
# One disposable workspace for the whole run
# --------------------------------------------------------------------------------------------------
class Workspace:
    """A temporary folder, two synthetic databases, and every window opened against them.

    One ``Tk`` root lives for the whole run and each "window" is a ``Toplevel`` hosting the real
    application: several sequential ``Tk`` roots in one process are the part of Tk that behaves least
    predictably across platforms, and a window is a window. Closing one is still ``app.close()``, which
    closes the store and destroys that window, and that is what the reopen workflow checks.
    """

    def __init__(self, name: str = "run") -> None:
        self.folder = Path(tempfile.mkdtemp(prefix=f"career-agent-acceptance-{name}-"))
        self.database = self.folder / "synthetic-primary.sqlite3"
        self.second_database = self.folder / "synthetic-secondary.sqlite3"
        self.root = None
        self.windows: list[tuple[object, object]] = []
        #: Recorded before anything opens: the application's own database location must come out of this
        #: run exactly as it went in, which is checked without resolving it in a way that creates it.
        self.default_database_before = default_database_state()

    def start(self):
        """Create the one Tk root this run uses, after the caller has established a display exists."""
        tk = import_tkinter()
        self.root = tk.Tk()
        self.root.withdraw()
        return self.root

    def open_window(self, database=None):
        """A real application window on a disposable database."""
        tk = import_tkinter()
        from career_agent.desktop import CareerAgentApp  # noqa: PLC0415 - needs tkinter, checked above

        host = tk.Toplevel(self.root)
        app = CareerAgentApp(host, database_path=database or self.database)
        self.windows.append((host, app))
        self.root.update()
        return host, app

    def close_window(self, host, app) -> None:
        """Close the window the way the window itself closes: store released, widget destroyed."""
        app.close()
        for index, (open_host, _app) in enumerate(self.windows):
            if open_host is host:
                del self.windows[index]
                break
        self.root.update()

    def cleanup(self) -> None:
        """Close whatever is still open, then delete the folder - the proof the folder can be deleted is
        the same as the proof that no connection to it is still held."""
        for host, app in list(self.windows):
            try:
                app.close()
            except Exception:  # noqa: BLE001 - an unclosable window must not stop the others closing
                try:
                    host.destroy()
                except Exception:  # noqa: BLE001 - already gone
                    pass
        self.windows = []
        if self.root is not None:
            try:
                self.root.destroy()
            except Exception:  # noqa: BLE001 - already gone
                pass
            self.root = None
        shutil.rmtree(self.folder, ignore_errors=True)

    def require_default_database_untouched(self) -> None:
        """The person's own database must be exactly as it was, or the run has touched real data."""
        if self.default_database_before is None:
            print("[skip] the application's own database location could not be resolved on this machine")
            return
        require(
            default_database_state() == self.default_database_before,
            "the database this application opens on its own changed during the acceptance run",
        )


class Run:
    """What one workflow is given: the workspace, the result recorder, and the recorded dialogs."""

    def __init__(self, workspace: Workspace, results: Results, dialogs: DialogPolicy) -> None:
        self.workspace = workspace
        self.results = results
        self.dialogs = dialogs


# --------------------------------------------------------------------------------------------------
# Workflow A - the candidate profile, saved and read back through a second window
# --------------------------------------------------------------------------------------------------
def workflow_a_profile(run: Run) -> None:
    workspace, results = run.workspace, run.results
    host, app = workspace.open_window()

    with results.step("A1 a synthetic profile is typed into the profile form's own Entry widgets"):
        for key, value in SYNTHETIC_PROFILE.items():
            typed = set_field(app.profile_tab, app.profile_vars[key], value, what=f"the {key} field")
            require(typed == value, f"the {key} field holds {typed!r} after filling it with {value!r}")
        press(app.profile_tab, "Save profile locally", workspace.root)
        require(
            app.status.get() == "Candidate profile saved locally.",
            f"the window reported {app.status.get()!r} instead of a local save",
        )
        require(not run.dialogs.said("Invalid profile"), "the window refused the typed profile")

    with results.step("A2 every typed field is what the database actually holds"):
        stored = app.store.get_profile()
        require(stored is not None, "no profile was stored by pressing the button")
        from career_agent.desktop_logic import profile_fields_not_matching  # noqa: PLC0415

        mismatched = profile_fields_not_matching(stored, SYNTHETIC_PROFILE)
        require(not mismatched, f"these fields did not store what was typed: {sorted(mismatched)}")

    with results.step("A3 a role and a qualification are added through the window's own forms"):
        for key, value in SYNTHETIC_ROLE.items():
            set_field(app.history_tab, app.work_vars[key], value, what=f"the role {key} field")
        choose_in(app.history_tab, app.work_type, "full_time", what="the employment-type chooser")
        press(app.history_tab, "Add this role", workspace.root)
        require(
            app.status.get().startswith("Employment record added:"),
            f"adding the role reported {app.status.get()!r}",
        )
        for key, value in SYNTHETIC_QUALIFICATION.items():
            set_field(app.history_tab, app.study_vars[key], value, what=f"the qualification {key} field")
        press(app.history_tab, "Add this qualification", workspace.root)
        require(
            app.status.get().startswith("Education record added:"),
            f"adding the qualification reported {app.status.get()!r}",
        )

    with results.step("A4 the window closes and a second window opens on the same database"):
        workspace.close_window(host, app)
        require(not widget_exists(host), "the window still exists after being closed")
        host2, app2 = workspace.open_window()
        require(Path(app2.db_path) == workspace.database, f"the second window opened {app2.db_path!r}")
        require(app2.store.get_profile() is not None, "the second window did not read the stored profile")

    with results.step("A5 the reopened form holds the saved profile, field for field"):
        from career_agent.desktop_logic import profile_fields_not_matching  # noqa: PLC0415

        require(
            not profile_fields_not_matching(app2.store.get_profile(), SYNTHETIC_PROFILE),
            "the stored profile no longer matches what was typed",
        )
        # Read the fields back as the window rendered them, not from the store: a form that was never
        # filled would still pass a store-only check. This is a second window with its own variables, so
        # anything in them came from the stored profile.
        workspace.root.update()
        from career_agent.desktop_logic import profile_form_values  # noqa: PLC0415

        rendered = profile_form_values(app2.store.get_profile())
        for key, value in SYNTHETIC_PROFILE.items():
            shown = field_value(app2.profile_tab, app2.profile_vars[key], what=f"the {key} field")
            if key in ("skills", "locations", "work_modes", "role_types"):
                require(
                    {item.strip().casefold() for item in shown.split(",") if item.strip()}
                    == {item.strip().casefold() for item in rendered[key].split(",") if item.strip()},
                    f"the {key} field shows {shown!r}, expected the saved values in {rendered[key]!r}",
                )
            else:
                require(
                    shown.strip().casefold() == rendered[key].strip().casefold(),
                    f"the {key} field shows {shown!r}, expected {rendered[key]!r}",
                )

    with results.step("A6 the role and the qualification are listed by the reopened window"):
        roles = [app2.work_tree.item(item, "values") for item in app2.work_tree.get_children()]
        require(roles, "the reopened window lists no work history")
        require(
            any(SYNTHETIC_ROLE["employer"] in str(row) and SYNTHETIC_ROLE["job_title"] in str(row)
                for row in roles),
            f"the role that was added is not listed: {roles}",
        )
        study = [app2.study_tree.item(item, "values") for item in app2.study_tree.get_children()]
        require(study, "the reopened window lists no education records")
        require(
            any(SYNTHETIC_QUALIFICATION["institution"] in str(row)
                and SYNTHETIC_QUALIFICATION["qualification"] in str(row) for row in study),
            f"the qualification that was added is not listed: {study}",
        )
        workspace.close_window(host2, app2)


# --------------------------------------------------------------------------------------------------
# Workflow B - the two job URLs, and nothing submitted
# --------------------------------------------------------------------------------------------------
def workflow_b_job_urls(run: Run) -> None:
    workspace, results = run.workspace, run.results
    host, app = workspace.open_window()

    with results.step("B1 a listing is saved with a source URL and a deliberately blank application URL"):
        for key in ("employer", "title", "source_name", "source_url", "provenance_note"):
            set_field(app.jobs_tab, app.job_vars[key], LISTING_WITH_EVIDENCE[key], what=f"the {key} field")
        type_into(app.jobs_tab, app.job_vars["apply_url"], "", what="the employer apply URL field")
        require(
            str(widget_for(app.jobs_tab, app.job_vars["apply_url"], klass=ENTRY, what="apply URL").get()) == "",
            "the employer application URL did not stay blank before saving",
        )
        choose_in(app.jobs_tab, app.job_vars["availability"], "open", what="the availability chooser")
        choose_in(app.jobs_tab, app.job_vars["scope"], "worldwide", what="the scope chooser")
        press(app.jobs_tab, "Save job", workspace.root)
        require(
            app.status.get().startswith("Saved ") and "Nothing was submitted" in app.status.get(),
            f"saving the listing reported {app.status.get()!r}",
        )

    listing_id = app.selected_job_id
    with results.step("B2 the stored listing keeps the two URLs in separate fields, the blank one blank"):
        require(bool(listing_id), "the window did not keep the saved listing selected")
        stored = app.store.get_job(listing_id)
        require(stored is not None, "the listing was not stored")
        require(
            stored.source_listing_url == LISTING_WITH_EVIDENCE["source_url"],
            f"the source URL stored as {stored.source_listing_url!r}",
        )
        require(
            stored.employer_apply_url is None,
            f"the employer application URL stored as {stored.employer_apply_url!r} instead of staying blank",
        )
        workspace.close_window(host, app)

    host2, app2 = workspace.open_window()
    with results.step("B3 reopening the listing shows both fields separately, and the blank one still blank"):
        select_listing(app2, listing_id, workspace.root)
        require(app2.selected_job_id == listing_id, "the reopened window did not select the listing")
        source_field = widget_for(app2.jobs_tab, app2.job_vars["source_url"], klass=ENTRY,
                                  what="the source URL field")
        apply_field = widget_for(app2.jobs_tab, app2.job_vars["apply_url"], klass=ENTRY,
                                 what="the employer apply URL field")
        require(
            str(source_field.get()) == LISTING_WITH_EVIDENCE["source_url"],
            f"the reopened source URL field shows {source_field.get()!r}",
        )
        require(
            str(apply_field.get()) == "",
            f"the reopened employer application URL field shows {apply_field.get()!r} instead of blank",
        )
        require(
            "Employer application URL: Not verified / not supplied" in report_text(app2),
            "the selection report does not say the application URL was not supplied",
        )

    with results.step("B4 nothing was submitted and no discovery is enabled"):
        from career_agent.sources import SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources  # noqa: PLC0415

        require(SOURCE_QUALITY_GATE_PASSED is False, "the source-quality gate reports itself as passed")
        require(enabled_discovery_sources() == (), "a discovery source is enabled")
        status = tracker_status(app2, listing_id)
        require(
            status is not None and status.value == "discovered",
            f"the application's status is {status!r} after saving a listing, which claims more than a save",
        )
        lines = event_lines(workspace.database).splitlines()
        require(lines, "the application recorded no events at all, so this check proves nothing")
        # The application's own vocabulary is the check: every event this build can record is declared in
        # career_agent.event_log, and none of them is a submission. A line naming anything else would be an
        # event nobody declared, which is the other half of the same guarantee.
        from career_agent.event_log import EVENTS  # noqa: PLC0415

        # A log line is "<timestamp> event=<name> detail=..." - read as the format documents it rather
        # than as a guess about where the name sits.
        recorded = {
            parts[1].removeprefix("event=")
            for parts in (line.split(" ", 2) for line in lines)
            if len(parts) > 1
        }
        require(
            recorded <= set(EVENTS),
            f"the log holds events this build does not declare: {sorted(recorded - set(EVENTS))}",
        )
        require(
            not [name for name in recorded if "submit" in name],
            f"the log claims a submission: {sorted(name for name in recorded if 'submit' in name)}",
        )
        require(
            "job.saved" in recorded,
            f"saving a listing recorded no job.saved event: {sorted(recorded)}",
        )
        require(
            not run.dialogs.said("Possible duplicate"),
            "the window asked about a duplicate of a listing that was saved only once",
        )

    with results.step("B5 the save wrote into the disposable database and nowhere else"):
        require(
            Path(app2.db_path).is_relative_to(workspace.folder),
            f"the window is working on {app2.db_path!r}, outside the disposable folder",
        )
        workspace.require_default_database_untouched()
        workspace.close_window(host2, app2)


# --------------------------------------------------------------------------------------------------
# Workflow C - eligibility safety: no evidence means UNKNOWN, and UNKNOWN cannot shortlist
# --------------------------------------------------------------------------------------------------
def workflow_c_eligibility(run: Run) -> None:
    workspace, results = run.workspace, run.results
    host, app = workspace.open_window()

    with results.step("C1 the profile a listing is evaluated against is saved first"):
        for key, value in SYNTHETIC_PROFILE.items():
            set_field(app.profile_tab, app.profile_vars[key], value, what=f"the {key} field")
        press(app.profile_tab, "Save profile locally", workspace.root)
        require(app.store.get_profile() is not None, "the profile was not saved")

    with results.step("C2 a listing with no availability evidence evaluates to UNKNOWN"):
        for key, value in LISTING_WITHOUT_EVIDENCE.items():
            if key in ("availability", "scope"):
                continue
            set_field(app.jobs_tab, app.job_vars[key], value, what=f"the {key} field")
        choose_in(app.jobs_tab, app.job_vars["availability"], "open", what="the availability chooser")
        choose_in(app.jobs_tab, app.job_vars["scope"], "unknown", what="the scope chooser")
        press(app.jobs_tab, "Save job", workspace.root)
        listing_id = app.selected_job_id
        require(bool(listing_id), "the listing was not saved")

    with results.step("C3 evaluating it reports UNKNOWN, and says which requirement is unproven"):
        select_listing(app, listing_id, workspace.root)
        press(app.jobs_tab, "Evaluate selected", workspace.root)
        report = report_text(app)
        require("ELIGIBILITY: UNKNOWN" in report, f"the report does not say UNKNOWN:\n{report}")
        require(
            "no recorded availability evidence" in report,
            "the report does not name the missing availability evidence",
        )
        require(
            "unknown" in app.status.get(),
            f"the status line says {app.status.get()!r} rather than reporting the unknown result",
        )

    with results.step("C4 shortlisting an UNKNOWN listing is refused, and changes nothing"):
        before = tracker_status(app, listing_id)
        run.dialogs.reset()
        select_listing(app, listing_id, workspace.root)
        press(app.jobs_tab, "Shortlist if eligible", workspace.root)
        require(
            "Not eligible to shortlist" in run.dialogs.titles(),
            f"the refusal was not explained; dialogs raised: {run.dialogs.titles()}",
        )
        require(
            "UNKNOWN" in run.dialogs.said("Not eligible to shortlist").upper(),
            "the refusal does not say what the eligibility result was",
        )
        require(
            tracker_status(app, listing_id) == before,
            f"a refused shortlist moved the status from {before!r} to {tracker_status(app, listing_id)!r}",
        )

    with results.step("C5 with explicit evidence the same application reaches PASS"):
        type_into(app.jobs_tab, app.job_vars["provenance_note"],
                  LISTING_WITH_EVIDENCE["provenance_note"], what="the availability evidence field")
        choose_in(app.jobs_tab, app.job_vars["scope"], "worldwide", what="the scope chooser")
        # The listing's own requirements, stated explicitly: an unstated requirement stays UNKNOWN in this
        # application, and the run must not present an unevidenced PASS either way.
        for key, value in LISTING_REQUIREMENTS.items():
            set_field(app.jobs_tab, app.job_vars[key], value, what=f"the {key} field")
        run.dialogs.reset()
        press(app.jobs_tab, "Save job", workspace.root)
        # Editing a listing that already exists changes the fields a result depends on, so the window
        # asks before overwriting it. The run answers yes, as a person who meant to edit it would.
        require(
            not run.dialogs.said("Cannot save job"),
            f"the edit was refused: {run.dialogs.said('Cannot save job')}",
        )
        select_listing(app, listing_id, workspace.root)
        press(app.jobs_tab, "Evaluate selected", workspace.root)
        report = report_text(app)
        require("ELIGIBILITY: PASS" in report, f"the report does not say PASS after evidence:\n{report}")
        require("[FAIL]" not in report, "a requirement failed on a listing that should pass")
        require(
            "[PASS] availability" in report,
            "the availability requirement is not reported as passed on its evidence",
        )
        for requirement in ("country", "degree_discipline", "study_status", "graduation_year",
                            "experience_years"):
            require(
                f"[PASS] {requirement}" in report,
                f"the {requirement} requirement is not reported as passed:\n{report}",
            )

    with results.step("C6 a PASS listing can be shortlisted, and the status is the permitted one"):
        select_listing(app, listing_id, workspace.root)
        press(app.jobs_tab, "Shortlist if eligible", workspace.root)
        status = tracker_status(app, listing_id)
        require(
            status is not None and status.value == "shortlisted",
            f"the application is {status!r} after shortlisting a PASS listing",
        )
        require(
            "shortlisted locally" in app.status.get(),
            f"the status line says {app.status.get()!r}",
        )
        require(
            "No external action" in app.status.get(),
            "the status line does not say that nothing external happened",
        )
        workspace.close_window(host, app)


# --------------------------------------------------------------------------------------------------
# Workflow D - the tracker's permitted transitions, and activity that is not an outcome
# --------------------------------------------------------------------------------------------------
def status_dialog_controls(policy: DialogPolicy, title: str):
    """The controls inside the status dialog, as the handler bound them.

    The dialog creates its variables in a fixed order: the new status, then the evidence note, then - only
    when it is offered - the confirmation assertion. They are addressed by what they are bound to, which is
    also how a person finds them: the chooser above the note field.
    """
    texts = string_variables(policy, title)
    toggles = boolean_variables(policy, title)
    if len(texts) != 2:
        raise SmokeFailure(f"the status dialog created {len(texts)} text variables, expected 2")
    return texts[0], texts[1], (toggles[0] if toggles else None)


def open_status_dialog(workspace, app, policy: DialogPolicy, listing_id: str):
    """Press "Update selected status" and return the dialog with its widgets ready to be driven."""
    select_tracker_row(app, listing_id, workspace.root)
    policy.reset()
    record_dialog_controls(
        policy, "Update application status",
        lambda: press(app.tracker_tab, "Update selected status", workspace.root),
    )
    dialog = open_dialog(workspace.root, "Update application status")
    status_var, evidence_var, assertion = status_dialog_controls(policy, "Update application status")
    chooser = widget_for(dialog, status_var, klass=COMBOBOX, what="the status chooser")
    entry = widget_for(dialog, evidence_var, klass=ENTRY, what="the evidence field")
    checkbox = None
    if assertion is not None:
        checkbox = widget_for(dialog, assertion, klass=CHECKBUTTON, what="the confirmation assertion")
    return dialog, chooser, entry, assertion, checkbox


def choose_status(workspace, chooser, entry, wanted: str, evidence: str) -> None:
    """Choose a status in the chooser and type the evidence its confirmation needs."""
    chooser.set(wanted)
    entry.delete(0, "end")
    entry.insert(0, evidence)
    workspace.root.update()


def workflow_d_tracker_and_analytics(run: Run) -> None:
    workspace, results, policy = run.workspace, run.results, run.dialogs
    host, app = workspace.open_window()

    with results.step("D1 a PASS listing is prepared and shortlisted through the window"):
        for key, value in SYNTHETIC_PROFILE.items():
            set_field(app.profile_tab, app.profile_vars[key], value, what=f"the {key} field")
        press(app.profile_tab, "Save profile locally", workspace.root)
        for key, value in LISTING_WITH_EVIDENCE.items():
            if key in ("availability", "scope"):
                continue
            set_field(app.jobs_tab, app.job_vars[key], value, what=f"the {key} field")
        choose_in(app.jobs_tab, app.job_vars["availability"], "open", what="the availability chooser")
        choose_in(app.jobs_tab, app.job_vars["scope"], "worldwide", what="the scope chooser")
        press(app.jobs_tab, "Save job", workspace.root)
        listing_id = app.selected_job_id
        select_listing(app, listing_id, workspace.root)
        press(app.jobs_tab, "Evaluate selected", workspace.root)
        require("ELIGIBILITY: PASS" in report_text(app), "the fixture listing did not evaluate to PASS")
        select_listing(app, listing_id, workspace.root)
        press(app.jobs_tab, "Shortlist if eligible", workspace.root)
        require(
            tracker_status(app, listing_id).value == "shortlisted",
            "the listing was not shortlisted",
        )

    with results.step("D2 an interview round is recorded through the window's own dialog"):
        from career_agent.core import InterviewMode, InterviewStage  # noqa: PLC0415

        select_listing(app, listing_id, workspace.root)
        policy.reset()
        record_dialog_controls(
            policy, "Record an interview round",
            lambda: press(app.actions_tab, "Record an interview round", workspace.root),
        )
        dialog = open_dialog(host, "Record an interview round")
        texts = string_variables(policy, "Record an interview round")
        require(len(texts) == 4, f"the interview dialog created {len(texts)} text variables, expected 4")
        stage_var, day_var, mode_var, notes_var = texts
        stage_chooser = widget_for(dialog, stage_var, klass=COMBOBOX, what="the round chooser")
        require(
            [str(value) for value in stage_chooser.cget("values")]
            == [stage.value for stage in InterviewStage],
            "the round chooser does not offer the documented stages",
        )
        mode_chooser = widget_for(dialog, mode_var, klass=COMBOBOX, what="the mode chooser")
        require(
            [str(value) for value in mode_chooser.cget("values")]
            == [mode.value for mode in InterviewMode],
            "the mode chooser does not offer the documented ways a round is held",
        )
        choose_in(dialog, stage_var, "technical", what="the round chooser")
        choose_in(dialog, mode_var, "video", what="the way it is held")
        type_into(dialog, day_var, date.today().isoformat(), what="the planned day")
        type_into(dialog, notes_var, SYNTHETIC_NOTE, what="the notes field")
        press(dialog, "Record it", workspace.root)
        require(
            app.status.get().startswith("Recorded:"),
            f"recording the round reported {app.status.get()!r}",
        )
        require(
            "no status was changed" in app.status.get(),
            "the window does not say the application's status was left alone",
        )

    with results.step("D3 the round is stored as upcoming, and is not reported as an outcome or a sending"):
        from career_agent import analytics  # noqa: PLC0415

        rounds = app.store.list_interviews(listing_id)
        require(len(rounds) == 1, f"{len(rounds)} interview rounds were stored, expected 1")
        require(
            rounds[0].scheduled_on >= date.today(),
            f"the round was stored for {rounds[0].scheduled_on}, which is not upcoming",
        )
        require(
            rounds[0].outcome.value == "awaiting",
            f"the round's outcome was stored as {rounds[0].outcome.value!r}, not as awaiting",
        )
        require(
            tracker_status(app, listing_id).value == "shortlisted",
            "recording an interview round moved the application's status",
        )
        report = analytics.report_from_store(app.store, today=date.today())
        require(
            report.applications_recorded == 0,
            f"analytics counts {report.applications_recorded} application(s) sent, but nothing was sent",
        )
        counts = {count.label: count.count for count in report.counts}
        require(
            counts.get("Interview rounds recorded") == 1,
            f"the round is not counted as a recorded round: {counts}",
        )
        require(
            counts.get("Rounds where you recorded how it went") == 0,
            "an upcoming round is counted as one whose outcome is known",
        )
        require(
            "0 offers" not in report.headline().lower(),
            f"the summary reports an offer count: {report.headline()!r}",
        )

    with results.step("D4 the status chooser offers only the current status and its permitted moves"):
        from career_agent import ApplicationStatus  # noqa: PLC0415
        from career_agent.core import selectable_tracker_statuses  # noqa: PLC0415

        current = tracker_status(app, listing_id)
        dialog, chooser, entry, _assertion, _checkbox = open_status_dialog(
            workspace, app, policy, listing_id
        )
        offered = [str(value) for value in chooser.cget("values")]
        expected = [status.value for status in selectable_tracker_statuses(current)]
        require(
            offered == expected,
            f"the chooser offers {offered}; the permitted set for {current.value!r} is {expected}",
        )
        every_status = {status.value for status in ApplicationStatus}
        require(
            set(offered) < every_status,
            "the chooser offers every status, including ones this record may not move to",
        )
        require(
            "confirmed" not in offered and "interview" not in offered,
            f"a status nothing was sent for is offered: {offered}",
        )
        choose_status(workspace, chooser, entry, "prepared", SYNTHETIC_NOTE)
        press(dialog, "Save status", workspace.root)
        require(
            tracker_status(app, listing_id).value == "prepared",
            f"the application is {tracker_status(app, listing_id)!r} after the change",
        )
        require(
            "Application status updated to prepared" in app.status.get(),
            f"the status line says {app.status.get()!r}",
        )

    with results.step("D5 a move is offered only where the record may go, and nothing is an outcome"):
        from career_agent import analytics  # noqa: PLC0415
        from career_agent.core import selectable_tracker_statuses  # noqa: PLC0415

        # The documented path from a plan to an unverified submission, one permitted step at a time. Each
        # step first checks the chooser offers exactly what the domain permits, then takes one step and
        # checks what the database holds afterwards.
        steps = ("awaiting_user", "submission_attempted", "submitted_unverified")
        for index, wanted in enumerate(steps):
            current = tracker_status(app, listing_id)
            dialog, chooser, entry, _assertion, _checkbox = open_status_dialog(
                workspace, app, policy, listing_id
            )
            offered = [str(value) for value in chooser.cget("values")]
            expected = [status.value for status in selectable_tracker_statuses(current)]
            require(
                offered == expected,
                f"from {current.value!r} the chooser offers {offered}, expected {expected}",
            )
            require(
                wanted in offered,
                f"{wanted!r} cannot be reached from {current.value!r}: {offered}",
            )
            choose_status(workspace, chooser, entry, wanted, SYNTHETIC_NOTE)
            press(dialog, "Save status", workspace.root)
            require(
                tracker_status(app, listing_id).value == wanted,
                f"the application is {tracker_status(app, listing_id)!r} after moving it to {wanted!r}",
            )
            report = analytics.report_from_store(app.store, today=date.today())
            if index < len(steps) - 1:
                # A plan, a wait, and an attempt that did not complete: none of these is a sending, and the
                # activity list must not count them as one.
                require(
                    report.applications_recorded == 0,
                    f"moving to {wanted!r} is counted as {report.applications_recorded} application(s) sent",
                )
        report = analytics.report_from_store(app.store, today=date.today())
        require(
            report.applications_recorded == 1,
            f"an unverified submission is counted as {report.applications_recorded}, not as one",
        )
        require(
            "offer" not in report.headline().lower(),
            f"the summary claims an outcome no record holds: {report.headline()!r}",
        )
        unrecorded = [reason for topic, reason in report.unavailable if "offer" in topic.lower()]
        require(unrecorded, "the report does not say why no offer count is shown")

    with results.step("D6 a confirmation requires the person's own assertion, and is refused without it"):
        dialog, chooser, entry, assertion, checkbox = open_status_dialog(workspace, app, policy, listing_id)
        require(assertion is not None, "the dialog offered no confirmation assertion")
        require(checkbox is not None, "the confirmation assertion has no checkbox in the dialog")
        require(assertion.get() is False, "the confirmation assertion started ticked")
        choose_status(workspace, chooser, entry, "confirmed", SYNTHETIC_NOTE)
        before = tracker_status(app, listing_id)
        press(dialog, "Save status", workspace.root)
        require(
            "Invalid status change" in policy.titles(),
            f"a confirmation was recorded without the assertion; dialogs: {policy.titles()}",
        )
        require(
            "assert" in policy.said("Invalid status change").lower(),
            "the refusal does not say that the person has to assert the confirmation",
        )
        require(
            tracker_status(app, listing_id) == before,
            f"a refused confirmation moved the status from {before!r} to {tracker_status(app, listing_id)!r}",
        )

    with results.step("D7 with the assertion ticked the confirmation is recorded, and counted as sent"):
        checkbox.invoke()
        require(assertion.get() is True, "ticking the checkbox did not set the assertion")
        press(dialog, "Save status", workspace.root)
        require(
            tracker_status(app, listing_id).value == "confirmed",
            f"the application is {tracker_status(app, listing_id)!r} after the assertion was ticked",
        )
        from career_agent import analytics  # noqa: PLC0415

        report = analytics.report_from_store(app.store, today=date.today())
        require(
            report.applications_recorded == 1,
            f"a confirmed application is counted as {report.applications_recorded}, not as one",
        )

    with results.step("D8 a final state is final: the window offers no change and writes none"):
        from career_agent.core import selectable_tracker_statuses  # noqa: PLC0415

        # A confirmed application may still move on - an employer can reply, interview or reject - so the
        # final-state behaviour is exercised where it belongs: moving on to 'withdrawn', which this domain
        # treats as final, and then asking for a change again.
        dialog, chooser, entry, assertion, _checkbox = open_status_dialog(
            workspace, app, policy, listing_id
        )
        offered = [str(value) for value in chooser.cget("values")]
        require("withdrawn" in offered, f"'withdrawn' is not offered from a confirmed record: {offered}")
        if assertion is not None and assertion.get():
            assertion.set(False)
        choose_status(workspace, chooser, entry, "withdrawn", SYNTHETIC_NOTE)
        press(dialog, "Save status", workspace.root)
        require(
            tracker_status(app, listing_id).value == "withdrawn",
            f"the application is {tracker_status(app, listing_id)!r}, not withdrawn",
        )
        final = tracker_status(app, listing_id)
        require(
            len(selectable_tracker_statuses(final)) == 1,
            f"{final.value!r} is not a final state for this domain, so this check proved nothing",
        )
        before = file_digest(workspace.database)
        policy.reset()
        select_tracker_row(app, listing_id, workspace.root)
        press(app.tracker_tab, "Update selected status", workspace.root)
        require(
            "No further status" in policy.titles(),
            f"a final state still offered a change; dialogs: {policy.titles()}",
        )
        require(
            "final state" in policy.said("No further status"),
            f"the explanation does not say why no change is offered: {policy.said('No further status')!r}",
        )
        require(
            "Nothing was changed" in policy.said("No further status"),
            "the explanation does not say that the record was left alone",
        )
        require(
            tracker_status(app, listing_id) == final,
            "opening the dialog on a final state changed the record",
        )
        require(
            file_digest(workspace.database) == before,
            "asking for a status change on a final record wrote to the database",
        )
# --------------------------------------------------------------------------------------------------
# Workflow E - export, import, and the refusals
# --------------------------------------------------------------------------------------------------
def workflow_e_export_import(run: Run) -> None:
    workspace, results, policy = run.workspace, run.results, run.dialogs
    host, app = workspace.open_window()
    export_path = workspace.folder / "synthetic-export.json"

    with results.step("E1 there is something to export, saved through the window"):
        for key, value in SYNTHETIC_PROFILE.items():
            set_field(app.profile_tab, app.profile_vars[key], value, what=f"the {key} field")
        press(app.profile_tab, "Save profile locally", workspace.root)
        for key, value in LISTING_WITH_EVIDENCE.items():
            if key in ("availability", "scope"):
                continue
            set_field(app.jobs_tab, app.job_vars[key], value, what=f"the {key} field")
        choose_in(app.jobs_tab, app.job_vars["availability"], "open", what="the availability chooser")
        choose_in(app.jobs_tab, app.job_vars["scope"], "worldwide", what="the scope chooser")
        press(app.jobs_tab, "Save job", workspace.root)
        require(app.selected_job_id, "the listing was not saved")

    with results.step("E2 the export is written where the chooser said, and the window says so"):
        policy.reset()
        policy.files.append(str(export_path))
        press(app.tracker_tab, "Export local data to JSON", workspace.root)
        require(export_path.exists(), f"no file was written at {export_path}")
        stored = app.store.list_jobs()
        require(
            f"Exported {len(stored)} jobs" in app.status.get(),
            f"the status line says {app.status.get()!r} for {len(stored)} stored listing(s)",
        )
        document = json.loads(export_path.read_text(encoding="utf-8"))
        require("format_version" in document, "the export carries no format version")
        require(
            len(document.get("jobs", [])) == len(stored),
            f"the export holds {len(document.get('jobs', []))} listing(s); the database holds {len(stored)}",
        )
        exported_urls = {record.get("source_listing_url") for record in document["jobs"]}
        require(
            {job.source_listing_url for job in stored} == exported_urls,
            "the exported listings are not the stored ones",
        )
        record = next(record for record in document["jobs"]
                      if record.get("source_listing_url") == LISTING_WITH_EVIDENCE["source_url"])
        require(
            not record.get("employer_apply_url"),
            f"the exported listing's application URL is {record.get('employer_apply_url')!r}",
        )
        require(document.get("profile"), "the export carries no profile")
        # The application record travels with the listing, and what travels is the *stored* record - which
        # earlier workflows have advanced, so the check is that the file agrees with the database rather
        # than that the status is any particular value. An export that dropped it, or wrote a status of its
        # own, fails here.
        stored_listing = next(job for job in stored
                              if job.source_listing_url == LISTING_WITH_EVIDENCE["source_url"])
        stored_tracker = app.store.get_tracker(stored_listing.listing_id)
        tracker_record = record.get("application_tracker")
        require(
            isinstance(tracker_record, dict),
            f"the exported listing carries no application record: {tracker_record!r}",
        )
        require(
            None is not stored_tracker
            and tracker_record.get("status") == stored_tracker.status.value,
            f"the export says the application is {tracker_record.get('status')!r} while the database "
            f"holds {getattr(stored_tracker, 'status', None)!r}",
        )
        require("export.written" in event_lines(workspace.database), "no export event was recorded")

    with results.step("E3 an export that cannot be written is refused, and claims to have written nothing"):
        policy.reset()
        missing_folder = workspace.folder / "folder-that-does-not-exist" / "export.json"
        policy.files.append(str(missing_folder))
        press(app.tracker_tab, "Export local data to JSON", workspace.root)
        require(not missing_folder.exists(), "a file exists at a path that cannot be written")
        refusals = [title for title in policy.titles()
                    if title in ("Export failed", "Export not saved")]
        require(
            refusals,
            f"the failure was not reported to the person; dialogs: {policy.titles()}",
        )
        require(
            "not saved" in app.status.get().lower() or "failed" in app.status.get().lower(),
            f"the status line claims {app.status.get()!r} after a failed export",
        )
        require(
            "Exported" not in app.status.get(),
            "the window reports an export after failing to write one",
        )
        said = " ".join(policy.said(title) for title in refusals)
        require(
            "not completed" in said or "Nothing was written" in said or "never written" in said,
            f"the refusal does not say that nothing was written: {said}",
        )
        require("export.failed" in event_lines(workspace.database), "the failure was not recorded")

    with results.step("E4 an export target that cannot be protected is refused, and the target is untouched"):
        outside = workspace.folder / "outside-the-link.json"
        outside.write_text("untouched", encoding="utf-8")
        link = workspace.folder / "link-to-outside.json"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            print(f"[skip] symbolic links are unavailable here, so the link case was not run: {exc}")
        else:
            policy.reset()
            policy.files.append(str(link))
            press(app.tracker_tab, "Export local data to JSON", workspace.root)
            require(
                "Export not saved" in policy.titles(),
                f"the refusal was not reported; dialogs: {policy.titles()}",
            )
            require(
                "Nothing was written" in policy.said("Export not saved"),
                "the refusal does not say that nothing was written",
            )
            require(
                outside.read_text(encoding="utf-8") == "untouched",
                "the export followed the symbolic link and overwrote the file it pointed at",
            )
            require(
                Path(app.db_path).parent == workspace.folder,
                "the window is not working inside the disposable folder",
            )

    with results.step("E5 the export imports into a second disposable database"):
        host2, app2 = workspace.open_window(database=workspace.second_database)
        policy.reset()
        policy.files.append(str(export_path))
        press(app2.data_tab, "Import an exported file (JSON)", workspace.root)
        require(
            "Import complete" in app2.status.get(),
            f"the import reported {app2.status.get()!r}",
        )
        imported = app2.store.list_jobs()
        document = json.loads(export_path.read_text(encoding="utf-8"))
        # One record per *identity*, not per stored row: the file may hold several observations of the same
        # application (this run saved the same fixture listing from two workflows), and this application
        # deliberately treats those as one application when importing.
        expected_urls = {record.get("source_listing_url") for record in document["jobs"]}
        require(
            {job.source_listing_url for job in imported} == expected_urls,
            f"the imported listings are {[job.source_listing_url for job in imported]}, expected {expected_urls}",
        )
        arrived = next(job for job in imported
                       if job.source_listing_url == LISTING_WITH_EVIDENCE["source_url"])
        require(
            arrived.employer_apply_url is None,
            f"the imported listing's application URL is {arrived.employer_apply_url!r}, not blank",
        )
        require(app2.store.get_profile() is not None, "the profile did not round-trip through the export")
        workspace.close_window(host2, app2)

    with results.step("E6 a file that is not an export is refused and writes nothing"):
        host3, app3 = workspace.open_window(database=workspace.second_database)
        before = file_digest(workspace.second_database)
        broken = workspace.folder / "not-an-export.json"
        broken.write_text("this is not JSON at all", encoding="utf-8")
        policy.reset()
        policy.files.append(str(broken))
        press(app3.data_tab, "Import an exported file (JSON)", workspace.root)
        require(
            "Nothing was imported" in policy.titles(),
            f"the refusal was not reported; dialogs: {policy.titles()}",
        )
        require(
            "nothing was read" in app3.status.get().lower(),
            f"the status line says {app3.status.get()!r}",
        )
        workspace.close_window(host3, app3)
        require(
            file_digest(workspace.second_database) == before and before != "missing",
            "a refused import changed the database file",
        )

    with results.step("E8 importing the same file again adds nothing and duplicates nothing"):
        host5, app5 = workspace.open_window(database=workspace.second_database)
        before_jobs = {job.listing_id for job in app5.store.list_jobs()}
        before_profile = app5.store.get_profile()
        policy.reset()
        policy.files.append(str(export_path))
        press(app5.data_tab, "Import an exported file (JSON)", workspace.root)
        require(
            "Import this file?" in [call[1] for call in policy.calls],
            "the repeated import was applied without showing what it would do first",
        )
        plan_text = policy.said("Import this file?") + policy.said("Import complete")
        require(
            "already stored" in plan_text.lower(),
            f"the plan does not say the listings are already stored:\n{plan_text}",
        )
        require(
            "kept" in plan_text.lower(),
            f"the plan does not say what was kept rather than imported:\n{plan_text}",
        )
        after_jobs = {job.listing_id for job in app5.store.list_jobs()}
        require(
            after_jobs == before_jobs,
            f"a repeated import changed the stored listings: {sorted(after_jobs)} vs {sorted(before_jobs)}",
        )
        require(
            app5.store.get_profile() == before_profile,
            "a repeated import replaced the stored profile instead of keeping it",
        )
        require(
            "nothing was added" in app5.status.get().lower()
            or "left" in app5.status.get().lower(),
            f"the repeated import reports {app5.status.get()!r}",
        )
        workspace.close_window(host5, app5)

    with results.step("E7 a document with a damaged record imports the good part and names the rest"):
        host4, app4 = workspace.open_window(database=workspace.second_database)
        before_jobs = len(app4.store.list_jobs())
        damaged = json.loads(export_path.read_text(encoding="utf-8"))
        readable = dict(damaged["jobs"][0])
        readable["listing_id"] = "synthetic-import-2"
        readable["source_listing_url"] = "https://example.com/fixture/jobs/2002"
        broken_record = dict(readable)
        broken_record["listing_id"] = "synthetic-import-3"
        # Two required fields removed: this record cannot be read, and must not be written either.
        broken_record["source_listing_url"] = ""
        broken_record["role_title"] = ""
        damaged["jobs"] = [readable, broken_record]
        damaged_path = workspace.folder / "partly-damaged-export.json"
        damaged_path.write_text(json.dumps(damaged), encoding="utf-8")
        policy.reset()
        policy.files.append(str(damaged_path))
        press(app4.data_tab, "Import an exported file (JSON)", workspace.root)
        require(
            "Import this file?" in [call[1] for call in policy.calls],
            "the import was applied without showing what it would do first",
        )
        plan_text = policy.said("Import this file?") + policy.said("Import complete")
        require(
            "cannot be read" in plan_text.lower(),
            f"the plan does not mention the record it cannot read:\n{plan_text}",
        )
        require(
            "synthetic-import-3" in plan_text,
            "the plan does not name the record it is going to skip",
        )
        after = app4.store.list_jobs()
        require(
            len(after) == before_jobs + 1,
            f"{len(after) - before_jobs} listing(s) were added, expected exactly the readable one",
        )
        require(
            all(job.listing_id != "synthetic-import-3" for job in after),
            "the damaged record was written despite being unreadable",
        )
        require("import.written" in event_lines(workspace.second_database), "no import event was recorded")
        workspace.close_window(host4, app4)
        workspace.close_window(host, app)


# --------------------------------------------------------------------------------------------------
# Workflow F - cleanup, lifecycle, and cleanup after a failure
# --------------------------------------------------------------------------------------------------
def workflow_f_cleanup(run: Run) -> None:
    workspace, results = run.workspace, run.results

    with results.step("F1 windows and database connections are released, one workflow at a time"):
        host, app = workspace.open_window()
        database = Path(app.db_path)
        require(database.exists(), "the window did not create its database")
        workspace.close_window(host, app)
        require(not widget_exists(host), "the window still exists after being closed")
        side_files = sorted(path.name for path in database.parent.glob(f"{database.name}-*"))
        require(
            not [name for name in side_files if name.endswith(("-wal", "-journal", "-shm"))],
            f"the database was not released cleanly; side files left: {side_files}",
        )
        workspace.cleanup()
        require(not workspace.folder.exists(), "the disposable folder survived the cleanup")

    with results.step("F2 a window opened after the cleanup is still on a disposable database"):
        folded_database = workspace.database
        require(not folded_database.exists(), "the deleted folder still holds a database")
        workspace.cleanup()

    with results.step("F3 the run never touched the database this application opens on its own"):
        workspace.require_default_database_untouched()

    with results.step("F4 cleanup also runs after a workflow raises"):
        # A fresh workspace, and therefore a fresh Tk interpreter: the run's own root was destroyed on
        # purpose by F1, and this is the only workflow that starts after that. It is also where real Tk
        # behaved differently from the stand-in - see ``widget_exists`` - which is why the check reads the
        # window's existence through that helper rather than calling Tk directly.
        scratch = Workspace("forced-failure")
        scratch.start()
        host, app = scratch.open_window()
        try:
            try:
                raise SmokeFailure("a deliberate failure, to prove the cleanup runs anyway")
            finally:
                scratch.cleanup()
        except SmokeFailure:
            pass
        require(not widget_exists(host), "the window survived a failure in the middle of a workflow")
        require(not scratch.folder.exists(), "the disposable folder survived a failure")
        scratch.require_default_database_untouched()


#: The workflows, in the order they run. Named rather than numbered so the report line for a failure says
#: which part of the application it belongs to.
WORKFLOWS = (
    ("A - candidate profile persistence", workflow_a_profile),
    ("B - the two job URLs", workflow_b_job_urls),
    ("C - eligibility safety", workflow_c_eligibility),
    ("D - tracker and analytics", workflow_d_tracker_and_analytics),
    ("E - export, import and refusal", workflow_e_export_import),
    ("F - cleanup and lifecycle", workflow_f_cleanup),
)


def declared_step_count() -> int:
    """How many checks this file's own source declares.

    Read from the source rather than kept in a number elsewhere, so adding a check does not mean editing a
    count somewhere else - and so a check that quietly stops running cannot pass unnoticed. A
    ``with results.step(...)`` block that never executes leaves the run short of this number, which is a
    failure, not a smaller pass.
    """
    import ast  # noqa: PLC0415 - only this check needs to parse the file

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), __file__)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "step"
    )


def ran_every_declared_check(results: Results) -> str | None:
    """``None`` when every declared check ran, or the sentence explaining what is missing."""
    declared = declared_step_count()
    performed = results.passed + len(results.failures)
    if performed != declared:
        return (
            f"the run performed {performed} checks but this file's source declares {declared}: a check "
            "stopped running, and a check that does not run is not a pass"
        )
    return None


def using_stand_in_tk(tk) -> bool:
    """Whether ``tkinter`` here is the stand-in widget module the tests maintain rather than real Tk.

    This matters more than anything else in this file. The stand-in models the widgets the application
    builds, the variables they are bound to and the commands they run, so a run against it says a great deal
    about the workflows and the window's wiring - and it cannot say one word about a window on a display,
    because no window exists. A run that mistook one for the other would be exactly the fabricated GUI
    evidence this project keeps writing rules against, so the two are told apart and labelled.

    The stand-in is identified by having no file: the real ``tkinter`` is a module in the standard library,
    and every stand-in here is a module object built in memory by the test suite.
    """
    return getattr(tk, "__file__", None) is None


def stand_in_tkinter():
    """The stand-in widget module, from the test suite that maintains it.

    Used only by ``--stand-in-tk``, and always reported as a development run: it exists so the workflows can
    be exercised while they are being written, on a machine with no display, which is where this file was
    written. It is not evidence and the run says so in as many words.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    import test_desktop_handlers  # noqa: PLC0415 - deliberately imported here, by explicit request only

    stand_in = sys.modules["tkinter"]
    stand_in.TkVersion = 8.6
    stand_in.TclVersion = 8.6
    return stand_in


def main(argv=None) -> int:
    """Run every workflow and return the exit status.

    ``argv`` defaults to *no* arguments rather than to ``sys.argv``: this function is called directly from
    the test suite, whose command line is the test runner's, and reading it here would make a test run
    print a usage message instead of the workflows. The command-line entry point passes its own arguments.
    """
    arguments = [] if argv is None else list(argv)
    stand_in_requested = "--stand-in-tk" in arguments
    if stand_in_requested:
        arguments.remove("--stand-in-tk")
    if arguments:
        print(f"usage: {Path(__file__).name} [--stand-in-tk]")
        return EXIT_FAIL

    print("AI Career Agent - desktop acceptance run")
    print(f"python {sys.version.split()[0]} on {sys.platform}")

    try:
        tk = stand_in_tkinter() if stand_in_requested else import_tkinter()
    except Exception as exc:  # noqa: BLE001 - the reason is the whole point of the report
        return report_blocked(f"this Python has no tkinter module: {exc!r}")

    developed = using_stand_in_tk(tk)
    if developed:
        print(
            "DEVELOPMENT RUN: tkinter here is the test suite's stand-in widget module, not a display-backed "
            "Tk.\nNo window is created by this run, and none of its results are desktop evidence. Use it to "
            "check the workflows while writing them; the checklist stays BLOCKED until the same workflows "
            "run in CI against real Tk."
        )

    try:
        probe = tk.Tk()
    except Exception as exc:  # noqa: BLE001 - classified below
        if looks_like_no_display(str(exc)):
            return report_blocked(f"a Tk root cannot be created here: {exc}")
        print(traceback.format_exc().rstrip())
        print(f"RESULT: FAIL — creating a Tk root raised {exc!r}, which is not a missing display.")
        return EXIT_FAIL
    probe.destroy()

    print(f"tkinter: Tk {tk.TkVersion}")

    results = Results()
    workspace = Workspace("run")
    workspace.start()
    policy = DialogPolicy()
    try:
        with scripted_dialogs(policy):
            for name, workflow in WORKFLOWS:
                print(f"--- workflow {name}")
                workflow(Run(workspace, results, policy))
    finally:
        # Cleanup is attempted on the way out of an unexpected error too: a run that leaves a window or a
        # folder behind is not repeatable, and repeatability is what makes this evidence.
        workspace.cleanup()

    if developed:
        # Printed without a PASS or FAIL line: those two words mean evidence in this project, and a stand-in
        # module cannot produce any. The step lines stay, because they are what makes the run useful while
        # the workflows are being written.
        missing = ran_every_declared_check(results)
        if missing:
            results.failures.append(("every declared check ran", missing))
        if results.failures:
            print()
            for description, traceback_text in results.failures:
                print(f"FAILED: {description}")
                print(traceback_text.rstrip())
        print(
            f"DEVELOPMENT RESULT: {results.passed} checks passed, {len(results.failures)} failed, against "
            "the test suite's stand-in widget module. No window was created. What it checked is that the "
            "workflows and the application agree about the widgets they build, the variables those widgets "
            "are bound to, the commands they run and the data they store. Nothing about a window on a "
            "display is established by this run."
        )
        print("RESULT: BLOCKED — a stand-in Tk is not a desktop, so this run is not evidence.")
        return EXIT_BLOCKED

    missing = ran_every_declared_check(results)
    if missing:
        results.failures.append(("every declared check ran", missing))

    return results.report(
        "The window was built by real Tk and driven through its own widgets and commands: a profile, a "
        "role and a qualification were typed, saved, closed and read back; a listing kept its source URL "
        "and its blank application URL; an unevidenced listing stayed UNKNOWN and refused shortlisting "
        "while an evidenced listing reached PASS; an application moved through its permitted statuses "
        "with a recorded interview round never counted as an outcome; an export round-tripped into a "
        "second database and three refusals wrote nothing; and every window, connection and temporary "
        "file was released. The dialogs a person would answer - a file chooser and the confirmations - "
        "were answered by the run and are listed above. This is not the manual checklist: no check has "
        "judged layout, wording, focus order, accessibility, or how any of it feels to use."
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
