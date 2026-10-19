# Arena task: per-contact deletion with verified erasure semantics

Date: 2026-10-16
Repository: rajaryan1111/ai-career-agent
Working branch: arena/351e052d-ai-career-agent
Status: proposed implementation task; do not claim complete until code, tests and CI are verified.

## Goal

Let a user delete one stored HR contact from the local HR contacts tab, including its associated conflict records, while preserving database integrity and the app's established data-erasure contract. This is a destructive local action, so confirmation, accurate scope, transaction safety, and privacy-safe audit behavior are mandatory.

## Mandatory preflight

1. Verify the actual remote HEAD and worktree state; do not assume the SHA in any handoff is current.
2. Confirm PR #2 is OPEN and unmerged and main is untouched.
3. Inspect the current schema 7 contact and conflict relationships, foreign-key configuration, store APIs, backup/restore and export/forget-local-data behavior, event-log policy, HR contacts tab controls, and manual checklist.
4. Read the latest HR contact persistence, do-not-contact control, and conflict-review research notes. Verify their claims against current code.
5. Determine exactly which records are dependent on a contact and what the app's existing erasure rules require. If a contact can be referenced by other records or deletion would violate an established retention contract, stop and document the issue rather than guessing.

## Required behavior

- Add a selected-contact deletion action to the existing HR contacts tab, initially disabled until a valid stored row is selected.
- Confirmation must identify the selected record using only a non-sensitive local position/reference, and explicitly state that the contact and its associated conflict-review records will be deleted. Never place the email address, name, company, stored reason, or conflict values in the confirmation.
- Declining, closing, having no selection, using a stale selection, or encountering a storage error must perform no partial deletion and must not show success.
- Implement deletion through one store-layer operation with a transaction; do not delete rows directly from UI code. Delete dependent conflict records according to the inspected schema/erasure contract. Avoid schema changes unless inspection proves they are necessary.
- After successful commit, refresh both contact and conflict views and clear stale selection. The contact's suppression mark and note should no longer remain because the contact itself has been erased; unrelated contacts and their marks must remain unchanged.
- Ensure events/logs contain only minimal action/result counts and no contact PII or notes. Do not add a tombstone containing the data that the user asked to erase unless an existing, documented requirement demands it.
- Do not change CSV parsing/import policy, JSON export scope, source permissions, discovery, outreach, or application behavior in this increment.

## Tests and acceptance

Use only synthetic .invalid email fixtures. Test:

- successful deletion removes exactly the selected contact and its dependent conflict records;
- unrelated contacts, conflict rows and do-not-contact marks remain intact;
- confirmation decline/close, no selection, stale ID and injected database failure result in zero committed partial deletion and no false success;
- transaction rollback preserves the contact and its conflict records on failure;
- backup/restore and restart behavior remain coherent under existing documented semantics;
- event/log/status privacy and absence of raw contact values;
- no orphan records, integrity violations, or unexpected cascade behavior;
- UI selection, disabled/enabled state, keyboard navigation, scrolling, minimum-window layout and display-backed acceptance checks;
- full regression suite and every current CI matrix leg.

Add numbered manual GUI checklist steps, but keep them BLOCKED until a human has run the real window on a display. A widget stand-in is not human acceptance. Record failed CI runs and fixes honestly.

## Documentation and evidence

Only after verified implementation, update task.md, design.md, memory.md, phases.md and README.md where their claims need to change. Add research/hr-contact-per-contact-deletion-2026-10-16.md documenting the inspected erasure contract, affected tables, transaction and rollback semantics, files/commits, exact commands/test counts, actual CI run IDs and per-platform results, manual GUI status, and remaining gaps.

## Hard constraints

- Keep main untouched and PR #2 open/unmerged.
- No force-push, history rewrite, destructive cleanup of unrelated work, or discarding existing changes.
- No real contact data in fixtures, logs, screenshots, CI artifacts or repository content.
- No network, discovery, email, external transfer or application side effects.
- Keep SOURCE_QUALITY_GATE_PASSED = False and enabled_discovery_sources() == ().
- Do not broaden this task to bulk deletion, export redesign, conflict resolution, or automatic contact actions.