# Project Memory and Decision Log

This file is the durable record of meaningful decisions, research findings, assumptions, and open questions. Update it whenever the project reaches a meaningful point.

## Project identity

- Working name: **AI Career Agent** (not final).
- Repository: https://github.com/rajaryan1111/ai-career-agent
- Current stage: research and product strategy; no implementation.
- Last updated: 2026-10-13.

## Confirmed user decisions

1. Distribution: downloadable desktop application.
2. Automation: hybrid — automate supported, permitted cases and ask for intervention on exceptions.
3. Long-term audience: everyone, across candidate types and industries.
4. Initial budget: zero.
5. Primary priority: quality over application volume.
6. First research scope: broad, including Indian and international platforms.
7. Data handling: local-first; candidate data stays on the user's device by default.
8. Company research: detailed research for shortlisted/high-priority jobs.
9. Application policy: strict eligibility and match criteria.
10. Submission confirmation: ask only for missing information, sensitive declarations, unsupported steps, or uncertainty.
11. Default search schedule: 00:00 and 12:00 Asia/Kolkata.
12. Research-only constraint: do not write code or begin implementation until the product and feasibility research reaches a meaningful decision point.

## GitHub documentation workflow

- Repository of record: https://github.com/rajaryan1111/ai-career-agent, default branch `main`.
- When meaningful AI Career Agent research, a product idea, a decision, a risk, or a feasibility finding is developed in our conversations, update the relevant project Markdown file(s) and commit/push the change to this repository as part of that project work, without requiring a separate reminder each time.
- Keep the six core documents aligned: `prd.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, and `memory.md`. Add another file only when it gives the project a clear benefit.
- Add research sources and the date checked; distinguish verified facts from hypotheses, proposals, and unresolved questions.
- Prefer small, focused commits with descriptive messages. Do not silently overwrite or remove meaningful prior decisions; record material changes in the change log.
- Preserve the research-first constraint: documentation and research may be pushed, but do not start implementation/code until the agreed decision gate is reached.
- If an idea conflicts with a confirmed decision, creates a significant cost/privacy/compliance risk, or is ambiguous enough that it could change the product direction, record it as an open question or proposal rather than treating it as approved.
- This workflow applies when we are actively working on this project in ChatGPT. It is not a background service: it cannot monitor unrelated conversations or push changes while no project work is happening.

## Product principles

- Relevant and eligible applications matter more than raw volume.
- A public listing does not imply permission to scrape or automate.
- Job discovery and application submission must be evaluated separately.
- Do not fabricate candidate information or screening answers.
- Never mark an application confirmed without reliable evidence.
- Keep resumes, candidate profiles, and application records local by default.
- Core use should not require a paid AI API or hosted backend.
- A desktop-only scheduler cannot run while the computer is powered off or asleep.
- Do not promise universal platform coverage until individually verified.

## Current hypotheses (not facts)

- A local-first desktop application may provide meaningful core value without a mandatory recurring cost.
- A modular monolith is likely simpler than microservices for an initial version.
- Rules-based eligibility checks plus explainable scoring should precede advanced AI ranking.
- A source-by-source adapter design may make platform limitations easier to isolate.
- Company intelligence is most cost-effective when generated for shortlisted jobs.
- A trust-first workflow may differentiate the product better than maximizing automated application volume.
- A useful first release may focus on permitted job discovery, evidence-backed candidate facts, eligibility filters, tailored application kits, and user-confirmed tracking rather than automated submission.

## Research claims to verify and keep current

- Current terms and permitted access methods for LinkedIn, Internshala, Naukri, Indeed, Wellfound, and company career pages.
- Official APIs or feeds available for job discovery and application submission.
- Current competitor capabilities, limitations, and pricing.
- Whether at least three useful discovery sources can be supported at zero mandatory recurring cost.
- Whether a permitted application workflow can be validated for the MVP.
- Whether proposed features materially save users time in interviews or usability tests.

Record each finding with: claim, source URL, date checked, confidence, implication, and follow-up action.

## Open questions (highest priority)

1. Which job sources have documented permitted discovery access?
2. Which sources support or permit application submission, and under what conditions?
3. Can the product deliver useful discovery and matching without paid services?
4. How will the app recover from missed runs when the computer is offline?
5. Which candidate segment should be used for initial quality validation?
6. What test set and metrics establish resume extraction and matching quality?
7. Which desktop framework and local storage approach best meet privacy and maintenance goals?
8. What evidence is sufficient to mark an application as confirmed?
9. How can company research be sourced, timestamped, and kept affordable?
10. Which features produce the greatest measurable time savings?
11. Which competitor workflows should be tested hands-on before setting product scope?
12. Can company-specific Greenhouse, Lever, and Ashby job boards provide sufficient discovery coverage without prohibited scraping or a paid data provider?
13. What are the current official Adzuna API quotas, terms, and data-coverage limitations?
14. What privacy/data-protection obligations apply to local resume and application data?

## Proposed validation thresholds (not achieved)

- At least 95% exact extraction accuracy for selected critical fields on parseable resumes.
- At least 80% precision in the top 10 recommendations against a human-reviewed standard.
- Zero known hard-eligibility violations among recommended jobs.
- No duplicate submissions caused by retries.
- No confirmed application state without reliable evidence.
- At least three useful discovery sources with documented permitted access.
- At least one legitimate, testable application workflow.

These are proposed targets. Do not report them as measured results.

## Change log

### 2026-10-13 — Live job-source smoke test
- Opened the official AI Dev Jobs public jobs endpoint and Remote OK JSON feed through web retrieval. Both returned structured records; this was a limited smoke test, not a paginated or statistically representative coverage test.
- AI Dev Jobs' first visible records were senior roles; its documented job-type enum does not include internship. This is a risk/unknown, not proof that junior or India queries are empty.
- Remote OK returned mixed-function remote roles and requires source attribution plus links to each original job post. A visible India-location record was not an entry-level AI example.
- Created [live source smoke-test report](research/live-source-smoke-test-2026-10-13.md), updated the feasibility matrix and public API review. Proposed go/no-go thresholds are clearly marked as proposed, not observed results.
- Current decision remains no production integration until a bounded human-reviewed sample demonstrates useful target coverage and all permission/attribution gates pass.

### 2026-10-13 — AI Dev Jobs and Remote OK terms review
- Re-checked the providers' official docs/terms, not just the public-API directory.
- AI Dev Jobs documents anonymous public read endpoints and says API data may be used in applications but not resold as a standalone dataset; its API is throttled and the provider disclaims listing completeness/accuracy. Prioritized it for a small, human-reviewed target-coverage test; India internship/fresher coverage remains unmeasured.
- Remote OK's official FAQ asks aggregators to credit it and link every original job post; its terms require an in-app/web hyperlink back to Remote OK on the screen/page where API/site data is used. Attribution is a product requirement, not an optional nice-to-have.
- Neither source is production-approved yet. Test source relevance, freshness, duplicates, eligibility fields and direct links within documented access rules; do not infer global remote eligibility.
- Updated the official-source feasibility matrix and public API review. No live coverage sample was claimed because current listing coverage was not successfully measured in this pass.

### 2026-10-13 — Deep audit of internal reuse candidates
- Reviewed key code paths in `graphone-intelligence-pipeline` and `ai-orbit-tools-ingestion`, including HTTP transport, retry behavior, job adapters, source registry, pagination guards, checkpointing, robots handling, and official-site verification.
- Kept the reuse recommendation narrow: transport/error patterns, provenance, unknown/unverified states, safe pagination, resumability and deterministic fixtures are useful references. Existing job adapters and datasets are not automatically approved for reuse.
- Explicitly flagged the Wellfound sitemap crawler as incompatible with the current Wellfound source-policy stance unless an authorized route is verified. Robots.txt behavior is not a permission grant; fail-open retrieval must not be interpreted as approval.
- Added [deep internal reuse audit](research/internal-reuse-candidates-deep-audit-2026-10-13.md) and linked it from architecture. No code or datasets copied, no dependencies added, and implementation remains gated.

### 2026-10-13 — SmartRecruiters API policy gate
- Reviewed official SmartRecruiters Posting API documentation and its linked SAP API Policy v.4.2026a.
- The policy restricts API use for semi-autonomous/generative-AI systems orchestrating API-call sequences and for systematic/large-scale extraction unless an expressly identified SAP-endorsed architecture/data service/pathway or authorization applies. The Career Agent has not been shown to qualify for an exception.
- Downgraded SmartRecruiters to **not approved pending written clarification / applicable endorsed pathway**. Do not integrate, run broad board coverage tests, or count it toward the three-permitted-source exit criterion.
- Added [dedicated review](research/smartrecruiters-api-policy-review-2026-10-13.md) and aligned the source feasibility matrix, API directory review, and architecture adapter gate. No code, credentials, data, or dependencies added.


### 2026-10-13 — Sixth-pass India career-page audit
- Expanded the CSV to 39 data rows and added seven India-focused employer-page leads: RadialBrain AI Engineering Intern, two Zyora Labs student tracks, Inferova AI/ML Engineer Intern, Hajana AI/ML Intern, ATRISI ML/AI Intern, and Onelogica Data & AI Engineer / GenAI Platforms Intern.
- These are not seven confirmed-open, unique, fully verified vacancies. Several lack clear intake dates, stipend, detailed eligibility, or permission evidence; the two Zyora tracks share one application form and must not trigger duplicate applications.
- Added product-relevant risk notes: a form asking for “Father/Husband Name” should trigger data-minimization review and user confirmation, and role/timezone/cohort details (e.g., Hajana's 9 PM–6 AM IST schedule and 2025/2026 pass-out requirement) must not be collapsed into generic “remote internship” fields.
- Updated the coverage pilot with official URLs, source-specific limitations, and the interpretation that this mixed evidence dataset is not a clean 39-unique-open-job sample and cannot support precision/recall claims.
- Research-only constraint remains in force; no code started.


### 2026-10-13 — Fifth-pass evidence updates
- Added additional job/source records after checking current official/API pages and current search-index leads. CSV now has 32 data rows, but this is not 32 unique, verified-open vacancies: source-level entries, duplicate copies and negative controls remain intentionally included.
- Confirmed current AI Dev Jobs API docs expose anonymous reads, hourly IP throttling and filters for level, location, workplace and explicitly worldwide remote; terms disclaim completeness/availability and prohibit exceeding API limits or reselling data as a standalone dataset. Remains a candidate for measured coverage testing, not source of truth.
- Confirmed Remote OK FAQ documents free JSON/RSS feeds and requests credit plus links to original job pages for aggregators; legal terms should be checked against the proposed consumption/display model.
- Official RIVR Lever posting states Zürich/on-site and only Schengen-area citizens may apply, except certain ETHZ/EPFL compulsory interns — a concrete work-authorization exclusion case.
- Added a comparison copy for Ema from AI Dev Jobs showing source-field disagreement versus official Ashby data, and retained stale/unknown listings instead of falsely marking them open.
- Coverage audit remains a convenience lead/evidence set, not a statistical source-quality sample. The target of 25 India-focused + 25 international-remote unique listings is not yet complete; the present 32 rows must not be treated as such.
- No implementation started.


### 2026-10-13 — Fifth-pass source and workflow audit
- Added `research/superpowers-review-2026-10-13.md`; reviewed the upstream MIT-licensed Superpowers repo and key skill instructions. Recommendation is to reuse selected engineering-process ideas after the research gate, not install it as a runtime dependency.
- Added three CSV data rows covering an aggregator copy of Ema's existing official Ashby role and source-level AI Dev Jobs/Remote OK checks. This brings the CSV to 22 data rows, but not 22 unique vacancies and not the planned 50 unique listing audit.
- AI Dev Jobs docs support free anonymous read/search with hourly throttling and filters such as role level, location, workplace and explicit worldwide scope. Its terms disclaim listing completeness/accuracy, prohibit exceeding API limits, and prohibit standalone dataset resale. It remains a candidate source requiring an official-page coverage test.
- Remote OK FAQ documents free JSON/RSS feeds and requests attribution plus direct links to original postings for aggregators. Review current terms before integration. Not yet integration-approved.
- Ema comparison illustrates why the canonical employer role description must override conflicting aggregator seniority/type labels and why duplicates need distinct source IDs but not duplicate vacancy counts.
- No implementation started.


### 2026-10-13 — Superpowers workflow review
- Added `research/superpowers-review-2026-10-13.md` after inspecting upstream README, MIT license, and relevant skill files for brainstorming, writing plans, TDD, systematic debugging, verification-before-completion, subagent-driven development, and Git worktrees.
- Conclusion: Superpowers is development-process tooling, not a runtime job-search dependency, job data source, or fix for source permission/coverage. Do not install or copy it wholesale during research.
- Recommended future subset after the research gate: product brainstorming/spec, bite-sized explicit plans, test-first deterministic logic, root-cause debugging, fresh verification evidence, and isolated branches/worktrees. Use subagents only when work is independent and reviewable; preserve human authorization for external, irreversible, security-sensitive, privacy-sensitive, paid, and submission actions.
- The job-source coverage audit remains incomplete: the dataset now contains 22 CSV data rows, but three of those entries are source-level audit rows or a duplicate aggregator representation, so this is still not a 50-unique-listing sample. Continue official-page validation and add unique records in verified increments; don't infer coverage or precision from the convenience sample.
- No implementation started.


### 2026-10-13 — Public APIs directory reviewed
- Added `research/public-apis-directory-review-2026-10-13.md` after inspecting the upstream repository README and its Jobs, Business, Open Skills, Text Analysis, Machine Learning, email, and document-related sections.
- Conclusion: use `public-apis/public-apis` as a research index only, not a runtime dependency or proof that any listed service is production-free or authorized for our use.
- Added AI Dev Jobs as a high-priority candidate for a small, permission-aware AI/ML role coverage audit; its official docs describe free anonymous read endpoints and matching, while its terms disclaim listing completeness and restrict reselling data as a standalone dataset.
- Added Remote OK as a remote-job feed candidate based on its own FAQ; verify location scope, link-back/attribution and current terms before integration.
- Left Arbeitnow lower priority pending API-use clarification. Kept Adzuna's terms/coverage question unresolved. Open Skills may help skill taxonomy later but the directory marks it non-HTTPS, requiring secure-endpoint verification.
- Next recommended experiment: manually audit 50 roles (25 India/India-eligible entry-level AI/ML roles and 25 international remote roles) against official company pages, measuring relevance, eligibility, freshness, duplicates, location scope, and apply-link integrity.
- No implementation started.

### 2026-10-13 — Official platform feasibility matrix
- Added `research/job-platform-feasibility-matrix-2026-10-13.md` with a source-by-source capability and permission assessment for Greenhouse, Lever, Ashby, Adzuna, LinkedIn, Indeed, Wellfound, Workday, Naukri, and Internshala.
- Verified that Greenhouse, Lever, and Ashby offer employer-board-level discovery paths, but this does not establish comprehensive cross-employer search coverage or generic candidate-side submission permission.
- Recorded official restrictions affecting automated access or applications on LinkedIn, Indeed, Wellfound, and Workday; left Naukri and Internshala unresolved rather than guessing.
- Found Adzuna's official documented default API limits and trial/usage terms; its suitability for a distributed zero-cost desktop product remains unconfirmed.
- Strategic conclusion: the main feasibility risk is lawful, maintainable company-board discovery and coverage, not simply API parsing. Submission remains out of initial scope. No implementation started.

### 2026-10-13 — Claude report critically reviewed
- Added `research/claude-report-review-and-feasibility-gaps.md` with a critical review of the supplied partial Claude report and independent checks of official LinkedIn, Indeed, Lever, Ashby, and Greenhouse sources.
- Kept the strongest proposals as hypotheses: candidate fact provenance, hard eligibility gates, visible resume diffs, explicit application states, and catch-up behavior.
- Flagged unresolved source coverage, Adzuna quota, competitor pricing/quality, and legal/privacy questions; clarified that an anonymous 404 does not establish that a private repository is missing.
- No implementation started.

### 2026-10-13 — Initial competitor and feature scan
- Added `research/competitor-landscape-and-feature-opportunities.md` with a preliminary competitor comparison, initial platform compliance signals, feature opportunities, and validation experiments.
- Recorded the need to distinguish vendor marketing claims from tested behavior and proposals from confirmed product requirements.
- No implementation started.

### 2026-10-13 — Documentation workflow added
- Recorded the standing instruction to document and push meaningful project research, ideas, decisions, and feasibility findings to GitHub during active project work.
- Clarified that this is not a background process and does not authorize starting implementation.

### 2026-10-13 — Initial product baseline
- Established desktop-first, local-first, zero-mandatory-cost direction.
- Set hybrid automation and strict quality-first application rules.
- Defined research-first workflow and deferred implementation.
- Added proposed feasibility tests and decision gates.


### 2026-10-13 — Initial job-source coverage pilot
- Added `research/job-source-coverage-audit-pilot-2026-10-13.md` after checking a small sample of India-focused and international AI/ML internship listings on official Lever/Ashby/employer pages, including Ema, Drivetrain, Sprinto, Mactores, Meraki Labs, Cohere, STRATIVIS, Whiterabbit.ai, Output Biosciences, GPTZero, Preference Model, and Tesla, plus AICTE's National Internship Portal.
- Main finding: job-level eligibility and geography cannot be inferred from titles or a generic “remote” label. Examples include Ema's final-year/GPA/graduation conditions, Cohere's country-limited remote role, STRATIVIS's US-only remote role, and on-site/specialised research roles that should be hard-filtered for many users.
- The pilot is qualitative and intentionally **not** represented as the planned 50-listing audit. It does not establish source precision/recall, completeness, ongoing freshness, or automated-use permission.
- Next step remains the full 50-listing audit: 25 India-focused internship/fresher roles and 25 international remote roles, each checked against its official employer page with eligibility, status, location, work mode, duplicates, apply URL, and source permission recorded separately.
- No code or implementation started.


### 2026-10-13 — Second-pass job-source coverage leads
- Expanded `research/job-source-coverage-audit-pilot-2026-10-13.md` with second-pass leads from Apple Careers, Hibilter, ATRISI, Wadhwani AI, Zyora Labs, Trackmind, AICTE, Cohere, Great Question, Parspec, Persona AI, and Azul.
- Added useful positive and negative test cases: India-remote vs country-limited remote, on-site roles, experience requirements, zero-stipend roles, stale cohorts, US-program requirements, and AI-adjacent roles that are not AI/ML engineering.
- Audit remains qualitative and incomplete. Search-index visibility does not establish current availability, employer legitimacy, coverage quality, permission for bulk ingestion, or permission to automate applications.
- Next: build the structured 50-listing audit dataset (25 India-focused, 25 international remote), recording unknown/not-verified explicitly and validating each listing against its canonical employer page.
- No implementation started.


### 2026-10-13 — Third-pass source coverage and audit schema
- Expanded the job-source pilot with additional leads from General Motors, Atlys, Atlan, Amgen, Kinaxis, Matrice AI, Humans Care Foundation, Wadhwani AI, AICTE and Adobe.
- Recorded distinct hard-filter examples: on-site work, sponsorship restrictions, role-family mismatch, country-limited remote, time-zone requirements, graduate-level research eligibility, expired deadlines, short/zero-stipend tracks, and cohort dates.
- Added a proposed listing-level audit schema covering discovery and canonical URLs, first/last-seen timestamps, status, geography/work authorization, role family, education, work mode, compensation, application link, duplicates, source agreement, permission and confidence.
- Research remains qualitative and incomplete; do not claim the 50-listing audit is complete. Search results are leads, and each role needs canonical-page review.
- No implementation started.


### 2026-10-13 — Structured job-source audit seed created
- Added `research/job-source-audit-seed-2026-10-13.csv` with 16 seeded listing leads across employer career pages, Lever, Ashby, Workday, and the AICTE portal.
- Seed rows include explicit unknowns, last-checked date, source/canonical URLs, geography, work mode, role family, seniority, degree/experience criteria, dates, compensation, apply URL, permission status, confidence, and review notes.
- This is a **seed dataset**, not a completed 50-job audit: some rows are stale leads or negative controls, and current status/eligibility/permission remains unknown where not directly established. Do not calculate aggregate precision or coverage from this convenience sample.
- Freshly rechecked official pages include Apple Applied ML Intern, Drivetrain GenAI Engineering Intern, Ema AI/Data Resident, Trackmind Junior AI Engineer, and Cohere Winter 2027 ML Intern/Co-op. The sources demonstrate distinct India eligibility, work-mode, experience, and geography conditions.
- Next: inspect/normalize all seeded rows, then continue adding verified rows until the pre-defined 25 India-focused + 25 international remote audit is genuinely complete. Keep application automation permission separate from public page availability.
- No implementation started.


### 2026-10-13 — Fourth-pass status checks and audit corrections
- Updated `research/job-source-audit-seed-2026-10-13.csv` to 19 seed rows and added Apple PhD ML internship, Apple full-time Applied ML Engineer, and Workiva Summer 2027 ML internship as explicit role/seniority and staleness controls.
- Rechecked Kinaxis official page: Canada/Eastern-time-zone remote only; full-time 8- or 12-month placement starting Jan 2027; applications accepted through 18 Oct 2026. Updated the seed row to open with the stated deadline and removed an earlier unsupported inference of a Master's/PhD requirement.
- Marked Workiva as expired because the official posting close date was 2 Oct 2026, before the 13 Oct audit date, despite the page still being reachable.
- Reinforced audit interpretation: retain negative controls; permission_status=unknown means not established, not automatically allowed or forbidden; public official pages do not by themselves authorize bulk crawling or application automation.
- Current seed count is 19, not 50. The full 25 India-focused + 25 international remote audit remains incomplete; no implementation started.


### 2026-10-13 — Safe workflow distilled from gstack and Superpowers
- Added `development-workflow.md`, a project-specific guide that distills useful practices: problem framing, explicit specifications, small verifiable plans, test-first deterministic rules, root-cause debugging, two-pass review, fresh verification, and deliberate release/decision logging.
- Expanded `research/gstack-review-notes.md` from a brief conclusion into a clear record of what is useful and what is deliberately excluded. Updated `rules.md` to make the workflow a reference for future authorized engineering and explicitly preserve the research gate.
- Did not install either upstream toolchain, copy their skill directories, add dependencies/hooks/browser controls/telemetry, or start implementation. The guidance is an original adaptation, not a wholesale import of upstream text.
- Product-specific gates take precedence over developer-agent autonomy: verify source permissions separately for discovery and submission; never fabricate candidate facts; do not bypass CAPTCHA/OTP/anti-bot/access controls/rate limits; distinguish form fill/attempt from confirmed submission; retain local-first and zero-mandatory-cost constraints; require fresh evidence before completion claims.
- Sources: https://github.com/garrytan/gstack and https://github.com/obra/superpowers. Both are workflow/tooling references, not job-data sources or product dependencies. Upstream licensing should be rechecked before any future copying or redistribution.
- Research-only constraint remains active. No application code or third-party toolchain was added.


### 2026-10-13 — Selective review of awesome-llm-apps
- Reviewed upstream README, root Apache-2.0 license, and representative examples: Typed Agentic RAG, local hybrid-search RAG, local RAG, Corrective RAG, Scope Creep Detector, and AI Recruitment Agent Team. This is a selective review, not a line-by-line audit of the full catalog.
- Added `research/awesome-llm-apps-review-2026-10-13.md` with relevant patterns, explicit non-adoptions, sources, constraints, and review limits.
- Product-relevant ideas: evidence-backed fields/citations and refusal/unknown state for weak evidence; deterministic hard eligibility and state transitions; optional local inference/hybrid retrieval only after hardware and quality benchmarking; bounded fallback/retry; provider-free deterministic tests; and a lightweight “does every changed file/dependency serve the stated goal?” review.
- Deliberately rejected importing the recruitment-team demo as-is because it is employer-side and relies on hosted OpenAI, Gmail credentials and Zoom APIs; rejected wholesale agent/RAG frameworks, browser automation/scraping assumptions, self-modifying agents, and API-heavy stacks as premature or costly.
- GitHub reports the source repository as Apache-2.0; root LICENSE was inspected. No code, dependencies, copied skills, external services, database, or agent framework was added. Any future direct code/file reuse requires checking the exact source file/subproject, license/NOTICE and separate model/dependency terms.
- Research-first, local-first, zero-mandatory-recurring-cost constraints remain active. No implementation started.


### 2026-10-13 — Selective Ruflo review
- Added `research/ruflo-review-2026-10-13.md` after checking the Ruflo README, root MIT LICENSE, package manifest, user guide, and selected security, AIDefence, cost, memory and diff-review plugin READMEs.
- Retained only product-level ideas: risk/permission-gated tools and explicit approvals; privacy/secret handling and runtime input validation at boundaries; source-backed action logs and honest application-state transitions; simple cost budgets for any optional hosted inference; scoped, attributable, deletable candidate memory; and focused change/risk review.
- Rejected Ruflo CLI/MCP/hooks/plugins/console, swarms/federation/self-learning, AgentDB/RuVector, and broad dependency adoption at this stage. The README itself warns Claude Code mods run with the account's permissions and are not sandboxed; we should not add host-wide automation or privileges without a narrowly proven need.
- Ruflo is a developer-agent orchestration harness, not a job source or direct candidate application integration. It does not address the current top feasibility questions around permitted job-source access and coverage.
- No dependency installed, no Ruflo code copied, no app code written, and no product implementation started. Research gate and local-first/zero-mandatory-cost requirements remain unchanged.
- License observed as MIT at the repository root, but any future code reuse requires checking exact files, notices and third-party dependencies/models/services.

### 2026-10-13 — Broad GitHub repository audit and ATS API field study
- Screened all 18 repositories visible under the user's `rajaryan1111` account and carried forward focused reviews of the four previously shared external repos: Superpowers, gstack, awesome-llm-apps, and Ruflo. Deep-reviewed relevant source paths in `graphone-intelligence-pipeline`, `ai-orbit-tools-ingestion`, `AI_resume_review`, `indian-standards-procurement-ai`, and `jarvis-assistant`; other personal/college/portfolio repositories did not provide meaningful Career Agent domain assets.
- Added `research/github-repository-audit-2026-10-13.md` with the full inventory, relevant patterns, limitations, non-adoptions, and next validation priorities.
- Added `research/ats-board-api-field-coverage-review-2026-10-13.md` after reviewing `GregoryBolshakov/ats-job-boards-reference` and `strongboxr/ats-jobs-api-examples`. The dated 2026-08-29 field sample provides valuable edge cases but is not a representative current India internship dataset. No snapshot data was copied because its content redistribution rights and freshness are not established for our use.
- SmartRecruiters is now a research candidate only. Its current official docs/terms, permissions, rate limits, retention, and India/internship coverage remain unverified; no connector is approved.
- Highest-value internal code references: GraphOne's shared bounded HTTP client, typed errors, bounded backoff, freshness/schema/provenance/idempotency/entity resolution; AI Orbit's source registry, official-site-only verification, explicit unknown/unverified states, explainable dedup, resumability, and fixture tests; AI Resume Review's resume/JD UX (not directly reusable because its current frontend sends files to a separate API and uses a fixed demo user); IS Copilot's retrieval/reranking/evidence/provider abstractions; Jarvis's bounded tool loop and confirmation patterns.
- Added source-specific design/rules about provider-specific empty-response semantics, ATS migration, pagination, timestamp distinctions, pay range/unit ambiguity, missing vs zero, filtered runs not implying closure, and per-source contract fixtures.
- No code or third-party job data was copied; no dependencies or frameworks installed; no product implementation started. Research-first, local-first, zero-mandatory-recurring-cost constraints remain in force.

### 2026-10-13 — Target-audience source search probe
- Added [target-audience source search probe](research/target-audience-source-search-probe-2026-10-13.md) and linked it from the official source feasibility matrix.
- Search-indexed AI Dev Jobs company pages surfaced India-location roles and junior/internship-labelled examples, but also concrete negative controls: an AI/ML internship labelled Remote (US), and an internship in San Francisco/on-site. Crawl dates vary; canonical employer status and apply links were not verified in this probe. Treat these as leads and filter-test examples, not confirmed-open vacancies or measured coverage.
- Remote OK's structured feed remains broad across job families; its attribution/link-back requirement must be implemented on the screen where its data appears and each listing must link to the original post if the source is eventually approved.
- No source passes production approval. The 50-listing canonical audit (25 India-focused and 25 international remote) remains incomplete; precision/recall and target coverage are not measured. Continue source permission and coverage validation before implementation.
- No code, dependencies, credentials, or job datasets added. Research-first, local-first and zero-mandatory-recurring-cost constraints remain in force.


### 2026-10-13 — Incremental India AI internship listing audit
- Added three incremental audit leads (Sprinto AI Implementation Intern, Meraki Labs AI Engineer Intern, Sarvam ML & Speech Data Pipeline Intern) to `research/job-source-audit-seed-2026-10-13.csv`; CSV now has 42 data rows including negative controls, stale leads and unknown-status entries, not 42 confirmed-open unique jobs.
- Added [India AI Internship Listing Audit](research/india-ai-internship-listing-audit-2026-10-13.md) and linked it from the source-feasibility matrix.
- Evidence notes: Sprinto's canonical Lever page showed a current apply link but did not establish explicit candidate-country eligibility; Meraki's indexed Ashby content surfaced strict academic/GitHub signals but the browser returned a JavaScript-only shell; Sarvam's indexed Ashby page was months old and is treated as a stale lead until rechecked.
- Reinforced ATS retrieval semantics: a JavaScript-only shell is a retrieval limitation, not proof a job is missing; an apply link or public listing does not grant permission for automated submission. Keep unknowns explicit.
- No production source approved, no implementation/dependencies added, and the planned 50-listing canonical audit remains incomplete.


### 2026-10-13 — AI Dev Jobs agent workflow and privacy-boundary review
- Added [AI Dev Jobs agent workflow and privacy review](research/ai-dev-jobs-agent-workflow-privacy-review-2026-10-13.md) and linked it from the feasibility matrix after reviewing current official API docs, terms and privacy policy.
- The provider documents public search/detail/match APIs, an MCP endpoint and a candidate application endpoint that requires the exact compiled artifact to be reviewed/approved and uses single-use authorization. This is a potentially useful safety pattern, not approval to integrate automatically.
- Important local-first tradeoff: the provider's privacy policy says the submitted resume artifact is retained with the application and shared with the employer. Any future route requires explicit provider-specific opt-in and per-application disclosure/approval, local credential protection, retry/idempotency and status verification; preserve a direct-to-employer alternative.
- Provider terms disclaim listing accuracy/completeness/availability. Independent target-coverage validation and canonical employer checks remain necessary. Provider-stated free candidate access is not a guarantee of future pricing or a reason to relax the zero-mandatory-cost gate.
- No API integration or application endpoint calls made; no credentials or dependencies added. Production status remains not approved.


### 2026-10-13 — AI Dev Jobs metadata quality stress test
- Added [AI Dev Jobs metadata quality stress test](research/ai-dev-jobs-metadata-quality-stress-test-2026-10-13.md) and linked it from the source feasibility matrix.
- Targeted indexed-page review found concrete edge cases: an “AI Builder Intern” tagged full-time/junior; a SentinelOne AI/ML intern tagged Remote (US), full-time and junior; and an indexed Remote (India) junior ML engineer lead requiring freshness/canonical revalidation. These are negative/ambiguous controls, not a representative sample or proof of current-open status.
- Product requirement: preserve raw provider metadata separately from normalized values; treat internship/title/type contradictions as review signals; never infer worldwide eligibility from “remote”; verify canonical employer status, work authorization, role requirements and direct apply URL.
- The provider docs have no explicit internship type enum and describe junior as a level filter, not a guarantee of fresher eligibility. This web-indexed stress test is not a completed direct filtered API experiment; no coverage/precision/recall metrics claimed.
- No production source approved, no code/dependencies added. Continue with a bounded read-only API sample and canonical verification before implementation.


### 2026-10-13 — live AI Dev Jobs REST sample
- Read-only GET of `https://aidevboard.com/api/v1/jobs` succeeded through browser retrieval. Provider response reported 20 records/page, page 1, has_next=true, total=9,083, exact=true, total_pages=455.
- No internship title appeared in page 1. One record labelled junior was an on-site Electrical Integration Systems Engineer in Costa Mesa, California (Anduril); it is a negative control, not a candidate recommendation. The first page skewed toward senior/lead and US roles; several remote records had restricted or unknown scope. Some Anduril listings were near-duplicates.
- Many `expires_at` fields cluster around 2026-10-14 although `published_at`/ `updated_at` were in September. Semantics may be feed refresh/expiry, not employer deadline; clarify with provider and verify canonical employer page.
- Added [live API first-page sample](research/ai-dev-jobs-live-api-first-page-sample-2026-10-13.md) and CSV negative-control record `API-001`. CSV row schema remains 27 columns.
- Query-filtered URLs could not be retrieved through this interface, so no filtered API experiment or overall precision/recall is claimed. This is a convenience sample only. AI Dev Jobs remains discovery-only, not approved for production; no code/dependencies, account, API key, or application action added/used.


