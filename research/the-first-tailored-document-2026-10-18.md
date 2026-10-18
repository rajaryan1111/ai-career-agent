# The first tailored document, built from the window — 2026-10-18

The lineage rules landed in P7 and were good: an artifact cites the résumé its facts came from, it
is tied to one strategy version, and `require_current_artifact` refuses to hand over one whose basis
has moved. What nobody had noticed is that **no part of the application could create one**. Reading
the call graph says it plainly: before this change, `tailored_resume_document` and
`cover_letter_document` had exactly two callers between them — `rebuild_artifact`, which needs an
artifact to already exist, and `scripts/desktop_acceptance.py`, which manufactured one by calling
`store.new_tailored_artifact` directly so that workflow M would have a row to test the refusals on.

So the Tailored documents tab offered *Check before use*, *Rebuild from current facts…* and
*Refresh* — three controls that all presuppose a document, in front of a list that could only ever
be empty for a real user. The feature was a rule about objects that could not be made.

## What was built

One small complete workflow, not more controls: **choose → preview → store what was previewed →
save a copy**.

`career_agent/artifacts.py` gained four functions and two records:

- `plan_artifact(store, *, listing_id, strategy_id, kind) -> ArtifactPlan` — resolves the listing
  and the strategy, captures the basis, runs the existing builder, and returns everything without
  writing a byte. It refuses an unstored listing, an unstored strategy and
  `ArtifactKind.SCREENING_ANSWERS` ("a plausible answer this build invented is exactly the thing it
  must never write"). It also reports `duplicate_of` when the identical document already exists for
  that listing, strategy version and kind.
- `ArtifactPlan.describe()` — the inputs as sentences: facts used, files they were read from, facts
  still unconfirmed, work/education counts, the **strategy's** requirements the facts do not state,
  and separately the **listing's** requirements they do not state either.
- `store_planned_artifact(store, plan)` — stores exactly the plan, after three refusals: the
  strategy moved to another version, the listing is gone, or `capture_basis(store) != plan.basis`.
- `export_artifact(store, artifact_id, path)` — `require_current_artifact` first, then a provenance
  header above the document, written through `store.create_private_file(..., exclusive=True)`.

The preview panel shows the inputs and then the document **in full**, unaltered: "review it before it
is stored" is not a promise a summary can keep.

The window pins the reviewed plan (`self._artifact_plan`) and will not store anything else: if the
listing, strategy or kind chosen in the comboboxes no longer matches the plan, the build is refused
and the person is sent back to preview. The confirmation dialog repeats the preview text rather than
summarising it.

## The arguments this had with itself

**Why a preview at all, when the builders are deterministic?** Because "the document is built from
your saved facts" is a claim the person has to be able to check *before* it is stored, and because
the pairing is what makes "what was stored is what was reviewed" an enforceable property rather than
a hope. The plan carries the basis it was captured from; storing compares that basis with the store
as it is now. Without the plan there is nothing to compare against, and a fact edited in another tab
between the click and the write would be silently absorbed into a document claiming provenance it
never had.

**Why refuse a duplicate instead of writing a second row?** The lineage list is history. Two rows
with identical text, the same listing and the same strategy version are not two events; they are one
event and a misclick. The refusal names the identifier of the one already stored, which is the only
useful answer. A *new strategy version* producing the same text is still a second document, and that
is deliberate: the version is part of what the row records.

**Why does an existing file get refused outright, with no "replace?" prompt?** Everywhere else in
this project an overwrite is a question (`_export_contacts` asks). Here the file most likely to be
named by accident is the résumé the document was built from — same folder, similar name, and the
chooser's default directory is wherever the person last opened one. A prompt converts that accident
into one careless click; a refusal costs a rename. The roadmap rule is that the original résumé is
never overwritten, and the structural way to keep it is to never overwrite anything.

**Why export plain text?** The artifact's `content` is text; writing it as `.txt` with a header is
the honest format. A `.docx` would imply formatting decisions nobody made, and inventing a layout is
the kind of small lie this application is built to avoid. The header is eight lines: kind, document
id, listing, strategy and version, built-at, files the facts came from, facts recorded as
unconfirmed, and the sentence that it was built only from saved facts and sent nowhere.

**Gaps against the strategy *and* against the listing.** The builders report what the strategy's
`required_skills` lack. That is right for how the document is *assembled*, but a person deciding
whether to use it is applying to one employer, and the listing has its own requirements. The plan
reports both, in separate sentences, and neither is ever written into the document.

## Two defects found on the way

- `cover_letter_document` has always produced "My profile states 1.0 of experience." — invisible
  while no screen could build a cover letter, and the first thing a reader would have seen now that
  one can. The fact is a number of years, so the sentence now says so ("1.0 years of experience",
  "1 year" when it is exactly one). `tests/test_artifacts.py` pinned the broken wording and was
  updated with the fix rather than around it.
- Workflow K5 of the acceptance script read every label with `cget("text")`, which is empty (or a
  `KeyError` against the stand-in module) for a label built with `textvariable=`. A label a person
  can plainly read was being reported as carrying nothing. `visible_text()` now falls back to the
  variable's current value, and a `LabelFrame`'s own title counts as a label for the controls
  inside it.

## What is verified, and what is not

- `tests/test_artifact_build.py` — 23 tests: planning (including the refusals and that a plan writes
  nothing), storing (version moved, facts moved, listing deleted, duplicate, a new version being
  history rather than a duplicate, the profile untouched), exporting (provenance, owner-only mode,
  existing file, missing folder, stale document, unknown document, a write that fails half way
  leaving nothing behind, two exports of the same document).
- `tests/test_desktop_handlers.py::BuildingADocumentTests` — 16 tests driving the real window
  against stand-in widgets and a real database: dead controls say what is missing, a preview writes
  nothing, a declined confirmation stores nothing, what is stored is what was previewed, pressing
  build twice stores one document, every refusal path, the export paths, and that the document text
  never reaches the status line, the detail line or the event log.
- `tests/test_desktop_logic.py::BuildADocumentTextTests` — 11 tests on the Tk-free sentences.
- `scripts/desktop_acceptance.py` workflow M gained **M6–M12**: the controls offer what is stored, a
  preview writes nothing, building asks first, accepting stores exactly what was previewed, an
  identical document is reported rather than stored, a copy is written with its provenance and
  owner-only mode while a decoy `acceptance-resume.docx` in the same folder is untouched, an
  existing file is refused, and a document whose facts moved is not written out at all. The run is
  **154 checks, 0 failed** — and still `RESULT: BLOCKED`, because a stand-in widget module is not a
  desktop. There is no display on this machine; the manual checklist items for these controls stay
  blocked.
- Full suite: **2690 OK, 13 skipped** (12 × `pypdf` absent, 1 × the checkout is not the source tree
  the test needs).

Nothing in this increment opens a gate, enables a source, or sends anything: the only external
effect in the whole path is one file, written owner-only, at a path the person typed into a save
dialog.

## Audit, same day: what a second reading found

The implementation above was re-read independently, and the workflow re-traced outside the test
suite against a throwaway database. The trace held on every leg. Two defects did not.

**A cover letter reported no gaps.** `tailored_resume_document` computed them; the letter builder
returned `BuiltArtifact(content=...)` and let `gaps` default to `()`. Nothing noticed while no
screen could build a letter. Now a screen can, and the preview was printing *"Nothing the strategy
asks for is missing from your saved facts"* over a letter built for a strategy that asks for Docker
from a profile that never mentions it. The document itself was honest — it claimed nothing — but the
sentence above it was false, which is worse than silence. The builder now computes gaps the same way
as the résumé, which also repairs the rebuild status line (`artifact_rebuild_text` reads
`built.gaps`, so rebuilt letters had been reporting none either).

**The listing could move under a document between the preview and the write.** The preview→store
pairing checked the strategy version, the facts and the listing's *existence*, which is everything a
résumé is built from — but a cover letter writes the employer's name and the role title into its
first two lines, and the gaps on screen come partly from the listing's requirements. Editing the
listing on the Jobs tab between the two clicks stored a letter addressed to the old employer against
the new listing, silently. `ArtifactPlan` now carries the listing, and `store_planned_artifact`
refuses when the employer, the role title or the required skills have moved.

The comparison is deliberately narrow. A listing also carries a source URL, an availability status
and a provenance note; refusing a build because one of those was touched would be a refusal nobody
could act on, so only the fields a document is actually written from are compared
(`_listing_changes`), and a test pins that touching the others does not block a build.

**Coverage gaps closed.** A symbolic link named as the export destination — the one path by which
"never overwrite" could still overwrite a résumé — was handled by `create_private_file` and pinned
by nothing; both the live link and the dangling link are now tested. The singular/plural experience
sentence ("1 year", "2.5 years") had no test, and `experience_years` accepts an int, so the singular
branch is reachable rather than dead. Changing the document *kind* after a preview was implemented
but untested. And `visible_text()`, the K5 fix, had no unit test at all — it is the function that
decides what a display-backed run means, so it has five now.

**What is still open here.** `lineage_status` cannot see a listing edited *after* a document is
stored: the artifact row keeps `listing_id`, not the listing fields the document used. Detecting it
needs a column and a migration (schema 15), so it is written down as the next task in this area
rather than bolted on during an audit. A cover letter whose employer has since been renamed still
reads as "Current".

**Not started, with reasons.** Choosing between several imported résumés has no data model behind it
— one `candidate_profile`, one `document_name` per fact, no table of imported documents — so it is a
product change with a migration, not a remainder of this feature. Richer export formats would mean
inventing layout nobody supplied. Both are enhancements; neither is a gap in what was built.

**Numbers at the audited head:** full suite **2706 OK (skipped=13)** — 12 × optional `pypdf` absent,
1 × the checkout is not an installed distribution; acceptance **155 checks, 0 failed**, still
`RESULT: BLOCKED` (a stand-in widget module is not a display). CI has never run on this branch:
the workflow triggers on `main` only, and `check-runs` for this head returns `0`.
