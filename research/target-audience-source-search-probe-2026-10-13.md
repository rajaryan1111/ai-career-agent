# Target-Audience Search Probe: AI Dev Jobs and Remote-Role Leads

**Checked:** 2026-10-13  
**Purpose:** Continue the source-feasibility gate by probing visible search-indexed results for India-eligible internships/fresher roles and international remote roles.  
**Method limitation:** This was a bounded web-search/index probe, not direct execution of filtered API requests, not a full feed crawl, not a canonical-employer verification pass, and not a representative sample. Search snippets may be stale or incomplete. No credentials, scraping scripts, applications, or new dependencies were used.

## Executive result

**No source passes the production gate yet.** The probe provides evidence that AI Dev Jobs pages can expose junior/internship-labelled roles and India-location role listings, but the evidence is fragmented across company pages and does not establish a sufficient number of currently open, India-eligible entry-level jobs. Remote OK's feed is structured and broad, but its first visible records are not target-role evidence and it has a mandatory attribution/link-back requirement.

The next useful step remains a reproducible human-reviewed audit against canonical employer pages, not implementation.

## AI Dev Jobs: useful signals, unresolved coverage

Official API documentation describes filters for `level=junior`, `location`, `workplace`, and explicit `global_remote=true`; documented `type` values are full-time, part-time, contract, and freelance, not internship. Anonymous reads are subject to hourly IP throttling. Source: https://aidevboard.com/docs

Search-indexed company pages provided the following leads:

- **Workato:** its AI Dev Jobs company page listed multiple Hyderabad, India roles, but most visible India roles were mid-level or higher. A separate AI Engineering Intern listing was shown as San Francisco/on-site. This is evidence of some India-local coverage and a potential internship/role-type normalization issue, not evidence that the internship is India-eligible. Source: https://aidevboard.com/company/workato
- **SentinelOne:** its company page showed an AI/Machine Learning Engineer Intern role labelled “Remote (US)” and “junior,” alongside an India-located software engineer role that was not labelled entry-level. The intern is a negative eligibility test for an India-based candidate unless the canonical posting says otherwise. Source: https://aidevboard.com/company/sentinelone
- **Scale AI:** the page surfaced Software Engineering Intern roles in several named countries/cities, generally on-site. Those listings should not be treated as worldwide remote. Source: https://aidevboard.com/company/scale-ai

These pages have different search-index crawl dates (including months-old results). Their displayed status, counts, and apply links have not been freshly validated against the canonical employer boards in this probe. They must remain **leads**, not confirmed-open vacancies.

### Interpretation

- The absence of an `internship` value in the API's documented type enum does not prove internships are absent from the dataset; role titles and other fields may carry the signal. It does mean internship detection cannot rely only on the type field.
- `junior` is a source classification, not proof of fresher eligibility.
- “Remote (US)” is not India-eligible and is not worldwide remote.
- Company-page aggregate counts and search snippets are not a denominator for source recall.
- A canonical employer posting should override conflicting aggregator fields for current status, eligibility, work mode, and apply URL.

## Remote OK: feed quality and product requirement

Official feed: https://remoteok.com/api  
FAQ: https://remoteok.com/faq  
Terms: https://remoteok.com/legal

The live feed returns structured JSON and its first record carries a legal/attribution notice. The first visible job records include unrelated senior functions (for example, sales and product-design leadership); this is expected for a broad remote-work feed and demonstrates why relevance filtering is required. This tiny visible slice cannot establish whether suitable junior AI/software jobs exist elsewhere in the feed.

If used, the product must mention Remote OK and provide a followed hyperlink back to Remote OK on the screen where its data appears, and link each listing to its original job post. The attribution requirement is a product-design gate, not an optional credit.

## What this probe does and does not establish

**Established:**
- AI Dev Jobs has documented query filters and a structured API schema.
- Search-indexed AI Dev Jobs pages expose some India-location roles and some junior/internship-labelled roles, including examples that are clearly not eligible for every India-based candidate.
- Remote OK provides a structured feed with mixed-function roles and explicit attribution/link-back requirements.

**Not established:**
- Count of current, unique, valid India-eligible entry-level AI/ML/software jobs on either source.
- Count of current international remote roles that explicitly permit applicants located in India or worldwide.
- Precision, recall, completeness, freshness distribution, direct-link validity, or duplicate rate.
- Canonical employer status or the current permission to use each source in our intended production design beyond the documented points above.
- Any permission to automate application forms or submit applications.

## Recommended next experiment

1. Use documented source endpoints only and remain within published limits; record exact request/filter, timestamp, status, rate-limit headers, and result count. If this environment cannot reliably expose filtered endpoint responses, run the test in a local research script only after reviewing the endpoint terms; do not substitute search snippets for API results.
2. Collect a bounded sample of target records and verify each on the canonical employer page. Separately sample India-focused internship/fresher roles and international remote roles with explicit country eligibility.
3. Label: role family; evidence of entry-level/internship eligibility; allowed candidate countries; work mode; post/close dates; canonical status; valid direct apply URL; duplicates/reposts; pay with original currency and period; source agreement; permission/attribution status.
4. Include negative controls (e.g. “Remote (US),” on-site, senior roles, expired cohort, unrelated function) to verify that hard filters reject them.
5. Compare surfaced records with a manually assembled official-employer-board sample. Report precision among reviewed surfaced records only; do not claim recall without a defensible denominator.
6. Keep the proposed gate unchanged and explicitly unachieved: at least 20 currently valid target-relevant records, at least 90% valid direct application links, zero known false worldwide-eligibility claims, and no unresolved permission/attribution blocker. The 50-listing audit (25 India-focused, 25 international remote) is still not complete.

## Decision

**Continue research; do not integrate either source yet.** The probe improves our understanding of useful fields and false-positive cases, but it is not a source-coverage test. Next effort should finish the canonical 50-listing audit and source permission checks rather than collect more frameworks or start code.

## Sources checked on 2026-10-13

- AI Dev Jobs API docs: https://aidevboard.com/docs
- Workato AI Dev Jobs page: https://aidevboard.com/company/workato
- SentinelOne AI Dev Jobs page: https://aidevboard.com/company/sentinelone
- Scale AI AI Dev Jobs page: https://aidevboard.com/company/scale-ai
- Remote OK JSON feed: https://remoteok.com/api
- Remote OK FAQ: https://remoteok.com/faq
- Remote OK terms: https://remoteok.com/legal
