# Confirming a stored profile fact, and asking for the facts that are missing

Date: 2026-10-16 · Task: `planning/arena-task-phase-a-profile-confirmation-and-setup-2026-10-16.md` ·
Branch: `arena/941d963f-ai-career-agent` · Scope: local, offline, no schema change, no external action.

**Status:** implemented, tested, and **green on the whole CI matrix**: run **`38914820675`** at **`982e87c`**,
**13/13 jobs**, with every unit and cross-platform leg reporting `Ran 2065 tests … OK` (the skip counts
differ by platform) and the five display-backed legs reporting `RESULT: PASS — 113 checks passed`. Verified locally as well: the full suite
`Ran 2065 tests … OK (skipped=13)`, `compileall` clean, the stand-in acceptance run `113 checks passed,
0 failed` (which reports **BLOCKED** by design — a stand-in Tk is not a desktop), and **eleven mutation
checks, 11 of 11 detected**, one of them only after the gap the miss exposed was closed (section 7).

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
  message, with *"Nothing was confirmed; your saved profile is unchanged."*
- the database cannot be written → *"Not confirmed"* and the status line says nothing was recorded

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
| Full suite | `Ran 2065 tests … OK (skipped=13)` | `python3 -m unittest discover -s tests` |
| Compile check | clean | `python3 -m compileall -q career_agent scripts tests` |
| Acceptance harness (development run) | `DEVELOPMENT RESULT: 113 checks passed, 0 failed` — `RESULT: BLOCKED` (no tkinter on this machine) | `python3 scripts/desktop_acceptance.py --stand-in-tk` |
| Mutation checks | **11 of 11 detected** | `python3 /home/user/scratch/mutation_checks_fact_review.py`, log beside it |
| CI matrix | **run `38914820675` @ `982e87c1fc55375200e1ab3871cd655d126aa55b`: 13/13 jobs** — unit legs 3.10–3.14, four cross-platform legs, five display-backed acceptance legs reporting `RESULT: PASS — 113 checks passed`, both installed-package legs and the optional-PDF leg | `gh run view 38914820675` |

The suite stood at **2004** tests at the commit this increment started from and stands at **2065** with it:
25 tests were added to `tests/test_profile_provenance.py` (74 in the file now) and 36 to
`tests/test_desktop_handlers.py` (380 in the file now), and the acceptance harness gained 11 checks inside
workflow A (A7–A17) - a new workflow letter was deliberately **not** added, so the CI job's loop over workflow
letters is unchanged and `declared_step_count()` went from 102 to 113. The window smoke test's expectations gained the new list
(`facts_tree`, four columns) and its summary variable, so all five display-backed legs check that the new
controls exist and fill, not only that the workflow reached them.

## 7. What verification found

Three things, all found by running the code rather than by reading it:

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
