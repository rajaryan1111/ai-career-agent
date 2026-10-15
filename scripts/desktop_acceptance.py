"""End-to-end desktop acceptance workflows, driven through the real window and its real widgets.

The manual checklist in ``research/`` is what a *person* has to do, and this script does not pretend to
replace it. What it does is narrower and still worth having: it builds the real ``CareerAgentApp`` window on
a disposable synthetic database, types into the real ``Entry`` widgets, presses the real buttons through
Tk's own ``invoke``, answers the dialogs a person would answer, and then checks the *stored* result and what
the window says about it. Ten workflows run, in the order a first-time user would meet them:

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
* **G - work history and study records.** Add a current role and an ongoing qualification through their own
  forms and check what is stored; refuse an end date before its start, a date written in another shape, and a
  qualification marked ongoing that carries a completion date, and check that a refusal stores nothing.
* **H - follow-up reminders and the next-action list.** Record an application's first follow-up day from the
  tracker tab, check that overdue, due-today and later days read as words computed from fixed offsets, move
  and clear a day from its own row (with a refused clear changing nothing), reopen the window and find the
  list unchanged, add preparation items through their own dialog, tick one off without touching any status,
  and check that the calendar preview and the email draft write nothing and send nothing.
* **I - the scheduler tab.** Add the default tasks through the tab (and check that adding them again keeps
  them), pause one after a confirmation that can be declined, check the pause survives a restart, resume it
  and check the next occurrence is scheduled from now with nothing replayed - and check that none of this
  starts a worker, takes the lease or records an attempt.
* **J - data safety.** Write a backup through the tab and check it is verified before success is reported,
  refuse an existing destination and an unwritable one, refuse a malformed, foreign, truncated and too-new
  file with the live database untouched, decline a restore and check nothing moved, then restore a valid
  backup and check the records came back, the previous database was kept as a readable copy and nothing
  temporary was left behind.
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
LABEL = "TLabel"
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


def describe_bindings(parent, *, klass: str) -> str:
    """What every widget of one class under ``parent`` is bound to, for a message that has to explain itself.

    Read with the same two options ``linked_to`` reads, and each read is reported as it happened: an option
    a widget does not have, or a value Tk will not hand over, is reported as that rather than as a missing
    widget. A lookup that fails without this has to be guessed at, and a guess is not evidence.
    """
    described = []
    for widget in find_widgets(parent, klass=klass):
        parts = []
        for option in ("textvariable", "variable"):
            try:
                parts.append(f"{option}={widget.cget(option)!r}")
            except Exception as exc:  # noqa: BLE001 - the refusal is the finding, so it is reported
                parts.append(f"{option}=<{type(exc).__name__}>")
        described.append("(" + ", ".join(parts) + ")")
    body = "; ".join(described) if described else "none"
    return f"{len(described)} {klass} widget(s) under it: {body}"


def linked_to(widget, variable) -> bool:
    """Whether a widget is bound to ``variable``.

    Both options a Tk widget can bind a variable through are read: entries and choosers use
    ``textvariable``, while a checkbutton - the confirmation assertion in the status dialog among them -
    uses ``variable``. Real Tk answers either with the variable's Tcl *name*; this project's tests use a
    stub that answers with the variable object. Both spellings are accepted, so the same helper reads a
    real window and a stubbed one, and neither has to know which it is looking at.
    """
    names = {name for name in (str(variable), getattr(variable, "_name", None)) if isinstance(name, str)}
    names.discard("")
    for option in ("textvariable", "variable"):
        try:
            linked = widget.cget(option)
        except Exception:  # noqa: BLE001 - a widget without that option is simply not bound through it
            continue
        if linked is variable:
            return True
        # ``str(linked)`` as well as ``linked``: Tk can hand back a string-like object of its own rather
        # than a ``str``, and the name it carries is the same name either way.
        for spelling in (linked, getattr(linked, "_name", None)):
            if isinstance(spelling, str) and spelling in names:
                return True
        if not isinstance(linked, str) and linked is not None and str(linked) in names:
            return True
    return False


def widget_for(parent, variable, *, klass: str, what: str):
    """The one widget of ``klass`` under ``parent`` that is bound to ``variable``."""
    matches = [widget for widget in find_widgets(parent, klass=klass) if linked_to(widget, variable)]
    if len(matches) != 1:
        wanted = {str(variable)} | {str(getattr(variable, "_name", ""))}
        raise SmokeFailure(
            f"expected exactly one {what}, found {len(matches)}; looked for the {klass} bound to "
            f"{sorted(wanted - {''})!r}, and {describe_bindings(parent, klass=klass)}"
        )
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
        #: A third database for the workflows that record follow-ups and next actions. Kept apart from the
        #: other two so that a day recorded here cannot be read as part of an export or import workflow,
        #: and so that the damaged-record checks below damage a database nothing else depends on.
        self.third_database = self.folder / "synthetic-third.sqlite3"
        #: A fourth database for the schedule: the worker's tables are the worker's business, and a
        #: paused task here must not be readable as part of any other workflow's results.
        self.scheduler_database = self.folder / "synthetic-scheduler.sqlite3"
        #: A fifth database for backup and restore. Restoring replaces a file, so this one is never the
        #: database any other workflow reads: a mistake here could destroy the run's own results.
        self.data_safety_database = self.folder / "synthetic-data-safety.sqlite3"
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
        # The window tells the person what kind of file it has just made, and this is the step that says
        # the warning exists: a chosen file that may hold personal data must come with that said out loud.
        require(
            "Export complete" in policy.titles(),
            f"no confirmation was shown after the export; dialogs: {policy.titles()}",
        )
        warning = policy.said("Export complete")
        for phrase in ("personal data", "owner-only", "private"):
            require(
                phrase in warning.lower(),
                f"the export confirmation does not mention {phrase!r}: {warning!r}",
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
        from career_agent.importer import EXPORT_FORMAT_VERSION  # noqa: PLC0415

        require(
            document.get("format_version") == EXPORT_FORMAT_VERSION,
            f"the export declares format version {document.get('format_version')!r}",
        )
        # The person's own history travels in the file too, at the top level: this run added a role and a
        # qualification through the window in workflow A, so a file that dropped them would be visible here.
        stored_work = app.store.list_work_history()
        stored_study = app.store.list_education()
        require(stored_work and stored_study, "the earlier workflows added no history to this database")
        require(
            {entry.get("employer") for entry in document.get("work_history", [])}
            == {entry.employer for entry in stored_work},
            "the exported work history is not the stored one",
        )
        require(
            len(document.get("education", [])) == len(stored_study),
            f"the export holds {len(document.get('education', []))} education record(s), "
            f"the database holds {len(stored_study)}",
        )
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

    with results.step("E9 declining the import plan changes nothing at all"):
        host6, app6 = workspace.open_window(database=workspace.second_database)
        before_digest = file_digest(workspace.second_database)
        before_jobs = [job.listing_id for job in app6.store.list_jobs()]
        policy.reset()
        policy.files.append(str(export_path))
        # The one answer this run gives differently: a person declining the plan they were shown.
        policy.answers["Import this file?"] = False
        try:
            press(app6.data_tab, "Import an exported file (JSON)", workspace.root)
        finally:
            policy.answers.pop("Import this file?", None)
        require(
            "Import this file?" in policy.titles(),
            f"the plan was not shown before anything was written; dialogs: {policy.titles()}",
        )
        require(
            "cancel" in app6.status.get().lower(),
            f"declining the import reports {app6.status.get()!r}",
        )
        require(
            [job.listing_id for job in app6.store.list_jobs()] == before_jobs,
            "declining the import changed the stored listings",
        )
        workspace.close_window(host6, app6)
        require(
            file_digest(workspace.second_database) == before_digest and before_digest != "missing",
            "declining the import still wrote to the database file",
        )

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
# Workflow G - work history and study through their own forms, refusals included
# --------------------------------------------------------------------------------------------------
def tick(container, variable, *, what: str, on: bool = True):
    """Find the checkbutton bound to ``variable``, set it to ``on`` and return the variable.

    A real checkbutton is pressed with ``invoke()`` - the same command a click runs - so the state the
    handler reads is the state the widget shows. Where it is already in the wanted state, nothing is pressed.
    """
    box = widget_for(container, variable, klass=CHECKBUTTON, what=what)
    if bool(variable.get()) != on:
        box.invoke()
    require(
        bool(variable.get()) is on,
        f"{what} is {variable.get()!r} after being pressed, not {on!r}",
    )
    return box


def clear_history_forms(app, root) -> None:
    """Empty both forms, as closing and reopening the tab would."""
    for key, variable in app.work_vars.items():
        set_field(app.history_tab, variable, "", what=f"the role {key} field")
    for key, variable in app.study_vars.items():
        set_field(app.history_tab, variable, "", what=f"the qualification {key} field")
    for variable, what in ((app.work_current, "the current-role checkbox"),
                           (app.study_ongoing, "the still-studying checkbox")):
        if bool(variable.get()):
            tick(app.history_tab, variable, what=what, on=False)
    root.update()


def workflow_g_history_records(run: Run) -> None:
    """Add a role and a qualification through their forms, and check the refusals they must make.

    Every refusal here is a date that cannot be true or a pair of answers that contradict each other. What is
    checked is that the window says which field is wrong and that nothing was stored - a refused record that
    leaves a row behind would be worse than no refusal at all.
    """
    workspace, results, policy = run.workspace, run.results, run.dialogs
    host, app = workspace.open_window()

    with results.step("G1 the form's checkbuttons are the application's own variables, unticked"):
        require(
            app.work_current.get() is False and app.study_ongoing.get() is False,
            "a history form opened with its checkbox already ticked",
        )
        require(
            widget_for(app.history_tab, app.work_current, klass=CHECKBUTTON,
                       what="the current-role checkbox") is not None,
            "the role form has no current-role checkbox",
        )
        require(
            widget_for(app.history_tab, app.study_ongoing, klass=CHECKBUTTON,
                       what="the still-studying checkbox") is not None,
            "the qualification form has no still-studying checkbox",
        )
        print(f"[note] the two history checkbuttons read as "
              f"{describe_bindings(app.history_tab, klass=CHECKBUTTON)}")

    with results.step("G2 a role whose end date is before its start is refused, and nothing is stored"):
        before = len(app.store.list_work_history())
        clear_history_forms(app, workspace.root)
        impossible = {"employer": "Fixture Analytics Ltd", "job_title": "Fictional Impossible Role",
                      "start_date": "2025-06-01", "end_date": "2025-01-01"}
        for key, value in impossible.items():
            set_field(app.history_tab, app.work_vars[key], value, what=f"the role {key} field")
        policy.reset()
        press(app.history_tab, "Add this role", workspace.root)
        require(
            "Role not saved" in policy.titles(),
            f"an impossible employment period was stored; dialogs: {policy.titles()}",
        )
        said = policy.said("Role not saved")
        require(
            "2025-01-01" in said and "2025-06-01" in said,
            f"the refusal does not name both dates: {said!r}",
        )
        require(
            len(app.store.list_work_history()) == before,
            "a refused role was written to the database",
        )

    with results.step("G3 a date written as '1 April 2023' is refused, naming the shape wanted"):
        clear_history_forms(app, workspace.root)
        for key, value in (("employer", "Fixture Analytics Ltd"), ("job_title", "Fictional Dated Role"),
                           ("start_date", "1 April 2023")):
            set_field(app.history_tab, app.work_vars[key], value, what=f"the role {key} field")
        policy.reset()
        press(app.history_tab, "Add this role", workspace.root)
        require(
            "Role not saved" in policy.titles(),
            f"a date in the wrong shape was accepted; dialogs: {policy.titles()}",
        )
        require(
            "YYYY-MM-DD" in policy.said("Role not saved"),
            f"the refusal does not say the shape it wants: {policy.said('Role not saved')!r}",
        )
        require(
            app.store.list_work_history() and len(app.store.list_work_history()) == before,
            "a refused role changed the stored records",
        )

    with results.step("G4 a current role is added through the form and reported"):
        clear_history_forms(app, workspace.root)
        for key, value in (("employer", "Fixture Systems Ltd"), ("job_title", "Fictional Current Role"),
                           ("start_date", "2025-03-01")):
            set_field(app.history_tab, app.work_vars[key], value, what=f"the role {key} field")
        tick(app.history_tab, app.work_current, what="the current-role checkbox")
        press(app.history_tab, "Add this role", workspace.root)
        require(
            "Employment record added" in app.status.get(),
            f"adding a current role reported {app.status.get()!r}",
        )
        stored = [entry for entry in app.store.list_work_history()
                  if entry.job_title == "Fictional Current Role"]
        require(len(stored) == 1, f"{len(stored)} matching role(s) were stored, expected 1")
        require(
            stored[0].is_current is True and stored[0].end_date is None,
            f"the role was stored as current={stored[0].is_current!r}, end={stored[0].end_date!r}",
        )

    with results.step("G5 an ongoing qualification with no dates lists as ongoing"):
        for key, value in (("institution", "Fixture Institute of Technology"),
                           ("qualification", "MSc Fictional Computing")):
            set_field(app.history_tab, app.study_vars[key], value, what=f"the qualification {key} field")
        tick(app.history_tab, app.study_ongoing, what="the still-studying checkbox")
        press(app.history_tab, "Add this qualification", workspace.root)
        require(
            "Education record added" in app.status.get(),
            f"adding an ongoing qualification reported {app.status.get()!r}",
        )
        stored_study = [entry for entry in app.store.list_education()
                        if entry.qualification == "MSc Fictional Computing"]
        require(len(stored_study) == 1, f"{len(stored_study)} matching record(s) were stored, expected 1")
        require(
            stored_study[0].is_ongoing is True
            and stored_study[0].completion_date is None
            and stored_study[0].start_date is None,
            f"the record was stored as {stored_study[0]!r}",
        )
        rows = [app.study_tree.item(item, "values") for item in app.study_tree.get_children()]
        require(
            any("MSc Fictional Computing" in str(row) and "ongoing" in str(row).lower() for row in rows),
            f"no listed row shows the qualification as ongoing: {rows}",
        )

    with results.step("G6 a completion date while 'Still studying' is ticked is refused"):
        before = len(app.store.list_education())
        set_field(app.history_tab, app.study_vars["institution"], "Fixture Institute of Technology",
                  what="the qualification institution field")
        set_field(app.history_tab, app.study_vars["qualification"], "BSc Fictional Contradiction",
                  what="the qualification field")
        set_field(app.history_tab, app.study_vars["completion_date"], "2026-06-30",
                  what="the qualification completion date field")
        require(
            bool(app.study_ongoing.get()) is True,
            "the still-studying checkbox was cleared before the contradictory case could be tested",
        )
        policy.reset()
        press(app.history_tab, "Add this qualification", workspace.root)
        require(
            "Qualification not saved" in policy.titles(),
            f"a record marked ongoing with a completion date was accepted; dialogs: {policy.titles()}",
        )
        said = policy.said("Qualification not saved")
        require(
            "still on" in said or "ongoing" in said.lower(),
            f"the refusal does not explain the contradiction: {said!r}",
        )
        require(
            len(app.store.list_education()) == before,
            "a refused qualification was written to the database",
        )

    with results.step("G7 the selected role's title can be changed and saved over the record"):
        entries = app.store.list_work_history()
        target = next(entry for entry in entries if entry.job_title == "Fictional Current Role")
        # The form is emptied first, so that what the button fills it from can be told apart from what was
        # already in it: a form still holding this role's own values would pass a check like this without
        # the role ever being read. Every save rebuilds the list, and a rebuilt list has no row selected,
        # so the row is chosen again the way a person re-clicks it before pressing the button.
        clear_history_forms(app, workspace.root)
        app.work_tree.selection_set(str(target.entry_id))
        workspace.root.update()
        policy.reset()
        press(app.history_tab, "Select the selected role for editing", workspace.root)
        require(
            "Nothing selected" not in policy.titles(),
            f"reading the role asked for a selection that was already made: {policy.titles()}",
        )
        require(
            field_value(app.history_tab, app.work_vars["job_title"], what="the role job title field")
            == "Fictional Current Role"
            and field_value(app.history_tab, app.work_vars["employer"], what="the role employer field")
            == "Fixture Systems Ltd"
            and field_value(app.history_tab, app.work_vars["start_date"], what="the role start date field")
            == "2025-03-01",
            "selecting the role for editing did not fill the emptied form from the stored record",
        )
        set_field(app.history_tab, app.work_vars["job_title"], "Fictional Renamed Role",
                  what="the role job title field")
        tick(app.history_tab, app.work_current, what="the current-role checkbox")
        policy.reset()
        press(app.history_tab, "Save changes to the selected role", workspace.root)
        require(
            "Role not updated" not in policy.titles(),
            f"saving the change was refused: {policy.said('Role not updated')!r}",
        )
        require(
            "Employment record" in app.status.get() and "saved" in app.status.get(),
            f"saving the change reported {app.status.get()!r}",
        )
        renamed = [entry for entry in app.store.list_work_history()
                   if entry.entry_id == target.entry_id]
        require(len(renamed) == 1, "the edited role disappeared from the database")
        require(
            renamed[0].job_title == "Fictional Renamed Role",
            f"the stored title is {renamed[0].job_title!r}",
        )
        require(
            len(app.store.list_work_history()) == len(entries),
            "editing a role added or removed a record",
        )

    with results.step("G8 a role can stop being current, and the flag is stored as it was left"):
        # The form is cleared first, which unticks the checkbuttons: clearing used to look for them the
        # way it looks for entries, so a form left with one ticked could never be cleared.
        clear_history_forms(app, workspace.root)
        require(
            app.work_current.get() is False and app.study_ongoing.get() is False,
            "clearing the history forms left a checkbox ticked",
        )
        renamed = [entry for entry in app.store.list_work_history()
                   if entry.job_title == "Fictional Renamed Role"]
        require(len(renamed) == 1, f"{len(renamed)} renamed role(s) are stored, expected 1")
        # The save in G7 rebuilt the list, so nothing is selected until the row is chosen again.
        app.work_tree.selection_set(str(renamed[0].entry_id))
        workspace.root.update()
        policy.reset()
        press(app.history_tab, "Select the selected role for editing", workspace.root)
        require(
            "Nothing selected" not in policy.titles(),
            f"reading the role asked for a selection that was already made: {policy.titles()}",
        )
        require(
            field_value(app.history_tab, app.work_vars["start_date"], what="the role start date field")
            == "2025-03-01",
            "the emptied form was not filled from the stored role before the flag was changed",
        )
        tick(app.history_tab, app.work_current, what="the current-role checkbox", on=False)
        set_field(app.history_tab, app.work_vars["end_date"], "2026-09-30",
                  what="the role end date field")
        policy.reset()
        press(app.history_tab, "Save changes to the selected role", workspace.root)
        require(
            "Role not updated" not in policy.titles(),
            f"saving the change was refused: {policy.said('Role not updated')!r}",
        )
        saved = [entry for entry in app.store.list_work_history()
                 if entry.job_title == "Fictional Renamed Role"]
        require(len(saved) == 1, f"{len(saved)} renamed role(s) are stored, expected 1")
        require(
            saved[0].is_current is False and saved[0].end_date is not None,
            f"the role was stored as current={saved[0].is_current!r}, end={saved[0].end_date!r}",
        )
        rows = [app.work_tree.item(item, "values") for item in app.work_tree.get_children()]
        require(
            any("Fictional Renamed Role" in str(row) and str(row[-1]).strip() == "" for row in rows),
            f"the list still marks the role as current: {rows}",
        )

    workspace.close_window(host, app)


# --------------------------------------------------------------------------------------------------
# Workflow H - follow-up reminders and the combined next-action list
# --------------------------------------------------------------------------------------------------
#: The title the preparation item is given. A fixture, like every other string this run types: it names no
#: real employer, role or person.
PREPARATION_TITLE = "Fixture: revise the fixture exercise"


def follow_up_listing(reference: str) -> dict:
    """A synthetic listing for this workflow, with the same fields the Jobs form holds."""
    return {
        **LISTING_WITH_EVIDENCE,
        "employer": f"Fixture Follow-up Ltd {reference}",
        "title": f"Fictional Analyst {reference}",
        "source_url": f"https://example.com/fixture/followups/{reference}",
        "provenance_note": "Fixture: created by the desktop acceptance run's follow-up workflow.",
    }


def save_listing(app, workspace, values) -> str:
    """Type a listing into the Jobs form and save it, returning the id the window is working on.

    New-listing mode is entered first on purpose: saving switches the form to editing the listing it just
    wrote, so a second save in the same window would update the first listing instead of creating another.
    """
    press(app.jobs_tab, "New job", workspace.root)
    for key, value in values.items():
        if key in ("availability", "scope"):
            continue
        set_field(app.jobs_tab, app.job_vars[key], value, what=f"the {key} field")
    choose_in(app.jobs_tab, app.job_vars["availability"], values["availability"],
              what="the availability chooser")
    choose_in(app.jobs_tab, app.job_vars["scope"], values["scope"], what="the scope chooser")
    press(app.jobs_tab, "Save job", workspace.root)
    listing_id = app.selected_job_id
    require(bool(listing_id), "the listing was not saved")
    return str(listing_id)


def set_follow_up_through_the_window(app, workspace, listing_id: str, day, note: str) -> None:
    """Select one application and record its follow-up day through the Follow-ups tab's own button.

    The application is selected on the Application tracker tab, because that is where an application
    without a day can be selected at all: the Follow-ups tab lists the applications that already hold a
    day, so its own list cannot hold the one being recorded for the first time.
    """
    select_tracker_row(app, listing_id, workspace.root)
    type_into(app.follow_up_tab, app.follow_up_day, day.isoformat(), what="the follow-up day field")
    type_into(app.follow_up_tab, app.follow_up_note, note, what="the follow-up note field")
    press(app.follow_up_tab, "Set the day for the selected application", workspace.root)


def select_follow_up_row(app, listing_id: str, root) -> None:
    """Select a reminder row on the Follow-ups tab, which is what its own buttons act on.

    Real Tk dispatches ``<<TreeviewSelect>>`` and the window then fills its day and note fields from the
    reminder that was chosen. What proves it reacted is a field holding *that* reminder's stored day, not
    the tree's selection, which the click itself sets and would say yes even if nothing had run. Where the
    window did not react, the command the tree's binding runs is called: the same command a person's click
    runs, never a second implementation of it.
    """
    app.follow_up_tree.selection_set(listing_id)
    root.update()
    tracker = app.store.get_tracker(listing_id)
    stored_day = "" if tracker is None or tracker.follow_up_on is None else tracker.follow_up_on.isoformat()
    if app.follow_up_day.get() != stored_day:
        app._select_follow_up()  # noqa: SLF001 - the command the tree's <<TreeviewSelect>> binding runs
        root.update()
    require(
        list(app.follow_up_tree.selection())[:1] == [listing_id],
        f"the reminder row for {listing_id!r} is not selected",
    )
    require(
        app.follow_up_day.get() == stored_day,
        f"selecting the reminder for {listing_id!r} left {app.follow_up_day.get()!r} in the day field",
    )


def reminder_rows(app) -> list[tuple[str, tuple]]:
    """Every row on the Follow-ups tab in the order the tab built it: (row id, cell values)."""
    return [(str(item), app.follow_up_tree.item(item, "values"))
            for item in app.follow_up_tree.get_children()]


def action_rows(app) -> dict[str, tuple]:
    """Every row on the Next actions tab, by the record its row id names."""
    return {str(item): app.actions_tree.item(item, "values") for item in app.actions_tree.get_children()}


def select_action_row(app, row_id: str, root) -> None:
    """Select a next-action row, which is what that tab's own buttons act on."""
    app.actions_tree.selection_set(row_id)
    root.update()
    if list(app.actions_tree.selection())[:1] != [row_id]:
        app._select_action()  # noqa: SLF001 - the command the tree's <<TreeviewSelect>> binding runs
        root.update()
    require(
        list(app.actions_tree.selection())[:1] == [row_id],
        f"the next-action row {row_id!r} is not selected",
    )