### 2026-10-13 — Himalayas remote-job API feasibility review
- Added [Himalayas API feasibility review](research/himalayas-remote-jobs-api-feasibility-review-2026-10-13.md) and linked it from the source feasibility matrix.
- Official schema appears better suited to remote internship discovery than AI Dev Jobs: explicit `employmentType=Intern`, `seniority=Entry-level`, country and worldwide filters, per-listing country/timezone restrictions, salary currency/pay period, publication/expiry timestamps, and application link.
- API documented free/public/no-auth, max 20 jobs/request and rate-limited. Requires visible Himalayas attribution and link to listing; do not resubmit its records to third-party aggregators. Remote-focused; does not cover India on-site/hybrid needs.
- Filtered live JSON endpoints could not be retrieved in this environment and local runtime had no DNS/network. No API query or coverage/precision metric claimed. Prioritize a bounded 4-query read-only pilot (India vs worldwide; AI vs ML; entry-level internship) once network access is available, then verify canonical employer pages.
- No code/dependencies, credentials, account, candidate data, or application action used. Neither Himalayas nor AI Dev Jobs is production-approved.


### 2026-10-13 — Remote OK source comparison
- Added [Remote OK API feasibility review](research/remote-ok-api-feasibility-review-2026-10-13.md) and linked it from the source feasibility matrix.
- Remote OK official docs describe free unauthenticated JSON/RSS feeds and tag filtering; attribution and original job-post links are required. The reviewed docs do not establish explicit internship, entry-level, country-eligibility, worldwide or timezone filters comparable to Himalayas. “Not established in docs reviewed” is not proof that a feature cannot exist.
- Decision: Remote OK is a secondary remote-source comparison; Himalayas remains first candidate for a structured remote-internship pilot. Neither is approved for production. Live feed JSON could not be retrieved from this environment, so no counts or quality metrics are claimed.
- No code/dependencies, account, API key, candidate data or application action added/used.


