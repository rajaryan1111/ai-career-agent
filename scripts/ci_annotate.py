#!/usr/bin/env python3
"""Turn a failing step's recorded output into GitHub annotations.

Why this exists
---------------

A job that fails on a runner tells the checkout nothing: the step's output is written to the run's log,
which is served from a storage host that some networks (including the restricted one this project is
developed from) cannot reach, and what the API does return for a failed step is the line
``Process completed with exit code 1``. Without this script a red cross-platform leg is indistinguishable
from any other red leg, and the only way to see which test failed would be to read the run in a browser.

The workflow therefore redirects the output of its important steps into one notes file and runs this
script afterwards. It prints ``::error::``/``::warning::`` workflow commands, which the runner turns into
annotations on the job, and annotations *are* readable through the API - so the failing test names, the
smoke test's failed checks and the tail of each traceback stay available outside the browser.

Usage::

    python scripts/ci_annotate.py NOTES_FILE [--start 0] [--count 10] [--level error]
    python scripts/ci_annotate.py NOTES_FILE --tail 3

Only standard library, no network, no repository state: it reads a file and prints lines.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

#: The lines that begin a finding in the recorded output. ``unittest`` writes ``FAIL: <id>`` and
#: ``ERROR: <id>``; ``scripts/desktop_smoke_test.py`` writes ``FAILED: <check>``.
FINDING_START = re.compile(r"^(FAIL|ERROR): \S|^FAILED: \S")

#: Where the findings stop and the run's summary begins, in either format.
FINDING_END = re.compile(
    r"^(RESULT: |Ran \d+ tests? |OK\b|FAILED \(|\[ ok \] |\[skip\] |\[fail\] )"
)

#: How much of a finding's detail travels with it. Annotations have their own size limit and a traceback
#: is mostly framework frames; the exception line at the end is the part that names the defect.
DETAIL_LIMIT = 1200

#: GitHub un-escapes these in a command's message, so a message containing them has to escape them first.
_ESCAPES = (("%", "%25"), ("\r", "%0D"), ("\n", "%0A"))


def escape(message: str) -> str:
    """Escape a message for a workflow command, in the order GitHub un-escapes it."""
    for plain, encoded in _ESCAPES:
        message = message.replace(plain, encoded)
    return message


def findings(text: str) -> list[tuple[str, str]]:
    """Every failure in the recorded output, as ``(title, detail)`` pairs, in the order they appear."""
    found: list[tuple[str, str]] = []
    title: str | None = None
    detail: list[str] = []

    def flush() -> None:
        if title is not None:
            joined = "\n".join(detail).strip()[:DETAIL_LIMIT]
            found.append((title, joined))

    for line in text.splitlines():
        if FINDING_START.match(line):
            flush()
            title, detail = line.strip(), []
        elif title is not None:
            if FINDING_END.match(line):
                flush()
                title, detail = None, []
            else:
                detail.append(line)
    flush()
    return found


def annotation(level: str, title: str, message: str) -> str:
    """One workflow command, ready for the runner to read on stdout."""
    return f"::{level} title={escape(title)}::{escape(message)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("notes", type=Path, help="the file a step redirected its output into")
    parser.add_argument("--start", type=int, default=0, help="index of the first finding to report")
    parser.add_argument("--count", type=int, default=10, help="how many findings to report")
    parser.add_argument("--level", choices=("error", "warning", "notice"), default="error")
    parser.add_argument("--tail", type=int, default=0, help="report the last N non-empty lines instead")
    arguments = parser.parse_args(argv)

    try:
        text = arguments.notes.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        # The job may have failed before the step that writes notes ran. Nothing to say, and saying
        # nothing is not itself a failure: the step that broke has already failed the job.
        print(f"no notes at {arguments.notes}; nothing to annotate")
        return 0

    if arguments.tail:
        lines = [line for line in text.splitlines() if line.strip()][-arguments.tail:]
        if lines:
            print(annotation(arguments.level, "the run's last words", "\n".join(lines)))
        return 0

    selected = findings(text)[arguments.start:arguments.start + arguments.count]
    if not selected:
        print(f"no failure is recorded between findings {arguments.start} and "
              f"{arguments.start + arguments.count}")
        return 0
    for title, detail in selected:
        print(annotation(arguments.level, title, title))
        if detail and arguments.level != "notice":
            # A second annotation per finding, at the other level: the runner allows ten errors *and*
            # ten warnings per step, so using both keeps twice as many failures readable.
            other = "warning" if arguments.level == "error" else "error"
            print(annotation(other, f"detail: {title}", detail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
