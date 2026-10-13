# MVP Scope and Data Contract — 2026-10-14

## Status

Pre-implementation design only. This document defines the smallest useful candidate-facing workflow and data contract. It does not authorize production code, live API queries, source ingestion, candidate-data transfer, autofill or application submission. The overall source-quality gate remains NOT PASSED until the documented evidence requirements are met.

## Product objective

Help an India-based BTech ECE undergraduate/fresher discover relevant AI/ML internships and entry-level roles, understand why each role matches or fails eligibility checks, open a traceable application destination, and track application progress locally. Do not promise placement, infer legal work eligibility, or apply on the candidate's behalf.

## MVP user flow

1. Candidate enters a minimal profile: degree/discipline, current study status, expected graduation date/year, location/country, work authorization only if the candidate chooses to provide it, skills, experience/projects, work-mode preference, availability, compensation floor, and preferred role types.
2. Candidate explicitly chooses which profile fields may be used for matching. Resume upload is out of scope for the first prototype; if introduced later, it requires a separate privacy/data-retention decision.
3. The app obtains listings only from approved read-only source adapters, stores source provenance and observation timestamps, and normalizes the source fields.
4. Deduplication groups identical requisitions and cross-postings. A shared careers page is not treated as a unique vacancy without evidence that the requisitions differ.
5. Eligibility rules run before ranking. Hard requirements are three-valued: `pass`, `fail`, or `unknown`. Unknown must never be silently treated as pass. Candidate can inspect the evidence behind every hard requirement.
6. Results show role, employer, source, original source URL, direct employer application URL only when verified, location/work mode, compensation and period if provided, posted/checked dates, requirement evidence, uncertainty, and an explanation of fit.
7. Candidate opens the employer application destination manually and decides whether to apply. The app can store a local status (saved, considering, applied, interview, rejected, withdrawn) and candidate-entered notes. No application data is sent to employers by the app.
8. Candidate can export or delete the locally stored profile and tracker. Any cloud account/sync is out of scope for MVP unless separately reviewed.

## Minimum data contract

### CandidateProfile (local only)
- `profile_id`: locally generated opaque ID.
- `degree_level`, `degree_discipline`, `study_status`, `graduation_year`.
- `candidate_country`, `preferred_locations`, `work_mode_preferences`.
- `work_authorization`: optional; explicit values only, otherwise `unknown`.
- `skills`, `projects_summary`, `experience_level`, `availability_hours`, `role_types`.
- `minimum_compensation`: optional with currency and period; absence means no stated floor, not zero.
- `consent_settings`, `created_at`, `updated_at`.
- No date of birth, government ID, family details, passwords, or employer-form answers are needed for matching.

### JobListing
- `listing_id`: internal stable ID.
- `source_id`, `source_listing_id`, `source_listing_url`, `source_name`, `source_terms_reviewed_at`.
- `employer_name`, `role_title`, `canonical_requisition_id` when supported by evidence.
- `employer_apply_url`: nullable; populate only after direct destination is verified. Never alias it to `source_listing_url`.
- `location_text`, `work_mode`, `eligible_countries`, `work_authorization_notes`.
- `role_family`, `seniority`, `employment_type`, `degree_requirements`, `graduation_cohort`, `experience_requirements`, `skills_required`.
- `compensation_min`, `compensation_max`, `compensation_currency`, `compensation_period`; preserve missing/unclear separately from zero.
- `posted_at`, `deadline_at`, `first_seen_at`, `last_seen_at`, `last_verified_at`.
- `availability_status`: `open`, `closed`, `unknown`, `expired`, `not_a_listing`, or `source_review`.
- `eligibility_evidence`: requirement-level evidence references and `pass`/`fail`/`unknown` outcomes.
- `provenance`, `duplicate_group_id`, `content_hash`, `last_error`.

### MatchExplanation
- `listing_id`, `profile_version`, `computed_at`.
- `hard_requirement_results`: requirement ID, result (`pass`/`fail`/`unknown`), evidence, explanation.
- `rank_score` only among candidates that pass all configured mandatory requirements; if any mandatory result is unknown, display a review-needed state rather than a definitive eligible rank.
- `skill_overlap`, `skill_gaps`, `location_fit`, `work_mode_fit`, `compensation_fit` with transparent evidence.
- Never fabricate a numeric score as a probability of being hired.

### ApplicationTracker (local only)
- `tracker_id`, `listing_id`, `status`, `saved_at`, `applied_at` (candidate-entered), `next_action_at`, `notes`.
- Do not claim `applied` unless the candidate explicitly records that they submitted it.
- No automated form fill, email, message, or submission in MVP.

## Status semantics

- `open`: supported by current source evidence, with observation time.
- `closed`: explicit closure evidence from a reliable source.
- `expired`: explicit deadline/expiry evidence; not inferred from absence alone.
- `unknown`: status cannot be confirmed.
- `not_a_listing`: source record is not a vacancy.
- `source_review`: terms or source identity needs human review before use.
- A listing disappearing from a seven-day feed is not proof that it closed.

## Security, privacy and reliability requirements

- Read-only source adapters; source-specific allowlist and request-rate limits.
- No source calls with candidate-specific profile data; no candidate profile/resume sent to job sources.
- Treat all source text and HTML as untrusted. Sanitize rendered HTML, escape text, reject scripts and remote embeds.
- Keep API keys out of the repository and browser. MVP's Jobicy public endpoint needs no key; paid endpoints are out of scope.
- Record source terms/version review, request time, response outcome, parsing errors and provenance.
- Respect rate limits; bounded retries with backoff; preserve last known data but do not present stale data as newly verified.
- Local-first storage and clear delete/export controls. No analytics/telemetry containing profile or resume data by default.
- Keep source listing URL and employer application URL distinct in UI and metrics.

## Acceptance tests before first prototype is called usable

1. At least 50 research-sample records (25 India-focused, 25 international-remote) are deduplicated and evidence-tagged; this is a validation target, not a claim that the current audit has met it.
2. Direct employer application-link validity is measured with explicit success/failure/unknown outcomes and a documented denominator; target at least 90% among links claimed to be direct.
3. Zero unsupported worldwide-eligibility claims in the audited sample.
4. Zero cases where unknown mandatory eligibility is rendered as pass.
5. Duplicate requisitions count once; shared-page roles remain unresolved until differentiated.
6. Closed, expired, unknown and missing-from-feed states are tested independently.
7. Source attribution and canonical URL are preserved for every source listing.
8. Candidate profile remains local, deletable and not transmitted to source providers.
9. Manual application workflow never submits without candidate action.
10. Source terms permit the exact ingestion and display behavior used by each adapter.

## Out of scope until a separate decision

- Paid source APIs or any spend.
- Scraping employer career sites, bypassing access controls, or proxy rotation to evade blocking.
- Resume upload/AI parsing, cloud sync, candidate accounts, bulk emailing, browser automation, form autofill, or application submission.
- Claims of job-market coverage, precision/recall, eligibility, or hiring probability without measured evidence.

## Go/no-go checkpoint

Do not start production source integration until the source-permission matrix, 50-record validation sample, link-quality metric, eligibility false-claim audit, and product-flow review have been approved. Once they pass, implement one approved read-only adapter first, with the Jobicy public API as the current leading candidate, and validate end-to-end before adding another source.
