# Architecture Notes

**Status:** Production-oriented architecture; Tkinter/SQLite local alpha implemented, source integrations remain gated  
**Last updated:** 2026-10-14

## 1. Architectural direction

Use a local-first desktop application with clear boundaries between desktop UI/settings, candidate storage, resume parsing, job-source adapters, normalization/deduplication, eligibility and matching, company research, application preparation/submission, scheduling/retries, and audit history.

Do not split into microservices for the initial product. A modular monolith or desktop application with local services is likely easier to build and maintain, but must be evaluated during research.

## 2. Conceptual data flow

Manual profile setup (local resume parsing is a later, separately tested increment) → user verifies critical candidate facts → configurable occupation/role taxonomy and preferences → permitted source adapters discover listings only after source gates pass → normalize/deduplicate and check freshness → hard eligibility filters → explainable, occupation-aware relevance scoring → shortlist/company research → truthful application preparation → policy-gated permitted submission or exception handling → evidence-backed status and outcome analytics. A durable queue/scheduler coordinates work; a desktop UI and optional always-on worker share explicit contracts, not hidden shared state.

## 3. Local-first boundary

Default local data: original resumes, parsed candidate profile, job preferences/exclusions, application history/notes, generated documents, and local audit records.

External transfer must be explicit and limited to the minimum necessary data. Before using an external LLM, job-data provider, or company research source, disclose what is sent and allow the user to opt in.

## 4. Technology decision record

### Initial desktop shell — 2026-10-14
The first usable desktop slice uses Python's standard-library Tkinter UI, the existing Python domain core, and SQLite. This minimizes dependencies and avoids a separate frontend/backend bridge while the product is offline-only. The UI is a functional local alpha, not yet a packaged production release. Keep the domain layer independent of Tkinter so a future shell can replace the UI without rewriting eligibility or persistence rules.

The decision is reversible. Validate Tk availability, accessibility, native look-and-feel, packaging, update strategy, and Windows/macOS/Linux smoke tests before release. If those checks fail, compare Tauri/React or another shell using measured packaging and maintenance evidence.

