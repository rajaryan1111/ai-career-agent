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

The decision is reversible. Validate Tk availability, accessibility, native look-and-feel, packaging, update strategy, and Windows/macOS/Linux smoke tests before release. As of 2026-10-15 CI covers part of that: the full suite and a scripted desktop smoke test run on Linux under a real virtual display (Xvfb), and the suite plus an installed-wheel rehearsal of the command surface run on Windows and macOS runners. Tk availability is therefore measured on three operating systems, while accessibility, native look-and-feel, packaging, code signing and the update strategy remain unvalidated. If those checks fail, compare Tauri/React or another shell using measured packaging and maintenance evidence.

Cross-platform execution also settled two boundaries that had only been stated. The owner-only file guarantee
is POSIX-only: `career_agent.store` applies the mode where the platform has one and reports nothing applied
where it does not, instead of refusing the write - the first Windows run showed what refusing costs, because
the store records its own start in the event log and every store construction failed with the descriptor
applied through a missing `os.fchmod`. Decisions of that kind are named once, in the module that makes them,
and the tests that need them resolve them there rather than spelling out a platform's folder names, which is
how six doctor tests came to fail on macOS and Windows while passing on Linux.

- UI/runtime: Python + Tkinter; launch with `python -m career_agent`, or install the package and use the `career-agent` console script (same `main()`). `--version` reports `career_agent.__version__` plus the database schema version, with no packaging metadata and no display; `pyproject.toml` takes the distribution version from that same literal, so packaged metadata and the app cannot disagree, and the wheel contains only the `career_agent` package. There is no required third-party dependency; PDF résumé reading is the optional `pdf` extra. `career_agent.config` is the single place that decides which database file a run uses — an explicit path, then `CAREER_AGENT_DATABASE`, then `<data folder>/career_agent.sqlite3`, where the data folder follows `CAREER_AGENT_HOME` when it is absolute and the platform's per-user application-data folder otherwise — so the window, the backup/restore commands and `--doctor` cannot disagree about the file. It creates no directory and reads nothing while resolving; only the default location is created automatically, when a run actually needs it. A relative value in either setting is ignored and reported rather than resolved against the working directory. Start-up failures are explained by `career_agent.diagnostics` (Tk-free): a plain-language message that names the next step, with local paths redacted, plus one bounded owner-only note beside the app data; `--doctor` prints the same settings read-only and exits non-zero when it finds a problem; on a file whose schema is the current one it also decodes every stored record through the same functions the read paths use (`store.unreadable_stored_records`, over a `mode=ro` connection), so "no problems found" cannot be printed over a record every read path refuses, and reports a file that records an **older** schema by version instead of decoding a layout an upgrade would have changed. `career_agent.event_log` keeps the sequence: one bounded, rotated, owner-only line per event beside the database, holding event names, identifiers and counts rather than candidate content, with every detail redacted through the same function the start-up note uses and a write failure returning `None` instead of failing the action it describes. The version/data-compatibility policy is written in the README (what a release number promises about the database, the snapshot taken before an update, the refusal of a newer file, and the export format version); launchers, signed desktop bundles and installers are not implemented, and the exact missing pieces are listed in the README's packaging status.
- Core logic: Python standard library.
- Local database: SQLite; verified local backup and restore are implemented (owner-only files, no overwrite, validated before and after replacement; a restore holds the database's exclusive lock across the swap and reports a replaced file it cannot reopen instead of claiming success). Tracker writes are validated at the storage boundary, and a caller that decided from a row it read can write conditionally, so a record another writer moved on is refused rather than overwritten. Schema updates are recorded steps (`store._MIGRATIONS`, currently 1 to 6): each runs statement-by-statement inside one explicit transaction that writes the version it reached in the same commit, a failing step is rolled back and reported with the version re-read from the file, and a database recording a newer version - or one holding tables with no recorded version at all - is refused untouched by named exception types (`SchemaTooNewError`, `UnrecognisedDatabaseError`, `SchemaMigrationError`). `backup.validate_app_database` checks a candidate file against the tables of the version that file records (`SCHEMA_TABLES_BY_VERSION`), so an older backup is accepted and updated when this build opens it, while a newer one is refused rather than downgraded. Encryption-at-rest and portability remain Phase 2 work.
- Resume parsing: deferred from the first usable slice; later local PDF/DOCX extraction must include field-level confidence/review and must not upload candidate data.
- Matching: deterministic eligibility rules plus transparent scoring; evaluate embeddings/LLMs only where they measurably improve results.
- Scheduling: OS scheduler vs in-app scheduler; document behavior while sleeping/offline.
- Browser automation: consider only for workflows that are explicitly authorized and technically appropriate.
- Company research: official pages and permitted public sources, with retrieval timestamps and citations.

## 5. Job-source adapter contract

Implemented in `career_agent/adapters.py` (reported by `python -m career_agent --sources`; no adapter of
any live source exists). A `SourceAdapter` fetches and reports; the registry owns the gate, the framework
owns validation, and nothing else may call a source. `SourceCapabilities` declares what an adapter can do
and refuses `submission=True` by construction. Each run carries a `RequestBudget` (a hard request cap plus
a minimum interval, both enforced before a request is issued) and an `AdapterRequest` whose page size is
required and capped, so an unbounded request cannot be expressed. Failures are translated into the run
taxonomy, only transient outcomes are retried, and every wait is injected so the backoff schedule is
tested rather than slept. Normalisation keeps provenance and reports every rejected record with its index
and reason; it deliberately leaves eligibility scope, disciplines, experience ranges and compensation
unset until a reviewed parser exists for a source. Health keeps success, empty, partial, failed and
disabled apart.

### 5a. Original contract notes

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
- Crash-safe writes and database migrations. Implemented for the local alpha: each schema step runs in
  one explicit transaction that records the version it reached in the same commit, the recorded version is
  re-read from the file before "nothing changed" is claimed, and an existing database at an older version
  is first copied to a verified snapshot beside itself - because a step that succeeds and is only later
  found to be wrong is already committed, and that copy is then the recovery path. A copy that cannot be
  written stops the update instead of proceeding without one.
- The work around an application is its own record, in its own module. ``career_agent/preparation.py`` is
  pure: it takes preparation items, interview rounds, follow-up reminders, the listings and a ``today`` the
  caller supplies, and returns one ordered action list plus the sentences that describe it. The ordering is
  a documented decision (overdue first, then today, then the window; within the overdue group the oldest
  promise first whatever its kind, with the kind breaking same-day ties - an appointment on somebody else's
  clock ahead of a chase, ahead of your own checklist), the two summary functions distinguish "nothing
  recorded" from "nothing due", and a capped report always states how many lines it left out. The records
  themselves live in schema 5's ``application_preparation`` and ``interview_round`` tables, both deleted
  with their listing, and both deliberately unable to touch an application: the item has no status column,
  and the round's outcome vocabulary has no value that sounds like an employer's decision. Completing an
  item is refused a second time so the stored timestamp keeps meaning the first time it was reported, and a
  duplicate open item or a duplicate round for the same stage and day is refused rather than merged.
- The candidate's own employment and education are records, not more profile fields.
  ``career_agent/core.py`` holds ``WorkHistoryEntry`` and ``EducationEntry`` - frozen records whose
  validation runs in ``__post_init__``, so a contradiction (an end before a start, a current role with an
  end date, an ongoing qualification with a completion date) cannot exist in memory, in the store, or in an
  imported file. Blank optional text becomes ``None`` rather than an empty string, and neither record has a
  field that could move an application or be mistaken for an employer's decision. Both are ordered by the
  store rather than by the caller (the current role first, then most recent; an ongoing qualification
  before completed ones, and an undated one after the dated ones) so the window, the CLI and any future
  front end read the same list in the same order. ``months_covered_by`` is the one duration figure the app
  reports: the union of the months covered by current or fully dated roles, counting a month covered twice
  once and a role with no recorded end not at all, because adding up job durations would overstate exactly
  the people with concurrent or undated roles. The records live in schema 6's ``candidate_work_history``
  and ``candidate_education`` tables; both are deleted with the profile in one transaction (and never with
  a listing), and ``profile_record_counts`` is what the confirmation dialog names before it deletes
  anything. They are absent from eligibility, matching and scoring, which read the profile's own fields.
- Progress reporting is a pure function over the stored records. ``career_agent/analytics.py`` takes the
  listings, the tracker rows, the per-listing activity and the interview rounds plus a ``today`` the caller
  supplies, and returns a report: counts, rates, two timings and one period comparison. Nothing else in the
  app computes a statistic, so the window, ``--analytics`` and any test read the same numbers. The module's
  rules are the product requirements rather than formatting choices - every rate carries the label of its
  denominator, a denominator below ``MIN_RATE_DENOMINATOR`` (five) withholds the rate and states the floor,
  a zero denominator is reported as nothing measured rather than as 0% (the two are finally different
  sentences), a metric the schema cannot observe is listed in ``UNAVAILABLE_METRICS`` with its reason
  instead of being printed as zero, a median below ``MIN_MEDIAN_SAMPLES`` is withheld with its sample size,
  and a period comparison needs ``MIN_RATE_DENOMINATOR`` recorded applications in *both* windows before the
  two are set beside each other. Reply timing uses only dates the person recorded: a reply that exists only
  as a status change has no date, because the tracker stores when the row was saved rather than the day the
  employer wrote, and the report says so rather than counting it as day zero. ``_CAVEATS`` is data, printed
  by every report, so an edit that dropped a caveat fails a test rather than quietly shipping a bare
  percentage.
- Local backups and export/import. Back up/restore moves the whole SQLite file and is the local
  durability path; the JSON export/import is the portable, versioned format and is deliberately stricter
  about what it will assert: `career_agent/importer.py` owns both directions of the format
  (`EXPORT_FORMAT_VERSION`, currently 2, with `READABLE_FORMAT_VERSIONS` naming every version still read),
  reads and validates the whole file before writing anything, refuses any document whose version is not one
  this build reads (naming the number it holds and the ones it reads), and returns a plan (what would be added, linked, kept or
  refused) that a caller must show and confirm before `apply_import` runs. The import never replaces
  stored data: a listing already present is linked through the same duplicate key the rest of the app uses
  and keeps its first-seen time, a stored candidate profile is kept and reported, and an application
  record is always created at `ApplicationStatus.DISCOVERED` — a later status in the file is *reported* as
  not imported rather than adopted, because a status here is only ever reached by the guarded transition
  path. Follow-up days travel as data, unreadable days are reported rather than dropped, and activity is
  appended with (day, kind, text) deduplication so re-importing a file cannot double a timeline. Writes
  go through `store.write_private_text_file` (owner-only, symlink-refusing); the CLI dry-runs by default, and
  an import sweeps the target file with `store.unreadable_stored_records` before it plans anything, so a file
  holding a record this build cannot read is refused instead of being half-applied.
- Safe handling of source schema or page changes.
- Provider-specific response semantics: a successful response with zero records is not always proof that a board is valid and empty; migrations can leave old and new boards both responding; filtered runs must not mark omitted records closed. Record per-source run outcomes, counts before/after filters and deduplication, stable IDs touched, and explicit error categories (empty success, blocked, rate-limited, transient failure, schema error, permission gate closed). See the [n8n workflow pattern review](research/n8n-workflows-repository-review-2026-10-13.md).
- Matching is a comparison, not a forecast. `career_agent/matching.py` reports each factor
  (required skills, experience range, stated qualification, location, work mode, role type) as
  pass/partial/fail/unknown/not applicable with its evidence, and returns a score together with the
  coverage of the applicable weight that was actually known; below half, the reading is "not enough
  information" and the score is not allowed to look confident. Silence is never a pass, equivalences
  between differently-spelled skills come only from a caller-supplied table, and no output may describe a
  score as a probability. Compensation is deliberately not compared: the domain model has no field for it.
- Follow-ups are a *plan*, not an event: `application_tracker.follow_up_on` and `follow_up_note`
  (schema 4, additive columns) hold a day a person chose and a short note; `career_agent/followups.py`
  turns them into reminders (overdue / due today / upcoming / later) counted in whole days against a date
  the caller supplies, so a report is reproducible and no timezone is guessed. Nothing in that path moves
  an application's status, writes an activity entry, or records that an employer replied. Two local
  surfaces read it - the `follow-up-digest` scheduled task (day taken from the occurrence, not from the
  wall clock, so a late run reports the day it was due for) and `--follow-ups` - and one local export
  writes it out: an `.ics` with all-day events, no attendees and no links, folded at 75 octets on
  character boundaries, written owner-only. There is no email, calendar-account or push integration.
- Field-level uncertainty: preserve missing vs. zero, raw pay ranges, currency, unit/period, source wording and evidence. Do not normalize ambiguous compensation to annual salary.
- Contract fixtures per source for pagination, timestamp units, empty/error responses, missing fields, challenge pages, dedup/reposts, and malformed payloads. Keep live smoke tests separate from deterministic offline tests.

## 8. Scheduling and deployment boundary

Default discovery schedule is 00:00 and 12:00 Asia/Kolkata. Implemented so far is the durable half of
the local scheduler: task definitions stored with their schedule in a named zone, one run row per
scheduled occurrence and attempt (the uniqueness constraint is the duplicate-run protection, so a
restart, a retry or a second process cannot execute one occurrence twice), bounded exponential retries
that serve the occurrence a failed attempt still owes, heartbeats with stale-attempt recovery recorded
as *interrupted* rather than guessed at, and a worker lease that refuses a second scheduler over the
same database. The worker loop itself, the user-visible surfaces (command line, window, missed-run and
health reporting) and any always-on deployment are still to come. The requirement to operate while the
laptop is off means desktop-only scheduling is insufficient. Evaluate an always-on worker as a separate deployable component with durable queues, idempotent run keys, bounded retries, health/last-run reporting, missed-run catch-up, and alertable failures. A remote worker must not silently receive resumes or email contents: minimize data, encrypt transport/storage, document retention/location, and make remote processing opt-in. A free tier is not a reliability guarantee; disclose sleep, quota, cold-start, and uptime limitations. Never claim background operation until the deployed worker is actually verified.

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
The repository now includes a Python/Tkinter UI launched with `python -m career_agent`, deterministic eligibility evaluation, explainable skill overlap, conservative URL/requisition deduplication, separate source/application URL fields, optional exact-match work-authorization requirements, guarded application-state transitions, and standard-library SQLite persistence for profile/job/tracker records. The desktop app chooses a per-user application-data path and performs no network requests. This is an internal local alpha, not a packaged production release. The store also has a verified local backup and restore path (desktop *Data safety* tab, or `python -m career_agent --backup-to/--restore-from`), so a database that cannot be read can be backed up or restored without opening the window. The store copies an existing database to a verified snapshot beside itself before it applies the first schema step for an update to a newer application version (never for a new or already-current file, and refusing to start the update if the copy cannot be written), so a committed step that turns out to be wrong can be undone by restoring that copy. `career_agent/resume.py` reads a PDF or DOCX the person chooses, entirely on this machine and with no network request, and proposes only values the existing profile schema already holds; the profile is never written from a document without the person reviewing and selecting each value. PDF text extraction needs the optional `pypdf` library, DOCX extraction uses the standard library, and there is no OCR, so a scanned PDF with no text layer is reported as unreadable rather than guessed at. `career_agent/integrations.py` is the email and calendar boundary, and it is deliberately an interface with no enabled implementation: an `EmailDraft` and a `CalendarEventRequest` are values, `preview_email` and `preview_event` turn one into the text a person would read (with a separate list of the facts that are missing and the facts that would make the entry more precise), and performing anything goes through an `Integration`. The default is a `DisabledIntegration` that answers every request with an explicit disabled result naming the reason and what to do instead; nothing in configuration, the environment or the database selects anything else. `LocalMockIntegration` is the one implementation that performs anything, it performs it in a ledger (memory, or an owner-only local file), and it contacts nothing - the shipped-code scan in `tests/test_local_only.py` and a guarded interpreter with no sockets keep that true. Idempotency is structural: an operation id is a digest of the operation's own content, a recorded id is refused a second time as a duplicate, a failed attempt is not recorded as done so a retry is both allowed and non-duplicating, and an id recorded against a different kind of operation is refused rather than guessed at. The local `.ics` export remains the only working calendar path; the preview of it calls the same `followups.event_uid`/`event_summary` the writer does, so the preview cannot promise a different event from the one the file will hold. Live source adapters, remote execution, autofill, and submission remain deferred or gated; *manual* GUI acceptance and signed desktop packaging remain outstanding, while installing the package into a supported Python environment (`pip install .`, optional `[pdf]` extra) is implemented and its wheel is built, inspected and run in CI on Linux, Windows and macOS. The window itself is exercised on three levels that are not interchangeable: handler tests with stubbed widgets, the scripted smoke test under a real display (Xvfb on Linux, where it must pass; reported as BLOCKED where a runner has none), and the human checklist, whose GUI steps are still unrun.


## 12. Production product architecture and cross-industry extensibility

### 12.1 Modular product boundaries

Keep a modular monolith/domain core until measured complexity justifies service separation. Define explicit interfaces for candidate profile/resume extraction, occupation taxonomy, job-source discovery, normalization/deduplication, eligibility, relevance ranking, company intelligence, application preparation, platform-specific application adapters, scheduler/queue, email/calendar integrations, audit/evidence, and UI. Do not introduce microservices or a multi-agent framework without a concrete operational need.

### 12.2 Industry-agnostic core with occupation packs

The shared engine must not assume AI/ML or software engineering. Occupation packs/configuration may contribute synonyms, skill families, credentials, portfolio/work-sample requirements, seniority signals, tools, and role-specific evaluation rubrics for fields such as design, VLSI/embedded, mechanical, civil, software/data, business, and other professions. Keep these as versioned data/rules or isolated modules behind stable interfaces; preserve the source evidence and explain each match. Unsupported roles must degrade transparently, not receive fabricated precision. Validate on representative resumes and job descriptions across different domains before claiming broad coverage.

### 12.3 Remote worker and durable orchestration

Separate the desktop experience from the optional always-on execution worker. The worker should claim durable tasks, use idempotency keys for discovery/application actions where possible, record per-source outcomes, resume interrupted work, enforce concurrency/rate limits, and isolate adapter failures. The desktop is the control plane for profile, permissions, policies, logs, and status; it must show the worker's actual health and last successful run. Do not treat the local SQLite file as automatically safe or synchronized for remote execution; define a deliberate storage/sync boundary first.

### 12.4 Production readiness

Require schema migrations, backup/restore and export/delete flows, secure secret storage, structured redacted logs, supported-platform packaging and update strategy, adapter health/version tracking, deterministic tests plus integration tests, and pilot evidence. Each source's discovery permission and submission permission are distinct. A supported adapter must have current permission evidence, documented limitations, fixtures, error handling, and a regression path. No feature is production-ready solely because a happy-path demo succeeds.

---

## Target Architecture Addendum — Autonomous Career Operations (2026-10-16)

### Architectural objective
Evolve the existing local-first desktop alpha into a policy-driven career agent while reusing the current profile, importer, SQLite store, activity history, backup/restore and fail-closed source gates. Inspect current modules and migrations before adding abstractions; do not create parallel stores, schedulers, ledgers or importers without proving existing components are insufficient.

### Logical components
- **Profile & Resume Intelligence:** parsers, normalized profile facts, fact provenance, confidence/uncertainty, profile versioning and missing-field onboarding.
- **Career Policy Engine:** target-role taxonomy, location/work preferences, eligibility constraints, exclusions, per-source capabilities, global action authorization, limits and stop conditions.
- **Discovery Scheduler:** timezone-aware twice-daily runs, per-source jobs, run history, bounded retries, cancellation, next-run visibility and pause/stop control.
- **Source Adapters:** independently assessed adapters for permitted public feeds, official company career pages, supported ATS APIs and platform-approved workflows. Each declares capabilities, permission/terms review, freshness, rate limits, authentication needs and evidence quality.
- **Job Normalization & Matching:** canonical job identity, duplicate clustering, stale/expired detection, explainable matching, eligibility assessment and evidence-backed fit.
- **Application Orchestrator:** deterministic state machine, tailored artifact versioning, required-answer validation, source-specific execution, idempotency keys and reconciliation of uncertain outcomes.
- **Private Contact & Outreach Service:** CSV import/review, provenance, email normalization, conflict queue, suppression/opt-out, campaign policy, contact-level idempotency, authorized mail provider and delivery/bounce state.
- **Application/Communication Ledger:** durable activity events and current projections; persist source evidence, timestamps, external IDs, artifacts, attempts and final/unknown states.
- **Inbox/Reconciliation Service:** only with separately authorized mailbox access; associate actual replies with contacts/applications and preserve message references.
- **Notification & Reporting Service:** run summaries, failures, responses, deadlines, follow-up queue and configurable daily/weekly reporting.
- **Integration & Secrets Boundary:** least-privilege OAuth/API credentials or supported local credential mechanisms; no plaintext passwords or committed tokens.
- **Safety/Policy Gate:** centralized decision before any network, email or submission side effect; default deny when permissions, source support, required facts or outcome confidence are insufficient.

### State and execution invariants
1. Discovery, preparation, sending and submission are separate capabilities and separate gates.
2. A discoverable source does not imply automated submission is supported.
3. External side effects must have persisted intent and policy evaluation; completion is recorded only after evidence is observed.
4. Use stable deduplication keys for jobs, applications, contacts and outreach campaigns. Never blindly retry an ambiguous external submission.
5. Preserve a durable submission-unknown state and reconcile before retrying.
6. Preserve suppression/opt-out history across re-imports and migrations.
7. Record decisions and transitions with timestamps, evidence references, results and reasons; redact secrets and contact details from diagnostics.
8. Real external actions are never performed in tests.

### Implementation constraints
- Preserve the existing schema migration contract and backup/restore guarantees.
- Reuse the current SQLite schema/store where possible; introduce migrations only after inspection and migration/restore tests.
- Keep source quality gates disabled until the source is individually assessed, permitted and tested.
- Respect platform terms, rate limits, authentication and human-verification requirements. No CAPTCHA/OTP bypass, anti-bot evasion or prohibited scraping.
- Support one-time global authorization for routine eligible actions, with revocation, limits, pause and stop-all.
