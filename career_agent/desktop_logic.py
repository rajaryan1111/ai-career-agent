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
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping

from .core import Availability, CandidateProfile, JobListing
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


def career_agent_data_root(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user application-data root for the current platform.

    Parameters are injectable so each operating-system branch can be tested without
    being on that operating system.
    """
    resolved_system = platform.system() if system is None else system
    environment = os.environ if environ is None else environ
    resolved_home = Path.home() if home is None else Path(home)
    if resolved_system == "Darwin":
        return resolved_home / "Library" / "Application Support"
    if resolved_system == "Windows":
        return Path(environment.get("LOCALAPPDATA") or (resolved_home / "AppData" / "Local"))
    return Path(environment.get("XDG_DATA_HOME") or (resolved_home / ".local" / "share"))


def default_database_path(
    *,
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Choose a per-user app-data database path; candidate data never enters the repository."""
    resolved_system = platform.system() if system is None else system
    folder_name = APPLICATION_FOLDER_NAME if resolved_system in {"Darwin", "Windows"} else "ai-career-agent"
    folder = career_agent_data_root(system=resolved_system, environ=environ, home=home) / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder / DATABASE_FILE_NAME


def _require_http_url(value: str | None, label: str) -> None:
    """Reject anything that is not a plain, public http(s) address (see ``urls.py``)."""
    if value:
        validate_public_http_url(value, label=label)


def _split_or_none(value: str) -> tuple[str, ...] | None:
    values = split_values(value)
    return values or None


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
