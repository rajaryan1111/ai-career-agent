# Confirming a stored profile fact, and asking for the facts that are missing

Date: 2026-10-16 · Task: `planning/arena-task-phase-a-profile-confirmation-and-setup-2026-10-16.md` ·
Branch: `arena/941d963f-ai-career-agent` · Scope: local, offline, no schema change, no external action.

**Status:** implemented, tested, and **green on the whole CI matrix**. The increment's final head `2514b52`
is verified by run **`38925910370`**: **13/13 jobs**, `Ran 2071 tests … OK` on every unit and cross-platform leg
(the skip counts differ by platform) and `RESULT: PASS — 113 checks passed` on the five display-backed legs.
The feature commit `982e87c` had been verified the same way by run `38914820675` (13/13 jobs, `Ran 2065 tests …
OK` per leg, the same 113 checks) before the second verification pass that section 7 records. Verified locally
as well: the full suite `Ran 2071 tests … OK (skipped=13)`, `compileall` clean, the stand-in acceptance run
`113 checks passed, 0 failed` (which reports **BLOCKED** by design — a stand-in Tk is not a desktop), and
**fourteen mutation checks, 14 of 14 detected**, one of them only after the gap the miss exposed was closed and
three of them added by the pass that fixed findings 4-6.

The human half is **not** done. This increment adds widgets, so it adds manual steps: **six numbered steps
(118–123)** in
[the local-alpha manual smoke-test checklist](local-alpha-manual-smoke-test-checklist-2026-10-14.md), all of
them **BLOCKED**, and no existing box was ticked. The checklist now stands at **123 steps: 22 PASS, 101
BLOCKED, 0 FAIL**.

Schema is still **8**, `EXPORT_FORMAT_VERSION` is still **2** and this increment does not touch it,
`SOURCE_QUALITY_GATE_PASSED` is still `False`, `enabled_discovery_sources()` is still `()`, and no socket is
opened anywhere in it.

## The question this note answers

The previous increment made the application *record* where each stored profile fact came from and whether the
person confirmed it, and left one thing undone, in its own words: "a fact can be confirmed through
`store.confirm_profile_fact` — tested from end to end — but there is **no control in the window** for it yet",
and the facts a profile does not state were discoverable in code but never asked for. So a candidate could
read a value the app had extracted from a résumé, and the only way to say *that is right* was to write code;
and a profile missing the country a listing is blocked on had no path that asked for the country.

This increment answers both, in the window, reusing what exists: one table of stored facts with their origins
and their confirmation state, one control that confirms the selected fact, and one setup flow that asks for
the required facts that are missing - and for nothing else.

## 1. The saved-facts table (`CareerAgentApp._build_profile_facts`)

Every fact the stored profile **states** is one row of a tree: the fact's plain-language name, its stored
value, where it came from, and whether the person has confirmed it. A fact with no value has no row at all,
because there is nothing stored to show and nothing anybody could confirm. The row id is the fact's canonical
name (`country`, `work_authorization`), which is what the store's confirmation call takes: the table cannot
select something that is not a fact, and no value a person typed is ever read back to decide which fact is
being acted on.

The four sentences are built by `career_agent/desktop_logic.py` and are unit-tested without a window:

| State | What the row says |
|---|---|
| typed in the form | `You typed it in this app` |
| read out of a document | `Read out of a document you chose (cv.docx)` |
| imported from a file | `Imported from a file you chose (export.json)` |
| stored before origins were recorded | `Not recorded — this profile was saved before the app kept track` |
| not confirmed | `Not confirmed yet — you have not checked this value` |
| confirmed | `Confirmed by you (2026-10-16 14:22:31 UTC)` |

A document or an imported file is named by its **name** and never by a folder: the store keeps no folder, and
`fact_origin_text` has none to show. The internal enum spellings (`extracted_from_document`,
`user_confirmed`) are never rendered — they are field names, not explanations.

The summary line under the table is one sentence: how many facts are stored, how many the person has
confirmed, and - where they exist - which of the six facts a listing can require are still not stated. It
never says a profile is complete; what can be complete is the set of required facts, which is a fact about
those six and about nothing else.

## 2. The confirm control, and the one path to a confirmed fact

`This is correct — confirm it` is built **disabled** and enabled only while exactly one stored fact is
selected, like the HR contacts tab's mark controls. Its handler calls `CareerStore.confirm_profile_fact` -
there is no SQL in the window - and then reads the row, the value and the provenance back out of the database
and reports **what the database says**, not what it intended:

- the row comes back confirmed and the value is unchanged → *"Confirmed: you checked Country. Its value and
  where it came from are unchanged."*
