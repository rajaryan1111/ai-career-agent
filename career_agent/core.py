"""Local-first, dependency-free domain logic for AI Career Agent.

This module deliberately performs no network access, file persistence, resume parsing,
form filling, or application submission. It provides deterministic rules for the
future desktop application to call and test.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import math
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


class ActivityKind(str, Enum):
    """What a dated activity entry is.

    A closed set, so the log can be grouped and read without interpreting free text. It records what
    the *person* says happened; it is not evidence for a tracker confirmation and never changes a
    status.
    """

    APPLIED = "applied"
    RESPONSE = "response"
    INTERVIEW = "interview"
    ASSESSMENT = "assessment"
    FOLLOW_UP = "follow-up"
    NOTE = "note"


#: How each kind is shown. First person for the person's own actions, plain description for the
#: employer's, so the label never claims something the entry does not say.
ACTIVITY_KIND_LABELS = {
    ActivityKind.APPLIED: "I applied",
    ActivityKind.RESPONSE: "Employer replied",
    ActivityKind.INTERVIEW: "Interview",
    ActivityKind.ASSESSMENT: "Assessment or test",
    ActivityKind.FOLLOW_UP: "I followed up",
    ActivityKind.NOTE: "Note",
}

#: The longest detail text an activity entry may hold. A log line, not a document: the limit keeps one
#: entry readable in a list and keeps a pasted document out of the history.
MAX_ACTIVITY_DETAIL_LENGTH = 500

#: Bounds for a date a person typed. Wide enough for any real application history, narrow enough to
#: catch a mistyped year (`2202-01-01`) instead of storing it.
_MIN_ACTIVITY_YEAR = 1900
_MAX_ACTIVITY_YEAR = 2100


def validate_activity_detail(detail: str) -> str:
    """Return the trimmed detail text, or raise ``ValueError`` with a message to show the person."""
    if not isinstance(detail, str) or not detail.strip():
        raise ValueError("Write what happened before saving an activity entry.")
    text = detail.strip()
    if len(text) > MAX_ACTIVITY_DETAIL_LENGTH:
        raise ValueError(
            f"An activity entry can hold at most {MAX_ACTIVITY_DETAIL_LENGTH} characters "
            f"(this one is {len(text)}). Summarise it instead of pasting a whole document."
        )
    return text


def validate_activity_date(value: date) -> date:
    """Return the date, or raise ``ValueError`` when it cannot be a real entry date."""
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("Give the activity entry a date as YYYY-MM-DD.")
    if not _MIN_ACTIVITY_YEAR <= value.year <= _MAX_ACTIVITY_YEAR:
        raise ValueError(
            f"The date must be a real calendar date between {_MIN_ACTIVITY_YEAR} and "
            f"{_MAX_ACTIVITY_YEAR}; {value.isoformat()} looks like a typo."
        )
    return value


@dataclass(frozen=True)
class ApplicationActivity:
    """One dated entry in an application's history: what the person says happened.

    ``occurred_on`` is the day the person names and ``recorded_at`` is when this application wrote the
    row, so the two are never confused. An entry is the person's own record: it is not evidence for a
    tracker confirmation, it does not change a status, and it is never treated as proof that an
    employer did anything.
    """

    kind: ActivityKind
    occurred_on: date
    detail: str
    activity_id: int | None = None
    recorded_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", validate_activity_detail(self.detail))
        object.__setattr__(self, "occurred_on", validate_activity_date(self.occurred_on))
        if not isinstance(self.kind, ActivityKind):
            object.__setattr__(self, "kind", ActivityKind(self.kind))

    @property
    def label(self) -> str:
        return ACTIVITY_KIND_LABELS[self.kind]


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
        if not (_is_real_number(profile.experience_years) and _is_real_number(job.minimum_experience_years)
                and _is_real_number(job.maximum_experience_years)):
            # A stored value that is not a real number (an old or hand-edited row holding nan or
            # infinity) cannot be compared with anything: nan is false against every bound, so
            # comparing it would fall through to "within the stated range" and pass a requirement
            # that was never actually satisfied. Unknown is the honest answer.
            results.append(RequirementResult("experience_years", Decision.UNKNOWN, "The stated experience range or the candidate experience value is not a real number, so it cannot be evaluated."))
        elif profile.experience_years is None:
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


def _is_real_number(value: object) -> bool:
    """True when ``value`` is ``None`` (not stated) or a finite number.

    Guards the experience comparison against a stored ``nan`` or ``inf``: ``nan`` is false against
    every bound, so an unguarded comparison reaches the "within range" branch and reports a pass for
    a requirement nobody satisfied.
    """
    if value is None:
        return True
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


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
        # A phrase about trying the feature is not a record of what an employer showed either. These
        # are whole values, like the list above, so an honest note that merely contains a word such as
        # "test" or "sample" is still accepted; only the bare phrase is refused.
        "this is a test", "this is only a test", "just a test", "just testing", "test only",
        "testing only", "for testing", "test text", "sample", "sample text", "example",
        "example text", "dummy", "lorem ipsum",
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


#: The longest a follow-up note may be. Long enough for "ask Priya about the interview panel", short
#: enough that it stays a reminder rather than becoming a document.
MAX_FOLLOW_UP_NOTE_LENGTH = 300


def validate_follow_up_date(value: date) -> date:
    """Return the day, or raise ``ValueError`` when it cannot be a day to act on.

    The bounds are the same as an activity date's, for the same reason: a mistyped year (``0202``,
    ``20226``) should be refused where it is typed rather than quietly stored as a reminder nobody will
    ever see.
    """
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError("Give the follow-up a day as YYYY-MM-DD.")
    if not _MIN_ACTIVITY_YEAR <= value.year <= _MAX_ACTIVITY_YEAR:
        raise ValueError(
            f"The follow-up day must be a real calendar date between {_MIN_ACTIVITY_YEAR} and "
            f"{_MAX_ACTIVITY_YEAR}; {value.isoformat()} looks like a typo."
        )
    return value


def validate_follow_up_note(note: str | None) -> str | None:
    """Return the trimmed note (or ``None``), refusing one that is blank or too long."""
    if note is None:
        return None
    if not isinstance(note, str):
        raise ValueError("A follow-up note must be text.")
    text = " ".join(note.split())
    if not text:
        return None
    if len(text) > MAX_FOLLOW_UP_NOTE_LENGTH:
        raise ValueError(
            f"A follow-up note can hold at most {MAX_FOLLOW_UP_NOTE_LENGTH} characters (this one is "
            f"{len(text)}). Keep it to what you will need on the day."
        )
    return text


@dataclass(frozen=True)
class ApplicationTracker:
    listing_id: str
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    status_evidence: str | None = None
    candidate_confirmed: bool = False
    follow_up_on: date | None = None
    follow_up_note: str | None = None
    # ``follow_up_on`` and ``follow_up_note`` survive ``transition``: they are a plan the person made,
    # not a property of a status, and the store writes them only when a caller says to (see
    # ``CareerStore.save_tracker``).

    def with_follow_up(self, on: date | None, *, note: str | None = None) -> "ApplicationTracker":
        """Return the tracker with a day to act on set, changed, or cleared.

        This is a *plan*, not a status: setting a reminder to chase a reply does not make the
        application chase itself, and nothing here changes ``status``. That separation is the whole
        point - ordinary activity must never advance an application, and neither must a reminder.

        A note without a day is refused rather than stored, because a reminder with no day is a note
        the person will never be shown at the right time; clear the day and the note goes with it.
        """
        if on is None:
            if note:
                raise ValueError(
                    "A follow-up note needs a day to appear on. Set the day as well, or clear both."
                )
            return replace(self, follow_up_on=None, follow_up_note=None)
        day = validate_follow_up_date(on)
        return replace(self, follow_up_on=day, follow_up_note=validate_follow_up_note(note))

    @property
    def has_follow_up(self) -> bool:
        """Whether a day to act on has been recorded."""
        return self.follow_up_on is not None

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
            # A plan outlives a status change. The day was chosen by the person and the status moving on
            # does not make it wrong - silently dropping the reminder here would mean a follow-up that
            # disappears exactly when the application becomes worth chasing.
            follow_up_on=self.follow_up_on,
            follow_up_note=self.follow_up_note,
        )


class PreparationKind(str, Enum):
    """What kind of preparation an item is. A closed set, so the interface can group by it."""

    TAILORING = "tailoring"
    RESEARCH = "research"
    PRACTICE = "practice"
    DOCUMENTS = "documents"
    OTHER = "other"


PREPARATION_KIND_LABELS = {
    PreparationKind.TAILORING: "Tailor the application",
    PreparationKind.RESEARCH: "Research the employer",
    PreparationKind.PRACTICE: "Practise for the interview",
    PreparationKind.DOCUMENTS: "Get a document ready",
    PreparationKind.OTHER: "Something else",
}

MAX_PREPARATION_TITLE_LENGTH = 200


def validate_preparation_title(title: str) -> str:
    """Return the trimmed title, refusing an empty or over-long one where it is typed."""
    if not isinstance(title, str):
        raise ValueError("A preparation item needs a short title.")
    text = " ".join(title.split())
    if not text:
        raise ValueError("A preparation item needs a short title; this one is empty.")
    if len(text) > MAX_PREPARATION_TITLE_LENGTH:
        raise ValueError(
            f"A preparation title can hold at most {MAX_PREPARATION_TITLE_LENGTH} characters (this one "
            f"is {len(text)}). Keep it to something you will recognise in a list."
        )
    return text


@dataclass(frozen=True)
class PreparationItem:
    """One thing to do before applying, or before an interview. A plan, never a claim.

    Nothing here is evidence about an application: finishing an item does not mean anything was sent,
    and the record carries no status field for exactly that reason. Completing an item is something the
    *person* did - the row remembers when they said so - and it never moves the application on. That
    separation is the same rule the activity log and the follow-up day follow.
    """

    listing_id: str
    title: str
    kind: PreparationKind = PreparationKind.OTHER
    due_on: date | None = None
    preparation_id: int | None = None
    done_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", validate_preparation_title(self.title))
        if not isinstance(self.kind, PreparationKind):
            object.__setattr__(self, "kind", PreparationKind(self.kind))
        if self.due_on is not None:
            object.__setattr__(self, "due_on", validate_follow_up_date(self.due_on))

    @property
    def is_done(self) -> bool:
        return self.done_at is not None

    @property
    def label(self) -> str:
        return PREPARATION_KIND_LABELS[self.kind]


class InterviewStage(str, Enum):
    """Which round of an employer's process a record describes."""

    SCREENING = "screening"
    TECHNICAL = "technical"
    SYSTEM_DESIGN = "system_design"
    BEHAVIOURAL = "behavioural"
    PANEL = "panel"
    FINAL = "final"
    OTHER = "other"


