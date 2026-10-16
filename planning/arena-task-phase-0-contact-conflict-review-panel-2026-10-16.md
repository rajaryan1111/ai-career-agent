# Arena task: local HR contact conflict review panel

Date: 2026-10-16  
Repository: rajaryan1111/ai-career-agent  
Working branch: arena/351e052d-ai-career-agent  
Increment: Phase 0 / local-only HR contact review  
Status at planning time: proposed next focused task; implementation not yet verified.

## Goal

Make disagreements already recorded in hr_contact_conflict reviewable from the existing HR contacts tab. Keep this a local, read-only review increment: show enough context for a human to understand the disagreement without silently choosing a value or mutating contact identity. Do not combine this with per-contact deletion, export changes, discovery, or outreach.

## Mandatory preflight

1. Verify the actual remote branch HEAD and local worktree state before editing; do not assume the reported SHA is still current.
2. Confirm PR #2 is still OPEN and unmerged, and main remains untouched.
3. Read the current schema-7 conflict model, list_contact_conflicts API, import conflict generation, HR contacts tab layout, test conventions, event/log policy, backup/restore behavior, and the six canonical docs.
4. Inspect research/hr-contact-import-persistence-and-review-ui-2026-10-16.md and research/hr-contact-do-not-contact-control-2026-10-16.md. Treat them as evidence to verify against code, not as a substitute for inspection.

## Scope

- Add a conflict-review area to the existing HR contacts tab, using the existing scrolling-body and widget patterns.
- List recorded disagreements from the store in a deterministic order. Clearly label the affected normalized contact key only if existing UI/privacy conventions permit it; otherwise use a stable local row/contact reference and show the original conflicting values only to the local user.
- Present both sides of each disagreement and their provenance using only fields actually persisted by the current schema. Distinguish stored/current contact metadata from the incoming conflicting metadata; do not imply either side is correct.
- Read-only behavior: no automatic merge, no implicit winner, no changes to stored contact identity, suppression flag/date/reason, or import state.
- Keep rendering bounded and usable for long lists/long values; use safe text display and avoid exposing filesystem paths.
- Refresh the view after a successful import and when the tab is revisited, following existing UI lifecycle patterns.
- If the existing conflict record cannot support an accurate, understandable comparison, document the limitation rather than inventing provenance or adding a migration by default.
- Keep do-not-contact state and reason private. No PII, conflicting values, email addresses, names, companies, or suppression notes in logs/events, test output, screenshots, or CI artifacts.

## Tests and acceptance

Use synthetic .invalid email fixtures only. Add tests for:

- conflict rows appear for a real stored disagreement and are absent when there are none;
- both recorded sides and provenance are labelled correctly based on actual schema fields;
- deterministic ordering and safe handling of long/unusual text;
- refresh after import and no stale data after revisiting the tab;
- read-only guarantee: opening, refreshing, selecting, and viewing conflicts produce zero database writes;
- suppression mark/date/reason remain unchanged while reviewing conflicts;
- no PII in logs/events/status messages;
- keyboard navigation, scrolling, minimum-window layout and display-backed acceptance workflow;
- full unit/regression suite and all current CI matrix legs.

The manual GUI checklist must gain numbered steps for this panel. Keep it explicitly BLOCKED until a human actually runs the window on a display and records the outcome. A stand-in widget check is not human GUI acceptance.

## Documentation and evidence

After code and tests are actually verified, update the relevant canonical files among task.md, design.md, memory.md, phases.md, and README.md only where the implementation changes their claims. Add a dated research note at research/hr-contact-conflict-review-panel-2026-10-16.md that records:

- inspected schema/API and the exact conflict semantics;
- files/commits changed;
- commands and test counts actually run;
- current CI run IDs/status and per-platform evidence;
- manual GUI acceptance status and exact remaining gaps.

Do not mark a task complete based only on an intended design or an unverified report. Record failed CI runs and fixes honestly.

## Hard constraints

- Do not edit main; keep PR #2 open and unmerged.
- No force push, history rewrite, reset, destructive cleanup, or discarding unrelated work.
- No new schema migration unless code inspection proves the current record cannot safely support the read-only view; explain the reason first in the research note.
- No contact discovery, network requests, email drafting/sending, applications, or external side effects.
- Keep SOURCE_QUALITY_GATE_PASSED = False and enabled_discovery_sources() == ().
- No private or real contact data in fixtures, logs, artifacts, or repository content.
- This task is conflict review only: no conflict resolution, merge, contact deletion, or export policy change.