"""Tk-free logic shared by the desktop UI and the tests.

This module imports no GUI toolkit: it maps raw form strings to validated domain
objects, decides how a save must behave (new listing versus edit of the selected
listing), resolves the per-user database path, and describes persisted records
back to form strings. The Tkinter layer in ``desktop.py`` stays thin and calls
these functions; no eligibility, deduplication, or persistence rule is duplicated
here — everything is delegated to ``core.py``, ``store.py``, and ``validation.py``.
"""
from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping

from .core import (
    ActivityKind, ApplicationActivity, Availability, CandidateProfile, JobListing,
)
from .urls import validate_public_http_url
from .validation import optional_float, optional_int, split_values

APPLICATION_FOLDER_NAME = "AI Career Agent"
DATABASE_FILE_NAME = "career_agent.sqlite3"

#: Fields that can change whether a listing is treated as currently open and
#: unchanged, or whether a candidate satisfies a hard eligibility requirement.
#: Values are the labels shown when a user is asked to confirm a consequential edit.
FIELD_LABELS: dict[str, str] = {
    "employer": "employer",
    "title": "role title",
    "source_url": "source listing URL",
    "apply_url": "employer apply URL",
    "requisition": "requisition ID",
    "availability": "availability",
    "scope": "eligibility scope",
    "countries": "allowed countries",
    "degrees": "allowed disciplines",
    "study_statuses": "allowed study statuses",
    "graduation_years": "allowed graduation years",
    "allowed_work_authorizations": "allowed work authorizations",
    "min_exp": "minimum experience",
    "max_exp": "maximum experience",
    "provenance_note": "availability evidence / note",
}
HIGH_CONSEQUENCE_FIELDS: tuple[str, ...] = tuple(FIELD_LABELS)


class JobSaveMode(str, Enum):
    """Explicit intent for a job save: create a separate listing or edit one in place."""

    NEW = "new"
    EDIT = "edit"


@dataclass(frozen=True)
class JobSavePlan:
    """What a save will do, decided without touching the UI or the database."""

    mode: JobSaveMode
    listing_id: str
    changed_consequential_fields: tuple[str, ...] = ()

    @property
    def is_edit(self) -> bool:
        return self.mode is JobSaveMode.EDIT

    @property
    def needs_update_confirmation(self) -> bool:
        """True when an edit changes eligibility-relevant fields and should be confirmed."""
        return self.is_edit and bool(self.changed_consequential_fields)

    def update_confirmation_message(self) -> str:
        labels = ", ".join(FIELD_LABELS.get(key, key) for key in self.changed_consequential_fields)
        return (
            f"This edit changes eligibility-relevant fields ({labels}). "
            "The saved listing keeps its identity but must be re-evaluated "
            "before it can be shortlisted.\n\nSave the change?"
        )


def form_values(variables: Mapping[str, object]) -> dict[str, str]:
    """Read plain strings from Tk StringVars (or any object exposing ``get()``)."""
    return {key: variable.get() for key, variable in variables.items()}  # type: ignore[attr-defined]


def _absolute_root(value: str | None) -> Path | None:
    """An environment-provided data root, or ``None`` when it cannot name a stable location.

    The XDG Base Directory Specification requires these variables to hold absolute paths, and says an
    implementation "should consider the path invalid and ignore it" when one does not. A relative root
    is resolved against whatever directory the app happened to be started from, so the person's own
    database would appear to move (and their profile with it) between launches; the documented
    per-user default is used instead. The same rule is applied to the Windows variable, because a
    relative value there has exactly the same problem.
    """
    if not value:
        return None
    candidate = Path(value)
    return candidate if candidate.is_absolute() else None


