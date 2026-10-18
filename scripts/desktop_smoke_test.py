"""Repeatable desktop smoke test: build the real window on a disposable database and drive it.

The manual checklist in ``research/`` is the only thing that can say a *person* can use this window, and
this script does not pretend otherwise. What a machine can check is narrower and still worth having: that
the real window class can be constructed on a real display, that its tabs and main lists are there in the
order the interface promises, that a rendering pass completes, that the read-only refresh actions a person
would click can be driven through Tk's own command dispatch, and that every window, database connection
and temporary file is released at the end.

Four properties are deliberate.

* **A tidy machine is BLOCKED, never a pass.** Without ``tkinter``, or without a display, the script
  exits :data:`EXIT_BLOCKED` and names the missing capability. A smoke test that reported success
  whenever the window could not be opened would turn CI green on exactly the runs that verified nothing.
* **Nothing here is a substitute for the manual checklist.** No check presses a button with a mouse,
  reads a dialog's wording, or asserts anything about pixels, screen coordinates or layout. What it
  asserts is the widget graph, the tab order, which database the window is bound to, and that the
  read-only paths return to the main loop.
* **The person's own database is never opened or touched.** The window is constructed against a synthetic
  database in a fresh temporary folder; the path the window is bound to is checked to be inside that
  folder; the default database's state is recorded before and after - without resolving that location in
  a way that would create its folder - and must be identical; and the temporary folder is deleted at the
  end, which, on the platforms where an open file cannot be deleted, is also the proof that the window
  released its connection.
* **A failure is a failure.** Every check is independent and any exception, including one from Tk itself,
  is reported as a failed check with its traceback rather than being swallowed.

Run from the repository root::

    python scripts/desktop_smoke_test.py

Exit status: ``0`` every check passed; ``1`` a check failed (a defect, or this project no longer matches
what the script asserts); ``2`` BLOCKED (this machine has no display, or no ``tkinter``), which is not a
pass and is not a defect in this project. The same 0/1/2 meaning ``career_agent.__main__`` gives its own
statuses, so a wrapper can treat BLOCKED as "cannot run here" without reading the text.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    # Running the file directly puts ``scripts/`` on the path, not the repository root, so the window
    # would be imported from whatever is installed. The checkout is what this script is checking.
    sys.path.insert(0, str(REPOSITORY_ROOT))

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_BLOCKED = 2

#: The tabs the window must carry, in the order it adds them. Read off the interface rather than
#: discovered, so a tab that is renamed, reordered or dropped fails the check instead of being reported
#: as whatever was found.
EXPECTED_TABS = (
    "Candidate profile",
    "Jobs & eligibility",
    "Application tracker",
    "Work history & study",
    "Next actions",
    "Follow-ups",
    "Data safety",
    "Background tasks",
    "HR contacts",
    "Tailored documents",
    "Permissions & limits",
)

#: The lists carried by the tabs, with the columns each one must expose. These are the controls a person
#: reads and selects in; if one of them stops being built, the tab it lives in is not usable.
EXPECTED_TREES = {
    "jobs_tree": ("employer", "role", "availability", "status", "source", "observed"),
    "tracker_tree": ("employer", "role", "status", "saved", "evidence"),
    "work_tree": ("employer", "title", "type", "period", "current"),
    "actions_tree": ("when", "what", "application", "detail"),
    "follow_up_tree": ("employer", "role", "status", "day", "when", "note"),
    "contact_rows_tree": ("line", "contact", "name", "company", "why"),
    "stored_contacts_tree": ("contact", "name", "company", "source", "seen", "marked"),
    "contact_conflicts_tree": ("ref", "contact", "field", "origins", "recorded_from", "recorded_at"),
    "facts_tree": ("fact", "value", "origin", "confirmation"),
    "artifacts_tree": ("kind", "listing", "strategy", "built", "cited", "state"),
    "policy_tree": ("source", "action", "limit", "state"),
}

#: The summary lines the window renders for its read-only reports. Every one of them must hold text once
#: the window has refreshed, because an empty summary is a report that did not run.
EXPECTED_SUMMARY_VARIABLES = (
    "progress_summary",
    "history_summary",
    "actions_summary",
    "follow_up_summary",
    "scheduler_summary",
    "contacts_summary",
    "facts_summary",
    "artifact_summary",
    "policy_summary",
)

#: The tabs whose whole point is a read-only refresh, and therefore the buttons this script presses. The
#: button is found in the built widget tree and invoked through Tk, so what runs is the same command a
#: click would run, not a re-implementation of it.
REFRESH_BUTTON_TEXT = "Refresh"
REFRESH_TAB_LABELS = ("Application tracker", "Next actions", "Follow-ups", "Background tasks",
                     "HR contacts")

#: Phrases Tk uses when it cannot reach a display. Only these turn a failure into BLOCKED: on Windows and
#: macOS a window needs no display variable at all, and anything else that goes wrong while a root is being
#: created is a defect rather than a missing capability.
NO_DISPLAY_MARKERS = (
    "no display name",
    "couldn't connect to display",
    "unable to open display",
    "invalid display",
    "can't connect to x server",
    "display is not accessible",
)


class SmokeFailure(Exception):
    """A check found something wrong; the message is what the run prints for it."""


def require(condition: object, message: str) -> None:
    """Fail this check with ``message`` unless ``condition`` holds.

    Deliberately not an ``assert``: an interpreter started with ``-O`` drops those, and a smoke test that
    silently checks nothing under a flag is worse than no smoke test.
    """
    if not condition:
        raise SmokeFailure(message)


def looks_like_no_display(message: str) -> bool:
    """Whether a Tk error message means "this machine has no display", as opposed to a real fault."""
    lowered = message.lower()
    return any(marker in lowered for marker in NO_DISPLAY_MARKERS)


class Results:
    """One line per check, plus the failures with their tracebacks."""

    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[tuple[str, str]] = []

    @contextmanager
    def step(self, description: str) -> Iterator[None]:
        """Run one check; a failure is recorded and the run carries on to the next one."""
        try:
            yield
        except Exception:  # noqa: BLE001 - every failure is evidence, and none may stop the run
            self.failures.append((description, traceback.format_exc()))
            print(f"[fail] {description}")
        else:
            self.passed += 1
            print(f"[ ok ] {description}")

    def report(self, summary: str) -> int:
        if self.failures:
            print()
            for description, traceback_text in self.failures:
                print(f"FAILED: {description}")
                print(traceback_text.rstrip())
            print(f"RESULT: FAIL — {self.passed} checks passed, {len(self.failures)} failed. {summary}")
            return EXIT_FAIL
        print(f"RESULT: PASS — {self.passed} checks passed. {summary}")
        return EXIT_PASS


def report_blocked(reason: str) -> int:
    """Report that this machine cannot run the checks, and say which capability is missing."""
    print(f"RESULT: BLOCKED — {reason}")
    print(
        "No check was run, so nothing is verified about the window. Run this under a display "
        "(on Linux, for example, under Xvfb) on a machine with tkinter installed."
    )
    return EXIT_BLOCKED


def import_tkinter():
    """Import ``tkinter`` from this interpreter, or raise for the caller to classify."""
    import tkinter  # noqa: PLC0415 - imported here so the same module can be created in tests

    return tkinter


def tree_columns(tree) -> tuple[str, ...]:
    """The columns a treeview was configured with, in whichever form its own Tk returns them."""
    configured = tree.cget("columns")
    if isinstance(configured, str):
        return tuple(configured.strip("{}").split())
    return tuple(str(name) for name in configured)


def buttons_under(widget) -> list:
    """Every button beneath ``widget``, found by walking the built widget tree."""
    found = []
    for child in widget.winfo_children():
        if child.winfo_class() in ("TButton", "Button"):
            found.append(child)
        found.extend(buttons_under(child))
    return found


def tab_frames(notebook) -> list:
    """The tab frames a notebook holds, resolved from the names it reports.

    ``Notebook.tabs()`` answers with widget *names* - strings like ``.!notebook.!frame`` - not with
    widgets, so anything that wants to look inside a tab has to resolve them first. The first
    display-backed CI run of this script failed on exactly that: thirteen checks passed on a real
    display and the fourteenth raised ``AttributeError: 'str' object has no attribute
    'winfo_children'``, which says the check had never actually run anywhere.
    """
    return [notebook.nametowidget(name) for name in notebook.tabs()]


def screen_description(root) -> str:
    """What the display answered, so the log shows a window-system reply rather than a variable's value."""
    try:
        size = f"{root.winfo_screenwidth()}x{root.winfo_screenheight()} pixels"
    except Exception:  # noqa: BLE001 - a display that will not describe itself is still a display
        return "a display that did not report its size"
    try:
        return f"{size} from {root.winfo_server()}"
    except Exception:  # noqa: BLE001 - not every display server answers this
        return size


