# AI Career Agent — Readiness Audit (2026-10-14)

**Status of this document:** audit artifact, **written but not committed**. The audit itself changed no
production code, no test, and no documentation in the repository. The only proposed code changes are
listed as patches to review first (section 6).

**Verdict: not ready for a public desktop alpha release.** The local workflow is genuinely functional and
the correctness work to date is real, but three release blockers remain (export permissions, packaging and
error reporting, backup/restore), and the primary analysis action has no automated coverage.

---

## 1. Baseline (inspected before any analysis)

| Item | Value |
|---|---|
| Branch | `arena/351e052d-ai-career-agent` |
| HEAD | `2bdf1ecc03d62b20bf715b5fd09b2697f2a7b1f9` (matches the reported commit) |
| Working tree | clean; no stash; 7 commits ahead of `main` |
| `origin/main` | `127244b5f79e245da31ee58608701058de2f476d` — untouched |
| Remote tip | `refs/heads/arena/351e052d-ai-career-agent` = HEAD (in sync, no unpushed work) |
| PR #2 | **OPEN**, unmerged (`mergedAt`/`mergeCommit` null), head = HEAD, 24 files, +4546/−141 |
| CI | run `38571209370` at HEAD → success; `unit-tests (3.10)`, `(3.11)`, `(3.12)` all pass |
| CI definition | unchanged from `main` (`.github/workflows/tests.yml`): unittest → compileall → CSV audit |
| Code size | application 2114 LOC (9 modules), tests 3051 LOC (9 modules), scripts 344 LOC (2 scripts) |
| Corpus | 8 root docs, 46 research docs, 1 audit CSV, 1 audit JSON |

The user's local database was never opened or modified. All probes used temporary directories.

## 2. How this audit was produced

Everything below is from executed checks, not inspection alone: repository reads, the real test suite,
an independent statement-coverage measurement, six behavioural probes (stale selection, export file mode,
data-directory mode, corrupted database, damaged payload row, tkinter-present/absent test runs), and a
sandboxed-`HOME` isolation test. Commands and outputs are cited per finding.

**Coverage caveat, stated up front:** the stdlib `trace` module reports "100% coverage" for these modules,
but that number is an artifact — it silently omits function bodies that never execute. Demonstrated on a
3-line sample where an uncalled function's body was neither counted nor flagged. I therefore measured
coverage with my own tracer comparing executed lines against the executable-line set derived from every
code object (including nested functions). The honest total is **1469/1600 = 91.8%**.

| Module | Coverage (measured) | Never-executed notes |
|---|---:|---|
| `career_agent/__init__.py` | 100% | — |
| `career_agent/core.py` | 97.2% | 8 lines (edge branches, see L2) |
| `career_agent/store.py` | 97.9% | `_json_default` TypeError path |
| `career_agent/desktop_logic.py` | 100% | — |
| `career_agent/urls.py` | 100% | — |
| `career_agent/validation.py` | 100% | — |
| `career_agent/sources.py` | 98.9% | 2 lines |
| **`career_agent/desktop.py`** | **83.4%** | **78 lines — including all of `_evaluate` and `_delete_job`** |
| `career_agent/__main__.py` | 0% | entry point (expected, but part of the release story) |
| `scripts/audit_job_source_csv.py` | 81.8% | `main()` (10 lines) — CI exercises it, unit test does not |
| `scripts/correct_tracker_record.py` | 85.6% | `main()` and failure branches |

## 3. Feature status

**Complete and genuinely working** (implemented + tested + exercised):

