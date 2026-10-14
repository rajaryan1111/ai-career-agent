"""Resource-lifecycle regression tests for the SQLite connections this project opens.

Reported from macOS on 2026-10-14: ``python -m unittest discover -s tests`` passed but printed
``ResourceWarning: unclosed database``, pointing at ``tests/test_desktop_handlers.py:34`` — the body
of a ``StringVar`` stub. That line is where the garbage collector happened to run, not where the
connection was created. Measured on the same commit, four connections were never closed: three that a
restore handler opened when it gave the app a new store, and one read-only connection opened by a
test fixture with ``with sqlite3.connect(...)`` (which manages the transaction and never closes the
connection). This module keeps that class of leak visible on every supported Python, including the
versions that never emit the warning.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_agent.store import CareerStore

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
LEAK_WATCH_MODULE = "leak_watch_sitecustomize.py"
LEAK_WATCH_MARKER = "[leak-watch]"
#: The child run of the suite must not start another leak watch (it would recurse).
CHILD_MARKER_VARIABLE = "CAREER_AGENT_LEAK_WATCH_CHILD"
#: The whole suite opens hundreds of connections through the store, so a harness that silently failed
#: to install (and therefore counted nothing) is caught instead of passing as "no leaks".
MINIMUM_CONNECTIONS_IN_SUITE = 100

#: Built by concatenation so this module's own source does not contain the pattern it forbids.
_CONNECT_CALL = "sqlite3." + "connect("
_SOURCE_FOLDERS = ("career_agent", "scripts", "tests")


class FailedOpenConnectionTests(unittest.TestCase):
    """A store that cannot open must close the connection it opened before raising."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)

    def assertIsClosed(self, connection):
        """A closed connection refuses to work; an open one would satisfy the query."""
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def failed_open_with_recording(self, database_path, expected_error):
        """Open ``CareerStore(database_path)``, expecting ``expected_error``, and return the connections.

        The store is the only holder of its connection, and a failed construction never exposes it,
        so the connection has to be captured where it is created: this is the only way to check the
        lifecycle of a connection whose owner does not exist.
        """
        created = []
        real_connect = sqlite3.connect

        def recording_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            created.append(connection)
            return connection

        with mock.patch.object(sqlite3, "connect", recording_connect):
            with self.assertRaises(expected_error) as caught:
                CareerStore(database_path)
        self.addCleanup(self.close_all, created)  # a closing guard must never itself leak
        return created, caught.exception

    @staticmethod
    def close_all(connections):
        """Close every connection, idempotently, so a failing test leaves nothing open either."""
        for connection in connections:
            connection.close()

    def test_a_store_that_cannot_be_read_closes_its_connection(self):
        """An unreadable database used to leave its connection open until the collector ran."""
        target = Path(self._directory.name) / "not-a-database.sqlite3"
        target.write_text("plain text, not SQLite", encoding="utf-8")

        created, _error = self.failed_open_with_recording(target, sqlite3.DatabaseError)

        self.assertEqual(len(created), 1, "the store opens exactly one connection")
        self.assertIsClosed(created[0])

    def test_a_newer_schema_closes_its_connection(self):
        """The pre-existing refusal path keeps closing its connection, whatever order it runs in."""
        target = Path(self._directory.name) / "newer.sqlite3"
        with CareerStore(target) as store:
            store._connection.execute("PRAGMA user_version = 99")
            store._connection.commit()

        created, error = self.failed_open_with_recording(target, RuntimeError)

        self.assertIn("newer than supported", str(error))
        self.assertEqual(len(created), 1)
        self.assertIsClosed(created[0])

    def test_a_successful_open_hands_back_a_usable_connection(self):
        """The failure guard must not close the connection a successful open hands to the caller."""
        created = []
        real_connect = sqlite3.connect

        def recording_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            created.append(connection)
            return connection

        with mock.patch.object(sqlite3, "connect", recording_connect):
            store = CareerStore(Path(self._directory.name) / "fine.sqlite3")
        try:
            self.assertEqual(len(created), 1)
            self.assertEqual(store.list_jobs(), (), "the caller must receive a working connection")
        finally:
            store.close()
        self.assertIsClosed(created[0])


class ConnectionContextPatternTests(unittest.TestCase):
    """``with sqlite3.connect(...)`` reads as if it closed the connection; it does not."""

    def test_no_module_uses_a_connection_as_a_context_manager(self):
        offenders = []
        for folder in _SOURCE_FOLDERS:
            for path in sorted((REPOSITORY_ROOT / folder).rglob("*.py")):
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                    code = line.split("#", 1)[0]
                    if code.strip().startswith("with ") and _CONNECT_CALL in code:
                        offenders.append(f"{path.relative_to(REPOSITORY_ROOT)}:{number}: {line.strip()}")

        self.assertEqual(
            offenders, [],
            "a connection opened in a `with` statement is never closed by it; use try/finally",
        )


@unittest.skipIf(
    os.environ.get(CHILD_MARKER_VARIABLE),
    "this is the child run started by the leak watch below; it must not start another",
)
class SuiteConnectionLeakTests(unittest.TestCase):
    """Run the whole suite again in a child process that counts never-closed connections."""

    def test_the_suite_leaves_no_sqlite_connection_open(self):
        support = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as directory:
            shutil.copy(support / LEAK_WATCH_MODULE, Path(directory) / "sitecustomize.py")
            completed = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                cwd=REPOSITORY_ROOT,
                env=dict(
                    os.environ, PYTHONPATH=directory, PYTHONDONTWRITEBYTECODE="1",
                    **{CHILD_MARKER_VARIABLE: "1"},
                ),
                capture_output=True, text=True, timeout=900,
            )

        report = [line for line in completed.stderr.splitlines() if line.startswith(LEAK_WATCH_MARKER)]
        self.assertTrue(
            report, f"the leak watch did not run:\n{completed.stdout}\n{completed.stderr}"
        )
        self.assertEqual(
            completed.returncode, 0, f"the suite failed in the child run:\n{completed.stderr}"
        )
        created, never_closed = self.parse_counts(report[0])
        self.assertGreaterEqual(
            created, MINIMUM_CONNECTIONS_IN_SUITE,
            f"the leak watch counted too few connections to be meaningful:\n{report[0]}",
        )
        self.assertEqual(
            never_closed, 0,
            "connections were left to the garbage collector instead of being closed:\n"
            + "\n".join(report),
        )

    @staticmethod
    def parse_counts(line):
        """Read ``connections created: N; never closed: M`` from the watch's summary line."""
        words = line.split()
        return int(words[words.index("created:") + 1].rstrip(";")), int(words[words.index("closed:") + 1])


if __name__ == "__main__":
    unittest.main()