def dialog_lines(dialog) -> str:
    """Everything a read-only dialog says, as a person reading it sees it."""
    lines = []
    for widget in descendants(dialog):
        if widget.winfo_class() != LABEL:
            continue
        try:
            lines.append(str(widget.cget("text")))
        except Exception:  # noqa: BLE001 - a label with no readable text contributes nothing
            continue
    return "\n".join(lines)


def change_the_synthetic_database(database, statements) -> None:
    """Make a change the window itself would never make, in a disposable database.

    Each statement is passed with its own parameters, so nothing is assembled into SQL text here. Used
    only to reach the states the damaged-record handling exists for - an application whose listing is
    gone, a reminder whose application row is gone. Foreign-key enforcement is left off in this
    connection deliberately: that is how a database copied between machines or edited by hand ends up
    holding a row that refers to nothing, and what the checks below are about is that the window reports
    such a row instead of crashing on it or acting on it. This never runs against the person's own
    database, which this run does not open.
    """
    import sqlite3  # noqa: PLC0415 - only these checks reach past the application to a database

    connection = sqlite3.connect(database)
    try:
        with connection:
            for statement, parameters in statements:
                connection.execute(statement, parameters)
    finally:
        connection.close()


def workflow_h_follow_ups_and_actions(run: Run) -> None:
    """Follow-up reminders and the combined next-action list, driven through the window itself.

    What this covers: an application saved in the window holds no reminder until one is recorded; the
    first day *is* recordable, from the application the person selected; overdue, due-today, upcoming and
    later days read as words computed from fixed days; the list survives closing and reopening the window;
    a day can be moved and cleared, and a refused clear changes nothing; recording or clearing a day never
    moves the application; the calendar preview and the email draft write nothing and send nothing; a
    preparation item is added through its own dialog and appears as a next action with its day; ticking an
    item off touches no status; and a reminder whose record has gone is reported rather than acted on.

    Every day this workflow checks is computed from the machine's own day, which is the day the window
    compares against: the offsets are fixed, and the words they must produce are asserted exactly.
    """
    from datetime import timedelta  # noqa: PLC0415 - only this workflow needs day arithmetic

    workspace, results, policy = run.workspace, run.results, run.dialogs
    host, app = workspace.open_window(database=workspace.third_database)

    with results.step("H1 an application saved in the window has no follow-up day recorded yet"):
        from career_agent import ApplicationStatus  # noqa: PLC0415

        listing_a = save_listing(app, workspace, follow_up_listing("a"))
        select_tracker_row(app, listing_a, workspace.root)
        status = tracker_status(app, listing_a)
        require(
            status is not None and status is ApplicationStatus.DISCOVERED,
            f"a listing saved a moment ago is {status!r} in the tracker",
        )
        press(app.follow_up_tab, "Refresh", workspace.root)
        require(reminder_rows(app) == [], f"a reminder exists before one was recorded: {reminder_rows(app)}")
        require(
            "No follow-ups are recorded" in app.follow_up_summary.get(),
            f"the tab says {app.follow_up_summary.get()!r} with nothing recorded",
        )

    with results.step("H2 the first follow-up day is recorded from the application selected in the window"):
        from career_agent import ApplicationStatus  # noqa: PLC0415

        today = date.today()
        day = today + timedelta(days=2)
        note = "Fixture: chase the reply, written by the acceptance run."
        require(reminder_rows(app) == [], "the reminder list is not empty before the first day is recorded")
        set_follow_up_through_the_window(app, workspace, listing_a, day, note)
        line = app.status.get()
        require(line.startswith(f"Follow-up set for {day.isoformat()}"),
                f"the window says {line!r} after recording the day")
        require(
            "the application's status was not changed" in line,
            "the window does not say the application's status was left alone",
        )
        tracker = app.store.get_tracker(listing_a)
        require(tracker is not None and tracker.follow_up_on == day,
                f"the stored day is {getattr(tracker, 'follow_up_on', None)!r}, not {day.isoformat()}")
        require(tracker.follow_up_note == note, f"the stored note is {tracker.follow_up_note!r}")
        require(tracker.candidate_confirmed is False,
                "recording a reminder marked the application as confirmed by a candidate")
        require(tracker.status is ApplicationStatus.DISCOVERED,
                f"recording a reminder moved the status to {tracker.status!r}")
        rows = reminder_rows(app)
        require([row_id for row_id, _values in rows] == [listing_a],
                f"the reminder list holds {[row_id for row_id, _values in rows]}")
        values = rows[0][1]
        require(str(values[3]) == day.isoformat(), f"the reminder row's day reads {values[3]!r}")
        require(str(values[4]) == "in 2 day(s)", f"the reminder row's timing reads {values[4]!r}")
        require(str(values[5]) == note, f"the reminder row's note reads {values[5]!r}")
        require("none are due yet" in app.follow_up_summary.get(),
                f"the summary reads {app.follow_up_summary.get()!r}")

    with results.step("H3 overdue, due today and later days are classified in words, from fixed days"):
        today = date.today()
        listing_b = save_listing(app, workspace, follow_up_listing("b"))
        listing_c = save_listing(app, workspace, follow_up_listing("c"))
        listing_d = save_listing(app, workspace, follow_up_listing("d"))
        for listing_id, offset, wording in (
            (listing_b, -3, "3 day(s) overdue"),
            (listing_c, 0, "due today"),
            (listing_d, 20, "in 20 day(s)"),
        ):
            wanted = today + timedelta(days=offset)
            set_follow_up_through_the_window(
                app, workspace, listing_id, wanted,
                f"Fixture: reminder at {offset:+d} day(s), written by the acceptance run.",
            )
            values = dict(reminder_rows(app))[listing_id]
            require(str(values[3]) == wanted.isoformat(),
                    f"the reminder for {offset:+d} day(s) stored {values[3]!r}, not {wanted.isoformat()}")
            require(str(values[4]) == wording,
                    f"the reminder for {offset:+d} day(s) reads {values[4]!r}, not {wording!r}")

    with results.step("H4 the reminder list is ordered by day and the summary counts what is due"):
        from career_agent import ApplicationStatus  # noqa: PLC0415

        order = [row_id for row_id, _values in reminder_rows(app)]
        expected = [listing_b, listing_c, listing_a, listing_d]
        require(order == expected, f"the reminder list is ordered {order}, not {expected}")
        require(
            app.follow_up_summary.get().startswith("1 overdue, 1 due today: 2 application(s) need a look."),
            f"the summary reads {app.follow_up_summary.get()!r}",
        )
        for listing_id in (listing_a, listing_b, listing_c, listing_d):
            tracker = app.store.get_tracker(listing_id)
            require(
                tracker is not None and tracker.status is ApplicationStatus.DISCOVERED
                and tracker.candidate_confirmed is False,
                f"{listing_id} is {tracker!r} after four follow-up days were recorded",
            )

    with results.step("H5 a reminder is moved and cleared from its own row, and a refused clear changes nothing"):
        from career_agent import ApplicationStatus  # noqa: PLC0415

        today = date.today()
        select_follow_up_row(app, listing_a, workspace.root)
        require(
            app.follow_up_day.get() == (today + timedelta(days=2)).isoformat(),
            f"selecting the reminder put {app.follow_up_day.get()!r} in the day field",
        )
        require(
            app.follow_up_note.get() == "Fixture: chase the reply, written by the acceptance run.",
            f"selecting the reminder put {app.follow_up_note.get()!r} in the note field",
        )
        moved = today + timedelta(days=1)
        type_into(app.follow_up_tab, app.follow_up_day, moved.isoformat(), what="the follow-up day field")
        type_into(app.follow_up_tab, app.follow_up_note, "Fixture: the day was moved.",
                  what="the follow-up note field")
        press(app.follow_up_tab, "Set the day for the selected application", workspace.root)
        tracker = app.store.get_tracker(listing_a)
        require(tracker is not None and tracker.follow_up_on == moved,
                f"the moved day reads {getattr(tracker, 'follow_up_on', None)!r}")
        # A refresh rebuilds the list, so the row that was selected is no longer selected: each press
        # below selects the row it acts on again, which is what a person does as well.
        policy.answers["Clear this follow-up?"] = False
        select_follow_up_row(app, listing_a, workspace.root)
        press(app.follow_up_tab, "Clear the selected follow-up", workspace.root)
        tracker = app.store.get_tracker(listing_a)
        require(tracker is not None and tracker.follow_up_on == moved,
                "a refused clear removed the day anyway")
        require(any(row_id == listing_a for row_id, _values in reminder_rows(app)),
                "the reminder row disappeared after a refused clear")
        policy.answers["Clear this follow-up?"] = True
        select_follow_up_row(app, listing_a, workspace.root)
        press(app.follow_up_tab, "Clear the selected follow-up", workspace.root)
        tracker = app.store.get_tracker(listing_a)
        require(tracker is not None and tracker.follow_up_on is None and tracker.follow_up_note is None,
                f"after clearing, the stored record is {tracker!r}")
        require(tracker.status is ApplicationStatus.DISCOVERED,
                f"clearing a reminder moved the status to {tracker.status!r}")
        require("Follow-up cleared; the application itself was not changed." in app.status.get(),
                f"the window says {app.status.get()!r} after clearing")
        require(all(row_id != listing_a for row_id, _values in reminder_rows(app)),
                "the cleared reminder is still listed")
        require(app.follow_up_day.get() == "" and app.follow_up_note.get() == "",
                "the fields still hold a day that was cleared")

    with results.step("H6 closing the window and opening it again shows the same reminders"):
        before = [(row_id, tuple(str(value) for value in values)) for row_id, values in reminder_rows(app)]
        summary_before = app.follow_up_summary.get()
        statuses_before = {listing_id: tracker_status(app, listing_id)
                           for listing_id in (listing_b, listing_c, listing_d)}
        workspace.close_window(host, app)
        host, app = workspace.open_window(database=workspace.third_database)
        press(app.follow_up_tab, "Refresh", workspace.root)
        after = [(row_id, tuple(str(value) for value in values)) for row_id, values in reminder_rows(app)]
        require(after == before, f"the reminders changed across a restart:\n{before}\n{after}")
        require(app.follow_up_summary.get() == summary_before,
                f"the summary changed to {app.follow_up_summary.get()!r}")
        for listing_id, status in statuses_before.items():
            require(tracker_status(app, listing_id) == status,
                    f"{listing_id} is {tracker_status(app, listing_id)!r} after the window was reopened")
        require(app.follow_up_day.get() == "",
                "a window that has just opened already holds a follow-up day in its fields")

    with results.step("H7 the calendar preview and the email draft write nothing and send nothing"):
        files_before = sorted(path.name for path in workspace.folder.iterdir())
        digest_before = file_digest(workspace.third_database)
        select_follow_up_row(app, listing_c, workspace.root)
        policy.reset()
        press(app.follow_up_tab, "Preview the calendar export", workspace.root)
        listed = [row_id for row_id, _values in reminder_rows(app)]
        preview = open_dialog(host, "Calendar export preview (read-only)")
        preview_text = dialog_lines(preview)
        require(
            f"Calendar export preview: {len(listed)} event(s) would be written." in preview_text,
            f"the calendar preview does not describe the {len(listed)} reminders the tab lists:\n"
            f"{preview_text[:400]}",
        )
        require("no invitation" in preview_text,
                "the calendar preview does not say that no invitation is involved")
        require("no attendee is invited" in preview_text,
                "the calendar preview does not say that nobody is invited")
        require("Nothing has been written yet" in preview_text,
                "the calendar preview does not say that nothing has been written")
        require("nothing has been written yet" in app.status.get(),
                f"the status line says {app.status.get()!r} after the preview")
        close_open_dialogs(host)
        select_follow_up_row(app, listing_c, workspace.root)
        policy.reset()
        press(app.follow_up_tab, "Draft a follow-up email", workspace.root)
        drafted = open_dialog(host, "Follow-up email draft (read-only, nothing is sent)")
        draft_text = dialog_lines(drafted)
        require("nothing here can send anything" in draft_text,
                f"the draft does not say it cannot be sent:\n{draft_text[:400]}")
        require("No email account is connected" in draft_text,
                "the draft does not say that no email account is connected")
        require("Fictional Analyst c" in draft_text,
                "the draft does not name the role it was written for")
        close_open_dialogs(host)
        require(sorted(path.name for path in workspace.folder.iterdir()) == files_before,
                "a read-only preview or draft wrote a file")
        require(file_digest(workspace.third_database) == digest_before and digest_before != "missing",
                "the database changed while two read-only dialogs were open")
        require("nothing was sent" in app.status.get(),
                f"the status line says {app.status.get()!r} after the draft")

    with results.step("H8 a preparation item is added through its dialog and appears with its own day"):
        from career_agent.core import PreparationKind  # noqa: PLC0415

        today = date.today()
        select_tracker_row(app, listing_c, workspace.root)
        policy.reset()
        record_dialog_controls(
            policy, "Add a preparation item",
            lambda: press(app.actions_tab, "Add a preparation item", workspace.root),
        )
        dialog = open_dialog(host, "Add a preparation item")
        texts = string_variables(policy, "Add a preparation item")
        require(len(texts) == 3, f"the preparation dialog created {len(texts)} text variables, expected 3")
        title_var, kind_var, day_var = texts
        chooser = widget_for(dialog, kind_var, klass=COMBOBOX, what="the kind chooser")
        require(
            [str(value) for value in chooser.cget("values")] == [kind.value for kind in PreparationKind],
            "the kind chooser does not offer the documented kinds of preparation",
        )
        type_into(dialog, title_var, PREPARATION_TITLE, what="the item field")
        choose_in(dialog, kind_var, PreparationKind.PRACTICE.value, what="the kind chooser")
        type_into(dialog, day_var, (today - timedelta(days=1)).isoformat(), what="the day field")
        press(dialog, "Add it", workspace.root)
        line = app.status.get()
        require(line.startswith("Preparation item added"), f"the window says {line!r}")
        require("No status was changed." in line, "adding an item does not say the status was left alone")
        open_items = [item for item in app.store.list_preparation(listing_c) if not item.is_done]
        require(len(open_items) == 1, f"the stored open preparation items are {open_items!r}")
        preparation_id = open_items[0].preparation_id
        rows = action_rows(app)
        row_id = f"preparation:{preparation_id}"
        require(row_id in rows, f"the new item is not in the next actions: {sorted(rows)}")
        job = app.store.get_job(listing_c)
        require(job is not None, "the listing the item was added to is no longer stored")
        require(str(rows[row_id][0]) == f"{(today - timedelta(days=1)).isoformat()} (1 day(s) overdue)",
                f"the row reads {rows[row_id][0]!r} for a day one day gone")
        require(PREPARATION_TITLE in str(rows[row_id][1]), f"the row does not name the item: {rows[row_id]!r}")
        require(f"{job.role_title} at {job.employer_name}" in str(rows[row_id][2]),
                f"the row does not name the application: {rows[row_id]!r}")

    with results.step("H9 an item with no day is listed rather than hidden, and a reminder shows here too"):
        today = date.today()
        select_tracker_row(app, listing_c, workspace.root)
        policy.reset()
        record_dialog_controls(
            policy, "Add a preparation item",
            lambda: press(app.actions_tab, "Add a preparation item", workspace.root),
        )
        dialog = open_dialog(host, "Add a preparation item")
        title_var, kind_var, day_var = string_variables(policy, "Add a preparation item")
        undated_title = f"{PREPARATION_TITLE} (no day)"
        type_into(dialog, title_var, undated_title, what="the item field")
        choose_in(dialog, kind_var, "research", what="the kind chooser")
        type_into(dialog, day_var, "", what="the day field")
        press(dialog, "Add it", workspace.root)
        undated = [item for item in app.store.list_preparation(listing_c)
                   if not item.is_done and item.due_on is None]
        require(len(undated) == 1, f"the undated item was not stored as undated: {undated!r}")
        rows = action_rows(app)
        undated_row = f"preparation:{undated[0].preparation_id}"
        require(undated_row in rows, f"the undated item is not listed: {sorted(rows)}")
        require(str(rows[undated_row][0]) == "No day set", f"the undated row reads {rows[undated_row][0]!r}")
        reminder_row = f"follow-up:{listing_c}"
        require(reminder_row in rows, f"the recorded reminder is not in the next actions: {sorted(rows)}")
        require(str(rows[reminder_row][0]) == f"{today.isoformat()} (today)",
                f"the reminder row reads {rows[reminder_row][0]!r}")
        summary = app.actions_summary.get()
        require("2 item(s) still to do" in summary, f"the summary reads {summary!r}")
        require("1 overdue" in summary, f"the summary does not count the overdue item: {summary!r}")
        require("1 with no day set" in summary, f"the summary does not count the undated item: {summary!r}")

    with results.step("H10 ticking off the selected item changes it and no status anywhere"):
        from career_agent import ApplicationStatus  # noqa: PLC0415

        before = tracker_status(app, listing_c)
        row_id = f"preparation:{preparation_id}"
        select_action_row(app, row_id, workspace.root)
        press(app.actions_tab, "Mark the selected item done", workspace.root)
        require(app.status.get() == f"Done: {PREPARATION_TITLE}. The application's status was not changed.",
                f"the window says {app.status.get()!r} after ticking the item off")
        require(row_id not in action_rows(app), "the finished item is still listed as something to do")
        stored = [item for item in app.store.list_preparation(listing_c)
                  if item.preparation_id == preparation_id]
        require(len(stored) == 1 and stored[0].is_done is True,
                f"the stored item is {stored!r} after being ticked off")
        require(tracker_status(app, listing_c) == before,
                f"ticking off an item moved the application from {before!r} to {tracker_status(app, listing_c)!r}")
        require(tracker_status(app, listing_c) is ApplicationStatus.DISCOVERED,
                "an application with only follow-ups and preparation done is not still discovered")
        require("Every preparation item is done" not in app.actions_summary.get(),
                "the summary claims every item is done while one is still open")

    with results.step("H11 the buttons that do not apply to a reminder explain instead of acting"):
        reminder_row = f"follow-up:{listing_c}"
        tracker_before = app.store.get_tracker(listing_c)
        select_action_row(app, reminder_row, workspace.root)
        policy.reset()
        press(app.actions_tab, "Mark the selected item done", workspace.root)
        require("That row is not a preparation item" in policy.titles(),
                f"ticking off a reminder row was not explained; dialogs raised: {policy.titles()}")
        require(all(item.is_done is False for item in app.store.list_preparation(listing_c)
                    if item.preparation_id != preparation_id),
                "ticking off a reminder row completed a preparation item")
        select_action_row(app, reminder_row, workspace.root)
        policy.reset()
        press(app.actions_tab, "Delete the selected record", workspace.root)
        require("Follow-up days are cleared, not deleted" in policy.titles(),
                f"deleting a reminder row was not explained; dialogs raised: {policy.titles()}")
        tracker_after = app.store.get_tracker(listing_c)
        require(
            tracker_after is not None and tracker_after.follow_up_on == tracker_before.follow_up_on
            and tracker_after.follow_up_note == tracker_before.follow_up_note
            and tracker_after.status == tracker_before.status,
            f"the reminder changed from {tracker_before!r} to {tracker_after!r} when its row was refused",
        )
        require(reminder_row in action_rows(app), "the reminder row disappeared after a refusal")

    with results.step("H12 a reminder whose listing is gone is reported, and nothing else changes"):
        change_the_synthetic_database(workspace.third_database, [
            ("DELETE FROM job_listings WHERE listing_id = ?", (listing_d,)),
        ])
        press(app.follow_up_tab, "Refresh", workspace.root)
        summary = app.follow_up_summary.get()
        require(
            "1 record(s) have a day but no stored listing any more" in summary,
            f"the tab does not report the reminder whose listing is gone: {summary!r}",
        )
        listed = [row_id for row_id, _values in reminder_rows(app)]
        require(listing_d not in listed, "a reminder whose listing is gone is still listed")
        require(listing_b in listed and listing_c in listed,
                f"the reminders that still have listings were dropped instead: {listed}")
        require(app.store.get_job(listing_d) is None, "the listing this check removed is still stored")

    with results.step("H13 a reminder whose application record is gone is refused, not acted on"):
        change_the_synthetic_database(workspace.third_database, [
            ("DELETE FROM application_tracker WHERE listing_id = ?", (listing_b,)),
        ])
        select_follow_up_row(app, listing_b, workspace.root)
        type_into(app.follow_up_tab, app.follow_up_day, date.today().isoformat(),
                  what="the follow-up day field")
        policy.reset()
        press(app.follow_up_tab, "Set the day for the selected application", workspace.root)
        require("Listing not found" in policy.titles(),
                f"a reminder whose record is gone was not reported; dialogs raised: {policy.titles()}")
        require("no longer in the local database" in policy.said("Listing not found"),
                "the refusal does not say that the record is gone")
        require(app.store.get_tracker(listing_b) is None,
                "an application record was written for a reminder whose record is gone")
        require("Follow-up set for" not in app.status.get(),
                f"the status line claims a day was recorded: {app.status.get()!r}")
        press(app.follow_up_tab, "Refresh", workspace.root)
        listed = [row_id for row_id, _values in reminder_rows(app)]
        require(listing_b not in listed, f"the reminder whose record is gone is still listed: {listed}")
        require(listing_c in listed, f"the tab lost the reminders it can still show: {listed}")

    with results.step("H14 nothing here is recorded as an employer decision or as a career outcome"):
        from career_agent import analytics  # noqa: PLC0415

        for tracker in app.store.list_trackers():
            require(tracker.candidate_confirmed is False,
                    f"{tracker.listing_id} is stored as confirmed after reminders and preparation")
        report = analytics.report_from_store(app.store, today=date.today())
        require(report.applications_recorded == 0,
                f"{report.applications_recorded} application(s) are counted as sent by this workflow")
        names = recorded_events(workspace.third_database)
        require("preparation.added" in names and "preparation.completed" in names,
                f"the preparation events are missing from the log: {sorted(names)}")
        require(not any("confirm" in name for name in names),
                f"a confirmation event was recorded by this workflow: {sorted(names)}")

    workspace.close_window(host, app)


