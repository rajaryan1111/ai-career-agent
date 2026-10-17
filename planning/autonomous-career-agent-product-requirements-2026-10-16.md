# Autonomous Career Agent — Product Requirements

**Date:** 2026-10-16  
**Status:** Product direction / planning only; these requirements are not implemented merely by this document.

## Product goal

Build a local-first personal career agent whose normal starting point is the user's resume. The user should not have to manually search every job board, tailor every application, or remember every follow-up. After an explicit one-time setup of profile, boundaries, account integrations, and operating rules, the agent should run a bounded autonomous workflow without asking for per-application approval for routine, policy-compliant actions.

The product must be truthful about what is implemented, what is connected, what was attempted, and what was actually submitted or sent. Never represent a prepared draft as a sent email or an opened job listing as a completed application.

## Desired end-to-end workflow

1. **Resume understanding and profile setup**
   - Import PDF/DOCX/text locally where supported.
   - Extract skills, education, projects, work history, dates, links, location, graduation year, and relevant evidence.
   - Show extracted facts for initial confirmation; ask only for missing fields that are required for matching or applications.
   - Store source evidence for profile claims. Never invent qualifications, experience, grades, work authorization, answers, or achievements.

2. **Career preferences and global authorization**
   - Configure target roles (including AI/ML Engineer, Applied AI Engineer, AI Engineer, Forward Deployed Engineer, and relevant internships), location/remote preferences, compensation, work type, graduation/eligibility rules, sponsorship/work authorization, and exclusions.
   - Establish a clear global authorization policy once during setup: which sources may be checked, which actions may be performed automatically, what data may be shared, daily limits, email account/sender identity, attachment rules, and stop conditions.
   - Do not require a fresh approval for every routine application that fits the saved policy and uses supported, permitted workflows. Keep controls to pause, revoke, narrow, or review that authorization.

3. **Scheduled discovery — twice daily**
   - Run configurable morning/evening discovery jobs, with timezone, last-run status, retries, and a visible next-run time.
   - Search only sources with a permitted and technically supported integration. Prioritize official company career pages and supported ATS/public feeds; evaluate LinkedIn, Unstop, Internshala, Naukri.com, and other platforms individually rather than claiming universal coverage.
   - Record source URL, company, role, location, date found, deadline if known, source freshness, eligibility evidence, and application route.
   - Respect platform terms, rate limits, robots/access controls, privacy requirements, and account restrictions. No CAPTCHA/OTP bypass, anti-bot evasion, or unsupported scraping.

4. **Fit, eligibility, and truthful application preparation**
   - Score role fit using explainable evidence from the resume and profile; distinguish required qualifications from preferences and unknowns.
   - Filter out expired, duplicate, clearly ineligible, suspicious, or unverifiable postings.
   - Prepare a role-specific resume/cover letter and screening responses using only verified profile facts. Preserve the original resume and version every tailored artifact.
   - Never guess answers to legal, demographic, work-authorization, conflict-of-interest, salary, disability, or other sensitive/attestation questions. If a required answer is unknown or an attestation cannot be truthfully supported, stop that application and notify the user.

5. **Autonomous application execution**
   - For a job that meets the saved policy, passes eligibility and safety checks, has no unresolved required fields, and has a supported, permitted submission path, submit without a per-job confirmation.
   - Use official APIs, supported integrations, or platform-permitted workflows. A platform that prohibits automation or requires an interactive human step must not be bypassed; mark it as blocked/needs user action and provide the exact next step.
   - Use idempotency and a persistent application ledger to avoid repeat submissions. Treat uncertain submission outcomes as submission_unknown until verified; do not retry blindly.
   - Record an application as submitted only with concrete evidence (confirmation page/ID, email receipt, or supported API response).

6. **HR and company outreach**
   - Import the user's HR/company contact list privately, preserve source/provenance, and show ambiguous records for review.
   - Normalize emails for comparison, detect duplicate email groups, conflicting names/company labels, malformed addresses, missing names, suppression/opt-out, prior sends, and prior replies.
   - Send personalized internship outreach from the explicitly connected and authorized email account, with the appropriate resume attachment, only to contacts that pass configured eligibility, provenance, suppression, and duplicate checks.
   - Enforce one-send-per-contact/campaign policy, cross-run deduplication, bounce handling, rate limits, opt-out suppression, and a complete audit trail. Do not send to uncertain or suppressed contacts. Never expose contact lists in the public repository, logs, test fixtures, or telemetry.

7. **Tracking, replies, and follow-ups**
   - Maintain a durable timeline per company/role/contact: discovered, evaluated, prepared, blocked, submitted, sent, bounced, reply received, interview, assessment, rejection, offer, withdrawn, and follow-up due.
   - Distinguish confirmed facts from inferred status. Link each status to evidence and timestamp.
   - With separately authorized email access, match replies to the correct application/contact, summarize them, and suggest or prepare a response. Never claim a reply was received unless it exists in the connected mailbox.
   - Schedule follow-ups with configurable intervals and limits; avoid repeated or unwanted messages and honor opt-outs.
   - Provide dashboard, notifications, daily/weekly summaries, failures, upcoming follow-ups, and a pause/stop-all control.

## Autonomy model

The desired experience is **one-time policy authorization, then routine autonomy**, not repeated approval prompts. This does not override a platform's terms, account security, or a required human attestation. Initial account connection, email permission, personal-data sharing boundaries, and the overall automation policy must be explicitly configured. CAPTCHA, OTP, identity verification, missing facts, legal attestations, suspicious jobs, conflicting contact data, and uncertain submission outcomes stop only the affected workflow and ask for the specific human action needed.

## Reliability and privacy requirements

- Local-first storage; explicit encryption/secrets strategy for connected credentials; never store passwords in plaintext or commit tokens.
- Least-privilege OAuth/API access where available; user can revoke connections and delete data.
- Database migrations must preserve existing data and suppression history.
- Backups, restore tests, export/delete controls, audit events, bounded retries, timeouts, and idempotency.
- No real external submissions or email sends in tests. Use synthetic fixtures and mocked adapters.
- Tests cover duplicate prevention across restarts/re-imports, timezone scheduling, stale/expired jobs, conflicting records, suppression/opt-out, missing required answers, partial failures, uncertain submission outcomes, and accurate event logs.
- No PII in public repository, CI output, screenshots, test fixtures, or telemetry.
- Keep discovery and sending/submission fail-closed until source-specific feasibility, permission, and test gates are passed.

## Implementation order

1. Finish the existing Phase 0 offline HR CSV import/review task in planning/arena-task-phase-0-hr-contact-csv-import-2026-10-16.md; inspect and reuse existing importer/storage/UI first.
2. Audit current profile/resume ingestion, job/application schema, activity history, backup/restore, and scheduler before adding parallel abstractions.
3. Implement profile fact provenance and missing-information onboarding.
4. Implement durable application ledger, deduplication/idempotency, status evidence, and user-visible audit timeline.
5. Build a source-feasibility matrix for each named job platform and official company/ATS source; enable only integrations that are permitted and testable.
6. Add a twice-daily scheduler with observable runs, safe retries, and pause/stop controls.
7. Add email connection and private contact import; then test draft generation and suppression/deduplication before enabling any real sending.
8. Enable real application submission and HR email sending separately, source by source, only after explicit global authorization, permission review, safety checks, and end-to-end tests.

## Current state caveat

This document captures the target product direction only. It does not enable live discovery, connect accounts, send email, submit applications, or change the source quality gate. Existing gates and behavior must remain fail-closed until the relevant implementation and evidence exist.