INTERVIEW_STAGE_LABELS = {
    InterviewStage.SCREENING: "Screening call",
    InterviewStage.TECHNICAL: "Technical interview",
    InterviewStage.SYSTEM_DESIGN: "Design or case round",
    InterviewStage.BEHAVIOURAL: "Behavioural interview",
    InterviewStage.PANEL: "Panel interview",
    InterviewStage.FINAL: "Final round",
    InterviewStage.OTHER: "Other round",
}


class InterviewMode(str, Enum):
    VIDEO = "video"
    PHONE = "phone"
    ONSITE = "onsite"
    TAKE_HOME = "take_home"
    UNKNOWN = "unknown"


INTERVIEW_MODE_LABELS = {
    InterviewMode.VIDEO: "Video call",
    InterviewMode.PHONE: "Phone",
    InterviewMode.ONSITE: "On site",
    InterviewMode.TAKE_HOME: "Take-home exercise",
    InterviewMode.UNKNOWN: "Not recorded",
}


class InterviewOutcome(str, Enum):
    """The person's own view of how a round went, and whether it has happened at all.

    There is deliberately no ``passed`` or ``rejected`` value. The application cannot know what an
    employer decided - that arrives as a message, it is recorded as an activity entry by the person,
    and the *status* moves only through the guarded transition path with evidence. Offering an outcome
    value that sounds like an employer's decision would put words in an employer's mouth.
    """

    AWAITING = "awaiting"
    WENT_WELL = "went_well"
    UNCLEAR = "unclear"
    WENT_POORLY = "went_poorly"
    NOT_HELD = "not_held"


