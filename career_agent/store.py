"""Local persistence for AI Career Agent; storage is local and has no network code.

Holds the SQLite store and the owner-only file primitives shared with the desktop
export and with database backup/restore: one place decides what "owner-only" means and
what the schema contract is, so the database, exported candidate data and backup files
cannot drift apart.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from enum import Enum
from typing import Callable
import errno
import json
import os
import sqlite3
import uuid
from pathlib import Path

from .core import (
    validate_follow_up_date, validate_follow_up_note,
    INITIAL_APPLICATION_STATUS, ActivityKind, ApplicationActivity, ApplicationStatus,
    ApplicationTracker, Availability, CandidateProfile, EducationEntry, EmploymentType, InterviewMode,
    InterviewOutcome, InterviewRound, InterviewStage, JobListing, PreparationItem, PreparationKind,
    WorkHistoryEntry, duplicate_key, is_allowed_tracker_transition, require_confirmation_evidence,
    validate_activity_detail, validate_activity_date,
)
from .tasks import (
    RunState, ScheduledTask, TaskRun, TaskValidationError, WorkerLease, WorkerLeaseHeld,
    clean_detail, next_run_after, plan_after_run, slot_key,
)

_SCHEMA_VERSION = 6

#: Every schema version this build can open, with the tables that version leaves behind. The lists are
#: cumulative and explicit. ``career_agent.backup`` checks a candidate file against the tables of the
#: version that file *records*, not against the newest list, because a backup written by an older
#: build is restored as it is and updated when this build opens it. A drift test in
#: ``tests/test_backup.py`` compares the newest list with a freshly initialised database, so the
#: schema cannot grow without this contract being updated deliberately.
SCHEMA_TABLES_BY_VERSION = {
    1: ("application_tracker", "candidate_profile", "job_listings"),
    2: ("application_activity", "application_tracker", "candidate_profile", "job_listings"),
    3: ("application_activity", "application_tracker", "candidate_profile", "job_listings",
        "scheduled_task", "task_run", "worker_lease"),
    4: ("application_activity", "application_tracker", "candidate_profile", "job_listings",
        "scheduled_task", "task_run", "worker_lease"),
    5: ("application_activity", "application_preparation", "application_tracker", "candidate_profile",
        "interview_round", "job_listings", "scheduled_task", "task_run", "worker_lease"),
    6: ("application_activity", "application_preparation", "application_tracker", "candidate_education",
        "candidate_profile", "candidate_work_history", "interview_round", "job_listings",
        "scheduled_task", "task_run", "worker_lease"),
}
SCHEMA_VERSION = _SCHEMA_VERSION
SCHEMA_TABLES = SCHEMA_TABLES_BY_VERSION[_SCHEMA_VERSION]


def schema_tables(version: int) -> tuple[str, ...] | None:
    """The tables schema ``version`` holds, or ``None`` for a version this build does not know."""
    return SCHEMA_TABLES_BY_VERSION.get(version)

#: Owner read/write only: the database holds candidate PII and should not be group/world readable.
_OWNER_ONLY_MODE = 0o600

#: The single worker lease a database can have. One name, because "two schedulers over one database"
#: is exactly what the lease exists to prevent.
_LEASE_NAME = "scheduler"



def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso(value: datetime) -> str:
    """One instant in the form the scheduler columns hold: UTC, ISO-8601, second precision.

    Seconds are enough for a schedule and make the stored text sort chronologically, which is what
    lets "the next task that is due" be one indexed comparison instead of a table scan.
    """
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _instant_or_none(value: object, noun: str, field: str) -> datetime | None:
    """A stored instant, as an aware UTC datetime, or a named problem with the stored text."""
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise StoredRecordError(
            noun, f"its {field} time {value!r} is not a reading this version understands"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StoredRecordError(noun, f"its {field} time {value!r} carries no timezone offset")
    return parsed.astimezone(timezone.utc)


def _stored_int(value: object, noun: str, field: str) -> int:
    """One stored whole number, reported as a named problem when it is not one."""
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            return int(str(value))
        except (TypeError, ValueError) as exc:
            raise StoredRecordError(
                noun, f"its {field} is {value!r} rather than a whole number"
            ) from exc
    return value


class TrackerStatusError(ValueError):
    """A stored tracker status is not a value this build recognises.

    Raised from read paths instead of the bare ``ValueError`` an enum constructor produces, so a
    legacy or hand-edited value can be reported as itself. Nothing is repaired, migrated, or
    deleted: an unknown status has no defined position in the state machine, so no transition from
    it can be validated, and the app refuses to change such a record rather than guessing.
    """

    def __init__(self, raw_value: str) -> None:
        self.raw_value = raw_value
        super().__init__(
            f"The saved status {raw_value!r} is not one this version of the application recognises. "
            "The record was not changed. Read the value in the database or restore a verified backup "
            "if the record is wrong."
        )


class StaleTrackerRecord(ValueError):
    """A conditional tracker write matched no row: the record changed after it was read.

    Raised by :meth:`CareerStore.save_tracker` when ``expected`` no longer describes the stored row,
    which is the only reliable way to catch a change that the transition rules alone would allow
    (a forward move, new evidence, or a confirmation recorded while the caller was deciding). Nothing
    is written, so the newer data wins by default rather than being overwritten by a stale decision.
    """


class StoredRecordError(ValueError):
    """A stored record holds data this build cannot interpret.

    Raised from read paths instead of the ``KeyError``, ``TypeError``, ``AttributeError`` or
    ``json.JSONDecodeError`` a malformed payload would otherwise produce, so that a damaged or
    hand-edited record is reported as itself and can be handled like any other validation failure (it
    is a ``ValueError``). Nothing is repaired, migrated, rewritten, or deleted: the record stays exactly
    as stored, so the local backup/restore commands still work on the file and the user decides what to
    do about it.
    """

    def __init__(self, noun: str, detail: str) -> None:
        self.noun = noun
        self.detail = detail
        super().__init__(
            f"The saved {noun} could not be read ({detail}). It was not changed. Use the export tool or "
            "restore a verified backup if the record is wrong."
        )


class FollowUpWrite(str, Enum):
    """Whether a tracker write touches the follow-up plan the person recorded.

    A status change and a reminder are independent facts about the same application, and the row holds
    both. Writing the whole row from a tracker object made a status update silently clear the plan,
    because the object a caller built from a status alone carries no day. So the default,
    :attr:`KEEP`, means "this save is not about the reminder": a stored plan stays as it is.

    ``WRITE`` says "use the plan on this tracker", including clearing it - a planless tracker written
    with ``WRITE`` removes the stored day, which is why :meth:`CareerStore.clear_follow_up` exists.
    Under ``KEEP``, a tracker that carries a plan is stored when the row had none, and a plan that
    *differs* from a stored one raises instead of winning quietly: the caller either meant it or did not
    notice the stored reminder, and guessing would lose or invent a day.
    """

    KEEP = "keep"
    WRITE = "write"


class TaskRunConflict(ValueError):
    """A run cannot be changed the way the caller asked - it is missing, or already finished.

    Raised when a finish or a heartbeat does not match a run that is still running, which is what a
    second worker, a restarted process, or a duplicate claim looks like from the store's side. Nothing
    is written: the first outcome is the real one, and a later writer overwriting it would turn a
    record of what happened into a record of what somebody guessed afterwards.
    """


class StoreUnavailable(sqlite3.Error):
    """The store cannot be used at all, so no read or write may be attempted through it.

    Raised when a connection is replaced by :class:`UnavailableStore` after the database could not be
    reopened (a restore that finished but left a file this process cannot open). It subclasses
    ``sqlite3.Error`` deliberately: every caller that already reports a database failure reports this
    one too, with the reason attached, instead of letting a raw ``ProgrammingError`` escape a Tk
    callback and appear as a traceback.
    """


class UnavailableStore:
    """Stands in for :class:`CareerStore` when the database cannot be opened.

    Kept deliberately tiny: it answers ``close()`` so shutdown stays safe, and refuses every other
    use with :class:`StoreUnavailable` and the reason the reopen failed. Without it the closed
    connection stayed in place, so the next action raised ``ProgrammingError: Cannot operate on a
    closed database`` - a message that describes the symptom, not the cause, and not the fix.
    """

    def __init__(self, database_path: str | Path, reason: str) -> None:
        # Both are plain attributes: the window shows the path and the reason, and neither read may
        # fail just because nothing is open.
        self.database_path = str(database_path)
        self.reason = reason

    def close(self) -> None:
        """Nothing is open; closing twice must stay safe (the window close handler calls this)."""
        return None

    def __getattr__(self, name: str):
        # Only reached for attributes this class does not define, so ``close``/``reason`` above are
        # unaffected. Every store method becomes an honest refusal rather than an AttributeError.
        def refuse(*_args, **_kwargs):
            raise StoreUnavailable(
                f"The local database could not be opened ({self.reason}). Restart the application "
                f"once the problem is resolved; this window cannot read or write "
                f"{Path(self.database_path).name}."
            )

        return refuse


class SchemaTooNewError(RuntimeError):
    """The file records a schema version newer than this build understands.

    A distinct type so callers can say "update the application" instead of guessing from a message.
    Nothing is written and no downgrade is attempted.
    """

    def __init__(self, version: int, supported: int) -> None:
        self.version = version
        self.supported = supported
        super().__init__(
            f"Database schema {version} is newer than supported schema {supported}. Update the "
            "application; this version cannot read that database and did not modify it."
        )


class UnrecognisedDatabaseError(RuntimeError):
    """The file holds tables but records no schema version, so this application did not write it.

    Adopting it would add this application's tables to somebody else's file. The file is left exactly
    as it was.
    """


class SchemaMigrationError(RuntimeError):
    """A schema upgrade step failed; the database is left at the version that step started from.

    The failure is reported as itself rather than as a raw SQLite error, because what the person
    needs to know is which database they should be looking at and whether their data survived. The
    version is re-read after the rollback and carried in the message, so the claim "nothing changed"
    is only made when the database actually says so.
    """

    def __init__(self, target_version: int, description: str, from_version: int,
                 observed_version: int | None, cause: BaseException) -> None:
        self.target_version = target_version
        self.description = description
        self.from_version = from_version
        self.observed_version = observed_version
        self.cause = cause
        if observed_version is None:
            state = "The database's recorded schema version could not be read back afterwards."
            advice = (
                "Do not keep using this database. Restore a verified backup "
                "(python -m career_agent --restore-from PATH --yes) and report this message."
            )
        elif observed_version == from_version:
            state = f"The step was rolled back, so the database is still at schema version {from_version}."
            advice = (
                "Your data was not changed. Restore a verified backup if the app cannot start, or keep "
                "this message and the sanitised start-up note for whoever is helping you."
            )
        else:
            state = (
                f"The database now records schema version {observed_version} rather than {from_version}, "
                "so the step may have been applied only in part."
            )
            advice = (
                "Do not keep using this database. Restore a verified backup "
                "(python -m career_agent --restore-from PATH --yes) before anything else."
            )
        super().__init__(
            f"The database could not be updated to schema version {target_version} ({description}). "
            f"{state} SQLite reported: {cause}. {advice}"
        )


class SchemaUpgradeRefused(RuntimeError):
    """An update was stopped before it started because no safety copy of the database could be written.

    A step that fails is rolled back whole (see :class:`SchemaMigrationError`), but a rollback is not a
    backup: a step can be applied, committed, and only *then* found to have been the wrong step, and a
    disk that fills while a copy is being taken is not something a transaction can help with. The
    database is therefore copied first, and if that copy cannot be made the update does not begin. The
    message says which versions are involved and that nothing was changed, because that is what a person
    needs in order to decide between freeing space, copying the file by hand, or restoring a backup.
    """

    def __init__(self, target_version: int, from_version: int, cause: BaseException) -> None:
        self.target_version = target_version
        self.from_version = from_version
        self.cause = cause
        super().__init__(
            f"The database was not updated from schema version {from_version} to version "
            f"{target_version} because a safety copy of it could not be written first ({cause}). "
            "Nothing was changed: the database is still at schema version "
            f"{from_version}. Free some space or check that the folder is writable, then try again - "
            "or make a copy of the database file yourself and update a copy of it."
        )


class PrivateWriteError(OSError):
    """A private (owner-only) file write could not be completed safely.

    An ``OSError`` subclass so callers that already handle file errors keep working; the message is
    written to be shown to the user as-is.
    """


def _apply_owner_only_mode(target: int | str) -> bool:
    """Apply the owner-only mode to a descriptor or path; return False if the OS refuses.

    A descriptor (used when writing new files) is preferred where available because it cannot be
    redirected by swapping the path, but the path form is kept for existing callers.
    """
    try:
        if isinstance(target, int):
            os.fchmod(target, _OWNER_ONLY_MODE)
        else:
            os.chmod(target, _OWNER_ONLY_MODE)
    except OSError:
        return False
    return True


def _restrict_to_owner(path: str) -> bool:
    """Make the database file owner-only where the platform supports it.

    Best effort and non-fatal: an OS or filesystem that refuses the change (or Windows, where the
    POSIX mode bits are not meaningful) leaves storage working exactly as before. This is a
    defence-in-depth measure, not an access-control guarantee: SQLite's own ``-wal``/``-shm``/
    ``-journal`` side files and the containing directory are outside this function's scope.

    Concept adapted from Agent-Reach's owner-only config handling (MIT License, Copyright (c) 2025
    Agent Eyes): https://github.com/Panniantong/Agent-Reach, ``agent_reach/config.py``.
    """
    return _apply_owner_only_mode(path)


def _symlink_refusal(target: Path) -> PrivateWriteError:
    """The refusal used whenever a write would be redirected through a symbolic link."""
    return PrivateWriteError(
        f"{target} is a symbolic link. Refusing to write through it because the link could "
        "redirect the write to a different file. Choose a regular file."
    )


def create_private_file(path: str | Path, *, exclusive: bool = False) -> int:
    """Create ``path`` owner-only and return its open descriptor; never follow a symbolic link.

    The owner-only mode is applied through the descriptor *before* anything is written, so there is
    no window in which candidate data exists in a group/world-readable file, and an existing file at
    ``path`` is tightened rather than trusted (``umask`` can only remove bits, never add them).

    ``exclusive=True`` additionally refuses to touch an existing file at all, which is how a backup
    avoids overwriting something the user still needs. Raises :class:`PrivateWriteError` with a
    user-facing message; the caller owns the returned descriptor and must close it.
    """
    target = Path(path)
    if target.is_symlink():
        # Checked before opening so the refusal also holds where O_NOFOLLOW is unavailable; the
        # O_NOFOLLOW flag below additionally closes the race between this check and the open.
        raise _symlink_refusal(target)

    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    try:
        descriptor = os.open(target, flags, _OWNER_ONLY_MODE)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise _symlink_refusal(target) from exc
        raise PrivateWriteError(f"{target} could not be opened for writing: {exc.strerror or exc}.") from exc

    if not _apply_owner_only_mode(descriptor):
        os.close(descriptor)
        if exclusive:
            # This call created the file, so removing it leaves the folder exactly as it was found
            # instead of an empty file that would then block a retry as "already exists".
            try:
                os.unlink(target)
            except OSError:
                pass
            raise PrivateWriteError(
                f"{target} could not be restricted to owner-only on this system, so nothing was "
                "written and the new file was removed. Choose a location that supports file permissions."
            )
        raise PrivateWriteError(
            f"{target} could not be restricted to owner-only on this system, so nothing was "
            "written. Choose a location that supports file permissions."
        )
    return descriptor


def require_owner_only(path: str | Path, *, noun: str = "file") -> None:
    """Verify ``path`` is owner-only on POSIX, removing it and raising when that is impossible.

    Re-applies the mode first (a writer may have replaced the file since it was created), then
    checks the real mode bits. A filesystem that silently ignores the change must not be left
    holding candidate data, so the file is removed where possible and the error says what happened.
    Non-POSIX platforms have no POSIX mode bits to verify, so this is a no-op there and no
    protection is claimed.
    """
    if os.name != "posix":
        return
    target = Path(path)
    _apply_owner_only_mode(target)
    try:
        current_mode = os.lstat(target).st_mode & 0o777
    except OSError as exc:
        raise PrivateWriteError(
            f"{target} was written but could not be checked for owner-only access: "
            f"{exc.strerror or exc}. Delete the {noun}."
        ) from exc
    if current_mode & 0o077:
        try:
            os.unlink(target)
            removed = f"the {noun} was removed"
        except OSError:
            removed = f"delete {target} manually"
        raise PrivateWriteError(
            f"{target} could not be kept owner-only on this filesystem (mode "
            f"{oct(current_mode)}), so it was not kept: {removed}."
        )


def write_private_text_file(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Write ``text`` to ``path`` so the file is owner-only from the moment it holds any data.

    The file is created through :func:`create_private_file`, so a destination that already exists is
    corrected rather than left at whatever mode and umask produced it, and a destination that is a
    symbolic link is refused instead of followed.

    Fail-safe by omission: when the mode cannot be applied or cannot be verified, no candidate data
    is written, and any file left behind by the failed attempt is removed where possible.

    Raises :class:`PrivateWriteError` (an ``OSError``) with a user-facing message. POSIX mode
    guarantees apply on POSIX systems; other platforms get the same write path without the
    permission guarantee, which is not claimed there.
    """
    target = Path(path)
    descriptor = create_private_file(target)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding) as handle:
            descriptor = None  # the file object owns the descriptor from here
            handle.write(text)
    except OSError as exc:
        raise PrivateWriteError(
            f"{target} could not be written: {exc.strerror or exc}. The export was not completed."
        ) from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass

    require_owner_only(target, noun="export")
    return target


