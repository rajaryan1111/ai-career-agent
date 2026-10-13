# AI Dev Jobs: Agent Workflow and Privacy-Boundary Review

**Checked:** 2026-10-13  
**Status:** Research only. Not production approval.  
**Sources:** Official API docs, terms, and privacy policy.

## Why this deserves a closer look

The official AI Dev Jobs API documentation has evolved beyond a basic listing feed: it documents public job discovery, job details, matching, company and salary endpoints, an MCP server, optional free API keys for recurring agents, and a candidate-controlled application workflow. This could reduce integration work compared with building a generic scraper, but it introduces a distinct external-data and application-authorization boundary that must be evaluated against our local-first default.

Official docs: https://aidevboard.com/docs  
Terms: https://aidevboard.com/terms  
Privacy policy: https://aidevboard.com/privacy

## Verified capabilities and stated conditions

- **Discovery:** public unauthenticated GET endpoints support query, tags, type, level, location, workplace, explicit `global_remote=true`, remote scope and pagination. Anonymous access is hourly-throttled; the docs describe optional free API keys for recurring agents. Do not evade 429s or create alternate identities to bypass limits.
- **Agent interface:** the provider documents a Streamable HTTP MCP endpoint and search/detail/match/company/salary tools. Availability of an MCP server does not itself prove that its complete workflow is appropriate for our architecture.
- **Application action:** the documented developer apply endpoint accepts a compiled artifact ID/hash and single-use authorization after the candidate has reviewed and approved the exact artifact and verified candidate email. This is materially safer than blind auto-submit, but the precise authorization, revocation, failure/retry and duplicate-application semantics still need a controlled review.
- **Provider's stated price:** public discovery and candidate application preparation are described as free; the provider says its employer-funded verified-interview pilot is not a candidate charge. This is a provider claim, not a guarantee of future terms or a reason to assume all product operations are cost-free.
- **Listing quality:** the terms explicitly disclaim listing accuracy, completeness and availability. Canonical employer verification and hard eligibility checks remain required.

## Local-first and privacy implications

The privacy policy says public discovery does not require candidate identity. It also says that, when an application is submitted, the exact resume artifact is retained with the application and shared with the company owning the job. Candidate application and artifact records are therefore an external data transfer, not a purely local workflow.

Implications for our product:

1. Keep local-only discovery and application preparation as the default unless the user explicitly enables this provider-specific route.
2. Before any external application route, show a clear disclosure naming the recipient/provider, employer, exact resume/document version and fields being transmitted.
3. Require a per-application user review/approval of the exact compiled artifact; do not interpret a general app setting as permission to submit every future application.
4. Store provider credentials locally using OS-appropriate secure storage if a later implementation is approved; never put keys in logs, project files or source control.
5. Persist the provider's returned application ID/status and timestamps, but distinguish submitted, unverified, failed and confirmed states. Reconcile ambiguous timeouts before retrying.
6. Provide a local record of what was sent, to whom, when, and with which artifact hash; explain any provider-side retention and deletion limitations before opt-in.
7. Keep a user-controlled direct-to-employer route available for users who do not want application materials sent through this provider.

## Decision matrix

| Area | Current assessment | Gate before production |
|---|---|---|
| Public job discovery | Technically documented; free public read access stated | Bounded, canonical human-reviewed coverage sample; freshness and link checks |
| AI/agent compatibility | Provider explicitly documents agent/MCP use | Verify exact applicable terms and rate-limit behavior; do not assume all endpoints share identical semantics |
| Candidate submission | Documented workflow requires review/approval of exact artifact and single-use authorization | Test in a controlled account, with user consent, idempotency/retry behavior and authoritative status semantics |
| Privacy/local-first fit | Not local-only when an application artifact is submitted | Explicit opt-in and per-application disclosure; document retention and deletion |
| Monetary cost | Provider states candidate access/preparation is free and employer-funded pilot does not charge candidates | Re-check terms/pricing before release; no mandatory paid AI or service dependency |
| Listing correctness | Provider disclaims completeness, accuracy and availability | Verify canonical employer role, current status, eligibility and direct apply path |
| Production status | **Not approved yet** | All above gates must pass; do not count the provider as an independently validated coverage win until sample audit is complete |

## Recommended next step

Run a small, read-only API evaluation using the documented filters and within rate limits. Log exact queries, timestamps, HTTP status, rate-limit headers, response counts and schema fields. Human-review a bounded sample against official employer pages. Keep application endpoints out of the first coverage test; evaluate them separately only after discovery coverage and privacy disclosures are settled.

If a submission proof-of-concept is later authorized, use a test candidate/account and one harmless, deliberately reviewed application artifact only where a genuine application is intended. Do not submit dummy applications to employers, bypass verification or access controls, or infer successful submission from an HTTP request alone.

## Source notes checked 2026-10-13

- API docs: https://aidevboard.com/docs
- Terms (last updated 2026-04-16): https://aidevboard.com/terms
- Privacy policy (last updated 2026-08-02): https://aidevboard.com/privacy
