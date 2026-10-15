"""Local export and import: one file a person owns, read back with the same rules it was written under.

The export is the application's own JSON: the profile, every listing with its stored facts, the
application record exactly as stored, and the activity history exactly as stored. This module owns both
directions of that format, so the window and the command line cannot drift apart, and so an import can be
planned and shown before anything is written.

**Nothing is overwritten and nothing is invented.** The rules, in the order they matter:

* **The profile is imported only into an empty profile.** A stored profile is the candidate's own facts;
  replacing it with a file's copy would silently undo whatever they edited since exporting, so the plan
  says it is keeping the local one - and "the file's profile is newer" is not knowable, so it is not
  guessed at.
* **A listing already stored is not replaced.** Identity is the canonical rule the rest of the app uses
  (`core.duplicate_key`), so an exported copy of a listing the person already has is *linked*, and its
  first-seen time is left alone. The plan says so and does not touch the row.
* **An application is imported, its status is not asserted.** The record is created at the initial
  status - so the imported database knows an application exists here and can remind, follow up and take
  a note about it - and the file's later status is *reported as not imported*, with the reason. A stored
  status is the outcome of transitions this application never observed locally, and the store refuses to
  create a record anywhere else; rather than weaken that rule for imports, the flow that would need it
  is named in the plan. The listing, its facts, its follow-up plan and its history still come across.
* **A follow-up plan is imported as data.** It is a day the person chose, not an observation, so it
  travels; a plan whose day cannot be read is reported rather than dropped.
* **Activity history is appended, never merged.** Entries are the person's own record; a duplicate is
  detected on (occurred_on, kind, detail) and skipped, and everything else is appended, because their
  history is not this program's to rewrite.

Every decision is in the plan, which is computed read-only: the window shows it and asks before applying
it, and the command line prints it unless `--yes` is given.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .core import (
    ActivityKind, ApplicationActivity, ApplicationStatus, ApplicationTracker, Availability,
    CandidateProfile, JobListing, duplicate_key,
)
from .store import CareerStore, PrivateWriteError, StoredRecordError, write_private_text_file

#: The export format this build writes and the only one it reads. A file that records a different
#: number is refused with the number it holds, because guessing at an unknown format is how a recovery
#: tool turns into a data-loss tool.
EXPORT_FORMAT_VERSION = 1

#: How many rejections are named before the rest are counted. A plan is read by a person; a hundred
#: lines is not a plan, it is a log, and the count is always given even when the reasons are not.
PLAN_DETAIL_LIMIT = 20

REQUIRED_JOB_FIELDS = ("listing_id", "source_listing_url", "employer_name", "role_title")


class ImportRefused(Exception):
    """The file cannot be read as this application's export. The message is written to be shown."""


@dataclass(frozen=True)
class RejectedJob:
    """One record in the file that cannot be imported, and why."""

    identifier: str
    reason: str