INTERVIEW_OUTCOME_LABELS = {
    InterviewOutcome.AWAITING: "Waiting - it has not happened yet",
    InterviewOutcome.WENT_WELL: "You felt it went well",
    InterviewOutcome.UNCLEAR: "You could not tell",
    InterviewOutcome.WENT_POORLY: "You felt it went poorly",
    InterviewOutcome.NOT_HELD: "It did not go ahead",
}

MAX_INTERVIEW_NOTES_LENGTH = 500


def validate_interview_notes(notes: str | None) -> str | None:
    """Return trimmed notes (or ``None``), refusing an empty or over-long value."""
    if notes is None:
        return None
    if not isinstance(notes, str):
        raise ValueError("Interview notes must be text.")
    text = " ".join(notes.split())
    if not text:
        return None
    if len(text) > MAX_INTERVIEW_NOTES_LENGTH:
        raise ValueError(
            f"Interview notes can hold at most {MAX_INTERVIEW_NOTES_LENGTH} characters (this one is "
            f"{len(text)}). Keep them to what you will want to read before the next round."
        )
    return text


@dataclass(frozen=True)
class InterviewRound:
    """One round of an employer's process, as the candidate recorded it.

    ``scheduled_on`` is the day the round is *planned* for, which is why it is required: a round with no
    day cannot appear on a timeline or remind anybody. ``outcome`` is the person's own reading of how it
    went and is filled in after the fact; it is never employer evidence and cannot confirm anything.
    """

    listing_id: str
    stage: InterviewStage
    scheduled_on: date
    mode: InterviewMode = InterviewMode.UNKNOWN
    outcome: InterviewOutcome = InterviewOutcome.AWAITING
    notes: str | None = None
    round_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.stage, InterviewStage):
            object.__setattr__(self, "stage", InterviewStage(self.stage))
        if not isinstance(self.mode, InterviewMode):
            object.__setattr__(self, "mode", InterviewMode(self.mode))
        if not isinstance(self.outcome, InterviewOutcome):
            object.__setattr__(self, "outcome", InterviewOutcome(self.outcome))
        object.__setattr__(self, "scheduled_on", validate_follow_up_date(self.scheduled_on))
        object.__setattr__(self, "notes", validate_interview_notes(self.notes))

    @property
    def stage_label(self) -> str:
        return INTERVIEW_STAGE_LABELS[self.stage]

    @property
    def mode_label(self) -> str:
        return INTERVIEW_MODE_LABELS[self.mode]

    @property
    def outcome_label(self) -> str:
        return INTERVIEW_OUTCOME_LABELS[self.outcome]

    def is_ahead(self, today: date) -> bool:
        """Whether the planned day is today or still to come, in the caller's own calendar.

        Deliberately *not* called "has not happened": this record cannot know whether a round took place,
        because that is what ``outcome`` is for and only the person fills it in. What it does know is the
        day it is planned for, and a round planned for today is still ahead of you at breakfast - which is
        exactly the case a summary must not bury in the past.
        """
        return self.scheduled_on >= today

    def is_past(self, today: date) -> bool:
        """Whether the planned day has gone by: the round is either recorded or it never happened."""
        return self.scheduled_on < today

    def days_away(self, today: date) -> int:
        return (self.scheduled_on - today).days


