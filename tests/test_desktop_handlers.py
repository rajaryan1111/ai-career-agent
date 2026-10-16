"""Handler-level regression tests for career_agent.desktop.

Tkinter is not guaranteed to be installed in headless CI, so this module installs a
minimal stub for the widget classes and dialogs the handlers touch, then imports and
exercises the real desktop module against real SQLite files in a temporary directory.

These tests verify handler decisions, validation messages, and database-error
handling. They do not verify rendering, theming, layout, or macOS behaviour; the
manual smoke-test checklist in research/ is still required before GUI acceptance.
"""
import contextlib
import csv
import io
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from xml.sax.saxutils import escape

from career_agent import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, Decision, JobListing,
    evaluate_eligibility, is_allowed_tracker_transition, selectable_tracker_statuses,
)
from career_agent.core import ActivityKind, ApplicationActivity, InterviewOutcome, PreparationKind
from career_agent import backup as backup_module
from career_agent import contact_export
from career_agent import contacts
from career_agent.backup import BackupError, create_backup, validate_app_database
from career_agent import analytics as career_agent_analytics
from career_agent import resume
from career_agent.event_log import log_path, read_lines
import career_agent.store as store_module
from career_agent.store import SCHEMA_VERSION, CareerStore, StoredRecordError, UnavailableStore

# The acceptance harness owns the definitions the display-backed checks use - what counts as a scrolling
# area, and which box a widget is judged against. Reusing them here keeps one reading of a window.
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import desktop_acceptance as acceptance  # noqa: E402 - after the path is set
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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


#: The widget classes a person can put the keyboard into. Spelled once, because both the focus-order
#: stub below and the acceptance harness's own focus check read the same list, and a class missing here
#: would make a control invisible to a check about controls.
INTERACTIVE_WIDGET_CLASSES = (
    "TButton", "Button", "TEntry", "Entry", "TCombobox", "Combobox",
    "TCheckbutton", "Checkbutton", "Text", "Treeview", "TNotebook",
)


def _stand_in_descendants(widget):
    """Every widget under ``widget``, deepest last, in the order the tree holds them."""
    found = []
    for child in widget.winfo_children():
        found.append(child)
        found.extend(_stand_in_descendants(child))
    return found


class Widget:
    #: What real Tk answers for ``winfo_class()``. Every subclass names its own, so a test (or the
    #: acceptance harness) can find widgets the way a person sees them - "the button", "the entry" -
    #: instead of by where they happen to sit in a list.
    tk_class = "Widget"

    def __init__(self, *args, **kwargs):
        self.options = kwargs
        # Tk reads a widget's state flags back, so the stub keeps them: a widget built ``state="disabled"``
        # has the disabled flag from the moment it exists, which is what ``instate`` then answers.
        self._state_flags = {"disabled"} if kwargs.get("state") == "disabled" else set()
        # The first positional argument is the parent widget in every real Tk constructor, so tests can
        # check where a widget was placed (inside the scrolling area, or in the fixed footer).
        self.master = args[0] if args else kwargs.get("master")
        self.destroyed = False
        # Real Tk knows its own widget tree, and walking it is how the acceptance harness (and the
        # desktop smoke test) find the control a person would press. A stub that did not build one
        # would make those walks untestable here, which is the opposite of what a stub is for.
        # Deliberately *not* called ``children``: the tree-view stub already uses that name for its rows.
        self.widget_children = []
        if isinstance(self.master, Widget):
            self.master.widget_children.append(self)

    def winfo_children(self):
        """The widgets whose parent this one is, in the order real Tk would list them."""
        return list(self.widget_children)

    def winfo_class(self):
        """The Tk class name, as real ``winfo_class`` reports it."""
        return self.tk_class

    def cget(self, name):
        """The configured value of one option, as real ``cget`` reports it.

        Real Tk answers with the *value* for most options and with the variable's Tcl name for
        ``textvariable``; here it is whatever the widget was constructed with, which is the variable
        object. Both spellings are accepted by the acceptance harness: it compares a widget's linked
        variable with the application's own variable by identity *or* by name, so a real window and this
        stub are read the same way.
        """
        if name in self.options:
            return self.options[name]
        raise KeyError(f"{self.tk_class} has no option {name!r} as configured")

    def nametowidget(self, name):
        """Real ``nametowidget`` resolves a widget path; here the widget itself is the name."""
        if isinstance(name, Widget):
            return name
        raise KeyError(name)

    def winfo_exists(self):
        return not self.destroyed

    def instate(self, spec, *rest):
        """Real ``instate``: whether every named flag is set (a leading ``!`` asks for it to be clear).

        Takes the same spellings ``state`` does - one flag, a list of them, or several arguments - because
        real Tk's ``instate ["disabled"]`` is how a widget's state is read back, and a stub that only
        understood the bare spelling would answer a different question than the platform does.
        """
        for item in (spec, *rest):
            for flag in (item if isinstance(item, (list, tuple)) else (item,)):
                name = str(flag)
                present = name.lstrip("!") in self._state_flags
                if present == name.startswith("!"):
                    return False
        return True

    #: What a widget reports when asked for the size it would like to be. Real Tk measures the text and
    #: the padding; this is a constant, which is the honest limit of a stub. These numbers exist so that
    #: code which *measures* a window - the acceptance harness's layout checks - can be exercised on a
    #: machine with no display, and such a run reports itself as a development run, not as evidence
    #: about layout.
    stand_in_requested_size = (120, 30)

    def winfo_reqwidth(self):
        return int(self.options.get("width") or self.stand_in_requested_size[0])

    def winfo_reqheight(self):
        return int(self.options.get("height") or self.stand_in_requested_size[1])

    def winfo_width(self):
        """The allocated width: this stub is laid out exactly as large as it asked to be."""
        return self.winfo_reqwidth()

    def winfo_height(self):
        return self.winfo_reqheight()

    def winfo_x(self):
        return 0

    def winfo_y(self):
        return 0

    def winfo_rootx(self):
        """Where this widget sits on the screen: its parent's origin, since nothing here is offset."""
        return self.master.winfo_rootx() + self.winfo_x() if isinstance(self.master, Widget) else 0

    def winfo_rooty(self):
        return self.master.winfo_rooty() + self.winfo_y() if isinstance(self.master, Widget) else 0

    def winfo_ismapped(self):
        """Real ``winfo ismapped``: a destroyed widget is not on the screen; nothing else is hidden."""
        return not self.destroyed

    def winfo_viewable(self):
        return not self.destroyed

    def winfo_screenwidth(self):
        """The screen a stand-in run pretends to have; no window is created to have a real one."""
        return 1280

    def winfo_screenheight(self):
        return 1024

    def update(self, *args, **kwargs):
        return None

    def update_idletasks(self, *args, **kwargs):
        return None

    def focus_set(self, *args, **kwargs):
        """Real ``focus_set``: remember where the keyboard would go, as the acceptance harness asks."""
        self.focused = True
        return None

    def event_generate(self, sequence=None, **kwargs):
        """Real ``event_generate``, as far as a stub without an event loop can honestly go.

        The acceptance harness presses a key to check that the window follows a selection a *person* made,
        and Tk's own class binding is what handles that key - not this application's code. So the stand-in
        implements exactly the class behaviours the workflows press, refuses every other key loudly (a key
        this stub had silently swallowed would make a workflow pass for the wrong reason), and is never
        evidence about a display: the run that uses it reports itself as a development run.
        """
        handled = self._class_binding(sequence)
        if handled:
            return None
        raise NotImplementedError(
            f"the stand-in models no class binding for {sequence!r} from a {self.tk_class}, so a workflow "
            "that presses it cannot be exercised here"
        )

    def _class_binding(self, sequence) -> bool:
        """The key bindings Tk itself installs for this widget class, as far as the stand-in models them."""
        return False

    def withdraw(self, *args, **kwargs):
        """Real ``wm withdraw``: the window exists but is not shown."""
        self.withdrawn = True
        return None

    def deiconify(self, *args, **kwargs):
        self.withdrawn = False
        return None

    def state(self, *args, **kwargs):
        """Real Tk's ``state``, in both of the shapes this window uses.

        Called with no arguments it answers how a window is being shown - ``withdrawn`` or ``normal``, which
        is what ``wm state`` reports. Called with flags it is ``ttk``'s own spelling,
        ``state(["!disabled"])``, which sets or clears a control's state flags; a control that is enabled and
        disabled while the window is open is read back with ``instate``, exactly as on a display.
        """
        if args or kwargs:
            for item in args:
                for flag in (item if isinstance(item, (list, tuple)) else (item,)):
                    name = str(flag)
                    if name.startswith("!"):
                        self._state_flags.discard(name[1:])
                    else:
                        self._state_flags.add(name)
            return tuple(sorted(self._state_flags))
        return "withdrawn" if getattr(self, "withdrawn", False) else "normal"

    def focus_set(self, *args, **kwargs):
        """Record where the focus went, so code that reads it back can be exercised here.

        Real Tk asks the window manager; this records the widget on the window that owns it, which is
        what ``focus_get`` then answers. Nothing in the application reads focus, so this is additive:
        it exists for the acceptance harness's focus checks, which cannot run against real Tk on a
        machine with no display.
        """
        owner = self
        while isinstance(owner.master, Widget):
            owner = owner.master
        owner.focused_widget = self
        return None

    def focus_force(self, *args, **kwargs):
        return self.focus_set()

    def focus_get(self):
        return getattr(self, "focused_widget", None)

    def tk_focusNext(self):
        """The next focusable widget after this one, in this stub's own tree order.

        Tk computes the real order - skipping hidden and ``takefocus=0`` widgets, and honouring
        bindings - and the stand-in does not model any of that. It answers with the next interactive
        widget so the harness's focus-order check can run to completion on a machine with no display,
        where the run reports itself as a development run rather than as evidence.
        """
        # The window this widget belongs to, which is what Tk's own focus order is computed within:
        # climbing stops at a Toplevel rather than at the root of the whole stub, so a widget in one
        # window can never be handed back as the next stop for a widget in another.
        owner = self
        while isinstance(getattr(owner, "master", None), Widget) and owner.winfo_class() != "Toplevel":
            owner = owner.master
        order = [widget for widget in _stand_in_descendants(owner)
                 if widget.winfo_class() in INTERACTIVE_WIDGET_CLASSES]
        if self in order:
            return order[(order.index(self) + 1) % len(order)]
        return order[0] if order else None

    def see(self, *args, **kwargs):
        return None

    def wait_window(self, *args, **kwargs):
        # Nothing is modal in a test: the handler that opened the dialog has already returned.
        return None

    def after(self, *_args, **_kwargs):
        return None

    def pack(self, *args, **kwargs):
        return self

    def grid(self, *args, **kwargs):
        return self

    def configure(self, *args, **kwargs):
        # Real Tk applies the options it is given and answers ``cget`` with what the widget is configured
        # with *now*. Recording them is what lets a handler that turns a widget's read-only mode on and off
        # be checked where there is no display; nothing in the suite reads an option expecting the value it
        # was constructed with.
        self.options.update(kwargs)
        if kwargs.get("state") == "disabled":
            self._state_flags.add("disabled")
        elif kwargs.get("state") == "normal":
            self._state_flags.discard("disabled")
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
        """Real ``title`` sets the window title, and answers with it when called with no argument."""
        if args:
            self.title_text = args[0]
            return None
        return getattr(self, "title_text", None)

    def geometry(self, *args, **kwargs):
        self.requested_geometry = args[0] if args else None
        return None

    def minsize(self, *args, **kwargs):
        """Real ``minsize`` sets the minimum size, and answers with it when called with no argument."""
        if args:
            self.requested_minsize = args[:2]
            return None
        return getattr(self, "requested_minsize", None)

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
        if isinstance(self.master, Widget) and self in self.master.widget_children:
            self.master.widget_children.remove(self)


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
    tk_class = "TFrame"
    allowed_options = TTK_FRAME_OPTIONS


class LabelFrame(Frame):
    tk_class = "TLabelframe"

    """``ttk.LabelFrame``: a frame that also accepts the option naming it.

    The real widget's own option list, so a typo in the window's code is still caught here - and the title
    is recorded, which is how a test can tell one labelled group from another.
    """

    allowed_options = TTK_FRAME_OPTIONS | {"text"}

    @property
    def title(self):
        return self.options.get("text")


class Notebook(ValidatedWidget):
    """Notebook stand-in; records each tab as ``(frame, label)`` in the order it was added."""

    tk_class = "TNotebook"
    allowed_options = TTK_NOTEBOOK_OPTIONS
    created = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tabs = []
        #: Nothing is selected until something selects it, as in a fresh notebook.
        self.selected_tab = None
        Notebook.created.append(self)

    def add(self, frame, **kwargs):
        self.tabs.append((frame, kwargs.get("text")))
        return None

    def labels(self):
        return [text for _frame, text in self.tabs]

    # The three methods a notebook is read and driven through, as real ``ttk.Notebook`` implements them:
    # asking which tab is shown, choosing one, resolving a widget name, and reading a tab's label.
    def _fire_tab_changed(self):
        """Real Tk's ``<<NotebookTabChanged>>``: choosing a tab runs the handler bound to it.

        The window re-reads the contacts tab when it is shown, and a stub that changed the shown tab
        silently would let that lifecycle look correct here while never running on a display - which is
        the one thing a stand-in must not do.
        """
        handler = getattr(self, "bindings", {}).get("<<NotebookTabChanged>>")
        if handler is not None:
            handler(None)

    def select(self, tab=None):
        """Choose a tab (or answer which one is chosen), as real ``ttk.Notebook.select`` does."""
        if tab is None:
            return self.selected_tab
        self.selected_tab = tab
        self._fire_tab_changed()
        return None

    def index(self, tab):
        """The position of a tab, accepting the string ``"current"`` as real Tk does."""
        frames = [frame for frame, _label in self.tabs]
        if str(tab) == "current":
            if self.selected_tab is None:
                raise KeyError("no tab is selected")
            return frames.index(self.selected_tab)
        return frames.index(tab)

    def tab(self, tab, option=None, **kwargs):
        if option == "text":
            for frame, label in self.tabs:
                if frame is tab:
                    return label
            raise KeyError(f"{tab!r} is not a tab of this notebook")
        return {}


class Canvas(ValidatedWidget):
    """Canvas stand-in: keeps the scrolled child window and any scroll request a test caused."""

    tk_class = "Canvas"
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
    tk_class = "Treeview"
    allowed_options = TTK_TREEVIEW_OPTIONS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = ()
        self.inserted = ()
        self.current = {}
        self.selected = ()
        self.children = ()
        #: The item Tk draws its focus rectangle around. It is *not* the selection: a click sets both, and
        #: Tk's own arrow-key navigation starts from this one and does nothing while it is empty.
        self.focus_item = ""

    def focus(self, item=None):
        """Real Tk's treeview ``focus`` subcommand: get the focus item, or set it.

        Tk keeps this item separately from the selection, and its ``ttk::treeview::Keynav`` procedure
        returns without moving anything when no item holds it - so a workflow that presses an arrow key has
        to say which row the person had clicked, or it is asking Tk to navigate from nowhere.
        """
        if item is None:
            return self.focus_item
        self.focus_item = str(item)
        return None

    def selection(self):
        return self.selected

    def _fire_select(self):
        """Real Tk's ``<<TreeviewSelect>>``: a selection change runs the handler bound to it.

        On a display the widget queues that virtual event and the window re-reads whatever the selection
        means; a stub that changed the selection silently would let a handler that only ever runs on a
        display look correct here, which is the opposite of what this stand-in is for.
        """
        handler = getattr(self, "bindings", {}).get("<<TreeviewSelect>>")
        if handler is not None:
            handler(None)

    def selection_set(self, selection):
        # Real Tk accepts either one item id or a sequence; a bare string is one item.
        self.selected = (selection,) if isinstance(selection, str) else tuple(selection)
        self._fire_select()

    def _class_binding(self, sequence) -> bool:
        """Tk's own treeview navigation, as ``ttk::treeview::Keynav`` implements it.

        Read off Tk 8.6's ``library/ttk/treeview.tcl``: the arrow keys move the tree's *focus item* and
        select it, and the procedure returns immediately when no item holds the focus - pressing Down in a
        list nobody has clicked moves nothing. Modelled here because the workflow that presses the key is
        asking whether the window's own handler follows the selection Tk moves, and a stand-in that invented
        a different starting point would make that check mean something else.
        """
        if sequence not in ("<Down>", "<Up>"):
            return False
        children = list(self.children)
        if not children or self.focus_item not in children:
            # The binding is there and it does nothing, which is what pressing Down in a list no row has
            # been clicked in does on a display. Answering "no binding" here would be a different claim.
            return True
        position = children.index(self.focus_item)
        step = 1 if sequence == "<Down>" else -1
        following = children[min(max(position + step, 0), len(children) - 1)]
        self.focus(following)
        self.selection_set(str(following))
        return True

    def delete(self, item):
        # The row Tk was drawing its focus rectangle around is gone with the row.
        if self.focus_item == str(item):
            self.focus_item = ""
        # A deleted row leaves the tree: it is no longer a child, can no longer be read, and is no longer
        # selected - real Tk drops a deleted item from the selection, and a list refresh rebuilds every
        # row, so a window that repopulates its list loses the row the person had chosen.
        self.rows = tuple(row for row in self.rows if str(row) != str(item))
        self.children = tuple(child for child in self.children if str(child) != str(item))
        self.current.pop(str(item), None)
        self.selected = tuple(chosen for chosen in self.selected if str(chosen) != str(item))
        self._fire_select()

    def selection_remove(self, selection):
        self.selected = ()
        self._fire_select()

    def get_children(self):
        return self.children

    def insert(self, parent, index, iid=None, values=None):
        self.rows += (iid,)
        # ``inserted`` is an append-only record of what was inserted (what tests assert on);
        # ``children`` is the current state, as real ``get_children`` reports it, and ``current`` is what
        # each live item holds *now*, as real ``item`` reports it.
        self.inserted += ((iid, values),)
        self.current[str(iid)] = values
        if parent in ("", None):
            self.children += (iid,)
        return iid

    def item(self, item, option=None, **kwargs):
        """Real ``Treeview.item`` reads a row's options; ``values`` is the one this suite uses.

        Item ids are Tcl strings, so an integer id reads the row inserted under that number's string
        form, and a row that is no longer in the tree cannot be read at all. Reading a row that was
        inserted again under the same id - how every refresh here updates a row - answers with the values
        of the latest insert, the way a real tree does, rather than with the first ones ever inserted.
        """
        if option == "values":
            # The values a row holds *now*: a row refreshed with new values reads back as the new ones,
            # which is what real Tk answers and what a workflow reading the list back is asking about.
            if str(item) in {str(row) for row in self.rows}:
                return self.current[str(item)]
            raise KeyError(f"Item {item} not found")
        return {}


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
    tk_class = "TButton"
    allowed_options = TTK_BUTTON_OPTIONS

    @property
    def text(self):
        return self.options.get("text", "")

    def invoke(self):
        """Run the command this button was built with: real ``invoke``, without the mouse."""
        command = self.options.get("command")
        return command() if command else None


class Text(Widget):
    """``tk.Text`` stand-in: keeps the text so a test can read a report back out of the widget.

    Deliberately permissive about options, like the assignment it replaces: the real text widget has a
    long option list of its own, and this stub's job is the content, not the option set.
    """

    tk_class = "Text"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content = ""

    def insert(self, index, text):
        # Real Tk inserts at a position; the harness only ever writes the whole buffer at "1.0".
        if str(index) in ("1.0", "end", "end-1c"):
            self.content += str(text)
        return None

    def delete(self, first, last=None):
        self.content = ""
        return None

    def get(self, first=None, last=None):
        return self.content

    def yview(self, *args, **kwargs):
        return None


class Entry(ValidatedWidget):
    """Entry stand-in that keeps what was typed, which a handler's own widget has to.

    Real ``insert``/``delete`` write into the linked ``textvariable`` when there is one; here the text
    is kept and the variable is updated as well, so both ways of reading an entry agree.
    """

    tk_class = "TEntry"
    allowed_options = TTK_ENTRY_OPTIONS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.typed = str(self.options.get("textvariable").get()) if self.options.get("textvariable") else ""

    def insert(self, index, text):
        self.typed = self.typed + str(text)
        if self.options.get("textvariable") is not None:
            self.options["textvariable"].set(self.typed)
        return None

    def delete(self, first, last=None):
        self.typed = ""
        if self.options.get("textvariable") is not None:
            self.options["textvariable"].set("")
        return None

    def get(self):
        if self.options.get("textvariable") is not None:
            return str(self.options["textvariable"].get())
        return self.typed


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

    tk_class = "TScrollbar"

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

    tk_class = "TCombobox"
    allowed_options = TTK_COMBOBOX_OPTIONS
    created = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        RecordingCombobox.created.append(self)

    @property
    def offered(self):
        """The values this chooser offered, as a list of status strings."""
        return list(self.options.get("values") or ())

    def set(self, value):
        """Real ``ttk.Combobox.set``: choose a value, updating the linked variable."""
        if self.options.get("textvariable") is not None:
            self.options["textvariable"].set(str(value))
        return None

    def get(self):
        variable = self.options.get("textvariable")
        return "" if variable is None else str(variable.get())

    def current(self, index=None):
        """Real ``current()``: the index of the chosen value, or the one it is set to."""
        values = self.offered
        chosen = self.get()
        if index is not None:
            self.set(values[index])
            return None
        return values.index(chosen) if chosen in values else -1


class RecordingCheckbutton(ValidatedWidget):
    """Checkbutton stand-in; keeps every instance so a test can read or set its variable."""

    tk_class = "TCheckbutton"
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

    def invoke(self):
        """Real ``Checkbutton.invoke``: flip the linked variable, as a click does."""
        variable = self.variable
        if variable is not None:
            variable.set(not variable.get())
        return None

    def state(self, *args, **kwargs):
        return ("selected",) if self.variable is not None and self.variable.get() else ()


class RecordingLabel(ValidatedWidget):
    """Label stand-in that keeps every instance, so a test can read what a dialog displayed."""

    tk_class = "TLabel"

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

    tk_class = "Toplevel"
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
# A real Toplevel is a Toplevel: dialogs the window opens must be findable as such, which is how a test
# or the acceptance harness reaches the controls inside them.
_tkinter.Toplevel = RecordingToplevel
_tkinter.Text = Text
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
    LabelFrame=LabelFrame,
    Button=BUTTONS.button,
)

_ORIGINAL_TKINTER = sys.modules.get("tkinter")
sys.modules["tkinter"] = _tkinter

from career_agent import contacts as contacts_module  # noqa: E402  (after the stub, like the window)
from career_agent import desktop  # noqa: E402  (imported after the stub is installed)
from career_agent.handlers import default_tasks, seed_default_tasks  # noqa: E402  (after the stub, like the window)
from career_agent.tasks import build_task  # noqa: E402  (the product's own task builder)