@dataclass
class ImportPlan:
    """What an import would do, computed without writing anything.

    ``jobs`` is what would be added, ``linked`` is what is already stored (matched by canonical
    identity), ``rejected`` is what could not be read, and the four counts at the end are what the
    person is shown. The plan is deliberately a plain object: it is printed, shown in a dialog, and
    asserted in tests, and none of those should have to re-derive it.
    """

    source: str
    format_version: int
    new_jobs: tuple[JobListing, ...] = ()
    new_profiles: tuple[CandidateProfile, ...] = ()
    linked_jobs: tuple[str, ...] = ()
    linked_as: tuple[tuple[str, str], ...] = ()  # (identity kept locally, file's listing id)
    rejected: tuple[RejectedJob, ...] = ()
    trackers_without_status: tuple[tuple[str, str], ...] = ()  # (listing id, status in the file)
    trackers_at_initial_status: tuple[str, ...] = ()
    follow_ups: tuple[tuple[str, str], ...] = ()  # (listing id, ISO day)
    activity_entries: tuple[tuple[str, int], ...] = ()  # (listing id, how many would be appended)
    kept_local_profile: bool = False
    truncated_rejections: int = 0

    @property
    def adds_anything(self) -> bool:
        """Whether applying this plan would write anything at all."""
        return bool(self.new_jobs or self.new_profiles)

    def describe(self) -> tuple[str, ...]:
        """The plan as lines a person reads, in the order the decisions were made."""
        lines = [f"File: {self.source} (format version {self.format_version})"]
        if self.kept_local_profile:
            lines.append("Profile: your stored profile is kept. A file never replaces facts you have "
                         "edited here; delete your profile first if you want the file's copy instead.")
        if self.new_profiles:
            lines.append(f"Profile: would be imported ({len(self.new_profiles[0].skills)} skill(s) and "
                         "the other recorded facts).")
        if self.new_jobs:
            lines.append(f"Listings: {len(self.new_jobs)} would be added.")
        if self.linked_jobs:
            lines.append(f"Listings already stored: {len(self.linked_jobs)} left exactly as they are "
                         f"({', '.join(self.linked_jobs[:5])}"
                         f"{', ...' if len(self.linked_jobs) > 5 else ''}).")
        for identity, file_id in self.linked_as[:PLAN_DETAIL_LIMIT]:
            lines.append(f"  - {file_id} is the same application as your stored {identity}; the stored "
                         "record wins.")
        if self.trackers_at_initial_status:
            lines.append(f"Application records: {len(self.trackers_at_initial_status)} would be created at "
                         f"'{ApplicationStatus.DISCOVERED.value}', the status a new record must start at.")
        for listing_id, status in self.trackers_without_status:
            lines.append(f"  - {listing_id}: the file recorded '{status}', which is NOT imported. A record "
                         f"this app never advanced has to start at "
                         f"'{ApplicationStatus.DISCOVERED.value}'; the application itself, its listing, "
                         "facts, follow-up plan and history still come across.")
        if self.follow_ups:
            lines.append(f"Follow-up days: {len(self.follow_ups)} would be recorded as you set them.")
        if self.activity_entries:
            total = sum(count for _, count in self.activity_entries)
            lines.append(f"Activity history: {total} entr(ies) would be appended where they are missing.")
        if self.rejected:
            lines.append(f"Records that cannot be read: {len(self.rejected)} (nothing is written for "
                         "them):")
            for item in self.rejected[:PLAN_DETAIL_LIMIT]:
                lines.append(f"  - {item.identifier}: {item.reason}")
            if self.truncated_rejections:
                lines.append(f"  - and {self.truncated_rejections} more")
        if not self.adds_anything and not self.follow_ups and not self.activity_entries:
            lines.append("Nothing would be added: this file holds nothing this database does not "
                         "already have.")
        lines.append("Nothing has been written yet." if not self.adds_anything else
                     "Nothing has been written yet; this is what an import would do.")
        return tuple(lines)


@dataclass(frozen=True)
class ImportOutcome:
    """What an applied import actually did, counted from the writes that happened."""

    added_jobs: int = 0
    added_profile: bool = False
    linked_jobs: int = 0
    trackers_imported: int = 0
    follow_ups_imported: int = 0
    activity_added: int = 0
    rejected: int = 0

    def describe(self) -> str:
        """One line for a status bar or a command-line report."""
        parts = []
        if self.added_jobs:
            parts.append(f"added {self.added_jobs} listing(s)")
        if self.added_profile:
            parts.append("imported the profile")
        if self.linked_jobs:
            parts.append(f"left {self.linked_jobs} already-stored listing(s) as they were")
        if self.trackers_imported:
            parts.append(f"created {self.trackers_imported} application record(s)")
        if self.follow_ups_imported:
            parts.append(f"recorded {self.follow_ups_imported} follow-up day(s)")
        if self.activity_added:
            parts.append(f"appended {self.activity_added} activity entr(ies)")
        if self.rejected:
            parts.append(f"skipped {self.rejected} unreadable record(s)")
        return "; ".join(parts) if parts else "nothing was added"