### 2026-10-13 — official employer freshness audit
- Added [official employer freshness audit](research/official-employer-freshness-audit-2026-10-13.md); updated the 27-column CSV with IN-025–IN-028 and NC-001–NC-002, then corrected IN-027 to the exact linked Google Form URL.
- Airbus official Workday GenAI internship is the strongest new lead: six months, RAG/LLM research and fine-tuning data preparation; still verify complete eligibility and live apply flow. GM official Workday AI/ML student intern says Bengaluru on-site, six months and 45 hours/week, but status remains unknown due inconsistent freshness indicators.
- vINe AI remote ML internship and ATRISI remote/hybrid Bengaluru ML/AI internship are low-confidence; role/country/pay details and application form privacy need review.
- Hard-negative controls: Semark canonical page explicitly says hiring finished 2026-10-11; BNP Paribas canonical page says Data Science Intern position is already filled, last updated 2026-10-12. Accessible job page or search freshness is not evidence that vacancy is open.
- CSV now has 49 data rows including leads, stale/closed negative controls and mixed source evidence. Do not call these 49 open unique jobs. No production integration or candidate-data submission.


### Dataset integrity repair — 2026-10-13
- Strict parsing of `research/job-source-audit-seed-2026-10-13.csv` found six pre-existing malformed rows: four unquoted commas split review-note columns, and two rows had a stray `unknown` before the apply URL. Repaired all six, preserved intended notes/URLs, and re-parsed the entire file.
- CSV now contains 49 data rows with exactly 27 columns in every data row. Future CSV updates must quote commas and revalidate schema after each edit. Repair noted in official employer freshness audit and source matrix.


