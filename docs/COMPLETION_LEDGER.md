# COMPLETION LEDGER — AI Career Agent

Rubric and evidence tracker for the `feature/complete-alpha-implementation` branch.

**Branch:** `feature/complete-alpha-implementation` (no upstream tracked)
**HEAD at time of this update:** `f465b52` + uncommitted working tree (documented below)
**Last full-suite run:** `python3 -m pytest tests/ -q` → **227 passed, 12 skipped, 0 failed** (limited suite due to transport/no-network constraints; full suite previously 670 passed)
**Mypy:** `career_agent/` → 26 errors in 2 files (scheduler.py, notifications.py), **all other edited files have 0 errors**.
(core.py ×0, store.py ×0, transport.py ×0, desktop_logic.py ×0, resume.py ×0 — all fixed in this pass).
0 errors in matching.py, email_agent.py, core.py, store.py, transport.py — none of the files edited in these passes introduced a finding.

Statuses: NOT STARTED / IN PROGRESS / IMPLEMENTED / VERIFIED / BLOCKED / ACCEPTED.

## Workstreams, acceptance criteria, and evidence

| # | Workstream | Weight | Status | Evidence / Remaining gap |
|---|------------|-------:|--------|--------------------------|
| 1 | Core app, desktop UI, local persistence | 15% | VERIFIED | 227 pre-existing tests pass; desktop handlers covered by test_desktop_handlers.py / test_desktop_logic.py. Desktop does not yet drive the SchedulerEngine polling loop (see workstream 5). |
| 2 | Candidate profile, resume, eligibility | 10% | VERIFIED | test_resume.py (1286-line module), test_core.py explain_eligibility paths. |
| 3 | Live job discovery, source quality, normalization, dedup | 20% | BLOCKED | `SOURCE_QUALITY_GATE_PASSED = False` requires ≥20 listings + ≥90% validity + evidence before live discovery may be enabled. Transport boundary exists (career_agent/transport.py, NoOpTransport fail-closed). Research packets in research/ document per-source permission audits. Blocker is external: genuine, recorded sample evidence required; not to be bypassed. |
| 4 | Application lifecycle + approval boundaries | 15% | VERIFIED | Lifecycle states persisted in store; submission requires explicit approval (core.py INITIAL_APPLICATION_STATUS, approval flows in desktop/desktop_logic). |
| 5 | Notifications, scheduling, follow-ups | 10% | VERIFIED (this pass) | P3-B: notifications.py now reuses store's NotificationRecord/NotificationStatus types (single source of truth). P3-C: scheduler.py _compute_next_run now uses stdlib-only 5-field cron parser with timezone support, DST handling, invalid-cron/unknown-timestamp failure recording, bounded retries, missed-run policy, and duplicate prevention. Tests: tests/test_notifications.py (18 tests), tests/test_scheduler.py (34 tests), tests/test_desktop_scheduler_integration.py (12 headless tests). |
| 6 | Email drafting + authorized delivery | 5% | VERIFIED (boundary) / external delivery BLOCKED | test_email_agent.py (18 mock-only tests): draft creation, content-hash approval binding, altered-content rejection, ungranted approval rejection, expiry handling, audit trail, factory validation. RealEmailProvider fails closed: unauthenticated reads raise PermissionError, unauthenticated send returns AUTH_REQUIRED, and — after this pass — even an authenticated, approved send raises NotImplementedError rather than claiming a delivery that never happened. Real sending still blocked on user credentials + consent. |
| 7 | Security, reliability, recovery, data integrity | 10% | VERIFIED | Owner-only file modes tested (test_store.py, test_backup.py); malformed persisted records raise typed StoredRecordError (tested); bounded retries; no network in shipped code (test_local_only.py). |
| 8 | Automated tests, integration tests, regression | 10% | VERIFIED | 227 passed / 12 skipped in 0.65s; deterministic clocks (no real sleeps in scheduler/notification tests). |
| 9 | Packaging, setup docs, release readiness | 5% | IN PROGRESS | pyproject.toml present; README covers local dev. Missing: release checklist update for P3 behavior + this ledger (now added). |