# --------------------------------------------------------------------------------------------------
# Workflow I - the schedule: what the window shows, what pausing does, and what it never starts
# --------------------------------------------------------------------------------------------------
def task_rows(app) -> list[tuple[str, tuple]]:
    """Every row on the Scheduler tab in the order the tab built it: (row id, cell values)."""
    return [(str(item), app.tasks_tree.item(item, "values"))
            for item in app.tasks_tree.get_children()]


def attempt_rows(app) -> list[tuple[str, tuple]]:
    """Every row in the Scheduler tab's attempt list: (row id, cell values)."""
    return [(str(item), app.task_runs_tree.item(item, "values"))
            for item in app.task_runs_tree.get_children()]


def select_task_row(app, task_id: str, root) -> None:
    """Select a scheduled-task row, which is what that tab's own buttons act on."""
    app.tasks_tree.selection_set(task_id)
    root.update()
    require(
        list(app.tasks_tree.selection())[:1] == [task_id],
        f"the scheduled task {task_id!r} is not selected",
    )


def label_text_in(parent) -> str:
    """Everything the labels under ``parent`` say, joined: what the tab itself tells the person."""
    said = []
    for widget in find_widgets(parent, klass=LABEL):
        try:
            said.append(str(widget.cget("text")))
        except Exception:  # noqa: BLE001 - a label with no readable text contributes nothing
            continue
    return "\n".join(line for line in said if line)