#: The ids a fresh installation is seeded with, taken from the seeder rather than written out here, so a
#: task added to the product does not require every listing assertion to be edited by hand.
DEFAULT_TASK_IDS = tuple(task.task_id for task in default_tasks())
from career_agent.tasks import RunState  # noqa: E402  (same reason: after the stub)
from career_agent.worker import missed_occurrences  # noqa: E402  (the same read the tab makes)
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
        Notebook.created = []
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
        app.work_tree = Tree()
        app.study_tree = Tree()
        # The history tab's own widgets, so its handlers run against real state rather than a stand-in.
        app.history_summary = StringVar()
        app.work_vars = {key: StringVar() for key in ("employer", "job_title", "start_date", "end_date",
                                                      "summary")}
        app.study_vars = {key: StringVar() for key in ("institution", "qualification", "discipline",
                                                       "start_date", "completion_date")}
        app.work_type = StringVar(value="unknown")
        app.work_current = BooleanVar()
        app.study_ongoing = BooleanVar()
        app.profile_tab = Widget()
        app.jobs_tab = Widget()
        app.tracker_tab = Widget()
        app.data_tab = Widget()
        app.history_tab = Widget()
        app.contacts_tab = Widget()
        app.contacts_preview = None
        app.contacts_summary = StringVar()
        app.contacts_preview_text = Text()
        app.contact_rows_tree = Tree()
        self.stored_contacts_tree = app.stored_contacts_tree = Tree()
        # The do-not-contact controls, built the way the real tab builds them: disabled until the list has
        # a selected row, with the reason box beside them.
        app.contact_selected_key = None
        app.contact_mark_state = StringVar(value="No stored contact is selected.")
        app.contact_note = StringVar()
        app.contact_note_entry = Entry(textvariable=app.contact_note, state="disabled")
        app.mark_contact_button = Button(text="Mark do not contact", state="disabled")
        app.clear_contact_button = Button(text="Remove do-not-contact mark", state="disabled")
        # The destructive control, built the way the real tab builds it: disabled until the list has a
        # selected row, so a test that presses it with nothing selected is pressing a greyed-out button.
        app.delete_contact_button = Button(text="Delete selected contact", state="disabled")
        # The recorded-disagreement panel, built the way the real tab builds it: read-only, with a list, a
        # count line and a detail box that is disabled to typing from the moment it exists.
        app.contact_conflict_selected_id = None
        app.contact_conflicts_shown = 0
        app.contact_conflict_note = StringVar(value="Reading the recorded disagreements...")
        app.contact_conflicts_tree = Tree()
        app.contact_conflict_text = Text(state="disabled")
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
            # Closed inside the block: the connection holds the database file open, and a platform that
            # will not delete a file another program has open (Windows) fails the folder's own cleanup -
            # which reported this test as an error on the first Windows run rather than as a pass.
            app.close()
        self.assertTrue(app.job_save_mode is desktop.JobSaveMode.NEW)
        self.assertIn("New listing", app.job_mode.get())
        self.assertEqual(app.job_vars["availability"].get(), "unknown")
        self.assertEqual(app.job_vars["scope"].get(), "unknown")
        self.assertEqual(app.db_path.name, "startup.sqlite3")
        self.assertTrue(app.root.destroyed)


class TabLayoutPolicyTests(unittest.TestCase):
    """What the window's own tabs *ask* for, checked where there is no display to ask Tk.

    Neither test is a layout measurement, and neither claims to be one: whether Tk had room for a widget is
    answered only by a real display with real fonts, which is why the display-backed harness asks it there.
    What can be checked anywhere is what the window asks for in the first place, and that is what failed on
    run 38820361412 (2026-10-16). The Linux job reported two labels of the Data safety tab 23 and 31 pixels
    past the notebook page's right edge - wrapped at 900 pixels, in a page that is 878 pixels wide at the
    window's own declared minimum - and the Tasks tree of the Background tasks tab 65 pixels below its tab,
    whose content was taller than the page with nothing to scroll. Both were the window asking for more room
    than it could be given.
    """

    def page_named(self, app, name):
        """The tab's own frame, found by the label a person reads rather than by position."""
        for frame, label in app.tabs.tabs:
            if label == name:
                return frame
        raise AssertionError(f"the window has no tab named {name!r}; it has {app.tabs.labels()!r}")

    @contextlib.contextmanager
    def open_window(self, name):
        """A real window over a disposable database, closed before its folder is cleaned up.

        Closing happens inside the temporary folder's own block, not in a cleanup: Windows will not delete a
        file another program holds open, so a connection closed afterwards makes the folder's cleanup raise
        and reports the test as an error - which is what this class did on the Windows legs of run
        38822542797 before this was fixed.
        """
        with tempfile.TemporaryDirectory() as directory:
            app = desktop.CareerAgentApp(Widget(), database_path=Path(directory) / name)
            try:
                yield app
            finally:
                app.close()

    #: How wide a label drawn across a tab may ask to be wrapped, in pixels.
    #:
    #: The window declares 900x600 as its own smallest size, and the page it gets for that is the platform's
    #: business: 878x483 on the Linux leg of run 38820361412 (2026-10-16), 826x453 on its macOS legs, where
    #: labels wrapped at 830 reached 18 and 14 pixels past the page on run 38822542797. The tab's own padding
    #: takes 24 of the width and the scrollbar a scrolling tab carries about 15 more, and Tk rounds a wrapped
    #: line a pixel or two wide of the number it was given.
    NARROWEST_TAB_TEXT_WIDTH = 826 - 24 - 15 - 2

    def test_every_label_drawn_across_a_tab_wraps_inside_the_narrowest_tab(self):
        with self.open_window("wrap.sqlite3") as app:
            checked = 0
            for page, label in app.tabs.tabs:
                for widget in acceptance.descendants(page):
                    if widget.winfo_class() not in ("TLabel", "Label"):
                        continue
                    if "wraplength" not in widget.options:
                        continue
                    checked += 1
                    asked = float(widget.options["wraplength"])
                    self.assertLessEqual(
                        asked, self.NARROWEST_TAB_TEXT_WIDTH,
                        f"a label of the {label!r} tab wraps at {asked:g} pixels, wider than the "
                        f"{self.NARROWEST_TAB_TEXT_WIDTH} pixels the narrowest tab has: it asks for more "
                        "width than the tab can give it, and Tk draws the difference outside the tab",
                    )
            # A walk that found nothing would pass this test while checking nothing at all.
            self.assertGreaterEqual(checked, 12, "no label drawn across a tab was found to check")

    def test_the_notebook_rereads_the_contacts_tab_when_it_is_shown(self):
        """The tab's own lifecycle event is registered, on the notebook the window builds."""
        with self.open_window("tabs.sqlite3") as app:
            self.assertIn("<<NotebookTabChanged>>", getattr(app.tabs, "bindings", {}),
                          "nothing is bound to the event a tab change posts, so a person coming back to "
                          "the contacts tab would read whatever it last drew")
            self.assertEqual(app.tabs.bindings["<<NotebookTabChanged>>"], app._on_tab_changed)
            # Bound methods are not the same object twice, so the function behind them is what is
            # compared: this asks whether the tree would run the panel's handler on a selection change.
            for tree, handler in ((app.stored_contacts_tree, app._on_contact_selection),
                                  (app.contact_conflicts_tree, app._on_conflict_selection)):
                bound = tree.bindings.get("<<TreeviewSelect>>")
                self.assertIsNotNone(bound, f"{tree} is not bound to anything on a selection change")
                self.assertEqual(bound.__func__, handler.__func__,
                                 f"{tree} is not bound to the handler its selection change posts")

    def test_the_export_control_says_what_the_file_is_and_what_it_cannot_do(self):
        """The sentence beside the export button, read from the real window that builds it.

        The claim about the do-not-contact column is asserted as the *module's own* sentence rather than as
        a copy of it: the window and the command line have to say the same thing about a safety-critical
        column, and a test that spelled the words out again would only prove the test agrees with itself.
        """
        with self.open_window("export-note.sqlite3") as app:
            note = app.contact_export_note.get()
            self.assertIn(contact_export.MARK_COLUMN_LIMITATION, note,
                          "the window does not carry the format module's own sentence about the mark")
            # Sharing the sentence proves the screens agree; these prove the sentence is worth sharing.
            self.assertIn('"Do Not Contact"', note)
            self.assertIn("cannot set or clear", note,
                          "the sentence beside the export never says an import cannot apply the mark")
            self.assertIn("read the column", note,
                          "the sentence never says what to do with the mark column instead")
            for claim in ("per stored contact", "not a backup", "replaced"):
                self.assertIn(claim, note, f"the sentence beside the export never says {claim!r}: {note!r}")
            self.assertIn("Nothing is sent anywhere", note)
            self.assertFalse(app.export_contacts_button.instate(["disabled"]),
                             "the export control is offered greyed out with no reason to refuse")

    def test_the_delete_control_says_what_it_costs_and_where_it_sits(self):
        """The one action on the contacts tab that cannot be undone, read from the tab that really builds it.

        The sentence is asserted here rather than on the handler double, because a copy of the window's prose
        in a fixture would only prove that the fixture and the window still agree with each other.
        """
        with self.open_window("delete-note.sqlite3") as app:
            note = app.contact_delete_note.get()
            self.assertIn("no undo", note, "the window never says that a deletion cannot be undone")
            self.assertIn("disagreement", note, "the sentence never says what goes with the contact")
            self.assertIn("backup", note, "the sentence never says what a backup still holds")
            self.assertIn("Nothing is sent", note, "the sentence never says that nothing is sent")
            self.assertTrue(app.delete_contact_button.instate(["disabled"]),
                            "the destructive control is offered before any row is selected")

    def test_the_window_wraps_its_tab_text_at_the_width_those_tabs_have(self):
        self.assertLessEqual(desktop._TAB_TEXT_WRAP, self.NARROWEST_TAB_TEXT_WIDTH)

    def test_content_taller_than_its_tab_is_reachable_rather_than_clipped(self):
        with self.open_window("scroll.sqlite3") as app:
            page = self.page_named(app, "Background tasks")
            for tree in (app.tasks_tree, app.task_runs_tree):
                container = acceptance.layout_container(tree, page)
                self.assertIsNot(
                    container, page,
                    f"{tree.winfo_class()} {tree} is judged against its tab: content taller than the tab "
                    "is clipped by the notebook unless something scrolls it",
                )
                self.assertTrue(
                    acceptance.is_scrolled_frame(container),
                    f"{tree.winfo_class()} {tree} is not inside an area that scrolls",
                )
            # The HR contacts tab holds two lists that grow with the person's own export, so its lists
            # must be inside a scrolling body for the same reason - and this is checked where the tab is
            # built, not only on a display.
            contacts_page = self.page_named(app, "HR contacts")
            for tree in (app.contact_rows_tree, app.stored_contacts_tree):
                container = acceptance.layout_container(tree, contacts_page)
                self.assertIsNot(
                    container, contacts_page,
                    f"{tree.winfo_class()} {tree} is judged against its tab: the contact lists grow with "
                    "the person's own file and would be clipped without something to scroll them",
                )
                self.assertTrue(acceptance.is_scrolled_frame(container),
                                f"{tree.winfo_class()} {tree} is not inside an area that scrolls")
            # The disagreement panel is in that body too: its list grows with every contradictory import
            # and its detail box holds two values that wrap, so both must scroll with the tab rather than
            # being drawn outside it.
            for widget in (app.contact_conflicts_tree, app.contact_conflict_text):
                container = acceptance.layout_container(widget, contacts_page)
                self.assertIsNot(
                    container, contacts_page,
                    f"{widget.winfo_class()} {widget} is judged against its tab: the recorded "
                    "disagreements grow with the person's own imports and would be clipped without "
                    "something to scroll them",
                )
                self.assertTrue(acceptance.is_scrolled_frame(container),
                                f"{widget.winfo_class()} {widget} is not inside an area that scrolls")
            # The controls that write the do-not-contact mark are in the same body, so they scroll with the
            # list they act on rather than being pinned below content that can grow past the page.
            for widget in (app.mark_contact_button, app.clear_contact_button, app.contact_note_entry,
                           app.delete_contact_button, app.export_contacts_button):
                container = acceptance.layout_container(widget, contacts_page)
                self.assertIsNot(container, contacts_page,
                                 f"{widget.winfo_class()} {widget} is judged against its tab")
                self.assertTrue(acceptance.is_scrolled_frame(container),
                                f"{widget.winfo_class()} {widget} is not inside an area that scrolls")
            # And a tab that holds no growing content is still judged against itself, so "scrolls" below
            # cannot be a helper that answers yes for every widget in the window.
            data_page = self.page_named(app, "Data safety")
            for widget in acceptance.descendants(data_page):
                self.assertIs(acceptance.layout_container(widget, data_page), data_page)


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


class HistoryTabTests(HandlerTestCase):
    """The Work history & study tab: the handlers behind its buttons.

    Handler-level, like the rest of this file: the widgets are stubs, so nothing here is evidence about
    how the tab renders or looks. What is checked is what each button does to the database and what it
    tells the person - including the refusals, which are the paths most likely to be wrong.
    """

    def fill_work(self, app, **values):
        defaults = {"employer": "Sandbox Systems", "job_title": "Data Engineer", "start_date": "2023-04-01",
                    "end_date": "", "summary": ""}
        for key, value in {**defaults, **values}.items():
            app.work_vars[key].set(value)

    def fill_study(self, app, **values):
        defaults = {"institution": "IIT Delhi", "qualification": "B.Tech", "discipline": "ECE",
                    "start_date": "2015-08-01", "completion_date": "2019-05-31"}
        for key, value in {**defaults, **values}.items():
            app.study_vars[key].set(value)

    def test_adding_a_role_writes_it_and_reports_what_was_saved(self):
        app = self.make_app()
        self.fill_work(app, summary="built the pipeline")

        app._add_work_history()

        stored = self.store.list_work_history()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].employer, "Sandbox Systems")
        self.assertEqual(stored[0].summary, "built the pipeline")
        self.assertIn("Data Engineer at Sandbox Systems", app.status.get())

    def test_a_current_role_is_saved_as_current_and_reads_as_present(self):
        app = self.make_app()
        self.fill_work(app, end_date="")
        app.work_current.set(True)
        app.work_type.set("full_time")

        app._add_work_history()

        stored = self.store.list_work_history()[0]
        self.assertTrue(stored.is_current)
        self.assertEqual(stored.period, "2023-04-01 - present")
        self.assertIn("2023-04-01 - present", app.status.get())

    def test_an_impossible_period_is_refused_with_a_dialog_and_writes_nothing(self):
        app = self.make_app()
        self.fill_work(app, end_date="2019-01-01")

        app._add_work_history()

        self.assertIn("Role not saved", MESSAGES.titles("showerror"))
        self.assertEqual(self.store.list_work_history(), ())
        self.assertNotIn("added", app.status.get())

    def test_a_current_role_with_an_end_date_is_refused_the_same_way(self):
        app = self.make_app()
        self.fill_work(app, end_date="2025-01-01")
        app.work_current.set(True)

        app._add_work_history()

        self.assertIn("Role not saved", MESSAGES.titles("showerror"))
        self.assertEqual(self.store.list_work_history(), ())

    def test_an_end_date_that_is_not_a_date_is_refused_before_it_reaches_the_store(self):
        app = self.make_app()
        self.fill_work(app, end_date="last winter")

        app._add_work_history()

        self.assertIn("Role not saved", MESSAGES.titles("showerror"))
        self.assertIn("YYYY-MM-DD", MESSAGES.text("showerror"))
        self.assertEqual(self.store.list_work_history(), ())

    def test_a_missing_start_date_is_refused_for_an_employment_record(self):
        app = self.make_app()
        self.fill_work(app, start_date="   ")

        app._add_work_history()

        self.assertIn("Role not saved", MESSAGES.titles("showerror"))
        self.assertEqual(self.store.list_work_history(), ())

    def test_education_dates_are_optional_and_an_ongoing_course_needs_no_completion(self):
        app = self.make_app()
        self.fill_study(app, start_date="", completion_date="")
        app.study_ongoing.set(True)

        app._add_education()

        stored = self.store.list_education()[0]
        self.assertTrue(stored.is_ongoing)
        self.assertIsNone(stored.start_date)
        self.assertEqual(stored.period, "start not recorded - ongoing")
        self.assertIn("ongoing", app.status.get())

    def test_ongoing_study_with_a_completion_date_is_refused(self):
        app = self.make_app()
        self.fill_study(app)
        app.study_ongoing.set(True)

        app._add_education()

        self.assertIn("Qualification not saved", MESSAGES.titles("showerror"))
        self.assertEqual(self.store.list_education(), ())

    def test_editing_a_role_requires_a_selected_row_and_says_so(self):
        self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1))
        app = self.make_app()
        self.fill_work(app, job_title="Senior Data Engineer")

        app._update_work_history()

        self.assertIn("Select a row first", MESSAGES.titles("showinfo"))
        self.assertEqual(self.store.list_work_history()[0].job_title, "Data Engineer",
                         "nothing is saved without a row to save it to")

    def test_editing_a_role_saves_the_typed_values_over_the_selected_row(self):
        added = self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1))
        app = self.make_app()
        app.work_tree.selected = (str(added.entry_id),)
        self.fill_work(app, job_title="Senior Data Engineer", summary="led the migration")
        app.work_type.set("full_time")

        app._update_work_history()

        stored = self.store.get_work_history(added.entry_id)
        self.assertEqual(stored.job_title, "Senior Data Engineer")
        self.assertEqual(stored.summary, "led the migration")
        self.assertIn("saved", app.status.get())

    def test_editing_a_qualification_saves_the_typed_values_over_the_selected_row(self):
        added = self.store.add_education("IIT Delhi", "B.Tech", discipline="ECE",
                                         completion_date=date(2019, 5, 31))
        app = self.make_app()
        app.study_tree.selected = (str(added.entry_id),)
        self.fill_study(app, discipline="Electrical Engineering")

        app._update_education()

        self.assertEqual(self.store.get_education(added.entry_id).discipline,
                         "Electrical Engineering")

    def test_editing_something_that_is_gone_reports_it_rather_than_recreating_it(self):
        added = self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1))
        app = self.make_app()
        app.work_tree.selected = (str(added.entry_id),)
        self.store.delete_work_history(added.entry_id)
        self.fill_work(app)

        app._update_work_history()

        self.assertIn("Role not updated", MESSAGES.titles("showerror"))
        self.assertEqual(self.store.list_work_history(), ())

    def test_deleting_a_role_asks_first_and_then_deletes_only_with_consent(self):
        added = self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1))
        app = self.make_app()
        app.work_tree.selected = (str(added.entry_id),)

        CONFIG["Delete this role?"] = False
        app._delete_work_history()
        self.assertEqual(len(self.store.list_work_history()), 1, "a refused confirmation deletes nothing")

        CONFIG["Delete this role?"] = True
        app._delete_work_history()
        self.assertEqual(self.store.list_work_history(), ())
        self.assertIn("Employment record deleted", app.status.get())

    def test_deleting_a_qualification_asks_first_and_reports_a_row_that_was_already_gone(self):
        added = self.store.add_education("IIT Delhi", "B.Tech")
        app = self.make_app()
        app.study_tree.selected = (str(added.entry_id),)
        CONFIG["Delete this qualification?"] = True
        self.store.delete_education(added.entry_id)

        app._delete_education()

        self.assertIn("That education record was already gone; nothing was deleted.", app.status.get())

    def test_the_delete_question_says_what_else_is_not_touched(self):
        added = self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1))
        app = self.make_app()
        app.work_tree.selected = (str(added.entry_id),)
        CONFIG["Delete this role?"] = False

        app._delete_work_history()

        asked = MESSAGES.text("askyesno")
        self.assertIn("cannot be brought back", asked)
        self.assertIn("not changed", asked, "the question says what it leaves alone, not only what it takes")

    def test_selecting_a_row_loads_its_own_values_into_the_form(self):
        added = self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1),
                                            end_date=date(2024, 4, 1), employment_type="contract",
                                            summary="built the pipeline")
        app = self.make_app()
        app.work_tree.selected = (str(added.entry_id),)

        app._load_work_history()

        self.assertEqual(app.work_vars["employer"].get(), "Sandbox Systems")
        self.assertEqual(app.work_vars["end_date"].get(), "2024-04-01")
        self.assertEqual(app.work_type.get(), "contract")
        self.assertEqual(app.work_vars["summary"].get(), "built the pipeline")

    def test_the_list_shows_the_current_role_first_and_an_unknown_end_honestly(self):
        self.store.add_work_history("Old Co", "Analyst", date(2020, 1, 6))
        self.store.add_work_history("Now", "Lead", date(2022, 6, 1), is_current=True)
        app = self.make_app()

        app._refresh_history()

        expected = [str(entry.entry_id) for entry in self.store.list_work_history()]
        self.assertEqual(list(app.work_tree.children), expected, "both roles are listed, newest first")
        periods = [app.work_tree.item(item, "values")[3] for item in expected]
        self.assertEqual(periods, ["2022-06-01 - present", "2020-01-06 - end date not recorded"],
                         "a missing end date is shown as missing, not as today")
        self.assertIn("2 employment record(s)", app.history_summary.get())

    def test_the_summary_counts_months_but_never_calls_them_years_of_experience(self):
        self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1), is_current=True)
        self.store.add_work_history("Old Co", "Analyst", date(2015, 1, 1), end_date=date(2020, 1, 1))
        app = self.make_app()

        app._refresh_history()

        summary = app.history_summary.get()
        self.assertIn("employment record(s)", summary)
        self.assertIn("month(s) of recorded employment", summary)
        self.assertIn("not a claim about experience", summary)
        self.assertNotIn("years of experience", summary)

    def test_the_summary_says_which_records_it_could_not_count(self):
        self.store.add_work_history("Old Co", "Analyst", date(2020, 1, 6))
        app = self.make_app()

        app._refresh_history()

        self.assertIn("no end date recorded", app.history_summary.get())
        self.assertIn("no duration is counted", app.history_summary.get())

    def test_an_empty_history_says_so_instead_of_showing_a_zero(self):
        app = self.make_app()

        app._refresh_history()

        summary = app.history_summary.get()
        self.assertIn("No employment or education records yet", summary)
        self.assertNotIn("0 month", summary)

    def test_an_unreadable_stored_value_is_reported_rather_than_shown_as_a_blank_row(self):
        added = self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1))
        reader = sqlite3.connect(self.store.database_path)
        with reader:
            reader.execute("UPDATE candidate_work_history SET employment_type='side-hustle'")
        reader.close()
        app = self.make_app()

        app._refresh_history()

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertEqual(app.work_tree.children, (),
                         "a list that cannot be read is left empty rather than shown as if it were fine")
        self.assertIn("nothing was changed", app.status.get())

    def test_a_database_error_is_reported_without_claiming_the_save_worked(self):
        app = self.make_app()
        self.fill_work(app)
        with mock.patch.object(self.store, "add_work_history",
                               side_effect=sqlite3.OperationalError("attempt to write a readonly database")):
            app._add_work_history()

        self.assertIn("Local database unavailable", MESSAGES.titles("showerror"))
        self.assertNotIn("record added", app.status.get())

    def test_deleting_the_profile_names_the_records_it_takes_with_it(self):
        self.store.save_profile(PROFILE)
        self.store.add_work_history("Sandbox Systems", "Data Engineer", date(2023, 4, 1))
        self.store.add_education("IIT Delhi", "B.Tech")
        app = self.make_app()
        CONFIG["Delete profile"] = True

        app._delete_profile()

        asked = MESSAGES.text("askyesno")
        self.assertIn("1 employment record(s)", asked)
        self.assertIn("1 education record(s)", asked)
        self.assertIn("job listings and applications are not deleted", asked)
        self.assertIsNone(self.store.get_profile())
        self.assertEqual(self.store.list_work_history(), (), "the confirmation was not a lie")

    def test_deleting_a_profile_with_no_history_does_not_mention_history(self):
        self.store.save_profile(PROFILE)
        app = self.make_app()
        CONFIG["Delete profile"] = True

        app._delete_profile()

        asked = MESSAGES.text("askyesno")
        self.assertNotIn("employment record", asked)
        self.assertIn("deleted", app.status.get())

    def test_history_records_are_not_listed_as_applications(self):
        """Adding a role must not make the Jobs tab think there is an application to show."""
        app = self.make_app()
        self.fill_work(app)

        app._add_work_history()

        self.assertEqual(self.store.list_jobs(), ())
        self.assertIsNone(self.store.get_tracker("j1"))


