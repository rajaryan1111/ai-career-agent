"""Immutable eligibility-decision audit records.

A record captures what the hard-eligibility rules decided, which rule version
produced it, and versioned SHA-256 fingerprints of the inputs that were used.
Raw candidate values are never copied into a record, so a decision can be
traced without duplicating personal data in the database or in backups.

Fingerprints are change detectors, not a security boundary: they cover a small,
low-entropy field set and can be brute-forced by anyone who already holds the
database. They are not a substitute for encryption at rest.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence
import uuid

from .core import (
    ELIGIBILITY_RULE_VERSION, CandidateProfile, Decision, EligibilityReport, JobListing,
    RequirementResult,
)

FINGERPRINT_VERSION = "fp1"
MAX_AUDIT_TEXT = 4000
MAX_DECISION_ID = 128
MAX_RULE_VERSION = 64
MAX_REQUIREMENTS = 64
MAX_AUDIT_TRAIL_CHARS = 32000

# Only fields that can change the hard-eligibility outcome are fingerprinted.
# Skills, locations and role preferences affect relevance, never eligibility.
_PROFILE_INPUT_FIELDS = (
    "candidate_country", "degree_discipline", "study_status", "graduation_year",
    "experience_years", "work_authorization",
)
_JOB_INPUT_FIELDS = (
    "availability_status", "provenance_note", "eligibility_scope", "eligible_countries",
    "allowed_work_authorizations", "allowed_degree_disciplines", "allowed_study_statuses",
    "allowed_graduation_years", "minimum_experience_years", "maximum_experience_years",
)

_REQUIREMENT_FIELDS = {"requirement", "decision", "explanation", "evidence"}


@dataclass(frozen=True)
class EligibilityDecision:
    """One recorded evaluation; historical records are never rewritten."""

    decision_id: str
    listing_id: str
    evaluated_at: str
    rule_version: str
    outcome: Decision
    profile_fingerprint: str | None
    job_fingerprint: str
    requirements: tuple[RequirementResult, ...]


def _json_scalar(value: Any) -> Any:
    if isinstance(value, (frozenset, set)):
        return sorted(_json_scalar(item) for item in value)
    if isinstance(value, (tuple, list)):
        return [_json_scalar(item) for item in value]
    if hasattr(value, "value") and isinstance(value.value, str):  # enums
        return value.value
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{FINGERPRINT_VERSION}:{digest}"


def is_fingerprint(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    prefix, separator, digest = value.partition(":")
    return (
        separator == ":"
        and prefix == FINGERPRINT_VERSION
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )


def profile_fingerprint(profile: CandidateProfile | None) -> str | None:
    """Fingerprint the eligibility-relevant candidate facts, or None when absent."""
    if profile is None:
        return None
    return _fingerprint({name: _json_scalar(getattr(profile, name)) for name in _PROFILE_INPUT_FIELDS})


def job_fingerprint(job: JobListing) -> str:
    """Fingerprint the eligibility-relevant listing facts."""
    return _fingerprint({name: _json_scalar(getattr(job, name)) for name in _JOB_INPUT_FIELDS})


def build_decision(
    profile: CandidateProfile,
    job: JobListing,
    report: EligibilityReport,
    *,
    decision_id: str | None = None,
    evaluated_at: str | None = None,
) -> EligibilityDecision:
    """Create a record for one explicit evaluation without writing it anywhere."""
    return EligibilityDecision(
        decision_id=decision_id or str(uuid.uuid4()),
        listing_id=job.listing_id,
        evaluated_at=evaluated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        rule_version=ELIGIBILITY_RULE_VERSION,
        outcome=report.decision,
        profile_fingerprint=profile_fingerprint(profile),
        job_fingerprint=job_fingerprint(job),
        requirements=tuple(report.requirements),
    )


def inputs_changed(
    decision: EligibilityDecision,
    profile: CandidateProfile | None,
    job: JobListing,
) -> tuple[str, ...]:
    """Return which inputs differ from the ones the decision was recorded against."""
    changed: list[str] = []
    if decision.profile_fingerprint != profile_fingerprint(profile):
        changed.append("profile")
    if decision.job_fingerprint != job_fingerprint(job):
        changed.append("job")
    return tuple(changed)


def requirement_records(requirements: Sequence[RequirementResult]) -> list[dict[str, Any]]:
    """Render the requirement trail for JSON storage without candidate values."""
    return [
        {
            "requirement": item.requirement,
            "decision": item.decision.value,
            "explanation": item.explanation,
            "evidence": item.evidence,
        }
        for item in requirements
    ]


def _audit_text(value: Any, where: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{where} must be text.")
    if not value.strip():
        raise ValueError(f"{where} must not be blank.")
    if len(value) > MAX_AUDIT_TEXT:
        raise ValueError(f"{where} is longer than the {MAX_AUDIT_TEXT}-character limit.")
    return value


def requirements_from_records(
    data: Any, *, context: str = "decision"
) -> tuple[RequirementResult, ...]:
    """Validate a stored requirement trail; any malformed record is refused."""
    if not isinstance(data, (list, tuple)):
        raise ValueError(f"{context}: requirements must be a list.")
    if not data:
        raise ValueError(f"{context}: requirements must not be empty.")
    results: list[RequirementResult] = []
    for index, raw in enumerate(data):
        where = f"{context}, requirement {index + 1}"
        if not isinstance(raw, Mapping):
            raise ValueError(f"{where} must be an object.")
        unknown = sorted(set(raw) - _REQUIREMENT_FIELDS)
        if unknown:
            raise ValueError(f"{where} contains unsupported field(s): {', '.join(unknown)}.")
        requirement = _audit_text(raw.get("requirement"), f"{where} requirement")
        explanation = _audit_text(raw.get("explanation"), f"{where} explanation")
        value = raw.get("decision")
        if not isinstance(value, str):
            raise ValueError(f"{where} decision must be a decision string.")
        try:
            decision = Decision(value)
        except ValueError as exc:
            raise ValueError(f"{where} has an unknown decision: {value!r}.") from exc
        evidence = _audit_text(raw.get("evidence"), f"{where} evidence", allow_none=True)
        results.append(
            RequirementResult(
                requirement=requirement,
                decision=decision,
                explanation=explanation,
                evidence=evidence,
            )
        )
    return tuple(results)


def requirements_to_json(requirements: Sequence[RequirementResult]) -> str:
    return _canonical_json(requirement_records(requirements))


def requirements_from_json(text: str, *, context: str = "decision") -> tuple[RequirementResult, ...]:
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{context}: requirements are not valid JSON.") from exc
    return requirements_from_records(data, context=context)


def validate_decision(
    decision: EligibilityDecision, *, context: str = "decision"
) -> EligibilityDecision:
    """Validate a decision before it is written; never persists a partial record."""
    if not isinstance(decision, EligibilityDecision):
        raise ValueError(f"{context}: expected an EligibilityDecision value.")
    if not isinstance(decision.decision_id, str) or not decision.decision_id.strip():
        raise ValueError(f"{context}: decision_id must be non-empty text.")
    if len(decision.decision_id) > MAX_DECISION_ID:
        raise ValueError(f"{context}: decision_id exceeds {MAX_DECISION_ID} characters.")
    if not isinstance(decision.listing_id, str) or not decision.listing_id.strip():
        raise ValueError(f"{context}: listing_id must be non-empty text.")
    if not isinstance(decision.rule_version, str) or not decision.rule_version.strip():
        raise ValueError(f"{context}: rule_version must be non-empty text.")
    if len(decision.rule_version) > MAX_RULE_VERSION:
        raise ValueError(f"{context}: rule_version exceeds {MAX_RULE_VERSION} characters.")
    if not isinstance(decision.outcome, Decision):
        raise ValueError(f"{context}: outcome must be a Decision value.")
    if not isinstance(decision.evaluated_at, str) or not decision.evaluated_at.strip():
        raise ValueError(f"{context}: evaluated_at must be a non-empty ISO-8601 timestamp.")
    try:
        datetime.fromisoformat(decision.evaluated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{context}: evaluated_at is not a valid ISO-8601 timestamp: {decision.evaluated_at!r}."
        ) from exc
    if decision.profile_fingerprint is not None and not is_fingerprint(decision.profile_fingerprint):
        raise ValueError(f"{context}: profile_fingerprint is not a recognised versioned fingerprint.")
    if not is_fingerprint(decision.job_fingerprint):
        raise ValueError(f"{context}: job_fingerprint is not a recognised versioned fingerprint.")
    if len(decision.requirements) > MAX_REQUIREMENTS:
        raise ValueError(
            f"{context}: the requirement trail has more than {MAX_REQUIREMENTS} entries."
        )
    try:
        records = requirement_records(decision.requirements)
    except (TypeError, AttributeError) as exc:
        raise ValueError(f"{context}: the requirement trail is malformed: {exc}") from exc
    requirements_from_records(records, context=context)
    size = len(_canonical_json(records))
    if size > MAX_AUDIT_TRAIL_CHARS:
        raise ValueError(
            f"{context}: the requirement trail is {size} characters, above the "
            f"{MAX_AUDIT_TRAIL_CHARS}-character limit."
        )
    return decision
