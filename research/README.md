# Research and evidence index

Everything in this folder is an artefact: a decision record, a measurement, a review, or a run of the
product. None of it ships, and none of it is the product's documentation — the canonical documents are the
ones in the repository root (`prd.md`, `architecture.md`, `rules.md`, `design.md`, `phases.md` and `README.md`).
What this index adds is the answer to three questions a reader otherwise has to reconstruct:

1. **What question does each document answer?** One line each, below.
2. **Is it current guidance or historical evidence?** Current guidance stays true as of the date it carries
   and is maintained in place; historical evidence records what was true on a date and is never rewritten.
   Where a document has been superseded, the successor is named beside it.
3. **Which decision does it feed?** Most of these documents exist for one forked decision: whether any job
   source may be enabled. The answer is recorded, and it is **no** — `SOURCE_QUALITY_GATE_PASSED is False`,
   `enabled_discovery_sources()` is empty, and every source document below is evidence for, or against, a
   decision that has not been reopened.

## Current guidance (maintained; read these first)

| Document | What it answers | Status |
| --- | --- | --- |
| [human-desktop-acceptance-handoff-2026-10-16.md](human-desktop-acceptance-handoff-2026-10-16.md) | How does a person actually run the manual acceptance, area by area, and what do they write down? | **Current.** The run-book; it points at the checklist rather than replacing it, and it says what automation has already established so a tester does not redo it by hand. |
| [local-alpha-manual-smoke-test-checklist-2026-10-14.md](local-alpha-manual-smoke-test-checklist-2026-10-14.md) | What are the 98 numbered manual steps, what is the verdict on each, and what has automation covered? | **Current, updated in place.** Dated updates at the top; historical verdicts and citations are kept. No box is ticked until a person ticks it. |
| [cross-platform-desktop-ci-evidence-2026-10-15.md](cross-platform-desktop-ci-evidence-2026-10-15.md) | What did the CI matrix and the real-desktop harness prove, on which platform, and which defects did that find? | **Current.** The cumulative evidence and defect register (D1–D20 — D21–D25 are extractor defects found by the Phase 4 corpus and are written up in the evaluation run beside it): per-leg platform/Tk/screen strings, per-leg check counts, and one section per defect with its fix and its regression test. |
| [cross-industry-evaluation-run-2026-10-16.md](cross-industry-evaluation-run-2026-10-16.md) and [cross-industry-evaluation-set-2026-10-16.json](cross-industry-evaluation-set-2026-10-16.json) | Is the product usable outside software/data, and where is the extractor blind? | **Current.** The Phase 4 corpus and harness: seven occupation groups, the measured agreement with a written review standard, and the five real extractor defects that running it found (D21–D25). Synthetic only; not human acceptance. |
| [threat-model-2026-10-16.md](threat-model-2026-10-16.md) | What does this alpha defend against, and what does it not? | **Current.** Assets, adversaries, one control per threat with the test that enforces it, the residual risks (no encryption at rest, no erase-everything command), and the measurements taken while writing it. Phase 2 stays partially complete. |
| [release-readiness-audit-2026-10-15.md](release-readiness-audit-2026-10-15.md) | What still blocks a release, and what is deliberately not done? | **Current.** The release blockers; the per-phase verdict lives in `phases.md`, which this audit points at. |
| [local-alpha-manual-acceptance-run-2026-10-15.md](local-alpha-manual-acceptance-run-2026-10-15.md) | What could a headless machine execute of that checklist, and what did it find? | **Historical evidence** (22 PASS, 76 BLOCKED, 0 FAIL) with a revision-scope note; the window half is now driven automatically, and the human half is still open. |
| [mvp-scope-and-data-contract-2026-10-14.md](mvp-scope-and-data-contract-2026-10-14.md) | What is in scope for the first local alpha, and what is explicitly out? | **Current and authoritative for scope**; it takes precedence over earlier planning documents where they disagree. |
| [source-quality-gate-assessment-2026-10-14.md](source-quality-gate-assessment-2026-10-14.md) | Has the source-quality gate passed? | **Current decision: NOT PASSED — remain research-only.** It also states what would have to change. |
| [source-permission-decision-matrix-2026-10-14.md](source-permission-decision-matrix-2026-10-14.md) | What does each reviewed source's own terms allow, separately from accuracy and eligibility? | **Current reference.** Not legal advice; re-check the linked terms before any release. |

