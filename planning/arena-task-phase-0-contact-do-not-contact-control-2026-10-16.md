# Arena task — local HR contact do-not-contact control

**Date:** 2026-10-16  
**Repository:** `rajaryan1111/ai-career-agent`  
**Required branch:** `arena/351e052d-ai-career-agent`  
**Prerequisite:** schema-7 HR contacts persistence and the HR Contacts tab are reported implemented in commits ending at `57f8abc96bcd0063a555c296068d4c258f1e189f`. Verify the live branch head and files before acting; this SHA is the report's stated head, not a substitute for preflight.

## Objective

Add the smallest safe local UI control to set and clear a stored contact's do-not-contact/suppression mark using the existing `CareerStore.set_contact_suppression` API. This closes a real safety gap: the store can preserve a suppression mark, but a user currently has no control in the application to create or remove it.

This is a local data-management feature only. Do not add email sending, contact matching, campaign management, job applications, mailbox access or any network capability.

## Mandatory preflight

1. Confirm current branch, worktree cleanliness, exact HEAD, PR #2 state and current CI. Do not discard or overwrite changes.
2. Read the actual `career_agent/contacts.py`, `career_agent/store.py` suppression API and models, HR Contacts tab/handlers, confirmation/error dialog conventions, activity-event policy, `scripts/desktop_acceptance.py`, relevant tests, backup/restore semantics and the six canonical files.
3. Confirm the exact method signature and stored suppression fields; reuse them. Do not add a new table or migration unless inspection proves the existing model cannot represent the requested behaviour. If the implementation differs from the report, reconcile before editing.
4. Record baseline test commands and current source-quality gates.

## Required behaviour

- In the existing HR Contacts tab, allow selecting a stored contact and viewing its current suppression/do-not-contact state.
- Add clear **Mark do not contact** and **Remove do-not-contact mark** actions, enabled only when a valid stored contact is selected and the action changes its state.
- Before either change, show a confirmation describing the contact by the least data needed for the user to distinguish it and explaining the effect. Do not log the displayed identity.
- Provide a small optional note/reason if the existing store supports it. Do not invent a new persistence field just for a note without first inspecting the model and documenting why it is necessary. If notes are unsupported, say so in the UI and keep the change minimal.
- Cancel, window-close, or confirmation decline must cause zero writes. Assert this using the existing connection's `total_changes` or an equivalent reliable database-state assertion.
- On confirmation, call the existing store API once. Report success only after the store call returns successfully. On exception, show the established safe error dialog and leave the previous mark intact.
- Refresh the selected contact and list from persisted state after a successful change. Avoid stale UI state and duplicate writes.
- Preserve suppression state across re-import, metadata conflicts, application restart and backup/restore. Do not change existing re-import semantics.
- If the store supports both marking and unmarking, implement both paths; unmarking must be an explicit confirmed user action, never implicit during import.
- Keep logs and activity events free of email addresses, names, companies, free-text notes and file paths. If an activity event is appropriate under the existing event contract, record counts/outcome only.
- Keep the tab inside the existing scrolling layout and preserve keyboard navigation/focus order on Linux, macOS and Windows.
- Do not modify JSON export/delete policy in this task. The current report says contacts are excluded from JSON export and lack per-contact deletion; treat those as separate, explicitly documented gaps.

## Tests required

Use synthetic contacts only, with reserved `.invalid` addresses.

1. Mark selected contact: confirmation shown, one store call/write, persisted suppression true, UI refreshes.
2. Unmark selected contact: confirmation shown, one store call/write, persisted suppression false.
3. Decline confirmation, cancel, and close: zero writes and unchanged stored state.
4. No selection, stale selection, unknown/deleted contact, and disabled controls: no write; actionable safe feedback where appropriate.
5. Injected store failure: no success message, existing state remains intact, no PII in logs.
6. Suppression survives a subsequent identical import, a conflicting metadata import, close/reopen and backup/restore.
7. No contact PII or user-entered note in logger output, activity events, test stdout, screenshots or CI artifacts.
8. Existing workflow L and display-backed tab/focus/scroll acceptance include the new controls and prove keyboard traversal reaches them.
9. Run focused contact/store/UI tests, relevant backup/restore tests, compile checks and the full suite; verify current cross-platform CI head.

Do not weaken or delete tests to obtain green CI.

## Documentation and evidence

Update `task.md`, `design.md`, `memory.md`, `phases.md` and README only where the behaviour changes their current claims. Add a focused research note covering the control, confirmation/no-write semantics, privacy boundaries, tests, manual acceptance still outstanding and remaining gaps.

Report the exact branch/head before and after, changed files, commit SHAs, test commands/results, CI URL and actual status. Keep separate the automated display-backed checks from the human manual GUI checklist; do not claim a human has opened the app unless that actually happened.

## Constraints

- Keep `main` unchanged and PR #2 open/unmerged.
- No force-push, history rewrite, or discarding existing work.
- No private contact data in repository files, fixtures, logs, screenshots or artifacts.
- No email sending, outreach, live discovery, application submission, network calls, credentials or source-gate changes.
- Keep `SOURCE_QUALITY_GATE_PASSED = False` and `enabled_discovery_sources() == ()`.
- If the existing API cannot safely express a required state transition, stop and report the precise blocker instead of inventing parallel storage.
