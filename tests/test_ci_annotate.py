"""Tests for scripts/ci_annotate.py, the small bridge between a failing step and the API.

The property worth pinning is that a failure recorded in a notes file comes back as an annotation that
still says *which* test failed and why: this project reads CI through the API, and an annotation that lost
the failing test's name - or that arrived with its newlines unescaped and was therefore truncated at the
first line - would hide exactly the evidence the script exists to carry.
"""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import ci_annotate  # noqa: E402

UNITTEST_OUTPUT = """\
....F.E...
======================================================================
FAIL: test_a_thing (tests.test_example.Case.test_a_thing)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/runner/work/tests/test_example.py", line 12, in test_a_thing
    self.assertEqual("a", "b")
AssertionError: 'a' != 'b'
- a
+ b

======================================================================
ERROR: test_another (tests.test_example.Case.test_another)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/runner/work/tests/test_example.py", line 20, in test_another
    raise RuntimeError("50% of the time")
RuntimeError: 50% of the time

----------------------------------------------------------------------
Ran 42 tests in 1.234s

FAILED (failures=1, errors=1)
"""

SMOKE_OUTPUT = """\
AI Career Agent - desktop smoke test
python 3.12.3 on linux
tkinter: Tk 8.6, from /usr/lib/python3.12/tkinter/__init__.py
[ ok ] a window can be built
[ ok ] the window is titled AI Career Agent - Local Workspace
[fail] every tab was built
FAILED: every tab was built
Traceback (most recent call last):
  File "scripts/desktop_smoke_test.py", line 300, in main
    require(tab.winfo_exists(), "the tab was destroyed")
AssertionError: the tab was destroyed

RESULT: FAIL — 2 checks passed, 1 failed. The window is not what this script expects.
"""


class AnnotationFormatTests(unittest.TestCase):
    def test_a_percent_and_a_newline_survive_the_round_trip(self):
        line = ci_annotate.annotation("error", "50%", "first\nsecond")
        self.assertNotIn("\n", line)
        self.assertIn("50%25", line)
        self.assertIn("%0A", line)
        self.assertTrue(line.startswith("::error title="))

    def test_the_level_is_carried_into_the_command(self):
        for level in ("error", "warning", "notice"):
            with self.subTest(level=level):
                self.assertTrue(ci_annotate.annotation(level, "t", "m").startswith(f"::{level} "))


class FindingTests(unittest.TestCase):
    def test_a_unittest_failure_carries_its_name_and_the_end_of_its_traceback(self):
        found = ci_annotate.findings(UNITTEST_OUTPUT)
        self.assertEqual([title.split(" ")[0] for title, _ in found], ["FAIL:", "ERROR:"])
        self.assertIn("tests.test_example.Case.test_a_thing", found[0][0])
        self.assertIn("AssertionError: 'a' != 'b'", found[0][1])
        self.assertIn("RuntimeError: 50% of the time", found[1][1])
        for _, detail in found:
            self.assertNotIn("Ran 42 tests", detail, "the run's summary is not part of a finding")

    def test_a_smoke_failure_is_one_finding_that_names_the_failed_check(self):
        found = ci_annotate.findings(SMOKE_OUTPUT)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], "FAILED: every tab was built")
        self.assertIn("the tab was destroyed", found[0][1])
        self.assertNotIn("RESULT:", found[0][1])

    def test_output_without_a_failure_yields_nothing(self):
        self.assertEqual(ci_annotate.findings("....\nRan 4 tests in 0.1s\n\nOK\n"), [])

    def test_a_very_long_traceback_is_cut_rather_than_sent_whole(self):
        text = "FAIL: test_big (tests.test_example.Case.test_big)\n" + ("x" * 5000) + "\n"
        found = ci_annotate.findings(text)
        self.assertEqual(len(found), 1)
        self.assertLessEqual(len(found[0][1]), ci_annotate.DETAIL_LIMIT)


class MainTests(unittest.TestCase):
    def run_main(self, notes: str | None, argv: list[str]) -> tuple[int, str]:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "notes.txt"
            if notes is not None:
                path.write_text(notes, encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                status = ci_annotate.main([str(path), *argv])
        return status, stdout.getvalue()

    def test_a_missing_notes_file_is_not_itself_a_failure(self):
        status, output = self.run_main(None, [])
        self.assertEqual(status, 0)
        self.assertIn("nothing to annotate", output)
        self.assertNotIn("::", output)

    def test_the_default_slice_reports_every_finding_with_two_annotations_each(self):
        status, output = self.run_main(UNITTEST_OUTPUT, [])
        lines = output.splitlines()
        self.assertEqual(status, 0)
        self.assertEqual(sum(line.startswith("::error ") for line in lines), 2)
        self.assertEqual(sum(line.startswith("::warning title=detail: ") for line in lines), 2)
        self.assertIn("tests.test_example.Case.test_another", output)

    def test_a_slice_past_the_end_says_so_instead_of_inventing_a_finding(self):
        status, output = self.run_main(UNITTEST_OUTPUT, ["--start", "5", "--count", "10"])
        self.assertEqual(status, 0)
        self.assertNotIn("::", output)
        self.assertIn("no failure is recorded", output)

    def test_the_tail_mode_reports_the_last_lines_at_the_requested_level(self):
        status, output = self.run_main(UNITTEST_OUTPUT, ["--tail", "2", "--level", "notice"])
        self.assertEqual(status, 0)
        self.assertEqual(len(output.splitlines()), 1)
        self.assertTrue(output.startswith("::notice "))
        self.assertIn("FAILED (failures=1, errors=1)", output)

    def test_a_warning_level_run_still_pairs_each_finding_with_its_detail(self):
        status, output = self.run_main(SMOKE_OUTPUT, ["--level", "warning"])
        self.assertEqual(status, 0)
        self.assertIn("::warning title=FAILED: every tab was built::", output)
        self.assertIn("::error title=detail: FAILED: every tab was built::", output)


if __name__ == "__main__":
    unittest.main()
