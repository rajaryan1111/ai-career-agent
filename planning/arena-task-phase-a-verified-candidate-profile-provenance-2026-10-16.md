# Arena task: verified candidate profile and fact provenance baseline

Date: 2026-10-16
Repository: rajaryan1111/ai-career-agent
Working branch: arena/351e052d-ai-career-agent
Status: proposed next focused implementation increment; do not mark complete without verified code and CI evidence.

## Why this is next

The offline HR contact utility increment is implemented and documented at `5fe30194e264967340a9c425da647fdbd924229c`. The larger product still needs its resume-first candidate foundation before job matching and application preparation can be trusted. Begin Phase A with a small, migration-safe profile model and explicit fact provenance; do not jump to resume parsing, external discovery, or automation.

## Mandatory preflight

1. Verify current remote HEAD, worktree/index state, PR #2 status, and that `main` remains unchanged. Never assume the reported SHA is still current.
2. Inspect the current profile/preferences schema, dataclasses, store APIs, migrations, backup/restore, JSON export/import v2, UI setup flow, tests, and all relevant canonical docs before changing code.
3. Reuse existing patterns. If a suitable profile model already exists, extend it rather than creating parallel storage or abstractions.
4. Keep this increment local-only and compatible with schema migration, backup/restore, and the existing export/import contract.

## Scope

- Define a small candidate-profile model for user-confirmed facts and preferences needed by later matching, using only fields supported by the current product docs and existing implementation.
- Track provenance per fact: user-entered, extracted from a local document, or imported; record verification state and update time only where the existing architecture supports it. Never present extracted/imported facts as user-verified automatically.
- Make missing required fields discoverable so a future setup flow can ask targeted questions; do not build a large onboarding redesign in this task.
- Provide deterministic, transactional store read/write/update behavior with bounded values, safe handling of optional fields, and tests for restart persistence and backup/restore if the current store supports those workflows.
- Keep all resume content and profile data local. No external LLM calls, uploads, source discovery, email, applications, or scheduler activation.
- Preserve JSON export version 2 compatibility. If adding profile data to it would change the contract, do not do so silently; document the limitation and propose a separately versioned follow-up.
- Do not add guessed candidate facts, role defaults tied to a specific person, or fabricated provenance.

## Required tests

- Schema/migration tests prove fresh install and upgrade paths work and remain idempotent.
- Store tests cover create/read/update, empty/optional values, invalid bounds, transaction rollback, and persistence after reopening.
- Provenance tests prove extracted/imported facts remain unverified until explicitly confirmed, and edits update the correct provenance without silently verifying unrelated facts.
- Backup/restore and existing JSON export/import regression tests remain green.
- Privacy tests ensure profile values do not leak into ordinary logs, exception text, or test diagnostics.
- Full unit suite, compile checks, all CI matrix legs, and the display-backed acceptance harness must run; record exact evidence.

## Non-negotiable constraints

- Keep `main` untouched and PR #2 open and unmerged. No force-push, history rewrite, or destructive reset.
- Do not enable live discovery, email sending, application submission, or any external transfer. Keep `SOURCE_QUALITY_GATE_PASSED = False` and `enabled_discovery_sources() == ()`.
- No real candidate data in fixtures, CI output, screenshots, logs, or public repository content.
- Do not mark manual GUI checklist steps complete without a human testing the real application.
- If scope reveals a larger schema or export-contract change, stop and document the decision instead of expanding scope silently.

## Completion report

Report the verified remote HEAD and commit SHAs, files changed, schema/export compatibility, exact test counts, CI run IDs and job matrix, acceptance-harness results, manual steps still blocked, and any follow-up decisions. Distinguish tool-reported evidence from independently fetched evidence.