## Source research (evidence for a gate that is closed)

These record what was measured or read about candidate sources. They are the material a future gate decision
would have to be made from; none of them enables anything, and several are explicitly inconclusive.

| Document | What it answers |
| --- | --- |
| [job-platform-feasibility-matrix-2026-10-13.md](job-platform-feasibility-matrix-2026-10-13.md) | Which official job platforms were compared, on what criteria, and with what result? |
| [live-source-smoke-test-2026-10-13.md](live-source-smoke-test-2026-10-13.md), [live-source-smoke-test-round2-2026-10-13.md](live-source-smoke-test-round2-2026-10-13.md) | Do two real public feeds answer, and what do their records look like? |
| [ai-dev-jobs-live-api-first-page-sample-2026-10-13.md](ai-dev-jobs-live-api-first-page-sample-2026-10-13.md), [ai-dev-jobs-metadata-quality-stress-test-2026-10-13.md](ai-dev-jobs-metadata-quality-stress-test-2026-10-13.md), [ai-dev-jobs-agent-workflow-privacy-review-2026-10-13.md](ai-dev-jobs-agent-workflow-privacy-review-2026-10-13.md) | What does that source's API return, how good is its metadata, and what does its agent policy permit? |
| [himalayas-api-permission-terms-conflict-2026-10-13.md](himalayas-api-permission-terms-conflict-2026-10-13.md), [himalayas-filtered-api-retrieval-attempt-2026-10-13.md](himalayas-filtered-api-retrieval-attempt-2026-10-13.md), [himalayas-remote-jobs-api-feasibility-review-2026-10-13.md](himalayas-remote-jobs-api-feasibility-review-2026-10-13.md), [himalayas-search-page-pilot-round2-2026-10-13.md](himalayas-search-page-pilot-round2-2026-10-13.md) | Does that source's permission text and API behaviour agree, and what did the filtered attempt return? |
| [remote-ok-api-feasibility-review-2026-10-13.md](remote-ok-api-feasibility-review-2026-10-13.md) | How does that feed fit, and what does its policy allow? |
| [smartrecruiters-api-policy-review-2026-10-13.md](smartrecruiters-api-policy-review-2026-10-13.md) | What does that ATS vendor's API policy permit an agent to do? |
| [ats-board-api-field-coverage-review-2026-10-13.md](ats-board-api-field-coverage-review-2026-10-13.md) | Which fields would the ATS board APIs actually supply, against what the product needs? |
| [public-apis-directory-review-2026-10-13.md](public-apis-directory-review-2026-10-13.md) | Did that directory turn up any usable source that the other passes missed? |
| [target-audience-source-search-probe-2026-10-13.md](target-audience-source-search-probe-2026-10-13.md) | Where does the intended audience's work actually get listed? |
| [job-source-coverage-audit-pilot-2026-10-13.md](job-source-coverage-audit-pilot-2026-10-13.md) | What fraction of a candidate's targets does the current seed cover? |
| [independent-employer-sample-pilot-2026-10-13.md](independent-employer-sample-pilot-2026-10-13.md), [official-employer-freshness-audit-2026-10-13.md](official-employer-freshness-audit-2026-10-13.md), [official-employer-freshness-audit-round2-2026-10-13.md](official-employer-freshness-audit-round2-2026-10-13.md), [official-employer-freshness-audit-round3-2026-10-13.md](official-employer-freshness-audit-round3-2026-10-13.md) | Were those listings still live, on the employer's own page, on the day they were checked? |
| [india-ai-internship-listing-audit-2026-10-13.md](india-ai-internship-listing-audit-2026-10-13.md) | How do listings for the candidate's own market hold up on the canonical page? |
| [open-status-and-canonical-evidence-audit-2026-10-13.md](open-status-and-canonical-evidence-audit-2026-10-13.md) | Does the seed's `open` status survive a canonical-evidence check? |
| [canonical-requisition-deduplication-2026-10-13.md](canonical-requisition-deduplication-2026-10-13.md) | Are duplicate requisitions across sources reconciled, and how? |
| [application-route-spot-check-2026-10-14.md](application-route-spot-check-2026-10-14.md) | Where does each listing's application route actually lead? |
| [candidate-relevant-record-review-2026-10-14.md](candidate-relevant-record-review-2026-10-14.md) | Which seeded records are relevant to this candidate at all? |
| [50-record-candidate-validation-roster-2026-10-14.md](50-record-candidate-validation-roster-2026-10-14.md) | What would the 50-record validation sample be made of, and how far along is it? |
| [source-validation-test-suite-2026-10-13.md](source-validation-test-suite-2026-10-13.md) | What tests would a source have to pass before it could be enabled? |
| [batch-research-pass-2026-10-14.md](batch-research-pass-2026-10-14.md) | What did the consolidation pass add, and why did it leave the gate closed? |
| [tracker-confirmation-smoke-test-diagnosis-2026-10-14.md](tracker-confirmation-smoke-test-diagnosis-2026-10-14.md) | Why did the confirmation-evidence floor behave the way it did in that smoke test? |

