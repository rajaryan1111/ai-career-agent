# Where a profile fact came from, and whether a person confirmed it

Date: 2026-10-16 · Task: `planning/arena-task-phase-a-verified-candidate-profile-provenance-2026-10-16.md` ·
Branch: `arena/351e052d-ai-career-agent` · Scope: local, offline, one additive schema table, no external action.

**Status:** Implemented and tested locally; **not yet pushed and not yet verified on CI**. What is proven today,
with output: the full suite `Ran 2004 tests … OK (skipped=13)`, `compileall` clean, the stand-in acceptance run
`102 checks passed, 0 failed` (which reports **BLOCKED**, by design — no stand-in is a desktop), and fourteen
mutation checks on a disposable copy, **14 of 14 detected** — `exit 0`, the log is
`/home/user/scratch/mutation_checks_provenance.log`. The human half is **not** done: no new manual step was
added and none existing was ticked, because this increment adds no widget; the checklist still stands at
**117 steps, 22 PASS / 95 BLOCKED / 0 FAIL**.

Schema is now **8** — one new, initially-empty table (`profile_fact_provenance`). `EXPORT_FORMAT_VERSION` is
still **2**, and an export is asserted to carry none of the new vocabulary; the limitation is stated rather than
silently resolved (section 5). `SOURCE_QUALITY_GATE_PASSED` is still `False`,
`enabled_discovery_sources()` is still `()`, and this increment opens no socket and sends nothing.

## The question this note answers

The profile could hold ten facts and a timestamp, and nothing recorded *where* any of them came from. A country
typed into the form, a graduation year accepted out of a local DOCX, and a skills list imported from a JSON file
exported by another machine all landed in `candidate_profile.payload` as the same bytes. The application could
therefore not keep the one promise this increment exists for: **a value it read somewhere must never be shown as
something the person said about themselves** — and after a résumé import it said the opposite, in the words
"Verified in the local database", where *verified* was a claim about the person because the reader had no other
way to take it.

## 1. The model, and why each piece is shaped that way (`career_agent/core.py`)

- **`PROFILE_FACTS`** fixes the vocabulary: `country`, `degree`, `study_status`, `graduation_year`, `experience`,
  `work_authorization`, `skills`, `locations`, `work_modes`, `role_types`. These are the **profile form's own
  keys** — the same ten the form reads and writes and the same ten `resume.FieldProposal.key` proposes values
  under. A second spelling for the same ten facts would be a second thing to keep in step, so a test binds the
  three together.
- **`REQUIRED_PROFILE_FACTS`** is the six `evaluate_eligibility` can be blocked on (country, degree, study
  status, graduation year, experience, work authorization). The four preferences are deliberately not required:
  they are choices a person makes, not facts a document or a person can be right or wrong about. The discoverable
  question this increment owes a future setup flow is *which of these six does the stored profile not state* —
  and a test reads `evaluate_eligibility`'s own source to fail if the two lists drift apart. It is a
  "worth supplying" list, never a gate.
- **`FactSource`** is `unknown` / `user_entered` / `extracted_from_document` / `imported_from_file`, and
  **`unknown` is load-bearing**: it is the honest answer for a fact stored before this build existed, and it is
  not the person's own words.
- **`FactVerification`** is `unverified` / `user_confirmed` — two states, not three, because the question is only
  ever "did the person say this is right".
- **`document_name_only`** reduces a path to the file's **name**, on both separators, and returns `None` for a
  value that names no file at all (empty, `/`, or a path ending in a separator). A folder path written into a
  database that gets backed up is somebody's home directory (`C:\Users\…\CV.docx`), and a path that names a
  folder names no document, so there is nothing to record.
- **`profile_fact_values`** is the single renderer: a stored profile as its ten facts, exactly as the form shows
  them. `desktop_logic.profile_form_values` now **delegates** to it instead of keeping a second copy, and
  `missing_profile_facts` / `missing_required_profile_facts` / `changed_profile_facts` are built on the same
  function — which is what makes "which facts did this write change" answerable rather than guessed.

## 2. The rule the increment enforces

1. **Nothing but an explicit confirmation confirms a fact.** `confirm_profile_fact(fact)` is the only path to
   `user_confirmed`; the writes that come out of a document, an import, or a form save can never set it.
2. **A save records an origin only for the facts it changed.** Merging reviewed résumé values into a form
   refreshes the facts it touched and leaves every other fact's origin exactly as it was — so accepting one value
   out of a résumé cannot quietly turn a typed profile into "read out of a document", and cannot turn anything
   into "the person's own".
3. **A document is remembered by name, never by folder**, because the database is backed up, exported and
   restored, and a folder is not one of the facts anybody agreed to store.
4. **An old file reads as `unknown`, not as the person.** A database written before schema 8 upgrades, keeps
   every row, and reports every stated fact as `unknown`; re-saving unchanged values records nothing, so an
   upgrade cannot attribute old facts to anybody.
5. **Deleting the profile deletes its origins in the same transaction.** "Delete my profile" that leaves a row
   saying *this came out of CV.docx* is not a deletion.