class ProgressReportTests(HandlerTestCase):
    """The progress line and report on the Application tracker tab.

    Handler-level: the widgets are stubs, so nothing here is evidence about how the dialog looks. What is
    checked is that the line counts what is stored, that a figure this app cannot measure is never shown as
    a zero, that the dialog carries the report's own caveats, and that a database that cannot be read does
    not stop the tracker from being drawn.
    """

    def applied_entry(self, listing_id: str, days_ago: int):
        return ApplicationActivity(ActivityKind.APPLIED, date(2026, 10, 15) - timedelta(days=days_ago),
                                   f"applied to {listing_id}")

    def filled_app(self):
        for index in range(6):
            listing_id = f"j{index}"
            self.store.save_job(sample_job(listing_id=listing_id))
            self.store.save_tracker(ApplicationTracker(listing_id))
            self.store.add_activity(listing_id, self.applied_entry(listing_id, 30 + index))
        self.store.add_activity("j0", ApplicationActivity(
            ActivityKind.RESPONSE, date(2026, 10, 10), "reply from j0"))
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.RESPONSE, date(2026, 10, 9), "reply from j1"))
        return self.make_app()

    def test_the_summary_line_counts_the_stored_records(self):
        app = self.filled_app()
        app.progress_summary = StringVar()

        app._refresh_progress()

        self.assertIn("6 application(s) recorded as sent", app.progress_summary.get())
        self.assertIn("2 with a recorded reply", app.progress_summary.get())

    def test_the_summary_line_withholds_a_percentage_below_the_floor(self):
        self.store.save_job(sample_job())
        app = self.make_app()
        app.progress_summary = StringVar()

        app._refresh_progress()

        self.assertIn("No application has been recorded as sent", app.progress_summary.get())
        self.assertNotIn("%", app.progress_summary.get())

    def test_a_database_that_cannot_be_read_says_so_instead_of_showing_a_wrong_figure(self):
        self.store.save_job(sample_job())
        app = self.make_app()
        app.progress_summary = StringVar()
        with mock.patch.object(self.store, "list_trackers",
                               side_effect=sqlite3.OperationalError("attempt to write a readonly database")):
            app._refresh_progress()

        self.assertIn("could not be computed", app.progress_summary.get())
        self.assertNotIn("recorded as sent", app.progress_summary.get())

    def test_the_summary_is_never_shown_above_a_report_it_does_not_match(self):
        """One computation feeds both surfaces, so the line and the dialog cannot disagree."""
        app = self.filled_app()
        app.progress_summary = StringVar()
        app._refresh_progress()
        report = career_agent_analytics.report_from_store(self.store, today=datetime.now().date())

        self.assertEqual(app.progress_summary.get(), report.headline())

    def test_the_report_dialog_prints_the_report_and_its_caveats(self):
        app = self.filled_app()
        app.status = StringVar()
        RecordingLabel.created = []
        RecordingToplevel.created = []

        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._show_progress_report()

        dialog = RecordingToplevel.created[-1]
        self.assertEqual(dialog.title_text, "Progress from your records (read-only)")
        self.assertEqual(dialog.requested_geometry, "900x640",
                         "a fixed size, so the Close button stays visible")
        texts = " ".join(label.options.get("text", "") for label in RecordingLabel.created)
        self.assertIn("Applications recorded as sent: 6", texts)
        self.assertIn("How to read this", texts)
        self.assertIn("not your ability", texts, "the caveats travel with the numbers into the window")
        self.assertIn("missing data, not a zero", texts)
        self.assertIn("read-only", app.status.get())

    def test_the_report_dialog_is_reachable_by_keyboard_and_closes(self):
        app = self.filled_app()
        RecordingLabel.created = []
        RecordingToplevel.created = []

        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._show_progress_report()

        dialog = RecordingToplevel.created[-1]
        self.assertIn("<Escape>", dialog.bindings)
        self.assertIn("<Return>", dialog.bindings)
        dialog.bindings["<Escape>"](None)
        self.assertTrue(dialog.destroyed)

    def test_opening_the_report_writes_nothing(self):
        app = self.filled_app()
        RecordingToplevel.created = []
        before = [self.store.get_tracker(f"j{i}") for i in range(6)]

        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._show_progress_report()

        self.assertEqual([self.store.get_tracker(f"j{i}") for i in range(6)], before)
        self.assertEqual(len(self.store.list_activity("j0")), 2)

    def test_an_unreadable_tracker_value_refuses_the_report_rather_than_guessing(self):
        self.store.save_job(sample_job())
        self.store.save_tracker(ApplicationTracker("j1"))
        reader = sqlite3.connect(self.store.database_path)
        with reader:
            reader.execute("UPDATE application_tracker SET status='casually_hired'")
        reader.close()
        app = self.make_app()
        RecordingToplevel.created = []

        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._show_progress_report()

        self.assertEqual(RecordingToplevel.created, [], "no report is drawn from a record it cannot read")
        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))


class IntegrationSurfaceTests(HandlerTestCase):
    """Drafting an email and previewing the calendar export: text on screen, and nothing else.

    Handler-level only, with stub widgets: this says nothing about how the dialog looks on any platform.
    What it checks is the part that would be a safety problem if it were wrong - that both actions exist
    on the reminders tab, that what they show names the application, marks the missing address and states
    that nothing was sent or created, that neither writes a record or a file, and that a selection that
    has gone away or a database that cannot be read is reported instead of producing a draft.
    """

    def reminders_tab(self, *, days=2, note="ask about the panel"):
        """A window whose store holds one application with a follow-up day."""
        root = RecordingToplevel()
        app = desktop.CareerAgentApp(root, database_path=Path(self._directory.name) / "window.sqlite3")
        self.addCleanup(app.store.close)
        app.store.save_job(sample_job())
        app.store.save_tracker(desktop.ApplicationTracker("j1").with_follow_up(
            date(2026, 10, 15) + timedelta(days=days), note=note))
        app._refresh_follow_ups()
        RecordingToplevel.created = []
        return root, app

    def dialog_labels(self, created_before):
        """Every label text drawn since a marker, which is what a dialog body ends up as."""
        return [label.text for label in RecordingLabel.created[created_before:]]

    def test_the_reminders_tab_offers_both_read_only_actions(self):
        _root, _app = self.reminders_tab()

        texts = [button.text for button in BUTTONS.created if button.text]

        self.assertIn("Preview the calendar export", texts)
        self.assertIn("Draft a follow-up email", texts)
        self.assertIn("Export to a calendar file", texts, "the local export must stay where it was")

    def test_the_preview_lists_the_events_and_writes_nothing(self):
        _root, app = self.reminders_tab()
        before = RecordingToplevel.created[:]
        marker = len(RecordingLabel.created)

        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._preview_calendar_export()

        dialog = RecordingToplevel.created[-1]
        self.assertNotIn(dialog, before, "a dialog must have been opened")
        self.assertEqual(dialog.requested_geometry, "900x640")
        self.assertIn("read-only", dialog.title_text)
        lines = "\n".join(self.dialog_labels(marker))
        self.assertIn("1 event(s) would be written", lines)
        self.assertIn("Follow up: AI Intern at Example Inc", lines)
        self.assertIn("follow-up-j1-20261017@ai-career-agent.local", lines)
        # The whole per-event line, as the checklist documents it: the day the person chose, the summary
        # the .ics writer builds, and the uid that identifies the event it would create.
        self.assertIn(
            "2026-10-17: Follow up: AI Intern at Example Inc"
            "  [follow-up-j1-20261017@ai-career-agent.local]",
            lines,
        )
        self.assertIn("Nothing has been written yet", lines)
        self.assertIn("no attendee is invited", lines)
        self.assertIn("nothing has been written yet", app.status.get())
        self.assertEqual(FILEDIALOG.opened, None, "a preview must not open a save dialog")
        self.assertEqual(
            [item.name for item in Path(self._directory.name).iterdir()
             if item.name not in ("logs", "handlers.sqlite3", "window.sqlite3")],
            [],
            "a preview must not write a file",
        )

    def test_the_preview_says_there_is_nothing_to_preview_when_no_day_is_recorded(self):
        root = RecordingToplevel()
        app = desktop.CareerAgentApp(root, database_path=Path(self._directory.name) / "window.sqlite3")
        self.addCleanup(app.store.close)
        app.store.save_job(sample_job())
        app.store.save_tracker(desktop.ApplicationTracker("j1"))
        RecordingToplevel.created = []

        app._preview_calendar_export()

        self.assertIn("Nothing to preview", MESSAGES.titles("showinfo"))
        self.assertEqual(RecordingToplevel.created, [], "no dialog should have been built")

    def test_the_draft_carries_the_stored_context_and_states_that_nothing_was_sent(self):
        _root, app = self.reminders_tab()
        app.follow_up_tree.selected = ("j1",)
        marker = len(RecordingLabel.created)

        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._draft_follow_up_email()

        dialog = RecordingToplevel.created[-1]
        self.assertIn("nothing is sent", dialog.title_text.lower())
        lines = "\n".join(self.dialog_labels(marker))
        self.assertIn("Subject: Following up on my application: AI Intern at Example Inc", lines)
        self.assertIn("ask about the panel", lines)
        self.assertIn("To: NOT SUPPLIED", lines)
        self.assertIn("Status: DRAFT ONLY", lines)
        self.assertIn("Missing, and not guessed:", lines)
        self.assertIn("Nothing was sent and nothing was created", lines)
        self.assertIn("Operation id: email-", lines)
        self.assertIn("nothing was sent", app.status.get())
        self.assertEqual(FILEDIALOG.opened, None)
        self.assertEqual(
            [item.name for item in Path(self._directory.name).iterdir()
             if item.name not in ("logs", "handlers.sqlite3", "window.sqlite3")],
            [],
            "a draft must not write a file",
        )

    def test_the_draft_refuses_with_nothing_selected_and_opens_nothing(self):
        """What the button does with no row chosen: the refusal the checklist names, and no dialog at all."""
        _root, app = self.reminders_tab()
        app.follow_up_tree.selected = ()
        app.jobs_tree.selected = ()
        before = RecordingToplevel.created[:]
        MESSAGES.reset()

        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._draft_follow_up_email()

        self.assertIn("Select an application", MESSAGES.titles("showinfo"))
        self.assertIn("Select the reminder this draft is about first.", MESSAGES.text("showinfo"))
        self.assertEqual(RecordingToplevel.created, before,
                         "a refusal must open no dialog window, let alone a draft")
        self.assertEqual(FILEDIALOG.opened, None, "a refusal must not open a file chooser")
        self.assertNotIn("nothing was sent", app.status.get(),
                         "a refusal must not report having drafted anything")

    def test_the_draft_does_not_move_the_application(self):
        _root, app = self.reminders_tab()
        app.follow_up_tree.selected = ("j1",)
        before = app.store.get_tracker("j1")

        with mock.patch.object(desktop.tk, "Toplevel", RecordingToplevel):
            app._draft_follow_up_email()

        after = app.store.get_tracker("j1")
        self.assertEqual(after.status, before.status)
        self.assertEqual(after.follow_up_on, before.follow_up_on)
        self.assertEqual(after.follow_up_note, before.follow_up_note)

    def test_the_draft_needs_a_selected_reminder(self):
        _root, app = self.reminders_tab()
        app.follow_up_tree.selected = ()

        app._draft_follow_up_email()

        self.assertIn("Select an application", MESSAGES.titles("showinfo"))
        self.assertEqual(RecordingToplevel.created, [])

    def test_a_selection_that_has_gone_is_reported_rather_than_drafted_from(self):
        _root, app = self.reminders_tab()
        app.follow_up_tree.selected = ("gone",)

        app._draft_follow_up_email()

        self.assertIn("Listing not found", MESSAGES.titles("showinfo"))
        self.assertEqual(RecordingToplevel.created, [])

    def test_an_application_without_a_recorded_day_is_refused_with_the_reason(self):
        root = RecordingToplevel()
        app = desktop.CareerAgentApp(root, database_path=Path(self._directory.name) / "window.sqlite3")
        self.addCleanup(app.store.close)
        app.store.save_job(sample_job())
        app.store.save_tracker(desktop.ApplicationTracker("j1"))
        app._refresh_follow_ups()
        app.follow_up_tree.selected = ("j1",)
        RecordingToplevel.created = []

        app._draft_follow_up_email()

        self.assertIn("Nothing to draft from", MESSAGES.titles("showinfo"))
        self.assertIn("no follow-up day recorded", MESSAGES.text("showinfo"))
        self.assertEqual(RecordingToplevel.created, [])

    def test_a_database_that_cannot_be_read_refuses_the_preview_instead_of_drawing_one(self):
        _root, app = self.reminders_tab()
        app.store.close()

        app._preview_calendar_export()

        self.assertIn("Local database unavailable", MESSAGES.titles("showerror"))
        self.assertNotIn("Traceback", MESSAGES.text("showerror"))
        self.assertEqual(RecordingToplevel.created, [])

    def test_a_database_that_cannot_be_read_refuses_the_draft_too(self):
        _root, app = self.reminders_tab()
        app.follow_up_tree.selected = ("j1",)
        app.store.close()

        app._draft_follow_up_email()

        self.assertIn("Local database unavailable", MESSAGES.titles("showerror"))
        self.assertEqual(RecordingToplevel.created, [])


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

    def test_the_history_tab_is_the_window_s_own_tab_and_not_more_profile_rows(self):
        """The reason the tab exists: employment and education are records, not ten more form fields.

        The profile form is the summary a person holds in their head, and it was already at the limit of
        what the window shows at ``1120x760``; records that grow over a career get a list of their own.
        """
        app, _root, _database = self.build_app()
        notebook = Notebook.created[-1]

        self.assertIn("Work history & study", notebook.labels())
        frames = {text: frame for frame, text in notebook.tabs}
        self.assertIs(frames["Work history & study"], app.history_tab)
        self.assertEqual(notebook.labels()[0], "Candidate profile")
        self.assertIs(frames["Candidate profile"], app.profile_tab)
        # The tab is built from real widgets, so both lists and both forms exist over the real store.
        self.assertEqual(app.store.list_work_history(), ())
        self.assertEqual(sorted(app.work_vars), ["employer", "end_date", "job_title", "start_date",
                                                 "summary"])
        self.assertEqual(sorted(app.study_vars), ["completion_date", "discipline", "institution",
                                                 "qualification", "start_date"])
        self.assertEqual(app.work_type.get(), "unknown", "a new role starts with no claimed type")

    def test_saving_the_profile_does_not_write_a_history_record(self):
        """The two are separate on purpose: editing a summary must not invent the records behind it."""
        app, _root, _database = self.build_app()
        app.profile_vars["country"].set("India")
        app.profile_vars["experience"].set("3")

        app._save_profile()

        self.assertIsNotNone(app.store.get_profile())
        self.assertEqual(app.store.list_work_history(), ())
        self.assertEqual(app.store.list_education(), ())

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

    def test_opening_and_closing_the_window_are_recorded_in_the_log(self):
        """The sequence is what makes the log useful later, so both ends of a run are written."""
        app, _root, database = self.build_app()
        log = log_path(database_path=database)

        started = log.read_text(encoding="utf-8")
        app.close()
        finished = log.read_text(encoding="utf-8")

        self.assertIn("event=app.started", started)
        self.assertIn("event=database.opened", started)
        self.assertIn("event=app.stopped", finished)
        self.assertGreater(len(finished.splitlines()), len(started.splitlines()))


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
        self.assertEqual(payload["format_version"], 2)
        self.assertIn("privacy_note", payload)
        self.assertEqual(payload["profile"]["degree_discipline"], "ECE")
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(payload["jobs"][0]["application_tracker"]["status"], "confirmed")
        self.assertIn("Export complete", MESSAGES.titles())
        self.assertIn("Exported 1 jobs", self.app.status.get())

    def test_the_export_is_recorded_with_counts_and_no_profile_values(self):
        self.app._export()

        logged = log_path(database_path=Path(self.store.database_path)).read_text(encoding="utf-8")
        self.assertIn("event=export.written detail=jobs=1", logged)
        self.assertNotIn("ECE", logged)
        self.assertNotIn("India", logged)

    def test_a_failed_export_is_recorded_as_a_failure(self):
        FILEDIALOG.path = str(Path(self._directory.name) / "absent-folder" / "export.json")

        self.app._export()

        logged = read_lines(database_path=Path(self.store.database_path), limit=1)
        self.assertEqual(len(logged), 1)
        self.assertIn("event=export.failed", logged[0])

    def test_the_export_carries_the_activity_history_as_stored(self):
        """The history is part of the person's data, so taking it out must not depend on this build."""
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.APPLIED, date(2026, 10, 12), "Sent through the employer portal."))
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.RESPONSE, date(2026, 10, 20), "They asked for transcripts."))

        self.app._export()

        entries = self.exported()["jobs"][0]["activity"]
        self.assertEqual([entry["occurred_on"] for entry in entries], ["2026-10-12", "2026-10-20"])
        self.assertEqual(entries[0]["kind"], "applied")
        self.assertEqual(entries[0]["detail"], "Sent through the employer portal.")
        self.assertNotIn("kind_recognised", entries[0],
                         "the marker is only added for a value this version cannot label")

    def test_an_activity_kind_this_version_cannot_read_is_exported_and_marked(self):
        """Otherwise one row a later version wrote would stop the person exporting anything."""
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.NOTE, date(2026, 10, 12), "Called the recruiter."))
        self.store._connection.execute("UPDATE application_activity SET kind = 'telerecruited'")
        self.store._connection.commit()

        self.app._export()

        self.assertIn("Export complete", MESSAGES.titles())
        entry, = self.exported()["jobs"][0]["activity"]
        self.assertEqual(entry["kind"], "telerecruited")
        self.assertIs(entry["kind_recognised"], False)
        self.assertEqual(entry["detail"], "Called the recruiter.")

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

    @unittest.skipUnless(os.name == "posix", "a filesystem refusing the file mode is a POSIX scenario")
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
        self.assertIn("MATCHING (explainable, and never a prediction)", report)
        self.assertIn("Overlap score:", report)
        self.assertIn("How much was known:", report)
        self.assertIn("not a probability of being hired", report,
                      "the disclaimer travels with the comparison, in the window too")
        self.assertTrue(
            self.app.status.get().startswith(f"Eligibility for {job.role_title}: {expected.decision.value};"),
            f"the status line must lead with the decision and add the matching reading: "
            f"{self.app.status.get()!r}")

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
        self.assertEqual(payload["format_version"], 2)
        self.assertEqual(payload["profile"]["candidate_country"], "India")
        self.assertEqual(payload["jobs"][0]["application_tracker"]["status_evidence"], "Employer email")
        self.assertIn("personal information", payload["privacy_note"])
        self.assertIn("Export complete", MESSAGES.titles())


