# What already exists, before adding anything: scheduler, worker, ledger, events, integrations, reporting — 2026-10-18

P8 item 1 asks for this audit *before* new abstractions, and it is the right order: three of the
things the roadmap asks for turned out to exist already, and one of the things it warns about (claiming
laptop-off operation) is already refused in the README. Everything below was read from the code and the
tests in this checkout and re-verified by running it, not recalled.

## The pieces, and what each actually does

| Piece | Where | What it is |
| --- | --- | --- |
| Schedule | `career_agent/tasks.py` | `ScheduledTask` (times + IANA zone + enabled + timeout + attempts + backoff), `next_run_after`, `plan_after_run`, `TaskRun`, `RunState`, `WorkerLease` |
| Worker | `career_agent/worker.py` | `Worker` loop, `WorkerSettings` (poll/heartbeat/stale/max-runs-per-tick), `worker_status`, `missed_occurrences`, lease takeover |
| Handlers | `career_agent/handlers.py` | exactly three: `backup.snapshot`, `discovery.run`, `followup.digest` |
| Application ledger | `career_agent/store.py` | `application_tracker` + `application_activity` + `interview_round` + `application_preparation` |
| Activity events | `career_agent/event_log.py` | append-only local log, names registered in `EVENTS`, ids and counts only |
| Integrations | `career_agent/integrations.py` | `DisabledIntegration` (default, refuses), `LocalMockIntegration` (local ledger), operation ids, `dispatch_with_retry` |
| Reporting | `career_agent/analytics.py` | counts, rates with denominators, withheld below five, explicit "cannot measure" list |

## What the run actually reports

`default_tasks()` seeds three tasks: `scheduled-discovery` (`discovery.run`, 00:00 and 12:00
Asia/Kolkata), `daily-backup` (23:30), `follow-up-digest` (09:00). `describe_default_handlers()`:

```
backup.snapshot: Write a verified snapshot of the database beside it (refuses instead of deleting old ones)
discovery.run: Run scheduled discovery (refuses while the source-quality gate is closed; no network access)
followup.digest: Report the follow-up days that are due or overdue (writes nothing; contacts nobody)
```

`discovery_run` refuses in three separate places - gate closed, no source enabled, no adapter
implemented - and returns `HandlerOutcome.REFUSED`, which is counted as neither success nor failure and
is never retried. That is the behaviour the new report preserves rather than re-deriving.

## Remote-worker status and laptop-off limits, from evidence

The README already states it plainly (section "What it does not guarantee"): *"This is a local worker,
not a service: close the terminal, shut the laptop, or sleep the machine, and nothing runs until you
start it again. Operating while the computer is off needs a separately deployed and verified worker,
which does not exist yet — so that capability is not claimed anywhere in this project."*

Verified against the code: the worker is started by `python -m career_agent --worker` and runs in the
foreground; there is no service unit, no daemon, no scheduler registration with the operating system,
and no remote storage boundary. `WorkerLease` is single-writer protection for *one SQLite file on one
machine* - a lease whose heartbeat goes stale is taken over, which is correct for crash recovery on one
machine and is **not** a distributed lock. So:

- **always-on operation: not available, and not claimed.** Nothing in this repository should be read as
  offering it.
- **a remote worker pointed at the local SQLite file: refused by design.** Roadmap item 8 says it, and
  this audit confirms nothing has quietly been built towards it.

## What was genuinely missing, and is now added

The audit's actual finding: *operational* reporting did not exist. `analytics.py` answers "how is the
search going?" (counts, rates, medians over the tracker). Nothing answered "what has this thing been
doing, and what needs me?" - last/next run, source outcomes, unverified applications, unresolved
attempts, dated work - which is P8 item 4. That is `career_agent/reporting.py`
(`daily_report`, `weekly_report`, `build_operations_report`), surfaced as `--report` / `--report
--weekly`, built from stored rows only, with three rules pinned by tests:

1. **queued is not done** - scheduled tasks, pending runs and prepared applications are reported as
   plans, never as outcomes;
2. **unknown leads** - unresolved attempts, timed-out runs and unverified submissions come first and
   are the only things counted as "needs you";
3. **a refusal is not a failure** - a refused discovery run is reported as the permission rule working.

The report deliberately does not duplicate `analytics.py`: one answers *how is it going*, the other
*what happened and what is stuck*.

## Still true, and worth repeating

- Nothing in the report, and nothing in the reporting module, can cause a fetch, a send or a
  submission. It reads.
- No notification is delivered anywhere - `--report` prints to a terminal a person chose to run.
  Notification preferences and delivery are roadmap item 5 and remain unbuilt.
- The report's section about sources quotes each gate's own reason rather than summarising it, so it
  cannot drift from `career_agent/sources.py`.

## Evidence

- `tests/test_reporting.py` — 21 tests, including the three rules above, a privacy check (no address,
  no skill, no name in the output) and three subprocess tests of the command itself.
- Existing suites that cover the audited pieces and still pass unchanged: `tests/test_tasks.py`,
  `tests/test_worker.py`, `tests/test_handlers.py`, `tests/test_store_tasks.py`,
  `tests/test_analytics.py`, `tests/test_integrations.py`, `tests/test_cli_worker.py`.
- Suite after this increment: **2389 OK (skipped=13)**.
