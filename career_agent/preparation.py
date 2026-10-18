"""Offline, deterministic application preparation from recorded facts.

Nothing here sends data anywhere, generates answers, or claims a submission.
The draft is an assembly of the candidate profile and the listing exactly as
stored; missing facts stay missing and eligibility stays three-valued.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .core import (
    CandidateProfile,
    Decision,
    EligibilityReport,
    JobListing,
    evaluate_eligibility,
    score_relevance,
)


class Readiness(str, Enum):
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ChecklistItem:
    requirement: str
    decision: Decision
    explanation: str


@dataclass(frozen=True)
class ReadinessReport:
    decision: Readiness
    eligibility: EligibilityReport
    items: tuple[ChecklistItem, ...]
    notes: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @property
    def can_prepare(self) -> bool:
        return self.decision is Readiness.READY


@dataclass(frozen=True)
class DraftField:
    label: str
    value: str | None
    source: str


@dataclass(frozen=True)
class ApplicationDraft:
    role_title: str
    employer_name: str
    fields: tuple[DraftField, ...]
    summary: str
    warnings: tuple[str, ...] = ()


def assess_readiness(
    profile: CandidateProfile,
    job: JobListing,
    *,
    other_active_label: str | None = None,
) -> ReadinessReport:
    """Decide whether the recorded facts support marking an application prepared.

    Blockers are hard: failed/unknown eligibility or an active application on a
    duplicate observation. A missing employer application URL is not fabricated;
    it downgrades the result to review because the destination is unverified.
    """
    eligibility = evaluate_eligibility(profile, job)
    items = tuple(
        ChecklistItem(result.requirement, result.decision, result.explanation)
        for result in eligibility.requirements
    )
    blockers: list[str] = []
    notes: list[str] = []

    if eligibility.decision is Decision.FAIL:
        blockers.extend(
            f"Eligibility failed: {result.requirement} — {result.explanation}"
            for result in eligibility.failed_requirements
        )
    elif eligibility.decision is Decision.UNKNOWN:
        blockers.extend(
            f"Eligibility unknown: {result.requirement} — {result.explanation}"
            for result in eligibility.unknown_requirements
        )

    if other_active_label:
        blockers.append(
            "Another observation of this job already has an active application: "
            f"{other_active_label}. Use that record instead of preparing a duplicate."
        )

    if not job.employer_apply_url:
        notes.append(
            "No verified employer application URL is recorded; the destination of any "
            "future application is unknown."
        )

    if blockers:
        decision = Readiness.BLOCKED
    elif notes:
        decision = Readiness.NEEDS_REVIEW
    else:
        decision = Readiness.READY

    return ReadinessReport(decision, eligibility, items, tuple(notes), tuple(blockers))


def _field(label: str, value: object, source: str) -> DraftField:
    if value is None:
        return DraftField(label, None, "not recorded")
    if isinstance(value, str):
        text = value.strip() or None
        return DraftField(label, text, source if text else "not recorded")
    return DraftField(label, str(value), source)


def build_application_draft(profile: CandidateProfile, job: JobListing) -> ApplicationDraft:
    """Assemble a human-readable preview using only recorded profile/listing data."""
    relevance = score_relevance(profile, job)
    matched = ", ".join(relevance.get("matched_skills") or [])
    missing = ", ".join(relevance.get("missing_required_skills") or [])
    recorded_skills = ", ".join(sorted(profile.skills)) or None

    fields = (
        _field("Employer", job.employer_name, "listing"),
        _field("Role", job.role_title, "listing"),
        _field("Source listing URL", job.source_listing_url, "listing"),
        _field("Employer application URL", job.employer_apply_url, "listing"),
        _field("Location", job.location_text, "listing"),
        _field("Work mode", job.work_mode, "listing"),
        _field("Role type", job.role_type, "listing"),
        _field("Availability", job.availability_status.value, "listing"),
        _field("Availability evidence", job.provenance_note, "listing"),
        _field("Candidate country", profile.candidate_country, "candidate profile"),
        _field("Degree / discipline", profile.degree_discipline, "candidate profile"),
        _field("Study status", profile.study_status, "candidate profile"),
        _field("Graduation year", profile.graduation_year, "candidate profile"),
        _field("Experience (years)", profile.experience_years, "candidate profile"),
        _field("Work authorization", profile.work_authorization, "candidate profile"),
        _field("Recorded skills", recorded_skills, "candidate profile"),
        _field("Matched required skills", matched or None, "candidate profile + listing"),
        _field("Required skills not recorded", missing or None, "candidate profile + listing"),
    )

    facts = [
        f"{label.lower()}: {value}"
        for label, value in (
            ("Candidate country", profile.candidate_country),
            ("discipline", profile.degree_discipline),
            ("study status", profile.study_status),
            ("graduation year", profile.graduation_year),
            ("experience years", profile.experience_years),
            ("work authorization", profile.work_authorization),
        )
        if value not in (None, "")
    ]
    skills = f" Skills recorded: {recorded_skills}." if recorded_skills else ""
    gaps = f" Required skills not recorded: {missing}." if missing else ""
    summary = (
        f"Application draft for {job.role_title} at {job.employer_name}. "
        f"Recorded candidate facts: {', '.join(facts) if facts else 'none recorded'}."
        f"{skills}{gaps} "
        f"Eligibility: {evaluate_eligibility(profile, job).decision.value.upper()}. "
        "Prepared locally from recorded facts only; no answers, contact details, or "
        "qualifications were invented, and nothing has been submitted."
    )

    warnings: list[str] = []
    if not job.employer_apply_url:
        warnings.append("Employer application URL is not recorded.")
    if not profile.skills:
        warnings.append("No candidate skills are recorded.")
    return ApplicationDraft(job.role_title, job.employer_name, fields, summary, tuple(warnings))
