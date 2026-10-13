"""SQLite persistence for AI Career Agent; storage is local and has no network code."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from .core import (
    INITIAL_APPLICATION_STATUS, ApplicationStatus, ApplicationTracker, Availability,
    CandidateProfile, JobListing, duplicate_key, is_allowed_tracker_transition,
)

_SCHEMA_VERSION = 1


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
        self._initialize()

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
        values = json.loads(row["payload"])
        for key in ("skills", "preferred_locations", "preferred_work_modes", "preferred_role_types"):
            values[key] = frozenset(values.get(key) or [])
        return CandidateProfile(**values)

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

    def save_tracker(self, tracker: ApplicationTracker) -> None:
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
        """
        stored = self.get_tracker(tracker.listing_id)
        self._check_tracker_invariants(tracker, stored)
        timestamp = _now()
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
        if tracker.status is ApplicationStatus.CONFIRMED and not (
            tracker.status_evidence and tracker.status_evidence.strip()
        ):
            raise ValueError(
                "A confirmed application requires evidence; a click or attempted submission is not proof."
            )
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

    def get_tracker(self, listing_id: str) -> ApplicationTracker | None:
        row = self._connection.execute(
            "SELECT listing_id, status, status_evidence, candidate_confirmed FROM application_tracker WHERE listing_id=?",
            (listing_id,),
        ).fetchone()
        if row is None:
            return None
        return ApplicationTracker(
            listing_id=row["listing_id"], status=ApplicationStatus(row["status"]),
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
        values = json.loads(payload)
        values["availability_status"] = Availability(values["availability_status"])
        values["eligible_countries"] = tuple(values.get("eligible_countries") or [])
        for key in ("allowed_work_authorizations", "allowed_degree_disciplines", "allowed_study_statuses", "allowed_graduation_years"):
            if values.get(key) is not None:
                values[key] = tuple(values[key])
        values["required_skills"] = frozenset(values.get("required_skills") or [])
        return JobListing(**values)
