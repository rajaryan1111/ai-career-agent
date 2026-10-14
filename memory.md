# Project Memory and Decision Log

This file is the durable record of meaningful decisions, research findings, assumptions, and open questions. Update it whenever the project reaches a meaningful point.

## Project identity

- Working name: **AI Career Agent** (not final).
- Repository: https://github.com/rajaryan1111/ai-career-agent
- Current stage: production-oriented, cross-industry product implementation plus parallel source/competitor/permission research; the local Tkinter/SQLite alpha is implemented; resume parsing, source adapters and remote worker remain gated or pending.
- Last updated: 2026-10-14.

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
12. Superseded on 2026-10-14: the strict research-only constraint applied to all code. The user directed that the software must be built; safe local product implementation proceeds in parallel with research, while live integrations remain evidence-gated.
13. Product commitment reaffirmed on 2026-10-14: treat AI Career Agent as a real-world, production-oriented product, not a prototype-only deliverable. The long-term audience spans all job profiles and industries; use an industry-agnostic core plus extensible occupation-specific intelligence.
14. Product outcome: help real candidates discover relevant jobs, prepare truthful applications, apply through permitted and validated workflows, track employer responses, and improve their process. Never guarantee hiring or selection.
15. Background operation: default discovery runs are 00:00 and 12:00 Asia/Kolkata. Operation while the laptop is powered off requires a separately deployed and verified always-on worker; desktop-only scheduling is insufficient.
16. Standing authorization: routine applications may proceed without per-job prompts only when the candidate has configured a scoped, revocable policy and the provider/employer permits the workflow. Uncertain facts, sensitive declarations, assessments, CAPTCHA/OTP, prohibited automation, and ambiguous submissions remain exceptions.

## GitHub documentation workflow