### 2026-10-13 — official employer freshness audit round 2
- Added [official employer freshness audit round 2](research/official-employer-freshness-audit-round2-2026-10-13.md); CSV now includes IN-029–IN-033 and NC-003.
- Leads: Unisys AI Engineering Intern (Bangalore; AI pipelines/agents), AtkinsRéalis Robotics & AI Engineering Intern (Bengaluru; needs freshness recheck), Needl.ai AI Engineering Intern (Bengaluru hybrid; email application requires explicit approval), Concentric AI Machine Learning Intern (six months; ML/LLM/RAG), Bruker Graduate Apprenticeship Trainee AI/ML (apprenticeship eligibility unknown).
- Hard negative: GE Aerospace Data Science Intern official Workday result states deadline 2026-09-24, past as of 2026-10-13. Keep as expired control unless new requisition is confirmed.
- CSV has 55 mixed data rows, not 55 confirmed-open unique jobs. Validate every row's 27-column schema after edits. No candidate data sent, no application automation or production integration approved.

### 2026-10-13 — source validation test suite
- Added [Source Validation Test Suite](research/source-validation-test-suite-2026-10-13.md), a research-only QA gate with 32 deterministic fixture cases, bounded read-only live-source tests, reviewer labels, and proposed go/no-go thresholds.
- Reparsed the complete job-source CSV: 55 mixed data rows, 27 columns in every row, no duplicate listing IDs. Status counts: 7 open, 41 unknown, 3 expired, 2 closed, 1 not-a-listing, 1 source-review. These rows are not 55 verified-open unique jobs.
- Explicitly tests closed/expired controls, source-vs-vacancy rows, duplicate aggregator/employer evidence, role-family false positives, PhD/experience/location eligibility, email approval boundaries, missing compensation, and unknown permissions.
- Current live-source gate remains **not passed**: AI Dev Jobs filtered coverage is unmeasured; Himalayas filtered responses/coverage are unverified in this environment; Remote OK target precision is unmeasured; permission/attribution questions remain for candidate sources. Current official docs reaffirm Himalayas' 20-result cap, rate limiting, 24-hour refresh and attribution requirement, and Greenhouse's public GET vs API-key-protected application POST distinction.
- No product code, dependencies, credentials, candidate data transfer, or applications added/used. Continue research-only until the pre-registered sample and all hard gates are satisfied.