class ActivityHistoryTests(HandlerTestCase):
    """The activity panel: append, read back, delete, and never touch the status from here."""

    def setUp(self):
        super().setUp()
        self.store.save_job(sample_job())
        self.app = self.make_app()
        self.app.activity_tree = Tree()
        self.app.tracker_tree.selected = ("j1",)

    def open_activity_dialog(self):
        """Run the real handler and return the dialog's variables plus its save command."""
        created = []
        original = desktop.tk.StringVar

        def recording(*args, **kwargs):
            variable = original(*args, **kwargs)
            created.append(variable)
            return variable

        desktop.tk.StringVar = recording
        self.addCleanup(setattr, desktop.tk, "StringVar", original)
        self.app._add_activity()
        self.assertEqual(len(created), 3, "the dialog has a kind, a date and a detail field")
        return created[0], created[1], created[2], BUTTONS.command

    def test_selecting_an_application_shows_its_history_oldest_first(self):
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.RESPONSE, date(2026, 10, 20), "They replied."))
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.APPLIED, date(2026, 10, 12), "Applied through the portal."))

        self.app._refresh_activity()

        self.assertEqual([values[0] for _iid, values in self.app.activity_tree.inserted],
                         ["2026-10-12", "2026-10-20"], "rows are shown oldest first")
        self.assertEqual(self.app.activity_tree.inserted[0][1][1], "I applied")
        self.assertEqual(self.app.activity_tree.inserted[0][1][2], "Applied through the portal.")

    def test_selecting_a_row_loads_that_application_s_history(self):
        """The wiring the panel depends on: choosing an application is what loads its entries."""
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.APPLIED, date(2026, 10, 12), "Applied through the portal."))
        self.app.tracker_tree.children = ("j1",)

        self.app._select_tracker()

        self.assertEqual([values[2] for _iid, values in self.app.activity_tree.inserted],
                         ["Applied through the portal."])
        self.assertEqual(self.app.selected_job_id, "j1")

    def test_saving_an_entry_stores_it_and_leaves_the_status_alone(self):
        kind_var, date_var, detail_var, apply = self.open_activity_dialog()
        kind_var.set("applied")
        date_var.set("2026-10-12")
        detail_var.set("Sent through the employer portal.")

        apply()

        stored, = self.store.list_activity("j1")
        self.assertIs(stored.kind, ActivityKind.APPLIED)
        self.assertEqual(stored.occurred_on, date(2026, 10, 12))
        self.assertEqual(stored.detail, "Sent through the employer portal.")
        self.assertIsNone(self.store.get_tracker("j1"), "an entry must not create a tracker record")
        self.assertIn("status was not changed", self.app.status.get())
        self.assertIn("2026-10-12", self.app.status.get())

    def test_a_bad_date_is_refused_and_nothing_is_written(self):
        kind_var, date_var, detail_var, apply = self.open_activity_dialog()
        kind_var.set("applied")
        date_var.set("12/10/2026")
        detail_var.set("Sent it.")

        apply()

        self.assertIn("Activity entry not saved", MESSAGES.titles())
        self.assertIn("YYYY-MM-DD", MESSAGES.messages[-1][2])
        self.assertEqual(self.store.list_activity("j1"), ())
        self.assertNotIn("status was not changed", self.app.status.get())

    def test_a_blank_detail_is_refused_and_nothing_is_written(self):
        kind_var, date_var, detail_var, apply = self.open_activity_dialog()
        kind_var.set("note")
        date_var.set("2026-10-12")
        detail_var.set("   ")

        apply()

        self.assertIn("Activity entry not saved", MESSAGES.titles())
        self.assertEqual(self.store.list_activity("j1"), ())

    def test_a_database_failure_is_reported_and_not_as_success(self):
        kind_var, date_var, detail_var, apply = self.open_activity_dialog()
        kind_var.set("note")
        date_var.set("2026-10-12")
        detail_var.set("Called the recruiter.")

        with mock.patch.object(self.store, "add_activity", side_effect=sqlite3.OperationalError("readonly")):
            apply()

        self.assertNotIn("Activity entry saved", self.app.status.get())
        self.assertEqual(self.store.list_activity("j1"), ())

    def test_adding_an_entry_needs_a_selected_application(self):
        self.app.tracker_tree.selected = ()

        self.app._add_activity()

        self.assertIn("Select application", MESSAGES.titles())
        self.assertEqual(self.store.list_activity("j1"), ())

    def test_an_application_deleted_elsewhere_is_refused_before_a_dialog_opens(self):
        self.store.delete_job("j1")
        BUTTONS.clear()

        self.app._add_activity()

        self.assertIn("Application not saved", MESSAGES.titles())
        self.assertIsNone(BUTTONS.command, "no dialog should have been built")

    def test_deleting_reports_the_entry_and_asks_first(self):
        activity_id = self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.NOTE, date(2026, 10, 12), "Called the recruiter."))
        self.app._refresh_activity()
        self.app.activity_tree.selected = (str(activity_id),)
        CONFIG["Delete activity entry?"] = True

        self.app._delete_activity()

        self.assertIn("Delete activity entry?", MESSAGES.titles())
        self.assertIn("Called the recruiter.", MESSAGES.messages[-1][2])
        self.assertEqual(self.store.list_activity("j1"), ())
        self.assertIn("Activity entry deleted", self.app.status.get())

    def test_declining_the_confirmation_keeps_the_entry(self):
        activity_id = self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.NOTE, date(2026, 10, 12), "Called the recruiter."))
        self.app._refresh_activity()
        self.app.activity_tree.selected = (str(activity_id),)
        CONFIG["Delete activity entry?"] = False

        self.app._delete_activity()

        self.assertEqual(len(self.store.list_activity("j1")), 1)
        self.assertIn("cancelled", self.app.status.get())

    def test_deleting_something_already_gone_is_not_reported_as_a_deletion(self):
        activity_id = self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.NOTE, date(2026, 10, 12), "Called the recruiter."))
        self.app._refresh_activity()
        self.app.activity_tree.selected = (str(activity_id),)
        self.store.delete_activity(activity_id)
        CONFIG["Delete activity entry?"] = True

        self.app._delete_activity()

        self.assertNotIn("Activity entry deleted", self.app.status.get())
        self.assertIn("already gone", self.app.status.get())

    def test_deleting_without_a_selected_entry_changes_nothing(self):
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.NOTE, date(2026, 10, 12), "Called the recruiter."))
        self.app._refresh_activity()
        self.app.activity_tree.selected = ()

        self.app._delete_activity()

        self.assertIn("Select activity entry", MESSAGES.titles())
        self.assertEqual(len(self.store.list_activity("j1")), 1)

    def test_a_stored_entry_this_version_cannot_read_is_reported_not_rendered(self):
        """A later version's kind must not reach the panel as if it were understood."""
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.NOTE, date(2026, 10, 12), "Called the recruiter."))
        self.store._connection.execute("UPDATE application_activity SET kind = 'telerecruited'")
        self.store._connection.commit()

        self.app._refresh_activity()

        self.assertEqual(self.app.activity_tree.rows, ())
        self.assertIn("Saved record could not be read", MESSAGES.titles())
        self.assertIn("telerecruited", MESSAGES.messages[-1][2])

    def test_the_history_is_cleared_when_no_application_is_selected(self):
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.NOTE, date(2026, 10, 12), "Called the recruiter."))
        self.app._refresh_activity()
        self.assertEqual(len(self.app.activity_tree.inserted), 1)

        self.app.tracker_tree.selected = ()
        self.app._refresh_activity()

        self.assertEqual(self.app.activity_tree.get_children(), ())
        self.assertEqual(self.app.activity_tree.rows, (), "no rows may be left from another record")


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
        # The application keeps its own event log in a ``logs`` folder beside the database, so what a
        # cancelled action must not do is change what is already there - not make the folder empty.
        before = {
            path.name: (path.read_bytes() if path.is_file() else None)
            for path in sorted(Path(self._directory.name).rglob("*"))
        }

        self.app._backup_database()

        after = {
            path.name: (path.read_bytes() if path.is_file() else None)
            for path in sorted(Path(self._directory.name).rglob("*"))
        }
        self.assertEqual(after, before, "a cancelled backup changed the folder")
        self.assertFalse(self.destination.exists())
        self.assertFalse(any("backup" in path.name for path in Path(self._directory.name).iterdir()))
        self.assertEqual(MESSAGES.calls, [])
        self.assertIn("cancelled", self.app.status.get())

    def test_a_written_backup_and_a_refusal_are_both_recorded(self):
        """A backup that never happened must not look like one that did."""
        self.app._backup_database()
        self.app._backup_database()  # the same destination again: refused, and never overwritten

        lines = read_lines(database_path=Path(self.store.database_path), limit=100)
        events = [line for line in lines if "event=backup." in line]
        self.assertEqual([line.partition(" event=")[2].split(" ", 1)[0] for line in events],
                         ["backup.written", "backup.refused"])
        self.assertIn("jobs=1 trackers=0 schema=", events[0])
        self.assertNotIn("Confidential Employer", "\n".join(events))

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


class DataImportHandlerTests(HandlerTestCase):
    """The import button: it shows the plan, asks, and never replaces what is already stored.

    The stub harness drives the handler, not the pixels; a real window is part of the consolidated
    manual checklist. What is checked here is the decision sequence - refuse, plan, ask, write - and that
    a declined confirmation leaves the database exactly as it was.
    """

    def setUp(self):
        super().setUp()
        self.exports = Path(self.store.database_path).parent

    def write_export(self, *, name: str = "export.json", role: str = "Data Engineer",
                     profile: bool = True) -> Path:
        """A file this app wrote, holding one invented application, made through the real exporter."""
        from career_agent import importer as import_export
        from career_agent.core import CandidateProfile

        path = self.exports / name
        with CareerStore(str(self.exports / "source.sqlite3")) as source:
            if profile:
                source.save_profile(CandidateProfile(candidate_country="India",
                                                     skills=frozenset({"Python"})))
            source.save_job(JobListing("imported-1", "fixture", "Fixture",
                                       "https://jobs.example.invalid/imported-1", "Imported Systems",
                                       role, availability_status=Availability.OPEN))
            source.save_tracker(ApplicationTracker("imported-1"))
            import_export.write_export(source, path)
        return path

    def test_the_import_shows_the_plan_and_applies_it_only_after_yes(self):
        path = self.write_export()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        CONFIG["Import this file?"] = True

        app._import_data()

        self.assertIn("Import complete", MESSAGES.titles())
        listing = self.store.get_job("imported-1")
        assert listing is not None
        self.assertEqual(listing.employer_name, "Imported Systems")
        self.assertEqual(self.store.get_profile().candidate_country, "India")
        self.assertIn("Import complete:", app.status.get())

    def test_a_declined_confirmation_writes_nothing(self):
        path = self.write_export()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        CONFIG["Import this file?"] = False

        app._import_data()

        self.assertIsNone(self.store.get_job("imported-1"))
        self.assertEqual(self.store.list_jobs(), ())
        self.assertIn("Import cancelled", app.status.get())
        self.assertIn("Apply it now?", MESSAGES.text("askyesno"))

    def test_a_file_that_is_not_an_export_is_refused_without_a_dialog_to_continue(self):
        broken = self.exports / "broken.json"
        broken.write_text("{}", encoding="utf-8")
        app = self.make_app()
        FILEDIALOG.path = str(broken)

        app._import_data()

        self.assertIn("Nothing was imported", MESSAGES.titles())
        self.assertIn("format_version", MESSAGES.text("showerror"))
        self.assertNotIn("Import this file?", MESSAGES.titles(),
                         "a refused file must not reach the confirmation step")
        self.assertEqual(self.store.list_jobs(), ())

    def test_cancelling_the_file_chooser_does_nothing_at_all(self):
        app = self.make_app()
        FILEDIALOG.path = ""

        app._import_data()

        self.assertEqual(MESSAGES.titles(), [])
        self.assertEqual(self.store.list_jobs(), ())

    def test_a_second_import_of_the_same_file_leaves_everything_as_it_is(self):
        path = self.write_export()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        CONFIG["Import this file?"] = True

        app._import_data()
        MESSAGES.reset()
        app._import_data()

        self.assertIn("left 1 already-stored listing(s) as they were", MESSAGES.text("showinfo"))
        self.assertEqual(len(self.store.list_jobs()), 1)

    def test_a_stored_profile_is_kept_and_the_dialog_says_so(self):
        from career_agent.core import CandidateProfile

        self.store.save_profile(CandidateProfile(candidate_country="Canada", skills=frozenset({"Go"})))
        path = self.write_export()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        CONFIG["Import this file?"] = True

        app._import_data()

        self.assertIn("your stored profile is kept", MESSAGES.text("askyesno"))
        self.assertEqual(self.store.get_profile().candidate_country, "Canada")


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

    def test_restoring_a_backup_from_an_earlier_schema_reports_the_update(self):
        """The dialog describes what was installed *and* what reopening it did to that file.

        Leaving the older version number unexplained would read as a contradiction: the summary line
        is built from the validated file, while the update is what this window recorded when it
        reopened the database.
        """
        older = Path(self._directory.name) / "older-backup.sqlite3"
        steps = tuple(step for step in store_module._MIGRATIONS if step[0] == 1)
        with mock.patch.object(store_module, "_MIGRATIONS", steps):
            with CareerStore(str(older)) as legacy:
                legacy.save_job(sample_job(listing_id="only-in-the-older-backup"))
        FILEDIALOG.path = str(older)

        self.app._restore_database()

        self.assertIn("Restore complete", MESSAGES.titles())
        body = MESSAGES.text("showinfo")
        self.assertIn("older schema (version 1)", body)
        self.assertIn(f"updated to schema version {SCHEMA_VERSION}", body)
        self.assertEqual(self.listing_ids(), ["only-in-the-older-backup"])
        self.assertEqual(
            self.app.store._connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION,
            "the reopened database must record the updated schema",
        )

    def test_a_current_backup_does_not_mention_a_schema_update(self):
        self.app._restore_database()

        self.assertIn("Restore complete", MESSAGES.titles())
        self.assertNotIn("older schema", MESSAGES.text("showinfo"))

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
        connection.execute(
            """INSERT INTO application_tracker
                   (listing_id, status, status_evidence, candidate_confirmed, updated_at)
               VALUES ('missing', 'discovered', NULL, 0, '2026-01-01')"""
        )
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

    def test_a_refused_document_is_recorded_by_type_and_never_by_text(self):
        """The log explains that a read failed without repeating anything the document said."""
        unreadable = Path(self._directory.name) / "resume.docx"
        unreadable.write_text("SECRET-DOCUMENT-TEXT that is not a Word file at all", encoding="utf-8")
        app = self.make_app()

        _app, dialog = self.import_resume(unreadable)

        self.assertIsNone(dialog)
        self.assertIn("Resume not imported", MESSAGES.titles())
        logged = log_path(database_path=Path(self.store.database_path)).read_text(encoding="utf-8")
        self.assertIn("event=resume.failed detail=type=ResumeUnreadable", logged)
        self.assertNotIn("SECRET-DOCUMENT-TEXT", logged)

    def test_a_readable_document_is_recorded_by_counts_only(self):
        response = self.import_resume(self.write_docx())

        self.assertIsNotNone(response[1])
        logged = log_path(database_path=Path(self.store.database_path)).read_text(encoding="utf-8")
        self.assertIn("event=resume.proposed detail=format=DOCX proposals=", logged)
        self.assertNotIn("ada@example.com", logged)

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


class TreeRowReadbackTests(unittest.TestCase):
    """The tree double reads a row back the way a real tree does: the values it holds now.

    A workflow that refreshes a list and then reads the refreshed rows back is asking the double what
    the window shows. Answering with the values of the first insert ever made for that id would let a
    stale list pass for a current one - which is what a refresh workflow has to be able to catch.
    """

    def test_a_row_refreshed_under_the_same_id_reads_back_as_the_new_values(self):
        tree = Tree()
        tree.insert("", "end", iid="7", values=("first",))

        self.assertEqual(tree.item("7", "values"), ("first",))

        tree.delete("7")
        tree.insert("", "end", iid="7", values=("second",))

        self.assertEqual(
            tree.item("7", "values"), ("second",),
            "a row inserted again under the same id must read back as the values it now holds",
        )

    def test_deleting_the_selected_row_leaves_nothing_selected(self):
        tree = Tree()
        tree.insert("", "end", iid="7", values=("a row",))
        tree.selection_set("7")

        tree.delete("7")

        self.assertEqual(tree.selection(), (), "a deleted row cannot still be selected")

    def test_a_refresh_of_every_row_drops_the_selection_like_a_real_tree(self):
        """Every refresh here deletes each row and inserts it again, which is what a person's edit does."""

        tree = Tree()
        for listing_id in ("j1", "j2"):
            tree.insert("", "end", iid=listing_id, values=(listing_id,))
        tree.selection_set("j1")

        for listing_id in ("j1", "j2"):
            tree.delete(listing_id)
        for listing_id in ("j1", "j2"):
            tree.insert("", "end", iid=listing_id, values=(listing_id, "renamed"))

        self.assertEqual(tree.selection(), (), "the rebuilt list must not claim a row is still selected")
        self.assertEqual(tree.item("j1", "values"), ("j1", "renamed"))

    def test_the_arrow_keys_navigate_from_the_focus_item_the_way_tk_does(self):
        """Tk 8.6's ``ttk::treeview::Keynav`` moves the tree's *focus item*, and does nothing without one.

        This is the behaviour the display-backed workflow depends on when it presses a real Down key, and
        the CI run at ``7323457`` is why it is modelled: on a real window the key did nothing, because the
        check had selected a row without ever setting the item Tk navigates from - the thing a click sets.
        """
        tree = Tree()
        for item in ("j1", "j2"):
            tree.insert("", "end", iid=item, values=(item,))
        followed = []
        tree.bind("<<TreeviewSelect>>", lambda _event: followed.append(tree.selection()))

        tree.event_generate("<Down>")
        self.assertEqual(tree.selection(), (), "Tk navigates from nowhere when no item holds the focus")
        self.assertEqual(followed, [], "nothing was selected, so nothing may claim a selection changed")

        tree.focus("j1")
        tree.event_generate("<Down>")

        self.assertEqual(tree.selection(), ("j2",), "the arrow key must select the following row")
        self.assertEqual(tree.focus(), "j2", "and the focus item moves with it, as Tk moves it")
        self.assertEqual(followed, [("j2",)], "the selection change must run the bound handler once")

    def test_a_deleted_row_is_no_longer_the_focus_item(self):
        tree = Tree()
        tree.insert("", "end", iid="j1", values=("a row",))
        tree.focus("j1")

        tree.delete("j1")

        self.assertEqual(tree.focus(), "", "Tk drops the focus item when its row is deleted")

    def test_a_deleted_row_cannot_be_read_back(self):
        tree = Tree()
        tree.insert("", "end", iid="8", values=("gone",))
        tree.delete("8")

        with self.assertRaises(KeyError):
            tree.item("8", "values")

        tree.insert("", "end", iid="9", values=("here",))
        self.assertEqual(tree.item("9", "values"), ("here",))
        self.assertNotIn("8", tree.get_children(), "a deleted row is no longer a child")


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


class FollowUpTabTests(HandlerTestCase):
    """The Follow-ups tab: what it lists, what setting one does, and what it must never do.

    The window is driven through the same stub harness the other tab tests use, so these are tests of
    the handler logic behind the widgets - not of pixels. A real Tk session is part of the consolidated
    manual checklist, and nothing here claims to have run one.
    """

    def make_follow_up_app(self):
        """The app with the widgets the Follow-ups tab builds, wired to the same stub harness."""
        app = self.make_app()
        app.follow_up_tab = Widget()
        app.follow_up_summary = StringVar()
        app.follow_up_day = StringVar()
        app.follow_up_note = StringVar()
        app.follow_up_tree = Tree()
        app.follow_up_tree.selected = ()
        MESSAGES.reset()
        FILEDIALOG.path = ""
        return app

    def add_application(self, listing_id: str, *, days: int | None, role: str = "Data Engineer",
                        note: str | None = None) -> None:
        """Store one application with (or without) a follow-up day relative to today."""
        self.store.save_job(JobListing(listing_id, "fixture", "Fixture",
                                       f"https://jobs.example.invalid/{listing_id}", "Sandbox Systems",
                                       role, availability_status=Availability.UNKNOWN))
        self.store.save_tracker(ApplicationTracker(listing_id))
        if days is not None:
            self.store.save_tracker(ApplicationTracker(listing_id).with_follow_up(
                date.today() + timedelta(days=days), note=note))

    def test_the_tab_lists_the_recorded_days_nearest_action_first(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=5, role="Designer")
        self.add_application("j2", days=-2, role="Data Engineer", note="ask about the panel")
        self.add_application("j3", days=None, role="Analyst")

        app._refresh_follow_ups()

        rows = app.follow_up_tree.inserted
        self.assertEqual([iid for iid, _ in rows], ["j2", "j1"],
                         "the overdue one comes first, and the undated one is not listed at all")
        self.assertIn("2 day(s) overdue", rows[0][1][4])
        self.assertIn("ask about the panel", rows[0][1][5])
        self.assertIn("1 overdue", app.follow_up_summary.get())

    def test_the_summary_distinguishes_nothing_recorded_from_nothing_due(self):
        app = self.make_follow_up_app()

        app._refresh_follow_ups()
        self.assertIn("No follow-ups are recorded", app.follow_up_summary.get())

        self.add_application("j1", days=6)
        app._refresh_follow_ups()
        self.assertIn("none are due yet", app.follow_up_summary.get())

    def test_selecting_a_row_puts_its_own_day_and_note_in_the_fields(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=3, note="chase the recruiter")
        app.follow_up_tree.selected = ("j1",)

        app._select_follow_up()

        expected = (date.today() + timedelta(days=3)).isoformat()
        self.assertEqual(app.follow_up_day.get(), expected)
        self.assertEqual(app.follow_up_note.get(), "chase the recruiter")

    def test_setting_a_day_moves_no_status_and_says_so(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=None)
        app.follow_up_tree.selected = ("j1",)
        app.follow_up_day.set((date.today() + timedelta(days=2)).isoformat())
        app.follow_up_note.set("nudge them")

        app._set_follow_up()

        tracker = self.store.get_tracker("j1")
        assert tracker is not None
        self.assertEqual(tracker.follow_up_on, date.today() + timedelta(days=2))
        self.assertEqual(tracker.follow_up_note, "nudge them")
        self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED,
                         "a reminder never advances an application")
        self.assertIn("the application's status was not changed", app.status.get())

    def test_a_mistyped_day_is_refused_before_anything_is_written(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=None)
        app.follow_up_tree.selected = ("j1",)
        app.follow_up_day.set("next tuesday")

        app._set_follow_up()

        self.assertIn("Give the day", MESSAGES.titles())
        self.assertIn("YYYY-MM-DD", MESSAGES.text("showinfo"))
        tracker = self.store.get_tracker("j1")
        assert tracker is not None
        self.assertIsNone(tracker.follow_up_on, "nothing was written from a day that is not a day")

    def test_setting_a_day_with_nothing_selected_asks_rather_than_guessing(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=None)

        app._set_follow_up()

        self.assertIn("Select an application", MESSAGES.titles())
        self.assertIn("Application tracker", MESSAGES.text("showinfo"),
                      "the message says where an application can be selected")
        self.assertIsNone(self.store.get_tracker("j1").follow_up_on)

    def test_the_first_follow_up_day_is_recordable_from_the_selected_application(self):
        """The regression: the first reminder for an application could not be recorded at all.

        This tab lists the applications that already hold a day, so the list is empty before the first
        one is set - and the button used to take its subject from that empty list, which reported
        "select an application" to somebody who had one selected and left the first follow-up day
        unsettable from anywhere in this application. The subject is now the selected application.
        """
        app = self.make_follow_up_app()
        self.add_application("j1", days=None)
        app.tracker_tree.selected = ("j1",)
        app._refresh_follow_ups()
        self.assertEqual(app.follow_up_tree.inserted, (),
                         "the reminder list cannot hold an application that has no day yet")
        day = date.today() + timedelta(days=3)
        app.follow_up_day.set(day.isoformat())
        app.follow_up_note.set("send the portfolio")

        app._set_follow_up()

        tracker = self.store.get_tracker("j1")
        assert tracker is not None
        self.assertNotIn("Select an application", MESSAGES.titles())
        self.assertEqual(tracker.follow_up_on, day)
        self.assertEqual(tracker.follow_up_note, "send the portfolio")
        self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED,
                         "a reminder never advances an application")
        self.assertIn("the application's status was not changed", app.status.get())
        self.assertEqual([iid for iid, _values in app.follow_up_tree.inserted], ["j1"],
                         "the reminder just recorded is listed at once")

    def test_the_day_and_note_fields_follow_the_selected_application(self):
        """The fields describe the selection, so one application's note cannot be saved onto another."""
        app = self.make_follow_up_app()
        self.add_application("j1", days=4, note="chase the reply")
        self.add_application("j2", days=None)

        app.tracker_tree.selected = ("j1",)
        app._select_tracker()
        self.assertEqual(app.follow_up_day.get(), (date.today() + timedelta(days=4)).isoformat())
        self.assertEqual(app.follow_up_note.get(), "chase the reply")

        app.tracker_tree.selected = ("j2",)
        app._select_tracker()
        self.assertEqual(app.follow_up_day.get(), "",
                         "another application's day was left in the fields")
        self.assertEqual(app.follow_up_note.get(), "")

    def test_a_selection_whose_record_vanished_is_reported_and_writes_nothing(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=2)
        app.tracker_tree.selected = ("j1",)
        self.store._connection.execute("DELETE FROM application_tracker WHERE listing_id = 'j1'")
        self.store._connection.commit()
        app.follow_up_day.set((date.today() + timedelta(days=9)).isoformat())

        app._set_follow_up()

        self.assertIn("Listing not found", MESSAGES.titles())
        self.assertIsNone(self.store.get_tracker("j1"),
                          "no application record was invented for a selection that is gone")
        self.assertNotIn("Follow-up set", app.status.get())

    def test_a_refreshed_list_does_not_refill_the_fields_from_another_application(self):
        """The regression: clearing a reminder appeared not to have happened.

        Every write here rebuilds the list, and a rebuilt list leaves no row selected - which is exactly
        the moment the tab's own selection binding runs. Reading the subject from the application selected
        on another tab at that moment put a *different* application's day back into the fields, so the
        reminder that had just been cleared was still on screen, under the name of the application it did
        not belong to. A test with stub widgets has to dispatch that binding itself: real Tk fires it when
        the rows are deleted and re-inserted, and the stub tree models the rebuilt list, not Tk's events.
        """
        app = self.make_follow_up_app()
        self.add_application("j1", days=2, note="chase the reply")
        self.add_application("j2", days=9, note="a different application's day")
        app.jobs_tree.selected = ("j2",)
        app.follow_up_tree.selected = ("j1",)
        app._select_follow_up()
        self.assertEqual(app.follow_up_day.get(), (date.today() + timedelta(days=2)).isoformat())

        app._clear_follow_up()
        app.follow_up_tree.selected = ()
        app._select_follow_up()

        self.assertIsNone(self.store.get_tracker("j1").follow_up_on)
        self.assertEqual(app.follow_up_day.get(), "",
                         "the fields show a day after the reminder was cleared")
        self.assertEqual(app.follow_up_note.get(), "")

    def test_the_buttons_still_fall_back_to_the_selected_application(self):
        """What the fallback is for: the first reminder, on an application nothing has recorded yet."""
        app = self.make_follow_up_app()
        self.add_application("j1", days=None)
        app.follow_up_tree.selected = ()
        app.jobs_tree.selected = ("j1",)

        app.follow_up_day.set((date.today() + timedelta(days=5)).isoformat())
        app._set_follow_up()

        tracker = self.store.get_tracker("j1")
        assert tracker is not None
        self.assertEqual(tracker.follow_up_on, date.today() + timedelta(days=5))

    def test_clearing_a_follow_up_asks_first_and_keeps_the_application(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=-1, note="chase them")
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.APPLIED, date(2026, 10, 10), "Sent through the employer portal."))
        self.store.add_activity("j1", ApplicationActivity(
            ActivityKind.RESPONSE, date(2026, 10, 12), "A recruiter asked for a time slot."))
        history = self.activity_history("j1")
        self.assertEqual(len(history), 2,
                         "the fixture's history must exist, or comparing it proves nothing")
        app.follow_up_tree.selected = ("j1",)
        CONFIG["Clear this follow-up?"] = False

        app._clear_follow_up()
        self.assertIsNotNone(self.store.get_tracker("j1").follow_up_on, "a declined confirmation does nothing")
        self.assertEqual(self.activity_history("j1"), history,
                         "a declined confirmation wrote to the application's history")

        CONFIG["Clear this follow-up?"] = True
        app._clear_follow_up()

        tracker = self.store.get_tracker("j1")
        assert tracker is not None
        self.assertIsNone(tracker.follow_up_on)
        self.assertIsNone(tracker.follow_up_note)
        self.assertEqual(tracker.status, ApplicationStatus.DISCOVERED)
        self.assertEqual(app.follow_up_day.get(), "")
        self.assertEqual(app.follow_up_tree.inserted, (), "the list is refreshed after clearing")
        self.assertEqual(
            self.activity_history("j1"), history,
            "the confirmation promises the application's history stays as it is, so clearing a day must "
            "not add an entry, drop one, or rewrite one",
        )

    def activity_history(self, listing_id: str) -> list:
        """The stored history of one application, as values: what the promise above is about.

        ``recorded_at`` is deliberately not compared - it is this application's own write clock, and the
        claim is about the entries the person recorded and their order.
        """
        return [(entry.occurred_on, entry.kind, entry.detail)
                for entry in self.store.list_activity(listing_id)]

    def test_a_status_change_through_the_window_keeps_the_recorded_reminder(self):
        """The regression: moving an application on used to cancel the reminder silently.

        ``_update_status`` builds the tracker it works from and saves the transitioned record, and the
        transition rebuilt the record from the status and evidence alone - so the day and note were
        written back as empty. Driven here through the same dialog handler the smoke test uses.
        """
        self.make_follow_up_app()
        self.add_application("j1", days=4, note="chase the reply")
        dialog_app, status_var, evidence_var, assertion, apply = self.open_status_dialog("j1")

        status_var.set("shortlisted")
        apply()

        tracker = self.store.get_tracker("j1")
        assert tracker is not None
        self.assertEqual(tracker.status, ApplicationStatus.SHORTLISTED)
        self.assertIn("updated to shortlisted", dialog_app.status.get())
        self.assertEqual(tracker.follow_up_on, date.today() + timedelta(days=4),
                         "the reminder must survive the status change")
        self.assertEqual(tracker.follow_up_note, "chase the reply")

    def test_an_unrecognised_status_does_not_cost_the_recorded_reminder(self):
        """The refusal path reads the row through the parsed record, so a damaged status cannot wipe a plan.

        Reading the tracker to build the dialog is where an unreadable value must stop the flow, and the
        stop must be *before* anything is written. The day and note stay exactly as they were.
        """
        self.make_follow_up_app()
        self.add_application("j1", days=2, note="chase the reply")
        self.store._connection.execute("UPDATE application_tracker SET status='ghosted' WHERE listing_id='j1'")
        self.store._connection.commit()
        expected_day = (date.today() + timedelta(days=2)).isoformat()
        app = self.make_app()
        app.tracker_tree.selected = ("j1",)

        with mock.patch.object(
            self.store, "save_tracker", side_effect=AssertionError("nothing may be written for ghosted")
        ):
            app._update_status()

        self.assertIn("Status not recognised", MESSAGES.titles())
        self.assertIn("'ghosted'", MESSAGES.text("showerror"))
        row = self.store.get_tracker_raw("j1")
        self.assertEqual(row["status"], "ghosted")
        self.assertEqual(row["follow_up_on"], expected_day)
        self.assertEqual(row["follow_up_note"], "chase the reply")

    def test_export_writes_a_calendar_file_for_the_recorded_days(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=2, note="ask about the panel")
        target = Path(self.store.database_path).parent / "reminders.ics"
        FILEDIALOG.path = str(target)

        app._export_follow_ups()

        self.assertTrue(target.is_file())
        text = target.read_text(encoding="utf-8")
        self.assertIn("BEGIN:VCALENDAR", text)
        self.assertIn("Follow up: Data Engineer at Sandbox Systems", text)
        self.assertIn("ask about the panel", text)
        self.assertIn("Wrote 1 reminder(s)", app.status.get())

    def test_export_with_nothing_recorded_writes_no_file(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=None)
        target = Path(self.store.database_path).parent / "reminders.ics"
        FILEDIALOG.path = str(target)

        app._export_follow_ups()

        self.assertFalse(target.exists())
        self.assertIn("Nothing to export", MESSAGES.titles())

    def test_export_asks_before_replacing_an_existing_file(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=2)
        target = Path(self.store.database_path).parent / "reminders.ics"
        target.write_text("the person's own file", encoding="utf-8")
        FILEDIALOG.path = str(target)
        CONFIG["Replace this file?"] = False

        app._export_follow_ups()

        self.assertEqual(target.read_text(encoding="utf-8"), "the person's own file")

    def test_cancelling_the_file_chooser_writes_nothing(self):
        app = self.make_follow_up_app()
        self.add_application("j1", days=2)
        FILEDIALOG.path = ""

        app._export_follow_ups()

        self.assertNotIn("Wrote", app.status.get())
        self.assertEqual([name for name in os.listdir(Path(self.store.database_path).parent)
                          if name.endswith(".ics")], [])


