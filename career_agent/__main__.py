"""Command-line entry point: open the desktop app, or back up and restore the local database.

    python -m career_agent                            # open the desktop app
    python -m career_agent --version                  # print the version this checkout runs
    python -m career_agent --backup-to PATH           # write a verified, owner-only backup
    python -m career_agent --restore-from PATH        # validate, confirm, then replace the database

The two database commands exist because the situation that needs a restore most — a database the app
cannot read — is also the situation in which the window cannot be opened. They import no GUI toolkit,
so they work in a headless session, and they use the same tested :mod:`career_agent.backup` module as
the desktop buttons: one implementation, two front ends. ``--version`` and the start-up failure report
are likewise Tk-free, so they work when the window cannot open.

Nothing here touches the network. Restoring replaces candidate data, so it always requires an explicit
confirmation: the file must be named and confirmed interactively, or ``--yes`` must be passed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .backup import BackupError, create_backup, restore_backup, suggested_backup_name
from .desktop_logic import default_database_path
from .diagnostics import describe_startup_failure, record_startup_failure
from .store import SCHEMA_VERSION

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_UNEXPECTED = 3


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m career_agent",
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
    return Path(args.database).expanduser() if args.database else default_database_path()


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
        # Imported only when the window is actually opened, so the database commands work headless.
        from .desktop import main as run_desktop
        run_desktop(database_path=Path(args.database).expanduser() if args.database else None)
        return EXIT_OK
    except BackupError as exc:  # defensive: the actions above already handle their own failures
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Exception as exc:
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