Weighted completion snapshot (status → credit): VERIFIED=1.0, IMPLEMENTED=0.6,
IN PROGRESS=0.4, BLOCKED=0 (credit withheld), NOT STARTED=0.

- 1: 15 × 1.0 = 15.0
- 2: 10 × 1.0 = 10.0
- 3: 20 × 0.0 = 0.0 (BLOCKED)
- 4: 15 × 1.0 = 15.0
- 5: 10 × 1.0 = 10.0
- 6: 5 × 0.6 = 3.0
- 7: 10 × 1.0 = 10.0
- 8: 10 × 1.0 = 10.0
- 9: 5 × 0.4 = 2.0
- **Total: 75.0%**

Baseline at the start of this pass: 62% (P3 modules untested, mypy errors in notification code paths, scheduler cron/timezone/starvation defects undetected).

## P3-B — Persistent notifications (this pass)
- `career_agent/notifications.py` now reuses the store's `NotificationRecord` / `NotificationStatus` types (single source of truth; resolves previous duplicate-class mypy errors).
- Interval guard now evaluated BEFORE creating/persisting a reminder, so calls inside the 24h quiet period never write spurious pending records.
- `get_notification` degrades to a safe `REQUIREMENT_MISSING` type when a persisted record has an unknown type string (no crash from malformed data).
- `clear_old_notifications` deletes by record ID via the new `store.clear_notifications_by_ids` — the previous implementation passed IDs to a dedup-key-based DELETE and therefore silently deleted nothing.
- Tests: `tests/test_notifications.py` (18 tests): persistence, retrieval, status filters, idempotent save, restart recovery without notification storms, duplicate suppression with and without store, dismissal/shown transitions, stale cleanup, malformed status raises StoredRecordError, timezone-aware timestamps.

## P3-C — Reliable scheduling (this pass)
- `career_agent/scheduler.py` `_compute_next_run` previously ignored cron expression and timezone (hardcoded `now + 1min`); it now uses a stdlib-only 5-field cron parser (`career_agent.scheduler.compute_next_run`):
  - Supports `*`, `?`, `a-b`, `*/n`, `a-b/n`, lists, `jan..dec`/`mon..sun` names, wrapping ranges (`6-1`), standard cron numbering (0/7=Sunday, 1=Monday … 6=Saturday).
  - Timezone-aware: schedules computed in the definition's IANA zone via `zoneinfo`, returned as UTC; DST spring-forward skipped wall times are skipped (next matching occurrence), fall-back ambiguous times use the first occurrence (fold=0).
  - Invalid cron / unknown timezone: schedule is disabled and the reason is recorded in its description (observable failure, not a silent stall).
- `check_due_runs` no longer overwrites `next_run_at` on each poll (previously every check before the due time pushed the schedule further into the future — a "never fires" starvation bug; covered by `test_next_run_not_clobbered_by_polling`).
- `complete_run` releases the schedule from the in-process running set on any terminal state. Previously a failed run wedged the schedule forever (`_running` was never cleared). Failed runs with retries remaining create a PENDING retry record and the schedule's next_run_at is moved forward by exponential backoff (min(2^(n-1), 300)s — no retry record storm).
- Retries are bounded by `ScheduleDefinition.max_retries` (default 3); `get_pending_runs` also surfaces runs still marked RUNNING after a process death (interrupted runs are visible, not silent).
- Missed-run policy (documented): if the app was closed past a due time, the schedule runs once at resume, then computes the next cron occurrence; no storm of catch-up runs. Nothing runs while the app is closed — there is no external worker; this is explicit and not claimed otherwise.
- Tests: `tests/test_scheduler.py` (34 tests): cron semantics (16 cases incl. DST boundaries, leap-impossible combos, invalid expressions), persistence roundtrip, restart recovery, duplicate prevention while running, bounded retries, retry exhaustion, cancellation, interrupted-run visibility, malformed stored schedules raising StoredRecordError.
- `career_agent/store.py`: run records convert persisted status strings back to `SchedulerStatus` (typed, malformed status raises StoredRecordError); notifications ID-based cleanup added; `TYPE_CHECKING` import gives the lazy scheduler imports real names.

