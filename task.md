# AI Career Agent — Product Execution Backlog

**Last updated:** 2026-10-17
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
- [x] Test migration/rollback, backup/restore, repeated imports, conflicts, suppression persistence, cancellation/no-write, confirmation, storage failure, GUI keyboard/scrolling paths and regression behavior: 39 contact-store tests (40 after the mark's own privacy test below), 3 schema tests, 12 tab handler tests, workflow **L** in `scripts/desktop_acceptance.py` (five checks on the display-backed CI legs, whose focus walk and per-tab measurements cover the new tab), and the full suite `Ran 1832 tests ... OK (skipped=13)` locally. A human still has to use the tab: steps 99-105 were its first numbered manual steps and all seven are BLOCKED (the tab now has thirteen, 99-111, after the deletion increment below).
- [x] Keep all private contact data out of the repository, tests, logs, screenshots and workflow artifacts. Every fixture address is on a reserved `.invalid` domain; the event carries counts only; the panel copies nothing and logs nothing; provenance is a file name, never a path; the JSON export does not carry the contact tables.
- [x] Do not add matching-to-jobs, email drafts, sending, reply tracking, external calls or source enabling to this increment. Nothing in `168ac31` reaches a network, and `SOURCE_QUALITY_GATE_PASSED` is still `False` with `enabled_discovery_sources()` still `()` (asserted by the CI legs and by `tests/test_sources.py`).
- [x] Delete one stored contact and the disagreements recorded about it, as one transactional store
  operation with no partial deletion: **Delete selected contact** on the HR contacts tab, greyed out until a
  stored row is selected and usable for a marked row as much as an unmarked one, confirmed once with the row's
  position in the stored list, the file the record came from and the number of disagreements that go with it -
  and with no address, name, company, stored reason or conflict value anywhere in a dialog, a status line or an
  event; a declined confirmation, a closed dialog, no selection, a stale row and an injected storage failure all
  delete nothing and say so; the record and its conflict rows go in one `BEGIN IMMEDIATE` transaction inside
  `CareerStore.delete_contact`, with the explicit conflict delete asserted *and* the declared `ON DELETE
  CASCADE` left as the second line of defence; unrelated contacts, their disagreements and their marks
  (reason included) are untouched; both views re-read from the database afterwards, which clears the selection.
  Evidence: 12 tests in `tests/test_contacts_store.py::ContactDeletionTests`, 11 in
  `tests/test_desktop_handlers.py::ContactDeletionControlTests`, acceptance checks L13-L15, [the increment's
  research note](research/hr-contact-per-contact-deletion-2026-10-16.md); no schema change, schema stays **7**.
- [x] Let a person take a copy of the stored HR contact list, as a separate user-initiated export that
  cannot disturb the version-2 JSON contract: `career_agent/contact_export.py` documents and alone writes the
  format `hr-contact-export/1` - UTF-8 with a byte-order mark, `\r\n` record separators, one row per stored
  contact with `Email`, `Name`, `Company`, `Do Not Contact` and `Export Format` (the version cell on every
  row) - and the file is written through `store.write_private_bytes_file`, owner-only where the platform has
  permissions, never through a symbolic link, and reported as written **only after it has been read back and
  compared byte for byte**. The mark travels as readable text and **an import of the file cannot set or clear
  it** (`set_contact_suppression` stays the only writer), so the format module owns one sentence -
  `MARK_COLUMN_LIMITATION` - that the window, the command and the research note all repeat, and the file is
  never described as a backup: the whole-database backup on the Data safety tab is what copies everything.
  A cell a spreadsheet would execute is written with a leading apostrophe; over 50,000 contacts or 20 MiB the
  export refuses **before a path is created** and names the backup instead. **Export the stored list...** asks
  before replacing an existing file, writes and says nothing when the dialog is closed, and reports every
  failure without claiming an export; `--export-contacts-to PATH` refuses an existing path outright. The
  database is only read (asserted against `total_changes`), and the log carries counts only
  (`contacts.exported`, `contacts.export.failed`). Evidence: 37 tests in `tests/test_contact_export.py`, 11 in
  `tests/test_cli_export_contacts.py`, 6 in `tests/test_store.py::PrivateBytesWriteTests`, 3 in
  `tests/test_contacts_store.py::ContactExportReadBackTests`, 10 in
  `tests/test_desktop_handlers.py::ContactsExportHandlerTests`, acceptance checks L16-L20, [the increment's
  research note](research/hr-contact-export-2026-10-16.md); no schema change, schema stays **7**, and
  `EXPORT_FORMAT_VERSION` is asserted to still be **2**.
- [x] Give the mark a control: **Mark do not contact** / **Remove do-not-contact mark** on the HR contacts tab, enabled only for the action that would change the selected row, each confirmed once, with an optional reason stored on the record and never in a dialog, the status line or an event; zero writes on a declined confirmation, a stale selection or an injected failure, and the mark (with its reason) still shown after a re-import, a restart and a backup restore. Evidence: 12 tests in `tests/test_desktop_handlers.py::ContactMarkControlTests` (alongside the import tab's own 12), one in `tests/test_contacts_store.py::ContactPrivacyTests`, acceptance checks L6-L9, and [the control's research note](research/hr-contact-do-not-contact-control-2026-10-16.md); no schema change was needed, because the store could already represent the mark. **Corrected (2026-10-18):** the control wrote only the contact column, which nothing enforced; it now records the address on the `contact_suppression` list `guarded_dispatch` checks, from the same confirmation, and that list is shown on the tab. Taking a mark off needs a note, refused before the question. `tests/test_desktop_handlers.py::DoNotContactListPanelTests`, acceptance L9 and L9b. Note: `research/one-mark-not-two-2026-10-18.md`.

**Found and fixed while verifying this increment (both with regression tests
that fail without the fix):** **D36** - a path redaction in `career_agent/diagnostics.py` could not match a
location that continued past one of its own placeholders, so a refused backup's activity-log line kept a
folder name on Windows (the run that added the export, `38883986337` at `bdf443b`, failed both Windows legs on
that check); and a write that failed part way left a ten-byte fragment of the export at the person's chosen
path while reporting that nothing had been written. Evidence: `tests/test_diagnostics.py::PathRedactionTests`
and `tests/test_store.py::PrivateBytesWriteTests`, run `38891340290` at `546d065` (13/13 jobs).

**Next Arena task (candidates, smallest first):** **a first tailored document built from the window** - the artifacts tab can display and rebuild lineage but nothing in the application creates the first document from a stored résumé and a strategy; or **screening answers**, which `SCREENING_ANSWERS` describes and no builder produces. Mailbox authorisation, delivery and reply evidence (P8 item 7) stay blocked on an external permission this project does not have, and so does any claim that discovery runs twice a day.

## P1 — Resume intelligence and one-time onboarding
- [ ] Inspect existing resume ingestion and reuse supported PDF/DOCX/text paths.
- [ ] Normalize skills, education, graduation year, projects, experience, links, location and job-relevant facts.
- [ ] Store provenance per extracted fact and distinguish confirmed, uncertain and missing values. The provenance half is implemented (schema 8) and the confirmation half now has a control in the window; what is still open is per-record provenance for the work-history and education tables and the rest of this phase.
- [ ] Add profile review/edit and ask only for required missing information. The profile tab now shows every stored fact with its value, origin and confirmation state, and **Set up missing required facts...** asks only for the required facts the profile does not state ([note](research/candidate-profile-fact-review-and-setup-2026-10-16.md)); normalising the remaining job-relevant facts is still open.
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
- [ ] Enforce email normalization, duplicate checks, opt-out/suppression, prior-send checks, campaign limits and contact-level idempotency. **Reachable from the window (2026-10-18):** the Follow-ups tab's *Try to send this follow-up...* is the first in-application caller of `integrations.guarded_dispatch`; the recipient can only be a stored HR contact and a suppressed address is not offered. Pressing it writes a refusal into the attempt records - `FollowUpDispatchTests` (9) pins that a full standing authorisation and a working `LocalMockIntegration` still cannot send, because the route's gate is closed in code. Giving the guard a caller exposed one defect, fixed with `RepeatedOperationTests` (4): a settled operation id is now answered rather than raised. Real sending stays blocked on an authorised mailbox. **Any address, not just an imported one (2026-10-18):** the HR contacts tab takes an address directly onto the do-not-contact list, with one confirmation, no invented contact row and the first reason kept on a repeat - `AddressNotInYourContactsTests` (6), `SuppressionAddQuestionTests` (3), acceptance L21-L22.
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

**Completed increment:** [profile fact confirmation and the missing-information setup](planning/arena-task-phase-a-profile-confirmation-and-setup-2026-10-16.md). Feature commits `982e87c`, the honesty fix `2514b52` and the scope fix `e57788e`, green on run `38914820675` (13/13 jobs, `Ran 2065 tests ... OK` per leg, `RESULT: PASS - 113 checks passed` on the five display-backed legs), on run `38925910370` at `2514b52` (`Ran 2071 tests ... OK` per leg, the same 113 display-backed checks) and on run `38933027065` at `e57788e` (`Ran 2073 tests ... OK` per leg, the same 113 display-backed checks); written up in `research/candidate-profile-fact-review-and-setup-2026-10-16.md`. The profile tab shows every stored fact with its value, where it came from and whether the person confirmed it, one control confirms the selected fact through `CareerStore.confirm_profile_fact` and reports what the database says afterwards, and the setup window asks only for the required facts the profile does not state. No schema change, no change to the version-2 JSON export, `SOURCE_QUALITY_GATE_PASSED` still `False`, `enabled_discovery_sources()` still `()`, and the six new manual steps (118-123) are BLOCKED. A second verification pass fixed three paths that could report a write that had already reached the database as "nothing was changed", and a failed read that decided what the profile states; the new coverage is in `research/candidate-profile-fact-review-and-setup-2026-10-16.md` section 7. **Next Arena task:** the parts of Phase A that no window step can close - per-record provenance for the work-history and education tables (schema 6), and the rest of P1 (normalising job-relevant facts beyond the ten profile fields and configuring target roles and preferences) - or, if the HR contact work is taken up first, the matching/drafts half of P5, which stays gated behind the same quality and permission decisions it always was.

**Completed since:** [per-contact deletion task](planning/arena-task-phase-0-per-contact-deletion-2026-10-16.md). The reported implementation deletes one selected contact and its recorded disagreements in one store transaction, preserves unrelated records, and keeps schema 7. See [the deletion research note](research/hr-contact-per-contact-deletion-2026-10-16.md). The reported CI runs `38875397574` and `38877100936` each passed 13/13 jobs; manual GUI acceptance for steps 106–111 remains blocked.

**Completed increment:** [privacy-reviewed HR contact export](planning/arena-task-phase-0-hr-contact-export-2026-10-16.md). Feature commit `bdf443b`, fixes commit `546d065`, and documentation commit `5fe30194e264967340a9c425da647fdbd924229c`. The research note [HR contact export](research/hr-contact-export-2026-10-16.md) documents the `hr-contact-export/1` CSV contract, excluded fields, suppression limitation, D36 redaction defect and partial-write cleanup. Arena reports run `38893130883` green with 13/13 jobs, 1,950 tests per unit leg, 102 display-backed checks and 20/20 mutation checks caught. The workflow-run lookup did not independently return that run for the short SHA query, so confirm the exact run/commit association before treating the CI result as independently verified. Existing JSON export stays at version 2; schema remains 7; manual GUI steps 112–117 remain BLOCKED.

**Completed increment:** [verified candidate profile and fact provenance](planning/arena-task-phase-a-verified-candidate-profile-provenance-2026-10-16.md). Feature commit `9581f81`, test-fix commit `4321458`, green on run `38903585396` (13/13, `Ran 2004 tests ... OK` per leg, `RESULT: PASS - 102 checks passed` on the five display-backed legs); written up in `research/candidate-profile-provenance-2026-10-16.md`. **Next Arena task (delivered by the increment above):** the trust dialogue it deliberately left open - a control that confirms a single stored fact in the window, with the value visible beside it, plus the setup flow that asks for the required facts a profile does not state. The next prompt in this file (below) is superseded for the profile half: Start Phase A with a migration-safe local profile model and fact-level provenance/verification, after auditing the existing implementation. Preserve backup/restore and JSON v2 compatibility; do not add resume parsing or external integrations in this increment. Keep all external-action gates closed.
**Verification repair, 2026-10-17:** before taking up another product increment, the authorized PR head was
re-run locally. A four-pixel K1 overflow in the Jobs & eligibility tab at the declared `900x600` minimum was
fixed without changing the minimum or weakening the measurement. The repository's `tests/` directory is now an
explicit package, so `python -m unittest discover -s tests` does not import an unrelated installed `tests`
package; the leak-watch child uses that same command and interpreter. The current local results are **2073
tests OK (skipped=1)**, **113/113** real-window acceptance checks, and **14/14** desktop smoke checks. The
manual checklist remains **123 steps: 22 PASS, 101 BLOCKED, 0 FAIL**. No source, discovery, email, submission or
external transfer was enabled. The next product audit remains the linked application-state import gap and
post-write resume-import outcome distinction identified by the independent code review, unless a higher-priority
release issue appears.

**Profile import follow-up, 2026-10-17:** the valid partial-profile JSON gap identified in the audit is now
fixed in `career_agent/importer.py`. Version-2 exports and imports may omit any optional profile fact,
including country and skills, without silently dropping the profile; imported values still carry imported,
unconfirmed provenance. Non-object profile shapes remain rejected. Local verification is **2075 tests OK
(skipped=1)**, including the focused importer/profile/store subset; linked application-state reconciliation
and post-write resume-import outcome reporting remain open findings.

**Application-state import follow-up, 2026-10-17:** a linked JSON listing now reconciles missing tracker,
follow-up and activity state through the existing store methods without replacing the local listing payload or
identity. Existing local tracker state is preserved; a conflicting local follow-up is refused and repeat imports
are idempotent. The focused subset ran **251 tests OK** and the full local suite **2079 tests OK (skipped=1)**;
the evidence is in [the JSON import state note](research/json-import-state-reconciliation-2026-10-17.md).

**Resume-import reliability follow-up, 2026-10-17:** post-write read-back failure and mismatch now report
**saved, but not verified** instead of **nothing was saved**. Pre-write refusal remains distinct. The review keeps
the dialog open and directs the person to inspect the Profile tab; extracted values remain unconfirmed. Focused
desktop/resume tests ran **174** and **523** tests OK, and the full local suite ran **2080 tests OK (skipped=1)**.
See [the resume-import write-verification note](research/resume-import-write-verification-2026-10-17.md).

**DOCX XML boundary hardening, 2026-10-18:** the audit reproduced a DTD/entity rejection bypass: a
declaration after the old 4 KiB byte scan, and a UTF-16 declaration, both reached `ElementTree` and
expanded an internal entity. `career_agent.resume` now performs an encoding-aware Expat preflight and
refuses a DTD before the entity set reaches the extracting parser. The focused DTD tests ran **3 OK**,
the DOCX extraction class **13 OK**, the full résumé module **86 OK**, and the repository suite **2082 OK
(1 skipped)**; `compileall`, `tabnanny`, the 14-check smoke test and 113-check real-window acceptance
harness also passed. Source-quality and external-action gates remain unchanged. Evidence: [DOCX DTD
boundary note](research/docx-dtd-boundary-2026-10-18.md).

## Non-negotiable engineering rules
- Inspect and reuse existing implementation before adding modules, schemas or abstractions.
- Keep main unchanged and do not merge/close PR #2 as part of this work.
- Do not enable live discovery, email sending or application submission before relevant gates pass.
- No CAPTCHA/OTP bypass, anti-bot evasion, prohibited scraping, fabricated profile facts or unapproved external data transfer.
- No real external side effects in tests.
- Never claim completion without code and test evidence.


## P7 — Role strategies, resume versions and artifact lineage
- [x] Inspect the current profile, resume-import, artifact/preparation and store models first; reuse existing records and migration patterns rather than creating a parallel profile or artifact store. Strategies and artifacts went through the existing one-step migration runner (schema **9** and **10**, additive, re-runnable, rollback-safe), the store's decoder/doctor pattern, the private-write primitives and the event vocabulary; see the two research notes of 2026-10-18.
- [x] Define a versioned role-strategy model with role families/title synonyms, seniority, location/work mode, employment type, compensation, hard eligibility, exclusions and explainable ranking preferences. Keep the engine industry-agnostic and treat AI/ML, Applied AI/GenAI/LLM, AI agents, FDE, data, backend, MLOps and research/vision as initial examples only. `career_agent/strategies.py`: free-text fields only, no recognised vocabulary; versions append-only with no-op revisions writing nothing; compensation bounds and employment types recorded **but not compared** (the listing model has no such field); `matching.assess_for_strategy`/`rank_for_strategy` apply exclusions and required skills as gates before ranking and locations/work modes/preferred skills as explainable factors. 27+19 tests; suite 2175 OK.
- [x] Preserve the original resume as immutable input. Link tailored resume/cover-letter/screening artifacts to the source resume, confirmed profile-fact version, role strategy version, job identity and generation timestamp. Artifacts are append-only rows (schema 10) carrying job identity, strategy version, generation time, the rendered fact basis with the unconfirmed set, **and the name of the document each fact was read out of** (`ArtifactBasis.fact_documents`, copied from provenance, a file name and never a path, absent for a value the person typed). `lineage_status` reports a citation that stopped being true (`documents_changed`) and `require_current_artifact` refuses the artifact for it. No schema change was needed: the citation rides in the same row's `fact_basis` JSON and an older row that cites nothing stays readable and current. Evidence: 10 tests in `tests/test_artifacts.py::ArtifactCitationTests`, suite 2185 OK.
- [x] Add invalidation/review behavior when a fact or strategy changes; never silently reuse a stale artifact or attach a version whose source facts are no longer current. `artifacts.require_current_artifact` is the enforcement gate (refuses with `StaleArtifactError` naming what moved - facts changed, facts confirmed since, the cited document, history changed, superseded strategy version), and the **Tailored documents** tab is where a person meets it: the row says what must be rebuilt and why, **Check before use** asks the same gate, and accepting the offer calls `artifacts.rebuild_artifact`, which appends a document built from the current facts under the strategy's newest version and leaves the stale one stored. Evidence: 8 rebuild tests, 10 handler tests through the real window, 7 text tests, acceptance workflow **M** (M1-M5; stand-in run only - no display-backed run yet), manual steps 124-129 BLOCKED, suite 2215 OK. Building it found and fixed a real defect: `revise_role_strategy` built a new version from its arguments alone, which would have silently emptied the exclusion and required-skill gates (5 regression tests). Still open, and named rather than implied: no control in this window *prepares* a new document for a listing.
- [x] Test multiple role strategies, empty/unknown facts, conflicting facts, version changes, artifact lineage, restart persistence and backup/restore. Do not add a schema migration until the current schema and required invariants are inspected. Migrations were inspected first and are appended as steps 9 and 10 with full-database upgrade, re-run and rollback tests; strategy/artifact suites cover multiple strategies, empty fields, changed and confirmed facts, version changes, lineage, restarts, backup/restore, damage reporting and privacy of logs and exports.

## P8 — Global policy, outcomes and proactive reporting
- [x] Reconcile the current scheduler, worker, application ledger, activity events, integrations and reporting before adding new abstractions. Confirm actual remote-worker status and laptop-off limitations from evidence. Audited in [note](research/operational-reconciliation-2026-10-18.md): the schedule (`tasks.py`), the worker and its lease (`worker.py`), the three handlers (`backup.snapshot`, `discovery.run` - which refuses in three separate places - and `followup.digest`), the tracker/activity/interview tables, the append-only event log and the disabled-by-default integrations all already exist and were re-verified by running them. Remote-worker status, from evidence rather than intention: `--worker` is a foreground local process, there is no service unit, no OS scheduler registration and no remote storage boundary, and `WorkerLease` is single-machine crash recovery, not a distributed lock - so laptop-off operation is **not available and not claimed**, exactly as the README already says. The one real gap the audit found was operational reporting, which is item 4 below.
- [x] Make the one-time global policy explicit and revocable: allowed source/action pairs, daily limits, job/role/location constraints, attachment rules, follow-up limits, quiet hours and stop conditions. Enforce it centrally immediately before every external side effect. **Mostly complete:** `career_agent/policy.py` is the decision - `(source_id, action)` pairs over the four independently gated actions, a **required** daily limit per action, quiet hours (midnight-wrapping), `stop_all` and `revoked_at`; `evaluate_policy` takes the source's own gate answer as an argument and refuses when it is closed, so a policy that names everything still opens nothing, and every refusal reason is reported rather than the first. It is now **stored** (schema 11, `policy_version`, append-only: a change appends, a withdrawal appends a version that keeps what it withdrew, a revision that changes nothing writes nothing, a damaged row raises instead of reading as permissive, and no row at all means nothing is authorised), **shown and editable** (the **Permissions & limits** tab: grant, remove, stop-all, withdraw, and *What would happen now?*, every write behind one confirmation and every decline asserted to write nothing), and **consulted** at the two sites that can act - `AdapterRegistry.execute(..., policy=, done_today=)` immediately before `call_adapter`, composed with the gate's own answer, and `integrations.authorised_dispatch(...)` as the only authorised door for an email. Both fail closed: a missing policy refuses, and a policy without today's count refuses rather than assuming zero. Evidence: 24 policy tests, 16 persistence tests, 21 wiring tests, 16 handler tests through the real window, 11 text tests, acceptance workflow **N** (N1-N6; stand-in run only - 124 checks, 0 failed, no display-backed run), manual steps 130-136 BLOCKED, suite **2303 OK (skipped=13)**, [note](research/standing-authorisation-stored-and-enforced-2026-10-18.md). **Still open:** job/role/location constraints, attachment rules and follow-up limits are not in the model; quiet hours are not editable in the window; nothing counts a day's actions from durable records yet, so `done_today` has no producer; and no external side effect is permitted today, so every wiring site refuses by construction. **Now complete.** The three gaps named above are closed: `GlobalPolicy` carries `role_terms`, `locations`, `allowed_attachments` and `follow_up_limit` alongside the pairs, limits, quiet hours and stop switch, all part of `content_key()` (a tightened authorisation is a different authorisation and gets its own stored version) and all round-tripped through the stored payload. `PolicySubject` describes what an action is about and is deliberately separate, so a caller that cannot describe its subject gets a **refusal rather than an exemption**; an attachment with no rule recorded is refused outright; every failed condition is reported together. `CareerStore.actions_done_today` is the missing producer for the daily limit, counted from durable `action_attempt` rows, where **a refusal does not spend the allowance it protected** and **an unknown outcome does**, with the day boundary in the person's own timezone; `integrations.COUNT_FROM_RECORDS` lets `guarded_dispatch` count for itself before it writes its own row, and counts a job's prior follow-ups for the per-job limit. Two defects were found and fixed on the way: attempts were stored as `"ActionKind.DISCOVERY"` so a caller holding `"discovery"` could never find them (the duplicate block failing quietly), and the permissions tab rebuilt the policy field by field, which would have **dropped conditions it does not display** - a silent loosening, now `dataclasses.replace` with a regression test. Evidence: 22 tests in `tests/test_policy_conditions.py`, 12 in `tests/test_attempts.py`, the desktop regression, README table, suite **2457 OK (skipped=13)**, [note](research/conditions-on-what-may-be-acted-on-2026-10-18.md). **Still open:** the window preserves conditions and quiet hours but cannot edit them (command line and API only), and no external side effect is permitted today, so every refusal fires where the gate would refuse anyway. **In the window (2026-10-18):** the conditions and the quiet window are editable on the Permissions & limits tab - role terms, places, file endings, the follow-up limit and the quiet hours - with one confirmation that lists each change in both directions, refusals before the question (half a quiet window, equal hours, something that is not a file ending), and no version written when nothing changed. `tests/test_desktop_handlers.py::PolicyConditionsTabTests`, `tests/test_desktop_logic.py::PolicyConditionTextTests`, acceptance N7-N9. Note: `research/conditions-you-can-actually-set-2026-10-18.md`.
- [x] Implement/verify cross-source job identity and duplicate prevention, plus application/outreach idempotency and reconciliation of timeouts. A prior unknown outcome must block blind retries. `career_agent/identity.py` answers "same job?" with **three** verdicts - same (employer + requisition id, a shared employer apply page, or the same listing page), different (different employers, or two requisition ids), and **unknown**, which is kept apart and reported through `possible_duplicates()` rather than merged; a similar title is never evidence, and two spellings of one id (`REQ-42` / `REQ 42`) are unknown rather than different. `career_agent/attempts.py` + schema **12** (`action_attempt`, keyed by identity, not listing) write the attempt as `unknown` **before** the act, settle it only from what was observed, and translate a *failed* dispatch to `UNKNOWN` rather than `FAILED` because a failure mid-flight may still have arrived; `may_attempt()` then refuses a further attempt while anything is unresolved or already performed, reporting every reason. Time resolves nothing: `attempts_needing_reconciliation()` only lists what a person should check, and `reconcile_attempt()` requires their evidence in words. `integrations.guarded_dispatch` is the composed door (record → refuse or begin → authorised dispatch → settle). Evidence: 22 identity tests, 43 attempt tests, suite **2368 OK (skipped=13)**, [note](research/job-identity-and-unknown-outcomes-2026-10-18.md). **Still open:** nothing in the window lists unresolved attempts or possible duplicates yet, there is no submission path to guard, and no provider is enabled, so every dispatch in the tests ends in a refusal or the local stand-in ledger.
- [x] Add daily/weekly report data from durable records only: last/next run, source outcomes, relevant jobs, eligibility blockers, prepared/submitted/unknown applications, outreach/bounces/replies, interview/deadline actions and failures. Never infer success from queued work. `career_agent/reporting.py` (`daily_report`, `weekly_report`, `build_operations_report`), surfaced as `--report` and `--report --weekly`, built from stored rows only. Three rules are pinned by tests: **queued is not done** (a scheduled task, a pending run and a *prepared* application are reported as plans, never as outcomes), **unknown leads** (unresolved attempts, timed-out runs and unverified submissions come first and are the only things counted as "needs you"; time never settles one), and **a refusal is not a failure** (a refused discovery run is reported as the permission rule working). The sources section quotes each gate's own reason, so it cannot drift from `sources.py`. Evidence: 21 tests in `tests/test_reporting.py` including a privacy check and three subprocess runs of the command, README section, suite **2389 OK (skipped=13)**, [note](research/operational-reconciliation-2026-10-18.md). **Still open:** nothing *delivers* a report anywhere - no notification, no schedule, no window tab - and replies, bounces and employer decisions appear only where a person wrote them down. **In the window (2026-10-18):** the *What's happening* tab shows this report verbatim — `headline()` and `describe()[1:]`, no second count of the same records — lists the attempts nobody settled above it, and settles one only with evidence and an explicit confirmation. `tests/test_desktop_handlers.py::WhatsHappeningTabTests`, `tests/test_desktop_logic.py::WhatsHappeningTextTests`, acceptance workflow O. Note: `research/what-has-been-happening-in-the-window-2026-10-18.md`.
- [x] Add notification preferences, quiet hours, pause/resume, stop-all and revocation tests; status must be read back from the scheduler/worker rather than assumed from a click. `career_agent/notifications.py` + schema 13 (`app_preference`, one row per named choice) + `--notifications [show|off|daily|weekly]`. **Off by default**, and a missing row reads as "no permission to interrupt" while a damaged row raises rather than falling back to a default. Six independent refusals are reported together, not one at a time: not asked for, everything stopped or authorisation withdrawn, inside the quiet hours recorded in the standing authorisation, before the chosen hour, already prepared for this period (day, or ISO week), and nothing needing the person. The read-back half is pinned separately: a pause is asserted on the task re-read from the database and is obeyed by `claim_due_run` without anything telling the worker; a resume schedules the next occurrence and leaves `list_task_runs` empty; `worker_status` reports no lease from the rows; stop-all and withdrawal are re-read from the stored authorisation, refuse an otherwise-allowed decision, appear in the report and silence notifications. Evidence: 33 tests in `tests/test_notifications.py` (four of them subprocess runs of the command), README section, suite **2422 OK (skipped=13)**, [note](research/notification-preferences-and-read-back-controls-2026-10-18.md). **Still open:** nothing *delivers* a notification - there is no email, no push and no system notification in this build, the preference has no window surface, and no scheduled task prepares the report; quiet hours are still only editable through the authorisation, not here. **In the window (2026-10-18):** the preference is set on the *What's happening* tab, read back there, and its confirmation states what it does not buy — no email, no push, no system notification, nothing while the application is closed. Quiet hours are shown there and still edited nowhere.
- [x] Define source-specific acceptance evidence for LinkedIn, Unstop, Internshala, Naukri.com, official employer pages and any ATS/provider route before enabling it. Keep discovery, submission, outbound email and inbox reading as independent fail-closed gates; never bypass platform restrictions or human verification. **Defined.** `career_agent/acceptance_evidence.py` + `--acceptance-evidence` name all six routes and nine baseline requirements each (written permission basis, dated terms and robots review with clauses quoted, stated rate limits held to the smaller of theirs and ours, an honest client identity, a no-circumvention statement checkable in the code, data minimisation, a test route, a person's own account of one complete real run - *not* a passing test suite - and a tested withdrawal path). A route may add requirements and **cannot drop one**; `held_evidence()` returns nothing for every route, so all six are outstanding on all nine, pinned by tests. The data states that the four capabilities are independently gated and that no evidence opens the source-quality gate, and a test re-asserts `enabled_discovery_sources() == ()` after it all. Evidence: 16 tests in `tests/test_acceptance_evidence.py`, suite **2480 OK (skipped=13)**, [note](research/acceptance-evidence-and-the-boundary-2026-10-18.md). **Still open:** obtaining any of this evidence is external work, so no route moves from *defined* to *ready* in this build. **Recorded, not just described (2026-10-18):** schema 15 `route_evidence` stores one row per (route, requirement) with a reference and a note; `record_route_evidence` refuses an unknown route or kind, a reference under four characters, a note under eight, and any requirement that is already held - withdrawing one needs its own reason. The new **Sources & evidence** tab shows each reviewed source with the gate's own reason for being closed, and each route's nine requirements as held or missing. `tests/test_route_evidence.py` (23), `SourcesAndEvidenceTabTests` (15), `SourceStatusTextTests`/`AcceptanceEvidenceTextTests` (9) and acceptance workflow **P** (P1-P6) all pin the same negative: recording every requirement for a route leaves `SOURCE_QUALITY_GATE_PASSED` false, `enabled_discovery_sources()` empty and every gate closed.
- [ ] Verify secure mailbox authorization, contact-to-opportunity linking, suppression/opt-out persistence, bounded personalized outreach, provider-result versus delivery/reply distinctions and duplicate prevention before any real sending. Use mocked providers in tests only. **Partly verified, with mocked providers only; the mailbox half cannot be and is not claimed.** Done: **suppression/opt-out persistence** - `career_agent/suppression.py` + schema 14 (`contact_suppression`), checked inside `guarded_dispatch` before any attempt row is written, so a blocked message leaves no record saying something was attempted; matching is on the normalised address (case and whitespace only - no dot-stripping or plus-tag removal, which would suppress somebody who never asked); **the first reason wins** so "they asked us to stop" cannot be softened on a second write; **nothing expires**; lifting needs a note and is never a side effect of an import, a retry or a cleanup; an unreadable reason still blocks; the event log records a count, never the address. **Bounded outreach**: a required daily limit counted from durable rows plus a per-job follow-up limit counted from that job's attempts. **Duplicate prevention**: cross-source identity + write-ahead attempt. **Provider result versus delivery**: a failed dispatch settles *unknown*, never sent or failed. Evidence: 20 tests in `tests/test_suppression.py`, README section, suite **2500 OK (skipped=13)**, [note](research/the-do-not-contact-list-2026-10-18.md). **Not verified, and not claimed:** secure mailbox authorisation (there is no mailbox, no OAuth flow and no credential store - the only tested statement is that nothing stores a credential anywhere), delivery and reply evidence (nothing reads an inbox, so a reply appears only where a person wrote it down), and contact-to-opportunity linking beyond the listing id a draft carries. This item stays open until a real mailbox can be authorised and verified.
- [x] Add release evidence for laptop-off operation before claiming always-on behavior; document the remote storage/sync boundary and secure credential handling. Do not point a remote worker at the local SQLite file without a designed and tested boundary. **Documented half done; the claim is refused rather than evidenced.** README section "Syncing, credentials, and what is deliberately not claimed": laptop-off operation is **not available and not claimed**, with the release evidence such a claim would need written out (a deployed worker, a tested storage boundary, a recorded run while the laptop was shut, a stated recovery behaviour for an interrupted run); the sync hazard is described rather than hinted (a SQLite file two machines open through a sync service can be corrupted by it; `WorkerLease` is single-machine crash recovery, **not a distributed lock**; pointing a remote worker at the local file is refused by design); the supported transfers are named; and **no credential is stored anywhere**. The credential claim is checked against the software, not the prose: no credential-shaped column in the live schema, no credential store imported, no credential-shaped literal in the package. Evidence: 7 tests in `tests/test_operational_claims.py`, suite **2480 OK (skipped=13)**, [note](research/acceptance-evidence-and-the-boundary-2026-10-18.md). **Still open by definition:** there is no always-on behaviour to evidence, and there will not be until a worker is deployed and a boundary designed and tested - so this item stays the documented refusal it is, not a shipped capability.

## P9 — The first tailored document, built from the window

The builders (`artifacts.tailored_resume_document`, `artifacts.cover_letter_document`) and the whole
lineage rule have existed since P7, and nothing a person could press reached them: the Tailored
documents tab could *check* and *rebuild* a document that already existed, and no part of the
application created a first one. A document that can only be made from a Python prompt is not a
feature of this application.

- [x] Choose a strategy and a listing in the window, see what the document would be built from, and
      build it: the facts used, the documents those facts came from, the facts still unconfirmed and
      the requirements the profile does not state (the gaps, never invented). **Done.** A *Build one*
      panel on the Tailored documents tab: listing chooser, strategy chooser (each line naming the
      version a document would be tied to), document chooser, and *Show what would be used...*, which
      calls `artifacts.plan_artifact` and writes nothing - the panel shows the document itself in full
      below the inputs, so what is approved is what was read. `ArtifactPlan.describe()` lists the facts,
      the files they were read from, the ones still unconfirmed, the work/education counts, the
      strategy's requirements the facts do not state and - separately - the **listing's** own
      requirements they do not state either. Screening answers are not offered and are refused by
      `plan_artifact`. Evidence: `tests/test_artifact_build.py` (23), handler tests
      `BuildingADocumentTests` (16), logic tests `BuildADocumentTextTests` (11), acceptance M6.
- [x] Review the document itself before anything is written, and write exactly what was reviewed:
      a strategy that moved, or facts that changed, between the preview and the confirmation refuses
      rather than quietly storing something else. **Done.** The window keeps the plan that was read and
      `store_planned_artifact` re-checks before any write: strategy missing or moved to another
      version, listing deleted, or `capture_basis(store) != plan.basis` each refuse with what moved
      and store nothing; the window also refuses when the choices themselves changed after the
      preview, and the confirmation repeats the preview text rather than summarising it. Evidence:
      `StoringTests`, the four refusal handler tests, acceptance M7-M8.
- [x] Refuse a duplicate: the same document, under the same strategy version, for the same listing is
      reported with the identifier of the one already stored rather than written twice. **Done.**
      `plan_artifact` sets `duplicate_of`, the preview says so, the build button stays disabled and
      `store_planned_artifact` refuses naming the stored identifier. Pressing build twice stores one
      document. Evidence: `test_an_identical_document_is_reported_rather_than_stored_twice`,
      `test_pressing_build_twice_stores_one_document`, acceptance M9.
- [x] Persist lineage - listing, strategy and version, basis, documents cited, built-at - and show it
      again when the document is reopened. **Done.** The stored artifact carries the previewed basis
      (so `lineage_status` has something true to compare against), and the row shows kind, listing,
      strategy version, built-at, cited document and state the moment it is built. Evidence:
      `test_storing_a_plan_writes_exactly_what_was_planned_with_its_lineage`,
      `test_what_is_stored_is_the_document_that_was_previewed`, acceptance M8.
- [x] Export a stored document to a file the person names, through the owner-only write this project
      already uses, **refusing to overwrite an existing file** so no original resume can be replaced.
      **Done.** *Save a copy to a file...* writes a provenance header (document id, listing, strategy
      version, built-at, cited files, unconfirmed facts, and that nothing was sent anywhere) above the
      document, through `store.create_private_file(..., exclusive=True)`. An existing file is refused
      outright - no replace prompt - and a failed write leaves nothing behind. Evidence: `ExportTests`,
      the export handler tests, acceptance M10-M11.
- [x] Refuse to export a document whose facts or strategy have moved on, with the lineage reason, and
      never silently treat it as current. **Done.** `export_artifact` calls `require_current_artifact`
      first; the button is disabled for a stale row and pressing it refuses with the lineage reasons
      before any file chooser opens. Evidence:
      `test_a_stale_document_is_refused_with_the_reason_rather_than_exported`,
      `test_a_stale_document_is_not_offered_for_saving_and_is_refused_if_asked`, acceptance M12.
- [x] Nothing in this workflow contacts anything: no upload, no send, no source enabled, no gate
      opened. Candidate text stays in the database and in the file the person chose. **Done.** The
      whole path is `store` + `artifacts` + one local file write; no integration, source or network
      call is reachable from it, and the document text never reaches the status line, the detail line
      or the event log. Evidence:
      `test_the_document_text_never_reaches_the_status_line_or_the_event_log`, and the suite-wide
      gate tests that still pin `enabled_discovery_sources() == ()`.

**Where it stands:** full suite **2706 OK (skipped=13)**; development acceptance run **155 checks,
0 failed** under the stand-in widget module (not GUI evidence - no display on this machine);
[note](research/the-first-tailored-document-2026-10-18.md).

### Post-implementation audit, 2026-10-18 (independent re-read, not the implementer's report)

Every leg of the workflow was re-traced against a throwaway database outside the test suite
(preview writes nothing -> stored content is byte-identical to the previewed content -> duplicate
refused -> export `0o600` with the id, strategy version and source file in its header -> overwrite
refused -> naming the résumé refused and the résumé unchanged -> stale export refused with no file
written -> journal holds no candidate text and no path). **Two real defects were found and fixed:**

- [x] **A cover letter reported no gaps at all**, so the preview printed "Nothing the strategy asks
      for is missing from your saved facts" while the strategy required a skill the profile does not
      state. `cover_letter_document` now computes gaps the way the résumé builder does, which also
      fixes the rebuild status line. Evidence: `test_the_cover_letter_reports_the_requirements_it_leaves_out`,
      `test_a_cover_letter_reports_the_requirements_it_could_not_claim`,
      `test_a_cover_letter_preview_names_what_it_could_not_claim`.
- [x] **The listing could be edited between the preview and the confirmation** and the document was
      stored anyway - a letter addressed to "First Employer" about a "GenAI Engineer" role, recorded
      against a listing now reading "Other Corp / Data Entry Clerk". `ArtifactPlan` now carries the
      listing it was built from and `store_planned_artifact` refuses when the employer, the role
      title or the required skills moved (fields no document reads are deliberately not compared).
      Evidence: `test_a_listing_edited_while_the_document_was_read_is_refused`,
      `test_a_changed_role_title_or_requirement_is_refused_too`,
      `test_a_listing_field_no_document_reads_does_not_block_the_build`,
      `test_a_listing_edited_after_the_preview_refuses_the_build`, acceptance **M13**.

Coverage gaps closed at the same time: a symbolic link named as the export destination (the one path
by which "never overwrite" could still overwrite a résumé - refused by `create_private_file`, now
pinned), the singular/plural experience sentence, changing the *kind* after a preview, and
`visible_text()` (the K5 label-visibility fix had no unit test of its own).

**That known limitation is now closed — see "Listing-aware artifact lineage" below.** It read: the
artifact record keeps `listing_id` but not the listing fields it was built from, so a stale-by-listing
cover letter still read as "Current".

**Assessed and deliberately not started** (step 5 of the audit brief): *choosing between several
imported résumés* has no data model behind it - the store holds one `candidate_profile` and a
`profile_fact_provenance.document_name` per fact, with no table of imported documents - so it is a
product change with a migration, not a remainder of this feature; and *richer export formats*
(DOCX/PDF) would require inventing layout this application was never given, which is the kind of
small lie the rest of the design refuses. Both stay enhancements, unstarted.

**CI at this head:** none. `.github/workflows/tests.yml` triggers on `push`/`pull_request` to `main`
only, PR #4 targets `arena/351e052d-ai-career-agent`, and `gh api .../commits/<head>/check-runs`
reports `0`. There is no green CI for this head and none is claimed.

### Listing-aware artifact lineage, 2026-10-18 (schema 16)

A tailored document is written *for a job*, and until this change the row recorded only the job's
identifier. Renaming the employer left a cover letter addressed to somebody else reading as
**Current** and exportable. Research note:
`research/listing-aware-artifact-lineage-2026-10-18.md`.

- [x] **Schema 16**: one nullable column, `tailored_artifact.listing_fingerprint`, added by step 16
      of the existing `_MIGRATIONS` table (`ALTER TABLE ... ADD COLUMN`, no table rewritten, no row
      touched, re-runnable). It holds the employer, the role title and the required skills as they
      were when the document was written, plus a sha256 of those three values in the canonical form
      the integration layer already uses. No candidate facts and no résumé text: a test asserts the
      stored JSON has exactly those four keys and contains neither.
- [x] **Existing rows get `NULL`, and nothing is back-filled.** A listing read *today* is not
      evidence of what it said last month; writing it in would have declared every old document
      verified. Evidence: `test_the_listing_step_adds_its_column_and_leaves_every_stored_document_alone`,
      `test_running_the_listing_step_again_changes_nothing`.
- [x] **Listing drift makes a document stale**, evaluated beside fact, document-citation, work,
      education and strategy drift. Employer, role title and required skills each do it
      independently; the source URL, the availability flag and the provenance note deliberately do
      not, because no document reads them. One comparison
      (`ListingFingerprint.changes_against`) now serves both the build-time refusal and the lineage
      check, so the two cannot disagree. Evidence: `ListingLineageTests` (16 tests),
      `test_a_stored_document_keeps_the_listing_it_was_written_for`.
- [x] **A document that cannot be checked is never reported current.** A row with no fingerprint
      (stored before schema 16) and a row whose listing has gone are reported as unverifiable, with
      their own wording in the window - "Cannot be checked — …" rather than "Rebuild before use —
      …" - their own export refusal title, and their own count in the summary line. Not one of the
      three states is signalled by colour. `require_current_artifact` refuses them, so none can be
      exported. Evidence: `test_a_document_stored_before_schema_16_is_never_reported_as_current`,
      `test_a_document_that_cannot_be_checked_is_not_written_out`,
      `test_a_document_with_no_record_of_its_listing_says_so_in_words`,
      `test_a_document_that_cannot_be_checked_is_not_offered_for_saving`, acceptance **M16**.
- [x] **The record is checkable, and the store is the last gate.** A fingerprint edited in the
      database no longer matches its digest and is reported as a damaged record rather than
      believed; `save_tailored_artifact` refuses a document whose fingerprint disagrees with the
      listing it is being filed under. Evidence:
      `test_a_fingerprint_edited_in_the_database_is_reported_as_damage`,
      `test_a_document_cannot_be_filed_under_a_listing_it_was_not_written_for`.
- [x] **Rebuild closes the loop**: it uses the listing as it stands, the new row is current and
      carries its own fingerprint, and the original keeps its historical record unchanged and stays
      stale. Evidence: `test_rebuilding_writes_the_current_listing_and_keeps_the_old_record_intact`,
      `test_rebuilding_a_legacy_document_produces_one_that_can_be_checked`, acceptance **M15**.
- [x] **Migration fault found and fixed on the way**: a column step run against a file whose
      recorded `user_version` runs ahead of its tables raised, leaving a database that could not be
      opened at all (exposed by `tests/test_route_evidence.py`'s version-14-with-no-tables file).
      Steps 4 and 16 now check the table exists and do nothing when it does not. Evidence:
      `test_the_listing_step_does_not_break_a_file_whose_version_runs_ahead_of_its_tables`.

**Verification at this head:** full suite **2733 tests, 0 failures, 0 errors, 13 skipped** (12 ×
"the optional pypdf package is not installed", 1 × "ai-career-agent is not installed in this
interpreter (source checkout)"). `scripts/desktop_acceptance.py --stand-in-tk` → **158 checks, 0
failed**, exit verdict `RESULT: BLOCKED` — a stand-in Tk is not a desktop and this is not GUI
acceptance. **CI at this head: none**; the workflow triggers on `main` only, and no check run exists
for this commit. Not production-ready, and not claimed to be.

## Acceptance checklist for the expansion
- [x] Resume/profile/role strategy versions and tailored artifacts remain traceable and truthful. Every artifact row cites the résumé document by name, the confirmed profile-fact version, the strategy version, the job identity and when it was generated; `require_current_artifact` refuses a stale one with `StaleArtifact` rather than reusing it, and the window surfaces the refusal and the rebuild. Evidence: P7 items 1-5 above, with their test counts.
- [x] Eligibility is evaluated before ranking and hard failures/unknowns cannot be overridden by fit score. Blocked listings are excluded from the default order and only available on request (`test_blocked_listings_are_excluded_from_the_default_order_but_available_on_request`, and the strategy-aware equivalent), an undecided eligibility is reported as undecided rather than resolved, a stated minimum not met is a failure with the gap named, and a strategy-aware score is pinned as equivalent to `evaluate_eligibility` on the plain path.
- [x] Repeated runs, duplicate sources, repeated imports and ambiguous timeouts do not produce duplicate applications or emails. Cross-source identity collapses one vacancy found on two boards into one key (and sends genuinely ambiguous pairs to `UNKNOWN` rather than merging them), the write-ahead attempt record is idempotent on `operation_id`, a prior unknown outcome blocks any further attempt until a person reconciles it with evidence, and a repeated import is bounded by the import-number rule. Evidence: P8 item 3 and `tests/test_identity.py`, `tests/test_attempts.py`, `tests/test_suppression.py`.
- [x] Daily/weekly reports reflect persisted evidence and clearly label blocked, partial, empty, failed and unknown outcomes. `--report` is built from stored rows only; queued work is labelled as a plan, a refusal is labelled as the permission rule working, an unresolved attempt leads the report, and a closing section states what the report cannot say. Evidence: P8 item 4.
- [x] Every external capability has its own permission, quality, test, rate-limit and revocation gate; real external side effects never run in automated tests. Discovery, submission, outbound email and inbox reading are independently gated; the source-quality gate is closed over all of them; the standing authorisation adds per-pair permission, a required daily limit now counted from durable rows, conditions on the job itself, quiet hours, a stop switch and withdrawal; and the written acceptance evidence for each route is recorded before any of it could be enabled. The suite blocks sockets on the import path and every integration is the local stand-in. Evidence: P8 items 2 and 6.
- [ ] Cross-platform tests and human desktop acceptance remain outstanding until actually completed; documentation must not mark them done based on CI alone. **Honoured, and still outstanding.** The manual GUI checklist stands at **136 steps - 22 PASS, 114 BLOCKED, 0 FAIL**: every step needing a display is BLOCKED on this machine and is recorded as BLOCKED, never as passed. No display-backed acceptance run has executed workflows M or N. CI does not run for this branch at all (its triggers are main-only), so nothing here is marked done on the strength of CI, and the README's packaging section continues to separate the three levels (stubbed handlers, a scripted smoke test under a real display, and a person at the keyboard) rather than letting the first stand in for the third.
