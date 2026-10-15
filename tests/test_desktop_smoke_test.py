"""Tests for scripts/desktop_smoke_test.py — the entry point CI uses for the desktop window.

A test file rather than a note because the property that matters here is the one that is easiest to lose:
the smoke test must report BLOCKED, not success, whenever this machine cannot show a window. A smoke test
that passed on a machine with no display would make every platform leg of CI green while verifying nothing,
so the checks below pin that behaviour without needing a display themselves. They also pin the static half
of the contract - the tab list the script expects and the exit statuses the workflow gates on - because
those drift silently: a tab renamed in ``desktop.py`` would otherwise only be noticed on the one runner
that has a window.

Nothing here creates a Tk root: the module is imported, its pure helpers are called, and ``main`` is driven
with a stand-in ``tkinter``. Whether a real window can be built is exactly what this file cannot answer.
"""
from __future__ import annotations

import io
import re
import sys
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import desktop_smoke_test as smoke  # noqa: E402


class NoDisplayClassificationTests(unittest.TestCase):
    """Only a display problem may be reported as BLOCKED; anything else is a defect."""

    def test_the_messages_tk_produces_without_a_display_are_recognised(self):
        for message in (
            "no display name and no $DISPLAY environment variable",
            "couldn't connect to display \":99\"",
            "unable to open display \"localhost:10.0\"",
            "Invalid display name: :0",
        ):
            with self.subTest(message=message):
                self.assertTrue(smoke.looks_like_no_display(message))

    def test_a_different_tk_failure_is_not_treated_as_a_missing_display(self):
        for message in ("invalid command name \"ttk::style\"", "out of memory", "bad window path name"):
            with self.subTest(message=message):
                self.assertFalse(smoke.looks_like_no_display(message))


class MainResultTests(unittest.TestCase):
    """What the entry point returns, driven with a stand-in tkinter."""

    def run_main(self, module) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(smoke, "import_tkinter", return_value=module), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            status = smoke.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_an_interpreter_without_tkinter_is_blocked_and_checks_nothing(self):
        def no_tkinter():
            raise ModuleNotFoundError("No module named 'tkinter'")

        with mock.patch.object(smoke, "import_tkinter", no_tkinter), \
                mock.patch.object(smoke, "default_database_state",
                                  side_effect=AssertionError("nothing may be inspected without a display")), \
                mock.patch.object(smoke.tempfile, "mkdtemp",
                                  side_effect=AssertionError("nothing may be created without a display")):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                status = smoke.main()

        output = stdout.getvalue()
        self.assertEqual(status, smoke.EXIT_BLOCKED)
        self.assertIn("RESULT: BLOCKED", output)
        self.assertNotIn("RESULT: PASS", output)
        self.assertNotIn("[ ok ]", output, "a check ran without a display, so its result means nothing")

    def test_a_display_that_cannot_be_reached_is_blocked_before_anything_is_created(self):
        def explode():
            raise RuntimeError("couldn't connect to display \":99\"")

        module = types.SimpleNamespace(TkVersion=8.6, Tk=explode)
        with mock.patch.object(smoke.tempfile, "mkdtemp",
                               side_effect=AssertionError("a temporary folder may not be created")):
            status, output, _ = self.run_main(module)

        self.assertEqual(status, smoke.EXIT_BLOCKED)
        self.assertIn("RESULT: BLOCKED", output)
        self.assertIn("couldn't connect to display", output)

    def test_a_display_that_breaks_for_another_reason_is_a_failure_not_a_blocked_run(self):
        def explode():
            raise RuntimeError("tkinter is built against a Tk this process cannot load")

        module = types.SimpleNamespace(TkVersion=8.6, Tk=explode)
        status, output, _ = self.run_main(module)

        self.assertEqual(status, smoke.EXIT_FAIL)
        self.assertIn("RESULT: FAIL", output)
        self.assertNotIn("RESULT: BLOCKED", output)


