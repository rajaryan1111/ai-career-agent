# Arena task: explicit, privacy-reviewed HR contact export

Date: 2026-10-16
Repository: rajaryan1111/ai-career-agent
Working branch: arena/351e052d-ai-career-agent
Status: proposed focused task; implementation and CI evidence must be verified before marking complete.

## Goal

Let the user intentionally export their locally stored HR contact list so they can back it up or move it between machines, without silently changing the existing version-2 JSON export contract. Keep this increment offline and user-initiated. Define the export format and privacy scope explicitly before implementation.

## Mandatory preflight

1. Verify the actual remote HEAD and worktree state. Do not assume a SHA from a prior report is current.
2. Confirm PR #2 is OPEN and unmerged and main is untouched.
3. Read the existing JSON export/import contract, `EXPORT_FORMAT_VERSION`, `--forget-local-data`, file permission patterns, backup/restore implementation, HR contact store APIs, parser limits, contact/conflict schema, suppression policy, and current desktop UI/test conventions.
4. Read the HR contact import/persistence, do-not-contact control, conflict-review, and per-contact deletion research notes. Treat their statements as claims to compare with the actual current code.
5. Determine which fields are necessary for a useful portable contact export and which are sensitive. Do not assume conflict evidence, do-not-contact reasons, internal IDs, timestamps, or activity logs should be exported.

## Required behavior

- Add a separate, clearly labelled, user-initiated HR contact export action. Do not silently add contact data to the existing version-2 JSON export or change its compatibility contract in this task.
- Use a documented, versioned, bounded format suitable for re-import or manual transfer. Prefer an explicit CSV schema for the contact fields already supported by the existing parser, unless inspection demonstrates a better existing portable format.
- Define the export column list and behavior for empty lists, duplicate normalized keys, non-ASCII text, commas/quotes/newlines, spreadsheet formula injection, and large datasets.
- Use a safe save-dialog flow and avoid overwriting an existing file without explicit confirmation. Apply restrictive file permissions where supported by the existing codebase.
- Treat suppression as safety-critical: do not silently discard do-not-contact state in a way that could make a later import contact someone who opted out. Either include a clearly documented portable suppression field supported by a compatible import path, or refuse to claim a lossless/safety-preserving backup and document the limitation. Do not export suppression reasons by default.
- Do not export conflict-review values, internal database IDs, raw activity logs, or filesystem paths unless the preflight establishes a compelling documented requirement and the user explicitly opts in.
- Export must be read-only: no changes to stored contacts, conflict records, suppression state, event history, or schema. Use atomic file creation/replacement patterns already established by the project.
- Report success only after the output file is completely written and verified. Errors, cancel, close, invalid path, permission failure, or interrupted writes must not claim success or mutate the database.
- Keep the current import behavior and existing JSON export format unchanged unless a required compatibility change is explicitly documented and separately justified.

## Tests and acceptance

Use synthetic `.invalid` email fixtures only. Add tests for:

- exact exported columns/format and documented schema/version;
- round-trip compatibility with the existing contact parser where safe, including suppression safety behavior;
- UTF-8, Unicode, CSV quoting/newlines, formula-injection defenses, empty and large bounded datasets;
- declined/closed save dialog, overwrite refusal, invalid path and injected I/O failure;
- export does not change database `total_changes`, contact/conflict rows, suppression mark/date/reason or activity state;
- exported bytes contain only approved fields and no conflict values, internal IDs, notes, or PII in logs/status/events beyond the file the user explicitly chose to create;
- cross-platform paths, permissions where supported, UI keyboard/scrolling and display-backed acceptance workflow;
- full regression suite and all current CI matrix legs.

Add numbered steps to the manual GUI checklist. Keep them BLOCKED until a human tests the real window and resulting file on a display. A stand-in widget run is not human acceptance. Record failures and fixes honestly.

## Documentation and evidence

Only after code and tests are verified, update task.md, design.md, memory.md, phases.md, README.md and the relevant export/import docs where their claims change. Add `research/hr-contact-export-2026-10-16.md` describing the chosen format, included/excluded fields, suppression safety decision, compatibility, atomicity, permissions, commands/test counts, actual CI run IDs/platform results, manual GUI status and remaining gaps.

## Hard constraints

- Keep main untouched and PR #2 open/unmerged.
- No force-push, history rewrite, destructive cleanup, or discarding existing work.
- No real contact data in fixtures, logs, screenshots, CI artifacts or repository content.
- No network, contact discovery, email, application submission, or external transfer.
- Keep `SOURCE_QUALITY_GATE_PASSED = False` and `enabled_discovery_sources() == ()`.
- No bulk deletion, conflict resolution, new database schema, or version-2 JSON export redesign in this increment unless preflight identifies a genuine blocking compatibility issue; document such an issue before expanding scope.