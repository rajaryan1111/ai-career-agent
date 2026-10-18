#!/usr/bin/env python3
"""Run the repository full local verification suite with one command.

Every step runs in a subprocess so a failure cannot be masked by an earlier
import or a shared interpreter state. Only the failing step output is shown.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("unit tests", ("-m", "unittest", "discover", "-s", "tests")),
    ("compileall", ("-m", "compileall", "-q", "career_agent", "scripts", "tests")),
    ("CSV audit", ("scripts/audit_job_source_csv.py",)),
)


def run_check(name: str, arguments: tuple[str, ...]) -> bool:
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.monotonic() - started
    passed = result.returncode == 0
    status = "PASS" if passed else "FAIL"
    print("%4s  %-20s %5.1fs" % (status, name, elapsed))
    if not passed:
        print(result.stdout[-4000:], file=sys.stderr)
        print(result.stderr[-4000:], file=sys.stderr)
    return passed


def main() -> int:
    results = [run_check(name, arguments) for name, arguments in COMMANDS]
    failures = len(results) - sum(results)
    print()
    print("%d/%d checks passed" % (sum(results), len(results)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
