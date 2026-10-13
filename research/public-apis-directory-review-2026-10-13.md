# Review of `public-apis/public-apis` for AI Career Agent

**Reviewed:** 2026-10-13  
**Project stage:** research and product strategy only; no implementation authorized.  
**Repository reviewed:** https://github.com/public-apis/public-apis  
**Primary source inspected:** https://github.com/public-apis/public-apis/blob/master/README.md  
**Note:** The catalogue is a discovery directory maintained in Markdown, not itself a universal API service or quality guarantee. Individual providers have their own terms, availability, and licensing.

## Verdict

**Useful as a research index and shortlist generator, not as a dependency.** The most meaningful finding is that the current catalogue lists a few job-source candidates worth evaluating against our company-board strategy. It does not remove the main risk already identified: proving relevant India/international fresher and internship coverage using permitted, maintainable sources.

Do not automatically integrate everything marked “No auth” or “free”. The table records simple attributes (authentication, HTTPS, CORS) but does not establish accuracy, job coverage, production SLA, commercial rights, retention policy, or continued zero-cost use.

## Most relevant candidates from its Jobs category

### 1. AI Dev Jobs — highest-priority coverage-test candidate

Official docs: https://aidevboard.com/docs  
Terms (updated 2026-04-16): https://aidevboard.com/terms  
Privacy policy: https://aidevboard.com/privacy

The official API docs describe anonymous public read endpoints for search and job details, including filters for role level, location, workplace and explicit worldwide remote scope. Its terms say public reads are free and throttled hourly, prohibit scraping beyond API limits, permit API data to be used in applications, and prohibit reselling it as a standalone dataset. The provider disclaims listing accuracy, completeness and availability; job-listing content belongs to the respective companies.

**Why it is worth testing first**
- Clearer documented API-use language than sources with no public integration route.
- Search filters can support a focused AI/ML discovery experiment without building a scraper.
- Its explicit `global_remote` / remote-scope fields may help avoid falsely treating region-limited remote roles as worldwide.

**Limitations / caveats**
- Coverage of Indian internships, fresher roles and entry-level hiring is **not measured**. Documentation is not a coverage guarantee.
- The API is focused on AI developer roles, not all industries.
- Public-read hourly throttles and anti-abuse controls apply. Never exceed them or use alternate identities to evade them.
- The provider's own matching score is not ground truth; independently enforce hard eligibility and evidence-backed ranking.
- Its candidate-application endpoints belong to its own application flow and are not a generic way to submit applications to other employers.
- Minimize cached listing content and preserve source/original apply links; confirm any remaining retention/display details before production.

**Status:** First candidate for a small, human-reviewed coverage test; not yet approved as a production dependency. A limited live smoke test confirmed useful structured fields, but the first visible records were senior roles and the documented job-type enum does not include internship. India fresher/internship coverage remains unmeasured. See [live smoke test](live-source-smoke-test-2026-10-13.md).

### 2. Remote OK — possible remote-role source, with explicit attribution requirements

Official API/feed: https://remoteok.com/api  
RSS: https://remoteok.com/remote-jobs.rss  
FAQ: https://remoteok.com/faq  
Terms (updated 2026-07-20): https://remoteok.com/legal

Remote OK's FAQ describes its JSON and RSS feeds as free and unauthenticated. It asks job aggregators to credit Remote OK and link to every original job post. Its current terms also require a web or in-app hyperlink back to Remote OK on the page or app screen where API/site data is used.

**Why it may help**
- A low-cost remote-job discovery source with official feed URLs.
- Original-job links and a visible Remote OK attribution can be built into the product experience.

**Caveats**
- “Remote” is not the same as worldwide eligibility. Country restrictions must be captured separately.
- India fresher/internship coverage, stale-listing rate, duplicate rate, current rate expectations and caching/retention requirements have not been measured.
- The relevant app screen must visibly link back to Remote OK, and every role must link to its original job post.
- Re-check terms before production use.

**Status:** Candidate for a small coverage test after documenting attribution and retention behavior; not yet approved for integration. A limited live smoke test confirmed structured feed data and mandatory attribution language; visible entries included non-target functions. India fresher relevance remains unmeasured. See [live smoke test](live-source-smoke-test-2026-10-13.md).

### 3. Arbeitnow — regionally focused candidate, not a global source assumption

Catalogue entry: https://documenter.getpostman.com/view/18545278/UVJbJdKh  
Terms: https://www.arbeitnow.com/terms

The directory describes it as a Europe/remote job aggregator. The provider's terms say API use requires a backlink and may be revoked; the terms also describe personal/non-commercial limitations for some website materials.

**Implication:** Do not adopt it merely because the directory lists no authentication. Clarify the API-specific permission for our intended desktop product and assess whether its European-heavy coverage helps our initial audience. Lower priority than a source with clearer fit and usage permission.

### 4. Adzuna — already under review; directory entry adds no permission evidence

Catalogue entry: https://developer.adzuna.com/overview

Adzuna requires an API key. The directory does not answer whether the exact distributed desktop-product use case is permitted, whether quotas cover our refresh schedule, or whether India coverage is adequate. Continue using the separate official terms/quota review rather than treating inclusion here as endorsement.

### 5. SmartRecruiters — blocked pending explicit authorization