- the row was already confirmed before this press → *"Country was already confirmed by you; nothing changed,
  including the time."* (the store is idempotent, and the redraw keeps the row selected)
- the row does not come back confirmed, or its value moved → *"Confirmation not recorded …"* with the status
  line saying the confirmation could not be confirmed
- the store refuses (a fact the profile no longer states, a file older than schema 8) → the store's own
  message, with *"Nothing was confirmed; your saved profile is unchanged."* A refusal is decided before any
  row is written, which is what separates it from the failures below
- the call raised out of `confirm_profile_fact` any other way → see the next paragraph

**A failure is never turned into a sentence about a write.** `CareerStore.confirm_profile_fact` reads the
stored profile before its one transaction and again after it, and it commits the row before the last of those
reads - so an error raised out of that call can arrive *after* the person's confirmation is stored, and from
the window the two are indistinguishable. So the window does not say anything about what did or did not
change: `_resolve_confirmation_after_failure` reads the stored state and reports it. If the row comes back
confirmed, the window says so (and, when the row was already confirmed before the press, says *already
confirmed, unchanged, including the time*). If it does not, it says *"Nothing was confirmed for Country; your
saved profile is unchanged."* If even that read fails, it says the answer is **not known** - *"Confirmation not
verified … it is not known whether Country was recorded as confirmed"* - and names the safe way back:
confirming a fact that is already confirmed changes nothing, so the control can simply be pressed again once
the saved facts can be read. The one failure that says nothing was written at all is the read *before* the
attempt, where nothing has been tried yet.

Confirming a fact never rewrites its value or where it came from: a fact read out of a CV stays a fact read
out of a CV, now confirmed, and the document's name stays on the row. Nothing confirms a fact except this
action - not a save, not an import, not a résumé review, and not the setup flow's own write.

## 3. The setup window: only what is genuinely missing

`Set up missing required facts...` opens a window that is **rebuilt from storage** every time it is drawn -
when it opens and after every successful save - so what it asks for is what the database does not state, not
what the last handler believed.

- **What it asks.** One question per fact `core.missing_required_profile_facts` reports, in the profile's own
  order, from `_FACT_QUESTIONS` - one question and one hint per required fact, with a test binding the mapping
  to `REQUIRED_PROFILE_FACTS` so a required fact without a question would fail the suite rather than disappear.
  The study-status question offers `resume.study_status_choices()`, which is the same list the profile form's
  own combobox now uses, so an answer this dialog accepts is an answer the form can hold.
- **What it does not ask.** A fact that is stored is never asked for again, whatever its origin and whatever
  its confirmation state. Preferences - skills, locations, work modes, role types - are never asked at all: a
  listing cannot be blocked on them.
- **What it shows instead.** The required facts that are stored but not yet confirmed are listed beside their
  values and their origins with a checkbox: the open question is whether the value is right, and the answer is
  a confirmation, not a re-typed value.
- **What it writes.** Answers go through the same `build_candidate_profile` validation and the same
  `CareerStore.save_profile` write as the form above, so there is no second, weaker route into the stored
  profile. A blank is never inferred from the other answers and stays unknown. The profile is read back and
  compared before anything is confirmed; only then is one `confirm_profile_fact` call made per fact the person
  typed here or ticked, and only after that is the window rebuilt to say what is still not stated. Incomplete
  is reported as incomplete, in the window and in the status line.
- **What it never does.** Cancel, Escape, the window's close button and a declined confirmation write nothing;
  a validation refusal keeps what the person typed on screen; a write failure leaves the stored profile alone
  and says so; and a write that succeeds but cannot be read back says **"Saved, but not verified"** with the
  facts left unconfirmed rather than reported as done. One window exists at a time; opening the control again
  lifts the window that is already open.
- **What it says when the failure comes after the write.** This flow writes and verifies before it confirms,
  so it has *three* places where a read can fail around a write that already happened, and each one now has
  its own sentence rather than the shared one whose promise is "nothing was changed":
  the verification read-back (above), a read inside the loop that records the checks -
  *"Saved, but the rest could not be checked"*, naming what was recorded and saying plainly that the check it
  could not read is not known to be recorded, with the profile tab's **Refresh the saved facts** named as where
  to look - and the state read that follows the checks, where nothing is inferred from the failure at all: the
  window says the read failed and shows the state it read again, and the status line says the saved facts had
  to be read again to say what is still missing. A failed read is never allowed to decide a sentence about the
  profile, so a save that stored five facts cannot be described as missing all six.

## 4. What is reused, and what was deliberately not built

