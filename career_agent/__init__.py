"""AI Career Agent deterministic local domain core."""
#: Single source of truth for the version this checkout reports. Kept as a literal so
#: ``python -m career_agent --version`` works from a source checkout with no packaging metadata
#: and no third-party tooling. A future packaged build may read the same value from the
#: distribution metadata; until then this literal is the honest answer for both.
__version__ = "0.1.0"

from .core import (
    INITIAL_APPLICATION_STATUS,
    ApplicationStatus,
    ApplicationTracker,
    Availability,
    CandidateProfile,
    Decision,
    EligibilityReport,
    JobListing,
    RequirementResult,
    canonicalize_url,
    deduplicate_listings,
    duplicate_key,
    evaluate_eligibility,
    is_allowed_tracker_transition,
    is_substantive_confirmation_evidence,
    job_to_public_dict,
    require_confirmation_evidence,
    score_relevance,
    selectable_tracker_statuses,
)
from .store import CareerStore, StoredRecordError, TrackerStatusError

__all__ = [
    "INITIAL_APPLICATION_STATUS",
    "ApplicationStatus",
    "ApplicationTracker",
    "Availability",
    "CandidateProfile",
    "CareerStore",
    "Decision",
    "EligibilityReport",
    "JobListing",
    "RequirementResult",
    "StoredRecordError",
    "TrackerStatusError",
    "__version__",
    "canonicalize_url",
    "deduplicate_listings",
    "duplicate_key",
    "evaluate_eligibility",
    "is_allowed_tracker_transition",
    "is_substantive_confirmation_evidence",
    "job_to_public_dict",
    "require_confirmation_evidence",
    "score_relevance",
    "selectable_tracker_statuses",
]
