"""AI Career Agent deterministic local domain core."""
from .store import CareerStore, StaleApplicationError
from .core import (
    ApplicationEvent, ApplicationStatus, ApplicationTracker, Availability, CandidateProfile,
    Decision, EligibilityReport, JobListing, RequirementResult,
    REAPPLICATION_ALLOWED_FROM, TERMINAL_STATUSES, allowed_transitions,
    canonicalize_url, deduplicate_listings, duplicate_key,
    evaluate_eligibility, job_to_public_dict, score_relevance,
)

__all__ = [
    "CareerStore", "StaleApplicationError",
    "ApplicationEvent", "ApplicationStatus", "ApplicationTracker", "Availability", "CandidateProfile",
    "Decision", "EligibilityReport", "JobListing", "RequirementResult",
    "REAPPLICATION_ALLOWED_FROM", "TERMINAL_STATUSES", "allowed_transitions",
    "canonicalize_url", "deduplicate_listings", "duplicate_key",
    "evaluate_eligibility", "job_to_public_dict", "score_relevance",
]
