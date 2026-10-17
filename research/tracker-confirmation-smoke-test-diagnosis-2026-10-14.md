# Tracker Confirmation Smoke-Test Diagnosis — 2026-10-14

## What was reported

A desktop smoke test on macOS left this state in the local database
(`~/Library/Application Support/AI Career Agent/career_agent.sqlite3`):

- Job: `Example Test Company` / `AI/ML Intern` / requisition `TEST-001` / listing id
  `dd559b6c-9674-4791-93c9-55f6e5eae71c`, availability `unknown`, scope `restricted`, source URL
  `https://example.com/jobs/ai-ml-intern`, no employer application URL.
- Tracker: status `confirmed`, `candidate_confirmed = 1`, evidence containing repeated instructional
  text that tells the reader what evidence to enter and warns not to confirm a simulated submission.

No application was ever submitted. The `confirmed` row is therefore misleading, and the confirmation
was recorded with text that the application itself (or its own checklist) supplied as guidance rather
than with a record of what an employer showed.

## How the failure was reproduced in this environment

The Mac database is not reachable from this checkout, so the reported shape was reproduced
deterministically against a throwaway file-backed database, driving the same code paths the GUI uses
(`ApplicationTracker.transition` → `CareerStore.save_tracker`):

```
empty                -> REFUSED: Confirmation requires evidence; a click or attempted submission is not proof.
app guidance         -> ACCEPTED as confirmed; candidate_confirmed=1
                        evidence now: 'A confirmed application requires evidence. An attempt or timeout is no'
checklist guidance   -> ACCEPTED as confirmed; candidate_confirmed=1
dialog label         -> ACCEPTED as confirmed; candidate_confirmed=1
persisted row: {'status': 'confirmed', 'evidence': 'A confirmed application requires evidence. ...', 'confirmed': 1}
```

That is the reported defect, reproduced: any non-empty string — including this project's own
instructions — was accepted as proof of an employer confirmation, and the program asserted
`candidate_confirmed` on the user's behalf.

## Root cause

Three distinct causes, in order of importance:

1. **The software asserted the confirmation, not the person.** `desktop._update_status` set
   `candidate_confirmed=True` automatically whenever the selected status was `confirmed`. The only
   human input was a free-text string, so a click sequence alone produced a record claiming the
   candidate confirmed a real application. The field is named `candidate_confirmed` — a claim about
   the person — but the person was never asked to make it.
2. **The evidence field had no floor beyond "not empty".** Instruction text that the app and the
   smoke-test checklist themselves display ("A confirmed application requires evidence. An attempt or
   timeout is not proof.", "Evidence / note (required to confirm)", "Confirm with a meaningful
   evidence note…") was storable as the evidence for a confirmation, where it then reads as proof.
   The checklist step 12 told the tester to "Confirm with a meaningful evidence note", which invites
   exactly this paste.
3. **No honest exit from a mistaken confirmation.** From `confirmed` the state machine permits
   `response_received`, `interview`, `rejected_by_employer`, and `withdrawn`. Three of those are false
   claims about an employer; only `withdrawn` is truthful for a record where nothing was ever
   submitted. The GUI can withdraw, but it deliberately never clears a stored `candidate_confirmed`
   flag on its own, and it cannot revise the evidence of the current status (re-applying a status is
   an explicit no-op, by design from Phase 1.1). So the misleading `candidate_confirmed = 1` could
   not be corrected through the UI at all.

## What can be validated, and what cannot

Recorded because the fix depends on the distinction:

- **Can be validated deterministically:** evidence is non-empty after trimming; evidence is not this
  project's own instructional text; evidence is not a bare placeholder (`todo`, `n/a`, `yes`, …); the
  transition is permitted by the state machine; `candidate_confirmed` is never invented by the app.
- **Cannot be validated by this software, at all:** whether an employer actually confirmed anything.
  Free text cannot be authenticated, a screenshot cannot be verified, and no keyless check can prove
  an application exists. That decision must remain an explicit, recorded user assertion — software
  that pretends to verify it would be more misleading than the bug being fixed.

## Fix implemented

| Change | File | Why |
|---|---|---|
| `is_substantive_confirmation_evidence` / `require_confirmation_evidence`: refuse empty, placeholder, template-marker, and this project's own instruction text as confirmation evidence | `career_agent/core.py` | Cause 2. Deliberately narrow and documented as a floor, not authentication; realistic notes are tested to still pass. |
| `ApplicationTracker.transition` uses the shared floor | `career_agent/core.py` | Keeps the domain rule in one place. |
| `CareerStore._check_tracker_invariants` uses the same floor | `career_agent/store.py` | Storage cannot be bypassed by writing directly; the boundary enforces it too. |
| Confirmation requires an explicit assertion checkbox; `candidate_confirmed` is set only from that assertion; an assertion with a non-confirmation status is refused; an already-confirmed record is told the honest correction | `career_agent/desktop.py` | Cause 1. The claim now comes from the person, not from the status selection. |
| `scripts/correct_tracker_record.py`: dry-run by default, backup before any write, one record only, refuses to confirm, reasons required, result re-read and verified | new script | Cause 3. |
| Checklist step 12 reworded; local recovery procedure documented | `research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` | Removes the instruction that invited the paste. |

## Local recovery for the reported record

Not performed here: this environment has no access to the Mac database, and nothing in this task
claims the local row was repaired. The supported, test-verified correction is `withdrawn` with a
truthful reason and the unearned confirmation flag cleared — `withdrawn` is permitted from
`confirmed` and is the only forward status that is not a claim about an employer.

One consolidated action, with the app closed (dry run first, then apply):

```bash
cd ~/ai-career-agent-pr2 && git pull --ff-only
DB="$HOME/Library/Application Support/AI Career Agent/career_agent.sqlite3"
ID=dd559b6c-9674-4791-93c9-55f6e5eae71c
REASON="Fictional smoke-test record: no application was ever submitted, and the earlier confirmed state came from pasting the app's own guidance text, so it is not evidence of an application."

python scripts/correct_tracker_record.py --database "$DB" --listing-id "$ID" \
    --to withdrawn --reason "$REASON" --clear-confirmation            # dry run: writes nothing

python scripts/correct_tracker_record.py --database "$DB" --listing-id "$ID" \
    --to withdrawn --reason "$REASON" --clear-confirmation --apply    # one row written + a backup
```

The tool prints the current record, the intended record, and the backup path
(`career_agent.sqlite3.backup-<UTC timestamp>`), re-reads the row afterwards, and exits non-zero
without pretending success if verification fails. It refuses an invalid transition, a placeholder
reason, a missing record, and any attempt to set `confirmed`.

## Rejected alternatives

- **Adding a reverse transition (`confirmed → submitted_unverified`) or a new "not submitted" status.**
  Rejected: it weakens the forward-only audit property the tracker relies on, and a new status is a
  state-machine change with migration and UI consequences, not a bug fix. Deferred as a design
  question: if users routinely record test data in the real database, an explicit append-only
  correction note is the safer long-term design.
- **Rejecting evidence that "looks fabricated" (semantic or keyword heuristics).** Rejected: it
  cannot be done reliably, would refuse legitimate notes, and would imply the app can authenticate
  free text. The narrow floor refuses only text this project itself emits as instruction.
- **Deleting or resetting the smoke-test record.** Rejected: destructive, and the record is useful
  evidence of what happened; `withdrawn` plus the backup preserves the audit trail.
- **Filling in the evidence automatically during correction.** Rejected: the tool requires the user's
  own truthful `--reason`; it never invents one.