## Reuse and competitor reviews (decisions recorded, nothing adopted wholesale)

| Document | What it answers |
| --- | --- |
| [github-repository-audit-2026-10-13.md](github-repository-audit-2026-10-13.md) | Which public repositories were considered, and what was the reuse decision for each? |
| [public-github-reuse-audit-2026-10-14.md](public-github-reuse-audit-2026-10-14.md) | A second, broader relevance-led pass over public repositories — what did it add? |
| [internal-reuse-candidates-deep-audit-2026-10-13.md](internal-reuse-candidates-deep-audit-2026-10-13.md) | Of those candidates, which pieces would actually have been reused, and why? |
| [agency-agents-repository-review-2026-10-13.md](agency-agents-repository-review-2026-10-13.md), [n8n-workflows-repository-review-2026-10-13.md](n8n-workflows-repository-review-2026-10-13.md), [awesome-llm-apps-review-2026-10-13.md](awesome-llm-apps-review-2026-10-13.md), [superpowers-review-2026-10-13.md](superpowers-review-2026-10-13.md), [ruflo-review-2026-10-13.md](ruflo-review-2026-10-13.md), [gstack-review-notes.md](gstack-review-notes.md), [agent-reach-reuse-review-2026-10-14.md](agent-reach-reuse-review-2026-10-14.md), [open-source-ai-job-agent-review-2026-10-13.md](open-source-ai-job-agent-review-2026-10-13.md) | One reuse verdict per reviewed project, with the reason. |
| [competitor-landscape-and-feature-opportunities.md](competitor-landscape-and-feature-opportunities.md) | What does the surrounding product landscape do, and which gaps are worth occupying? |
| [claude-report-review-and-feasibility-gaps.md](claude-report-review-and-feasibility-gaps.md) | Which claims in an outside report held up against this codebase, and which did not? |

## Superseded or bounded to their date

| Document | Stands as | Superseded by |
| --- | --- | --- |
| [readiness-audit-2026-10-14.md](readiness-audit-2026-10-14.md) | The audit that produced the first defect list and the packaging/CI plan; its patch proposals are history. | [release-readiness-audit-2026-10-15.md](release-readiness-audit-2026-10-15.md) |
| The 2026-10-13 source-research batch and the 2026-10-14 consolidation above | Evidence as gathered on those dates, including the parts that were inconclusive. | Nothing: the gate they feed is still closed, so there is nothing newer to supersede them with. |

## Data files

| File | What it is |
| --- | --- |
| [job-source-audit-seed-2026-10-13.csv](job-source-audit-seed-2026-10-13.csv) | The 83-record seeded audit sample. Its bytes are pinned by SHA-256 in the audit script and the CI job that runs it; changing the file fails that check, and no test may edit it to pass. |
| [job-source-audit-summary-2026-10-14.json](job-source-audit-summary-2026-10-14.json) | The machine-readable summary of the audit over that seed. |

## How to read the dates

A date in a file name is the date the artefact was written, not a promise that its contents are current. The
two exceptions are the checklist and the CI-evidence file, which are maintained in place and carry their own
dated updates; where an update changes a number, the older number stays in the sentence that recorded it, and
the update says which one is current.
