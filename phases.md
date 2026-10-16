# Research and Delivery Phases

**Status:** Production-oriented implementation and evidence-gated source research in parallel  
**Last updated:** 2026-10-14

## Product north star

Deliver a downloadable, maintainable career-automation product that real candidates can use—not a demo-only prototype. It should serve candidates across industries and experience levels through a shared core plus extensible occupation-specific intelligence. It should search on a configurable schedule (default 00:00 and 12:00 Asia/Kolkata), and laptop-independent operation requires a separately verified always-on worker. Selection is an employer decision and is never guaranteed.

## Phase 0 — Product contract and risk controls

**Status: Complete** (audited 2026-10-16 — see [Phase status](#phase-status-audited-2026-10-16)).

**Goal:** Keep the product promise, user control, safety boundaries, and measurable quality criteria consistent across all six canonical documents.

Tasks: maintain the cross-industry scope; distinguish implemented, gated, experimental, and production-supported capabilities; preserve candidate truth, privacy, source permission, and evidence-backed application state.

Exit criteria: PRD, architecture, rules, design, and memory agree; no stale statement says implementation is unauthorized or that the product is research-only.

## Phase 1 — Usable local desktop workflow

**Status: Partially complete** — the workflow is implemented and driven end to end automatically; the
manual GUI half of its exit criterion is outstanding (audited 2026-10-16).

**Goal:** Turn the existing offline core into a usable end-to-end local application.

Tasks: implement the chosen Python/Tkinter local shell; candidate profile editing; manual job entry; hard eligibility and explainable matching; shortlist; application ledger/status evidence; persistent SQLite storage; export/delete; and clear unsupported-source states. Resume parsing is deliberately deferred to a follow-on local-only increment so it does not block a complete, testable first workflow.

Exit criteria: a user can configure a profile, add and evaluate a job, shortlist only an explicitly eligible job, track application state with evidence for confirmation, export/delete local data, restart the app, and find saved state intact without a network connection or paid API. Automated tests and manual GUI smoke tests cover critical workflows and invalid inputs. The manual half now has a run-book: [the human desktop acceptance handoff](research/human-desktop-acceptance-handoff-2026-10-16.md). This is an internal local alpha, not the final product. The manual test protocol is recorded in [the local-alpha smoke-test checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md); it must be executed before GUI acceptance is claimed.

### Phase 1B — Local resume import and profile review

**Status: Partially complete** — implemented locally and tested automatically; no human has run the review
dialog, and OCR is deliberately out of scope (audited 2026-10-16). A stored profile fact now carries
**where it came from** (typed, read out of a local document, or imported) and **whether the person
confirmed it**, in the database beside the value (schema 8): a value read out of a document or imported
from a file is stored and reported as unconfirmed, a write records an origin only for the facts it
changed, and a profile stored before this existed reads as *unknown* rather than as the person's own
words. The control that confirms a single fact in the window, and the setup flow that asks for the
required facts a profile does not state, are the remaining piece; the JSON export keeps its version-2
shape and does not carry the origins. Verified on the whole matrix: run `38903585396` at `4321458`, 13/13 jobs,
`Ran 2004 tests ... OK` per leg and `RESULT: PASS - 102 checks passed` on the five display-backed legs; the run
that found the one wrong assertion in the four cross-platform legs is `38901274611`, and the defect is written up
in `research/candidate-profile-provenance-2026-10-16.md`.

Add PDF/DOCX parsing only after the profile/job workflow is stable. Parsing must run locally, retain source text/field provenance where practical, mark uncertain fields for user review, and never silently promote extracted guesses to verified facts. OCR remains optional and must not become a mandatory paid dependency.

## Phase 2 — Product reliability and security foundation

**Status: Partially complete** — migrations, backup/restore, owner-only file permissions, redacted logs, data
export, data deletion for every file this application derives (`--forget-local-data`), the
[threat model](research/threat-model-2026-10-16.md) and packaging metadata exist; encryption at rest and a
release/upgrade policy do not (audited 2026-10-16; threat model and the deletion command added the same day).

**Goal:** Make the application recoverable, maintainable, and safe before external actions are enabled.

Tasks: schema migrations; backup/restore; secure secret storage; redacted logs; data export/deletion; packaging/install/update strategy; threat model; test fixtures; crash recovery; adapter capability/status UI; and regression tests.

Exit criteria: repeatable installation and recovery tests pass; privacy/security boundaries are documented and enforced; no secrets or real candidate data enter source control or test fixtures.

## Phase 3 — Source permission and job-quality validation

**Status: Blocked** — the gate is closed and no source has current permission evidence; nothing may be
enabled from this state (audited 2026-10-16).

**Goal:** Prove that source integrations are permitted and useful, not merely technically reachable.

Tasks: finish the 50-record validation sample; measure direct employer application-link outcomes using a defined denominator; validate source terms and attribution/caching/rate limits; prove source-level error semantics; and identify a minimum set of useful permitted sources. Keep discovery and submission permissions separate.

Exit criteria: documented evidence for each enabled source; quality thresholds met or explicitly revised with rationale; unresolved providers remain disabled. The current source-quality gate remains NOT PASSED until the research record says otherwise.

**What would have to be true to leave this state (2026-10-16).** Three things, none of which this
repository can produce by itself: (1) each candidate source's own terms re-read and recorded with a date
and a quotation in `research/source-permission-decision-matrix-2026-10-14.md`, with the
permission/accuracy decisions kept separate; (2) the 50-record validation sample finished with a stated
denominator and its outcome recorded in `research/source-quality-gate-assessment-2026-10-14.md`; (3) an
explicit decision that the gate's thresholds are met. The gate code is `career_agent/sources.py:30`
(`SOURCE_QUALITY_GATE_PASSED`) and `enabled_discovery_sources()` stays empty until those records exist —
nothing in the codebase needs to change to keep it closed, and nothing may be enabled while it is.

Matching is implemented as a transparent comparison rather than a score:
`career_agent/matching.py` reports required-skill overlap, the experience range, a stated qualification,
location, work mode and role type as pass/partial/fail/unknown/not applicable, each with its evidence,
and returns a score *with the coverage that produced it*. Below half of the applicable weight known the
reading is "not enough information", a "strong" reading needs two thirds, and the ranking order puts
listings that could be compared first so a barely-known listing cannot outrank a compared one. Nothing is
inferred: silence about skills or a location is not a pass, equivalence between different skill names is
used only when a caller supplies it, and compensation is not compared at all because the domain model has
no such field (recorded as outstanding). The window shows these lines with the eligibility report, from
the same evaluation. Synthetic fixtures cover software/data, embedded/VLSI, mechanical, civil, design, a
sparse record and a near-silent listing; the ranking has not been validated against real outcomes, and
nothing in the product is calibrated to one industry's vocabulary.

## Phase 4 — Cross-industry matching validation

**Status: Partially complete** — a privacy-safe, reviewed evaluation set and a reproducible harness now exist
([the run](research/cross-industry-evaluation-run-2026-10-16.md)): 7 occupation groups, 21 synthetic listings
with a stated review order, engine agreement 7/7, **zero** hard-eligibility violations, and 22/22 stated
values extracted from 7 synthetic résumés. Running it found five real extractor defects (D21–D25, each fixed
with a fail-before test); **the corpus is synthetic and small, so the thresholds remain measured, not
achieved for the product** (audited 2026-10-16, corpus added the same day).

**Goal:** Ensure the product is not effectively an AI/ML-only tool.

Tasks: create privacy-safe, human-reviewed resume/job-description test sets across representative domains (for example design, VLSI/embedded, mechanical, civil, software/data, and business); define occupation-aware skill and credential schemas; evaluate extraction and top-ranked relevance separately from hard eligibility.

Proposed initial thresholds (not yet achieved):
- At least 95% exact extraction accuracy on selected critical fields for parseable resumes.
- At least 80% precision in the top 10 recommendations against a predefined human-reviewed relevance standard.
- Zero known hard-eligibility violations among recommendations marked eligible.
- No duplicate submissions caused by retries.
- No confirmed status without reliable evidence.

Exit criteria: reproducible evaluation results and explicit coverage gaps by occupation group.

## Phase 5 — Background execution and scheduled discovery

**Status: Partially complete** — the engine and both local surfaces exist and are tested; a deployed
always-on worker and laptop-off operation are unimplemented and unverified; what was missed is now reported, not run (audited 2026-10-16).

**What would have to be true to finish this phase (2026-10-16).** The missing half is deployment, not
code: a host that stays up, a decision about whether the person's data may leave their machine, and the
disclosure that goes with it. The rules that govern it are already written — any remote worker must
document what leaves the machine, minimise it, require explicit opt-in with a disable/revoke path, and
default to synthetic fixtures — so the next step is a decision by the project owner plus an environment
to deploy into, not a change to `career_agent/worker.py`. Until that decision exists, `--worker` remains a
foreground process on the person's own machine, and the occurrence report above is what keeps a missed
slot visible instead of silent.

**Goal:** Deliver reliable 00:00/12:00 IST runs, including when the user's laptop is off.

Tasks: design a durable queue and worker boundary; compare free/low-cost always-on deployment options; implement health status, missed-run catch-up, idempotent processing, bounded retries, rate limits, and per-source outcome reporting; clearly disclose any remote data transfer and provider limits.

Exit criteria: observed scheduled runs, laptop-off behavior, restart recovery, duplicate prevention, and outage reporting are tested in the chosen deployment. Do not claim this capability until verified.

The adapter framework is implemented and tested (`career_agent/adapters.py`, reported by
`python -m career_agent --sources`): declared capabilities with submission refused by construction, a
bounded request budget with pacing, retries for transient outcomes only, normalisation that validates
each record and reports every rejection, cross-source deduplication on the app's canonical identity, and
run outcomes that keep success/empty/partial/failure apart. **No adapter is implemented, because no source
has passed both reviews**, so live discovery stays disabled and the framework has never made a network
request. Fixture adapters are the only ones in the repository.

## Phase 6 — Permitted platform adapters and application automation

**Status: Blocked** — the framework exists, zero adapters are built in, and no source has passed both
reviews (audited 2026-10-16).

**Goal:** Expand from manual/local workflow to real, validated application flows.

Tasks: begin with read-only discovery adapters only after each source's permission gate passes; validate listing freshness and direct application routes; implement platform-specific preparation/submission adapters only when permitted; configure standing user policies; record all actions and evidence; pause only the affected workflow on uncertainty and continue independent safe work.

Exit criteria: each advertised source/workflow has current permission evidence, deterministic fixtures, integration tests, failure recovery, duplicate protection, and real-world pilot validation. CAPTCHA/OTP, access-control, anti-bot, and employer restrictions are never bypassed.

**What would have to be true to leave this state (2026-10-16).** Phase 3's exit criteria first — an
adapter cannot be permitted before its source is — and then, per adapter: any credential obtained from the
person with an explicit opt-in and a revocable store (which does not exist yet and would be a new threat
model section, not an extension of the current one), deterministic fixtures that need no live service,
integration tests that prove duplicate protection and failure recovery, and a real-world pilot with
recorded evidence. Submission automation additionally needs a separately authorized workflow; until then
`scripts/desktop_acceptance.py` and the CLI keep the local mock as the only thing that performs anything.

## Phase 7 — Email, interview lifecycle, and career intelligence

**Status: Partially complete** — reminders, interview rounds, read-only drafts/previews, calendar export and
analytics are implemented without any integration; a real provider connection is not (audited 2026-10-16).

**Goal:** Support the journey beyond initial application without expanding permissions silently.

Tasks: optional least-privilege email integration; confirmation and interview detection; follow-up drafts/reminders; job-specific truthful resume/cover-letter versions; company research with evidence; and career analytics that separate activity metrics from outcomes.

**Started, deliberately without the integration (2026-10-15).** The parts of this phase that need no
permission are implemented: follow-up email drafts built from an application's own recorded context, previews
of the calendar output before anything is written, and the typed contract a real provider would have to
satisfy (prepare / preview / perform, with an explicit result and a stable operation id). Every path to an
external side effect is closed: the default integration refuses with a reason, no configuration selects
another, and the only implementation that performs anything is a local mock that records operations in a local
ledger and contacts nothing. Enabling a real provider stays gated on the seven conditions
`--integration-status` prints, which is the same evidence-first rule the source gate uses. The remaining tasks
of this phase - confirmation and interview detection from real email, and any account connection - stay
unstarted and untested, and the docs say so rather than implying a capability.

Exit criteria: integrations are revocable, external data boundaries are explicit, and all generated claims are traceable to verified candidate facts or cited sources.

## Phase 8 — Pilot, release, and continuous maintenance

**Status: Not started** — no pilot, no packaged or signed release, and no human desktop acceptance on any
platform (audited 2026-10-16).

**Goal:** Prove the product useful in real life and keep it working as sources change.

Tasks: pilot with consenting users from more than one occupation group; measure time saved, matching quality, form/adapter failure rates, application integrity, user trust, and response/interview outcomes without promising selection; establish release notes, versioning, support/error reporting, and periodic platform-policy reviews.

Exit criteria: installation, upgrades, recovery, privacy/security checks, and pilot acceptance criteria pass; release claims match tested coverage; unsupported roles/sources are labeled honestly.

## Phase status (audited 2026-10-16)

Every status below was re-derived from the evidence named beside it, at commit `e18c6d2` plus the working tree
of that date. **Statuses were not changed to make the roadmap look finished, and a phase whose exit criteria
mention a real desktop, a real source or a packaged release is not "complete" because its code exists.** The
distinction the whole table turns on: *implemented* ≠ *automated-tested* ≠ *human-accepted* ≠ *release-ready*.

| Phase | Status | Evidence, and what is missing |
| --- | --- | --- |
| **0 — Product contract and risk controls** | **Complete** | `prd.md`, `architecture.md`, `rules.md`, `design.md`, `phases.md`, `memory.md` and `README.md` agree; no document says the implementation is unauthorized or research-only. |
| **1 — Usable local desktop workflow** | **Partially complete** | The workflow exists and is exercised end to end automatically: **twelve** workflows and **97** checks in the current source, on five display-backed CI legs. The current revision is green on the whole matrix too: run `38828908041` at `02962f6`, **13/13 jobs**, `RESULT: PASS - 87 checks passed` and `RESULT: PASS - 14 checks passed` on every display-backed leg, workflow **L** (`[ ok ]` L1-L5 on the Linux job and the same workflows on the other four legs), and `Ran 1832 tests ... OK` per leg (skips 13 on 3.10-3.14 as recorded there: 20 on macOS 3.10, 39 on Windows 3.13, 46 on Windows 3.10). The run before it, `38823626117` at `3a88e6e`, is the 82-check/1778-test state that measured layout green for the first time on all five legs. The increment that added the do-not-contact controls moves the source to **91** checks and 1845 tests and is green on the same matrix: run `38855211961` at `2d237bc`, **13/13 jobs**, `RESULT: PASS - 91 checks passed` with workflow L's L1-L9 `[ ok ]` and `Ran 1845 tests ... OK` per leg. The panel moved the source to **94**
checks and 1857 tests, green on the same matrix (run `38864632201` at `4b4e752`). **Per-contact deletion**
moves it to **97** checks and 1881 tests - the destructive control on the HR contacts tab, the
confirmation that names a row and a file instead of a person, and the store's one-transaction deletion of a
record with the disagreements recorded about it - and is green on the same matrix: run `38875397574` at
`c1b2ab1`, **13/13 jobs**, `RESULT: PASS - 97 checks passed` with workflow L's L1-L15 `[ ok ]` and
`Ran 1881 tests ... OK` per leg. **Exporting the stored contact list** moves it to **102** checks and 1950
tests - the CSV format the window and `--export-contacts-to` both write, its byte-level rules, the read-back
that has to pass before success is claimed, and the documented limitation that an import cannot apply the
do-not-contact column - and is green on the same matrix: run `38891340290` at `546d065`, **13/13 jobs**,
`RESULT: PASS - 102 checks passed` with workflow L's L1-L20 `[ ok ]` and `Ran 1950 tests ... OK` per leg. That
run also carries the fix for **D36**, a path redaction that kept a folder name in the activity log when a
location continued past one of its own placeholders (found by the two Windows legs of run `38883986337` at
`bdf443b`, which failed the new L20 check and nothing else). The exit criterion "automated tests **and manual
GUI smoke tests** cover critical workflows" is **half met**: no human has run the window on any platform, so all
95 window steps of the checklist stay BLOCKED (22 steps passed, all of them needing no window); nineteen of the
blocked steps are new for the HR contacts tab - its recorded-disagreement panel (99-105), the deletion control
that removes one stored contact with its evidence (106-111), and the export of the stored list (112-117) - a tab
that had no numbered steps before. |
| **1B — Local resume import and profile review** | **Partially complete** | Implemented locally and text-only: `career_agent/resume.py` extracts from DOCX with the standard library and from PDF through the optional `pypdf`, proposes values with their evidence and confidence, and writes **only** the values the person selects and confirms, recording each saved fact's origin
and unconfirmed state (schema 8). Automated coverage: the reader and proposal layers, encrypted/damaged/empty/oversized/textless refusals, a socket-blocked local-only run, and workflow H/I-independent handler tests for the review dialog. Missing: a human import review through the real window (checklist steps 24–31, all BLOCKED), a scanned-PDF path (OCR is deliberately out of scope, so a textless PDF is refused), and the 12 PDF-dependent tests skip in a checkout without the `pdf` extra. |
| **1C — HR contact list: offline preview, local import and review UI** | **Partially complete** | Phase 0 of `planning/hr-contact-outreach-and-application-tracking-2026-10-16.md`, parse → review → store, all offline. `career_agent/contacts.py` reads one CSV the person names with the standard library's `csv`, handles a UTF-8 BOM, validates the header explicitly, keeps every source string and computes the comparison key from the email alone (trim + case-fold), groups rows by that key, flags empty/malformed addresses, missing names, shared keys and conflicting company labels, and refuses ambiguity rather than resolving it; `--preview-contact-csv PATH` reports counts, flags and line numbers and **prints no contact value**, opening no database and writing no file (48 tests in `tests/test_contacts.py`, all synthetic and on reserved `.invalid` addresses). Schema **7** adds `hr_contact` and `hr_contact_conflict` through the existing migration runner, with the pre-upgrade verified snapshot, an additive step that is re-runnable after an interruption and a rollback that leaves the version and the rows untouched (3 tests in `tests/test_store.py::SchemaMigrationTests`, one of them on a populated version-6 file). `CareerStore.plan_contact_import` computes what an import would change having written nothing, `CareerStore.import_contacts` writes it as one transaction, one record per email key however many rows mention it, and `CareerStore.set_contact_suppression` is the only writer of the do-not-contact column (40 tests in `tests/test_contacts_store.py`, including zero-write assertions against the connection's change counter, an injected storage failure, and privacy assertions that no fixture value reaches a log or a summary). The window's **HR contacts** tab reads the file through that parser, shows the counts and the rows worth a look, asks once with the plan in front of the person, and reports only what was stored; the smoke entry point now checks **nine** tabs and the acceptance harness runs a twelfth workflow over the tab. **Missing, deliberately:** a human pass over the tab (its checklist steps stay BLOCKED), row-by-row accept/reject while reading, exporting refused rows, resolving or dismissing recorded disagreements from the window, keeping more than the current mark (its date and one reason) per contact, matching contacts to listings, drafts, and every external action - the last group also waits on the closed source gate. The **do-not-contact controls** are implemented: the two buttons beside the stored list, enabled only for the action that would change the selected row (and reachable by the keyboard exactly then), each confirmed once and each asserted to write nothing when declined, with the optional reason stored on the record and nowhere else, and the mark shown after a re-import, a restart and a restore (12 handler tests in `tests/test_desktop_handlers.py::ContactMarkControlTests`, one privacy test in `tests/test_contacts_store.py`, and checks L6-L9 of the acceptance workflow). **Per-contact deletion** is implemented on the same tab: the control is greyed out until a stored row is selected and usable for a marked row as much as an unmarked one; the confirmation names the row's position, the file it came from and how many disagreements go with it and no contact value; `CareerStore.delete_contact` removes the record and the `hr_contact_conflict` rows carrying its key inside one `BEGIN IMMEDIATE` transaction, reporting counts and writing `contacts.deleted contacts=1 conflicts=N`; declining, closing, no selection, a stale row and an injected storage failure all delete nothing, and every refusal is asserted against the connection's change counter; 12 store tests, 11 handler tests and checks L13-L15 of the same workflow. **Exporting the list** is implemented as its own format: the `hr-contact-export/1` CSV (UTF-8 with a byte-order mark, CRLF record separators, address/name/company/the mark as readable text/a version cell), written owner-only where the platform supports it and never through a link, reported only after being read back and compared byte for byte, refusing before it creates anything when the list is over the reader's own limits, and refusing an existing path outright on the command line while the window asks before replacing one; the do-not-contact state travels as text and **no import can set or clear it**, which the window, the command and the note all say in the format module's own words, and the whole-database backup is named as the copy that *does* carry the marks; 37 tests over the format and its bytes, 11 over the command, 6 over the writer, 3 read-back tests and 10 handler tests, checks L16-L20 of the same workflow. **Still missing, deliberately:** bulk deletion, deleting from anywhere but the selected row, exporting only selected rows, importing a do-not-contact mark from a file, and a human pass over the tab. |
| **2 — Product reliability and security foundation** | **Partially complete** | Schema migrations with a pre-update verified snapshot and honest refusals (newer/unrecognised files refused by type), backup/restore with validation, owner-only export and database permissions where the platform has them, redacted one-line event log, JSON export/import with a preview plan, packaging metadata and an installed-command rehearsal on three platforms. Missing: **encryption at rest**, a written release/upgrade policy beyond the README's data-compatibility section, a diagnostics/threat-model document, and per-platform launch artefacts. |
| **3 — Source permission and job-quality validation** | **Blocked** | The gate is closed (`SOURCE_QUALITY_GATE_PASSED = False`) and `enabled_discovery_sources()` is empty, by design: the 50-record validation sample is not finished, and no source has current permission evidence. Nothing may be enabled from this repository state. |
| **4 — Cross-industry matching validation** | **Not started** | Transparent matching exists (`career_agent/matching.py`) with synthetic fixtures across software/data, embedded/VLSI, mechanical, civil, design, a sparse record and a near-silent listing — but the phase's own thresholds (95% extraction accuracy, 80% top-10 precision against a human-reviewed standard) need human-reviewed, privacy-safe test sets across occupations. No such set exists and no threshold is claimed as met. |
| **5 — Background execution and scheduled discovery** | **Partially complete (foreground and local only)** | The scheduler engine, the task/run/lease schema, crash recovery as *interrupted*, retries that never retry a refusal, the two built-in handlers and both surfaces (`--worker` in the foreground and the window's **Background tasks** tab) are implemented and tested, and the window's tab is now driven end to end by workflow I. **A deployed always-on worker and therefore laptop-off operation remain unimplemented and unverified** — the phase's exit criterion is not met, and a foreground worker is not an always-on one. What the schedule walked past while nothing ran is now *reported* (`worker.missed_occurrences`, surfaced by `--worker-status` and the window's Background tasks tab, checked through the real window by workflow I9) — reporting a missed occurrence is not running it, and nothing catches up on one. |
| **6 — Permitted platform adapters and application automation** | **Blocked** | The adapter framework is implemented (capabilities with submission refused by construction, bounded request budget, retries for transient outcomes only, per-record validation, cross-source dedup, honest run outcomes) and 0 adapters are built in, because no source has passed both reviews. Live discovery and any application automation stay disabled. |
| **7 — Email, interview lifecycle and career intelligence** | **Partially complete** | Implemented without any integration: follow-up reminders and the next-action list, interview rounds with an outcome vocabulary that has no `passed`/`rejected`, typed draft/preview/perform contracts whose only implementation is a local mock that contacts nothing, calendar export and its preview, and activity-vs-outcome analytics that names denominators and refuses to print unobservable metrics. Missing: any real provider connection, confirmation/interview detection from real email, and résumé/cover-letter versions per application. |
| **8 — Pilot, release and continuous maintenance** | **Not started** | No pilot user, no consenting participant, no release notes process, no packaging/signing/notarisation, and no human desktop acceptance on any platform. Nothing is deployed. |

**Set beside each other, the four claims this table keeps apart:**

* **Implemented:** the domain core, storage, migrations and backup/restore, the Tk window with its tabs, the
  scheduler engine, the adapter framework, analytics, export/import, résumé reading, the event log.
* **Automated-tested:** 2004 unit and integration tests plus the two scripted desktop entry points, green on
  five display-backed legs and four interpreter versions — **and the checks are about records, widget cells and
  status lines, never about pixels, wording or focus**.
* **Human-accepted:** **nothing.** No person has opened this window on any platform.
* **Release-ready:** **nothing.** There is no packaged, signed or notarised build on any operating system, and
  one has never been attempted.

## Current implementation status

The offline domain core, the SQLite persistence layer, verified local backup/restore, local-first
résumé import (PDF and DOCX), and the Tkinter local desktop alpha (`python -m career_agent`) are
implemented, with 2004 tests passing locally (13 skipped in a checkout: 12 of them need the optional
`pypdf` library and one runs only where the project is installed) and a
Python 3.10–3.14 CI workflow running the suite, compilation checks, and the research-CSV audit, plus a
second job that builds the wheel, checks its contents, installs it into a clean environment, and runs
the installed `career-agent` command from outside the checkout — on the declared floor (3.10) and on the
newest interpreter the suite is run on (3.14), because a wheel or a console script that only works on the
version that built it is exactly what installing from a checkout hides. The suite also holds the safety properties an audit
turned up by probing rather than reading: a non-finite experience value (`nan`, `inf`) is refused by
the form and can never make an experience requirement pass, no test may resolve this machine's real
database path, every malformed or mis-shaped restore target is refused with the current database left
byte-identical, the window-closing path writes nothing, and the confirmation-evidence floor refuses
phrases that describe trying the feature rather than what an employer showed. A stored record whose
payload this version cannot read (an unknown field, damaged JSON, a bare string where a list belongs) is
refused as one named error with a plain message instead of a raw `KeyError`/`TypeError`/JSON error, on
every read path and in every view, and nothing is repaired or rewritten; a failure to verify a profile
save *after* the write is reported as unconfirmed rather than as "nothing was saved". Résumé reading
refuses a password-protected or unreadably compressed DOCX with its own message, and the import handler
reports an unforeseen reader failure by name instead of letting it escape a Tk callback, so no unreadable
document can end in a traceback; start-up diagnostics hide any absolute location quoted by a failure,
not only the locations a command named. The tests cover the domain rules, persistence (including file-backed restart durability), untrusted-URL validation, the fail-closed source permission gate and run-outcome rules, the tracker confirmation-evidence
floor and the backed-up record-correction tool, owner-only export
permissions, stale-selection handling, the status chooser's option set measured against the state machine, unrecognised stored statuses and the refusal paths they trigger, stored records this version cannot read (an unknown field, damaged JSON, a string where a list belongs, a listing with no saved availability status) on every read path and in every view, stored-timestamp rendering (missing, offset-less and unparseable values), version reporting and start-up diagnostics (including path redaction for the database, the home folder, and any file named on the command line), backup and restore (verified snapshots, corruption and
schema-version refusals, POSIX permissions, WAL and side-file handling, the command-line front end),
résumé extraction and proposal parsing (DOCX paragraphs and tables, database-engine-free PDF fixtures,
encrypted, damaged, empty, oversized and textless input, refusal to guess, and a socket-blocked
local-only run),
the Tk-free desktop logic (including platform data-folder resolution, where a relative `XDG_DATA_HOME` or `LOCALAPPDATA` is ignored as the base-directory specification requires so the database path never depends on the working directory), and the desktop handlers through widget stubs, including the review screen
that shows every proposal with its evidence before a single value can be written. They also hold the SQLite
resource lifecycle: a child process re-runs the whole suite counting connections that were never
closed (the macOS `ResourceWarning: unclosed database` came from exactly that, and Python 3.10/3.11
never emit the warning), and a source scan refuses `with sqlite3.connect(...)`, which manages the
transaction and never closes the connection. They do not cover widget
rendering, dialog wording, layout, or a person using the window. What CI does add since 2026-10-15: the suite
and a scripted desktop smoke test run on a Linux runner under a real virtual display (Xvfb, where the window
must be built and driven and a run without a display must report BLOCKED), and the suite, the résumé tests
with the optional `pypdf` extra, and the installed-command rehearsal run on real Windows and macOS runners.
The manual GUI smoke test — including macOS/Apple Silicon — remains outstanding, and no automated run closes
a step of it. Running those legs for the first time found three defects rather than confirming the status quo,
which is the point of running them: the sync between a notebook's tab names and the widgets they name, the
owner-only mode applied on a platform that has none, and six doctor tests that assumed Linux's folder name.
Each was reproduced, fixed and given a regression test that fails on the behaviour it replaced.

