# Conditions on which jobs may be acted on, and the counter that was missing — 2026-10-18

Closing the three named gaps in P8 item 2: the daily limit had no producer, and the authorisation
could not express a condition about the *job* being acted on (role, place, attachments, follow-ups).
Both turned up genuine defects on the way, which is the useful part of this note.

## The counter, and the two rules that decide what it counts

`CareerStore.actions_done_today(action, *, now)` counts attempts from the durable `action_attempt`
rows rather than from anything held in memory. Two deliberate rules:

- **a refusal does not spend the allowance it protected** - a refused attempt never left this
  machine, and counting it would let the permission rules consume the quota they just defended;
- **an unknown outcome does spend it** - if this application may have acted and nobody established
  what happened, the honest assumption is that it did; the alternative silently doubles a limit
  every time an outcome goes unconfirmed.

The day is the calendar day of `now` **in `now`'s own timezone**, so a limit resets at the person's
midnight rather than at UTC's; a test pins the two instants that fall on one day in UTC and two days
in Delhi. `integrations.COUNT_FROM_RECORDS` lets `guarded_dispatch` count for itself, taken *before*
the new attempt's own row is written - otherwise an allowance of one would refuse the first action of
the day for having already spent itself. `done_today=None` keeps meaning "nobody counted" and still
refuses.

## Two defects found while wiring it

1. **Attempts were stored under a name nobody else uses.** `begin_attempt` did `str(action)`, so an
   `ActionKind.DISCOVERY` was written as the literal text `"ActionKind.DISCOVERY"`. A caller holding
   the string `"discovery"` could never find that row - and the entire point of the attempt record is
   that the *next* caller finds it before acting again, so the duplicate block was failing quietly
   for any caller that did not happen to hold the same spelling. Fixed with one `_action_name`
   helper at the store's edge, regression-tested from both spellings.
2. **The permissions tab rebuilt the policy field by field.** Granting a permission, removing one or
   moving the stop switch constructed a fresh `GlobalPolicy` from the fields the tab knows about -
   so the moment conditions existed that the tab does not show, any change there would have dropped
   them. That is a silent *loosening* of a restriction somebody wrote down: the worst direction for
   an authorisation screen to be wrong in. Now `dataclasses.replace`, with a regression test that
   sets all four conditions, grants a permission, moves the stop switch and re-reads them.

The second was found by asking "what else constructs this value?" after adding a field - worth doing
every time a frozen value gains one.

## The conditions themselves

`PolicySubject(role_title, location, attachments, follow_ups_so_far)` describes what an action is
about; it is separate from the policy so that *a caller which cannot describe its subject gets a
refusal rather than an exemption*. `GlobalPolicy` gains `role_terms`, `locations`,
`allowed_attachments` and `follow_up_limit`, all part of `content_key()` (a tightened authorisation
is a different authorisation, and gets its own stored version) and all round-tripped through the
stored payload.

Fail-closed in both directions:

- conditions recorded but no subject given → refuse;
- a condition recorded but the subject is silent on it (no title, no location, no count) → refuse;
- an attachment with **no** attachment rule recorded → refuse: nothing may be attached until
  something says what may;
- a file ending outside the rule → refuse.

Every failed condition is reported together, so somebody fixing one learns about the other three now
rather than an attempt later. Conditions can only ever *narrow*: `source_gate_allows=False` still
refuses a subject that satisfies everything.

`guarded_dispatch` counts a job's prior follow-ups from its own attempt rows when a limit is recorded
and the caller did not supply one, so the per-job limit is enforced from durable evidence.

## What is still not done

- The window shows no editor for conditions or quiet hours. It now *preserves* them, which is the
  safety property; editing them is still command-line and API only.
- No external side effect is permitted today, so every one of these refusals fires in a world where
  the gate would refuse anyway. The conditions are the layer that will matter when a gate opens.

## Evidence

- `tests/test_policy_conditions.py` — 22 tests (model, stored form, enforcement, wiring through
  `guarded_dispatch`).
- `tests/test_attempts.py` — 12 new tests for the action-name regression and the day counter.
- `tests/test_desktop_handlers.py` — the silent-loosening regression.
- Suite: **2457 OK (skipped=13)**.
