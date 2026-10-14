"""Local-first, dependency-free domain logic for AI Career Agent.

This module deliberately performs no network access, file persistence, resume parsing,
form filling, or application submission. It provides deterministic rules for the
future desktop application to call and test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import re


class Decision(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class Availability(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
    UNKNOWN = "unknown"
    NOT_A_LISTING = "not_a_listing"
    SOURCE_REVIEW = "source_review"


class ApplicationStatus(str, Enum):
    DISCOVERED = "discovered"
    SHORTLISTED = "shortlisted"
    PREPARED = "prepared"
    AWAITING_USER = "awaiting_user"
    SUBMISSION_ATTEMPTED = "submission_attempted"
    SUBMITTED_UNVERIFIED = "submitted_unverified"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    UNKNOWN_STATUS = "unknown_status"
    RESPONSE_RECEIVED = "response_received"
    INTERVIEW = "interview"
    REJECTED_BY_EMPLOYER = "rejected_by_employer"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class CandidateProfile:
    """Only explicitly supplied candidate facts belong here; missing means unknown."""
    candidate_country: str | None = None
    degree_discipline: str | None = None
    study_status: str | None = None
    graduation_year: int | None = None
    experience_years: float | None = None
    work_authorization: str | None = None
    skills: frozenset[str] = field(default_factory=frozenset)
    preferred_locations: frozenset[str] = field(default_factory=frozenset)
    preferred_work_modes: frozenset[str] = field(default_factory=frozenset)
    preferred_role_types: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class JobListing:
    """Normalized listing with source provenance and explicit uncertainty."""
    listing_id: str
    source_id: str
    source_name: str
    source_listing_url: str
    employer_name: str
    role_title: str
    availability_status: Availability = Availability.UNKNOWN
    employer_apply_url: str | None = None
    canonical_requisition_id: str | None = None
    location_text: str | None = None
    work_mode: str | None = None
    role_type: str | None = None
    eligibility_scope: str = "unknown"  # worldwide | restricted | unknown
    eligible_countries: tuple[str, ...] = ()
    allowed_degree_disciplines: tuple[str, ...] | None = None
    allowed_study_statuses: tuple[str, ...] | None = None
    allowed_graduation_years: tuple[int, ...] | None = None
    minimum_experience_years: float | None = None
    maximum_experience_years: float | None = None
    required_skills: frozenset[str] = field(default_factory=frozenset)
    provenance_note: str | None = None
    allowed_work_authorizations: tuple[str, ...] | None = None


@dataclass(frozen=True)
class RequirementResult:
    requirement: str
    decision: Decision
    explanation: str
    evidence: str | None = None


@dataclass(frozen=True)
class EligibilityReport:
    decision: Decision
    requirements: tuple[RequirementResult, ...]

    @property
    def can_be_ranked_as_eligible(self) -> bool:
        return self.decision is Decision.PASS

    @property
    def failed_requirements(self) -> tuple[RequirementResult, ...]:
        return tuple(r for r in self.requirements if r.decision is Decision.FAIL)

    @property
    def unknown_requirements(self) -> tuple[RequirementResult, ...]:
        return tuple(r for r in self.requirements if r.decision is Decision.UNKNOWN)


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().casefold().split())
    return cleaned or None


def _country_norm(value: str) -> str:
    return " ".join(value.strip().casefold().replace(".", "").split())


def _label_norm(value: str) -> str:
    """Collapse case and whitespace for label-like values (discipline, study status).

    This normalizes formatting only. It never maps one distinct label onto another,
    so a related discipline or an approximate cohort still fails the check.
    """
    return " ".join(str(value).strip().casefold().split())


def _membership_key(value: str, *, fold_separators: bool = False) -> str:
    """Normalized comparison key for an explicitly listed requirement value.

    ``fold_separators`` additionally treats underscores as spaces, which is the same
    tolerance the project uses for comma/newline-separated lists; it does not make
    different values equivalent.
    """
    folded = _label_norm(value)
    return folded.replace("_", " ") if fold_separators else folded


def evaluate_eligibility(profile: CandidateProfile, job: JobListing) -> EligibilityReport:
    """Evaluate only explicit hard requirements; missing evidence remains unknown.

    An open listing is necessary but not sufficient. Any known failure makes the
    overall result fail; otherwise any unknown makes it unknown; only all-pass is pass.
    """
    results: list[RequirementResult] = []

    if job.availability_status is Availability.OPEN and job.provenance_note and job.provenance_note.strip():
        results.append(RequirementResult("availability", Decision.PASS, "The listing is marked open and has a recorded evidence/note; recheck the original listing before acting.", job.provenance_note.strip()))
    elif job.availability_status is Availability.OPEN:
        results.append(RequirementResult("availability", Decision.UNKNOWN, "The listing is marked open but has no recorded availability evidence/note."))
    elif job.availability_status in {Availability.CLOSED, Availability.EXPIRED, Availability.NOT_A_LISTING, Availability.SOURCE_REVIEW}:
        results.append(RequirementResult("availability", Decision.FAIL, f"Listing status is {job.availability_status.value}; it must not be recommended as an open vacancy."))
    else:
        results.append(RequirementResult("availability", Decision.UNKNOWN, "Current availability is not confirmed."))

    if job.eligibility_scope == "worldwide":
        if profile.candidate_country:
            results.append(RequirementResult("country", Decision.PASS, "The source explicitly identifies the role as worldwide.", "eligibility_scope=worldwide"))
        else:
            results.append(RequirementResult("country", Decision.UNKNOWN, "Candidate country is missing, so country-specific fit cannot be evaluated."))
    elif job.eligibility_scope == "restricted":
        if not profile.candidate_country or not job.eligible_countries:
            results.append(RequirementResult("country", Decision.UNKNOWN, "Country restrictions exist, but the candidate country or allowed-country list is missing."))
        elif _country_norm(profile.candidate_country) in {_country_norm(c) for c in job.eligible_countries}:
            results.append(RequirementResult("country", Decision.PASS, "Candidate country appears in the explicit allowed-country list.", ", ".join(job.eligible_countries)))
        else:
            results.append(RequirementResult("country", Decision.FAIL, "Candidate country is not in the explicit allowed-country list.", ", ".join(job.eligible_countries)))
    else:
        results.append(RequirementResult("country", Decision.UNKNOWN, "Worldwide eligibility or the allowed-country list has not been verified."))

    if job.allowed_work_authorizations is not None:
        _check_membership(
            results, "work_authorization", profile.work_authorization, job.allowed_work_authorizations,
            "Candidate work-authorization value matches an explicitly allowed value.",
            "Candidate work-authorization value does not match the explicitly allowed values.",
            "Work-authorization requirement or candidate work-authorization value is missing.",
            fold_separators=True,
        )

    _check_membership(results, "degree_discipline", profile.degree_discipline, job.allowed_degree_disciplines,
                      "Candidate discipline matches an explicitly allowed discipline.",
                      "Candidate discipline is not in the explicitly allowed list.",
                      "Degree/discipline eligibility or candidate discipline is missing.")
    _check_membership(results, "study_status", profile.study_status, job.allowed_study_statuses,
                      "Candidate study status matches an explicitly allowed status.",
                      "Candidate study status is not in the explicitly allowed list.",
                      "Study-status eligibility or candidate status is missing.")
    _check_membership(results, "graduation_year", profile.graduation_year, job.allowed_graduation_years,
                      "Candidate graduation year is explicitly accepted.",
                      "Candidate graduation year is outside the explicitly accepted cohort.",
                      "Graduation cohort or candidate graduation year is missing.")

    if job.minimum_experience_years is not None or job.maximum_experience_years is not None:
        if profile.experience_years is None:
            results.append(RequirementResult("experience_years", Decision.UNKNOWN, "Required experience range cannot be checked because candidate experience is missing."))
        elif job.minimum_experience_years is not None and profile.experience_years < job.minimum_experience_years:
            results.append(RequirementResult("experience_years", Decision.FAIL, "Candidate experience is below the stated minimum."))
        elif job.maximum_experience_years is not None and profile.experience_years > job.maximum_experience_years:
            results.append(RequirementResult("experience_years", Decision.FAIL, "Candidate experience exceeds the stated maximum."))
        else:
            results.append(RequirementResult("experience_years", Decision.PASS, "Candidate experience is within the stated range."))

    decisions = {r.decision for r in results}
    overall = Decision.FAIL if Decision.FAIL in decisions else Decision.UNKNOWN if Decision.UNKNOWN in decisions else Decision.PASS
    return EligibilityReport(overall, tuple(results))


def _check_membership(
    results: list[RequirementResult], name: str, actual: str | None, allowed: Sequence[str] | None,
    pass_message: str, fail_message: str, unknown_message: str, *, fold_separators: bool = False,
) -> None:
    """Record a PASS/FAIL/UNKNOWN membership check for one explicitly listed requirement.

    Formatting is normalized on both sides (case and surrounding whitespace; work
    authorization additionally treats underscores like spaces) so that the same
    declared value written differently still matches. Genuinely different values
    still fail, missing values stay unknown, and no fuzzy or semantic matching is
    applied: a related discipline or an approximate cohort must be reviewed by hand.
    """
    if allowed is None or actual is None or not str(actual).strip():
        results.append(RequirementResult(name, Decision.UNKNOWN, unknown_message))
        return
    normalized = _membership_key(str(actual), fold_separators=fold_separators)
    allowed_keys = {_membership_key(str(item), fold_separators=fold_separators) for item in allowed}
    if normalized in allowed_keys:
        results.append(RequirementResult(name, Decision.PASS, pass_message, str(actual)))
    else:
        results.append(RequirementResult(name, Decision.FAIL, fail_message, str(actual)))


_TRACKER_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.DISCOVERED: frozenset({ApplicationStatus.SHORTLISTED, ApplicationStatus.WITHDRAWN}),
    ApplicationStatus.SHORTLISTED: frozenset({ApplicationStatus.PREPARED, ApplicationStatus.WITHDRAWN}),
    ApplicationStatus.PREPARED: frozenset({ApplicationStatus.AWAITING_USER, ApplicationStatus.WITHDRAWN}),
    ApplicationStatus.AWAITING_USER: frozenset({ApplicationStatus.SUBMISSION_ATTEMPTED, ApplicationStatus.FAILED, ApplicationStatus.WITHDRAWN}),
    ApplicationStatus.SUBMISSION_ATTEMPTED: frozenset({ApplicationStatus.SUBMITTED_UNVERIFIED, ApplicationStatus.CONFIRMED, ApplicationStatus.FAILED, ApplicationStatus.UNKNOWN_STATUS}),
    ApplicationStatus.SUBMITTED_UNVERIFIED: frozenset({ApplicationStatus.CONFIRMED, ApplicationStatus.FAILED, ApplicationStatus.UNKNOWN_STATUS}),
    ApplicationStatus.UNKNOWN_STATUS: frozenset({ApplicationStatus.CONFIRMED, ApplicationStatus.FAILED}),
    ApplicationStatus.CONFIRMED: frozenset({ApplicationStatus.RESPONSE_RECEIVED, ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED_BY_EMPLOYER, ApplicationStatus.WITHDRAWN}),
    ApplicationStatus.RESPONSE_RECEIVED: frozenset({ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED_BY_EMPLOYER, ApplicationStatus.WITHDRAWN}),
    ApplicationStatus.INTERVIEW: frozenset({ApplicationStatus.REJECTED_BY_EMPLOYER, ApplicationStatus.WITHDRAWN}),
    ApplicationStatus.FAILED: frozenset({ApplicationStatus.AWAITING_USER}),
    ApplicationStatus.REJECTED_BY_EMPLOYER: frozenset(),
    ApplicationStatus.WITHDRAWN: frozenset(),
}


#: The only status a tracker record may be created with. A record with no history
#: cannot legitimately appear shortlisted, submitted, confirmed, or completed, so the
#: first write must be the honest starting point and every later status must be a
#: permitted transition from it.
INITIAL_APPLICATION_STATUS = ApplicationStatus.DISCOVERED


#: Instruction text this application or its repository displays about tracker evidence. A
#: confirmation claims that a real application was really confirmed, so guidance text must never
#: be storable as the evidence for it: a tester following the smoke-test checklist (or a user
#: copying a label) can paste instruction text into the evidence field, where it would then read
#: as proof. Entries are the app's own sentences, normalized the same way evidence is, so they
#: match pasted instructions without refusing ordinary notes that merely share a word.
#: Each entry names the place it is displayed.
_INSTRUCTIONAL_EVIDENCE_FRAGMENTS = (
    "a confirmed application requires evidence",        # tracker tab label and store refusal message
    "confirmation requires evidence",                   # refusal message when evidence is empty
    "click or attempted submission is not proof",        # refusal message
    "attempt or timeout is not proof",                   # tracker tab label
    "evidence / note (required to confirm)",             # status dialog field label
    "required to confirm",                               # status dialog field label
    "meaningful evidence note",                          # local-alpha smoke-test checklist, tracker step
    "move the status forward with a meaningful note",     # no-change dialog
    "move the status forward",                           # no-change dialog
    "keep the existing record as it is",                 # no-change dialog
    "do not confirm a simulated",                        # confirmation guidance
)

#: Whole-value placeholders that are never a record of what an employer showed. Matched after
#: normalization as the *complete* value rather than as a substring, so a real note that merely
#: contains one of these words (for example "Portal shows no test results yet") is not refused.
_PLACEHOLDER_EVIDENCE_VALUES = frozenset(
    {
        "", "-", "--", "...", "?", "n/a", "na", "none", "nil", "null", "todo", "tbd", "tbc",
        "fixme", "placeholder", "evidence", "note", "notes", "text", "unknown", "asdf", "test",
        "testing", "confirmed", "yes", "no",
    }
)


def _normalize_evidence_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def is_substantive_confirmation_evidence(text: str | None) -> bool:
    """True when ``text`` could honestly be a record of what the employer showed.

    This is a deliberately narrow *floor*, not authentication: it refuses empty or
    whitespace-only text, this project's own instructional text, and bare placeholders
    such as ``todo``, ``n/a``, or ``yes``. It cannot and does not decide whether a
    confirmation genuinely happened. That decision always remains the candidate's explicit
    assertion, which is why the desktop dialog asks for the assertion instead of inferring it
    from the chosen status.
    """
    normalized = _normalize_evidence_text(text or "")
    if not normalized or normalized in _PLACEHOLDER_EVIDENCE_VALUES:
        return False
    if normalized.startswith("<") and normalized.endswith(">"):
        return False
    return not any(fragment in normalized for fragment in _INSTRUCTIONAL_EVIDENCE_FRAGMENTS)


def require_confirmation_evidence(text: str | None) -> str:
    """Return the trimmed evidence text for a confirmation, or raise ``ValueError``.

    The message is user-facing and describes what to enter instead, without claiming the
    software can verify the claim itself.
    """
    if not (text or "").strip():
        raise ValueError("Confirmation requires evidence; a click or attempted submission is not proof.")
    if not is_substantive_confirmation_evidence(text):
        raise ValueError(
            "That text looks like an instruction or a placeholder rather than a record of what the "
            "employer showed you. Describe what you actually observed, for example "
            "\"Employer portal showed Application Received on 2026-10-14\". Nothing was saved."
        )
    return text.strip()


def is_allowed_tracker_transition(current: ApplicationStatus, new_status: ApplicationStatus) -> bool:
    """True when the domain state machine permits this status change.

    Re-applying the current status is treated as an idempotent no-op rather than an
    invalid jump, so a repeated save of unchanged state is not an error. Every other
    change must be listed in ``_TRACKER_TRANSITIONS``.
    """
    return new_status == current or new_status in _TRACKER_TRANSITIONS[current]


def selectable_tracker_statuses(current: ApplicationStatus) -> tuple[ApplicationStatus, ...]:
    """The statuses a chooser may offer for a record that is currently at ``current``.

    Exactly the statuses an action can succeed with: the current one (so a record can be re-saved, and
    a new record can be created at the permitted initial status) plus every permitted transition.
    Offering anything else would imply the application supports a move it will refuse, and a chooser
    that lists all thirteen statuses invites a user to pick one that cannot be recorded. The order
    follows the declaration order of :class:`ApplicationStatus` — the order the statuses are documented
    in — so the list reads the same way every time and no option is promoted by being listed first.
    """
    permitted = _TRACKER_TRANSITIONS[current]
    return tuple(status for status in ApplicationStatus if status is current or status in permitted)


@dataclass(frozen=True)
class ApplicationTracker:
    listing_id: str
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    status_evidence: str | None = None
    candidate_confirmed: bool = False

    def transition(
        self, new_status: ApplicationStatus, *, evidence: str | None = None,
        candidate_confirmed: bool | None = None,
    ) -> "ApplicationTracker":
        """Return the tracker moved to ``new_status``, or ``self`` for a no-op.

        Requesting the status the tracker already holds is not an update: the tracker
        is returned unchanged, so newly supplied evidence is neither recorded nor
        silently discarded. Evidence is revised by moving the status forward with
        ``evidence=...``; a confirmed status always requires evidence text.
        """
        if new_status == self.status:
            return self
        if new_status not in _TRACKER_TRANSITIONS[self.status]:
            raise ValueError(f"Invalid application transition: {self.status.value} -> {new_status.value}")
        if new_status is ApplicationStatus.CONFIRMED:
            require_confirmation_evidence(evidence)
        return ApplicationTracker(
            listing_id=self.listing_id,
            status=new_status,
            status_evidence=evidence.strip() if evidence else None,
            candidate_confirmed=self.candidate_confirmed if candidate_confirmed is None else candidate_confirmed,
        )


def canonicalize_url(url: str) -> str:
    """Normalize obvious URL noise without lowercasing case-sensitive paths."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.casefold()
    host = (parts.hostname or "").casefold()
    if not scheme or not host:
        return url.strip()
    port = parts.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        host = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    ignored_prefixes = ("utm_",)
    ignored_exact = {"gclid", "fbclid", "ref", "source"}
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.casefold() not in ignored_exact and not k.casefold().startswith(ignored_prefixes)]
    query.sort()
    return urlunsplit((scheme, host, path, urlencode(query, doseq=True), ""))


