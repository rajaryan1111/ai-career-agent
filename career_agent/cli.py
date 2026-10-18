"""Command-line entry point for the AI Career Agent desktop app.

Argument parsing and path validation live here so they work without a display;
the Tk UI is imported only when the app actually starts.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m career_agent",
        description="Open the offline AI Career Agent desktop workspace.",
    )
    parser.add_argument(
        "--database",
        metavar="PATH",
        help=(
            "SQLite database to use instead of the per-user application-data file. "
            "An existing file is opened and upgraded to the current schema; a missing file "
            "is created. An existing database is never replaced."
        ),
    )
    return parser


def resolve_database_path(value: str | None) -> Path | None:
    """Expand a ``--database`` argument; ``None`` means the per-user default."""
    if value is None:
        return None
    return Path(value).expanduser()


def check_database_path(path: Path) -> None:
    """Reject paths SQLite cannot open before a window or a database is created."""
    if path.exists() and path.is_dir():
        raise ValueError(f"The database path is a directory, not a file: {path}")
    if not path.exists() and not path.parent.is_dir():
        raise ValueError(
            f"The database folder does not exist: {path.parent}. Create it or choose another path."
        )


def run(database_path: Path | None) -> int:
    """Start the desktop UI, reporting a missing Tk runtime as an error."""
    try:
        from .desktop import run_desktop
    except ImportError as exc:  # Tkinter is absent from this interpreter.
        print(f"AI Career Agent requires Tkinter: {exc}", file=sys.stderr)
        return 1
    return run_desktop(database_path)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the desktop app; returns a process exit code instead of raising."""
    args = build_arg_parser().parse_args(argv)
    database_path = resolve_database_path(args.database)
    if database_path is not None:
        try:
            check_database_path(database_path)
        except ValueError as exc:
            print(f"AI Career Agent could not start: {exc}", file=sys.stderr)
            return 2
    return run(database_path)


if __name__ == "__main__":
    sys.exit(main())
