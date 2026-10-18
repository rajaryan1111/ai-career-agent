"""What this application did: a bounded, redacted, local record only the person can read.

The start-up note in :mod:`career_agent.diagnostics` explains *one* failed launch and is overwritten
each time, so it cannot answer "when did my database change?" or "did that backup actually run?". This
module keeps that sequence: one line per event, appended in order, bounded in size, and written beside
the database it describes.

Four rules, each of which is a test:

* **One line per event.** A detail is collapsed to a single line, so a value that contains newline
  characters cannot forge a second event or break a reader that parses line by line. The timestamp and
  the event name come first, and ``detail=`` is always the last field, so
  ``line.split(" event=", 1)[1].split(" ", 1)`` reads the name no matter what a detail contains.
* **Never candidate content.** Callers pass an event name plus an identifier, a count, or a category.
  Profile values, résumé text, evidence text and URLs are not events. Every detail is passed through
  :func:`career_agent.diagnostics.redact_paths` first, so a local location cannot reach a file that is
  meant to be safe to share.
* **Bounded.** The file is rotated once it would pass :data:`MAX_LOG_BYTES`, and a single previous file
  is kept, so the logs folder can never grow without limit on a machine this runs on for years.
* **Owner-only, and never in the way.** Where the platform supports POSIX permissions the file is
  owner-only, and a logging failure is reported by returning ``None`` rather than by raising: a full
  disk must not stop the application from saving a job.

This module is Tk-free and imports nothing that can reach the network. It never writes anywhere except
the ``logs`` folder beside the database it is told about, and it does not create that folder unless an
event is actually recorded.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from .diagnostics import redact_paths
from .store import PrivateWriteError, append_private_text_file

#: The log rotates when a line would push the file past this size, so the logs folder holds at most
#: roughly twice this much: the current file plus the one previous file. 256 KiB is thousands of lines,
#: which is far more than anyone reads, and small enough that it can never matter on a full disk.
MAX_LOG_BYTES = 256 * 1024

#: One detail keeps at most this many characters. A detail is a note for a human, not a data dump.
MAX_DETAIL_LENGTH = 200

LOG_FILE_NAME = "application.log"

#: The one previous file kept when the log rotates.
PREVIOUS_LOG_FILE_NAME = f"{LOG_FILE_NAME}.1"

#: Event names are lower-case words separated by dots (``job.saved``, ``backup.refused``). The shape is
#: checked rather than documented only, because a malformed name would make the log unparseable exactly
#: when someone is trying to read it.
EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+$")

#: Every event this application records, so the vocabulary is one list rather than a set of string
#: literals scattered through the code. ``tests/test_event_log.py`` reads the shipped source and fails
#: if a name is used that is not here, which keeps the log readable by whoever has to read it.
EVENTS: tuple[str, ...] = (
    "app.started",
    "app.stopped",
    "startup.failed",
    "database.opened",
    "database.migrated",
    "database.migration_failed",
    "database.upgrade_snapshot",
    # The profile, and where its facts came from. ``profile.saved`` carries a count and the origin of the
    # facts the write recorded - a field name, never a value - and ``profile.fact_confirmed`` carries the
    # fact's own name, which is what a person confirmed: the value they were looking at never reaches the
    # log.
    "profile.saved",
    "profile.deleted",
    "profile.fact_confirmed",
    "job.saved",
    "job.deleted",
    "tracker.saved",
    "activity.added",
    "activity.deleted",
    # Preparation items and interview rounds: the work around an application. Both are the person's own
    # notes, and neither can move an application's status - the events say what was recorded, never that
    # anything was decided.
    "preparation.added",
    "preparation.completed",
    "preparation.reopened",
    "preparation.deleted",
    "interview.recorded",
    "interview.outcome",
    "interview.deleted",
    # The candidate's own history: employment and study records. The first word is ``history`` because an
    # event name's first segment may not contain an underscore, and both kinds belong to one namespace.
    "history.work_added",
    "history.work_updated",
    "history.work_deleted",
    "history.education_added",
    "history.education_updated",
    "history.education_deleted",
    "resume.proposed",
    "resume.failed",
    "export.written",
    "export.failed",
    "import.written",
    "import.refused",
    "import.failed",
    # The imported HR contact list: one event per import that committed, one per change to a stored
    # contact's do-not-contact mark, one per contact the person deleted, and one per export of the stored
    # list and per export this build refused. Counts and a flag only - an event never carries an address,
    # a name, a company, the note a person typed beside a mark, or the name of a file somebody chose.
    "contacts.imported",
    "contacts.suppressed",
    "contacts.deleted",
    "contacts.exported",
    "contacts.export.failed",
    # The versioned role strategies: one event per strategy written, revised or deleted. The identifier
    # is generated (never typed) and the version is a number; the strategy's own content - its name, the
    # places, the employers ruled out - is the person's data and never reaches the log.
    "strategy.created",
    "strategy.revised",
    "strategy.deleted",
    "backup.written",
    "backup.refused",
    "restore.completed",
    "restore.refused",
    # The background scheduler: what it was told to do, what it did, and who was allowed to do it.
    "task.scheduled",
    "task.deleted",
    "task.run_started",
    "task.run_succeeded",
    "task.run_failed",
    "task.run_refused",
    "task.run_interrupted",
    "worker.lease_taken",
    "worker.lease_refused",
    "worker.lease_released",
)

#: Characters that would break the one-line-per-event rule, or that a terminal could act on.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]+")

#: Database "paths" that are not files: an in-memory database has no folder to keep a log in.
_NON_FILE_LOCATIONS = (":memory:", "")


def log_folder(database_path: str | Path | None = None, *, data_folder: str | Path | None = None) -> Path:
    """Where the log belongs: a ``logs`` folder beside the database, or beside an explicit folder.

    Nothing is created here. The location follows the database rather than a global constant so that a
    database on an external or backed-up volume takes its own history with it. When no location is
    known at all - a failure before the database path is resolved - the per-user application-data
    folder is used, never the current working directory: a relative folder would follow whatever
    directory the application happened to be started from, which for a desktop launch is not something
    anyone chose.
    """
    if data_folder is not None:
        return Path(data_folder) / "logs"
    if database_path is None:
        from .desktop_logic import default_data_folder  # local import: keeps this module import-light

        return default_data_folder() / "logs"
    return Path(database_path).parent / "logs"


def log_path(database_path: str | Path | None = None, *, data_folder: str | Path | None = None) -> Path:
    """The current log file's path, whether or not it exists yet."""
    return log_folder(database_path, data_folder=data_folder) / LOG_FILE_NAME


