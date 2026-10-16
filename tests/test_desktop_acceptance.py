"""Tests for scripts/desktop_acceptance.py - the end-to-end desktop workflows.

Two things are tested here, and they are different from each other.

* **Under this machine's own Tk, if it has one**, the workflows run for real: the real ``CareerAgentApp``
  window, the real widgets, the real handlers, the real SQLite files, and every check asserting what was
  actually stored. On Linux without a display, and on an interpreter without ``tkinter``, that half reports
  BLOCKED - the same 0/1/2 the script itself uses - rather than skipping quietly, so "no window here" can
  never be mistaken for "everything passed".
* **Always**, the harness's own reading of a window is exercised against a stand-in widget module: that a
  typed value reaches the entry bound to the application's variable, that a button is pressed through its
  own ``invoke``, that a dialog is found by its title, that every Tk variable a dialog creates is captured,
  and that a widget without the option asked for is not mistaken for the one wanted. Those are the parts of
  the harness that would silently stop checking things if Tk's own behaviour were assumed instead.

The stand-in is not a substitute for the display-backed run: whether the workflows pass against real Tk is
exactly what this file cannot answer, which is why the result is reported as BLOCKED here and as a real
pass or failure in CI's display-backed Linux job and on the Windows and macOS runners.
"""
from __future__ import annotations

import contextlib
import io
import re
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for folder in (REPOSITORY_ROOT / "scripts", REPOSITORY_ROOT / "tests"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import desktop_acceptance as acceptance  # noqa: E402
import desktop_smoke_test as smoke  # noqa: E402
import test_desktop_handlers as stub_module  # noqa: E402  (the stand-in widgets, reused on purpose)


def run_the_script(*arguments: str) -> tuple[int, str]:
    """Run ``scripts/desktop_acceptance.py`` in its own interpreter and return (status, output).

    In its own interpreter *on purpose*. This test file imports ``tests/test_desktop_handlers.py``, which
    installs its stand-in widget module for the whole process and leaves ``career_agent.desktop`` bound to
    it. A real display-backed run inside that process would build stub widgets inside a real host window,
    find nothing to drive, and fail - or, worse, if the stand-in were partial, look at widgets that are not
    on screen and call it evidence. A separate interpreter has none of that history: it runs exactly the
    command CI runs, and its exit status is the same 0/1/2 a person gets.
    """
    completed = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / "scripts" / "desktop_acceptance.py"), *arguments],
        cwd=str(REPOSITORY_ROOT), capture_output=True, text=True, timeout=600, check=False,
    )
    return completed.returncode, completed.stdout + completed.stderr