- Repository of record: https://github.com/rajaryan1111/ai-career-agent, default branch `main`.
- When meaningful AI Career Agent research, a product idea, a decision, a risk, or a feasibility finding is developed in our conversations, update the relevant project Markdown file(s) and commit/push the change to this repository as part of that project work, without requiring a separate reminder each time.
- Keep the six core documents aligned: `prd.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, and `memory.md`. Add another file only when it gives the project a clear benefit.
- Add research sources and the date checked; distinguish verified facts from hypotheses, proposals, and unresolved questions.
- Prefer small, focused commits with descriptive messages. Do not silently overwrite or remove meaningful prior decisions; record material changes in the change log.
- Implementation is authorized for the real product roadmap. Continue local UI/workflow and reliability work while source research proceeds; do not enable a specific live source, remote data transfer, paid service, email action, or application submission until its own permission/privacy/quality gates pass.
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
7. How well does the Tkinter/SQLite alpha package and behave on macOS, Windows, and Linux; what migration/backup/encryption work is needed before release?
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

### 2026-10-14 — Safe offline-core implementation authorized
- Decision: begin building the software now while source and competitor research continues in parallel. This supersedes the earlier blanket no-code/research-only constraint, but does not waive source-specific permission, data quality, privacy, or application-integrity gates.
- Added a dependency-free Python domain core in `career_agent/`: three-valued eligibility, explicit country scope, transparent skill overlap, conservative URL/requisition deduplication, separate source/application URLs, and guarded application-status transitions.
- Added 18 standard-library unit tests covering eligibility, unknown handling, explicit worldwide scope, URL normalization, duplicate behavior, source/apply URL separation, and application confirmation evidence. Local test run: 18 passed.
- Added a root README with current implementation status and test instructions. No source connector, live API call, network client, candidate-data transfer, resume parser, autofill, submission workflow, or third-party dependency was added.
- Current decision: implementation is allowed for safe local core only. The source-quality gate remains NOT PASSED for live integrations and job recommendation claims.

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
- Rechecked the expanded 82-row audit CSV: 27 columns, no malformed rows, no duplicate listing IDs, and 73 distinct canonical URL values. Status counts are 15 open, 56 unknown, 3 expired, 2 closed, 2 not_a_listing, and 4 source_review. The four new rows do not establish permission for automated collection/caching/autofill/submission. No API endpoint was called, no integration or dependency was added, no candidate data was transferred, and no application was submitted. Research/source-quality and implementation gates remain closed.


### 2026-10-14 — fifth continuation: four additional remote eligibility controls
- Refreshed existing INT-006 (Azul Marketing AI Intern) from the official Lever page instead of counting the same canonical requisition twice. Added three distinct records: INT-032 Azul IT Intern, AI and Operations (US remote; undergraduate and GPA requirements), INT-033 CertiK Blockchain Security Expert Intern — AI Track (ongoing applications, PhD-level requirement, US work-eligibility verification), and INT-034 Binance Tech Seeds Applied AI Agent Engineer (listed locations Taiwan/Hong Kong/Australia/New Zealand; local laws and team-dependent remote arrangements).
- Updated the pilot report to 67 unique role-like canonical URLs: 38 India-focused records including controls, 26 non-India remote comparison records including geography/freshness controls, and 3 other location/work-mode cases. Of the 26 international-remote comparison records, 25 have explicit listed geography and one Yotta Labs record has contradictory “Remote (Global)” versus listed-location evidence; it remains a contradiction control but is excluded from the 25-record explicit-geography target count.
- Verified the 82-row audit CSV has 27 columns, no malformed rows, no duplicate listing IDs, and 73 distinct canonical URLs. Status counts: 15 open, 56 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review. New records without explicit current availability evidence remain unknown; CertiK is marked open only because the employer page explicitly says applications are accepted on an ongoing basis. A duplicate Azul observation was merged into INT-006 rather than counted as another vacancy.
- No source API endpoint was queried; no source integration, dependency, candidate-data transfer, or application submission was performed. Permission for automated extraction/caching/autofill/submission remains unverified; research/source-quality and implementation gates remain closed.


### 2026-10-14 — sixth continuation: explicit-geography remote comparison target completed
- Added INT-035–INT-039 from official employer-hosted pages: Cohere Software Engineer Intern (Winter 2027; listed countries Canada/Dubai/London/UK/US), Wealth.com Applied Scientist AI/ML Intern (Remote US), Angi AI Enablement Intern (Remote US; AI adoption rather than core model building), Yotta Labs Research Engineer Intern (location header lists US/Canada/Hong Kong/Singapore but body says Remote Global; retained as contradictory-geography control, not counted toward explicit-geography target), and Higharc PhD Research Intern (Remote US). Added INT-040, 1Password Developer Intern (Fall 2026, Remote US/Canada), as a freshness control.
- The independent-employer sample report now records 67 unique role-like canonical URLs: 38 India-focused records including controls, 26 non-India remote comparison records including controls, and 3 other location/work-mode cases. Of the 26 remote-comparison records, 25 have explicit listed country/region evidence and one has contradictory geography, so the 25-record explicit-geography comparison target is met for research purposes. This does not mean 25 roles are open or eligible to an India-based undergraduate.
- Refreshed the source-validation test suite baseline on 2026-10-14: 82 data rows, 27 columns, no malformed rows, no duplicate IDs, 73 distinct canonical URL values; status counts 15 open, 56 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review; 8 repeated canonical URL groups remain for provenance/duplicate handling.
- Source-quality gate remains closed. Current status/freshness and full eligibility still need a systematic recheck, source permission must be established separately, and measured gate metrics (valid/relevant listings, direct-link rate, zero false worldwide claims, no permission/attribution blockers) have not yet been demonstrated. No API endpoint was queried, no connector/dependency was added, no candidate data was transferred, and no application was submitted.


### 2026-10-14 — record-level source-quality gate assessment
- Added [Source-Quality Gate Assessment](research/source-quality-gate-assessment-2026-10-14.md) with explicit PASS/FAIL/UNMEASURED decisions and a bounded 13-URL browser spot check.
- Re-parsed the current audit CSV: 82 rows, 27 columns, zero malformed-width rows, zero duplicate IDs; status counts remain 15 open, 56 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review; 73 distinct canonical URL values and 8 repeated-URL groups. Permission-status field has 77 unknown rows; the other five remain documented-read/feed/third-party statuses with product approval or terms review unresolved.
- Confirmed the 25-record explicit-geography international-remote comparison target is met as a research control sample only. It does not mean 25 open jobs or 25 India-eligible jobs.
- Browser spot check opened 13 canonical URLs: 9 returned readable role content, 3 returned a JS shell/no readable content (Ema, CertifyOS, Airbus), and one produced an internal research-browser error (Azul). This is a readability observation, not a definitive HTTP link-validity rate; the ≥90% link gate remains unmeasured.
- Decision remains **NOT PASSED / research-only**: the ≥20 valid relevant listing threshold is not demonstrated, source permission is unresolved, and the full claim-level worldwide-eligibility audit is incomplete. Added SV-044 for gate metric denominators/evidence tiers.
- No API endpoint was queried; no code/dependencies/connectors, candidate-data transfer, autofill, or application submission was performed. Next work: re-review the India/explicit-worldwide candidate-relevant subset record-by-record, with freshness, eligibility, status, direct route, and source terms independently evidenced before any implementation.


### 2026-10-14 — conservative canonical-status correction
- After opening 13 canonical URLs, downgraded five records from `open` to `unknown`: IN-002 Drivetrain and IN-022 Sprinto had readable role pages and Apply routes but no explicit current-open wording; IN-003 Ema and duplicate/source-comparison row INT-008 returned only a JavaScript shell; IN-025 Airbus returned no readable canonical page lines. Updated their last-checked dates to 2026-10-14 and documented the evidence limitations in the CSV.
- Revalidated CSV integrity: 82 rows, 27 columns, 0 malformed rows, 0 duplicate IDs. Updated status counts: 10 open, 61 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review; 73 distinct canonical URL values and 8 repeated-URL groups. Permission status remains 77 unknown with the other five still requiring product approval/terms review.
- Refreshed the gate assessment and validation-suite baseline. The gate remains NOT PASSED; the 25-record international explicit-geography comparison is a research control target, not a list of 25 confirmed-open or India-eligible jobs.


### 2026-10-14 — follow-up candidate-relevant record review
- Added [Candidate-Relevant Record Review](research/candidate-relevant-record-review-2026-10-14.md), covering current official-page evidence for Trackmind, RadialBrain, Inferova, WATER, Threxil AI Intern, Threxil Frontend + AI Intern, MailerMen ML Intern, QovaTech, Drivetrain, Ema, and Airbus.
- Updated the audit CSV after rechecking eight prioritized records. Trackmind was downgraded from open to unknown because its page conflicts (“Internship” heading vs “Full-Time” work details and a 6-month–2-year experience requirement). RadialBrain, Inferova and WATER remain unknown because forms/page content do not explicitly confirm current availability. Threxil's official careers page explicitly lists two open roles and work from anywhere; MailerMen says “Actively hiring” and “Open to applicants anywhere”; QovaTech says “Open internship” but applicant-country eligibility remains unknown.
- Latest CSV integrity: 82 records, 27 columns, 0 malformed rows, 0 duplicate IDs; status counts open 9, unknown 62, expired 3, closed 2, not_a_listing 2, source_review 4. Permission status remains unknown on 77 records.
- Added SV-045 to the validation suite: current availability and applicant-country eligibility must be supported by separate explicit evidence; Apply-form presence and “serving clients worldwide” are not sufficient.
- Refreshed the gate assessment. Gate remains **NOT PASSED / research-only**: ≥20 valid/relevant listings not demonstrated; ≥90% direct-link validity unmeasured; complete worldwide-eligibility audit and source permission unresolved. No API endpoint queried, no code/dependencies/connectors added, no candidate data transferred, and no application submitted.


### 2026-10-14 — Second India-focused employer-page recheck
- Rechecked ATRISI, Zyora Labs, Hajana Technologies, CertifyOS, Onelogica, Walmart Global Tech India and Bruker against current official pages/search-indexed canonical content. Updated CSV records IN-020, IN-028, IN-016, IN-017, IN-019, IN-013 and IN-035; all selected records now have last_checked_at 2026-10-14.
- ATRISI careers index explicitly marks ML / AI Intern Open; IN-020 and duplicate observation IN-028 now have status open, but IN-028 is excluded from unique-vacancy counts. Role details, compensation, duration and privacy terms remain incomplete.
- Zyora Labs official page explicitly labels the student internship section “Open internships”; IN-016 Research Intern and IN-017 Project Intern status updated to open. They share one general careers page; do not count them as distinct confirmed requisitions without employer confirmation. Onboarding page presents broad confidentiality and work-product ownership terms; candidate review is needed before agreeing. Source/product permission remains unknown.
- Hajana remains unknown: page specifies remote, 9 PM–6 AM IST, CSE/AI/ML degree, and 2025/2026 pass-outs, but the careers index does not explicitly confirm current-open status. Form asks for Father/Husband Name; no autofill/submission without explicit candidate review.
- CertifyOS remains unknown: canonical role content describes a remote, Pune-based, six-month ML engineering internship but retrieved evidence is stale-indexed and lacks explicit current-open wording; INT-014 is a duplicate control. Walmart remains unknown: recent official result lists a Bengaluru Gen AIML Engineering Intern and Apply, but full requirements and explicit current availability need confirmation. Onelogica remains unknown because the saved row title conflates a current internship entry with a distinct full-time GenAI Platforms role. Bruker AI/ML apprenticeship remains unknown; posted date/qualification wording need direct current confirmation.
- CSV integrity after recheck: 82 records, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URLs, 8 repeated URL groups. Status counts: 13 open, 58 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review. Permission field remains unknown for 77 records. Open labels are mixed audit rows, not unique candidate-ready vacancies.
- Gate remains NOT PASSED / research-only. ≥20 unique relevant currently available listings not demonstrated; ≥90% direct-link validity unmeasured; full worldwide eligibility and source terms remain unresolved. No source API queried, code/dependencies/connectors added, candidate data transferred, or application submitted.


### 2026-10-14 — Bruker record timestamp correction
- Updated IN-033 (Bruker Graduate Apprenticeship Trainee - AI/ML) after direct official iCIMS page recheck: Bengaluru, Intern/Apprentice, requisition 2026-19820, posted date 2026-09-10, recent bachelor's in Computer Science & Allied Courses. Status remains unknown because current-open wording, ECE-as-allied eligibility, deadline and apprenticeship details were not fully confirmed. Permission remains unknown.
- CSV was re-fetched after update and will be integrity-checked before reporting completion; status counts should be unchanged.


### 2026-10-14 — Third India-focused employer-page recheck
- Rechecked General Motors, Meraki Labs, Sarvam, vINe AI, AtkinsRéalis, Needl.ai and Concentric AI against official employer pages. Updated CSV records IN-006, IN-023, IN-024, IN-027, IN-030, IN-031 and IN-032; all last-checked dates are 2026-10-14.
- vINe AI's official careers page explicitly lists ML Engineer Intern under “Open Positions” and Remote AI/ML internships; status updated to open, but application form is a Google Form whose privacy terms were not verified. No candidate data was submitted.
- Needl.ai's official careers page lists AI Engineering Intern among open positions; status updated to open. Role is Bengaluru hybrid (three office days/week), targets recent B.Tech/M.Tech or equivalent CSE/EE/related graduates or 1–2 years experience; monthly stipend mentioned but amount absent. No email/application sent.
- GM's official Workday content identifies JR-202613434, Bengaluru on-site, full-time, 45 hours/week, six months, Python/NumPy/Pandas/ML, and explicitly says no immigration-related sponsorship. ECE not explicit in degree list and current-open evidence not sufficiently fresh/explicit; status remains unknown.
- Meraki Labs and AtkinsRéalis internship-title pages both state Full time employment type; Concentric lists Machine Learning Intern but Job Type Full-time. These role-type contradictions remain unknown. Meraki's academic/institution bar is highly selective; Atkins' named degree list does not explicitly include ECE.
- Sarvam role is technically relevant (speech data pipeline, Python, audio/video, ML inference) but current indexed evidence was crawled about four months ago, so remains unknown/stale lead.
- CSV integrity after edits: 82 records, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URLs, 8 repeated URL groups. Status counts: 15 open, 56 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review. Permission field remains unknown for 77 records.
- Added SV-047 to validate intern-title versus employment-type consistency and prevent inferred degree equivalence. Gate remains NOT PASSED / research-only; no source API queried, code/dependencies/connectors added, candidate data transferred, autofill or application submission performed.


### 2026-10-14 — sixth candidate-focused source review and count correction
- Current official employer pages rechecked: Sprinto lists AI Implementation Intern (Bengaluru / remote); Drivetrain lists India-based remote Engineering Intern – Gen AI; Needl.ai lists Bengaluru hybrid AI Engineering Intern and says it targets recent graduates with B.Tech/M.Tech or equivalent in CSE/EE/related or 1–2 years' experience; Threxil explicitly lists two open roles and says fully remote/work from anywhere.
- CSV records IN-002 (Drivetrain) and IN-022 (Sprinto) were updated to `open` in separate commits; both rows still have source/product permission unknown and candidate degree fit caveats. Existing IN-031 Needl.ai and INT-021/INT-022 Threxil roles remain open based on current official pages. “Work from anywhere” is not proof of legal hiring-country/work authorization or source permission.
- Added the sixth candidate-focused recheck to `research/candidate-relevant-record-review-2026-10-14.md`, candidate-fit/permission notes to `research/source-quality-gate-assessment-2026-10-14.md`, and SV-050 on separating remote marketing wording from country eligibility in `research/source-validation-test-suite-2026-10-13.md`.
- Latest CSV SHA before this pass: `c73238877a552f6b405caed3d800c7c7b646443c`; integrity check: 82 rows, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URL values, 8 repeated-URL groups. Statuses: 19 open, 52 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review. Permission remains unknown for 77 rows. The 19 open-labelled rows include duplicate/shared-page observations and are not 19 unique candidate-ready jobs.
- Candidate triage: Threxil AI Intern and Sprinto AI Implementation Intern merit careful manual review; HCF is a potential paid India-remote internship lead but exact stipend/eligibility are unclear. Drivetrain and Needl.ai need explicit confirmation of ECE/current-student eligibility. EduRankAI via AICTE is listed as full-time, three months, ₹0/month and needs legitimacy/workload review.
- Gate remains **NOT PASSED / research-only**. No source API queried, no production code/dependencies/connectors added, no candidate data sent, and no application submitted.


### 2026-10-14 — source-permission decision matrix / next implementation gate
- Added `research/source-permission-decision-matrix-2026-10-14.md` after reviewing current official terms for Jobicy, Remotive and AI Dev Jobs. Jobicy public Remote Jobs API is the strongest initial read-only adapter candidate because official docs explicitly permit normal product use without individual permission when Jobicy is credited and its canonical listing URL is retained. Public endpoint is free/no key and returns the Jobicy listing URL, not necessarily the employer ATS URL. Optional commercial direct-link endpoint may cost $0.01 per eligible job and requires a wallet; excluded from the no-mandatory-cost MVP absent explicit approval. Feed contains listings from the last 7 days; absence is not proof of closure; polling must not exceed hourly and a few checks/day are recommended.
- Remotive remains conditional: 24-hour delay, source attribution/linking, and no gating listing display behind sign-up/email capture. AI Dev Jobs remains conditional pending clarification of attribution, caching and product display. Himalayas remains blocked pending terms clarification. JobSpy rejected because proxy-based anti-blocking guidance conflicts with the non-evasion rule. Public employer pages are for manual evidence unless source-specific terms authorize intended automated use.
- Updated `research/source-quality-gate-assessment-2026-10-14.md` with source-permission decisions and added SV-051 to `research/source-validation-test-suite-2026-10-13.md` to separate source listing URLs from employer application URLs and prevent treating the Jobicy public URL as a verified direct ATS link.
- Latest audit CSV remains 82 rows × 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URL values, 8 repeated URL groups; statuses 19 open, 52 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review; permission unknown for 77 records. These are audit observations, not unique candidate-ready jobs.
- Gate remains **NOT PASSED / research-only**. This pass reviewed terms but did not query a source endpoint. No source connector, production code, dependency, candidate-data transfer, autofill or application submission was performed. Next decision: finalize candidate-facing flow and data fields, then explicitly authorize or reject a read-only Jobicy adapter under the matrix conditions.


### 2026-10-14 — MVP scope/data contract drafted
- Added `research/mvp-scope-and-data-contract-2026-10-14.md`. It defines a local-first candidate profile and application tracker; job listing provenance; distinct `source_listing_url` vs nullable verified `employer_apply_url`; three-valued hard eligibility (`pass`/`fail`/`unknown`); status semantics; no resume upload/cloud sync/paid API/scraping/autofill/submission in the initial prototype; and acceptance tests for coverage, direct-link reliability, eligibility claims, deduplication, attribution and local privacy.
- Added source-permission matrix `research/source-permission-decision-matrix-2026-10-14.md`: Jobicy public Remote Jobs API is leading candidate for one read-only adapter under explicit attribution/canonical URL/rate-limit/cache rules. Its public endpoint does not guarantee employer ATS links; optional commercial direct-link access may cost $0.01 per eligible job and remains out of scope absent explicit approval. Remotive is conditional, AI Dev Jobs needs clarification, Himalayas blocked pending terms clarification, JobSpy rejected.
- Added SV-051 to the source validation suite to ensure a source-listing URL is never counted as a verified employer application URL. Updated the source-quality gate assessment with both new design artifacts.
- Current CSV snapshot is unchanged: 82 records, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URLs; statuses 19 open, 52 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review; 77 records have unknown permission. Open-labelled rows are not necessarily unique/eligible vacancies.
- The source-quality gate remains **NOT PASSED / research-only**. Next go/no-go requirements: approve MVP flow/data contract, complete 50-record sample (25 India-focused + 25 international-remote), measure direct-employer link outcomes with a defined denominator, audit unsupported eligibility claims, and confirm exact permissions for each adapter. Then explicitly authorize one read-only Jobicy public API adapter. No source endpoint queried, no production code/connector/dependency added, no candidate data transferred, no autofill or application submitted.


### 2026-10-14 — consolidated batch research pass
- Added [Batch Research Pass](research/batch-research-pass-2026-10-14.md) to record one consolidated public-web review and explicitly preserve the NOT PASSED gate.
- Added CSV audit record IN-036 for Valura.AI AI Engineering Intern (Python), conservatively marked `unknown`: official page shows a 2026-07-27 post date, Chennai/GIFT City/Remote, 3–6 months with full-time preferred, 0–3 years, and relevant agents/RAG/evaluation work; current-open wording, degree eligibility and applicant-country/work authorization remain unresolved.
- Rechecked RadialBrain: remote across India and internship for current students, but no explicit current-open wording captured. Rechecked Unisys as a negative fit for the BTech ECE undergraduate because its role asks for current/recent M.Tech candidates.
- Added a Jobicy-hosted Spotify CoLM listing as a geography/posting-type negative control (UK/USA/Sweden and conference-specific); excluded a Flocci search result whose displayed deadline was 2026-09-30 absent evidence of reopening.
- Reconciled current CSV to 83 rows × 27 columns, 0 malformed rows, 0 duplicate IDs, 74 distinct canonical URLs, 8 repeated URL groups; statuses 19 open, 53 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review; permission unknown for 78 records. These are not unique candidate-ready vacancies.
- Jobicy remains the leading candidate for a later read-only adapter under attribution/canonical URL/rate-limit conditions. No source API endpoint was queried; no production code, connector, dependency, candidate-data transfer, autofill or application submission occurred.
- Gate remains **NOT PASSED / research-only**. The 50-record validation sample is not complete, direct-link reliability is unmeasured with a defined response-outcome denominator, and ≥20 unique relevant currently available vacancies are not demonstrated.


### 2026-10-14 — fixed 50-record QA roster and destination probes
- Added [50-Record Candidate-Validation Roster](research/50-record-candidate-validation-roster-2026-10-14.md), with 25 India-focused and 25 international-remote records, one canonical URL per row, explicit controls, and browser probe outcomes. The roster is reproducible but does not claim 50 open or eligible jobs.
- Rechecked 50 canonical URLs in the research browser. Apple IN-001 explicitly says the role does not exist/no longer available and is now closed; Matrice AI IN-007 returns 404 / Job Not Found and remains expired; Bruker IN-033 returned HTTP 410 Gone and is now closed; AtkinsRéalis IN-030 redirects to generic job search rather than the role and remains unknown; Azul INT-032 fetch failed without HTTP status and remains unknown.
- Updated the CSV last-checked date for sampled rows and added evidence notes for unavailable/deep-link outcomes. Latest CSV: 83 records, 27 columns, 0 malformed rows, 0 duplicate IDs, 74 distinct canonical URLs, 8 repeated URL groups; statuses 19 open, 51 unknown, 3 expired, 4 closed, 2 not_a_listing, 4 source_review; permission unknown for 78 rows.
- Added SV-052 for stale requisitions, HTTP 410, and generic-search redirects. A browser page rendering or shell is not proof the Apply action works; a research-browser fetch error without status is not proof of closure.
- Roster construction is complete, but full validation is not: the ≥90% direct-employer application-link metric remains unmeasured with a defensible denominator; ≥20 unique relevant currently available vacancies remain unproven; source permissions remain unresolved for most records. Gate stays **NOT PASSED / research-only**.
- No source API endpoint queried; no production code, dependency or connector added; no candidate data transferred; no autofill or application submitted.


## 2026-10-14 — Application-route spot-check update

- Re-fetched the current validation roster, audit CSV, validation test suite, candidate review, gate assessment, and memory before edits.
- Tested ten application paths from official employer pages. Four matching Lever application forms rendered (Drivetrain, Trackmind, Sprinto, CertiK); HCF reached a sign-in gate; Zyora displayed an embedded form; Needl.ai published an email route not tested; RadialBrain, Valura.AI, and MailerMen remained unknown due to browser/tool limitations.
- Added three audit columns: apply_route_outcome, apply_route_checked_at, and apply_route_evidence; updated apply_url where an actual destination was observed. Canonical listing URLs remain separate.
- This was a focused convenience sample, not representative validation. No link-validity percentage is claimed; the 50-record ≥90% direct-employer-link gate remains unproven.
- No forms submitted, resume uploaded, candidate data entered/transmitted, or email sent. No source permission inferred from a reachable page.
- Source-quality gate remains NOT PASSED / research-only. No production implementation or dependencies added.

### 2026-10-14 — Local persistence and continuous verification
- Added `career_agent/store.py`, a standard-library SQLite repository for a candidate profile, normalized job records, first/last-seen timestamps, conservative duplicate groups, and application tracker state. It provides explicit profile/job deletion and cascades tracker deletion with its job.
- Added storage tests and a GitHub Actions workflow for Python 3.10, 3.11, and 3.12. Local verification: `python -m unittest discover -s tests -v` passed all 25 tests; `python -m compileall -q career_agent tests` passed.
- Storage uses an explicitly supplied database path; the package does not create a candidate database or collect candidate data unless the future app calls these methods. No live source adapter or UI exists yet.


### 2026-10-14 — Review of multica-ai/andrej-karpathy-skills
- Reviewed the upstream README, SKILL.md, CLAUDE.md, CURSOR.md, EXAMPLES.md, Cursor rule and Claude plugin metadata at https://github.com/multica-ai/andrej-karpathy-skills (main tree inspected on 2026-10-14; skill file SHA `6a62d0441753157ca6ca50479e490c2948033adb`).
- The repository packages one behavioral skill around four principles: think before coding, simplicity first, surgical changes, and goal-driven execution/verification.
- Adopted an original, project-specific adaptation in [development-workflow.md](development-workflow.md): surface consequential assumptions, choose the smallest complete solution, keep diffs surgical, define observable acceptance criteria, run tests/checks, inspect and re-fetch the resulting GitHub state, and report verification honestly.
- Kept project-specific constraints authoritative. In particular, these principles do not re-close development after the user's decision to build the offline core; nor do they waive source permission, privacy, candidate truth, eligibility, cost, or application-integrity requirements.
- Did not copy the upstream entire EXAMPLES.md, Claude plugin manifests, or Cursor plugin rule into the product repository. They are environment-specific or duplicative; our existing workflow now carries the relevant concepts without installing a toolchain or adding dependencies.
- Upstream README identifies MIT license. This pass adapted principles in original wording rather than copying substantial source text or adding upstream code. No software dependencies, source connectors, or product runtime files were added in this reference-review pass.


### 2026-10-14 — Production product and cross-industry scope confirmed
- User explicitly confirmed the product must be usable for real job and internship applications, not stop at a prototype or hackathon demo. Treat this as a production-oriented software project with real installation, reliability, privacy, security, recovery, and maintenance requirements.
- Long-term product scope is all professions and job profiles, including but not limited to graphic design/creative, VLSI and embedded systems, mechanical, civil, software/data, business, finance, marketing, sales, operations, and research. Architecture must use a shared industry-agnostic core plus extensible occupation-specific knowledge; these examples are not a claim that every occupation is supported in the first release.
- Intended default search schedule is 00:00 and 12:00 Asia/Kolkata. Laptop-off operation requires a real always-on worker and must be tested; do not infer this capability from local scheduling or free-tier marketing.
- User wants maximum autonomy after setup. Use scoped, revocable standing authorization for routine permitted actions rather than prompting for every job; keep platform terms, employer instructions, truthful answers, sensitive declarations, unsupported steps, and ambiguous submissions as hard boundaries.
- Product success is real-world usefulness and improved job-search outcomes, not application volume alone. Selection cannot be guaranteed. Require evidence-backed capabilities, representative cross-industry evaluation, integration/pilot tests, and honest release claims.
- Updated the six canonical documents (`prd.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`, `memory.md`) to align the production product commitment, cross-industry scope, remote-worker requirement, and evidence-gated automation. Existing source-quality gate remains NOT PASSED; this documentation change does not authorize a live source adapter or submission workflow.


### 2026-10-14 — Local desktop alpha and contract reconciliation
- Added a Python/Tkinter local desktop workflow launched with `python -m career_agent`, backed by the existing SQLite store. It supports manual profile entry, manual job entry, eligibility review, PASS-only shortlisting, guarded tracker updates, local JSON export and explicit deletion. It performs no network requests and does not submit applications.
- Resolved the former MVP contradiction: resume parsing is deferred to a follow-on local-only increment; the first complete workflow uses manually entered/reviewed profile facts and job records. Long-term scope remains cross-industry, while source discovery and remote execution stay gated.
- Added an explicit optional `allowed_work_authorizations` field to job records. If a role states allowed work-authorization values, evaluation requires exact matching; missing or mismatched values cannot pass. Country eligibility remains a separate check.
- Added a reproducible CSV integrity summary tool with input SHA-256, malformed-row/duplicate checks, canonical URL groups, status/permission counts and apply-route outcomes. It deliberately leaves direct-link validity percentage unmeasured because the current outcomes do not support a defensible common denominator.
- Added tests for work-authorization eligibility and CSV audit behavior; CI now runs unit tests, Python syntax compilation, and the audit utility on Python 3.10–3.12. GUI smoke tests are still required before calling this release-ready. GitHub Actions PR verification passed on Python 3.10, 3.11 and 3.12 (unit tests, compileall, and source CSV audit); PR #1 was merged after all matrix jobs succeeded.
- Source-quality gate remains **NOT PASSED**. No source connector, external candidate-data transfer, autofill, email action or application submission was enabled.


### 2026-10-14 — CI verification completed
- GitHub Actions run 38463995269 for PR #1 passed all three Python matrix jobs (3.10, 3.11, 3.12). Each job completed the standard-library unit tests, `python -m compileall -q career_agent scripts tests`, and `python scripts/audit_job_source_csv.py` successfully.
- Added a backward-compatibility regression test confirming previously persisted job payloads without `allowed_work_authorizations` still decode using the dataclass default. PR #1 was squash-merged to `main` as `ab6586680b4ef1930205e861c08a06f738ced3b5`.
- CI success does not replace the manual GUI smoke-test checklist, cross-platform packaging tests, or the still-closed live source permission/quality gate.
- The CI audit emitted the current CSV snapshot (SHA-256 `0356b093ded3917c0fa9ba3aa9f12a682caaf81df7c49a6b042950d66a08f414`): 83 rows, 30 columns, 0 malformed-width rows, 0 duplicate IDs, 74 distinct canonical employer URLs, 8 repeated-URL groups; statuses 19 open, 51 unknown, 3 expired, 4 closed, 2 not-a-listing, 4 source-review; 78 permission-unknown rows. The JSON snapshot is committed in `research/job-source-audit-summary-2026-10-14.json`. Direct-link validity remains unmeasured; the source gate remains NOT PASSED.


### 2026-10-14 — Phase 1.1 scoped bug fixes and regression tests
- Fixed the audit's confirmed defects on the Arena task branch only; no source adapter, resume parser, scheduler, packaging, or submission work was started, and the source-quality gate remains **NOT PASSED**.
- **Eligibility normalization (H3):** `_check_membership` now normalizes label-like values on both sides (case and surrounding whitespace) for degree discipline and study status, and treats work-authorization values case-insensitively while also treating underscores like spaces. Genuinely different values still fail, missing or blank values still return UNKNOWN, and no fuzzy or semantic matching was added. This removes false hard-FAILs caused only by capitalization (for example `undergraduate` versus `Undergraduate`).
- **Job identity (M1):** job entry now has an explicit mode. **New job** always allocates a fresh listing id and therefore can never overwrite the selected listing; selecting a saved listing switches to **Edit**, preserves that listing's identity, and asks for confirmation when an eligibility-relevant field changes (availability, scope, countries, disciplines, study statuses, graduation years, work authorizations, experience bounds, URLs, requisition id, or the availability note). Non-consequential edits save without a prompt. The duplicate-URL observation prompt is unchanged for new listings.
- **Database errors (M2):** `_save_job`, `_save_profile`, `_shortlist`, `_update_status`, `_delete_job`, and `_delete_profile` now catch `sqlite3.Error`, show an actionable message stating that nothing changed, and never set a success status. A failed write leaves previous data intact (verified with a closed connection and with a simulated read-only database).
- **Tracker no-op and evidence (M3):** a transition that does not change the status returns the tracker unchanged; the dialog now reports "No change … nothing was saved" instead of an update, so supplied text is neither stored nor silently discarded. Evidence is revised by moving the status forward with a meaningful note; the evidence requirement for `confirmed` is unchanged and still enforced in the dialog and in the store.
- **Store invariants (M4):** `CareerStore.save_tracker` refuses a confirmed record without evidence and refuses status changes the domain state machine does not permit (re-applying the current status stays an idempotent no-op, so sequential valid use is unaffected). No schema change, no migration, and no existing row is rewritten.
- **Validation and durability (M7/L3):** graduation-year parsing goes through the shared `validation.optional_int` helper, so users see "Graduation year must be a whole number." instead of a raw Python `invalid literal for int()` message. Tests now cover file-backed close-and-reopen persistence, deletion persistence, newer-schema refusal, per-OS database-path resolution, and `sqlite3.Error` surfaces without asserting platform-specific exception text.
- **Testable desktop logic (H2/§8):** new Tk-free module `career_agent/desktop_logic.py` holds form mapping, save planning, and database-path resolution; `desktop.py` is now only widget wiring plus error handling, and no domain rule is duplicated. Tests were added in `tests/test_desktop_logic.py`, `tests/test_desktop_handlers.py` (real handlers and the window-construction path over stub widgets and real SQLite files), `tests/test_core.py`, and `tests/test_store.py`.
- Local verification: `python -m unittest discover -s tests -v` → **103 tests, OK** (was 36); `python -m compileall -q career_agent scripts tests` → exit 0; `python scripts/audit_job_source_csv.py` → unchanged SHA-256 `0356b093…f414`. Added `.gitignore` for bytecode, caches, virtual environments, local databases/exports, and OS noise; verified no tracked file becomes ignored.
- **Remaining limitations:** GUI rendering, a real Tk session, restart behavior of the running app, and macOS/Apple Silicon behavior are still unverified — Tkinter is unavailable and there is no display in the verification environment, and nothing was installed to work around that. The manual smoke-test checklist in `research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` still has to be executed on a real desktop before GUI or cross-platform acceptance is claimed.


### 2026-10-14 — Phase 1.1.1 tracker initial-state validation gap closed
- Closed the gap reported after Phase 1.1: `CareerStore.save_tracker` skipped transition validation whenever no tracker row existed, so a caller could persist an arbitrary first status (for example `interview`) without following the permitted state transitions.
- The domain now names its starting point explicitly: `core.INITIAL_APPLICATION_STATUS` is `discovered`. Creating a tracker record is only accepted at that status, with `candidate_confirmed` false; an initial `confirmed`, `shortlisted`, `submitted_unverified`, or `interview` record is refused and nothing is written.
- Later writes keep every existing rule (permitted transition or idempotent re-save, non-empty evidence for `confirmed`) and add one: `candidate_confirmed` is only ever *earned*. It may be true only when the stored row already carried it or when the write is the transition to `confirmed`, so a later status can keep or drop a real confirmation but cannot invent one. The reverse case (`confirmed` with the flag false) is deliberately still accepted; the store never adds a confirmation claim on its own, and enforcing the opposite direction could refuse a caller that records confirmation evidence without asserting candidate confirmation.
- No schema change and no migration: enforcement is entirely in the write path, and existing rows are never rewritten. Two tests seed a database with rows of the shape an earlier build could have produced (`shortlisted` as the first record, and a legacy `confirmed` row) and confirm they remain readable, can still advance along permitted transitions, and keep their confirmation flag.
- Two UI paths that can meet a job with no tracker row were updated so the stricter rule cannot break them: `_shortlist` and the status dialog now create the permitted initial `discovered` record before advancing it.
- Local verification: `python -m unittest discover -s tests -v` → **113 tests, OK** (was 103); `python -m compileall -q career_agent scripts tests` → exit 0; `python scripts/audit_job_source_csv.py` → unchanged SHA-256 `0356b093…f414`. New direct storage tests cover invalid initial states, the valid initial state, invalid subsequent transitions, confirmation without evidence, and contradictory confirmation flags.
- Still unverified and unchanged by this fix: GUI rendering, a real Tk session, and macOS/Apple Silicon behavior (Tkinter is unavailable and there is no display in the verification environment); the manual smoke-test checklist remains outstanding. Source-quality gate remains **NOT PASSED**; no adapter, scheduler, submission, packaging, or external service was enabled.


### 2026-10-14 — Phase 1.1.2 refused status changes no longer mutate data
- Fixed the review finding on PR #2: `_update_status` created the permitted initial `discovered` record *before* the domain transition validated the request, so a refused jump (for example a first action of `interview`, `prepared`, or `confirmed`) left a `discovered` row persisted even though the dialog reported an error. Reproduced against a real file-backed database before the fix: three refused scenarios each persisted a `discovered` row that survived close-and-reopen.
- Fix is confined to the handler: the requested action is now validated through `ApplicationTracker.transition` **before any persistent write**. Only a valid action creates a record (at the permitted initial status) and, when the action also moves the status, applies the transition afterwards. Invalid selections, refused first actions, invalid jumps on existing records, and the invalid-`confirmed`-without-evidence case now leave the database completely untouched.
- Preserved behavior: a valid first action of `discovered` creates the record and reports "Application record created at discovered."; `shortlisted` or `withdrawn` from an empty record create the initial record and then advance it; an existing record still follows `is_allowed_tracker_transition`; `confirmed` still requires non-empty evidence; a repeated status still reports "No change … nothing was saved" without altering stored evidence; store-level invariant enforcement is unchanged and was not weakened to make the UI pass.
- Honest limitation, now covered by an explicit test rather than an atomicity claim: creating and advancing a new record is two writes, not one transaction. If the second write fails, the handler reports "Status not saved" and the database holds the truthful `discovered` row. The test asserts exactly that (it demonstrates the behavior; it does not claim atomicity).
- Local verification: `python -m unittest discover -s tests -v` → **119 tests, OK** (was 113); `python -m compileall -q career_agent scripts tests` → exit 0; `python scripts/audit_job_source_csv.py` → exit 0 with the unchanged CSV SHA-256 `0356b093…f414`; the network-blocked suite (connect/getaddrinfo/bind denied) → 119 tests OK; three consecutive full-suite runs OK.
- Still unverified and unchanged by this fix: desktop GUI rendering, a real Tk session, and macOS/Apple Silicon behavior — Tkinter is unavailable and there is no display in the verification environment, and nothing was installed to work around that. The manual smoke-test checklist remains outstanding. Source-quality gate remains **NOT PASSED**; no adapter, scheduler, submission, packaging, or external service was enabled.

### 2026-10-14 — Agent-Reach reuse review and selective hardening
- Reviewed `https://github.com/Panniantong/Agent-Reach` at commit `94f06c1969dfc1834001269d79d3ad0972d9dee6` (MIT, "Copyright (c) 2025 Agent Eyes") by reading its source directly, not its README. Full decision table, reasons, and the list of rejected/deferred parts: [Agent-Reach reuse review](research/agent-reach-reuse-review-2026-10-14.md).
- **Rejected outright:** cookie export, browser-session bridges, MCP servers, social/authenticated scrapers, third-party reader proxying, paid search backends, proxy or stealth access, auto-installation of external tools, and any automatic retry of a non-idempotent action. Upstream's own documentation warns of platform-ban risk for cookie-based access, which reinforces the existing prohibition.
- **Implemented (all standard-library, no new dependencies):**
  - `career_agent/urls.py` — public HTTP(S) URL validation for manually entered links (scheme allow-list; refuses credentials, malformed or out-of-range authorities, control characters/backslashes, localhost and internal names, single-label hosts, non-global IPv4/IPv6 literals, and legacy IPv4 spellings such as `127.1`, `2130706433`, `0x7f.0.0.1`), plus `redact_url_credentials` for display. Wired into manual job entry via `desktop_logic._require_http_url`. Concept adapted from upstream `utils/url.py` and `utils/text.py`; attribution is in the module docstring.
  - `career_agent/sources.py` — the source permission gate as data (`SourceDecision`, `PermissionState`, per-source evidence reference, review date, discovery conditions, separate submission evidence) plus fail-closed `discovery_gate`/`submission_gate`. `SOURCE_QUALITY_GATE_PASSED` is `False` and `enabled_discovery_sources()` is empty; an unregistered source is refused, submission is refused wherever read access is approved, and a decision cannot be constructed without reasoning, evidence, and an ISO review date. `RunOutcome` keeps a run's outcome distinct from a listing's availability, distinguishes a legitimate empty result from permission-denied/rate-limited/auth-required/timeout/network/schema/challenge/partial outcomes, and marks only rate-limit, timeout, and network errors as retryable.
  - Display safety and file privacy: the selected-job report pane redacts credentials in older rows without rewriting them (the edit form keeps the stored value so the candidate can correct it), and `CareerStore` sets the local SQLite file to owner-only (`0600`) where the platform supports it, best-effort and non-fatal.