6. **A refusal never quotes the row.** These messages are written to be readable in a report; they name the field
   and what is wrong with it, and a value this build cannot interpret is described, not printed.

## 3. Storage (`career_agent/store.py`, schema 8)

One additive, initially-empty table, created by a new migration step keyed `8`:

```
profile_fact_provenance(fact TEXT PRIMARY KEY, source TEXT NOT NULL, verification TEXT NOT NULL,
                        document_name TEXT, recorded_at TEXT NOT NULL, confirmed_at TEXT)
```

`SCHEMA_TABLES_BY_VERSION[8]` is the version-7 list plus that table, so the drift test in `tests/test_backup.py`
(which compares the newest list against a freshly initialised database) passes unchanged.

- `save_profile(profile, *, source=FactSource.USER_ENTERED, document_name=None) -> tuple[str, ...]` writes the
  profile row and one origin row per **changed** stated fact in **one transaction** (`ON CONFLICT(fact) DO
  UPDATE`, `confirmed_at = NULL`); a fact the write no longer states has its origin row deleted with the value it
  described. It returns the facts whose origin it recorded. It refuses `source=UNKNOWN`, requires a document name
  for `EXTRACTED_FROM_DOCUMENT`, refuses one for `USER_ENTERED`, and allows one for `IMPORTED_FROM_FILE`.
- `get_profile_fact_provenance()` decodes **every** stored row first — an uninterpretable row is refused, not
  passed over — then returns one record per **stated** fact in `PROFILE_FACTS` order. A stated fact with no row
  reads `unknown`, never `user_entered`. `()` when no profile is stored. Strictly read-only.
- `confirm_profile_fact(fact)` refuses a key that is not a fact, a fact the stored profile does not state, and a
  file held at an older version; it is idempotent, and it never changes the source or the document name.
- `_schema_records_fact_provenance()` is the recorded version being ≥ 8 — deliberately **not** a probe for the
  table, so a file that claims schema 8 and is missing the table fails loudly instead of silently not recording
  anything. A write to a pre-8 file still succeeds and returns `()`, with a distinct log line
  (`origin=not recorded (this file predates schema 8)`) rather than a count that would be a fiction.

`profile.saved` now carries `facts=<count> origin=<source>`; the new `profile.fact_confirmed` carries
`fact=<name>` — a **field name**, never a value. `erasure.py` needed no change: it deletes files (the database,
its sidecars, the logs) rather than rows, and the origins live inside the database file.

## 4. Who writes an origin, and what each write is

| Producer | Recorded as | Site |
|---|---|---|
| The person typing in the form | `user_entered`, **unverified** | `desktop.py` `_save_profile` |
| "Save selected values" after a résumé review | `extracted_from_document`, the document's **name**, unverified | `desktop.py` `_apply_accepted_profile_values` |
| A JSON export imported into an empty profile | `imported_from_file`, the file's **name**, unverified | `importer.apply_import(..., document_name=…)`; the CLI passes `source.name`, the window `Path(chosen).name` |
| A profile stored before schema 8 | reads as `unknown`; a re-save of unchanged values records nothing | — |

A person's own save is recorded as theirs and **unverified**: the application knows who typed it, not that it is
right, and it does not conflate the two.

## 5. Compatibility findings, and the one thing deliberately not done

- **JSON export version 2 is unchanged.** Origins are not a field of `CandidateProfile`, so `asdict(profile)` and
  therefore the exported bytes do not move: a test exports a profile with origins recorded and asserts
  `format_version == 2`, the identical profile keys, the identical top-level keys, and that the document contains
  none of `profile_fact_provenance`, `extracted_from_document`, `user_confirmed`, `document_name`, or the
  document's name. (`provenance_note` is a **listing's** long-standing field and is untouched — the bare word
  appears in every export for that reason alone, which is why the test asserts on the vocabulary, not the word.)
- **This was a decision, not an oversight.** Adding origins to version 2 would change a contract other builds
  read, and the task says not to do that silently. Provenance therefore stays local bookkeeping in the database,
  travels with a **backup/restore** (a backup copies every table), and is **absent from the portable JSON file** —
  stated here, in the README, and in the PRD, with the follow-up named: if a later increment wants facts to carry
  their origin between machines, that is a separately versioned export document, not a new key in version 2.
- **An old file.** Schema-7 databases upgrade in one step with a verified copy taken first (the pre-existing
  migration machinery); nothing is downgraded; a backup written by an older build is still accepted, because
  `backup.py` accepts every version from 1 to `SCHEMA_VERSION`.
- **Gates.** `SOURCE_QUALITY_GATE_PASSED` is `False`, `enabled_discovery_sources()` is `()`, and no socket is
  opened anywhere in this increment.

## 6. Evidence

