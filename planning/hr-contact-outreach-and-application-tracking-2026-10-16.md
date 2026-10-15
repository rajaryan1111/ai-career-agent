# HR Contact Import, Outreach, and Application Tracking — Planning

**Status:** Planning only. No new implementation or external actions are authorized by this document.
**Current project gate:** `SOURCE_QUALITY_GATE_PASSED = False`; `enabled_discovery_sources() == ()`. Discovery and submission remain disabled until their separate gates pass.

## Goal

Use a reviewed HR-contact dataset to help the candidate find relevant internships/jobs, prepare tailored outreach and application materials, and keep a truthful history so the same company, role, contact, or application is not repeatedly contacted/applied to by mistake.

## Phase 0 — Safe data import and review

1. Import CSV locally; do not commit contact names/emails to a public repository or send them to third-party services by default.
2. Show source/provenance, import timestamp, source row IDs, company labels, and review flags.
3. Validate CSV schema and encoding; reject malformed rows with actionable diagnostics.
4. Normalize email for comparison (trim + case-fold) while preserving the original value for review.
5. Keep uncertain company associations as conflicts; never silently rewrite them.
6. Support preview, row-level selection, export of rejected rows, and idempotent re-import.
7. Treat syntax checks as heuristics, not mailbox verification.
8. Track user-supplied source, collection date, purpose, and any known permission/consent evidence; unknown means unverified.

## Phase 1 — Matching and deduplication

- Match only against job/internship listings from permitted sources after the source-quality gate passes.
- Rank relevance against the candidate's confirmed profile, skills, location/work-mode preferences, eligibility, and graduation details. Explain why each match was suggested.
- Canonicalize URLs carefully; retain original URLs and source IDs.
- Create stable identities for a listing/application using normalized employer, role/title, location, canonical URL, and source identifiers where available.
- Detect possible duplicates before creating a new application. Show likely matches for human resolution; do not merge uncertain records silently.
- Re-imports and repeated scans must not create duplicate contacts, listings, outreach drafts, or applications.

## Phase 2 — Application and outreach ledger

For each opportunity/contact, persist a truthful state and event history:
- discovered → reviewed → eligible/ineligible/needs-information → prepared → awaiting approval → submitted/contacted (only with verifiable evidence) → response received / follow-up due / closed.
- Record company, role, location, source URL, contact, date, channel, status, last action, next follow-up date, evidence/reference, and reason for skipping.
- Use a unique application key plus database constraints/idempotency checks to prevent duplicate submissions.
- Before any submission, check the ledger for an existing active or completed application to the same employer/role; require human resolution when uncertain.
- Before outreach, check recipient normalization, company/contact conflicts, previous sends, bounced addresses, and suppression/opt-out lists.
- Provide dashboard and CSV export: applied/contacted, pending approval, skipped/duplicate, responses, follow-ups due, and failures. Make it easy to see exactly where an application was submitted and when.

## Phase 3 — Draft generation

- Generate a tailored résumé variant and cover letter/email draft from confirmed candidate facts and the specific job description.
- Never invent experience, qualifications, achievements, contact identities, or job requirements.
- Show the job description, matched evidence, missing requirements, recipient, attachments, and full message before approval.
- Keep drafts local by default; minimize retained personal data.

## Phase 4 — Approval and sending/submission controls

- No automatic external email or application submission while any required source, consent, eligibility, or submission gate is blocked.
- Initial release should create drafts and a review queue only.
- Require explicit user approval for each recipient/message and each application submission, with a final preview of recipient, employer, role, résumé/attachments, and data to be transmitted.
- Do not bypass CAPTCHA, OTP, access controls, anti-bot controls, or source terms; do not use stealth/proxy/session-cookie evasion.
- Use official APIs or explicitly permitted workflows only. Respect rate limits and stop on errors.
- Support global pause, per-contact suppression, opt-out, bounce handling, and a do-not-contact list that survives re-imports.
- Never claim an email/application was sent/submitted without provider confirmation or equivalent verifiable evidence.
- Log idempotency key, action timestamp, approval event, provider/application reference, result, and error without storing secrets.
- Ask for explicit informed consent before sending résumé/profile data to an external provider; disclose exactly what data is shared.

## Phase 5 — Reliability, security, and tests

- Add migration-safe schema changes and rollback/recovery notes; do not run destructive tests against real user data.
- Test duplicate imports, case/whitespace variations, same role on different URLs, different roles at the same company, uncertain duplicate resolution, retry after timeout, provider success with lost response, opt-out persistence, and partial failures.
- Test that a failed or refused action does not advance the application state.
- Test no send/submit path is reachable while gates are false.
- Keep personal contact data out of logs, fixtures, screenshots, public reports, and test output.
- Document backup, deletion, retention, export, and local file permissions. Permissions alone are not encryption.
- Add a visible activity timeline and an audit report of all actions and evidence.

## Acceptance criteria

1. Import preview and validation work offline with no network requests.
2. Duplicate imports are idempotent and conflicts are visible.
3. Every opportunity has a stable identity and a clear status/history.
4. A second attempt at an already-submitted application is blocked or sent to manual duplicate review.
5. Contact suppression/opt-out is checked before every outreach action.
6. Drafts can be prepared without sending or submitting anything.
7. With source/submission gates closed, no discovery network request, email send, or application submission occurs.
8. Every real external action has an explicit approval record and verifiable outcome.
9. Reports show where, when, and for which role applications/outreach happened.
10. Unit tests, full suite, static checks, and CI pass; no unsupported manual acceptance is claimed.

## Out of scope until separately approved

- Bulk email campaigns, auto-send, auto-submit, scraping, or unapproved source adapters.
- Uploading the raw HR contact list to this public GitHub repository.
- Any modification to `main` or merging PR #2 as part of this planning task.