class HarnessTests(unittest.TestCase):
    """Reading a window: the harness against the project's own stand-in widget module."""

    def setUp(self):
        self.tk = stub_module._tkinter  # noqa: SLF001 - the stand-in module the suite already maintains
        self.original = sys.modules.get("tkinter")
        sys.modules["tkinter"] = self.tk
        sys.modules.setdefault("tkinter.ttk", types.ModuleType("tkinter.ttk"))
        stub_module.BUTTONS.clear()
        stub_module.MESSAGES.reset()

    def tearDown(self):
        if self.original is None:
            sys.modules.pop("tkinter", None)
        else:
            sys.modules["tkinter"] = self.original

    def make_vars(self, *names):
        return {name: self.tk.StringVar(value="") for name in names}

    def make_form(self, names):
        """A frame holding one entry per variable, built the way the window builds its forms."""
        frame = self.tk.ttk.Frame()
        variables = self.make_vars(*names)
        for variable in variables.values():
            self.tk.ttk.Entry(frame, textvariable=variable)
        return frame, variables

    def test_a_value_typed_into_the_bound_entry_reaches_the_applications_variable(self):
        frame, variables = self.make_form(["country", "graduation_year"])
        typed = acceptance.type_into(frame, variables["country"], "Syntheticland", what="the country field")
        self.assertEqual(typed, "Syntheticland")
        self.assertEqual(variables["country"].get(), "Syntheticland")
        self.assertEqual(variables["graduation_year"].get(), "", "the wrong field was written to")

    def test_typing_replaces_what_was_there_rather_than_appending(self):
        frame, variables = self.make_form(["country"])
        variables["country"].set("Old value")
        acceptance.type_into(frame, variables["country"], "New value", what="the country field")
        self.assertEqual(variables["country"].get(), "New value")

    def test_a_widget_bound_to_no_variable_is_not_taken_for_the_one_wanted(self):
        frame = self.tk.ttk.Frame()
        wanted = self.tk.StringVar(value="")
        self.tk.ttk.Entry(frame)  # an entry the window did not bind to anything
        self.tk.ttk.Entry(frame, textvariable=wanted)
        found = acceptance.widget_for(frame, wanted, klass=acceptance.ENTRY, what="the field")
        self.assertIs(found.cget("textvariable"), wanted)

    def test_a_widget_that_names_its_variable_the_way_real_tk_does_is_found(self):
        """Real Tk answers ``cget`` with the variable's Tcl name, not with the variable object.

        The stand-in answers with the object, so this is the half of the comparison only a real window
        exercises: a widget bound through a name has to be recognised, and a name that belongs to another
        variable - or to none - must not be.
        """

        class NamedVariable:
            def __init__(self, name):
                self._name = name

            def __str__(self):
                return self._name

        class NamedWidget:
            def __init__(self, bound):
                self.bound = bound

            def cget(self, option):
                if option == "textvariable":
                    raise KeyError("a checkbutton is not bound through textvariable here")
                return self.bound

        variable = NamedVariable("PY_VAR7")
        self.assertTrue(acceptance.linked_to(NamedWidget("PY_VAR7"), variable), "a name is a binding")
        self.assertTrue(acceptance.linked_to(NamedWidget(variable), variable), "the object itself is one too")
        self.assertFalse(acceptance.linked_to(NamedWidget("PY_VAR9"), variable), "another name is not")
        self.assertFalse(acceptance.linked_to(NamedWidget(""), variable), "no name at all is not")
        self.assertFalse(acceptance.linked_to(NamedWidget(None), variable), "a missing option is not")

    def test_a_variable_name_tk_hands_back_as_its_own_kind_of_object_is_still_read(self):
        """Tk does not always answer a lookup with a ``str``: what it hands back has to be read as one."""

        class NamedVariable:
            _name = "PY_VAR11"

            def __str__(self):
                return self._name

        class TclObject:
            """Stands in for whatever Tk returns when the result is not a plain Python string."""

            def __init__(self, text):
                self.text = text

            def __str__(self):
                return self.text

        class NamedWidget:
            def __init__(self, bound):
                self.bound = bound

            def cget(self, option):
                if option == "textvariable":
                    raise KeyError("a checkbutton is not bound through textvariable here")
                return self.bound

        variable = NamedVariable()
        self.assertTrue(
            acceptance.linked_to(NamedWidget(TclObject("PY_VAR11")), variable),
            "a name handed back as Tk's own object was not read as the name it carries",
        )
        self.assertFalse(acceptance.linked_to(NamedWidget(TclObject("PY_VAR12")), variable),
                         "another variable's name is not a binding")

    def test_a_lookup_that_finds_nothing_says_what_the_class_actually_holds(self):
        frame = self.tk.ttk.Frame()
        wanted = self.tk.BooleanVar(value=False)
        other = self.tk.BooleanVar(value=False)
        self.tk.ttk.Checkbutton(frame, variable=other)

        with self.assertRaises(acceptance.SmokeFailure) as caught:
            acceptance.widget_for(frame, wanted, klass=acceptance.CHECKBUTTON,
                                  what="the current-role checkbox")

        message = str(caught.exception)
        self.assertIn("the current-role checkbox", message)
        self.assertIn("1 TCheckbutton widget(s) under it", message, message)
        self.assertIn("variable=<", message, "the failure does not say what the widget is bound to")

    def test_a_missing_control_fails_with_a_message_naming_what_was_looking_for(self):
        frame = self.tk.ttk.Frame()
        self.tk.ttk.Label(frame, text="nothing like a button")
        with self.assertRaises(acceptance.SmokeFailure) as caught:
            acceptance.press(frame, "Save job", mock.Mock())
        self.assertIn("button labelled 'Save job'", str(caught.exception))
        self.assertIn("TLabel", str(caught.exception), "the failure does not say what was there instead")

    def test_pressing_a_button_runs_the_command_the_window_built_it_with(self):
        frame = self.tk.ttk.Frame()
        calls = []
        self.tk.ttk.Button(frame, text="Save job", command=lambda: calls.append("pressed"))
        acceptance.press(frame, "Save job", mock.Mock())
        self.assertEqual(calls, ["pressed"])

    def test_a_chooser_is_set_through_the_variable_the_window_bound_to_it(self):
        frame = self.tk.ttk.Frame()
        scope = self.tk.StringVar(value="unknown")
        self.tk.ttk.Combobox(frame, textvariable=scope, values=["unknown", "worldwide"])
        acceptance.choose_in(frame, scope, "worldwide", what="the scope chooser")
        self.assertEqual(scope.get(), "worldwide")

    def test_a_dialog_is_found_by_the_title_the_window_gave_it(self):
        host = self.tk.Tk()
        dialog = self.tk.Toplevel(host)
        dialog.title("Update application status")
        self.assertIs(acceptance.open_dialog(host, "Update application status"), dialog)
        with self.assertRaises(acceptance.SmokeFailure) as caught:
            acceptance.open_dialog(host, "No such dialog")
        self.assertIn("Update application status", str(caught.exception),
                      "the failure does not list the dialogs that were open")

    def test_every_variable_a_dialog_creates_is_recorded_for_it(self):
        from career_agent import desktop  # noqa: PLC0415 - imported with the stand-in installed

        policy = acceptance.DialogPolicy()
        created = []

        def build_dialog():
            created.append(desktop.tk.StringVar(value="first"))
            created.append(desktop.tk.BooleanVar(value=False))
            return created[-1]

        acceptance.record_dialog_controls(policy, "A dialog", build_dialog)
        self.assertEqual(created[0].get(), "first", "the dialog's own variable changed under it")
        self.assertEqual([variable.get() for variable in acceptance.string_variables(policy, "A dialog")],
                         ["first"])
        self.assertEqual([variable.get() for variable in acceptance.boolean_variables(policy, "A dialog")],
                         [False])
        self.assertEqual(list(policy.fields), ["A dialog"])

    def test_the_dialog_policy_answers_files_in_order_and_records_every_dialog(self):
        policy = acceptance.DialogPolicy(files=("/tmp/one.json", "/tmp/two.json"),
                                         answers={"Delete?": False})
        self.assertEqual(policy.asksaveasfilename(), "/tmp/one.json")
        self.assertEqual(policy.askopenfilename(), "/tmp/two.json")
        self.assertEqual(policy.asksaveasfilename(), "", "a chooser with no path left must cancel")
        self.assertFalse(policy.askyesno("Delete?", "Really?"))
        self.assertTrue(policy.askyesno("Import this file?", "Apply it now?"))
        policy.showinfo("Import complete", "Added one listing")
        self.assertEqual(policy.titles(), ["Delete?", "Import this file?", "Import complete"])
        self.assertEqual(policy.titles("showinfo"), ["Import complete"])
        self.assertIn("Added one listing", policy.said("Import complete"))

    def test_a_text_widget_reports_what_the_window_wrote_into_it(self):
        text = self.tk.Text()
        text.insert("1.0", "ELIGIBILITY: UNKNOWN\n")
        self.assertEqual(acceptance.text_in(text), "ELIGIBILITY: UNKNOWN\n")