- **Deferred with stated triggers** (not implemented, because there is nothing to apply them to yet): host/domain allow-list matching, per-adapter health isolation and run orchestration, response-size caps, timeouts and challenge-page detection for a future fetcher, RSS parsing, host-tool health probing, and directory/symlink-safe config writes. See the review's decision table for each trigger.
- **Honest limitation recorded in code, docs, and tests:** `urls.py` inspects the literal host only. It performs no DNS resolution and follows no redirects, so it is **not** SSRF protection; a passing host can still resolve to a private address or redirect anywhere. Any future fetcher must resolve and connect consistently, re-validate every redirect hop, and apply its own size/time limits before any such claim is made.
- Local verification: `python -m unittest discover -s tests -v` → **167 tests, OK** (was 119); `python -m compileall -q career_agent scripts tests` → exit 0; `python scripts/audit_job_source_csv.py` → exit 0 with the unchanged CSV SHA-256 `0356b093…f414`; the network-blocked suite (connect/connect_ex/bind/create_connection/getaddrinfo denied) → 167 tests OK. No network call was added: `urls.py` uses `socket.inet_aton` only for literal parsing.
- Source-quality gate remains **NOT PASSED**. No adapter, connector, scheduler, submission path, or external service was enabled, and no candidate data leaves the machine.