### 2026-10-13 — Remote OK live feed round-two smoke test
- Added [live source smoke test round two](research/live-source-smoke-test-round2-2026-10-13.md) and source-level audit row AUD-REMOTEOK-20261013. The official JSON feed was reachable through the web retrieval interface and returned a legal/attribution notice plus mixed roles; the retrieved response had no literal “intern” match, but this is not proof that the complete feed has no internships.
- Observed location-restricted roles and zero-like salary fields. Keep zero placeholders as unknown unless listing text confirms pay, and never infer India/worldwide eligibility from “remote”. Attribution and original listing links are mandatory; integration remains unapproved pending terms/retention review.
- Revalidated the full CSV after adding AUD-REMOTEOK-20261013: 56 data rows, 27 columns per row, no malformed rows, and unique listing IDs. A duplicate ID collision with an existing Barnes & Thornburg internship control was detected during verification and corrected by assigning the source-level audit a distinct AUD-prefixed ID. Status counts now: 7 open, 41 unknown, 3 expired, 2 closed, 1 not-a-listing, 2 source-review. These are mixed audit rows, not 56 open jobs.
- Filtered Himalayas API URLs and AI Dev Jobs query URLs were not accessible through this web retrieval interface; this is a tooling limitation, not evidence that the providers are down or that filtered queries return zero jobs. No target coverage or precision/recall claim is made.
- No product code, dependencies, credentials, candidate data transfer, or application submissions added/used.

### 2026-10-13 — Himalayas rendered-page pilot round 2
- Added [Himalayas search-page pilot round 2](research/himalayas-search-page-pilot-round2-2026-10-13.md). Current rendered India remote internship pages surface useful leads, but result counts varied between retrievals and categories include non-engineering jobs; counts/tags are not a qualified-vacancy metric. Filtered JSON API query URLs remain inaccessible through this web retrieval interface.
- Added three CSV controls: INT-019 Tether Research Engineer Intern (official role page; India listed; MSc/PhD requirement; current intake unknown), AUD-HIMALAYAS-MISMATCH-20261013 (One Impression title/company versus HexCoded description mismatch and growth/GTM responsibilities despite AI engineering tags), and INT-020 Origin CVAT Annotation Intern (aggregator reports India remote and a future deadline; official career page did not confirm this specific role in retrieved text; status remains unknown).
- Critical product rule: Tether's official application form explicitly says not to use AI tools when completing that application and warns generated answers may disqualify. Added a rule requiring the agent to honor employer-specific AI-use restrictions by not drafting or autofilling prohibited responses.
- CSV now has 59 mixed rows. Expected structural baseline: 27 columns, 59 data rows, no malformed rows or duplicate IDs; status counts should be 7 open, 43 unknown, 3 expired, 2 closed, 1 not-a-listing, 3 source-review. This is not 59 confirmed-open unique vacancies.
- No product implementation, dependencies, credentials, candidate data transfer, or application submissions added/used.

### 2026-10-13 — canonical verification of Sprinto internship
- Rechecked the existing IN-022 lead on the official Lever detail page: it displays an active apply link, Bengaluru/Remote, and student eligibility (currently pursuing CS/Engineering/Data Science or related), with AI infrastructure, model training/evaluation, document parsing/search and LLM integration responsibilities. Updated IN-022 to `open` with high confidence for listing status only; candidate eligibility still requires profile comparison, and deadline/stipend/work-authorization details remain unknown.
- Added SV-025 to the source validation suite as a positive canonical-page fixture. The role is AI implementation/applied engineering, not automatically ML research. No automated application or candidate data transfer occurred.

### 2026-10-13 — filtered API retrieval attempt and Tether eligibility correction
- Current official Himalayas docs confirm `/jobs/api/search` filters for keyword, country, worldwide, seniority, employment type, timezone, sort and page; public/no-auth access; 20-record maximum for browse requests; daily refresh and attribution/link-back requirements. Three direct filtered JSON URLs were inaccessible through the web retrieval interface, returning no HTTP status or body. Treat target coverage as unmeasured, not zero. Added [filtered API retrieval attempt report](research/himalayas-filtered-api-retrieval-attempt-2026-10-13.md) and source audit row AUD-HIMALAYAS-API-20261013.
- Rechecked Tether's current official application form: country selector begins with United Kingdom and “75 more” options; India-specific eligibility was not independently confirmed. Updated INT-019 to state India eligibility is unverified. The employer explicitly prohibits AI tools when completing application answers, which is now an application-integrity rule.
- CSV baseline updated: 60 rows, 27 columns each, no malformed rows, 60 unique IDs; statuses 8 open, 42 unknown, 3 expired, 2 closed, 1 not-a-listing, 4 source-review. These are mixed audit records, not 60 open jobs.
- No implementation code, dependencies, credentials, candidate data transfer or applications added/used.