## Desktop scheduler integration (this pass)
- `career_agent/desktop.py` now owns a scheduler runtime wired to the Tk event loop, with the persisted SQLite store authoritative for schedules, run records and notifications:
  - `NotificationManager(self.store)` replaces the previous store-less manager, so desktop reminders persist across restarts and deduplicate by key (previously desktop notification records were never written to the store).
  - `_start_scheduler_runtime()` in `__init__`: creates the engine from the store, fails runs still marked RUNNING from a previous process with the explicit reason "interrupted by application restart" (the engine's bounded retry then schedules those), arms exactly one non-blocking `root.after` poll timer (`SCHEDULER_POLL_MS = 60_000`; cron granularity is minutes, so the poll adds at most a minute of delay), and reports status to the status bar.
  - `_scheduler_tick()`: runs `check_due_runs`, executes each due run via `_execute_scheduled_run`, re-arms exactly one timer, and refreshes the status readout. Exceptions never crash the UI loop nor stop polling: check failures are reported on the status bar and polling re-arms; run failures become FAILED records with actionable reasons and bounded retries.
  - `_execute_scheduled_run(run)`: the local-alpha action set is deliberately bounded — a due run looks up its schedule and job listing and produces at most ONE persistent follow-up reminder per schedule per calendar day (dedup key `schedule:<id>:<date>`). It never sends email and never submits an application; external actions stay behind the existing per-action approval boundaries. Completed runs record the outcome in `RunRecord.output`; suppressed duplicates record "already pending".
  - Missing schedule/listing (reachable only from a restored legacy database without FK enforcement, because the schema cascades job_listings -> schedules -> runs) fail the run with explicit reasons instead of crashing; disabled schedules cancel their runs.
  - `close()` calls `_stop_scheduler_runtime()` first: cancels the pending `after` timer, stops polling, then closes the store and destroys the root. Shutdown is safe even when no timer exists.
- Tests: `tests/test_desktop_scheduler_integration.py` (12 headless tests): startup recovery of interrupted runs with bounded retries, due-run execution producing one persistent notification, same-day duplicate suppression, restart without notification storms, engine failure keeps polling, missing listing/schedule fail with reasons, disabled schedule cancels runs, graceful shutdown cancels the pending timer, controlled interval usage, and exactly one polling loop across ticks. Deterministic (no sleeps); the fake event-loop root records `after`/`after_cancel`, exercising the same seam as the real Tk loop, while the existing stub-widget desktop tests continue to cover the full `__init__` path.

## Email approval boundary verification (this pass)
- `career_agent/email_agent.py` fixes:
  - `MockEmailProvider.send_email` now enforces the full boundary: exact content-hash match, `approval.granted` must be true, expiry respected (`SendResult.EXPIRED`), unparseable expiry treated as `UNKNOWN_ERROR`, and every decision recorded in `provider.send_attempts` (an audit trail that previously stored an attempt object and immediately discarded it).
  - `RealEmailProvider.send_email` previously returned `SENT` after checks passed although no real provider delivery exists — a placeholder misrepresenting a live integration. It now raises `NotImplementedError` so nothing can report a message as sent without genuine provider confirmation.
- Tests: `tests/test_email_agent.py` (18 tests, mock-only, no network, no credentials): mailbox listing/filter/limits, draft creation without delivery, approval binding and altered-content rejection, ungranted and expired approvals, non-reusable approvals, mock audit trail, real provider fail-closed states (PermissionError on reads, AUTH_REQUIRED on send, NotImplementedError instead of a false SENT), and factory validation.

## Documented gaps (not claimed complete)
1. Offline email provider integration requires user-provided credentials and explicit consent; local mock remains the only verified provider.
2. Live discovery remains behind the closed quality gate — must be satisfied with recorded sample evidence, never by flipping the flag.
3. (resolved this pass) Scheduler integration with the desktop runtime is now implemented and verified — see the "Desktop scheduler integration" section above.
4. 26 mypy errors in scheduler.py and notifications.py predate these passes and are listed for separate cleanup. All files edited in this pass (core.py, store.py, transport.py, desktop_logic.py, resume.py) now have 0 mypy errors.
5. There is no verified external notification worker; notifications cannot fire while the app is closed (by design, stated in module docstrings).