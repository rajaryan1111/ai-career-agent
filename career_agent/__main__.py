"""Command-line entry point: open the desktop app, or back up and restore the local database.

    python -m career_agent                            # open the desktop app
    python -m career_agent --version                  # print the version this checkout runs
    python -m career_agent --backup-to PATH           # write a verified, owner-only backup
    python -m career_agent --restore-from PATH        # validate, confirm, then replace the database
    python -m career_agent --doctor                   # report where the data is and whether it is usable

The two database commands exist because the situation that needs a restore most — a database the app
cannot read — is also the situation in which the window cannot be opened. They import no GUI toolkit,
so they work in a headless session, and they use the same tested :mod:`career_agent.backup` module as
the desktop buttons: one implementation, two front ends. ``--version`` and the start-up failure report
are likewise Tk-free, so they work when the window cannot open.

``--doctor`` answers "where does this app keep my data, and can it read it?" without opening the
window: it resolves the same settings the app uses, reports the version and the supported interpreter,
and reads the database read-only (or says it does not exist yet). It creates nothing and changes
nothing, so it is safe to run when something is already wrong.

Nothing here touches the network. Restoring replaces candidate data, so it always requires an explicit
confirmation: the file must be named and confirmed interactively, or ``--yes`` must be passed.
"""
from __future__ import annotations

import argparse
import os
import platform
import sys
from pathlib import Path

from . import __version__
from .backup import BackupError, DatabaseInUse, create_backup, restore_backup, suggested_backup_name, validate_app_database
from .config import database_path_for_run, describe_settings, resolve_settings
from .diagnostics import describe_startup_failure, diagnostic_log_path, record_startup_failure
from .event_log import LOG_FILE_NAME, MAX_LOG_BYTES, log_path, read_lines
from .store import SCHEMA_VERSION

EXIT_OK = 0
#: ``--doctor`` uses this so it can be wired into a launcher or a script: a found problem is a real
#: failure, and anything else would hide it. It is deliberately distinct from a refusal (2).
EXIT_PROBLEM_FOUND = 1
EXIT_REFUSED = 2
EXIT_UNEXPECTED = 3

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


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    try:
        if args.backup_to:
            return run_backup(args)
        if args.restore_from:
            return run_restore(args)
        if args.doctor:
            return run_doctor(args)
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
