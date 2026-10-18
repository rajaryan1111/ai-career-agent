"""SQLite persistence for AI Career Agent; storage is local and has no network code.

Schema version 2 makes two guarantees that the UI relies on:

* An application attempt is addressed by ``(listing_id, attempt_number)`` so a
  re-application after withdrawal is a new, separate record rather than a revived one.
* Every persisted change appends an immutable row to ``application_events``, so the
  evidence behind a confirmation survives later status changes.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from .core import (
    ApplicationEvent, ApplicationStatus, ApplicationTracker, Availability, CandidateProfile,
    JobListing, REAPPLICATION_ALLOWED_FROM, TERMINAL_STATUSES, _TRACKER_TRANSITIONS,
    duplicate_key,
)

_SCHEMA_VERSION = 2

_STATUS_VALUES = ", ".join(f"'{status.value}'" for status in ApplicationStatus)

# A duplicate observation only blocks a sibling once it has actually been committed to.
# A merely discovered sibling is not yet an application and must not freeze the other.
_DUPLICATE_NON_BLOCKING = TERMINAL_STATUSES | {ApplicationStatus.DISCOVERED}


class StaleApplicationError(ValueError):
    """Persisted application changed since it was read; reload before saving."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_default(value):
    if isinstance(value, (set, frozenset, tuple)):
        return sorted(value)
    if isinstance(value, (ApplicationStatus, Availability)):
        return value.value
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