| Capability | Evidence |
|---|---|
| Hard eligibility, three-valued, conservative | `core.evaluate_eligibility`; `tests/test_core.py` (38 tests). Unknown availability or missing evidence never passes. The user's Mac run confirmed `ELIGIBILITY: UNKNOWN` for the smoke-test listing. |
| Shortlist safeguard | `desktop._shortlist` blocks anything but explicit PASS; wording locked by `ShortlistEligibilityMessageTests`. |
| Tracker state machine + invariants | `core._TRACKER_TRANSITIONS`, `core.INITIAL_APPLICATION_STATUS`, `store._check_tracker_invariants`; mutation-verified in the previous phase. |
| Confirmation integrity (evidence floor + explicit assertion) | `core.require_confirmation_evidence`, `is_substantive_confirmation_evidence`, dialog assertion; `TrackerConfirmationRegressionTests` (18 tests). |
| Durable local storage | SQLite with per-statement transactions, cascade delete, newer-schema refusal, file-backed restart tests. |
| Untrusted-URL validation + display redaction | `career_agent/urls.py`; `tests/test_urls.py` (15 tests). |
| Fail-closed source gate | `career_agent/sources.py`: `SOURCE_QUALITY_GATE_PASSED = False`, `enabled_discovery_sources() == ()`, decisions citing existing evidence files (asserted by test). |
| Local privacy by default | measured DB file mode `0o600`; `.gitignore` excludes `*.sqlite*`/`*.db`; no logging of candidate data anywhere; no candidate data in fixtures; no secrets in the tree. |
| No accidental network activity | only `urllib.parse` (string parsing) and `socket.inet_aton` (literal parsing, no DNS); socket-blocked suite passes 210/210. |
| Test hygiene | all 9 modules pass standalone; 3 consecutive full runs identical; no time/random dependence; sandboxed-`HOME` run created **zero** files; suite passes with tkinter importable and with it absent. |

**Partial** (exists but incomplete for a release):

| Area | What exists | What is missing |
|---|---|---|
| Desktop usability | Working tabs, entry forms, trees, evaluation text, tracker dialog, status bar, `WM_DELETE_WINDOW` shutdown (`desktop.py:37`) | No keyboard accelerators at all (only `<<TreeviewSelect>>` binds); status dialog offers all 13 statuses regardless of what is legal; no confirm step before a terminal status |
| Data integrity | Transactions, cascade delete, schema-version refusal, owner-only DB file | No integrity check, no backup on startup, no restore path, no migration code, cryptic failure on a damaged row |
| Provenance / freshness | `first_seen_at`, `last_seen_at`, `updated_at` stored | Never surfaced in the UI and no public accessor; `JobListing` carries no freshness field |
| Export | JSON export with form version, privacy notice, tracker history | No import/restore; file written with default permissions |
| First-run experience | Profile tab with a short instruction line | No welcome screen, no source-status screen, no version display (`design.md` §3 lists these) |
| Error reporting | Message boxes for the handled cases | No log file, no diagnostics bundle, `main()` re-raises after showing a box |

**Missing** (planned, not started): packaging/install/upgrade/uninstall; app version identifier; resume
parsing; live source adapters; scheduler/worker; email integrations; submission; backup/restore tooling;
multi-OS release docs.

**Unverified** (cannot be established from here): rendering, keyboard focus behaviour, Cmd+Q, menu-bar
behaviour and any macOS-specific widget behaviour (Tkinter and a display are absent in this environment —
`python -m career_agent` exits 1 with `ModuleNotFoundError: No module named 'tkinter'`). The user's manual
Mac run is the only real GUI evidence, and it covers the paths they exercised.

## 4. Findings, by severity

### BLOCKERS

**B1 — The JSON export writes the candidate's data with default (group/world-readable) permissions.**
`career_agent/desktop.py:522` calls `Path(destination).write_text(...)` with no permission handling.
Measured through the same code path under a standard `umask 022`: **export file `0o644`** while the
database is **`0o600`**. The export contains the whole profile (country, degree discipline, study status,
graduation year, experience, work authorization, skills, preferences) plus every listing and the full
application history with evidence notes. Note the honest bound: the model has **no name, email, phone or
address fields**, so this is exposure of sensitive attributes and application history — not identity data.
The app's own dialog says "Keep it private; it may contain personal data", so the intent is stated but not
enforced. Practical exposure requires another local account able to traverse the chosen folder, or a
synced/shared destination — a real risk on a family or work Mac, and on any cloud-synced folder.

**B2 — No packaging, no version, no install path, no diagnostics: the alpha cannot reach a non-developer.**
`git ls-files` contains no `pyproject.toml`, `setup.py`, `requirements*.txt`, `Info.plist`, `.app` bundle,
`Makefile` or `.python-version`; there is no `__version__` anywhere (only `_SCHEMA_VERSION = 1` in
`store.py`). The documented entry point is `python -m career_agent` from a cloned repo with Python 3.10+
and Tkinter (`README.md:32`). `main()` (`desktop.py:542-549`) shows an error box and then `raise`s, and
`grep -rn "logging|print|traceback" career_agent/*.py` finds nothing, so a startup failure on a packaged
or windowed launch leaves no record the user or maintainer can act on.