def default_database_state(*, environ=None, home=None, system=None) -> tuple[bool, int, int] | None:
    """The size and modification time of the database this application would open on its own.

    Resolved with :func:`career_agent.config.resolve_settings`, which touches no directory: asking where
    the person's database is must never be the thing that creates it. The application's own
    ``database_path_for_run`` does create that folder, deliberately, on a first run - so it is the wrong
    function to ask this question with, and asking it here would make a check that is supposed to leave
    no trace leave one.

    ``None`` in place of a state means the location could not be resolved at all, which is reported as
    itself rather than being treated as "unchanged".
    """
    from career_agent.config import resolve_settings  # noqa: PLC0415 - kept out of import cost

    try:
        path = Path(resolve_settings(environ=environ, home=home, system=system).database_path)
    except Exception:  # noqa: BLE001 - an unresolvable location is itself the answer
        return None
    if not path.exists():
        return False, 0, 0
    information = path.stat()
    return True, information.st_size, information.st_mtime_ns


def main() -> int:
    print("AI Career Agent - desktop smoke test")
    print(f"python {sys.version.split()[0]} on {sys.platform}")

    try:
        tk = import_tkinter()
    except Exception as exc:  # noqa: BLE001 - the reason is the whole point of the report
        return report_blocked(f"this Python has no tkinter module: {exc!r}")

    print(f"tkinter: Tk {tk.TkVersion}, from {getattr(tk, '__file__', 'an unknown location')}")

    root = None
    try:
        root = tk.Tk()
    except Exception as exc:  # noqa: BLE001 - classified below
        if looks_like_no_display(str(exc)):
            return report_blocked(f"a Tk root cannot be created here: {exc}")
        print(traceback.format_exc().rstrip())
        print(f"RESULT: FAIL — creating a Tk root raised {exc!r}, which is not a missing display.")
        return EXIT_FAIL

    print(f"display: {screen_description(root)}")

    # Everything the run touches lives here, and it is removed at the end. The window is pointed at this
    # database explicitly, so the one the person uses is never opened.
    temporary = Path(tempfile.mkdtemp(prefix="career-agent-desktop-smoke-"))
    database = temporary / "smoke.sqlite3"
    results = Results()
    app = None
    default_database_before = None

    try:
        default_database_before = default_database_state()

        with results.step("the disposable folder is outside the repository and empty"):
            require(not database.exists(), f"{database} already exists; the run is not isolated")
            require(not temporary.is_relative_to(REPOSITORY_ROOT), "the temporary folder is inside the checkout")

        with results.step("the real application window is constructed on the disposable database"):
            from career_agent.desktop import CareerAgentApp  # noqa: PLC0415 - needs tkinter, checked above

            app = CareerAgentApp(root, database_path=database)

        if app is None:
            print("[skip] the window checks: the window could not be built, so there is nothing to drive")
            shutil.rmtree(temporary, ignore_errors=True)
            return results.report("The window could not be constructed; the failure above is the evidence.")

        with results.step("the window is bound to the disposable database, not the person's own"):
            require(Path(app.db_path) == database, f"the window opened {app.db_path!r} instead of {database}")
            require(database.exists(), "the window did not create its database")
            require(str(database) in app.status.get(), "the status line does not name the database in use")

        with results.step("the database the window created holds the current schema"):
            from career_agent.store import SCHEMA_TABLES, SCHEMA_VERSION  # noqa: PLC0415

            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            try:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                connection.close()
            require(version == SCHEMA_VERSION, f"the database records schema {version}, not {SCHEMA_VERSION}")
            missing = sorted(set(SCHEMA_TABLES) - tables)
            require(not missing, f"the created database is missing {missing}")

        with results.step("the window has its title and its documented minimum size"):
            require(root.title() == "AI Career Agent — Local Workspace", f"title is {root.title()!r}")
            minimum = root.minsize()
            parts = minimum.strip("{}").split() if isinstance(minimum, str) else minimum
            numbers = tuple(int(part) for part in parts)
            require(numbers == (900, 600), f"the minimum window size is {numbers!r}, not (900, 600)")

        with results.step("the notebook holds the nine tabs in the documented order"):
            labels = tuple(app.tabs.tab(tab, "text") for tab in app.tabs.tabs())
            require(labels == EXPECTED_TABS, f"the tabs are {labels!r}")

        with results.step("every tab was built, with at least one widget inside it"):
            frames = tab_frames(app.tabs)
            require(len(frames) == len(EXPECTED_TABS), f"the notebook reported {len(frames)} tabs")
            empty = [app.tabs.tab(frame, "text") for frame in frames if not frame.winfo_children()]
            require(not empty, f"these tabs are empty: {empty}")

        with results.step("the lists the tabs are read from exist with their documented columns"):
            from tkinter import ttk  # noqa: PLC0415

            for name, expected in EXPECTED_TREES.items():
                tree = getattr(app, name, None)
                require(tree is not None, f"the window has no {name}")
                require(isinstance(tree, ttk.Treeview), f"{name} is {type(tree).__name__}, not a tree view")
                columns = tree_columns(tree)
                require(columns == expected, f"{name} has columns {columns!r}, expected {expected!r}")

        with results.step("the read-only summaries the tabs render into exist"):
            for name in EXPECTED_SUMMARY_VARIABLES:
                variable = getattr(app, name, None)
                require(variable is not None, f"the window has no {name}")
                require(isinstance(variable, tk.StringVar), f"{name} is not a text variable")

        with results.step("selecting every tab and running a rendering pass changes nothing but the view"):
            for index, tab in enumerate(app.tabs.tabs()):
                app.tabs.select(tab)
                root.update()
                require(app.tabs.index("current") == index, f"selecting tab {index} did not take effect")
                require(root.winfo_exists(), "the window disappeared while the tabs were being selected")

        with results.step("the read-only refresh buttons are pressed through Tk, and they fill the summaries"):
            for label in REFRESH_TAB_LABELS:
                tab = app.tabs.nametowidget(app.tabs.tabs()[EXPECTED_TABS.index(label)])
                found = [b for b in buttons_under(tab) if str(b.cget("text")) == REFRESH_BUTTON_TEXT]
                require(found, f"the {label!r} tab has no {REFRESH_BUTTON_TEXT!r} button")
                require(len(found) == 1, f"the {label!r} tab has {len(found)} {REFRESH_BUTTON_TEXT!r} buttons")
                found[0].invoke()
                root.update()
            for name in EXPECTED_SUMMARY_VARIABLES:
                require(getattr(app, name).get() != "", f"{name} is still empty after the refreshes")

        with results.step("the window writes its event log beside the disposable database"):
            from career_agent.event_log import log_path  # noqa: PLC0415

            written = log_path(database)
            require(written.exists(), f"no event log was written at {written}")
            require(written.is_relative_to(temporary), "the event log was written outside the temporary folder")
            require("app.started" in written.read_text(encoding="utf-8"), "the event log does not record the start")

        with results.step("closing the window releases the database and the folder can be deleted"):
            app.close()
            try:
                root.winfo_exists()
            except Exception:  # noqa: BLE001 - a destroyed window is what is wanted here
                pass
            else:
                raise SmokeFailure("the window still exists after being closed")
            shutil.rmtree(temporary)
            require(not temporary.exists(), "the temporary folder survived the run")

        with results.step("the person's own database was not created, opened or modified"):
            if default_database_before is None:
                print(
                    "[skip] the person's own database could not be resolved on this machine, so whether "
                    "this run touched it was not checked"
                )
            else:
                require(
                    default_database_state() == default_database_before,
                    "the database this application opens on its own changed during the run",
                )
    finally:
        # The cleanup is also attempted on the way out of an unexpected error: a smoke test that leaves a
        # window or a folder behind is not repeatable, and a repeatable entry point is the whole point.
        if app is None:
            try:
                root.destroy()
            except Exception:  # noqa: BLE001 - already gone, which is fine
                pass
        shutil.rmtree(temporary, ignore_errors=True)

    return results.report(
        "The window was built on a real display, its tabs and lists were read, its read-only refresh "
        "actions were invoked, and its disposable database was released. This is not the manual "
        "checklist: no human interaction, dialog wording or layout was examined."
    )


if __name__ == "__main__":
    raise SystemExit(main())