class ReportAndRequireTests(unittest.TestCase):
    def test_require_cannot_be_switched_off_by_a_python_flag(self):
        smoke.require(True, "this message must not be raised")
        with self.assertRaises(smoke.SmokeFailure):
            smoke.require(False, "the condition did not hold")

    def test_a_run_with_no_failures_passes_and_one_with_a_failure_does_not(self):
        passing = smoke.Results()
        with redirect_stdout(io.StringIO()):
            with passing.step("a check that holds"):
                pass
            status = passing.report("summary")
        self.assertEqual(status, smoke.EXIT_PASS)
        self.assertEqual(passing.passed, 1)

        failing = smoke.Results()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with failing.step("a check that does not hold"):
                raise smoke.SmokeFailure("the reason")
            status = failing.report("summary")
        self.assertEqual(status, smoke.EXIT_FAIL)
        self.assertIn("FAILED: a check that does not hold", stdout.getvalue())
        self.assertIn("the reason", stdout.getvalue())


class WidgetInspectionTests(unittest.TestCase):
    def test_tree_columns_reads_a_tuple_and_a_tcl_list_string(self):
        self.assertEqual(smoke.tree_columns(FakeTree(("a", "b"))), ("a", "b"))
        self.assertEqual(smoke.tree_columns(FakeTree("{a b}")), ("a", "b"))
        self.assertEqual(smoke.tree_columns(FakeTree("a b")), ("a", "b"))

    def test_buttons_are_found_wherever_they_are_nested(self):
        button = FakeWidget("TButton", text="Refresh")
        other = FakeWidget("Button", text="Export")
        deep = FakeWidget("TFrame", children=[FakeWidget("TLabel", text="label"), button])
        tab = FakeWidget("TFrame", children=[deep, other, FakeWidget("TEntry")])

        self.assertEqual(smoke.buttons_under(tab), [button, other])
        self.assertEqual([str(found.cget("text")) for found in smoke.buttons_under(tab)],
                         [smoke.REFRESH_BUTTON_TEXT, "Export"])

    def test_the_refresh_tabs_the_script_presses_are_tabs_the_window_has(self):
        for label in smoke.REFRESH_TAB_LABELS:
            with self.subTest(label=label):
                self.assertIn(label, smoke.EXPECTED_TABS)


class ExpectationsMatchTheWindowTests(unittest.TestCase):
    """The script's expectations must still describe the window it is pointed at.

    Read from the source rather than from a running window: this is the check that works on a machine with
    no display, and it is what keeps a renamed or reordered tab from only being discovered by the one CI
    runner that has one.
    """

    WINDOW = REPOSITORY_ROOT / "career_agent" / "desktop.py"

    def setUp(self):
        self.source = self.WINDOW.read_text(encoding="utf-8")

    def test_the_expected_tabs_are_the_tabs_the_window_adds_in_the_same_order(self):
        added = re.findall(r"self\.tabs\.add\(self\.\w+,\s*text=\"([^\"]+)\"\)", self.source)
        self.assertTrue(added, "no tabs were found in the window source; the pattern has gone stale")
        self.assertEqual(tuple(added), smoke.EXPECTED_TABS)

    def test_every_list_the_script_inspects_is_built_by_the_window(self):
        for name in smoke.EXPECTED_TREES:
            with self.subTest(name=name):
                self.assertRegex(self.source, rf"self\.{name} = ttk\.Treeview\(")

    def test_the_summary_variables_the_script_reads_exist_in_the_window(self):
        for name in smoke.EXPECTED_SUMMARY_VARIABLES:
            with self.subTest(name=name):
                self.assertRegex(self.source, rf"self\.{name} = tk\.StringVar\(")

    def test_the_script_is_the_entry_point_the_workflow_runs_and_gates_on(self):
        workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/desktop_smoke_test.py", workflow)
        self.assertIn("RESULT: BLOCKED", workflow)
        self.assertIn("RESULT: PASS", workflow)
        self.assertEqual(smoke.EXIT_PASS, 0)
        self.assertEqual(smoke.EXIT_BLOCKED, 2)


class FakeWidget:
    """Just enough of a Tk widget for the two inspection helpers."""

    def __init__(self, widget_class: str, *, text: str | None = None, children: list | None = None):
        self._class = widget_class
        self._options = {} if text is None else {"text": text}
        self._children = list(children or [])

    def winfo_class(self) -> str:
        return self._class

    def winfo_children(self) -> list:
        return self._children

    def cget(self, option: str):
        return self._options[option]


class FakeTree:
    def __init__(self, columns):
        self._columns = columns

    def cget(self, option: str):
        assert option == "columns", option
        return self._columns


if __name__ == "__main__":
    unittest.main()