### 2026-10-14 — Tracked smoke-test record diagnosed; confirmation claims now come from the person
- Diagnosed the reported Mac smoke-test state (`Example Test Company` / `AI/ML Intern`, listing `dd559b6c-…`) where a fictional record sat at `confirmed` with `candidate_confirmed = 1` and instructional text as its evidence, although nothing was ever submitted. The Mac database is not reachable from this checkout, so the shape was reproduced deterministically on a throwaway file-backed database through the same code paths the GUI uses. Full write-up and recovery procedure: [tracker confirmation smoke-test diagnosis](research/tracker-confirmation-smoke-test-diagnosis-2026-10-14.md).
- **Root cause 1 — the software made the claim.** `desktop._update_status` set `candidate_confirmed = True` automatically whenever the selected status was `confirmed`, so clicks alone produced a record asserting that the candidate had confirmed a real application. The dialog now requires an explicit assertion checkbox for that status, sets the flag only from that assertion, refuses an assertion used with any other status, and tells a user looking at an already-confirmed record that `withdrawn` with a truthful note is the honest correction.
- **Root cause 2 — no evidence floor.** Any non-empty string was accepted, including this project's own guidance text ("A confirmed application requires evidence. An attempt or timeout is not proof.", "Evidence / note (required to confirm)", the checklist's "Confirm with a meaningful evidence note"). New shared helper `is_substantive_confirmation_evidence` / `require_confirmation_evidence` in `core.py` refuses empty/whitespace, bare placeholders (`todo`, `n/a`, `yes`, …), template markers, and the app's own instruction sentences, and is enforced both by `ApplicationTracker.transition` and by `CareerStore._check_tracker_invariants` so direct storage writes cannot bypass it. It is documented as a narrow floor, not authentication: **free-text evidence cannot be objectively verified and must remain an explicit user assertion** — nothing here claims the app can prove a confirmation happened.
- **Root cause 3 — no honest exit.** From `confirmed` the permitted statuses are `response_received`, `interview`, `rejected_by_employer` and `withdrawn`; the first three would be false claims about an employer. New `scripts/correct_tracker_record.py` performs exactly one correction on exactly one record: dry-run by default (validated on a throwaway copy), a consistent SQLite backup before any write, a mandatory truthful `--reason`, `--clear-confirmation` for a flag that was never earned, one write through `CareerStore` so every invariant still applies, a re-read verification, and non-zero exit without a success claim if verification fails. It refuses to set `confirmed`, to bypass the state machine, or to invent a reason. No reverse transition or new status was added: that would weaken the forward-only audit property and needs its own design decision.
- Reworded smoke-test checklist step 12 so it no longer invites pasting instruction text, and added the assertion/refusal checks and the "use a throwaway database copy" precondition.
- Local verification: `python -m unittest discover -s tests -v` → **192 tests, OK** (was 167; +14 in `tests/test_correct_tracker_record.py`, +5 core, +4 store, +5 handler); `python -m compileall -q career_agent scripts tests` → exit 0; `python scripts/audit_job_source_csv.py` → exit 0 with the unchanged CSV SHA-256 `0356b093…f414`. An end-to-end run of the correction tool against a database reproducing the reported state produced `withdrawn` + `candidate_confirmed = 0` with a truthful reason, left the listing intact, and preserved the original `confirmed` row inside the backup.
- **Not verified and not claimed:** the Mac database was never accessed or modified from here, so the reported local record is still `confirmed` until the documented correction is run on that machine. GUI rendering, a real Tk session, and macOS/Apple Silicon behavior remain unverified (no Tkinter or display in this environment); the manual smoke-test checklist is still outstanding. Source-quality gate remains **NOT PASSED**; no adapter, scheduler, submission path, or external service was enabled.