- **No second model, store, importer or tab.** The panel lives on the existing **Candidate profile** tab,
  inside the tab's existing scrolling body; the write path is the form's own; `CareerStore.confirm_profile_fact`
  is called rather than reimplemented; and the setup window's `Study status` choices are the profile form's.
- **No schema change.** Schema 8 already had every column this needs. `profile_fact_provenance` is written by
  the same `save_profile` and the same `confirm_profile_fact` as before.
- **No change to the JSON export.** Origins and confirmations stay local bookkeeping: the export is still
  `format_version: 2`, and no new key enters it.
- **Nothing was enabled.** The source-quality gate is still not passed, discovery is still empty, and the new
  code opens no socket and sends nothing.

## 5. Compatibility and privacy

- **An older database** (schema ≤ 7) upgrades exactly as before and every stated fact reads as *not recorded*;
  confirming one of those facts works and keeps its origin as *not recorded* - the app does not claim the
  person typed it. A file held before schema 8 still refuses a confirmation, with the store's own message.
- **A backup and a restore** carry the origins and the confirmations, because they copy every table.
- **Deleting the profile** still deletes its origins in the same transaction, and the table is emptied in the
  same action.
- **Privacy.** The table shows the person their own stored values - that is its purpose - and no value reaches
  a log, an event or a status line: the only new event is the store's existing `profile.fact_confirmed`, whose
  detail is the **fact's name** (`detail=fact=country`). The acceptance check asserts the value is *not* in the
  log, and the setup window's confirmation names the field and the value the person is about to save, which is
  their own screen and nobody else's.

## 6. Evidence

| What | Result | Command |
|---|---|---|
| Full suite | `Ran 2071 tests … OK (skipped=13)` | `python3 -m unittest discover -s tests` |
| Compile check | clean | `python3 -m compileall -q career_agent scripts tests` |
| Acceptance harness (development run) | `DEVELOPMENT RESULT: 113 checks passed, 0 failed` — `RESULT: BLOCKED` (no tkinter on this machine) | `python3 scripts/desktop_acceptance.py --stand-in-tk` |
| Mutation checks | **14 of 14 detected** | `python3 /home/user/scratch/mutation_checks_fact_review.py`, log beside it |
| CI matrix (final head) | **run `38925910370` @ `2514b52`: 13/13 jobs** — unit legs 3.10–3.14 `Ran 2071 tests … OK`, four cross-platform legs `Ran 2071 tests … OK` with `RESULT: PASS — 113 checks passed`, the Linux display leg with the same 113 checks and the smoke's 14, both installed-package legs and the optional-PDF leg | `gh run view 38925910370` |
| CI matrix (feature commit) | **run `38914820675` @ `982e87c1fc55375200e1ab3871cd655d126aa55b`: 13/13 jobs**, `Ran 2065 tests … OK` per leg and the same `RESULT: PASS — 113 checks passed` on the five display-backed legs | `gh run view 38914820675` |

The suite stood at **2004** tests at the commit this increment started from and stands at **2071** with it:
25 tests were added to `tests/test_profile_provenance.py` (74 in the file now) and 42 to
`tests/test_desktop_handlers.py` (386 in the file now - 36 with the feature and 6 with the honesty fixes in
section 7), and the acceptance harness gained 11 checks inside
workflow A (A7–A17) - a new workflow letter was deliberately **not** added, so the CI job's loop over workflow
letters is unchanged and `declared_step_count()` went from 102 to 113. The window smoke test's expectations gained the new list
(`facts_tree`, four columns) and its summary variable, so all five display-backed legs check that the new
controls exist and fill, not only that the workflow reached them.

## 7. What verification found

Eight things, all found by running the code rather than by reading it: **five defects in this increment's
own reporting** (1, 2, 4, 5 and 6 - three of them saying *nothing was changed* about a write that had
already happened, and one deciding what a profile states from a read that had failed), **two reporting
branches that had no test at all** (3 and 7), and **one thing the mutation harness itself was getting
wrong** (8). Three were found while the increment was written and five by asking the same question of the
paths around them - *does this sentence still describe what just happened?* - and every defect was reproduced
against the real store before it was fixed.

1. **The table dropped the row the person had just used.** Confirming a fact redraws the table, and the redraw
   lost the selection, so the second confirmation press - and any reading of "what happened to that row" -
   needed the row to be clicked again. Found by the repeated-confirmation handler test, fixed by capturing the
   selected fact's key before the redraw and restoring it when that fact is still stored. A mutation that
   removes that restore is caught.
2. **A write that had happened was reported as "Nothing was changed".** The setup save used the shared
   unreadable-record report - whose sentence promises that nothing was changed - on the read-back *after* the
   profile had already been written. Found by a handler test that fails the read once the write has succeeded.
   The post-write path now has its own honest sentence, **"Saved, but not verified"**, and the facts it could
   not confirm are left unconfirmed.
