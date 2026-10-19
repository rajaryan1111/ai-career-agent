# Arena Implementation Task — Phase 0 HR Contact CSV Import (Offline Only)

**Repository:** `rajaryan1111/ai-career-agent`  
**Branch:** `arena/351e052d-ai-career-agent`  
**Scope:** Implement only the local CSV parsing/preview/review foundation. Do not merge PR #2.

## Read before changing code

- `planning/hr-contact-outreach-and-application-tracking-2026-10-16.md`
- `planning/arena-task-hr-contact-feature-2026-10-16.md`
- `research/hr-contact-list-audit-2026-10-15.md`
- `career_agent/store.py`, `career_agent/importer.py`, the desktop UI module(s), relevant tests, `phases.md`, and the current threat model.

Do not assume paths or schema details from this task; inspect the current branch first.

## Goal

Add an offline, local-first HR-contact CSV import review flow that can read the user's private CSV files without copying them into this repository. A user must be able to select a CSV, preview validated rows and review flags, and cancel without writing anything. If persistence/UI integration cannot be implemented safely in this increment, ship only a tested, clearly scoped parser and preview contract and document the remaining integration; do not fake a completed workflow.

## Hard constraints

- Keep `SOURCE_QUALITY_GATE_PASSED = False` and `enabled_discovery_sources() == ()`. Do not enable discovery.
- No network requests, email sending, application submission, form filling, or external service integrations.
- Do not read from GitHub or fetch the private repository from app code. The user selects a local file explicitly.
- Never include real names, email addresses, raw CSV rows, personal contact data, or screenshots in the public repository, logs, test output, fixtures, or CI artefacts.
- Do not modify `main`, force-push, rewrite history, merge/close PR #2, or modify unrelated features.
- Do not silently guess/repair company associations. Keep source values and conflicts visible.
- Do not treat syntax checks as proof of deliverability, consent, current employment, or permission to contact.
- Re-imports must be idempotent if persistence is introduced. Do not create duplicate contacts by case/whitespace variants of email.
- Use only synthetic test fixtures. Never run tests against the user's real database or the private CSVs.
- Do not claim tests, GUI checks, or manual acceptance passed unless actually run and evidenced.

## Required behaviour

1. Inspect existing import/storage/UI patterns first and reuse them. Do not create a second database or duplicate existing functionality.
2. Parse CSV with Python's standard-library `csv` module; handle UTF-8 BOM safely and provide actionable errors for unreadable encoding, missing required columns, malformed records, or empty files.
3. Preserve original email/company/name strings for review; derive a comparison key by trimming and case-folding email only. Do not mutate the source file.
4. Validate required schema explicitly against the actual uploaded export headers. Support both the deduplicated export and review-queue export only if their column sets are deliberately handled; otherwise state which one is supported.
5. Flag rows/groups for review, including invalid/suspicious email syntax, missing names, multiple company labels, duplicate email keys, and empty required values. Explain that syntax checks are heuristics.
6. Provide a preview model that reports counts and per-row flags without logging contact values. The user must be able to cancel before any persistence.
7. If adding persistence, use a migration that follows existing schema-version, backup-before-upgrade, and schema-contract rules. Store only the minimum necessary fields and source provenance. Preserve a user's do-not-contact/suppression decision across re-imports. Do not implement outreach/send capability.
8. Keep import/review UI consistent with existing Tkinter patterns and keyboard/accessibility behaviour. If UI integration expands beyond a small, reviewable change, split it into a separate follow-up instead of making a broad refactor.
9. Add synthetic tests for BOM, header validation, empty/malformed files, email normalization, duplicate groups, conflicting company labels, missing names, cancel/no-write behaviour, no PII in logs, and idempotent re-import if persistence is added.
10. Update relevant docs only to describe behaviour that exists; clearly mark any incomplete integration.

## Verification

Run the focused tests and the full test suite from a clean environment, plus the repository's existing compile/static/CSV checks and relevant CI. Record exact commands, results, and any skips/blocks. If unable to run any check, say so and do not claim it passed.

## Acceptance criteria

- Import parsing is offline and deterministic.
- No file is changed by preview or cancellation.
- Raw personal contact data never enters the public repository or test/CI output.
- Ambiguity is surfaced rather than silently resolved.
- Existing source, application, tracker, backup/restore, and deletion behaviour remains unchanged.
- Source discovery and all external actions remain disabled.
- Exact changed files, migration impact, tests and results, remaining limitations, and the next smallest step are reported.