### 2026-10-13 — Apple PhD eligibility and Sprinto CAPTCHA boundary
- Rechecked the official Apple Applied ML Intern listing. Its minimum qualification requires a PhD student in year 2 or beyond; Bengaluru location and “Intern” title do not make it suitable for undergraduate profiles. Updated CSV row IN-001 with degree/seniority evidence while retaining listing status as unknown pending a separate current-status check.
- Rechecked Sprinto's AI Implementation Intern page and application form. The role covers AI infrastructure, model training/evaluation, document parsing/search and LLM integration; the application page displays hCaptcha. Added a hard rule: never solve, bypass, or automate around CAPTCHA; pause for human intervention. An Apply link is not submission permission.
- Added SV-028 and SV-029 to the source validation suite and documented the findings in the official-employer freshness audit and feasibility matrix.
- Revalidated the full CSV after edits: 60 data rows, 27 columns, zero malformed rows, 60 unique IDs. Mixed leads and negative controls; not 60 open vacancies.
- Research-only gate remains in force. No product code/dependencies, candidate data transfer, API credentials, accounts, submissions, or CAPTCHA bypass.


### 2026-10-13 — repeat API retrieval attempt and pagination contract discrepancy
- Retried the three documented filtered Himalayas URLs and a documented read-only AI Dev Jobs India/junior query through web retrieval. All four were inaccessible through that interface and returned no HTTP status/body/headers. This is a tool limitation, not evidence of zero matches or provider outage; filtered target coverage remains unmeasured.
- Found an official-docs inconsistency for Himalayas browse pagination: its API landing page says cursor/nextCursor, while the public GitHub OpenAPI document describes limit/offset. Both specify a maximum of 20 jobs per request. Do not implement full-feed pagination until a live response or provider clarification resolves it.
- Updated the filtered API retrieval report, source validation suite, and feasibility matrix. Research-only gate remains in force; no code/dependencies, credentials, candidate data transfer, or application actions.

### 2026-10-13 — Himalayas pagination documentation freshness correction
- Rechecked the current official Himalayas API landing page against its public GitHub OpenAPI file and Python example. The landing page explicitly says cursor/nextCursor pagination is preferred and offset is deprecated; the OpenAPI file and example still use offset. Treat the latter as stale/out-of-sync documentation, not an unresolved API contract. If later authorized to implement, use cursor for browse and 1-based page for filtered search.
- Added SV-030 for API documentation freshness and corrected the earlier research report/matrix wording. Live filtered retrieval is still blocked in the current interface, so source coverage/precision remains unmeasured.
- No product implementation, dependencies, credentials, candidate data transfer or application actions.

### 2026-10-13 — Himalayas API permission clarification gate
- Compared current official API and AI-agent docs with the general Terms of Service. The API docs describe public integrations and require attribution/link-back; the general terms broadly prohibit automated data gathering/extraction without prior written approval.
- Marked Himalayas **blocked pending written clarification**. Do not run filtered coverage queries, crawl, cache, or build an adapter until the provider confirms the proposed local-first desktop use is permitted. Attribution alone does not resolve the conflict.
- Added a dedicated permission review with specific questions on personal job discovery, local caching/retention, displayed fields/links, local matching, attribution placement, export/offline use, and rate limits.
- Updated the feasibility matrix and source-validation suite (SV-031). Corrected the matrix's CSV baseline from 55 to the current 60 mixed records.
- No implementation code, dependencies, credentials, candidate data transfer, or application submissions added.


### 2026-10-13 — Agency Agents repository review
- Reviewed the upstream README, MIT license, security policy, selected specialist personas (minimal-change, search relevance, codebase onboarding, prompt engineering, evidence collection and reality checking), runbook examples, and the agent linter.
- Added [Agency Agents repository review](research/agency-agents-repository-review-2026-10-13.md) with an explicit reuse/reject decision. Adapt only minimum-change discipline, evidence-matched claims, human-labeled matching evaluation, prompt/retrieved-content safety, and selective use of specialist roles.
- Explicitly rejected copying/installing the full persona catalog, NEXUS/runbook orchestration, scripts, manifests, dependencies, and unrelated stacks. Upstream claims/metrics are not treated as empirical evidence; screenshots are not required for non-visual claims.
- No implementation code, dependencies, candidate data, job-source calls, credentials, or application actions added/used. Research-only gate remains in force.


### 2026-10-13 — Agency Agents repository review
- Reviewed the upstream README, MIT license, security policy, selected specialist personas (minimal-change, search relevance, codebase onboarding, prompt engineering, evidence collection and reality checking), runbook examples, and agent linter.
- Added [Agency Agents repository review](research/agency-agents-repository-review-2026-10-13.md) with an explicit reuse/reject decision. Adapt only minimum-change discipline, evidence-matched claims, human-labeled matching evaluation, prompt/retrieved-content safety, and selective use of specialist roles.
- Explicitly rejected copying/installing the full persona catalog, NEXUS/runbook orchestration, scripts, manifests, dependencies, and unrelated stacks. Upstream claims/metrics are not treated as empirical evidence; screenshots are not required for non-visual claims.
- No implementation code, dependencies, candidate data, job-source calls, credentials, or application actions added/used. Research-only gate remains in force.


### 2026-10-13 — n8n workflow collection review
- Reviewed upstream README, MIT license, security policy, and four representative workflow exports covering PDF/CV extraction, recruiter-side application intake/evaluation, scheduled webpage/news extraction, and scheduled RSS polling with batch/ID-cache/error handling.
- Added [n8n Workflows repository review](research/n8n-workflows-repository-review-2026-10-13.md). Reusable patterns are staged pipelines, bounded batches, stable-ID deduplication, explicit schema validation, visible per-source error outcomes, and resumable run evidence.
- Direct inspection found important caveats: the scheduled news workflow's node labelled “last 7 days” subtracts 70 days; two CV/application workflows contain external storage/email/calendar sinks and nodes represented as `noOp` stand-ins. They are not safe or verified drop-in templates. No workflow JSON was imported or executed.
- Updated the PRD and architecture to require explicit source-run outcome semantics and source-level counts. Kept local-first privacy, source permission gates, hard eligibility rules, and the implementation gate unchanged.
- Rejected adding n8n, Redis, Airtable, NocoDB, Google services, Slack, hosted LLMs, or any workflow engine as a dependency. No product code, dependencies, credentials, candidate data transfer, job-source calls, or application actions added/used.


### 2026-10-13 — source validation consistency pass
- Re-parsed the current audit CSV from the committed GitHub content: 60 data rows, 27-column header, zero malformed rows, zero duplicate listing IDs; statuses remain 8 open, 42 unknown, 3 expired, 2 closed, 1 not_a_listing and 4 source_review. This is a mixed audit set, not 60 open vacancies.
- Audited the source validation suite's test IDs: SV-001 through SV-031 were present with no gaps, despite the memory's stale “30 fixture cases” count. Corrected the count and added SV-032 for partial source failure/resume safety: source errors must not be treated as empty success, omitted records must not be marked closed, and retries must be idempotent.
- A fresh web search again found AI Dev Jobs official docs with public filters and hourly throttling, Remote OK free JSON/RSS feeds with mandatory on-screen source link-back, and current employer-page leads such as Airbus/Unisys. These findings do not replace a fixed, human-labelled sample or resolve filtered-query retrieval. No status was promoted from unknown solely on a search snippet.
- Verified the updated test suite and memory on GitHub after writing. Research-only gate remains closed; no source queries from the product, implementation code, dependencies, candidate data transfers, or application actions were performed.

### 2026-10-13 — official employer freshness audit round 3
- Added WATER's ML Intern Application as IN-034 after reviewing the official employer page: Hyderabad on-site, six months full-time, B.Tech/M.Tech/MS in CS/EE/Maths or related field, Python/PyTorch and evidence of end-to-end model training.
- Kept listing status as unknown: the page is dated 2026-08-24 and has a visible application form, but the retrieved page does not explicitly confirm the role is still open or give a deadline. Compensation and permission for automated extraction/submission are also unknown. No application was submitted and no candidate data was sent.
- Added SV-033 to the source validation suite: a visible application form is not sufficient evidence to label a vacancy open.
- Re-fetched and validated GitHub content: CSV has 61 mixed audit records, exactly 27 columns per row, zero malformed rows and zero duplicate IDs. Statuses: 8 open, 43 unknown, 3 expired, 2 closed, 1 not_a_listing, 4 source_review. These are mixed audit rows, not 61 confirmed-open jobs.
- Source validation suite contains SV-001 through SV-033 with no gaps. Research-only implementation gate remains closed; no product code/dependencies, source integrations, candidate data transfer, credentials or application actions.