The official [Posting API overview](https://developers.smartrecruiters.com/docs/posting-api) and [endpoint guide](https://developers.smartrecruiters.com/docs/endpoints) document listing and retrieving postings for a named company board. That establishes technical endpoints, not permission for our product.

The SmartRecruiters API platform page says API use is governed by the [SAP API Policy](https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf). The linked **SAP API Policy v.4.2026a** restricts API use for (semi-)autonomous or generative-AI systems that plan, select, or execute sequences of API calls, and for systematic/large-scale extraction, unless an expressly identified SAP-endorsed architecture, data service, service-specific pathway, or authorization applies. That restriction is directly relevant to this AI-agent concept. SmartRecruiters documentation also warns that credentials with `internal_postings_read` can access internal postings.

**Status: not approved for integration or broad coverage testing.** Do not add credentials, crawl employer boards, or rely on an assumed exception. Revisit only after written clarification identifies an allowed pathway for a downloadable desktop app and its AI-agent workflow. See [the dedicated policy review](smartrecruiters-api-policy-review-2026-10-13.md).

Sources checked 2026-10-13:
- https://developers.smartrecruiters.com/docs/posting-api
- https://developers.smartrecruiters.com/docs/endpoints
- https://developers.smartrecruiters.com/docs/the-smartrecruiters-platform
- https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf
- https://developers.smartrecruiters.com/docs/permission-reference

### 6. Other job APIs in the list — do not assume they are free or suitable

The catalogue also lists providers such as JobsPipe, JobDataLake, Jooble, Findwork, The Muse, Careerjet, Reed, ZipRecruiter and others. Many require API keys; the catalogue's table does not prove their pricing, permissions, geographic coverage, or suitability for redistribution.

**Action:** Add no more candidates to the production plan until a candidate passes a basic gate: official documentation; terms for intended use; pricing and rate limits; geography and target-segment coverage; listing freshness/deduplication; stable direct apply URL; and clear attribution/retention requirements.

## Other categories that might support later features

These are secondary possibilities, not core job-discovery solutions.

- **Open Skills** (listed under Jobs): https://github.com/workforce-data-initiative/skills-api/wiki/API-Overview. Potentially useful for normalizing job titles and skills and comparing role requirements with the candidate's verified skill profile. The catalogue reports HTTP as non-HTTPS, so do not call it directly in a production workflow unless the official project confirms a secure endpoint. Verify freshness, data license, and availability first.
- **Company / business data:** entries in the Business category may help company research in principle, but most require keys and have unverified quotas/terms. Prefer official company sources and save third-party enrichment for shortlisted roles.
- **Text analysis / machine learning:** categories include hosted NLP, embeddings, and inference services. They are not inherently necessary: the current local-first, zero-mandatory-cost direction favours local processing and provider-independent interfaces. Consider external services only after measuring a concrete quality gap, privacy impact, cost, and retention terms.
- **Email / productivity:** email APIs may later enable follow-up reminders or application status signals, but OAuth scopes and access to sensitive inbox data materially increase risk. Not part of the discovery MVP.
- **PDF/OCR/document APIs:** not a priority because they send resumes or other sensitive documents to third parties unless self-hosted or used locally. Prefer local parsing; benchmark before considering remote document APIs.

## A better way to use this directory in the project

Use it as an **API research backlog**, with each candidate recorded as:
1. Directory entry and official provider documentation.
2. Intended use and exact capability (search, details, company data, matching, or actions).
3. Current pricing, auth, rate limit, geography, attribution, caching/retention and commercial-use terms.
4. A tiny hand-checked sample for coverage, freshness, duplicates, salary/location normalization and direct-apply link integrity.
5. A clear status: `unreviewed`, `terms unclear`, `test candidate`, `approved for experiment`, or `rejected`.
6. A review date and re-check trigger.

Never turn the whole directory into a runtime dependency. API entries are pointers that need provider-level verification, not guarantees that the endpoint is alive, free, safe, or permitted for our use.

## Recommended next experiment

Prioritize a **manual 50-listing audit**:
- 25 AI/ML entry-level/internship roles in India or explicitly open to India.
- 25 international remote AI/ML roles, recording whether “remote” is global or location-restricted.
- Compare a small sample from AI Dev Jobs and Remote OK against official employer career pages.
- Label relevance, eligibility, freshness, duplicates, required experience, location/work authorization and application URL.
- Record precision/coverage separately; do not score against the providers' own match scores.
- Ask providers for written clarification if API/terms wording doesn't clearly permit the intended use.

Success is not “we can fetch JSON”; success is finding relevant, eligible jobs with reliable source links and permission to display the data.

## Sources checked on 2026-10-13

- Public APIs directory: https://github.com/public-apis/public-apis
- Current README / Jobs category: https://github.com/public-apis/public-apis/blob/master/README.md
- AI Dev Jobs API docs: https://aidevboard.com/docs
- AI Dev Jobs terms (updated 2026-04-16): https://aidevboard.com/terms
- AI Dev Jobs privacy policy: https://aidevboard.com/privacy
- AI Dev Jobs terms: https://aidevboard.com/terms
- Remote OK API and RSS FAQ: https://remoteok.com/faq
- Remote OK terms (updated 2026-07-20): https://remoteok.com/legal
- Arbeitnow terms: https://www.arbeitnow.com/terms
- Adzuna official API docs: https://developer.adzuna.com/overview
- SmartRecruiters official Posting API: https://developers.smartrecruiters.com/docs/posting-api
- SmartRecruiters API policy pointer: https://developers.smartrecruiters.com/docs/the-smartrecruiters-platform
- SAP API Policy v.4.2026a: https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf
- SmartRecruiters technical reference (secondary only): https://github.com/GregoryBolshakov/ats-job-boards-reference
- ATS API example code (secondary only): https://github.com/strongboxr/ats-jobs-api-examples
- Open Skills API overview: https://github.com/workforce-data-initiative/skills-api/wiki/API-Overview
