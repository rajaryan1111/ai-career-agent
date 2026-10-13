# Architecture Notes

**Status:** Research hypothesis — architecture is not approved  
**Last updated:** 2026-10-13

## 1. Architectural direction

Investigate a local-first desktop application with clear boundaries between desktop UI/settings, candidate storage, resume parsing, job-source adapters, normalization/deduplication, eligibility and matching, company research, application preparation/submission, scheduling/retries, and audit history.

Do not split into microservices for the initial product. A modular monolith or desktop application with local services is likely easier to build and maintain, but must be evaluated during research.

## 2. Conceptual data flow

Resume import → parse into candidate profile → user verifies fields → permitted job-source adapters discover listings → normalize and deduplicate → freshness/scam checks → hard eligibility filters → explainable relevance scoring → shortlist → company research → prepare application → permitted submission or user intervention → record evidence/status → dashboard and analytics.

## 3. Local-first boundary

Default local data: original resumes, parsed candidate profile, job preferences/exclusions, application history/notes, generated documents, and local audit records.

External transfer must be explicit and limited to the minimum necessary data. Before using an external LLM, job-data provider, or company research source, disclose what is sent and allow the user to opt in.

## 4. Technology options to research (not decisions)

- Desktop shell: Tauri vs Electron vs other viable options.
- UI: React, Vite, and TypeScript.
- Core logic: Python service vs TypeScript/Node vs a hybrid.
- Local database: SQLite as a candidate; assess encryption, migrations, backup, and portability.
- Resume parsing: local PDF/DOCX extraction with OCR as an optional path for scanned documents.
- Matching: deterministic eligibility rules plus transparent scoring; evaluate embeddings/LLMs only where they measurably improve results.
- Scheduling: OS scheduler vs in-app scheduler; document behavior while sleeping/offline.
- Browser automation: consider only for workflows that are explicitly authorized and technically appropriate.
- Company research: official pages and permitted public sources, with retrieval timestamps and citations.

## 5. Job-source adapter contract (conceptual)

Each source adapter should report source identity and documented access method; permission/terms review date and evidence; discovery capability separately from submission capability; listing URL and source identifier; retrieved/missing fields; retrieval timestamp/freshness; rate limits/restrictions/error categories; and support status (supported, experimental, unavailable, awaiting verification).

Never infer that a source permits automation merely because it is publicly viewable.

## 6. Application state model

Proposed states: discovered, shortlisted, rejected_by_rules, prepared, awaiting_user, submission_attempted, submitted_unverified, confirmed, failed, unknown_status, response_received, interview, rejected_by_employer, withdrawn.

Transitions must be auditable. A timeout after clicking submit must not be treated as a confirmed success. Retrying must first check whether a previous submission may already have succeeded.

## 7. Reliability concepts to validate

- Persistent scheduled-run records.
- Idempotency keys where supported.
- Deduplication based on normalized company, role, location, source IDs, and canonical URLs.
- Bounded retries with backoff.
- Manual recovery for ambiguous submissions.
- Crash-safe writes and database migrations.
- Local backups and export/import.
- Safe handling of source schema or page changes.

## 8. Scheduling limitation

Default schedule is 00:00 and 12:00 Asia/Kolkata. A desktop-only scheduler cannot execute when the computer is off or asleep. Research OS wake scheduling, missed-run catch-up, and optional cloud scheduling. Do not silently imply continuous availability.

## 9. Security considerations

Use OS credential storage where feasible. Never store platform passwords in plaintext. Avoid logging resumes, tokens, or full screening answers. Apply least privilege to integrations. Support profile/application-data deletion. Keep audit records useful without retaining unnecessary sensitive information. Document a threat model before enabling submission automation.

## 10. Architecture decisions pending

- Desktop framework.
- Single-language vs hybrid runtime.
- Database and local encryption strategy.
- Local inference vs optional external AI.
- Scheduler behavior while offline.
- Initial job-source adapters.
- Permitted submission workflows.
- Packaging and update strategy for macOS, Windows, and Linux.