The application activity log is implemented end to end: schema version 2 adds
`application_activity`, `ApplicationActivity`/`ActivityKind` define a dated entry whose detail is
validated at the domain *and* storage boundaries, the store appends, lists oldest-first and deletes
entries and cascades them with their listing, the desktop Tracker tab has an activity panel with an add
dialog and a delete confirmation, and the JSON export carries the log as stored (marking a kind this
version cannot label instead of blocking the export). An entry is deliberately not evidence: it cannot
change a status, create a tracker record, or satisfy the confirmation floor — each of those is a test.
The dates are used: a follow-up day is recorded against an application, the **Follow-ups** tab and the
**Next actions** list surface it, the `followup.digest` task reports the ones that are due, and the calendar
export writes them locally. What is not implemented is an operating-system notification or any alert that
could reach a person while the window is closed.

Local JSON export and import are implemented as one versioned format owned by `career_agent/importer.py`,
with a plan the caller must show before anything is written. Export is the same document it always was
(profile, listings, application records, follow-up days, activity) plus `EXPORT_FORMAT_VERSION`, written
owner-only through the store's private-write path and still refusing to replace an existing file or to
follow a symbolic link; the window's *Data safety* tab and `--export-to` both call that single function,
so the two surfaces cannot produce different files. Reading a file back is the new part: `read_export`
refuses a missing path, a folder, non-UTF-8 bytes, invalid JSON (with line and column), a document that is
not an object, a missing or different format version, and a non-list `jobs` value before any write is
attempted; `plan_import` is read-only and returns what would be added, linked, kept or refused;
`apply_import` recomputes that plan instead of trusting the caller. The rules it keeps are the point:
the profile is imported only into an empty profile, a stored listing is linked by the same duplicate key
the rest of the app uses and keeps its first-seen time, an application record is always created at
`discovered` while a later status in the file is *reported* as not imported (a status here is only ever
reached through the guarded transition path, and the store's initial-status rule was not weakened for
imports), a follow-up day travels as data and an unreadable day or history entry is reported rather than
dropped, and activity is appended with (day, kind, text) deduplication so importing the same file twice
cannot double a timeline. Both surfaces are wired: the *Data safety* tab has **Import an exported file
(JSON)**, which shows the plan and asks before applying, and `--import-from PATH` dry-runs unless `--yes`
is given, refusing before it touches a database that does not exist. `import.written`, `import.refused`
and `import.failed` join the event log, so an import that changed the data is as visible as any other
write.