### 2026-10-14 — Confirmation regression tests completed (stub-verified) after Mac GUI verification
- The user verified on macOS that the updated app renders, that the fictional `Example Test Company` job persists with its tracker at `withdrawn` (truthful evidence, no candidate confirmation), that evaluating it yields `ELIGIBILITY: UNKNOWN`, that "Shortlist if eligible" reports "Eligibility is UNKNOWN. Resolve unknown/failed requirements first.", and that the status dialog shows the evidence field, the instruction/placeholder-rejection hint, and the explicit confirmation assertion checkbox (dismissed without saving, so the withdrawn record is unchanged). **That GUI verification is the user's; it is not reproduced here** — this environment has no Tkinter or display, so the automated tests below exercise the same handlers through widget stubs and disposable databases, which is not a substitute for GUI or macOS testing.
- Added 18 handler/storage/domain regression tests (192 → **210**): empty and whitespace-only evidence refused; the app's own instruction sentences refused; placeholders/templates refused (`n/a`, `todo`, `TBD`, `test`, `yes`, `<your evidence here>`, …); `confirmed` without the explicit assertion refused; the assertion refused with each of the eight other statuses; a full permitted workflow (discovered → shortlisted → prepared → awaiting_user → submission_attempted → submitted_unverified → confirmed → response_received) with the confirmation flag appearing only at the confirmation step and preserved afterwards; `withdrawn` treated as terminal at the domain, storage and handler layers; re-applying `withdrawn` reported as a no-op; and a systematic proof that every refusal category leaves the row on disk byte-identical while `save_tracker` is never called. Also locks the Mac-verified shortlist wording for UNKNOWN/FAIL eligibility without creating a tracker row.
- Evidence the tests actually guard the behavior: four controlled mutations were applied and each was caught — removing the assertion requirement (2 failures), reverting the core evidence floor to the old empty-only check (49 failures), removing the storage-boundary floor (13 failures), and making `withdrawn` non-terminal (13 failures). Every mutated source file was restored byte-identically (SHA-256 verified) and the tree contains only test-file changes.
- Local verification after the additions: `python -m unittest discover -s tests -v` → **210 tests, OK** (twice, stable); `python -m compileall -q career_agent scripts tests` → exit 0; `python -m tabnanny career_agent scripts tests` → exit 0; `python scripts/audit_job_source_csv.py` → exit 0 with the unchanged CSV SHA-256 `0356b093…f414`; the network-blocked suite → 210 OK. **No linter is configured in this repository and none is installed**, so the applicable static checks are compilation and `tabnanny`; nothing was installed to manufacture a lint step. No dependency, adapter, scheduler, submission path, or external transmission was added; the source-quality gate remains **NOT PASSED** and the Mac database was never accessed or modified from here.