**B3 — No backup, restore or recovery path for the candidate's own data.**
No in-app backup (`grep "backup(" career_agent/*.py` → nothing), no import/restore capability anywhere,
and no backup/restore/upgrade/uninstall section in the 89-line `README.md`. The only backup in the project
is a side effect of `scripts/correct_tracker_record.py --apply`. `prd.md` §11 explicitly requires
"persistence and backup/restore" validation before general release. Impact: a corrupted, deleted or
clobbered SQLite file loses the profile and application history with no supported recovery.

### HIGH

**H1 — `_evaluate`, the primary analysis action, has zero automated coverage, and it crashes on a stale
selection.** Measured: lines 290–307 of `desktop.py` never execute in the suite (the handler tests
deliberately stub `app._evaluate`). Probe: with `selected_job_id` pointing at a listing absent from the
database, `_evaluate` raises `AttributeError: 'NoneType' object has no attribute 'availability_status'`;
`_shortlist` fails identically. Reachability is low today (the UI refreshes both trees after its own
deletes, so ordinary clicking keeps selections consistent), so the practical risk is: (a) the returned
report text, the profile-missing path and the selection-missing path are unverified, and (b) any future
import/refresh feature or external database change turns this into a raw traceback inside a Tk callback,
which surfaces on stderr only — no dialog, and nothing on a windowed launch.

**H2 — The status dialog offers all 13 statuses no matter what the state machine permits.** `desktop.py:404`
builds the combobox from `[x.value for x in ApplicationStatus]`. From `submission_attempted` only four are
legal (`confirmed`, `failed`, `submitted_unverified`, `unknown_status`); from `withdrawn` none are. The
existing tests prove illegal choices are rejected with "Invalid status change", so this is not a
correctness defect — it is a usability defect that guarantees users hit avoidable errors, and it works
against `design.md` §15 ("reject the update and explain the allowed next step").

**H3 — Observation freshness is stored but never shown.** The schema keeps `first_seen_at`, `last_seen_at`
and `updated_at` (`store.py:83-98`), but neither tree nor the evaluation report displays any timestamp, and
no public method returns one (`grep` in `desktop.py` finds none). `design.md` §8 asks to "display source and
last-checked time"; `architecture.md` §5 lists retrieval timestamp/freshness in the adapter contract. For a
job-search tool, not knowing whether a listing was recorded today or three weeks ago is material.

### MEDIUM

**M1 — Terminal states are irreversible and only half-explained.** `withdrawn` is offered from `discovered`,
`shortlisted`, `prepared`, `awaiting_user`, `confirmed`, `response_received` and `interview`, and has no
outgoing transitions; `rejected_by_employer` is likewise terminal. The dialog explains the correction path
only when the record is already `confirmed`. A mis-click permanently ends the record, and the shipped
correction tool deliberately refuses to leave `withdrawn`. Keep the one-way property (it is what makes the
history auditable) but confirm before entering a terminal state.

**M2 — A damaged row makes the app fail to start with a cryptic message.** Deterministic probe: after
damaging one `payload` value, `get_job`/`list_jobs` raise `json.JSONDecodeError: Unterminated string
starting at: line 1 column 21` (a `ValueError` subclass). `_refresh_jobs` has no `try/except` and runs from
`__init__`, so startup fails; `main()` shows that raw message and re-raises. There is no
`PRAGMA integrity_check`, no backup and no salvage path. (A separate crude byte-corruption probe was
**inconclusive** — the file remained readable — and is reported as such rather than as evidence of safety.)

**M3 — Unexpected exceptions in the status dialog leave a mouse-only exit.** `apply()` catches only
`ValueError` and `sqlite3.Error`; the dialog holds `grab_set()` and binds no `Escape`. On an unexpected
error the main window stays blocked and only the mouse can close the dialog — contrary to `design.md` §14
("keyboard-accessible workflows").

**M4 — No migration path or pre-migration backup.** `_SCHEMA_VERSION = 1` with a clear newer-version
refusal, but no migration code and no automatic backup before any future change. Fine today; a blocker for
the first schema change, which `prd.md` §11 requires to be validated.

