"""The commands the documentation tells people to run must be commands this program still has.

A README is the only part of a project that is guaranteed to be read by somebody who cannot read the code,
and a documented flag that no longer exists fails at the worst possible moment: after the person has decided
to trust the tool, in a terminal, with an argparse usage error. Nothing else in the suite compares prose to
the parser, so this does - the flags in `README.md` and in the manual checklist are looked up in the real
``--help`` output, and a flag that is not there fails the build.

Two limits are deliberate. Only *flag existence* is checked: whether the sentence around a flag describes its
behaviour accurately is a reading test, and the places where that matters most (exit statuses, what a command
refuses, what it writes) are asserted by the tests for the commands themselves. And the scan is proven to
find flags at all - a matcher that silently matched nothing would pass forever, so the expected count is
asserted and a planted unknown flag has to be reported.
"""
from __future__ import annotations

import io
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from career_agent import __main__ as cli

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

#: The documents a person is expected to follow, in the order they would read them.
DOCUMENTS = (
    REPOSITORY_ROOT / "README.md",
    REPOSITORY_ROOT / "research" / "local-alpha-manual-smoke-test-checklist-2026-10-14.md",
)

#: A line is only scanned when it names one of the two ways to start this program. Without that, a line
#: about another tool's flags (``pip install --upgrade``) would be read as a claim about ours.
_ENTRY_POINT = re.compile(r"(?:career-agent|python\s+-m\s+career_agent)\b")
_FLAG = re.compile(r"--[A-Za-z][A-Za-z0-9-]*")

#: How many flags the scan must find for its result to mean anything. The real number is higher; this is a
#: floor that a broken matcher or an emptied file cannot reach by accident.
MINIMUM_FLAGS_FOUND = 25


def documented_flags(text: str) -> dict[str, list[str]]:
    """Every ``--flag`` a document names on a line that starts this program, with those lines."""
    found: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not _ENTRY_POINT.search(line):
            continue
        for flag in _FLAG.findall(line):
            found.setdefault(flag, []).append(line.strip())
    return found


def parser_flags() -> set[str]:
    """Every option the real parser accepts, read from its own help output.

    The help text rather than the parser object, because the help text is what a person compares the README
    against: an option that exists but cannot be seen there is not documented either.
    """
    out = io.StringIO()
    with redirect_stdout(out):
        with unittest.TestCase().assertRaises(SystemExit):
            cli.parse_arguments(["--help"])
    return set(_FLAG.findall(out.getvalue()))


class DocumentedCommandTests(unittest.TestCase):
    """Every flag the documents use is a flag the program knows."""

    def test_the_help_output_lists_the_flags_a_person_would_look_for(self):
        known = parser_flags()

        for flag in ("--database", "--backup-to", "--restore-from", "--doctor", "--sources", "--analytics",
                     "--follow-ups", "--integration-status", "--preview-calendar-export",
                     "--draft-follow-up", "--record-follow-up", "--calendar-to", "--export-to",
                     "--import-from", "--worker", "--worker-status", "--seed-tasks", "--version"):
            with self.subTest(flag=flag):
                self.assertIn(flag, known)

    def test_every_flag_the_documents_use_exists(self):
        known = parser_flags()
        total = 0
        offenders: list[str] = []
        for document in DOCUMENTS:
            text = document.read_text(encoding="utf-8")
            found = documented_flags(text)
            total += len(found)
            for flag in sorted(found):
                if flag not in known:
                    offenders.append(f"{document.name}: {flag} ({found[flag][0]})")

        self.assertEqual(offenders, [], "documented commands that no longer exist:\n" + "\n".join(offenders))
        self.assertGreaterEqual(
            total, MINIMUM_FLAGS_FOUND,
            f"only {total} flags were found in the documents, so this check proved little",
        )

    def test_each_document_names_both_ways_to_start_the_program(self):
        for document in DOCUMENTS:
            with self.subTest(document=document.name):
                text = document.read_text(encoding="utf-8")
                self.assertIn("python -m career_agent", text)
                self.assertIn("career-agent", text)

    def test_the_scan_would_notice_a_flag_that_does_not_exist(self):
        """A matcher that found nothing, or a comparison that never ran, must not look like a pass."""
        planted = "python -m career_agent --a-flag-that-was-removed --analytics\n"
        known = parser_flags()

        found = documented_flags(planted)

        self.assertIn("--a-flag-that-was-removed", found)
        self.assertNotIn("--a-flag-that-was-removed", known)
        self.assertIn("--analytics", known)

    def test_a_line_about_another_tool_is_not_read_as_a_claim_about_this_one(self):
        """The scan is scoped to lines that start *this* program, so other tools' flags are not checked."""
        found = documented_flags("python -m pip install --upgrade build --quiet\n")

        self.assertEqual(found, {})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
