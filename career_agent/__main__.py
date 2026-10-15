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

Nothing here touches the network. Restoring replaces candidate data, so it always requires an explicit
confirmation: the file must be named and confirmed interactively, or ``--yes`` must be passed.
"""
from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timezone
import platform
import sys
from pathlib import Path

from . import __version__
from .backup import BackupError, DatabaseInUse, create_backup, restore_backup, suggested_backup_name, validate_app_database
from .config import database_path_for_run, describe_settings, resolve_settings
from .diagnostics import describe_startup_failure, diagnostic_log_path, record_startup_failure
from .event_log import LOG_FILE_NAME, MAX_LOG_BYTES, log_path, read_lines
from .handlers import default_registry, describe_default_handlers, seed_default_tasks
from .store import SCHEMA_VERSION, CareerStore, PrivateWriteError, write_private_text_file
from .followups import calendar_file_name, reminders, summary, to_calendar
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
        "--calendar-to", metavar="PATH",
        help="Write follow-up reminders to a calendar file (.ics) at PATH, for your own calendar.",
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
    with CareerStore(database) as store:
        status = worker_status(store)
        for line in status.describe():
            print(line)
        tasks = store.list_scheduled_tasks()
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
    with CareerStore(database) as store:
        pairs = _follow_up_pairs(store)
        upcoming = reminders(pairs, today)
        print(summary(upcoming))
        if upcoming:
            print("")
            for item in upcoming:
                print(f"  {item.describe()}")
        missing_listings = len(store.list_follow_up_trackers()) - len(pairs)
        if missing_listings:
            print("")
            print(f"{missing_listings} record(s) have a follow-up day but no listing stored any more; "
                  "they are not listed. Open the app to remove or re-link them.")
    print("")
    print("This report is read-only; no status was changed and nothing was sent.")
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
        if args.follow_ups:
            return run_follow_ups(args)
        if args.calendar_to:
            return run_calendar_export(args)
        if args.worker:
            return run_worker(args)
        # Imported only when the window is actually opened, so the database commands work headless.
        from .desktop import main as run_desktop
        run_desktop(database_path=args.database)
        return EXIT_OK
    except BackupError as exc:  # defensive: the actions above already handle their own failures
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as exc:  # noqa: BLE001 - report honestly rather than showing a bare traceback
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
