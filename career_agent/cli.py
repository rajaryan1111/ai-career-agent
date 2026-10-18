"""Command-line entry point for the AI Career Agent desktop app.

Argument parsing and path validation live here so they work without a display;
the Tk UI is imported only when the app actually starts.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import platform
import sqlite3
import sys

from . import __version__
from .paths import default_database_path


def _tk_status() -> str:
    """Probe Tkinter without leaving a window open."""
    try:
        import tkinter
    except Exception as exc:
        return f"unavailable ({type(exc).__name__})"
    try:
        root = tkinter.Tk()
        root.withdraw()
        patchlevel = str(root.tk.call("info", "patchlevel"))
        root.destroy()
    except Exception as exc:
        return f"unavailable ({exc})"
    return f"available (Tk {patchlevel})"


def _database_status() -> str:
    path = default_database_path(create=False)
    if not path.exists():
        return f"not created yet ({path})"
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            connection.close()
        size_kib = path.stat().st_size / 1024
    except (sqlite3.Error, OSError) as exc:
        return f"unreadable ({type(exc).__name__}: {exc}) at {path}"
    return f"exists (schema {version}, {size_kib:.1f} KiB) at {path}"


def diagnostics() -> list[tuple[str, str]]:
    """Return privacy-conscious environment facts; never includes record contents."""
    from .sources import enabled_discovery_sources, quality_gate_open

    return [
        ("version", __version__),
        ("python", platform.python_version()),
        ("platform", f"{platform.system()} {platform.release()}"),
        ("tkinter", _tk_status()),
        ("database", _database_status()),
        ("source quality gate", "open" if quality_gate_open() else "closed"),
        ("enabled discovery sources", str(len(enabled_discovery_sources()))),
    ]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m career_agent",
        description="Open the offline AI Career Agent desktop workspace.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the installed version and exit.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help=(
            "Print environment and database-location facts without starting the app. "
            "No record contents are printed, and nothing is created."
        ),
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
    if args.diagnostics:
        for key, value in diagnostics():
            print(f"{key}: {value}")
        return 0
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