class NextActionsTabTests(HandlerTestCase):
    """The Next actions tab: the combined list, and what each button does to what it names.

    Driven through the same stub harness as the other tabs, so this is the handler logic behind the
    widgets rather than pixels. The list itself is a pure function tested in tests/test_preparation.py;
    what is tested here is that the tab shows those rows, that a button acts on the record its row names,
    and that nothing in this tab can move an application on.
    """

    def make_actions_app(self):
        """The app with the widgets this tab builds, on the shared stub harness."""
        app = self.make_app()
        app.actions_tab = Widget()
        app.actions_summary = StringVar()
        app.actions_tree = Tree()
        app.actions_tree.selected = ()
        app.jobs_tree.selected = ()
        app.tracker_tree.selected = ()
        MESSAGES.reset()
        return app

    def add_application(self, listing_id: str, *, role: str = "Data Engineer") -> None:
        self.store.save_job(JobListing(listing_id, "fixture", "Fixture",
                                       f"https://jobs.example.invalid/{listing_id}", "Sandbox Systems",
                                       role, availability_status=Availability.UNKNOWN))

    def add_preparation(self, listing_id: str, title: str, *, days: int | None = None, kind: str = "tailoring"):
        self.add_application(listing_id)
        due = None if days is None else date.today() + timedelta(days=days)
        return self.store.add_preparation(listing_id, title, kind=kind, due_on=due)

    def test_the_list_shows_the_three_kinds_with_the_record_each_row_names(self):
        app = self.make_actions_app()
        item = self.add_preparation("j1", "Tailor the résumé", days=-1)
        self.store.save_tracker(ApplicationTracker("j1"))
        self.store.set_follow_up("j1", date.today() - timedelta(days=2), note="chase the reply")
        recorded = self.store.record_interview("j1", "technical", date.today() + timedelta(days=1))

        app._refresh_actions()

        self.assertEqual([iid for iid, _ in app.actions_tree.inserted],
                         [f"follow-up:j1", f"preparation:{item.preparation_id}",
                          f"interview:{recorded.round_id}"])
        self.assertIn("2 item(s) need you now", app.actions_summary.get())
        self.assertIn("1 item(s) still to do, 1 overdue", app.actions_summary.get())
        self.assertIn("Next: Technical interview tomorrow", app.actions_summary.get())

    def test_a_row_says_when_and_what_and_for_which_application(self):
        app = self.make_actions_app()
        self.add_preparation("j1", "Tailor the résumé", days=-1)

        app._refresh_actions()

        values = app.actions_tree.inserted[0][1]
        self.assertIn("1 day(s) overdue", values[0])
        self.assertEqual(values[1], "Tailor the résumé")
        self.assertEqual(values[2], "Data Engineer at Sandbox Systems")

    def test_an_undated_item_is_listed_rather_than_hidden(self):
        app = self.make_actions_app()
        self.add_preparation("j1", "Read the engineering blog", kind="research")

        app._refresh_actions()

        self.assertEqual(app.actions_tree.inserted[0][1][0], "No day set")

    def test_nothing_recorded_says_what_the_tab_is_for(self):
        app = self.make_actions_app()

        app._refresh_actions()

        self.assertEqual(app.actions_tree.inserted, ())
        self.assertIn("Nothing is waiting on you", app.actions_summary.get())
        self.assertIn("No preparation items are recorded", app.actions_summary.get())

    def test_ticking_off_the_selected_item_changes_nothing_about_the_application(self):
        app = self.make_actions_app()
        item = self.add_preparation("j1", "Tailor the résumé", days=0)
        self.store.save_tracker(ApplicationTracker("j1"))
        before = self.store.get_tracker("j1")
        app._refresh_actions()
        app.actions_tree.selected = (f"preparation:{item.preparation_id}",)

        app._complete_preparation()

        stored = self.store.get_preparation(item.preparation_id)
        self.assertTrue(stored.is_done)
        self.assertEqual(self.store.get_tracker("j1"), before, "ticking an item off is not a status change")
        self.assertIn("was not changed", app.status.get())
        # ``children`` is the tree's current state (``inserted`` is an append-only record of inserts).
        self.assertEqual(app.actions_tree.children, (), "the finished item leaves the list")

    def test_ticking_off_a_row_that_is_not_a_preparation_item_explains_instead_of_acting(self):
        app = self.make_actions_app()
        self.add_application("j1")
        recorded = self.store.record_interview("j1", "technical", date.today())
        app._refresh_actions()
        app.actions_tree.selected = (f"interview:{recorded.round_id}",)

        app._complete_preparation()

        self.assertIn("That row is not a preparation item", MESSAGES.titles())
        self.assertEqual(self.store.get_interview(recorded.round_id).outcome, InterviewOutcome.AWAITING)

    def test_recording_an_outcome_saves_the_persons_reading_and_no_status(self):
        app = self.make_actions_app()
        self.add_application("j1")
        self.store.save_tracker(ApplicationTracker("j1"))
        recorded = self.store.record_interview("j1", "technical", date.today() - timedelta(days=1))
        before = self.store.get_tracker("j1")
        app._refresh_actions()
        app.actions_tree.selected = (f"interview:{recorded.round_id}",)
        created = []
        original = desktop.tk.StringVar

        def recording(*args, **kwargs):
            variable = original(*args, **kwargs)
            created.append(variable)
            return variable

        desktop.tk.StringVar = recording
        self.addCleanup(setattr, desktop.tk, "StringVar", original)
        app._set_round_outcome()
        desktop.tk.StringVar = original

        outcome_var, notes_var = created[0], created[1]
        outcome_var.set("went_well")
        notes_var.set("they asked about the data pipeline")
        BUTTONS.command()

        stored = self.store.get_interview(recorded.round_id)
        self.assertEqual(stored.outcome, InterviewOutcome.WENT_WELL)
        self.assertEqual(stored.notes, "they asked about the data pipeline")
        self.assertEqual(self.store.get_tracker("j1"), before, "an outcome is not a status change")
        self.assertIn("You felt it went well", app.status.get())

    def test_deleting_a_follow_up_row_says_where_that_is_done_and_writes_nothing(self):
        app = self.make_actions_app()
        self.add_application("j1")
        self.store.save_tracker(ApplicationTracker("j1"))
        self.store.set_follow_up("j1", date.today(), note="chase")
        app._refresh_actions()
        app.actions_tree.selected = ("follow-up:j1",)

        app._delete_action_record()

        self.assertIn("Follow-up days are cleared, not deleted", MESSAGES.titles())
        self.assertEqual(self.store.get_tracker("j1").follow_up_on, date.today())

    def test_deleting_a_preparation_item_asks_first_and_only_then_removes_it(self):
        app = self.make_actions_app()
        item = self.add_preparation("j1", "Tailor the résumé")
        app._refresh_actions()
        app.actions_tree.selected = (f"preparation:{item.preparation_id}",)
        CONFIG["Delete this preparation item?"] = False

        app._delete_action_record()
        self.assertIsNotNone(self.store.get_preparation(item.preparation_id), "a declined confirmation does nothing")

        CONFIG["Delete this preparation item?"] = True
        app._delete_action_record()

        self.assertIsNone(self.store.get_preparation(item.preparation_id))
        self.assertIn("was deleted", app.status.get())

    def test_deleting_a_record_that_is_already_gone_says_so(self):
        app = self.make_actions_app()
        item = self.add_preparation("j1", "Tailor the résumé")
        app._refresh_actions()
        app.actions_tree.selected = (f"preparation:{item.preparation_id}",)
        CONFIG["Delete this preparation item?"] = True
        self.store.delete_preparation(item.preparation_id)

        app._delete_action_record()

        self.assertIn("was already gone", app.status.get())
        self.assertIn("nothing was deleted", app.status.get())

    def test_adding_a_preparation_item_needs_an_application_selected_first(self):
        app = self.make_actions_app()
        self.add_application("j1")

        app._add_preparation()

        self.assertIn("Add a preparation item", MESSAGES.titles())
        self.assertIn("Select the application", MESSAGES.text("showinfo"))
        self.assertEqual(self.store.list_preparation(), ())

    def test_a_preparation_item_is_added_through_the_dialog_with_its_day_and_kind(self):
        app = self.make_actions_app()
        self.add_application("j1")
        app.jobs_tree.selected = ("j1",)
        created = []
        original = desktop.tk.StringVar

        def recording(*args, **kwargs):
            variable = original(*args, **kwargs)
            created.append(variable)
            return variable

        desktop.tk.StringVar = recording
        self.addCleanup(setattr, desktop.tk, "StringVar", original)
        app._add_preparation()
        desktop.tk.StringVar = original

        title_var, kind_var, day_var = created[0], created[1], created[2]
        title_var.set("Write the cover letter")
        kind_var.set("documents")
        day_var.set((date.today() + timedelta(days=2)).isoformat())
        BUTTONS.command()

        stored = self.store.list_preparation("j1")[0]
        self.assertEqual(stored.title, "Write the cover letter")
        self.assertEqual(stored.kind.value, "documents")
        self.assertEqual(stored.due_on, date.today() + timedelta(days=2))
        self.assertIn("No status was changed", app.status.get())

    def test_a_mistyped_day_is_refused_before_anything_is_written(self):
        app = self.make_actions_app()
        self.add_application("j1")
        app.jobs_tree.selected = ("j1",)
        created = []
        original = desktop.tk.StringVar

        def recording(*args, **kwargs):
            variable = original(*args, **kwargs)
            created.append(variable)
            return variable

        desktop.tk.StringVar = recording
        self.addCleanup(setattr, desktop.tk, "StringVar", original)
        app._add_preparation()
        desktop.tk.StringVar = original

        created[0].set("Write the cover letter")
        created[2].set("next tuesday")
        BUTTONS.command()

        self.assertIn("Preparation item not saved", MESSAGES.titles())
        self.assertIn("YYYY-MM-DD", MESSAGES.text("showerror"))
        self.assertEqual(self.store.list_preparation("j1"), ())

    def test_an_interview_round_is_recorded_through_the_dialog_and_moves_no_status(self):
        app = self.make_actions_app()
        self.add_application("j1", role="Analyst")
        self.store.save_tracker(ApplicationTracker("j1"))
        before = self.store.get_tracker("j1")
        app.tracker_tree.selected = ("j1",)
        created = []
        original = desktop.tk.StringVar

        def recording(*args, **kwargs):
            variable = original(*args, **kwargs)
            created.append(variable)
            return variable

        desktop.tk.StringVar = recording
        self.addCleanup(setattr, desktop.tk, "StringVar", original)
        app._record_interview_round()
        desktop.tk.StringVar = original

        stage_var, day_var, mode_var, notes_var = created[0], created[1], created[2], created[3]
        stage_var.set("panel")
        day_var.set((date.today() + timedelta(days=5)).isoformat())
        mode_var.set("onsite")
        notes_var.set("bring the portfolio")
        BUTTONS.command()

        recorded = self.store.list_interviews("j1")[0]
        self.assertEqual(recorded.stage.value, "panel")
        self.assertEqual(recorded.mode.value, "onsite")
        self.assertEqual(recorded.notes, "bring the portfolio")
        self.assertEqual(recorded.outcome, InterviewOutcome.AWAITING, "a new round starts waiting")
        self.assertEqual(self.store.get_tracker("j1"), before)
        self.assertIn("no status was changed", app.status.get())

    def test_a_round_without_a_day_is_refused_before_anything_is_written(self):
        app = self.make_actions_app()
        self.add_application("j1")
        app.jobs_tree.selected = ("j1",)
        created = []
        original = desktop.tk.StringVar

        def recording(*args, **kwargs):
            variable = original(*args, **kwargs)
            created.append(variable)
            return variable

        desktop.tk.StringVar = recording
        self.addCleanup(setattr, desktop.tk, "StringVar", original)
        app._record_interview_round()
        desktop.tk.StringVar = original

        created[1].set("sometime next week")
        BUTTONS.command()

        self.assertIn("Interview round not saved", MESSAGES.titles())
        self.assertEqual(self.store.list_interviews("j1"), ())

    def test_an_unreadable_record_is_reported_rather_than_crashing_the_tab(self):
        app = self.make_actions_app()
        self.add_preparation("j1", "Tailor the résumé")
        self.store._connection.execute("UPDATE application_preparation SET kind='astrology'")
        self.store._connection.commit()

        app._refresh_actions()

        self.assertIn("could not be read", MESSAGES.text("showerror"))
        self.assertIn("astrology", MESSAGES.text("showerror"))