class CareerStore:
    """Small explicit local store. Pass a path; no database is created implicitly."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        try:
            self._initialize()
        except Exception:
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CareerStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------ schema

    def _initialize(self) -> None:
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version > _SCHEMA_VERSION:
            raise RuntimeError(f"Database schema {version} is newer than supported schema {_SCHEMA_VERSION}.")
        if version == _SCHEMA_VERSION:
            return
        # Table rebuilds are only safe with foreign keys disabled, and the pragma is a
        # no-op inside a transaction, so it is toggled around the migration block.
        self._connection.execute("PRAGMA foreign_keys = OFF")
        try:
            with self._connection:
                if self._has_table("application_tracker"):
                    self._migrate_to_v2()
                else:
                    self._create_schema_v2()
                self._connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        finally:
            self._connection.execute("PRAGMA foreign_keys = ON")

    def _has_table(self, name: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return row is not None

    def _create_schema_v2(self) -> None:
        self._connection.executescript(f"""
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
        """)
        self._create_application_tables()

    def _create_application_tables(self) -> None:
        self._connection.executescript(f"""
            CREATE TABLE IF NOT EXISTS application_tracker (
                listing_id TEXT NOT NULL REFERENCES job_listings(listing_id) ON DELETE CASCADE,
                attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
                status TEXT NOT NULL CHECK (status IN ({_STATUS_VALUES})),
                status_evidence TEXT,
                candidate_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (candidate_confirmed IN (0, 1)),
                revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
                updated_at TEXT NOT NULL,
                PRIMARY KEY (listing_id, attempt_number),
                CHECK (status <> 'confirmed'
                       OR (status_evidence IS NOT NULL AND length(trim(status_evidence)) > 0))
            );
            CREATE TABLE IF NOT EXISTS application_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL CHECK (to_status IN ({_STATUS_VALUES})),
                evidence TEXT,
                candidate_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (candidate_confirmed IN (0, 1)),
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (listing_id, attempt_number)
                    REFERENCES application_tracker(listing_id, attempt_number) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_application_events_attempt
                ON application_events(listing_id, attempt_number, event_id);
        """)

    def _migrate_to_v2(self) -> None:
        """Upgrade a v1 database in place, keeping every existing tracker row.

        Each legacy tracker becomes attempt 1 with revision 0. History cannot be
        reconstructed, so no event rows are fabricated for the pre-migration past.
        """
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(application_tracker)")
        }
        if "attempt_number" not in columns:
            self._connection.execute("ALTER TABLE application_tracker RENAME TO application_tracker_v1")
            self._create_application_tables()
            try:
                self._connection.execute(
                    """INSERT INTO application_tracker(
                           listing_id, attempt_number, status, status_evidence,
                           candidate_confirmed, revision, updated_at)
                       SELECT listing_id, 1, status, status_evidence,
                              candidate_confirmed, 0, updated_at
                       FROM application_tracker_v1"""
                )
            except sqlite3.IntegrityError as exc:
                raise RuntimeError(
                    "Existing tracker rows violate the schema-2 constraints "
                    f"(invalid status or confirmed without evidence): {exc}"
                ) from exc
            self._connection.execute("DROP TABLE application_tracker_v1")
        else:
            self._create_application_tables()

    # ----------------------------------------------------------------- profile

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
        values = json.loads(row["payload"])
        for key in ("skills", "preferred_locations", "preferred_work_modes", "preferred_role_types"):
            values[key] = frozenset(values.get(key) or [])
        return CandidateProfile(**values)

    def delete_profile(self) -> bool:
        with self._connection:
            cursor = self._connection.execute("DELETE FROM candidate_profile WHERE profile_id=1")
        return cursor.rowcount > 0

    # -------------------------------------------------------------------- jobs

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

    def job_timestamps(self, listing_id: str) -> tuple[str, str] | None:
        """Return ``(first_seen_at, last_seen_at)`` for a stored listing."""
        row = self._connection.execute(
            "SELECT first_seen_at, last_seen_at FROM job_listings WHERE listing_id=?",
            (listing_id,),
        ).fetchone()
        return (row["first_seen_at"], row["last_seen_at"]) if row else None

    def attempt_updated_at(self, listing_id: str, attempt_number: int) -> str | None:
        row = self._connection.execute(
            "SELECT updated_at FROM application_tracker WHERE listing_id=? AND attempt_number=?",
            (listing_id, attempt_number),
        ).fetchone()
        return row["updated_at"] if row else None

    def has_data(self) -> bool:
        """True when any user record exists, so a restore cannot silently overwrite it."""
        for table in ("candidate_profile", "job_listings", "application_tracker", "application_events"):
            if self._connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                return True
        return False

    def delete_all_data(self) -> dict[str, int]:
        """Delete every local candidate record in one transaction.

        Returns the number of removed rows per table so the UI can report what
        happened. An empty database is a no-op with zero counts.
        """
        with self._connection:
            counts = {
                "profile": self._connection.execute("SELECT COUNT(*) FROM candidate_profile").fetchone()[0],
                "jobs": self._connection.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0],
                "attempts": self._connection.execute("SELECT COUNT(*) FROM application_tracker").fetchone()[0],
                "events": self._connection.execute("SELECT COUNT(*) FROM application_events").fetchone()[0],
            }
            self._connection.execute("DELETE FROM application_events")
            self._connection.execute("DELETE FROM application_tracker")
            self._connection.execute("DELETE FROM job_listings")
            self._connection.execute("DELETE FROM candidate_profile")
        return counts

    def import_snapshot(
        self, *, profile: CandidateProfile | None, jobs, attempts, events, replace: bool,
    ) -> None:
        """Write a validated snapshot in one transaction.

        With ``replace`` the existing profile, jobs, attempts and events are removed
        inside the same transaction, so a failure rolls the whole restore back and
        leaves the previous database intact.
        """
        if not replace and self.has_data():
            raise ValueError("The database already contains data; restoring requires replacement.")
        with self._connection:
            if replace:
                self._connection.execute("DELETE FROM application_events")
                self._connection.execute("DELETE FROM application_tracker")
                self._connection.execute("DELETE FROM job_listings")
                self._connection.execute("DELETE FROM candidate_profile")
            if profile is not None:
                self._connection.execute(
                    "INSERT INTO candidate_profile(profile_id, payload, updated_at) VALUES (1, ?, ?)",
                    (json.dumps(asdict(profile), sort_keys=True, default=_json_default), _now()),
                )
            for row in jobs:
                job = row["job"]
                self._connection.execute(
                    """INSERT INTO job_listings(listing_id, payload, duplicate_key, first_seen_at, last_seen_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (job.listing_id, json.dumps(asdict(job), sort_keys=True, default=_json_default),
                     duplicate_key(job), row["first_seen_at"], row["last_seen_at"]),
                )
            for row in attempts:
                tracker = row["tracker"]
                self._connection.execute(
                    """INSERT INTO application_tracker(
                           listing_id, attempt_number, status, status_evidence,
                           candidate_confirmed, revision, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (tracker.listing_id, tracker.attempt_number, tracker.status.value,
                     tracker.status_evidence, int(tracker.candidate_confirmed),
                     tracker.revision, row["updated_at"]),
                )
            for event in events:
                self._connection.execute(
                    """INSERT INTO application_events(
                           listing_id, attempt_number, from_status, to_status,
                           evidence, candidate_confirmed, recorded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (event["listing_id"], event["attempt_number"],
                     event["from_status"].value if event["from_status"] else None,
                     event["to_status"].value, event["evidence"],
                     int(event["candidate_confirmed"]), event["recorded_at"]),
                )

    def find_duplicate_group(self, job: JobListing) -> tuple[JobListing, ...]:
        rows = self._connection.execute(
            "SELECT payload FROM job_listings WHERE duplicate_key=? ORDER BY first_seen_at, listing_id",
            (duplicate_key(job),),
        ).fetchall()
        return tuple(self._decode_job(row["payload"]) for row in rows)

    def delete_job(self, listing_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute("DELETE FROM job_listings WHERE listing_id=?", (listing_id,))
        return cursor.rowcount > 0

    # --------------------------------------------------------------- tracker

    def start_application(self, listing_id: str) -> ApplicationTracker:
        """Create the first attempt, or a new attempt after a withdrawal.

        Re-application is refused while the lone open attempt is active, when the
        listing is not open, and after a terminal rejection. A new attempt never
        inherits evidence or confirmation flags from the earlier one.
        """
        job = self.get_job(listing_id)
        if job is None:
            raise ValueError("Save the job listing before starting an application.")
        if job.availability_status is not Availability.OPEN:
            raise ValueError(
                f"The listing is {job.availability_status.value}; a new application cannot be started."
            )
        attempts = self.list_attempts(listing_id)
        if not attempts:
            return self.save_tracker(ApplicationTracker(listing_id))
        latest = attempts[-1]
        if not latest.is_terminal:
            raise ValueError(
                f"Attempt {latest.attempt_number} is {latest.status.value}; "
                "finish or withdraw it before starting another application."
            )
        if latest.status not in REAPPLICATION_ALLOWED_FROM:
            raise ValueError(
                f"A {latest.status.value} application is terminal; a new attempt is not offered."
            )
        return self.save_tracker(ApplicationTracker(listing_id, attempt_number=latest.attempt_number + 1))

    def save_tracker(self, tracker: ApplicationTracker) -> ApplicationTracker:
        """Persist one attempt, enforcing transition, evidence and concurrency rules.

        Returns the persisted tracker with its incremented revision.
        """
        if not isinstance(tracker, ApplicationTracker):
            raise TypeError("save_tracker expects an ApplicationTracker.")
        status = tracker.status  # validated by ApplicationTracker.__post_init__
        supplied_evidence = tracker.status_evidence.strip() if tracker.status_evidence else None
        if status is ApplicationStatus.CONFIRMED and not supplied_evidence:
            raise ValueError("Confirmation requires evidence; a click or attempted submission is not proof.")

        row = self._connection.execute(
            """SELECT listing_id, attempt_number, status, status_evidence,
                      candidate_confirmed, revision, updated_at
               FROM application_tracker WHERE listing_id=? AND attempt_number=?""",
            (tracker.listing_id, tracker.attempt_number),
        ).fetchone()
        timestamp = _now()

        if row is None:
            return self._insert_tracker(tracker, supplied_evidence, timestamp)

        persisted = self._decode_tracker(row)
        if tracker.revision != persisted.revision:
            raise StaleApplicationError(
                "This application changed elsewhere; reload it before saving."
            )
        # Never let a later save silently erase evidence: carry the recorded value forward.
        effective_evidence = supplied_evidence if supplied_evidence is not None else persisted.status_evidence
        if status is not persisted.status:
            if status not in _TRACKER_TRANSITIONS[persisted.status]:
                raise ValueError(
                    f"Invalid application transition: {persisted.status.value} -> {status.value}"
                )
            if status is ApplicationStatus.CONFIRMED and not supplied_evidence:
                raise ValueError(
                    "Confirmation requires evidence; a click or attempted submission is not proof."
                )
            if status is ApplicationStatus.SHORTLISTED:
                self._reject_active_duplicate(tracker.listing_id)
        if (
            status is persisted.status
            and effective_evidence == persisted.status_evidence
            and tracker.candidate_confirmed == persisted.candidate_confirmed
        ):
            return persisted

        updated = ApplicationTracker(
            listing_id=persisted.listing_id,
            status=status,
            status_evidence=effective_evidence,
            candidate_confirmed=tracker.candidate_confirmed,
            attempt_number=persisted.attempt_number,
            revision=persisted.revision + 1,
        )
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE application_tracker
                   SET status=?, status_evidence=?, candidate_confirmed=?, revision=?, updated_at=?
                   WHERE listing_id=? AND attempt_number=? AND revision=?""",
                (updated.status.value, updated.status_evidence, int(updated.candidate_confirmed),
                 updated.revision, timestamp, updated.listing_id, updated.attempt_number, persisted.revision),
            )
            if cursor.rowcount != 1:
                raise StaleApplicationError("This application changed elsewhere; reload it before saving.")
            self._append_event(updated, from_status=persisted.status, recorded_at=timestamp)
        return updated

    def _insert_tracker(
        self, tracker: ApplicationTracker, supplied_evidence: str | None, timestamp: str,
    ) -> ApplicationTracker:
        if tracker.revision != 0:
            raise StaleApplicationError("A new application attempt cannot carry an existing revision.")
        if tracker.status is not ApplicationStatus.DISCOVERED:
            raise ValueError("A new application attempt must start as discovered.")
        if tracker.candidate_confirmed:
            raise ValueError("A new application attempt cannot start already confirmed.")
        created = ApplicationTracker(
            listing_id=tracker.listing_id,
            status=ApplicationStatus.DISCOVERED,
            status_evidence=supplied_evidence,
            candidate_confirmed=False,
            attempt_number=tracker.attempt_number,
            revision=0,
        )
        with self._connection:
            try:
                self._connection.execute(
                    """INSERT INTO application_tracker(
                           listing_id, attempt_number, status, status_evidence,
                           candidate_confirmed, revision, updated_at)
                       VALUES (?, ?, ?, ?, 0, 0, ?)""",
                    (created.listing_id, created.attempt_number, created.status.value,
                     created.status_evidence, timestamp),
                )
            except sqlite3.IntegrityError as exc:
                if not self._connection.execute(
                    "SELECT 1 FROM job_listings WHERE listing_id=?", (created.listing_id,)
                ).fetchone():
                    raise ValueError("Save the job listing before its application tracker.") from exc
                raise ValueError(f"Could not create the application attempt: {exc}") from exc
            self._append_event(created, from_status=None, recorded_at=timestamp)
        return created

    def _reject_active_duplicate(self, listing_id: str) -> None:
        job = self.get_job(listing_id)
        if job is None:
            return
        rows = self._connection.execute(
            """SELECT t.listing_id, t.attempt_number, t.status
               FROM application_tracker t
               JOIN job_listings j ON j.listing_id = t.listing_id
               WHERE j.duplicate_key = ?
                 AND t.listing_id <> ?
                 AND t.attempt_number = (
                     SELECT MAX(attempt_number) FROM application_tracker x
                     WHERE x.listing_id = t.listing_id
                 )""",
            (duplicate_key(job), listing_id),
        ).fetchall()
        for row in rows:
            status = ApplicationStatus(row["status"])
            if status not in _DUPLICATE_NON_BLOCKING:
                raise ValueError(
                    "Another observation of this job already has an active application "
                    f"({row['listing_id']}, attempt {row['attempt_number']}, {status.value}). "
                    "Use that record instead of shortlisting a duplicate."
                )

    def _append_event(
        self, tracker: ApplicationTracker, *, from_status: ApplicationStatus | None, recorded_at: str,
    ) -> None:
        self._connection.execute(
            """INSERT INTO application_events(
                   listing_id, attempt_number, from_status, to_status,
                   evidence, candidate_confirmed, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tracker.listing_id, tracker.attempt_number,
             from_status.value if from_status else None, tracker.status.value,
             tracker.status_evidence, int(tracker.candidate_confirmed), recorded_at),
        )

    def get_tracker(self, listing_id: str, attempt_number: int | None = None) -> ApplicationTracker | None:
        if attempt_number is None:
            row = self._connection.execute(
                """SELECT listing_id, attempt_number, status, status_evidence,
                          candidate_confirmed, revision, updated_at
                   FROM application_tracker WHERE listing_id=?
                   ORDER BY attempt_number DESC LIMIT 1""",
                (listing_id,),
            ).fetchone()
        else:
            row = self._connection.execute(
                """SELECT listing_id, attempt_number, status, status_evidence,
                          candidate_confirmed, revision, updated_at
                   FROM application_tracker WHERE listing_id=? AND attempt_number=?""",
                (listing_id, attempt_number),
            ).fetchone()
        return self._decode_tracker(row) if row else None

    def list_attempts(self, listing_id: str) -> tuple[ApplicationTracker, ...]:
        rows = self._connection.execute(
            """SELECT listing_id, attempt_number, status, status_evidence,
                      candidate_confirmed, revision, updated_at
               FROM application_tracker WHERE listing_id=? ORDER BY attempt_number""",
            (listing_id,),
        ).fetchall()
        return tuple(self._decode_tracker(row) for row in rows)

    def list_events(
        self, listing_id: str, attempt_number: int | None = None,
    ) -> tuple[ApplicationEvent, ...]:
        query = """SELECT listing_id, attempt_number, from_status, to_status,
                          evidence, candidate_confirmed, recorded_at
                   FROM application_events WHERE listing_id=?"""
        params: list[object] = [listing_id]
        if attempt_number is not None:
            query += " AND attempt_number=?"
            params.append(attempt_number)
        query += " ORDER BY event_id"
        rows = self._connection.execute(query, params).fetchall()
        return tuple(
            ApplicationEvent(
                listing_id=row["listing_id"],
                attempt_number=row["attempt_number"],
                from_status=ApplicationStatus(row["from_status"]) if row["from_status"] else None,
                to_status=ApplicationStatus(row["to_status"]),
                evidence=row["evidence"],
                candidate_confirmed=bool(row["candidate_confirmed"]),
                recorded_at=row["recorded_at"],
            )
            for row in rows
        )

    # --------------------------------------------------------------- decoding

    def _decode_tracker(self, row: sqlite3.Row) -> ApplicationTracker:
        return ApplicationTracker(
            listing_id=row["listing_id"],
            status=ApplicationStatus(row["status"]),
            status_evidence=row["status_evidence"],
            candidate_confirmed=bool(row["candidate_confirmed"]),
            attempt_number=row["attempt_number"],
            revision=row["revision"],
        )

    def _decode_job(self, payload: str) -> JobListing:
        values = json.loads(payload)
        values["availability_status"] = Availability(values["availability_status"])
        values["eligible_countries"] = tuple(values.get("eligible_countries") or [])
        for key in ("allowed_work_authorizations", "allowed_degree_disciplines", "allowed_study_statuses", "allowed_graduation_years"):
            if values.get(key) is not None:
                values[key] = tuple(values[key])
        values["required_skills"] = frozenset(values.get("required_skills") or [])
        return JobListing(**values)
