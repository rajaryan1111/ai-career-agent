# Resume import: distinguish a write from its read-back verification

Date: 2026-10-17 · Scope: local PDF/DOCX review flow, no external action.

## Finding

The resume review handler saved accepted values before reading the profile back. A read-back failure or a
mismatch therefore meant the database could already contain the reviewed values, but the outer handler reported
`Profile not saved` and `Resume import: nothing was saved`. That wording was unsafe: it could encourage a blind
retry and obscure what the person needed to inspect.

## Fix and invariant

The handler now records the point at which the store call returns:

- validation, pre-write read failures, storage refusals and database write failures still report that nothing
  was saved and leave the previous profile unchanged;
- after `save_profile` returns, a missing profile, read-back exception or field mismatch reports **saved, but
  not verified**, leaves the review dialog open, names the Profile tab as the safe place to inspect the actual
  stored state, and never says that nothing was saved; and
- only a successful field-by-field read-back closes the review and reports the values saved from the document.

The existing write path and provenance rules are unchanged: accepted document values remain extracted and
unconfirmed, while fields not selected by the person remain from the form. No schema or external integration
was added.

## Verification

Handler tests use the real SQLite store and inject a post-write read-back failure and mismatch, asserting the
committed profile and truthful dialog/status text. The focused desktop/resume subset ran **174 tests, OK**;
the complete desktop-handler/resume/logic subset ran **523 tests, OK**; the full local suite ran **2080 tests,
OK (skipped=1)**. The real macOS acceptance harness reported **113 checks passed**, and the desktop smoke test
reported **14 checks passed**. Manual GUI acceptance remains separate and blocked.

No live discovery, email, application submission or candidate-data transfer was enabled.
