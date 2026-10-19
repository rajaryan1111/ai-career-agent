# Arena task — finish offline HR contact import: persistence + review UI

**Date:** 2026-10-16  
**Repository:** `rajaryan1111/ai-career-agent`  
**Required branch:** `arena/351e052d-ai-career-agent`  
**Authority:** the six canonical files (`prd.md`, `task.md`, `memory.md`, `architecture.md`, `design.md`, `phases.md`) and this task.  
**Predecessor:** parser/preview contract shipped in commit `062a88c`; follow-up layout fixes D33/D34 and CI correction are reported in the latest Arena report. Verify the actual branch head and worktree before acting.

## Objective

Finish the next bounded P0 increment: turn the existing offline-only contact CSV parser into a safe local import/review workflow using the repository's existing SQLite migration, backup-before-upgrade, storage, Tkinter, scrollable-tab and acceptance-test patterns. Do not build a new persistence abstraction or duplicate the parser's email normalisation.

## Mandatory preflight — inspect before changing anything

1. Confirm branch, clean/dirty worktree, exact HEAD, open PR #2 and latest workflow state. Do not overwrite or discard user/Arena work.
2. Read the current `career_agent/contacts.py`, CLI preview path, `career_agent/store.py`, schema version/migration helpers, backup/restore implementation, `career_agent/__main__.py`, desktop window/tab construction and `_scrollable_body`, activity/audit event model, existing UI tests and display-backed CI harness.
3. Trace the current migration and backup-before-upgrade contract end to end. Find how tests prove rollback, interrupted migration, permissions and restore. Reuse the existing patterns.
4. Record the actual schema version and current UI structure in the implementation summary. If the branch differs from the stated predecessor, reconcile first; do not assume file contents or test counts from this task.

## Required implementation

### A. Schema-7 migration and storage

- Add schema version 7 only if the preflight confirms the current schema version is 6. If it has changed, stop and adapt the migration sequence without rewriting history.
- Use the existing migration runner and backup-before-upgrade mechanism. Do not introduce a parallel migration path.
- Add the smallest contacts persistence model needed by the review workflow. Store the normalised email key only by calling/reusing `career_agent.contacts.normalise_email_key`; never implement a second normaliser.
- Preserve the original source strings needed for review (email, name, company and any existing source/provenance/review-reason fields supported by the parser), source-file/provenance reference, import/update timestamps and review/validation flags. Inspect existing models before deciding column names; do not create redundant fields.
- Preserve contact-level suppression / do-not-contact state across re-imports and across company/name conflicts. Re-import must update or add reviewable metadata without ever clearing a suppression flag.
- Do not store full source file paths if a privacy-preserving basename or source identifier is sufficient. Do not log contact values, full email addresses, CSV rows or sensitive path components.
- Make imports transactional. A failed import must leave the prior contact state unchanged. Use the existing store's transaction conventions.
- Define deterministic conflict behaviour. Do not silently merge contradictory companies or names. Keep conflict evidence available for human review. Duplicate input rows must not produce duplicate contact records.
- Provide a store-level import API that accepts the already-parsed parser result; keep parsing in `contacts.py` and persistence in the established store layer.

### B. Review UI

- Add a clearly named HR Contacts/import review tab using the existing tab and `_scrollable_body` patterns. Do not place a long contact table outside a scrolling body.
- Provide a file picker and call the existing parser. Preview must be read-only until the user explicitly presses a clearly labelled confirmation control.
- Show aggregate counts, used/unused column mapping, duplicate groups, company conflicts, and per-row validation/rejection reasons. Keep row content in the private local UI only; never write contact values into logs, test output, screenshots or public docs.
- Let the user cancel/close the preview with zero database writes. Do not auto-import when a file is selected or parsed.
- Require an explicit confirmation step before the transaction starts; display the number of records/groups to be added/updated and conflicts requiring review. If the existing interaction patterns support row-level acceptance/rejection, reuse them; otherwise keep ambiguous/conflicting rows clearly flagged and prevent unsafe silent merging.
- Make errors actionable but privacy-conscious. Never show success until the transaction commits.
- Do not add matching-to-jobs, email drafts, sending, reply tracking, external calls or source enabling in this increment.

### C. Safety and observability

- Contact suppression is durable and must survive repeated imports, conflicts, database backup and restore.
- Record a minimal local activity event for an import outcome only if the established event model supports it without storing contact PII. An event may contain counts and outcome, not addresses or row values.
- No network calls, OAuth, mailbox access, application submission, or external side effects.
- Keep `SOURCE_QUALITY_GATE_PASSED = False` and `enabled_discovery_sources() == ()`. Do not change application-submission gates.

## Required tests

Use synthetic data only; all fixture addresses must use reserved `.invalid` domains. No private CSVs or real contacts in repository, tests, logs, screenshots or workflow artifacts.

At minimum add tests for:

1. Migration 6→7 on a populated database, backup-before-upgrade, idempotent startup, rollback/failure recovery and older supported schema paths.
2. New import, repeated identical import, duplicate rows in one file, re-import after name/company changes, and deterministic conflict preservation.
3. Suppression/do-not-contact survives same-contact re-import, conflicting metadata, backup/restore and application restart.
4. Cancel, closing the preview, parse refusal and confirmation rejection cause **zero writes** (verify database state/change counter or equivalent, not merely the UI message).
5. Confirm writes exactly once; injected storage failure rolls back the whole import and displays no success.
6. Missing/invalid email, missing name, ambiguous columns, malformed CSV, size/row caps, extra columns, UTF-8 BOM and UTF-16 refusal remain correct.
7. Privacy assertions: synthetic cell values absent from logs, CLI output and captured root logger; no contact PII in activity events.
8. GUI tests follow existing display-backed CI patterns and exercise keyboard focus, scrolling, cancel and confirm paths on Linux/macOS/Windows where supported.
9. Regression suite, compile/lint checks and existing backup/restore tests.

Do not weaken or delete existing tests to obtain green CI. If any platform CI failure appears, determine whether it is a product defect, test defect or infrastructure issue and document evidence.

## Documentation and completion evidence

Update `task.md`, `phases.md`, `design.md`, `memory.md` and README only to describe what the code actually implements. Add a focused research/implementation note with schema version, migration/rollback behaviour, privacy boundaries, known gaps and exact test evidence. Do not call this feature complete until parser, persistence, UI and cancel/no-write behaviour are implemented and tested.

Report:
- exact branch and before/after commit SHAs;
- changed files and rationale;
- schema migration and backup/restore evidence;
- exact test commands, actual counts and CI run URL/status;
- any failed/pending checks and manual GUI acceptance still outstanding;
- known limitations and the next smallest task.

## Stop conditions / prohibited actions

- Do not touch `main`, merge or close PR #2, force-push, rewrite commits, or discard existing changes.
- Do not commit any real contact data, credentials, tokens, personal email addresses, or private export files.
- Do not send email, apply to jobs, scrape platforms, enable live discovery or change external-action gates.
- If migration/backup invariants or suppression semantics cannot be established from existing code, stop before writing and report the exact blocker rather than inventing a parallel design.
- Make the smallest complete, reviewable increment; do not bundle packaging audit or unrelated refactors into this task.