class SchedulerTabTests(HandlerTestCase):
    """The Background tasks tab: what a person can see and change, through the real handlers.

    The workers' own behaviour is covered in tests/test_worker.py and tests/test_store_tasks.py; what is
    tested here is the surface - that the tab shows the schedule the worker would act on, that adding
    the defaults never rewrites a task the person configured, and that pausing asks first and keeps the
    history.
    """

    def make_scheduler_app(self):
        """The app with the scheduler widgets the tab builds, wired to the same stub harness."""
        app = self.make_app()
        app.scheduler_summary = StringVar()
        app.tasks_tree = Tree()
        app.task_runs_tree = Tree()
        return app

    def keep_only(self, task_id: str) -> None:
        """Pause every default task except ``task_id``, so a claim can only land where the test wants it.

        A claim takes the earliest due task, and the three default tasks sit at 00:00 and 12:00, 23:30 and
        09:00 on the same clock, so *which* of them is the earliest due one depends on the hour the test
        runs at: seed before 23:30 and the backup slot is the earliest due occurrence; seed after it and
        the backup rolls to the next evening while the 09:00 digest is already the earliest one left, so a
        test that had only paused one competitor would claim the wrong task and fail - on the Windows legs
        at 23:38 Asia/Kolkata and nowhere else. Removing every other task from contention is what makes the
        assertion about a specific attempt hold at any hour, rather than depending on when CI happens to run.
        """
        paused = []
        for task in self.store.list_scheduled_tasks():
            if task.task_id == task_id:
                continue
            self.store.save_scheduled_task(task.with_definition(enabled=False))
            paused.append(task.task_id)
        assert paused, "the test is about one task among several; there was nothing else to pause"
        assert self.store.get_scheduled_task(task_id) is not None

    def test_the_tab_lists_the_tasks_and_says_no_worker_holds_the_lease(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        MESSAGES.reset()

        app._refresh_scheduler()

        rows = {iid: values for iid, values in app.tasks_tree.inserted}
        self.assertEqual(sorted(rows), sorted(DEFAULT_TASK_IDS))
        # Every default task's own cadence, in the window's own cells: the checklist states these times,
        # so what the tab shows for each of the three is asserted rather than one standing for all.
        self.assertEqual(rows["scheduled-discovery"][3], "00:00, 12:00")
        self.assertEqual(rows["daily-backup"][3], "23:30")
        self.assertEqual(rows["follow-up-digest"][3], "09:00")
        for task_id, values in rows.items():
            self.assertEqual(values[4], "Asia/Kolkata", f"{task_id} is listed in the wrong zone")
        self.assertEqual(rows["daily-backup"][6], "never run")
        self.assertIn("No worker holds the lease", app.scheduler_summary.get())
        self.assertIn("No attempt has been recorded yet", app.scheduler_summary.get())

    def test_the_tab_reports_what_the_schedule_walked_past_while_nothing_ran(self):
        """The laptop-off case, through the tab: the schedule is behind and the window says by how much.

        The task is added with a three-day-old clock and nothing ever claims it, so its next occurrence is
        overdue and the later ones are occurrences nothing will come back to. Reading the tab must show
        both facts without starting a worker: the summary is the same read the command line prints.
        """
        app = self.make_scheduler_app()
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        self.store.save_scheduled_task(
            build_task("missed-probe", "Missed occurrence probe", "discovery.run",
                       times=("00:00", "12:00"), timezone="Asia/Kolkata", now=three_days_ago),
            now=three_days_ago)

        app._refresh_scheduler()

        summary = app.scheduler_summary.get()
        expected = missed_occurrences(self.store)
        self.assertTrue(expected, "the probe must produce something to report, or this proves nothing")
        self.assertIn("Missed while nothing was running", summary)
        self.assertIn(f"({len(expected)} occurrence(s)", summary)
        self.assertIn("Nothing is catching up on these", summary)
        self.assertIn("(due now)", summary, "the overdue occurrence is named as the next one to serve")
        self.assertIsNone(self.store.get_worker_lease(), "reading the tab must not take the lease")
        self.assertEqual(self.store.list_task_runs(), (), "reading the tab must not record an attempt")
        rows = dict(app.tasks_tree.inserted)
        self.assertIn("missed-probe", rows, "the probe task is listed like any other")

    def test_refreshing_claims_nothing_and_creates_nothing(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()

        app._refresh_scheduler()

        self.assertIsNone(self.store.get_worker_lease())
        self.assertEqual(self.store.list_task_runs(), ())
        self.assertEqual(app.task_runs_tree.inserted, ())

    def test_a_finished_attempt_appears_with_its_outcome_and_how_long_it_took(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        self.keep_only("daily-backup")
        task = self.store.get_scheduled_task("daily-backup")
        assert task is not None and task.next_run_at is not None
        claimed = self.store.claim_due_run(worker_id="w1", now=task.next_run_at)
        assert claimed is not None
        self.store.finish_run(claimed.run_id, RunState.REFUSED,
                              detail="there is no database file to back up yet, so nothing was written",
                              now=task.next_run_at)

        app._refresh_scheduler()

        self.assertEqual(len(app.task_runs_tree.inserted), 1)
        values = app.task_runs_tree.inserted[0][1]
        self.assertEqual(values[0], "daily-backup")
        self.assertEqual(values[1], "1")
        self.assertEqual(values[2], "refused")
        self.assertIn("no database file", values[5])
        self.assertIn("Recent attempts:", app.scheduler_summary.get())

    def test_adding_the_defaults_twice_says_what_it_left_alone(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        MESSAGES.reset()

        app._add_default_tasks()

        self.assertIn("Created: nothing.", MESSAGES.text("showinfo"))
        self.assertIn("Left exactly as they were: scheduled-discovery, daily-backup, follow-up-digest",
                      MESSAGES.text("showinfo"))
        self.assertEqual(len(self.store.list_scheduled_tasks()), len(default_tasks()))

    def test_adding_the_defaults_never_rewrites_a_task_the_person_configured(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        task = self.store.get_scheduled_task("scheduled-discovery")
        assert task is not None
        self.store.save_scheduled_task(task.with_definition(times=("09:15",), enabled=False))

        app._add_default_tasks()

        stored = self.store.get_scheduled_task("scheduled-discovery")
        assert stored is not None
        self.assertEqual(stored.times, ("09:15",))
        self.assertFalse(stored.enabled)
        self.assertIsNone(stored.next_run_at)

    def test_toggling_without_a_selection_changes_nothing_and_says_so(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        MESSAGES.reset()

        app._toggle_scheduled_task()

        self.assertIn("Select a task", app.status.get())
        self.assertEqual(MESSAGES.calls, [], "no dialog should appear when there is nothing selected")
        assert self.store.get_scheduled_task("daily-backup").enabled

    def test_pausing_asks_first_and_a_declined_confirmation_changes_nothing(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        app.tasks_tree.selection_set("daily-backup")
        CONFIG["Pause this task"] = False

        app._toggle_scheduled_task()

        self.assertIn("Pause this task", MESSAGES.titles("askyesno"))
        self.assertIn("cancelled", app.status.get())
        assert self.store.get_scheduled_task("daily-backup").enabled

    def test_pausing_keeps_the_task_its_times_and_its_history(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        self.keep_only("daily-backup")
        task = self.store.get_scheduled_task("daily-backup")
        assert task is not None and task.next_run_at is not None
        claimed = self.store.claim_due_run(worker_id="w1", now=task.next_run_at)
        assert claimed is not None
        self.store.finish_run(claimed.run_id, RunState.SUCCEEDED, detail="wrote one snapshot",
                              now=task.next_run_at)
        # pausing reads the task itself, so it works whether or not the run above is still current
        self.store.save_scheduled_task(
            self.store.get_scheduled_task("daily-backup").with_definition(enabled=True))
        app.tasks_tree.selection_set("daily-backup")
        CONFIG["Pause this task"] = True

        app._toggle_scheduled_task()

        paused = self.store.get_scheduled_task("daily-backup")
        assert paused is not None
        self.assertFalse(paused.enabled)
        self.assertIsNone(paused.next_run_at)
        self.assertEqual(paused.times, ("23:30",), "pausing is not deleting")
        self.assertEqual([run.detail for run in self.store.list_task_runs(task_id="daily-backup")],
                         ["wrote one snapshot"])
        self.assertIn("paused", app.status.get())
        rows = dict(app.tasks_tree.inserted)
        self.assertEqual(sorted(rows), sorted(DEFAULT_TASK_IDS),
                         "every task is still listed: pausing is not deleting")
        self.assertEqual(rows["daily-backup"][5], "paused")
        self.assertEqual(rows["scheduled-discovery"][5], "paused",
                         "the other tasks were paused by this test to keep the claim unambiguous")

    def test_the_claim_a_test_makes_is_the_task_it_asked_for_at_any_hour(self):
        """The claim helper has to hold at the hour the failure was found as well as at the hour of writing.

        Run 38781575276 failed on both Windows legs because they were the only legs still inside the suite
        at 23:30 Asia/Kolkata: the 23:30 backup slot had just rolled to the next evening while the 09:00
        digest slot was already due, so the earliest due task stopped being the one the test named (D18).
        Seeding at a fixed 23:38 moment reproduces that window on any machine at any hour. The arrangement
        is asserted first - if a scheduling change ever makes the digest and the backup line up differently,
        this test says so instead of passing for the wrong reason - and then the claim is required to land
        on the task the test named.
        """
        late_evening = datetime(2026, 10, 16, 23, 38, tzinfo=ZoneInfo("Asia/Kolkata"))
        seed_default_tasks(self.store, now=late_evening)
        app = self.make_scheduler_app()

        backup = self.store.get_scheduled_task("daily-backup")
        digest = self.store.get_scheduled_task("follow-up-digest")
        assert backup is not None and backup.next_run_at is not None
        assert digest is not None and digest.next_run_at is not None
        self.assertLess(digest.next_run_at, backup.next_run_at,
                        "another task is due before the one under test: that is the arrangement the "
                        "failure needs, and its absence would make this test pass for the wrong reason")

        self.keep_only("daily-backup")
        claimed = self.store.claim_due_run(worker_id="w1", now=backup.next_run_at)

        assert claimed is not None, "the task under test was due and is the only one left due"
        self.assertEqual(claimed.task_id, "daily-backup")
        app._refresh_scheduler()
        values = {iid: row for iid, row in app.tasks_tree.inserted}
        self.assertEqual(len(values), len(DEFAULT_TASK_IDS),
                         "pausing the others is pausing, not deleting: every task is still listed")

    def test_resuming_a_paused_task_schedules_the_next_occurrence(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        app.tasks_tree.selection_set("daily-backup")
        CONFIG["Pause this task"] = True
        app._toggle_scheduled_task()
        asked_before_resuming = [kind for _title, _answer, kind in MESSAGES.calls].count("askyesno")

        # Pausing refreshed the list, and a refreshed list deletes and re-inserts every row, which is what
        # takes the selection away in a real window: choosing the row again is what the person does before
        # pressing the button a second time, and what the window tells them to do when they do not.
        app.tasks_tree.selection_set("daily-backup")
        app._toggle_scheduled_task()

        resumed = self.store.get_scheduled_task("daily-backup")
        assert resumed is not None
        self.assertTrue(resumed.enabled)
        self.assertIsNotNone(resumed.next_run_at)
        self.assertIn("enabled", app.status.get())
        self.assertEqual([kind for _title, _answer, kind in MESSAGES.calls].count("askyesno"),
                         asked_before_resuming,
                         "resuming does not need a confirmation; pausing does")

    def test_a_task_row_this_version_cannot_read_is_reported_and_the_list_is_left_alone(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        with self.store._connection:
            self.store._connection.execute(
                "UPDATE scheduled_task SET schedule_times = ? WHERE task_id = ?",
                ("not json", "daily-backup"))
        CONFIG.clear()
        MESSAGES.reset()

        app._refresh_scheduler()

        self.assertIn("Saved record could not be read", MESSAGES.titles("showerror"))
        self.assertIn("nothing was changed", app.status.get())
        self.assertIn("could not be read", app.status.get().lower())

    def test_a_stale_selection_is_reported_and_the_list_resynchronised(self):
        app = self.make_scheduler_app()
        app._add_default_tasks()
        app.tasks_tree.selection_set("daily-backup")
        self.store.delete_scheduled_task("daily-backup")
        MESSAGES.reset()

        app._toggle_scheduled_task()

        self.assertIn("no longer in the schedule", app.status.get())
        self.assertEqual(MESSAGES.calls, [], "a stale selection is not a question to ask the person")

    def test_the_selected_task_is_read_from_the_store_not_trusted_from_the_row(self):
        """The row is a display artefact; the write is planned from the stored task."""
        app = self.make_scheduler_app()
        app._add_default_tasks()
        app.tasks_tree.selection_set("daily-backup")
        # The row and the store disagree (an old window, a hand-edited tree): the store wins.
        self.store.save_scheduled_task(
            self.store.get_scheduled_task("daily-backup").with_definition(times=("22:00",)))
        CONFIG["Pause this task"] = True

        app._toggle_scheduled_task()

        paused = self.store.get_scheduled_task("daily-backup")
        assert paused is not None
        self.assertEqual(paused.times, ("22:00",), "the stored definition is the one that was changed")
        self.assertFalse(paused.enabled)


#: The synthetic contact fixtures this class imports: reserved ``.invalid`` domains only, and every value
#: listed here so the privacy assertions can name them instead of a wording.
CONTACT_HEADER = "Email,Name,Company Label,Source Rows,Review Reason\r\n"
CONTACT_EMAILS = ("first.contact@example.invalid", "second.contact@example.invalid",
                  "third.contact@example.invalid")
CONTACT_NAMES = ("Sample Person One", "Sample Person Two", "Sample Person Three")
CONTACT_COMPANIES = ("Sample Employer One", "Sample Employer Two")
ALL_CONTACT_FIXTURE_VALUES = CONTACT_EMAILS + CONTACT_NAMES + CONTACT_COMPANIES


class ContactTabTestCase(HandlerTestCase):
    """The fixtures the HR contacts tab's tests share: synthetic CSV files and what a write costs.

    Both classes below drive the tab's own handlers against the real store in a disposable folder, so
    "nothing was written" is asserted with the connection's change counter and the stored rows rather than
    with a message.
    """

    def write_csv(self, rows: str, name: str = "contacts.csv") -> Path:
        path = Path(self._directory.name) / name
        path.write_bytes((CONTACT_HEADER + rows).encode("utf-8"))
        return path

    def changes(self) -> int:
        return self.store._connection.total_changes

    def log_text(self) -> str:
        return (Path(self._directory.name) / "logs" / "application.log").read_text(encoding="utf-8")

    def two_contacts(self) -> Path:
        return self.write_csv(
            f"{CONTACT_EMAILS[0]},{CONTACT_NAMES[0]},{CONTACT_COMPANIES[0]},1,\r\n"
            f"{CONTACT_EMAILS[1]},{CONTACT_NAMES[1]},{CONTACT_COMPANIES[1]},2,\r\n")

    def import_two(self, app) -> None:
        """Store both synthetic contacts through the tab's own read-and-confirm path."""
        filedialog_path = str(self.two_contacts())
        FILEDIALOG.path = filedialog_path
        app._choose_contact_csv()
        app._store_contact_preview()

    def ids_of(self, app) -> dict:
        """Every stored contact's id by the address it was imported under, as the list keys its rows.

        Read from the application's own store: the tests that reopen a database give the application a second
        connection, and the fixture's is closed by then.
        """
        return {record.email_key: record.contact_id for record in app.store.list_contacts()}

    def contradicting_list(self, name: str = "later-list.csv") -> Path:
        """A second file that disagrees with what is stored and with itself.

        The first address is given a different name twice, so importing it records a disagreement between
        two rows of one file *and* one between that file and the stored record; the second address keeps
        its name and changes its company, which is a disagreement with the stored record only.
        """
        return self.write_csv(
            f"{CONTACT_EMAILS[0]},{CONFLICT_NAMES[0]},{CONTACT_COMPANIES[0]},1,\r\n"
            f"{CONTACT_EMAILS[0]},{CONFLICT_NAMES[1]},{CONTACT_COMPANIES[0]},2,\r\n"
            f"{CONTACT_EMAILS[1]},{CONTACT_NAMES[1]},{CONFLICT_COMPANIES[0]},3,\r\n", name=name)

    def import_list(self, app, path: Path) -> None:
        """Read one file through the tab's own chooser and store it the way a person would."""
        FILEDIALOG.path = str(path)
        app._choose_contact_csv()
        app._store_contact_preview()

    @staticmethod
    def conflict_rows(app):
        """The rows the panel is showing now, in the order it drew them - not every row it ever drew."""
        return [app.contact_conflicts_tree.item(iid, "values")
                for iid in app.contact_conflicts_tree.get_children()]

    @staticmethod
    def conflict_detail(app) -> str:
        return app.contact_conflict_text.get("1.0", "end")

    def select_conflict(self, app, item) -> None:
        """Select one disagreement the way a display does: the selection runs the bound handler.

        The stand-in tree records a selection without posting Tk's virtual event - it has no event loop to
        post it to - so the handler a real tree calls is called here by name, exactly as this suite's
        stored-contact selection helper does. That the tree is *bound* to that handler is asserted
        separately, and workflow L drives the real event through a real Tk.
        """
        app.contact_conflicts_tree.selection_set(item)
        app._on_conflict_selection()

    def select(self, app, contact_id) -> None:
        """Select one row of the stored list the way the tab's own selection event would."""
        app.stored_contacts_tree.selected = (() if contact_id is None else (str(contact_id),))
        app._sync_contact_actions()

    def stored_row(self, app, position: int):
        """One row of the stored list as the tab last rendered it, by position in the list.

        Read from the application's own store rather than the fixture's: the tests that reopen a database
        give the application a second connection, and the fixture's is closed by then.
        """
        rows = [values for _iid, values in app.stored_contacts_tree.inserted]
        return rows[len(rows) - len(app.store.list_contacts()) + position]


#: The second file's own values: it disagrees with the stored records *and* with itself, so one import
#: produces both kinds of disagreement the store records. Every value is listed here so the privacy
#: assertions can name them rather than a wording.
CONFLICT_NAMES = ("Sample Person One (later file)", "Sample Person One (later still)")
CONFLICT_COMPANIES = ("Sample Employer Three",)
ALL_CONFLICT_FIXTURE_VALUES = CONFLICT_NAMES + CONFLICT_COMPANIES


class ContactImportTabTests(ContactTabTestCase):
    """The HR contacts tab: what a preview writes (nothing), and what each path promises.

    The window is the second half of the increment the parser started: a person chooses their own export,
    sees what was read before anything is stored, and confirms once.
    """

    def test_choosing_a_file_shows_what_it_holds_and_writes_nothing(self):
        path = self.two_contacts()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        before = self.changes()

        app._choose_contact_csv()

        shown = app.contacts_preview_text.get("1.0", "end")
        self.assertIn("File: contacts.csv", shown)
        self.assertIn("Nothing was written", shown)
        self.assertIn("Nothing was written", shown)
        self.assertEqual(self.changes(), before, "a preview must not write a row")
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)
        self.assertEqual(app.contact_rows_tree.inserted, (), "nothing in this file needs a look")
        self.assertIn("Nothing has been stored yet", app.status.get())
        self.assertIn("nothing has been stored yet", app.status.get().lower())
        self.assertEqual(MESSAGES.titles(), [], "a readable file needs no dialog")

    def test_a_file_that_needs_review_lists_the_rows_and_their_reasons(self):
        path = self.write_csv(
            f",{CONTACT_NAMES[0]},{CONTACT_COMPANIES[0]},1,\r\n"
            f"{CONTACT_EMAILS[1].upper()},{CONTACT_NAMES[1]},{CONTACT_COMPANIES[1]},2,\r\n"
            f"{CONTACT_EMAILS[1].lower()},{CONTACT_NAMES[2]},{CONTACT_COMPANIES[0]},3,review this one\r\n")
        app = self.make_app()
        FILEDIALOG.path = str(path)

        app._choose_contact_csv()

        rows = [values for _iid, values in app.contact_rows_tree.inserted]
        self.assertEqual(len(rows), 3, "each flagged row is listed once, in file order")
        self.assertEqual([row[0] for row in rows], [2, 3, 4], "the file's own line numbers")
        self.assertIn("email-missing", rows[0][4])
        self.assertIn("duplicate-key", rows[1][4])
        self.assertIn("review this one", rows[2][4])
        self.assertIn("rows to review: 3", app.contacts_preview_text.get("1.0", "end"))
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)

    def test_a_refused_file_is_explained_and_writes_nothing(self):
        path = Path(self._directory.name) / "not-a-list.csv"
        path.write_bytes(b"Name,Company Label\r\nSample Person,Somewhere\r\n")
        app = self.make_app()
        FILEDIALOG.path = str(path)
        before = self.changes()

        app._choose_contact_csv()

        self.assertEqual(MESSAGES.titles("showerror"), ["Nothing was imported"])
        self.assertIn("nothing was changed", MESSAGES.text("showerror").lower())
        self.assertEqual(self.changes(), before)
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)
        self.assertIn("was not changed", app.status.get())
        self.assertIn("event=import.refused", self.log_text())

    def test_a_cancelled_chooser_changes_nothing(self):
        app = self.make_app()
        FILEDIALOG.path = ""

        app._choose_contact_csv()

        self.assertEqual(MESSAGES.titles(), [])
        self.assertIn("cancelled", app.status.get())
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)

    def test_declining_the_confirmation_writes_nothing(self):
        path = self.two_contacts()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        app._choose_contact_csv()
        CONFIG["Import these contacts?"] = False
        before = self.changes()

        app._store_contact_preview()

        self.assertIn("Import these contacts?", MESSAGES.titles("askyesno"))
        self.assertEqual(self.changes(), before, "a declined confirmation must write nothing")
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)
        self.assertEqual(app.stored_contacts_tree.inserted, ())
        self.assertIn("cancelled", app.status.get())
        self.assertNotIn("Contact import complete", MESSAGES.titles("showinfo"))

    def test_confirming_stores_each_contact_once_and_shows_it(self):
        path = self.two_contacts()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        app._choose_contact_csv()
        before = self.changes()

        app._store_contact_preview()

        self.assertEqual(self.store.contact_record_counts()["contacts"], 2)
        self.assertEqual([record.seen_count for record in self.store.list_contacts()], [1, 1])
        self.assertEqual(self.changes() - before, 2, "one insert per contact and nothing else")
        self.assertEqual(len(app.stored_contacts_tree.inserted), 2)
        self.assertIn("Contact import complete", MESSAGES.titles("showinfo"))
        self.assertIn("2 contact(s) added", app.status.get())
        # Importing the same previewed file again updates the two records and adds none.
        app._store_contact_preview()
        self.assertEqual(self.store.contact_record_counts()["contacts"], 2)
        self.assertEqual([record.seen_count for record in self.store.list_contacts()], [2, 2])

    def test_the_confirmation_dialog_carries_counts_and_no_contact_value(self):
        path = self.two_contacts()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        app._choose_contact_csv()

        app._store_contact_preview()

        said = MESSAGES.text("askyesno") + "\n" + MESSAGES.text("showinfo") + "\n" + app.status.get()
        for values in app.contact_rows_tree.inserted + app.stored_contacts_tree.inserted:
            self.assertNotEqual(values, ())
        for value in ALL_CONTACT_FIXTURE_VALUES:
            self.assertNotIn(value, said, f"{value!r} must not reach a dialog or the status line")
        # The file's own name is shown to the person (they chose it), and the event log deliberately
        # carries none: `contacts.imported` is a counts-only line, checked in test_contacts_store.
        self.assertIn("contacts.csv", said)
        self.assertNotIn("contacts.csv", self.log_text())
        self.assertIn("2 contact(s) added", said)

    def test_nothing_to_store_is_reported_without_a_preview(self):
        app = self.make_app()

        app._store_contact_preview()

        self.assertIn("Choose a file first", MESSAGES.titles("showinfo"))
        self.assertIn("nothing was changed", MESSAGES.text("showinfo").lower())
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)

    def test_a_storage_failure_is_reported_and_no_success_is_shown(self):
        path = self.two_contacts()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        app._choose_contact_csv()

        with mock.patch.object(self.store, "import_contacts",
                               side_effect=sqlite3.OperationalError("disk I/O error")):
            app._store_contact_preview()

        self.assertNotIn("Contact import complete", MESSAGES.titles("showinfo"),
                         "a failed import must never be reported as a completed one")
        self.assertEqual(MESSAGES.titles("showerror"), ["Local database unavailable"])
        self.assertIn("nothing was changed", app.status.get())
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)

    def test_a_damaged_stored_contact_is_reported_by_name_and_nothing_is_written(self):
        path = self.two_contacts()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        app._choose_contact_csv()
        self.store.import_contacts(contacts_module.read_contact_csv(path))
        self.store.close()
        connection = sqlite3.connect(str(self.store.database_path))
        try:
            connection.execute("UPDATE hr_contact SET seen_count = 0")
            connection.commit()
        finally:
            connection.close()
        app.store = CareerStore(self.store.database_path)
        self.addCleanup(app.store.close)
        before = app.store._connection.total_changes

        app._store_contact_preview()

        self.assertEqual(MESSAGES.titles("showerror"), ["Saved record could not be read"])
        self.assertIn("nothing was changed", app.status.get())
        self.assertEqual(app.store._connection.total_changes, before)

    def test_clearing_the_preview_changes_nothing(self):
        path = self.two_contacts()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        app._choose_contact_csv()
        before = self.changes()

        app._clear_contact_preview()

        self.assertIsNone(app.contacts_preview)
        self.assertEqual(app.contact_rows_tree.inserted, ())
        self.assertEqual(self.changes(), before)
        self.assertEqual(self.store.contact_record_counts()["contacts"], 0)
        self.assertIn("cleared", app.status.get())

    def test_the_stored_list_shows_a_do_not_contact_mark_and_the_counts(self):
        path = self.two_contacts()
        app = self.make_app()
        FILEDIALOG.path = str(path)
        app._choose_contact_csv()
        app._store_contact_preview()
        self.store.set_contact_suppression(CONTACT_EMAILS[0], note="asked not to be written to")

        app._refresh_contacts()

        rows = [values for _iid, values in app.stored_contacts_tree.inserted[-2:]]
        self.assertEqual(rows[0][5], "do not contact")
        self.assertEqual(rows[0][4], 1)
        self.assertIn("1 marked do-not-contact", app.contacts_summary.get())
        self.assertIn("Nothing here has been contacted", app.contacts_summary.get())


#: The synthetic reason a test types beside a mark: a person's own words about somebody, which is exactly
#: the text that must never reach a log, an activity event or a dialog.
CONTACT_NOTE = "asked not to be written to again (synthetic)"
MARK_TITLE = "Mark this contact do not contact"
CLEAR_TITLE = "Remove this contact's do-not-contact mark"


class ContactMarkControlTests(ContactTabTestCase):
    """The do-not-contact controls: one confirmation, one write, and nothing on every other path.

    The mark is the person's own decision about somebody on their list, and this is the only screen that
    writes it - the store's own method is the only writer of the column, and no import statement mentions
    it. These tests drive the tab's handlers against a real store, so "nothing was written" is the
    connection's change counter and the stored row rather than a message, and they read a contact's state
    back through the same panel the person does.
    """

    def test_the_controls_offer_only_the_action_that_would_change_the_selected_contact(self):
        app = self.make_app()
        self.import_two(app)
        ids = self.ids_of(app)

        # Nothing selected: both controls are off, and the line under them says what to do.
        self.select(app, None)
        self.assertTrue(app.mark_contact_button.instate(["disabled"]))
        self.assertTrue(app.clear_contact_button.instate(["disabled"]))
        self.assertTrue(app.contact_note_entry.instate(["disabled"]))
        self.assertIn("No stored contact is selected", app.contact_mark_state.get())

        # An unmarked contact: marking is offered, removing is not.
        self.select(app, ids[CONTACT_EMAILS[0]])
        self.assertFalse(app.mark_contact_button.instate(["disabled"]))
        self.assertTrue(app.clear_contact_button.instate(["disabled"]))
        self.assertIn("Selected contact 1 of 2", app.contact_mark_state.get())
        self.assertIn("Not marked do not contact", app.contact_mark_state.get())

        # A marked contact: the other way round, and the reason box is off because the only action left is
        # removing the mark - which removes the reason with it. The mark is made the way a person makes it.
        app.contact_note.set(CONTACT_NOTE)
        app._mark_selected_contact()
        self.select(app, ids[CONTACT_EMAILS[0]])
        self.assertTrue(app.mark_contact_button.instate(["disabled"]))
        self.assertFalse(app.clear_contact_button.instate(["disabled"]))
        self.assertTrue(app.contact_note_entry.instate(["disabled"]))
        self.assertIn("Marked do not contact, and a reason is recorded with it",
                      app.contact_mark_state.get())

    def test_marking_asks_first_and_stores_the_mark_with_the_reason_typed(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        app.contact_note.set(CONTACT_NOTE)
        before = self.changes()

        app._mark_selected_contact()

        self.assertIn(MARK_TITLE, MESSAGES.titles("askyesno"))
        asked = MESSAGES.text("askyesno")
        self.assertIn("row 1 of 2 in the stored list", asked)
        self.assertIn("contacts.csv", asked, "the file the row came from is how a person tells rows apart")
        self.assertIn("no import can clear it", asked)
        self.assertIn("The reason you typed is stored with the mark", asked)
        record = self.store.get_contact(CONTACT_EMAILS[0])
        self.assertTrue(record.suppressed)
        self.assertEqual(record.suppressed_note, CONTACT_NOTE)
        self.assertEqual(self.changes() - before, 1, "one update and nothing else")
        self.assertIn("Do-not-contact mark updated", MESSAGES.titles("showinfo"))
        self.assertIn("marked do not contact", app.status.get())
        self.assertEqual(app.contact_note.get(), "", "the reason box is cleared with the mark it recorded")
        self.assertEqual(self.stored_row(app, 0)[5], "do not contact")
        self.assertEqual(self.stored_row(app, 0)[0], CONTACT_EMAILS[0])
        self.assertEqual(self.stored_row(app, 1)[5], "", "the other contact is left alone")
        self.assertIn("1 marked do-not-contact", app.contacts_summary.get())
        self.assertIn("Marked do not contact", app.contact_mark_state.get())
        # The row the person acted on is the one still selected, so the line above reads its new state.
        self.assertEqual(app.stored_contacts_tree.selected, (str(record.contact_id),))

    def test_declining_the_mark_writes_nothing(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        CONFIG[MARK_TITLE] = False
        before = self.changes()

        app._mark_selected_contact()

        self.assertEqual(self.changes(), before, "a declined confirmation must write nothing")
        self.assertFalse(self.store.get_contact(CONTACT_EMAILS[0]).suppressed)
        self.assertIsNone(self.store.get_contact(CONTACT_EMAILS[0]).suppressed_note)
        self.assertEqual(app.contact_note.get(), "")
        self.assertIn("Cancelled; nothing was changed.", app.status.get())
        self.assertNotIn("Do-not-contact mark updated", MESSAGES.titles("showinfo"))

    def test_removing_the_mark_asks_first_and_clears_the_reason_with_it(self):
        app = self.make_app()
        self.import_two(app)
        self.store.set_contact_suppression(CONTACT_EMAILS[0], note=CONTACT_NOTE)
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        before = self.changes()

        app._clear_selected_contact()

        self.assertIn(CLEAR_TITLE, MESSAGES.titles("askyesno"))
        asked = MESSAGES.text("askyesno")
        self.assertIn("row 1 of 2 in the stored list", asked)
        self.assertIn("The stored reason and the day the mark was made are removed with it", asked)
        record = self.store.get_contact(CONTACT_EMAILS[0])
        self.assertFalse(record.suppressed)
        self.assertIsNone(record.suppressed_note, "a cleared mark leaves no reason behind that no longer applies")
        self.assertIsNone(record.suppressed_at)
        self.assertEqual(self.changes() - before, 1, "one update and nothing else")
        self.assertEqual(self.stored_row(app, 0)[5], "")
        self.assertIn("0 marked do-not-contact", app.contacts_summary.get())
        self.assertIn("Not marked do not contact", app.contact_mark_state.get())
        self.assertIn("no longer marked do not contact", app.status.get())

    def test_declining_the_removal_keeps_the_mark_and_its_reason(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        app.contact_note.set(CONTACT_NOTE)
        app._mark_selected_contact()
        marked = self.store.get_contact(CONTACT_EMAILS[0])
        MESSAGES.reset()
        CONFIG[CLEAR_TITLE] = False
        before = self.changes()

        app._clear_selected_contact()

        self.assertEqual(self.changes(), before)
        after = self.store.get_contact(CONTACT_EMAILS[0])
        self.assertTrue(after.suppressed)
        self.assertEqual(after.suppressed_note, CONTACT_NOTE)
        self.assertEqual(after.suppressed_at, marked.suppressed_at, "the day the mark was made is unchanged")
        self.assertIn("Cancelled; nothing was changed.", app.status.get())
        self.assertIn("1 marked do-not-contact", app.contacts_summary.get())

    def test_pressing_mark_with_nothing_selected_writes_nothing_and_explains(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, None)
        before = self.changes()

        app._mark_selected_contact()

        self.assertIn("Select a contact first", MESSAGES.titles("showinfo"))
        self.assertIn("nothing was changed", MESSAGES.text("showinfo"))
        self.assertIn("Select a stored contact in the list first; nothing was changed.", app.status.get())
        self.assertEqual(self.changes(), before)

    def test_a_selection_whose_contact_is_gone_is_reported_and_writes_nothing(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, 9999)  # a row id the database does not hold: what a restore can leave behind
        before = self.changes()

        app._mark_selected_contact()

        self.assertIn("That contact is no longer stored", MESSAGES.titles("showinfo"))
        self.assertIn("nothing was changed", MESSAGES.text("showinfo"))
        self.assertEqual(self.changes(), before)
        self.assertFalse(any(record.suppressed for record in self.store.list_contacts()))
        self.assertIn("no longer stored; nothing was changed", app.status.get())
        self.assertEqual(len(app.stored_contacts_tree.inserted), 4, "the list was refreshed, not emptied")

    def test_marking_a_contact_that_is_already_marked_changes_nothing(self):
        app = self.make_app()
        self.import_two(app)
        self.store.set_contact_suppression(CONTACT_EMAILS[0])
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        before = self.changes()

        # The control that would do nothing is off, so this is the stale-screen path: the handler is called
        # as if the row had been marked by something else since the panel was drawn.
        app._mark_selected_contact()

        self.assertIn("Nothing to change", MESSAGES.titles("showinfo"))
        self.assertNotIn(MARK_TITLE, MESSAGES.titles("askyesno"),
                         "an action that would change nothing is never confirmed")
        self.assertEqual(self.changes(), before)
        self.assertIn("already what was asked for; nothing was changed.", app.status.get())

    def test_an_injected_storage_failure_leaves_the_mark_alone_and_claims_no_success(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        app.contact_note.set(CONTACT_NOTE)

        with mock.patch.object(self.store, "set_contact_suppression",
                               side_effect=sqlite3.OperationalError("disk I/O error")):
            app._mark_selected_contact()

        self.assertNotIn("Do-not-contact mark updated", MESSAGES.titles("showinfo"),
                         "a failed write must never be reported as a stored mark")
        self.assertEqual(MESSAGES.titles("showerror"), ["Local database unavailable"])
        self.assertEqual(app.status.get(), "The local database could not be read; nothing was changed.")
        self.assertFalse(self.store.get_contact(CONTACT_EMAILS[0]).suppressed)
        self.assertEqual(app.contact_note.get(), CONTACT_NOTE,
                         "a failed write does not throw away what the person typed")

    def test_the_mark_survives_a_re_import_through_the_tab(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        app.contact_note.set(CONTACT_NOTE)
        app._mark_selected_contact()

        self.import_two(app)  # the same file, read and confirmed again

        record = self.store.get_contact(CONTACT_EMAILS[0])
        self.assertTrue(record.suppressed, "an import never clears a do-not-contact mark")
        self.assertEqual(record.suppressed_note, CONTACT_NOTE)
        self.assertEqual(record.seen_count, 2, "the import still did its own work")
        self.assertEqual(self.stored_row(app, 0)[5], "do not contact")
        self.assertIn("1 marked do-not-contact", app.contacts_summary.get())
        self.assertIn("that mark was left alone", app.status.get())
        # A file that contradicts the stored record is recorded as a disagreement and still cannot clear
        # the mark: the second contact's name and company are replaced in the file below.
        contradicted = self.write_csv(
            f"{CONTACT_EMAILS[0]},{CONTACT_NAMES[2]},{CONTACT_COMPANIES[1]},3,\r\n",
            name="later-list.csv")
        FILEDIALOG.path = str(contradicted)
        app._choose_contact_csv()
        app._store_contact_preview()
        after = self.store.get_contact(CONTACT_EMAILS[0])
        self.assertTrue(after.suppressed)
        self.assertEqual(after.name, CONTACT_NAMES[0], "the stored name is kept, not overwritten")
        self.assertEqual(len(self.store.list_contact_conflicts(email_key=after.email_key)), 2)

    def test_the_mark_is_still_shown_after_a_restart_and_a_backup_restore(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        app.contact_note.set(CONTACT_NOTE)
        app._mark_selected_contact()
        database = Path(self.store.database_path)
        backup = database.parent / "chosen-backup.sqlite3"

        # A restart: a second connection on the same file, read back through the tab's own refresh.
        app.store.close()
        app.store = CareerStore(database)
        app._refresh_contacts()
        self.assertEqual(self.stored_row(app, 0)[5], "do not contact")
        self.assertIn("1 marked do-not-contact", app.contacts_summary.get())
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        self.assertIn("Marked do not contact", app.contact_mark_state.get())

        create_backup(database, backup)
        # The live database loses the mark, so a restore that works is the only way the screen shows it.
        app.store.set_contact_suppression(CONTACT_EMAILS[0], suppressed=False)
        app._refresh_contacts()
        self.assertIn("0 marked do-not-contact", app.contacts_summary.get())
        validate_app_database(backup)
        # The connection is closed for the swap and reopened after it, the same way the window's own
        # restore handler does it: replacing the file cannot be coordinated with an open connection, and
        # on Windows an open handle makes the replacement fail rather than merely race it.
        app.store.close()
        backup_module.restore_backup(backup, database)
        app.store = CareerStore(database)
        app._refresh_contacts()
        self.assertEqual(self.stored_row(app, 0)[5], "do not contact")
        self.assertIn("1 marked do-not-contact", app.contacts_summary.get())
        restored_record = app.store.get_contact(CONTACT_EMAILS[0])
        self.assertEqual(restored_record.suppressed_note, CONTACT_NOTE,
                         "the reason travels with the mark in a backup and a restore")
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        self.assertIn("Marked do not contact, and a reason is recorded with it",
                      app.contact_mark_state.get())

    def test_no_contact_value_or_reason_reaches_a_dialog_the_status_line_or_the_log(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, self.ids_of(app)[CONTACT_EMAILS[0]])
        app.contact_note.set(CONTACT_NOTE)

        app._mark_selected_contact()
        app._clear_selected_contact()

        said = MESSAGES.text() + "\n" + app.status.get()
        for value in ALL_CONTACT_FIXTURE_VALUES + (CONTACT_NOTE,):
            self.assertNotIn(value, said, f"{value!r} must not reach a dialog or the status line")
        written = self.log_text()
        self.assertIn("event=contacts.suppressed", written)
        self.assertIn("suppressed=true", written)
        self.assertIn("suppressed=false", written)
        for value in ALL_CONTACT_FIXTURE_VALUES + (CONTACT_NOTE, "contacts.csv"):
            self.assertNotIn(value, written, f"{value!r} must not reach the activity log")
        details = [line.rsplit("detail=", 1)[-1].strip() for line in written.splitlines()
                   if "event=contacts.suppressed" in line]
        self.assertTrue(details, "the mark wrote no event at all")
        self.assertEqual(set(details), {"suppressed=true", "suppressed=false"},
                         "an event about a mark carries the flag and nothing else")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ContactDeletionControlTests(ContactTabTestCase):
    """The destructive control on the HR contacts tab: what it asks, what it refuses, what it deletes.

    Deleting is the one action on this tab that removes a record rather than annotating it, so these tests
    drive its real handler against a real store in a disposable folder and read the result back: the
    contact's row and its disagreements are asserted gone, every other row is asserted unchanged - including
    the marks and the reasons other contacts carry - and "nothing was written" is the connection's change
    counter rather than a message. The confirmation is checked for what it must *not* contain as carefully as
    for what it says, because a dialog is the part of this program somebody other than the owner may end up
    reading over a shoulder, and the same rule applies to the status line and the activity log.
    """

    def test_the_control_is_off_until_a_stored_row_is_selected(self):
        app = self.make_app()
        self.import_two(app)
        ids = self.ids_of(app)

        self.select(app, None)
        self.assertTrue(app.delete_contact_button.instate(["disabled"]),
                        "a destructive control is offered with nothing selected")

        self.select(app, ids[CONTACT_EMAILS[0]])
        self.assertFalse(app.delete_contact_button.instate(["disabled"]))
        # And the line under the controls says that deleting is one of the things a selected row offers,
        # so a person meets the destructive action before they go looking for it.
        self.select(app, None)
        self.assertIn("delete it", app.contact_mark_state.get(),
                      "the state line never mentions deleting among the actions a row offers")

        # A row that is no longer in the database leaves the control off again, which is the state a
        # refresh after another window's deletion puts the screen in.
        app.stored_contacts_tree.delete(str(ids[CONTACT_EMAILS[0]]))
        self.store.delete_contact(CONTACT_EMAILS[0])
        app._sync_contact_actions()
        self.assertTrue(app.delete_contact_button.instate(["disabled"]))

    def test_the_confirmation_names_a_position_and_a_file_and_no_contact_value(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[0]])
        MESSAGES.reset()

        app._delete_selected_contact()

        self.assertEqual(MESSAGES.titles("askyesno"), ["Delete this stored contact"])
        asked = MESSAGES.text("askyesno")
        self.assertIn("row 1 of 2 in the stored list", asked,
                      "the question must say which row, by the reference the other confirmations use")
        self.assertIn("'later-list.csv'", asked, "the file the record came from is the other reference")
        self.assertIn("2 recorded disagreement(s)", asked,
                      "the question must say how much evidence goes with the contact")
        self.assertIn("There is no undo in this application", asked,
                      "a destructive action that cannot be undone must say so before it asks")
        for value in (*CONTACT_EMAILS, *CONTACT_NAMES, *CONTACT_COMPANIES, *CONFLICT_NAMES,
                      *CONFLICT_COMPANIES):
            self.assertNotIn(value, asked, f"{value!r} reached the confirmation dialog")

    def test_a_declined_confirmation_deletes_nothing_and_says_so(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[0]])
        before = self.changes()
        CONFIG["Delete this stored contact"] = False
        MESSAGES.reset()

        app._delete_selected_contact()

        CONFIG.clear()
        self.assertEqual(self.changes(), before, "a declined deletion wrote to the database")
        self.assertIsNotNone(self.store.get_contact(CONTACT_EMAILS[0]))
        self.assertEqual(len(self.store.list_contact_conflicts()), 3,
                         "a declined deletion removed evidence")
        self.assertEqual(MESSAGES.titles("showinfo"), [],
                         "a declined deletion is not reported as one that happened")
        self.assertEqual(app.status.get(), "Cancelled; nothing was deleted.")
        self.assertNotIn("contacts.deleted", self.log_text())

    def test_deleting_with_nothing_selected_asks_for_a_selection_and_writes_nothing(self):
        app = self.make_app()
        self.import_two(app)
        self.select(app, None)
        before = self.changes()
        MESSAGES.reset()

        app._delete_selected_contact()

        self.assertEqual(self.changes(), before)
        self.assertEqual(MESSAGES.titles("askyesno"), [], "there is no question to ask about no row")
        self.assertEqual(MESSAGES.titles("showinfo"), ["Select a contact first"])
        self.assertIn("nothing was deleted", app.status.get())
        self.assertEqual(len(self.store.list_contacts()), 2)

    def test_a_stale_selection_is_reported_and_never_deleted_from_the_row(self):
        app = self.make_app()
        self.import_two(app)
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[0]])
        # The row goes behind the window's back - another window, or a restore that replaced the database.
        self.store.delete_contact(CONTACT_EMAILS[0])
        MESSAGES.reset()

        app._delete_selected_contact()

        self.assertEqual(MESSAGES.titles("showinfo"), ["That contact is no longer stored"])
        self.assertEqual(MESSAGES.titles("askyesno"), [],
                         "a row the database does not hold is not something to confirm deleting")
        self.assertIn("nothing was deleted", app.status.get())
        self.assertEqual([record.email_key for record in app.store.list_contacts()],
                         [CONTACT_EMAILS[1]],
                         "nothing beyond the deletion that already happened was removed")

    def test_a_contact_that_vanishes_while_the_question_is_being_answered_is_not_deleted_twice(self):
        """The window reads the row, asks, and *then* deletes - and the row can go in between."""
        app = self.make_app()
        self.import_two(app)
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[0]])
        MESSAGES.reset()
        before = self.changes()

        asked = []

        def vanish_then_answer(title, message, **kwargs):
            # The person is looking at the confirmation while another window deletes the same contact:
            # the window that is asking must not report a deletion it did not perform.
            asked.append(title)
            self.store.delete_contact(CONTACT_EMAILS[0])
            return True

        with mock.patch.object(desktop.messagebox, "askyesno", side_effect=vanish_then_answer):
            app._delete_selected_contact()

        self.assertEqual(MESSAGES.titles("showinfo"), ["That contact is no longer stored"],
                         "the step that deleted nothing must not announce a deletion")
        self.assertIn("already not stored", app.status.get())
        self.assertIn("nothing was deleted", app.status.get())
        self.assertIsNone(self.store.get_contact(CONTACT_EMAILS[0]))
        self.assertEqual(asked, ["Delete this stored contact"],
                         "the person was asked once, about a row that was there when they were asked")
        self.assertEqual(self.changes() - before, 1,
                         "the only row removed here is the one the other deletion removed: the step that "
                         "found the row already gone deleted nothing of its own")

    def test_a_confirmed_deletion_removes_the_contact_and_its_evidence_and_leaves_the_rest(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[1]])
        app.contact_note.set("keep this contact's reason")
        app._mark_selected_contact()
        app.stored_contacts_tree.selection_set(str(ids[CONTACT_EMAILS[1]]))
        app._sync_contact_actions()
        kept = self.store.get_contact(CONTACT_EMAILS[1])
        self.select(app, ids[CONTACT_EMAILS[0]])
        positions_before = [record.email_key for record in app.store.list_contacts()]
        before = self.changes()
        MESSAGES.reset()

        app._delete_selected_contact()

        self.assertEqual(self.changes() - before, 3,
                         "one contact row and its two disagreement rows, and nothing else")
        self.assertEqual(MESSAGES.titles("showinfo"), ["Contact deleted"])
        self.assertIsNone(self.store.get_contact(CONTACT_EMAILS[0]),
                          "the selected contact is gone")
        self.assertEqual([conflict.email_key for conflict in self.store.list_contact_conflicts()],
                         [CONTACT_EMAILS[1]],
                         "the disagreements kept about the other contact are untouched")
        self.assertEqual(self.store.get_contact(CONTACT_EMAILS[1]), kept,
                         "the other contact, its mark and its reason are exactly as they were")
        self.assertEqual(positions_before[1], CONTACT_EMAILS[1])
        # Both views were re-read: the deleted row is gone from the list and from the panel's count.
        self.assertEqual([record.email_key for record in app.store.list_contacts()], [CONTACT_EMAILS[1]])
        self.assertIn("1 disagreement(s) recorded", app.contact_conflict_note.get())
        self.assertEqual([str(row[1]) for row in self.conflict_rows(app)], [CONTACT_EMAILS[1]],
                         "the panel still lists one disagreement, and it belongs to the other contact")
        self.assertEqual(app.status.get(),
                         "1 stored contact deleted, with 2 recorded disagreement(s). Nothing was contacted.")

    def test_the_report_of_a_deletion_carries_the_stores_own_count_not_the_screens_earlier_one(self):
        """The question and the deletion read the evidence at different moments; the report says what went.

        The screen's own read is made to answer "nothing is recorded about this contact" while the store
        still deletes the two rows it holds, which is the shape a second window writing between the question
        and the answer would have. What the person is told afterwards must be the store's count.
        """
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[0]])
        MESSAGES.reset()

        with mock.patch.object(self.store, "list_contact_conflicts", return_value=()):
            app._delete_selected_contact()

        self.assertIn("no disagreement is recorded about this contact",
                      MESSAGES.text("askyesno"),
                      "the question was not built from the screen's read, so this test proves nothing")
        self.assertIn("2 recorded disagreement(s)", MESSAGES.text("showinfo"),
                      "the report does not carry what the store actually deleted")
        self.assertEqual([conflict.email_key for conflict in self.store.list_contact_conflicts()],
                         [CONTACT_EMAILS[1]],
                         "the deletion removed the two disagreements and left the other contact's")

    def test_the_row_the_person_selected_is_not_left_selected_afterwards(self):
        app = self.make_app()
        self.import_two(app)
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[0]])

        app._delete_selected_contact()

        self.assertEqual(app.stored_contacts_tree.selection(), (),
                         "the deleted row cannot still be selected")
        self.assertTrue(app.delete_contact_button.instate(["disabled"]))

    def test_a_readable_record_of_the_deletion_carries_counts_and_no_contact_value(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[0]])
        MESSAGES.reset()

        app._delete_selected_contact()

        written = self.log_text()
        self.assertIn("event=contacts.deleted", written)
        self.assertIn("detail=contacts=1 conflicts=2", written)
        said = "\n".join([MESSAGES.text(), app.status.get(), app.contact_mark_state.get(),
                          app.contacts_summary.get(), app.contact_conflict_note.get()])
        for value in (*CONTACT_EMAILS, *CONTACT_NAMES, *CONTACT_COMPANIES, *CONFLICT_NAMES,
                      *CONFLICT_COMPANIES, "later-list.csv", "contacts.csv"):
            self.assertNotIn(value, written, f"{value!r} reached the activity log")
        # What the person is shown: counts, the position of the row and the file it came from. No address,
        # name, company or disagreement value is among it - the file name is not a contact value, it is the
        # reference every other confirmation on this tab uses, and it is what makes the question answerable.
        for value in (*CONTACT_EMAILS, *CONTACT_NAMES, *CONTACT_COMPANIES, *CONFLICT_NAMES,
                      *CONFLICT_COMPANIES):
            self.assertNotIn(value, said, f"{value!r} reached something the person is shown")
        self.assertIn("'later-list.csv'", said, "the reference the question is answerable by is missing")
        for claim in ("undone", "recoverable", "erased from your backups"):
            self.assertNotIn(claim, MESSAGES.text().lower(),
                             f"the dialog claims {claim!r}, which this action cannot promise")

    def test_a_storage_failure_deletes_nothing_and_claims_no_success(self):
        app = self.make_app()
        self.import_two(app)
        ids = self.ids_of(app)
        self.select(app, ids[CONTACT_EMAILS[0]])
        before = self.changes()
        MESSAGES.reset()

        with mock.patch.object(self.store, "delete_contact",
                               side_effect=sqlite3.OperationalError("disk I/O error")):
            app._delete_selected_contact()

        self.assertEqual(self.changes(), before)
        self.assertNotIn("Contact deleted", MESSAGES.titles("showinfo"),
                         "a failed deletion must never be reported as one that happened")
        self.assertEqual(MESSAGES.titles("showerror"), ["Local database unavailable"])
        self.assertIn("nothing was changed", app.status.get())
        self.assertIsNotNone(self.store.get_contact(CONTACT_EMAILS[0]))
        self.assertEqual(len(self.store.list_contact_conflicts()), 0)
        self.assertEqual(len(self.store.list_contacts()), 2, "both contacts are still stored")

