"""Tests for the distribution metadata: one version, no surprise dependencies, one entry point.

These read the source tree (``pyproject.toml``, the package's version literal, and the CI workflow).
They deliberately do not build or install anything: that is what the CI ``installed-package`` job
does, because a build is the only way to find out whether the metadata actually produces an
installable wheel. What is held here is the part that can regress silently - the literal setuptools
reads for the version, the declared dependency surface, the console-script target, and the claim that
the metadata's supported Python range matches what CI exercises.

``tomllib`` is standard from Python 3.11; on 3.10 the metadata-reading tests skip with the reason
stated, and the same properties are asserted by the CI job on every supported interpreter.
"""
from __future__ import annotations

import ast
import importlib
import importlib.metadata
import io
import re
import sys
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from career_agent import __version__
from career_agent import __main__ as cli

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the 3.10 CI leg
    tomllib = None

#: The pattern the workflow must not contain: comparing installed requirement metadata to a literal
#: string. How a requirement is spelled in the metadata depends on the build backend's version -
#: ``python -m build`` writes ``pypdf>=4.3; extra == "pdf"`` while an older setuptools wrote
#: ``pypdf (>=4.3) ; extra == 'pdf'`` - so a byte-exact comparison passes on one build and fails on
#: another while proving nothing about the property that matters. It failed in CI exactly that way.
_EXACT_REQUIREMENT_COMPARISON = re.compile(r"metadata\.requires\([^)\n]*\)[^\n]*==")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPOSITORY_ROOT / "pyproject.toml"
PACKAGE_INIT = REPOSITORY_ROOT / "career_agent" / "__init__.py"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "tests.yml"
DISTRIBUTION_NAME = "ai-career-agent"

#: The interpreter floor the metadata declares, and therefore the oldest CI leg that must exist.
OLDEST_SUPPORTED = "3.10"


def load_pyproject() -> dict:
    """The parsed ``pyproject.toml``, or skip the test where ``tomllib`` is unavailable."""
    if tomllib is None:
        raise unittest.SkipTest(
            "tomllib requires Python 3.11+; the CI installed-package job asserts the same metadata "
            "properties on the 3.10 leg"
        )
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


class VersionSourceTests(unittest.TestCase):
    """The version must come from one readable place, or the packaged build drifts from the app."""

    def test_the_version_literal_is_statically_readable_for_setuptools(self):
        """``version = {attr = "career_agent.__version__"}`` reads the source without importing it.

        A literal assignment is what makes that work. If the version ever became computed (from
        ``importlib.metadata``, a date, or a function), the build would either fail or silently record
        a different version than the application reports, so the assignment is pinned here.
        """
        tree = ast.parse(PACKAGE_INIT.read_text(encoding="utf-8"), filename=str(PACKAGE_INIT))
        assignments = [
            node for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id == "__version__"
        ]

        self.assertEqual(len(assignments), 1, "expected exactly one module-level __version__ assignment")
        value = assignments[0].value
        self.assertIsInstance(value, ast.Constant, "__version__ must be a literal for the build to read it")
        self.assertIsInstance(value.value, str)
        self.assertEqual(value.value, __version__, "the literal and the imported version must be the same string")
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+", "the version should stay a plain release number")

    def test_the_metadata_takes_the_version_from_that_attribute(self):
        data = load_pyproject()

        self.assertEqual(data["project"]["dynamic"], ["version"])
        self.assertNotIn("version", data["project"], "the version must not also be hard-coded here")
        self.assertEqual(data["tool"]["setuptools"]["dynamic"]["version"], {"attr": "career_agent.__version__"})

    def test_an_installed_distribution_reports_the_same_version_as_the_source(self):
        """Runs only where the project is actually installed; in a source checkout there is no metadata."""
        try:
            installed = importlib.metadata.version(DISTRIBUTION_NAME)
        except importlib.metadata.PackageNotFoundError:
            self.skipTest(f"{DISTRIBUTION_NAME} is not installed in this interpreter (source checkout)")

        self.assertEqual(installed, __version__)


class DependencySurfaceTests(unittest.TestCase):
    """The application runs on the standard library; the one optional capability is declared."""

    def test_no_required_runtime_dependency_is_declared(self):
        data = load_pyproject()

        self.assertEqual(
            data["project"]["dependencies"], [],
            "a required dependency would change what an install pulls in; add it deliberately, with a reason",
        )

    def test_the_pdf_capability_is_declared_as_an_optional_extra(self):
        data = load_pyproject()
        extras = data["project"]["optional-dependencies"]

        self.assertIn("pdf", extras)
        requirements = extras["pdf"]
        self.assertEqual(len(requirements), 1, "one library, one requirement")
        self.assertTrue(requirements[0].startswith("pypdf>="), requirements[0])
        floor = requirements[0].split(">=")[1]
        self.assertRegex(floor, r"^\d+(\.\d+)*$", "the floor must be a release number the suite was run against")

    def test_the_optional_pdf_library_is_imported_lazily(self):
        """Declaring an optional dependency is only honest if the application runs without it."""
        from career_agent import resume

        try:
            import pypdf  # noqa: F401
        except ModuleNotFoundError:
            installed = False
        else:
            installed = True

        self.assertEqual(resume.PDF_SUPPORT_AVAILABLE, installed,
                         "the module must import either way, and report what is actually available")


