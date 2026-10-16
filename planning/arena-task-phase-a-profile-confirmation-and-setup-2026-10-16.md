# Arena task: profile fact confirmation and the missing-information setup

Date: 2026-10-16
Repository: rajaryan1111/ai-career-agent
Working branch: `arena/941d963f-ai-career-agent` (the Arena session's own branch, based on `a22b917d`, the
head of PR #2). The increment is delivered on that branch and verified by the CI run attached to it; PR #2
stays open, unmerged and untouched, and `main` is not written to.
Status: implemented, tested and verified in CI; the manual GUI half stays BLOCKED until a person runs it.

## Why this is next

The previous increment recorded **where each stored profile fact came from and whether the person confirmed
it** (schema 8, written up in
`research/candidate-profile-provenance-2026-10-16.md`), and deliberately stopped there. `CareerStore.confirm_profile_fact`
existed and was tested end to end, but **no control in the window called it**, and the facts a profile does not
state were discoverable in code (`core.missing_required_profile_facts`) but never asked for. A stored value
could therefore only be confirmed by writing code, and a person whose profile was missing a fact a listing can
be blocked on had no path that asked them for exactly that fact. This task closes both halves.

## Scope

- Show every non-empty stored profile fact on the existing profile tab: its value, where it came from, and
  whether the person confirmed it - in plain language, with a document named by its **file name** and never by
  a folder.
- One explicit confirm action that reuses `CareerStore.confirm_profile_fact` (no SQL in the window), is
  idempotent, never changes a value or an original origin, refuses a fact with no value or a fact that is no
  longer stated, and reports what the database says *after* the write rather than what the handler intended.
- A targeted setup flow that asks only for the required facts the canonical
  `core.REQUIRED_PROFILE_FACTS` / `core.missing_required_profile_facts` report, never treats a preference as
  required, never infers an unknown fact, writes through the same `build_candidate_profile` /
  `CareerStore.save_profile` path as the form, confirms only what the person typed or ticked, recomputes what
  is still missing from storage, and writes nothing on cancel, Escape or a failed save.
- Reuse the existing model, store, importer and tab. No second profile model, no second store, no schema
  change, and no change to the version-2 JSON export contract.
- Extend the existing acceptance harness and the window smoke test rather than adding a parallel one, and add
  manual checklist steps for the parts only a person can judge, left BLOCKED.

## Required tests

- Tk-free tests for the review rows, the origin and confirmation sentences, the setup questions, and bindings
  that keep the one vocabulary (`PROFILE_FACTS`, `REQUIRED_PROFILE_FACTS`, the eligibility checks, the résumé
  labels) from drifting.
- Handler tests driving the real store and the real SQLite file: confirming, repeating a confirmation, a
  refusal with nothing selected, a stale row, a failed write, a read-back that does not match, an unreadable
  record; and for the setup window: a first run, a partly filled profile, values offered for confirmation
  instead of being asked again, a preference never asked, blanks staying unknown, a declined confirmation,
  cancel, Escape, a second window, an invalid answer, a failed write, a write that cannot be read back, and
  resumption after a restart.
- Acceptance checks inside the existing harness for every functional claim, and the window smoke test's
  expectations extended to the new list and summary so the display-backed legs check them too.
- Mutation checks on a disposable copy, so a green suite is not mistaken for a suite that bites.
- Full unit suite, compile check, all CI matrix legs and the display-backed acceptance workflows; the manual
  GUI steps remain BLOCKED.

## Non-negotiable constraints

- Keep `main` untouched and PR #2 open and unmerged. No force-push, history rewrite or destructive reset.
- Keep `SOURCE_QUALITY_GATE_PASSED = False` and `enabled_discovery_sources() == ()`. No live discovery, no
  external data transfer, no email, no application submission, no new source enabled to show progress.
- No real candidate data in repository files, fixtures, logs, screenshots or CI artifacts; a source document is
  remembered by name only.
- Do not mark a manual step passed without a person running it, and do not weaken an assertion, delete a test
  or relabel a failure to get a green run.
