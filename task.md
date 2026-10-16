# AI Career Agent — Product Execution Backlog

**Last updated:** 2026-10-16  
**Purpose:** Actionable task inventory derived from the product vision. Completion must be based on verified implementation and test evidence.

## Product outcome
After resume upload and one-time setup, the agent should autonomously discover relevant jobs twice daily, evaluate fit and eligibility, prepare truthful application materials, submit through permitted supported workflows, send authorized personalized HR outreach, track actual replies/outcomes, prevent duplicates and proactively report progress. Routine actions inside saved global policy should not require per-application approval.

## P0 — Finish offline HR contact import
- [x] Implement the offline CSV parser/preview contract with synthetic fixtures: BOM/encoding handling, explicit header validation, ambiguous email-column refusal, source-value preservation, normalised comparison keys, duplicate grouping, conflict flags, privacy-safe aggregate CLI report, and strict size/row caps. See [parser/preview evidence](research/hr-contact-csv-preview-2026-10-16.md) and commit `062a88c`.
- [x] Add parser tests for malformed/empty files, normalisation, duplicate groups, conflicts, privacy, no-write behaviour and CLI refusal paths. The 13-job matrix has been green on run `38823626117` (`3a88e6e`), `38824979826` (`256fdae`), `38825791766` (`e0f8da4`) and `38825772870` (`4798b16`); the run that carries the persistence/review increment is cited in its research note.
- [x] Inspect and reuse the existing SQLite migration/backup-before-upgrade, storage, desktop tab/scrolling, activity-event, backup/restore and GUI acceptance patterns before adding persistence or UI abstractions. Seen in commit `168ac31`: the contacts step goes through `_MIGRATIONS` and the existing runner, the entity follows the store's dataclass/`_decode_*`/`_record`/`_select_*` shape, and the tab reuses `_scrollable_body`, `_clear_tree` and the shared failure reporters.
- [x] Add a migration-safe contacts store through the existing migration runner; preserve provenance and original review values; reuse `contacts.normalise_email_key`; make imports transactional and deterministic. Schema **7** adds `hr_contact` and `hr_contact_conflict` as an appended, additive, re-runnable step; the key always comes from `normalise_email_key`; the original address, name, company and the file's *name* are stored and never rewritten by a later import; `import_contacts` is one `BEGIN IMMEDIATE ... COMMIT` and `plan_contact_import` decides read-only from the database. Evidence: `tests/test_contacts_store.py` (39 tests) and three schema tests in `tests/test_store.py`, written up in [the persistence/review note](research/hr-contact-import-persistence-and-review-ui-2026-10-16.md).
- [x] Preserve suppression/do-not-contact state across duplicate imports, metadata conflicts, restarts, backup and restore. `suppressed` is written by exactly one method (`set_contact_suppression`) and by no import statement, and is asserted across a re-import, a contradictory file, a closed-and-reopened database and a backup restored over a database whose mark had been cleared.
- [x] Add the local review/import UI: preview, conflicts and rejected-row reasons; explicit confirm-before-write; cancel/close/parse-refusal must perform zero writes. The **HR contacts** tab shows the parser's report and the flagged rows in file order (the columns it used, and its refusal when two columns could be the address, are how "mappings" is handled today - a control that lets a person remap a column and row-by-row selection are **not** implemented and are named in the research note), the confirmation shows the plan computed from the database, and every zero-write path is asserted against the connection's `total_changes` rather than a message.
- [x] Test migration/rollback, backup/restore, repeated imports, conflicts, suppression persistence, cancellation/no-write, confirmation, storage failure, GUI keyboard/scrolling paths and regression behavior: 39 contact-store tests (40 after the mark's own privacy test below), 3 schema tests, 12 tab handler tests, workflow **L** in `scripts/desktop_acceptance.py` (five checks on the display-backed CI legs, whose focus walk and per-tab measurements cover the new tab), and the full suite `Ran 1832 tests ... OK (skipped=13)` locally. A human still has to use the tab: steps 99-105 are its first numbered manual steps and all seven are BLOCKED.
- [x] Keep all private contact data out of the repository, tests, logs, screenshots and workflow artifacts. Every fixture address is on a reserved `.invalid` domain; the event carries counts only; the panel copies nothing and logs nothing; provenance is a file name, never a path; the JSON export does not carry the contact tables.
- [x] Do not add matching-to-jobs, email drafts, sending, reply tracking, external calls or source enabling to this increment. Nothing in `168ac31` reaches a network, and `SOURCE_QUALITY_GATE_PASSED` is still `False` with `enabled_discovery_sources()` still `()` (asserted by the CI legs and by `tests/test_sources.py`).
- [x] Give the mark a control: **Mark do not contact** / **Remove do-not-contact mark** on the HR contacts tab, enabled only for the action that would change the selected row, each confirmed once, with an optional reason stored on the record and never in a dialog, the status line or an event; zero writes on a declined confirmation, a stale selection or an injected failure, and the mark (with its reason) still shown after a re-import, a restart and a backup restore. Evidence: 12 tests in `tests/test_desktop_handlers.py::ContactMarkControlTests` (alongside the import tab's own 12), one in `tests/test_contacts_store.py::ContactPrivacyTests`, acceptance checks L6-L9, and [the control's research note](research/hr-contact-do-not-contact-control-2026-10-16.md); no schema change was needed, because the store could already represent the mark.

**Next Arena task (candidates, smallest first):** a **conflict review panel** that lists a key's recorded disagreements so the evidence already stored is readable in the window, or **per-contact deletion** with the erasure rules the rest of the app follows. Both are local and need no new table; neither is decided here - see the named gaps in [the control's note](research/hr-contact-do-not-contact-control-2026-10-16.md) and in [the persistence note](research/hr-contact-import-persistence-and-review-ui-2026-10-16.md). The completed task this line named is [the do-not-contact control](planning/arena-task-phase-0-contact-do-not-contact-control-2026-10-16.md).