# ---------------------------------------------------------------------------- export

def export_document(store: CareerStore) -> dict[str, Any]:
    """The stored data as the export document: the same shape this module reads back.

    Values are exported exactly as stored, including a status or activity kind this version does not
    recognise, which is marked rather than rewritten: an export must always be able to take the data out
    of the app, even when this build cannot label part of it.
    """
    profile = store.get_profile()
    jobs = store.list_jobs()
    payload: dict[str, Any] = {
        "format_version": EXPORT_FORMAT_VERSION,
        "profile": None,
        "jobs": [],
        "privacy_note": "Export may contain personal information; store securely.",
    }
    if profile:
        payload["profile"] = _plain(profile)
    for job in jobs:
        record = _plain(job)
        record["availability_status"] = job.availability_status.value
        stored_status = store.get_tracker_raw(job.listing_id)
        if stored_status is None:
            record["application_tracker"] = None
        else:
            try:
                ApplicationStatus(stored_status["status"])
            except ValueError:
                stored_status["status_recognised"] = False
            record["application_tracker"] = stored_status
        entries = []
        for stored_entry in store.list_activity_raw(job.listing_id):
            entry = dict(stored_entry)
            try:
                ActivityKind(entry["kind"])
            except ValueError:
                entry["kind_recognised"] = False
            entries.append(entry)
        record["activity"] = entries
        payload["jobs"].append(record)
    return payload


def _plain(record: Any) -> dict[str, Any]:
    """A dataclass as a plain mapping, with sets and tuples as sorted lists for stable JSON."""
    from dataclasses import asdict

    values = asdict(record)
    for key, value in values.items():
        if isinstance(value, (set, frozenset, tuple)):
            values[key] = sorted(value)
    return values


def write_export(store: CareerStore, path: str | Path) -> Path:
    """Write the export document to ``path``, owner-only, and return where it went.

    The whole file goes through the private write path, so it is owner-only from its first byte and is
    never written through a symbolic link. Raises :class:`PrivateWriteError` with a message to show.
    """
    document = export_document(store)
    text = json.dumps(document, indent=2, ensure_ascii=False)
    return write_private_text_file(path, text)


# ---------------------------------------------------------------------------- import

def read_export(path: str | Path) -> dict[str, Any]:
    """Read an export file, or refuse with a message naming exactly what is wrong with it.

    Read-only: this opens the file, checks its shape, and returns the parsed object. Nothing here reads
    the database, so a refused file cannot have touched anything.
    """
    target = Path(path)
    if not target.exists():
        raise ImportRefused(f"{target} does not exist, so there is nothing to import.")
    if target.is_dir():
        raise ImportRefused(f"{target} is a folder. Choose the JSON file that was exported.")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ImportRefused(
            f"{target} is not readable as UTF-8 text ({exc}). It is probably not a JSON export."
        ) from exc
    except OSError as exc:
        raise ImportRefused(f"{target} could not be read: {exc.strerror or exc}.") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportRefused(
            f"{target} is not valid JSON (line {exc.lineno}, column {exc.colno}: {exc.msg}). Nothing was "
            "read from it."
        ) from exc
    if not isinstance(document, dict):
        raise ImportRefused(
            f"{target} holds a JSON {type(document).__name__}, not an export document."
        )
    if "format_version" not in document:
        raise ImportRefused(
            f"{target} has no format_version, so this app cannot tell what wrote it. An export written "
            "by this app always records one."
        )
    version = document["format_version"]
    if version != EXPORT_FORMAT_VERSION:
        raise ImportRefused(
            f"{target} records format version {version!r}, and this build reads version "
            f"{EXPORT_FORMAT_VERSION}. Nothing was imported."
        )
    if "jobs" in document and not isinstance(document["jobs"], list):
        raise ImportRefused(f"{target}: its jobs entry is not a list, so it is not an export this app "
                            "wrote.")
    return document