### 2026-10-13 — QaliAI AI Job Agent source review
- Reviewed the public MIT-licensed QaliAI/ai-job-agent README/license, ATS source reference, privacy/architecture docs, ATS engine, registry, verifier, preference filter, claim checker and daily workflow. No upstream code was run, copied, imported or executed.
- Added [open-source AI Job Agent review](research/open-source-ai-job-agent-review-2026-10-13.md). Useful design concepts include local-first candidate truth, deterministic dedupe, canonical schema, transparent scoring and claim QA. However, direct source inspection found that the verifier treats HTTP 403 and network errors as live, some fetch/parser failures collapse to empty results, and per-source outcomes are not structured. Work-mode inference and salary filtering also need stronger evidence separation and currency/pay-period normalization.
- Rejected importing the upstream repository/adapters as a foundation. In particular, do not use its SmartRecruiters adapter while our existing policy gate is blocked. Public/keyless endpoint access and upstream usage are not permission.
- Added SV-034–SV-037 for source-error/empty distinction, fail-closed verification, ambiguous work mode/incomparable compensation, and provider-specific permission gates. Updated the source feasibility matrix and architecture.
- No product code, dependencies, credentials, candidate data transfer, live job-source queries or application actions were used. Research-only implementation gate remains closed.

### 2026-10-13 — Handoff consistency check
- During handoff verification, found the source validation suite's baseline table still said 60 rows / 42 unknown while the current strict-CSV parse returned 61 rows / 43 unknown. Corrected the suite baseline and re-fetched it to verify the update.
- Current strict CSV validation: 61 data rows; 27 columns in every row; zero malformed rows; zero duplicate listing IDs. Status counts: open 8, unknown 43, expired 3, closed 2, not_a_listing 1, source_review 4. These remain mixed audit/control records, not 61 confirmed-open vacancies.
- Current acceptance suite contains SV-001 through SV-037 with no missing IDs.


### 2026-10-13 — open-status and canonical-evidence audit
- Added [open-status and canonical-evidence audit](research/open-status-and-canonical-evidence-audit-2026-10-13.md) after fetching the current CSV and checking the eight `open` rows against their canonical URLs.
- Strict CSV parse: 61 rows, 27 columns, no malformed rows, no duplicate listing IDs. Statuses remain 8 open, 43 unknown, 3 expired, 2 closed, 1 not_a_listing, 4 source_review.
- No blank `canonical_employer_url` or `apply_url` fields were found, but URL presence is not proof of authoritative evidence, active status, permission, or candidate eligibility.
- Identified 8 repeated-canonical-URL groups across the 61 records. These duplicate requisitions/pages can inflate unique-vacancy counts even though listing IDs are unique; the Ema aggregator row INT-008 duplicates IN-003 and must remain a source-comparison control, not a second vacancy.
- Rechecked current canonical pages for Drivetrain, Trackmind and Sprinto; their pages displayed role details and Apply routes. Trackmind's page contradicts itself: header says Internship, while Work Details says Full-Time and requires 6 months–2 years of experience. Updated IN-004 review notes and retained listing-state `open` without treating it as a suitable fresher role.
- Current research retrieval returned only an app shell or no readable content for Ema, Cohere, Kinaxis and Airbus. These failures were not interpreted as proof of closure; same-day prior evidence remains qualified and canonical rechecks are required before recommendations.
- No product code or dependencies added; no blocked source was queried, no candidate data was sent, and no application was submitted. Research-only implementation gate remains closed.


### 2026-10-13 — canonical requisition deduplication
- Added [canonical requisition deduplication report](research/canonical-requisition-deduplication-2026-10-13.md) and annotated duplicate-group/primary/control roles in the existing CSV's `review_notes`; no rows or listing IDs were deleted and no status values were changed.
- Exact same-role URL groups: Ema (IN-003 / INT-008), Atlys (IN-005 / IN-014 / INT-015), CertifyOS (IN-013 / INT-014), RIVR (INT-011 / INT-016), Barnes & Thornburg (INT-012 / INT-017), Formstack (INT-013 / INT-018), and ATRISI (IN-020 / IN-028). These seven groups contain 15 records and 8 excess duplicate observations beyond one representative per group.
- Zyora Labs (IN-016 / IN-017) shares a general careers page but describes two different advertised tracks. Do not infer whether there are one or two distinct vacancies from URL equality; preserve both records and keep the count unresolved until employer/requisition evidence is available.
- Across all repeated URL groups, 17 records map to 8 URL buckets; the dataset therefore has 52 distinct canonical URL values across 61 rows. This is not a confirmed-vacancy count because the dataset also includes controls/source-review rows and general feeds.
- Added acceptance case SV-038 requiring exact canonical requisition deduplication without losing source provenance and prohibiting merging distinct tracks solely because they share a general careers page.
- The eight rows labeled open map to seven distinct canonical URL buckets because Ema's aggregator row INT-008 duplicates IN-003; this is a deduplication count only, not confirmation that seven unique jobs are currently open or eligible.
- Research-only gate remains closed: no implementation code/dependencies, candidate-data transfer, blocked source calls, or application actions.


- Follow-up consistency fix: synchronized the source-validation suite baseline with the reconciled CSV (61 mixed rows, 52 distinct canonical URL values, 8 repeated-URL groups) and corrected stale wording that referred to 60 records. Acceptance IDs SV-001 through SV-038 are present without gaps; ordering of the legacy SV-030/SV-031 sections remains a documentation-order issue only and does not change test identity.


### 2026-10-13 — independent employer sample pilot
- Added [independent employer sample pilot](research/independent-employer-sample-pilot-2026-10-13.md) after a fresh read-only search of official employer career pages.
- Added Walmart Global Tech India's `(IND) Grad Intern - No Work Experience` as IN-035. Official Workday search evidence showed a recent posting, Bengaluru, Apply, and GenAI/ML engineering scope, but direct page retrieval returned no readable lines; status is deliberately `unknown`, and missing eligibility details remain unknown.
- Rechecked the existing Unisys IN-029 lead: official result showed Apply, Bangalore and a recent posting, but direct canonical retrieval was unreadable. Added evidence to the notes and kept status `unknown`.
- Rechecked Airbus IN-025: official Workday result showed Apply, Bangalore Area, a posting from two days earlier, six-month duration and relevant RAG/LLM responsibilities. Existing `open` label retained provisionally; verify full canonical requirements before recommendation.
- Preserved GE Aerospace NC-003 as an expired negative control because the stated application end date 2026-09-24 precedes the 2026-10-13 check; page indexing alone does not reopen it.
- Updated source-validation baseline to 62 mixed rows, 44 unknown, 8 open, 3 expired, 2 closed, 1 not_a_listing, 4 source_review, and 53 distinct canonical URL values. Added SV-039 for a recent search snippet with an unreadable canonical page. No candidate data was sent and no applications were submitted.
- This small pilot is not a statistically representative sample and does not pass the source-quality gate. Source permission remains unresolved where noted; the research-only implementation gate stays closed.


### 2026-10-13 — independent employer sample follow-up: Threxil Systems
- Rechecked Threxil Systems' official careers page and the two linked role pages. The careers page explicitly states two roles open and says fully remote/work from anywhere. The AI Intern page covers retrieval/evaluation layers and asks for Python, NumPy/Pandas, and data structures/algorithms; the Frontend + AI Intern page asks for React/modern frontend tooling and some TypeScript exposure or willingness to learn. Both role pages welcome freshers and self-taught developers and expose a direct application form.
- Added INT-021 (AI Intern) and INT-022 (Frontend + AI Intern) as separate role records. Status is open based on the employer's explicit open-roles statement, not merely the presence of a form. Legal/work authorization by jurisdiction, compensation, duration, posting date, employer-legitimacy signals, and source permission for automated collection/caching/autofill/submission remain unverified.
- Updated the independent employer pilot and source-validation baseline. These are research leads only; no application was submitted, no candidate data was sent, no code/dependencies/connectors were implemented, and the implementation gate remains closed.
- Official URLs: https://www.threxil.com/careers ; https://www.threxil.com/careers/apply/ai-intern ; https://www.threxil.com/careers/apply/frontend-ai-intern.


### 2026-10-13 — international-remote sample expansion round 2
- Added INT-023 MailerMen Machine Learning Intern based on the employer-hosted listing's explicit Actively hiring, Remote (Worldwide), Freshers only, three-month duration, stipend, and 2026-10-13 update timestamp. Permission for automated collection/caching/submission remains unknown.
- Added INT-024 QovaTech AI Intern from its official career page: open internship, remote-friendly, agent/RAG/evaluation requirements, but candidate-country eligibility is not stated despite the company saying it serves clients worldwide.
- Added INT-025 DataRobot Agentic AI Intern from an official Workday search result. It listed US offices and Remote Canada-Ontario; direct page retrieval was unreadable, so status remains unknown and the row is a geography negative control, not a verified-open job.
- Updated the CSV, independent employer pilot and source-validation baseline. No candidate data was sent, no applications were submitted, and no code/dependencies/connectors were implemented; the source-quality and implementation gates remain closed.


