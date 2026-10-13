# Live Source Smoke Test — Round 2: Remote OK feed

**Checked:** 2026-10-13  
**Method:** Read the official public JSON feed through the web retrieval interface and inspected returned content with exact-term searches. This is a limited live smoke test, not a full export, representative sample, or production integration.

## Observed evidence

- Official endpoint: https://remoteok.com/api
- The response was exposed as JSON and began with a legal/attribution object requiring a followed link to Remote OK and a mention of Remote OK as a source. The official legal terms also need to be reviewed before integration: https://remoteok.com/legal.
- The visible recent records included a senior sales executive role and a product-design director role. Further returned records included a Philippines-restricted administrator role and technical roles whose descriptions contained seniority/experience restrictions.
- A search for the literal word “intern” across the retrieved response returned no match. This is a property of the content available through this retrieval interface, **not proof that the full Remote OK feed has no internships**.
- The feed included records with specific country/location restrictions and records with salary_min / salary_max set to 0. Those zero values cannot safely be displayed as confirmed zero compensation without corroborating listing text.
- The response was long but bounded by the retrieval interface; it is not a complete reproducible API export and does not provide a valid denominator for precision/recall.

## What this supports

1. The public feed is reachable through this interface and returns structured listing records plus an attribution notice.
2. Role-family and seniority false positives are plausible if the product relies on broad tags or title-only matching.
3. Candidate geography must be checked per listing; “remote” is not equivalent to India-eligible or worldwide.
4. Salary zeros need explicit missing/placeholder handling.
5. Attribution is a product requirement, not a later polish item: display Remote OK as a source with a followed link and link each listing to its original job page.

## What this does not support

- It does not establish the total number of AI/ML roles, internships, fresher roles, or India-eligible jobs in Remote OK.
- It does not establish an overall freshness rate, precision, recall, or deduplicated unique-job count.
- It does not authorize automated application submission or settle every caching/retention question.
- It does not mean the absence of “intern” in the retrieved payload is a reliable full-feed negative result.

## Decision

Keep Remote OK as a secondary candidate for the pre-registered coverage pilot, not as a production-approved source. Before any implementation, use a repeatable bounded sample, manually label each vacancy, verify canonical employer/application pages, implement visible attribution, and resolve current terms/retention questions. Do not add application automation or dependencies during this research phase.

## Source

- Official JSON feed: https://remoteok.com/api
- Official FAQ: https://remoteok.com/faq
- Official legal terms: https://remoteok.com/legal