### 2026-10-14 — Phase 1 release hardening: export privacy and desktop crash guards
- Worked from [the readiness audit](research/readiness-audit-2026-10-14.md) (committed with this change as the evidence record) and re-verified both reported defects on the current HEAD before changing anything. The user's Mac database was never accessed.
- **A — export privacy.** Reproduced first: a new export was `0644`, a pre-existing `0644` file stayed `0644`, and — not previously reported — a **symlink destination was followed and the linked file was overwritten with exported candidate data**. Fixed with one shared primitive, `store.write_private_text_file`, built on the existing `_OWNER_ONLY_MODE`/owner-only helper (now `_apply_owner_only_mode`, reused by `_restrict_to_owner` for the database so permission logic lives in one place): the file is created with the owner-only mode through the open descriptor **before** any content is written, the mode is re-applied so an existing file is corrected rather than left permissive (`umask` can only remove bits, never add them), a symbolic link is refused both by an explicit pre-check and by `O_NOFOLLOW`, and the result is verified afterwards — a filesystem that silently ignores the mode leaves no readable export (the file is removed where possible). Failure raises `PrivateWriteError` (an `OSError`) with a user-facing message; `_export` reports "Export not saved" and never claims success. The export format, file dialog and workflow are unchanged.
- **B — stale selection.** Reproduced first: `_evaluate` and `_shortlist` each raised `AttributeError: 'NoneType' object has no attribute 'availability_status'` when the selected listing no longer existed in the database. Both now resolve the selection through shared helpers (`_selected_listing_id`, `_loaded_selected_job`, `_report_stale_selection`), report "Listing not found", resynchronise the lists, and return **without creating a tracker record or writing anything**. UNKNOWN and FAIL eligibility still block shortlisting, and only an explicit PASS proceeds — now covered by a positive control test as well.
- Tests: **210 → 243** (+33). New `tests/test_store.py::PrivateFileWriteTests` (real POSIX mode assertions, umask-hostile run, pre-existing `0644`/`0666`/`0777` files, symlink refusal with and without `O_NOFOLLOW`, mode-application failure, ignored-mode filesystem, unwritable destination, missing parent, `OSError` compatibility, unchanged database helper behaviour) and `tests/test_desktop_handlers.py::ExportPrivacyTests` plus `StaleSelectionTests` (export format/workflow, permissive-file tightening, symlink refusal through the real handler, cancel, no-success-on-failure; stale and missing selections for both handlers, no-write proofs with `save_tracker` patched to raise, the UNKNOWN/FAIL blocks, the PASS positive control, delete success/error and refresh/selection sync). Test doubles were corrected to match real Tk (`selection_set` with a bare string, `delete`, the `profile_tab` frames) rather than production code being bent to the doubles.
- Test-teeth check: six controlled mutations were applied and **all six were caught** (plain `write_text`; symlink pre-check disabled; post-write verification disabled; mode applied after writing instead of before; each stale-selection guard removed), with every mutated file restored byte-identically (SHA-256 verified). The first sweep missed one mutation — the symlink pre-check was redundant on POSIX because `O_NOFOLLOW` already refuses — so a test was added for platforms where that flag is unavailable.
- Verification: `python -m unittest discover -s tests -v` → **243 tests, OK** (twice, stable); `python -m compileall -q career_agent scripts tests` → exit 0; `python -m tabnanny career_agent scripts tests` → exit 0; `python scripts/audit_job_source_csv.py` → exit 0 with the unchanged CSV SHA-256 `0356b093…f414`; the network-blocked suite → 243 OK. No dependency, adapter, scheduler, submission path, or external transmission was added; the source-quality gate remains **NOT PASSED**.
- Deliberately **not** done here (separate phases per the audit): backup/restore, packaging/version/error reporting, the status-combobox filtering (H2), freshness display (H3), and the remaining coverage gaps.

## 2026-10-14 (later) — Secure local database backup and restore