Configuration and diagnostics are implemented for the local alpha: `career_agent.config` resolves the
database path from one rule (an explicit path, then the `CAREER_AGENT_DATABASE` setting, then the data
folder chosen by `CAREER_AGENT_HOME` or the platform), creates nothing while resolving, creates only the
default folder when a run needs it, and reports an ignored relative setting instead of resolving it
against the working directory. The window, the backup/restore commands and `--doctor` all use it, so the
file they name cannot differ. `python -m career_agent --doctor` reports the version, the interpreter,
the resolved path and the rule that chose it, whether the data folder is writable, and what the database
contains — or the same refusal the app would show for a damaged, empty, or too-new file — without a
display, without writing anything, and with exit status 1 when it finds a problem.

The application also keeps an event log: `logs/application.log` beside the database, written by
`career_agent/event_log.py` with one line per event (the application starting and stopping, a database
being opened and migrated, a migration failing, profile/job/tracker/activity writes, résumé imports,
exports, backups and restores, and each refusal). A line carries an event name plus an identifier, a
count or a category — never profile values, document text or URLs — is stripped to a single line, capped,
and redacted with the same function the start-up note uses; the file is owner-only where the platform
supports it, bounded by rotation at 256 KiB with one previous file kept, and a logging failure returns
`None` rather than failing the action it describes. `--doctor` prints the log's path and its most recent
line. A diagnostics view inside the window is still planned; the version/data-compatibility policy for releases is
written in the README ("What a version number promises about your data").