def previous_log_path(database_path: str | Path | None = None, *, data_folder: str | Path | None = None) -> Path:
    """The path of the one previous log file kept when the current one rotates."""
    return log_folder(database_path, data_folder=data_folder) / PREVIOUS_LOG_FILE_NAME


def describe_line(event: str, *, detail: str | None = None, timestamp: datetime | None = None) -> str:
    """The single line that records one event, without writing it.

    Exposed so the formatting rules - one line, capped length, redacted locations - can be tested and
    read on their own, and so a caller that only wants to show the line does not have to write a file.
    Raises ``ValueError`` for an event name that is not of the documented shape: that is a programming
    error in this application, not a condition a user can be in, and it must be caught while developing
    rather than shipped as an unreadable log.
    """
    if not EVENT_NAME_PATTERN.fullmatch(event):
        raise ValueError(
            f"{event!r} is not an event name of the form 'word.word': lower-case letters, digits and "
            "underscores, at least two words separated by dots."
        )
    stamp = datetime.now(timezone.utc) if timestamp is None else timestamp
    line = f"{stamp.isoformat(timespec='seconds')} event={event}"
    if detail:
        line = f"{line} detail={_clean_detail(detail)}"
    return line


def _clean_detail(detail: str) -> str:
    """One single line of redacted, capped text: the only form a detail can take in the log."""
    flattened = " ".join(_CONTROL_CHARACTERS.sub(" ", str(detail)).split())
    redacted = redact_paths(flattened)
    if len(redacted) > MAX_DETAIL_LENGTH:
        return f"{redacted[:MAX_DETAIL_LENGTH]}... (truncated)"
    return redacted


def record_event(
    event: str,
    *,
    detail: str | None = None,
    database_path: str | Path | None = None,
    data_folder: str | Path | None = None,
    timestamp: datetime | None = None,
) -> Path | None:
    """Append one event to the log; return the file it went to, or ``None`` if it could not be written.

    The only condition that raises is an event name of the wrong shape (a bug in this application).
    Everything else - a read-only folder, a full disk, a permissions model that refuses owner-only
    files, a database that is not a file at all - is reported by returning ``None``, because failing to
    write a log entry must never fail the operation it was describing.
    """
    line = describe_line(event, detail=detail, timestamp=timestamp)
    if _not_a_file(database_path, data_folder):
        return None
    path = log_path(database_path, data_folder=data_folder)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(path, len(line.encode("utf-8")))
        return append_private_text_file(path, f"{line}\n")
    except (OSError, PrivateWriteError, ValueError):
        # Deliberately swallowed and reported as ``None``: the caller carries on, and the failure
        # itself is visible to whoever looks at the logs folder (nothing new appears in it).
        return None


def _not_a_file(database_path: str | Path | None, data_folder: str | Path | None) -> bool:
    """Whether this location has no folder that could hold a log file."""
    if data_folder is not None:
        return False
    if database_path is None:
        return False
    text = str(database_path).strip()
    return text in _NON_FILE_LOCATIONS or text.startswith("file:")


def _rotate_if_needed(path: Path, incoming_bytes: int) -> None:
    """Move the current log to the one previous file when the next line would pass the size bound.

    Rotating *before* the write keeps the bound on the current file hard, and keeping exactly one
    previous file keeps the bound on the folder: the oldest lines are discarded rather than the log
    growing forever. A rotation that fails (a read-only folder, a file another program holds open on
    Windows) leaves the current file untouched and the caller's write fails on its own terms.
    """
    try:
        current_size = path.stat().st_size
    except OSError:
        return
    if current_size + incoming_bytes <= MAX_LOG_BYTES:
        return
    os.replace(path, path.with_name(PREVIOUS_LOG_FILE_NAME))


def read_lines(
    *,
    database_path: str | Path | None = None,
    data_folder: str | Path | None = None,
    limit: int = 50,
    include_previous: bool = True,
) -> tuple[str, ...]:
    """The most recent log lines, oldest first, for a person to read; ``()`` when there is no log.

    Read-only and quiet: a missing file, an unreadable one, or a line that is not valid UTF-8 is
    reported as "nothing to show" rather than as a failure, because this backs a diagnostics view whose
    whole purpose is to still be usable when something else has gone wrong.
    """
    if limit <= 0 or _not_a_file(database_path, data_folder):
        return ()
    folders = log_folder(database_path, data_folder=data_folder)
    names = [LOG_FILE_NAME, PREVIOUS_LOG_FILE_NAME] if include_previous else [LOG_FILE_NAME]
    lines: list[str] = []
    for name in names:
        try:
            text = (folders / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines.extend(line for line in text.splitlines() if line.strip())
    return tuple(lines[-limit:])
