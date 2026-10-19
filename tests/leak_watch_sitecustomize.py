"""Report every SQLite connection a test leaves open, as CPython 3.13's ResourceWarning would.

This file is not imported by the suite directly: ``tests/test_resource_lifecycle.py`` copies it into
a temporary folder that a child interpreter gets on its ``PYTHONPATH``, so it is imported as
``sitecustomize`` before the test modules import ``sqlite3``. Every connection created in that child
is recorded with the test that created it, and the ones that were never closed are printed at exit.

Why this exists: the interpreters this project runs on differ. Python 3.11 — the oldest supported
version — does not emit an "unclosed database" ``ResourceWarning`` at all: an unclosed connection
collected by the garbage collector stays completely silent (measured). The warning appeared on
macOS/Python 3.13+, where it pointed at the line *where the collector happened to run* rather than
where the connection was created. Counting never-closed connections instead finds the same defect
on every supported Python, and names the test and creation site.
"""
from __future__ import annotations

import atexit
import sqlite3
import sys
import traceback
import unittest

#: Prefix of every line this watch prints, so the guard test can pick it out of the suite output.
MARKER = "[leak-watch]"

_real_connect = sqlite3.connect
_records: list[tuple[sqlite3.Connection, str, str | None]] = []
_current_test: list[str | None] = [None]
_real_run = unittest.TestCase.run


def _run(self, result=None):
    """Track which test is running, so a leaked connection can be attributed to it."""
    _current_test[0] = self.id()
    try:
        return _real_run(self, result)
    finally:
        _current_test[0] = None


def _connect(*args, **kwargs):
    connection = _real_connect(*args, **kwargs)
    _records.append((connection, "".join(traceback.format_stack()[:-1]), _current_test[0]))
    return connection


def _still_open(connection: sqlite3.Connection) -> bool:
    """Whether a tracked connection was never closed (an unusable-but-open one still counts)."""
    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return False  # closed: SQLite refuses to operate on it
    except Exception:
        return True  # open, but no longer usable (for example a file that is not a database)
    return True


def _report() -> None:
    open_connections = [record for record in _records if _still_open(record[0])]
    print(
        f"{MARKER} connections created: {len(_records)}; never closed: {len(open_connections)}",
        file=sys.stderr, flush=True,
    )
    for _connection, creation, test in open_connections:
        frames = [line.strip() for line in creation.splitlines() if 'File "' in line]
        print(f"{MARKER} never closed, created during {test}", file=sys.stderr, flush=True)
        for frame in frames[-3:]:
            print(f"{MARKER}   {frame}", file=sys.stderr, flush=True)


unittest.TestCase.run = _run
sqlite3.connect = _connect
atexit.register(_report)
