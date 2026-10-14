"""Non-sensitive startup diagnostics: what went wrong, what to do, and nothing more.

A start-up failure is the one moment the app cannot show its own interface, so the message has to
carry the whole explanation. It must stay useful without exposing candidate data, database
contents, credentials, or filesystem locations: this module classifies the failure, redacts the
local paths out of whatever text remains, and can append the same redacted text to one bounded
local note the person can read later. It is Tk-free and dependency-free on purpose, so the desktop
window, the command line, and the tests all share one implementation.

Nothing here sends anything anywhere, and nothing here changes or repairs a database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .store import PrivateWriteError, write_private_text_file

#: One diagnostic keeps at most this many characters, so a pathological exception text cannot grow
#: the note without bound. Enough for a real message plus the recovery instructions.
MAX_DIAGNOSTIC_LENGTH = 600

#: File name of the bounded local note written when the app cannot start.
DIAGNOSTIC_FILE_NAME = "startup-diagnostics.log"

#: The default database file name is a product constant, not a user-specific location, so it may
#: stay visible; anything else is reduced to a placeholder.
_DEFAULT_DATABASE_NAME = "career_agent.sqlite3"

_RECOVERY_HINT = (
    "Nothing was uploaded and the local database file was not modified by this attempt. "
    "If you have a verified backup, restore it from a terminal with "
    "python -m career_agent --restore-from \"<backup file>\" --yes"
)


def redact_paths(text: str, *, database_path: str | Path | None = None, home: Path | None = None) -> str:
    """Replace filesystem locations in ``text`` with neutral placeholders.

    Replaces the longest paths first (the database file, then its folder, then the user's home
    folder) so a nested path cannot survive by being a prefix of another replacement. The default
    database file name is kept because it names a product file, not a location.
    """
    resolved_home = Path.home() if home is None else Path(home)
    replacements: list[tuple[str, str]] = []
    if database_path is not None:
        database = Path(database_path)
        if database.name != _DEFAULT_DATABASE_NAME:
            replacements.append((str(database), "<database file>"))
        replacements.append((str(database.parent), "<application data folder>"))
    replacements.append((str(resolved_home), "<home folder>"))
    redacted = text
    for value, placeholder in sorted(replacements, key=lambda item: -len(item[0])):
        if value:
            redacted = redacted.replace(value, placeholder)
    return redacted


def _truncate(text: str) -> str:
    if len(text) <= MAX_DIAGNOSTIC_LENGTH:
        return text
    return text[: MAX_DIAGNOSTIC_LENGTH - 3].rstrip() + "..."


def describe_startup_failure(exc: BaseException, *, database_path: str | Path | None = None) -> str:
    """Explain a start-up failure in plain language, with a next step and no sensitive detail.

    Known failures get a specific explanation; anything else keeps only the exception type and a
    redacted message, so an unexpected error is still reported honestly rather than hidden.
    """
    detail = redact_paths(f"{type(exc).__name__}: {exc}".strip(), database_path=database_path)
    message = _truncate(detail)
    if isinstance(exc, ModuleNotFoundError) or (isinstance(exc, ImportError) and "tkinter" in str(exc).lower()):
        return (
            "The desktop window needs Tkinter, which this Python installation does not provide. "
            "Install your platform's Tk package (for example python3-tk on Debian/Ubuntu) and start "
            "the app again. The database commands (--backup-to, --restore-from) work without it."
        )
    if type(exc).__name__ == "TclError":
        return (
            "The desktop window could not be opened because no display is available in this "
            "session. Run the app from a graphical session, or use the database commands "
            "(--backup-to, --restore-from) which need no display."
        )
    if isinstance(exc, PrivateWriteError):
        return (
            "The application could not create or protect a file it needs, so it did not start. "
            f"{message}\n\nNothing was written and nothing was uploaded. Check that you can write to "
            "your own application-data folder, then try again."
        )
    if isinstance(exc, sqlite3.DatabaseError):
        return (
            "The local database could not be read, so the application did not start. It may be "
            "damaged, or it may be a different kind of file. Your data is still on disk and was not "
            f"modified by this attempt.\n\nSQLite reported: {message}\n\n"
            f"{_RECOVERY_HINT}. If no backup is available, rename or move the unreadable database "
            "file and start again: the app will create a new empty database and leave the old file "
            "for you to inspect."
        )
    if isinstance(exc, PermissionError):
        return (
            "A file the application needs could not be opened because permission was denied, so it "
            f"did not start.\n\n{message}\n\nNothing was uploaded. Check the permissions on your own "
            "application-data folder, then try again."
        )
    if isinstance(exc, OSError):
        return (
            "A local file operation failed, so the application did not start. This is usually a "
            f"full disk or a folder that cannot be written.\n\n{message}\n\nNothing was uploaded and "
            "no data was deleted."
        )
    return (
        f"The application stopped while starting up.\n\n{message}\n\n"
        "Nothing was uploaded. If this repeats, the note saved beside your local data folder "
        "records the same sanitised message."
    )


def diagnostic_log_path(database_path: str | Path | None = None, *, data_folder: str | Path | None = None) -> Path:
    """Where the bounded start-up note belongs: a ``logs`` folder beside the local data.

    No directory is created here; the note is only written when a failure actually happens.
    """
    if data_folder is not None:
        base = Path(data_folder)
    elif database_path is not None:
        base = Path(database_path).parent
    else:
        from .desktop_logic import default_data_folder  # local import: keeps this module import-light
        base = default_data_folder()
    return base / "logs" / DIAGNOSTIC_FILE_NAME


def record_startup_failure(
    exc: BaseException,
    *,
    database_path: str | Path | None = None,
    data_folder: str | Path | None = None,
    timestamp: datetime | None = None,
) -> Path | None:
    """Write one bounded, redacted note about the failure; return its path, or ``None`` on failure.

    Overwrites the previous note instead of appending, so repeated crashes cannot grow the file or
    bury the newest information. Writing uses the same owner-only primitive as the export and the
    database, and a failure to write is reported by returning ``None``: a diagnostic that cannot be
    saved must never itself stop the app from telling the person what happened.
    """
    stamp = datetime.now(timezone.utc) if timestamp is None else timestamp
    path = diagnostic_log_path(database_path, data_folder=data_folder)
    body = (
        f"AI Career Agent start-up note, {stamp.isoformat(timespec='seconds')}\n"
        f"{describe_startup_failure(exc, database_path=database_path)}\n"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_private_text_file(path, body)
    except (OSError, ValueError):
        return None
    return path