class ContactsExportHandlerTests(ContactTabTestCase):
    """The export control: what it writes, what it refuses, and what it never claims.

    The export is the one control on this tab that writes outside the database, so these tests drive its
    real handler with the stubbed file dialog and read the file back: the documented columns, the mark
    column as the database holds it, the counts in the status line and the event, and no contact value or
    chosen path anywhere in the activity log. "Read-only" is the connection's change counter, and every
    refusal - a closed dialog, a declined overwrite, an unwritable folder, a list over the format's own
    limit - is required to leave the database and the folder exactly as they were and to claim nothing.
    """

    def destination(self, name: str = "contacts-export.csv") -> Path:
        return Path(self._directory.name) / name

    def stored_rows(self, path: Path) -> list:
        return list(csv.reader(io.StringIO(path.read_bytes().decode("utf-8-sig"), newline="")))

    def test_the_control_writes_the_documented_file_and_reports_what_it_held(self):
        app = self.make_app()
        self.import_two(app)
        self.store.set_contact_suppression(CONTACT_EMAILS[0], note=CONTACT_NOTE)
        target = self.destination()
        FILEDIALOG.path = str(target)
        MESSAGES.reset()
        before = self.changes()

        app._export_contacts()

        self.assertTrue(target.is_file())
        rows = self.stored_rows(target)
        self.assertEqual(rows[0], ["Email", "Name", "Company", "Do Not Contact", "Export Format"])
        self.assertEqual([row[0] for row in rows[1:]], [CONTACT_EMAILS[0], CONTACT_EMAILS[1]])
        self.assertEqual([row[1] for row in rows[1:]], [CONTACT_NAMES[0], CONTACT_NAMES[1]])
        self.assertEqual([row[3] for row in rows[1:]], ["yes", "no"],
                         "the mark column does not say what the database holds")
        self.assertTrue(target.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn("Contact list exported", MESSAGES.titles("showinfo"))
        self.assertIn("Exported 2 contact(s)", app.status.get())
        self.assertIn("Nothing was contacted", app.status.get())
        # Read-only: no contact, mark or disagreement row was touched by writing a file.
        self.assertEqual(self.changes(), before, "the export wrote to the database")
        record = self.store.get_contact(CONTACT_EMAILS[0])
        self.assertTrue(record.suppressed)
        self.assertEqual(record.suppressed_note, CONTACT_NOTE)
        # Counts in the log, and nothing else: no address, no name, no company, no note, no path.
        logged = self.log_text()
        self.assertIn("event=contacts.exported", logged)
        self.assertIn("detail=contacts=2 marked=1", logged)
        for value in (*ALL_CONTACT_FIXTURE_VALUES, CONTACT_NOTE, str(target)):
            self.assertNotIn(value, logged, f"{value!r} reached the activity log")

    def test_the_completion_report_carries_the_counts_and_the_marks_limitation(self):
        app = self.make_app()
        self.import_two(app)
        FILEDIALOG.path = str(self.destination())
        MESSAGES.reset()

        app._export_contacts()

        said = MESSAGES.text("showinfo")
        self.assertIn("2 contact(s)", said)
        self.assertIn("0 marked do not contact", said)
        self.assertNotIn(str(self.destination()), said,
                         "the completion report names the folder the file went into")
        self.assertIn(contact_export.MARK_COLUMN_LIMITATION, said,
                      "the report must repeat what the file can and cannot do with a mark")
        for value in (*ALL_CONTACT_FIXTURE_VALUES, CONTACT_NOTE):
            self.assertNotIn(value, said, f"{value!r} reached the completion report")

    def test_an_empty_list_still_writes_the_documented_file_and_says_it_is_empty(self):
        app = self.make_app()
        target = self.destination()
        FILEDIALOG.path = str(target)
        MESSAGES.reset()

        app._export_contacts()

        self.assertEqual(self.stored_rows(target), [["Email", "Name", "Company", "Do Not Contact",
                                                     "Export Format"]])
        self.assertIn("holds no rows", app.status.get())
        self.assertIn("0 contact(s)", MESSAGES.text("showinfo"))
        self.assertEqual(self.changes(), 0, "exporting an empty list wrote to the database")

    def test_a_closed_dialog_writes_nothing_and_says_nothing(self):
        app = self.make_app()
        self.import_two(app)
        FILEDIALOG.path = ""
        MESSAGES.reset()
        listing_before = sorted(path.name for path in Path(self._directory.name).iterdir())

        app._export_contacts()

        self.assertEqual(sorted(path.name for path in Path(self._directory.name).iterdir()),
                         listing_before, "a closed dialog left a file behind")
        self.assertEqual(MESSAGES.titles(), [], "a closed dialog is neither a failure nor a success")
        self.assertNotIn("Exported", app.status.get())
        self.assertNotIn("contacts.exported", self.log_text())

    def test_an_existing_file_is_replaced_only_after_the_question_is_answered(self):
        app = self.make_app()
        self.import_two(app)
        target = self.destination()
        target.write_bytes(b"a person's own file\r\n")
        FILEDIALOG.path = str(target)
        MESSAGES.reset()

        # Declined: nothing is written, the file is untouched, and nothing claims an export happened.
        CONFIG["Replace the existing file?"] = False
        try:
            app._export_contacts()
        finally:
            CONFIG.clear()

        self.assertEqual(target.read_bytes(), b"a person's own file\r\n")
        self.assertIn("Replace the existing file?", MESSAGES.titles("askyesno"))
        asked = MESSAGES.text("askyesno")
        self.assertIn("no undo", asked, "replacing a file the person chose must say it cannot be undone")
        self.assertNotIn("Contact list exported", MESSAGES.titles("showinfo"))
        self.assertIn("cancelled", app.status.get())
        self.assertNotIn("contacts.exported", self.log_text())

        # Confirmed: the file the person agreed to replace is the file the export is written to.
        app._export_contacts()

        self.assertEqual([row[0] for row in self.stored_rows(target)[1:]],
                         [CONTACT_EMAILS[0], CONTACT_EMAILS[1]])
        self.assertIn("Contact list exported", MESSAGES.titles("showinfo"))

    def test_a_folder_that_cannot_be_written_is_reported_without_claiming_success(self):
        app = self.make_app()
        self.import_two(app)
        FILEDIALOG.path = str(Path(self._directory.name) / "absent" / "contacts-export.csv")
        MESSAGES.reset()
        before = self.changes()

        app._export_contacts()

        self.assertEqual(MESSAGES.titles("showerror"), ["Export not saved"])
        self.assertNotIn("Contact list exported", MESSAGES.titles("showinfo"))
        self.assertIn("Export not saved", app.status.get())
        self.assertNotIn("Exported 2", app.status.get())
        self.assertEqual(self.changes(), before, "a failed export wrote to the database")
        self.assertIn("event=contacts.export.failed", self.log_text())
        self.assertNotIn("contacts.exported", self.log_text())
        for value in (*ALL_CONTACT_FIXTURE_VALUES, CONTACT_NOTE):
            self.assertNotIn(value, self.log_text(), f"{value!r} reached the activity log")

    def test_a_list_over_the_formats_own_limit_is_refused_and_writes_no_file(self):
        """The real refusal path: the format's own reader limit is what decides, not a handler's guess."""
        app = self.make_app()
        self.import_two(app)
        target = self.destination()
        FILEDIALOG.path = str(target)
        MESSAGES.reset()

        original = contacts.MAX_CONTACT_CSV_BYTES
        try:
            contacts.MAX_CONTACT_CSV_BYTES = 100
            app._export_contacts()
        finally:
            contacts.MAX_CONTACT_CSV_BYTES = original

        self.assertEqual(MESSAGES.titles("showerror"), ["Nothing was exported"])
        self.assertIn("100 bytes", MESSAGES.text("showerror"))
        self.assertIn("Data safety", MESSAGES.text("showerror"),
                      "the refusal must say where a copy that does hold everything lives")
        self.assertFalse(target.exists())
        self.assertIn("larger than the format", app.status.get())
        self.assertIn("event=contacts.export.failed", self.log_text())
        self.assertNotIn("contacts.exported", self.log_text())

    def test_a_storage_failure_while_reading_the_list_claims_nothing(self):
        app = self.make_app()
        self.import_two(app)
        target = self.destination()
        FILEDIALOG.path = str(target)
        MESSAGES.reset()

        with mock.patch.object(self.store, "list_contacts",
                               side_effect=sqlite3.OperationalError("disk I/O error")):
            app._export_contacts()

        self.assertFalse(target.exists())
        self.assertEqual(MESSAGES.titles("showerror"), ["Local database unavailable"])
        self.assertEqual(app.status.get(), "The local database could not be read; nothing was changed.")
        self.assertNotIn("contacts.exported", self.log_text())

    def test_a_stored_record_this_build_cannot_read_is_reported_and_nothing_is_written(self):
        app = self.make_app()
        self.import_two(app)
        target = self.destination()
        FILEDIALOG.path = str(target)
        MESSAGES.reset()
        self.store._connection.execute("UPDATE hr_contact SET email_key = '' WHERE contact_id = 1")
        self.store._connection.commit()

        app._export_contacts()

        self.assertFalse(target.exists(), "a refused export left a file holding the records it could read")
        self.assertEqual(MESSAGES.titles("showerror"), ["Saved record could not be read"],
                         "an unreadable record is reported by the shared explanation, not a new one")
        self.assertEqual(app.status.get(), "Contact export not written (a stored record could not be read).")
        self.assertNotIn("Contact list exported", MESSAGES.titles("showinfo"))
        self.assertNotIn("contacts.exported", self.log_text(),
                         "a refused export must not be recorded as one that happened")

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits are not meaningful on this platform")
    def test_the_written_file_is_owner_only(self):
        app = self.make_app()
        self.import_two(app)
        target = self.destination()
        FILEDIALOG.path = str(target)

        app._export_contacts()

        self.assertEqual(target.stat().st_mode & 0o777, 0o600)


class ContactConflictPanelTests(ContactTabTestCase):
    """The recorded-disagreement panel: both sides, honestly labelled, and nothing written.

    The panel reads what an import already recorded - the schema stores one row per pair of disagreeing
    non-empty values, with the field they disagree about, which value this database keeps, which one the
    file carried, whether the two sides are two rows of one file or the file against the stored record,
    the file it arrived in and when. These tests drive that screen through the tab's own handlers, so
    "nothing was written" is the connection's change counter, "the mark is untouched" is the stored row,
    and "no value leaked" is the log and the status line rather than a wording.
    """

    def test_each_recorded_disagreement_is_listed_with_its_own_provenance(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())

        rows = self.conflict_rows(app)
        stored_conflicts = app.store.list_contact_conflicts()

        self.assertEqual(len(rows), 3, "one row per recorded disagreement")
        self.assertEqual([str(iid) for iid in app.contact_conflicts_tree.get_children()],
                         [str(conflict.conflict_id) for conflict in stored_conflicts],
                         "the list is the store's own order, oldest first")
        self.assertEqual([row[0] for row in rows], [1, 2, 3], "and it counts the rows for the person")
        # The address is shown the way the stored list shows it - the text the person's own file wrote.
        self.assertEqual([row[1] for row in rows],
                         [CONTACT_EMAILS[0], CONTACT_EMAILS[0], CONTACT_EMAILS[1]])
        self.assertEqual([row[2] for row in rows], ["name", "name", "company"])
        self.assertEqual(rows[0][3], "two rows of one file")
        self.assertEqual(rows[1][3], "your records vs the file")
        self.assertEqual([row[4] for row in rows], ["later-list.csv"] * 3)
        self.assertEqual([row[5] for row in rows], [str(c.observed_at) for c in stored_conflicts])
        self.assertIn("3 disagreement(s) recorded", app.contact_conflict_note.get())
        self.assertIn("no disagreement can be dismissed from this screen", app.contact_conflict_note.get())
        # Looking at a disagreement is not a reason for the stored record to have moved.
        self.assertEqual(app.store.get_contact(CONTACT_EMAILS[0]).name, CONTACT_NAMES[0])

    def test_both_sides_are_labelled_and_neither_is_called_the_right_one(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        first, second, third = app.contact_conflicts_tree.get_children()

        self.select_conflict(app, first)
        detail = self.conflict_detail(app)
        self.assertIn(f"Disagreement {first} about {CONTACT_EMAILS[0]}", detail)
        self.assertIn("Field: name", detail)
        self.assertIn(f"Kept in this database:  {CONFLICT_NAMES[0]}", detail)
        self.assertIn(f"Recorded from the file: {CONFLICT_NAMES[1]}", detail)
        self.assertIn("Kept: the first answer in that file's own row order.", detail)
        self.assertIn("Not kept: a later row in 'later-list.csv' said something different", detail)
        self.assertIn("Recorded ", detail)
        self.assertIn("(UTC, by the import that saw it).", detail)

        self.select_conflict(app, second)
        detail = self.conflict_detail(app)
        self.assertIn(f"Kept in this database:  {CONTACT_NAMES[0]}", detail)
        self.assertIn(f"Recorded from the file: {CONFLICT_NAMES[0]}", detail)
        self.assertIn("Kept: the value this database already held when the file was imported.", detail)
        self.assertIn("so this screen does not claim which file supplied it.", detail)

        self.select_conflict(app, third)
        detail = self.conflict_detail(app)
        self.assertIn("Field: company", detail)
        self.assertIn(f"Kept in this database:  {CONTACT_COMPANIES[1]}", detail)
        self.assertIn(f"Recorded from the file: {CONFLICT_COMPANIES[0]}", detail)

        # Nothing anywhere in the panel says which value is the right one, and nothing offers to settle it.
        for shown in (self.conflict_detail(app), app.contact_conflict_note.get()):
            for claim in ("is correct", "is right", "should be", "was merged", "has been resolved"):
                self.assertNotIn(claim, shown, f"the panel claims {claim!r} about a disagreement")

    def test_a_list_with_no_disagreements_says_so_and_shows_nothing(self):
        app = self.make_app()
        self.import_two(app)

        self.assertEqual(self.conflict_rows(app), [])
        self.assertIn("No disagreements are recorded", app.contact_conflict_note.get())
        self.assertIn("No disagreement is selected", self.conflict_detail(app))
        self.assertEqual(app.store.contact_record_counts()["conflicts"], 0)

    def test_the_list_is_bounded_and_says_how_many_more_are_held(self):
        app = self.make_app()
        self.import_two(app)
        for index in range(45):
            # Each file changes the company to a value no earlier file gave: one stored disagreement each.
            self.import_list(app, self.write_csv(
                f"{CONTACT_EMAILS[0]},{CONTACT_NAMES[0]},Sample Employer variant {index},1,\r\n",
                name=f"variant-{index}.csv"))

        total = len(app.store.list_contact_conflicts())
        rows = self.conflict_rows(app)
        self.assertEqual(total, 45)
        self.assertEqual(len(rows), desktop._CONFLICT_ROWS_SHOWN, "the panel draws one page of them")
        self.assertEqual([row[0] for row in rows], list(range(1, desktop._CONFLICT_ROWS_SHOWN + 1)))
        note = app.contact_conflict_note.get()
        self.assertIn("45 disagreement(s) recorded", note)
        self.assertIn(f"the first {desktop._CONFLICT_ROWS_SHOWN} are listed, oldest first", note)
        self.assertIn("the rest are still stored", note)
        self.assertIn("no way to page to them yet", note)

    def test_a_long_value_is_bounded_in_the_detail_and_a_long_file_name_is_clipped_in_the_list(self):
        long_name = "Sample Person " + ("with a very long name " * 40)
        tabbed_company = "Sample\tEmployer with tabs and\nan embedded newline"
        long_file = ("a-contact-list-with-a-deliberately-long-file-name-to-be-clipped-"
                     "in-the-list-cell.csv")
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.write_csv(
            f'{CONTACT_EMAILS[0]},"{long_name}","{tabbed_company}",1,\r\n', name=long_file))

        # The parser trims a field, so the value the database holds is the trimmed one - and that is the
        # value the panel is describing.
        stored_value = long_name.strip()
        rows = self.conflict_rows(app)
        cell = rows[0][4]
        self.assertTrue(cell.startswith("a-contact-list-with-a-deliberately-long-file-name"),
                        f"the cell holds the file's name: {cell!r}")
        self.assertEqual(len(cell), desktop._CONFLICT_CELL_CHARACTERS + 1,
                         "a cell longer than the limit is clipped with an ellipsis")
        self.assertTrue(cell.endswith("\u2026"))
        self.assertNotIn("\n", cell, "a cell is one line whatever the value held")

        first, second = app.contact_conflicts_tree.get_children()
        self.select_conflict(app, first)
        detail = self.conflict_detail(app)
        self.assertIn(f"Recorded from the file: {stored_value[:desktop._CONFLICT_VALUE_CHARACTERS]}", detail)
        self.assertNotIn(stored_value, detail, "the whole value is not drawn into the panel")
        self.assertIn(f"[this value is {len(stored_value)} characters long; only the first "
                      f"{desktop._CONFLICT_VALUE_CHARACTERS} are shown here]", detail)
        self.select_conflict(app, second)
        self.assertIn(tabbed_company, self.conflict_detail(app),
                      "a value is shown as the file wrote it, tabs and newlines included")

    def test_reviewing_disagreements_writes_nothing_and_leaves_the_mark_alone(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        app.store.set_contact_suppression(CONTACT_EMAILS[0], note=CONTACT_NOTE)
        app._refresh_contacts()
        before = self.changes()
        marked = app.store.get_contact(CONTACT_EMAILS[0])

        app._refresh_contacts()
        for item in app.contact_conflicts_tree.get_children():
            self.select_conflict(app, item)
        app._on_tab_changed()
        app._show_selected_conflict()

        self.assertEqual(self.changes(), before, "reading a disagreement must not write a row")
        after = app.store.get_contact(CONTACT_EMAILS[0])
        self.assertEqual((after.suppressed, after.suppressed_at, after.suppressed_note),
                         (marked.suppressed, marked.suppressed_at, marked.suppressed_note),
                         "reviewing a disagreement must not touch the do-not-contact mark")
        self.assertEqual(app.contact_conflict_text.cget("state"), "disabled",
                         "the detail box is read-only to typing, not only by convention")

    def test_no_disagreement_value_reaches_a_log_a_dialog_or_the_status_line(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        app.status.set("Something the person was told before they looked at this tab.")
        MESSAGES.reset()

        app._refresh_contacts()
        for item in app.contact_conflicts_tree.get_children():
            self.select_conflict(app, item)

        self.assertEqual(MESSAGES.titles(), [], "reading a disagreement neither asks nor announces anything")
        self.assertEqual(app.status.get(), "Something the person was told before they looked at this tab.",
                         "the panel leaves the status line as it found it")
        written = self.log_text()
        for value in ALL_CONTACT_FIXTURE_VALUES + ALL_CONFLICT_FIXTURE_VALUES + ("later-list.csv",):
            self.assertNotIn(value, written, f"{value!r} must not reach the activity log")
        self.assertIn("event=contacts.imported", written, "the imports themselves are still recorded")

    def test_a_disagreement_recorded_while_the_tab_was_elsewhere_appears_when_it_is_shown(self):
        app = desktop.CareerAgentApp(Widget(), database_path=Path(self._directory.name) / "panel.sqlite3")
        try:
            self.import_two(app)
            app.tabs.select(app.profile_tab)
            # A second connection, as a second window or a script would be, records a disagreement while
            # nobody is looking at the contacts tab.
            elsewhere = CareerStore(Path(self._directory.name) / "panel.sqlite3")
            try:
                elsewhere.import_contacts(contacts.read_contact_csv(self.contradicting_list()))
            finally:
                elsewhere.close()
            self.assertEqual(self.conflict_rows(app), [], "the tab has not shown the new rows yet")

            app.tabs.select(app.contacts_tab)

            self.assertEqual(len(self.conflict_rows(app)), 3, "showing the tab re-reads the database")
            self.assertIn("3 disagreement(s) recorded", app.contact_conflict_note.get())
            app.tabs.select(app.profile_tab)
            self.assertEqual(len(self.conflict_rows(app)), 3, "looking at another tab keeps the list as it was")
        finally:
            app.close()

    def test_a_selection_that_is_no_longer_recorded_is_reported_rather_than_described(self):
        app = self.make_app()
        self.import_two(app)
        self.import_list(app, self.contradicting_list())
        first = app.contact_conflicts_tree.get_children()[0]
        self.select_conflict(app, first)
        self.assertIn("Kept in this database", self.conflict_detail(app))
        MESSAGES.reset()
        # The row goes (another window, or a restore that replaced the database) and the view is refreshed.
        app.store._connection.execute("DELETE FROM hr_contact_conflict WHERE conflict_id = ?", (int(first),))
        app.store._connection.commit()

        app._refresh_contacts()

        self.assertEqual(len(self.conflict_rows(app)), 2, "the disagreements that are still recorded remain")
        self.assertEqual([row[0] for row in self.conflict_rows(app)], [1, 2],
                         "and the list counts from one again")
        self.assertIn("No disagreement is selected", self.conflict_detail(app),
                      "the row the panel was describing is gone, so nothing is selected")
        # A stale identifier - a row the refresh dropped but a click had already chosen - is described as
        # what it is rather than as a disagreement that exists.
        app.contact_conflict_selected_id = 4242
        app._show_selected_conflict()
        self.assertIn("no longer recorded in this database", self.conflict_detail(app))
        self.assertEqual(MESSAGES.titles(), [], "nothing here is worth a dialog")
