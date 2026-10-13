# MVP Scope and Data Contract

**Status:** Authoritative scope for the first usable local alpha; live source gate remains NOT PASSED  
**Last updated:** 2026-10-14  
**Repository:** https://github.com/rajaryan1111/ai-career-agent

This file resolves conflicting scope statements in earlier planning. If an older document describes resume parsing, live discovery, cloud execution, or auto-submission as part of the first local alpha, this contract takes precedence until the canonical documents are updated.

## 1. Product scope: vision versus first release

### Long-term product
AI Career Agent is intended for candidates across industries, experience levels, geographies, and job types. It uses an industry-agnostic core plus configurable occupation-specific profiles and evaluation data. Design/creative, VLSI/embedded, mechanical, civil, software/data, business, finance, marketing, sales, operations, and research are examples—not a claim of launch-time coverage.

### First usable local alpha
Deliver one complete offline workflow before adding connectors or expensive infrastructure:

1. Enter and save a candidate profile locally.
2. Enter a job manually, keeping the source listing URL separate from an employer application URL that is only supplied when verified.
3. Evaluate hard eligibility with explicit PASS / FAIL / UNKNOWN results and explanations.
4. Show explainable skill overlap separately from eligibility.
5. Allow shortlisting only when all evaluated mandatory criteria explicitly PASS.
6. Track application status with guarded transitions and evidence required for confirmation.
7. Export local records to a user-selected JSON file and delete profile/job records explicitly.
8. Restart the app and retain saved state.

The current UI uses Python/Tkinter, the Python domain core, and SQLite. Launch with `python -m career_agent` using Python 3.10+ with Tkinter available. This is a local alpha, not a packaged or production-certified release.

## 2. Explicitly deferred or gated

| Capability | Decision | Gate to enable |
|---|---|---|
| Local PDF/DOCX resume parsing | Next local-only increment, not a blocker for the first workflow | Parser fixtures, field provenance/confidence, manual review, accuracy evaluation, no external upload |
| Automated job discovery | Disabled | Source-specific permission evidence plus source-quality gate and attribution/cache/rate-limit design |
| Remote worker and laptop-off execution | Deferred | Cost and privacy review, explicit data-transfer consent, health/retry/idempotency tests, real laptop-off acceptance test |
| External LLM or cloud processing | Disabled by default | Per-feature disclosure, minimum-data design, explicit opt-in, cost limits and provider review |
| Application autofill/submission | Disabled | Source/employer permission, truthful verified facts, source-specific adapter, duplicate protection, recovery, pilot evidence, scoped revocable policy |
| Email/calendar integrations | Deferred | Least-privilege permissions, explicit consent, revocation and test coverage |
| OCR for scanned resumes | Optional later enhancement | Local capability and quality tests; no mandatory paid service |

A standing user policy can reduce repeated prompts only inside its explicit, revocable scope and only where the source/employer permits the action. It never authorizes guessing, restricted assessments, sensitive declarations, CAPTCHA/OTP bypass, or retrying an ambiguous submission without checking for prior success.

## 3. Candidate profile contract

Store only explicitly supplied or user-reviewed facts. Missing values remain unknown.

- Identity/contact: optional, added only when needed by a future workflow.
- Country and work authorization: separate concepts; do not infer one from the other.
- Education: degree/discipline, study status, graduation year; do not fuzzy-assume degree equivalence.
- Experience: numeric years only when the user supplies/reviews the value.
- Skills: normalized labels with no inferred proficiency claims.
- Preferences: target role types, locations, work modes, exclusions, compensation preferences and occupation-specific criteria.
- Resume extraction: future extracted values must carry review/uncertainty state and cannot silently become verified facts.

Do not put personal profiles, resumes, tokens, credentials, local databases, or real candidate data in source control.

## 4. Job listing contract

Each job record must preserve:

- Stable local listing ID and source identity.
- Employer and role title.
- Source listing URL (where the listing was found).
- Nullable employer application URL, set only when that exact destination has been verified.
- Canonical requisition ID when explicitly known.
- Availability state: open, closed, expired, unknown, not-a-listing, or source-review.
- Retrieval/check timestamp and source provenance when the record came from an adapter.
- Work mode, role type, location text and explicit eligibility fields where known.
- Source permission state separately from technical availability.

A careers index is not a direct application URL. “Remote” is not proof of worldwide eligibility. A listing's disappearance from a partial feed is not proof of closure. Duplicate grouping must preserve source provenance and separate application destinations.

## 5. Eligibility and ranking contract

Hard eligibility is three-valued:

- **PASS:** every applicable mandatory requirement has explicit supporting evidence and passes.
- **FAIL:** at least one mandatory requirement is explicitly violated.
- **UNKNOWN:** at least one mandatory requirement cannot be evaluated due to missing, ambiguous, stale, or conflicting evidence, and no explicit failure already determines the result.

