# SmartRecruiters API Policy and AI-Agent Feasibility Review

**Checked:** 2026-10-13  
**Status:** Do not integrate unless SmartRecruiters/SAP confirms an authorized documented use or endorsed pathway for this product. Research only; no API calls, credentials, or connector implementation added.  
**Purpose:** Resolve the earlier open question about whether SmartRecruiters is a viable discovery source for a downloadable AI Career Agent.

## Decision

**Downgrade SmartRecruiters from “candidate to test” to “blocked pending explicit authorization / documented-use confirmation.”** Technical endpoints exist, but the official API policy contains a directly relevant restriction on (semi-)autonomous or generative-AI systems and systematic extraction. This product plans an AI agent that may plan, select, and execute workflows, so we must not assume the ordinary public-posting endpoint is suitable.

Do not ship a SmartRecruiters adapter, make repeated board queries, crawl company identifiers, use a credential that can expose internal postings, or work around the policy. Reconsider only after obtaining written clarification or a specifically endorsed service/architecture that clearly covers the intended use.

## What the official docs establish

### 1. Posting API is company-board oriented

The official [Posting API overview](https://developers.smartrecruiters.com/docs/posting-api) says the API is intended for customers to build customized career sites and says postings become accessible after being published through SmartRecruiters. The [endpoint guide](https://developers.smartrecruiters.com/docs/endpoints) describes listing active postings for a given company and retrieving a posting by ID. It is not a universal global job-search API.

### 2. Authentication and internal-posting exposure need special care

The official overview says the Posting API supports API keys and OAuth client credentials, and notes that a token with the relevant `internal_postings_read` scope can access internal postings; system roles/access groups are not enforced by this API for that scope. See [Posting API](https://developers.smartrecruiters.com/docs/posting-api) and [permission reference](https://developers.smartrecruiters.com/docs/permission-reference).

The endpoint guide includes example requests without an auth header, but this does not establish blanket authorization for a distributed AI product. Do not add credentials or rely on an ambiguous unauthenticated behavior without explicit source-specific approval and security review.

### 3. Current SAP API Policy is the decisive concern

The SmartRecruiters API platform page says its API use is governed by the [SAP API Policy](https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf), subject to SmartRecruiters-specific clarifications.

The linked policy is **SAP API Policy v.4.2026a**. It states:
- Published APIs are available for the purposes described in their documentation (“Documented Use”).
- SAP prohibits use for competitive analysis or scenarios outside documented use unless otherwise authorized.
- Except through and within the limits of SAP-endorsed architectures, data services, or service-specific pathways expressly identified and intended for such purposes, it prohibits API use for interaction/integration with (semi-)autonomous or generative AI systems that plan, select, or execute sequences of API calls, and for scraping, harvesting, or systematic/large-scale data extraction or replication.
- API controls must not be bypassed, disabled, or circumvented.

For this product, these clauses are material: a job-search agent that orchestrates multiple source requests could fall within the described restriction. We should not self-interpret an exception into existence.

### 4. Candidate terms are not a substitute for API authorization

The [Candidate Terms of Use](https://www.smartrecruiters.com/legal/terms-of-use/) are dated 14 May 2019 and include restrictions on certain automated access and collecting data about other users. Those terms are not a clear grant to build a third-party job aggregator. Customer terms are not necessarily the complete contract for an external developer either. The API policy and the exact documented/authorized use must be resolved directly.

## Product implications

- Keep SmartRecruiters in the source registry as **not approved / authorization required**, not as an available connector.
- Do not use SmartRecruiters to satisfy the “three permitted discovery sources” exit criterion.
- Do not query boards at scale to estimate coverage before the permission question is answered.
- Do not use application endpoints: the official Application API is authenticated and intended for customers/partners integrating an application process; that is not a candidate-side permission grant.
- Never expose internal/unlisted postings. Public-facing UI should use only verified public listings from an explicitly approved access path.
- The third-party ATS snapshot remains useful only for schema and failure-mode test ideas; it is not permission evidence.

## Questions to send SmartRecruiters/SAP if revisited

Ask for written answers covering:
1. Whether a downloadable desktop application for individual job seekers may use the public Posting API for personal job discovery and matching.
2. Whether use by an AI agent that plans/selects/executes source requests is allowed, and which endorsed architecture/service-specific pathway applies if so.
3. Whether queries may be issued across many employer boards and at what documented rate/volume.
4. Whether listings/descriptions may be cached locally, for how long, and what attribution/link-back is required.
5. How credentials must be scoped so internal postings cannot be retrieved.
6. Whether any marketplace/partner approval is required.

Until answered, no integration.

## Sources checked on 2026-10-13

- SmartRecruiters Posting API overview: https://developers.smartrecruiters.com/docs/posting-api
- SmartRecruiters endpoint guide: https://developers.smartrecruiters.com/docs/endpoints
- SmartRecruiters API platform and policy pointer: https://developers.smartrecruiters.com/docs/the-smartrecruiters-platform
- SAP API Policy v.4.2026a: https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf
- SmartRecruiters permission reference: https://developers.smartrecruiters.com/docs/permission-reference
- SmartRecruiters Candidate Terms of Use: https://www.smartrecruiters.com/legal/terms-of-use/

## Limitations

This is a product-risk interpretation of the official public documentation, not legal advice and not a claim that every possible SmartRecruiters integration is forbidden. The policy itself describes an exception for specifically endorsed architectures/data services/pathways; we have not established that the Career Agent qualifies for one. The safe decision is to defer integration pending explicit clarification.
