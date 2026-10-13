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

### 1. AI Dev Jobs — test first for AI/ML role discovery

Catalogue entry: https://aidevboard.com/openapi.yaml  
Official API docs: https://aidevboard.com/docs  
Terms: https://aidevboard.com/terms

The current docs describe an anonymous public read API with hourly abuse throttling and endpoints to search/filter active jobs, retrieve job details, inspect companies/tags, compare similar jobs, view salary trends, and request candidate-profile matching. Filters include keyword, tags, level, location, workplace, and an explicit worldwide-remote flag. Its published terms say API data may be used in applications but must not be resold as a standalone dataset; listing accuracy/completeness is not guaranteed.

**Why it may help**
- A fast experiment for AI/ML engineering roles without scraping job boards.
- A machine-readable API and MCP interface could let us test discovery and candidate-fit output before writing our own source connector.
- Company and salary endpoints could support shortlist-level company research.

**Limitations / caveats**
- It is focused on AI developer jobs, not all professions, and its India fresher/internship coverage has not been measured.
- Its own match score is a feature of that provider, not ground truth; we must independently apply our hard eligibility gates and explainable local matching.
- Free public access is throttled and the provider disclaims listing completeness/accuracy.
- Check terms and current endpoints again immediately before any integration; no production dependency should be approved based on a directory entry alone.

**Status:** High-priority candidate for a small coverage/quality audit; not approved as a production dependency.

### 2. Remote OK — possible remote-role source, subject to data-use constraints

API/feed listed: https://remoteok.com/api  
RSS: https://remoteok.com/remote-jobs.rss  
FAQ: https://remoteok.com/faq  
Terms: https://remoteok.com/legal

Remote OK's own FAQ describes its JSON and RSS job feeds as free and unauthenticated. It asks job aggregators or sites republishing the data to credit Remote OK and link to the original job post. This makes it worth investigating as a remote-only discovery candidate.

**Caveats**
- Remote does not necessarily mean worldwide eligibility. The agent must separate global-remote roles from location-restricted remote roles.
- The platform's terms can change; check current terms for the intended desktop application and use case, retention, display, refresh frequency, and attribution.
- Listing accuracy/freshness and Indian candidate relevance need measurement.

**Status:** Candidate for validation; not yet approved for integration.

### 3. Arbeitnow — regionally focused candidate, not a global source assumption

Catalogue entry: https://documenter.getpostman.com/view/18545278/UVJbJdKh  
Terms: https://www.arbeitnow.com/terms

The directory describes it as a Europe/remote job aggregator. The provider's terms say API use requires a backlink and may be revoked; the terms also describe personal/non-commercial limitations for some website materials.

**Implication:** Do not adopt it merely because the directory lists no authentication. Clarify the API-specific permission for our intended desktop product and assess whether its European-heavy coverage helps our initial audience. Lower priority than a source with clearer fit and usage permission.

### 4. Adzuna — already under review; directory entry adds no permission evidence

Catalogue entry: https://developer.adzuna.com/overview

Adzuna requires an API key. The directory does not answer whether the exact distributed desktop-product use case is permitted, whether quotas cover our refresh schedule, or whether India coverage is adequate. Continue using the separate official terms/quota review rather than treating inclusion here as endorsement.

### 5. Other job APIs in the list — do not assume they are free or suitable

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
- AI Dev Jobs terms: https://aidevboard.com/terms
- Remote OK API and RSS FAQ: https://remoteok.com/faq
- Remote OK terms: https://remoteok.com/legal
- Arbeitnow terms: https://www.arbeitnow.com/terms
- Adzuna official API docs: https://developer.adzuna.com/overview
- Open Skills API overview: https://github.com/workforce-data-initiative/skills-api/wiki/API-Overview