Schema versioning and safe updates are implemented. `career_agent.store` holds an ordered list of
schema steps (version 1 created the profile/job/tracker tables; version 2 adds the application activity
log), and each step runs statement-by-statement inside one explicit transaction that records the version
it reached in the same commit. Neither the sqlite3 module's implicit transaction (it covers
data-modifying statements only) nor `executescript` (it commits any open transaction before running its
script) is used, because either would let a partly applied step be committed with no way to roll it back;
a regression test asserts that a step which fails after creating an object leaves nothing behind. A failing step is rolled back and reported
through `SchemaMigrationError` with the version **re-read from the file** afterwards, so "nothing changed"
is only claimed when the file confirms it. An existing database at an older version is copied to a
verified, owner-only snapshot beside itself *before* the first step runs (never for a new file, never for
a file already current, and never by reusing an existing copy), because a step that succeeds and is only
later found to be wrong has already been committed and cannot be rolled back; if that copy cannot be
written the update does not start and `SchemaUpgradeRefused` says so, naming both versions. The event log
records the copy before the migration for each update; a database recording a newer version
(`SchemaTooNewError`) or holding tables with no recorded version at all (`UnrecognisedDatabaseError`) is
refused untouched, by type, and `diagnostics` explains each of those three cases in plain language.
`backup.validate_app_database` now validates a candidate file against the tables of the version that file
records, so restoring an older backup works again — installs it exactly as validated, then updates it
when the app opens it, reporting that in the window and on the command line — while a newer file is still
refused rather than downgraded. The desktop surface for the activity log now exists (the **Application
tracker** tab's activity panel, with an add dialog and a delete confirmation); the version/data-compatibility
policy is the README's "What a version number promises about your data". Encryption at rest and a written
release/upgrade policy remain outstanding.

Background execution is partially implemented. Schema version 3 stores what may run and what
happened when it did: a task definition with times in a named zone (default 00:00 and 12:00
Asia/Kolkata), one run row per scheduled occurrence *and attempt* - the uniqueness of that triple is
the duplicate-run protection, so two processes cannot both execute one occurrence - a retry rule that
serves the occurrence a failed attempt still owes, a heartbeat that separates "in progress" from "the
worker is gone", crash recovery that closes a stale attempt as *interrupted* and re-plans it, and a
worker lease that refuses a second scheduler over one database while taking over a lease whose
heartbeat has gone stale. Refusals (a rule saying no, such as the closed source-quality gate) are
recorded as refusals, not failures, and are never retried. The engine that executes it is implemented too
(`career_agent/worker.py`): a handler registry, validated timings, one claim per occurrence, a
heartbeat, recovery of an attempt whose worker stopped, and an honest set of outcomes - a handler that
reports success *after* its deadline is recorded as timed out, a refusal is recorded as a refusal and
never retried, and a kind with no handler fails naming what is registered. Two kinds are built in
(`career_agent/handlers.py`): a verified database snapshot, which refuses rather than delete old copies
once 30 sit beside the database, and a scheduled discovery run that refuses while the source-quality
gate is closed and reaches no network. Both surfaces exist: `python -m career_agent --worker` runs the schedule in the foreground (Ctrl-C
winds the current attempt up, records it, and releases the lease), `--worker-status` reports it
read-only, `--seed-tasks` adds the defaults without rewriting anything, and the window's **Background
tasks** tab shows the same summary, the task list and the recent attempts and can pause or resume a task.
The status surfaces also report the occurrences the schedule walked past while nothing was running
(``worker.missed_occurrences``): due instants that are occurrences of the task's own schedule, have no
attempt row, owe no retry and are not the instant the next claim will take - because a finished attempt
plans its next run from the moment it finished, those are occurrences nothing will come back to. Reporting
one is not running it: a deployed always-on worker, missed-run *catch-up*, and therefore any claim of
laptop-off operation remain outstanding, and the report says so in the window and on the command line.

The work around an application is now recorded rather than remembered: schema 5 adds
`application_preparation` (a checklist item with a kind, an optional day and the moment the person said it
was done) and `interview_round` (which round, the day it is planned for, how it is held, the candidate's
own reading of how it went, and their notes), and `career_agent/preparation.py` turns those records plus the
follow-up days into one ordered list - `career_agent` surfaces it as the **Next actions** tab and as
`--next-actions` / `--interviews`, both read-only apart from the two buttons that write a record the person
typed. The rules are enforced where they belong: `complete_preparation` refuses a second completion so the
timestamp keeps meaning the first time it was reported, an open item with the same title and kind cannot be
added twice, a round cannot be recorded twice for the same stage and day, both tables are deleted with their
listing, and neither record has any route to an application's status - the store tests assert the tracker
row is byte-identical after every one of these writes. The interview outcome vocabulary deliberately has no
`passed` or `rejected`: the application cannot know an employer's decision, so the tests refuse values that
would put words in an employer's mouth. `ApplicationTracker.is_ahead`/`is_past` replaced a single
`has_happened` while this was written, because "today" was being counted as the past and burying the round
that is about to happen.

The candidate's own record now exists as records rather than a summary. Schema 6 adds
`candidate_work_history` (employer, job title, employment type, start date, an end date that may be
absent, an explicit current-role flag, and an optional note) and `candidate_education` (institution,
qualification, optional discipline, optional start and completion dates, and an ongoing-study flag), and
`career_agent/core.py` refuses a contradiction at construction: an end before a start, a current role with
an end date, an ongoing qualification with a completion date, blank required text, an unknown employment
type, or the same record twice. `career_agent/desktop.py` surfaces them as the **Work history & study**
tab (two forms, two lists, and the buttons that add, load, save or delete the selected row) and
`career_agent/__main__.py` as `--history` (read-only), `--add-role` and `--add-study`; the store is the
only writer, the ordering lives in one query per list, and both tables are deleted with the profile in one
transaction after a confirmation that names the counts. The one duration the app reports is the union of
the months covered by current or fully dated roles (`months_covered_by`), which counts a month covered by
two roles once and a role with no recorded end not at all: a sum of job durations would overstate exactly
the people with concurrent, part-time or unfinished roles, and the figure is never written back into the
profile's own years-of-experience field. Deleting a role, a qualification or the profile itself is tested
for what it does *not* touch (applications, trackers, other records), and the JSON export format moved to
version 2 with `work_history` and `education` arrays while version 1 files are still read - an import
whose records would mix into records already stored keeps the stored ones and says so. Not implemented:
importing these records from a résumé, attaching documents, verifying anything with an employer, or using
them in eligibility and matching.

Outcome-versus-activity reporting is implemented for the records that exist. `career_agent/analytics.py` is a
pure module over the stored listings, tracker rows, activity entries and interview rounds; it reports what the
records hold and how often, with four rules that are enforced by tests rather than by care: every rate names
its denominator, a denominator below five applications produces no rate at all, a metric this application
cannot observe (an offer, or anything an employer did without telling you) is listed as unmeasurable rather
than printed as zero, and a genuine zero is printed as `0 of N`. Timings use only dates the person recorded,
and the period comparison needs both windows to hold five recorded applications before they are set beside
each other. The surface is the **Progress report** button on the Application tracker tab and
`python -m career_agent --analytics`, both read-only, both computed from the same function. Not implemented:
benchmarks, projections, any comparison against other people's searches, and any statement about causation -
the report denies causation in the text it prints.

Distribution and packaging are partially implemented. `pyproject.toml` (PEP 621) declares the project
name, `requires-python = ">=3.10"`, **no required runtime dependency**, the optional `pdf` extra
(`pypdf>=4.3`), and a `career-agent` console script pointing at the same `career_agent.__main__:main`
that `python -m career_agent` runs; only `career_agent/` is packaged, not `tests/` or `scripts/`. The
version stays a single literal in `career_agent.__version__` that setuptools reads statically, so the
installed metadata and `--version` cannot drift (a test refuses a computed version). The build and the
installed command are exercised in CI, and `tests/test_packaging.py` holds the metadata invariants from
the source tree. The repository half of the release rehearsal is now recorded with commands and observed
results in [the release-readiness audit](research/release-readiness-audit-2026-10-15.md): install from the
built wheel, `--doctor`, backup, restore, export, import, a genuine schema-5 file upgraded by the installed
build (row-preserving, snapshotted first), and the failure paths — including the defect that rehearsal
found, where `--doctor` reported "no problems found" on a database every read path refused; the doctor now
decodes every stored record read-only and names what it cannot read, and the read-only reports answer such a
record with one sanitised refusal and exit status 2 instead of an unexpected failure. The
version/data-compatibility policy that was missing is written in the README ("What a version number
promises about your data"). Still missing: per-platform launch artefacts, code signing/notarisation, a
decision on bundling the interpreter, and the per-operating-system half of the release checklist (a real
desktop, macOS and Windows). The macOS and Windows CI legs this paragraph used to list as missing now exist
(`windows-latest` and `macos-latest`, 3.10 and 3.13, each running the suite, the résumé tests with the `pypdf`
extra and the installed-command rehearsal) — so this is an installable alpha, not a packaged desktop release,
and no human has yet run it on either platform.

Résumé import is local and text-only: there is no OCR, so a scanned PDF with no text layer is refused with an explanation rather than guessed at, and PDF reading needs the optional `pypdf` library (DOCX import uses the standard library alone). A remote scheduler, live source connectors, email integration, and real application adapters are not yet implemented/verified. The source-quality gate remains NOT PASSED; no live integration or application automation should be represented as production-ready. Safe local product implementation is authorized and should proceed now.

---

## Product Vision Alignment and Delivery Sequence (2026-10-16)

The north star is a resume-first autonomous career operations agent. The user completes initial profile/policy/account setup once; the software then performs routine, policy-compliant work without per-application approval, within source permissions and explicit stop conditions. This is target state, not a claim that full automation is implemented.

### Phase A — Baseline and HR contact import
- Inspect and reuse existing resume/CSV importers, SQLite schema/migration contract, desktop views, activity events, backup/restore and tests.
- Complete offline HR CSV parsing, preview, duplicate/conflict review and explicit commit semantics.
- Preserve provenance and suppression/opt-out history; do not transmit contact data.
- Test malformed rows, duplicate groups, conflicts, missing names, BOM/encoding, re-import and cancellation/no-write behavior with synthetic fixtures.

### Phase B — Resume-derived profile and guided setup
- Extract profile facts from supported resume formats and retain provenance.
- Separate confirmed facts, uncertain extractions and missing values.
- Collect essential application fields once and persist target roles, preferences, eligibility, exclusions and action limits.
- Add profile review/edit/versioning and tests preventing invented facts.

### Phase C — Durable job and application ledger
- Audit existing job/application/event schema and reuse it where possible.
- Define stable job/application identity across sources and discovery runs.
- Track discovered, evaluated, prepared, blocked, submitted, submission-unknown, interview, assessment, rejected, offer, withdrawn and follow-up states.
- Store timestamps, source URLs, external IDs, artifact versions, decision reasons and submission evidence.
- Make side effects idempotent; reconcile uncertain outcomes before retrying; test migrations, backup and restore.

### Phase D — Source feasibility and scheduled discovery
- Build a source-by-source feasibility/permission matrix for official company career pages, supported ATS/public feeds, LinkedIn, Unstop, Internshala, Naukri.com and other relevant sources.
- Document access method, platform terms/permissions, authentication, rate limits, freshness, fields, failure modes and submission support.
- Implement timezone-aware twice-daily scheduling, run history, bounded retries, cancellation and pause/stop controls.
- Enable only sources that pass documented feasibility, permission and test gates. No unsupported scraping or human-verification bypass.

### Phase E — Application preparation and controlled execution
- Generate role-specific resume, cover letter and screening responses from verified facts only.
- Validate required fields, eligibility and policy before side effects.
- Implement only source-specific submission routes that are permitted and testable.
- Execute routine applications autonomously within saved global policy, without per-job approval, when no required fact or human attestation is unresolved.
- Stop affected tasks for missing facts, sensitive/legal attestations, identity verification, CAPTCHA/OTP, platform restriction or suspicious posting.
- Mark submitted only with evidence; reconcile uncertain outcomes before retrying.

### Phase F — Authorized email outreach and response tracking
- Connect a supported mail provider with least-privilege permissions and revocation.
- Import HR contacts privately; resolve duplicate/conflict queues and enforce suppression, opt-outs, campaign limits and cross-run idempotency.
- Test draft generation and attachment correctness before enabling real sends.
- Enable personalized internship outreach only after explicit global authorization and verified contact/campaign eligibility.
- With separately authorized mailbox access, track actual replies, bounces, delivery evidence and bounded follow-ups.

### Phase G — Reporting, resilience and release readiness
- Deliver run summaries, daily/weekly reports, deadline/follow-up alerts and actionable failure explanations.
- Validate pause/stop-all, permission revocation, secure credentials, privacy, export/delete, backup and restore.
- Run regression, migration, scheduler, idempotency, adapter-contract and mocked end-to-end tests.
- Document only verified capabilities and source coverage.

### Release gates and invariants
- Keep source discovery, email sending and application submission independently fail-closed until their own gates pass.
- Never bypass CAPTCHA/OTP, identity verification, platform restrictions or required human attestations.
- No real external applications or emails in tests.
- No personal contact data in public repository, fixtures, CI output, screenshots or telemetry.
- This documentation update does not merge to main or change unrelated PR state.