- UI/runtime: Python + Tkinter; launch with `python -m career_agent`, or install the package and use the `career-agent` console script (same `main()`). `--version` reports `career_agent.__version__` plus the database schema version, with no packaging metadata and no display; `pyproject.toml` takes the distribution version from that same literal, so packaged metadata and the app cannot disagree, and the wheel contains only the `career_agent` package. There is no required third-party dependency; PDF résumé reading is the optional `pdf` extra. `career_agent.config` is the single place that decides which database file a run uses — an explicit path, then `CAREER_AGENT_DATABASE`, then `<data folder>/career_agent.sqlite3`, where the data folder follows `CAREER_AGENT_HOME` when it is absolute and the platform's per-user application-data folder otherwise — so the window, the backup/restore commands and `--doctor` cannot disagree about the file. It creates no directory and reads nothing while resolving; only the default location is created automatically, when a run actually needs it. A relative value in either setting is ignored and reported rather than resolved against the working directory. Start-up failures are explained by `career_agent.diagnostics` (Tk-free): a plain-language message that names the next step, with local paths redacted, plus one bounded owner-only note beside the app data; `--doctor` prints the same settings read-only and exits non-zero when it finds a problem. Launchers, signed desktop bundles, installers, and a version/data-compatibility policy are not implemented; the exact missing pieces are listed in the README's packaging status.
- Core logic: Python standard library.
- Local database: SQLite; verified local backup and restore are implemented (owner-only files, no overwrite, validated before and after replacement; a restore holds the database's exclusive lock across the swap and reports a replaced file it cannot reopen instead of claiming success). Tracker writes are validated at the storage boundary, and a caller that decided from a row it read can write conditionally, so a record another writer moved on is refused rather than overwritten. Schema updates are recorded steps (`store._MIGRATIONS`, currently 1 and 2): each runs statement-by-statement inside one explicit transaction that writes the version it reached in the same commit, a failing step is rolled back and reported with the version re-read from the file, and a database recording a newer version - or one holding tables with no recorded version at all - is refused untouched by named exception types (`SchemaTooNewError`, `UnrecognisedDatabaseError`, `SchemaMigrationError`). `backup.validate_app_database` checks a candidate file against the tables of the version that file records (`SCHEMA_TABLES_BY_VERSION`), so an older backup is accepted and updated when this build opens it, while a newer one is refused rather than downgraded. Encryption-at-rest and portability remain Phase 2 work.
- Resume parsing: deferred from the first usable slice; later local PDF/DOCX extraction must include field-level confidence/review and must not upload candidate data.
- Matching: deterministic eligibility rules plus transparent scoring; evaluate embeddings/LLMs only where they measurably improve results.
- Scheduling: OS scheduler vs in-app scheduler; document behavior while sleeping/offline.
- Browser automation: consider only for workflows that are explicitly authorized and technically appropriate.
- Company research: official pages and permitted public sources, with retrieval timestamps and citations.

## 5. Job-source adapter contract (conceptual)

Each source adapter should report source identity and documented access method; permission/terms review date and evidence; discovery capability separately from submission capability; listing URL and source identifier; retrieved/missing fields; retrieval timestamp/freshness; rate limits/restrictions/error categories; and support status (supported, experimental, unavailable, awaiting verification).

Never infer that a source permits automation merely because it is publicly viewable. Record provider-level restrictions on AI orchestration, systematic extraction, and data reuse as hard adapter gates. A technical public endpoint is not sufficient; if the provider's API policy restricts autonomous/generative-AI workflows and no applicable endorsed pathway is verified, mark the adapter unavailable pending authorization. SmartRecruiters is blocked pending an applicable endorsed pathway or written authorization; Himalayas is also blocked pending written clarification because its public API docs contemplate integrations while its general terms broadly prohibit automated data gathering without prior written approval. See [SmartRecruiters policy review](research/smartrecruiters-api-policy-review-2026-10-13.md) and [Himalayas permission review](research/himalayas-api-permission-terms-conflict-2026-10-13.md).

The contract's permission gate is now encoded rather than implied: `career_agent/sources.py` holds the reviewed decision for each named source (state, evidence reference, review date, separate discovery and submission conditions, whether it is selected for use) and pure fail-closed gate functions. `SOURCE_QUALITY_GATE_PASSED` is `False`, so `enabled_discovery_sources()` is empty today, an unregistered source is refused, and submission is refused even where read access is approved. Run outcomes are a separate taxonomy (`RunOutcome`) from a listing's availability: a legitimate empty result is distinct from permission-denied, rate-limited, auth-required, timeout, network, schema, challenge-detected, and partial outcomes, and only a complete run with results may support a closure claim. Untrusted links are validated by `career_agent/urls.py`, which inspects the literal host only — no DNS resolution, no redirect following — so it must not be described as SSRF protection; resolution/redirect re-validation, response-size limits, and challenge-page detection remain requirements for whatever fetcher is authorized later. Review of the reference implementation, including what was deliberately not adopted, is in [the Agent-Reach reuse review](research/agent-reach-reuse-review-2026-10-14.md).

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
- Provider-specific response semantics: a successful response with zero records is not always proof that a board is valid and empty; migrations can leave old and new boards both responding; filtered runs must not mark omitted records closed. Record per-source run outcomes, counts before/after filters and deduplication, stable IDs touched, and explicit error categories (empty success, blocked, rate-limited, transient failure, schema error, permission gate closed). See the [n8n workflow pattern review](research/n8n-workflows-repository-review-2026-10-13.md).
- Field-level uncertainty: preserve missing vs. zero, raw pay ranges, currency, unit/period, source wording and evidence. Do not normalize ambiguous compensation to annual salary.
- Contract fixtures per source for pagination, timestamp units, empty/error responses, missing fields, challenge pages, dedup/reposts, and malformed payloads. Keep live smoke tests separate from deterministic offline tests.

## 8. Scheduling and deployment boundary

Default discovery schedule is 00:00 and 12:00 Asia/Kolkata. The requirement to operate while the laptop is off means desktop-only scheduling is insufficient. Evaluate an always-on worker as a separate deployable component with durable queues, idempotent run keys, bounded retries, health/last-run reporting, missed-run catch-up, and alertable failures. A remote worker must not silently receive resumes or email contents: minimize data, encrypt transport/storage, document retention/location, and make remote processing opt-in. A free tier is not a reliability guarantee; disclose sleep, quota, cold-start, and uptime limitations. Never claim background operation until the deployed worker is actually verified.

## 9. Security considerations

Use OS credential storage where feasible. Never store platform passwords in plaintext. Avoid logging resumes, tokens, or full screening answers. Apply least privilege to integrations. Support profile/application-data deletion. Keep audit records useful without retaining unnecessary sensitive information. Document a threat model before enabling submission automation.

## 10. Remaining architecture decisions

- Packaging, install/update/uninstall, and supported OS matrix for the Tkinter alpha.
- Local database migrations, encryption-at-rest, backup and restore strategy.
- Optional local inference versus external AI processing and its consent/cost boundary.
- Scheduler behavior while offline and an optional remote-worker deployment.
- Initial job-source adapters and separately permitted submission workflows.


## 11. Existing repository assets to evaluate later (not implementation approval)

The 2026-10-13 repository audit found reusable patterns in the user's existing repositories: `graphone-intelligence-pipeline` for ingestion/retries/freshness/provenance/schema validation, `ai-orbit-tools-ingestion` for source registries/official-site verification/checkpoints/deduplication, `AI_resume_review` for candidate/JD analysis UX, and `indian-standards-procurement-ai` for retrieval/reranking/evidence explanations. See [the complete repository audit](research/github-repository-audit-2026-10-13.md). Reuse should mean selecting and reviewing small modules and tests only after the decision gate, not copying entire applications or databases.

The ATS field-coverage study at [research/ats-board-api-field-coverage-review-2026-10-13.md](research/ats-board-api-field-coverage-review-2026-10-13.md) is a test-case reference, not proof of current provider behavior or permission. No source, dataset, framework, or dependency was approved by this audit. A targeted review of the internal ingestion/verification repositories is documented in [research/internal-reuse-candidates-deep-audit-2026-10-13.md](research/internal-reuse-candidates-deep-audit-2026-10-13.md): retain patterns selectively, do not copy source adapters without independent permission review, and treat robots.txt as courtesy rather than authorization. The live source smoke-test report is tracked at [research/live-source-smoke-test-2026-10-13.md](research/live-source-smoke-test-2026-10-13.md); it is a limited endpoint smoke test, not a production coverage result.

### Open-source reliability review — 2026-10-13

The [QaliAI/ai-job-agent review](research/open-source-ai-job-agent-review-2026-10-13.md) reinforces three architecture invariants before implementation: (1) per-source transport/schema/rate-limit/permission outcomes must be distinct from a valid empty result; (2) failed or blocked canonical verification means unknown/unverified, never open; and (3) work mode, country eligibility, compensation currency and pay period require separate evidence-backed fields. Do not reuse its SmartRecruiters adapter while our source-policy gate remains blocked. These are acceptance requirements, not implemented features. No code or dependencies added.


### Implemented local alpha — 2026-10-14
The repository now includes a Python/Tkinter UI launched with `python -m career_agent`, deterministic eligibility evaluation, explainable skill overlap, conservative URL/requisition deduplication, separate source/application URL fields, optional exact-match work-authorization requirements, guarded application-state transitions, and standard-library SQLite persistence for profile/job/tracker records. The desktop app chooses a per-user application-data path and performs no network requests. This is an internal local alpha, not a packaged production release. The store also has a verified local backup and restore path (desktop *Data safety* tab, or `python -m career_agent --backup-to/--restore-from`), so a database that cannot be read can be backed up or restored without opening the window. `career_agent/resume.py` reads a PDF or DOCX the person chooses, entirely on this machine and with no network request, and proposes only values the existing profile schema already holds; the profile is never written from a document without the person reviewing and selecting each value. PDF text extraction needs the optional `pypdf` library, DOCX extraction uses the standard library, and there is no OCR, so a scanned PDF with no text layer is reported as unreadable rather than guessed at. Live source adapters, remote execution, autofill, and submission remain deferred or gated; GUI smoke tests and signed desktop packaging remain outstanding, while installing the package into a supported Python environment (`pip install .`, optional `[pdf]` extra) is implemented and its wheel is built, inspected and run in CI.


## 12. Production product architecture and cross-industry extensibility

### 12.1 Modular product boundaries

Keep a modular monolith/domain core until measured complexity justifies service separation. Define explicit interfaces for candidate profile/resume extraction, occupation taxonomy, job-source discovery, normalization/deduplication, eligibility, relevance ranking, company intelligence, application preparation, platform-specific application adapters, scheduler/queue, email/calendar integrations, audit/evidence, and UI. Do not introduce microservices or a multi-agent framework without a concrete operational need.

### 12.2 Industry-agnostic core with occupation packs

The shared engine must not assume AI/ML or software engineering. Occupation packs/configuration may contribute synonyms, skill families, credentials, portfolio/work-sample requirements, seniority signals, tools, and role-specific evaluation rubrics for fields such as design, VLSI/embedded, mechanical, civil, software/data, business, and other professions. Keep these as versioned data/rules or isolated modules behind stable interfaces; preserve the source evidence and explain each match. Unsupported roles must degrade transparently, not receive fabricated precision. Validate on representative resumes and job descriptions across different domains before claiming broad coverage.

### 12.3 Remote worker and durable orchestration

Separate the desktop experience from the optional always-on execution worker. The worker should claim durable tasks, use idempotency keys for discovery/application actions where possible, record per-source outcomes, resume interrupted work, enforce concurrency/rate limits, and isolate adapter failures. The desktop is the control plane for profile, permissions, policies, logs, and status; it must show the worker's actual health and last successful run. Do not treat the local SQLite file as automatically safe or synchronized for remote execution; define a deliberate storage/sync boundary first.

### 12.4 Production readiness

Require schema migrations, backup/restore and export/delete flows, secure secret storage, structured redacted logs, supported-platform packaging and update strategy, adapter health/version tracking, deterministic tests plus integration tests, and pilot evidence. Each source's discovery permission and submission permission are distinct. A supported adapter must have current permission evidence, documented limitations, fixtures, error handling, and a regression path. No feature is production-ready solely because a happy-path demo succeeds.
