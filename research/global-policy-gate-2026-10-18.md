# The central policy gate (2026-10-18)

## What this increment is

The first half of P8's second item: the standing authorisation a person gives once and can revoke,
as a value and a decision (`career_agent/policy.py`). What it is **not**, yet: it is not stored, not
shown in the window, and not called from anywhere, because there is no external side effect to call
it from — discovery, submission, outbound email and inbox reading are all still closed. Persisting
it (a schema step), a control to grant and revoke it, and the call site immediately before each side
effect are the next steps, and nothing in this note claims they exist.

## What was inspected first (P8 item 1, in part)

* `career_agent/sources.py` — per-source `SourceDecision`, `PermissionState`, `discovery_gate` and
  `submission_gate` returning `GateResult(allowed, reason, conditions)`, all under
  `SOURCE_QUALITY_GATE_PASSED = False`. This is the *source's* half of the question and already
  fails closed; the policy must not duplicate or weaken it.
* `career_agent/integrations.py` — `OperationKind`, `Outcome`, `IntegrationLedger` (idempotency by
  operation id), `DisabledIntegration`, `dispatch_with_retry`. The mail/calendar side of the system
  already distinguishes "not enabled" from "request was wrong" from "provider failed", so the policy
  only has to answer "may this run at all", not "what happened".
* `career_agent/adapters.py`, `worker.py`, `tasks.py` — the adapter capability declarations and the
  scheduler/worker lease model. No existing abstraction carries a global authorisation, daily limit,
  quiet hour or stop switch, so this is new vocabulary rather than a second copy of an old one.

## The decision model

`GlobalPolicy(allowed, daily_limits, quiet_hours, stop_all, revoked_at)`:

* **The unit is a `(source_id, action)` pair.** "This board, for looking" is a different permission
  from "this board, for applying"; `ActionKind` has one member per independently gated capability
  (`discovery`, `submission`, `email_send`, `inbox_read`), so one can never read as another.
* **A limit is required, not optional.** An allowed action with no recorded daily limit is refused:
  an authorisation without a ceiling is how an automated system runs away with somebody's name on
  it. A limit of `0` means none today, and the limit is a ceiling (`done_today >= limit` refuses).
* **Quiet hours wrap.** `(22, 7)` is a night; `(9, 17)` is a working day; `(9, 9)` is refused at
  construction because it could mean "none" or "all day" and guessing is not this module's job.
* **Two ways to switch everything off**, both checked first: `stop_all` and `revoked_at`.

`evaluate_policy(policy, *, source_id, action, now, done_today, source_gate_allows)` returns a
`PolicyDecision(allowed, source_id, action, refusals)`:

* **It authorises, it never enables.** `source_gate_allows` is the source's own gate answer, passed
  in by the caller; `False` refuses whatever the policy says. A test composes a policy that
  authorises every action on a real source with the real `discovery_gate` and asserts every one is
  still refused — the property that matters most in a system whose gates are closed.
* **Every reason, not the first.** Somebody who turns off quiet hours should learn in the same
  breath that the daily limit is also reached.
* **Fails closed on anything unnamed**: unknown action, unnamed source, a clock with no timezone (a
  quiet hour on a naive clock is somebody else's quiet hour), a negative or invented count of what
  already ran. The count comes from the caller's durable records; this module remembers nothing.
* **It performs nothing.** A test reads the module's own source and fails if it ever mentions
  `requests`, `urllib`, `smtplib`, `imaplib`, `socket` or `subprocess`.

## Evidence

24 tests in `tests/test_policy.py` (model validation, each refusal path, the limit boundary, both
shapes of quiet hours, multi-reason refusals, and the two "this is not an enabler" properties). Full
local suite **2239 tests OK (skipped=13)**. `SOURCE_QUALITY_GATE_PASSED` is still `False` and
`enabled_discovery_sources()` is still `()`; this increment adds no capability, no network call and
no stored row.