def append_private_text_file(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Append ``text`` to ``path``, creating it owner-only and never following a symbolic link.

    Shares :func:`create_private_file`'s guarantees - the owner-only mode is applied through the
    descriptor before anything is written, and a link is refused - but opens for append rather than
    truncating, because this is how the application's own event log accumulates. The mode is applied
    on every append, so a file whose mode was loosened after creation is tightened again rather than
    trusted. Raises :class:`PrivateWriteError` (an ``OSError``) with a user-facing message.
    """
    target = Path(path)
    if target.is_symlink():
        raise _symlink_refusal(target)

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags, _OWNER_ONLY_MODE)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise _symlink_refusal(target) from exc
        raise PrivateWriteError(f"{target} could not be opened for writing: {exc.strerror or exc}.") from exc

    if not _apply_owner_only_mode(descriptor):
        os.close(descriptor)
        raise PrivateWriteError(
            f"{target} could not be restricted to owner-only on this system, so nothing was appended "
            "to it. Choose a location that supports file permissions."
        )
    try:
        with os.fdopen(descriptor, "a", encoding=encoding) as handle:
            descriptor = None  # the file object owns the descriptor from here
            handle.write(text)
    except OSError as exc:
        raise PrivateWriteError(f"{target} could not be written: {exc.strerror or exc}.") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    return target


def _json_default(value):
    if isinstance(value, (set, frozenset, tuple)):
        return sorted(value)
    if isinstance(value, (ApplicationStatus, Availability)):
        return value.value
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _stored_object(payload: object, noun: str) -> dict:
    """Decode a stored JSON payload into a record, or refuse with a message naming the problem."""
    try:
        values = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StoredRecordError(noun, f"the saved text is not valid JSON: {exc}") from exc
    if not isinstance(values, dict):
        raise StoredRecordError(noun, f"it holds {type(values).__name__} rather than a stored record")
    return values


def _stored_text(value: object, noun: str, field: str) -> str:
    """One stored string, reported as a named problem when it is not usable text."""
    if not isinstance(value, str) or not value.strip():
        raise StoredRecordError(noun, f"its {field} is {type(value).__name__} rather than text")
    return value


def _stored_date(value: object, listing_id: str) -> date | None:
    """A stored ``YYYY-MM-DD`` column as a date, or a refusal naming the record.

    Raises :class:`StoredRecordError` (a ``ValueError``) rather than ``None`` for text that is not a date:
    a reminder silently disappearing is worse than an error naming the record, because the person would
    never learn that the day they set is not being honoured.
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError as exc:
        raise StoredRecordError(
            f"the application record for {listing_id}",
            f"its follow-up day is {value!r}, which is not a YYYY-MM-DD date",
        ) from exc
    return parsed


def _stored_day(value: object, noun: str, field: str, *, optional: bool = False) -> date | None:
    """A stored ``YYYY-MM-DD`` column as a date, or a refusal naming the record and the field.

    The sibling of :func:`_stored_date`, which names a listing because a follow-up day belongs to one. A
    history record is identified by its own noun and field, and ``optional`` says whether an absent value is
    "not recorded" (a real answer) or a damaged row.
    """
    if value is None:
        if optional:
            return None
        raise StoredRecordError(noun, f"its {field} is missing")
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise StoredRecordError(noun, f"its {field} is {value!r}, which is not a YYYY-MM-DD date") from exc


def _stored_text_values(value: object, noun: str, field: str) -> list:
    """A stored list of strings, or refuse. A bare string is refused rather than split into letters.

    The application always writes a list here. A string instead - which only a hand edit or damage
    produces - would otherwise become a set of single characters, quietly turning one value into
    several wrong ones that later comparisons would use.
    """
    if value is None:
        return []
    if isinstance(value, str):
        raise StoredRecordError(noun, f"its {field} is a single string rather than a list of values")
    if not isinstance(value, (list, tuple)):
        raise StoredRecordError(noun, f"its {field} is {type(value).__name__} rather than a list of values")
    return list(value)


def _migration_to_v1(connection: sqlite3.Connection) -> None:
    """Schema 1: the original profile, job listing and application tracker tables.

    The statements are exactly the ones this application always created its schema with, so a database
    written by an earlier build has the same objects at the same version. ``IF NOT EXISTS`` is
    defensive only: a file that holds tables but records no version is refused before any step runs
    (see :meth:`CareerStore._initialize`), and a step that fails is rolled back whole, so in practice
    this step only ever runs against a file with no tables in it.
    """
    for statement in (
        """CREATE TABLE IF NOT EXISTS candidate_profile (
               profile_id INTEGER PRIMARY KEY CHECK (profile_id = 1),
               payload TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )""",
        """CREATE TABLE IF NOT EXISTS job_listings (
               listing_id TEXT PRIMARY KEY,
               payload TEXT NOT NULL,
               duplicate_key TEXT NOT NULL,
               first_seen_at TEXT NOT NULL,
               last_seen_at TEXT NOT NULL
           )""",
        """CREATE INDEX IF NOT EXISTS idx_job_duplicate_key ON job_listings(duplicate_key)""",
        """CREATE TABLE IF NOT EXISTS application_tracker (
               listing_id TEXT PRIMARY KEY REFERENCES job_listings(listing_id) ON DELETE CASCADE,
               status TEXT NOT NULL,
               status_evidence TEXT,
               candidate_confirmed INTEGER NOT NULL DEFAULT 0,
               updated_at TEXT NOT NULL
           )""",
    ):
        connection.execute(statement)


def _migration_to_v2(connection: sqlite3.Connection) -> None:
    """Schema 2: an append-only log of what happened for each tracked application.

    Additive: nothing existing is rewritten. The log is deleted with its listing (``ON DELETE
    CASCADE``), and the index matches the only read order the application uses - one listing, oldest
    date first. ``IF NOT EXISTS`` is defensive for the same reason as the first step.
    """
    connection.execute(
        """CREATE TABLE IF NOT EXISTS application_activity (
               activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
               listing_id TEXT NOT NULL REFERENCES job_listings(listing_id) ON DELETE CASCADE,
               occurred_on TEXT NOT NULL,
               recorded_at TEXT NOT NULL,
               kind TEXT NOT NULL,
               detail TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_application_activity_listing
               ON application_activity(listing_id, occurred_on, activity_id)"""
    )


def _migration_to_v3(connection: sqlite3.Connection) -> None:
    """Schema 3: the durable side of the background scheduler.

    Three tables, all additive:

    * ``scheduled_task`` - one row per task definition plus the bookkeeping the scheduler maintains
      (when it is next due, whether it is holding an occurrence that still has attempts left, and what
      happened last time).
    * ``task_run`` - one row per attempt at one scheduled occurrence. The uniqueness of
      ``(task_id, slot_key, attempt)`` is the duplicate-run protection: it is a property of the data
      rather than a convention, so two workers, a retry after a crash and a restarted process all
      resolve to "exactly one row, so exactly one execution".
    * ``worker_lease`` - one row proving which worker may execute tasks for this database, refreshed by
      a heartbeat. A fresh lease held by another worker is a refusal; a stale one is taken over, since
      the alternative is a database that can never be scheduled again.

    Nothing here changes the candidate tables: this step only adds objects.
    """
    connection.execute(
        """CREATE TABLE IF NOT EXISTS scheduled_task (
               task_id TEXT PRIMARY KEY,
               name TEXT NOT NULL,
               kind TEXT NOT NULL,
               timezone TEXT NOT NULL,
               schedule_times TEXT NOT NULL,
               enabled INTEGER NOT NULL,
               timeout_seconds INTEGER NOT NULL,
               max_attempts INTEGER NOT NULL,
               retry_backoff_seconds INTEGER NOT NULL,
               next_run_at TEXT,
               pending_slot_at TEXT,
               pending_attempt INTEGER,
               last_run_at TEXT,
               last_outcome TEXT,
               last_error TEXT,
               consecutive_failures INTEGER NOT NULL DEFAULT 0,
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_scheduled_task_due
               ON scheduled_task(enabled, next_run_at)"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS task_run (
               run_id TEXT PRIMARY KEY,
               task_id TEXT NOT NULL REFERENCES scheduled_task(task_id) ON DELETE CASCADE,
               slot_key TEXT NOT NULL,
               slot_at TEXT NOT NULL,
               attempt INTEGER NOT NULL,
               state TEXT NOT NULL,
               worker_id TEXT,
               timeout_seconds INTEGER NOT NULL,
               created_at TEXT NOT NULL,
               started_at TEXT,
               finished_at TEXT,
               heartbeat_at TEXT,
               detail TEXT NOT NULL DEFAULT '',
               error TEXT,
               UNIQUE (task_id, slot_key, attempt)
           )"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_task_run_task
               ON task_run(task_id, created_at DESC)"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_task_run_state
               ON task_run(state, heartbeat_at)"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS worker_lease (
               lease_name TEXT PRIMARY KEY,
               worker_id TEXT NOT NULL,
               acquired_at TEXT NOT NULL,
               heartbeat_at TEXT NOT NULL
           )"""
    )


def _migration_to_v4(connection: sqlite3.Connection) -> None:
    """Schema 4: two nullable columns recording the day a person plans to follow an application up.

    Additive and non-destructive: ``ALTER TABLE ... ADD COLUMN`` appends a column without rewriting the
    table, and existing rows get ``NULL`` - which is exactly right, because an existing record has no
    follow-up planned and inventing one would be putting a reminder in somebody's list they never asked
    for. Nothing is dropped, nothing is converted, and a database that never uses follow-ups is
    unchanged apart from two empty columns.

    The columns are plain text holding an ISO date (``YYYY-MM-DD``) and a short note. A date is stored as
    a date rather than a timestamp on purpose: the person names a day, and a day has no time of day to
    get wrong when the same database is opened in another timezone.

    Each column is added only when it is missing. SQLite has no ``ADD COLUMN IF NOT EXISTS``, so the
    check is explicit - the same defensiveness the other steps get from ``IF NOT EXISTS``. It matters in
    two real cases: a database whose recorded version was set back by a person or by a copied file, and a
    step that was interrupted after its first statement. Running the step twice must never fail, because
    a failed step leaves a database that cannot be opened at all.
    """
    existing = {row["name"] for row in connection.execute("PRAGMA table_info(application_tracker)")}
    if "follow_up_on" not in existing:
        connection.execute("ALTER TABLE application_tracker ADD COLUMN follow_up_on TEXT")
    if "follow_up_note" not in existing:
        connection.execute("ALTER TABLE application_tracker ADD COLUMN follow_up_note TEXT")


def _migration_to_v5(connection: sqlite3.Connection) -> None:
    """Schema 5: the preparation checklist and the interview rounds.

    Two new tables, additive and empty. An existing database gains the ability to record these things
    without any existing row being touched, and a database that never uses them is unchanged apart from two
    empty tables - which is what makes this a safe step to run on somebody's real data.

    * ``application_preparation`` - one thing to do before applying or before a round. The title and kind
      are the person's words; ``done_at`` is when *they* said it was finished, and it is NULL until then.
      There is no status column: a preparation item cannot move an application on, so there is nowhere to
      put such a claim.
    * ``interview_round`` - one round of an employer's process as the candidate recorded it: which stage,
      the day it is planned for, how it is being held, their own reading of how it went, and their notes.
      ``outcome`` defaults to ``awaiting`` because that is the truth before anything has happened.

    Both are deleted with their listing (``ON DELETE CASCADE``), and the indexes match the read orders the
    application actually uses: everything for one listing, and everything due across listings. ``IF NOT
    EXISTS`` keeps the step re-runnable, like every other step, because a step interrupted after its first
    statement must not leave a database that cannot be opened.
    """
    connection.execute(
        """CREATE TABLE IF NOT EXISTS application_preparation (
               preparation_id INTEGER PRIMARY KEY AUTOINCREMENT,
               listing_id TEXT NOT NULL REFERENCES job_listings(listing_id) ON DELETE CASCADE,
               title TEXT NOT NULL,
               kind TEXT NOT NULL,
               due_on TEXT,
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL,
               done_at TEXT
           )"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_application_preparation_listing
               ON application_preparation(listing_id, due_on, preparation_id)"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_application_preparation_open
               ON application_preparation(done_at, due_on)"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS interview_round (
               round_id INTEGER PRIMARY KEY AUTOINCREMENT,
               listing_id TEXT NOT NULL REFERENCES job_listings(listing_id) ON DELETE CASCADE,
               stage TEXT NOT NULL,
               scheduled_on TEXT NOT NULL,
               mode TEXT NOT NULL,
               outcome TEXT NOT NULL DEFAULT 'awaiting',
               notes TEXT,
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_interview_round_listing
               ON interview_round(listing_id, scheduled_on, round_id)"""
    )


def _migration_to_v6(connection: sqlite3.Connection) -> None:
    """Schema 6: the candidate's own employment history and education, as structured records.

    Two new tables, additive and empty. Until now the profile held one degree string and one number of
    years; these are the rows behind those summaries - many per candidate, each editable and deletable on
    its own - and an existing database gains them without a single existing row being touched.

    Neither table references ``job_listings``: this is the candidate's own history, not something attached
    to an application, so it is not deleted when a listing is. It *is* deleted with the profile itself,
    because it is profile data - see :meth:`CareerStore.delete_profile`, which says so and counts it.

    ``is_current`` and ``is_ongoing`` are stored flags rather than being derived from a missing end date: a
    role with no end date might be the current one, or one that ended at a time nobody recorded, and only
    the person knows which. Storing the flag keeps the record saying what they said.

    ``IF NOT EXISTS`` on both statements keeps the step re-runnable, like every other step, because a step
    interrupted after its first statement must not leave a database that cannot be opened.
    """
    connection.execute(
        """CREATE TABLE IF NOT EXISTS candidate_work_history (
               entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
               employer TEXT NOT NULL,
               job_title TEXT NOT NULL,
               employment_type TEXT NOT NULL,
               start_date TEXT NOT NULL,
               end_date TEXT,
               is_current INTEGER NOT NULL DEFAULT 0,
               summary TEXT,
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_candidate_work_history_order
               ON candidate_work_history(is_current, start_date, entry_id)"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS candidate_education (
               entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
               institution TEXT NOT NULL,
               qualification TEXT NOT NULL,
               discipline TEXT,
               start_date TEXT,
               completion_date TEXT,
               is_ongoing INTEGER NOT NULL DEFAULT 0,
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS idx_candidate_education_order
               ON candidate_education(is_ongoing, completion_date, entry_id)"""
    )


#: The ordered schema steps this build can run, as ``(version it reaches, what it does, how)``. This
#: is the single definition of how a database reaches the current schema. A step is only ever
#: appended, never rewritten or reordered: databases in the field have already run the earlier ones,
#: and the recorded version is what decides which steps still apply.
_MIGRATIONS: tuple[tuple[int, str, Callable[[sqlite3.Connection], None]], ...] = (
    (1, "create the profile, job listing and application tracker tables", _migration_to_v1),
    (2, "add the application activity log", _migration_to_v2),
    (3, "add the background task scheduler tables", _migration_to_v3),
    (4, "add the follow-up plan columns to the application tracker", _migration_to_v4),
    (5, "add the preparation checklist and the interview rounds", _migration_to_v5),
    (6, "add the candidate's own employment history and education", _migration_to_v6),
)


#: The version numbers of the steps above, in order, for callers that report or verify them. Derived
#: from the migration table so it cannot drift from what actually runs.
MIGRATION_STEPS: tuple[int, ...] = tuple(target for target, _, _ in _MIGRATIONS)


class CareerStore:
    """Small explicit local store. Pass a path; no database is created implicitly."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._connection = sqlite3.connect(self.database_path)
        try:
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._initialize()
            _restrict_to_owner(self.database_path)
            self._record("database.opened", f"schema={_SCHEMA_VERSION}")
        except BaseException:
            # A store that failed to open must not keep its connection: nothing can reach this one
            # (the caller only ever sees the exception), so leaving it to the garbage collector holds
            # the database file open for an unpredictable time and raises an "unclosed database"
            # ResourceWarning on interpreters that report it. ``close`` is idempotent, so the schema
            # check closing first is harmless.
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CareerStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _record(self, event: str, detail: str | None = None) -> None:
        """Append one line about this database to the application log; never fail a save over it.

        Imported here rather than at module level because ``event_log`` reports through
        ``diagnostics`` and ``diagnostics`` reports *about* this module: one local import keeps the
        import graph acyclic without moving the owner-only write primitive out of this module, which is
        the one place that decides what "owner-only" means.
        """
        from .event_log import record_event  # local import: avoids a circular import at load time

        record_event(event, detail=detail, database_path=self.database_path)

    def _initialize(self) -> None:
        """Bring the database to the schema this build expects, one recorded step at a time."""
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if version > _SCHEMA_VERSION:
            self._connection.close()
            raise SchemaTooNewError(version, _SCHEMA_VERSION)
        if version == 0 and self._holds_tables():
            # A file with tables that records no schema version was not written by this application.
            # Adopting it would add our tables to somebody else's file, so it is refused untouched.
            self._connection.close()
            raise UnrecognisedDatabaseError(
                "This file contains tables but records schema version 0, so it was not written by this "
                "application. Nothing was changed; point the app at a different file or restore a "
                "verified backup of your own database."
            )
        current = version
        if 0 < current < _SCHEMA_VERSION and self._holds_tables():
            # An existing database of an older version is about to be changed, so it is copied first.
            # A brand-new file has nothing to preserve, and neither has a file that already records the
            # current version, so neither is copied.
            self._snapshot_before_upgrade(current)
        for target, description, apply_migration in _MIGRATIONS:
            if target <= current:
                continue
            self._apply_migration(target, description, apply_migration, current)
            current = target

    def _snapshot_before_upgrade(self, from_version: int) -> Path:
        """Copy the database beside itself and verify the copy, before the first step changes it.

        The copy goes through the same verified, owner-only backup path the Data safety tab uses, so
        what it guarantees is exactly what that path guarantees - read back, checked, and kept rather
        than overwritten - and the file name says which version it holds. A copy that cannot be written
        stops the update (:class:`SchemaUpgradeRefused`) instead of changing a database nobody has a
        second copy of.
        """
        # Local import: ``backup`` imports this module's write primitives, so a module-level import
        # here would be circular.
        from .backup import BackupError, create_backup, next_automatic_backup_path

        # A fresh name every time: the copy has to describe the database as it is *now*, so a copy left
        # by an earlier attempt is never reused, and the second-resolution timestamp alone would make two
        # attempts in the same second collide (which is what a retry after a failed step does).
        target = next_automatic_backup_path(self.database_path)
        try:
            create_backup(self.database_path, target)
        except BackupError as exc:
            raise SchemaUpgradeRefused(_SCHEMA_VERSION, from_version, exc) from exc
        self._record("database.upgrade_snapshot", f"version={from_version} file={target.name}")
        return target

    def _holds_tables(self) -> bool:
        """Whether the database file holds any table of its own (SQLite's internal ones do not count)."""
        return self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone() is not None

    def _apply_migration(self, target: int, description: str, apply_migration, from_version: int) -> None:
        """Run one schema step and record its version in the same transaction.

        ``BEGIN IMMEDIATE`` is issued by hand instead of relying on the connection's implicit
        transaction, which the sqlite3 module opens for data-modifying statements only: DDL would run
        outside it, and ``executescript`` commits any open transaction before running its script. A
        step whose statements partly succeeded would then be impossible to roll back. Steps execute
        one statement at a time for the same reason, and ``PRAGMA user_version`` is written inside
        the transaction, so the recorded version and the structure always move together - a database
        can never claim a version whose objects are missing, or hold objects at a version it does not
        claim.
        """
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            apply_migration(self._connection)
            self._connection.execute(f"PRAGMA user_version = {target}")
            self._connection.execute("COMMIT")
        except Exception as exc:
            # A failed step is worth a line in the log as well as the exception: the log records the
            # sequence, so a step that was rolled back and one that was applied cannot be confused
            # when someone reads it afterwards.
            self._record("database.migration_failed", f"to={target} from={from_version}")
            raise SchemaMigrationError(target, description, from_version,
                                       self._roll_back_step(), exc) from exc
        # After the commit, so the log only claims a change the database itself records.
        self._record("database.migrated", f"from={from_version} to={target} ({description})")

    def _roll_back_step(self) -> int | None:
        """Undo a failed schema step and report the version the database records afterwards."""
        try:
            self._connection.execute("ROLLBACK")
        except sqlite3.Error:
            # SQLite may already have unwound the transaction (a full disk, for example). There is
            # nothing to undo in that case, and the version read below is what settles it either way.
            pass
        try:
            return int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        except sqlite3.Error:
            return None

    def save_profile(self, profile: CandidateProfile) -> None:
        payload = json.dumps(asdict(profile), sort_keys=True, default=_json_default)
        with self._connection:
            self._connection.execute(
                """INSERT INTO candidate_profile(profile_id, payload, updated_at) VALUES (1, ?, ?)
                   ON CONFLICT(profile_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""",
                (payload, _now()),
            )
        # No detail: what the profile says is candidate data and stays out of a log meant to be safe to
        # share. The timestamp is the answer to "when was this last saved?".
        self._record("profile.saved")

    def get_profile(self) -> CandidateProfile | None:
        row = self._connection.execute("SELECT payload FROM candidate_profile WHERE profile_id=1").fetchone()
        if row is None:
            return None
        return self._decode_profile(row["payload"])

    @staticmethod
    def _decode_profile(payload: str) -> CandidateProfile:
        """One ``candidate_profile`` payload as a record, refusing what this build cannot read."""
        noun = "candidate profile"
        values = _stored_object(payload, noun)
        for key in ("skills", "preferred_locations", "preferred_work_modes", "preferred_role_types"):
            values[key] = frozenset(_stored_text_values(values.get(key), noun, key))
        try:
            return CandidateProfile(**values)
        except TypeError as exc:
            raise StoredRecordError(noun, f"it holds field(s) this version cannot use ({exc})") from exc

    def save_job(self, job: JobListing, *, observed_at: str | None = None) -> None:
        timestamp = observed_at or _now()
        payload = json.dumps(asdict(job), sort_keys=True, default=_json_default)
        with self._connection:
            self._connection.execute(
                """INSERT INTO job_listings(listing_id, payload, duplicate_key, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(listing_id) DO UPDATE SET
                     payload=excluded.payload, duplicate_key=excluded.duplicate_key,
                     last_seen_at=excluded.last_seen_at""",
                (job.listing_id, payload, duplicate_key(job), timestamp, timestamp),
            )
        self._record("job.saved", f"id={job.listing_id}")

    def get_job(self, listing_id: str) -> JobListing | None:
        row = self._connection.execute("SELECT payload FROM job_listings WHERE listing_id=?", (listing_id,)).fetchone()
        return self._decode_job(row["payload"]) if row else None

    def list_jobs(self, *, status: Availability | None = None) -> tuple[JobListing, ...]:
        rows = self._connection.execute("SELECT payload FROM job_listings ORDER BY first_seen_at, listing_id").fetchall()
        jobs = tuple(self._decode_job(row["payload"]) for row in rows)
        if status is not None:
            jobs = tuple(job for job in jobs if job.availability_status is status)
        return jobs

    def find_duplicate_group(self, job: JobListing) -> tuple[JobListing, ...]:
        rows = self._connection.execute(
            "SELECT payload FROM job_listings WHERE duplicate_key=? ORDER BY first_seen_at, listing_id",
            (duplicate_key(job),),
        ).fetchall()
        return tuple(self._decode_job(row["payload"]) for row in rows)

    def save_tracker(self, tracker: ApplicationTracker, *, expected: dict | None = None,
                     follow_up: FollowUpWrite = FollowUpWrite.KEEP) -> None:
        """Persist tracker state, enforcing the domain invariants at the storage boundary.

        Creating a record always starts at :data:`~career_agent.core.INITIAL_APPLICATION_STATUS`
        (``discovered``), so a record cannot appear as shortlisted, submitted, confirmed, or
        completed without having passed through the permitted states. Later writes must be
        transitions the state machine permits (re-applying the current status stays an
        idempotent no-op), ``confirmed`` always requires evidence, and ``candidate_confirmed``
        cannot claim a confirmation that was never recorded. The desktop app moves through
        ``ApplicationTracker.transition`` before saving, so valid sequential use is
        unaffected; an arbitrary or contradictory record is refused instead of being written.
        No schema change is required and existing rows are never rewritten.

        ``expected`` is for callers that read a row, decide something about it, and then write
        minutes later (``scripts/correct_tracker_record.py``): pass the fields that were read and
        the write becomes a *conditional* update. Another writer moving the record on - even to a
        status this transition also permits, with evidence or a confirmation this caller never saw -
        makes the update match no row and raise :class:`StaleTrackerRecord` instead of silently
        overwriting the newer data. Re-checking only the transition rules cannot catch that: a
        forward move usually leaves the intended transition permitted.

        ``follow_up`` decides what happens to the recorded reminder, and the default protects it. A
        tracker built from a status alone carries no plan, so an ordinary save - a status change, a new
        confirmation - leaves a stored day and note exactly as they are; moving an application on cannot
        silently cancel the reminder the person set. A tracker that *does* carry a plan was built with
        ``ApplicationTracker.with_follow_up``, so that plan is stored, because ignoring it would drop a
        day the caller had just set. Two things are therefore explicit rather than guessed: clearing an
        existing plan (``clear_follow_up``, or :attr:`FollowUpWrite.WRITE` with a planless tracker), and
        replacing one with different values (always ``WRITE``, otherwise the write is refused and nothing
        changes).
        """
        stored = self.get_tracker(tracker.listing_id)
        self._check_tracker_invariants(tracker, stored)
        stored_day = stored.follow_up_on if stored else None
        stored_note = stored.follow_up_note if stored else None
        if follow_up is FollowUpWrite.WRITE:
            write_plan = True
        elif not tracker.has_follow_up:
            # An ordinary save cannot clear a reminder: a tracker with no day says nothing about the day
            # that is stored, and most of them are built from a status alone. Clearing is explicit -
            # ``clear_follow_up`` or ``FollowUpWrite.WRITE``.
            write_plan = False
        elif stored_day is None:
            # The stored record has no plan and this one carries one, which means the caller called
            # ``with_follow_up``. Storing it cannot lose anything, and ignoring it would drop a day they
            # just set.
            write_plan = True
        elif (tracker.follow_up_on, tracker.follow_up_note) == (stored_day, stored_note):
            write_plan = True  # the same plan, written again: a no-op either way
        else:
            raise ValueError(
                f"The tracker for {tracker.listing_id} carries a follow-up day and note that differ from "
                "the stored ones, and this save was not asked to write a plan. Nothing was written: pass "
                "follow_up=FollowUpWrite.WRITE if the new plan is the one you mean, so a status update "
                "and a reminder change can never be confused for each other."
            )
        timestamp = _now()
        if expected is not None:
            # One statement, so there is no window between checking and writing, and it is committed
            # before ``rowcount`` is interpreted: a conditional write left open in a transaction would
            # be invisible to the very read (often on another connection) that verifies it.
            # ``status_evidence`` is compared with IFNULL because a stored NULL and an absent note mean
            # the same thing.
            # A caller that read the follow-up fields and passed them in gets them guarded too: the
            # condition is added only when the caller supplied them, so an older caller's ``expected``
            # (status/evidence/confirmation) keeps working exactly as before.
            follow_up_guard = ""
            parameters: list[object] = [
                tracker.status.value, tracker.status_evidence, int(tracker.candidate_confirmed),
                *self._follow_up_columns(tracker, stored, write=write_plan),
                timestamp, tracker.listing_id, str(expected.get("status")),
                str(expected.get("status_evidence") or ""), int(bool(expected.get("candidate_confirmed"))),
            ]
            if "follow_up_on" in expected:
                follow_up_guard = " AND IFNULL(follow_up_on, '') = ? AND IFNULL(follow_up_note, '') = ?"
                parameters.extend([str(expected.get("follow_up_on") or ""),
                                   str(expected.get("follow_up_note") or "")])
            with self._connection:
                cursor = self._connection.execute(
                    """UPDATE application_tracker
                          SET status = ?, status_evidence = ?, candidate_confirmed = ?,
                              follow_up_on = ?, follow_up_note = ?, updated_at = ?
                        WHERE listing_id = ? AND status = ? AND IFNULL(status_evidence, '') = ?
                          AND candidate_confirmed = ?""" + follow_up_guard,
                    tuple(parameters),
                )
                matched = cursor.rowcount
            if matched != 1:
                raise StaleTrackerRecord(
                    f"The tracker record for {tracker.listing_id} changed after it was read "
                    f"(expected {expected.get('status')!r}, "
                    f"confirmed={bool(expected.get('candidate_confirmed'))}), so this write was "
                    "refused and nothing was changed. Read the record again and redo the change."
                )
            return
        try:
            with self._connection:
                self._connection.execute(
                    """INSERT INTO application_tracker(listing_id, status, status_evidence, candidate_confirmed,
                                                     follow_up_on, follow_up_note, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(listing_id) DO UPDATE SET status=excluded.status,
                         status_evidence=excluded.status_evidence, candidate_confirmed=excluded.candidate_confirmed,
                         follow_up_on=excluded.follow_up_on, follow_up_note=excluded.follow_up_note,
                         updated_at=excluded.updated_at""",
                    (tracker.listing_id, tracker.status.value, tracker.status_evidence,
                     int(tracker.candidate_confirmed),
                     *self._follow_up_columns(tracker, stored, write=write_plan),
                     timestamp),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Save the job listing before its application tracker.") from exc
        effective_day = tracker.follow_up_on if write_plan else stored_day
        self._record("tracker.saved", f"id={tracker.listing_id} status={tracker.status.value} "
                                      f"confirmed={int(bool(tracker.candidate_confirmed))}"
                                      f" follow_up={effective_day.isoformat() if effective_day else 'none'}"
                                      f" follow_up_write={follow_up.value}")

    def _follow_up_columns(self, tracker: ApplicationTracker, stored: ApplicationTracker | None,
                           *, write: bool) -> tuple[str | None, str | None]:
        """The two follow-up values a write should store: the tracker's, or the row's own.

        Kept in one place so both write paths (the conditional update and the insert-or-update) make the
        same decision, and so an ordinary save can only ever repeat what is already stored.
        """
        source = tracker if write else stored
        if source is None:
            return (None, None)
        return (source.follow_up_on.isoformat() if source.follow_up_on else None, source.follow_up_note)

    def set_follow_up(self, listing_id: str, on: date | None, *, note: str | None = None
                      ) -> ApplicationTracker:
        """Record (or change) the day this application should be chased, and return the stored record.

        Reading and writing the plan in one method keeps the two columns and the status row in step: the
        caller names the day, the store decides how it is written. A listing with no application record is
        refused - a reminder is a plan to act on an application, and inventing a record to hold it would
        put an application in the tracker that nobody applied for.
        """
        stored = self.get_tracker(listing_id)
        if stored is None:
            raise ValueError(
                f"There is no application record for {listing_id} yet, so there is nothing to plan a "
                "follow-up for. Record the application first."
            )
        planned = stored.with_follow_up(on, note=note)
        self.save_tracker(planned, follow_up=FollowUpWrite.WRITE)
        return planned

    def clear_follow_up(self, listing_id: str) -> ApplicationTracker:
        """Remove a recorded follow-up day, keeping the application and its status untouched."""
        return self.set_follow_up(listing_id, None, note=None)

    def add_activity(self, listing_id: str, activity: ApplicationActivity) -> int:
        """Append one dated entry to a listing's history and return its ``activity_id``.

        The log is append-only from the application's side: there is no update path, so an entry that
        was written cannot be turned into a different claim later. The values are checked again here,
        not only where they were typed, because the storage boundary is where the rule has to hold.

        An entry is the person's own record of what happened. It never changes the tracker status,
        never sets ``candidate_confirmed``, and is never accepted as confirmation evidence - the
        requirements for that live in ``save_tracker`` and are untouched by anything here.
        """
        if not isinstance(activity, ApplicationActivity):
            raise ValueError("An activity entry must be an ApplicationActivity.")
        kind = activity.kind if isinstance(activity.kind, ActivityKind) else ActivityKind(activity.kind)
        detail = validate_activity_detail(activity.detail)
        occurred_on = validate_activity_date(activity.occurred_on)
        try:
            with self._connection:
                cursor = self._connection.execute(
                    """INSERT INTO application_activity(listing_id, occurred_on, recorded_at, kind, detail)
                       VALUES (?, ?, ?, ?, ?)""",
                    (listing_id, occurred_on.isoformat(), _now(), kind.value, detail),
                )
        except sqlite3.IntegrityError as exc:
            # The listing has to exist before its history can: the foreign key refuses an entry that
            # would belong to nothing, and the message says which record to save first.
            raise ValueError(
                f"No saved listing {listing_id!r} to attach this activity to. Save the job listing first."
            ) from exc
        self._record("activity.added", f"id={listing_id} kind={kind.value}")
        return int(cursor.lastrowid)

    def list_activity(self, listing_id: str) -> tuple[ApplicationActivity, ...]:
        """One listing's entries, oldest first (the order they happened, then the order recorded)."""
        rows = self._connection.execute(
            """SELECT activity_id, occurred_on, recorded_at, kind, detail
                 FROM application_activity WHERE listing_id = ?
                ORDER BY occurred_on, activity_id""",
            (listing_id,),
        ).fetchall()
        return tuple(self._decode_activity(row) for row in rows)

    def list_activity_raw(self, listing_id: str) -> tuple[dict, ...]:
        """The stored rows exactly as they are, for the export.

        ``list_activity`` refuses a row this version cannot decode, which is right for a view that has
        to render it and wrong for an export: the export exists so the person can get their own data
        out, including a row a later version wrote. Same reasoning as ``get_tracker_raw``.
        """
        rows = self._connection.execute(
            """SELECT activity_id, occurred_on, recorded_at, kind, detail
                 FROM application_activity WHERE listing_id = ?
                ORDER BY occurred_on, activity_id""",
            (listing_id,),
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def delete_activity(self, activity_id: int) -> bool:
        """Remove one entry; return whether a row was deleted. Explicit, like the other deletions."""
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM application_activity WHERE activity_id = ?", (int(activity_id),)
            )
        removed = cursor.rowcount == 1
        if removed:
            self._record("activity.deleted", f"activity_id={int(activity_id)}")
        return removed

    @staticmethod
    def _decode_activity(row: sqlite3.Row) -> ApplicationActivity:
        noun = "activity entry"
        try:
            kind = ActivityKind(row["kind"])
        except ValueError as exc:
            raise StoredRecordError(noun, f"its kind {row['kind']!r} is not one this version recognises") from exc
        raw_date = str(row["occurred_on"])
        try:
            occurred_on = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise StoredRecordError(noun, f"its date {raw_date!r} is not a calendar date") from exc
        try:
            return ApplicationActivity(
                kind=kind, occurred_on=occurred_on, detail=_stored_text(row["detail"], noun, "detail"),
                activity_id=int(row["activity_id"]), recorded_at=str(row["recorded_at"]),
            )
        except ValueError as exc:
            raise StoredRecordError(noun, f"its detail is not one this version can read ({exc})") from exc

    # ------------------------------------------------------------------ preparation and interviews
    #
    # Two records about the *work around* an application rather than the application itself. Both are
    # deliberately unable to move an application on: a preparation item has no status column, and an
    # interview round records the candidate's own note rather than an employer's decision. What the store
    # enforces here is the shape of the data (names this build knows, days that are days, bounded text) and
    # that a record cannot outlive its listing.

    def add_preparation(self, listing_id: str, title: str, *, kind: str | PreparationKind = PreparationKind.OTHER,
                        due_on: date | None = None) -> PreparationItem:
        """Add one thing to do for a listing and return it as stored.

        A listing with no saved row is refused (the foreign key would refuse it anyway, and a ``KeyError``
        from SQLite is not an explanation), as is a second *open* item with the same title and kind: two
        identical rows in a checklist are almost always a double click, and merging them afterwards is
        harder than refusing them at the door. An item that is already done does not block a new one with
        the same title, because repeating a step is a real thing people do.
        """
        item = PreparationItem(listing_id=listing_id, title=title, kind=kind, due_on=due_on)
        self._require_job(listing_id, "add a preparation item for")
        if item.is_done:
            raise ValueError("A new preparation item cannot start out already done.")
        existing = [row for row in self.list_preparation(listing_id)
                    if not row.is_done and row.title.casefold() == item.title.casefold()
                    and row.kind is item.kind]
        if existing:
            raise ValueError(
                f"There is already an open preparation item called {item.title!r} for this listing. "
                "Finish or delete that one instead of adding it twice."
            )
        timestamp = _now()
        with self._connection:
            cursor = self._connection.execute(
                """INSERT INTO application_preparation(listing_id, title, kind, due_on, created_at,
                                                       updated_at, done_at)
                   VALUES (?, ?, ?, ?, ?, ?, NULL)""",
                (item.listing_id, item.title, item.kind.value,
                 item.due_on.isoformat() if item.due_on else None, timestamp, timestamp),
            )
        stored = item.__class__(
            listing_id=item.listing_id, title=item.title, kind=item.kind, due_on=item.due_on,
            preparation_id=int(cursor.lastrowid or 0), created_at=timestamp, updated_at=timestamp,
        )
        self._record("preparation.added", f"id={listing_id} kind={item.kind.value}")
        return stored

    def list_preparation(self, listing_id: str | None = None) -> tuple[PreparationItem, ...]:
        """Every preparation item, ordered for a list: open ones first, earliest day first.

        One query per call and no joins: the caller that needs employer names already has the listings, and
        a store method that returns presentation-ready rows would be the wrong place for that decision.
        """
        if listing_id is None:
            rows = self._connection.execute(
                """SELECT * FROM application_preparation
                   ORDER BY (done_at IS NOT NULL), due_on IS NULL, due_on, title, listing_id"""
            ).fetchall()
        else:
            rows = self._connection.execute(
                """SELECT * FROM application_preparation WHERE listing_id=?
                   ORDER BY (done_at IS NOT NULL), due_on IS NULL, due_on, title, listing_id""",
                (listing_id,),
            ).fetchall()
        return tuple(self._decode_preparation(row) for row in rows)

    def get_preparation(self, preparation_id: int) -> PreparationItem | None:
        row = self._connection.execute(
            "SELECT * FROM application_preparation WHERE preparation_id=?", (int(preparation_id),)
        ).fetchone()
        return None if row is None else self._decode_preparation(row)

    def complete_preparation(self, preparation_id: int, *, done: bool = True) -> PreparationItem:
        """Mark an item done (or open it again) and return it as stored.

        "Done" is the person's statement that they did the thing, which is why it is their action and not
        something the application infers. Re-marking an item that is already in the requested state is
        refused rather than written, so the timestamp on the row always means the first time it was
        reported - the same rule the tracker's no-op path follows.
        """
        current = self.get_preparation(preparation_id)
        if current is None:
            raise ValueError(f"There is no preparation item {preparation_id} to change.")
        if current.is_done == done:
            state = "already marked done" if done else "not marked done"
            raise ValueError(f"That preparation item is {state}; nothing was changed.")
        timestamp = _now()
        with self._connection:
            self._connection.execute(
                "UPDATE application_preparation SET done_at=?, updated_at=? WHERE preparation_id=?",
                (timestamp if done else None, timestamp, int(preparation_id)),
            )
        updated = self.get_preparation(preparation_id)
        assert updated is not None  # the row was just written in this connection
        # Two literals rather than one conditional expression: the event vocabulary is checked against the
        # shipped source, and a name that only appears inside an expression cannot be verified there.
        if done:
            self._record("preparation.completed", f"preparation_id={int(preparation_id)}")
        else:
            self._record("preparation.reopened", f"preparation_id={int(preparation_id)}")
        return updated

    def delete_preparation(self, preparation_id: int) -> bool:
        """Remove one item; return whether a row was deleted. Explicit, like the other deletions."""
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM application_preparation WHERE preparation_id=?", (int(preparation_id),)
            )
        removed = cursor.rowcount == 1
        if removed:
            self._record("preparation.deleted", f"preparation_id={int(preparation_id)}")
        return removed

    def record_interview(self, listing_id: str, stage: str | InterviewStage, scheduled_on: date, *,
                         mode: str | InterviewMode = InterviewMode.UNKNOWN,
                         notes: str | None = None) -> InterviewRound:
        """Record one round of an employer's process, as the candidate noted it down.

        The round is stored with ``outcome=awaiting`` whatever else is supplied: how a round went is filled
        in afterwards, by the person, through :meth:`set_interview_outcome`. Nothing here touches the
        tracker - an interview being scheduled is a fact the person knows, and moving the application to
        ``interview`` is their own status change, with their own evidence, through the guarded path.
        """
        round_record = InterviewRound(listing_id=listing_id, stage=stage, scheduled_on=scheduled_on,
                                     mode=mode, notes=notes)
        self._require_job(listing_id, "record an interview round for")
        duplicate = [row for row in self.list_interviews(listing_id)
                     if row.stage is round_record.stage and row.scheduled_on == round_record.scheduled_on]
        if duplicate:
            raise ValueError(
                f"A {round_record.stage_label.lower()} is already recorded for "
                f"{round_record.scheduled_on.isoformat()} on this listing. Record a different round rather "
                "than the same one twice."
            )
        timestamp = _now()
        with self._connection:
            cursor = self._connection.execute(
                """INSERT INTO interview_round(listing_id, stage, scheduled_on, mode, outcome, notes,
                                               created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (round_record.listing_id, round_record.stage.value, round_record.scheduled_on.isoformat(),
                 round_record.mode.value, InterviewOutcome.AWAITING.value, round_record.notes,
                 timestamp, timestamp),
            )
        stored = InterviewRound(
            listing_id=round_record.listing_id, stage=round_record.stage,
            scheduled_on=round_record.scheduled_on, mode=round_record.mode,
            outcome=InterviewOutcome.AWAITING, notes=round_record.notes,
            round_id=int(cursor.lastrowid or 0), created_at=timestamp, updated_at=timestamp,
        )
        self._record("interview.recorded", f"id={listing_id} stage={round_record.stage.value}")
        return stored

    def list_interviews(self, listing_id: str | None = None) -> tuple[InterviewRound, ...]:
        """Every recorded round, oldest planned day first."""
        if listing_id is None:
            rows = self._connection.execute(
                "SELECT * FROM interview_round ORDER BY scheduled_on, round_id"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM interview_round WHERE listing_id=? ORDER BY scheduled_on, round_id",
                (listing_id,),
            ).fetchall()
        return tuple(self._decode_interview(row) for row in rows)

    def get_interview(self, round_id: int) -> InterviewRound | None:
        row = self._connection.execute(
            "SELECT * FROM interview_round WHERE round_id=?", (int(round_id),)
        ).fetchone()
        return None if row is None else self._decode_interview(row)

    def set_interview_outcome(self, round_id: int, outcome: str | InterviewOutcome, *,
                              notes: str | None = None) -> InterviewRound:
        """Record how the person felt a round went, and optionally their notes for next time.

        ``outcome`` is the candidate's own reading; the vocabulary has no value that sounds like an
        employer's decision, because the application cannot know one. ``notes`` replaces the stored notes
        only when supplied explicitly (``None`` means "leave them as they are"), so a person can record an
        outcome without losing the preparation note they wrote earlier.
        """
        current = self.get_interview(round_id)
        if current is None:
            raise ValueError(f"There is no interview round {round_id} to update.")
        updated = InterviewRound(
            listing_id=current.listing_id, stage=current.stage, scheduled_on=current.scheduled_on,
            mode=current.mode, outcome=outcome, notes=current.notes if notes is None else notes,
            round_id=current.round_id, created_at=current.created_at,
        )
        with self._connection:
            self._connection.execute(
                "UPDATE interview_round SET outcome=?, notes=?, updated_at=? WHERE round_id=?",
                (updated.outcome.value, updated.notes, _now(), int(round_id)),
            )
        stored = self.get_interview(round_id)
        assert stored is not None
        self._record("interview.outcome", f"round_id={int(round_id)} outcome={updated.outcome.value}")
        return stored

    def delete_interview(self, round_id: int) -> bool:
        """Remove one round; return whether a row was deleted."""
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM interview_round WHERE round_id=?", (int(round_id),)
            )
        removed = cursor.rowcount == 1
        if removed:
            self._record("interview.deleted", f"round_id={int(round_id)}")
        return removed

    def preparation_and_interviews_for(self, listing_id: str) -> tuple[tuple[PreparationItem, ...],
                                                                      tuple[InterviewRound, ...]]:
        """Both records for one listing in a single call, for a detail view that shows them together."""
        return (self.list_preparation(listing_id), self.list_interviews(listing_id))

    def _require_job(self, listing_id: str, verb: str) -> None:
        """Refuse a record for a listing that is not stored, naming the actual problem."""
        if self.get_job(listing_id) is None:
            raise ValueError(
                f"There is no stored listing {listing_id!r} to {verb}. Save the listing first."
            )

    @staticmethod
    def _decode_preparation(row: sqlite3.Row) -> PreparationItem:
        noun = "preparation item"
        try:
            kind = PreparationKind(row["kind"])
        except ValueError as exc:
            raise StoredRecordError(noun, f"its kind {row['kind']!r} is not one this version recognises") from exc
        raw_due = row["due_on"]
        due_on = None
        if raw_due is not None:
            try:
                due_on = date.fromisoformat(str(raw_due))
            except ValueError as exc:
                raise StoredRecordError(noun, f"its day {raw_due!r} is not a calendar date") from exc
        try:
            return PreparationItem(
                listing_id=_stored_text(row["listing_id"], noun, "listing_id"),
                title=_stored_text(row["title"], noun, "title"), kind=kind, due_on=due_on,
                preparation_id=int(row["preparation_id"]), done_at=row["done_at"],
                created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
            )
        except ValueError as exc:
            raise StoredRecordError(noun, f"it cannot be read ({exc})") from exc

    @staticmethod
    def _decode_interview(row: sqlite3.Row) -> InterviewRound:
        noun = "interview round"
        try:
            stage = InterviewStage(row["stage"])
        except ValueError as exc:
            raise StoredRecordError(noun, f"its stage {row['stage']!r} is not one this version recognises") from exc
        try:
            mode = InterviewMode(row["mode"])
        except ValueError as exc:
            raise StoredRecordError(noun, f"its mode {row['mode']!r} is not one this version recognises") from exc
        try:
            outcome = InterviewOutcome(row["outcome"])
        except ValueError as exc:
            raise StoredRecordError(noun, f"its outcome {row['outcome']!r} is not one this version recognises") from exc
        raw_day = str(row["scheduled_on"])
        try:
            scheduled_on = date.fromisoformat(raw_day)
        except ValueError as exc:
            raise StoredRecordError(noun, f"its day {raw_day!r} is not a calendar date") from exc
        try:
            return InterviewRound(
                listing_id=_stored_text(row["listing_id"], noun, "listing_id"), stage=stage,
                scheduled_on=scheduled_on, mode=mode, outcome=outcome, notes=row["notes"],
                round_id=int(row["round_id"]), created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
        except ValueError as exc:
            raise StoredRecordError(noun, f"it cannot be read ({exc})") from exc

    # ------------------------------------------------------- the candidate's own history
    #
    # Employment and study records, which belong to the candidate rather than to any application. The rules
    # enforced here are the ones a repository should own, so every caller gets them: a record cannot be
    # blank, a period cannot be impossible, and the two "still there / still studying" flags cannot sit next
    # to an end date. The domain classes already refuse those; these methods refuse them again at the write
    # boundary, because a store that trusts its caller is one refactor away from storing nonsense.

    def add_work_history(self, employer: str, job_title: str, start_date: date, *, end_date: date | None = None,
                         is_current: bool = False, employment_type: str | EmploymentType = EmploymentType.UNKNOWN,
                         summary: str | None = None) -> WorkHistoryEntry:
        """Add one employment record and return it as stored.

        A record identical to one already stored - same employer, same title, same start date, compared
        without case - is refused rather than added twice: that is what a double-click looks like, and two
        identical CV lines are worse than one because a reader cannot tell which is true.
        """
        entry = WorkHistoryEntry(employer=employer, job_title=job_title, start_date=start_date,
                                 end_date=end_date, is_current=is_current, employment_type=employment_type,
                                 summary=summary)
        for stored in self.list_work_history():
            if (stored.employer.casefold() == entry.employer.casefold()
                    and stored.job_title.casefold() == entry.job_title.casefold()
                    and stored.start_date == entry.start_date):
                raise ValueError(
                    f"You already have a record for {entry.job_title} at {entry.employer} starting "
                    f"{entry.start_date.isoformat()}. Edit that one instead of adding it twice."
                )
        timestamp = _now()
        with self._connection:
            cursor = self._connection.execute(
                """INSERT INTO candidate_work_history(employer, job_title, employment_type, start_date,
                                                      end_date, is_current, summary, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry.employer, entry.job_title, entry.employment_type.value, entry.start_date.isoformat(),
                 entry.end_date.isoformat() if entry.end_date else None, int(entry.is_current),
                 entry.summary, timestamp, timestamp),
            )
        stored = replace(entry, entry_id=int(cursor.lastrowid or 0), created_at=timestamp,
                         updated_at=timestamp)
        self._record("history.work_added", f"entry_id={stored.entry_id} current={int(stored.is_current)}")
        return stored

    def list_work_history(self) -> tuple[WorkHistoryEntry, ...]:
        """Every employment record, in the order a CV reads: current role first, then most recent first."""
        rows = self._connection.execute(
            """SELECT * FROM candidate_work_history
               ORDER BY is_current DESC, start_date DESC, entry_id DESC"""
        ).fetchall()
        return tuple(self._decode_work_history(row) for row in rows)

    def get_work_history(self, entry_id: int) -> WorkHistoryEntry | None:
        row = self._connection.execute(
            "SELECT * FROM candidate_work_history WHERE entry_id=?", (int(entry_id),)
        ).fetchone()
        return None if row is None else self._decode_work_history(row)

    def update_work_history(self, entry_id: int, employer: str, job_title: str, start_date: date, *,
                            end_date: date | None = None, is_current: bool = False,
                            employment_type: str | EmploymentType = EmploymentType.UNKNOWN,
                            summary: str | None = None) -> WorkHistoryEntry:
        """Replace one employment record with the values supplied, and return it as stored.

        The caller supplies the whole record, which is why the window fills its form from the stored row
        before anything is typed: a partial update would have to guess that an omitted field means "leave it"
        or "clear it", and either guess loses data. ``created_at`` is preserved - it says when the record was
        first written here, and an edit does not change that.
        """
        current = self.get_work_history(entry_id)
        if current is None:
            raise ValueError(f"There is no work-history record {entry_id} to change.")
        updated = WorkHistoryEntry(employer=employer, job_title=job_title, start_date=start_date,
                                   end_date=end_date, is_current=is_current,
                                   employment_type=employment_type, summary=summary,
                                   entry_id=current.entry_id, created_at=current.created_at)
        for stored in self.list_work_history():
            if stored.entry_id == updated.entry_id:
                continue
            if (stored.employer.casefold() == updated.employer.casefold()
                    and stored.job_title.casefold() == updated.job_title.casefold()
                    and stored.start_date == updated.start_date):
                raise ValueError(
                    f"Another record already covers {updated.job_title} at {updated.employer} starting "
                    f"{updated.start_date.isoformat()}. Edit that one, or change this one so the two differ."
                )
        timestamp = _now()
        with self._connection:
            self._connection.execute(
                """UPDATE candidate_work_history
                      SET employer=?, job_title=?, employment_type=?, start_date=?, end_date=?, is_current=?,
                          summary=?, updated_at=?
                    WHERE entry_id=?""",
                (updated.employer, updated.job_title, updated.employment_type.value,
                 updated.start_date.isoformat(),
                 updated.end_date.isoformat() if updated.end_date else None, int(updated.is_current),
                 updated.summary, timestamp, int(entry_id)),
            )
        stored = self.get_work_history(entry_id)
        assert stored is not None  # the row was just written in this connection
        self._record("history.work_updated", f"entry_id={int(entry_id)} current={int(stored.is_current)}")
        return stored

    def delete_work_history(self, entry_id: int) -> bool:
        """Remove one employment record; return whether a row was deleted."""
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM candidate_work_history WHERE entry_id=?", (int(entry_id),)
            )
        removed = cursor.rowcount == 1
        if removed:
            self._record("history.work_deleted", f"entry_id={int(entry_id)}")
        return removed

    def add_education(self, institution: str, qualification: str, *, discipline: str | None = None,
                      start_date: date | None = None, completion_date: date | None = None,
                      is_ongoing: bool = False) -> EducationEntry:
        """Add one education record and return it as stored.

        The duplicate rule is the same as employment's, on (institution, qualification, start date): the same
        qualification from the same place starting the same day is one record, not two.
        """
        entry = EducationEntry(institution=institution, qualification=qualification, discipline=discipline,
                               start_date=start_date, completion_date=completion_date,
                               is_ongoing=is_ongoing)
        for stored in self.list_education():
            if (stored.institution.casefold() == entry.institution.casefold()
                    and stored.qualification.casefold() == entry.qualification.casefold()
                    and stored.start_date == entry.start_date):
                raise ValueError(
                    f"You already have a record for {entry.qualification} at {entry.institution}"
                    + (f" starting {entry.start_date.isoformat()}" if entry.start_date else "")
                    + ". Edit that one instead of adding it twice."
                )
        timestamp = _now()
        with self._connection:
            cursor = self._connection.execute(
                """INSERT INTO candidate_education(institution, qualification, discipline, start_date,
                                                    completion_date, is_ongoing, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (entry.institution, entry.qualification, entry.discipline,
                 entry.start_date.isoformat() if entry.start_date else None,
                 entry.completion_date.isoformat() if entry.completion_date else None,
                 int(entry.is_ongoing), timestamp, timestamp),
            )
        stored = replace(entry, entry_id=int(cursor.lastrowid or 0), created_at=timestamp,
                         updated_at=timestamp)
        self._record("history.education_added", f"entry_id={stored.entry_id} ongoing={int(stored.is_ongoing)}")
        return stored

    def list_education(self) -> tuple[EducationEntry, ...]:
        """Every education record: ongoing study first, then the most recently finished ones.

        Within the finished records, a qualification with no completion date sorts after the dated ones
        rather than being given an invented date to sort by - "finished, date not recorded" is a real
        answer, and a missing date is not a very old one. This is the same rule the task list uses for a
        task with no due date (see :meth:`list_scheduled_tasks`).
        """
        rows = self._connection.execute(
            """SELECT * FROM candidate_education
               ORDER BY is_ongoing DESC, (completion_date IS NULL), completion_date DESC,
                        institution, entry_id"""
        ).fetchall()
        return tuple(self._decode_education(row) for row in rows)

    def get_education(self, entry_id: int) -> EducationEntry | None:
        row = self._connection.execute(
            "SELECT * FROM candidate_education WHERE entry_id=?", (int(entry_id),)
        ).fetchone()
        return None if row is None else self._decode_education(row)

    def update_education(self, entry_id: int, institution: str, qualification: str, *,
                         discipline: str | None = None, start_date: date | None = None,
                         completion_date: date | None = None, is_ongoing: bool = False) -> EducationEntry:
        """Replace one education record with the values supplied, and return it as stored."""
        current = self.get_education(entry_id)
        if current is None:
            raise ValueError(f"There is no education record {entry_id} to change.")
        updated = EducationEntry(institution=institution, qualification=qualification, discipline=discipline,
                                 start_date=start_date, completion_date=completion_date,
                                 is_ongoing=is_ongoing, entry_id=current.entry_id,
                                 created_at=current.created_at)
        for stored in self.list_education():
            if stored.entry_id == updated.entry_id:
                continue
            if (stored.institution.casefold() == updated.institution.casefold()
                    and stored.qualification.casefold() == updated.qualification.casefold()
                    and stored.start_date == updated.start_date):
                raise ValueError(
                    f"Another record already covers {updated.qualification} at {updated.institution}. "
                    "Edit that one, or change this one so the two differ."
                )
        timestamp = _now()
        with self._connection:
            self._connection.execute(
                """UPDATE candidate_education
                      SET institution=?, qualification=?, discipline=?, start_date=?, completion_date=?,
                          is_ongoing=?, updated_at=?
                    WHERE entry_id=?""",
                (updated.institution, updated.qualification, updated.discipline,
                 updated.start_date.isoformat() if updated.start_date else None,
                 updated.completion_date.isoformat() if updated.completion_date else None,
                 int(updated.is_ongoing), timestamp, int(entry_id)),
            )
        stored = self.get_education(entry_id)
        assert stored is not None  # the row was just written in this connection
        self._record("history.education_updated", f"entry_id={int(entry_id)} ongoing={int(stored.is_ongoing)}")
        return stored

    def delete_education(self, entry_id: int) -> bool:
        """Remove one education record; return whether a row was deleted."""
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM candidate_education WHERE entry_id=?", (int(entry_id),)
            )
        removed = cursor.rowcount == 1
        if removed:
            self._record("history.education_deleted", f"entry_id={int(entry_id)}")
        return removed

    def profile_record_counts(self) -> dict[str, int]:
        """How many records a profile deletion would take with it. Read-only, for asking first."""
        return {
            "work_history": int(self._connection.execute(
                "SELECT COUNT(*) FROM candidate_work_history").fetchone()[0]),
            "education": int(self._connection.execute(
                "SELECT COUNT(*) FROM candidate_education").fetchone()[0]),
        }

    @staticmethod
    def _decode_work_history(row: sqlite3.Row) -> WorkHistoryEntry:
        noun = "work-history record"
        try:
            employment_type = EmploymentType(row["employment_type"])
        except ValueError as exc:
            raise StoredRecordError(
                noun, f"its employment type {row['employment_type']!r} is not one this version recognises"
            ) from exc
        try:
            return WorkHistoryEntry(
                employer=_stored_text(row["employer"], noun, "employer"),
                job_title=_stored_text(row["job_title"], noun, "job title"),
                start_date=_stored_day(row["start_date"], noun, "start date"),
                end_date=_stored_day(row["end_date"], noun, "end date", optional=True),
                is_current=bool(row["is_current"]),
                employment_type=employment_type,
                summary=row["summary"],
                entry_id=int(row["entry_id"]), created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
        except ValueError as exc:
            # The domain refuses a period that cannot have happened, so a stored contradiction means the
            # row was written by something else or edited by hand: it is reported, never repaired.
            raise StoredRecordError(noun, f"it does not describe a possible employment period ({exc})") from exc

    @staticmethod
    def _decode_education(row: sqlite3.Row) -> EducationEntry:
        noun = "education record"
        try:
            return EducationEntry(
                institution=_stored_text(row["institution"], noun, "institution"),
                qualification=_stored_text(row["qualification"], noun, "qualification"),
                discipline=row["discipline"],
                start_date=_stored_day(row["start_date"], noun, "start date", optional=True),
                completion_date=_stored_day(row["completion_date"], noun, "completion date", optional=True),
                is_ongoing=bool(row["is_ongoing"]),
                entry_id=int(row["entry_id"]), created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
        except ValueError as exc:
            raise StoredRecordError(noun, f"it does not describe a possible period of study ({exc})") from exc

    # ------------------------------------------------------------------ background tasks
    #
    # The scheduler's persistence layer. Two properties are enforced here rather than by convention,
    # because they are the ones a process crash would otherwise break:
    #
    # * One run per scheduled occurrence and attempt. The uniqueness of (task_id, slot_key, attempt) is
    #   what makes that true; a second claimer gets an IntegrityError and is told nothing was claimed.
    # * Only the worker that claimed a run may finish it, and only while it is still running. The first
    #   outcome recorded is the one that stands, so a restarted or duplicated process cannot rewrite
    #   what happened.

    def save_scheduled_task(self, task: ScheduledTask, *,
                            now: datetime | None = None) -> ScheduledTask:
        """Store a task definition and return what the database holds afterwards.

        Only the definition is taken from the argument. The bookkeeping columns - when the task is next
        due, whether it is holding an occurrence with attempts left, and what happened last time - are
        the scheduler's record of reality, so saving a definition again cannot rewind a due task,
        duplicate a retry, or clear a failure that has not been dealt with.

        Only the *schedule-defining* fields - the times and the zone - move the next occurrence, and
        moving it drops any occurrence the task was holding, because the occurrence it owed was
        defined by the schedule that changed. Renaming a task, pointing it at a different handler, or
        changing its timeout and attempt limits leaves the timing exactly as it was: a person editing a
        task's name at 12:00:30 should not silently skip the noon occurrence that is already due.
        Enabling a disabled task computes a fresh next occurrence rather than replaying the ones that
        were missed while it was off.
        """
        if not isinstance(task, ScheduledTask):
            raise ValueError("A scheduled task must be a ScheduledTask.")
        previous = self.get_scheduled_task(task.task_id)
        moment = now or datetime.now(timezone.utc)
        schedule_defining = (task.times, task.timezone)
        previous_schedule_defining = None if previous is None else (previous.times, previous.timezone)
        recompute = (previous is None or previous_schedule_defining != schedule_defining
                     or previous.next_run_at is None)

        if not task.enabled:
            # A disabled task keeps any occurrence it was holding (the schedule is not lost, it is
            # paused) but is never due.
            next_run_at = None
            pending_slot_at = None if previous is None else previous.pending_slot_at
            pending_attempt = None if previous is None else previous.pending_attempt
        elif recompute:
            next_run_at = next_run_after(task, moment)
            pending_slot_at = None
            pending_attempt = None
        else:
            assert previous is not None  # recompute covers the only case where it could be None
            next_run_at = previous.next_run_at
            pending_slot_at = previous.pending_slot_at
            pending_attempt = previous.pending_attempt

        stamp = _iso(moment)
        created_at = stamp if previous is None or previous.created_at is None else _iso(previous.created_at)
        with self._connection:
            self._connection.execute(
                """INSERT INTO scheduled_task(
                       task_id, name, kind, timezone, schedule_times, enabled, timeout_seconds,
                       max_attempts, retry_backoff_seconds, next_run_at, pending_slot_at,
                       pending_attempt, last_run_at, last_outcome, last_error, consecutive_failures,
                       created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                       name=excluded.name, kind=excluded.kind, timezone=excluded.timezone,
                       schedule_times=excluded.schedule_times, enabled=excluded.enabled,
                       timeout_seconds=excluded.timeout_seconds, max_attempts=excluded.max_attempts,
                       retry_backoff_seconds=excluded.retry_backoff_seconds,
                       next_run_at=excluded.next_run_at, pending_slot_at=excluded.pending_slot_at,
                       pending_attempt=excluded.pending_attempt, updated_at=excluded.updated_at""",
                (
                    task.task_id, task.name, task.kind, task.timezone,
                    json.dumps(list(task.times)), int(task.enabled), task.timeout_seconds,
                    task.max_attempts, task.retry_backoff_seconds,
                    None if next_run_at is None else _iso(next_run_at),
                    None if pending_slot_at is None else _iso(pending_slot_at),
                    pending_attempt,
                    None if previous is None or previous.last_run_at is None else _iso(previous.last_run_at),
                    None if previous is None or previous.last_outcome is None else previous.last_outcome.value,
                    None if previous is None else previous.last_error,
                    0 if previous is None else previous.consecutive_failures,
                    created_at, stamp,
                ),
            )
        stored = self.get_scheduled_task(task.task_id)
        assert stored is not None  # just written, so it must read back
        self._record("task.scheduled",
                     f"id={stored.task_id} kind={stored.kind} enabled={int(stored.enabled)} "
                     f"times={','.join(stored.times)} zone={stored.timezone}")
        return stored

    def get_scheduled_task(self, task_id: str) -> ScheduledTask | None:
        """One task as stored, or ``None`` when it is not there."""
        row = self._connection.execute(
            "SELECT * FROM scheduled_task WHERE task_id = ?", (str(task_id),)
        ).fetchone()
        return None if row is None else self._decode_scheduled_task(row)

    def list_scheduled_tasks(self) -> tuple[ScheduledTask, ...]:
        """Every stored task, in a stable order (by task id)."""
        rows = self._connection.execute("SELECT * FROM scheduled_task ORDER BY task_id").fetchall()
        return tuple(self._decode_scheduled_task(row) for row in rows)

    def delete_scheduled_task(self, task_id: str) -> bool:
        """Remove a task and its run history; return whether a row was deleted."""
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM scheduled_task WHERE task_id = ?", (str(task_id),)
            )
        removed = cursor.rowcount == 1
        if removed:
            self._record("task.deleted", f"id={str(task_id)}")
        return removed

    def next_due_task(self, now: datetime | None = None) -> ScheduledTask | None:
        """The next task that is due, or ``None``. Read-only: nothing is claimed by asking."""
        stamp = _iso(now or datetime.now(timezone.utc))
        row = self._connection.execute(
            """SELECT * FROM scheduled_task
                WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at, task_id LIMIT 1""",
            (stamp,),
        ).fetchone()
        return None if row is None else self._decode_scheduled_task(row)

    def claim_due_run(self, *, worker_id: str, now: datetime | None = None) -> TaskRun | None:
        """Claim the next due occurrence for ``worker_id``, or return ``None`` if there is none.

        One transaction covers the read and the write, so two workers calling this at the same moment
        cannot both take the same occurrence: the second one's insert violates the uniqueness of
        ``(task, slot, attempt)`` and is answered with ``None`` - "nothing was claimed", not "a run
        exists", which is the distinction a caller needs to decide whether to keep looking.

        The task's bookkeeping is deliberately *not* advanced here. It is advanced when the attempt
        finishes, by :meth:`finish_run`, so a process that dies between claiming and finishing leaves
        exactly one visible trace: a run row that is still running, which
        :meth:`recover_stale_runs` then closes and re-plans.
        """
        name = str(worker_id).strip()
        if not name:
            raise ValueError("A claim needs a worker id.")
        moment = now or datetime.now(timezone.utc)
        stamp = _iso(moment)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                """SELECT * FROM scheduled_task
                    WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
                    ORDER BY next_run_at, task_id LIMIT 1""",
                (stamp,),
            ).fetchone()
            if row is None:
                self._connection.execute("COMMIT")
                return None
            task = self._decode_scheduled_task(row)
            slot_at = task.pending_slot_at or task.next_run_at
            assert slot_at is not None  # the query requires a next_run_at, and pending wins over it
            attempt = task.pending_attempt or 1
            run = self._insert_running_run(task, slot_at, attempt, name, moment)
            self._connection.execute("COMMIT")
        except BaseException:
            self._roll_back_quietly()
            raise
        if run is not None:
            self._record("task.run_started",
                         f"id={task.task_id} attempt={attempt} slot={_iso(slot_at)} worker={name}")
        return run

    def finish_run(
        self, run_id: str, state: RunState, *, detail: str = "", error: str | None = None,
        worker_id: str | None = None, now: datetime | None = None,
    ) -> TaskRun:
        """Record a run's outcome and move the task on, in one transaction.

        Refuses - with :class:`TaskRunConflict` and no write - a run that is missing, one that already
        finished, and one claimed by a different worker. The refusal is the point: a duplicated or
        restarted process must not be able to replace the record of what actually happened.
        """
        outcome = RunState(state) if not isinstance(state, RunState) else state
        if not outcome.is_terminal:
            raise ValueError(f"A run finishes in a terminal state, not {outcome.value!r}.")
        moment = now or datetime.now(timezone.utc)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT * FROM task_run WHERE run_id = ?", (str(run_id),)
            ).fetchone()
            if row is None:
                raise TaskRunConflict(f"No run {run_id!r} was found, so nothing was recorded.")
            run = self._decode_task_run(row)
            if run.state is not RunState.RUNNING:
                raise TaskRunConflict(
                    f"Run {run.run_id} already finished as {run.state.value}, so it was not changed."
                )
            if worker_id is not None and run.worker_id is not None and run.worker_id != worker_id:
                raise TaskRunConflict(
                    f"Run {run.run_id} was claimed by {run.worker_id}, not by {worker_id}, so it was "
                    "not changed."
                )
            task_row = self._connection.execute(
                "SELECT * FROM scheduled_task WHERE task_id = ?", (run.task_id,)
            ).fetchone()
            if task_row is None:
                raise TaskRunConflict(
                    f"The task {run.task_id!r} for run {run.run_id} is gone, so nothing was recorded."
                )
            task = self._decode_scheduled_task(task_row)
            update = plan_after_run(task, outcome, run.attempt, run.slot_at, moment)
            finished = _iso(moment)
            # The run history is read in the window and travels with the export, so it follows the same
            # rule as the start-up note: a location on this machine is never written into text that is
            # meant to be safe to share. Local import for the usual reason - ``diagnostics`` reports
            # *about* this module, and importing it at module level would close a cycle.
            from .diagnostics import redact_paths
            cleaned_detail = redact_paths(clean_detail(detail), database_path=self.database_path)
            cleaned_error = redact_paths(clean_detail(error), database_path=self.database_path) or None
            changed = self._connection.execute(
                """UPDATE task_run SET state = ?, finished_at = ?, heartbeat_at = ?, detail = ?, error = ?
                    WHERE run_id = ? AND state = ?""",
                (outcome.value, finished, finished, cleaned_detail, cleaned_error, run.run_id,
                 RunState.RUNNING.value),
            ).rowcount
            if changed != 1:
                raise TaskRunConflict(
                    f"Run {run.run_id} was changed by another process while this one was finishing it."
                )
            self._connection.execute(
                """UPDATE scheduled_task
                      SET next_run_at = ?, pending_slot_at = ?, pending_attempt = ?, last_run_at = ?,
                          last_outcome = ?, last_error = ?, consecutive_failures = ?, updated_at = ?
                    WHERE task_id = ?""",
                (
                    _iso(update.next_run_at),
                    None if update.pending_slot_at is None else _iso(update.pending_slot_at),
                    update.pending_attempt, finished, update.last_outcome.value, cleaned_error,
                    update.consecutive_failures, finished, task.task_id,
                ),
            )
            self._connection.execute("COMMIT")
        except BaseException:
            self._roll_back_quietly()
            raise
        updated = self.get_task_run(run_id)
        assert updated is not None  # just written, so it must read back
        # Each outcome is written out as its own call site on purpose: the event vocabulary guard in
        # the tests reads the shipped source and refuses a declared event that no call site uses, so an
        # event reached through a lookup table would be a name nothing appears to record.
        base_detail = (f"id={updated.task_id} attempt={updated.attempt} "
                       f"seconds={int(updated.duration_seconds or 0)}")
        if outcome is RunState.SUCCEEDED:
            self._record("task.run_succeeded", base_detail)
        elif outcome is RunState.REFUSED:
            self._record("task.run_refused", base_detail)
        elif outcome is RunState.INTERRUPTED:
            self._record("task.run_interrupted", base_detail)
        else:
            # A failed attempt and one that ran out of time are both failures of the attempt; the state
            # is in the detail, so the log says which without needing the table beside it.
            self._record("task.run_failed", f"{base_detail} state={outcome.value}")
        return updated

    def get_task_run(self, run_id: str) -> TaskRun | None:
        """One run as stored, or ``None`` when it is not there."""
        row = self._connection.execute(
            "SELECT * FROM task_run WHERE run_id = ?", (str(run_id),)
        ).fetchone()
        return None if row is None else self._decode_task_run(row)

    def heartbeat_run(self, run_id: str, *, worker_id: str | None = None,
                      now: datetime | None = None) -> bool:
        """Say that a running attempt is still being worked on; return whether a row was touched.

        The heartbeat is what separates "this work is in progress" from "the process that claimed this
        is gone", so it is written on every poll while an attempt runs. It never changes anything else
        about the run.
        """
        moment = now or datetime.now(timezone.utc)
        statement = "UPDATE task_run SET heartbeat_at = ? WHERE run_id = ? AND state = ?"
        parameters: list[object] = [_iso(moment), str(run_id), RunState.RUNNING.value]
        if worker_id is not None:
            statement += " AND worker_id = ?"
            parameters.append(worker_id)
        with self._connection:
            cursor = self._connection.execute(statement, tuple(parameters))
        return cursor.rowcount == 1

    def running_runs(self, *, worker_id: str | None = None) -> tuple[TaskRun, ...]:
        """Attempts that are still marked as running, oldest first."""
        statement = "SELECT * FROM task_run WHERE state = ?"
        parameters: list[object] = [RunState.RUNNING.value]
        if worker_id is not None:
            statement += " AND worker_id = ?"
            parameters.append(worker_id)
        statement += " ORDER BY created_at, attempt"
        rows = self._connection.execute(statement, tuple(parameters)).fetchall()
        return tuple(self._decode_task_run(row) for row in rows)

    def list_task_runs(self, *, task_id: str | None = None,
                       limit: int = 50) -> tuple[TaskRun, ...]:
        """Run history, newest first - the view that answers \"what has this task been doing?\"."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("The run-history limit must be a positive whole number.")
        if task_id is None:
            rows = self._connection.execute(
                """SELECT * FROM task_run ORDER BY created_at DESC, attempt DESC, run_id DESC
                    LIMIT ?""",
                (limit,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """SELECT * FROM task_run WHERE task_id = ?
                    ORDER BY created_at DESC, attempt DESC, run_id DESC LIMIT ?""",
                (str(task_id), limit),
            ).fetchall()
        return tuple(self._decode_task_run(row) for row in rows)

    def recover_stale_runs(self, stale_before: datetime, *,
                           now: datetime | None = None) -> tuple[TaskRun, ...]:
        """Close attempts whose worker stopped, and re-plan their occurrences.

        A run that is still marked as running while nothing has refreshed its heartbeat for longer than
        ``stale_before`` means the process that claimed it is gone: it cannot be reported as successful
        (nobody saw it finish) and must not be left running forever, because the task would never be due
        again. It is recorded as ``interrupted`` - the honest description - and the occurrence it served
        is then re-planned by the same rule as a failure, so the work gets its remaining attempts or the
        task returns to its schedule. Each recovery is decided by the store, in one transaction, so two
        workers starting at once cannot both re-plan the same run.
        """
        threshold = stale_before.astimezone(timezone.utc)
        rows = self._connection.execute(
            """SELECT run_id, attempt, heartbeat_at, created_at FROM task_run
                WHERE state = ? AND (heartbeat_at IS NULL OR heartbeat_at < ?)
                ORDER BY created_at, attempt""",
            (RunState.RUNNING.value, _iso(threshold)),
        ).fetchall()
        recovered: list[TaskRun] = []
        for row in rows:
            last_seen = row["heartbeat_at"] or row["created_at"]
            try:
                recovered.append(self.finish_run(
                    str(row["run_id"]), RunState.INTERRUPTED,
                    detail=f"no heartbeat since {last_seen}; the worker that claimed this attempt stopped",
                    now=now,
                ))
            except TaskRunConflict:
                # Another worker recovered it between the read and the finish. Not an error: the
                # outcome is recorded exactly once, which is what matters.
                continue
        return tuple(recovered)

    def acquire_worker_lease(self, worker_id: str, *, now: datetime | None = None,
                             stale_before: datetime | None = None) -> WorkerLease:
        """Take the right to execute this database's tasks, or refuse because another worker has it.

        Refusing is the safe default: two schedulers over one database would each run work the other
        claimed and each believe it was alone. A lease whose heartbeat has gone stale is taken over
        rather than honoured, because the previous holder is gone and a database that can never be
        scheduled again is not a safe outcome either - and the take-over is recorded, so it is visible
        afterwards rather than silent.
        """
        name = str(worker_id).strip()
        if not name:
            raise ValueError("A worker lease needs a worker id.")
        moment = now or datetime.now(timezone.utc)
        stamp = _iso(moment)
        taken_over_from: str | None = None
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._connection.execute(
                "SELECT * FROM worker_lease WHERE lease_name = ?", (_LEASE_NAME,)
            ).fetchone()
            if row is not None:
                held = self._decode_worker_lease(row)
                if held.worker_id != name:
                    fresh = stale_before is None or held.heartbeat_at >= stale_before.astimezone(timezone.utc)
                    if fresh:
                        self._roll_back_quietly()
                        self._record("worker.lease_refused",
                                     f"holder={held.worker_id} asked_by={name}")
                        raise WorkerLeaseHeld(held)
                    taken_over_from = held.worker_id
                    self._connection.execute(
                        """UPDATE worker_lease SET worker_id = ?, acquired_at = ?, heartbeat_at = ?
                            WHERE lease_name = ?""",
                        (name, stamp, stamp, _LEASE_NAME),
                    )
                else:
                    self._connection.execute(
                        "UPDATE worker_lease SET heartbeat_at = ? WHERE lease_name = ?",
                        (stamp, _LEASE_NAME),
                    )
            else:
                self._connection.execute(
                    """INSERT INTO worker_lease(lease_name, worker_id, acquired_at, heartbeat_at)
                       VALUES (?, ?, ?, ?)""",
                    (_LEASE_NAME, name, stamp, stamp),
                )
            self._connection.execute("COMMIT")
        except BaseException:
            self._roll_back_quietly()
            raise
        lease = self.get_worker_lease()
        assert lease is not None  # just written, so it must read back
        self._record("worker.lease_taken",
                     f"worker={name}" + (f" took_over_from={taken_over_from}" if taken_over_from else ""))
        return lease

    def heartbeat_worker_lease(self, worker_id: str, *, now: datetime | None = None) -> WorkerLease | None:
        """Refresh the lease if this worker holds it; ``None`` when it does not."""
        moment = now or datetime.now(timezone.utc)
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE worker_lease SET heartbeat_at = ? WHERE lease_name = ? AND worker_id = ?",
                (_iso(moment), _LEASE_NAME, str(worker_id)),
            )
        if cursor.rowcount != 1:
            return None
        return self.get_worker_lease()

    def get_worker_lease(self) -> WorkerLease | None:
        """The current lease, whoever holds it, or ``None`` when no worker is scheduled."""
        row = self._connection.execute(
            "SELECT * FROM worker_lease WHERE lease_name = ?", (_LEASE_NAME,)
        ).fetchone()
        return None if row is None else self._decode_worker_lease(row)

    def release_worker_lease(self, worker_id: str) -> bool:
        """Give up the lease; return whether this worker held it. Only the holder can release it."""
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM worker_lease WHERE lease_name = ? AND worker_id = ?",
                (_LEASE_NAME, str(worker_id)),
            )
        released = cursor.rowcount == 1
        if released:
            self._record("worker.lease_released", f"worker={worker_id}")
        return released

    def _insert_running_run(self, task: ScheduledTask, slot_at: datetime, attempt: int,
                            worker_id: str, now: datetime) -> TaskRun | None:
        """Insert the row that claims one attempt; ``None`` when another worker already has it.

        Called inside the caller's transaction. The uniqueness of ``(task, slot, attempt)`` is what
        makes this safe, so an insert that violates it is answered - after checking that this is what
        the violation actually was - with "not claimed" rather than an exception the caller would have
        to interpret.
        """
        stamp = _iso(now)
        run = TaskRun(
            run_id=uuid.uuid4().hex, task_id=task.task_id,
            slot_key=slot_key(task.task_id, slot_at), slot_at=slot_at, attempt=attempt,
            state=RunState.RUNNING, timeout_seconds=task.timeout_seconds, worker_id=worker_id,
            created_at=now, started_at=now, heartbeat_at=now,
        )
        try:
            self._connection.execute(
                """INSERT INTO task_run(run_id, task_id, slot_key, slot_at, attempt, state, worker_id,
                                        timeout_seconds, created_at, started_at, heartbeat_at, detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')""",
                (run.run_id, run.task_id, run.slot_key, _iso(run.slot_at), run.attempt,
                 run.state.value, worker_id, run.timeout_seconds, stamp, stamp, stamp),
            )
        except sqlite3.IntegrityError as exc:
            existing = self._connection.execute(
                "SELECT 1 FROM task_run WHERE task_id = ? AND slot_key = ? AND attempt = ?",
                (run.task_id, run.slot_key, run.attempt),
            ).fetchone()
            if existing is None:
                raise  # a different integrity problem is not this one, and must not be hidden
            return None
        return run

    def _roll_back_quietly(self) -> None:
        """Undo an open transaction if one is still open; the caller re-raises the real error."""
        try:
            self._connection.execute("ROLLBACK")
        except sqlite3.Error:
            # SQLite may already have unwound it (a full disk, for example). The exception the caller
            # is about to raise is what matters, and this must not replace it.
            pass

    @staticmethod
    def _decode_scheduled_task(row: sqlite3.Row) -> ScheduledTask:
        noun = "scheduled task"
        try:
            times = json.loads(row["schedule_times"])
        except json.JSONDecodeError as exc:
            raise StoredRecordError(noun, "its schedule is not readable") from exc
        if not isinstance(times, list):
            raise StoredRecordError(noun, "its schedule is not a list of times")
        try:
            return ScheduledTask(
                task_id=_stored_text(row["task_id"], noun, "task id"),
                name=_stored_text(row["name"], noun, "name"),
                kind=_stored_text(row["kind"], noun, "kind"),
                times=tuple(_stored_text_values(times, noun, "schedule times")),
                timezone=_stored_text(row["timezone"], noun, "timezone"),
                enabled=bool(row["enabled"]),
                timeout_seconds=_stored_int(row["timeout_seconds"], noun, "timeout"),
                max_attempts=_stored_int(row["max_attempts"], noun, "attempt limit"),
                retry_backoff_seconds=_stored_int(row["retry_backoff_seconds"], noun, "retry delay"),
                next_run_at=_instant_or_none(row["next_run_at"], noun, "next run"),
                pending_slot_at=_instant_or_none(row["pending_slot_at"], noun, "pending slot"),
                pending_attempt=(None if row["pending_attempt"] is None
                                 else _stored_int(row["pending_attempt"], noun, "pending attempt")),
                last_run_at=_instant_or_none(row["last_run_at"], noun, "last run"),
                last_outcome=row["last_outcome"],
                last_error=row["last_error"],
                consecutive_failures=_stored_int(row["consecutive_failures"], noun,
                                                 "consecutive-failure count"),
                created_at=_instant_or_none(row["created_at"], noun, "created"),
                updated_at=_instant_or_none(row["updated_at"], noun, "updated"),
            )
        except TaskValidationError as exc:
            raise StoredRecordError(noun, f"it could not be read as a task ({exc})") from exc

    @staticmethod
    def _decode_task_run(row: sqlite3.Row) -> TaskRun:
        noun = "background task run"
        try:
            return TaskRun(
                run_id=_stored_text(row["run_id"], noun, "id"),
                task_id=_stored_text(row["task_id"], noun, "task id"),
                slot_key=_stored_text(row["slot_key"], noun, "scheduled occurrence"),
                slot_at=_instant_or_none(row["slot_at"], noun, "scheduled instant"),
                attempt=_stored_int(row["attempt"], noun, "attempt"),
                state=row["state"],
                timeout_seconds=_stored_int(row["timeout_seconds"], noun, "timeout"),
                worker_id=row["worker_id"],
                created_at=_instant_or_none(row["created_at"], noun, "created"),
                started_at=_instant_or_none(row["started_at"], noun, "started"),
                finished_at=_instant_or_none(row["finished_at"], noun, "finished"),
                heartbeat_at=_instant_or_none(row["heartbeat_at"], noun, "heartbeat"),
                detail=row["detail"] or "",
                error=row["error"],
            )
        except TaskValidationError as exc:
            raise StoredRecordError(noun, f"it could not be read as a run ({exc})") from exc

    @staticmethod
    def _decode_worker_lease(row: sqlite3.Row) -> WorkerLease:
        noun = "worker lease"
        try:
            return WorkerLease(
                lease_name=_stored_text(row["lease_name"], noun, "name"),
                worker_id=_stored_text(row["worker_id"], noun, "worker"),
                acquired_at=_instant_or_none(row["acquired_at"], noun, "acquired"),
                heartbeat_at=_instant_or_none(row["heartbeat_at"], noun, "heartbeat"),
            )
        except TaskValidationError as exc:
            raise StoredRecordError(noun, f"it could not be read as a lease ({exc})") from exc

    def _check_tracker_invariants(self, tracker: ApplicationTracker, stored: ApplicationTracker | None) -> None:
        """Refuse tracker writes that contradict the domain state machine.

        ``stored`` is the row already on disk, or ``None`` when this write creates the
        record. Confirmation is only ever *earned*: ``candidate_confirmed`` may be true
        only for a record that already carried the flag or that is being confirmed now,
        so a later status can keep or drop a real confirmation but cannot invent one.
        """
        # The follow-up plan is checked here as well as where it is set, because storage is the last
        # place a rule can be enforced: a note with no day would be a reminder nobody is ever shown.
        if tracker.follow_up_on is not None:
            validate_follow_up_date(tracker.follow_up_on)
            validate_follow_up_note(tracker.follow_up_note)
        elif tracker.follow_up_note:
            raise ValueError(
                "A follow-up note needs a day to appear on. Nothing was saved."
            )
        if tracker.status is ApplicationStatus.CONFIRMED:
            # The same evidence floor the domain applies, enforced again here so a caller cannot
            # bypass it by writing straight to storage. Storage can prove the field is filled with
            # something substantive; only the candidate can assert that it is true.
            require_confirmation_evidence(tracker.status_evidence)
        if stored is None:
            if tracker.status is not INITIAL_APPLICATION_STATUS:
                raise ValueError(
                    f"A new application record must start at {INITIAL_APPLICATION_STATUS.value}, "
                    f"not {tracker.status.value}; advance it with ApplicationTracker.transition. "
                    "Nothing was saved."
                )
            if tracker.candidate_confirmed:
                raise ValueError(
                    "A new application record cannot claim candidate confirmation; confirmation "
                    "requires a recorded transition with evidence. Nothing was saved."
                )
            return
        if not is_allowed_tracker_transition(stored.status, tracker.status):
            raise ValueError(
                f"Invalid application transition: {stored.status.value} -> {tracker.status.value}. "
                "Update the status through ApplicationTracker.transition."
            )
        if tracker.candidate_confirmed and not (stored.candidate_confirmed or tracker.status is ApplicationStatus.CONFIRMED):
            raise ValueError(
                "candidate_confirmed cannot be true before a confirmation is recorded: expected a "
                f"stored confirmation or a transition to {ApplicationStatus.CONFIRMED.value}, "
                f"not {tracker.status.value}."
            )

    def get_tracker_raw(self, listing_id: str) -> dict | None:
        """The stored tracker row exactly as persisted, or ``None`` when there is no record.

        Deliberately uninterpreted: a list view or an export can show a legacy or unexpected status
        as it is stored, and a read never fails because one row holds a value this build does not
        know. ``updated_at`` is when the app last wrote this record locally, not anything the
        employer or the source said. This is read-only; it never writes, repairs, migrates, or
        deletes anything.
        """
        row = self._connection.execute(
            """SELECT status, status_evidence, candidate_confirmed, updated_at, follow_up_on,
                      follow_up_note
                 FROM application_tracker WHERE listing_id=?""",
            (listing_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "status": row["status"], "status_evidence": row["status_evidence"],
            "candidate_confirmed": bool(row["candidate_confirmed"]), "updated_at": row["updated_at"],
            "follow_up_on": row["follow_up_on"], "follow_up_note": row["follow_up_note"],
        }

    @staticmethod
    def _decode_tracker(row: sqlite3.Row) -> ApplicationTracker:
        """One ``application_tracker`` row as a record, refusing a status this build cannot name.

        Shared by every reader of the table so the same damaged row produces the same refusal rather than
        three slightly different behaviours.
        """
        try:
            status = ApplicationStatus(row["status"])
        except ValueError as exc:
            raise TrackerStatusError(row["status"]) from exc
        return ApplicationTracker(
            listing_id=row["listing_id"], status=status,
            status_evidence=row["status_evidence"], candidate_confirmed=bool(row["candidate_confirmed"]),
            follow_up_on=_stored_date(row["follow_up_on"], row["listing_id"]),
            follow_up_note=row["follow_up_note"],
        )

    def list_trackers(self) -> tuple[ApplicationTracker, ...]:
        """Every application record, oldest first, in one query.

        The counterpart to :meth:`list_follow_up_trackers` for callers that need the whole table rather
        than the records carrying a reminder - the progress report adds up every application, not only the
        ones with a day set. Read-only, and each row is decoded by the same function as a single
        :meth:`get_tracker`, so an unreadable stored value is reported rather than quietly skipped.
        """
        rows = self._connection.execute(
            """SELECT listing_id, status, status_evidence, candidate_confirmed, follow_up_on, follow_up_note
                 FROM application_tracker
                ORDER BY rowid"""
        ).fetchall()
        return tuple(self._decode_tracker(row) for row in rows)

    def list_follow_up_trackers(self) -> tuple[ApplicationTracker, ...]:
        """Every application that has a follow-up day recorded, soonest day first.

        Read straight from the column, so a person's whole reminder list costs one query rather than a
        read per application, and a record with no day is not read at all. A record whose stored day
        cannot be parsed is reported as unreadable rather than skipped: silently dropping one reminder
        would hide exactly the thing this list exists to show.
        """
        rows = self._connection.execute(
            """SELECT listing_id, status, status_evidence, candidate_confirmed, follow_up_on,
                      follow_up_note
                 FROM application_tracker
                WHERE follow_up_on IS NOT NULL
                ORDER BY follow_up_on, listing_id"""
        ).fetchall()
        return tuple(self._decode_tracker(row) for row in rows)

    def get_record_times(self, listing_id: str) -> dict | None:
        """When this device first and last wrote a listing, or ``None`` when it is not stored.

        These are the application's own observation times: ``first_seen_at`` is never rewritten by a
        later save, while ``last_seen_at`` moves with every save. The store has no source publication
        or update date, so these values must never be shown as one.
        """
        row = self._connection.execute(
            "SELECT first_seen_at, last_seen_at FROM job_listings WHERE listing_id=?", (listing_id,)
        ).fetchone()
        if row is None:
            return None
        return {"first_seen_at": row["first_seen_at"], "last_seen_at": row["last_seen_at"]}

    def get_tracker(self, listing_id: str) -> ApplicationTracker | None:
        """The stored tracker record, or ``None`` when the listing has no record.

        Raises :class:`TrackerStatusError` (a ``ValueError``) instead of a bare enum error when the
        stored status is not one this build recognises, so callers refuse safely and can say why.
        """
        row = self._connection.execute(
            """SELECT listing_id, status, status_evidence, candidate_confirmed, follow_up_on,
                      follow_up_note
                 FROM application_tracker WHERE listing_id=?""",
            (listing_id,),
        ).fetchone()
        return None if row is None else self._decode_tracker(row)

    def delete_profile(self) -> bool:
        """Delete the candidate's profile **and** the history records that belong to it.

        The employment and education records are the detail behind the profile's summary fields, so leaving
        them behind on a "delete my profile" would keep the most identifying data on disk while telling the
        person their profile was removed. They go with it, in one transaction - and because that is a
        destructive decision, the interface asks first using :meth:`profile_record_counts`, which is what
        makes the counts in the confirmation real rather than guessed.

        Returns whether a profile row was deleted. Records with no profile row are still removed, because the
        person asked for their candidate data to go, not for a row of it to go.
        """
        counts = self.profile_record_counts()
        with self._connection:
            self._connection.execute("DELETE FROM candidate_work_history")
            self._connection.execute("DELETE FROM candidate_education")
            cursor = self._connection.execute("DELETE FROM candidate_profile WHERE profile_id=1")
        removed = cursor.rowcount > 0
        if removed or counts["work_history"] or counts["education"]:
            # The counts are in the log line because "delete my profile" removing eleven records should be
            # visible afterwards, in the one place that records what this application did.
            self._record("profile.deleted", f"work_history={counts['work_history']} "
                                            f"education={counts['education']}")
        return removed

    def delete_job(self, listing_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute("DELETE FROM job_listings WHERE listing_id=?", (listing_id,))
        removed = cursor.rowcount > 0
        if removed:
            self._record("job.deleted", f"id={listing_id}")
        return removed

    @staticmethod
    def _decode_job(payload: str) -> JobListing:
        noun = "job listing"
        values = _stored_object(payload, noun)
        raw_status = values.get("availability_status")
        try:
            values["availability_status"] = Availability(raw_status)
        except ValueError as exc:
            raise StoredRecordError(
                noun,
                "it has no saved availability status" if raw_status is None
                else f"its saved availability status {raw_status!r} is not one this version recognises",
            ) from exc
        values["eligible_countries"] = tuple(_stored_text_values(values.get("eligible_countries"), noun, "eligible_countries"))
        for key in ("allowed_work_authorizations", "allowed_degree_disciplines", "allowed_study_statuses", "allowed_graduation_years"):
            if values.get(key) is not None:
                values[key] = tuple(_stored_text_values(values[key], noun, key))
        values["required_skills"] = frozenset(_stored_text_values(values.get("required_skills"), noun, "required_skills"))
        try:
            return JobListing(**values)
        except TypeError as exc:
            raise StoredRecordError(noun, f"it holds field(s) this version cannot use ({exc})") from exc


# ---------------------------------------------------------------- reading a file without opening it
#
# The doctor's question is "can this app read the data on this machine?" and the store answers it by
# *opening* the file, which also updates an older schema - a change the doctor promises never to make. So
# the check below reads the same payloads through a read-only connection and the same decoders the read
# paths use, which is the only way the two answers can agree.

#: The payloads this build knows how to read, as ``(table, identifier column, decoder)``. A table missing
#: from a file is not a problem here: an older file simply has fewer tables, and the doctor reports the
#: schema version it found separately.
_RECORD_DECODERS: tuple[tuple[str, str, Callable[[sqlite3.Row], object]], ...] = (
    ("candidate_profile", "profile_id", lambda row: CareerStore._decode_profile(row["payload"])),
    ("job_listings", "listing_id", lambda row: CareerStore._decode_job(row["payload"])),
    ("application_tracker", "listing_id", CareerStore._decode_tracker),
    ("application_activity", "activity_id", CareerStore._decode_activity),
    ("application_preparation", "preparation_id", CareerStore._decode_preparation),
    ("interview_round", "round_id", CareerStore._decode_interview),
    ("candidate_work_history", "entry_id", CareerStore._decode_work_history),
    ("candidate_education", "entry_id", CareerStore._decode_education),
    ("scheduled_task", "task_id", CareerStore._decode_scheduled_task),
    ("task_run", "run_id", CareerStore._decode_task_run),
    ("worker_lease", "worker_id", CareerStore._decode_worker_lease),
)

#: How many rows of each kind are read before the scan stops looking. A database in this application holds
#: hundreds of rows at most, so this is not a limit anybody reaches; it exists so a damaged file cannot make
#: a read-only check run for an unbounded time.
MAX_SCANNED_ROWS = 5000


def unreadable_stored_records(database_path: str | Path) -> tuple[str, ...]:
    """Every stored record this build cannot read, one plain sentence each. Read-only, creates nothing.

    This is the check that makes ``--doctor`` able to say what the app would say when it opens the file. A
    structural check alone answers "is this a database" - it counts rows and verifies references - and a
    file can pass all of that while holding a status, availability value or payload this build cannot
    interpret. Those rows are exactly what turns into a refusal on every read path, so the doctor looks for
    them by decoding through the same functions the read paths use.

    Nothing is written: the connection is opened ``mode=ro``, so the file cannot be modified, and no
    migration runs - which is why this is safe to call on a file an older version wrote. A missing file
    yields nothing, because there is nothing to read; a file that cannot be opened at all raises the
    ``sqlite3.Error`` the caller already reports.
    """
    path = Path(database_path)
    if not path.exists():
        return ()
    problems: list[str] = []
    # The URI helper is imported from the backup module so spaces and other special characters in a path
    # are escaped the same way everywhere in the program. Imported here rather than at the top of the file
    # because ``backup`` imports this module.
    from .backup import read_only_uri

    connection = sqlite3.connect(read_only_uri(path), uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table, identifier, decoder in _RECORD_DECODERS:
            if table not in tables:
                continue
            # The table name is one of the constants above, never anything a caller supplies.
            rows = connection.execute(f"SELECT * FROM {table} LIMIT {MAX_SCANNED_ROWS}").fetchall()
            for row in rows:
                try:
                    decoder(row)
                except (StoredRecordError, TrackerStatusError) as exc:
                    problems.append(f"{exc} (in the '{table}' table, record {row[identifier]!r})")
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    # A decoder that raises something unnamed is still a record this build cannot read: the
                    # report says so with the values it can name, never with the record's contents.
                    problems.append(
                        f"The saved record in the '{table}' table (record {row[identifier]!r}) could not be "
                        f"read ({type(exc).__name__}: {exc}). It was not changed."
                    )
    finally:
        connection.close()
    return tuple(problems)