3. **One reporting branch had no test at all, and the mutation run is what said so.** The first mutation pass
   ran eleven mutations and caught ten; the miss was the branch that reports a fact as *already confirmed* when
   the setup save finds it confirmed at write time. That branch is reachable - two windows, or two runs of this
   application, on one database: the window draws a fact for confirmation, the same fact is confirmed somewhere
   else, and the person then presses save. A test was written for exactly that (`test_a_fact_confirmed_elsewhere_while_the_window_was_open_is_reported_as_unchanged`,
   which asserts the earlier confirmation's own time still stands and that this press does not claim the work),
   the mutation was re-run, and it is now caught. This is the second increment in a row where a green suite
   said nothing about an untested path and the mutation harness asked the question.
4. **A confirmation reported as "nothing was changed" after its row had been committed.** Reproduction: the
   read `confirm_profile_fact` makes *after* its own insert was made to fail, and the handler was run. The
   database held the confirmation - asserted in the test by reading it back - while the window's status line
   said *"A saved record could not be read; nothing was changed."* The handler now splits the pre-write reads
   (where that sentence is true) from the write call, and resolves anything raised out of the write call by
   reading the stored state and reporting it (section 2). The same defect covered the database-error branch,
   which had said *"the confirmation could not be written … nothing was recorded"* for a failure that may
   have come after the row was committed.
5. **The same sentence, one step later, in the setup save.** Reproduction: the read the confirmation loop
   makes before its first check was made to fail, after the answers had been written and read back. The
   window said nothing was changed while the answer was stored. It is now reported by
   `_setup_saved_but_unchecked` - saved, with the rest unchecked, and the uncertainty named (section 3).
6. **A failed read deciding the sentence "Still not stated: …".** Reproduction: the state read after the
   checks was made to fail while the earlier reads worked. The code read the profile as `None` and turned
   that into *all six required facts are missing*, for a profile that had just stored one of them - and the
   status line repeated the count. Nothing is inferred from a failed read now, and the note, the status line
   and the window's own state each come from a read that succeeded.
7. **A reporting branch with no test, again.** The loop's store-refusal sentence - *"Could not be confirmed
   (the local database refused the write): …"* - had no test at all, which the inspection that found 4-6
   turned up by looking for messages no test named. It is now covered: a refused confirmation is named, the
   stored value it refers to is asserted unchanged, and the sentence says the value is saved and can be
   confirmed again from the table.
8. **The mutation harness could call a crash a catch.** While adding mutations for 4-6, one of them left a
   syntax error behind (a two-line call patched as one line), which fails every module import - and the
   harness counted the failing run as *caught*. It now refuses that: a mutated copy that fails without one
   named test failing is reported as an invalid mutation, not as a detection. The three mutations added for
   4-6 are caught by the tests written for them, and one of the harness's own anchors had gone stale when the
   code moved - reported as `[stale]` rather than silently mutating nothing, which is what that guard is for.

One harness-side change is worth recording because it changed the *window's* own record: a check that read the
setup window's sentence by scanning label text was replaced by `ProfileSetupWindow.awaiting`, the rows the
window says it is offering for confirmation. A check that scrapes text can pass on a window that shows nothing;
a check that reads what the window says it drew cannot.

## 8. What a person still has to judge

Six numbered steps (118–123) cover the parts no harness can: whether the table and its sentences read clearly
and fit the tab at the window's opening size and at 900x600, whether a greyed-out confirm button *looks* greyed
out and whether the enabled one is obvious, whether the keyboard and the mouse can reach and use every control
(including the setup window's boxes and checkboxes) without a pointer, what a screen reader announces for a
table whose rows are a person's own facts, whether the setup window's wording makes it clear that a blank stays
unknown and that an answer typed there is recorded as confirmed *by the person*, and whether the confirmation
that a save is about to record is understood. None of that is measurable, which is why every one of those steps
stays **BLOCKED**.

## 9. Follow-ups

1. **Provenance for work-history and education records** (schema 6): they have their own tables and their own
   records, and per-record provenance for them is a separate decision.
2. **Origins between machines**: if a fact should carry where it came from through the portable JSON file, that
   is a separately versioned export document; version 2 stays as it is.
3. **Preferences as first-class setup questions** (skills, locations, work modes, role types): deliberately not
   asked here, because a listing cannot be blocked on them; a product decision about onboarding, not a bug.
4. **The conflict between two sources' values** - a résumé that disagrees with a stored fact is currently shown
   as the document's value beside the person's own, and a comparison view would be its own increment.