class StepCoverageTests(unittest.TestCase):
    """A check that stops running is a failure, and the run says so itself."""

    def test_the_declared_count_is_read_from_the_source_and_is_not_trivial(self):
        declared = acceptance.declared_step_count()
        self.assertGreaterEqual(declared, 30, "the declared count looks wrong")
        # Matched with the opening quote so the mention of the form inside a docstring is not counted as
        # a call: this is a check on the AST's answer, not a second implementation of it.
        self.assertEqual(declared, len(re.findall(r'results\.step\("', self.source)), "AST and text disagree")

    def test_a_run_that_performed_fewer_checks_than_it_declares_is_not_a_pass(self):
        results = smoke.Results()
        results.passed = acceptance.declared_step_count() - 1
        self.assertIsNotNone(acceptance.ran_every_declared_check(results))

    def test_a_run_that_performed_every_declared_check_has_nothing_to_report(self):
        results = smoke.Results()
        results.passed = acceptance.declared_step_count()
        self.assertIsNone(acceptance.ran_every_declared_check(results))

    def test_a_failed_check_still_counts_as_a_check_that_ran(self):
        results = smoke.Results()
        results.passed = acceptance.declared_step_count() - 1
        results.failures.append(("a check", "traceback"))
        self.assertIsNone(acceptance.ran_every_declared_check(results))

    def setUp(self):
        self.source = (REPOSITORY_ROOT / "scripts" / "desktop_acceptance.py").read_text(encoding="utf-8")


