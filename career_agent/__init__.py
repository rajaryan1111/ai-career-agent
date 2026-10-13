"""AI Career Agent deterministic local domain core."""
from .store import CareerStore
from .core import (
    ApplicationStatus, ApplicationTracker, Availability, CandidateProfile,
    Decision, EligibilityReport, JobListing, RequirementResult,
    canonicalize_url, deduplicate_listings, duplicate_key,
    evaluate_eligibility, job_to_public_dict, score_relevance,
)

__all__ = [
    "CareerStore", "ApplicationStatus", "ApplicationTracker", "Availability", "CandidateProfile",
    "Decision", "EligibilityReport", "JobListing", "RequirementResult",
    "canonicalize_url", "deduplicate_listings", "duplicate_key",
    "evaluate_eligibility", "job_to_public_dict", "score_relevance",
]