# ------------------------------------------------------------------ the candidate's own history
#
# Employment and study are the two things a job application is *about*, and until now the profile could
# only hold one summary number and one degree string. These records are the detail behind those summary
# fields: many rows per candidate, each editable and deletable on its own.
#
# Three rules shape them, and each one exists because of a specific way this kind of data lies:
#
# * **A contradiction is refused where it is typed.** "This role ended in 2023 and I still work there" is
#   not a formatting problem, and storing it would put a claim in the person's own record that they would
#   then be shown as fact. The refusal names both values so the person can see which one to fix.
# * **Missing is not zero.** An end date nobody supplied stays absent rather than becoming "ended today" or
#   "ended at the start date"; a role with no end date and ``is_current`` false means exactly that - it
#   ended and the person has not said when. Nothing is inferred.
# * **A free-text field is a note, not evidence.** ``summary`` is the person's words about what they did. It
#   is never parsed, never matched against a listing, and never treated as proof of anything.

class EmploymentType(str, Enum):
    """How a role was held. ``UNKNOWN`` is the default and means the person has not said."""

    UNKNOWN = "unknown"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    INTERNSHIP = "internship"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    APPRENTICESHIP = "apprenticeship"
    VOLUNTEER = "volunteer"
    OTHER = "other"


EMPLOYMENT_TYPE_LABELS = {
    EmploymentType.UNKNOWN: "Not recorded",
    EmploymentType.FULL_TIME: "Full time",
    EmploymentType.PART_TIME: "Part time",
    EmploymentType.INTERNSHIP: "Internship",
    EmploymentType.CONTRACT: "Contract",
    EmploymentType.FREELANCE: "Freelance",
    EmploymentType.APPRENTICESHIP: "Apprenticeship",
    EmploymentType.VOLUNTEER: "Volunteering",
    EmploymentType.OTHER: "Something else",
}

