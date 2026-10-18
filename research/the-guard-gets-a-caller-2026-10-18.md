# The guard gets a caller

**Date:** 2026-10-18
**Increment:** the Follow-ups tab reaches `integrations.guarded_dispatch`; one defect found and fixed.

## The gap

`guarded_dispatch` has carried the whole outbound order since it was written - do-not-contact, then
what is already recorded for this job, then the standing authorisation, then the enabling gate, then
the integration, with a write-ahead attempt row in the middle so a crash leaves evidence. Every one of
its paths was tested. **Nothing a person could press reached it.** The follow-up tab stopped at a
read-only draft with no recipient, and the comment that mentioned the guard was in another module.

A guard with no caller is a claim, not a control. This increment gives it one.

## What the window does now

A third control on **Follow-ups**: a recipient chooser and **Try to send this follow-up...**.

- **The recipient can only be a stored HR contact.** No typing. An address on the do-not-contact list
  is not offered - `dispatch_recipient_choices(contacts, blocked)` filters on the contact row's mark
  *and* on the separate suppression list, because those are two different records and either is enough.
- **One confirmation**, which states the five checks in the order the guard applies them, says the
  attempt is written down before it is made, and says the honest expectation in this build is a
  refusal.
- **The result is whatever the guard returned**, shown in a read-only dialog: a refusal says nothing
  left the machine; a performed dispatch would say the integration accepted it and explicitly *not*
  that it was delivered, read or replied to.
- `source_gate_allows=False` is passed explicitly, with the reason in a comment: no mailbox route has
  ever been enabled, and reading a *discovery* decision here would let permission to read a site stand
  in for permission to write to a person.

## The defect this found

Pressing the button twice for the same job raised `AttemptError: ... already recorded as refused; a
settled outcome is not rewritten` out of the store.

The operation id is derived from the message's content **on purpose** - the same draft asked for twice
is the same operation, and putting a timestamp in it would be the bug idempotency keys exist to
prevent. So the second press rebuilt the same id, found its write-ahead row already settled, and tried
to settle it again. Every earlier caller built a fresh message each time, so nobody had hit it.

Fixed inside the guard, where the ordering lives: before the write-ahead row is written, an operation
id that already has a **settled** attempt is answered with an `IntegrationResult` naming the recorded
outcome and the date, `performed=False`, nothing sent, no second row. An attempt still **unknown** is
left to `may_attempt`, which blocks it as it always did. Regression tests:
`tests/test_integrations.py::RepeatedOperationTests` (4).

**Known limitation, written down rather than worked around:** because the id is content-derived, a
message refused today and attempted again after the authorisation changes is reported as "already
attempted and recorded as refused" instead of being retried. In this build that is academic - every
attempt is refused anyway, since the route has no authorised mailbox - but when one exists the ledger
needs a deliberate answer: either a refusal is not an attempt and may be re-opened, or the message must
differ. Not guessed at here.

## Evidence

- `tests/test_desktop_handlers.py::FollowUpDispatchTests` → **9 tests, OK**: only stored contacts are
  offered; no recipient means no attempt; the question states the order; a confirmed attempt is refused,
  recorded once and explained; a refusal does not spend the daily allowance; a suppressed address is
  withdrawn from the chooser *and* refused if forced past it, before any row is written; the same
  message twice writes one row; an unresolved attempt at the same job blocks the next one; and - the
  one that matters most - **a full standing authorisation and a working `LocalMockIntegration` still
  cannot send**, because the gate is closed in code and no authorisation opens a gate.
- `tests/test_desktop_logic.py::DispatchTextTests` → **7 tests, OK** (the prose, including that a
  performed dispatch is never called delivered).
- `tests/test_integrations.py` → **88 tests, OK** (4 new).
- `python scripts/desktop_acceptance.py --stand-in-tk` → **145 checks, 0 failed** (new steps H15-H19).
  A stand-in is not a display; this run is reported as BLOCKED, as always.
- Full suite: **Ran 2631 tests, OK (skipped=13)**.

## What is still true

Nothing in this build can send anything. The integration is disabled, the route's gate is closed, and
P8 item 7 - an authorised mailbox, delivery and reply evidence, inbox reading - remains blocked on a
permission this project does not have. What changed is that the refusal is now something a person can
produce on purpose, read in their own records, and check.
