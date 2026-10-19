"""Where the application keeps its data, and how that choice is made.

One place decides the database path, so the desktop window, the command line and the diagnostics
report can never disagree about which file is in use. The rules are deliberately few:

1. an explicit path (``--database``) wins;
2. otherwise ``CAREER_AGENT_DATABASE``, which must hold an absolute path;
3. otherwise ``<data folder>/career_agent.sqlite3``.

The data folder is ``CAREER_AGENT_HOME`` followed by the application's own folder name when that
variable holds an absolute path, and the platform's per-user application-data folder otherwise (see
:func:`career_agent.desktop_logic.career_agent_data_root`).

A *relative* value in either variable is ignored rather than resolved against the working directory:
the person's profile and history would otherwise appear to move between launches depending on where
the app was started from. Ignored settings are not hidden - :meth:`Settings.notes` carries an
explanation, and ``python -m career_agent --doctor`` prints it.

This module only decides paths. It creates no directories, opens no database and writes nothing, so
it is safe to call from the doctor, from tests, and before any decision has been made.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .desktop_logic import (
    CAREER_AGENT_HOME_ENV, DATABASE_FILE_NAME, default_data_folder, default_database_path,
)

#: An absolute path to the database file this run should use. Takes precedence over the default
#: location; ``--database`` takes precedence over this.
DATABASE_ENV = "CAREER_AGENT_DATABASE"

#: Shown by the doctor and in error messages, so the reason a path was chosen is never a mystery.
SOURCE_COMMAND_LINE = "the --database option"
SOURCE_ENVIRONMENT = f"the {DATABASE_ENV} setting"
SOURCE_DEFAULT = "the default location"


@dataclass(frozen=True)
class Settings:
    """The resolved paths for one run, plus anything the person should know about the choice."""

    #: Where a database, its logs folder and its backups go when no path is given, and the folder the
    #: application's own folder is created in.
    default_data_folder: Path
    #: The database this run will use.
    database_path: Path
    #: Which rule chose ``database_path`` (one of the ``SOURCE_*`` constants).
    database_source: str
    #: Settings that were supplied but ignored, with the reason. Never silently dropped.
    notes: tuple[str, ...] = ()

    @property
    def uses_default_location(self) -> bool:
        return self.database_source == SOURCE_DEFAULT


def resolve_settings(
    *,
    database_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    system: str | None = None,
) -> Settings:
    """Resolve the paths for this run without touching the filesystem.

    ``database_path`` is what a caller was given explicitly (``--database``). Everything else comes
    from the environment, then from the platform defaults. No directory is created and no file is
    read, so a caller can report what *would* be used before deciding to use it.
    """
    environment = os.environ if environ is None else environ
    notes: list[str] = []
    folder = default_data_folder(system=system, environ=environment, home=home)

    chosen: Path | None = None
    source = SOURCE_DEFAULT
    if database_path is not None and str(database_path).strip():
        chosen = Path(database_path).expanduser()
        source = SOURCE_COMMAND_LINE
    else:
        supplied = (environment.get(DATABASE_ENV) or "").strip()
        if supplied:
            candidate = Path(supplied).expanduser()
            if candidate.is_absolute():
                chosen, source = candidate, SOURCE_ENVIRONMENT
            else:
                notes.append(
                    f"{DATABASE_ENV} was ignored because it is not an absolute path; a relative path "
                    "would point at a different file depending on the folder the app was started from."
                )
    if chosen is None:
        chosen = folder / DATABASE_FILE_NAME

    # A relative data root is ignored inside ``career_agent_data_root``; say so here rather than
    # letting the person wonder why their setting had no effect.
    supplied_home = (environment.get(CAREER_AGENT_HOME_ENV) or "").strip()
    if supplied_home and not Path(supplied_home).expanduser().is_absolute():
        notes.append(
            f"{CAREER_AGENT_HOME_ENV} was ignored because it is not an absolute path; the platform's "
            "per-user application-data folder is used instead."
        )

    return Settings(
        default_data_folder=folder, database_path=chosen, database_source=source, notes=tuple(notes),
    )


def database_path_for_run(
    database_path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    system: str | None = None,
) -> Path:
    """The database this run should open, with the default folder created if it is not there.

    Creating that one folder is deliberate: SQLite cannot open a database inside a folder that does
    not exist, so without it a first run would fail before the window could appear; the folder is
    where the app keeps its own files and is the only place this application creates unasked. A path
    that was named explicitly - on the command line or in ``CAREER_AGENT_DATABASE`` - is used exactly
    as given and no folders are created for it, so a mistyped path reports a missing directory instead
    of quietly becoming a real one.
    """
    settings = resolve_settings(database_path=database_path, environ=environ, home=home, system=system)
    if settings.uses_default_location:
        # ``desktop_logic.default_database_path`` names the same default and is the function that
        # creates the folder, so delegating leaves one implementation of that side effect instead of
        # two that could drift apart.
        return default_database_path(environ=environ, home=home, system=system)
    return settings.database_path


def describe_settings(settings: Settings) -> tuple[str, ...]:
    """The settings as lines to show a person, including why the database path was chosen."""
    lines = [
        f"Database: {settings.database_path}",
        f"          chosen by {settings.database_source}",
        f"Application data folder: {settings.default_data_folder}",
    ]
    if settings.uses_default_location:
        lines.append(
            "          (set " + CAREER_AGENT_HOME_ENV + " to an absolute folder to keep the app's "
            "files somewhere else, or pass --database for one run)"
        )
    lines.extend(f"Note: {note}" for note in settings.notes)
    return tuple(lines)