### Current sampling segmentation and remaining gap — 2026-10-13
- After the Threxil and international-remote follow-up additions, the audit CSV contains 67 mixed records, 58 distinct canonical URL values, and 8 repeated-canonical-URL groups. Strict validation: 27 columns per row, no malformed rows, no duplicate listing IDs, and no missing canonical/apply URLs.
- A rough classification of unique role-like canonical URLs (excluding source-review/category rows and deduplicating exact canonical URLs) yields 53 records: 38 India-focused including negative controls, 12 non-India remote including geography/freshness controls, and 3 other location/work-mode cases. This is a sampling label, not a claim that these roles are currently open, eligible, or source-authorized.
- The planned international-remote comparison set target is 25 unique listings, so 12 additional distinct records remain to be reviewed. Continue with official canonical evidence, keep stale/unreadable records unknown, and do not loosen source-permission or human-submission gates.


### 2026-10-13 — restricted-remote controls and SV-040
- Added INT-026 Cohere Research Internship (Winter 2027) from the official Ashby page. The page says remote but lists Canada, Europe, UK and US locations (not India), requires work authorization in the employment country, and is PhD-level. Current status remains unknown; it is a geography/seniority negative control for an India-based undergraduate.
- Added AUD-ZOLVE-20261013 for the official Zolve Summer Internship Program 2026 page. It explicitly says applications closed and requires a Bachelor's or Master's degree pursued in the US; since it is a multi-role program page, status is `not_a_listing` and it is excluded from vacancy counts.
- Added SV-040 to require remote work mode and country eligibility to remain separate, and to reject global-eligibility inference when a finite location whitelist excludes the candidate's country.
- Updated the audit CSV, pilot report, test-suite baseline, and memory. Research-only gate remains closed; no code/dependencies/connectors, candidate-data transfer, or application submissions.


### 2026-10-13 — segmentation refresh after restricted-remote controls
- Recalculated unique role-like canonical URL segmentation after adding Cohere Research Internship and the Zolve program control: 54 role-like canonical URLs; 39 India-focused records including controls; 12 non-India remote records including geographic/freshness controls; 3 other location/work-mode cases.
- The international-remote target remains 25 unique records, leaving 13 additional distinct records to review. Zolve is excluded from vacancy counts because its source is a closed multi-role program page, not a single requisition.


### Sampling classification correction — 2026-10-13
- Cohere Research Internship (INT-026) is counted as a non-India remote sample because its explicit listed employment locations are Canada, Europe, the UK and US, with India not listed. The phrase “India not listed” is an eligibility restriction, not an India-focused location. Current segmentation: 54 unique role-like canonical URLs; 38 India-focused (including controls), 13 non-India remote (including controls), 3 other location/work-mode cases; 12 more non-India remote records are needed to reach the target of 25.


### 2026-10-14 — broad public GitHub reuse audit
- Completed a bounded public-GitHub search across 12 relevant query themes, with 100+ result entries before deduplication and README/license/documentation review of a selected set of external repositories. This was not an exhaustive crawl of all public GitHub; the user's own repositories were excluded from discovery.
- Added [Public GitHub Reuse Audit](research/public-github-reuse-audit-2026-10-14.md). Findings retained as design references: Career-Ops' local-first/evidence-first workflow and user-controlled submission; Job-Radar's employer-board identity verification, per-host pacing and resumable scans; an evidence-grounded resume agent's verified-claim registry, `do_not_claim` boundaries, deterministic audit and hard-negative tests.
- Identified Remotive's public remote-jobs API as a conditional research candidate only. Its repository states a 24-hour delay, recommends at most four requests/day, requires a canonical Remotive link and attribution, and prohibits submitting its listings to third-party job websites. No API request was made; source use remains unapproved pending intended-use/terms review and coverage testing.
- Rejected JobSpy integration because its README advertises proxy support to bypass blocking; rejected importing an n8n workflow that transfers Gmail job alerts into hosted Notion; did not import scraped job datasets or historical Open Jobs snapshot. Open Jobs' README says the live service stopped on 2026-10-10 and its last snapshot was 2026-10-05.
- Added SV-041 (API terms/attribution/rate limits) and SV-042 (dataset license vs upstream provenance/freshness) to the source-validation suite. Updated the feasibility matrix with Remotive's conditional status.
- No code, dependencies, credentials/API keys, workflows, datasets, candidate data transfers, live job-source queries, or application actions were added/performed. Current CSV remains 69 mixed audit records, 27 columns per row, zero malformed rows, zero duplicate IDs, statuses: 14 open, 48 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review; 64 distinct canonical URL values. These are not 73 confirmed vacancies. Source-quality and implementation gates remain closed.


### 2026-10-14 — second public GitHub search pass: Jobicy and remote APIs
- Expanded the external-repository search to Jobicy, Himalayas, Arbeitnow, The Muse, public API catalogs, evaluation datasets, and India internship APIs.
- Added a follow-up to [Public GitHub Reuse Audit](research/public-github-reuse-audit-2026-10-14.md) and the source feasibility matrix. Jobicy's official repository documents a no-key remote-jobs API with structured filters and a rolling seven-day window; its Fair Use rules allow product use with canonical Jobicy links and attribution, and say not to begin new automated polling/synchronization more frequently than hourly. Its code MIT license does not license the job data itself. Prioritize only a bounded, human-reviewed coverage test after the gate authorizes it; no endpoint was called and no integration was added.
- Reconfirmed Himalayas remains blocked pending written clarification: its GitHub README has attribution terms and a 24-hour refresh/rate-limit note, but the existing broader Terms of Service conflict remains unresolved. Do not query/cache the feed until permission is clarified.
- Arbeitnow third-party catalogs and a May 2025 tracker snapshot were not accepted as sources or imported datasets. No code, data, dependencies, credentials/API keys, or application actions were added/performed; research-only gate remains closed.


### 2026-10-14 — third public GitHub pass: API client and matching patterns
- Reviewed Jobicy's public MIT-licensed API examples, including its typed Python client and MCP example. Retain future-adapter design ideas only: optional-field-safe typed records, provider-ID deduplication, canonical URL validation, bounded pagination, repeated/expired-cursor handling, dynamic tool/schema discovery, and explicit failure for partial exports. Added SV-043 to the validation suite. No code copied, dependency installed, or endpoint called.
- Reviewed a multilingual LaBSE/FAISS + cross-encoder job-matching prototype and generic job-search/RAG projects. Their mock/synthetic corpora, project-specific reported scores, missing expected-path license files, or insufficient validation detail do not justify importing code or data. Keep only the general research idea of comparing lexical baselines with semantic retrieval/reranking and reporting relevance separately from latency.
- Updated the public GitHub reuse audit and feasibility matrix with these decisions. Jobicy remains conditional for a bounded human-reviewed test; Himalayas remains blocked pending written clarification; source-quality and implementation gates remain closed. No code, data, dependencies, credentials, candidate data transfers, live source API queries, or application actions were added/performed.


### 2026-10-14 — fourth continuation: country-scoped remote sample expansion
- Added audit records INT-027–INT-030 from official employer pages: Khan Academy Summer 2027 Software Engineer Intern (US/Canada only; deadline 2026-10-16; prior internship and 2028/2029 graduation requirements), Datacor Summer 2027 AI Engineer Intern (Remote US; master's/PhD requirement; status unknown), Kinaxis AI&ML Research Intern (existing vacancy; Eastern Canada location rules; master's/PhD requirement), and Celestica Student Intern, AI Project Coordinator (Remote Canada; 16-month internship starting May 2027; status unknown without explicit open/closed wording).
- Updated the independent-employer sample report: 58 unique role-like canonical URLs, 38 India-focused records including controls, 17 non-India remote records including geographic/freshness controls, and 3 other location/work-mode cases. The 25-record international-remote comparison now has 8 distinct records remaining to review. This is a research sample, not 25 qualified or India-eligible jobs; country restrictions and degree level remain independent filters.
- Rechecked the existing 73-row audit CSV: 27 columns, no malformed rows, no duplicate listing IDs, and 64 distinct canonical URL values. Status counts are 14 open, 48 unknown, 3 expired, 2 closed, 2 not_a_listing, and 4 source_review. The four new rows do not establish permission for automated collection/caching/autofill/submission. No API endpoint was called, no integration or dependency was added, no candidate data was transferred, and no application was submitted. Research/source-quality and implementation gates remain closed.
