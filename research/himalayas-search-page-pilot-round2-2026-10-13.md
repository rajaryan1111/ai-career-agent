# Himalayas Search-Page Pilot — Round 2

**Checked:** 2026-10-13  
**Status:** Research only. Filtered API requests remain inaccessible through the current web retrieval interface; this pass uses the public rendered search pages and direct listing pages. It is not a reproducible API payload test or a representative market sample.

## Executive result

The rendered Himalayas search pages demonstrate useful India-specific remote internship discovery, but also show why category counts and tags cannot be treated as qualified-job counts. The API's documented filters are a good fit, yet direct API query URLs could not be retrieved here. The source remains a candidate, not production-approved.

## Observed rendered search pages

| Page | Visible count/evidence | Interpretation |
|---|---|---|
| [Remote AI Internships in India](https://himalayas.app/jobs/countries/india/intern--ai) | One render displayed 33; a later page-two render displayed 21–39 of 39 | Count changed between retrievals; treat counts as time-varying and do not compare as a stable snapshot without capturing one response consistently |
| [Remote AI ML Internships in India](https://himalayas.app/jobs/countries/india/intern-ai-ml) | Direct page render showed 5 listings; search index had previously surfaced 6 | Indexed snippets and rendered pages are not a consistent measurement frame |
| [Remote Entry-level AI Engineer Jobs in India](https://himalayas.app/jobs/countries/india/entry-level-ai-engineer) | Rendered page contains a mixture of AI internships, full-time roles, and non-engineering AI-adjacent work | Role-family filtering and explicit employment-type checks are mandatory |

The AI-intern page displayed role cards including Drivetrain's Engineering Intern – Gen AI for FP&A Platform, Tether's Research Engineer Intern (Video/Multimodal LLM), Mactores' Product Engineer Intern, Origin's CVAT Annotation Intern, and multiple marketing, product, sales, or operations internships. This is useful discovery breadth, but it is not evidence that every card is a relevant engineering vacancy or that all are currently open.

## Listing-level controls examined

### Tether — Research Engineer Intern (Multimodal LLM)

Official page: https://careers.tether.io/o/research-engineer-intern-videomultimodal-llm-remote

- The official page lists Bangalore and Delhi among locations and has an application form.
- The role description says internships in 2025/2026 and rolling review; the current intake is not conclusively established by the retrieved page alone.
- The stated minimum qualification is an MSc or PhD candidate in computer science or a related technical field, with relevant LLM/CV/multimodal research experience and PyTorch proficiency. This must hard-exclude candidate profiles that do not meet the stated qualification.
- The application form explicitly says not to use AI tools when completing the application and warns that AI-generated answers may disqualify candidates. This is a critical product rule: if a posting prohibits AI assistance for application answers, do not draft, autofill, or submit those prohibited responses. The candidate must answer independently.

### Origin — CVAT Annotation Intern

Aggregator listing: https://himalayas.app/companies/origin-tech/jobs/cvat-annotation-intern  
Official careers page: https://origin.tech/career

- Himalayas reports India-only remote work, a six-month contract-to-hire arrangement, and an apply-before date of 2026-12-09.
- The retrieved official Origin careers page displays a generic Open Roles section but does not visibly confirm this specific role. Keep status unknown until the specific requisition is verified.
- The work described is computer-vision annotation and dataset QA supporting robotics, not model-training or ML-engineering work. Keep it as an adjacent role family; recommend only when the candidate's configured preferences include it.
- The Himalayas “Job expired?” control is a user-report link, not evidence that the listing is expired.

### One Impression / HexCoded — AI Generalist Intern

Aggregator listing: https://himalayas.app/companies/one-impression/jobs/ai-generalist-intern

- The title/company label says One Impression, while the body says “About HexCoded” and describes a small AI video studio in Gurgaon. This identity mismatch is unresolved.
- The responsibilities focus on growth/GTM, funnel metrics, user calls and product testing; the description says an engineer is not required, despite broad AI/ML and AI-engineering category tags.
- The listing says final-year student or 2026 graduate, India-only, with an aggregator-reported 2026-12-12 deadline. Do not promote this as an ML-engineering role until employer identity and role details are confirmed.

## What this pilot proves — and does not prove

**Supported:**
- Himalayas rendered search pages can surface India-filtered internship leads and metadata such as role type, level, location restriction, posted date, deadline, and description.
- Tags and page totals can be noisy or change between retrievals; source metadata must be independently validated.
- Canonical employer pages can reveal hard eligibility constraints and application-specific restrictions that an aggregator category does not express.

**Not supported:**
- No live filtered API response payload was retrieved, so API-query coverage is still unmeasured.
- The visible search-page count is not a count of unique, currently valid, target-relevant jobs.
- This pass does not establish precision, recall, stable listing counts, or production permission for every downstream use.

## Decision

Keep Himalayas as the first candidate for a bounded remote-internship pilot, with canonical-page verification and source attribution. The next data test should capture a reproducible response from the documented `/jobs/api/search` endpoint in a network-enabled environment and manually label a fixed sample. Until then, no production integration or application automation is approved.

## Sources checked

- API docs: https://himalayas.app/api
- API reference: https://himalayas.app/docs/remote-jobs-api
- India AI internship search: https://himalayas.app/jobs/countries/india/intern--ai
- India AI/ML internship search: https://himalayas.app/jobs/countries/india/intern-ai-ml
- Tether official role: https://careers.tether.io/o/research-engineer-intern-videomultimodal-llm-remote
- Origin official careers: https://origin.tech/career
- Origin aggregator listing: https://himalayas.app/companies/origin-tech/jobs/cvat-annotation-intern
- One Impression / HexCoded listing: https://himalayas.app/companies/one-impression/jobs/ai-generalist-intern