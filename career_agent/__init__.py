"""AI Career Agent deterministic local domain core."""
__version__ = "0.1.0"

from .store import CareerStore, StaleApplicationError
from .export import (
    FORMAT_VERSION, ExportFormatError, RestoreError, build_export_payload,
    load_export, restore_export, restore_export_file, restore_from_backup,
    validate_export, write_export,
)
from .preparation import (
    ApplicationDraft, ChecklistItem, DraftField, Readiness, ReadinessReport,
    assess_readiness, build_application_draft,
)
from .core import (
    ApplicationEvent, ApplicationStatus, ApplicationTracker, Availability, CandidateProfile,
    Decision, EligibilityReport, JobListing, RequirementResult,
    REAPPLICATION_ALLOWED_FROM, TERMINAL_STATUSES, allowed_transitions,
    canonicalize_url, deduplicate_listings, duplicate_key,
    evaluate_eligibility, job_to_public_dict, score_relevance,
)

__all__ = [
    "__version__",
    "CareerStore", "StaleApplicationError",
    "FORMAT_VERSION", "ExportFormatError", "RestoreError", "build_export_payload",
    "load_export", "restore_export", "restore_export_file", "restore_from_backup",
    "validate_export", "write_export",
    "ApplicationEvent", "ApplicationStatus", "ApplicationTracker", "Availability", "CandidateProfile",
    "Decision", "EligibilityReport", "JobListing", "RequirementResult",
    "REAPPLICATION_ALLOWED_FROM", "TERMINAL_STATUSES", "allowed_transitions",
    "canonicalize_url", "deduplicate_listings", "duplicate_key",
    "evaluate_eligibility", "job_to_public_dict", "score_relevance",
    "ApplicationDraft", "ChecklistItem", "DraftField", "Readiness", "ReadinessReport",
    "assess_readiness", "build_application_draft",
]