def plan_import(store: CareerStore, document: Mapping[str, Any], *, source: str = "the chosen file") -> ImportPlan:
    """Decide what an import would do, without writing anything.

    Read-only against the store as well as the file: the plan is what the window shows before asking,
    and what the command line prints unless it is told to apply it.
    """
    plan = ImportPlan(source=source, format_version=int(document.get("format_version", 0)))
    profile_record = document.get("profile")
    if isinstance(profile_record, Mapping):
        if store.get_profile() is not None:
            plan.kept_local_profile = True
        else:
            parsed = _profile_from_record(profile_record)
            if parsed is None:
                plan = _with_rejection(plan, RejectedJob(
                    "the profile in the file",
                    "it does not carry the fields this app stores a profile with (country and skills)"))
            else:
                plan.new_profiles = (parsed,)
    elif profile_record is not None:
        plan = _with_rejection(plan, RejectedJob(
            "the profile in the file", f"it is a {type(profile_record).__name__}, not a stored profile"))
    records = document.get("jobs") or []
    if not isinstance(records, list):
        raise ImportRefused("The document's jobs entry is not a list, so nothing was imported.")
    stored_jobs = store.list_jobs()
    stored_by_key = {duplicate_key(job): job for job in stored_jobs}
    file_keys: dict[str, str] = {}
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            plan = _with_rejection(plan, RejectedJob(
                f"record {index}", f"it is a {type(record).__name__}, not a stored listing"))
            continue
        parsed = _job_from_record(record, index)
        if isinstance(parsed, RejectedJob):
            plan = _with_rejection(plan, parsed)
            continue
        key = duplicate_key(parsed)
        if key in stored_by_key:
            plan.linked_jobs = plan.linked_jobs + (stored_by_key[key].listing_id,)
            plan.linked_as = plan.linked_as + ((stored_by_key[key].listing_id, parsed.listing_id),)
            continue
        if key in file_keys:
            plan = _with_rejection(plan, RejectedJob(
                parsed.listing_id,
                f"it is the same application as record {file_keys[key]} earlier in this file"))
            continue
        file_keys[key] = parsed.listing_id
        plan.new_jobs = plan.new_jobs + (parsed,)
        plan = _plan_application_record(store, plan, record, parsed)
    if len(plan.rejected) > PLAN_DETAIL_LIMIT:
        plan.truncated_rejections = len(plan.rejected) - PLAN_DETAIL_LIMIT
    return plan


def _with_rejection(plan: ImportPlan, rejection: RejectedJob) -> ImportPlan:
    plan.rejected = plan.rejected + (rejection,)
    return plan


def _plan_application_record(store: CareerStore, plan: ImportPlan, record: Mapping[str, Any],
                             job: JobListing) -> ImportPlan:
    """Work out what the file's application record, follow-up plan and history would do."""
    stored = record.get("application_tracker")
    if isinstance(stored, Mapping):
        status = str(stored.get("status") or "")
        # The record is created whatever the file said, so the imported database knows an application
        # exists; only the *status* is refused when it is one this app never advanced to.
        plan.trackers_at_initial_status = plan.trackers_at_initial_status + (job.listing_id,)
        if status and status != ApplicationStatus.DISCOVERED.value:
            plan.trackers_without_status = plan.trackers_without_status + ((job.listing_id, status),)
    day = None
    if isinstance(stored, Mapping):
        day = stored.get("follow_up_on")
    if day:
        if _is_iso_day(str(day)):
            plan.follow_ups = plan.follow_ups + ((job.listing_id, str(day)),)
        else:
            plan = _with_rejection(plan, RejectedJob(
                job.listing_id,
                f"its follow-up day is {day!r}, which is not a YYYY-MM-DD date, so the reminder was not "
                "imported"))
    entries = record.get("activity") or []
    if isinstance(entries, list):
        readable = sum(1 for entry in entries if isinstance(entry, Mapping) and _entry_is_readable(entry))
        unreadable = len(entries) - readable
        if readable:
            plan.activity_entries = plan.activity_entries + ((job.listing_id, readable),)
        if unreadable:
            plan = _with_rejection(plan, RejectedJob(
                job.listing_id, f"{unreadable} of its history entr(ies) cannot be read and were skipped"))
    return plan