## P1 — Resume intelligence and one-time onboarding
- [ ] Inspect existing resume ingestion and reuse supported PDF/DOCX/text paths.
- [ ] Normalize skills, education, graduation year, projects, experience, links, location and job-relevant facts.
- [ ] Store provenance per extracted fact and distinguish confirmed, uncertain and missing values.
- [ ] Add profile review/edit and ask only for required missing information.
- [ ] Configure target roles (AI/ML Engineer, Applied AI Engineer, AI Engineer, Forward Deployed Engineer and relevant internships), work/location preferences, eligibility, exclusions and limits.
- [ ] Never invent skills, employment, grades, legal eligibility or screening answers.

## P2 — Durable application ledger and deduplication
- [ ] Audit existing job/application/event schema and reuse it where possible.
- [ ] Define stable job/application identity across sources and discovery runs.
- [ ] Track discovered, evaluated, prepared, blocked, submitted, submission-unknown, interview, assessment, rejected, offer, withdrawn and follow-up-due states as applicable.
- [ ] Store timestamps, source URLs, external identifiers, artifact versions, decision reasons and submission evidence.
- [ ] Make side effects idempotent; reconcile uncertain outcomes before retrying.
- [ ] Test duplicates across restarts, migrations, backups and restoration.

## P3 — Source feasibility and twice-daily discovery
- [ ] Create a feasibility/permission matrix for official company career pages, supported ATS/public feeds, LinkedIn, Unstop, Internshala, Naukri.com and other relevant sources.
- [ ] For each source document permitted access, authentication, terms, rate limits, freshness, fields, failure modes and submission capability.
- [ ] Implement timezone-aware morning/evening scheduling with next-run display, run history, bounded retries, cancellation and pause/stop.
- [ ] Record posting freshness, deadline, location, eligibility evidence and canonical application route.
- [ ] Keep each source disabled until its own permission, quality and test gate passes; do not claim universal coverage.

## P4 — Tailoring and permitted autonomous applications
- [ ] Generate role-specific resume/cover letter versions from verified facts; preserve the original and version outputs.
- [ ] Validate required fields, eligibility and policy before executing an application.
- [ ] Implement only source-specific submission routes that are supported, permitted and testable.
- [ ] Allow routine submissions without per-job approval when they fit saved global authorization and require no unresolved fact or human attestation.
- [ ] Stop affected applications for missing information, sensitive/legal attestations, identity verification, CAPTCHA/OTP, platform restrictions or suspicious postings.
- [ ] Mark submitted only with evidence; represent uncertain outcomes distinctly and never blindly retry.
- [ ] Use mocks in tests; never submit real applications from tests.

## P5 — Private HR outreach and inbox reconciliation
- [ ] Connect a supported mail provider with least-privilege permissions; never store plaintext passwords or commit tokens.
- [ ] Keep HR contacts in private local storage; retain provenance and review ambiguous records.
- [ ] Enforce email normalization, duplicate checks, opt-out/suppression, prior-send checks, campaign limits and contact-level idempotency.
- [ ] Generate personalized internship outreach and attach the correct resume version.
- [ ] Enable real sending only after explicit global authorization, permission checks and end-to-end safety tests.
- [ ] With separately authorized mailbox access, track actual replies, bounces and delivery evidence; do not infer replies.
- [ ] Add follow-up intervals/limits and respect opt-outs and prior contact history.

## P6 — Reporting, safety and release
- [ ] Build dashboard for discovery runs, applications, HR outreach, replies, interviews, deadlines, blockers and next actions.
- [ ] Provide configurable run notifications and daily/weekly summaries with truthful, evidence-backed states.
- [ ] Provide pause/resume, stop-all, source revocation, export/delete and privacy controls.
- [ ] Verify backup/restore, recovery, secrets handling, logging redaction, scheduler behavior and migration safety.
- [ ] Run focused and full regression suites; report exact commands/results and limitations.
- [ ] Document only verified capabilities and source coverage.

## Next focused increment

**Completed since:** [local HR contact conflict review panel](planning/arena-task-phase-0-contact-conflict-review-panel-2026-10-16.md) - the read-only view over the disagreements schema 7 already records, in the existing HR contacts tab, with no new table, no migration and no way to resolve or merge anything. `career_agent/desktop.py`, `tests/test_desktop_handlers.py`, acceptance checks L10-L12 and the checklist's steps 99-105; commits `7323457` and `3778a39`, green matrix run `38864632201` at `4b4e752`. See [the panel's note](research/hr-contact-conflict-review-panel-2026-10-16.md).

**Next Arena task:** **per-contact deletion** with the erasure rules the rest of the app follows, or an **export of the contact list** with the same privacy review the JSON export had - both local, neither decided here. Manual GUI acceptance remains blocked until a human uses the real window on a display, and the HR contacts tab's steps 99-105 are the newest part of that.

## Non-negotiable engineering rules
- Inspect and reuse existing implementation before adding modules, schemas or abstractions.
- Keep main unchanged and do not merge/close PR #2 as part of this work.
- Do not enable live discovery, email sending or application submission before relevant gates pass.
- No CAPTCHA/OTP bypass, anti-bot evasion, prohibited scraping, fabricated profile facts or unapproved external data transfer.
- No real external side effects in tests.
- Never claim completion without code and test evidence.