def recorded_events(database) -> set[str]:
    """The name of every event the application recorded in the log beside this database."""
    import re  # noqa: PLC0415 - only the checks that read the log need it

    return set(re.findall(r"event=([a-z_.]+)", event_lines(database)))


def workflow_i_scheduler(run: Run) -> None:
    """The Scheduler tab, driven through the window: the schedule, pausing, resuming, and no side effects.

    The window is a control panel for the schedule; it is deliberately not the scheduler. Running a task
    loop on the interface's thread would freeze the window, and closing the window would be closing a
    worker mid-attempt - so the worker runs in its own process and the tab reads the same tables the
    worker reads. What this workflow therefore checks is what the window *shows* and what its own writes
    do: an empty schedule, the default tasks added once and kept the second time, a declined pause that
    changes nothing, a real pause that keeps the definition and the history, the paused state surviving a
    restart, a resume that schedules the next occurrence from now instead of replaying what was missed,
    a task whose record has gone reported rather than acted on, and - the check that matters most - that
    using this tab starts no worker, takes no lease and records no attempt of any kind.
    """
    from datetime import datetime, timezone  # noqa: PLC0415 - the next run is an instant

    from career_agent.worker import worker_status  # noqa: PLC0415 - the same read the worker uses

    workspace, results, policy = run.workspace, run.results, run.dialogs
    host, app = workspace.open_window(database=workspace.scheduler_database)

    with results.step("I1 the schedule starts empty, and the window says nothing is running"):
        require(task_rows(app) == [], f"the schedule is not empty to begin with: {task_rows(app)}")
        require(attempt_rows(app) == [],
                f"the attempt list is not empty to begin with: {attempt_rows(app)}")
        summary = app.scheduler_summary.get()
        require("No worker holds the lease" in summary,
                f"the tab does not say that no worker is running: {summary!r}")
        require("No task is scheduled to run." in summary,
                f"the tab does not say that nothing is scheduled yet: {summary!r}")
        require(worker_status(app.store).lease is None, "a lease exists before any worker was started")

    with results.step("I2 the default tasks are added through the window, and adding them again keeps them"):
        policy.reset()
        press(app.scheduler_tab, "Add the default tasks", workspace.root)
        require("Default tasks" in policy.titles(),
                f"adding the defaults was not reported; dialogs raised: {policy.titles()}")
        said = policy.said("Default tasks")
        require("Created:" in said and "Left exactly as they were:" in said,
                f"the dialog does not say what was created and what was left alone: {said!r}")
        rows = task_rows(app)
        require(bool(rows), "no task is listed after the defaults were added")
        stored = app.store.list_scheduled_tasks()
        require(len(stored) == len(rows), f"{len(stored)} task(s) are stored and {len(rows)} are listed")
        for task in stored:
            require(task.enabled and task.next_run_at is not None,
                    f"the default task {task.task_id} is stored as enabled={task.enabled!r}, "
                    f"next={task.next_run_at!r}")
        policy.reset()
        press(app.scheduler_tab, "Add the default tasks", workspace.root)
        said_again = policy.said("Default tasks")
        require("Created: nothing" in said_again,
                f"adding the defaults twice does not say that nothing was created: {said_again!r}")
        require(task_rows(app) == rows, "adding the defaults again changed the listed schedule")
        require(app.store.list_scheduled_tasks() == stored,
                "adding the defaults again rewrote a task that was already stored")

    with results.step("I3 pausing asks first, and a declined confirmation changes nothing"):
        task_id = str(task_rows(app)[0][0])
        before = app.store.get_scheduled_task(task_id)
        require(before is not None, f"the listed task {task_id!r} is not stored")
        select_task_row(app, task_id, workspace.root)
        policy.reset()
        policy.answers["Pause this task"] = False
        press(app.scheduler_tab, "Enable or disable the selected task", workspace.root)
        require("Pause cancelled; nothing was changed." in app.status.get(),
                f"the window says {app.status.get()!r} after a declined pause")
        require(app.store.get_scheduled_task(task_id).enabled is True,
                "a declined pause disabled the task anyway")

    with results.step("I4 a real pause keeps the task, its times and its history, and says it is paused"):
        select_task_row(app, task_id, workspace.root)
        policy.reset()
        policy.answers["Pause this task"] = True
        press(app.scheduler_tab, "Enable or disable the selected task", workspace.root)
        paused = app.store.get_scheduled_task(task_id)
        require(paused.enabled is False, f"the task is stored as enabled={paused.enabled!r} after pausing")
        require("is paused; no occurrence will run until it is resumed" in app.status.get(),
                f"the window says {app.status.get()!r} after pausing")
        require((paused.name, paused.kind, paused.times, paused.timezone)
                == (before.name, before.kind, before.times, before.timezone),
                "pausing rewrote the task's own definition")
        require((paused.last_outcome, paused.last_run_at, paused.consecutive_failures)
                == (before.last_outcome, before.last_run_at, before.consecutive_failures),
                "pausing changed the task's history")
        row = dict(task_rows(app))[task_id]
        require(str(row[5]) == "paused", f"the paused row's next-run cell reads {row[5]!r}")
        require(attempt_rows(app) == [], "pausing recorded an attempt")

    with results.step("I5 the paused task is still paused after the window is closed and opened again"):
        rows_before = task_rows(app)
        workspace.close_window(host, app)
        host, app = workspace.open_window(database=workspace.scheduler_database)
        press(app.scheduler_tab, "Refresh", workspace.root)
        require(task_rows(app) == rows_before, "the schedule changed across a restart")
        require(str(dict(task_rows(app))[task_id][5]) == "paused",
                "the task is no longer shown as paused after the window was reopened")
        stored = app.store.get_scheduled_task(task_id)
        require(stored is not None and stored.enabled is False,
                f"the task came back enabled after the window was reopened: {stored!r}")

    with results.step("I6 resuming schedules the next occurrence from now and replays nothing"):
        select_task_row(app, task_id, workspace.root)
        policy.reset()
        press(app.scheduler_tab, "Enable or disable the selected task", workspace.root)
        resumed = app.store.get_scheduled_task(task_id)
        require(resumed.enabled is True, f"the task is stored as enabled={resumed.enabled!r} after resuming")
        require("is enabled; its next run is" in app.status.get(),
                f"the window says {app.status.get()!r} after resuming")
        moment = datetime.now(timezone.utc)
        require(resumed.next_run_at is not None and resumed.next_run_at > moment,
                f"resuming left the next run at {resumed.next_run_at!r}, which is not ahead of "
                f"{moment.isoformat()}")
        require(app.store.list_task_runs(task_id=task_id) == (),
                "resuming replayed an occurrence that was missed while the task was paused")
        require(str(dict(task_rows(app))[task_id][5]) != "paused",
                "the resumed row still says the task is paused")

    with results.step("I7 a task whose record is gone is reported, and nothing else is changed"):
        others = [row_id for row_id, _values in task_rows(app) if row_id != task_id]
        require(bool(others), "the schedule holds one task, so this check cannot tell two apart")
        victim = others[0]
        change_the_synthetic_database(workspace.scheduler_database, [
            ("DELETE FROM scheduled_task WHERE task_id = ?", (victim,)),
        ])
        select_task_row(app, victim, workspace.root)
        policy.reset()
        press(app.scheduler_tab, "Enable or disable the selected task", workspace.root)
        require("no longer in the schedule; nothing was changed" in app.status.get(),
                f"the window says {app.status.get()!r} for a task that is gone")
        require(all(row_id != victim for row_id, _values in task_rows(app)),
                "the task that was removed behind the window is still listed")
        require(app.store.get_scheduled_task(victim) is None, "the removed task was written back")
        require(app.store.get_scheduled_task(task_id).enabled is True,
                "another task was changed instead of the one selected")

    with results.step("I8 using this tab starts no worker, takes no lease and records no attempt"):
        require(worker_status(app.store).lease is None, "the window took the worker's lease")
        require(app.store.get_worker_lease() is None, "a lease is stored after the tab was used")
        require(app.store.list_task_runs() == (), "the window recorded a task attempt")
        require(attempt_rows(app) == [], "the attempt list is not empty after using the tab")
        names = recorded_events(workspace.scheduler_database)
        require(not any(name.startswith("task.run_") or name.startswith("worker.") for name in names),
                f"a task run or a worker lease was recorded by this workflow: {sorted(names)}")
        require("task.scheduled" in names,
                f"the schedule write is missing from the recorded events: {sorted(names)}")
        said = label_text_in(app.scheduler_tab)
        require("python -m career_agent --worker" in said,
                "the tab does not say which command runs the schedule")
        require("gate is closed" in said and "fetches nothing" in said,
                "the tab does not say that the source-quality gate is closed and that a scheduled "
                "discovery run fetches nothing")

    workspace.close_window(host, app)