def apply_import(store: CareerStore, document: Mapping[str, Any], *, source: str = "the chosen file"
                 ) -> ImportOutcome:
    """Apply an import, writing only what the plan describes.

    The plan is recomputed here rather than trusted from the caller, so the writes and the promise cannot
    diverge: whatever the window showed, this function decides again and writes that. Every write goes
    through the store's own methods, so the storage boundary still enforces every rule.
    """
    plan = plan_import(store, document, source=source)
    added_jobs = 0
    trackers = 0
    follow_ups = 0
    activity = 0
    added_profile = False
    for profile in plan.new_profiles:
        store.save_profile(profile)
        added_profile = True
    for job in plan.new_jobs:
        store.save_job(job)
        added_jobs += 1
        record = _record_for_listing(document, job)
        if record is None:
            continue
        stored = record.get("application_tracker")
        if isinstance(stored, Mapping):
            store.save_tracker(ApplicationTracker(job.listing_id))
            trackers += 1
            day = stored.get("follow_up_on")
            if day and _is_iso_day(str(day)):
                store.set_follow_up(job.listing_id, _day(str(day)),
                                    note=_optional_text(stored.get("follow_up_note")))
                follow_ups += 1
        for entry in record.get("activity") or []:
            if not isinstance(entry, Mapping) or not _entry_is_readable(entry):
                continue
            activity_entry = _activity_from_entry(entry)
            if activity_entry is None:
                continue
            if _already_recorded(store, job.listing_id, activity_entry):
                continue
            store.add_activity(job.listing_id, activity_entry)
            activity += 1
    return ImportOutcome(
        added_jobs=added_jobs, added_profile=added_profile, linked_jobs=len(plan.linked_jobs),
        trackers_imported=trackers, follow_ups_imported=follow_ups, activity_added=activity,
        rejected=len(plan.rejected),
    )


def _record_for_listing(document: Mapping[str, Any], job: JobListing) -> Mapping[str, Any] | None:
    """The file's record for a listing that was just added, matched on identity."""
    for record in document.get("jobs") or []:
        if not isinstance(record, Mapping):
            continue
        if str(record.get("listing_id") or "") == job.listing_id:
            return record
    return None


def _already_recorded(store: CareerStore, listing_id: str, entry: ApplicationActivity) -> bool:
    """Whether this exact entry is already in the stored history.

    Compared on the day, the kind and the text, because those are the three things an entry claims; the
    recorded-at instant differs between machines and is not part of the claim.
    """
    for stored in store.list_activity(listing_id):
        if (stored.occurred_on == entry.occurred_on and stored.kind == entry.kind
                and stored.detail == entry.detail):
            return True
    return False


# ---------------------------------------------------------------------------- parsing helpers

def _job_from_record(record: Mapping[str, Any], index: int) -> JobListing | RejectedJob:
    """One stored listing, or a rejection naming what is missing."""
    identifier = _text(record.get("listing_id")) or f"record {index}"
    missing = [name for name in REQUIRED_JOB_FIELDS if not _text(record.get(name))]
    if missing:
        return RejectedJob(identifier, "it does not carry " + ", ".join(missing))
    try:
        listing = JobListing(
            listing_id=_text(record["listing_id"]),
            source_id=_text(record.get("source_id")) or "imported",
            source_name=_text(record.get("source_name")) or "An exported file",
            source_listing_url=_text(record["source_listing_url"]),
            employer_name=_text(record["employer_name"]),
            role_title=_text(record["role_title"]),
            availability_status=_availability(record.get("availability_status")),
            employer_apply_url=_optional_text(record.get("employer_apply_url")),
            canonical_requisition_id=_optional_text(record.get("canonical_requisition_id")),
            location_text=_optional_text(record.get("location_text")),
            work_mode=_optional_text(record.get("work_mode")),
            role_type=_optional_text(record.get("role_type")),
            eligibility_scope=_text(record.get("eligibility_scope")) or "unknown",
            eligible_countries=tuple(_text_list(record.get("eligible_countries"))),
            allowed_degree_disciplines=_optional_text_list(record.get("allowed_degree_disciplines")),
            allowed_study_statuses=_optional_text_list(record.get("allowed_study_statuses")),
            allowed_graduation_years=_year_list(record.get("allowed_graduation_years")),
            minimum_experience_years=_number(record.get("minimum_experience_years")),
            maximum_experience_years=_number(record.get("maximum_experience_years")),
            required_skills=frozenset(_text_list(record.get("required_skills"))),
            provenance_note=_optional_text(record.get("provenance_note")),
            allowed_work_authorizations=_optional_text_list(record.get("allowed_work_authorizations")),
        )
    except (ValueError, TypeError) as exc:
        return RejectedJob(identifier, f"it is not a listing this application can store ({exc})")
    return listing


