# Himalayas API Permission and Terms Conflict Review

**Checked:** 2026-10-13  
**Status:** Unresolved permission gate; not approved for product integration.  
**Scope:** Research-only review of official Himalayas API documentation and general Terms of Service. This is not legal advice.

## Executive decision

Do not implement or call Himalayas for product data collection until the provider clarifies in writing that the proposed desktop application use is permitted under the applicable terms. The public API docs invite public-data integrations and describe use cases including job search experiences and AI agents, but the general Terms of Service prohibit data mining, robots, screen scraping, or similar automated gathering/extraction/publication without prior written approval.

These statements appear to conflict or at least leave material ambiguity about whether the API integration is an exception to the general prohibition. Do not assume that a public unauthenticated endpoint, an API guide, or attribution alone resolves the conflict. Equally, do not conclude the API is categorically prohibited in all circumstances: obtain a source-specific clarification.

## Official evidence

1. **Public API guidance:** https://himalayas.app/api — checked 2026-10-13. It describes a free public JSON API, no authentication, browse and filtered search endpoints, request limits, and says integrations can use the data for remote job boards, search experiences, internal dashboards, or AI-agent workflows. It requires visible mention of Himalayas and a link back to Himalayas, and says not to resubmit its listings to third-party websites/aggregators.
2. **API reference / AI-agent guidance:** https://himalayas.app/docs/remote-jobs-api and https://himalayas.app/docs/ai-agents — checked 2026-10-13. These describe public API/feed/MCP options, rate limiting, and attribution requirements.
3. **General Terms of Service:** https://himalayas.app/terms — checked 2026-10-13. Section 30 states users may not use data mining, robots, screen scraping, or similar automated data-gathering, extraction, or publication tools on the site without prior written approval. Other terms restrict copying/reproducing/distributing material except where permitted.

## Interpretation and boundaries

- The API documentation is meaningful evidence that API-based integrations are contemplated, but the general terms' broad language means we should not treat API availability as an unconditional authorization.
- A direct API call is not the same mechanism as screen scraping, but the terms' language is broad enough that this distinction should not be used as a self-issued permission exception.
- Attribution is required if use is approved; it does not by itself resolve the permission conflict.
- Do not use the website scraper, crawl the full feed, run filtered API coverage sampling, cache or redistribute job data, or build an adapter while this gate remains unresolved.
- Do not submit Himalayas-sourced listings to third-party job aggregators. The proposed local-first desktop app is not itself a third-party job board, but its display, caching, export, and distribution model should be described accurately when seeking clarification.
- Keep the earlier API pagination finding separate: current docs recommend cursor pagination for browse and page pagination for filtered search, but correct technical mechanics do not establish permission.

## Clarification request checklist

Ask Himalayas support (hi@himalayas.app) to confirm in writing:
1. Whether a downloadable local-first desktop application may query the public JSON search API for individual users' personal job discovery.
2. Whether results may be cached locally, and for how long; what fields may be retained.
3. Whether displaying listing titles/snippets and links to both Himalayas and the canonical employer listing is permitted.
4. Whether local matching/ranking and user-generated application preparation are permitted, provided no applications are submitted to Himalayas or third parties by the app.
5. Whether attribution must appear on every result card, every screen, or another specified placement.
6. Whether there are restrictions on redistribution, export, offline use, or bundled copies of listing data.
7. What rate limits apply to this desktop-client use case and whether a backend proxy is required or discouraged.

Do not send candidate profiles, resumes, or other personal data in this request.

## Product decision until clarified

- Source status: **blocked pending written clarification**.
- Production approval: **no**.
- Coverage evidence: **not measured**; previous retrieval-interface failures are not evidence of zero results or provider downtime.
- Safe fallback: continue researching other sources with clearer documented permission and independently verified target coverage. Do not silently count Himalayas toward the three-source feasibility gate.
- Re-open only after written clarification is recorded with date, contact/context, scope of permission, attribution, rate limits, and retention terms.

## Change log

- 2026-10-13: Added after comparing the current public API documentation with the general Terms of Service. This is a permission clarification requirement, not a final legal conclusion.
