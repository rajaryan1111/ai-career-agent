# Cross-source job identity, idempotency and unknown outcomes — 2026-10-18

P8 item 3. Three separate problems that only look like one: *is this the same job?*, *has this already
been done?*, and *did that actually happen?* The third is the hard one, and the one most frameworks
answer by guessing.

## 1. Identity — `career_agent/identity.py`

Three verdicts, not two: `SAME`, `DIFFERENT`, `UNKNOWN`.

| Evidence | Verdict |
| --- | --- |
| same employer + same requisition id | `SAME` (basis: the employer's own requisition id) |
| same canonicalised employer apply URL | `SAME` |
| same canonicalised source listing URL | `SAME` |
| different employers | `DIFFERENT` |
| same employer, two different requisition ids | `DIFFERENT` |
| same employer, two *spellings* of one id (`REQ-42` / `REQ 42`) | `UNKNOWN` |
| same employer, same title, no shared identifier or page | `UNKNOWN` |

`identity_key()` is strict: case and surrounding whitespace are folded, punctuation is **not**. An
identifier is opaque, and normalising `REQ-42` into `REQ42` would be this module deciding that two ids
are one. But the comparison does not call those pairs *different* either - it reports `UNKNOWN` and
`possible_duplicates()` hands them to a person. The asymmetry is deliberate: a missed merge costs the
person seeing a job twice; a wrong merge costs them a job they never applied for. Title similarity is
never evidence of anything.

## 2. Attempts — `career_agent/attempts.py` + schema 12

`action_attempt(operation_id PRIMARY KEY, identity_key, action, state, started_at, settled_at, detail,
evidence)`, keyed by **identity**, not by listing id, so the same vacancy found on two sources cannot
be applied to twice.

The order matters more than the table:

1. `begin_attempt()` writes the row **before** the act, in state `unknown`. A process that dies between
   the write and the act leaves evidence; a row written afterwards would leave silence.
2. The act runs.
3. `settle_attempt()` records what was *observed*.

`state_from_outcome` is where the honesty lives:

| Integration outcome | Recorded state | Why |
| --- | --- | --- |
| `completed`, `duplicate` | `PERFORMED` | it happened |
| `disabled`, `invalid`, `unsupported` | `REFUSED` | nothing was attempted - that is knowledge |
| `failed` | **`UNKNOWN`** | a failure mid-flight may still have arrived |

`may_attempt()` refuses a further attempt while any `UNKNOWN` exists for that identity and action
("it may already have happened") and while one is `PERFORMED` ("a second one is a duplicate, not a
retry"). Both reasons are reported, not the first one.

**Time resolves nothing.** `attempts_needing_reconciliation()` lists unknown attempts older than a
threshold (default 6 hours) so somebody can go and look; it changes no state, and nothing else may
settle an attempt on the strength of its age. The only way out of `unknown` is
`reconcile_attempt(state=…, evidence=…)`, which **requires** the person's note of what they checked -
blank evidence is refused rather than stored as a confident-looking record of nothing. A settled
attempt is never rewritten.

A row that cannot be decoded raises `StoredRecordError` and is reported by the doctor, because the
convenient reading - "nothing was attempted" - is exactly the one that would permit a blind retry.

## 3. The door — `integrations.guarded_dispatch`

`guarded_dispatch(store, integration, draft, *, identity_key, policy, source_id, now, done_today,
source_gate_allows)` composes the three: read the record → refuse or write the attempt → dispatch
through `authorised_dispatch` (policy and gate still decide) → settle from what was observed. A failed
dispatch returns with its message extended: *"Whether it arrived could not be established, so it is
recorded as unknown and no further attempt will be made at this job until you check and reconcile
it."*

An `EmailDraft` derives a stable `operation_id` from its own content, so two identical messages are
one operation - the test asserts it rather than assuming it.

## What is still not true

- **Nothing sends.** Every test here ends in a refusal or in the local stand-in ledger; no provider is
  enabled, no gate is open, and `guarded_dispatch` cannot change either.
- **Submissions are not wired.** The door exists for email. A submission path does not exist to guard.
- **Nothing surfaces this in the window yet** - no tab lists unresolved attempts or possible duplicate
  pairs, and `attempts_needing_reconciliation` has no caller in the UI.
- **No automatic reconciliation.** By design: this machine cannot establish what a provider did, and
  the evidence requirement makes that explicit rather than polite.

## Evidence

- `tests/test_identity.py` — 22 tests.
- `tests/test_attempts.py` — 43 tests (record invariants, the retry rule, outcome translation,
  staleness, the stored half, and the guarded door including the cross-source block).
- Schema literals re-pinned deliberately at **12** in `tests/test_store.py` and
  `tests/test_store_tasks.py`; `tests/test_policy_store.py` now pins "11 or later" plus the current
  version, so the authorisation's own tests do not need editing at every future step.
- Suite: **2368 OK (skipped=13)**.
