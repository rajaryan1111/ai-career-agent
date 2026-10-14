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
from typing import Iterable
import os
import re
import sqlite3

from .store import (
    PrivateWriteError, SchemaMigrationError, SchemaTooNewError, UnrecognisedDatabaseError,
    write_private_text_file,
)

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


def _is_substitutable_path(value: str) -> bool:
    """True when replacing this text cannot damage unrelated prose.

    ``Path("db.sqlite3").parent`` is the current folder, and its text is the single character ".":
    substituting that would replace every dot in the message and leave something unreadable (for
    example "schema version 2.0" became "schema version 2<placeholder>0"). A bare relative name
    such as "data" would likewise be replaced wherever it appears as an ordinary word. Only an
    absolute path, or a path that carries a separator, is a location rather than a word.
    """
    if not value or value in (".", ".."):
        return False
    return Path(value).is_absolute() or "/" in value or "\\" in value


def _path_replacements(value: str | Path, placeholder: str) -> list[tuple[str, str]]:
    """(text, placeholder) pairs that hide one path, longest first at the call site.

    The folder is only hidden when it is itself a location (absolute), so a relative folder name
    cannot be replaced inside ordinary words. A relative file name is still hidden when it looks
    like a file name, because the person's choice of file name is theirs to keep private.
    """
    text = str(value)
    pairs: list[tuple[str, str]] = []
    if _is_substitutable_path(text):
        pairs.append((text, placeholder))
    elif "/" not in text and "\\" not in text and "." in Path(text).name:
        pairs.append((text, placeholder))
    parent = str(Path(text).parent)
    if Path(parent).is_absolute() and _is_substitutable_path(parent):
        pairs.append((parent, placeholder))
    return pairs


#: Shapes of an *absolute* location that can appear inside text this module did not write - the message
#: of an unexpected exception, for instance, which the caller cannot enumerate in advance. The quoted
#: form may contain spaces (this is how Python formats a path in ``FileNotFoundError`` and friends); a
#: bare form may not, because a space would turn ordinary prose into part of the match. A URL is never
#: a match: it names a public address rather than a location on this machine, and hiding it would lose
#: the one piece of information that diagnoses a link problem. A bare relative word is never a match
#: either, which is what keeps a folder name such as ``data`` out of ordinary sentences.
_ABSOLUTE_LOCATION_PATTERNS = (
    re.compile(r"""(?P<quote>['"])(?P<path>(?:/|[A-Za-z]:[\\/]|\\\\)[^'"\n]*)(?P=quote)"""),
    re.compile(
        r"(?<![\w:/<>\"'])"
        r"(?:/[^\s/<>\"'|]+)+(?: [^\s/<>\"'|]+(?:/[^\s/<>\"'|]+)+)*/?"
        r"|(?<![\w:])(?:[A-Za-z]:[\\/]|\\\\)(?:[^\s\\/<>\"'|]+[\\/]?)+"
    ),
)

#: Punctuation that ends a sentence rather than a file name. Trimmed from a match so that
#: "cannot open /Volumes/X/notes.sqlite3." keeps its full stop.
_TRAILING_PUNCTUATION = ".,;:)]}"


def _replace_location(match: re.Match) -> str:
    if "path" in match.groupdict():  # the quoted form: keep the quotes, hide the location inside
        return match.group(0).replace(match.group("path"), "<local path>")
    token = match.group(0)
    trailing = ""
    while token and token[-1] in _TRAILING_PUNCTUATION:
        trailing = token[-1] + trailing
        token = token[:-1]
    return "<local path>" + trailing if token else match.group(0)


def _hide_undeclared_locations(text: str) -> str:
    """Hide absolute locations in ``text`` that no caller named, so nothing can smuggle one through.

    The declared locations are handled first (they get the more informative placeholders, and the
    home folder is a prefix of most of them). This sweep is the safety net for a location that only
    appears in the failure text itself: without it, a message quoting a path from somewhere else on
    the machine - an external volume, a sync folder - would be copied verbatim into a note that is
    written to be safe to share.
    """
    redacted = text
    for pattern in _ABSOLUTE_LOCATION_PATTERNS:
        redacted = pattern.sub(_replace_location, redacted)
    return redacted


def redact_paths(
    text: str,
    *,
    database_path: str | Path | None = None,
    home: Path | None = None,
    extra_paths: Iterable[str | Path] = (),
) -> str:
    """Replace filesystem locations in ``text`` with neutral placeholders.

    Replaces the longest paths first (the database file, then its folder, then the user's home
    folder) so a nested path cannot survive by being a prefix of another replacement. The default
    database file name is kept because it names a product file, not a location.

    Afterwards, any remaining *absolute* location is replaced with a neutral placeholder. This
    supersedes the earlier rule of leaving unsupplied paths alone: a caller cannot list every location
    an unexpected failure message might quote, and the note this text ends up in is written to be safe
    to share. Relative words are still never touched, and neither are public URLs.

    ``extra_paths`` covers locations this module cannot know about - a file the person named on the
    command line, for instance - so that a failure reported about such a file cannot write that
    location into a note meant to be safe to share.
    """
    resolved_home = Path.home() if home is None else Path(home)
    replacements: list[tuple[str, str]] = []
    if database_path is not None:
        database = Path(database_path)
        if database.name != _DEFAULT_DATABASE_NAME:
            replacements.extend(_path_replacements(database, "<database file>"))
        replacements.extend(_path_replacements(database.parent, "<application data folder>"))
    for extra in extra_paths:
        replacements.extend(_path_replacements(extra, "<local path>"))
    replacements.extend(_path_replacements(resolved_home, "<home folder>"))
    redacted = text
    for value, placeholder in sorted(replacements, key=lambda item: -len(item[0])):
        redacted = redacted.replace(value, placeholder)
    return _hide_undeclared_locations(redacted)