Task: "Implement Secure Local Database Backup and Restore" (the audit's B3 release blocker), on PR #2's
branch, without touching the user's real Mac database, without new dependencies, and with PR #2 left
open and unmerged.

**Hazards measured before choosing an implementation** (disposable temp databases only; probes kept
under `/tmp`):

- A plain file copy of a *live* database is not a backup: with a WAL-format database the committed rows
  live in the `-wal` sidecar, and the copy failed with `no such table: candidate_profile`; it also
  inherited the umask (`0o644`) and silently destroyed an older backup; a copy onto a symbolic link
  followed the link and overwrote the target file.
- Replacing only the main file while a stale `-wal` remained beside it **silently discarded the restored
  data** — after the "restore", reads returned the old data from the replayed WAL. This is why a restore
  removes side files and why it reopens and verifies what is on disk.
- `sqlite3.Connection.backup()` **blocks indefinitely** when the source connection has an open
  transaction (measured: still blocked after 45 s), and its `progress` callback returning truthy does
  **not** abort the retry loop (480 calls over 25 s). A pre-flight exclusive-lock check is therefore the
  thing that turns the common "another connection holds the database" case into a refusal with a message
  instead of an apparent freeze; the unbounded wait of the standard-library loop itself remains a
  documented limitation.
- Backing up a WAL-format source produces a WAL-marked copy, so every copy this module writes is
  normalised with `PRAGMA journal_mode=DELETE`; opening a WAL-marked database later would create
  `-wal`/`-shm` side files with ordinary (non-owner-only) permissions next to candidate data.
- The correction tool's `--apply` snapshot was written `0o644` and was never verified or protected from
  overwriting (reproduced by running the tool on a throwaway database).

**Implementation.** New `career_agent/backup.py` (standard library only, no Tkinter, no network):
`validate_app_database()` (read-only integrity check, exact schema-version match, required tables, row
counts, foreign-key check), `create_backup()` (destination created owner-only with `O_EXCL` before any
data is written, never overwritten, never through a symlink, copied through SQLite's backup API,
normalised, verified, partial file removed and reported on any failure), and `restore_backup()`
(validate → stage beside the database and re-validate → preserve the current database, verified when
readable and raw-but-owner-only when not, refusing if it cannot be preserved at all → refuse while
another connection holds the database → atomic `os.replace` → remove stale side files → reopen and
verify, putting the previous database back if the final check fails). `store.py` grew the shared
primitives (`create_private_file`, `require_owner_only`) so permission logic stays in one place, and
exposes `SCHEMA_VERSION`/`SCHEMA_TABLES` so the backup contract cannot drift from the schema (a drift
test compares them with a freshly initialised database). The desktop gained a **Data safety** tab with
*Back up database* / *Restore from backup* (validate, confirm, close the connection, restore, reopen);
`python -m career_agent --backup-to PATH` and `--restore-from PATH [--yes]` provide the same operations
headless, which is what a database too damaged to open the window requires. `scripts/correct_tracker_record.py`
now takes its pre-change snapshot through `create_backup`, which also fixed its unprotected `0o644`
snapshot. `.gitignore` now covers backup, side-file and staging names, with a test that proves each
generated name is ignored.

**Guarantees and limits stated in the README.** Backups are verified before success, owner-only on POSIX,
never overwritten, single self-contained files, never modified by a restore; restores validate first,
coordinate with other connections, are atomic, and verify after. Backups are **not encrypted**; POSIX
permissions do not apply on Windows; a synced/shared folder can still expose a file; SQLite's integrity
check cannot detect every byte-level change; a concurrent writer can make the standard-library backup
wait.

**Evidence.** Reproduced each hazard above before the fix. Tests **243 → 312** (new `tests/test_backup.py`
with 51 cases plus 12 GUI handler cases and 3 correction-tool cases). Test-teeth: **14 controlled
mutations, all 14 caught**, each file restored SHA-256-identical (the first sweep missed two — an outer
exclusive-lock check that the snapshot already performs, which was then removed as provably redundant,
and one badly-anchored mutation, re-targeted and caught). Verification: full suite 312 OK (also with a
socket-blocking `sitecustomize` shim, re-created at `/tmp/blocknet`), `compileall` exit 0, `tabnanny`
exit 0, CSV audit exit 0 with the unchanged SHA-256 `0356b093…f414` (83 records). No dependency,
adapter, scheduler, submission path, or external transmission was added; the source-quality gate remains
**NOT PASSED**; the Mac database was never accessed. Stated honestly rather than tested: no GUI was
rendered here (no display, no tkinter in this sandbox), so the macOS checklist items added to
`research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` still need the user's manual run.

## 2026-10-14 (desktop readiness) — Status choices, record times, version reporting

**Scope.** Three inspected areas, in this order: (A) tracker status choices and transition validation,
(B) data freshness and timestamps, (C) packaging, version reporting, and diagnostics. Starting point
`9f5fb9db11a4a1ad198a67f2c679011959896242` on branch `arena/351e052d-ai-career-agent`; `main` untouched.

**Findings (reproduced before any change).**

- **A1 — the status dialog offered illegal statuses.** `_update_status` listed all thirteen
  `ApplicationStatus` values for every record, so a record at `discovered` was offered ten transitions the
  domain refuses (`confirmed`, `interview`, `submitted_unverified`, …). The refusal only appeared after
  clicking Save. The canonical vocabulary is the existing enum and `_TRACKER_TRANSITIONS`; no new
  vocabulary was invented.
- **A2 — one unrecognised stored status disabled four views.** `store.get_tracker` builds
  `ApplicationStatus(row["status"])`, so a legacy, hand-edited, or future value raised a bare
  `ValueError` from a read path: the tracker list, the jobs list, the status dialog, and the JSON export
  all failed with `'ghost_status' is not a valid ApplicationStatus`. The stored row itself was never
  modified, which is correct and was preserved.
- **A3 — a final state still presented a full chooser.** A `withdrawn` record was offered every status,
  all of which the domain refuses (withdrawal is terminal).
- **B — no freshness information was displayed at all**, although the database has persisted
  `job_listings.first_seen_at`/`last_seen_at` and `application_tracker.updated_at` since schema 1. The
  app stores no source publication or update date, so no source date can be shown and none is invented.
- **C — no version reporting, no packaging metadata, unusable start-up diagnostics.** `--version` was not
  recognised, `career_agent.__version__` did not exist, there was no `pyproject.toml`, and a start-up
  failure showed only the raw exception text (`file is not a database`) with no version, no next step,
  and no redaction.

**Decisions.**

- Storage-level enforcement stays exactly as it is: `save_tracker`/`_check_tracker_invariants` remain the
  authority for initial status, permitted transitions, the confirmation-evidence floor, and
  earned-only `candidate_confirmed`. Nothing was moved into the UI, and no safeguard was weakened.
- The chooser is now derived from the state machine through `core.selectable_tracker_statuses`, and a
  record in a final state is told so instead of being offered impossible changes.
- A stored status the build does not recognise is surfaced verbatim (lists, status dialog, export) and
  blocks status changes, because no transition can be validated from an unknown state. The app does not
  guess, repair, rewrite, or delete the row. A scoped repair flow is deferred: choosing a replacement
  status is a domain decision that needs its own safety design (explicit target, reason, backup,
  migration tests), not a side effect of this phase.
- Record times are displayed in the detail pane as this app's own observations, labelled as local, with a
  plain statement that the source's publication or update date is not available. Missing values read
  "not recorded"; an offset-less or unparseable value is shown as stored with a label instead of being
  guessed at. No schema change: the columns already exist.
- Version reporting is a literal in `career_agent/__init__.py` (`__version__`), reported by
  `python -m career_agent --version` together with the schema version, and it works with no packaging
  metadata and no display.
- Start-up failures are explained by the new Tk-free `career_agent.diagnostics`: a plain-language
  message that names the next step, with the database and home paths redacted, plus one bounded
  owner-only note beside the app data that holds no candidate data, credentials, or filesystem
  locations.
- Packaging stays a documented gap: no `pyproject.toml`, installer, or bundled interpreter was added,
  because none of that can be verified for the supported operating systems here. The README lists the
  missing pieces and the order they are needed in.
- `desktop.main` now shows the sanitised explanation (including the note's file name) instead of the raw
  exception, and still re-raises so the process exit status stays non-zero. The status dialog gained
  Escape (cancel) and Return (save) bindings and a final `except Exception` that reports an unexpected
  failure without claiming success.

**Evidence.** Regression tests cover the chooser's option set measured against the state machine, every
stored status, terminal records, unrecognised stored values across all four affected views, the unchanged
storage-level refusals, timestamp rendering (missing, offset-less, unparseable, converted), the
version path with Tkinter blocked, and diagnostics redaction. Test count **313 → 388**. Test teeth: **20
controlled mutations, all 20 caught** (the one initially missed — disabling the dialog's unrecognised-status
check — showed the same refusal was reached through a second read; the two reads were merged into one, and
the mutation was then caught by 15 tests). Files were restored SHA-256-identical after each run.
Verification: full suite 388 OK, also with a socket-blocking `sitecustomize` shim (`/tmp/blocknet`);
`compileall` exit 0; `tabnanny` exit 0; CSV audit exit 0 with the unchanged SHA-256 `0356b093…f414` (83
records). No dependency, adapter, scheduler, submission path, or external transmission was added; the
source-quality gate remains **NOT PASSED**; the Mac database was never accessed. Stated honestly rather
than tested: no GUI was rendered here (no display, no tkinter in this sandbox), so the macOS checklist
items added for the new UI behaviour still need the user's manual run.

## 2026-10-14 (later) — SQLite connection lifecycle: the macOS `ResourceWarning`

**Reported.** `python -m unittest discover -s tests` on macOS (after syncing `1ffe480`) passed but
printed `ResourceWarning: unclosed database in <sqlite3.Connection object ...>`, located at
`tests/test_desktop_handlers.py:34` — the body of the `StringVar` stub.

**Measurement, not guesswork.** Python 3.11 (this sandbox) does not implement that warning at all: an
unclosed connection collected by the garbage collector is completely silent (demonstrated directly), so
the reported line is where the collector happened to run, not where the connection was created. The
leak was therefore measured instead: every `sqlite3.connect` in the suite was tracked with its creation
traceback and the test that was running. Result on the reported commit: **856 connections created, 4
never closed** — three where `_restore_database` gave the app a new `CareerStore` and the test fixture
only closed the store it started with (`desktop.py:282 → store.py:230`, in
`DatabaseRestoreHandlerTests`), and one in `BackupValidationTests.test_a_truncated_database_is_refused`,
where `with sqlite3.connect(...) as connection:` reads as if it closed the connection but only manages
the transaction.

**Fixes.** `CareerStore.__init__` closes its connection when opening or initialising fails (a store that
cannot open used to hold the file until the collector ran, with no reference left to close it);
`tests/test_backup.py` reads the page size in `try/finally`; `HandlerTestCase.make_app` registers a
cleanup that closes whatever store the app holds when the test ends, so a handler that replaces the
store cannot leak it. No behaviour, schema, permission or safeguard changed.

**Regression tests.** New `tests/test_resource_lifecycle.py` (5 tests): a failed open closes its
connection (unreadable file and newer schema) and a successful open still hands back a usable one; a
source scan refuses `with sqlite3.connect(...)` anywhere in `career_agent/`, `scripts/` or `tests/`; and
a child process re-runs the entire suite with `tests/leak_watch_sitecustomize.py` on its `PYTHONPATH`,
failing if any connection is never closed (it also fails if the watch counted implausibly few
connections, so a silently broken watch cannot pass). A handler-level test covers the replaced store.

**Evidence.** Test count 388 → **394**, all passing; the required
`python -W error::ResourceWarning -m unittest discover -s tests` passes (exit 0) — and on this
interpreter that command cannot fail, which is why the leak watch exists. Measured with the committed
watch: **before 4 never-closed connections, after 0**. Teeth: three controlled mutations — removing the
failed-open close (caught by the store test), restoring the `with sqlite3.connect(...)` fixture (caught
by both the source scan and the leak watch), and unregistering the fixture cleanup (caught by the leak
watch, which names the three leaked connections) — all caught, files restored SHA-256-identical.
Verification: full suite 394 OK, also with the socket-blocking shim; `compileall` exit 0; `tabnanny`
exit 0; CSV audit exit 0 with the unchanged SHA-256 `0356b093…f414`. The Mac database was never
accessed, `main` was not touched, and PR #2 stays open and unmerged.

## 2026-10-14 (later) — Local-first PDF/DOCX résumé import with a review step

**Task.** Implement local-only résumé import: native file picker → local text extraction → proposals
restricted to fields the existing `CandidateProfile` schema already holds → a review screen showing every
proposal (value, evidence, confidence) → per-value accept/reject → the accepted values validated and saved
through the existing persistence path → a truthful result naming saved and skipped fields. The profile must
never be overwritten straight after parsing, nothing may leave the machine, and no schema field may be
invented.

**What was built.** New module `career_agent/resume.py` (Tk-free): `extract_text`/`extract_pdf`/`extract_docx`
and `parse_resume`/`parse_resume_text`, with `FieldProposal` (key, label, value, confidence, evidence),
`UnmappedItem`, `ResumeParseResult`, and the error taxonomy `ResumeImportError` → `ResumeTooLarge`,
`ResumeUnreadable`, `ResumeEncrypted`, `ResumeNoText`. DOCX extraction is standard-library `zipfile` +
`xml.etree.ElementTree` (DTD refused, macro part reported and ignored, declared uncompressed size checked
before decompression); PDF extraction uses the **optional** `pypdf` library, imported lazily, with a clear
"PDF support is not installed" refusal when it is absent. Limits: 10 MB per file, 32 MB declared DOCX
uncompressed size, 40 PDF pages, 400k extracted characters — every limit refuses rather than truncating, and
no error message carries document text. `career_agent/desktop.py` gained *Import resume (PDF/DOCX)* on the
Candidate Profile tab, `_import_resume` (pick, parse, honest refusal, no profile change), `_review_resume`
(dialog: per-proposal tickboxes that start ticked **only** for `confident` proposals, evidence and confidence
shown, missing-field list, "present in the document but not stored" list, notes, Escape/Return bindings,
Cancel and Save selected values), and `_apply_accepted_profile_values` (merge accepted over the current form
→ the shared `build_candidate_profile` validation → `save_profile` → `get_profile` read-back compared
field-by-field with `desktop_logic.profile_fields_not_matching`; success is reported only after that
comparison passes). Cancelling, declining the confirmation, selecting nothing, and every failure path leave
the stored profile exactly as it was. No schema change, no migration, no new mandatory dependency, no
network call anywhere in the path.

**Never guessed.** Only six keys are ever proposed: skills (from an explicit Skills section), degree (only
with a subject), graduation year (only from an explicit phrase; a bare year is `needs review`, two years or
none are not proposed), study status and country (explicit/labelled text only, always `needs review`), work
authorization (quoted, always `needs review`), and experience years (never derived from employment dates).
Name, email, phone, institutions and dates have no profile field, so they surface as informational
`UnmappedItem`s — the schema was not extended for them.

**Two defects found and fixed while building (both by tests, before any commit).** (1) The first DOCX walker
searched a paragraph element for paragraph/table *children*, so every real DOCX produced zero lines and the
import refused every file; it was rewritten as the recursive `_docx_lines_for`. (2) `pypdf` logs structural
complaints about a damaged file — with fragments of it — straight to stderr; the `pypdf` logger now has a
`NullHandler` and `propagate = False`, and a test asserts the captured stderr of a damaged-PDF import is
empty.

**Evidence.** `python3 -m unittest discover -s tests` (no `pypdf`) → **475 tests, OK, 11 skipped**, and the
same suite with `pypdf` 6.20.1 installed → **475 tests, OK** (394 before this task, +81 tests).
Targeted: `tests/test_resume.py` 55 tests in both interpreters; `tests/test_desktop_handlers.py` 128 (20
new résumé-review handler tests); `tests/test_desktop_logic.py` 38 (6 new read-back comparison tests). The
new handler tests run the real handlers, the real parser and a real SQLite file through widget stubs —
rendering itself is still not tested here. Teeth: eight controlled mutations of the new code were applied
to a scratch copy — auto-applying the extracted values before review, skipping the review dialog entirely,
reporting a failed save as success, removing the read-back verification, starting every tickbox checked,
cancelling and saving anyway, dropping unselected form values, and leaving a copy of the chosen file next to
the database — each was caught by the intended test(s) (the copy mutation by exactly one test, with the
extra file named in the failure). Automated tests do **not** cover GUI
rendering (no display or `tkinter` in this sandbox), and CI installs nothing, so the 11 PDF tests skip with a
reason there; they were run locally with `pypdf` 6.20.1 (BSD-3-Clause, no mandatory dependencies).

## 2026-10-14 (later) — macOS crash in the résumé review window: `unknown option "-wraplength"`

**Reported.** On macOS with Python 3.14 and pypdf 6.20.1, a PDF import extracted text and then
`_review_resume()` died at `career_agent/desktop.py:411` with
`_tkinter.TclError: unknown option "-wraplength"`.

**Root cause.** The proposal row passed `wraplength=720, justify=LEFT` to `ttk.Checkbutton`. Those are
`ttk.Label` options: real Tk raises while the widget is being constructed. The headless tests could not
catch it because every stub widget accepted any keyword, so the same code that crashed on macOS passed
here and in CI on all three Python versions.

**Fix.** The row is now a plain `ttk.Checkbutton(row, text=proposal.label, variable=variable)` — the
label alone, which is all a checkbox should carry — beside two wrapping `ttk.Label`s that hold the value
(`<field>: <value>`) and the review state (`<confidence> · from: <evidence>`). The dialog was rebuilt
around that: a fixed header, a scrolling `tk.Canvas` + `ttk.Scrollbar` body that holds the proposal rows
(with `<Configure>` re-fitting the scroll region and the content width, and mouse-wheel scrolling), and a
footer `ttk.Frame` packed before the body so **Save selected values** and **Cancel** cannot scroll away.
The dialog now opens at 900x640 with a 620x400 minimum, and `WM_DELETE_WINDOW` is wired to the same
`cancel()` as Escape and the Cancel button, which writes nothing and says so in the status line.

**Regression tests (8).** The stubs now refuse options real Tk refuses: each stub widget class declares
the option set its real counterpart accepts (`TTK_CHECKBUTTON_OPTIONS` and friends) and raises
`TclOptionError` for anything else, so construction-time crashes of this class fail headlessly. New
tests: a wrapping option on a checkbutton is refused like real Tk; every proposal row passes only
`text`/`variable` and matches the row count; the wrapping labels carry the value and the
confidence-plus-evidence; exactly one canvas and one scrollbar exist, every row is inside the scrolled
frame, the buttons share a parent outside it, and the scroll-region and mouse-wheel bindings exist; the
dialog opens at a usable size with a smaller minimum; closing the window writes nothing; and — in the new
`WindowConstructionTests` — the whole window with every tab is built against those validating stubs.

**Evidence.** Suite 475 → **483 tests, OK**, in the default interpreter (11 PDF tests skip without pypdf)
and with pypdf 6.20.1 installed (**483 OK, no skips**); socket-blocked run 483 OK; `-W
error::ResourceWarning` run 483 OK; `compileall` and `tabnanny` exit 0; CSV audit exit 0 with the
unchanged SHA-256 `0356b093…f414` (83 records). Teeth: seven controlled mutations on a scratch copy —
restoring the reported `-wraplength` line, dropping the scrollable area, packing the actions into the
scrolling frame, removing the close-button handler, removing the geometry, letting the checkbox swallow
the value, and disabling the stubs' option checking — were all caught (the last with the `-wraplength`
bug restored as well, showing the option assertion catches it even without the validating stub); both
scratch files were verified restored by SHA-256. Rendering itself is still not tested here (no display,
no tkinter in the sandbox), and steps 24-31 of
research/local-alpha-manual-smoke-test-checklist-2026-10-14.md are the macOS retest for this fix.

### 2026-10-14 — End-to-end audit of PR #2 (branch, code, gates, docs)

- Scope: an autonomous audit of the whole working branch — profile persistence and validation, PDF/DOCX
  extraction, parsing, review, cancellation and selective saving, SQLite connections/transactions/
  schema/backup/restore, listing validation and provenance, the source-quality gate, eligibility and
  fail-closed shortlisting, tracker transitions and confirmation evidence, GUI error handling/
  cancellation/scrolling/shutdown, sensitive-data handling, malformed input, resource limits, CLI,
  diagnostics — with every verified defect fixed under a regression test. Nothing was enabled: no
  adapter, no network, no automatic submission, and `main` was not touched.

- Defect 1 (fail-open shortlisting). `validation.optional_float` accepted `nan`, `inf` and `1e400`, so a
  profile or listing could store a non-finite value — and `NaN` is not valid JSON, so the stored payload
  was unreadable to a strict parser. Worse, a listing whose `minimum_experience_years` was `nan`
  evaluated `experience_years: pass`, giving `Decision.PASS` and `can_be_ranked_as_eligible = True`.
  Fixed in `validation.py` (finite check with a user-facing message) and, in depth, in `core.py`
  (`_is_real_number` guard that returns UNKNOWN for a non-finite candidate value or bound, covering rows
  written before the guard existed). Tests: `test_optional_float_refuses_values_that_are_not_real_numbers`,
  `test_the_largest_ordinary_numbers_are_still_accepted`, `test_a_non_finite_experience_value_is_never_a_pass`,
  `test_a_non_finite_job_experience_bound_is_never_a_pass`, `test_an_ordinary_experience_range_still_passes_and_still_fails`,
  plus two form-level cases in `test_desktop_logic.py`.

- Defect 2 (résumé skills sections discarded). The parser dropped the skills value when a heading shared a
  line with its list — exactly what real PDF extraction produces (`SKILLS Python, SQL`, `SKILLS: Python`);
  a 31-layout synthetic probe found 24 layouts that produced no proposal, and 7 synthetic PDFs read
  through pypdf showed the same shape. `resume.py` now keeps column gaps as a separator instead of collapsing them, recognises a
  much wider heading vocabulary (Technical/Key/Core/Software/Soft skills, Skillset, Areas of Expertise,
  Competencies, Technologies, Tech Stack, Tools & …), tolerates decoration, letter-spacing and
  same-line/merged-column headings, treats a category label inside a block as a label rather than a skill,
  and reports "no skills heading recognised" separately from "heading found, no list followed". Probe
  24/31 → 2/31 failures, and the 2 that remain are correct refusals (text hidden under a summary heading;
  content extracted before its heading). 13 new test methods in `test_resume.py` (several of them looping
  over dozens of heading names or layouts), including DOCX tables and sidebar-style absolute-positioned
  PDFs; unselected or absent fields still leave the saved profile as it was.

- Defect 3 (misleading restore refusal). Pointing a restore at a folder reported "the current database
  could not be preserved", which is true of nothing; it now refuses with "is a folder, not a database
  file" before any staging file exists. Two more restore shapes were probed and are now tested: a symbolic
  link in place of the live database is refused with its target left byte-identical, and an ordinary
  confirmed restore still keeps a verified copy of what it replaced.

- Defect 4 (confirmation-evidence floor). `is_substantive_confirmation_evidence` refused bare placeholders
  but accepted a phrase about testing the feature ("This is a test"), which could then be recorded as the
  evidence for `confirmed`. The whole-value list now covers those phrases; a sentence that merely contains
  such a word is still accepted, and both the domain and storage tests list the new cases.

- Coverage added where the audit found none: `tests/test_cli_backup_restore.py` (14 tests) drives the real
  argument parser and exit codes for `--backup-to`/`--restore-from` — refusals leave files untouched, a
  restore without a terminal or without `--yes` is refused, a confirmed restore keeps the previous
  database as a verified copy, the two actions cannot be combined, and the database commands never import
  the desktop module. `WindowShutdownTests` (3 tests) builds the app through its real `__init__` against
  the validating stubs and proves the `WM_DELETE_WINDOW` handler closes the store, destroys the window and
  writes none of the form's unsaved values. `RealDatabaseSafetyTests` (3 tests) reads the test files as
  syntax trees and refuses a `CareerStore(...)` with no path, and any call to the default-path functions
  that would resolve this machine's real folder, so the suite cannot open the candidate's database.

- Evidence. Suite 483 → **525 tests, OK** (12 skips without pypdf: the PDF-extraction cases) and **525 OK,
  no skips** with pypdf 6.20.1; targeted runs green (backup 54, CLI 14, resume, store/core/validation,
  desktop handlers, resource lifecycle). Backup/restore probed end-to-end on disposable databases
  (round trip, 2000-row file, garbage, truncated, empty, symlink, directory, newer schema, missing table,
  dangling tracker row, read-only folder, unreadable file — every refusal left the live database
  byte-identical). URL probe 42/42; CSV audit exit 0 with the unchanged SHA-256 `0356b093…f414`;
  `compileall` and `tabnanny` exit 0. No test or script opens the default database, and no candidate data,
  database file, secret or temporary artifact entered the commit.

- Gate status unchanged. `SOURCE_QUALITY_GATE_PASSED` stays `False`: `enabled_discovery_sources()` is
  still empty, the acceptance evidence (≥20 unique relevant currently-available vacancies, a measured
  direct-link validity with a defensible denominator, the eligibility/applicant-country audit, and
  per-source permission) is still unmet, and `open` is still not treated as verified availability. A unit
  test asserts the constant is `False`, so nothing can flip it to make a build pass.

- Limitations. No display and no tkinter in this environment, so widget rendering, window behaviour and
  macOS-specific behaviour still rest on the manual smoke-test checklist; the audit changed behaviour only
  where a probe or a test could demonstrate it, and the two remaining skills-layout failures are documented
  instead of papered over.
