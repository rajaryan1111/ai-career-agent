"""The local-first promise, checked two ways: by reading the shipped code, and by running it blind.

The project states that its local alpha performs no network activity and never sends candidate data
anywhere. No unit test can observe every path, so this module establishes the two things that can be
established here and says plainly what remains unproven:

* nothing in the shipped code can open a connection or transmit a request - checked by reading the
  source rather than by trusting a docstring or a comment;
* the documented command-line backup and restore complete in an interpreter where creating a socket
  raises, which is what "works with networking switched off" means for those commands.

What this does not establish: that a future dependency, an operating-system helper or the desktop
toolkit cannot make a request, and it is no substitute for the manual checklist step that inspects the
running application. ``career_agent/urls.py`` is deliberately allowed to use ``urllib.parse`` and
``socket.inet_aton``: both only read a string the user typed, and neither resolves a name or connects.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
#: Only the code that ships. What the tests themselves do is not part of the promise.
SHIPPED_FOLDERS = ("career_agent", "scripts")

#: Calls that can put bytes on the wire, or ask a resolver to look something up.
_FORBIDDEN_CALLS = (
    r"socket\.socket\b", r"socket\.create_connection\b", r"socket\.getaddrinfo\b",
    r"socket\.gethostbyname\b", r"socket\.gethostbyname_ex\b", r"socket\.gethostbyaddr\b",
    r"socket\.socketpair\b", r"\burlopen\b", r"\burlretrieve\b",
    r"\bHTTPConnection\b", r"\bHTTPSConnection\b", r"webbrowser\.open\b",
    r"subprocess\.\w+\([^)]*\b(?:curl|wget)\b",
)
#: Modules whose whole purpose is remote communication, so importing one is intent, not detail.
_FORBIDDEN_IMPORTS = (
    "requests", "urllib.request", "http.client", "smtplib", "ftplib", "telnetlib",
    "poplib", "imaplib", "nntplib", "xmlrpc.client", "aiohttp", "httpx",
)

#: Copied into a child interpreter's ``PYTHONPATH`` so it cannot create a socket. The marker proves
#: the guard really installed: a silently absent guard would let this test pass while proving nothing.
_NO_NETWORK_MARKER = "[no-network]"
_NO_NETWORK_SITECUSTOMIZE = f'''\
"""{_NO_NETWORK_MARKER} guard: make socket creation impossible in this interpreter."""
import socket

_real_socket = socket.socket


class Blocked(OSError):
    """Raised instead of touching the network."""


class _NoSocket(_real_socket):
    def __init__(self, *args, **kwargs):
        raise Blocked("socket creation is blocked; this process must not need the network")


def _block(*args, **kwargs):
    raise Blocked("networking is blocked; this process must not need the network")


socket.socket = _NoSocket
socket.create_connection = _block
socket.getaddrinfo = _block
socket.gethostbyname = _block
'''

#: Run in the guarded child first, so the guard itself is verified before anything is concluded.
_NO_NETWORK_PROBE = (
    "import socket\n"
    "try:\n"
    "    socket.socket()\n"
    "except OSError as exc:\n"
    "    print('blocked:', exc)\n"
    "else:\n"
    "    print('NOT BLOCKED')\n"
)


def _imports_module(code: str, module: str) -> bool:
    """Whether one line of source imports ``module``, in any of the ways it can be written."""
    stripped = code.strip()
    if stripped.startswith("import "):
        names = [name.strip().split(" as ")[0] for name in stripped[len("import "):].split(",")]
        return any(name == module or name.startswith(module + ".") for name in names)
    match = re.match(r"from\s+([\w.]+)\s+import\s+(.+)", stripped)
    if not match:
        return False
    source, imported = match.group(1), [name.strip().split(" as ")[0] for name in match.group(2).split(",")]
    if source == module or source.startswith(module + "."):
        return True
    return any(f"{source}.{name}" == module for name in imported)  # ``from urllib import request``


def outbound_offenders(source: str) -> list[str]:
    """Every line of ``source`` that could transmit or resolve, as ``line: text`` entries."""
    offenders = []
    for number, line in enumerate(source.splitlines(), start=1):
        code = line.split("#", 1)[0]
        if not code.strip():
            continue
        if any(re.search(pattern, code) for pattern in _FORBIDDEN_CALLS):
            offenders.append(f"{number}: {line.strip()}")
        elif re.match(r"\s*(?:from|import)\s", code):
            if any(_imports_module(code, module) for module in _FORBIDDEN_IMPORTS):
                offenders.append(f"{number}: {line.strip()}")
    return offenders


class ShippedCodeCannotTransmitTests(unittest.TestCase):
    """Read the shipped modules and require that none of them can open a connection."""

    def shipped_sources(self):
        for folder in SHIPPED_FOLDERS:
            for path in sorted((REPOSITORY_ROOT / folder).rglob("*.py")):
                yield path, path.read_text(encoding="utf-8")

    def test_no_shipped_module_can_transmit_or_resolve(self):
        offenders = []
        for path, source in self.shipped_sources():
            for entry in outbound_offenders(source):
                offenders.append(f"{path.relative_to(REPOSITORY_ROOT)}:{entry}")

        self.assertEqual(
            offenders, [],
            "the shipped code must not be able to send data anywhere:\n" + "\n".join(offenders),
        )

    def test_the_scan_reaches_the_shipped_code_and_would_catch_a_violation(self):
        """A scan that silently matched nothing, or read nothing, would pass forever."""
        checked = [path for path, _source in self.shipped_sources()]

        self.assertIn(REPOSITORY_ROOT / "career_agent" / "desktop.py", checked)
        self.assertIn(REPOSITORY_ROOT / "scripts" / "correct_tracker_record.py", checked)
        self.assertGreaterEqual(len(checked), 10, f"only {len(checked)} files were scanned")

        for planted in (
            "import socket\nvalue = socket.socket()\n",
            "from urllib.request import urlopen\n",
            "from urllib import request\n",
            "import requests\n",
            "response = HTTPConnection('example.com')\n",
            "subprocess.run(['curl', 'https://example.com'])\n",
        ):
            with self.subTest(planted=planted.splitlines()[0]):
                self.assertTrue(outbound_offenders(planted), f"the scan missed: {planted!r}")

    def test_the_string_parsing_helpers_are_not_flagged_because_they_do_not_connect(self):
        """``urls.py`` may read a link the user typed; that must not read as making a request."""
        for source in (
            "from urllib.parse import urlsplit\n",
            "packed = socket.inet_aton(host)\n",
            "import ipaddress\n",
            "import subprocess\n",
        ):
            with self.subTest(source=source.strip()):
                self.assertEqual(outbound_offenders(source), [])


class WorksWithNetworkingSwitchedOffTests(unittest.TestCase):
    """Run the documented commands in an interpreter where creating a socket raises."""

    def guarded_environment(self, directory: str) -> dict:
        """A child-interpreter environment whose ``sitecustomize`` blocks socket creation."""
        (Path(directory) / "sitecustomize.py").write_text(_NO_NETWORK_SITECUSTOMIZE, encoding="utf-8")
        return dict(os.environ, PYTHONPATH=directory, PYTHONDONTWRITEBYTECODE="1")

    def run_guarded(self, environment: dict, arguments):
        """Run the CLI in the guarded interpreter, after proving the guard is installed."""
        probe = subprocess.run(
            [sys.executable, "-c", _NO_NETWORK_PROBE],
            capture_output=True, text=True, cwd=str(REPOSITORY_ROOT), env=environment, timeout=120,
        )
        self.assertIn(
            "blocked:", probe.stdout,
            "the no-network guard did not install, so this run would prove nothing:\n"
            f"{probe.stdout}{probe.stderr}",
        )
        return subprocess.run(
            [sys.executable, "-m", "career_agent", *arguments],
            capture_output=True, text=True, cwd=str(REPOSITORY_ROOT), env=environment, timeout=120,
        )

    def make_throwaway_database(self, database: Path):
        created = subprocess.run(
            [sys.executable, "-c", (
                "import sys\n"
                "sys.path.insert(0, '.')\n"
                "from career_agent import ApplicationTracker, Availability, JobListing\n"
                "from career_agent.store import CareerStore\n"
                "with CareerStore(sys.argv[1]) as store:\n"
                "    store.save_job(JobListing(listing_id='j1', source_id='manual',\n"
                "        source_name='Manual entry', source_listing_url='https://example.com/jobs/1',\n"
                "        employer_name='Example', role_title='AI Intern',\n"
                "        availability_status=Availability.OPEN))\n"
                "    store.save_tracker(ApplicationTracker('j1'))\n"
            ), str(database)],
            capture_output=True, text=True, cwd=str(REPOSITORY_ROOT), timeout=120,
        )
        self.assertEqual(created.returncode, 0, created.stderr)

    def test_backup_and_restore_work_with_socket_creation_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "throwaway.sqlite3"
            backup = Path(directory) / "backup.sqlite3"
            self.make_throwaway_database(database)
            with tempfile.TemporaryDirectory() as blocker:
                environment = self.guarded_environment(blocker)

                written = self.run_guarded(
                    environment, ["--database", str(database), "--backup-to", str(backup)]
                )
                self.assertEqual(written.returncode, 0,
                                 f"the backup needed the network:\n{written.stdout}{written.stderr}")
                self.assertIn("Backup written and verified", written.stdout)
                self.assertTrue(backup.exists(), "the backup file must exist")

                restored = self.run_guarded(
                    environment, ["--database", str(database), "--restore-from", str(backup), "--yes"]
                )
                self.assertEqual(restored.returncode, 0,
                                 f"the restore needed the network:\n{restored.stdout}{restored.stderr}")
                self.assertIn("Restored", restored.stdout)

    def test_the_draft_and_the_local_mock_need_no_network_either(self):
        """The whole draft-preview-record sequence, in an interpreter that cannot create a socket.

        This is the strongest evidence available here for the promise that an integration interface
        contacts nothing: not that the mock *chooses* not to, but that the process performing it has no
        socket at all, and the recorded operation still completes.
        """
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "throwaway.sqlite3"
            ledger = Path(directory) / "ledger.json"
            draft = Path(directory) / "draft.txt"
            created = subprocess.run(
                [sys.executable, "-c", (
                    "import sys\n"
                    "from datetime import date, timedelta\n"
                    "sys.path.insert(0, '.')\n"
                    "from career_agent import ApplicationTracker, Availability, JobListing\n"
                    "from career_agent.store import CareerStore\n"
                    "with CareerStore(sys.argv[1]) as store:\n"
                    "    store.save_job(JobListing(listing_id='j1', source_id='manual',\n"
                    "        source_name='Manual entry', source_listing_url='https://example.com/jobs/1',\n"
                    "        employer_name='Example', role_title='AI Intern',\n"
                    "        availability_status=Availability.OPEN))\n"
                    "    store.save_tracker(ApplicationTracker('j1').with_follow_up(\n"
                    "        date.today() + timedelta(days=2), note='follow up'))\n"
                ), str(database)],
                capture_output=True, text=True, cwd=str(REPOSITORY_ROOT), timeout=120,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            with tempfile.TemporaryDirectory() as blocker:
                environment = self.guarded_environment(blocker)

                status = self.run_guarded(environment, ["--database", str(database),
                                                        "--integration-status"])
                self.assertEqual(status.returncode, 0,
                                 f"the status report needed the network:\n{status.stdout}"
                                 f"{status.stderr}")
                self.assertIn("nothing is enabled", status.stdout)

                drafted = self.run_guarded(environment, [
                    "--database", str(database), "--draft-follow-up", "j1",
                    "--recipient", "hiring@example.invalid", "--save-draft", str(draft),
                    "--mock-ledger", str(ledger),
                ])
                self.assertEqual(drafted.returncode, 0,
                                 f"the draft needed the network:\n{drafted.stdout}{drafted.stderr}")
                self.assertIn("[completed]", drafted.stdout)
                self.assertIn("No email was sent", drafted.stdout)
                self.assertTrue(draft.exists(), "the local draft file must exist")
                self.assertTrue(ledger.exists(), "the local mock ledger must exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