def career_agent_data_root(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user application-data root for the current platform.

    Parameters are injectable so each operating-system branch can be tested without
    being on that operating system.

    A relative value in ``XDG_DATA_HOME`` or ``LOCALAPPDATA`` is ignored, per the XDG Base Directory
    Specification, so the database path never depends on the current working directory.
    """
    resolved_system = platform.system() if system is None else system
    environment = os.environ if environ is None else environ
    resolved_home = Path.home() if home is None else Path(home)
    if resolved_system == "Darwin":
        return resolved_home / "Library" / "Application Support"
    if resolved_system == "Windows":
        return _absolute_root(environment.get("LOCALAPPDATA")) or (resolved_home / "AppData" / "Local")
    return _absolute_root(environment.get("XDG_DATA_HOME")) or (resolved_home / ".local" / "share")


#: Shown when a record carries no usable timestamp. Never replaced with an invented time.
TIMESTAMP_NOT_RECORDED = "not recorded"


def format_stored_timestamp(value: str | None, *, fallback: str = TIMESTAMP_NOT_RECORDED) -> str:
    """Render a stored instant for display, or say exactly why it cannot be shown.

    This is a display helper: it never invents a time and never reinterprets one. The application
    writes UTC timestamps with an explicit offset; those are converted to UTC and rendered
    unambiguously. A value with no offset is timezone-ambiguous, and a value that cannot be parsed
    may have been written by another tool, so both are shown as they are stored with a plain label
    instead of being guessed at, dropped, or silently "corrected".
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return fallback
    # ``fromisoformat`` accepts a trailing ``Z`` only from Python 3.11, so normalise it first: the
    # application runs on 3.10 as well and the same instant must format identically on both.
    parsable = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
    try:
        moment = datetime.fromisoformat(parsable)
    except ValueError:
        return f"{text} (unrecognised timestamp format)"
    if moment.tzinfo is None:
        return f"{text} (no timezone recorded)"
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def default_data_folder(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """The per-user folder the app keeps its own files in; no directory is created here.

    Shared by the database path and by the start-up diagnostic note, so both always point at the
    same folder on every platform. Callers that need the folder to exist create it themselves;
    a diagnostics path in particular must not have directory side effects.
    """
    resolved_system = platform.system() if system is None else system
    folder_name = APPLICATION_FOLDER_NAME if resolved_system in {"Darwin", "Windows"} else "ai-career-agent"
    return career_agent_data_root(system=resolved_system, environ=environ, home=home) / folder_name


def default_database_path(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Choose a per-user app-data database path, creating the folder that holds it.

    Creating the folder is this function's one side effect, and it is deliberate: SQLite cannot open a
    database inside a folder that does not exist, so without it a first run would fail before the window
    opens. Nothing is written into the folder here, and candidate data never enters the repository.
    """
    folder = default_data_folder(system=system, environ=environ, home=home)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / DATABASE_FILE_NAME


def _require_http_url(value: str | None, label: str) -> None:
    """Reject anything that is not a plain, public http(s) address (see ``urls.py``)."""
    if value:
        validate_public_http_url(value, label=label)


def _split_or_none(value: str) -> tuple[str, ...] | None:
    values = split_values(value)
    return values or None


#: The kinds offered in the activity dialog, in the order the domain declares them.
ACTIVITY_KIND_CHOICES = tuple(kind.value for kind in ActivityKind)

#: How an activity date is written by this module, and the shape a typed one must have. The shape is
#: checked before parsing: ``date.fromisoformat`` also accepts basic-format and ISO week dates, and a
#: field that promises ``YYYY-MM-DD`` should not quietly accept three other spellings.
ACTIVITY_DATE_FORMAT = "%Y-%m-%d"
ACTIVITY_DATE_HINT = "YYYY-MM-DD"
ACTIVITY_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def activity_form_values(*, today: date) -> dict[str, str]:
    """The starting values for a new activity entry: a neutral kind and today's date.

    ``note`` is the default on purpose. A neutral label cannot be saved by accident as the claim that
    an application was sent, which is the entry whose meaning matters most.
    """
    return {"kind": ActivityKind.NOTE.value, "occurred_on": today.strftime(ACTIVITY_DATE_FORMAT), "detail": ""}


def build_activity(values: Mapping[str, str]) -> ApplicationActivity:
    """Map the raw form strings to a validated activity entry; raise ``ValueError`` to show.

    The date must be written exactly as ``YYYY-MM-DD``: a date a person typed is not guessed at, so a
    value this cannot read is refused with the accepted form named rather than reinterpreted.
    """
    kind_text = (values.get("kind") or "").strip()
    try:
        kind = ActivityKind(kind_text)
    except ValueError as exc:
        raise ValueError(f"Choose what the entry records: {', '.join(ACTIVITY_KIND_CHOICES)}.") from exc
    raw_date = (values.get("occurred_on") or "").strip()
    if not raw_date:
        raise ValueError(f"Give the entry a date as {ACTIVITY_DATE_HINT}, for example 2026-10-12.")
    if ACTIVITY_DATE_PATTERN.fullmatch(raw_date) is None:
        raise ValueError(
            f"{raw_date!r} is not a date in the form this field expects. Write it as "
            f"{ACTIVITY_DATE_HINT}, for example 2026-10-12."
        )
    try:
        occurred_on = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError(
            f"{raw_date!r} is not a real calendar date. Write it as {ACTIVITY_DATE_HINT}, for example "
            "2026-10-12."
        ) from exc
    return ApplicationActivity(kind=kind, occurred_on=occurred_on, detail=values.get("detail") or "")


def build_job_listing(values: Mapping[str, str], *, listing_id: str) -> JobListing:
    """Map raw form strings to a validated listing; raise ``ValueError`` with a user-facing message."""
    employer = (values.get("employer") or "").strip()
    title = (values.get("title") or "").strip()
    source_url = (values.get("source_url") or "").strip()
    if not (employer and title and source_url):
        raise ValueError("Employer, role title, and source listing URL are required.")
    _require_http_url(source_url, "Source listing URL")
    apply_url = (values.get("apply_url") or "").strip() or None
    _require_http_url(apply_url, "Employer apply URL")

    availability_text = (values.get("availability") or "").strip() or "unknown"
    try:
        availability = Availability(availability_text)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in Availability)
        raise ValueError(f"Availability must be one of: {allowed}.") from exc

    graduation_years = tuple(
        optional_int(item, "Graduation year") for item in split_values(values.get("graduation_years") or "")
    )
    minimum = optional_float(values.get("min_exp") or "", "Minimum experience")
    maximum = optional_float(values.get("max_exp") or "", "Maximum experience")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("Minimum experience cannot exceed maximum experience.")

    return JobListing(
        listing_id=listing_id,
        source_id="manual",
        source_name=(values.get("source_name") or "").strip() or "Manual entry",
        source_listing_url=source_url,
        employer_name=employer,
        role_title=title,
        availability_status=availability,
        employer_apply_url=apply_url,
        canonical_requisition_id=(values.get("requisition") or "").strip() or None,
        location_text=(values.get("location") or "").strip() or None,
        work_mode=(values.get("work_mode") or "").strip() or None,
        role_type=(values.get("role_type") or "").strip() or None,
        eligibility_scope=(values.get("scope") or "").strip() or "unknown",
        eligible_countries=split_values(values.get("countries") or ""),
        allowed_work_authorizations=_split_or_none(values.get("allowed_work_authorizations") or ""),
        allowed_degree_disciplines=_split_or_none(values.get("degrees") or ""),
        allowed_study_statuses=_split_or_none(values.get("study_statuses") or ""),
        allowed_graduation_years=graduation_years or None,
        minimum_experience_years=minimum,
        maximum_experience_years=maximum,
        required_skills=frozenset(split_values(values.get("required_skills") or "")),
        provenance_note=(values.get("provenance_note") or "").strip() or None,
    )


def plan_job_save(
    values: Mapping[str, str],
    *,
    mode: JobSaveMode,
    new_listing_id: str,
    selected_job_id: str | None = None,
    baseline: Mapping[str, str] | None = None,
) -> tuple[JobListing, JobSavePlan]:
    """Build the listing to save and the plan describing what the save will do.

    ``NEW`` mode always uses the freshly generated ``new_listing_id``, so an unsaved
    form can never overwrite the currently selected listing. ``EDIT`` mode reuses the
    selected listing's identity and reports which eligibility-relevant fields changed.
    """
    try:
        mode = JobSaveMode(mode)
    except ValueError as exc:
        raise ValueError(f"Unknown job save mode: {mode!r}") from exc
    if mode is JobSaveMode.EDIT:
        if not selected_job_id:
            raise ValueError("Select a saved listing before editing it.")
        listing_id = selected_job_id
    else:
        listing_id = new_listing_id

    job = build_job_listing(values, listing_id=listing_id)
    changed: tuple[str, ...] = ()
    if mode is JobSaveMode.EDIT and baseline is not None:
        current = job_form_values(job)
        changed = tuple(
            key for key in HIGH_CONSEQUENCE_FIELDS
            if (baseline.get(key) or "") != (current.get(key) or "")
        )
    return job, JobSavePlan(mode=mode, listing_id=listing_id, changed_consequential_fields=changed)


def job_form_values(job: JobListing) -> dict[str, str]:
    """Render a saved listing back into the job form's string fields."""
    return {
        "employer": job.employer_name,
        "title": job.role_title,
        "source_name": job.source_name,
        "source_url": job.source_listing_url,
        "apply_url": job.employer_apply_url or "",
        "requisition": job.canonical_requisition_id or "",
        "availability": job.availability_status.value,
        "scope": job.eligibility_scope,
        "work_mode": job.work_mode or "",
        "role_type": job.role_type or "",
        "location": job.location_text or "",
        "countries": ", ".join(job.eligible_countries),
        "degrees": ", ".join(job.allowed_degree_disciplines or []),
        "study_statuses": ", ".join(job.allowed_study_statuses or []),
        "graduation_years": ", ".join(str(item) for item in (job.allowed_graduation_years or [])),
        "allowed_work_authorizations": ", ".join(job.allowed_work_authorizations or []),
        "min_exp": "" if job.minimum_experience_years is None else str(job.minimum_experience_years),
        "max_exp": "" if job.maximum_experience_years is None else str(job.maximum_experience_years),
        "required_skills": ", ".join(sorted(job.required_skills)),
        "provenance_note": job.provenance_note or "",
    }


def build_candidate_profile(values: Mapping[str, str]) -> CandidateProfile:
    """Map raw profile form strings to a validated candidate profile."""
    return CandidateProfile(
        candidate_country=(values.get("country") or "").strip() or None,
        degree_discipline=(values.get("degree") or "").strip() or None,
        study_status=(values.get("study_status") or "").strip() or None,
        graduation_year=optional_int(values.get("graduation_year") or "", "Graduation year"),
        experience_years=optional_float(values.get("experience") or "", "Experience"),
        work_authorization=(values.get("work_authorization") or "").strip() or None,
        skills=frozenset(split_values(values.get("skills") or "")),
        preferred_locations=frozenset(split_values(values.get("locations") or "")),
        preferred_work_modes=frozenset(split_values(values.get("work_modes") or "")),
        preferred_role_types=frozenset(split_values(values.get("role_types") or "")),
    )


def profile_fields_not_matching(profile: CandidateProfile, expected: Mapping[str, str]) -> tuple[str, ...]:
    """Which expected form values the stored profile does not actually hold.

    A save is only reported as successful after the stored profile is read back and compared with what
    was asked for. Comparison is semantic rather than textual, because the form renders a multi-value
    field back in one canonical way (sorted, comma separated) and an integer field as a string: a
    textual comparison would report a failure for a value that was stored correctly, and a false
    failure is as unhelpful as a false success.
    """
    rendered = profile_form_values(profile)
    mismatched: list[str] = []
    for key, wanted in expected.items():
        stored = rendered.get(key, "")
        if key in ("skills", "locations", "work_modes", "role_types"):
            matches = (
                {item.casefold() for item in split_values(wanted)}
                == {item.casefold() for item in split_values(stored)}
            )
        elif key == "graduation_year":
            matches = _compared(optional_int, wanted, stored)
        elif key == "experience":
            matches = _compared(optional_float, wanted, stored)
        else:
            matches = wanted.strip().casefold() == stored.strip().casefold()
        if not matches:
            mismatched.append(key)
    return tuple(mismatched)


def _compared(parse, wanted: str, stored: str) -> bool:
    """Whether two form strings parse to the same value (``False`` when either cannot be parsed)."""
    try:
        return parse(wanted, "value") == parse(stored, "value")
    except ValueError:
        return False


def profile_form_values(profile: CandidateProfile) -> dict[str, str]:
    """Render a saved candidate profile back into the profile form's string fields."""
    return {
        "country": profile.candidate_country or "",
        "degree": profile.degree_discipline or "",
        "study_status": profile.study_status or "",
        "graduation_year": str(profile.graduation_year or ""),
        "experience": "" if profile.experience_years is None else str(profile.experience_years),
        "work_authorization": profile.work_authorization or "",
        "skills": ", ".join(sorted(profile.skills)),
        "locations": ", ".join(sorted(profile.preferred_locations)),
        "work_modes": ", ".join(sorted(profile.preferred_work_modes)),
        "role_types": ", ".join(sorted(profile.preferred_role_types)),
    }