#: Bounds on the text a person types. Chosen to match the fields already in this module (a 200-character
#: name, a 500-character note) so the interface has one idea of how long a line of a record is.
MAX_EMPLOYER_LENGTH = 200
MAX_JOB_TITLE_LENGTH = 200
MAX_WORK_SUMMARY_LENGTH = 500
MAX_INSTITUTION_LENGTH = 200
MAX_QUALIFICATION_LENGTH = 200
MAX_DISCIPLINE_LENGTH = 200


def _record_day(value: object, *, noun: str) -> date:
    """A day a person typed, or a refusal naming which field was wrong and why it looks wrong."""
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"Give the {noun} as a calendar date (YYYY-MM-DD).")
    if not _MIN_ACTIVITY_YEAR <= value.year <= _MAX_ACTIVITY_YEAR:
        raise ValueError(
            f"The {noun} must be a real calendar date between {_MIN_ACTIVITY_YEAR} and "
            f"{_MAX_ACTIVITY_YEAR}; {value.isoformat()} looks like a typo."
        )
    return value


def _required_record_text(value: object, *, noun: str, limit: int) -> str:
    """Trimmed, non-empty, bounded text for a field a record cannot do without."""
    if not isinstance(value, str):
        raise ValueError(f"A {noun} must be text.")
    text = " ".join(value.split())
    if not text:
        raise ValueError(f"Enter the {noun}: a record with an empty one names nothing.")
    if len(text) > limit:
        raise ValueError(
            f"The {noun} can hold at most {limit} characters (this one is {len(text)}). Keep it to what "
            "you would put on a CV line."
        )
    return text