def duplicate_key(job: JobListing) -> str:
    """Conservative identity key; do not merge jobs merely because titles look similar."""
    employer = _norm(job.employer_name) or "unknown-employer"
    if job.canonical_requisition_id:
        return f"requisition:{employer}:{_norm(job.canonical_requisition_id)}"
    if job.source_listing_url.strip():
        return f"url:{canonicalize_url(job.source_listing_url)}"
    return f"source:{job.source_id}:{job.listing_id}"


def deduplicate_listings(jobs: Sequence[JobListing]) -> tuple[JobListing, ...]:
    """Keep first-seen representative for each conservative key; retain source provenance upstream."""
    seen: set[str] = set()
    unique: list[JobListing] = []
    for job in jobs:
        key = duplicate_key(job)
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return tuple(unique)


def score_relevance(profile: CandidateProfile, job: JobListing) -> dict[str, Any]:
    """Return transparent overlap, never a probability of getting hired.

    This function intentionally does not override eligibility. Callers must evaluate
    eligibility first and must not rank a FAIL or UNKNOWN result as definitively eligible.
    """
    candidate_skills = {_norm(s) for s in profile.skills if _norm(s)}
    required_skills = {_norm(s) for s in job.required_skills if _norm(s)}
    matched = sorted(candidate_skills & required_skills)
    missing = sorted(required_skills - candidate_skills)
    skill_score = round(len(matched) / len(required_skills), 3) if required_skills else None
    factors: dict[str, Any] = {
        "matched_skills": matched,
        "missing_required_skills": missing,
        "skill_overlap": skill_score,
        "role_type_fit": "unknown",
        "work_mode_fit": "unknown",
        "eligible": "not_evaluated",
        "note": "Relevance indicators only; not a hiring probability and not an eligibility decision.",
    }
    if job.role_type and profile.preferred_role_types:
        factors["role_type_fit"] = "pass" if _norm(job.role_type) in {_norm(v) for v in profile.preferred_role_types} else "fail"
    if job.work_mode and profile.preferred_work_modes:
        factors["work_mode_fit"] = "pass" if _norm(job.work_mode) in {_norm(v) for v in profile.preferred_work_modes} else "fail"
    return factors


def job_to_public_dict(job: JobListing) -> Mapping[str, Any]:
    """Serialize fields explicitly; source and employer application URLs stay separate."""
    return {
        "listing_id": job.listing_id,
        "source_id": job.source_id,
        "source_name": job.source_name,
        "source_listing_url": job.source_listing_url,
        "employer_apply_url": job.employer_apply_url,
        "employer_name": job.employer_name,
        "role_title": job.role_title,
        "availability_status": job.availability_status.value,
        "location_text": job.location_text,
        "work_mode": job.work_mode,
        "eligibility_scope": job.eligibility_scope,
        "eligible_countries": list(job.eligible_countries),
        "allowed_work_authorizations": list(job.allowed_work_authorizations) if job.allowed_work_authorizations is not None else None,
        "provenance_note": job.provenance_note,
    }
