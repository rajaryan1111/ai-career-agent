"""Local persistence for AI Career Agent; storage is local and has no network code.

Holds the SQLite store and the owner-only file primitives shared with the desktop
export and with database backup/restore: one place decides what "owner-only" means and
what the schema contract is, so the database, exported candidate data and backup files
cannot drift apart.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from datetime import datetime, timezone
import errno
import json
import os
import sqlite3
from pathlib import Path

from .core import (
    INITIAL_APPLICATION_STATUS, ApplicationStatus, ApplicationTracker, Availability,
    CandidateProfile, JobListing, duplicate_key, is_allowed_tracker_transition,
    require_confirmation_evidence,
)

_SCHEMA_VERSION = 2

#: Public names for the schema contract. ``career_agent.backup`` validates a candidate backup file
#: against these instead of repeating the schema, so the two can never disagree (a drift test in
#: ``tests/test_backup.py`` compares them with a freshly initialised database).
SCHEMA_VERSION = _SCHEMA_VERSION
SCHEMA_TABLES = ("application_tracker", "candidate_profile", "job_listings", "notification_records", "schedule_definitions", "run_records")

# Notification status values for the persistent store.
class NotificationStatus(str, Enum):
    """Status of a notification record in the persistent store."""
    PENDING = "pending"
    SHOWN = "shown"
    DISMISSED = "dismissed"
    ARCHIVED = "archived"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class NotificationRecord:
    """Persistent record of a notification, survives app restarts."""
    id: str
    type: str
    title: str
    message: str
    timestamp: str  # ISO format when created
    scheduled_time: str | None = None  # ISO format when next reminder is due
    status: NotificationStatus = NotificationStatus.PENDING
    dedup_key: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_by: str | None = None

#: Owner read/write only: the database holds candidate PII and should not be group/world readable.
_OWNER_ONLY_MODE = 0o600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def _json_default(value):
    if isinstance(value, (set, frozenset, tuple)):
        return sorted(value)
    if isinstance(value, (ApplicationStatus, Availability)):
        return value.value
    if isinstance(value, Enum):
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

    def _initialize(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version > _SCHEMA_VERSION:
            self._connection.close()
            raise RuntimeError(f"Database schema {version} is newer than supported schema {_SCHEMA_VERSION}.")
        with self._connection:
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS candidate_profile (
                    profile_id INTEGER PRIMARY KEY CHECK (profile_id = 1),
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_listings (
                    listing_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    duplicate_key TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_job_duplicate_key ON job_listings(duplicate_key);
                CREATE TABLE IF NOT EXISTS application_tracker (
                    listing_id TEXT PRIMARY KEY REFERENCES job_listings(listing_id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    status_evidence TEXT,
                    candidate_confirmed INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    scheduled_time TEXT,
                    status TEXT NOT NULL,
                    dedup_key TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    created_by TEXT,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schedule_definitions (
                    schedule_id TEXT PRIMARY KEY,
                    cron_expression TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_run_at TEXT,
                    next_run_at TEXT
                );
                CREATE TABLE IF NOT EXISTS run_records (
                    run_id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL REFERENCES schedule_definitions(schedule_id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    exit_code INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );
            """)
            self._connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    def save_profile(self, profile: CandidateProfile) -> None:
        payload = json.dumps(asdict(profile), sort_keys=True, default=_json_default)
        with self._connection:
            self._connection.execute(
                """INSERT INTO candidate_profile(profile_id, payload, updated_at) VALUES (1, ?, ?)
                   ON CONFLICT(profile_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""",
                (payload, _now()),
            )

    def get_profile(self) -> CandidateProfile | None:
        row = self._connection.execute("SELECT payload FROM candidate_profile WHERE profile_id=1").fetchone()
        if row is None:
            return None
        noun = "candidate profile"
        values = _stored_object(row["payload"], noun)
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

    def save_tracker(self, tracker: ApplicationTracker, *, expected: dict | None = None) -> None:
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
        """
        stored = self.get_tracker(tracker.listing_id)
        self._check_tracker_invariants(tracker, stored)
        timestamp = _now()
        if expected is not None:
            # One statement, so there is no window between checking and writing, and it is committed
            # before ``rowcount`` is interpreted: a conditional write left open in a transaction would
            # be invisible to the very read (often on another connection) that verifies it.
            # ``status_evidence`` is compared with IFNULL because a stored NULL and an absent note mean
            # the same thing.
            with self._connection:
                cursor = self._connection.execute(
                    """UPDATE application_tracker
                          SET status = ?, status_evidence = ?, candidate_confirmed = ?, updated_at = ?
                        WHERE listing_id = ? AND status = ? AND IFNULL(status_evidence, '') = ?
                          AND candidate_confirmed = ?""",
                    (tracker.status.value, tracker.status_evidence, int(tracker.candidate_confirmed),
                     timestamp, tracker.listing_id, str(expected.get("status")),
                     str(expected.get("status_evidence") or ""),
                     int(bool(expected.get("candidate_confirmed")))),
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
                    """INSERT INTO application_tracker(listing_id, status, status_evidence, candidate_confirmed, updated_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(listing_id) DO UPDATE SET status=excluded.status,
                         status_evidence=excluded.status_evidence, candidate_confirmed=excluded.candidate_confirmed,
                         updated_at=excluded.updated_at""",
                    (tracker.listing_id, tracker.status.value, tracker.status_evidence,
                     int(tracker.candidate_confirmed), timestamp),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Save the job listing before its application tracker.") from exc

    def _check_tracker_invariants(self, tracker: ApplicationTracker, stored: ApplicationTracker | None) -> None:
        """Refuse tracker writes that contradict the domain state machine.

        ``stored`` is the row already on disk, or ``None`` when this write creates the
        record. Confirmation is only ever *earned*: ``candidate_confirmed`` may be true
        only for a record that already carried the flag or that is being confirmed now,
        so a later status can keep or drop a real confirmation but cannot invent one.
        """
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
            "SELECT status, status_evidence, candidate_confirmed, updated_at FROM application_tracker WHERE listing_id=?",
            (listing_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "status": row["status"], "status_evidence": row["status_evidence"],
            "candidate_confirmed": bool(row["candidate_confirmed"]), "updated_at": row["updated_at"],
        }

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
            "SELECT listing_id, status, status_evidence, candidate_confirmed FROM application_tracker WHERE listing_id=?",
            (listing_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            status = ApplicationStatus(row["status"])
        except ValueError as exc:
            raise TrackerStatusError(row["status"]) from exc
        return ApplicationTracker(
            listing_id=row["listing_id"], status=status,
            status_evidence=row["status_evidence"], candidate_confirmed=bool(row["candidate_confirmed"]),
        )

    def delete_profile(self) -> bool:
        with self._connection:
            cursor = self._connection.execute("DELETE FROM candidate_profile WHERE profile_id=1")
        return cursor.rowcount > 0

    def delete_job(self, listing_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute("DELETE FROM job_listings WHERE listing_id=?", (listing_id,))
        return cursor.rowcount > 0

    def _decode_job(self, payload: str) -> JobListing:
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

    # --------------------------------------------------------------- notification

    def save_notification(self, notification: NotificationRecord) -> NotificationRecord:
        """Persist a notification record."""
        with self._connection:
            self._connection.execute(
                """INSERT INTO notification_records
                   (notification_id, type, title, message, timestamp, scheduled_time,
                    status, dedup_key, retry_count, max_retries, created_by, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (notification.id, notification.type, notification.title, notification.message,
                 notification.timestamp, notification.scheduled_time, notification.status.value,
                 notification.dedup_key, notification.retry_count, notification.max_retries,
                 notification.created_by, notification.timestamp),
            )
        return notification

    def list_notifications(self, status: str | None = None) -> tuple[NotificationRecord, ...]:
        """List notification records, optionally filtered by status.

        Args:
            status: Filter by status string (e.g. 'pending', 'shown', 'dismissed', 'archived').
                    If None, all records are returned.

        Returns:
            Tuple of NotificationRecord objects, ordered by recorded_at descending.
        """
        query = "SELECT * FROM notification_records"
        params: list[object] = []
        if status is not None:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY recorded_at DESC"
        rows = self._connection.execute(query, params).fetchall()
        return tuple(
            NotificationRecord(
                id=row['notification_id'],
                type=row['type'],
                title=row['title'],
                message=row['message'],
                timestamp=row['timestamp'],
                scheduled_time=row['scheduled_time'] if 'scheduled_time' in row.keys() else None,
                status=NotificationStatus(row['status']),
                dedup_key=row['dedup_key'] if 'dedup_key' in row.keys() else None,
                retry_count=row['retry_count'] if 'retry_count' in row.keys() else 0,
                max_retries=row['max_retries'] if 'max_retries' in row.keys() else 3,
                created_by=row['created_by'] if 'created_by' in row.keys() else None,
            )
            for row in rows
        )

    def get_pending_notifications(self) -> tuple[NotificationRecord, ...]:
        """Return all notification records with status PENDING.

        Returns:
            Tuple of NotificationRecord objects with PENDING status, ordered by recorded_at descending.
        """
        return self.list_notifications(status=NotificationStatus.PENDING.value)

    def clear_notifications(self, dedup_keys: tuple[str, ...] = ()) -> int:
        """Clear notifications by dedup keys.

        Deletes all notification records whose dedup_key is in the given tuple.
        Returns the number of deleted rows.
        """
        if not dedup_keys:
            return 0
        # Collect notification IDs matching the dedup keys
        placeholders = ','.join('?' * len(dedup_keys))
        rows = self._connection.execute(
            f"SELECT notification_id FROM notification_records WHERE dedup_key IN ({placeholders})",
            dedup_keys,
        ).fetchall()
        notification_ids = [row["notification_id"] for row in rows]
        if not notification_ids:
            return 0
        return self.clear_notifications_by_ids(notification_ids)

    def get_notification(self, notification_id: str) -> NotificationRecord | None:
        """Retrieve a notification record by ID."""
        row = self._connection.execute(
            "SELECT * FROM notification_records WHERE notification_id=?",
            (notification_id,),
        ).fetchone()
        if row is None:
            return None
        # dataclasses imported at module level, dataclass
        # NotificationStatus is defined in this module
        values = dict(row)
        values['status'] = NotificationStatus(values['status'])
        # Convert to NotificationRecord - need to handle the dataclass fields
        return NotificationRecord(
            id=values['notification_id'],
            type=values['type'],
            title=values['title'],
            message=values['message'],
            timestamp=values['timestamp'],
            scheduled_time=values.get('scheduled_time'),
            status=NotificationStatus(values['status']),
            dedup_key=values.get('dedup_key'),
            retry_count=values.get('retry_count', 0),
            max_retries=values.get('max_retries', 3),
            created_by=values.get('created_by'),
        )

    def update_notification_status(self, notification_id: str, status: str | NotificationStatus, retry_count: int = 0) -> None:
        """Update the status of a notification record."""
        status_val = status.value if isinstance(status, NotificationStatus) else status
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE notification_records SET status=?, retry_count=? WHERE notification_id=?",
                (status_val, retry_count, notification_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Notification {notification_id} not found")

    def clear_notifications_by_ids(self, notification_ids: list[str]) -> int:
        """Clear notifications by their IDs. Returns the number of deleted rows."""
        with self._connection:
            placeholders = ','.join('?' * len(notification_ids))
            cursor = self._connection.execute(
                f"DELETE FROM notification_records WHERE notification_id IN ({placeholders})",
                notification_ids,
            )
            return cursor.rowcount

    # --------------------------------------------------------------- schedule

    def save_schedule_definition(self, definition) -> None:
        """Persist a schedule definition."""
        from .scheduler import ScheduleDefinition  # local import to avoid circular dependency
        definition = definition if isinstance(definition, ScheduleDefinition) else ScheduleDefinition(**definition)
        with self._connection:
            self._connection.execute(
                """INSERT OR REPLACE INTO schedule_definitions
                   (schedule_id, cron_expression, timezone, created_at, last_run_at, next_run_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (definition.id, definition.cron_expression, definition.timezone,
                 definition.created_at or _now(), definition.last_run_at, definition.next_run_at),
            )

    def list_schedule_definitions(self) -> list[dict]:
        """List all schedule definitions."""
        rows = self._connection.execute(
            "SELECT schedule_id, cron_expression, timezone, created_at, last_run_at, next_run_at FROM schedule_definitions"
        ).fetchall()
        return [
            {
                'schedule_id': row['schedule_id'],
                'cron_expression': row['cron_expression'],
                'timezone': row['timezone'],
                'created_at': row['created_at'],
                'last_run_at': row['last_run_at'],
                'next_run_at': row['next_run_at'],
            }
            for row in rows
        ]

    def get_schedule_definition(self, schedule_id: str) -> dict | None:
        """Get a schedule definition by ID."""
        row = self._connection.execute(
            "SELECT schedule_id, cron_expression, timezone, created_at, last_run_at, next_run_at FROM schedule_definitions WHERE schedule_id=?",
            (schedule_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            'schedule_id': row['schedule_id'],
            'cron_expression': row['cron_expression'],
            'timezone': row['timezone'],
            'created_at': row['created_at'],
            'last_run_at': row['last_run_at'],
            'next_run_at': row['next_run_at'],
        }

    def save_run_record(self, run_id: str, schedule_id: str, status: str, started_at: str) -> None:
        """Persist a run record."""
        with self._connection:
            self._connection.execute(
                """INSERT OR REPLACE INTO run_records
                   (run_id, schedule_id, status, started_at)
                   VALUES (?, ?, ?, ?)""",
                (run_id, schedule_id, status, started_at),
            )

    def get_run_record(self, run_id: str) -> dict | None:
        """Get a run record by ID."""
        row = self._connection.execute(
            "SELECT run_id, schedule_id, status, started_at, completed_at, exit_code, error_message, created_at FROM run_records WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            'run_id': row['run_id'],
            'schedule_id': row['schedule_id'],
            'status': row['status'],
            'started_at': row['started_at'],
            'completed_at': row['completed_at'],
            'exit_code': row['exit_code'],
            'error_message': row['error_message'],
            'created_at': row['created_at'],
        }

    def list_run_records(self, schedule_id: str | None = None) -> list[dict]:
        """List run records, optionally filtered by schedule_id."""
        if schedule_id:
            rows = self._connection.execute(
                "SELECT run_id, schedule_id, status, started_at, completed_at, exit_code, error_message, created_at FROM run_records WHERE schedule_id=? ORDER BY started_at DESC",
                (schedule_id,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT run_id, schedule_id, status, started_at, completed_at, exit_code, error_message, created_at FROM run_records ORDER BY started_at DESC"
            ).fetchall()
        return [
            {
                'run_id': row['run_id'],
                'schedule_id': row['schedule_id'],
                'status': row['status'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at'],
                'exit_code': row['exit_code'],
                'error_message': row['error_message'],
                'created_at': row['created_at'],
            }
            for row in rows
        ]