### LOW

- **L1** The tracker tab shows "discovered" for listings with **no** tracker row (`desktop.py:262` and
  `_refresh_tracker`'s `get_tracker(...) or ApplicationTracker(...)`), conflating "no record" with
  "record at discovered" — a state the store and tests otherwise distinguish.
- **L2** Untested-but-implemented branches worth locking: over-maximum experience must FAIL
  (`core.py:206` — a real eligibility branch with no test), worldwide-without-candidate-country UNKNOWN
  (167), restricted-with-missing-data UNKNOWN (170), experience-range UNKNOWN (202), `canonicalize_url`
  fallbacks (382/385), `_norm` empty (117), `duplicate_key` fallback (404), `_json_default` TypeError
  (store 48-50), `sources.py:66`, and both scripts' `main()` functions.
- **L3** `research/source-quality-gate-assessment-2026-10-14.md` §1 cites "82 records / 27 columns" while
  the current CSV parses as **83 / 30**; the gate decision is unaffected but the citation is stale.
- **L4** The audit JSON is not byte-reproducible: a fresh run differs from the committed snapshot only in
  `generated_at_utc`.
- **L5** Cosmetic: `tests/test_audit_job_source_csv.py` ends with `if ( __name__ == "__main__" ):`.
- **L6** The data folder is created `0o755` while the database file is `0o600` — acceptable, since the
  file itself is protected.

## 5. Source-quality gate (area 6): still NOT PASSED, and correctly so

`research/source-quality-gate-assessment-2026-10-14.md` records five acceptance gates: **2 FAIL**
(≥20 valid relevant listings; no unresolved permission blockers) and **3 UNMEASURED** (≥90% valid direct
links; zero false worldwide claims; independent eligibility/status verification). The code matches that
decision and is fail-closed: `SOURCE_QUALITY_GATE_PASSED = False`, `enabled_discovery_sources() == ()`,
unregistered sources refused, submission refused even where reading is approved, and each recorded decision
must cite an evidence file that exists (asserted by test). **Nothing here justifies moving that gate.**

## 6. Proposed patches (review before applying — none applied)

**P1 (B1, ~8 lines + 2 tests).** In `_export`, after the successful `write_text`, apply best-effort
owner-only permissions using the existing pattern from `store._restrict_to_owner`:

```python
            Path(destination).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            _restrict_to_owner(destination)          # reuse the store helper; non-fatal, POSIX-only effect
```
Regression test: export to a temp path, assert `stat().st_mode & 0o777 == 0o600` on POSIX, and assert the
export still succeeds when `os.chmod` raises (mirroring `DatabaseFilePermissionTests`). Also mention the
shared-folder caveat in the confirmation dialog.

**P2 (H1, ~6 lines + ~8 tests).** Guard the missing-row case in `_evaluate` and `_shortlist`
(`if job is None or profile is None: <existing message>; return`), then add tests for: the report text of a
real evaluation, profile-missing, selection-missing, and stale-selection; plus `_delete_job` success and
`sqlite3.Error`, `_delete_profile` success, `_refresh_jobs`/`_refresh_tracker` population, `_select_tracker`,
and `_export` cancel/'OSError'.

**P3 (H2, ~6 lines + ~4 tests).** Populate the combobox from the current status plus
`_TRACKER_TRANSITIONS[current]`, and label terminal states explicitly. Keep the domain as the authority;
the UI simply stops advertising illegal choices.

**P4 (M3, ~3 lines + ~2 tests).** Bind `Escape` to `dialog.destroy` and `Return` to `apply`, and add a
final `except Exception` that reports "nothing was saved" instead of leaving a modal with a raw traceback.

**P5 (B3/M2/M4, larger).** A documented `backup`/`restore` pair (the SQLite backup API is already used in
the correction script), an integrity check with a readable message, `__version__` plus a no-dependency
`pyproject.toml`, and README sections for first run, backup, restore, upgrade and uninstall.

## 7. Release blockers

1. **B1** export written world-readable while claiming privacy.
2. **B2** no packaging, version, or install/error-reporting path for a non-developer.
3. **B3** no supported backup/restore, and no upgrade story for the first schema change (**M4**).
4. **H1** the primary analysis action is untested and crashes on a stale selection.
5. The manual smoke-test checklist (`research/local-alpha-manual-smoke-test-checklist-2026-10-14.md`) is
   still **not recorded as passed**; the user's Mac session covered several steps but was not recorded per
   the checklist's own rules, and no other OS has been exercised.

## 8. Must remain disabled

Live source adapters (gate NOT PASSED), automated application submission, background scheduling or remote
workers, email/ATS integrations, resume parsing, any external transmission of candidate data, paid APIs,
and all cookie/session/social scrapers. Current code already keeps all of these off; no change is proposed.

## 9. Suggested next phase — "Phase 1.2: release-candidate hardening"

Ordered by dependency and value, each with a measurable acceptance criterion. No new dependencies.

| # | Work | Acceptance criterion |
|---|---|---|
| 1 | Apply P1 (export permissions) | Test asserts `0o600` on POSIX and graceful behaviour when `chmod` fails; macOS re-check by the user |
| 2 | Apply P2 and raise desktop coverage | `desktop.py` measured coverage ≥ 95% by the tracer method above; no handler raises on a missing row |
| 3 | Apply P3/P4 (dialog usability) | Tests for the filtered status list, terminal-status confirmation, `Escape`/`Return`; user re-checks the dialog on macOS |
| 4 | Surface freshness (H3) | Selected listing shows its stored first/last-seen values; test proves the value comes from storage, not from `now()` |
| 5 | Apply P5 (backup/restore + `__version__` + `pyproject`) | `python -m career_agent --version` prints; backup → destroy → restore returns the same data, demonstrated by a file-backed test; README documents first run/backup/restore/upgrade/uninstall |
| 6 | Execute and record the manual smoke checklist on macOS | Every step recorded pass/fail with OS and Python versions, per the checklist's own "Record results" section |
| 7 | Only then: revisit the source-quality gate with new evidence | Unchanged criteria from the gate assessment; keep adapters disabled until it genuinely passes |

Explicitly **not** in this phase: adapters, submission, scheduling, resume parsing, or any new integration.

## 10. Remaining limitations of this audit

- No GUI was rendered: rendering, focus behaviour, macOS menu/Cmd+Q, and accessibility remain unverified
  here; the user's manual run is the only GUI evidence.
- Coverage is statement coverage, not branch coverage, and says nothing about correctness of untested
  inputs; mutation testing (previous phase) covered only the tracker paths.
- Corrupt-body behaviour was probed inconclusively (section M2) and is reported as such.
- No performance, memory, or large-database testing was done; the largest real corpus is the 83-row
  research CSV, and the job store has not been exercised at scale.

## 11. Status update, same day (2026-10-14, later)

The findings above are kept as they were recorded. Three of them have since been implemented on the
`arena/351e052d-ai-career-agent` branch (PR #2, still open and unmerged), each with reproduction before
the change and regression tests afterwards:

- **B1 (export permissions)** and **H1 (stale-selection crash)** — implemented in the phase described in
  `memory.md`; a third, unreported defect found while reproducing B1 (an export through a symbolic link
  followed the link and overwrote the target file) was fixed at the same time.
- **B3 (backup/restore)** — implemented as `career_agent/backup.py`, the desktop *Data safety* tab, and
  the `--backup-to` / `--restore-from` command-line actions. Backups use SQLite's backup API into a
  pre-created owner-only file, are never overwritten, are verified (integrity, schema version, required
  tables) before success is reported, and are normalised to single-file classic format. Restore validates
  the chosen file, stages and re-validates a copy, preserves the current database (verified, or raw and
  owner-only when it cannot be read), refuses while another connection holds the database, replaces the
  file atomically, removes stale SQLite side files, reopens and verifies the result, and puts the previous
  database back if that final check fails. The correction tool's pre-change snapshot now goes through the
  same path; measured before the change, that snapshot was written `0o644` and was never verified.
- Tests went from 243 to 312; corruption, incompatible-schema, permission, no-overwrite, symlink, WAL,
  side-file, in-use and failure-path cases are covered, plus the command-line front end and the GUI
  confirmation/cancellation behaviour. 14 controlled mutations were applied and all 14 were caught.

**Still open from this audit:** B2 (packaging, `__version__`, install/diagnostics/error reporting), M2/M4
(corrupt-body detection and the pre-migration backup story), H2 (status combobox offers illegal
transitions), H3 (freshness/last-checked display), P4 (Escape/Return bindings and a final `except
Exception` in `main`), P5's packaging/README items, desktop statement coverage (83.4% at audit time), and
the manual GUI smoke checklist, which still needs recording on a real desktop. Nothing in the "must
remain disabled" section has changed: the source-quality gate is still **NOT PASSED**, and no adapters,
submission, scheduling, resume parsing or external data transmission were added.

## 12. Status update, same day (2026-10-14, desktop-readiness phase)

This section records what the next phase changed, so the findings above stay readable as the point-in-time
record they are. All work is on the same open, unmerged branch; `main` was not touched.

- **H2 (status chooser offered illegal transitions) — fixed.** The chooser is now derived from the state
  machine through `core.selectable_tracker_statuses`: a record at `discovered` is offered exactly
  `discovered`, `shortlisted`, `withdrawn`; a record in a final state (`withdrawn`,
  `rejected_by_employer`) is told that no further change is permitted and is not given a chooser at all.
  Storage-level enforcement was not touched and is still the authority; regression tests assert the option
  set against `is_allowed_tracker_transition` rather than a second hand-written list.
- **Unrecognised stored statuses — handled, and the four views they disabled are fixed.** The audit did
  not report this one: reproducing H2 showed that a status value this build does not know (an older build,
  another tool, a hand edit) raised a bare `ValueError` from `store.get_tracker`, which broke the tracker
  list, the jobs list, the status dialog, **and the JSON export**. Reads now distinguish an interpreted
  record (`get_tracker`, still strict, now raising a named `UnrecognizedStoredStatus` with an actionable
  message) from the stored row itself (`get_tracker_row`/`list_tracker_rows`), which is surfaced verbatim.
  Such a row blocks status changes — no transition can be validated from an unknown state — and is never
  guessed at, repaired, rewritten, or deleted. A scoped repair mode remains deferred with its own design
  requirements.
- **H3 (no freshness display) — fixed without a schema change.** `job_listings.first_seen_at`/`last_seen_at`
  and `application_tracker.updated_at` existed but were never shown. The detail pane now reports the app's
  own observation times, labelled as local, and states that the source's publication or update date is not
  available (the app stores none, and import time is never presented as one). Missing values read "not
  recorded"; offset-less or unparseable values are shown as stored with a label. Formatting lives in the
  Tk-free `desktop_logic` module and is unit-tested for missing, malformed and timezone cases.
- **B2 (packaging, `__version__`) — partly fixed, partly documented rather than claimed.**
  `career_agent.__version__` is now the single literal the source reports, and
  `python -m career_agent --version` prints it with the schema version, with no packaging metadata and no
  display. `pyproject.toml`, installers, code signing, and an interpreter-bundling decision are *not*
  implemented; the README's packaging status lists them and the order they are needed in.
- **P4 (dialog bindings, final catch) — partly fixed.** The status dialog now binds Escape (cancel) and
  Return (save) and has a final `except Exception` that reports an unexpected failure instead of closing as
  if the change had been saved. `desktop.main` shows the sanitised explanation rather than the raw
  exception; it still re-raises so the exit status stays non-zero.
- **Diagnostics (previously absent) — implemented.** `career_agent.diagnostics` classifies a start-up
  failure, explains it in plain language with a next step, redacts the database and home paths, and keeps
  one bounded owner-only note (`logs/startup-diagnostics.log`) containing no candidate data, credentials, or
  filesystem locations.
- Tests went from 312 to 388. Twenty controlled mutations were applied; all twenty were caught (the first
  sweep missed one because a second read enforced the same refusal — the two reads were merged into one and
  the mutation was then caught by fifteen tests). Files were restored SHA-256-identical after every run.

**Still open after this phase:** M2/M4 (corrupt-body detection and the pre-migration backup story), H2's
siblings in area A that need a *repair* path for unrecognised statuses, packaging and distribution
(README's packaging status), residual desktop statement coverage, and the manual GUI smoke checklist,
which still needs recording on a real desktop. The source-quality gate remains **NOT PASSED**, and nothing
in the "must remain disabled" section changed.