A known failure wins over unknowns for the overall decision. Unknown never qualifies for an eligible shortlist. Ranking/relevance never overrides hard eligibility. Relevance is an explanation of overlap, not a probability of hiring.

For restricted hiring countries, compare the candidate's country against an explicit allowed-country list. For worldwide roles, require explicit source evidence and still check any other work authorization or residency criteria that apply.

## 6. Application state contract

Allowed statuses in the current domain model include discovered, shortlisted, prepared, awaiting_user, submission_attempted, submitted_unverified, confirmed, failed, unknown_status, response_received, interview, rejected_by_employer and withdrawn.

- Status changes must follow the transition state machine.
- Confirmation requires evidence; a button click, HTTP success alone, or attempted submission is not automatically proof that an application was accepted by the destination.
- A timeout or interrupted flow can mean unknown status. Check for prior success before retrying.
- Do not infer a rejection or closure from a missing record in a partial source run.
- Current alpha tracks manually entered records and does not submit applications.

## 7. Source-quality gate

**Current decision: NOT PASSED. Live discovery adapters remain disabled.**

Research snapshots in the repository have conflicting historical counts. Until the audit CSV and the assessment report are reconciled by a repeatable audit script with a recorded input SHA, timestamp, exact denominator, and generated status counts, no one count should be treated as authoritative.

The proposed source go/no-go targets remain proposed, not achieved:

- Complete a 50-record human-reviewed sample (25 India-focused and 25 international-remote) without treating the roster as 50 open/eligible jobs.
- Demonstrate at least 20 unique, relevant, currently available vacancies.
- Measure employer application-route outcomes with an explicit denominator and achieve the proposed 90% valid-direct-route threshold, or document a justified revision.
- Demonstrate zero false worldwide-eligibility claims and zero mandatory unknowns passing eligibility.
- Document exact permission, attribution, cache/reuse, rate-limit, and permitted-use boundaries for every enabled adapter.
- Report source errors and partial results separately from valid empty results.
- Preserve source-listing URLs separately from verified employer application URLs.

A technically reachable endpoint, public listing, attribution statement, or free API does not automatically authorize all forms of automated gathering or downstream reuse. A provider remains disabled if its applicable terms conflict or are unclear.

## 8. Privacy, security and recovery

- Default storage is local in a per-user application-data directory.
- The app performs no network calls in the local alpha.
- Export is explicit and user-selected; warn that exports may contain personal data.
- Delete actions require confirmation and remove the corresponding local records.
- Do not claim database encryption, backup/restore, automatic updates, secure credential storage, or packaged installer support until implemented and tested.
- Do not store credentials in the repo or logs.
- Any future remote worker must disclose data fields transferred, purpose, retention, location/provider and cost before opt-in. A local desktop scheduler cannot run while the computer is powered off or asleep.

## 9. First-alpha acceptance checklist

- [ ] Profile fields persist across application restart.
- [ ] Invalid numeric fields produce a useful error and do not save malformed values.
- [ ] A manual job persists and preserves separate source/apply URLs.
- [ ] Missing mandatory eligibility data yields UNKNOWN, not PASS.
- [ ] Explicit country/degree/status/cohort violations yield FAIL.
- [ ] Only an explicit PASS can be shortlisted.
- [ ] Invalid tracker transitions are rejected.
- [ ] CONFIRMED without evidence is rejected.
- [ ] Export produces valid JSON with an explicit privacy warning.
- [ ] Delete profile/job removes the saved record and associated tracker entry.
- [ ] GUI smoke tests pass on each OS that is advertised as supported.
- [ ] No network request is made during local alpha workflows.
- [ ] CI unit tests and syntax compilation pass on supported Python versions.

## 10. Implementation order

1. Local desktop vertical slice (profile → manual job → eligibility → shortlist → tracker → export/delete).
2. Harden store migrations, backup/recovery, input validation and test coverage.
3. Add local PDF/DOCX parsing with reviewed field provenance.
4. Reconcile source audit metrics from a reproducible CSV audit.
5. Re-open source permission/quality gate; implement only the first adapter whose gate passes.
6. Validate occupation-specific matching across representative job families.
7. Design and test optional remote worker for laptop-off execution.
8. Add source-specific application automation only after separate permission and reliability gates.
9. Add email/interview lifecycle integrations under least privilege.

## Change note — 2026-10-14

This contract resolves the former contradiction where the PRD/phases required resume parsing in the first milestone while the detailed MVP contract excluded it. The first local workflow is now manual-profile/manual-job and fully offline; resume parsing is a follow-on increment. It also distinguishes the cross-industry product vision from launch-time validation coverage and distinguishes future standing authorization from current manual submission.