class WorkflowWiringTests(unittest.TestCase):
    """The acceptance run is only evidence if CI runs it where a window exists, and gates on it."""

    def setUp(self):
        self.workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    def test_the_script_runs_on_the_display_backed_leg_and_gates_on_its_result(self):
        self.assertIn("xvfb-run -a --server-args=\"-screen 0 1280x1024x24\" python3 scripts/desktop_acceptance.py",
                      self.workflow)
        self.assertIn("grep -q \"RESULT: PASS\"", self.workflow)
        self.assertIn("RESULT: BLOCKED", self.workflow)
        self.assertEqual(acceptance.EXIT_PASS, 0)
        self.assertEqual(acceptance.EXIT_FAIL, 1)
        self.assertEqual(acceptance.EXIT_BLOCKED, 2)

    def test_the_leg_fails_when_a_workflow_stops_running_or_a_check_stops(self):
        self.assertIn("for workflow in ", self.workflow)

    def test_ci_requires_every_workflow_letter_the_run_defines(self):
        # Read from the run's own list, so adding a workflow without adding it to CI fails here rather than
        # leaving a workflow that never runs on a runner. Compared as a set: each of CI's greps stands on its
        # own, so the order it lists them in carries no meaning.
        letters = sorted(name[0] for name, _workflow in acceptance.WORKFLOWS)
        self.assertIn(f"for workflow in {' '.join(letters)}; do", self.workflow,
                      "CI does not require every workflow this run defines")
        # The run compares what it performed against what its own source declares, and says what that means.
        script = (REPOSITORY_ROOT / "scripts" / "desktop_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("a check that does not run is not a pass", script)
        # And CI carries no count of its own to drift: a number there would have to be edited whenever a
        # check is added, and the check that matters - did every declared check run - is the script's job.
        self.assertNotIn("-eq 36", self.workflow)
        self.assertNotIn("-eq 37", self.workflow)

    def test_the_stand_in_flag_is_used_only_to_prove_it_is_not_evidence(self):
        # Exactly one run asks for the stand-in, and it is the step that requires BLOCKED and no pass
        # line from it. A second one anywhere would mean CI had started accepting stand-in results.
        self.assertEqual(self.workflow.count("desktop_acceptance.py --stand-in-tk"), 1)
        self.assertIn("Confirm the acceptance workflows cannot be run against stand-in widgets in CI",
                      self.workflow)

    def test_a_run_with_no_display_must_not_report_a_pass(self):
        # The step that runs with DISPLAY unset requires exit 2 and forbids a pass line, which is what
        # keeps a display-less runner from looking green.
        self.assertIn('env -u DISPLAY python3 scripts/desktop_acceptance.py', self.workflow)
        self.assertIn("the acceptance run reported success without a display", self.workflow)

    def test_the_windows_and_macos_legs_run_the_workflows_and_tolerate_only_blocked(self):
        self.assertIn("Desktop acceptance workflows (the real window, or an honest BLOCKED)", self.workflow)
        self.assertIn("the acceptance workflows reported BLOCKED on ${{ matrix.os }}", self.workflow)
        self.assertIn("the acceptance workflows failed on this runner", self.workflow)


class DevelopmentRunTests(unittest.TestCase):
    """The stand-in run: useful for writing the workflows, and impossible to mistake for evidence."""

    def test_a_stand_in_run_never_reports_a_pass_or_failure_and_exits_blocked(self):
        status, output = run_the_script("--stand-in-tk")

        self.assertEqual(status, smoke.EXIT_BLOCKED, "a stand-in run must never be a pass or a failure")
        self.assertNotIn("RESULT: PASS", output, "a stand-in run printed a pass line")
        self.assertNotIn("RESULT: FAIL", output, "a stand-in run printed a failure line")
        self.assertIn("DEVELOPMENT RUN", output)
        self.assertIn("not a desktop", output)
        self.assertIn("[ ok ] A1", output, "the development run did not exercise the workflows")
        self.assertIn(
            f"DEVELOPMENT RESULT: {acceptance.declared_step_count()} checks passed, 0 failed", output
        )

    def test_a_stand_in_tkinter_is_recognised_as_one(self):
        self.assertTrue(acceptance.using_stand_in_tk(types.ModuleType("tkinter")))
        self.assertFalse(acceptance.using_stand_in_tk(smoke))  # a real module, with a file


class DestroyedWindowTests(unittest.TestCase):
    """A window whose Tk interpreter is gone: the case that only a real display produces.

    The display-backed CI run reported it: after the run's root was destroyed, ``winfo_exists`` no longer
    answered - it raised ``TclError: can't invoke "winfo" command: application has been destroyed`` - and the
    cleanup check reported a defect that was not there. The stand-in cannot produce that, because it has no
    interpreter to destroy, which is why the shape of the real failure is written down here as well.
    """

    class Gone:
        """A widget of a destroyed interpreter: it still exists as an object, and Tk will not answer."""

        def winfo_exists(self):
            raise RuntimeError('can\'t invoke "winfo" command: application has been destroyed')

        def winfo_children(self):
            raise RuntimeError('can\'t invoke "winfo_children" command: application has been destroyed')

        def winfo_class(self):
            raise RuntimeError('can\'t invoke "winfo_class" command')

    def test_a_window_whose_interpreter_is_destroyed_does_not_count_as_surviving(self):
        self.assertFalse(acceptance.widget_exists(self.Gone()))

    def test_a_window_that_really_survived_still_counts_as_existing(self):
        self.assertTrue(acceptance.widget_exists(self.tk_widget()))

    def test_a_widget_that_really_was_destroyed_does_not_count_as_existing(self):
        widget = self.tk_widget()
        widget.destroy()
        self.assertFalse(acceptance.widget_exists(widget))

    def test_no_dialogs_are_reported_for_a_window_tk_will_not_answer_for(self):
        self.assertEqual(acceptance.dialogs_under(self.Gone()), [])

    def tk_widget(self):
        stub = stub_module._tkinter  # noqa: SLF001
        host = stub.Toplevel()
        return stub.ttk.Frame(host)


class SelectionTests(unittest.TestCase):
    """Selecting a row, against a window whose event loop cannot dispatch a selection event."""

    def setUp(self):
        self.tk = stub_module._tkinter  # noqa: SLF001
        self.original = sys.modules.get("tkinter")
        sys.modules["tkinter"] = self.tk
        stub_module.BUTTONS.clear()
        stub_module.MESSAGES.reset()

    def tearDown(self):
        if self.original is None:
            sys.modules.pop("tkinter", None)
        else:
            sys.modules["tkinter"] = self.original

    def fake_app(self):
        """The smallest stand-in for the window: a jobs tree, a handler, and its own record of the row."""
        app = types.SimpleNamespace()
        app.jobs_tree = self.tk.ttk.Treeview()
        app.jobs_tree.insert("", "end", iid="synthetic-1", values=("a listing",))
        app.selected_job_id = None
        app.handler_calls = []

        def select_job():
            app.handler_calls.append(app.jobs_tree.selection()[:1])
            app.selected_job_id = str(app.jobs_tree.selection()[0])

        app._select_job = select_job
        return app

    def test_the_handler_runs_once_when_the_window_has_not_reacted(self):
        app = self.fake_app()
        acceptance.select_listing(app, "synthetic-1", mock.Mock(update=lambda: None))
        self.assertEqual(len(app.handler_calls), 1, "the selection handler did not run exactly once")
        self.assertEqual(app.selected_job_id, "synthetic-1")

    def test_the_handler_is_not_run_again_when_the_window_already_reacted(self):
        app = self.fake_app()
        app.selected_job_id = "synthetic-1"  # as if the event loop had already dispatched the selection
        acceptance.select_listing(app, "synthetic-1", mock.Mock(update=lambda: None))
        self.assertEqual(app.handler_calls, [], "the window's own dispatch was duplicated by the harness")

    def test_a_window_that_never_reacts_fails_the_selection_check(self):
        app = self.fake_app()
        app._select_job = lambda: None  # a window that does nothing with the selection
        with self.assertRaises(acceptance.SmokeFailure) as caught:
            acceptance.select_listing(app, "synthetic-1", mock.Mock(update=lambda: None))
        self.assertIn("not working on 'synthetic-1'", str(caught.exception))


class DisplayBackedWorkflowTests(unittest.TestCase):
    """The workflows themselves, against this machine's own Tk when it has one.

    Reported as BLOCKED, not skipped, when it does not: a suite that went green here while asserting
    nothing about the workflows would be the exact failure this project keeps writing rules about.
    """

    def test_the_workflows_run_against_a_real_window_or_report_they_cannot(self):
        status, output = run_the_script()

        if status == smoke.EXIT_BLOCKED:
            self.assertIn("RESULT: BLOCKED", output)
            self.assertNotIn("RESULT: PASS", output)
            self.assertNotIn("RESULT: FAIL", output)
            print(f"\n[acceptance] BLOCKED on this machine: {output.strip().splitlines()[-2]}")
            return

        self.assertIn("A1", output, "the profile workflow did not run")
        self.assertEqual(
            status, smoke.EXIT_PASS,
            f"the acceptance run did not pass. Exit {status}. Output tail:\n{output[-6000:]}",
        )
        self.assertIn("RESULT: PASS", output)
        # Every workflow is named in the report, so a workflow that silently stopped running shows up here.
        for name, _workflow in acceptance.WORKFLOWS:
            self.assertIn(f"--- workflow {name}", output)

    def test_the_workflow_list_covers_the_documented_letters(self):
        # The order is the run's own, and H sits before F because F releases the Tk root the run works
        # through: a workflow that needs a window has to come before the one that takes it away.
        names = [name for name, _workflow in acceptance.WORKFLOWS]
        # K is the measured half of the layout, keyboard and labelling checks: unlike the workflows
        # before it, it asserts nothing about the records and only reports numbers about the window, so
        # it runs after them and before F for the same reason they do.
        self.assertEqual([name[0] for name in names],
                         ["A", "B", "C", "D", "E", "G", "H", "I", "J", "K", "L", "F"])
        for name, workflow in acceptance.WORKFLOWS:
            self.assertTrue(callable(workflow), f"{name} is not runnable")
            self.assertTrue(workflow.__doc__ or workflow.__name__, f"{name} has no name in the report")

class LayoutMeasurementTests(unittest.TestCase):
    """What workflow K measures a widget against, and what it refuses to call a layout failure.

    The rule is a unit test rather than a comment because it decides what a display-backed run means. Two
    cases it must not conflate: content below the fold of a scrolling area is reachable - that is what
    scrolling is for - and a control wider than the frame that scrolls it is not reachable however far the
    wheel turns. Both were added after the measurement of 2026-10-16, where the tab that holds more than a
    small window shows needed a scrolling area and the harness had no notion of one.
    """

    class FakeWidget:
        """A widget answering the geometry questions the harness asks, with numbers a test chooses."""

        def __init__(self, klass, *, master=None, x=0, y=0, width=100, height=30):
            self.tk_class = klass
            self.master = master
            self.rectangle = (x, y, width, height)
            self.children = []
            if master is not None:
                master.children.append(self)

        def winfo_class(self):
            return self.tk_class

        def winfo_children(self):
            return list(self.children)

        def winfo_exists(self):
            return True

        def winfo_ismapped(self):
            return True

        def winfo_viewable(self):
            return True

        def winfo_width(self):
            return self.rectangle[2]

        def winfo_height(self):
            return self.rectangle[3]

        def winfo_rootx(self):
            return self.rectangle[0]

        def winfo_rooty(self):
            return self.rectangle[1]

        def winfo_reqwidth(self):
            return self.rectangle[2]

        def winfo_reqheight(self):
            return self.rectangle[3]

        def cget(self, _name):
            return ""

    def scrolling_pair(self, page_width=400, page_height=200, content_height=900):
        """A tab with a canvas in it, and the frame that canvas scrolls."""
        page = self.FakeWidget("TFrame", width=page_width, height=page_height)
        canvas = self.FakeWidget("Canvas", master=page, width=page_width, height=page_height)
        scrolled = self.FakeWidget("TFrame", master=canvas, width=page_width, height=content_height)
        return page, canvas, scrolled

    def test_a_widget_inside_a_scrolling_area_is_measured_against_the_frame_that_scrolls(self):
        page, canvas, scrolled = self.scrolling_pair()
        inner = self.FakeWidget("TFrame", master=scrolled)
        entry = self.FakeWidget("TEntry", master=inner)

        self.assertTrue(acceptance.is_scrolled_frame(scrolled),
                        "the frame a canvas scrolls is the content root of that scrolling area")
        self.assertIs(acceptance.layout_container(entry, page), scrolled)
        self.assertIs(acceptance.layout_container(inner, page), scrolled,
                      "a frame nested in the content root is measured against the content root too")
        self.assertIs(acceptance.layout_container(canvas, page), page,
                      "the canvas itself is laid out in the tab, not in the area it scrolls")

    def test_content_below_the_fold_of_a_scrolling_area_is_reachable_and_not_a_failure(self):
        page, _canvas, scrolled = self.scrolling_pair()
        below_the_fold = self.FakeWidget("TFrame", master=scrolled, y=600, width=380, height=40)

        measured, problems = acceptance.layout_problems(None, page)

        self.assertEqual(problems, [], "content a person can scroll to is not clipped content")
        self.assertGreaterEqual(measured, 2, "the canvas and the widget below the fold are both measured")
        self.assertIn(below_the_fold, acceptance.descendants(page))

    def test_a_control_wider_than_the_frame_that_scrolls_it_is_still_reported(self):
        page, _canvas, scrolled = self.scrolling_pair(page_width=400)
        too_wide = self.FakeWidget("TButton", master=scrolled, x=350, width=200, height=30)

        _measured, problems = acceptance.layout_problems(None, page)

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("is outside the scrolling area it is in", problems[0])
        self.assertIn(str(too_wide), problems[0])

    def test_the_content_root_of_a_scrolling_area_is_not_measured_itself(self):
        page, canvas, scrolled = self.scrolling_pair(content_height=900)
        inside = self.FakeWidget("TFrame", master=scrolled, width=380, height=40)

        measured, problems = acceptance.layout_problems(None, page)

        self.assertNotIn(scrolled, acceptance.measurable_widgets(page),
                         "the scrolled frame is the box the content is measured in, not content")
        self.assertEqual(problems, [])
        self.assertEqual(measured, 2, "the canvas and the widget inside the scrolling area are measured")
        self.assertIn(canvas, acceptance.measurable_widgets(page))
        self.assertIn(inside, acceptance.measurable_widgets(page))

    def test_a_window_smaller_than_its_own_minimum_is_recognised(self):
        self.assertTrue(acceptance.window_below((950, 502), (900, 600)),
                        "shorter than the minimum counts, even when it is wider")
        self.assertTrue(acceptance.window_below((800, 700), (900, 600)))
        self.assertFalse(acceptance.window_below((900, 600), (900, 600)))
        self.assertFalse(acceptance.window_below((1400, 900), (900, 600)))

    def judge_through(self, page, *, asked, achieved, minimum, message="content outside:"):
        """Run ``judge_layout_at`` over one stand-in page and return what it returned and printed."""
        app = types.SimpleNamespace(tabs=self.FakeWidget("TNotebook"))
        printed = io.StringIO()
        with mock.patch.object(acceptance, "tab_pages", return_value=[("the tab", page)]), \
                mock.patch.object(acceptance, "show_tab", lambda *_args: None), \
                contextlib.redirect_stdout(printed):
            judged = acceptance.judge_layout_at(app, app, "at the declared minimum", asked, achieved,
                                                minimum, message)
        return judged, printed.getvalue()

    def test_a_window_below_its_own_declared_minimum_is_reported_rather_than_judged(self):
        # The macOS runners in run 38814625351 answered a 1400x900 request with a 950x502 page: a display
        # that cannot show this window's own 900x600 minimum. Below that minimum there is no layout to hold
        # the application to, so what the run must do is say so - with both sizes - not call it a defect.
        page, _canvas, scrolled = self.scrolling_pair(page_width=400, page_height=200)
        self.FakeWidget("TButton", master=scrolled, x=350, width=200, height=30)

        judged, printed = self.judge_through(page, asked=(900, 600), achieved=(950, 502), minimum=(900, 600))

        self.assertIsNone(judged)
        self.assertIn("NOT judged", printed)
        self.assertIn("950x502", printed, "the size the window has must be in the report")
        self.assertIn("900x600", printed, "so must the size the application declares")

    def test_content_outside_the_tab_is_a_failure_at_a_size_the_window_can_be_shown_at(self):
        page, _canvas, scrolled = self.scrolling_pair(page_width=400, page_height=200)
        self.FakeWidget("TButton", master=scrolled, x=350, width=200, height=30)

        with self.assertRaises(acceptance.SmokeFailure) as caught:
            self.judge_through(page, asked=(900, 600), achieved=(900, 600), minimum=(900, 600),
                               message="content sits outside its tab at the smallest size this window allows:")

        self.assertIn("content sits outside its tab at the smallest size this window allows:", str(caught.exception))
        self.assertIn("the tab: TButton", str(caught.exception))

    def test_nothing_outside_the_tab_is_not_a_failure(self):
        page, _canvas, _scrolled = self.scrolling_pair(page_width=400, page_height=200)
        self.FakeWidget("TFrame", master=page, width=200, height=40)

        judged, printed = self.judge_through(page, asked=(900, 600), achieved=(900, 600), minimum=(900, 600))

        self.assertEqual(judged, 2, "both widgets were measured and neither was outside")
        self.assertIn("layout judged", printed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