class EntryPointTests(unittest.TestCase):
    """``python -m career_agent`` and the installed ``career-agent`` must be the same program."""

    def test_the_console_script_target_exists_and_is_callable(self):
        data = load_pyproject()
        target = data["project"]["scripts"]["career-agent"]
        module_name, _, attribute = target.partition(":")

        module = importlib.import_module(module_name)
        self.assertTrue(callable(getattr(module, attribute)), f"{target} must name a callable")

    def test_the_console_script_is_the_module_entry_point_the_dash_m_form_runs(self):
        data = load_pyproject()
        target = data["project"]["scripts"]["career-agent"]

        self.assertEqual(target, "career_agent.__main__:main")
        self.assertTrue(callable(cli.main), "``python -m career_agent`` runs exactly this callable")

    def test_the_usage_line_names_how_the_program_was_invoked(self):
        for argv0, expected in (
            ("/usr/local/bin/career-agent", "career-agent"),
            ("/usr/lib/python3.12/unittest/__main__.py", "python -m career_agent"),
            ("/tmp/some-runner", "python -m career_agent"),
        ):
            with self.subTest(argv0=argv0):
                with mock.patch.object(sys, "argv", [argv0]):
                    self.assertEqual(cli._program_name(), expected)

    def test_both_spellings_print_help_that_names_themselves_and_the_same_actions(self):
        for argv0, expected_name in (
            ("career-agent", "career-agent"),
            ("/usr/lib/python3.12/unittest/__main__.py", "python -m career_agent"),
        ):
            with self.subTest(argv0=argv0), mock.patch.object(sys, "argv", [argv0]):
                out = io.StringIO()
                with redirect_stdout(out), self.assertRaises(SystemExit) as exited:
                    cli.parse_arguments(["--help"])
                text = out.getvalue()

            self.assertEqual(exited.exception.code, 0)
            self.assertIn(expected_name, text, "the usage line must name how the program was invoked")
            for action in ("--database", "--backup-to", "--restore-from", "--yes", "--version"):
                self.assertIn(action, text)


class SupportedEnvironmentTests(unittest.TestCase):
    """What the metadata claims must match what is actually tested."""

    def test_the_supported_python_floor_is_declared_and_covered_by_ci(self):
        data = load_pyproject()

        self.assertEqual(data["project"]["requires-python"], f">={OLDEST_SUPPORTED}")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f'"{OLDEST_SUPPORTED}"', workflow, "CI must run the oldest interpreter the metadata allows")
        self.assertIsNotNone(re.search(r"python-version:\s*\[", workflow), "the CI matrix must stay explicit")

    def test_the_doctor_checks_the_same_interpreter_floor_the_metadata_declares(self):
        """``--doctor`` repeats the floor so it can check it without packaging metadata; keep them equal."""
        self.assertEqual(
            ".".join(str(part) for part in cli.MINIMUM_PYTHON), OLDEST_SUPPORTED,
            "--doctor would warn about an interpreter the package says it supports (or stay silent about one it does not)",
        )

    def test_the_installed_package_holds_only_the_application_package(self):
        data = load_pyproject()

        self.assertEqual(data["tool"]["setuptools"]["packages"], ["career_agent"])
        for excluded in ("tests", "scripts"):
            self.assertNotIn(excluded, data["tool"]["setuptools"]["packages"])


class ContinuousIntegrationTests(unittest.TestCase):
    """What the workflow claims to verify has to be verifiable in the workflow itself."""

    def test_the_workflow_never_compares_requirement_metadata_to_a_literal_string(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        match = _EXACT_REQUIREMENT_COMPARISON.search(text)

        self.assertIsNone(
            match,
            f"normalise before comparing (the build backend decides the spelling): {match.group(0) if match else ''}",
        )

    def test_that_check_catches_the_form_it_refuses(self):
        """Non-vacuous: the regression that reached CI is caught, and the fixed form is not flagged."""
        regressed = 'assert metadata.requires("ai-career-agent") == ["pypdf (>=4.3) ; extra == \'pdf\'"]'
        fixed = (
            'requirements = metadata.requires("ai-career-agent") or []\n'
            'compact = requirements[0].replace(" ", "")\n'
            'assert len(requirements) == 1'
        )

        self.assertIsNotNone(_EXACT_REQUIREMENT_COMPARISON.search(regressed))
        self.assertIsNone(_EXACT_REQUIREMENT_COMPARISON.search(fixed))

    def test_every_embedded_workflow_script_is_valid_python(self):
        """A broken inline script fails the whole job; catch it here instead of on the runner."""
        text = WORKFLOW.read_text(encoding="utf-8")
        blocks = re.findall(r"python - <<'PY'\n(.*?)\n\s*PY", text, re.DOTALL)

        self.assertGreaterEqual(len(blocks), 3, "the installed-package job should still exercise real code")
        for index, block in enumerate(blocks, start=1):
            with self.subTest(block=index):
                ast.parse(textwrap.dedent(block))

    def test_the_installed_package_job_builds_installs_and_runs_the_command(self):
        """The README claims a build and install is verified in CI; this holds that claim to a job."""
        text = WORKFLOW.read_text(encoding="utf-8")
        marker = "installed-package:"
        self.assertIn(marker, text)
        job = text[text.index(marker):]

        for required in (
            "python -m build --wheel",
            "pip install --quiet dist/*.whl",
            "career-agent --version",
            "career-agent --doctor",
            "career-agent --database",
        ):
            self.assertIn(required, job, f"the installed-package job should run: {required}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
