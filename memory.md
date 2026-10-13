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
