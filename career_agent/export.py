"""Local backup/export contract for AI Career Agent.

The desktop UI, the smoke-test script and the unit tests share this module, so
the file format has exactly one definition. Nothing leaves the machine and no
imported content is ever executed.

Format history:

* version 2 — profile, jobs, attempts and events, but no timestamps or revisions.
* version 3 — adds ``schema_version``, ``exported_at``, per-job observation
  timestamps and per-attempt revision/updated_at, making the file a lossless
  local backup. Version 2 files are still accepted and restored with documented
  defaults.

Restore always validates the whole file before touching the database and writes
inside a single transaction, so a rejected or failed restore leaves the previous
data untouched.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping

from .core import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, JobListing,
    allowed_transitions,
)
from .store import CareerStore

FORMAT_VERSION = 3
SUPPORTED_FORMAT_VERSIONS = (2, 3)
SCHEMA_VERSION = 2
PRIVACY_NOTE = "Export may contain personal information; store securely."
MAX_BACKUP_BYTES = 10 * 1024 * 1024

_PROFILE_FIELDS = {
    "candidate_country", "degree_discipline", "study_status", "graduation_year",
    "experience_years", "work_authorization", "skills", "preferred_locations",
    "preferred_work_modes", "preferred_role_types",
}
_TOP_LEVEL_FIELDS = {"format_version", "schema_version", "exported_at", "profile", "jobs", "privacy_note"}
_JOB_FIELDS = {
    "listing_id", "source_id", "source_name", "source_listing_url", "employer_name",
    "role_title", "availability_status", "employer_apply_url", "canonical_requisition_id",
    "location_text", "work_mode", "role_type", "eligibility_scope", "eligible_countries",
    "allowed_degree_disciplines", "allowed_study_statuses", "allowed_graduation_years",
    "minimum_experience_years", "maximum_experience_years", "required_skills",
    "provenance_note", "allowed_work_authorizations", "application_attempts",
    "first_seen_at", "last_seen_at",
}
_ATTEMPT_FIELDS = {
    "attempt_number", "status", "status_evidence", "candidate_confirmed",
    "revision", "updated_at", "application_events",
}
_EVENT_FIELDS = {"from_status", "to_status", "evidence", "candidate_confirmed", "recorded_at"}
_JOB_TEXT_FIELDS = ("listing_id", "source_id", "source_name", "source_listing_url", "employer_name", "role_title")
_JOB_OPTIONAL_TEXT_FIELDS = (
    "employer_apply_url", "canonical_requisition_id", "location_text",
    "work_mode", "role_type", "provenance_note",
)
_ELIGIBILITY_SCOPES = {"worldwide", "restricted", "unknown"}


class ExportFormatError(ValueError):
    """The file is not a supported, valid backup."""


class RestoreError(RuntimeError):
    """The restore failed while writing; the previous database was rolled back."""


@dataclass(frozen=True)
class RestoredJob:
    job: JobListing
    first_seen_at: str
    last_seen_at: str


@dataclass(frozen=True)
class RestoredAttempt:
    tracker: ApplicationTracker
    updated_at: str


@dataclass(frozen=True)
class RestoredData:
    profile: CandidateProfile | None
    jobs: tuple[RestoredJob, ...]
    attempts: tuple[RestoredAttempt, ...]
    events: tuple[dict[str, Any], ...]

    def counts(self) -> dict[str, int]:
        return {
            "profile": 1 if self.profile else 0,
            "jobs": len(self.jobs),
            "attempts": len(self.attempts),
            "events": len(self.events),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_ready(values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        if isinstance(value, (set, frozenset, tuple)):
            values[key] = sorted(value)
    return values


# --------------------------------------------------------------------- reading

def build_export_payload(store: CareerStore) -> dict[str, Any]:
    """Return a complete, restorable backup of ``store`` without touching the filesystem."""
    exported_at = _now()
    profile = store.get_profile()
    payload: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "exported_at": exported_at,
        "profile": _json_ready(asdict(profile)) if profile else None,
        "jobs": [],
        "privacy_note": PRIVACY_NOTE,
    }
    for job in store.list_jobs():
        record = _json_ready(asdict(job))
        record["availability_status"] = job.availability_status.value
        first_seen, last_seen = store.job_timestamps(job.listing_id) or (exported_at, exported_at)
        record["first_seen_at"] = first_seen
        record["last_seen_at"] = last_seen
        attempts = []
        for attempt in store.list_attempts(job.listing_id):
            attempts.append({
                "attempt_number": attempt.attempt_number,
                "status": attempt.status.value,
                "status_evidence": attempt.status_evidence,
                "candidate_confirmed": attempt.candidate_confirmed,
                "revision": attempt.revision,
                "updated_at": store.attempt_updated_at(job.listing_id, attempt.attempt_number) or exported_at,
                "application_events": [
                    {
                        "from_status": event.from_status.value if event.from_status else None,
                        "to_status": event.to_status.value,
                        "evidence": event.evidence,
                        "candidate_confirmed": event.candidate_confirmed,
                        "recorded_at": event.recorded_at,
                    }
                    for event in store.list_events(job.listing_id, attempt.attempt_number)
                ],
            })
        record["application_attempts"] = attempts
        payload["jobs"].append(record)
    return payload


def write_export(store: CareerStore, destination: str | Path) -> dict[str, Any]:
    """Write the backup to ``destination`` and return the payload that was written."""
    payload = build_export_payload(store)
    Path(destination).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def load_export(path: str | Path) -> dict[str, Any]:
    """Read and JSON-parse a backup file; validation happens in :func:`validate_export`."""
    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise ExportFormatError(f"Could not read the backup file: {exc}") from exc
    if not raw.strip():
        raise ExportFormatError("The backup file is empty.")
    if len(raw) > MAX_BACKUP_BYTES:
        raise ExportFormatError(
            f"The backup file is larger than the {MAX_BACKUP_BYTES // (1024 * 1024)} MiB safety limit."
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExportFormatError("The backup file is not valid UTF-8 text.") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExportFormatError(
            f"The backup file is not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}."
        ) from exc
    if not isinstance(payload, dict):
        raise ExportFormatError("The backup root must be a JSON object.")
    return payload


# ------------------------------------------------------------------ validation

def _fail(message: str) -> None:
    raise ExportFormatError(message)


def _mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{context} must be a JSON object.")
    return value


def _reject_unknown(record: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(record) - allowed)
    if unknown:
        _fail(f"{context} contains unsupported field(s): {', '.join(unknown)}.")


def _text(record: Mapping[str, Any], key: str, context: str, *, required: bool) -> str | None:
    value = record.get(key)
    if value is None:
        if required:
            _fail(f"{context}: missing required field {key!r}.")
        return None
    if not isinstance(value, str):
        _fail(f"{context}: field {key!r} must be text.")
    if not value.strip():
        if required:
            _fail(f"{context}: field {key!r} must not be blank.")
        return None
    return value


def _text_list(record: Mapping[str, Any], key: str, context: str) -> tuple[str, ...]:
    value = record.get(key)
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        _fail(f"{context}: field {key!r} must be a list of strings.")
    return tuple(value)


def _optional_text_list(record: Mapping[str, Any], key: str, context: str) -> tuple[str, ...] | None:
    if record.get(key) is None:
        return None
    return _text_list(record, key, context)


def _optional_int_list(record: Mapping[str, Any], key: str, context: str) -> tuple[int, ...] | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        _fail(f"{context}: field {key!r} must be a list of whole numbers.")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            _fail(f"{context}: field {key!r} must contain only whole numbers.")
    return tuple(value)


def _int(record: Mapping[str, Any], key: str, context: str, *, default: int | None = None, minimum: int | None = None) -> int | None:
    value = record.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{context}: field {key!r} must be a whole number.")
    if minimum is not None and value < minimum:
        _fail(f"{context}: field {key!r} must be at least {minimum}.")
    return value


def _number(record: Mapping[str, Any], key: str, context: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail(f"{context}: field {key!r} must be a finite number.")
    return float(value)


def _boolean(record: Mapping[str, Any], key: str, context: str, *, default: bool = False) -> bool:
    value = record.get(key, default)
    if not isinstance(value, bool):
        _fail(f"{context}: field {key!r} must be true or false.")
    return value


def _timestamp(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{context} must be a non-empty timestamp.")
    text = value.strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExportFormatError(f"{context} is not a valid ISO-8601 timestamp: {value!r}.") from exc
    return text


def _status(value: Any, context: str) -> ApplicationStatus:
    if not isinstance(value, str):
        _fail(f"{context} must be a status string.")
    try:
        return ApplicationStatus(value)
    except ValueError as exc:
        raise ExportFormatError(f"{context} has an unknown application status: {value!r}.") from exc


def _evidence(value: Any, context: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(f"{context} must be text or null.")
    if not value.strip():
        _fail(f"{context} must not be blank; omit the field instead.")
    return value


def _parse_profile(data: Any) -> CandidateProfile | None:
    if data is None:
        return None
    record = _mapping(data, "profile")
    _reject_unknown(record, _PROFILE_FIELDS, "profile")
    try:
        return CandidateProfile(
            candidate_country=_text(record, "candidate_country", "profile", required=False),
            degree_discipline=_text(record, "degree_discipline", "profile", required=False),
            study_status=_text(record, "study_status", "profile", required=False),
            graduation_year=_int(record, "graduation_year", "profile"),
            experience_years=_number(record, "experience_years", "profile"),
            work_authorization=_text(record, "work_authorization", "profile", required=False),
            skills=frozenset(_text_list(record, "skills", "profile")),
            preferred_locations=frozenset(_text_list(record, "preferred_locations", "profile")),
            preferred_work_modes=frozenset(_text_list(record, "preferred_work_modes", "profile")),
            preferred_role_types=frozenset(_text_list(record, "preferred_role_types", "profile")),
        )
    except ValueError as exc:
        raise ExportFormatError(f"profile is invalid: {exc}") from exc


def _parse_job(record: Mapping[str, Any], context: str) -> JobListing:
    _reject_unknown(record, _JOB_FIELDS, context)
    values: dict[str, Any] = {
        "listing_id": _text(record, "listing_id", context, required=True),
        "source_id": _text(record, "source_id", context, required=True),
        "source_name": _text(record, "source_name", context, required=True),
        "source_listing_url": _text(record, "source_listing_url", context, required=True),
        "employer_name": _text(record, "employer_name", context, required=True),
        "role_title": _text(record, "role_title", context, required=True),
    }
    for key in _JOB_OPTIONAL_TEXT_FIELDS:
        values[key] = _text(record, key, context, required=False)

    availability = record.get("availability_status")
    try:
        values["availability_status"] = Availability(availability)
    except ValueError as exc:
        raise ExportFormatError(f"{context}: unknown availability_status {availability!r}.") from exc

    scope = record.get("eligibility_scope", "unknown")
    if scope not in _ELIGIBILITY_SCOPES:
        _fail(f"{context}: eligibility_scope must be one of {sorted(_ELIGIBILITY_SCOPES)}.")
    values["eligibility_scope"] = scope

    values["eligible_countries"] = _text_list(record, "eligible_countries", context)
    values["required_skills"] = frozenset(_text_list(record, "required_skills", context))
    values["allowed_degree_disciplines"] = _optional_text_list(record, "allowed_degree_disciplines", context)
    values["allowed_study_statuses"] = _optional_text_list(record, "allowed_study_statuses", context)
    values["allowed_work_authorizations"] = _optional_text_list(record, "allowed_work_authorizations", context)
    values["allowed_graduation_years"] = _optional_int_list(record, "allowed_graduation_years", context)
    values["minimum_experience_years"] = _number(record, "minimum_experience_years", context)
    values["maximum_experience_years"] = _number(record, "maximum_experience_years", context)
    if (
        values["minimum_experience_years"] is not None
        and values["maximum_experience_years"] is not None
        and values["minimum_experience_years"] > values["maximum_experience_years"]
    ):
        _fail(f"{context}: minimum_experience_years must not exceed maximum_experience_years.")
    try:
        return JobListing(**values)
    except ValueError as exc:
        raise ExportFormatError(f"{context} is invalid: {exc}") from exc


def _parse_events(data: Any, listing_id: str, attempt_number: int, context: str) -> list[dict[str, Any]]:
    if data is None:
        return []
    if not isinstance(data, (list, tuple)):
        _fail(f"{context}: application_events must be a list.")
    events: list[dict[str, Any]] = []
    for index, raw in enumerate(data):
        where = f"{context}, event {index + 1}"
        record = _mapping(raw, where)
        _reject_unknown(record, _EVENT_FIELDS, where)
        from_status = record.get("from_status")
        parsed_from = None if from_status is None else _status(from_status, f"{where} from_status")
        events.append({
            "listing_id": listing_id,
            "attempt_number": attempt_number,
            "from_status": parsed_from,
            "to_status": _status(record.get("to_status"), f"{where} to_status"),
            "evidence": _evidence(record.get("evidence"), f"{where} evidence"),
            "candidate_confirmed": _boolean(record, "candidate_confirmed", where),
            "recorded_at": _timestamp(record.get("recorded_at"), f"{where} recorded_at"),
        })
    return events


def _validate_history(attempt: Any, events: list[dict[str, Any]], context: str) -> None:
    """Replay the recorded chain so an inconsistent history cannot enter the database."""
    if not events:
        if attempt.revision != 0:
            _fail(f"{context}: has revision {attempt.revision} but no event history.")
        return
    first = events[0]
    if first["from_status"] is not None:
        _fail(f"{context}: the first event must start without a source status.")
    if first["to_status"] is not ApplicationStatus.DISCOVERED:
        _fail(f"{context}: the first event must create a discovered attempt.")
    current = first["to_status"]
    for index, event in enumerate(events[1:], start=2):
        if event["from_status"] is not current:
            _fail(f"{context}, event {index}: source status does not match the previous event.")
        if event["to_status"] is not current and event["to_status"] not in allowed_transitions(current):
            _fail(
                f"{context}, event {index}: invalid transition "
                f"{current.value} -> {event['to_status'].value}."
            )
        if event["to_status"] is ApplicationStatus.CONFIRMED and not event["evidence"]:
            _fail(f"{context}, event {index}: a confirmation event requires evidence.")
        current = event["to_status"]
    if current is not attempt.status:
        _fail(
            f"{context}: history ends at {current.value} but the attempt is {attempt.status.value}."
        )
    if events[-1]["evidence"] != attempt.status_evidence:
        _fail(f"{context}: the final event evidence does not match the attempt evidence.")
    if events[-1]["candidate_confirmed"] != attempt.candidate_confirmed:
        _fail(f"{context}: the final event confirmation flag does not match the attempt.")


def _parse_attempts(
    data: Any, listing_id: str, context: str, *, exported_at: str, version: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if data is None:
        return [], []
    if not isinstance(data, (list, tuple)):
        _fail(f"{context}: application_attempts must be a list.")
    attempt_rows, event_rows = [], []
    seen: set[int] = set()
    for index, raw in enumerate(data):
        where = f"{context}, attempt {index + 1}"
        record = _mapping(raw, where)
        _reject_unknown(record, _ATTEMPT_FIELDS, where)
        attempt_number = _int(record, "attempt_number", where, minimum=1)
        if attempt_number is None:
            _fail(f"{where}: missing attempt_number.")
        if attempt_number in seen:
            _fail(f"{context}: duplicate attempt_number {attempt_number}.")
        seen.add(attempt_number)
        status = _status(record.get("status"), f"{where} status")
        evidence = _evidence(record.get("status_evidence"), f"{where} status_evidence")
        if status is ApplicationStatus.CONFIRMED and not evidence:
            _fail(f"{where}: a confirmed attempt requires evidence.")
        try:
            # Version 3 must carry its own timestamp; version 2 falls back to the export time.
            updated_raw = record.get("updated_at") if version >= 3 else record.get("updated_at", exported_at)
            updated_at = _timestamp(updated_raw, f"{where} updated_at")
            tracker = ApplicationTracker(
                listing_id=listing_id,
                status=status,
                status_evidence=evidence,
                candidate_confirmed=_boolean(record, "candidate_confirmed", where),
                attempt_number=attempt_number,
                revision=_int(record, "revision", where, default=0, minimum=0),
            )
        except ValueError as exc:
            raise ExportFormatError(f"{where} is invalid: {exc}") from exc
        events = _parse_events(record.get("application_events"), listing_id, attempt_number, where)
        _validate_history(tracker, events, where)
        attempt_rows.append({"tracker": tracker, "updated_at": updated_at})
        event_rows.extend(events)
    return attempt_rows, event_rows


def validate_export(payload: Mapping[str, Any]) -> RestoredData:
    """Validate a parsed backup completely, without touching any database."""
    if not isinstance(payload, Mapping):
        _fail("The backup root must be a JSON object.")
    _reject_unknown(payload, _TOP_LEVEL_FIELDS, "backup")
    version = payload.get("format_version")
    if isinstance(version, bool) or not isinstance(version, int):
        _fail("The backup is missing an integer format_version.")
    if version not in SUPPORTED_FORMAT_VERSIONS:
        _fail(
            f"Unsupported backup format version {version}; this build supports "
            f"{', '.join(str(v) for v in SUPPORTED_FORMAT_VERSIONS)}."
        )
    if version >= 3:
        if payload.get("schema_version") != SCHEMA_VERSION:
            _fail(
                f"Unsupported database schema version {payload.get('schema_version')!r}; "
                f"this build supports {SCHEMA_VERSION}."
            )
        exported_at = _timestamp(payload.get("exported_at"), "exported_at")
    else:
        exported_at = _timestamp(payload.get("exported_at") or _now(), "exported_at")
        if payload.get("schema_version") not in (None, SCHEMA_VERSION):
            _fail(f"Unsupported database schema version {payload.get('schema_version')!r}.")
    if payload.get("privacy_note") is not None and not isinstance(payload["privacy_note"], str):
        _fail("privacy_note must be text when present.")

    profile = _parse_profile(payload.get("profile"))

    jobs_data = payload.get("jobs")
    if not isinstance(jobs_data, (list, tuple)):
        _fail("The backup must contain a jobs list.")
    jobs, attempts, events = [], [], []
    listings: set[str] = set()
    for index, raw in enumerate(jobs_data):
        record = _mapping(raw, f"job {index + 1}")
        job = _parse_job(record, f"job {index + 1}")
        if job.listing_id in listings:
            _fail(f"Duplicate listing_id {job.listing_id!r} in the backup.")
        listings.add(job.listing_id)
        if version >= 3:
            first_seen = _timestamp(record.get("first_seen_at"), f"job {index + 1} first_seen_at")
            last_seen = _timestamp(record.get("last_seen_at"), f"job {index + 1} last_seen_at")
        else:
            first_seen = _timestamp(record.get("first_seen_at", exported_at), f"job {index + 1} first_seen_at")
            last_seen = _timestamp(record.get("last_seen_at", exported_at), f"job {index + 1} last_seen_at")
        jobs.append(RestoredJob(job, first_seen, last_seen))
        attempt_rows, event_rows = _parse_attempts(
            record.get("application_attempts"),
            job.listing_id,
            f"job {index + 1} ({job.listing_id})",
            exported_at=exported_at,
            version=version,
        )
        attempts.extend(RestoredAttempt(row["tracker"], row["updated_at"]) for row in attempt_rows)
        events.extend(event_rows)
    return RestoredData(profile, tuple(jobs), tuple(attempts), tuple(events))


# -------------------------------------------------------------------- restore

def restore_export(
    store: CareerStore, payload: Mapping[str, Any], *, replace: bool = False,
) -> dict[str, int]:
    """Validate and restore a backup into ``store``.

    Without ``replace`` the restore only succeeds into an empty database. With
    ``replace`` every existing record is removed inside the same transaction as the
    inserts, so a failure leaves the previous data exactly as it was.
    """
    restored = validate_export(payload)
    if not replace and store.has_data():
        raise ExportFormatError(
            "The database already contains data. Restoring over it requires an explicit replace."
        )
    try:
        store.import_snapshot(
            profile=restored.profile,
            jobs=[{"job": row.job, "first_seen_at": row.first_seen_at, "last_seen_at": row.last_seen_at} for row in restored.jobs],
            attempts=[{"tracker": row.tracker, "updated_at": row.updated_at} for row in restored.attempts],
            events=list(restored.events),
            replace=replace,
        )
    except sqlite3.Error as exc:
        raise RestoreError(f"The restore failed and was rolled back: {exc}") from exc
    except ValueError as exc:
        raise ExportFormatError(str(exc)) from exc
    summary = restored.counts()
    summary["replaced"] = int(replace)
    return summary


def restore_export_file(
    store: CareerStore, source: str | Path, *, replace: bool = False,
) -> dict[str, int]:
    """Load, validate and restore a backup file."""
    return restore_export(store, load_export(source), replace=replace)


def restore_from_backup(
    store: CareerStore,
    source: str | Path,
    *,
    confirm: Callable[[dict[str, int]], bool] | None = None,
) -> dict[str, int] | None:
    """Load, validate, then restore a backup file after the caller confirms replacement.

    The file is fully validated before ``confirm`` is called, and ``confirm`` is
    only consulted when the database already holds data. Declining returns
    ``None`` with the database untouched, which is what the desktop dialog uses
    for cancellation. Restoring over existing data always requires ``confirm``.
    On success the summary counts are returned.
    """
    payload = load_export(source)
    restored = validate_export(payload)
    replace = store.has_data()
    if replace:
        if confirm is None:
            raise ExportFormatError(
                "The database already contains data; replacing it requires confirmation."
            )
        if not confirm(restored.counts()):
            return None
    return restore_export(store, payload, replace=replace)
