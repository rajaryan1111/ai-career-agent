# The standing authorisation: stored, shown, and consulted — 2026-10-18

Written while building P8 item 2 to the point where a person can give, see and withdraw permission, and
the two places that could act on it actually ask. The policy *model* landed earlier the same day
(`research/global-policy-gate-2026-10-18.md`); this note records what was added around it, what was
decided and why, and - the part that matters most here - what is still not true.

## What exists now

| Part | Where | What it does |
| --- | --- | --- |
| Persistence | `career_agent/store.py`, schema **11** | `policy_version(version, payload, created_at)`, append-only, newest row in force |
| Serialisation | `career_agent/policy.py` | `content_key()`, `policy_payload()`, `policy_from_payload()` |
| Enforcement | `career_agent/adapters.py`, `career_agent/integrations.py` | `AdapterRegistry.execute(..., policy=, done_today=)`; `authorised_dispatch(...)` |
| The window | `career_agent/desktop.py`, **Permissions & limits** tab | grant, remove, stop, withdraw, and "what would happen now?" |
| Words | `career_agent/desktop_logic.py` | every sentence the tab shows, Tk-free and tested |

## Decisions, and the reasoning behind each

**No row means nothing is authorised, not "no restrictions".** `get_global_policy()` on a file that has
never been authorised returns `no_authorisation()` - an empty policy that refuses everything - rather
than `None`. A `None` would make every caller responsible for remembering the missing case, and the one
that forgot would be the one that performed something. The table is created empty by the migration for
the same reason: an upgraded database has authorised nothing, and that is a true statement about it.

**Versions are appended, never updated.** An action that ran yesterday ran under yesterday's
authorisation, and "what was I permitting when that happened?" has to stay answerable. So a change
writes a new row, a withdrawal writes a new row *that keeps the pairs it is withdrawing* (with
`revoked_at` set), and nothing ever deletes one. The cost is a growing table; one row per decision a
person actually makes is a cost worth paying.

**A revision that changes nothing writes nothing.** `save_global_policy` compares `content_key()` -
sorted pairs and limits, key-sorted JSON, version deliberately excluded - and returns the current
version untouched when they match. Pressing *Authorise* twice on the same permission is not two
decisions, and a version history full of no-ops would make the real decisions harder to find.

**A damaged row raises.** `policy_from_payload` rejects unknown fields and bad shapes, and the store
reports a `StoredRecordError` through the same decoder registry the doctor reads. The alternative -
falling back to an empty policy - is defensible for a *refusing* default, but it would mean a corrupted
file silently loses a withdrawal, and the person would be told nothing. The doctor reporting it is the
honest version.

**The authorisation is not in the JSON export.** The export stays at format version 2. A permission is
about this machine and this installation; a file a person might send to somebody else is the wrong
place for it. It travels in a whole-database backup, which is what a backup is for, and a test pins
both halves.

**`execute` gained `policy=` and `done_today=`, and both fail closed.** The check sits *after* the gate
and *immediately before* `call_adapter`, and it is composed with the gate's own answer
(`source_gate_allows=gate.allowed`), so the two can only ever agree to permit. A missing policy refuses.
A policy supplied without `done_today` also refuses, which is the less obvious half: a daily ceiling
cannot be honoured against a number this layer would have to invent, so the caller must count from
durable records or be refused.

**Integrations got a new door rather than a changed one.** `dispatch_with_retry` is the mechanical part
- perform, retry a failure, stop - and it is what the local stand-in and the existing tests use, where
nothing leaves the machine. Forcing an authorisation through it would have made every existing test
carry a policy to test retry arithmetic. `authorised_dispatch(...)` is the door a real provider would be
called through: policy, source, clock, count and gate are all required, and an operation the
authorisation has no word for (a calendar event) raises `PolicyError` rather than being guessed into
some other limit.

**The tab says what it cannot do.** Every sentence on **Permissions & limits** states that permitting
something does not switch it on, because the opposite impression is the one a permissions screen
naturally gives. The confirmation dialogs say it too, at the moment a person is deciding.

## What is still not true

- **Nothing runs.** `SOURCE_QUALITY_GATE_PASSED` is `False` and `enabled_discovery_sources()` is `()`.
  Every wiring site refuses by construction today; the tests that exercise the path *after* the gate
  replace the gate function with a stand-in for the length of one test and drive a fixture adapter.
- **No daily counter exists.** `done_today` is a parameter, and nothing yet counts a day's actions from
  durable records. Until something does, a caller can only pass `0` honestly on a day nothing ran - and
  passing nothing refuses, which is the right failure.
- **Quiet hours are set in code, not in the window.** The tab grants, removes, stops and withdraws; it
  does not yet edit quiet hours, and there are no job, role, location, attachment or follow-up
  constraints in the model at all.
- **`SCREENING_ANSWERS` has no builder** and remains refused, unchanged by this work.
- **No display-backed run.** Acceptance workflow **N** passes under the stand-in widget module
  (124 checks, 0 failed, `RESULT: BLOCKED`), and manual steps 130-136 are BLOCKED like the rest.

## Evidence

- `tests/test_policy_store.py` — 16 tests (first version, append, no-op revision, withdrawal, re-grant,
  restart, backup/restore, damaged row, log privacy, export exclusion, refusal of non-policies, a v10
  file upgrading, a re-runnable step).
- `tests/test_policy_wiring.py` — 21 tests (both call sites refusing, the ceiling, quiet hours, stop,
  withdrawal, the composition with the gate, and three that pin that nothing was enabled).
- `tests/test_desktop_handlers.py::PermissionsTabTests` — 16 tests through the real window against a
  real database, with every decline asserted against the connection's own change counter.
- `tests/test_desktop_logic.py::PolicyTextTests` — 11 tests for the sentences.
- Suite at this increment: **2303 OK (skipped=13)**; stand-in acceptance **124 passed, 0 failed**.