def _truncate(text: str) -> str:
    if len(text) <= MAX_DIAGNOSTIC_LENGTH:
        return text
    return text[: MAX_DIAGNOSTIC_LENGTH - 3].rstrip() + "..."


def _explain_database_open_failure(exc: BaseException, database_path: str | Path | None) -> str | None:
    """Explain a database that SQLite could not *open*, when the cause is the location itself.

    Reached only when SQLite's own message is "unable to open database file", which is what it reports
    when the file cannot be created or opened at all - as opposed to a file that exists and is not a
    database ("file is not a database", handled separately below). The distinction matters because the
    two need opposite advice. Reported verbatim from a real run: starting the app with a database path
    inside a folder that did not exist produced "The local database could not be read ... it may be
    damaged" and told the person to rename or restore a file that was never there.

    The three causes that can be told apart here are the location's own: the folder does not exist, the
    path is itself a folder, or the folder is not writable by this account. Nothing is created, moved,
    renamed or tested destructively - only ``Path.is_dir`` and ``os.access`` are consulted - and no
    filesystem location is ever put into the message. Returns ``None`` when the folder looks usable, so
    the caller keeps its existing explanation for a file that is present but unreadable.
    """
    if not isinstance(exc, sqlite3.Error) or "unable to open database file" not in str(exc).lower():
        return None
    if database_path is None:
        return None  # no path to inspect: claiming a cause here would be a guess
    target = Path(database_path)
    try:
        parent = target.parent
        parent_missing = not parent.is_dir()
        target_is_folder = parent.is_dir() and target.is_dir()
        parent_unwritable = parent.is_dir() and not os.access(parent, os.W_OK)
    except OSError:
        return None  # the check itself failed: report the original failure rather than a guess
    if parent_missing:
        return (
            "The application could not create or open the local database because the folder that is "
            "meant to hold it does not exist, so the application did not start. Nothing was created "
            "and nothing was uploaded.\n\n"
            "Create that folder and start the app again, or point the app at a database inside a "
            "folder that already exists: python -m career_agent --database PATH"
        )
    if target_is_folder:
        return (
            "The application could not open the local database because the path it was given is "
            "itself a folder, so the application did not start. Nothing was created and nothing was "
            "uploaded.\n\n"
            "Give the app a file path inside a folder: python -m career_agent --database PATH"
        )
    if parent_unwritable:
        return (
            "The application could not create or open the local database because the folder that "
            "holds it is not writable by your account, so the application did not start. Nothing was "
            "written and nothing was uploaded.\n\n"
            "Check that you can write to your own application-data folder (or to the folder you "
            "passed with --database), then start the app again."
        )
    return None


def describe_startup_failure(
    exc: BaseException,
    *,
    database_path: str | Path | None = None,
    extra_paths: Iterable[str | Path] = (),
) -> str:
    """Explain a start-up failure in plain language, with a next step and no sensitive detail.

    Known failures get a specific explanation; anything else keeps only the exception type and a
    redacted message, so an unexpected error is still reported honestly rather than hidden.
    """
    detail = redact_paths(
        f"{type(exc).__name__}: {exc}".strip(), database_path=database_path, extra_paths=extra_paths
    )
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
    location_problem = _explain_database_open_failure(exc, database_path)
    if location_problem is not None:
        return location_problem
    if isinstance(exc, sqlite3.DatabaseError):
        return (
            "The local database could not be read, so the application did not start. It may be "
            "damaged, or it may be a different kind of file. Your data is still on disk and was not "
            f"modified by this attempt.\n\nSQLite reported: {message}\n\n"
            f"{_RECOVERY_HINT}. If no backup is available, rename or move the unreadable database "
            "file and start again: the app will create a new empty database and leave the old file "
            "for you to inspect."
        )
    if isinstance(exc, SchemaMigrationError):
        # The store already worked out what the database is at now; this adds what to do about it
        # without repeating the version numbers as if they were the whole story.
        return (
            "The local database could not be updated to the schema version this app expects, so the "
            f"application did not start.\n\n{message}\n\n"
            f"{_RECOVERY_HINT} The previous database is never deleted by this attempt: its file is "
            "still on disk exactly as it was."
        )
    if isinstance(exc, SchemaTooNewError):
        return (
            "The local database was written by a newer version of this application, so this version "
            f"did not open it.\n\n{message}\n\nNothing was changed and no downgrade was attempted. "
            "Update the application, or use the database commands (--backup-to, --restore-from) to "
            "work with a different file."
        )
    if isinstance(exc, UnrecognisedDatabaseError):
        return (
            "The file this app was pointed at is a database, but not one this application created, so "
            f"it was not opened or changed.\n\n{message}\n\nPoint the app at your own database file, "
            "or start it without --database to use the default location."
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
    extra_paths: Iterable[str | Path] = (),
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
        f"{describe_startup_failure(exc, database_path=database_path, extra_paths=extra_paths)}\n"
    )
    # The note is overwritten by the next failure, so the sequence is kept in the application log
    # as well: only the exception's type, because the note already holds the full explanation and the
    # log must stay one line per event without document or profile text in it.
    from .event_log import record_event  # local import: ``event_log`` reports *through* this module

    record_event(
        "startup.failed", detail=f"type={type(exc).__name__}",
        database_path=database_path, data_folder=data_folder, timestamp=stamp,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_private_text_file(path, body)
    except (OSError, ValueError):
        return None
    return path
