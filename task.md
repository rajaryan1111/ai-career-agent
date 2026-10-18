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
- [x] Give the mark a control: **Mark do not contact** / **Remove do-not-contact mark** on the HR contacts tab, enabled only for the action that would change the selected row, each confirmed once, with an optional reason stored on the record and never in a dialog, the status line or an event; zero writes on a declined confirmation, a stale selection or an injected failure, and the mark (with its reason) still shown after a re-import, a restart and a backup restore. Evidence: 12 tests in `tests/test_desktop_handlers.py::ContactMarkControlTests` (alongside the import tab's own 12), one in `tests/test_contacts_store.py::ContactPrivacyTests`, acceptance checks L6-L9, and [the control's research note](research/hr-contact-do-not-contact-control-2026-10-16.md); no schema change was needed, because the store could already represent the mark.

**Found and fixed while verifying this increment (both with regression tests
that fail without the fix):** **D36** - a path redaction in `career_agent/diagnostics.py` could not match a
location that continued past one of its own placeholders, so a refused backup's activity-log line kept a
folder name on Windows (the run that added the export, `38883986337` at `bdf443b`, failed both Windows legs on
that check); and a write that failed part way left a ten-byte fragment of the export at the person's chosen
path while reporting that nothing had been written. Evidence: `tests/test_diagnostics.py::PathRedactionTests`
and `tests/test_store.py::PrivateBytesWriteTests`, run `38891340290` at `546d065` (13/13 jobs).

**Next Arena task (candidates, smallest first):** a **conflict review panel** that lists a key's recorded disagreements so the evidence already stored is readable in the window, or **per-contact deletion** with the erasure rules the rest of the app follows. Both are local and need no new table; neither is decided here - see the named gaps in [the control's note](research/hr-contact-do-not-contact-control-2026-10-16.md) and in [the persistence note](research/hr-contact-import-persistence-and-review-ui-2026-10-16.md). The completed task this line named is [the do-not-contact control](planning/arena-task-phase-0-contact-do-not-contact-control-2026-10-16.md).

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
- [ ] Reconcile the current scheduler, worker, application ledger, activity events, integrations and reporting before adding new abstractions. Confirm actual remote-worker status and laptop-off limitations from evidence.
- [ ] Make the one-time global policy explicit and revocable: allowed source/action pairs, daily limits, job/role/location constraints, attachment rules, follow-up limits, quiet hours and stop conditions. Enforce it centrally immediately before every external side effect. **Mostly complete:** `career_agent/policy.py` is the decision - `(source_id, action)` pairs over the four independently gated actions, a **required** daily limit per action, quiet hours (midnight-wrapping), `stop_all` and `revoked_at`; `evaluate_policy` takes the source's own gate answer as an argument and refuses when it is closed, so a policy that names everything still opens nothing, and every refusal reason is reported rather than the first. It is now **stored** (schema 11, `policy_version`, append-only: a change appends, a withdrawal appends a version that keeps what it withdrew, a revision that changes nothing writes nothing, a damaged row raises instead of reading as permissive, and no row at all means nothing is authorised), **shown and editable** (the **Permissions & limits** tab: grant, remove, stop-all, withdraw, and *What would happen now?*, every write behind one confirmation and every decline asserted to write nothing), and **consulted** at the two sites that can act - `AdapterRegistry.execute(..., policy=, done_today=)` immediately before `call_adapter`, composed with the gate's own answer, and `integrations.authorised_dispatch(...)` as the only authorised door for an email. Both fail closed: a missing policy refuses, and a policy without today's count refuses rather than assuming zero. Evidence: 24 policy tests, 16 persistence tests, 21 wiring tests, 16 handler tests through the real window, 11 text tests, acceptance workflow **N** (N1-N6; stand-in run only - 124 checks, 0 failed, no display-backed run), manual steps 130-136 BLOCKED, suite **2303 OK (skipped=13)**, [note](research/standing-authorisation-stored-and-enforced-2026-10-18.md). **Still open:** job/role/location constraints, attachment rules and follow-up limits are not in the model; quiet hours are not editable in the window; nothing counts a day's actions from durable records yet, so `done_today` has no producer; and no external side effect is permitted today, so every wiring site refuses by construction.
- [ ] Implement/verify cross-source job identity and duplicate prevention, plus application/outreach idempotency and reconciliation of timeouts. A prior unknown outcome must block blind retries.
- [ ] Add daily/weekly report data from durable records only: last/next run, source outcomes, relevant jobs, eligibility blockers, prepared/submitted/unknown applications, outreach/bounces/replies, interview/deadline actions and failures. Never infer success from queued work.
- [ ] Add notification preferences, quiet hours, pause/resume, stop-all and revocation tests; status must be read back from the scheduler/worker rather than assumed from a click.
- [ ] Define source-specific acceptance evidence for LinkedIn, Unstop, Internshala, Naukri.com, official employer pages and any ATS/provider route before enabling it. Keep discovery, submission, outbound email and inbox reading as independent fail-closed gates; never bypass platform restrictions or human verification.
- [ ] Verify secure mailbox authorization, contact-to-opportunity linking, suppression/opt-out persistence, bounded personalized outreach, provider-result versus delivery/reply distinctions and duplicate prevention before any real sending. Use mocked providers in tests only.
- [ ] Add release evidence for laptop-off operation before claiming always-on behavior; document the remote storage/sync boundary and secure credential handling. Do not point a remote worker at the local SQLite file without a designed and tested boundary.

## Acceptance checklist for the expansion
- [ ] Resume/profile/role strategy versions and tailored artifacts remain traceable and truthful.
- [ ] Eligibility is evaluated before ranking and hard failures/unknowns cannot be overridden by fit score.
- [ ] Repeated runs, duplicate sources, repeated imports and ambiguous timeouts do not produce duplicate applications or emails.
- [ ] Daily/weekly reports reflect persisted evidence and clearly label blocked, partial, empty, failed and unknown outcomes.
- [ ] Every external capability has its own permission, quality, test, rate-limit and revocation gate; real external side effects never run in automated tests.
- [ ] Cross-platform tests and human desktop acceptance remain outstanding until actually completed; documentation must not mark them done based on CI alone.