def _profile_from_record(record: Mapping[str, Any]) -> CandidateProfile | None:
    """The stored profile, or ``None`` when the record is not one this app could have written."""
    # The field names are the stored ones, checked against the dataclass rather than written from
    # memory: a mismatch here would reject every profile in every file, silently, which is the kind of
    # bug that hides behind a plan line reading "cannot be read".
    if not _text(record.get("candidate_country")):
        return None
    if "skills" not in record:
        return None
    try:
        return CandidateProfile(
            candidate_country=_text(record["candidate_country"]),
            degree_discipline=_optional_text(record.get("degree_discipline")),
            study_status=_optional_text(record.get("study_status")),
            graduation_year=_year(record.get("graduation_year")),
            experience_years=_number(record.get("experience_years")),
            work_authorization=_optional_text(record.get("work_authorization")),
            skills=frozenset(_text_list(record.get("skills"))),
            preferred_locations=frozenset(_text_list(record.get("preferred_locations"))),
            preferred_work_modes=frozenset(_text_list(record.get("preferred_work_modes"))),
            preferred_role_types=frozenset(_text_list(record.get("preferred_role_types"))),
        )
    except (ValueError, TypeError):
        return None


def _activity_from_entry(entry: Mapping[str, Any]) -> ApplicationActivity | None:
    """One stored history entry, or ``None`` when this build cannot read it."""
    try:
        kind = ActivityKind(str(entry["kind"]))
    except (KeyError, ValueError):
        return None
    try:
        occurred_on = _day(str(entry["occurred_on"]))
    except (KeyError, ValueError):
        return None
    detail = _text(entry.get("detail"))
    if not detail:
        return None
    return ApplicationActivity(occurred_on=occurred_on, kind=kind, detail=detail)


def _entry_is_readable(entry: Mapping[str, Any]) -> bool:
    return _activity_from_entry(entry) is not None


def _is_iso_day(value: str) -> bool:
    try:
        _day(value)
    except ValueError:
        return False
    return True


def _day(value: str):
    from datetime import date

    return date.fromisoformat(value)


def _availability(value: Any) -> Availability:
    """The stored availability, defaulting to unknown rather than to a guess."""
    try:
        return Availability(str(value))
    except ValueError:
        return Availability.UNKNOWN


def _text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _optional_text(value: Any) -> str | None:
    return _text(value) or None


def _text_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_text(value),) if _text(value) else ()
    if isinstance(value, Iterable):
        return tuple(text for text in (_text(item) for item in value) if text)
    return ()


def _optional_text_list(value: Any) -> tuple[str, ...] | None:
    """A stored optional list: ``None`` when the field was absent, which is not the same as empty."""
    if value is None:
        return None
    return _text_list(value)


def _year_list(value: Any) -> tuple[int, ...] | None:
    if value is None:
        return None
    years = []
    for item in value if isinstance(value, Iterable) and not isinstance(value, str) else [value]:
        year = _year(item)
        if year is not None:
            years.append(year)
    return tuple(years)


def _year(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