# --------------------------------------------------------------------------------------------------
# Workflow J - data safety: a verified backup, a validated restore, and every refusal in between
# --------------------------------------------------------------------------------------------------
#: Names that would show a temporary or half-written file left beside a database. A staged restore ends
#: in ``.partial`` and is hidden, so the check reads the folder's entries by name rather than by look.
_TEMPORARY_MARKERS = (".partial", ".part", ".tmp", "restore-")


def folder_files(workspace) -> set[str]:
    """Every entry name in the run's disposable folder, as a set, for before-and-after comparisons."""
    return {path.name for path in workspace.folder.iterdir()}


def leftover_temporary_files(workspace) -> list[str]:
    """Any temporary or half-written file the backup and restore paths left beside the database."""
    return sorted(
        name for name in folder_files(workspace) if any(marker in name for marker in _TEMPORARY_MARKERS)
    )


def choose_and_press(parent, button: str, policy, files: list[str], root) -> None:
    """Answer the next file chooser with ``files`` and press ``button``.

    ``files`` empty means the person closed the chooser without choosing: the policy hands back an empty
    path, which is exactly what a real chooser does when it is cancelled.
    """
    policy.files = list(files)
    press(parent, button, root)


def workflow_j_data_safety(run: Run) -> None:
    """Backup and restore driven through the window, on a disposable database this run alone owns.

    What this covers: a backup written through the window and verified before success is reported, with
    the file's own mode checked where the platform expresses one; an existing file never overwritten; a
    destination that cannot be written refused with nothing left behind; a cancelled chooser that writes
    nothing; a malformed, foreign, truncated or too-new file refused before the live database is touched;
    a restore the person declines that changes nothing; a real restore that brings the backed-up records
    back, undoes what came afterwards, keeps the previous database as a readable copy and leaves the
    window working; a restore refused while another connection holds the database; and no temporary file
    left behind by any of it, on success or on failure. It is never pointed at the person's own database:
    this run does not open that file at all, and the last workflow checks it is untouched.
    """
    import os  # noqa: PLC0415 - one check asks what this platform's file modes can express
    import sqlite3  # noqa: PLC0415 - the held-connection check needs a second connection of its own

    from career_agent import backup as backup_module  # noqa: PLC0415 - the module behind the buttons
    from career_agent.store import SCHEMA_VERSION  # noqa: PLC0415 - for the too-new file below

    workspace, results, policy = run.workspace, run.results, run.dialogs
    host, app = workspace.open_window(database=workspace.data_safety_database)
    backup_file = workspace.folder / "fixture-backup-1.sqlite3"

    with results.step("J1 a backup is written through the window and verified before success is reported"):
        for key, value in SYNTHETIC_PROFILE.items():
            set_field(app.profile_tab, app.profile_vars[key], value, what=f"the {key} field")
        press(app.profile_tab, "Save profile locally", workspace.root)
        primary = save_listing(app, workspace, follow_up_listing("data-safety"))
        require(app.store.get_profile() is not None, "the profile was not saved")
        digest_before = file_digest(workspace.data_safety_database)
        require(digest_before != "missing", "the window did not create its own database")
        policy.reset()
        choose_and_press(app.data_tab, "Back up database", policy, [str(backup_file)], workspace.root)
        require("Backup verified" in policy.titles(),
                f"the backup was not reported; dialogs raised: {policy.titles()}")
        said = policy.said("Backup verified")
        require(str(backup_file) in said, "the dialog does not name the file it wrote")
        require(backup_file.is_file(), "no backup file was written")
        info = backup_module.validate_app_database(backup_file)
        require(info.profile_present, "the backup does not hold the saved profile")
        require(info.job_count == 1, f"the backup holds {info.job_count} job(s), expected 1")
        require(info.summary() in said,
                f"the dialog's summary is not what the file holds: {said!r} against {info.summary()!r}")
        require("Backup verified:" in app.status.get(),
                f"the status line says {app.status.get()!r} after a verified backup")
        if os.name == "posix":
            mode = backup_file.stat().st_mode & 0o777
            require(mode == 0o600, f"the backup was written with mode {oct(mode)}, not owner-only")
        else:
            print(f"[skip] {os.name} cannot express owner-only permissions; not claimed on this platform")
        require(file_digest(workspace.data_safety_database) == digest_before,
                "writing a backup changed the live database")
        require(primary in [job.listing_id for job in app.store.list_jobs()],
                "backing up lost the listing the window had saved")

    with results.step("J2 an existing file is never overwritten, and a failed backup leaves nothing behind"):
        existing_digest = file_digest(backup_file)
        policy.reset()
        choose_and_press(app.data_tab, "Back up database", policy, [str(backup_file)], workspace.root)
        require("Backup not created" in policy.titles(),
                f"an existing file was not refused; dialogs raised: {policy.titles()}")
        refusal = policy.said("Backup not created")
        require("already exists" in refusal, f"the refusal does not say the file exists: {refusal!r}")
        require("The destination was left as it was." in refusal,
                "the refusal does not say the destination was left alone")
        require(file_digest(backup_file) == existing_digest, "the existing backup was overwritten")
        require("Backup not created; nothing was written." in app.status.get(),
                f"the status line says {app.status.get()!r} after a refused backup")
        files_before = folder_files(workspace)
        unwritable = workspace.folder / "no-such-folder" / "backup.sqlite3"
        policy.reset()
        choose_and_press(app.data_tab, "Back up database", policy, [str(unwritable)], workspace.root)
        require("Backup not created" in policy.titles(),
                f"a destination in a folder that does not exist was accepted: {policy.titles()}")
        require(not unwritable.exists(), "a backup was written into a folder that does not exist")
        require(folder_files(workspace) == files_before,
                f"a refused backup left something behind: {sorted(folder_files(workspace) - files_before)}")

    with results.step("J3 a cancelled file chooser writes nothing and raises no dialog"):
        files_before = folder_files(workspace)
        policy.reset()
        choose_and_press(app.data_tab, "Back up database", policy, [], workspace.root)
        require("Backup cancelled; nothing was written." in app.status.get(),
                f"the status line says {app.status.get()!r} after a cancelled backup")
        require(not policy.titles(), f"a cancelled chooser raised a dialog: {policy.titles()}")
        require(folder_files(workspace) == files_before, "a cancelled backup wrote something")

    with results.step("J4 a malformed, foreign, truncated or too-new file is refused, changing nothing"):
        live_digest = file_digest(workspace.data_safety_database)
        not_a_database = workspace.folder / "not-a-database.sqlite3"
        not_a_database.write_text("A text file that has a database file's name.\n", encoding="utf-8")
        foreign = workspace.folder / "another-programs.sqlite3"
        other = sqlite3.connect(foreign)
        try:
            other.execute("CREATE TABLE notes (body TEXT)")
            other.commit()
        finally:
            other.close()
        truncated = workspace.folder / "truncated-backup.sqlite3"
        truncated.write_bytes(backup_file.read_bytes()[:4096])
        too_new = workspace.folder / "from-a-newer-version.sqlite3"
        shutil.copyfile(backup_file, too_new)
        newer = sqlite3.connect(too_new)
        try:
            newer.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
            newer.commit()
        finally:
            newer.close()
        for candidate, explanation in (
            (not_a_database, "not a database this app can read"),
            (foreign, "does not recognise"),
            (truncated, None),
            (too_new, "newer than this app supports"),
        ):
            policy.reset()
            choose_and_press(app.data_tab, "Restore from backup", policy, [str(candidate)], workspace.root)
            require("Backup cannot be used" in policy.titles(),
                    f"{candidate.name} was not refused; dialogs raised: {policy.titles()}")
            said = policy.said("Backup cannot be used")
            require("The current database was not changed." in said,
                    f"the refusal for {candidate.name} does not say the database was left alone")
            if explanation is not None:
                require(explanation in said,
                        f"the refusal for {candidate.name} does not explain why: {said!r}")
            else:
                require("integrity check" in said or "not a database" in said,
                        f"the refusal for {candidate.name} does not say what is wrong: {said!r}")
            require("Restore refused; the current database was not changed." in app.status.get(),
                    f"the status line says {app.status.get()!r} after refusing {candidate.name}")
            require(file_digest(workspace.data_safety_database) == live_digest,
                    f"a refused file ({candidate.name}) replaced the live database anyway")
        require(not leftover_temporary_files(workspace),
                f"a refusal left a temporary file behind: {leftover_temporary_files(workspace)}")

    with results.step("J5 declining the restore confirmation changes nothing at all"):
        files_before = folder_files(workspace)
        live_digest = file_digest(workspace.data_safety_database)
        policy.reset()
        policy.files = [str(backup_file)]
        policy.answers["Replace the local database?"] = False
        press(app.data_tab, "Restore from backup", workspace.root)
        require("Replace the local database?" in policy.titles(),
                "the window did not ask before replacing the database")
        require("Restore cancelled; the current database was not changed." in app.status.get(),
                f"the status line says {app.status.get()!r} after a declined restore")
        require(file_digest(workspace.data_safety_database) == live_digest,
                "a declined restore changed the live database")
        require(folder_files(workspace) == files_before,
                f"a decline left files behind: {sorted(folder_files(workspace) - files_before)}")

    with results.step("J6 restoring a valid backup brings the records back and undoes what came after"):
        added_after_backup = save_listing(app, workspace, follow_up_listing("after-backup"))
        jobs_before_restore = len(app.store.list_jobs())
        require(jobs_before_restore == 2, f"{jobs_before_restore} job(s) are stored, expected 2")
        policy.reset()
        policy.files = [str(backup_file)]
        policy.answers["Replace the local database?"] = True
        press(app.data_tab, "Restore from backup", workspace.root)
        require("Restore complete" in policy.titles(),
                f"the restore was not reported; dialogs raised: {policy.titles()}")
        said = policy.said("Restore complete")
        require("reopened and verified" in said, f"the report does not say what was verified: {said!r}")
        require(app.store.get_job(added_after_backup) is None,
                "the listing saved after the backup is still in the database")
        require(len(app.store.list_jobs()) == jobs_before_restore - 1,
                f"the restored database holds {len(app.store.list_jobs())} job(s), expected "
                f"{jobs_before_restore - 1}")
        require(app.store.get_profile() is not None, "the restored database has no profile")
        require("Restored from" in app.status.get(),
                f"the status line says {app.status.get()!r} after a restore")
        listed = [str(item) for item in app.jobs_tree.get_children()]
        require(added_after_backup not in listed,
                "the window still lists the listing the restore removed")
        require(len(listed) == len(app.store.list_jobs()),
                f"the window lists {len(listed)} listing(s) and the database holds "
                f"{len(app.store.list_jobs())}")
        kept = sorted(workspace.folder.glob(f"{workspace.data_safety_database.name}.backup-*"))
        require(len(kept) == 1, f"the previous database was not kept as one copy: {kept}")
        previous = backup_module.validate_app_database(kept[0])
        require(previous.job_count == jobs_before_restore,
                f"the kept copy holds {previous.job_count} job(s), not {jobs_before_restore}")
        require("Previous database kept as a verified copy" in said,
                f"the report does not say what happened to the previous database: {said!r}")
        require(str(kept[0]) in said, f"the report does not name the kept copy: {said!r}")
        require(info.summary() in said,
                f"the report does not describe what is now in use: {said!r}")
        written_after = save_listing(app, workspace, follow_up_listing("after-restore"))
        require(app.store.get_job(written_after) is not None,
                "the window could not save a listing after a restore")

    with results.step("J7 a restore is refused while another connection holds the database"):
        live_digest = file_digest(workspace.data_safety_database)
        jobs_now = len(app.store.list_jobs())
        holder = sqlite3.connect(workspace.data_safety_database, isolation_level=None)
        try:
            holder.execute("BEGIN IMMEDIATE")
            policy.reset()
            policy.files = [str(backup_file)]
            policy.answers["Replace the local database?"] = True
            press(app.data_tab, "Restore from backup", workspace.root)
            require("Restore failed" in policy.titles(),
                    f"a database another connection holds was replaced anyway: {policy.titles()}")
            said = policy.said("Restore failed")
            require("in use" in said or "busy" in said.lower(),
                    f"the refusal does not say the database is in use: {said!r}")
            require(file_digest(workspace.data_safety_database) == live_digest,
                    "the live database changed although another connection held it")
            require(len(app.store.list_jobs()) == jobs_now,
                    f"the window's database holds {len(app.store.list_jobs())} job(s) after the refusal")
        finally:
            holder.execute("ROLLBACK")
            holder.close()

    with results.step("J8 nothing temporary is left behind, and the database in place is the app's own"):
        require(not leftover_temporary_files(workspace),
                f"temporary files were left behind: {leftover_temporary_files(workspace)}")
        require(not (workspace.folder / "no-such-folder").exists(),
                "a folder was created for a destination that could not be written")
        info = backup_module.validate_app_database(workspace.data_safety_database)
        require(info.schema_version == SCHEMA_VERSION,
                f"the database in place records schema version {info.schema_version}")
        require(info.job_count == len(app.store.list_jobs()),
                f"the file holds {info.job_count} job(s) and the window reads {len(app.store.list_jobs())}")
        copies = sorted(workspace.folder.glob(
            f"{workspace.data_safety_database.name}{backup_module.AUTOMATIC_BACKUP_INFIX}*"))
        require([path.name for path in copies] == [path.name for path in kept],
                f"the previous-database copies changed: {[path.name for path in copies]}")

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
#: which part of the application it belongs to, and ordered deliberately: F releases the run's own Tk root
#: and deletes the disposable folder, so every workflow that needs a window on the run's database comes
#: before it - G to J included, which is why the letters are not alphabetical here.
WORKFLOWS = (
    ("A - candidate profile persistence", workflow_a_profile),
    ("B - the two job URLs", workflow_b_job_urls),
    ("C - eligibility safety", workflow_c_eligibility),
    ("D - tracker and analytics", workflow_d_tracker_and_analytics),
    ("E - export, import and refusal", workflow_e_export_import),
    ("G - work history and study records", workflow_g_history_records),
    ("H - follow-up reminders and next actions", workflow_h_follow_ups_and_actions),
    ("I - the schedule, paused and resumed", workflow_i_scheduler),
    ("J - data safety: backup and restore", workflow_j_data_safety),
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
        "second database and three refusals wrote nothing; follow-up days were recorded, moved, refused "
        "and cleared on an application nothing else moved, with overdue, due-today and later days read "
        "back in words from fixed days, the list read back after the window was closed and reopened, a "
        "preparation item added through its own dialog and ticked off, and reminders whose records had "
        "gone reported instead of acted on; the default schedule added once and kept the second time, a "
        "paused task keeping its times and its history across a restart, a resume scheduling the next "
        "occurrence instead of replaying what was missed, a task whose record had gone reported rather "
        "than acted on, and no worker, lease or attempt started by any of it; a backup written and "
        "verified before success was reported, an existing file never overwritten, a malformed, foreign, "
        "truncated or too-new file refused before the live database was touched, a declined restore that "
        "changed nothing, a restore that brought the backed-up records back, kept the previous database "
        "as a readable copy and left the window writing, and a restore refused while another connection "
        "held the database; and every window, connection and temporary file was released."        "connection and temporary file was "
        "released. The dialogs a person would answer - a file chooser and the confirmations - were "
        "answered by the run and are listed above. This is not the manual checklist: no check has judged "
        "layout, wording, focus order, accessibility, or how any of it feels to use."
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