def _optional_record_text(value: object, *, noun: str, limit: int) -> str | None:
    """Trimmed text or ``None``, for a field the record can do without."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"The {noun} must be text.")
    text = " ".join(value.split())
    if not text:
        return None
    if len(text) > limit:
        raise ValueError(
            f"The {noun} can hold at most {limit} characters (this one is {len(text)})."
        )
    return text


def validate_work_dates(start: date, end: date | None, *, is_current: bool) -> tuple[date, date | None]:
    """Check one employment period, refusing an impossible range or a contradictory current flag.

    Returns the validated pair so a caller can use what was checked rather than re-deriving it. The two
    refusals this exists for:

    * **An end before a start.** Not a formatting problem - it is a period that cannot have happened, and
      storing it would make every later question about "time in this role" wrong.
    * **A current role that has an end date.** One of the two is a mistake, and the interface cannot know
      which, so it refuses and names both rather than choosing for the person.

    A role with *no* end date and ``is_current`` false is accepted: it ended, and the person has not said
    when. That is a real answer, and inventing a date for it would be worse than the gap.
    """
    checked_start = _record_day(start, noun="start date")
    if end is None:
        return checked_start, None
    checked_end = _record_day(end, noun="end date")
    if checked_end < checked_start:
        raise ValueError(
            f"The end date ({checked_end.isoformat()}) is before the start date "
            f"({checked_start.isoformat()}). Fix the dates so the period makes sense, or clear the end "
            "date if the role has not finished."
        )
    if is_current:
        raise ValueError(
            f"This is marked as your current role, and it has an end date ({checked_end.isoformat()}). "
            "A role you are still in has not ended: clear the end date, or untick the current-role box."
        )
    return checked_start, checked_end


def validate_study_dates(start: date | None, completion: date | None, *,
                         is_ongoing: bool) -> tuple[date | None, date | None]:
    """Check one period of study, refusing an impossible range or a contradictory ongoing flag.

    Both dates are optional here, because people remember their qualification and their institution far
    more reliably than the month a course began, and a required field would be filled with a guess. What
    is refused is a completion before a start, and "still studying" next to a completion date.
    """
    checked_start = None if start is None else _record_day(start, noun="start date")
    checked_completion = None if completion is None else _record_day(completion, noun="completion date")
    if checked_start is not None and checked_completion is not None and checked_completion < checked_start:
        raise ValueError(
            f"The completion date ({checked_completion.isoformat()}) is before the start date "
            f"({checked_start.isoformat()}). Fix the dates so the period makes sense."
        )
    if is_ongoing and checked_completion is not None:
        raise ValueError(
            f"This is marked as ongoing study, and it has a completion date "
            f"({checked_completion.isoformat()}). A course you are still on has not finished: clear the "
            "completion date, or untick the ongoing box."
        )
    return checked_start, checked_completion


@dataclass(frozen=True)
class WorkHistoryEntry:
    """One job, as the candidate describes it. A record they own, not a verified fact.

    ``is_current`` is stated rather than derived from ``end_date``: a role with no end date might be the
    current one, or one that ended at a time the person did not record, and only they know which.
    """

    employer: str
    job_title: str
    start_date: date
    end_date: date | None = None
    is_current: bool = False
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    summary: str | None = None
    entry_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "employer",
                           _required_record_text(self.employer, noun="employer", limit=MAX_EMPLOYER_LENGTH))
        object.__setattr__(self, "job_title",
                           _required_record_text(self.job_title, noun="job title", limit=MAX_JOB_TITLE_LENGTH))
        if not isinstance(self.employment_type, EmploymentType):
            object.__setattr__(self, "employment_type", EmploymentType(self.employment_type))
        object.__setattr__(self, "summary", _optional_record_text(
            self.summary, noun="summary of the role", limit=MAX_WORK_SUMMARY_LENGTH))
        if not isinstance(self.is_current, bool):
            raise ValueError("The current-role flag must be true or false.")
        start, end = validate_work_dates(self.start_date, self.end_date, is_current=self.is_current)
        object.__setattr__(self, "start_date", start)
        object.__setattr__(self, "end_date", end)

    @property
    def employment_type_label(self) -> str:
        return EMPLOYMENT_TYPE_LABELS[self.employment_type]

    @property
    def period(self) -> str:
        """The period as a CV writes it, with an unknown end stated as unknown rather than guessed."""
        if self.is_current:
            return f"{self.start_date.isoformat()} - present"
        if self.end_date is None:
            return f"{self.start_date.isoformat()} - end date not recorded"
        return f"{self.start_date.isoformat()} - {self.end_date.isoformat()}"

    def months_covered(self, *, today: date | None = None) -> int:
        """Whole months this role covers, for a factual total a person can read.

        A current role is counted up to ``today``, which the caller supplies - never this machine's clock
        inside the function. A role that has ended with no recorded end date returns 0, because the period
        is unknown and counting it to today would assert employment that nobody stated. The answer is a
        *duration of one employment period*, not a claim about experience: overlaps between roles are not
        merged, and nothing here is ever written back into the profile's own ``experience_years``.
        """
        if self.end_date is not None:
            end = self.end_date
        elif self.is_current:
            if today is None:
                raise ValueError("Give the day to measure a current role up to.")
            end = today
        else:
            # The role has ended and nobody recorded when. Counting it up to today would claim the person
            # is still there, so the honest answer is zero months *known*, and the caller can say how many
            # roles are in that state instead of quietly including them.
            return 0
        if end < self.start_date:
            return 0
        # Whole months completed: the difference in months, less one when the day of the month has not
        # been reached yet. The reverse (adding one when it has) counts the starting day itself as a
        # finished month, which reads a same-day start-and-end as one month of work.
        months = (end.year - self.start_date.year) * 12 + (end.month - self.start_date.month)
        if end.day < self.start_date.day:
            months -= 1
        return max(0, months)


def months_covered_by(entries: Iterable[WorkHistoryEntry], *, today: date | None = None) -> int:
    """The whole months covered by these roles together, counting months covered twice only once.

    Adding up each role's own duration would overstate somebody who changed employer without a gap, or
    who held two roles at once - and it would overstate them in the direction of "more experience",
    which is the direction to be wrong in last. This returns the span of months in which at least one
    of the recorded roles was running, which is what "these periods cover N months" claims.

    A role whose end is not recorded contributes nothing unless it is marked current, exactly as
    :meth:`WorkHistoryEntry.months_covered` decides: nothing states that it continued.
    """
    spans: list[tuple[int, int]] = []
    for entry in entries:
        months = entry.months_covered(today=today)
        if months <= 0:
            continue
        # A month is identified by the count of months since year zero, so two roles can be compared
        # without any calendar arithmetic in the comparison itself.
        first = entry.start_date.year * 12 + entry.start_date.month
        spans.append((first, first + months - 1))
    if not spans:
        return 0
    spans.sort()
    total = 0
    running_start, running_end = spans[0]
    for start, end in spans[1:]:
        if start <= running_end + 1:
            running_end = max(running_end, end)
        else:
            total += running_end - running_start + 1
            running_start, running_end = start, end
    return total + (running_end - running_start + 1)


@dataclass(frozen=True)
class EducationEntry:
    """One qualification or course, as the candidate describes it.

    ``qualification`` and ``institution`` are required because a record without them names nothing a person
    could check; the dates and the discipline are not, because a guess there would be stored as a fact.
    """

    institution: str
    qualification: str
    discipline: str | None = None
    start_date: date | None = None
    completion_date: date | None = None
    is_ongoing: bool = False
    entry_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "institution", _required_record_text(
            self.institution, noun="institution", limit=MAX_INSTITUTION_LENGTH))
        object.__setattr__(self, "qualification", _required_record_text(
            self.qualification, noun="qualification", limit=MAX_QUALIFICATION_LENGTH))
        object.__setattr__(self, "discipline", _optional_record_text(
            self.discipline, noun="discipline", limit=MAX_DISCIPLINE_LENGTH))
        if not isinstance(self.is_ongoing, bool):
            raise ValueError("The ongoing-study flag must be true or false.")
        start, completion = validate_study_dates(self.start_date, self.completion_date,
                                                 is_ongoing=self.is_ongoing)
        object.__setattr__(self, "start_date", start)
        object.__setattr__(self, "completion_date", completion)

    @property
    def period(self) -> str:
        """The period as a CV writes it, distinguishing "still studying" from "dates not recorded"."""
        start = self.start_date.isoformat() if self.start_date is not None else "start not recorded"
        if self.is_ongoing:
            return f"{start} - ongoing"
        if self.completion_date is None:
            return f"{start} - completion not recorded"
        return f"{start} - {self.completion_date.isoformat()}"

    @property
    def label(self) -> str:
        """The one-line description: qualification, then discipline when there is one."""
        return f"{self.qualification} - {self.discipline}" if self.discipline else self.qualification


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
