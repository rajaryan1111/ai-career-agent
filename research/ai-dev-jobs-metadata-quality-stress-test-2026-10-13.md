# AI Dev Jobs: Listing Metadata Quality and Eligibility Stress Test

**Checked:** 2026-10-13  
**Status:** Research only; no integration approved.  
**Method:** Review of the provider's current official API docs plus search-indexed job/category/company pages. This is a targeted stress test, not a direct filtered API execution, not a representative sample, and not a canonical-employer status audit.

## Executive finding

AI Dev Jobs may be technically convenient, but its indexed listing metadata must not be treated as ground truth for role type, seniority, geography, or current status. Several visible records are useful negative controls:

- A listing titled **AI Builder Intern** on the provider's junior-jobs page is labelled `full-time` and `junior`.
- An **AI/Machine Learning Engineer Intern** on the SentinelOne company page is labelled `Remote (US)`, `full-time`, and `junior`.
- A **Machine Learning Engineer** on the provider's listing page is marked `Remote (India)` and `junior`, but the page is two months old in the search index and must be checked against the employer's current careers page before it is recommended.
- The provider's junior-jobs page contains many roles whose actual titles/responsibilities are experienced engineering, management, or specialist positions. A source-level `junior` value is therefore not proof of fresher eligibility.

Sources:
- Provider's junior category: https://aidevboard.com/level/junior
- SentinelOne company page: https://aidevboard.com/company/sentinelone
- Coinbase job listing: https://aidevboard.com/job/machine-learning-engineer-14ab9c77
- API docs: https://aidevboard.com/docs

## What the official docs establish

The documented `type` values are full-time, part-time, contract, and freelance; there is no explicit internship value. The `level` values include junior, mid, senior, lead, and principal. Location, workplace, `global_remote`, and `remote_scope` filters are available. The provider states that `global_remote=true` returns only roles explicitly open worldwide. Anonymous read requests have hourly IP throttling; stay within it and do not retry around 429s.

Source: https://aidevboard.com/docs

## Stress-test cases

| Case | Provider-visible metadata | Correct product treatment |
|---|---|---|
| Internship title, full-time type | AI Builder Intern / `full-time` / `junior` | Preserve raw fields; infer a potential contradiction; verify canonical employer role type; never silently normalize to a confirmed internship |
| Intern, Remote (US) | AI/ML Engineer Intern / `Remote (US)` / `full-time` / `junior` | Hard-reject for an India-based candidate unless the employer explicitly allows India; do not treat remote as worldwide |
| India-remote junior role with old indexed timestamp | Machine Learning Engineer / Remote (India) / junior; page indexed two months ago | Treat as a lead only until canonical status and eligibility are freshly verified |
| Junior tag on experienced/manager role | Some junior-page titles or responsibilities indicate manager/experienced specialist scope | Role title, requirements and canonical description override generic source level; mark ambiguous rather than assume entry-level |
| Salary data missing or placeholder | Some records omit pay | Preserve unknown; never translate missing/zero-like placeholder into unpaid or ₹0 salary |
| Filter returns zero | API docs do not make an empty filtered result proof of overall source coverage | Distinguish query returned no records from endpoint unavailable, unsupported filter, pagination limit or no target listings in the sample |

## Product requirements derived from these cases

1. **Store raw source values and normalized values separately.** Never overwrite the provider's original `type`, `level`, location or remote scope with our inferred classification.
2. **Attach evidence to normalized role type.** Titles containing “intern”, “co-op”, “graduate”, “apprentice” or “new grad” can trigger review, but cannot override contradictory requirements or canonical employer facts.
3. **Treat geography as a hard gate.** `Remote (US)`, `Remote (Canada)`, country-limited work authorization and unknown scope must not become worldwide eligibility.
4. **Do not rely on source level alone.** Read required years of experience, degree/cohort restrictions, responsibilities and seniority language. A hard-filter uncertainty should lower confidence or trigger review, not a positive assumption.
5. **Verify active status and direct apply URL.** Freshness of the aggregator page and canonical employer page must be separate timestamps. An apply click or accessible detail page does not prove the role is open.
6. **Record field conflicts.** Contradictions such as intern title + full-time type should be a measurable source-quality signal and an explainable warning.
7. **Keep the first coverage test read-only.** Do not call application endpoints or create candidate accounts to test discovery. If direct API requests are not available in the current research environment, record that limitation instead of claiming a filtered API test was completed.
8. **Respect source limits.** Use documented endpoints, bounded pagination and published rate limits only. Never evade 429s or access controls.

## Evaluation proposal

Add these adversarial records to the human-reviewed sample. For each surfaced record, compare provider fields with the canonical employer page and label:

- title/type contradiction;
- level/requirements contradiction;
- country eligibility and work authorization;
- remote scope;
- current canonical status and last checked timestamp;
- apply URL validity;
- missing or placeholder compensation;
- duplicate/repost status.

Report contradiction rate and false-eligibility rate separately from relevance precision. Proposed safety target remains zero known false worldwide-eligibility claims. No source precision/recall is measured by this small targeted stress test.

## Decision

Keep AI Dev Jobs as a candidate for the next bounded, read-only coverage test, not as an authoritative source of eligibility. The most valuable next step is a reproducible direct API sample with captured request filters, response status, rate-limit headers and canonical verification. This web-indexed stress test does not count as that API experiment and does not satisfy the production gate.

## Source log checked 2026-10-13

- https://aidevboard.com/docs
- https://aidevboard.com/level/junior
- https://aidevboard.com/company/sentinelone
- https://aidevboard.com/job/machine-learning-engineer-14ab9c77
