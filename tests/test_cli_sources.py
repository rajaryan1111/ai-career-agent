"""Tests for ``--sources``: the report that says why nothing is being fetched.

The command exists because "no sources are enabled" is not a useful thing to tell somebody on its own -
it is indistinguishable from a broken installation. So what is tested here is that the report names the
gate, names every reviewed source with its decision and its evidence, and admits that no adapter exists,
while creating nothing and contacting nothing.
"""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import career_agent.__main__ as cli
from career_agent.adapters import default_registry
from career_agent.sources import SOURCE_DECISIONS, SOURCE_QUALITY_GATE_PASSED, enabled_discovery_sources


class SourcesCommandTests(unittest.TestCase):
    """A temporary folder holds the database path the command is given, so "created nothing" is provable."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([*arguments, "--database", str(self.database)])
        return code, out.getvalue(), err.getvalue()

    def test_the_report_says_the_gate_has_not_passed_and_no_source_may_run(self):
        code, output, error = self.run_cli("--sources")

        self.assertEqual(code, 0, error)
        self.assertIn("Source-quality gate: NOT passed", output)
        self.assertIn("Sources permitted to run discovery now: none.", output)
        self.assertIn("nothing was contacted and nothing was run", output)
        self.assertFalse(SOURCE_QUALITY_GATE_PASSED, "this report must not be written after a gate change")

    def test_every_reviewed_source_is_named_with_its_decision_and_its_evidence(self):
        _, output, _ = self.run_cli("--sources")

        for decision in SOURCE_DECISIONS:
            with self.subTest(source=decision.source_id):
                self.assertIn(decision.source_id, output)
                self.assertIn(decision.permission_state.value, output)
                self.assertIn(decision.evidence_ref, output)

    def test_the_report_admits_there_is_no_adapter_and_no_application_path(self):
        _, output, _ = self.run_cli("--sources")

        self.assertIn("Adapters built into this version: 0.", output)
        self.assertIn("the permissions are not", output)
        self.assertIn("applying for jobs here: not permitted", output)
        self.assertEqual(output.count("applying for jobs here: permitted"), 0)

    def test_the_report_matches_what_the_framework_actually_holds(self):
        """The printed counts come from the registry, not from a sentence somebody forgot to update."""
        registry = default_registry()

        self.assertEqual(registry.source_ids(), ())
        self.assertEqual(enabled_discovery_sources(), ())

    def test_asking_for_the_report_creates_no_database(self):
        self.run_cli("--sources")

        self.assertFalse(self.database.exists(), "a report about policy must not write to somebody's data")

    def test_the_report_is_exclusive_with_the_other_actions(self):
        quiet = io.StringIO()
        with contextlib.redirect_stderr(quiet), self.assertRaises(SystemExit) as caught:
            cli.parse_arguments(["--sources", "--worker-status"])

        self.assertEqual(caught.exception.code, 2, "argparse rejects the combination with a usage error")


if __name__ == "__main__":
    unittest.main()