| What | Result | Command |
|---|---|---|
| Full suite | `Ran 2004 tests … OK (skipped=13)` | `python3 -m unittest discover -s tests` |
| Compile check | clean | `python3 -m compileall -q career_agent scripts tests` |
| Display-backed acceptance | `DEVELOPMENT RESULT: 102 checks passed, 0 failed` — `RESULT: BLOCKED` (no tkinter on this machine) | `python3 scripts/desktop_acceptance.py --stand-in-tk` |
| Mutation checks | **`14 of 14 detected`** (13 by the test named for the mutation, 1 by three other tests) — `exit 0` | `python3 /home/user/scratch/mutation_checks_provenance.py` |

The suite stood at 1950 before this increment; the new coverage is the 49 tests of
`tests/test_profile_provenance.py`, two schema-8 migration tests in `tests/test_store.py`, two regression tests in
`tests/test_importer.py`, and one in `tests/test_desktop_handlers.py`.

The mutation harness works on an isolated copy (never the checkout), verifies the unmutated copy green first,
requires each anchor to match exactly once, compiles every mutation, and restores each file byte-for-byte. It
broke, one at a time: a typed write recorded as confirmed; every save re-attributing every fact; a save recording
nothing; a stated fact with no row reading as user-entered and as confirmed; confirmation of a fact with no value;
the whole path stored as the document name; the résumé path dropping its origin; the résumé path naming another
file; an import recorded as the person's own; deletion leaving origins behind; an unreadable row passed over; and
an older file claimed to record origins, and a contradictory origin row escaping a read as a programming
error. **Every one was detected** — the résumé-path mutation only after the gap described in section 7 — and
one of them (a save that records no origin) was caught by three *other* tests rather than the one named for
it, which is why the log reports 14 of 14 detected and 13 by the named test.

## 7. What verification found, and why the tests did not

Four defects, all found by running code rather than by reading it:

1. **A damaged record was reported as invalid input.** `StoredRecordError` subclasses `ValueError`, so the new
   `except ValueError` on the résumé save path — written for form validation — caught a stored record this build
   cannot read and told the person the values they typed were unusable. Caught by an existing read-back test in the
   full suite, not by review. Fixed by catching `StoredRecordError` **first** in both `_save_profile` and
   `_apply_accepted_profile_values`; the fix has the read-back assertion it always had, plus the ordering.
2. **`save_profile` claimed to have recorded origins on a file that has no table for them.** Fixed: it returns
   the facts actually recorded (`()`) and logs that origins were not recorded.
3. **Nothing asserted the résumé review path's provenance at all.** The `save_profile(..., source=
   EXTRACTED_FROM_DOCUMENT, document_name=…)` call site could have dropped the origin, or recorded another
   document's name, with the whole suite still green. This was found **only by the mutation run** — the first pass
   ran 12 mutations, ten were caught, and the résumé-path mutation was **missed**; a test was written for it
   (`test_accepted_values_are_recorded_as_read_out_of_that_document_and_unconfirmed`), the mutation re-run, and
   the path is now covered. A green suite says nothing about an untested data path; the mutation harness is what
   asks.

4. **A contradictory origin row escaped a read as a programming error.** A row each of whose fields is
   one this build knows, but which contradict each other - an origin claiming the person typed the value
   while naming a document - raised a bare `ValueError` out of `get_profile_fact_provenance` instead of the
   store's own `StoredRecordError`. Found by hand-editing a row while reviewing the decoder, which is exactly
   how such a row arrives in the field. Now reported as the damaged record it is, with a test
   (`test_a_row_whose_fields_contradict_each_other_is_reported_as_damaged`) and a mutation check of its own.

## 8. What a person sees today, and the gap that is stated rather than papered over

No widget was added: this increment is the storage-and-truth baseline, and the task says not to build the asking
flow here. Two sentences changed:

- After a résumé import, the completion message no longer says "Verified in the local database". It says the
  values were written to the local database and read back to check them, and that the app recorded them as
  **values read out of that document** and **as not confirmed by you** — "a sentence in a document is not your own
  statement about yourself, and this app does not treat it as one."
- A typed save still says the candidate profile was saved locally: true, and no claim beyond it.

**The gap:** a fact can be confirmed through `store.confirm_profile_fact` — tested from end to end — but there is
**no control in the window** for it yet. That control belongs with the setup flow that also asks for the required
facts a profile does not state (`missing_required_profile_facts` is what that flow will read), where the value
being confirmed can be shown beside the control; a bare "confirm" button added here would have been a guess about
an interaction this increment does not own, and the message that had promised such a button was reworded rather
than left pointing at a control that does not exist. This is the first follow-up, not a hidden one.

## 9. Follow-ups

1. The confirmation control and the targeted-questions setup flow (section 8), within the profile tab's existing
   1120×760 non-scrollable budget or with the tab's layout measured again if it grows.
2. Provenance for **work-history and education records** (schema 6) — they have their own tables and their own
   records, and per-record provenance for them is a separate decision.
3. If origins should travel between machines, a **separately versioned** export document; version 2 stays as it
   is.
4. `README.md`, `design.md`, `prd.md`, `phases.md` and `memory.md` carry the behaviour as implemented; the
   completion report for this task lists the exact files, counts and the CI run once it has been read.
