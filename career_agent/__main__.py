"""Command-line entry point: open the desktop app, or back up and restore the local database.

    python -m career_agent                            # open the desktop app
    python -m career_agent --version                  # print the version this checkout runs
    python -m career_agent --backup-to PATH           # write a verified, owner-only backup
    python -m career_agent --restore-from PATH        # validate, confirm, then replace the database
    python -m career_agent --doctor                   # report where the data is and whether it is usable
    python -m career_agent --worker-status            # what is scheduled, and what happened last
    python -m career_agent --worker                   # run the local scheduler until stopped
    python -m career_agent --seed-tasks               # add the default tasks to this database

The two database commands exist because the situation that needs a restore most — a database the app
cannot read — is also the situation in which the window cannot be opened. They import no GUI toolkit,
so they work in a headless session, and they use the same tested :mod:`career_agent.backup` module as
the desktop buttons: one implementation, two front ends. ``--version`` and the start-up failure report
are likewise Tk-free, so they work when the window cannot open.

``--doctor`` answers "where does this app keep my data, and can it read it?" without opening the
window: it resolves the same settings the app uses, reports the version and the supported interpreter,
and reads the database read-only (or says it does not exist yet). It creates nothing and changes
nothing, so it is safe to run when something is already wrong.

``--worker`` runs the scheduled tasks recorded in the database (:mod:`career_agent.worker`) and
``--worker-status`` reports them without running anything: what holds the lease, what is in progress,
what is next, and how the recent attempts ended. Both import no GUI toolkit. The worker runs in the
foreground of whatever starts it - this is a local scheduler, and it stops when the process stops or
the window is closed with Ctrl-C; nothing here runs after the computer is switched off, and the command
says so rather than implying otherwise.

``--seed-tasks`` writes the default schedule (00:00 and 12:00 Asia/Kolkata for discovery, 23:30 for a
database backup) into a database that does not already have those tasks, and leaves any task that
exists exactly as the person configured it.

``--integration-status``, ``--preview-calendar-export``, ``--draft-follow-up`` and ``--record-follow-up``
are the email and calendar side of the same promise: a draft is not a send, a preview is not an action, and
no integration is enabled in this build. ``--draft-follow-up`` writes a message from an application's own
recorded context and prints it in full; ``--preview-calendar-export`` says which events the local ``.ics``
export would contain before anything is written. Both are read-only, and the only thing that can be
performed by any of them is through an explicitly named local mock ledger, which contacts nothing.

Nothing here touches the network. Restoring replaces candidate data, so it always requires an explicit
confirmation: the file must be named and confirmed interactively, or ``--yes`` must be passed.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import date, datetime, time, timezone
import platform
import sys
from pathlib import Path

from . import __version__
from .backup import BackupError, DatabaseInUse, create_backup, restore_backup, suggested_backup_name, validate_app_database
from .config import database_path_for_run, describe_settings, resolve_settings
from .diagnostics import describe_startup_failure, diagnostic_log_path, record_startup_failure
from .event_log import LOG_FILE_NAME, MAX_LOG_BYTES, log_path, read_lines
from .handlers import default_registry, describe_default_handlers, seed_default_tasks
from .core import EmploymentType, months_covered_by
from .desktop_logic import ACTIVITY_DATE_PATTERN
from .store import (
    SCHEMA_VERSION, CareerStore, PrivateWriteError, StoredRecordError, TrackerStatusError,
    unreadable_stored_records, write_private_text_file,
)
from . import analytics, importer, preparation
from . import integrations
from .followups import calendar_file_name, reminder_for, reminders, summary, to_calendar
from .tasks import WorkerLeaseHeld
from .worker import Worker, WorkerSettings, worker_status
# Imported as a namespace: ``default_registry`` here is the *handler* registry the worker runs, and the
# adapter framework has a function of the same name. Aliasing keeps the two from being confused at the
# call site - a worker that resolved the wrong registry would silently register no handlers.
from . import adapters as adapter_framework
from .sources import (
    SOURCE_DECISIONS, SOURCE_QUALITY_GATE_PASSED, discovery_gate, enabled_discovery_sources,
    submission_gate,
)

EXIT_OK = 0
#: ``--doctor`` uses this so it can be wired into a launcher or a script: a found problem is a real
#: failure, and anything else would hide it. It is deliberately distinct from a refusal (2).
EXIT_PROBLEM_FOUND = 1
EXIT_REFUSED = 2
EXIT_UNEXPECTED = 3
#: ``--worker`` exits with this when another worker already holds the lease for this database: nothing
#: is wrong with the request, but this process must not run the schedule, and saying so with a distinct
#: status lets a launcher (a service file, a task runner) tell that apart from a crash.
EXIT_ALREADY_RUNNING = 4

#: How the worker identifies itself in the lease and in the run history. A person can pass their own
#: with ``--worker-id``; the default names the machine so two machines do not look like one worker.
DEFAULT_WORKER_ID = f"{platform.node() or 'this-machine'}-cli"

#: The oldest interpreter ``pyproject.toml`` supports, repeated here so ``--doctor`` can check it
#: without reading packaging metadata at run time.
MINIMUM_PYTHON = (3, 10)

#: The name shown in ``--help`` and usage errors when this is run as a console script rather than as
#: a module. Both spellings are documented in the README, and the usage line should name the one the
#: person actually typed.
CONSOLE_SCRIPT_NAME = "career-agent"


def _program_name() -> str:
    """What to call this program in usage text.

    ``python -m career_agent`` reports ``__main__.py`` as ``sys.argv[0]``, which is not something to
    show anyone; the installed console script reports its own name. Anything else (a test runner, an
    embedding application) keeps the module form, so the usage line stays reproducible.
    """
    invoked = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else ""
    return CONSOLE_SCRIPT_NAME if invoked == CONSOLE_SCRIPT_NAME else "python -m career_agent"


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=_program_name(),
        description="Local-first career workspace. With no action, the desktop window opens.",
        epilog=(
            "Backups are verified before success is reported and are never overwritten. Restoring "
            "validates the chosen file, copies the current database aside first, and reopens the "
            "result to verify it. Candidate data never leaves the local machine."
        ),
    )
    parser.add_argument(
        "--database", metavar="PATH",
        help="Database to use (default: the per-user application-data folder).",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--backup-to", metavar="PATH",
        help=f"Write a verified backup to PATH (suggested name: {suggested_backup_name()}).",
    )
    actions.add_argument(
        "--restore-from", metavar="PATH",
        help="Replace the local database with this backup after validating it.",
    )
    actions.add_argument(
        "--doctor", action="store_true",
        help="Report the version, the data location and whether the database can be read, then exit.",
    )
    actions.add_argument(
        "--worker-status", action="store_true",
        help="Report the schedule, the lease and the recent attempts, then exit (changes nothing).",
    )
    actions.add_argument(
        "--worker", action="store_true",
        help="Run this database's scheduled tasks in the foreground until stopped (Ctrl-C).",
    )
    actions.add_argument(
        "--seed-tasks", action="store_true",
        help="Add the default scheduled tasks to this database, leaving existing tasks untouched.",
    )
    actions.add_argument(
        "--sources", action="store_true",
        help="Report each job source's permission state, adapter and health, then exit (changes nothing).",
    )
    actions.add_argument(
        "--follow-ups", action="store_true",
        help="List the applications whose follow-up day has arrived or is coming, then exit.",
    )
    actions.add_argument(
        "--next-actions", action="store_true",
        help="List what needs doing now: due follow-ups, rounds ahead and open preparation items.",
    )
    actions.add_argument(
        "--interviews", action="store_true",
        help="List the interview rounds recorded for your applications, next one first, then exit.",
    )
    actions.add_argument(
        "--analytics", action="store_true",
        help="Add up what the records hold: counts, rates with their denominators, then exit (read-only).",
    )
    actions.add_argument(
        "--history", action="store_true",
        help="List your recorded employment and education, most recent first, then exit (read-only).",
    )
    actions.add_argument(
        "--add-role", metavar="EMPLOYER",
        help="Add an employment record for EMPLOYER (needs --title and --start; see --current, --end).",
    )
    actions.add_argument(
        "--add-study", metavar="INSTITUTION",
        help="Add an education record for INSTITUTION (needs --qualification; dates are optional).",
    )
    actions.add_argument(
        "--integration-status", action="store_true",
        help="Report which email and calendar integrations exist and why none is enabled, then exit.",
    )
    actions.add_argument(
        "--preview-calendar-export", action="store_true",
        help="Show what --calendar-to PATH would write, without writing it (read-only).",
    )
    actions.add_argument(
        "--draft-follow-up", metavar="LISTING_ID",
        help="Write a follow-up email draft for LISTING_ID and print it; nothing is sent.",
    )
    actions.add_argument(
        "--record-follow-up", metavar="LISTING_ID",
        help="Ask to record a calendar event for LISTING_ID's follow-up day; disabled unless a mock ledger is named.",
    )
    actions.add_argument(
        "--calendar-to", metavar="PATH",
        help="Write follow-up reminders to a calendar file (.ics) at PATH, for your own calendar.",
    )
    actions.add_argument(
        "--export-to", metavar="PATH",
        help="Write this database's profile, listings and history to a JSON file at PATH.",
    )
    actions.add_argument(
        "--import-from", metavar="PATH",
        help="Show what importing a JSON export at PATH would do (add --yes to apply it).",
    )
    parser.add_argument(
        "--recipient", metavar="ADDRESS", default=None,
        help="The address to put on a --draft-follow-up; never guessed, and optional (the draft says so).",
    )
    parser.add_argument(
        "--save-draft", metavar="PATH", default=None,
        help="Also write the --draft-follow-up to a local file at PATH (refused if the file exists).",
    )
    parser.add_argument(
        "--mock-ledger", metavar="PATH", default=None,
        help="Perform --draft-follow-up or --record-follow-up through the local mock, recording it at PATH.",
    )
    parser.add_argument(
        "--at", metavar="HH:MM", default=None,
        help="Start time for --record-follow-up. Needs --minutes and --timezone; without it the event is all-day.",
    )
    parser.add_argument(
        "--minutes", metavar="MINUTES", default=None,
        help="How long the --record-follow-up event is expected to take.",
    )
    parser.add_argument(
        "--timezone", metavar="NAME", default=None,
        help="The IANA timezone the --record-follow-up start time is in, for example Asia/Kolkata.",
    )
    parser.add_argument(
        "--title", metavar="TITLE", default=None,
        help="Job title for --add-role.",
    )
    parser.add_argument(
        "--start", metavar="YYYY-MM-DD", default=None,
        help="Start date for --add-role, or the optional start of a qualification for --add-study.",
    )
    parser.add_argument(
        "--end", metavar="YYYY-MM-DD", default=None,
        help="End date for --add-role (omit while the role is current).",
    )
    parser.add_argument(
        "--current", action="store_true",
        help="Mark the record added by --add-role as your current role.",
    )
    parser.add_argument(
        "--qualification", metavar="QUALIFICATION", default=None,
        help="Qualification for --add-study, for example B.Tech or M.Sc.",
    )
    parser.add_argument(
        "--discipline", metavar="SUBJECT", default=None,
        help="Optional subject or discipline for --add-study.",
    )
    parser.add_argument(
        "--completed", metavar="YYYY-MM-DD", default=None,
        help="Completion date for --add-study (omit while the study is ongoing).",
    )
    parser.add_argument(
        "--ongoing", action="store_true",
        help="Mark the qualification added by --add-study as still being studied.",
    )
    parser.add_argument(
        "--employment-type", metavar="TYPE", default="unknown",
        choices=[kind.value for kind in EmploymentType],
        help="Employment type for --add-role (default: unknown, which claims nothing).",
    )
    parser.add_argument(
        "--summary", metavar="TEXT", default=None,
        help="Optional note about what you did in the role added by --add-role.",
    )
    parser.add_argument(
        "--worker-id", metavar="NAME", default=None,
        help=f"Name this worker in the lease and run history (default: {DEFAULT_WORKER_ID}).",
    )
    parser.add_argument(
        "--poll-seconds", type=float, default=None, metavar="SECONDS",
        help="How often the worker looks for due work (default: every 15 seconds).",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Confirm the restore without the interactive prompt (needed when input is not a terminal).",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {__version__} (database schema version {SCHEMA_VERSION})",
        help="Print the version of this checkout and exit.",
    )
    return parser.parse_args(argv)


def _database_path(args: argparse.Namespace) -> Path:
    """The database these commands act on, resolved by the same rule the window uses.

    ``--database`` wins, then ``CAREER_AGENT_DATABASE``, then the per-user default; that way a backup
    or a restore always names the file the app itself would open.
    """
    return database_path_for_run(args.database)


def _nearest_existing(path: Path) -> Path | None:
    """The closest existing ancestor of ``path``, used to explain a folder that is not there yet."""
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return None


#: The closing sentence of every refusal to read a database, so one answer is worded one way whichever
#: command reaches the failure first.
_REFUSAL_ADVICE = ("Nothing was changed or repaired. `python -m career_agent --doctor` reports which record "
                   "it is, and a verified backup taken earlier can be restored over it.")

#: SQLite's own words for "this database cannot be written", as opposed to "this database cannot be read".
#: The two send a person somewhere different: a file that cannot be read is damaged or is not a database,
#: while a file that cannot be written is intact and the *location* refused the change - a read-only file
#: or folder, a folder that is not there, or another process holding the database. Measured on 2026-10-15
#: against a valid database at mode 444, inside a folder the account could not write to, and on a
#: read-only filesystem: all three produced a write error, and all three were described as a read failure.
_WRITE_FAILURE_MARKERS = (
    "attempt to write a readonly database",
    "unable to open database file",
    "database is locked",
    "read-only file system",
)


def looks_like_a_write_failure(message: str) -> bool:
    """Whether SQLite's message means the database could not be *written*, rather than read.

    Deliberately a short list of its own words rather than anything cleverer: the messages this
    distinguishes are the ones observed on this project's own failure paths, and a read failure - a file
    that is not a database, a malformed image, a table that is not there - must keep the read sentence.
    """
    lowered = message.lower()
    return any(marker in lowered for marker in _WRITE_FAILURE_MARKERS)


def _refuse_database_problem(exc: Exception | None = None, *, problems: tuple[str, ...] = ()) -> int:
    """Report a database this build could not read or could not write, having written nothing.

    Every read-only report goes through this rather than letting the failure reach the top-level handler,
    which would describe a damaged row as "COULD NOT START" and exit with an unexpected-failure status.
    Three different failures arrive here and they are not described the same way: a *stored record* this
    version cannot decode, a *file* that cannot be read as a database at all (a text file with the wrong
    name, a truncated download), and a database that is intact but cannot be *written* (a read-only file,
    a read-only folder, another process holding it). Saying "this database holds a record this version
    cannot read" about a file that holds no records would send somebody looking for a row that does not
    exist, and saying "could not be read" about a write - with the advice to restore a backup over the
    file - sends them looking for damage that is not there and recommends a restore that would fail the
    same way, so each one says what actually happened. In every case the message names what failed - never
    a record's contents - says nothing was changed or repaired, and points at the doctor, which reads the
    same file without writing and gives its own reason.

    ``problems`` is the other way in: the sentences the read-only sweep found before a command that *writes*
    touched anything. A command that plans to write has to know this first, because applying part of its work
    and failing halfway would leave a half-written database behind a message saying nothing was written.
    """
    if problems:
        print("REFUSED: this database holds a record this version cannot read:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(_REFUSAL_ADVICE, file=sys.stderr)
        return EXIT_REFUSED
    if isinstance(exc, sqlite3.Error) and looks_like_a_write_failure(str(exc)):
        print(f"REFUSED: this database could not be written to, so nothing was changed: {exc}",
              file=sys.stderr)
        print("A read-only file or folder, a folder that is not there, or another program holding the "
              "database are the usual reasons. `python -m career_agent --doctor` reads the same database "
              "without writing to it and reports what it finds.", file=sys.stderr)
        return EXIT_REFUSED
    if isinstance(exc, sqlite3.Error):
        print(f"REFUSED: this database file could not be read, so nothing was reported: {exc}",
              file=sys.stderr)
        print("Nothing was changed or repaired. `python -m career_agent --doctor` names the file and the "
              "reason, and a verified backup taken earlier can be restored over it.", file=sys.stderr)
        return EXIT_REFUSED
    print(f"REFUSED: this database holds a record this version cannot read: {exc}", file=sys.stderr)
    print(_REFUSAL_ADVICE, file=sys.stderr)
    return EXIT_REFUSED


def run_doctor(args: argparse.Namespace) -> int:
    """Report the resolved settings and whether the data on this machine is usable.

    Read-only by design: nothing is created, opened for writing, or repaired. Every check states what
    was inspected and what was found, so an unreadable database is reported as the exact refusal the
    app itself would give rather than as a generic failure.
    """
    settings = resolve_settings(database_path=args.database)
    print(f"AI Career Agent {__version__} · database schema version {SCHEMA_VERSION}")
    print(f"Python {platform.python_version()} on {platform.system()} {platform.release()}")
    for line in describe_settings(settings):
        print(line)

    problems: list[str] = []
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        problems.append(
            f"This Python is {platform.python_version()}, but version {required} or newer is required."
        )
        print(f"PROBLEM: this Python is older than {required}, which this app requires.")

    folder = settings.default_data_folder
    if folder.is_dir():
        if os.access(folder, os.W_OK):
            print(f"Data folder: exists and is writable ({folder}).")
        else:
            problems.append(f"The data folder {folder} exists but is not writable.")
            print(f"PROBLEM: the data folder exists but is not writable ({folder}).")
    else:
        existing = _nearest_existing(folder)
        if existing is not None and not os.access(existing, os.W_OK):
            problems.append(f"The data folder {folder} cannot be created: {existing} is not writable.")
            print(f"PROBLEM: the data folder cannot be created; {existing} is not writable.")
        else:
            print(f"Data folder: not created yet; the app creates it on first run ({folder}).")

    database = settings.database_path
    if not database.exists():
        print("Database: no file yet, so there is nothing saved to check. The app creates it on first run.")
        if not database.parent.is_dir() and not problems:
            print(f"          (the folder {database.parent} will be created as well)")
    else:
        try:
            info = validate_app_database(database)
        except DatabaseInUse as exc:
            problems.append(str(exc))
            print(f"PROBLEM: the database could not be checked: {exc}")
        except (BackupError, OSError) as exc:
            problems.append(str(exc))
            print(f"PROBLEM: the database could not be read as this app's own file: {exc}")
            print("         Nothing was changed. The app gives the same message when it opens this file.")
        else:
            print(f"Database: readable, {info.summary()}.")
            if info.schema_version < SCHEMA_VERSION:
                print(
                    f"          It was written by schema version {info.schema_version}; opening the app "
                    f"updates it to version {SCHEMA_VERSION} and records that step in the file."
                )
                print("          Its records are not decoded here: this check never changes the file, so "
                      "the version check comes first.")
            else:
                # The structural check above cannot see a row this build cannot interpret - a status or a
                # payload that is present, well-formed SQLite, and unreadable to the app. The scan decodes
                # every record through the same functions the read paths use, read-only, so this report can
                # say what the app would say rather than "no problems found" above damaged data.
                try:
                    unreadable = unreadable_stored_records(database)
                except sqlite3.Error as exc:
                    problems.append(f"The stored records could not be read: {exc}")
                    print(f"PROBLEM: the stored records could not be read: {exc}")
                else:
                    if unreadable:
                        problems.extend(unreadable)
                        print(f"PROBLEM: {len(unreadable)} stored record(s) cannot be read by this version. "
                              "The app refuses those records rather than guessing, and this check changed "
                              "nothing:")
                        for sentence in unreadable:
                            print(f"         - {sentence}")
                    else:
                        print("          Every stored record could be decoded by this version.")
            if info.foreign_key_violations:
                problems.append(
                    f"The database has {info.foreign_key_violations} broken reference(s) between its tables."
                )
                print(f"PROBLEM: {info.foreign_key_violations} broken reference(s) between tables were found.")

    note_path = diagnostic_log_path(database_path=database)
    note_folder = note_path.parent
    if note_folder.is_dir() and not os.access(note_folder, os.W_OK):
        problems.append(f"Start-up notes cannot be written: {note_folder} is not writable.")
        print(f"PROBLEM: start-up notes cannot be written to {note_folder}.")
    else:
        print(f"Start-up notes: {note_path} (kept local; paths are redacted before they are written)")
        events = log_path(database_path=database)
        print(
            f"Event log: {events} "
            f"(one line per event, rotated at {MAX_LOG_BYTES // 1024} KiB, local paths redacted)"
        )
        recent = read_lines(database_path=database, limit=1)
        if recent:
            print(f"          last event: {recent[-1]}")
        elif not events.exists():
            print(f"          nothing recorded yet ({LOG_FILE_NAME} is created by the first event)")

    if settings.notes:
        print("Settings that were ignored are listed above with the reason.")
    if problems:
        print(f"\n{len(problems)} problem(s) found. Nothing was changed or repaired by this check.")
        print("The app's own error messages are what you would see when opening it; this report adds nothing.")
        return EXIT_PROBLEM_FOUND
    print("\nNo problems found. This report lists file locations, so remove them before sharing it.")
    return EXIT_OK


def run_backup(args: argparse.Namespace) -> int:
    """Write a verified backup; report the outcome truthfully and exit accordingly."""
    database = _database_path(args)
    destination = Path(args.backup_to).expanduser()
    try:
        info = create_backup(database, destination)
    except BackupError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        print("No backup was created.", file=sys.stderr)
        return EXIT_REFUSED
    print(f"Backup written and verified: {destination}")
    print(f"Contents: {info.summary()}")
    print("Owner-only where the file system supports POSIX permissions; not encrypted, so keep it private.")
    return EXIT_OK


def _confirmation(database: Path, source: Path) -> bool:
    """Ask for explicit confirmation; refuse rather than assume when there is no terminal."""
    if not sys.stdin.isatty():
        print(
            "REFUSED: restoring replaces the local database and needs explicit confirmation, but input "
            "is not a terminal. Re-run with --yes once you are sure of the file and the database.",
            file=sys.stderr,
        )
        return False
    print(f"Restoring replaces:\n  {database}\nwith the contents of:\n  {source}")
    print("The current database is copied aside first, and nothing is replaced if that copy fails.")
    return input("Type 'restore' to continue: ").strip().lower() == "restore"


def run_restore(args: argparse.Namespace) -> int:
    """Replace the local database from a validated backup, after confirmation."""
    database = _database_path(args)
    source = Path(args.restore_from).expanduser()
    if not args.yes and not _confirmation(database, source):
        print("Cancelled. Nothing was changed.")
        return EXIT_REFUSED
    try:
        result = restore_backup(source, database)
    except BackupError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        print("The restore did not complete.", file=sys.stderr)
        return EXIT_REFUSED
    print(f"Restored {database}\nfrom     {source}")
    print(f"Contents: {result.info.summary()}")
    if result.needs_schema_update:
        print(
            f"The restored file was written by an older schema (version {result.info.schema_version}); "
            f"opening the app updates it to schema version {SCHEMA_VERSION} and records that in the file."
        )
    if result.pre_restore_backup is not None:
        quality = "verified copy" if result.pre_restore_verified else "raw copy (it could not be read as a database)"
        print(f"Previous database kept as a {quality}: {result.pre_restore_backup}")
    if result.removed_sidecars:
        print("Removed stale SQLite side files: " + ", ".join(path.name for path in result.removed_sidecars))
    print("Keep the previous-database copy until you have confirmed everything you need is present.")
    return EXIT_OK


def run_seed_tasks(args: argparse.Namespace) -> int:
    """Add the default scheduled tasks to this database, without touching tasks that exist.

    The database is opened (and therefore created and updated to the current schema if needed), because
    a schedule is stored in it. Opening it is the only write: seeding itself adds rows only for tasks
    that are not there yet, and says which those were.
    """
    database = _database_path(args)
    with CareerStore(database) as store:
        outcome = seed_default_tasks(store)
    print(f"Schedule for {database}")
    print(f"  {outcome.describe()}")
    for task in outcome.tasks:
        next_run = task.next_run_at.isoformat() if task.next_run_at else "paused"
        state = "enabled" if task.enabled else "disabled"
        print(f"  {task.task_id}: {task.name} - {', '.join(task.times)} {task.timezone} "
              f"({state}); next {next_run}")
    print("Run them with: python -m career_agent --worker")
    return EXIT_OK


def run_worker_status(args: argparse.Namespace) -> int:
    """Report what is scheduled and what happened, without claiming anything or writing anything.

    Read-only on purpose: a status command that took the lease or marked an attempt as running would
    change the thing it is reporting on. If the database does not exist yet, that is not a problem to
    report as a failure - it is a fresh installation, and the report says so.
    """
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · scheduled tasks in {database}")
    if not database.exists():
        print("No database yet, so no tasks are scheduled. Open the app, or run "
              "python -m career_agent --seed-tasks, to add the default schedule.")
        return EXIT_OK
    try:
        with CareerStore(database) as store:
            status = worker_status(store)
            tasks = store.list_scheduled_tasks()
    except (StoredRecordError, TrackerStatusError, sqlite3.Error) as exc:
        return _refuse_database_problem(exc)
    for line in status.describe():
        print(line)
    if tasks:
        print("Scheduled tasks:")
        for task in tasks:
            due = task.next_run_at.isoformat() if task.next_run_at else "paused"
            print(f"  {task.task_id}: {task.name} - {', '.join(task.times)} {task.timezone} "
                  f"| next {due} | last "
                  f"{task.last_outcome.value if task.last_outcome else 'never run'}")
    else:
        print("No tasks are stored in this database yet; "
              "python -m career_agent --seed-tasks adds the defaults.")
    print("This report is read-only; nothing was claimed and nothing was run.")
    return EXIT_OK


def _follow_up_pairs(store: CareerStore) -> list[tuple]:
    """The stored follow-up records paired with their listings, in a stable order.

    A stored tracker whose listing has since been deleted is skipped *and counted*, so the report can say
    so. Dropping it silently would make a disappearing reminder look like the app forgetting.
    """
    pairs = []
    for tracker in store.list_follow_up_trackers():
        job = store.get_job(tracker.listing_id)
        if job is not None:
            pairs.append((tracker, job))
    return pairs


def run_export(args: argparse.Namespace) -> int:
    """Write this database's own export document to the path the person named.

    Local only, owner-only, and never overwritten silently: the file may hold the whole profile and
    history, so it goes through the same private write path as a backup. It is the same document the
    window's export button writes, built by the same function, so a file exported here imports there and
    the other way round.
    """
    target = Path(args.export_to).expanduser()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · export local data")
    if not database.exists():
        print("No database yet, so there is nothing to export. Nothing was written.")
        return EXIT_REFUSED
    if target.exists():
        print(f"REFUSED: {target} already exists. Choose another name so the existing file is not "
              "replaced.", file=sys.stderr)
        return EXIT_REFUSED
    with CareerStore(database) as store:
        try:
            written = importer.write_export(store, target)
            document = importer.export_document(store)
        except PrivateWriteError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return EXIT_REFUSED
        except (StoredRecordError, sqlite3.Error) as exc:
            print(f"REFUSED: the database could not be read for export: {exc}", file=sys.stderr)
            return EXIT_REFUSED
    print(f"Wrote {len(document['jobs'])} listing(s) and the profile to {written}")
    print("This file may hold personal information. It was written owner-only where the file system "
          "supports it, and nothing was sent anywhere.")
    return EXIT_OK


def run_import(args: argparse.Namespace) -> int:
    """Show what importing a file would do, and apply it only when told to.

    Reading the file and planning are read-only, so a mistyped path or a file from another program is
    refused without touching the database. Applying it writes through the store's own methods, so every
    storage rule still holds, and the report is counted from what actually happened.
    """
    source = Path(args.import_from).expanduser()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · import local data")
    try:
        document = importer.read_export(source)
    except importer.ImportRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    if not database.exists():
        print(f"No database exists yet at {database}. Opening an import is how it would be created; "
              "run the app or the commands once first, then import.")
        return EXIT_REFUSED
    with CareerStore(database) as store:
        # An import is planned and then applied to the whole file. If the file holds a record this build
        # cannot read, the apply would write the parts it can and fail on that record - leaving a
        # part-written database behind a refusal that says nothing was written. So the file is swept first,
        # read-only, and the command refuses before it plans or writes anything.
        problems = unreadable_stored_records(database)
        if problems:
            return _refuse_database_problem(problems=problems)
        try:
            plan = importer.plan_import(store, document, source=str(source))
        except importer.ImportRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return EXIT_REFUSED
        for line in plan.describe():
            print(line)
        if not args.yes:
            print("")
            print("Nothing was written. Run the same command with --yes to apply this plan.")
            return EXIT_OK
        outcome = importer.apply_import(store, document, source=str(source))
    print("")
    print(f"Import complete: {outcome.describe()}.")
    print("Nothing was replaced: a listing or profile already stored wins over the file's copy. "
          "Nothing was sent anywhere.")
    return EXIT_OK


def run_follow_ups(args: argparse.Namespace) -> int:
    """List the applications whose follow-up day has arrived or is coming up, and nothing else.

    Read-only: this never sets a day, never moves an application's status, and never contacts anybody.
    The day compared against is *this machine's* local day, and the report says so, because "due today"
    is a statement about the person's calendar rather than about UTC.
    """
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · follow-ups for {today.isoformat()} (local day)")
    if not database.exists():
        print("No database yet, so no follow-up days are recorded. Open the app to save applications "
              "and set the day you plan to follow each one up.")
        return EXIT_OK
    try:
        with CareerStore(database) as store:
            pairs = _follow_up_pairs(store)
            upcoming = reminders(pairs, today)
            missing_listings = len(store.list_follow_up_trackers()) - len(pairs)
    except (StoredRecordError, TrackerStatusError, sqlite3.Error) as exc:
        return _refuse_database_problem(exc)
    print(summary(upcoming))
    if upcoming:
        print("")
        for item in upcoming:
            print(f"  {item.describe()}")
    if missing_listings:
        print("")
        print(f"{missing_listings} record(s) have a follow-up day but no listing stored any more; "
              "they are not listed. Open the app to remove or re-link them.")
    print("")
    print("This report is read-only; no status was changed and nothing was sent.")
    return EXIT_OK


def run_next_actions(args: argparse.Namespace) -> int:
    """Report what needs doing about these applications, and nothing else.

    This is the one question a career workspace should answer first: not "what do you have" but "what is
    waiting on you". It combines the three things a person can have to do - a round to prepare for, a
    follow-up day that has arrived, and an open preparation item - orders them so what is most overdue comes
    first, with the kind breaking ties on the same day, and says how many items are further out rather than
    hiding them.

    Read-only, and deliberately so: nothing here moves an application's status, and the report says so. The
    day compared against is this machine's local day, because "due today" is a statement about the person's
    calendar rather than about UTC.
    """
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · what needs doing on {today.isoformat()} (local day)")
    if not database.exists():
        print("No database yet, so nothing is recorded. Open the app to save applications, plan "
              "follow-ups and write down what you have to do.")
        return EXIT_OK
    try:
        with CareerStore(database) as store:
            jobs = {job.listing_id: job for job in store.list_jobs()}
            preparation_items = store.list_preparation()
            rounds = store.list_interviews()
            pairs = _follow_up_pairs(store)
            found = preparation.actions(preparation_items, rounds, reminders(pairs, today), jobs, today,
                                        include_later=False, include_undated=True)
            everything = preparation.actions(preparation_items, rounds, reminders(pairs, today), jobs, today,
                                            include_later=True, include_undated=True)
    except (StoredRecordError, TrackerStatusError, sqlite3.Error) as exc:
        return _refuse_database_problem(exc)
    print(preparation.summary(found, today))
    if found:
        print("")
        for line in preparation.describe_actions(found):
            print(f"  {line}")
    later = len(everything) - len(found)
    if later:
        print("")
        # Only items beyond the window are hidden here: undated ones are listed above, because an
        # open item with no day is still work a person is carrying.
        print(f"{later} more item(s) are further out than the coming week; open the app to see them all.")
    print("")
    print(f"{len(preparation_items)} preparation item(s) and {len(rounds)} interview round(s) are "
          "recorded.")
    print("")
    print("This report is read-only; no status was changed and nothing was sent.")
    return EXIT_OK


def run_interviews(args: argparse.Namespace) -> int:
    """List the interview rounds recorded for these applications, next one first.

    Read-only. A round is the candidate's own note: the stage, the day it is planned for, how it is being
    held, their own reading of how it went, and their notes. Nothing here is an employer's decision, and the
    report says so rather than letting a stage name look like a result.
    """
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · recorded interview rounds ({today.isoformat()}, local day)")
    if not database.exists():
        print("No database yet, so no rounds are recorded. Open the app to record one after an employer "
              "gets in touch.")
        return EXIT_OK
    try:
        with CareerStore(database) as store:
            rounds = store.list_interviews()
            jobs = {job.listing_id: job for job in store.list_jobs()}
    except (StoredRecordError, TrackerStatusError, sqlite3.Error) as exc:
        return _refuse_database_problem(exc)
    print(preparation.interview_summary(rounds, today))
    if rounds:
        print("")
        for entry in preparation.rounds_ordered(rounds, today):
            job = jobs.get(entry.listing_id)
            where = (f"{job.role_title} at {job.employer_name}" if job is not None
                     else f"listing {entry.listing_id} (no longer stored)")
            when = f"{entry.scheduled_on.isoformat()} ({_relative_day(entry.days_away(today))})"
            print(f"  {when}: {entry.stage_label} - {entry.mode_label} [{where}]")
            print(f"      {entry.outcome_label}" + (f" - {entry.notes}" if entry.notes else ""))
    print("")
    print("These are your own notes about each round, not an employer's decision: nothing here says "
          "whether you passed, and no status was changed.")
    return EXIT_OK


def _relative_day(days: int) -> str:
    """A plain-language day offset, so a report does not make a person do arithmetic."""
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "yesterday"
    return f"in {days} day(s)" if days > 0 else f"{abs(days)} day(s) ago"


def _day_argument(raw: str | None, *, label: str, optional: bool) -> date | None:
    """Parse a ``YYYY-MM-DD`` option the same way the window's own date fields do.

    ``date.fromisoformat`` also accepts basic-format and ISO week dates; an option that promises
    ``YYYY-MM-DD`` should not quietly accept four spellings of it, so the shape is checked first. A
    refusal names the option that was wrong rather than the record that failed.
    """
    text = (raw or "").strip()
    if not text:
        if optional:
            return None
        raise ValueError(f"--{label} is required here and has to be a date, for example "
                         f"{_local_today().isoformat()}.")
    if ACTIVITY_DATE_PATTERN.fullmatch(text) is None:
        raise ValueError(f"--{label} has to be a date written as YYYY-MM-DD, for example "
                         f"{_local_today().isoformat()}.")
    return date.fromisoformat(text)


def run_analytics(args: argparse.Namespace) -> int:
    """Report what the stored records add up to, with every rate naming its denominator.

    Read-only. The report is computed by :mod:`career_agent.analytics` from the same records the window
    reads, so the two cannot disagree, and everything it refuses to report - because the denominator is too
    small, because a figure this application cannot know, or because a comparison needs more history than
    this database has - is printed with the reason. Silence there would read as a zero.
    """
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · progress from this database ({today.isoformat()}, local day)")
    if not database.exists():
        print("")
        print("No database yet, so nothing is recorded to add up. The counts start from what you write "
              "down: an application you applied to, a reply you received, a round you have been invited to.")
        print("")
        print("This report is read-only; nothing was changed, uploaded or sent to anybody.")
        return EXIT_OK
    try:
        with CareerStore(database) as store:
            report = analytics.report_from_store(store, today=today)
    except (StoredRecordError, TrackerStatusError, sqlite3.Error) as exc:
        return _refuse_database_problem(exc)
    lines = list(report.describe()[1:])
    while lines and not lines[0]:
        lines.pop(0)
    print("")
    for line in lines:
        print(line)
    print("")
    print("This report is read-only; no status was changed, nothing was uploaded and nothing was sent.")
    return EXIT_OK


def run_history(args: argparse.Namespace) -> int:
    """List the candidate's own employment and education records, most recent first.

    Read-only, like every other listing command here. The duration line reports months *covered* by
    current or fully dated roles and says how many records it could not count, rather than adding up to
    a single confident "years of experience" figure that overlapping or undated roles would falsify.
    """
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · your employment and education (local database)")
    if not database.exists():
        print("No database yet, so nothing is recorded. Open the app to add your roles as you go; "
              "nothing is uploaded and no employer is contacted.")
        return EXIT_OK
    try:
        with CareerStore(database) as store:
            roles = store.list_work_history()
            study = store.list_education()
    except (StoredRecordError, TrackerStatusError, sqlite3.Error) as exc:
        return _refuse_database_problem(exc)
    print("")
    print(f"Employment ({len(roles)} record(s), current role first)")
    if not roles:
        print("  None recorded. The profile's experience figure is a summary and is kept separate.")
    for role in roles:
        print(f"  {role.period}: {role.job_title} at {role.employer}"
              f" [{role.employment_type_label}]")
        if role.summary:
            print(f"      {role.summary}")
    counted = months_covered_by(roles, today=today)
    uncounted = sum(1 for role in roles if role.end_date is None and not role.is_current)
    if counted:
        print(f"  These periods cover {counted} month(s) in total; months covered by two roles at "
              "once are counted once, a role with no recorded end counts nothing, and this is not a "
              "claim about experience.")
    if uncounted:
        print(f"  {uncounted} ended role(s) have no end date recorded, so no duration is counted "
              "for them.")
    print("")
    print(f"Education ({len(study)} record(s), ongoing first)")
    if not study:
        print("  None recorded.")
    for entry in study:
        print(f"  {entry.period}: {entry.label} at {entry.institution}")
    print("")
    print("This report is read-only; nothing was changed, uploaded or sent to anybody.")
    return EXIT_OK


def run_add_role(args: argparse.Namespace) -> int:
    """Add one employment record, with the same validation the window applies.

    A write, and the only one this command does: it adds a record, and refuses rather than writing
    anything when the dates contradict each other or the role is already recorded. It never edits or
    deletes an existing record. Like ``--seed-tasks``, it opens the database rather than refusing when
    there is none yet, so on a fresh machine this creates the empty schema and then the one record.
    """
    database = _database_path(args)
    if not args.title:
        print("REFUSED: --add-role needs --title, for example --title 'Data Engineer'. Nothing was "
              "written.", file=sys.stderr)
        return EXIT_REFUSED
    try:
        started = _day_argument(args.start, label="start", optional=False)
        ended = _day_argument(args.end, label="end", optional=True)
    except ValueError as exc:
        print(f"REFUSED: {exc} Nothing was written.", file=sys.stderr)
        return EXIT_REFUSED
    with CareerStore(database) as store:
        try:
            added = store.add_work_history(args.add_role, args.title, started, end_date=ended,
                                          is_current=bool(args.current),
                                          employment_type=args.employment_type, summary=args.summary)
        except ValueError as exc:
            print(f"REFUSED: {exc} Nothing was written.", file=sys.stderr)
            return EXIT_REFUSED
        print(f"Added employment record {added.entry_id}: {added.job_title} at {added.employer} "
              f"({added.period}, {added.employment_type_label}).")
        print(f"{len(store.list_work_history())} employment record(s) are now recorded. Nothing was "
              "uploaded and no employer was contacted.")
    return EXIT_OK


def run_add_study(args: argparse.Namespace) -> int:
    """Add one education record. Dates are optional, and ongoing study takes no completion date."""
    database = _database_path(args)
    if not args.qualification:
        print("REFUSED: --add-study needs --qualification, for example --qualification M.Sc. Nothing "
              "was written.", file=sys.stderr)
        return EXIT_REFUSED
    try:
        started = _day_argument(args.start, label="start", optional=True)
        completed = _day_argument(args.completed, label="completed", optional=True)
    except ValueError as exc:
        print(f"REFUSED: {exc} Nothing was written.", file=sys.stderr)
        return EXIT_REFUSED
    with CareerStore(database) as store:
        try:
            added = store.add_education(args.add_study, args.qualification, discipline=args.discipline,
                                        start_date=started, completion_date=completed,
                                        is_ongoing=bool(args.ongoing))
        except ValueError as exc:
            print(f"REFUSED: {exc} Nothing was written.", file=sys.stderr)
            return EXIT_REFUSED
        print(f"Added education record {added.entry_id}: {added.label} at {added.institution} "
              f"({added.period}).")
        print(f"{len(store.list_education())} education record(s) are now recorded. Nothing was "
              "uploaded and no institution was contacted.")
    return EXIT_OK


# ---------------------------------------------------------------------------- email and calendar

#: Options that only mean something together with one of the integration commands. Using one on its own is
#: refused rather than ignored: a dropped ``--recipient`` would look exactly like a message that went
#: nowhere, and a dropped ``--at`` would silently turn an appointment into an all-day entry.
_DEPENDENT_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("recipient", "--recipient", "--draft-follow-up"),
    ("save_draft", "--save-draft", "--draft-follow-up"),
    ("at", "--at", "--record-follow-up"),
    ("minutes", "--minutes", "--record-follow-up"),
    ("timezone", "--timezone", "--record-follow-up"),
)


def describe_orphan_options(args: argparse.Namespace) -> str | None:
    """The first option that was given without the command it belongs to, or ``None``.

    A command-line option that is quietly ignored is a false statement about what the command did, so this
    returns a sentence the caller prints as a refusal instead.
    """
    for attribute, option, command in _DEPENDENT_OPTIONS:
        if getattr(args, attribute, None) is None:
            continue
        wanted = getattr(args, command.removeprefix("--").replace("-", "_"), None)
        if not wanted:
            return f"{option} only means something with {command}."
    if args.mock_ledger and not (args.draft_follow_up or args.record_follow_up):
        return "--mock-ledger only means something with --draft-follow-up or --record-follow-up."
    return None


def run_integration_status(args: argparse.Namespace) -> int:
    """Report which integrations exist and why none is enabled. Database-free and read-only.

    It does not open the database, so it answers on a machine where nothing has been recorded yet - which is
    exactly when a person asks whether this app can send email on their behalf.
    """
    print(f"AI Career Agent {__version__} · email and calendar integrations")
    for line in integrations.describe_integrations():
        print(line)
    print("")
    print("This report is read-only: nothing was sent, nothing was created, no account was touched and no "
          "connection was opened to produce it.")
    return EXIT_OK


def _integration_from_options(args: argparse.Namespace) -> integrations.Integration:
    """The integration these commands use: none at all unless a local mock ledger was named.

    There is no configuration, environment variable or stored setting that selects a provider, so asking for
    something to be performed without naming the mock gets the disabled integration and its reason. That is
    the honest answer rather than an error, and it is the same answer the window gives.
    """
    if args.mock_ledger:
        return integrations.LocalMockIntegration(ledger_path=Path(args.mock_ledger).expanduser())
    return integrations.default_integration()


def _reminder_for_listing(
    store: CareerStore, listing_id: str, today: date,
) -> tuple[object | None, str | None]:
    """The follow-up reminder for one stored application, or the reason there is not one.

    Every refusal here is about a fact that is genuinely absent. None of them is filled in: a listing id with
    no recorded day gets a sentence asking for the day, not today's date, and a listing that has been deleted
    gets a sentence saying so rather than a draft addressed to a role nobody can look up.
    """
    tracker = store.get_tracker(listing_id)
    if tracker is None:
        return None, f"No application is stored with listing id {listing_id}, so there is nothing to write from."
    if tracker.follow_up_on is None:
        return None, (
            f"{listing_id} has no follow-up day recorded, and this command will not invent one. Set the day "
            "on the Reminders tab in the window, then run this again."
        )
    job = store.get_job(listing_id)
    if job is None:
        return None, (
            f"The listing {listing_id} is no longer stored, so there is no role or employer to write from. "
            "Add it again or pick another application."
        )
    return reminder_for(tracker, job, today), None


def run_preview_calendar_export(args: argparse.Namespace) -> int:
    """Say exactly which events the local ``.ics`` export would contain. Writes nothing.

    The working calendar path in this application is that file: local, owner-only, importable into whatever
    calendar the person already uses, with no account and no invitation. Previewing it makes the difference
    between that and an integration explicit instead of implied - and it is the same code the export uses, so
    a preview cannot promise a different event from the one the file will hold.
    """
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · calendar export preview (nothing is written)")
    if not database.exists():
        print("No database yet, so there are no follow-up days to preview. Nothing was written.")
        return EXIT_REFUSED
    with CareerStore(database) as store:
        upcoming = reminders(_follow_up_pairs(store), today)
    if not upcoming:
        print("No follow-up days are recorded, so there would be nothing to export. Set a day on an "
              "application in the window and run this again. Nothing was written.")
        return EXIT_REFUSED
    plan = integrations.calendar_export_plan(upcoming)
    for line in plan.describe():
        print(line)
    print(f"To write it: python -m career_agent --calendar-to {calendar_file_name(today)}")
    print("Nothing was written by this command, no calendar account was contacted, and no invitation was "
          "sent.")
    return EXIT_OK


def run_draft_follow_up(args: argparse.Namespace) -> int:
    """Write a follow-up email draft from what is already recorded, and print it. Sends nothing.

    The draft is built from the employer, the role, the day the person chose and their own note - facts the
    database already holds - and from nothing else. The recipient comes only from ``--recipient``: an address
    guessed from an employer's name would send somebody's private message to a stranger.
    """
    listing_id = args.draft_follow_up
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · follow-up email draft (nothing is sent)")
    if not database.exists():
        print("No database yet, so there is no application to write from. Nothing was written.")
        return EXIT_REFUSED
    try:
        integration = _integration_from_options(args)
    except ValueError as exc:
        print(f"REFUSED: {exc} Nothing was written.", file=sys.stderr)
        return EXIT_REFUSED
    with CareerStore(database) as store:
        reminder, problem = _reminder_for_listing(store, listing_id, today)
        if reminder is None:
            print(f"REFUSED: {problem} Nothing was written.", file=sys.stderr)
            return EXIT_REFUSED
        job = store.get_job(listing_id)
        try:
            draft = integrations.draft_for_follow_up(reminder, recipient=args.recipient)
        except ValueError as exc:
            print(f"REFUSED: {exc} Nothing was written.", file=sys.stderr)
            return EXIT_REFUSED
        preview = integrations.preview_email(draft, integration=integration, listing=job)

    for line in preview.describe():
        print(line)
    print("")
    print("The draft in full:")
    print("-" * 72)
    print(integrations.draft_as_text(draft).rstrip("\n"))
    print("-" * 72)
    written_path: Path | None = None
    if args.save_draft:
        target = Path(args.save_draft).expanduser()
        if target.exists():
            print(f"REFUSED: {target} already exists, so the draft was not written over it.", file=sys.stderr)
            return EXIT_REFUSED
        try:
            written = write_private_text_file(target, integrations.draft_as_text(draft))
        except PrivateWriteError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return EXIT_REFUSED
        except OSError as exc:
            print(f"REFUSED: {target} could not be written: {exc.strerror or exc}. Nothing was written.",
                  file=sys.stderr)
            return EXIT_REFUSED
        written_path = written
        print(f"Wrote the draft to {written} (a plain text file on this machine, not a message that was sent).")
    if not args.mock_ledger:
        print("Nothing was attempted: no email integration is enabled in this build, so this draft could not "
              "be sent even if you asked. Add --mock-ledger PATH to run it through the local mock, which "
              "records the operation locally and contacts nothing.")
        return EXIT_OK
    result = integrations.dispatch_with_retry(integration, draft)
    print(result.describe())
    if not result.succeeded:
        # Two different states arrive here and the sentence has to fit the one that happened: a draft saved
        # to a file and then refused, and a draft that was never written anywhere because the request was
        # missing a fact. Saying "the draft was written" in the second case sends somebody looking for a file
        # that does not exist - reproduced from the acceptance run on 2026-10-15, where a draft with no
        # recipient printed that sentence and left nothing on disk.
        if written_path is None:
            print(f"REFUSED: no file was written and the draft was not performed "
                  f"({result.outcome.value}); the preview above is not a file on this machine.",
                  file=sys.stderr)
        else:
            print(f"REFUSED: the draft was written to {written_path} but not performed "
                  f"({result.outcome.value}).", file=sys.stderr)
        return EXIT_REFUSED
    return EXIT_OK


def _requested_start_time(args: argparse.Namespace) -> tuple[time | None, int | None]:
    """The start time and duration that were asked for, or a refusal explaining the combination.

    Nothing is defaulted here. Without ``--at`` the event stays an all-day entry on the follow-up day, which
    is what the person recorded; a time invented by the command would be an appointment in somebody's
    calendar that nobody agreed to.
    """
    if not args.at:
        if args.minutes or args.timezone:
            raise ValueError(
                "--minutes and --timezone describe a start time, so they need --at HH:MM. Without --at the "
                "event is an all-day entry on the follow-up day."
            )
        return None, None
    try:
        start = time.fromisoformat(args.at.strip())
    except ValueError as exc:
        raise ValueError(
            f"--at {args.at!r} is not a time of day. Write it as HH:MM, for example 10:30."
        ) from exc
    if not args.timezone:
        raise ValueError(
            "Give --timezone as well, for example --timezone Asia/Kolkata: without it the same clock reading "
            "means a different moment to whoever receives it."
        )
    if not args.minutes:
        raise ValueError("Give --minutes as well: how long is the event expected to take?")
    try:
        minutes = int(str(args.minutes).strip())
    except ValueError as exc:
        raise ValueError(f"--minutes {args.minutes!r} is not a whole number of minutes.") from exc
    return start, minutes


def run_record_follow_up(args: argparse.Namespace) -> int:
    """Ask to record a calendar event for a follow-up day, and report what actually happened.

    With no integration enabled - which is every build of this application - the answer is a refusal that
    names the reason and points at the local export, and no event exists anywhere afterwards. With
    ``--mock-ledger`` the operation is performed by the local mock, which records it in that file and
    contacts nothing. Either way the command reports the outcome it got rather than the outcome it wanted.
    """
    listing_id = args.record_follow_up
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · calendar event for a follow-up (nothing is created on its own)")
    if not database.exists():
        print("No database yet, so there is no follow-up day to record. Nothing was created.")
        return EXIT_REFUSED
    try:
        integration = _integration_from_options(args)
        start, minutes = _requested_start_time(args)
    except ValueError as exc:
        print(f"REFUSED: {exc} Nothing was created.", file=sys.stderr)
        return EXIT_REFUSED
    with CareerStore(database) as store:
        reminder, problem = _reminder_for_listing(store, listing_id, today)
        if reminder is None:
            print(f"REFUSED: {problem} Nothing was created.", file=sys.stderr)
            return EXIT_REFUSED
        job = store.get_job(listing_id)
        try:
            request = integrations.event_from_reminder(
                reminder, start_time=start, duration_minutes=minutes, timezone_name=args.timezone)
        except ValueError as exc:
            print(f"REFUSED: {exc} Nothing was created.", file=sys.stderr)
            return EXIT_REFUSED
        preview = integrations.preview_event(request, integration=integration, listing=job)

    for line in preview.describe():
        print(line)
    result = integrations.dispatch_with_retry(integration, request)
    print("")
    print(result.describe())
    if not result.succeeded:
        print(f"REFUSED: no calendar event was recorded ({result.outcome.value}).", file=sys.stderr)
        return EXIT_REFUSED
    print("No calendar account was contacted, and no invitation was sent to anybody.")
    return EXIT_OK


def run_calendar_export(args: argparse.Namespace) -> int:
    """Write the recorded follow-ups to a calendar file at the path the person named.

    Local only: a file on this machine, no calendar account, no credentials and no network. The file
    holds what the person recorded (role, employer, their own note, the day) and is written through the
    same owner-only write path as everything else, so it is not readable by other accounts on the
    machine. An existing file is never overwritten in place silently: a name that is taken is reported.
    """
    target = Path(args.calendar_to).expanduser()
    today = _local_today()
    database = _database_path(args)
    print(f"AI Career Agent {__version__} · calendar export")
    if not database.exists():
        print("No database yet, so there are no follow-up days to export. Nothing was written.")
        return EXIT_REFUSED
    with CareerStore(database) as store:
        pairs = _follow_up_pairs(store)
        upcoming = reminders(pairs, today)
    if not upcoming:
        print("No follow-up days are recorded, so no calendar file was written. Set a day on an "
              "application in the window and run this again.")
        return EXIT_REFUSED
    if target.exists():
        # Refusing rather than overwriting: the file holds somebody's plan, and a second export that
        # quietly replaced the first would lose the reminders they had already imported elsewhere.
        print(f"REFUSED: {target} already exists. Choose another name (for example "
              f"{calendar_file_name(today)}) so the existing file is not replaced.", file=sys.stderr)
        return EXIT_REFUSED
    text = to_calendar(upcoming, now=datetime.now(timezone.utc))
    try:
        written = write_private_text_file(target, text)
    except PrivateWriteError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except OSError as exc:
        print(f"REFUSED: {target} could not be written: {exc.strerror or exc}. Nothing was written.",
              file=sys.stderr)
        return EXIT_REFUSED
    print(f"Wrote {len(upcoming)} reminder(s) to {written}")
    print(f"Import it into your own calendar when you like; the file is local to this machine "
          f"({len(text.encode('utf-8'))} bytes, {summary(upcoming)})")
    print("Nothing was sent anywhere, and no application status changed.")
    return EXIT_OK


def _local_today() -> date:
    """Today's date on this machine, which is the day a person's own calendar is on."""
    return datetime.now().date()


def run_sources(args: argparse.Namespace) -> int:
    """Report what could be fetched from where, and why nothing is being fetched.

    Read-only and database-free: the answer does not depend on this machine's data, and printing it must
    not create a database. Each reviewed source is listed with its permission state, whether it is
    selected for use, and what the gate says about it *now* - because the honest answer today is "none",
    and a report that only said "no sources" would not tell a person whether that is a policy decision or
    a broken installation.
    """
    print(f"AI Career Agent {__version__} · job sources")
    gate_open = "passed" if SOURCE_QUALITY_GATE_PASSED else "NOT passed"
    print(f"Source-quality gate: {gate_open}. While it is not passed no source may run, whatever its own "
          "permission says.")
    enabled = enabled_discovery_sources()
    print(f"Sources permitted to run discovery now: {', '.join(enabled) if enabled else 'none'}.")
    print("")
    print("Reviewed sources:")
    for decision in SOURCE_DECISIONS:
        gate = discovery_gate(decision.source_id)
        selected = "selected for use" if decision.selected_for_use else "not selected for use"
        print(f"  {decision.source_id}: {decision.permission_state.value} ({selected})")
        print(f"    decision: {gate.reason}")
        print(f"    evidence: {decision.evidence_ref or 'none recorded'}"
              f"{' - reviewed ' + decision.reviewed_on if decision.reviewed_on else ''}")
        for condition in decision.discovery_conditions:
            print(f"    condition: {condition}")
        submission = submission_gate(decision.source_id)
        print(f"    applying for jobs here: "
              f"{'permitted' if submission.allowed else 'not permitted'}")
    print("")
    registry = adapter_framework.default_registry()
    adapters = registry.source_ids()
    print(f"Adapters built into this version: {len(adapters)}"
          f"{' (' + ', '.join(adapters) + ')' if adapters else ''}.")
    if not adapters:
        print("  None, deliberately: an adapter is only written for a source whose permission review and "
              "the source-quality gate have both passed. The framework that will run one is in place and "
              "tested; the permissions are not.")
    for line in registry.health():
        print(f"  {line.describe()}")
    print("")
    print("This report is read-only; nothing was contacted and nothing was run.")
    return EXIT_OK


def run_worker(args: argparse.Namespace) -> int:
    """Run this database's scheduled tasks in the foreground until stopped.

    The worker executes local work only: the registered handlers write a verified local backup and
    refuse the gated discovery run, so nothing here reaches the network. Ctrl-C stops it cleanly - the
    attempt in progress is given the chance to wind up, its outcome is recorded, and the lease is
    released - and the exit status says which of those happened.
    """
    database = _database_path(args)
    worker_id = (args.worker_id or DEFAULT_WORKER_ID).strip()
    settings = WorkerSettings() if args.poll_seconds is None else WorkerSettings(
        poll_seconds=args.poll_seconds)
    print(f"AI Career Agent {__version__} · worker {worker_id}")
    print(f"Database: {database}")
    print("Registered kinds:")
    for line in describe_default_handlers():
        print(f"  {line}")
    print("Live discovery is disabled: the source-quality gate has not passed. Scheduled discovery runs "
          "are recorded as refusals, and nothing is fetched.")
    print("This worker runs while this process does. It stops when you press Ctrl-C or close this "
          "window, and it does not run while the computer is off or asleep.")
    if not database.exists():
        print("No database yet; the default schedule is being added so there is something to run.")
    with CareerStore(database) as store:
        if not store.list_scheduled_tasks():
            outcome = seed_default_tasks(store)
            print(f"  {outcome.describe()}")
        worker = Worker(store, worker_id=worker_id, registry=default_registry(),
                        settings=settings, on_outcome=_print_run_outcome)
        try:
            worker.run(stop_event=_stop_event_installed())
        except WorkerLeaseHeld as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return EXIT_ALREADY_RUNNING
    print("Worker stopped; its lease has been released.")
    return EXIT_OK


def _print_run_outcome(run) -> None:
    """One line per finished attempt, so a person watching the terminal sees what happened."""
    seconds = run.duration_seconds
    timing = f"{seconds:.1f}s" if seconds is not None else "an unrecorded time"
    line = f"{run.slot_at.isoformat()} {run.task_id} attempt {run.attempt}: {run.state.value} ({timing})"
    if run.detail:
        line += f" - {run.detail}"
    if run.error:
        line += f" - error: {run.error}"
    print(line, flush=True)


def _stop_event_installed():
    """A stop event wired to Ctrl-C, or ``None`` where signals are not available.

    ``signal.signal`` only works on the main thread of the main interpreter, so a caller in a test or an
    embedding application gets the plain event with no handler and stops the worker through the object
    instead.
    """
    import signal
    import threading as _threading

    event = _threading.Event()
    try:
        signal.signal(signal.SIGINT, lambda signum, frame: event.set())
        signal.signal(signal.SIGTERM, lambda signum, frame: event.set())
    except (ValueError, OSError):
        # Not the main thread, or a platform without these signals: the worker still stops when it is
        # asked to through its own API, and Ctrl-C still ends the process.
        return None
    return event


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    #: Whether the person asked for the window rather than a command. Only the window branch below sets
    #: it, and every command keeps it False, so the failure handler can tell a start-up apart from a
    #: command that could not read the database it was pointed at.
    opening_the_window = False
    try:
        if args.backup_to:
            return run_backup(args)
        if args.restore_from:
            return run_restore(args)
        if args.doctor:
            return run_doctor(args)
        if args.worker_status:
            return run_worker_status(args)
        if args.seed_tasks:
            return run_seed_tasks(args)
        if args.sources:
            return run_sources(args)
        if args.integration_status:
            return run_integration_status(args)
        orphan = describe_orphan_options(args)
        if orphan is not None:
            print(f"REFUSED: {orphan} Nothing was written.", file=sys.stderr)
            return EXIT_REFUSED
        if args.follow_ups:
            return run_follow_ups(args)
        if args.next_actions:
            return run_next_actions(args)
        if args.interviews:
            return run_interviews(args)
        if args.analytics:
            return run_analytics(args)
        if args.history:
            return run_history(args)
        if args.add_role:
            return run_add_role(args)
        if args.add_study:
            return run_add_study(args)
        if args.preview_calendar_export:
            return run_preview_calendar_export(args)
        if args.draft_follow_up:
            return run_draft_follow_up(args)
        if args.record_follow_up:
            return run_record_follow_up(args)
        if args.calendar_to:
            return run_calendar_export(args)
        if args.export_to:
            return run_export(args)
        if args.import_from:
            return run_import(args)
        if args.worker:
            return run_worker(args)
        # Imported only when the window is actually opened, so the database commands work headless.
        from .desktop import main as run_desktop
        # Opening the window is the one thing the person can ask for that really is a start-up, so a
        # database it cannot read is described by the start-up handler below. Every command above is a
        # report or an action that runs to completion: for those the same failure is a refusal.
        opening_the_window = True
        run_desktop(database_path=args.database)
        return EXIT_OK
    except BackupError as exc:  # defensive: the actions above already handle their own failures
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as exc:  # noqa: BLE001 - report honestly rather than showing a bare traceback
        if not opening_the_window and isinstance(exc, (StoredRecordError, TrackerStatusError, sqlite3.Error)):
            # A record this build cannot read, or a file that cannot be read as a database at all, is a
            # refusal rather than a crash. The read-only reports already word it that way; routing the
            # commands that read the same records through the same sentence is what makes the answer the
            # same whichever one is asked first. Without this, a damaged record in a command that is not
            # one of those reports was reported as "the application stopped while starting up" - with a
            # start-up note written beside the data for a start-up that never happened, and a status
            # meaning "unexpected failure" where every other path uses the documented refusal.
            return _refuse_database_problem(exc)
        # Start-up failures are explained in plain language with local paths redacted, and kept in a
        # bounded owner-only note beside the app data, because a terminal transcript is easy to paste
        # somewhere and must not carry candidate data, credentials, or filesystem locations.
        # A backup or restore that fails unexpectedly is reported here, so the file the person named
        # on the command line is passed as well: a location they chose must not reach a note that is
        # meant to be safe to share, even when the message mentioning it comes from an unexpected
        # failure rather than a refusal this module already words.
        named_paths = [named for named in (args.backup_to, args.restore_from) if named]
        explanation = describe_startup_failure(exc, database_path=args.database, extra_paths=named_paths)
        note = record_startup_failure(exc, database_path=args.database, extra_paths=named_paths)
        print(f"COULD NOT START: {explanation}", file=sys.stderr)
        if note is not None:
            print(f"A sanitised note was saved as {note.name} in the application's logs folder.", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    raise SystemExit(main())
