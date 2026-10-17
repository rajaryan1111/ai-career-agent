# Project Memory and Decision Log

This file is the durable record of meaningful decisions, research findings, assumptions, and open questions. Update it whenever the project reaches a meaningful point.

## Project identity

- Working name: **AI Career Agent** (not final).
- Repository: https://github.com/rajaryan1111/ai-career-agent
- Current stage: production-oriented, cross-industry product implementation plus parallel source/competitor/permission research; the local Tkinter/SQLite alpha is implemented; resume parsing, source adapters and remote worker remain gated or pending.
- Last updated: 2026-10-17.

## Latest verified local checkpoint

- On 2026-10-17 at the authorized PR head `fbe19a9`, the local macOS/Python 3.14 verification pass found and
  fixed a four-pixel K1 overflow in the Jobs & eligibility tab at the declared `900x600` minimum, and made the
  repository `tests/` directory explicit so standard-library discovery cannot resolve an unrelated installed
  `tests` package. The full suite then ran **2073 tests, OK (skipped=1)**; the real-window acceptance harness
  reported **113 checks passed** and the desktop smoke test **14 checks passed**. The manual desktop checklist
  remains **123 steps: 22 PASS, 101 BLOCKED, 0 FAIL**; no human step was marked from automation.
- The partial-profile JSON round-trip gap identified by the audit was fixed locally without changing the
  version-2 format: optional facts, including country and skills, may be absent and imported values remain
  imported and unconfirmed. The linked-state JSON import gap was then fixed locally: local listing identity and
  tracker state are preserved, missing follow-up/activity state is reconciled idempotently, and conflicting
  local follow-ups are refused.
  The post-write resume-import status distinction was then fixed locally as well: committed-but-unverified
  writes no longer report "nothing was saved". The focused desktop/resume runs were 174 and 523 tests OK, and
  the full local suite was 2080 tests OK (skipped=1). The external-action gates remain closed:
  `SOURCE_QUALITY_GATE_PASSED = False` and
  `enabled_discovery_sources() == ()`.

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

### 2026-10-15 — Cross-platform CI reached green, and what it cost to get there
- Decision: the declared support remains Linux, macOS and Windows on CPython 3.10-3.13; 3.14 is not added to
  the policy because no compatible interpreter has been exercised here.
- Added `cross-platform` GitHub Actions legs (windows-latest, macos-latest x Python 3.10, 3.13) that verify
  installation, `--version`, `--doctor` against a missing and a damaged database, schema creation and
  cross-process persistence, backup/restore that really replaces data, JSON export/import, the discovery
  invariants, Tk availability plus a minimal widget lifecycle, and the desktop smoke test on every leg - on the
  Windows and macOS runners Tk needs no display variable, and both the lifecycle check and the 14-check window
  smoke test pass there. Every step records its output into one notes file, and `scripts/ci_annotate.py` publishes failures
  (and a green run's counts) as annotations, because this project must be able to read a run through the API.
- Defects found by the first runs, each fixed with a regression test: the scripted window check inspected a
  notebook's tab *names* as widgets; the owner-only mode helper raised on Windows (no `os.fchmod`), refusing
  every private write and with it every store construction; six doctor tests hard-coded Linux's folder name;
  the wheel-verification step ran `python -` from the checkout, so the checkout satisfied an assertion about
  the installed copy; four tests patched `os.fchmod` and one patched `os.O_NOFOLLOW`, neither present on
  Windows; a temporary folder was removed while the app that used it was still open.
- Platform limits, stated and asserted rather than assumed: the owner-only guarantee is POSIX-only; Windows
  refuses `os.replace` while another handle holds the destination open, so the restore's guard is released
  before the swap and the release window is a documented, asserted limit; an idle SQLite connection is
  invisible to the coordination on every platform.
- Result: run 38713190679 on commit `f38ac49` is green - 12 jobs, including both Windows and both macOS
  legs. The three jobs that record notes also publish a green run's counts as an annotation, so "the job is
  green" is never the only thing known about a platform.
- Written up in `research/cross-platform-desktop-ci-evidence-2026-10-15.md` (probe, matrix, root causes,
  transcripts, invariants) with a second dated follow-up in the manual checklist and phase 3 of the
  platform work in `research/release-readiness-audit-2026-10-15.md` (section 8.1).
- **Corrected later the same day, and this is the part worth remembering:** the first reading of those runs
  said the window was BLOCKED on Windows and macOS. It was not. Two defects sat between the runs and the
  reading - D11, the reporting steps turning a green Windows leg red because the notes file mixes the bash
  steps' UTF-8 with the Python steps' ANSI code page, and D12, a widget-lifecycle check that published every
  exception as "could not run on this runner" while never having imported `tkinter.ttk` (and whose report a
  copy of it broke on macOS's bash 3.2). Fixed in `76d0a3c`, `d56172d` and `e803286`; run 38719357147 is green
  and every leg publishes its own interpreter, Tk version, screen and verdicts. The lesson is in `rules.md`:
  a BLOCKED is a claim about a machine, so it must name the missing capability and quote the platform, and a
  reporting step must never be able to fail the run it reports on.

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

- Defect 3 (a second restore inside one second was refused, for the wrong reason). The pre-restore
  snapshot name is timestamped to the second, and `create_backup` never overwrites an existing file, so
  the second restore in a scripted pair was refused with "the current database could not be preserved" —
  which described the wrong problem, since the only obstacle was that the first restore had already used
  that second's name. `_snapshot_path` now keeps each restore's copy under the next free name
  (`…backup-<stamp>-2`), raising a clear refusal only in the practically unreachable case of no free name;
  nothing is overwritten. Regression test: `test_a_second_restore_in_the_same_second_keeps_its_own_copy`.

- Defect 4 (misleading restore refusal). Pointing a restore at a folder reported "the current database
  could not be preserved", which is true of nothing; it now refuses with "is a folder, not a database
  file" before any staging file exists. Two more restore shapes were probed and are now tested: a symbolic
  link in place of the live database is refused with its target left byte-identical, and an ordinary
  confirmed restore still keeps a verified copy of what it replaced.

- Defect 5 (confirmation-evidence floor). `is_substantive_confirmation_evidence` refused bare placeholders
  but accepted a phrase about testing the feature ("This is a test"), which could then be recorded as the
  evidence for `confirmed`. The whole-value list now covers those phrases; a sentence that merely contains
  such a word is still accepted, and both the domain and storage tests list the new cases.

- Defect 6 (a damaged stored record crashed the read paths). `store.get_profile()` and `store._decode_job()`
  passed a stored JSON payload straight into a dataclass, so a hand-edited or damaged row raised whatever
  the standard library raised: an unknown field gave `TypeError: CandidateProfile.__init__() got an
  unexpected keyword argument`, a list/string/`null` payload gave `AttributeError: '…' object has no
  attribute 'get'`, truncated or empty text gave `json.JSONDecodeError`, and a listing without
  `availability_status` gave `KeyError`. None of those is caught by a Tk callback or a list refresh, so one
  bad row could take a whole view down with a traceback. Worse, `{"skills": "Python"}` did not raise at all:
  `frozenset("Python")` silently turned one value into six single-character skills that later comparisons
  would use. Reads now go through `_stored_object`/`_stored_text_values` and raise one named
  `store.StoredRecordError` (a `ValueError`, exported like `TrackerStatusError`) with a plain message; a
  string where a list belongs is refused rather than split into letters; and nothing is repaired, rewritten,
  or deleted. `desktop.py` handles it on every read path (`_load_profile`, `_refresh_jobs`,
  `_refresh_tracker`, `_select_job`, `_evaluate`, `_shortlist`, `_export`, the résumé read-back) with one
  `_report_unreadable_record` helper, so the person sees what is wrong and that nothing changed. Regression
  tests: `UnreadableStoredRecordTests` in `tests/test_store.py` (10) and in `tests/test_desktop_handlers.py` (8).

- Defect 7 (a post-write verification failure claimed nothing was saved). `_apply_accepted_profile_values`
  wrapped `save_profile` and the verifying `get_profile` read-back in one `try`, so any failure of the
  read-back was reported with "Nothing was saved; your previously saved profile is unchanged" even though
  the row had already been written. The write and the verification are now separate steps: a failure before
  the write keeps that wording, and a failure to read the profile back afterwards is reported as written but
  unconfirmed, pointing at the Profile tab. Regression test:
  `test_a_resume_save_whose_read_back_fails_is_not_reported_as_saved`.

- Defect 8 (start-up diagnostics mangled the message or leaked a name the user chose). `redact_paths`
  replaced "the database folder" literally, so `--database db.sqlite3` (whose parent is the current folder,
  text `.`) rewrote every dot in the explanation — "Schema version 2.0" became
  "Schema version 2<application data folder>0" — and a short relative folder name such as `data` was
  replaced inside ordinary prose ("the data folder could not be used"). A file named on the command line
  (`--backup-to`, `--restore-from`) was not covered at all, so an unexpected failure while restoring could
  write the person's own backup location into the local note that exists to be safe to share. Substitution
  now applies only to absolute paths or paths that carry a separator, the folder is hidden only when it is
  itself absolute, and `describe_startup_failure`/`record_startup_failure` accept `extra_paths`, which
  `__main__.main()` fills with the paths named on the command line. Regression tests:
  `test_a_relative_database_file_does_not_replace_every_dot_in_the_message`,
  `test_a_relative_folder_name_is_not_replaced_inside_ordinary_words`,
  `test_a_path_the_caller_names_is_redacted_when_it_is_supplied`,
  `test_an_unsupplied_foreign_path_is_left_alone_rather_than_guessed_at`, and
  `test_a_file_the_person_named_on_the_command_line_stays_out_of_the_note`.

- Defect 9 (a relative data-folder override moved the database with the working directory). `XDG_DATA_HOME`
  and `LOCALAPPDATA` were used as given, so a relative value produced a database path resolved against
  whatever directory the app was started from: the same person's profile would appear to move (or vanish)
  between launches. The base-directory specification requires these variables to be absolute and says a
  relative value should be considered invalid and ignored, which is what `_absolute_root` now does, falling
  back to the documented per-user default. Regression tests: `test_a_relative_environment_override_is_ignored`
  and `test_a_relative_override_never_reaches_the_database_path` (a non-empty absolute override is still
  respected, by the existing test).

- Defect 10 (a skills category was saved as a skill, and merged columns were pre-ticked on a word count).
  "Languages: Python, SQL" already read correctly, but the same statement written with the column gap the
  extractors report — "Languages | Python, SQL" — kept the category, producing 'Languages, Python, SQL' as
  a *confident* proposal, one click from being saved. Merged columns were worse
  than inconsistent: "Python, SQL, Django␣␣␣␣Built ETL pipelines" offered the prose as a skill (three words,
  under the four-word guard) while "Python, SQL␣␣␣␣Built ETL pipelines at scale" silently dropped it (five
  words) — the same layout, opposite outcomes, decided by counting words. The category list is now applied
  to the column-gap form exactly as to the colon form, and a line that merges two columns with no
  recognisable category label is still offered exactly as read but marked `needs review`, so nothing that
  was guessed at is pre-ticked. Regression tests:
  `test_a_category_name_before_a_column_gap_is_not_read_as_a_skill`,
  `test_a_plain_pipe_separated_list_of_skills_is_still_read`,
  `test_a_skills_line_that_merges_two_columns_is_offered_for_review_not_pre_ticked`,
  `test_a_single_column_skills_list_is_confident_and_unchanged`. Known residual: a skills line with no
  column gap whose values are prose of four words or fewer is still offered as read (no reliable rule
  distinguishes "Built ETL pipelines" from "Google Cloud Platform"), and the two layouts that produce no
  proposal at all (a category on its own line, a headline merged with a skills heading) are still refused.

- Defect 11 (a test run wrote into the person's own application-data folder). `cli.main([])` carries no
  database path when it fails before one is resolved, so `record_startup_failure` fell back to the real
  per-user folder and wrote `logs/startup-diagnostics.log` there - which is exactly where a real failure
  writes its note, so running the suite overwrote the note a real failure had left behind. Verified by
  running the suite and reading the file it produced (`ValueError: boom before any path is resolved`, the
  message of the one test that does this). That test now redirects `default_data_folder` into its own
  temporary directory and asserts the note still lands there, and `RealDatabaseSafetyTests` gained a fourth
  scan that refuses any test call to `record_startup_failure()` with no `data_folder=`/`database_path=`.
  Re-run evidence: the real note's mtime and size are byte-identical before and after a full suite run.

- Defect 12 (two DOCX shapes escaped the reader as raw exceptions). `extract_docx` refused the shapes it
  knew about, but a DOCX arriving with ZIP's encryption flag set on its members - which some archivers and
  online converters produce, distinct from Word's own password-protected OLE container, already refused -
  made the standard library raise `RuntimeError("File 'word/document.xml' is encrypted, password required
  for extraction")`. A member declared with an unimplemented compression method (AES, method 99) raised
  `NotImplementedError`. Both are reproducible with a normal ZIP whose header fields are rewritten, and
  neither is a `ResumeImportError`, which is the *only* type `_import_resume` catches: the person choosing
  that file would have seen a Tk traceback instead of an explanation. The reader now checks the document
  part's flag bits and compression method itself and refuses with its own wording, and any remaining
  failure in the function is wrapped as `ResumeUnreadable`, so `parse_resume`'s documented promise - every
  failure is a `ResumeImportError` - holds for shapes this build has not seen. Verified with
  `/tmp/probe_docx_hostile.py`: nine fixture shapes, `non-ResumeImportError escapes: 0` (was 2), with the
  control file still reading `skills='Python, SQL'`. Regression tests:
  `test_a_password_protected_docx_is_refused_as_encrypted`,
  `test_a_docx_stored_with_an_unsupported_compression_method_is_refused`,
  `test_a_damaged_compression_stream_is_refused_with_the_docx_message`,
  `test_every_unreadable_docx_is_refused_as_a_resume_import_error` (nine shapes), plus the handler tests
  `test_a_password_protected_docx_is_reported_and_nothing_is_saved` and
  `test_an_unexpected_reader_failure_is_reported_rather_than_escaping_the_callback`. That last one also
  hardened `_import_resume` with a last-resort branch: it reports the exception's *type* (never its
  message, which could quote document text) and states that nothing was proposed and the profile is
  unchanged, so an unforeseen reader failure cannot reach a Tk callback that has no handler above it.

- Defect 13 (a location quoted by a failure message reached the note meant to be safe to share).
  `redact_paths` replaced the database path, its folder, the home folder, and paths named on the command
  line, and deliberately left every other path-shaped string alone - a documented rule with its own test.
  Measured, that rule leaks: a path inside an exception's own text (the file `create_backup` names, or any
  location an unexpected failure quotes) stays verbatim in both the terminal message and
  `logs/startup-diagnostics.log`, so a note advertised as sanitised could carry
  `/Volumes/Investor Backup/private/notes.sqlite3`. The rule is superseded: after the named locations are
  replaced, any remaining *absolute* location - POSIX, Windows drive, UNC, quoted or containing single
  spaces - becomes `<local path>`. The sweep is deliberately narrow: a relative word, a version number, a
  relative file name, and a public URL are not locations and are untouched, and trailing sentence
  punctuation is preserved. Regression tests:
  `test_an_unsupplied_absolute_path_is_hidden_rather_than_copied_into_a_note` (five shapes),
  `test_redacting_a_location_keeps_the_sentence_around_it_readable`,
  `test_a_relative_word_or_a_public_url_is_never_mistaken_for_a_location`, and the end-to-end
  `test_a_location_quoted_inside_the_failure_message_never_reaches_the_note`. Recorded limit: prose the
  module cannot classify as a location is still copied into the note, because it is local and the message
  is what makes it useful - the promise is path redaction, not content filtering.

- Coverage added where the audit found none: `tests/test_cli_backup_restore.py` (14 tests) drives the real
  argument parser and exit codes for `--backup-to`/`--restore-from` — refusals leave files untouched, a
  restore without a terminal or without `--yes` is refused, a confirmed restore keeps the previous
  database as a verified copy, the two actions cannot be combined, and the database commands never import
  the desktop module. `WindowShutdownTests` (3 tests) builds the app through its real `__init__` against
  the validating stubs and proves the `WM_DELETE_WINDOW` handler closes the store, destroys the window and
  writes none of the form's unsaved values. `RealDatabaseSafetyTests` (3 tests) reads the test files as
  syntax trees and refuses a `CareerStore(...)` with no path, and any call to the default-path functions
  that would resolve this machine's real folder, so the suite cannot open the candidate's database. The
  audit in this stretch added `UnreadableStoredRecordTests` (10 tests, the stored-record refusal), the
  handler-suite `UnreadableStoredRecordTests` (8 tests, every view), four path-redaction tests, a
  command-line redaction test, two data-folder tests for relative environment overrides, four skills
  tests (category labels before a column gap, merged columns, and the flag surviving a later labelled
  line), and a fourth isolation scan (no start-up note may be written into the real folder). A second
  audit stretch added nine tests: four DOCX-refusal cases (encryption flag, unsupported compression
  method, damaged stream, and one battery over nine malformed shapes), two import-handler cases (a
  password-protected file, and an unforeseen reader failure that must not escape the callback), three
  redaction cases (absolute locations in five shapes, punctuation preserved, relative words or URLs left
  alone), and their end-to-end command-line case.

- Evidence. Suite 483 → 526 → 557 → **566 tests, OK** (12 skips without pypdf: the PDF-extraction cases)
  and **566 OK, no skips** with pypdf 6.20.1; targeted runs green (backup 55, CLI 14, resume, store/core/validation,
  desktop handlers, resource lifecycle). Backup/restore probed end-to-end on disposable databases with
  `/tmp/probe_backup.py`, 17/17 checks: a verified backup holding profile, jobs and tracker rows; a round
  trip restoring the same rows with the replaced database kept as a verified owner-only copy; the chosen
  backup file never modified; a 2000-row (2.2 MB) database; and a missing, empty, non-database, truncated,
  newer-schema, missing-table or folder input each refused with the live database byte-identical, a
  read-only folder refused with the database untouched, bytes damaged in the middle of the file refused
  with the database untouched, and the real per-user database never created. `/tmp/probe_restore_edges.py`
  adds six odd destination shapes (symlink in place of the live database, a folder, an empty file, a
  restore onto its own source, a read-only folder, an unreadable backup): each is refused or completed
  safely, with the symlink target and the folder left untouched. URL probe 42/42; CSV audit exit 0 with the
  unchanged SHA-256 `0356b093…f414`; `compileall` and `tabnanny` exit 0; `git diff --check` exit 0. The
  second audit stretch adds: `/tmp/probe_backup_scale.py` 11/11 (a 500-listing database round-trips with
  every row and the listing order intact, a 512 MiB file of zeroes is refused in 0.00 s without touching
  the database, a torn file is refused, the live database is byte-identical after each refusal, and a
  second backup/restore cycle keeps the rows), `/tmp/probe_tracker_matrix.py` (all 13 statuses reachable,
  the chooser offers exactly the domain's transitions for every status, and the store accepts all 41
  permitted pairs and refuses the rest), `/tmp/probe_sources_gate.py` (discovery and submission closed for
  all six reviewed sources, unknown ids refused, no network-capable import in `sources.py`, every recorded
  decision carrying a real ISO date and an evidence reference), `/tmp/probe_cli_e2e.py` 27/27 (process-level
  exit codes 0/2/3, an existing backup never overwritten, a restore without `--yes` refused, the previous
  database kept, a corrupt backup refused with the live database byte-identical, and a note that carries no
  path from the failure text), `/tmp/probe_eligibility_conservative.py` 7/7 (label fields normalise case
  and spacing, work authorization stays exact but case-insensitive, unknown never passes, and a
  similar-looking country does not match), `/tmp/probe_display_credentials.py` 9/9 (the real application
  object builds against the stubs, the jobs list, tracker list, status line and detail report show no
  stored credential, and an export is owner-only `0600`), and the re-run hostile-DOCX probe with zero
  escapes. No test
  or script opens the default database or writes into the real application-data folder (verified by mtime),
  and no candidate data, database file, secret or temporary artifact entered a commit.

- Gate status unchanged. `SOURCE_QUALITY_GATE_PASSED` stays `False`: `enabled_discovery_sources()` is
  still empty, the acceptance evidence (≥20 unique relevant currently-available vacancies, a measured
  direct-link validity with a defensible denominator, the eligibility/applicant-country audit, and
  per-source permission) is still unmet, and `open` is still not treated as verified availability. A unit
  test asserts the constant is `False`, so nothing can flip it to make a build pass.

- Limitations. No display and no tkinter in this environment, so widget rendering, window behaviour and
  macOS-specific behaviour still rest on the manual smoke-test checklist: the two behaviours this stretch
  changed in a window (a merged-column skills proposal arrives unticked, and an unreadable stored record
  shows a "Saved record could not be read" dialog instead of a traceback) are proven here only through the
  widget stubs. The audit changed behaviour only where a probe or a test could demonstrate it; the two
  remaining skills-layout failures, prose of four words or fewer inside a skills section, and the
  folder-creating side effect of `default_database_path` (deliberate - SQLite cannot open a database in a
  folder that does not exist - and now stated in its docstring rather than only implied by a test) are
  documented instead of papered over. A note keeps prose from an exception message that is not a location:
  the redaction promise covers filesystem locations, not content the module cannot classify.

## 2026-10-14 (later) — Review of restore concurrency, tracker correction and the reopen path

Three defects were reported for review on branch `arena/351e052d-ai-career-agent` (PR #2) and each one was first
reproduced against disposable databases, then fixed at the smallest point that removes it, then covered by a test
that fails without the fix.

- **A restore could report success while the window was unusable.** ``_restore_database`` installed the new store
  only on success; after a failed reopen the *closed* connection stayed as ``self.store``, the next refresh raised
  ``ProgrammingError: Cannot operate on a closed database`` out of a Tk callback, and the app still showed
  "Restore complete" and the status line "Restored from …". Reproduced with the handler harness (mock
  ``CareerStore`` raising) before any change. Now a failed reopen installs ``store.UnavailableStore``, which refuses
  every use with ``StoreUnavailable`` and a plain message; the success dialog and the "Restored from" status are
  not shown at all in that case, the real reason is reported, and ``close()`` stays safe. The silent list
  refreshes (``_refresh_jobs``/``_refresh_tracker``), ``_select_job``, ``_evaluate`` and ``_load_profile`` now also
  report a dead connection instead of letting ``sqlite3.Error`` escape as a raw traceback.
- **A competing write could be accepted and then silently discarded by the swap.** ``create_backup`` refused while
  another connection held a lock, but the window between that check and ``os.replace`` was open: a second
  connection could begin *and commit* a transaction there, and the replacement then threw the committed file away.
  Reproduced by patching ``os.replace``. ``_lock_for_swap`` now holds the database's exclusive lock across the
  replacement, so the competing writer is told the database is busy instead of winning and being erased. An
  *idle* connection still cannot be detected on any platform (it holds no SQLite lock) — the restore proceeds,
  the idle connection keeps its old view, and its next write fails with SQLite's own ``SQLITE_READONLY``. That
  limit is now documented in the README and covered by a test that asserts the behaviour rather than claiming a
  detection that does not exist.
- **A tracker correction could overwrite newer data and report success.** ``save_tracker`` re-checked only the
  transition rules, which a forward move normally leaves permitted, so ``scripts/correct_tracker_record.py`` could
  replace a record's newer evidence and confirmation flag; its verification also compared only the status.
  ``save_tracker(..., expected=...)`` now performs one conditional UPDATE comparing the fields the caller decided
  from and raises ``StaleTrackerRecord`` when no row matches, and the tool verifies listing id, status, evidence,
  confirmation flag and that ``updated_at`` is a parseable ISO-8601 write time. The conditional write is committed
  before ``rowcount`` is interpreted — without that, a write whose verification happens on another connection would
  look like it never happened (this was caught by the tool's own dry-run test).
- Local verification: ``python -m unittest discover -s tests`` → **582 tests, OK (skipped=12)** on a tree whose
  unmodified tip (``c7bb081``) runs 567, so the fifteen added tests are the difference; ``python -m compileall -q
  career_agent scripts tests`` → exit 0; ``python scripts/audit_job_source_csv.py`` → exit 0 with the unchanged CSV
  SHA-256 ``0356b093…f414``. Each change was also run against the pre-fix code (a throwaway worktree) and the new
  tests failed there: the tracker tests ended in a reported success over an overwritten record and a verification
  that passed with the intended evidence missing; the restore test recorded the competing write as *accepted*; the
  desktop tests showed "Restore complete" after "Database unavailable" and the raw ``ProgrammingError``.
- Still unverified after this pass: the reviewer's résumé-import and export/persistence checklists were reviewed
  against the code and the existing tests (78 résumé tests OK, including the notice-heading regression that keeps
  the skills proposal at exactly ``Python, SQL, Git``) but no new defect was reproduced there; the gate remains
  **NOT PASSED** and live discovery stays disabled.

## 2026-10-14 (later) — Platform review of the swap guard, the side-file window, and the verification pass

A review pass over the three hardening changes from the previous entry, plus the repository-side verification
that can be done without a Mac.

- **One genuine defect found and fixed: the swap guard could not work on Windows.** ``_lock_for_swap`` takes
  ``BEGIN EXCLUSIVE`` and holds it across ``os.replace``. On POSIX that is exactly right — measured during this
  pass, the guard's own open handle is what refuses a competing writer inside the swap window (an independent
  connection attempting ``BEGIN IMMEDIATE`` there is told "database is locked", while an opener arriving after
  the swap sees the restored data). On Windows it was a defect: SQLite opens its database files with
  ``FILE_SHARE_READ | FILE_SHARE_WRITE`` and never ``FILE_SHARE_DELETE``, so ``MoveFileEx`` - what
  ``os.replace`` calls - fails with a sharing violation (WinError 32) while the app holds its own guard open,
  which would have made **every** restore fail there. ``_CAN_REPLACE_AN_OPEN_FILE`` now records the platform
  capability (``os.name != "nt"``), and where it is false the guard is closed immediately before the
  replacement. Nothing is lost on Windows: the operating system refuses to replace a file any other handle has
  open, so a second copy of the app makes the restore refuse with the current database untouched, and the only
  remaining window is the instant between releasing the guard and the swap. Two tests pin the two behaviours so
  neither can regress into the other: one asserts a competing write is *refused* where the guard is held, the
  other asserts the database is writable again inside the replacement where it is released first.
- **A second genuine defect, from the same Mac report: the start-up message described the wrong problem.**
  The person's first attempt to launch the window on a disposable database failed because the database's
  parent folder did not exist. Reproduced here with the exact code path: SQLite reports "unable to open
  database file", and ``describe_startup_failure`` answered "The local database could not be read ... it may be
  damaged, or it may be a different kind of file" and advised restoring a verified backup or renaming the
  unreadable file - a file that never existed, with advice that could not work. Nothing was damaged and the
  remedy was to create the folder. ``_explain_database_open_failure`` now separates the three causes that can
  be established from the location itself (the folder does not exist, the path is a folder, the folder is not
  writable) from a file that is present but unreadable, and each message names a next step that can work
  without disclosing any filesystem location. Only ``Path.is_dir`` and ``os.access`` are consulted: nothing is
  created, renamed or tested destructively, and when no path was supplied the honest general message stays.
  Four tests cover it, and the two behaviour tests fail when the branch is disabled (verified with the branch
  short-circuited), so they are not decoration. The window and the terminal start-up both call this function,
  so the improvement reaches the path the person actually sees; the window itself still needs a Mac.
- **A documented risk that did not reproduce.** ``_remove_sidecars`` described a stale ``-wal`` being replayed
  onto a replaced database as silently discarding the restored data. The removal is necessary (the side files
  belong to the previous database) but its stated rationale is stronger than the code path demonstrates: with a
  genuine stale ``-wal`` written by a killed WAL-mode writer, an opener arriving in the window between the swap
  and the removal saw the **restored** rows, both with the stale ``-shm`` present and with it deleted, and the
  restore completed (the restore removes both afterwards). SQLite discarded the mismatched WAL itself, because
  the change counter it records (9) no longer matches the restored file's (1). The docstring now says that
  rather than claiming the module is the thing preventing the loss, and a test guards the ordering
  (snapshot → swap → remove) that keeps that window safe.
- **Verification completed without a Mac**: full suite **588 tests, OK** locally (582 at the reviewed head plus
  the six added here; 12 skipped only because the optional ``pypdf`` was absent); with ``pypdf 6.20.1``
  installed in an isolated virtual environment the same suite runs **588 OK with nothing skipped**, so the PDF
  extraction, scanned-encrypted-damaged rejection and sidebar-layout tests really execute rather than skip.
  ``compileall`` exit 0; ``scripts/audit_job_source_csv.py`` exit 0 with the unchanged CSV SHA-256
  ``0356b093…f414``; ``--version`` and ``--help`` exit 0. The suite's own leak watch reports **1260 connections
  created, 0 never closed** across the whole suite, which includes the new guard paths.
- **The local-first promise gained two checks that can be automated** (``tests/test_local_only.py``). One reads
  the shipped modules (``career_agent/``, ``scripts/``) and refuses any call that could transmit or resolve -
  ``socket.socket``, ``getaddrinfo``, ``urlopen``, ``HTTPConnection``, ``webbrowser.open``, ``subprocess``
  invoking curl/wget - or any import of a module whose purpose is remote communication (``requests``,
  ``urllib.request``, ``http.client``, ``smtplib``, and the like), while explicitly allowing
  ``urllib.parse`` and ``socket.inet_aton`` because both only read a string the user typed. The other runs the
  documented ``--backup-to`` and ``--restore-from`` commands in a child interpreter whose ``sitecustomize``
  makes socket creation raise, after first proving in that same child that the block is real; both commands
  exit 0 with no socket available. Neither check is vacuous: planting ``import requests`` in a shipped module
  fails the scan, and neutering the guard fails the runtime test with "the guard did not install, so this run
  would prove nothing". Together with the existing résumé-import network test this is static-plus-runtime
  evidence for a stated product guarantee; it still cannot prove that the desktop toolkit or a future
  dependency never opens a socket, and the manual inspection step stays outstanding.
- **Checklist steps 17, 18, 21, 22 and 23 were executed end to end at the CLI level** against a throwaway
  database in a temporary folder: a backup is written and verified; a second backup to the same path is refused
  with exit 2 and the earlier file is byte-identical (same hash and mtime); the backup file is ``-rw-------`` on
  Linux; a restore from a text file is refused with exit 2 and the database hash is unchanged; a confirmed
  restore replaces the data (the job added after the backup is gone), reports the previous-database copy beside
  the database, and exits 0; nothing is written inside the repository. The GUI half of those steps, and the
  résumé review window, still require a real desktop session: the UI tests run against a stub harness that
  reproduces Tk's option validation (``unknown option "-wraplength"`` is raised by the stub exactly as real ttk
  raised it), which is what guards the macOS regression, but the harness is not Tk and the manual checklist stays
  outstanding. Python 3.14 on macOS remains unverified here.

## 2026-10-15 — Installable package: PEP 621 metadata, one version, and a build verified in CI

**What changed.** The README's packaging gap #1 ("distribution metadata plus a build verified in CI") is
now implemented rather than planned. Added `pyproject.toml` with PEP 621 metadata: project name
`ai-career-agent`, `requires-python = ">=3.10"`, **no required runtime dependency**, an optional `pdf`
extra (`pypdf>=4.3`), and a `career-agent` console script bound to `career_agent.__main__:main` — the same
callable `python -m career_agent` runs. Only the `career_agent` package is packaged; `tests/` and
`scripts/` stay in the checkout, so the maintenance tooling (`audit_job_source_csv.py`,
`correct_tracker_record.py`) is deliberately not importable from an installed environment.

**Decisions and reasons.**

- **The version stays a literal, and setuptools reads it instead of a second copy.** `pyproject.toml`
  declares `dynamic = ["version"]` with `version = {attr = "career_agent.__version__"}`, so the installed
  metadata and `--version` come from the same string and cannot drift. `tests/test_packaging.py` parses
  `career_agent/__init__.py` with `ast` and requires exactly one module-level `__version__` assignment
  whose value is a `str` constant — a computed version would break the build rather than silently record
  something else.
- **No required dependency.** The application, the tests and the CLI tools all run on the standard
  library, and Tkinter ships with CPython. PDF résumé reading is the single optional capability and is
  declared as the `pdf` extra; `pypdf` is imported lazily and its absence is reported in the app. A
  required dependency would change what an install pulls in for everyone, so it needs a deliberate
  decision, not a default.
- **The declared `pypdf` floor is measured, not guessed.** The PDF tests were run against pypdf 4.3.1,
  5.9.0 and 6.20.1 in disposable virtual environments (`tests.test_resume`: 78 tests OK on each), so
  `pypdf>=4.3` describes releases actually exercised here. 6.20.1 is the version the macOS report used.
- **`requires-python = ">=3.10"` matches the CI matrix**, and a test refuses the metadata drifting away
  from the oldest CI leg, because a floor nobody tests is a claim rather than coverage.
- **CI verifies the artefact, not just the source tree.** A second job (`installed-package`) builds the
  wheel with `python -m build`, asserts the wheel contains only modules under `career_agent/` and no
  `tests/` or `scripts/`, installs it into a clean environment, and — from outside the checkout — checks
  the metadata version against `career_agent.__version__`, refuses any required dependency, and runs
  `career-agent --version`, `--help`, a throwaway database write, a backup and a restore. Those
  assertions mirror `tests/test_packaging.py`, which is why one interpreter is enough for the job.
- **The usage line now names how the program was invoked.** `career_agent.__main__` reports
  `career-agent` when that is what was typed and `python -m career_agent` otherwise (the module form's
  `sys.argv[0]` is `__main__.py`, which is not something to show a person). Configuration, exit codes,
  the redaction rules and every failure path are untouched.
- **`tomllib` is a 3.11+ module, so the metadata tests skip with a stated reason on 3.10** and the CI
  job covers the same properties there; no dependency was added just to read the file in the suite.

**Evidence.** `python -m unittest tests.test_packaging` → 12 tests OK. Full suite at this state: 604 OK
(13 skipped without `pypdf`). `python -m pip wheel . --no-deps --no-build-isolation` and
`python -m build --wheel` both produce `ai_career_agent-0.1.0-py3-none-any.whl` with 12 modules, all
under `career_agent/`, and metadata `Requires-Python: >=3.10`, `Requires-Dist: pypdf (>=4.3) ; extra ==
'pdf'`, and `career-agent = career_agent.__main__:main`. In a throwaway virtual environment the wheel
installs with no dependencies, `career-agent --version` prints `career-agent 0.1.0 (database schema
version 1)` (exit 0) and the module form still prints `python -m career_agent 0.1.0 (database schema
version 1)`; a disposable database written through the *installed* package survived
`--backup-to`/`--restore-from --yes` with exit 0; `tests`, `scripts` and `correct_tracker_record` are not
importable after installation. `compileall` exit 0, the research-CSV audit exit 0 and the CSV SHA-256
unchanged, and the source-quality gate still `False` with an empty `enabled_discovery_sources()`.

**Defect found and fixed the same day: a CI assertion pinned the build backend's spelling.** The first
CI run on the packaging commit failed in the new `installed-package` job. The assertion compared
`metadata.requires("ai-career-agent")` to the byte-exact string `pypdf (>=4.3) ; extra == 'pdf'` — which
is what `pip wheel` with setuptools 66 writes, while `python -m build` (the modern backend CI uses)
writes `pypdf>=4.3; extra == "pdf"`. Reproduced by extracting the workflow step and running it against a
wheel built the way CI builds it: `AssertionError: the install must pull in nothing`, exit 1. Fixed by
asserting the properties instead — exactly one declared requirement, it names `pypdf`, and it carries an
`extra == "pdf"` marker, so nothing installs unconditionally — after normalising spaces and quote style.
The step now exits 0 locally against the CI-built wheel, and the three regressions it exists to catch (a
required dependency appears, the wrong library is declared, a second requirement appears) are each still
caught. What let it through: the local metadata check had been run against a `pip wheel` artefact with an
older setuptools while the contents check used `python -m build`; the fix to the process is to run the CI
step verbatim against an artefact built the way CI builds it. `tests/test_packaging.py` now refuses a
literal comparison of `metadata.requires(...)` in the workflow (and is itself checked against the exact
regressed line, so the guard is not vacuous), refuses an embedded workflow script that is not valid
Python, and holds the `installed-package` job to actually building, installing and running the command.

**Still missing (unchanged product claim).** No installer, no signed/notarised desktop bundle, no bundled
interpreter, no published release, and no version/data-compatibility policy yet; nothing was published to
any package index. `README.md` and `phases.md` were updated so the installation instructions, the
packaging status and the test count describe what actually exists.

## 2026-10-15 — Schema versioning: recorded steps, atomic updates, and older backups accepted again

**What changed.** The database schema moved to version 2 and the store gained a migration framework.
`career_agent/store.py` now holds `_MIGRATIONS`, an ordered list of `(version, description, step)`:
version 1 creates the original profile/job/tracker tables (the very statements the schema was always
created with, so a database written by an earlier build holds the same objects at the same version), and
version 2 adds
`application_activity`, the append-only log the tracker needs, with an index on
`(listing_id, occurred_on, activity_id)`. No existing object is rewritten by either step.

**Decisions and reasons.**

- **One explicit transaction per step, statements executed one at a time.** Probed before writing the
  framework: `PRAGMA user_version` and DDL roll back together, so the version can be recorded inside the
  same transaction as the structure; but `executescript` **commits any open transaction before running its
  script**, and the sqlite3 module's implicit transaction covers data-modifying statements only. A step
  that applied three of four statements through `executescript` would therefore be committed,
  half-applied, with no way back. The framework issues `BEGIN IMMEDIATE`/`COMMIT` by hand and applies
  steps statement-by-statement; a test asserts that a step creating an index before failing leaves no
  object behind and does not move the version, and that test fails when the hazard is reintroduced.
- **"Nothing changed" is verified, not assumed.** After a failed step the version is re-read from the
  file. `SchemaMigrationError` carries the version the step started from *and* the version observed
  afterwards, and its message differs accordingly ("still at schema version 1" versus "now records
  schema version 2 … may have been applied only in part"), including the case where the version cannot be
  read back at all. Each branch has a test.
- **Refusals are named types instead of a bare `RuntimeError`.** `SchemaTooNewError` (a newer schema) and
  `UnrecognisedDatabaseError` (tables present, no recorded version, so the file was not written by this
  application — adopting it would add our tables to somebody else's file) both leave the file
  byte-identical, which the tests assert rather than assume.
- **Backups from an earlier schema version are accepted again.** Bumping the version would otherwise have
  broken the main recovery path ("back up, upgrade, restore"), because validation required
  `version == SCHEMA_VERSION`. It now checks the candidate against the tables *of the version that file
  records* (`SCHEMA_TABLES_BY_VERSION`), so a version-1 backup validates, is installed exactly as
  validated, and is updated when the app opens it; a version the application has never written is still
  refused. The restore report says the file was an older schema and what will update it: the desktop
  dialog says which versions, the command line prints the same fact, and the validation of the *installed*
  file afterwards proves the update was recorded.
- **A new database is still created the same way, and an empty file is a new database.** A file holding
  tables but no recorded version is now refused instead of being adopted, which is stricter than before
  and is what stops a foreign SQLite file from acquiring this application's tables.

**Evidence.** `tests/test_store.py` `SchemaMigrationTests` (11 tests: fresh database pins literal version
2; the step list is 1..2 with descriptions and table contracts; a version-1 database updated in place with
its job, profile and rows intact; an up-to-date database runs no step; the failed-step rollback and the
no-object-left-behind property; a later step failing keeps the earlier one applied; the three failure
messages; byte-identical refusals for newer and unrecognised files; an empty file treated as new);
`tests/test_backup.py` (an older backup accepted with `activity_count` correctly `None` and no "activity"
in the summary; an older backup missing a table of its own version still refused with the version named;
the version contract checked to be cumulative); `tests/test_cli_backup_restore.py` (restoring an older
backup reports the update, restores the data, and the file records the new version only after being
opened; a current backup says nothing about an update); `tests/test_desktop_handlers.py` (the restore
dialog describes both the installed version and the update, and a current backup does not mention one);
`tests/test_diagnostics.py` (the three new failure classes explained, with no location quoted back).
Full suite 628 OK (13 skipped without `pypdf`), `compileall` exit 0, CSV audit exit 0 with the hash
unchanged, leak-watch 1363 connections created / 0 never closed. The activity log currently only has its
table: the domain type, storage API, export and desktop surface are the next commit.

**Still missing.** Encryption at rest, portability, a written release/upgrade policy (what a version number
promises), and everything that consumes the new table.

## 2026-10-15 — Application activity log: the dated history the tracker was missing

**What changed.** Schema version 2's table now has a product surface. `career_agent.core` gained
`ActivityKind` (a closed set: applied, response, interview, assessment, follow-up, note),
`ACTIVITY_KIND_LABELS`, and the frozen `ApplicationActivity` (kind, `occurred_on`, detail, plus the
`activity_id` and `recorded_at` the store assigns); the store gained `add_activity`, `list_activity`,
`list_activity_raw` and `delete_activity`; `desktop_logic` gained `build_activity` and
`activity_form_values`; the Tracker tab gained an activity panel with an add dialog and a delete
confirmation; and the JSON export carries the log.

**Decisions and reasons.**

- **The log sits beside the status, not inside it.** An entry is the person's own account of what
  happened, so it must not be able to move a status, create a tracker record, or satisfy the
  confirmation floor — a note such as "I applied" is exactly what someone might expect to double as
  proof, and it is refused as evidence at the *storage* boundary, not only in the dialog. Three tests
  name those properties directly.
- **Two dates, never conflated.** `occurred_on` is the day the person says it happened;
  `recorded_at` is when this application wrote the row. The panel shows them in separate columns and the
  list is ordered by `occurred_on` then `activity_id`, so "they replied on the 20th" cannot be confused
  with "this app heard about it on the 22nd".
- **A typed date is never guessed at.** The field accepts exactly `YYYY-MM-DD`: the shape is matched
  before parsing, because `date.fromisoformat` also reads basic (`20261012`) and ISO-week (`2026-W41-1`)
  forms, and a field that promises one shape should not quietly accept three. A blank date is refused
  rather than defaulted to today; the dialog pre-fills today so the common case is one keystroke.
- **The neutral default is deliberate.** A new entry starts as `note`, not `applied`: the one entry a
  person could save by accident must not be the one that claims an application was sent.
- **Refusals are reportable, not silent.** An entry for a listing that does not exist is refused before a
  dialog opens; a database failure during a save is reported and never as success; deleting an entry that
  is already gone says "already gone" instead of claiming a deletion; and a stored row this version cannot
  read (`kind` or `occurred_on` written by a later version) is refused by name on the read path, reported
  in the window, and still exportable through `list_activity_raw` — the export marks it
  `kind_recognised: false` rather than blocking the whole file.
- **Entries cascade with their listing.** Deleting a job deletes its history (foreign key, verified by a
  test that counts rows afterwards), which is the same explicit-delete behaviour the rest of the store has.

**Evidence.** `tests/test_core.py` (7 tests: labels, trimming, blank/over-long detail boundaries,
impossible and out-of-range dates, a `datetime` where a date is meant, a future date allowed because an
interview can be scheduled, string-kind normalisation, unknown kind refused by name);
`tests/test_store.py` `ActivityLogTests` (12 tests: round-trip with both dates, oldest-first ordering
regardless of write order, no tracker row created, not usable as confirmation evidence, unsaved listing
refused, storage-boundary re-validation, durability across reopen, single delete, delete-not-there,
cascade, unreadable rows on the read path with the raw read still working); `tests/test_desktop_logic.py`
(8 tests: defaults, offered kinds, trimming, strict date shape, impossible date, missing date, unknown
kind, blank detail); `tests/test_desktop_handlers.py` `ActivityHistoryTests` (13 tests through the real
handlers) and two export tests. Full suite 671 OK (13 skipped without `pypdf`), `compileall` exit 0, CSV
audit exit 0 with the hash unchanged, leak-watch 1391 connections created / 0 never closed. As part of
this work the widget stub in `tests/test_desktop_handlers.py` was made more faithful: inserted rows now
appear in `get_children()`, deleted rows leave it, and `item(id, "values")` coerces item ids the way Tcl
does — the last is what surfaced that the panel's delete summary had to read a real item id.

**Still missing.** Reminders, notifications, interview/follow-up scheduling, and any email or calendar
integration (Phase F) — the log records dates but nothing acts on them. The panel shows entries for the
selected application only; there is no filtering or search across the history yet.

## 2026-10-15 — One rule for the database path, and a read-only `--doctor`

**Decision.** Which database file a run uses is now decided in exactly one place,
`career_agent.config.resolve_settings`: an explicit path (`--database`), then the `CAREER_AGENT_DATABASE`
setting (absolute paths only), then `<data folder>/career_agent.sqlite3`. The data folder is
`CAREER_AGENT_HOME` plus the app's folder name when that setting is absolute, and the platform's per-user
application-data folder otherwise. `career_agent.desktop_logic.career_agent_data_root` gained the
`CAREER_AGENT_HOME` branch; everything else about platform resolution (the XDG rule that a relative
`XDG_DATA_HOME` or `LOCALAPPDATA` is ignored) is unchanged.

**Why.** Three front ends previously resolved the path by two different rules: the window called
`default_database_path()` (which ignores `CAREER_AGENT_DATABASE`), the command line called
`default_database_path()` unless `--database` was given, and there was no way to ask "which file is this
app actually using?" without opening a window. A person who keeps their data on an encrypted volume had
to pass `--database` on every launch, and a backup could name a different file than the app would open.

**What is deliberate about it.** Resolving settings has no side effects — no folder is created, nothing
is read — so the doctor can report what *would* be used. The single side effect is that
`config.database_path_for_run()` creates the *default* folder, because SQLite cannot open a database in a
folder that does not exist and a first run would otherwise fail before the window appeared. A path named
explicitly is used exactly as given and no folders are created for it: a mistyped path reports a missing
folder instead of quietly becoming a real one. A relative value in either setting is ignored and carried
in `Settings.notes`, which the doctor prints; silently resolving it against the working directory would
let a person's profile and history appear to move between launches.

**`--doctor`** (`python -m career_agent --doctor`, or the installed `career-agent --doctor`) reports the
version, the interpreter and platform, the resolved path *and the rule that chose it*, whether the data
folder exists and is writable, and what the database contains — using the same read-only
`backup.validate_app_database` the restore dialog uses, so a damaged, empty, or too-new file is reported
with the same refusal the app itself would show. It creates nothing, changes nothing, repairs nothing,
needs no display, and exits `1` when it finds a problem (distinct from the refusal code `2`). It is
mutually exclusive with `--backup-to`/`--restore-from`, since asking for a report and an action in one
command would be two answers to one question.

**Also changed:** the backup and restore commands now use the same rule, so `CAREER_AGENT_DATABASE`
moves all three front ends at once, and the window no longer reaches for `default_database_path()`
directly.

**How it was checked.** 24 new tests in `tests/test_config.py` (three path rules, the ignored-setting
notes, "resolving creates nothing", the single folder side effect, the doctor's exit codes and wording
for a missing, readable, older-schema, newer-schema, damaged, empty and unwritable-folder case, the
mutual exclusion with the backup command, and a subprocess check that `--doctor` never imports
`tkinter`). Three teeth checks confirmed the tests bite: dropping the
relative-path guard failed 2 tests, making the doctor always return success failed 4, and creating the
data folder inside the doctor failed 2 (all restored afterwards). The full suite caught two real
regressions this change introduced — a CLI test that patched `__main__.default_database_path` (rewritten
to point the *setting* at a different database and assert the backup's own row counts), and a new test of
mine that opened a connection in a `with` statement, which `tests/test_resource_lifecycle.py` refuses.
Suite: 695 OK (13 skipped). The suite's own guards are the reason both were caught rather than shipped.

## 2026-10-15 — One event log the person can read, and the bounds that keep it honest

**What changed.** `career_agent/event_log.py` records what the application did, one line per event, into
`logs/application.log` beside the database it describes. It is written from the places that already know
an outcome: `CareerStore` (opened, migrated, migration failed, profile saved/deleted, job saved/deleted,
tracker saved, activity added/deleted), `backup.create_backup`/`restore_backup` (written, refused,
completed), the desktop app (started, stopped, résumé proposed/failed, export written/failed), and
`diagnostics.record_startup_failure` (startup failed). `--doctor` now prints the log's path and its most
recent line; `store.append_private_text_file` is the owner-only append primitive, sharing the mode and
symlink rules with `write_private_text_file`.

**Why.** The start-up note explains *one* failed launch and is overwritten each time, so nothing answered
"when did my database change?", "did that backup actually run?", or "which step migrated this file?".
Support questions about a local-first app have exactly those shapes.

**The rules the module keeps, each one a test.** *One line per event:* a detail is flattened (control
characters to spaces, whitespace collapsed), capped at 200 characters with a `... (truncated)` marker,
and redacted with `diagnostics.redact_paths`, so a newline in a detail cannot forge a second event and a
local location cannot reach a file meant to be shareable. *Never candidate content:* callers pass an
identifier, a count or a category — the tests save a job, a profile and an activity entry through the real
store and assert the employer name, the role title, the skills and the entry text are all absent.
*Bounded:* rotation at 256 KiB keeps one previous file, so the logs folder can never grow without limit;
the newest events are the ones that survive. *Never in the way:* an unwritable folder, a full disk, a
database that is not a file (`:memory:`) or a permissions model that refuses owner-only files is reported
by returning `None`, because a log line failing must not fail the job save it was describing. The one
condition that raises is a malformed event name, which is a bug in this application rather than a state a
person can be in.

**Decisions.** The vocabulary lives in one tuple (`event_log.EVENTS`) and a test reads the shipped source
with `ast` and fails if a name is used that is not declared, or declared and never used — otherwise the
list would rot into documentation. Event names are positional-first (`timestamp event=name detail=...`),
which is what makes "a detail cannot impersonate an event" a property rather than a convention. The log
follows the database rather than a global constant, so a database on an external or backed-up volume
takes its own history with it; when no location is known at all, it falls back to the per-user
application-data folder, never the current working directory. A *second* guard test scans `tests/` and
fails any `record_event(...)` call that names neither `database_path=` nor `data_folder=`, because the
fallback would otherwise let a test write into this machine's real logs folder — the same protection the
start-up note already had.

**Teeth checks.** Removing the detail sanitisation failed 2 tests; removing rotation failed 2; making a
write failure escape failed 2; moving the activity event before the write failed 1; and inserting a bare
`record_event("app.started")` into a test made the new guard fail. All restored afterwards.

**Found rather than assumed.** Two existing tests caught this change honestly: "validating a database
creates no side files" and "a cancelled backup writes nothing" both noticed the new `logs` folder, and
both were rewritten to compare the folder's contents before and after the action (the first now also
checks every pre-existing neighbour's bytes and mode) instead of being weakened into passing.

## 2026-10-15 — A copy before the schema is changed, not only before a restore

**What changed.** `career_agent/store.py` now takes a verified safety copy of an existing database
*before* the first migration step runs. `_snapshot_before_upgrade` is called from the migration loop when
the file records a version between 1 and the current one and actually holds this application's tables;
the copy is written through the same `backup.create_backup` the desktop and command-line backups use
(verified by reading it back, owner-only where the platform supports it) and is reported as
`backup.written`. If it cannot be written the update does not start: `SchemaUpgradeRefused` names the
version on disk and the version it was going to become, says nothing was changed, and
`diagnostics.describe_startup_failure` explains the situation and the next step in plain language. On
success the event log records `database.upgrade_snapshot detail=version=<old> file=<name>` immediately
before `database.migrated from=<old> to=<new>`, so the copy and the update are visible in the history in
the order they happened. `backup.next_automatic_backup_path` names the copy: `<db>.backup-<UTC second
stamp>Z`, then `-2` … `-1000`, the first free name beside the database.

**Why.** The migration steps were already one explicit transaction each, rolled back and re-read from the
file when they fail, so a step that fails is not the dangerous case. The dangerous case is a step that
*succeeds*: it is committed, the application is usable, and only afterwards is it found to be the wrong
step — a wrong value, a mis-set status, a column that should have stayed. Rollback cannot help after a
commit, and the schema-2 change (the activity log) was the project's first real upgrade of data someone
may have been keeping for weeks. Copying the file first turns that into "restore the copy".

**The rules this keeps, each one a test.** *Only existing databases*: a new file and a file already at
the current version are not copied (2 tests), so the ordinary first run does not leave a snapshot of an
empty database beside it. *A refused copy refuses the update*: with the copy forced to fail, the open
raises `SchemaUpgradeRefused` and a byte-comparison test shows the file is unchanged and still records
version 1 — the update never begins. *A failed step keeps its copy*: when the next step then fails, the
first copy is still there, at the version it saw, with the rows it saw, and the live file is left where
the failure left it (`store` re-reads the recorded version; the copy is what makes recovery possible).
*Each copy describes its own moment*: an existing name is never reused, because a retry after a failure
would otherwise overwrite the evidence of the state the first attempt started from. *A verification of
the copy, not an assumption*: the snapshot goes through `create_backup`, so it is read back and validated
before the update proceeds.

**Why a shared name-finder rather than a second copy of the same code.** The pre-restore snapshot already
needed "the next free timestamped name", with its own `-2` … `-999` search, and this increment needed the
same search with a refusal message that says the update was not started. Two searches would have drifted.
`next_automatic_backup_path` is now that one search with one message; `restore_backup` calls it and so
does the upgrade path, and the previous `_snapshot_path` helper is gone (nothing else called it — verified
by grep, and the restore tests, including the pre-existing same-second retry test, pass unchanged). It
only *proposes* a name: `create_backup` still refuses to overwrite, so two processes racing on the same
second produce a safe refusal rather than one of them losing a copy.

**Evidence.** The focused run `python3 -B -m unittest tests.test_store tests.test_backup` is 166 OK; the
full suite is 743 OK (13 skipped without the optional `pypdf`); `python3 -m compileall -q career_agent
scripts tests` is clean. Before the tests, an end-to-end script upgraded a real version-1 database with a
saved job: the folder gained `career_agent.sqlite3.backup-<stamp>Z`, `backup.validate_app_database` read
that copy back as schema 1 with the job intact, the live file became schema 2, and the log read
`backup.written` → `database.upgrade_snapshot detail=version=1 file=…Z` → `database.migrated from=1 to=2`.

**Teeth checks.** Making a failed safety copy non-fatal failed 1 test (the byte-comparison one that
requires the update never to start); removing the call before the update failed 3 tests in
`tests/test_store.py`; reusing the timestamped name instead of searching for a free one failed 2 tests
and errored 1 in `tests/test_backup.py`. All three were restored afterwards, and the focused and the full
suite were re-run to confirm the restore was complete.

**Found while writing it.** The first version reused the timestamped name unconditionally, and the honest
test — open, fail the step, open again in the same second — was refused with "a file already exists at …
Backups are never overwritten". That was the code being wrong, not the test: the second attempt was a
*different* moment and deserved its own copy. The fix is `next_automatic_backup_path`; nothing in
`create_backup`'s refusal was relaxed to make the test pass.

## 2026-10-15 — Durable task storage: one run per occurrence, and a lease per database

**What changed.** Schema version 3 adds the storage half of the background scheduler.
`career_agent/tasks.py` holds the domain - a task definition with its schedule
(:class:`ScheduledTask`), the arithmetic that turns a schedule into its next instant
(:func:`next_run_after`), the identity of one occurrence (:func:`slot_key`), the retry rule
(:func:`retry_delay_seconds`, :func:`plan_after_run`) and the states a run moves through
(:class:`RunState`) - with no SQLite and no network code. `career_agent/store.py` adds three tables
(`scheduled_task`, `task_run`, `worker_lease`), the migration step that creates them, and the
operations: save/list/delete a task, `claim_due_run`, `finish_run`, `heartbeat_run`,
`recover_stale_runs`, `running_runs`, `list_task_runs`, and
`acquire`/`heartbeat`/`release`/`get_worker_lease`. The event vocabulary grew by ten names
(`task.scheduled`, `task.deleted`, `task.run_started|succeeded|failed|refused|interrupted`,
`worker.lease_taken|refused|released`).

**Why this shape.** The failure that matters for a scheduler is not "it crashed" - it is "it ran the
same thing twice", "it never ran what it owed", or "it silently moved a run". Each of those is
answered by data rather than by careful code:

*One run per occurrence* holds because a run is keyed by ``(task, slot, attempt)`` where the slot is
the instant the schedule named, not the moment execution started. Two workers, a retry after a crash,
and a restart all compute the same key, so the uniqueness constraint decides which of them runs it -
the loser is told "nothing was claimed" rather than being handed the run (a test proves this with two
connections to one file). *An occurrence is never lost* holds because the task keeps the occurrence it
owes: a failure with attempts left sets ``pending_slot_at``/``pending_attempt`` and comes back after
the backoff to serve *that* instant, and a process that dies mid-attempt leaves a run row whose
heartbeat goes stale, which `recover_stale_runs` closes as ``interrupted`` and re-plans by the same
rule as a failure. *A run cannot be rewritten* holds because `finish_run` refuses a run that already
finished, a run claimed by a different worker, and a run that is not there - each with
`TaskRunConflict` and no write - so the first recorded outcome is the one that stands.

**The states are deliberately not just "failed".** `REFUSED` means a rule said no (the closed
source-quality gate, for instance) and is not a malfunction: it is not retried, and it does not count
towards anything. `TIMED_OUT` and `FAILED` mean the attempt ran and did not work; `INTERRUPTED` means
nobody observed an outcome at all because the process stopped. Reporting a refusal as a failure, or an
interruption as a success, would each be a false claim about what the machine did.

**Time is wall-clock in a named zone.** The default cadence is 00:00 and 12:00 in `Asia/Kolkata`
(confirmed user decision), and the arithmetic works in the task's own zone and converts to UTC only for
storage, so a machine whose own clock zone differs cannot move a run (a test asks the same question
from three zones). Two DST cases are decided rather than inherited: a local time inside the
spring-forward gap is *skipped* for that day (moving it to 01:30 or 03:30 would silently run a task at
an hour nobody chose), and a local time that occurs twice uses the first occurrence only, so a daily
task cannot run twice that day.

**Found while writing it (a design flaw the test caught).** The first version recomputed the next
occurrence whenever *any* definition field changed, so renaming a task at 12:00:30 - after its noon
occurrence was due but before it ran - silently skipped that occurrence. Only the times and the zone
move a schedule now; renaming a task, pointing it at another handler, or changing its timeout leaves
the timing exactly as it was, and a test renames a due task and then claims the occurrence it owed.

**Not implied by this.** The store schedules nothing and runs nothing: no worker loop exists yet, no
command line or window exposes it, and the discovery schedule still cannot run live sources (the gate
is closed). Laptop-off operation remains unimplemented and is not claimed.

**Evidence.** Full suite 817 tests OK (13 skipped without the optional `pypdf`), with
`tests/test_tasks.py` (35 tests: schedule arithmetic including both DST cases, retry planning,
validation, slot identity) and `tests/test_store_tasks.py` (39 tests: upgrade to schema 3 keeping
existing rows and taking the pre-upgrade copy, claim/finish/heartbeat/recovery, duplicate claims from
two connections, lease refusal and stale take-over, and damaged rows reported as themselves).

## 2026-10-15 — The worker: running what is due, and recording what actually happened

**What changed.** `career_agent/worker.py` adds the engine (a registry of handlers, a validated
:class:`WorkerSettings`, a :class:`TaskContext` a handler is given, the tick/run loop, and a read-only
status report), and `career_agent/handlers.py` adds the two kinds this application registers:
`backup.snapshot` (writes and verifies a snapshot beside the database) and `discovery.run` (refuses
while the source-quality gate is closed, and touches no network). `backup.automatic_backup_snapshots`
became the one place that lists automatic snapshots, because the scheduled backup counts them to refuse
before a disk fills up.

**Timeouts and cancellation are described as what they are.** A handler runs on the worker's thread and
is given a deadline and a stop flag; a handler that ignores both keeps running. The module says so
plainly rather than promising cancellation, and the *record* is still honest: an attempt that finished
after its deadline is `TIMED_OUT` even when the handler reported success, because reporting a success
would promise a bound that was broken. Refusing is decided first: a handler that says "no" is recorded
as a refusal even if it says so late, since a decision is not work that ran out of time.

**Nothing is inferred from a handler's own opinion.** Raising is `FAILED` with the exception's type and
text; returning something that is not a `HandlerResult` is `FAILED` saying what came back instead;
returning `STOPPED` because a stop was asked for is `INTERRUPTED`, and `STOPPED` at the deadline is
`TIMED_OUT`. A kind with no handler fails and names the kinds that *are* registered. In every case the
run history keeps the distinction the honest reading requires.

**The handlers can only do what they say.** The backup handler refuses when no database file exists
yet, refuses once 30 automatic snapshots sit beside the database (naming the count and telling the
person to move some), never deletes an existing file - a scheduled backup must not destroy the recovery
copies it exists to create - and reports the verified content (`3 jobs · schema version 3`) from
`DatabaseInfo.summary()`. The discovery handler refuses with the gate's state in the message; a test
opens the gate in the module and proves the handler still refuses, because no live adapter exists, so
even an open gate cannot manufacture a run.

**Found while writing it (a real defect, kept as a regression test).** `build_task` has a parameter
called `timezone` holding a zone *name*, which hid `datetime.timezone` inside that function: the line
`datetime.now(timezone.utc)` was an attribute lookup on a string, so building a task without an explicit
reference time crashed. It surfaced the first time a default task was built, and
`test_building_a_task_without_a_reference_time_reads_the_real_clock` now builds one that way on purpose.
The alias it was replaced with (`_UTC = timezone.utc`) carries the reason in a comment.

**Also fixed here.** Run details and errors are stored through `diagnostics.redact_paths`, so an
absolute location cannot reach a database column that the export carries - while relative words, file
names and public URLs stay exactly as written, which is what makes a message useful.

**Evidence.** Full suite 870 tests OK (13 skipped without the optional `pypdf`), of which
`tests/test_worker.py` (34) and `tests/test_handlers.py` (17) are new, plus 2 regression tests in
`tests/test_tasks.py`. One test previously failed because it asserted `len(executed) == 1` while the
discovery task was legitimately also due at that instant; the test now pauses it explicitly, since that
test is about the backup.

**Not implied.** Nothing schedules itself yet: the worker is a library, no command line or window starts
it, and laptop-off operation remains unimplemented and unclaimed.

## 2026-10-15 — The schedule a person can actually use: commands and a window

**What changed.** The scheduler is reachable now. `python -m career_agent --worker` runs it in the
foreground (Ctrl-C stops it: the attempt in progress winds up, its outcome is recorded, and the lease is
released), `--worker-status` reports the lease, what is in progress, which task is next and the recent
attempts without claiming or writing anything, and `--seed-tasks` writes the default schedule into a
database that does not have those tasks. All three import no GUI toolkit, checked by a subprocess test.
The window gained a **Background tasks** tab: the same summary, the task list (times, zone, next run in
local time, last result), the fifty most recent attempts with their outcome and duration, buttons to add
the defaults and to pause/resume the selected task, and a refresh - reading the tables through the same
module the worker uses, so the view cannot disagree with what the scheduler would act on. The tab
deliberately does not run the loop: a worker on the interface's thread would freeze the window for as
long as a handler took, and closing the window would then be closing a worker mid-attempt.

**The boundary, in the product's own words.** `--worker` prints, before it does anything, that it runs
while the process runs, that it stops when the window or the terminal closes, that it does not run while
the computer is off or asleep, and that live discovery is disabled so scheduled discovery runs are
recorded as refusals. A person reading the output cannot come away believing their laptop will run jobs
overnight - which is the claim this project is not entitled to make until a separately deployed and
verified worker exists.

**Deliberately not the window's job.** Adding the defaults never rewrites an existing task: a task the
person configured (their own times, a different zone, paused) is left exactly as it is by both the
command and the button, and each says so. Pausing asks first, keeps the definition, the times and the run
history, and resuming schedules the next occurrence from now rather than replaying the missed ones.

**Found while writing it (a real UX flaw the tests caught).** The first version's selection helper folded
"nothing is selected" into "the selected task no longer exists", so a person who had selected a task that
had just been removed was told to select a task first - a message about the wrong problem. The helper now
only reads the selection, and the caller reports the two cases separately; a test deletes the selected
task and asserts the message that names what actually happened.

**Evidence.** Full suite 894 tests OK (13 skipped without the optional `pypdf`): 12 in
`tests/test_cli_worker.py` (seeding idempotence and non-overwriting, a read-only status that creates no
database, the refusal to run beside a lease holder, one real due task run through the command, the
headless check) and 12 in the new `SchedulerTabTests` (the list and summary, adding the defaults twice,
never rewriting a configured task, pausing with a declined confirmation, keeping history, resuming,
an unreadable row reported, a stale selection, and the stored definition winning over a stale row).
A real end-to-end run outside the tests: a due backup task wrote `career_agent.sqlite3.backup-<stamp>`
and verified it, status showed the run, and Ctrl-C released the lease - with the log reading
`worker.lease_taken` → `task.run_started` → `backup.written` → `task.run_succeeded` → `worker.lease_released`.

## 2026-10-15 — Explainable matching across industries, with coverage leading the ranking

**What changed.** `career_agent/matching.py` is the comparison engine, and
`tests/matching_fixtures.py` holds synthetic fixtures for six industries (software/data, embedded/VLSI,
mechanical, civil, design), a sparse record, a listing that states nothing, and a case where one factor
out of ten weight units is comparable. The engine builds six factors - required skills, experience
range, stated qualification, location, work mode, role type - reports each as pass, partial, fail,
unknown or not applicable with the evidence behind it, and returns a score *and the coverage that
produced it*. The window's evaluate dialog now shows these lines under the eligibility report, computed
from the *same* eligibility report so the two answers cannot disagree.

**Nothing is invented.** A listing that names no required skills has a skills factor that is
*not applicable* with no score - not zero and not a perfect score. A person who recorded no skills gets
"unknown", not a failure. A listing that states no location gets "unknown" for location, not a pass.
Text is folded only for case, spacing and separators: ``Power-BI``/``power_bi`` are one skill,
``VHDL``/``Verilog`` are not, and equivalences such as ``Postgres``/``PostgreSQL`` are used only when the
caller supplies them. **Compensation is not compared at all**, because the domain model has no field for
it: inventing one from free text is exactly what this module refuses, and it is recorded as outstanding
rather than approximated.

**A number is never a forecast.** The score is the share of the *recorded preference weight* the listing
satisfies, always reported beside its coverage, always with the disclaimer that it is not a probability
of being hired. A test scans every string the module can produce for forecast-like phrases
(``probability``, ``chance of``, ``likely to be hired``, ``guaranteed``, ``will be selected``) and fails
if one appears outside the disclaimer that denies it.

**Coverage decides the band, and the ranking.** Below 50% of the applicable weight known, the band is
"not enough information" whatever the known factors said; a "strong" reading needs two thirds, because a
bare majority is not a strong comparison. Three tests pin those boundaries, including one where a perfect
skills match covers only 30% of the weighted picture and is therefore *not* a strong fit. The ranking
order puts listings that could actually be compared first, then by score, then by coverage, then by id -
so the order is stable between runs and a barely-known listing cannot outrank a compared one.

**Eligibility is not overruled.** A FAIL blocks the recommendation while keeping the comparison visible
(blocking is not hiding), an UNKNOWN eligibility is reported as undecided rather than rounded to a match,
and blocked listings are excluded from the default order but kept in the full set.

**Found while writing it (two real flaws the tests caught).** First, the original ranking key put
coverage ahead of score, so a listing with a perfect skills match and a zero-everything-else record
outranked a listing that fitted well and was fully known; the key is now grouped and documented. Second,
the first version of the experience factor let a stored ``nan``/``inf`` satisfy a range, contradicting the
eligibility checker, which refuses it; a non-finite value is now "unknown, not a usable number".

**Teeth checks.** Treating "no skills recorded" as a pass failed 2 tests; ignoring the ranking key failed
4; removing the coverage floor failed 1; making a preference mismatch always pass failed 2 - and that last
one first *found a gap*: nothing had pinned a mismatch, so a test was added for work mode and role type
before the check could bite.

**Evidence.** Full suite 936 tests OK (13 skipped without the optional `pypdf`); `tests/test_matching.py`
is 45 of them, and the existing evaluation-dialog test was extended rather than weakened.

## 2026-10-15 — The adapter framework, and the one constant everything rests on

**What changed.** `career_agent/adapters.py` is the layer a job source would run under, and
`python -m career_agent --sources` is its surface: a read-only report of the gate, every reviewed source
with its decision/evidence/conditions, whether applying would be permitted anywhere (it would not), and
how many adapters exist (zero). The command creates no database and contacts nothing.

**The framework fixes the rules in code, not prose.** `SourceCapabilities` declares what an adapter can
do, and `submission=True` raises at construction: no adapter in this project may declare it. `RequestBudget`
caps a run at five requests, refuses a second request within the source's documented interval, and counts a
*failed* request against the budget - the bound is on what leaves the machine, not on what succeeds. A
page size is required and capped at 100, so "fetch everything" cannot be written. Retries happen only for
the three transient outcomes (rate limit, timeout, network), at most three times, with doubling waits
injected so the schedule is tested without waiting; a permission refusal or a schema error is **not**
retried, because repeating a source that said no is the behaviour this project refuses.

**Four results, kept apart.** Success with results, a legitimate empty result, a partial run, and a
failure - each a distinct outcome, and health reports them distinctly, because "the source is down" and
"the source has nothing today" lead to opposite decisions, and a partial run may not be used to conclude a
listing closed. Normalisation keeps provenance (source, request summary, UTC retrieval time with a
timezone enforced) and reports every rejected record with its index and the field it was missing; a
non-http(s) URL is rejected rather than stored as where a listing came from.

**What the framework refuses to do.** It does not populate the fields that would require reading the
source's prose: eligibility scope, degree disciplines, experience ranges and compensation all stay unset,
because guessing them is how an app starts asserting eligibility nobody stated. Those need a reviewed
parser per source. It also carries no bypass: I first added a `quality_gate_passed` parameter to
`AdapterRegistry.execute` for testability, then measured what the override does - `enabled_discovery_sources(
quality_gate_passed=True)` returns `('jobicy',)` - and removed it. The whole "nothing runs" property
therefore rests on exactly one constant, and a test asserts both the recorded emptiness and the measured
`jobicy` consequence, so a future change that moves either one says so loudly.

**Tests.** 61 in `tests/test_adapters.py` plus 6 for the command; the full suite is **1006 OK (13
skipped)**. Teeth checks: ignoring the gate failed 8 tests, allowing an undeclared capability 1, removing
the request cap 2, allowing a self-contradicting response 2, removing URL validation 2, allowing
submission capability 1, retrying non-transient failures 3.

**Still outstanding.** No adapter exists, live discovery stays disabled, and the framework has never made
a network request - the fixtures are the only adapters in the repository. Compensation is still not
compared anywhere in matching (no field exists), and a deployed, always-on worker is still not built.

## 2026-10-15 — Follow-ups reach the window and the schedule

**What changed.** The Follow-ups tab shows every recorded day (overdue first, then due today, then what is
coming), with a picker and note field, a Clear button that asks first, and a calendar export that writes
an `.ics` beside whatever the person chooses. A third scheduled task, `follow-up-digest`, runs at 09:00
Asia/Kolkata, reads the recorded days and reports the due and overdue ones in the run history - and
changes nothing else. `--follow-ups` and `--calendar-to PATH` do the same two things from a terminal.

**Three decisions worth keeping.** (1) The tab's summary distinguishes "no follow-ups recorded" from
"none are due yet": the first usually means the feature has not been used, the second means it is working.
(2) The digest derives its day from the *occurrence*, not from `datetime.now()`, so a run claimed after a
laptop was asleep still reports the day it was due for - and a test asserts the same occurrence expressed
in two zones gives the same report. (3) The digest's detail carries its count of unnamed reminders
*before* the names, because run details are capped at 300 characters: a marker that only appeared at the
end of a long line would be the part that got cut off, leaving a short line that reads like a short list.

**A reminder is not an event.** No handler, tab action or command writes an activity entry, moves a
status, or sets `candidate_confirmed`; the digest test asserts the activity log is still empty afterwards,
and the tab test asserts the tracker status is untouched after setting a day.

**Third default task, and the test churn it caused.** Seeding now creates three tasks, so every assertion
that named two had to be updated - honestly, not weakened: counts now derive from `default_tasks()`, and
the desktop tests take their expected ids from `DEFAULT_TASK_IDS`, so the next task added does not need a
dozen hand edits. One new test asserts that every registered handler kind is either scheduled for a fresh
installation or has to be explained, because "a kind nobody schedules is a feature nobody gets".

**Teeth checks.** Reading the day from the wall clock failed 1 test; everything counting as due failed 1
(after strengthening the test to assert a not-yet-due reminder is not *named*); a not-yet-due list
reported as a refusal failed 2; hiding the count of unnamed reminders failed 1; dropping the missing
database refusal failed 1; exporting without asking before replacing a file failed 1; silently substituting
today for a mistyped day failed 1.

**Evidence.** Full suite 1077 tests OK (13 skip without `pypdf`); the checklist in
`research/local-alpha-manual-smoke-test-checklist-2026-10-14.md` gained steps 42-52 for the new surfaces,
all unchecked, because no real GUI session has been run for them.

## 2026-10-15 — JSON export and import: a file you can carry, and the rules that keep it honest

**What changed.** The JSON document gained a `format_version`, and reading one back is implemented.
`career_agent/importer.py` now owns both directions: `export_document`/`write_export` produce the file,
`read_export` validates the whole document before anything is written, `plan_import` is read-only and
returns what would be added, linked, kept or refused, and `apply_import` recomputes that plan rather than
trusting the caller, so the promise shown and the writes made cannot diverge. The window's *Data safety*
tab has **Import an exported file (JSON)** beside the export button, which shows the plan in a dialog and
asks before applying it; `--export-to PATH` and `--import-from PATH` do the same from a terminal, the
second a dry run until `--yes` is added. `import.written`, `import.refused` and `import.failed` joined the
event log.

**The import is deliberately not a restore.** A backup moves the whole file; an import must survive
landing in a database that already holds work. So: a listing already present is linked through the same
`duplicate_key` the rest of the app uses and keeps its first-seen time, a stored profile is kept and the
plan says so, and every application record arrives at `discovered`.

**The bug that made the last rule real.** `_profile_from_record` had been written against remembered
field names — `work_authorizations` (plural, a tuple) instead of `work_authorization` and
`preferred_locations` as a `frozenset` — and it coerced a missing `experience_years` to `0.0`, which
states a fact the file did not carry. The round trip only reproduced the source profile after both were
corrected; the parser now reads the stored names and leaves a missing number missing.

**A status is never asserted.** My first pass had the tracker refused entirely when the file's status was
later than `discovered`, which contradicted the promise that the application itself imports. The rule is
now: the record is always created at `discovered` (the status `store.save_tracker` requires for a new
record), and only the *status* is reported as not imported. The store's initial-status rule was not
weakened for imports, and a test walks the real transition path
(`discovered → shortlisted → prepared → awaiting_user → submission_attempted → submitted_unverified →
confirmed`) to prove a confirmed record in a file cannot arrive confirmed here.

**Two API facts the tests taught.** `store.save_tracker` refuses a new record at any status other than
`discovered`, and `prepared → submission_attempted` is not a legal edge — `awaiting_user` sits between
them. Also, `recorded_at` is the writing database's clock, so the round-trip test compares activity on
(kind, occurred_on, detail) rather than on a timestamp two databases will never agree about.

**Teeth checks.** Four deliberate mutations of the new rules, each reverted and verified by hash
(`66612e3f…`): adopting the file's status → 1 failure + 2 errors; treating an already-stored listing as
new → 3 failures; letting the file's profile replace the stored one → 2 failures; accepting any format
version → 1 failure. Every one was caught by the tests that exist for it.

**Evidence.** `tests/test_importer.py` 23 OK, `tests/test_cli_export_import.py` 11 OK, six new handler
tests in `tests/test_desktop_handlers.py` (206 OK), full suite 1117 tests OK (13 skip without `pypdf`).
A real command-line round trip on `/tmp/roundtrip` produced `Wrote 1 listing(s) and the profile to
/tmp/roundtrip/out.json`, a dry run that listed its plan and then `Nothing was written. Run the same
command with --yes to apply this plan.`, an apply that reported
`Import complete: added 1 listing(s); imported the profile; created 1 application record(s); recorded 1
follow-up day(s); appended 1 activity entr(ies).`, and a second apply that reported
`left 1 already-stored listing(s) as they were`. A second export to the same path refused with status 2.
The manual checklist gained the window-import and round-trip steps; nothing in them is marked passed,
because no real GUI session has been run for them.

## 2026-10-15 — A reminder that survived the status change (defect found while writing the import tests)

**The defect.** `ApplicationTracker.transition` built the next record from `status` and `evidence` alone,
and `CareerStore.save_tracker` wrote the whole row - including `follow_up_on` and `follow_up_note` - from
the object it was handed. So the most ordinary update in the app, moving an application's status, wrote the
person's reminder back to NULL. Reproduced against a file-backed database before any fix: save
`with_follow_up(2026-10-20, note="chase the reply")`, call `.transition(SHORTLISTED)`, save, re-read - both
columns empty. Nothing reported it, and the Follow-ups tab would simply have shown one fewer reminder.

**Two fixes, because one layer was not enough.** (1) The domain: `transition` now carries the plan, so the
record it returns is the whole record rather than the status portion of it. (2) The storage boundary, which
is where the guarantee belongs: `save_tracker` takes `follow_up: FollowUpWrite = FollowUpWrite.KEEP`, and
under `KEEP` the stored day and note are written back exactly as they are. A save is only allowed to touch
the plan when it says so, with a new `store.set_follow_up`/`store.clear_follow_up` pair as the intended way
to set or remove one. A plan that *differs* from the stored one under `KEEP` raises instead of winning
quietly: the caller either meant it or did not notice the stored reminder, and guessing would lose or
invent a day.

**Why the boundary rule, and not only the domain fix.** A tracker built from a status alone carries no day,
and there is no way for a store to tell "I did not mention the reminder" from "clear the reminder" - which
is exactly how the defect happened. Making the default mean "this save is not about the reminder" removes
the whole class of bug for every future caller, including the import path, which sets a plan on a freshly
created record. The plan is written by one method per direction, and the event line records which of the two
happened (`follow_up_write=keep|write`).

**The third place it would have bitten.** The status dialog rebuilt the record from `get_tracker_raw` and
passed only status, evidence and confirmation into the constructor - so even with the domain fix, the object
it transitioned from would have had no plan and the write would have cleared it. That read now goes through
`get_tracker`, which is the parsed record (and still reports an unrecognised status as
`TrackerStatusError` through the same refusal path the Mac smoke test exercised).

**Teeth checks.** Two mutations, both caught, both reverted and verified by hash
(`core.py be7242f7…`, `store.py d1a575e8…`): dropping the plan again in `transition` → 2 failures (the
record-equality test and the stored-row agreement test); making `save_tracker` write the plan
unconditionally → 4 failures across the store and desktop suites, including the window-path regression.

**Evidence.** Full suite 1133 tests OK (13 skip without `pypdf`), 12 new store tests, 2 new domain tests, 2
new window-handler tests. The store tests cover: the plan surviving a plain status change and a conditional
(`expected=...`) write, the transitioned object equalling the stored row, a fresh record keeping a plan set
through `with_follow_up`, a differing plan under `KEEP` being refused and changing nothing, explicit
replacement, `clear_follow_up` leaving the status alone, clearing a record that has no plan, refusing a plan
for a listing with no application record, refusing a mistyped day at the boundary, and the event line naming
the plan it left alone.

## 2026-10-15 — Preparation items and interview rounds: the work around an application

**What changed.** Schema 5 adds two tables and nothing else: `application_preparation` (a checklist item
with a kind, an optional day, and the moment the person said it was done) and `interview_round` (which
round, the day it is planned for, how it is held, the candidate's own reading of how it went, notes).
`career_agent/preparation.py` is pure and turns those records plus the follow-up days into one ordered list;
the window shows it as a **Next actions** tab with buttons that write only the record they name, and
`--next-actions` and `--interviews` print it from a terminal, read-only. Both tables are deleted with their
listing, and the migration was exercised on a real v4 file: the pre-upgrade snapshot was written beside it,
the version moved to 5, every existing row survived, the new tables came up empty and were usable at once.

**Three rules, each enforced where it belongs.** (1) Neither record can move an application on: the item
has no status column, the round has no route to the tracker, and a store test asserts the tracker row is
byte-identical after adding, completing, recording, updating and deleting each of them. (2) "Done" is the
person's statement, so a second completion is refused rather than re-timestamped - the same rule the
tracker's no-op path follows - and the same open title/kind cannot be added twice, while a finished one can
be repeated. (3) An interview outcome is the candidate's reading: the vocabulary is awaiting / went well /
unclear / went poorly / did not go ahead, and a test refuses `passed`, `rejected`, `offer`, `hired` and
`accepted`, because an application cannot know an employer's decision and a field offering one would put
words in an employer's mouth.

**One design correction while writing the tests.** `InterviewRound.has_happened` counted a round scheduled
for *today* as past, so a summary would have buried the interview that is about to happen. It is replaced by
`is_ahead`/`is_past`, and the tab's rows read "today" rather than "0 day(s) ago". The name was wrong as well
as the boundary: the record cannot know whether a round took place - only `outcome` says that, and only the
person fills it in.

**The action list is a decision, not a sort.** Overdue (most overdue first), then today, then the coming
week; inside a group an interview outranks a follow-up, which outranks a preparation item, because an
appointment is on somebody else's clock, a chase is a promise, and your own checklist is yours to arrange.
Undated items are listed (open work with no day is still work), items beyond the window are counted in one
line rather than hidden, and two runs over the same data print the same list - each of those is a test.

**Teeth checks.** Three mutations, each caught and reverted with the file hashes verified
(`preparation.py c65e9d2e…`, `store.py 0abfaaf0…`): keeping finished items on the list → 4 failures;
completing an item also moving the application to shortlisted → 2 failures; making the kind order
irrelevant → 1 failure.

**Evidence.** Full suite 1210 tests OK (13 skip without `pypdf`); 31 new tests in `tests/test_preparation.py`,
31 in `tests/test_store.py` (including the v4→v5 upgrade on a file that already holds records), and 16
window-handler tests in `tests/test_desktop_handlers.py`. The new checklist steps 61-67 are unchecked: no
real GUI session has been run for them.


## 2026-10-15 — The candidate's own employment and education, as records rather than a summary

**What changed.** Schema 6 adds `candidate_work_history` and `candidate_education`, and both the window
and the command line can now read and write them. The profile stays what it was - a summary the person
holds in their head - and the record underneath it is a list that grows over a career:

- `career_agent/core.py`: `WorkHistoryEntry` (employer, job title, employment type, start date, optional
  end date, explicit `is_current`, optional note) and `EducationEntry` (institution, qualification,
  optional discipline, optional start date, optional completion date, `is_ongoing`), both frozen with
  validation in `__post_init__`. `months_covered(today=...)` and the module-level `months_covered_by` are
  the only duration arithmetic in the app.
- `career_agent/store.py`: `_migration_to_v6`, the two tables with one ordering index each, eleven methods
  (add/list/get/update/delete for both kinds plus `profile_record_counts`), and a `delete_profile` that now
  deletes both tables in the same transaction and records `work_history=N education=M` in its event.
- `career_agent/event_log.py`: `history.work_added|work_updated|work_deleted|education_added|
  education_updated|education_deleted`.
- `career_agent/importer.py`: `EXPORT_FORMAT_VERSION = 2`, `READABLE_FORMAT_VERSIONS = (1, 2)`, top-level
  `work_history` and `education` arrays, and an all-or-nothing rule for importing history.
- `career_agent/desktop.py`: the **Work history & study** tab (two forms, two lists, add/load/save/delete
  buttons that act on the selected row) and a `_delete_profile` that asks the store how many records the
  profile has before naming them in the confirmation.
- `career_agent/__main__.py`: `--history` (read-only), `--add-role`, `--add-study` and their options.

**Three decisions worth keeping.**

- **The profile form did not grow.** The window is fixed at `1120x760` and the profile form is the summary
  a person keeps in mind; eleven more rows would have made both worse. Employment and education got their
  own tab, which is what the record is: a list you edit row by row.
- **`months_covered_by` is a union, not a sum.** Adding up job durations overstates exactly the people with
  concurrent, part-time or unfinished roles, and it overstates them in the flattering direction. The
  reported figure is the set of months in which at least one dated or current role was running, a role with
  no recorded end contributes nothing, and the sentence next to it says so. It is never written into the
  profile's own `experience_years`, which the person controls.
- **History imports are all or nothing.** If the store already holds any history record, the file's records
  are not imported at all and the plan says how many were kept. Merging two half-CVs would produce a list
  that describes nobody, and a person who wants the file's copy can delete the stored records first - which
  the message says.

**Bugs found and fixed while building it.**

- The month arithmetic counted the starting day itself as a finished month (`+1` when `end.day >=
  start.day`), so a role that began and ended on the same day read as one month of work. The correct rule
  subtracts one when the day of the month has not been reached; the domain test now pins the boundary from
  both sides.
- The desktop summary line and the CLI report claimed overlapping roles were "counted once each" while the
  code summed each role's own duration. That is a false claim in a user-facing sentence, so the union
  function was written and both front ends now use it; the CLI test asserts the arithmetic for two
  overlapping roles (18 months, not 24).
- `_history_entry` passed `padx` twice through a conditional `**` expansion, which raised `TypeError` on the
  first real call. Rewritten as two explicit values. (A reminder that the stub widget layer catches nonsense
  the real Tk would have accepted at run time.)
- Two `ImportPlan` field-name typos (`kept_local_history_counts`, and a field list edit that silently
  dropped `kept_local_profile`) meant `describe()` raised rather than printing the plan. Both were found by
  running the code, not by reading it.

**Verified by running, not by reading.** `tests.test_store` builds a database at version 5 by patching
`_MIGRATIONS[:5]`, fills every table that predates this increment, reopens it with the current build, and
asserts the version moved to 6, every existing row is unchanged, the new tables are empty, and both are
immediately writable on the upgraded file. `tests.test_importer` round-trips records with every field,
imports a version 1 document (no history arrays, nothing invented), refuses version 99 naming the numbers it
reads, and asserts that a batch of bad records writes no history at all. `tests.test_backup` asserts a
version 6 file without the new tables is *refused*, which is the check that would have caught the schema
table contract not being updated. `tests.test_cli_history` runs the real `main()` and asserts the refusals
exit non-zero with the option named and the database unchanged. `tests.test_desktop_handlers` covers the tab
handlers (add, load, save, delete, refusals, an unreadable stored value, a closed database), the tab's own
presence in the notebook through the real `__init__`, and that deleting a profile names the counts.

**Test reading.** 1339 tests, `OK (skipped=13)` - up from 1210 before this increment. The version literals
that had to move (`SCHEMA_VERSION == 6` in two places, `format_version == 2` in three) were moved with the
reason left in the message, and no assertion was weakened.


## 2026-10-15 — What the records add up to, and the four rules that keep the numbers honest

**What changed.** `career_agent/analytics.py` is a new pure module: it takes the listings, the tracker rows,
the per-listing activity and the interview rounds plus a `today` the caller supplies, and returns a report of
counts, rates, two timings and one period comparison. Both front ends use it - `python -m career_agent
--analytics`, and the summary line plus **Progress report** button under the **Application tracker** list - so
the window and the terminal cannot disagree about a person's own numbers. The store gained `list_trackers()`
(one query for the whole table, the counterpart to `list_follow_up_trackers()`), and the three tracker readers
now share one `_decode_tracker`, so a stored status this build cannot name is refused identically wherever it
is read.

**The four rules, and why they are code rather than care.** A report like this is easy to write and easy to
make dishonest, so each rule is a constant with a test that fails if it moves:

- **Every rate names its denominator.** The label is stored on the `Rate` and printed in the same line, so a
  percentage cannot be separated from what it was computed over.
- **A denominator below `MIN_RATE_DENOMINATOR` (5) produces no rate at all.** The counts print, the rate does
  not, and the floor is named as the reason. Over three applications one email moves a percentage by thirty
  points; that is a description of noise presented as a trend.
- **Unavailable is not zero.** `UNAVAILABLE_METRICS` lists what this schema cannot observe - an offer above
  all, since no column, field or status can hold one - with the reason. Printing `0 offers` would read as
  "you received none", which is the opposite of "nothing here can know".
- **A zero denominator is not a rate of zero, and a real zero is not withheld.** `0 of 0` says nothing was
  measured; `0 of 20` is a genuine, important fact and prints as `0%`.

**What the timings refuse.** The reply median uses only dates the person recorded, over the pairs that have
both. A reply that exists only as a status change has no date - the tracker records when the row was saved
here, not the day the employer wrote - so it is counted as unpaired and the reason is printed rather than the
sample being quietly shrunk or a zero-day gap invented. A reply dated before the application is excluded as a
typing mistake, not counted as a negative gap. Below three pairs nothing is reported, with the count.

**The period comparison.** The last 90 days against the 90 before, only when both windows hold five recorded
applications; otherwise both counts print and the comparison is withheld with the reason, including how many
applications could not be placed in either window because no application date was recorded. An entirely empty
database returns no comparison at all rather than a `0 of 0 against 0 of 0` sentence, and the report says
there is nothing to compare.

**Bugs found and fixed while building it.**

- My first `_rate` gave the zero-denominator case the same "floor of 5 not reached (denominator is 0)" text
  as a thin denominator, which is technically true and reads as though a measurement was attempted.
  Zero now has its own sentence, and a test pins both.
- `_periods` returned a comparison even with nothing recorded, so the report's "Nothing to compare" branch
  was unreachable and an empty database got a 0-of-0 comparison. Fixed at the source rather than by editing
  the sentence.
- The median's empty case read "only 0 application(s) have both dates written down", which is the wrong
  sentence for "none yet". Reworded, with a test for the empty case separately from the thin case.
- `count_line`/`line_containing` in the tests were initially written from intent: the count and the rate for
  the same label share their wording, so a helper that matched either would have let a broken rate pass. The
  helpers now separate them.

**Verified by running, not by reading.** 46 tests in `tests/test_analytics.py` cover the counting routes (an
activity entry, a status that implies sending, both at once counted once, a shortlisted application *not*
counted), the rate floor on both sides of the boundary, the unavailable-versus-zero distinction as printed
text, the caveats, the medians (including the out-of-order pair and the status-only reply), the window
boundaries on the first and last day of each window, and the store-backed gathering path. 7 more tests cover
`--analytics` (counts, the withheld floor, the offers statement, no database created by a read-only command,
nothing changed, the parser refusing two actions at once) and 8 cover the desktop surface (the summary line,
the dialog's title/size/bindings/contents, that Escape closes it, that it writes nothing, and that an
unreadable stored status refuses the report instead of drawing one). Mutation-checked: removing the rate
floor, the zero-denominator sentence, the offers statement, the caveats or the empty-database guard each fails
the suite.

**Test reading.** 1399 tests, `OK (skipped=13)` - 1339 before this increment. No assertion was weakened.

## 2026-10-15 — Email and calendar: the interface, with every path to a side effect switched off

**What changed.** `career_agent/integrations.py` is a new module holding the email and calendar contract, and it
deliberately contains no provider. `EmailDraft` (subject, body, the application it belongs to, a recipient only
if one is supplied, a purpose, a stable operation id) and `CalendarEventRequest` (title, day, and - only when
the person records them from an invitation - a start time, a duration and an IANA timezone name, plus notes)
are values. `preview_email` and `preview_event` turn one into the lines a person would read, list what is
*missing* separately from what is merely imprecise, and have no side effect of any kind: no ledger entry, no
attempt, no write. Performing anything goes through an `Integration`: the default is a `DisabledIntegration`
that refuses every request with an explicit `disabled` result naming the reason and what to do instead, and
nothing in configuration, the environment, a stored value or a command selects anything else. The one
implementation that performs anything is `LocalMockIntegration`, which records operations in a
`IntegrationLedger` (memory, or an owner-only file) and contacts nothing - and it is chosen only by naming it
(tests, or `--mock-ledger PATH`).

**Why the shape, and not a provider behind a flag.** A real provider needs credentials, an authorization
decision and provider-side idempotency, in that order, and each is a decision with evidence behind it rather
than a setting. `ENABLEMENT_REQUIREMENTS` holds the seven conditions as data, printed by
`--integration-status`: an approved provider and scope; credentials in the OS keyring with a documented way to
revoke them; provider-side idempotency (a client cannot prove that a request it never saw answered did not
arrive - without the provider refusing the repeat, the honest answer is "unknown", and this app will not
guess); a data-minimization statement written before the first request; an off-by-default switch with a
visible state; failure handling that cannot lie; and a provider-level test path, because a local mock proves
this module's bookkeeping and not a provider's behaviour.

**Idempotency is structural, not a flag.** An operation id is a SHA-256 digest of the operation's own content
(no timestamp: a clock would make every attempt a new operation, which is exactly the bug idempotency keys
exist to prevent), so the same draft asked for twice produces the same id and is reported as `duplicate`
rather than performed again. A failed attempt is **not** recorded as done, so `dispatch_with_retry` may retry
with the same key and still perform the operation once. A key already recorded against a *different* kind of
operation is refused (`invalid`, naming the recorded kind) rather than treated as a repeat, because one key
must mean one operation. A ledger that exists and cannot be read raises instead of being treated as empty:
"I could not read the record of what I have already done" and "I have done nothing" are the same thing only in
a system that is about to do it twice. A ledger write that fails is reported as `failed`, not `completed`.

**Nothing is inferred.** A draft with no address is a valid draft with one missing fact, printed as
`To: NOT SUPPLIED - this application never guesses an address`; nothing derives an address from an employer's
name. An event with no time is an all-day entry with the gap stated (`Not recorded, and not invented`), never a
guessed appointment; a time requires a duration and a named timezone, a timezone without a time is refused
rather than reinterpreted, a zone-aware `time` is refused so the two cannot disagree, and a name the platform's
tz database does not know is refused too (an unknown zone would otherwise travel to a provider or move the
event).

**What a person can actually do with it.** On the reminders tab: **Preview the calendar export** (the events
the local `.ics` file would hold, read-only) and **Draft a follow-up email** (built from the recorded employer,
role, follow-up day and note). On the command line: `--integration-status`, `--preview-calendar-export`,
`--draft-follow-up LISTING_ID [--recipient ADDRESS] [--save-draft PATH]`, and `--record-follow-up LISTING_ID`
(disabled with no mock named). The two new dialogs reuse one extracted `_open_read_only_dialog` shell that the
progress report now also uses, so there is one read-only surface rather than three; the window's geometry and
its widget choices are unchanged. The "listing is gone" branch of the reminder lookup is defensive and is
tested against a store double, because the store's foreign key makes that state unreachable through its own
API - the test says so rather than pretending it is a live path.

**Reuse, not a second exporter.** `career_agent/followups.py` gained `event_uid(reminder)` and
`event_summary(reminder)`, and the `.ics` writer now calls them; the export preview calls the same two, so a
preview cannot promise a different event from the one the file will hold. The export itself is unchanged:
all-day entries, no `ATTENDEE`, no `ORGANIZER`, no URLs, owner-only file, and an existing file is never
replaced silently.

**Verified by running, not by reading.** 82 tests in `tests/test_integrations.py` (draft and event validation
including every refusal for a bad address, a duration without a time, a zone-aware time and an unknown
timezone; preview accuracy and purity; the disabled default for both kinds of operation; the mock's success,
duplicate, failure, retry, collision and ledger-write-failure paths; ledger round trip, damage and version
refusal; the export preview against the real `.ics` document; and the operation id's stability across three
fresh interpreters with different hash seeds). 35 more in `tests/test_cli_integrations.py` (status creates no
database; the preview writes nothing; the draft is printed in full, saved owner-only when asked, refused over
an existing file, and refused for an unknown listing, a missing follow-up day and a bad address; the mock
records once and reports a repeat; the timed path and each of its refusals; every orphan option refused with
the reason; and the database byte-for-byte unchanged, with no new file, after the read-only commands). 10 more
cover the two desktop surfaces and their refusals, and the no-network suite now runs the whole
draft-and-record sequence in an interpreter where creating a socket raises, so "contacts nothing" is a property
of the process rather than a promise in a docstring. Mutation-checked with fifteen mutations (a space allowed
inside an address, the recipient dropped from the identity, the disabled integration reporting success, the
mock forgetting what it did, a ledger write failure reported as success, a missing timezone, a preview claiming
a message would be sent, a retry repeating an invalid request, a guessed recipient, a preview disagreeing with
the export, an ignored orphan option, a command performing without a named mock, a time read as UTC, a draft
produced for an application with no day, and a preview writing the file it previews): every one failed the
suite.

**Test reading.** 1527 tests, `OK (skipped=13)` - 1399 before this increment. No assertion was weakened.

## 2026-10-15 — Release rehearsal: the doctor cleared a file the app refused, and the policy that was missing

**The rehearsal found a real defect, which is the point of doing it.** An installed wheel was built, installed
into a clean environment, and driven from a folder under `/tmp` with synthetic records. The first failure probe
built a database whose tracker row held a status no version of the app knows (the shape a hand-edited file or a
file from a later build has). Every read path refused that record — and `--doctor` answered
**"No problems found" with exit 0** on the same file, because it checked structure (schema version, required
tables, foreign keys, counts) and never decoded a row. `--analytics` and `--follow-ups` exited **3** — the
"unexpected failure" status — with a sanitised start-up note written to `logs/startup-diagnostics.log`, while
`--history` (which does not read tracker rows) exited 0. A report that clears a file the application refuses is
worse than no report: it is the one place a person would look before trusting their data.

**The fix has one mechanism, not two.** `store.unreadable_stored_records(path)` decodes every stored record of
every kind through the **same decoder functions the read paths use** — the profile, listing, tracker, activity,
preparation, interview, work-history, education, scheduled-task, task-run and lease decoders became
`@staticmethod`s taking a row, which is what makes them callable without a store, and the profile payload
decoder was extracted from `get_profile` so the rules exist once. The sweep runs over a `mode=ro` connection,
skips tables a file does not have (an older file simply has fewer), caps at 5000 rows per table, reuses the
backup module's read-only URI helper (renamed `read_only_uri`, no second implementation), and returns one
plain sentence per unreadable record naming the table and the record id — never its contents. `--doctor` runs it
only when the structural check is clean *and* the file records the current schema: a file recording an older
schema is reported by version, not decoded, because the doctor promises never to change a file and therefore
cannot migrate it, and decoding an old layout could report problems the upgrade itself resolves. The doctor
prints exactly that instead of implying the data is fine. On the read side, `--analytics`, `--follow-ups`,
`--next-actions`, `--interviews`, `--history` and `--worker-status` now answer an unreadable record with
`_refuse_unreadable_records`: one sanitised sentence, exit status `2` (`EXIT_REFUSED`), no half-printed report,
and a pointer at `--doctor`.

**Measured before and after, on the same file.** `--doctor`: exit 0 → exit 1 naming
`application_tracker`, record `'j1'`. `--analytics`: exit 3 → exit 2 with `REFUSED: this database holds a
record this version cannot read: …`. `--follow-ups`: exit 3 → exit 2. `--history`: 0 → 0, unchanged, because it
never reads that record. The database's SHA-256 was identical before and after every command. Reverting
`career_agent/store.py` and `career_agent/__main__.py` to `dc20325` makes the new test file fail
(`ImportError: cannot import name 'unreadable_stored_records'`), so the regression tests fail before the fix.
The export path needed no change and was verified not to need one: `--export-to` on the damaged database exits
0, writes the record with `"status_recognised": false`, and keeps the follow-up day and note — an export must
always be able to take the data out.

**The rehearsal that produced a real schema upgrade.** An earlier attempt was invalid and is recorded as such:
the copied file already recorded `user_version = 6`, so nothing migrated. A genuine schema-5 database was built
by running this build's real migration steps and stopping at 5, then opened by the installed CLI. Result:
`user_version` 6, a verified snapshot taken first (`old2.sqlite3.backup-20261015T070533Z`, 110592 bytes,
`user_version 5`, 10 tables — the pre-upgrade file), and the listing, tracker (status, follow-up day and note)
and activity entry all intact, with the same table set the current build declares. Row survival after an
upgrade is now proven against a file the previous version really wrote, not against a current file with the
version number lowered.

**One probe's expectation was wrong, and that is recorded too.** A database file at mode `444` was expected to
produce a write refusal. It does not: opening a database re-applies owner-only permissions
(`_restrict_to_owner`, best-effort, POSIX-only), so the file was observed changing from `-r--r--r--` to
`-rw-------` on a read-only command and writes then succeed. That is a deliberate privacy measure with a
documented side effect, not a defect; the write-refusal paths that exist are around *targets* (a backup or
export destination) and around damaged files, and a read-only *filesystem* was not available on this machine to
exercise the remaining case.

**The written policy that was missing piece 4.** The README now states what a version number promises about
data: no stability promise while no build is released, a newer build opens an older database, an older build
refuses a newer one, an existing file is verified-copied before the first step changes it, steps are additive
and transactional with no separate migration command, backups are accepted across versions and upgraded when
opened, export documents carry `format_version` and import never overwrites a stored record, an unreadable
record is reported rather than repaired, and there is no downgrade path. `architecture.md`, `prd.md`,
`rules.md` and `design.md` were updated in the same increment, and `rules.md` gained the invariant this
rehearsal earned: a diagnostic must not clear data the app refuses to read.

**CI coverage audit.** The matrix is now the floor and the newest interpreter that has actually run
(`3.10`–`3.13`) rather than an open-ended claim, and the installed-package job runs on `3.10` and `3.13` — a
wheel or console script that only works on the interpreter that built it is exactly what installing from a
checkout hides. A new test, `tests/test_documented_commands.py`, reads every `--flag` this README and the
manual checklist tell a person to run (30 in the README, 20 in the checklist) and looks it up in the real
`--help` output, so a documented command that no longer exists fails the suite; its own guards are tested too
(a planted unknown flag must be reported). No 3.14 leg exists: `uv python install 3.13` and a direct download
from the `python-build-standalone` releases were both refused by this sandbox's network policy
(`UnknownIssuer` / `SSL_ERROR_SYSCALL`), so the newest leg can only be proven by CI, and the audit says so.

**Evidence, and what is still missing.** `research/release-readiness-audit-2026-10-15.md` holds the commands
and observed output for install, `--doctor`, backup, restore, export, import, the schema upgrade, eleven
failure paths, the defect with its before/after exit codes, the CI audit and the reproducibility recipe —
repository half only. Still open: per-platform launch artefacts and signing, the interpreter-bundling decision,
the per-operating-system half of the rehearsal (macOS and Windows), real GUI coverage, a 3.14 and a
macOS/Windows CI leg, the read-only-filesystem case, and branch protection/release archives. Nothing here is a
production-readiness claim.

**Test reading.** 1550 tests, `OK (skipped=13)` — 12 of the skips need the optional `pypdf` extra (absent
here) and one runs only where the project is installed (a source checkout carries no metadata); 1532 before
this increment (1527 plus the five documented-command tests). Before the ignored `build/` and
`ai_career_agent.egg-info/` directories from an earlier in-checkout build were removed, that packaging test
ran instead of skipping (which is why an intermediate run read `skipped=12`). No assertion was
weakened. Mutation checks re-run on the new code: reverting the two source files was executed and fails the new
tests, and the before/after exit codes were measured on the same database.

## 2026-10-15 — Manual acceptance run: 98 steps on a headless machine, four defects, and the refusal that now reaches every command

**The campaign was executed, not planned.** The 98-step manual checklist was run on the only machine available
(a headless Linux sandbox, CPython 3.11.2, no display, no Tkinter, no `sqlite3` CLI). 22 numbered steps passed,
76 are blocked for a named missing capability (almost all for the absent window), none failed, and six of the
seven preconditions passed. The per-step state is in the checklist itself and the full record — command,
observed result, status, and the before/after evidence for every fix — is
[`research/local-alpha-manual-acceptance-run-2026-10-15.md`](research/local-alpha-manual-acceptance-run-2026-10-15.md).
Headless execution of a *window* checklist was possible because most steps have two halves: what the window
does, and what the record must hold afterwards. The record half was driven through the same store and domain
layer the dialogs use, in 48 assertions that each printed what they observed.

**Four defects, all found by executing the steps rather than by reading the code.**

1. **The progress report counted a round nobody had attended as one whose outcome was recorded.** A round saved
   for tomorrow stores `outcome='awaiting'`, and the count was `record.outcome is not None` under the label
   "your own reading of the round, saved after it happened" — so a future interview appeared to have been read
   back to itself. The count now excludes `awaiting`; the regression test fails before the fix with `3` where
   the label promises `2`.
2. **A readable database holding one unreadable record was reported as a start-up that failed.** `--doctor`,
   `--analytics`, `--follow-ups` and friends had been given the refusal in the release rehearsal, but
   `--preview-calendar-export`, `--calendar-to`, `--draft-follow-up` and `--record-follow-up` still reached the
   top-level handler: `COULD NOT START … the application did not start`, exit **3**, and a start-up note written
   beside the data for a start-up that never happened. The handler now refuses a database it cannot read for
   every command (one sentence, exit 2, no note) and describes a start-up only when the window is what was
   asked for — the window is the only thing that really starts.
3. **An import into such a database wrote part of the file and then refused, saying nothing had been written.**
   Row counts on a refused `--import-from … --yes`: profile 0→1, employment 0→3, education 0→2, and the stored
   listing's payload rewritten, behind the sentence "Nothing was changed or repaired". The import now sweeps
   its target read-only with the same decoder sweep the doctor uses and refuses before it plans or applies
   anything; the same command now leaves every row and the file's bytes untouched.
4. **A refusal claimed a draft had been written when nothing was on disk.** `--draft-follow-up j1
   --mock-ledger …` with no recipient printed "the draft was written but not performed (invalid)" and exited 2
   with no file anywhere. One sentence served two states; it now names what happened (no file written, or the
   path that was written), and the test that had pinned the old wording could not see the missing file.

**The rule was extended rather than patched per command.** `rules.md`'s diagnostic invariant now says the
refusal reaches every command and that a command which writes checks first; `design.md` states that the window
is the only start-up path; `architecture.md` records the import's pre-write sweep; the README's unreadable-record
bullet says an import into such a database is refused before it writes anything. The release-readiness audit
cross-references the run in its defect and coverage sections, and its flag count was corrected (21, not 20).

**What the run could not do, and said so.** Every window step is BLOCKED: no display, no Tkinter, no X tooling.
The résumé steps are blocked twice over (no window, and the optional `pypdf` extra is absent; the 12 PDF tests
skip for the same reason). A real calendar application and a mail client are not present, so "import the `.ics`
into your calendar" and "watch for a mail window" are unrun. macOS, Windows and Python 3.14 remain unexecuted and
unclaimed. Nothing was simulated: an assertion that a unit test covers a related rule is never reported as the
step passing.

**Test reading.** 1559 tests, `OK (skipped=13)` — 12 need the optional `pypdf` extra and one runs only where
the project is installed. Nine tests were added here (seven covering the damaged-record and refusal cases, one for the
analytics count, one for the saved-draft message), and each fix has a fail-before check that was actually
executed: reverting the source hunk makes the new test fail (exit 3 vs 2
for defect 2, `6` failures for the command group, `3` vs `2` for the analytics count, and the file claim for
defect 4). The job-source CSV was not touched (`input_sha256 0356b093…`, 83 records), `compileall` is clean,
`SOURCE_QUALITY_GATE_PASSED` stays `False` and `enabled_discovery_sources()` stays empty. The wheel built and
installed during the run was byte-different across two builds of the same tree while every entry's *content*
was identical: a wheel hash identifies one build, not one revision.

## 2026-10-15 — The desktop harness grows to ten workflows: follow-ups, the scheduler and data safety

**Eleven commits turned a two-workflow harness into ten.** `scripts/desktop_acceptance.py` now drives the real
`CareerAgentApp` through A (profile), B (the two job URLs), C (eligibility safety), D (tracker transitions and
analytics), E (export/import and its refusals), G (work history and study), H (follow-up reminders and the
combined next-action list), I (the scheduler tab), J (data safety: backup, validation and restore) and F
(cleanup) — **76 checks**, each workflow in its own disposable database, each step pressing the window's own
widgets through Tk's command dispatch and answering the dialogs a person would answer, with the file chooser
and every confirmation recorded so a refusal can be checked for being *explained*, not merely performed. The
script declares its own check count and the runner compares the two, so a step that stops running fails the job
with "a check that does not run is not a pass".

**Two defects only a real display could show, both with fail-before regression tests.** D17: the Follow-ups tab
lists only applications that already hold a follow-up day, so its list is empty exactly when a person records
the first one — and the button that sets the day read its subject from that empty list, so the first follow-up
day was unrecordable from anywhere in the window; fixed in `480dca1`, with H1–H2 recording an application's
first day from the tracker tab as the display-backed proof. The second: run `38758158210` failed H5 on all five
legs with `the fields still hold a day that was cleared`, because clearing a day rebuilds the reminder list,
real Tk fires `<<TreeviewSelect>>` on the rebuilt tree, and the handler refilled the fields from another tab's
selection; the binding now reads only the reminder list's own row, the acceptance step re-selects the row it
acts on exactly as a person does, and the fail-before check reproduced as `AssertionError: '2026-10-24' != ''`
(`0215413`). The stand-in tree could not have produced either: it re-inserts rows without firing the event, and
it never had an empty list to read a subject from.

**Verified on real windows, per leg, not by badge.** Run `38762008724` at `5b291a7a`: 12/12 jobs, and all five
display-backed legs report `RESULT: PASS — 76 checks passed` — Linux under Xvfb (`1280x1024 pixels from X11R0`,
`Tk 8.6`) and Windows 2025 / macOS 26 on CPython 3.10 and 3.13 (`1024x768 pixels from Windows 10.0 26100 Win64`
and `… from CG0.0 Apple AppKit 2685.7`), with the suite at 1648 tests `OK` (13, 20, 37 and 44 skipped by
interpreter and platform). Workflow I's first green run was `38761595835` at `d12c2bcb` (68 checks, 12/12) and
the 60-check run `38759670194` at `0215413` was green before that. The local stand-in development run reports
76 passed with `RESULT: BLOCKED` and exit 2, and is never used as evidence of window behaviour; a machine with
no display runs the real entry point and exits 2 with `RESULT: BLOCKED`.

**Test reading.** 1648 tests, `OK (skipped=13)` locally — 12 skips need the optional `pypdf` extra and one runs
only where the project is installed; `skipped=37` on Windows and `skipped=20` on macOS 3.10 are the platform
differences the CI legs report. `compileall` is clean, `declared_step_count()` reads 76, and the checklist
carries 35 "Automated coverage" lines (ten of them in part). No assertion was weakened and no test family was
skipped to reach green: the two acceptance failures above were fixed in the product and in the check, and the
earlier timing-sensitive store case was fixed by pinning the write clock rather than by relaxing the comparison.

**What the run still cannot say.** No human has opened this window on any platform. Layout and clipping at
normal and smaller sizes, dialog wording and clarity, keyboard-only navigation and focus order, screen-reader
behaviour, real mouse-driven flows and native feel are unverified and stay BLOCKED in the checklist, whose
verdicts are unchanged at 22 PASS / 76 BLOCKED / 0 FAIL with no box ticked. macOS, Windows and Python 3.14 GUI
behaviour has only ever been exercised by a script on a runner, never by a person, and installers, signing and
notarisation remain unimplemented and unclaimed. `SOURCE_QUALITY_GATE_PASSED` stays `False`,
`enabled_discovery_sources()` stays `()`, the job-source CSV is untouched (`input_sha256 0356b093…`, 83
records), and no generated database or backup is committed.

## 2026-10-16 — Closing the coverage gaps, correcting the metadata, and handing the window to a person

**The five gaps the previous report left open are closed, and none of them by adding another acceptance
workflow.** The milestone's harness stays where it was: ten workflows, 76 checks, `declared_step_count()` 76.
Four claims that had been recorded as "covered in part" now have a verified assertion at the level where the
claim actually lives, and one was already covered:

1. **The activity history survives clearing a follow-up day.** `clear_follow_up`'s confirmation says the
   application's history stays as it is, and nothing tested that. `FollowUpTabTests::
   test_clearing_a_follow_up_asks_first_and_keeps_the_application` now records two history entries, compares
   them (day, kind, detail - not `recorded_at`, this application's own clock) after a *declined* answer and
   again after an accepted one, and asserts the fixture really has two entries so the comparison cannot be
   vacuous. A temporary mutation that also deleted the activity rows made it fail; the file was restored.
2. **The default tasks' names, times and timezone.** Already covered, at two levels, and now said so plainly:
   `test_handlers.py::DefaultTaskTests::test_the_defaults_are_the_product_cadence_and_a_daily_backup` (all
   three ids in order, `00:00, 12:00`, `23:30`, the digest cadence, every task in `Asia/Kolkata`) and the
   window's own cells in `SchedulerTabTests::test_the_tab_lists_the_tasks_and_says_no_worker_holds_the_lease`,
   which now asserts `00:00, 12:00`, `23:30`, **`09:00`** and the zone for every row. The literal `09:00` is
   the part the module test cannot catch: it compares the digest's times against the same constant the product
   uses, so redefining the constant to `08:00` left that test green and turned this one red - which is exactly
   what a mutation check is for. Both were run.
3. **Next-action row ordering.** Already covered; no test added. `test_preparation.py::ActionTests` holds
   most-overdue-first, the kind tie-break on the same day, and independence from input order;
   `NextActionsTabTests::test_the_list_shows_the_three_kinds_with_the_record_each_row_names` holds the exact
   row order across all three kinds.
4. **The calendar preview's per-event line.** The dialog drew a line the tests only partly pinned. The whole
   line is now asserted as the checklist documents it:
   `2026-10-17: Follow up: AI Intern at Example Inc  [follow-up-j1-20261017@ai-career-agent.local]`. Dropping
   the day prefix in `CalendarExportPlan.describe` made it fail. Escape/Return closing the dialog remains
   unasserted and is now named as the remaining half rather than implied by "partial".
5. **The complete email-draft field set, and the refusal with no reminder selected.** The field set was
   already asserted (`IntegrationSurfaceTests::test_the_draft_carries_the_stored_context_and_states_that_
   nothing_was_sent`: subject, a body line, `To: NOT SUPPLIED`, `Status: DRAFT ONLY`, `Missing, and not
   guessed:`, the operation id, "Nothing was sent and nothing was created"); the refusal was not, so
   `test_the_draft_refuses_with_nothing_selected_and_opens_nothing` now drives the button with no row chosen
   and asserts it explains itself, opens no dialog and no chooser, and claims nothing in the status line.
   Making the handler return silently made it fail.

**Stale metadata corrected.** `scripts/desktop_acceptance.py`'s module docstring said six workflows and listed
A, B, C, D, E, G, F; it now describes all ten, including H, I and J, in the order they run. `phases.md` said
1550 tests (now 1651) and listed a macOS/Windows CI leg as missing, which it no longer is; it also said the
activity log had no desktop surface and that the version/data-compatibility policy was unwritten, both of
which stopped being true when those shipped, and it described reminders as not implemented when the recorded
day, the digest handler and the local export all exist - what is missing there is an OS notification, and the
text now says that. `phases.md` gained an audited **phase status table** (Phase 0 complete, Phases 1, 1B, 2, 5
and 7 partially complete, Phases 3 and 6 blocked, Phases 4 and 8 not started) with the evidence beside each,
plus a **Status:** line under every phase heading, and the four-way distinction the whole document turns on:
implemented ≠ automated-tested ≠ human-accepted ≠ release-ready. The checklist's historical "third follow-up"
subsection is now labelled as the 38-check record it is, the acceptance-run file says which sections quote
which revision's totals, and the five partly-covered steps now name the level of every half (workflow on a
display-backed runner, module test, or handler-stub test) - with the one genuinely unasserted half, whether
some other window control could connect an account, still called out as such.

**A human desktop acceptance handoff, deliberately short.** `research/human-desktop-acceptance-handoff-2026-10-16.md`
is a run-book, not a second checklist: prerequisites, how to run the two automated entry points first (and what
they do *not* establish), the thirteen areas with the checklist step numbers that carry each, expected results,
what to capture, the per-area human-only judgement, the per-platform table, and where to write the result - in
the checklist, in its existing style, without deleting the lines already there and without ticking a box for a
step nobody executed. It covers launch/shutdown, layout and resizing down to the documented `900x600` minimum,
profile/job/eligibility/tracker, the first follow-up and its restart behaviour, next-action ordering, scheduler
pause/resume and truthful worker status, backup/refusals/restore, résumé import review and cancellation, file
chooser and confirmation wording, keyboard-only navigation and focus, screen-reader behaviour (an area with no
coverage anywhere, so it is named as such), real mouse and native feel, and macOS/Windows/Linux specifics.

**Evidence and invariants.** Focused tests for the four touched tests plus their classes: 41 tests, `OK`;
mutation checks in four places, each failed as designed and each file restored byte-identical to its backup.
Full suite `Ran 1651 tests ... OK (skipped=13)` (one test added by this increment, and two more by the concurrent commit below); `compileall` clean; `declared_step_count()` 76; the acceptance
harness under the stand-in reports 76 passed with `RESULT: BLOCKED` and exit 2 and is never evidence; on this
machine the real entry point exits 2 with `RESULT: BLOCKED` because there is no display and no Tkinter - no
human run is claimed anywhere. `SOURCE_QUALITY_GATE_PASSED` is `False`, `enabled_discovery_sources()` is `()`,
the job-source CSV audit reports `input_sha256 0356b093ded3917c0fa9ba3aa9f12a682caaf81df7c49a6b042950d66a08f414`
and 83 records, and no database, backup or credential is committed.

**A concurrent commit landed mid-increment, and its documentation caught up with it.** While this increment
was being verified, the repository owner pushed `d16f8cf` ("fix(preparation): prioritize most overdue actions
across kinds") onto the same branch, on top of `1f1e50c`. It was fast-forwarded here rather than fought with:
it changes the ordering rule so that within the overdue group the *oldest promise comes first whatever its
kind*, with the kind breaking same-day ties, and adds two tests
(`test_most_overdue_action_wins_across_kinds`, `test_kind_priority_breaks_ties_for_overdue_actions`). Three
places still described the old rule and now describe the new one - `preparation.py`'s module docstring and the
`_KIND_ORDER` comment (which now says the kind decides *ties*, not the whole order), `__main__.py`'s
`run_next_actions` docstring, the README's Next-actions paragraph and `architecture.md`'s ordering sentence -
and the checklist's ordering citation for step 61 names the age-first rule and the two new tests. Only words
changed: no behaviour, no test, and no assertion was touched to accommodate the commit, and the full suite is
green at 1651 tests after it.

**2026-10-16 - the final commit's CI found a real defect, and it was a defect in the tests (D18).** Run 38781575276 at
`e69e5836` came back red on two jobs: the Windows legs at Python 3.10 and 3.13, three failures each - the two
`scheduled-backup` tests in `SchedulerTabTests` and the suite-wide connection-leak test, which re-runs the whole
suite in a child process and so reported the same two failures again. Every other job on that commit was green,
including both macOS legs and all four interpreter legs. The annotations gave it away: `AssertionError:
'follow-up-digest' != 'daily-backup'` and an empty attempt list for the task the test was about.

**The cause was the hour, not the product.** A claim takes the earliest due task (`ORDER BY next_run_at, task_id
LIMIT 1`), both tests seeded the three default tasks from the real clock and paused only `scheduled-discovery`,
and the three default slots straddle the boundary: seeded before 23:30 Asia/Kolkata the 23:30 backup is the
earliest due occurrence, seeded after it the backup rolls to the next evening while the already-due 09:00 digest
becomes the earliest one left. The job timestamps show exactly that - the four `unit-tests` legs finished by
23:28:10 IST and the two macOS legs by 23:29:51, while the Windows legs ran 23:27:09 → 23:37:29 and 23:38:02 and
were the only legs still inside the suite when the clock crossed 23:30. Classification: **test defect**. The
product's behaviour is correct and documented; the test asserted a fact about the arrangement that only held for
part of the day.

**What was done.** The shared helper became `keep_only(task_id)`, which pauses every default task *except* the
one under test, so the claim can only land where the test wants it; both tests keep every assertion they had, and
no product line changed. The regression test
`SchedulerTabTests.test_the_claim_a_test_makes_is_the_task_it_asked_for_at_any_hour` seeds at a fixed
`2026-10-16 23:38 Asia/Kolkata` - the window the Windows legs were in - asserts that the digest genuinely is due
before the backup (so it cannot stop exercising the ambiguous hour without saying so), removes the other tasks
from contention and requires the claimed run to belong to `daily-backup`. Fail-before proof: with the old
one-competitor pause restored the new test fails with `- follow-up-digest / + daily-backup`, the same shape as
the CI annotation; with the fix it passes, at any hour, because the seed no longer reads the clock. The fix and
test are `6e92c9b`; the suite moved 1651 → 1652 and the totals in `phases.md` were re-grepped to match. D18 is
written up in `research/cross-platform-desktop-ci-evidence-2026-10-15.md` section 16 with the table of job
times, the two annotations verbatim, the classification and what it does not establish (no window coverage, no
human acceptance, and the window steps stay BLOCKED).

**Resolved the same night.** The run for the fix and its write-up,
[38784018777](https://github.com/rajaryan1111/ai-career-agent/actions/runs/38784018777) at `eba6b4f2`, is
**green 12/12** with the suite at **1652 tests on every leg** and the five display-backed legs at
`RESULT: PASS — 76 checks passed` (plus `14 checks passed` on the window-lifecycle step). It started at 23:44
IST and the Windows legs ran to 23:53 and 23:56 - the same window that had broken the run three hours of suite
earlier in the evening - so the fix is confirmed at the hour of the failure, not just at the hour it was written.
`main` is still `127244b5`; the branch also carries the small docs cross-reference from the release-readiness
audit to `phases.md`'s audited phase table and to the handoff.

**2026-10-16, second session of the day - one defect found by probing, one Phase 5 gap closed, and the
metadata swept (D19).** The audit that opened this session changed nothing, and the first real finding came
from *probing* the command line rather than reading it: `--restore-from` given the live database itself
reported `Restored <the same path>`, replaced the file with a copy of itself and left an automatic snapshot
beside it - exit 0 for a no-op, and a file nobody asked for. The likeliest way to reach it is pasting back the
path the product's own refusal advice prints. It is written up as **D19** in
`research/cross-platform-desktop-ci-evidence-2026-10-15.md` section 17, with the exact output, the changed
digest, and the classification (product defect, data-safety path). The fix refuses before validating or
staging anything, comparing device and inode so a hard link or symlinked folder is caught as well as a
respellable path, and falls back to resolved paths where the platform will not stat; a real backup whose
contents happen to match is still restored. Two regression tests fail before it - `BackupError not raised` at
the module level (same path, differently spelled path, hard link; byte-identical database, no snapshot, no
staging file) and `0 != 2` on the command line - and pass after. Commit `a29d2d4`.

**The Phase 5 gap that needed no deployment: what the schedule walked past while nothing ran.** A read-only
report (`worker.missed_occurrences`) now answers that question, and `WorkerStatus.describe()` prints it, so
the window's Background tasks tab and `--worker-status` show the same thing without a second implementation.
The definition is exact and was corrected once during the work: a due occurrence of the task's own schedule
with no attempt row, no retry owed, and not the instant the next claim will take. The last exclusion is the
whole point - `plan_after_run` plans the next run from the moment the previous one finished, so every other
occurrence between then and now is one nothing will come back to, while the occurrence at `next_run_at` is
merely overdue and stays named "(due now)". A first attempt at the horizon (everything strictly before
`next_run_at`) turned out to be vacuous - it can never match, because the scheduler always plans the next
occurrence after the last finish - and was replaced after a scenario test showed 0 reported where 3 were
skipped. The window is bounded to seven days, cut off at each task's creation, and the report says which
window it used. Nothing catches up on a missed occurrence, and the surface says so; that is why phase 5's
laptop-off exit criterion is still unmet. Coverage: eight module tests (including a read-only proof over the
lease, the run table and the event log), the tab-level test, the command-line test, and **one new check in
workflow I** (I9) that drives it through a real window and real widgets on the five display-backed legs -
which moved the harness from 76 to **77 declared checks**. I1-I8 were deliberately left numbered as they
were, so every earlier citation still names the same check. Commit `e6f01dd`; full suite 1665 tests, OK.

**Metadata swept, and what was already correct.** The acceptance script's docstring already described ten
workflows (the "six workflows" report was stale before this session), and the checklist and handoff were
already current on the phase table. What actually moved: `phases.md` (1665 tests, 77 checks, and a Phase 5 row
that now distinguishes *reporting* a missed occurrence from *running* it), `README.md` and `design.md` (77
checks, and the scheduler clause names the report), the manual checklist (a new dated update plus step 51's
coverage line for I9; verdicts unchanged at 22 PASS / 76 BLOCKED / 0 FAIL, **no box ticked**, and the earlier
76-check citations left standing as the historical records they are), the handoff (77 checks, and area F now
says the summary names both the overdue occurrence and what was missed), and a new **`research/README.md`**
index that says, for every artefact in that folder, what question it answers and whether it is current
guidance or dated evidence - linked from `README.md` and from the handoff.

**2026-10-16, same session - a second defect from the same probing pass (D20).** `--poll-seconds` took any
`float` the parser would accept, and `WorkerSettings` validated its three numeric fields with `value <= 0` -
which is False for NaN and for positive infinity, so both passed. Measured on the primitives rather than
assumed: `threading.Event().wait(nan)` returns immediately (the loop's sleep becomes a no-op, so a mistyped
flag turns the worker into a poll loop with no delay), and `wait(inf)` raises `OverflowError: timestamp too
large to convert`, which escaped the worker loop *after* it had started and reached the top level as an
"unexpected failure" - exit 3 plus a startup-diagnostics note for one mis-typed number. The tracker, the
matcher and the form validation already refuse non-finite numbers; the worker settings were the one place
that did not.

The fix requires a finite positive value, names finiteness in the refusal, and catches
`WorkerConfigurationError` in `run_worker` so a bad flag value is the documented refusal (exit 2, message, no
diagnostics note) rather than an unexpected failure; the option's help text says what is accepted, and a
merely unusual finite value (0.5) still works. Regression tests at both levels:
`SettingsTests::test_a_non_finite_interval_is_refused_rather_than_run_with` (nine `WorkerConfigurationError
not raised` subtest failures before the fix) and
`WorkerCommandTests::test_an_interval_the_worker_cannot_run_with_is_refused_before_it_starts` (exit 2, a
REFUSED line naming finiteness, and **no stdout at all** - the strong form of "nothing was started" - for
nan, inf, 0 and -1, plus a parser-level refusal for -inf). The command-line fail-before was measured directly
because the unfixed code starts the worker: nan ran until a six-second cap killed it (exit 124), inf exited 3.
D20 is written up in `research/cross-platform-desktop-ci-evidence-2026-10-15.md` section 19, including what it
does not establish (a finite but absurd interval such as 1e9 is the operator's own choice and is left alone).
**2026-10-16, same session - the threat model, and a repeat-idempotence rehearsal.** Phase 2's remaining
documented task was the threat model, and it was genuinely absent (the release-readiness audit does not
contain one). It is now `research/threat-model-2026-10-16.md`: assets, six adversary classes, one control per
threat with the test or code that enforces it, what is explicitly out of scope, and six residual risks named
honestly - no encryption at rest, no single erase-everything command (records can each be deleted from the
window and the database file can be removed, but backups, pre-restore snapshots, logs, exports, calendars and
the mock ledger have to be found and deleted by hand), synchronised folders, exports that travel, Windows ACL
semantics this project has no evidence about, and no release/upgrade policy. It is linked from `README.md`'s
safety principles, from the Phase 2 line in `phases.md`, and from the research index.

Writing it required a rehearsal rather than a claim, so a repeat-idempotence battery ran on disposable
synthetic databases: file modes (every file the app writes came out `600`); the store refusing a new record
that does not start at `discovered`, and one claiming confirmation without a recorded transition (both with
"Nothing was saved"); backup twice (second `REFUSED`, never overwritten); restore twice from the same backup
(both exit 0, snapshots named `-2` so they do not collide); seed twice (three tasks untouched); import twice
(second adds nothing, the stored record wins, listings stay at 1); import without `--yes` (writes nothing);
import with no database present (refused); `--calendar-to` twice (second refused); `--save-draft` twice
(second refused); `--record-follow-up --mock-ledger` twice (second reports `[duplicate]`, ledger stays at one
operation); `--record-follow-up` without a mock (`REFUSED … (disabled)`); identical `--add-role` twice (second
refused by name, one row). No defect came out of the battery - the pattern it verifies is already the
product's, and the point of running it was to be able to say so with commands and exit codes rather than by
reading code. Phase 2 remains **Partially complete**: encryption at rest and a release/upgrade policy are
still open, and the threat model claims nothing about either.
**2026-10-16, third session of the day - Phase 4 started, and it found six extractor defects.** Phase 4 was the
one phase marked "Not started", and its first task was a privacy-safe, human-reviewed cross-industry
evaluation set. That now exists: `research/cross-industry-evaluation-set-2026-10-16.json` holds seven
occupation groups (software/data, VLSI/embedded, mechanical, civil, product design, business/financial
analysis, laboratory/biotech), each with one synthetic profile, three synthetic listings carrying an explicit
review order (which a reviewer should open first), and one synthetic resume text with the values a reviewer
says are stated plainly in it. `scripts/evaluate_cross_industry.py` measures the engine and the extractor
against it and exits non-zero if any hard-eligibility violation is measured;
`tests/test_cross_industry_evaluation.py` keeps the corpus well-formed, synthetic and fully ranked.

The first run measured 7/7 agreement with the reviewed order, zero hard-eligibility violations, and 22/22
stated values extracted - but it got there only after finding six real defects, all of them invisible to the
existing suite because its fixtures are written in the vocabulary the code already knew:

* **D21** - `WORK AUTHORIZATION` and `COUNTRY` as headings (value beneath) were not in the section
  vocabulary, so their wording landed in the **skills** proposal, marked confident; one of them put the
  country itself there, a value that feeds eligibility, offered as a skill. Fixed by adding the two headings
  this module already proposes fields for.
* **D22** - the degree vocabulary was engineering/science/commerce only: `B.Des in Design, 2026` proposed no
  degree and no graduation year. Design, architecture, medical, pharmacy, law, education and hospitality
  qualifications were all invisible. Widened by discipline, with the abbreviations that are also English
  words requiring their full stop so prose cannot be read as a qualification.
* **D23** - an abbreviation's own full stop hid the discipline: `B.Sc. in Biotechnology, 2026` proposed
  "B.Sc" while the same line without the stop proposed "Biotechnology". The leftover stop is now stripped.
* **D24** - only `technical/key/core/...` before the word "skills" opened a skills section, so `LABORATORY
  SKILLS` was not a heading at all and the document was reported as having no skills heading.
* **D25** - the skills token filter allowed `+#.()` but not `&`, so the mechanical resume's headline skill
  `GD&T` was silently dropped (and a finance resume's `M&A` would have been). A dropped skill is worse than
  a noisy one: the person reviews what is proposed and never sees what was discarded.
* the sixth, smaller: `B.B.A.` was recognised while `B.A.` and `M.A.` were not.

Each has a regression test that fails before the fix and passes after. Every number the run reports is
reported with its denominator, and the eight values that sit outside what the extractor claims (country is
read only from a labelled line; that rule is deliberate because country decides eligibility) are counted
separately from the accuracy figure rather than into it, with rule checks passing in both directions so a
silent widening cannot go unnoticed. Phase 4 moves from **Not started** to **Partially complete**: the
corpus is synthetic and small, so the thresholds stay *measured*, not achieved for the product.
**2026-10-16, same session - the Phase 2 deletion task, closed for every file the app can derive.** Phase 2's
task list names "data export/deletion"; export existed and per-record deletion existed, but there was no way
to make the application's own data go away - a gap the threat model had recorded. `career_agent/erasure.py`
now plans the removal (database, SQLite sidecars, the snapshots and staged restores beside it, and the two
logs it writes) without creating anything or opening a database, and `--forget-local-data` shows that plan by
default and performs it only with `--yes`. What it cannot derive - a backup, export, `.ics`, draft or ledger
at a path the person chose - it reports instead of pretending to have handled; a folder or symbolic link as
the database path is refused rather than followed, and every failure is reported with its reason rather than
counted as success.

Writing the tests found two more product gaps in the same pass: a folder passed as `--database` was planned
around instead of refused (it would have deleted the logs beside it), and `--yes` on its own was silently
ignored - the program went on to open the window, which is not what someone typing `--yes` asked for. Both
are fixed, the second by an orphan-option refusal in the same style as the existing ones. The module also
corrected one of my own test expectations: a symlinked candidate is refused at *planning* time, so it appears
in the "left alone" report rather than in the failure list - which is the safer behaviour and is now what the
test asserts. `tests/test_cli_forget.py` (15 tests) covers the plan, the preview writing nothing, the delete
removing exactly the derived files while a foreign file survives, idempotence, and each refusal. Full suite
1702 tests, OK (skipped=13).
**2026-10-16, same session - Python 3.14 measured, and one more unbounded read closed.** The release-readiness
audit had recorded the gap in its own words ("Still missing: a CI leg for Python 3.14"), with the reason the
development environment cannot close it (`uv python install 3.14` and a direct download are both blocked by
the sandbox's network policy). It was closed in CI instead: `unit-tests (3.14)` now runs the suite,
`compileall` and the CSV audit - run 38804198342 at `709242b` reports `Ran 1702 tests ... OK (skipped=13)` and
the expected CSV hash prefix - and the installed-package leg moved from 3.13 to 3.14, so the wheel is built,
installed into a clean environment and run from outside the checkout on the newest claimed interpreter (run
38805511543 at `791f9ed`, green). README, `phases.md`, the audit's coverage table and the handoff's
interpreter requirement all now say 3.10-3.14, and the CI evidence register gained section 20 with both legs,
their results and their run ids. What is still not measured is stated rather than glossed: no 3.14 leg on
Windows or macOS, and the display-backed desktop harness remains 3.10/3.13.

The same pass closed the last unbounded local read: the mock ledger answers "has this already been
performed?", and it was read whole before being parsed - the same shape as the export importer's gap. It is
now bounded at 16 MB with the check taken from a `stat` first, and the refusal is fail-closed in the module's
own words ("Nothing was performed, because this application cannot establish what it has already done and
will not risk doing it twice"). Measured: refusing a 20 MB file allocates 1.1 KB (tracemalloc peak). Tests
cover the refusal (with the limit patched small, asserting the shipped 16 MB value as well) and that an
ordinary ledger still loads and reports its one operation. Full suite 1708 tests, OK (skipped=13).

**2026-10-16, same session - five more defects, all found by pointing the program at something it did not
expect.** Each was reproduced outside the suite first, refused by a test that fails before the fix, and
fixed in the smallest place that owns the rule. D26: `--forget-local-data` promised to refuse anything
"reached through a symbolic link", but the `logs` folder it derives from the database path was not checked -
with that folder replaced by a link, it deleted a same-named file out of somebody else's folder. D27/D28: the
database's name was interpolated into a glob pattern unescaped, so a database called `my[1].sqlite3` made the
snapshot pattern match `my1.sqlite3.backup-...` (listed and deleted by the removal command) while missing its
own snapshots - and `automatic_backup_snapshots`, which `MAX_AUTOMATIC_SNAPSHOTS` counts, therefore reported
zero however many were there, so the cap that stops a schedule filling the disk could never be reached.
D29: an import replaced a stored listing whose identifier it reused. Linking is decided by
`core.duplicate_key`, the row is keyed by `listing_id` and `save_job` is an upsert by that id, so a record
that matched no stored identity but reused a stored identifier was planned as new and then overwrote the
stored listing - employer, URL and availability - while the command printed "Nothing was replaced". D30:
every read-only command guarded itself with `database.exists()`, and an empty file exists: SQLite reads a
zero-byte file as a valid empty database and writes the schema into it, so six reports plus the two
read-only exports wrote 126,976 bytes and an `application.log` beside a file the person had named, then
printed a line saying nothing had changed. All five are written up in the threat model's section 8.4 with
their regression tests (`tests/test_cli_forget.py`, `tests/test_handlers.py`, `tests/test_importer.py`,
`tests/test_config.py`), the README gained the two rules a person needs to know (an identifier a file
reuses is refused rather than written; an empty file is not a database this app will create), and the
window harness check for a damaged import now asserts the promise rather than the old heading. Full suite
1718 tests, OK (skipped=13); compileall clean. CI run 38807628488 at `a57e86c` is the first in which all
thirteen jobs are green together, which is what makes "3.14 is measured" a statement about the whole matrix
(`unit-tests (3.14)`: `Ran 1709 tests ... OK (skipped=13)`, `csv: 0356b093ded3...`; `Installed package
(3.14)` green in the same run).

**2026-10-16, this session — the release rehearsal found D31: a refused command still printed its title.** The
rehearsal in `scratch/release_rehearsal.sh` builds an artifact from a clean `git archive` of one revision and
installs it into disposable environments; the failure battery (`scratch/failure_probes.sh`) then walks the
installed command over a data folder that cannot be created, a read-only folder, `--database` pointing at a
directory, a corrupt file, a truncated file, a PDF résumé without `pypdf`, and a missing target folder. Every
failure path already behaved: exit 2 or 3, one plain sentence, "nothing was changed", no traceback. What the
battery showed with the two streams **separated** was that the refusal was not the only thing the command
wrote - `--analytics` on a text file named like a database put `AI Career Agent 0.1.0 · progress from this
database (…, local day)` on stdout and then refused on stderr, and eleven other commands did the same (twelve
of the fourteen that open the database; `--backup-to`, `--seed-tasks` and `--worker` were already correct,
the last one because D20 fixed it). So `career-agent --analytics > report.txt` left a report file that was a
title and nothing else, and a pipeline got a title beside a status saying the command had failed. It also
contradicted a rule already in `design.md` ("nothing half-printed") and `rules.md`.

The fix writes each heading once the data it reports on has been read (reports after the records are decoded,
`--export-to`/`--calendar-to` after the file is written, `--import-from` once the plan exists, the draft and
the calendar-event commands once the reminder resolves); no message, exit status or report body changed, and
the commands that explain a refusal about the *request* still print what they explain. `tests/test_damaged_records.py`
gained `DATABASE_COMMANDS` and `test_no_command_announces_itself_before_refusing_a_file_it_cannot_read` (all
fourteen commands against a corrupt file: exit 2, a `REFUSED` line, **empty stdout**, no file written, no byte
changed, and `--import-from` is handed a real `importer.write_export` document so it cannot pass for the wrong
reason), the shared `assert_refused_cleanly` helper now requires empty stdout, and the three refusing reports
assert it too. One existing check was replaced because it could not fail: it searched for `Progress from this
database` in the last line of stdout, and the heading spells that word lower-case - it only errored once the
stream became empty. Fail-before measured with the fix reverted: `Ran 30 … FAILED (failures=22)`, six methods.
Full suite 1719 tests, OK (skipped=13 in a clean checkout); `compileall` clean. D31 is section 21 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`; `rules.md`, `design.md`, `README.md`,
`research/README.md` and `phases.md` carry the rule and the new counts.

**A build left `ai_career_agent.egg-info/` in the checkout.** `python -m build` writes setuptools metadata into
the source tree, and on the next suite run `importlib.metadata.version("ai-career-agent")` found it, so
`test_packaging`'s installed-only test ran (and passed) instead of skipping and the suite reported
`skipped=12` where a clean checkout reports 13. It is gitignored, so nothing was committed, but the rehearsal
script now exports the tracked revision with `git archive` into `/tmp` before building, and the folder was
removed: a checkout that is also a build directory is not the state any measurement should be taken in.

**2026-10-16, this session — workflow K's first real-display results found D32: content drawn outside its
tab.** CI run `38814625351` at `dd92918` came back 10/13 jobs green, and the three jobs that failed are the
three that had never had layout measured on them before: the Linux display-backed smoke job (K1 at 900x600 and
K2 at 1120x760) and all four cross-platform legs (K3 on macOS, K2/K3 on Windows). The numbers were the
diagnosis: on Linux the **Work history & study** tab's employment entry sat 117 px past the tab's right edge
and the education form's widgets ~174 px past it, while `Next actions`' *Delete the selected record* had been
squeezed from 200x28 to 29x28 and `Follow-ups`' *Export to a calendar file* from 181x28 to 13x28; on Windows
and macOS the same tab overflowed *downwards* (28-43 px), because the one tab whose content grows with a career
was the one tab built without a scrolling area. The cause was mechanical: two `fill=X` forms in four grid
columns with no `columnconfigure`, so nothing could shrink, and four- and six-button rows packed into one line
each. The fix extracts the read-only dialogs' canvas into a shared `_scrollable_body(parent)`, puts the history
tab's content in it with the inner frame pinned to the canvas width, gives both forms
`columnconfigure(1/3, weight=1)`, wraps labels at 830 px, and splits the long button rows in two on the history,
**Next actions** and **Follow-ups** tabs. No handler, record, wording or dialog changed.

Two of workflow K's own rules were wrong and were fixed with it, and this is the part worth remembering:
a widget inside a scrolling area was measured against the *tab*, so a working scrollable tab would have been
reported as clipped - measurement is now against the box a widget is drawn in (the tab, or the frame a
scrolling area scrolls), while content *wider* than that frame is still reported because a form that scrolls
down does not scroll sideways; and a window smaller than the minimum the application declares for itself was
judged anyway, which turned the macOS runners' screen (a 950x502 page for a 1400x900 request) into a layout
failure that no layout fix could ever clear. `judge_layout_at` now prints both sizes, states in one line that
layout was not judged and why, and judges at every size the application can be shown at - Linux (Xvfb
1280x1024) and Windows (a 1004x631 page) are judged. `_LAYOUT_TOLERANCE_PIXELS` is untouched at 1.
`tests/test_desktop_acceptance.py` gained `LayoutMeasurementTests` (8 tests) covering the measurement box, the
below-the-fold case, the wider-than-the-frame case, the declared-minimum predicate and the
report-rather-than-judge path. Full suite 1727 tests, OK (skipped=13); `compileall` clean; the stand-in
development run still performs all 82 checks and still exits 2. D32 is section 22 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`. The real-display verdict is the next CI run's K1,
K2 and K3: nothing here is evidence that the fixed layout fits on a screen, only that the rules that measure
it are right.

**Left open by that run, next in the register.** `SuiteConnectionLeakTests` - the child process that counts
never-closed SQLite connections - failed on all four macOS and Windows legs while being green on every Linux
leg and locally, and `gh run download` of the screenshot artifact fails with `EOF`, so the images cannot be
fetched through that route. Both are recorded in section 22 rather than left as footnotes.

**2026-10-16, this session — Phase 0 of the HR contact plan: an offline CSV preview that stores nothing.**
`planning/arena-task-phase-0-hr-contact-csv-import-2026-10-16.md` asked for an offline, local-first contact
CSV read/preview/cancel flow and allowed, in the same breath, shipping only a tested parser and preview
contract if persistence or UI integration could not be done safely in one increment. That is what was
shipped, and the difference is visible in the code rather than in a note: there is no write path at all.
`career_agent/contacts.py` (new) reads one file the person names with the standard library's `csv`,
handles a UTF-8 BOM, names a UTF-16 export as UTF-16, validates the header explicitly (blank names and two
names differing only in case are refused; the names are printed so the person can see what the file has),
matches a documented set of column spellings and reports every header it did not use, refuses two columns
that could be the email address instead of choosing, keeps every source string exactly as written while
computing the comparison key from the email alone (trim + case-fold), groups rows by that key, keeps
conflicting company labels in first-seen order without ever combining them, and flags `email-missing`,
`email-syntax`, `name-missing`, `duplicate-key` and `company-conflict` per row. Limits are 20 MB and 50,000
rows, refused rather than truncated. `--preview-contact-csv PATH` prints counts, flags and **line numbers**
and no cell value at all, opens no database (proved by pointing `--database` at a text file and getting exit
0), writes no file, and refuses with one sentence on stderr, exit 2 and an empty stdout - the D31 rule.
`tests/test_contacts.py`: 48 synthetic tests (6 classes) covering BOM, header validation, encodings, empty
and malformed files, the parser's own field limit, normalization, duplicate groups, company conflicts,
missing names, the five flags, counts that add up, the privacy assertions (no fixture value in the report,
in a refusal, or in a log; the root logger must record nothing at all), and file bytes/mtime/folder listing
unchanged after both a read and a refusal. Full suite 1775 tests, OK (skipped=13); compileall clean.
Written up in `research/hr-contact-csv-preview-2026-10-16.md`, registered in `research/README.md`, with a
`phases.md` row (1C, partially complete) and a `design.md` operational-state bullet; the README gained a
"Preview an HR contact list CSV" section that states what is checked, what a syntax flag is not, and what is
deliberately absent. Not claimed: the private exports' real headers have never been seen here, no real row
was read, "re-import creates no duplicates" is untestable while nothing is stored, and no GUI or manual
acceptance happened. Next smallest step: a store migration holding the key, the preserved strings, the
provenance and a suppression state that survives re-import, then the review tab built on `_scrollable_body`
with its steps in the desktop acceptance harness.


---

## Product Vision Decision — Resume-First Autonomous Career Agent (2026-10-16)

### Accepted product direction
The user wants AI Career Agent to operate as a personal career operations system. The intended workflow is: upload a resume, complete one-time onboarding and global authorization, then let the software autonomously perform routine permitted career tasks and continuously report what happened. This is not merely a job recommender or resume builder.

### Desired capabilities
- Understand resume/profile data: skills, education, projects, experience, graduation year, links and missing information.
- Discover relevant roles, including AI/ML Engineer, Applied AI Engineer, AI Engineer, Forward Deployed Engineer and internships, twice daily.
- Evaluate fit, eligibility, source freshness and deadlines with explanations and evidence.
- Tailor resumes, cover letters and screening responses without fabricating facts.
- Apply autonomously without per-job approval when saved global policy allows it and the source workflow is supported and permitted.
- Privately import the user's HR/company list; deduplicate and resolve conflicts; send personalized internship emails with the right resume from an explicitly authorized mailbox.
- Track applications, email sends, bounces, actual replies, interviews, rejections, offers and follow-ups with timestamps and evidence.
- Provide dashboard, run status, daily/weekly reports, notifications, pause/stop-all and revocable permissions.

### Autonomy contract
The user explicitly prefers no repeated permission prompts for routine applications. Implement one-time policy configuration followed by routine autonomy within configured limits. This does not authorize bypassing platform restrictions or required human attestations. Stop only the affected task when required facts are missing, contact records conflict, opt-out/suppression applies, a legal/sensitive answer cannot be verified, identity verification/CAPTCHA/OTP is required, the source disallows automation, or an external outcome is uncertain.

### Truthfulness and privacy invariants
- A draft is not a sent email; a click is not a confirmed application.
- Mark external actions complete only with evidence; use an unknown state and reconcile uncertain outcomes rather than blindly retrying.
- Never invent resume facts, eligibility, legal attestations or screening answers.
- Keep HR contact data private; never place it in public repository files, test fixtures, screenshots, logs or telemetry.
- No real external application/email side effects in tests.
- Use permitted, supported source integrations only; no anti-bot evasion or CAPTCHA/OTP bypass.
- Keep discovery, email and submission gates separate and fail-closed until each source/action passes its own feasibility, permission and test gate.
- Preserve existing store/migration, backup/restore and suppression history; inspect and reuse existing code before creating parallel abstractions.

### Current project boundary
This records product intent only. It does not imply live discovery, account connection, email sending or job submission is enabled. The existing source-quality gate remains disabled until implementation evidence supports changing it. Keep main and PR #2 untouched; work belongs on arena/351e052d-ai-career-agent unless the user explicitly changes that instruction.

### Documentation map
- prd.md: user outcome, requirements and trust contract.
- task.md: implementation backlog and verifiable acceptance tasks.
- architecture.md: components, state invariants and side-effect boundaries.
- design.md: onboarding, dashboard, status language, controls and failure UX.
- phases.md: staged delivery sequence and release gates.
- memory.md: durable product decisions, constraints and current-state caveats.

**2026-10-16, this session — D33: two tabs were still asking for more room than they had.**
The run that carried D32's fix (`38820361412` at `494d931`) measured workflow K again and failed it on the
Linux display-backed job and on both cross-platform legs, for two reasons D32's fix had not reached. The
first is a wrap width, not a height: seventeen labels drawn right across a tab were wrapped at a fixed 850, 900
or 1000 pixels, and the widest a tab can be at the window's own minimum size is narrower than that - the
notebook's page measured 878 pixels at 900x600, its padding takes 24 and a scrolling tab's scrollbar about 15
more, and Tk does not shrink text to fit: it keeps the text and draws the difference outside the tab. That is
what the two `Data safety` labels did, 23 and 31 pixels past the page's right edge. The second is the old
height problem, in the last place it was still possible: `Background tasks` was the one tab still built
outside a scrolling area, so its two six-row trees pushed the second tree 65 pixels below the Linux page and
38 below the macOS one, where nothing could scroll to it. The fix is one constant - `_TAB_TEXT_WRAP = 830`,
with the arithmetic and the run in the comment beside it - now the only wrap for text drawn across a tab (the
read-only line helpers inside dialogs and the label standing beside the progress report button keep their own
smaller numbers, for their own reasons), and `_build_scheduler` building its content into
`_scrollable_body(self.scheduler_tab)` exactly as the history tab does. `scripts/desktop_acceptance.py` was
not touched: its judging rule - measure against the tab, or against the frame a scrolling area scrolls - was
already what K measured with, and the section 22 write-up records why it reads that way. Three tests in
`tests/test_desktop_handlers.py::TabLayoutPolicyTests` pin what the window *asks for* without a display, and
they are labelled as the structural checks they are: any label across a tab must wrap within the narrowest tab
(against the window before this fix the walk reports `850.0 not less than or equal to 839 ... the 'Candidate
profile' tab`), the constant must equal that limit, and both scheduler trees must be inside something that
scrolls while a tab holding no growing content is still judged against itself. Written up as section 23 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`; `design.md` and the README now say which tabs
scroll and how wide a tab's text may ask to be; `phases.md` moves to 1778 tests. Still open on the same run:
`SuiteConnectionLeakTests` fails on all four macOS/Windows legs and is unchanged by this work. No local
machine here has a display, so the real-display verdict for this fix is the CI run on the commit that carries
it - the structural tests pin what the window asks for, not whether Tk had room.
**2026-10-16, this session — D34: the wrap had to fit the smallest page any platform gives, and two new tests errored on Windows.**
The run carrying D33 (`38822542797` at `7ca7879`) is the first whose Linux display-backed job passed workflow K
outright, and the first where `Background tasks` stopped being reported on any leg - so D33's fix is verified
where it was measured. The same run then reported two things about D33. First, K1 failed on both macOS legs on
two `Data safety` labels and nothing else: 832 px wide and 18 px past the page's right edge, 828 px and 14 px
past it, against a notebook page of **826x453** at the window's own declared minimum of 900x600 - where the
Linux page at the same window size is 878x483. One number taken from one platform cannot fit every page, so the
constant came down from 830 to **780** (826 - 24 of tab padding - 15 of a scrolling tab's scrollbar - a little
room for Tk's rounding of a wrapped line), and the test's own limit is now derived from the macOS page rather
than the Linux one so that a number measured on one platform cannot pass on the other. Second, two of D33's
three tests errored on both Windows legs: they closed the window's database in an `addCleanup`, which runs
after the temporary folder's own cleanup, and Windows will not delete a file another program holds open - the
same trap `StartupPathTests` documents, and invisible on Linux and macOS because POSIX unlinks regardless. Both
now take the window from a context manager that closes it inside the folder's block. Recorded as section 24 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`, with the section 23 wrap number marked superseded
rather than rewritten. Still open on this run: `SuiteConnectionLeakTests` on every macOS and Windows leg.
Verified locally: the three desktop suites together (376 tests, `OK`), the full suite 1778 tests
`OK (skipped=13)`, compileall clean.
**2026-10-16, this session — the matrix is fully green for the first time, and one register entry was wrong.**
Run `38823626117` at `3a88e6e` (the D34 commit) completed **13/13 jobs green**: every display-backed leg reports
`RESULT: PASS - 82 checks passed` with workflow K's K1/K2/K3 on Linux, macOS and Windows, `RESULT: PASS - 14
checks passed` for the smoke workflow, and `Ran 1778 tests ... OK` per leg (skips 13/20/39/46 by platform). So
D33 and D34 are verified where they were measured, not only structurally: the 780-pixel wrap fits macOS's 826
x453 page, the scrolling `Background tasks` tab holds, and Windows no longer errors on the two tests D34 fixed.
The same run also showed that a claim already written into the register was wrong: `SuiteConnectionLeakTests`
had been recorded in section 22 as a platform-specific connection leak on all four macOS/Windows legs, but that
test asserts the child suite exited zero *before* it looks at any counts, so what was seen on those legs was
workflow K failing inside the child run - the cascade section 4.1 had already described, reported by a test
whose name says "leak". No unclosed connection was ever demonstrated there, and the failure is green on all five
legs now that K passes. The correction is appended beside the original paragraph in section 22 (and pointed to
from section 23) rather than edited into it, and section 24 now carries the verification the run it describes
could not provide; `phases.md` cites the green run in the Phase 1 row. Nothing in
`tests/test_resource_lifecycle.py` was changed to bring that about.

**2026-10-16, this session — Phase 0 finished: a reviewed HR contact list is now stored, and what a re-import may not do (schema 7).**
`062a88c` could read a contact CSV offline and store nothing. The second half of that phase is in
`168ac31`: schema **7** adds `hr_contact` and `hr_contact_conflict` through the existing migration runner
(appended, additive, `IF NOT EXISTS`, so an interrupted step is completed by re-running it and a file that
never imports a list differs from version 6 only by two empty tables), the store gained the seven-method
contact API (`plan_contact_import`, `import_contacts`, `list_contacts`, `get_contact`,
`list_contact_conflicts`, `contact_record_counts`, `set_contact_suppression`), and the window gained a ninth
tab, **HR contacts**, inside a scrolling body. Three rules hold the feature together and each is asserted
rather than intended: one normaliser (`contacts.normalise_email_key`, called, never re-implemented, so the
review panel and the store cannot disagree about what "the same contact" means); one record per key however
many rows name it, with a re-import updating review metadata and never the address, the name or the company a
person can already see; and nothing merged silently - a later file that names a different non-empty name or
company has the stored value kept and the other recorded as evidence with its file and date, two rows inside
one file that disagree are recorded the same way with the first value in file order winning, and a
disagreement already stored is not recorded twice (which is what makes re-importing the same file ask the same
question once). `suppressed` is written by exactly one method and never by any import statement, which is why
a do-not-contact mark survives re-imports, contradictory files, a backup and a restore. Provenance is the
file's *name* and never its path; `contacts.imported` carries counts and an outcome and no contact value;
`ContactImportPlan.describe()` prints counts, field names and reasons for the same reason. The import is one
`BEGIN IMMEDIATE ... COMMIT` with `_roll_back_quietly()` on any exception, so a failure leaves nothing behind
and can never be reported as success, and the plan a person confirms is computed read-only from the database
they would be writing to. Covered by `tests/test_contacts_store.py` (39 tests, including zero-write assertions
against the connection's own `total_changes`), three schema tests in `tests/test_store.py` (a populated
version-6 file upgraded with its rows intact and its pre-upgrade copy still at version 6, the step re-run, and
a failing step rolled back with `SchemaMigrationError(target=7, from=6)`), the tab's handler tests in
`tests/test_desktop_handlers.py::ContactImportTabTests`, and workflow **L** in `scripts/desktop_acceptance.py`
(five checks through the real window on the five display-backed CI legs). The full suite is
`Ran 1832 tests ... OK (skipped=13)` locally and the acceptance harness declares **87** checks. Written up in
`research/hr-contact-import-persistence-and-review-ui-2026-10-16.md`, with the schema, the migration evidence,
the privacy boundaries and the named gaps; `phases.md`'s row 1C moves from "preview only" to the parse →
review → store increment, and `design.md`'s contact bullet describes the tab and what it refuses to do. The
smoke entry point now checks **nine** tabs. Nothing here matches a contact to a listing, drafts a message or
sends one, and `SOURCE_QUALITY_GATE_PASSED` is still `False` with `enabled_discovery_sources()` still empty.
Verified where the window actually is: run `38828908041` at `02962f6` completed **13/13 jobs green**, every
display-backed leg reporting `RESULT: PASS - 87 checks passed` (workflow L's L1-L5 `[ ok ]`, K4 and K5 `[ ok ]`,
and the focus walk reaching `HR contacts` in the same shape as `Jobs & eligibility`) and `Ran 1832 tests ...
OK` (skips 13/20/39/46 by platform), so the ninth tab is inside every layout measurement on Linux, macOS 26 and
Windows 2025 without a K1/K2/K3 failure. One process defect worth recording, because its evidence is in
the repository rather than in a report: the commit message of `a868275` was passed through a shell that
expanded its backticked phrases as commands, so it arrived full of gaps. A pushed message is not rewritten;
the sentence above names the run instead, and every commit message in this increment otherwise went through
`git commit -F`.


**2026-10-16, this session — the mark gets a control, and the control keeps its mouth shut.**
The stored contact record could already represent a do-not-contact mark - the column, the date it was made,
the reason, and exactly one method that writes all three - and the stored list already showed it, but nothing
in the window could set it. That gap is now closed with no schema change at all: the record's own
`suppressed_note` was read, found sufficient, and a new column would have moved the version for nothing. Two
buttons sit under the stored list (row 10 and 11 of the tab's grid) with a reason box and one line of state
beside them, and what they obey is the interesting part rather than the fact that they exist. Both are built
disabled and are driven by one method that re-reads `list_contacts()` and enables exactly the action that
would change the selected row - mark when it is unmarked, clear when it is marked, the reason box only while
marking - so there is no state in which a person is offered a button whose only outcome is "nothing to
change". The row's tree id is the stored `contact_id`, so the panel asks the widget which row is selected and
then asks the store for that record rather than keeping a parallel copy of the list on screen; a selection
that a restore has since removed is caught as a stale id, refreshes the list and writes nothing. Both
confirmations describe the row by its **position in the list and the file it came from** and never by the
address, the name, the company or the reason, because dialog text is what a screenshot or a bug report keeps,
and the reason a person types is stored on that one record and reaches no dialog, no status line, no message
and no event: the event is `contacts.suppressed` with `detail=suppressed=true|false` and nothing else.
Clearing nulls the flag, the date and the reason together, so an unmarked contact is not left carrying an
explanation that no longer applies. Zero-write is asserted the way the rest of this feature asserts it -
against the connection's own `total_changes`, not against the message shown - for a declined confirmation, a
stale selection and an injected `sqlite3.OperationalError` that leaves the mark and the typed reason exactly
as they were and reports no success. Covered by 12 new tests in
`tests/test_desktop_handlers.py::ContactMarkControlTests` (with the widget stand-in taught two things it was
missing: `configure` must record the options it is given, and a selection change must run the
`<<TreeviewSelect>>` handler the way a display does, because a tree that changes its selection silently would
let a handler that only ever runs on a display look correct here), one new privacy test in
`tests/test_contacts_store.py::ContactPrivacyTests` asserting the log holds a flag and no fixture value, and
four new acceptance checks **L6-L9** - the controls off until a row is selected with the keyboard's own
walk reaching the one that can act, a declined removal leaving the mark and its date untouched, a confirmed
one clearing both, and a mark made from the window through the real entry with its reason stored and shown in
no dialog, status line or log line. Both of the defects this increment had were found by the display-backed
legs rather than by anything runnable here, and both are worth recording because each is a class. The first
was an assertion of mine: the keyboard check asked Tk's focus walk to reach all three new controls while two
of them were disabled, and Tk walks a control only while it can act, so the check was asking for something the
platform deliberately does not do; it now asks for the control that can act, which is the property worth
having. The second is D34's family appearing in a new place, on Windows only: the restart-and-restore test
replaced the database while its own connection was still open, and an open handle makes `os.replace` fail
there with `PermissionError: [WinError 5]` instead of merely racing it - the fix is the sequence the window's
own restore handler already used, close for the swap and reopen afterwards, and the guarantee is that the test
now runs that way on the Windows legs too. The increment is verified where the window is: run `38855211961`
at `2d237bc` completed **13/13 jobs green**, every display-backed leg reporting `RESULT: PASS - 91 checks
passed` (L1-L9 `[ ok ]`, K4 and K5 `[ ok ]`, the contacts tab measured at 24 widgets with none outside the box
they are in) and `RESULT: PASS - 14 checks passed`, with `Ran 1845 tests ... OK` per leg (skips 13 on Linux, 20
on macOS, 39 and 46 on Windows). The runs that carried the two defects above are red and are history rather
than evidence. The suite is `Ran 1845 tests ... OK (skipped=13)` locally and the harness
now declares **91** checks. Written up in `research/hr-contact-do-not-contact-control-2026-10-16.md`; `task.md`
ticks the control, `phases.md` row 1C and `design.md`'s contacts bullet describe it, and the README's contact
section states the two controls, the reason rule and what is still absent. What this does not do: no human has
used the control (the tab has no numbered manual steps at all, so nothing is even marked BLOCKED), the record
keeps one current reason rather than a history of marks, a cleared mark is not a deleted record, the contact
tables are still outside the JSON export, recorded disagreements still cannot be read in the window, and
nothing acts on the mark because nothing contacts anybody - `SOURCE_QUALITY_GATE_PASSED` is still `False` and
`enabled_discovery_sources()` still empty.

---

**2026-10-16 — The recorded disagreements become readable: a read-only review panel, and D35 found by the
display-backed legs.** The last increment closed the do-not-contact control but left its own named gap open:
the application had been recording disagreements between a person's contact files and their stored contacts
since schema 7, and the only thing a person could see about them was a count. The **HR contacts** tab now lists
them - oldest first, numbered, each row naming the address the stored list already uses, the field, which two
sides disagree (`two rows of one file` or `your records vs the file`) and the file the disagreeing value arrived
in - and describes the selected one in full under `Kept in this database:` and `Recorded from the file:`, with
the provenance the schema actually holds and a closing sentence that says nothing here is merged, resolved or
dismissible. Neither side is called right, and the panel deliberately does *not* use the stored contact's own
first-seen file as the provenance of the value the database keeps, because the record does not connect those two
facts. Nothing new was needed to do it: the panel reads `list_contact_conflicts()` (the store's own order, no
paging parameter added) and `list_contacts()`, the `hr_contact_conflict` row holds everything shown, and **no
migration was added**. Read-only is measured rather than asserted in prose: `total_changes` is unchanged by
opening the panel, listing it, selecting every row and re-reading it, the do-not-contact mark and its reason are
untouched, no contact value reaches a dialog, the status line, the activity log or the count-only note under the
list, and the detail widget is left `disabled`. Rendering is bounded where a screen needs it: 40 rows with the
note saying how many are held when the cap bites, 60-character list cells, and a 400-character detail value that
states the value's real length instead of looking complete. The tab also re-reads itself from
`<<NotebookTabChanged>>` through the same `_refresh_contacts()` a Refresh click runs, so an import made by
another connection shows up the moment the tab is looked at and no second read path exists. Evidence: nine tests
in `tests/test_desktop_handlers.py::ContactConflictPanelTests`, one layout-policy test that the panel's widgets
sit inside the tab's scrolled container and that both trees are bound to the handlers their selection events
post, acceptance checks **L10-L12** (94 declared checks now, `declared_step_count()` reading the source), the
smoke script's inventory of the window's lists, `Ran 1857 tests ... OK (skipped=13)` locally - and the tab's
first numbered manual steps, **99-105**, all BLOCKED, which is why the handoff's "one tab has no numbered
steps" gap is closed. **D35** is the defect of the increment and it was found by a display, not by anything
runnable here: L11 pressed `<Down>` after setting the tree's *selection*, and Tk 8.6's
`ttk::treeview::Keynav` moves the tree's **focus item** - the row a click draws its rectangle around - and
returns at its first line when no item holds it, so on a real display the key moved nothing (`the down arrow did
not move the selection: ('1',)` on the Linux display job `116844709877` and both macOS legs of run `38861539212`
at `7323457`). The stand-in could not have caught it because it navigated from the selection; the check now
sets the focus item the way a click does, and the stand-in models Tk's behaviour faithfully - a separate focus
item, navigation from it, arrow bindings that exist and silently do nothing without one, and a deleted row
losing the focus item - read off Tk 8.6's own `treeview.tcl`, with two `TreeRowReadbackTests` pinning that
parity. What a person therefore meets in *every* list in this window is Tk's own behaviour - arrow keys move
from the row that was last clicked - and the manual checklist asks a tester to observe it and write it down
rather than pretending otherwise. The green matrix is run `38864632201` at `4b4e752`: **13/13 jobs**, every
display-backed leg reporting `RESULT: PASS - 94 checks passed` (workflow L's L1-L12 `[ ok ]`, K4 and K5 `[ ok ]`,
the focus walk reading `7/12 interactive control(s) reached` on the contacts tab) and `RESULT: PASS - 14 checks
passed`, with `Ran 1857 tests ... OK` per leg. What this does not do: more than 40 disagreements are counted but
not browsable, nothing can be dismissed, resolved or merged, the list cannot be exported, no contact can be
edited or deleted from this screen, the do-not-contact mark still has one current reason rather than a history,
and **no human has used the tab** - its wording, wrapping, keyboard feel and native look stay unverified, which
is what steps 99-105 are for. `SOURCE_QUALITY_GATE_PASSED` is still `False` and `enabled_discovery_sources()`
still empty. Written up in `research/hr-contact-conflict-review-panel-2026-10-16.md`; D35 is section 25 of the
cross-platform evidence register, `phases.md` row 1 and `design.md`'s workflow list carry the new check count,
`README.md` describes the panel, and `task.md` records the increment and names per-contact deletion and a
contact-list export as the next candidates.
**2026-10-16, this session — per-contact deletion: one transaction, a row reference instead of a name, and the limit a backup is.**
The HR contacts tab could import, mark and review, but a record could never be removed: the only erasure this
application offered was `--forget-local-data`, which takes the whole database. Per-contact deletion is now a
store operation — `CareerStore.delete_contact(email_key)` opens `BEGIN IMMEDIATE`, reads the row, deletes the
`hr_contact_conflict` rows carrying that key **by name** and then the `hr_contact` row, commits, and returns
`ContactDeletionOutcome(deleted, conflicts)` with `describe()` for the status line. That object deliberately
does not carry the address: an outcome is what a dialog and a log line are built from, and neither may carry a
contact value. The explicit conflict delete is what makes the outcome independent of a pragma — `ON DELETE
CASCADE` is declared on the only foreign key that references either table and `PRAGMA foreign_keys = ON` is set
when the connection opens, and that cascade stays as a second line of defence, but a deletion that quietly
stopped removing rows would leave orphans while reporting a success, so both are asserted (one test deletes
with foreign keys off and still requires the evidence to be gone; another asserts the cascade really is declared
and enabled). Any exception rolls both statements back and the database stays usable, which is the half-deletion
this increment had to make impossible. A key the store does not hold is not an error: for a delete, "already
gone" is the requested end state, and the caller is *told* (`deleted=False`, no write, no event) rather than
handed an exception — deliberately unlike `set_contact_suppression`, where a mark that silently did not happen
would be a false claim about state meant to persist. The event is `contacts.deleted` with
`detail=contacts=1 conflicts=N`, written only after the commit.

The window asks in references, not identities: `row N of M in the stored list`, the file the record came from,
and the exact number of disagreements that go with it — the same style the mark confirmations already use — then
"there is no undo in this application" and what a backup written earlier still holds. The address, name, company,
the reason a mark carries and every disagreement value stay out of the dialog, the status line, the state line,
the summary and the log. The button is built disabled, on its own row under its own sentence (a `StringVar`, so
its words are read back by a test rather than only drawn), and enabled for **any** selected stored contact,
marked or not — a mark is a reason to be careful about contacting somebody, never a reason to keep their record,
and this window does not decide which records a person may remove from their own database. Every refusal path —
no selection, a stale row, a declined confirmation, a row that vanishes *while the question is being answered*,
a `StoredRecordError`, an `sqlite3.Error` — writes nothing and says so, and the report afterwards is built from
the store's own outcome rather than the count the question used, because the two are read at different moments.
One `_refresh_contacts()` re-reads both views after a successful deletion, which is what clears the selection and
greys the button again. Evidence: twelve tests in `tests/test_contacts_store.py::ContactDeletionTests` (exactly
two rows go, measured against `total_changes`; both contacts carry a disagreement of their own in the fixture so
a deletion that removed *every* conflict row could not pass; marks, reasons, timestamps, `integrity_check`,
`foreign_key_check` and `user_version = 7` all asserted; a restart and a backup-afterwards agree; **a backup
taken before the deletion still holds the record after a restore**, which is the honest limit asserted rather
than papered over), eleven tests in `tests/test_desktop_handlers.py::ContactDeletionControlTests`, acceptance
checks **L13-L15** (97 declared checks now), and `Ran 1881 tests ... OK (skipped=13)` locally. Four temporary
mutations were made and reverted to prove the tests bite: removing the explicit conflict delete (2 failures),
removing the rollback (1 failure, 1 error), ignoring the confirmation's answer (1 failure) and dropping the
post-deletion refresh (2 failures). No schema change was needed, so **schema 7 stands** and the JSON export
still does not carry the contact tables. The green matrix is run `38875397574` at `c1b2ab1`: **13/13 jobs**, the
Linux display job `116889109924` reporting `RESULT: PASS — 97 checks passed` with L13-L15 `[ ok ]` beside L1-L12
and the macOS/Windows legs running `Ran 1881 tests ... OK` with the same acceptance pass. What this does not do:
no bulk deletion, no deletion from the command line, no export of the list, no tombstone anywhere, no change to
`--forget-local-data` or to backup/restore semantics — and **no human has used it**, so the six new manual steps
**106-111** are BLOCKED, the checklist's head count moves to 111 steps (22 PASS / 89 BLOCKED / 0 FAIL, no box
ticked), and the greyed button's appearance, the dialog's wording, the keyboard feel, the screen reader's output
and the native look stay unverified. `SOURCE_QUALITY_GATE_PASSED` is still `False`, `enabled_discovery_sources()`
still `()`, and nothing in the increment opens a socket. Written up in
`research/hr-contact-per-contact-deletion-2026-10-16.md`; `task.md` records the increment and names a
contact-list export and row-by-row CSV decisions as the next candidates; `phases.md`, `design.md`, `README.md`
and the handoff carry the new counts; and no new defect (D36) was found, so the cross-platform register is
unchanged.

## 2026-10-16 — Exporting the stored HR contact list, and the two defects the verification found

The HR contacts tab could read a list, store it, mark it, review its disagreements and delete one record, but
the list itself could not leave the database: the only export was the version-2 JSON document, which
deliberately carries no contact table. This increment adds a **separate, user-initiated CSV export** with its
own contract - `career_agent/contact_export.py`, format `hr-contact-export/1`: UTF-8 **with a byte-order mark**,
`\r\n` record separators, one row per stored contact with `Email`, `Name`, `Company`, `Do Not Contact` (the
mark as readable text, `yes`/`no`, never empty) and `Export Format` on every row. Excluded on purpose and
documented as such: internal ids, first/last seen, import counts, the source file and row, review flags and
notes, every disagreement value, the mark's date and note, and every activity record - all of which the
whole-database backup on the Data safety tab carries instead, because it copies the database itself.

The safety decision was made from the code before anything was written, and it is the one the task allowed:
`set_contact_suppression` is the only writer of the mark in the whole application and no import statement names
that column, so the export does **not** claim to preserve suppression state. The column is text a person reads,
an import can neither set nor clear it, and one sentence (`MARK_COLUMN_LIMITATION`) is repeated by the window,
the completion dialog and the command rather than paraphrased three ways. Both directions are asserted: a file
saying `yes` everywhere marks nobody, and a file edited to say `no` unmarks nobody. A mutation showed those
tests were asserting the sentence's *identity* and would have accepted a sentence that said nothing useful, so
three of them now assert its substance too.

The write is byte-for-byte (`store.write_private_bytes_file`, because a text write would translate `\n` and make
one documented format two files), owner-only on POSIX, never through a symbolic link, and read back and compared
before success is claimed; over 50,000 rows or 20 MiB the export refuses before creating a path and names the
backup. Cells that would make a spreadsheet evaluate them are written with a leading apostrophe. The window asks
before replacing a file, says nothing at all when the dialog is closed, and reports every failure without
claiming an export; `--export-contacts-to` refuses an existing path outright. The database is only read, and the
log carries counts (`contacts.exported`, `contacts.export.failed`).

**Two defects were found by verification rather than by reading, and both are fixed with tests that fail
without them.** **D36**: the Windows display-backed legs of run `38883986337` at `bdf443b` failed the new L20
check - `the path the person chose reached the activity log` - while Linux, macOS and every other job were
green. `diagnostics.redact_paths` hides declared paths and then any remaining absolute location, but both of its
patterns refuse to match after the `>` that every placeholder ends with, and its Windows branch needs a drive
letter or share prefix that does not survive the home-folder replacement; on the runners the temporary folder
sits under the *parent* of `Path.home()` (`C:\Users\RUNNER~1\AppData\Local\Temp\...`), so
`<home folder>\RUNNER~1\...\no-such-folder` stayed in a log written to be safe to share. The fix is a third
pattern - a location continuing past a placeholder into two or more further segments - and one trailing segment
stays visible because that shape is `<application data folder>/career_agent.sqlite3`, the product's own file
name; widening the shared guard was tried first and is exactly what that test caught. While writing the
regression test, the POSIX half turned out to fail on the shipped code as well (`/home/other/matter-notes/...`
kept its folder name), so D36 was never really Windows-only. **The partial write**: `write_private_bytes_file`
promised the bytes it was given or nothing, but a mid-write I/O failure left a ten-byte fragment of the header
at the person's chosen path while the error said the export was not completed; the writer now removes what it
started and says whether the removal succeeded. Two regression tests hold it.

**Mutation checks were rebuilt before they were trusted.** The first version mutated the real working tree and
restored from a backup taken on its first run, so a reused backup restored an older revision over a newer edit -
the tests correctly reported the resulting failure, but the harness had caused it. The harness now copies the
worktree to a temporary directory removed in a `finally`, verifies the unmutated copy green **first** so a
failure can be attributed to the mutation, requires the failing test to be in the module the entry names, checks
that each mutation actually changed the file and still compiles, and verifies every file restored byte for byte
afterwards. **Twenty mutations - both spreadsheet guards, the read-back, the byte-order mark, the line endings,
the version cell, the mark column, the mark's note, both limits, the shared sentence, the partial-write discard,
the D36 pattern, two window claims, two command claims and the JSON version - were all caught**, and the run
prints the failing test for each.

Evidence: 37 tests in `tests/test_contact_export.py`, 11 in `tests/test_cli_export_contacts.py`, 6 in
`tests/test_store.py::PrivateBytesWriteTests`, 3 in `tests/test_contacts_store.py::ContactExportReadBackTests`,
10 in `tests/test_desktop_handlers.py::ContactsExportHandlerTests`, acceptance checks **L16-L20** (102 declared
checks), `Ran 1950 tests ... OK (skipped=13)` locally, and run `38891340290` at `546d065` green **13/13** with
`RESULT: PASS — 102 checks passed` on all five display-backed legs. Commits: `bdf443b` (feature) and `546d065`
(the two fixes). No schema change (still **7**), `EXPORT_FORMAT_VERSION` is asserted to still be **2** and the
JSON document is asserted byte-identical across a contact export, no new table, no change to
`--forget-local-data`, backup or restore, and nothing opens a socket: `SOURCE_QUALITY_GATE_PASSED` is still
`False` and `enabled_discovery_sources()` still `()`. **No human has used it**: the six new manual steps
**112-117** are BLOCKED, the checklist's head count moves to 117 steps (22 PASS / 95 BLOCKED / 0 FAIL, no box
ticked), and whether the paragraph reads clearly, whether the save dialog is reachable at 900x600, what a
spreadsheet does with the apostrophe and whether non-ASCII names look right in a person's own tools stay
unverified. Written up in `research/hr-contact-export-2026-10-16.md`; D36 is recorded in section 26 of
`research/cross-platform-desktop-ci-evidence-2026-10-15.md`.

## 2026-10-16 — A profile fact now knows where it came from, and the app can no longer call a document's words the person's own

**The gap.** The candidate profile was ten facts and a timestamp. A country typed into the form, a graduation
year accepted out of a local DOCX, and a skills list imported from a JSON file exported by another machine all
landed in `candidate_profile.payload` as the same bytes, and after a résumé import the window said "Verified in
the local database" — where *verified* could only be read as a claim about the person, because the reader had no
other way to take it. The word was true of the values (they were written and read back) and false about the
facts, and there was nothing in the database to tell the difference.

**The increment (schema 8).** One additive, initially-empty table, `profile_fact_provenance(fact PRIMARY KEY,
source, verification, document_name, recorded_at, confirmed_at)`, and the rule that governs it: a **machine's
fact is never a person's confirmation**. `FactSource` is unknown / user_entered / extracted_from_document /
imported_from_file, `FactVerification` is unverified / user_confirmed, and the vocabulary is the profile form's
own ten keys (`PROFILE_FACTS`) rather than a second spelling of them. `REQUIRED_PROFILE_FACTS` is the six
`evaluate_eligibility` can be blocked on, so a future setup flow can ask for exactly what the profile does not
state; a test reads `evaluate_eligibility`'s source to fail if the list drifts.

`save_profile(profile, *, source=…, document_name=…)` writes the profile row and one origin row per **changed**
stated fact in one transaction and returns the facts whose origin it recorded; a fact the write no longer states
loses its row with the value it described. `get_profile_fact_provenance()` decodes every stored row (an
unreadable one is refused, never passed over) and reports a stated fact with no row as **unknown** — not as the
person's own. `confirm_profile_fact(fact)` is the only path to `user_confirmed`: it refuses a fact the profile
does not state, is idempotent, and never rewrites the source. A document is remembered by its **name**, never its
folder, on both separators. `delete_profile` deletes the origins in the same transaction, so "delete my profile"
cannot leave a row saying *this came out of CV.docx* behind; `erasure.py` needed no change because it removes
files, and the origins live inside the database file.

**What a person is told.** The résumé-import completion message no longer says "Verified in the local database".
It says the values were written to the local database and read back to check them, and that the app recorded
them as **values read out of that document** and **as not confirmed by you**: "a sentence in a document is not
your own statement about yourself, and this app does not treat it as one." An earlier draft of that message
promised a "Confirm selected fact button"; no such control exists, and a message must not name a control the
window does not have — the sentence was rewritten rather than the promise left standing.

**Two defects, both found by running the code rather than reading it.** (1) `StoredRecordError` subclasses
`ValueError`, so the new `except ValueError` on the résumé save path — written for form validation — swallowed a
stored record this build cannot read and told the person their typed values were unusable; found by an existing
read-back test going red in the full suite, fixed by catching `StoredRecordError` **first** in both handlers.
(2) `save_profile` returned "recorded" on a file held at an older version, where there is no table to record
into; now it returns `()` and logs that origins were not recorded. A third finding was not a defect in the code
but in the tests: **nothing asserted the résumé review path's provenance at all**, so that call site could have
dropped the origin with the whole suite green. A mutation harness on a disposable copy found it — the first pass
ran 12 mutations, ten caught, that one **missed**; a test was added for it and the mutation is now caught, and
`tests/test_desktop_handlers.py` holds 344 tests. A fourth, smaller defect came out of hand-editing a row while reviewing the decoder: an origin that contradicted itself (typed-then-names-a-document) escaped the read as a bare `ValueError` instead of the store's `StoredRecordError`; it is now reported as the damaged row it is, with its own test and mutation.

**Evidence.** `Ran 2004 tests ... OK (skipped=13)` (the suite stood at 1950), `compileall` clean, the stand-in
acceptance run `102 checks passed, 0 failed` — which reports **BLOCKED**, by design, because a stand-in Tk is not
a desktop — and **14 of 14 mutation checks detected** on an isolated copy (13 by the test named for the mutation,
1 by three other tests), log at `/home/user/scratch/mutation_checks_provenance.log`. Compatibility: the JSON
export is still `format_version: 2` and is asserted to carry none of the new vocabulary — origins are this app's
local bookkeeping, travel with a backup and a restore, and are deliberately **absent** from the portable file.
`SOURCE_QUALITY_GATE_PASSED` is still `False` and `enabled_discovery_sources()` still `()`.

**A fifth defect was the CI matrix's,** and it was a test rather than the code: the delete-with-its-orphans test
read the database file and required the deleted document name's bytes to be gone, which holds on Linux and fails
on all four cross-platform legs (run `38901274611` at `9581f81`) — SQLite keeps a deleted row's content in the
pages it frees, and the threat model already says so. The assertion now checks the rows the application actually
deletes. Run **`38903585396`** at `4321458` is green **13/13**: `Ran 2004 tests ... OK` on every leg, the five
display-backed legs reporting `RESULT: PASS — 102 checks passed`.

**What is deliberately not done.** No widget was added, so no manual step was ticked: the checklist stays
**117 steps, 22 PASS / 95 BLOCKED / 0 FAIL**. A fact can be confirmed through `store.confirm_profile_fact`
(tested end to end) but there is **no control in the window** for it yet — the confirmation belongs with the
setup flow that also asks for the required facts a profile does not state, where the value can be shown beside
the control. Work-history and education records (schema 6) still have no per-record provenance. Written up in
`research/candidate-profile-provenance-2026-10-16.md`.

## 2026-10-16 — The profile shows what it holds, a person confirms one fact, and the setup asks only for what is missing

**What was built.** The profile tab now carries a panel under the form: *Saved facts: the value, where it came
from, and whether you confirmed it*. One row per fact the stored profile **states** - a fact with no value has no
row, because there is nothing to show and nothing anybody could confirm - with the value, an origin in plain
words (``You typed it in this app``, ``Read out of a document you chose (cv.docx)``, ``Imported from a file you
chose (export.json)``, ``Not recorded — this profile was saved before the app kept track``), and whether the
person has confirmed it with the time the database holds. A document is named by its **file name** and never by a
folder: the store keeps no folder and the sentence has none to show. The row id is the fact's canonical name, so
the table cannot select something that is not a fact, and no value a person typed is ever read back to decide
which fact is being acted on. One control, **This is correct — confirm it**, is built disabled and enabled only
while exactly one row is selected; it calls ``CareerStore.confirm_profile_fact`` - the only writer of a confirmed
fact, with no SQL in the window - and then **reads the row, the value and the provenance back out of the
database**, so what the window reports is the database's answer rather than the handler's intention: a
confirmation that did not take effect, a value that moved, a fact the profile no longer states, a file older than
schema 8 and an unwritable database are each reported as what they are, and a second press on the same fact says
it was already confirmed and moves nothing, including the time of the first confirmation. Confirming a fact never
rewrites the value or where it came from: a fact read out of a CV stays a fact read out of a CV, now confirmed.

**The setup for what is missing.** **Set up missing required facts...** opens one window at a time - opening it
again lifts the window already open rather than drawing a second one over answers it would have changed - and
that window is rebuilt from storage every time it is drawn, so it asks for what the database does not state
rather than for what the last handler believed. It asks one question per fact
``core.missing_required_profile_facts`` reports, from one mapping keyed by the canonical fact names with a test
binding it to ``REQUIRED_PROFILE_FACTS``; a fact that is stored is **never** asked for again whatever its origin
and whatever its confirmation state, and the required facts that are stored but not yet confirmed are shown beside
their values and origins with a checkbox instead of being re-asked, because the open question about those is
whether the value is right. The four preferences are never asked at all: a listing cannot be blocked on them.
Answers go through the same ``build_candidate_profile`` validation and the same ``save_profile`` write the form
above uses, so there is no second and weaker route into the stored profile; a blank is never inferred from the
other answers and stays unknown; the profile is read back and compared before anything is confirmed, and only
then is one ``confirm_profile_fact`` call made per fact the person typed here or ticked. The window is rebuilt
afterwards and reports what is still not stated instead of claiming completion. Cancel, Escape, the close button
and a declined confirmation write nothing; a validation refusal keeps what was typed on screen; a failed write
leaves the stored profile alone; and a write that succeeded but cannot be read back says **"Saved, but not
verified"** with the facts left unconfirmed. The study-status question offers ``resume.study_status_choices()``,
and the profile form's own combobox now uses that same list, so an answer the dialog accepts is an answer the form
can hold.

**What changed around it, and what deliberately did not.** The table is redrawn after a profile save, a profile
deletion and an accepted résumé import, so a value read out of a document appears as that document's value and as
not confirmed by the person. No schema change (schema 8 already had every column this needs), no change to the
version-2 JSON export - origins and confirmations stay local bookkeeping - and no new model, store, importer or
tab: the panel lives on the existing profile tab inside the tab's scrolling body, and the write path is the
form's own.

**Three things verification found, all by running the code.** (1) The table dropped the row the person had just
used: confirming a fact redraws the table, and the redraw lost the selection, so a second press - and any reading
of "what happened to that row" - needed the row to be clicked again. Found by the repeated-confirmation test,
fixed by capturing the selected fact's key before the redraw and restoring it when that fact is still stored; a
mutation that removes it is caught. (2) A write that had **happened** was reported as *"Nothing was changed"*:
the setup save used the shared unreadable-record report, whose sentence promises that nothing was changed, on the
read-back after the profile had already been written. Found by a handler test that fails the read once the write
has succeeded; the post-write path now has its own honest sentence, *"Saved, but not verified"*. (3) One
reporting branch had **no test at all**, and the mutation run is what said so: the first pass ran eleven
mutations and caught ten, the miss being the branch that reports a fact as *already confirmed* when the setup
save finds it confirmed at write time. That branch is reachable - two windows, or two runs of the application,
on one database - and a test now drives exactly that (the same fact confirmed elsewhere while the setup window
was open; the earlier confirmation's own time must stand and this press must not claim the work). Second
increment in a row where a green suite said nothing about an untested path and the mutation harness asked.

**Evidence.** ``Ran 2065 tests … OK (skipped=13)`` on this machine (the suite stood at 2004 before the
increment's own tests: 25 added to ``tests/test_profile_provenance.py``, which now holds 74, and 36 to
``tests/test_desktop_handlers.py``, which now holds 380), ``compileall`` clean, the stand-in acceptance run
``113 checks passed, 0 failed`` - which reports **BLOCKED**, by design, because a stand-in Tk is not a desktop -
and **11 of 11 mutation checks detected** on a disposable copy, one of them only after the miss above was closed.
The harness gained **eleven checks inside workflow A** (A7-A17) rather than a thirteenth workflow, so the CI
job's loop over workflow letters is unchanged and ``declared_step_count()`` is 113; A17 builds a synthetic DOCX
in the run's own disposable folder and drives the real résumé review, so "a document's value is shown as that
document's and is not confirmed" is checked end to end, and A9 asserts the log line the store writes
(``profile.fact_confirmed detail=fact=country``) **and that no candidate value reaches the log**. The window
smoke test's ``EXPECTED_TREES`` gained ``facts_tree`` with its four columns and ``EXPECTED_SUMMARY_VARIABLES``
gained ``facts_summary``, so all five display-backed legs check the new controls exist and fill. CI: run
``38914820675`` at ``982e87c``, 13/13 jobs, ``RESULT: PASS — 113 checks passed`` on the five display-backed legs.

**What is deliberately not done.** No manual step was ticked: this increment adds widgets, so it adds **six**
numbered steps (118-123), all of them **BLOCKED**, and the checklist stands at **123 steps, 22 PASS / 101
BLOCKED / 0 FAIL**. Whether the table and its sentences read clearly and fit the tab at both sizes, whether a
greyed-out confirm button looks greyed out, whether the keyboard alone can work it, what a screen reader
announces for a table of a person's own facts, whether the setup window's wording makes it clear that a blank
stays unknown and that an answer typed there becomes the person's own statement - none of that is measurable, and
no automated check is offered as a substitute. Still open, and named in the note's follow-ups: per-record
provenance for the work-history and education tables (schema 6), origins travelling between machines (a
separately versioned export document, not a new key in version 2), asking for preferences as part of onboarding
(a product decision, not a bug), and a comparison view for a document's value that disagrees with a stored fact.
``SOURCE_QUALITY_GATE_PASSED`` is still ``False``, ``enabled_discovery_sources()`` is still ``()``, and no socket
is opened. Written up in ``research/candidate-profile-fact-review-and-setup-2026-10-16.md``.

## 2026-10-16 (later) — The same increment, asked one more question: does each sentence still describe what just happened?

**Why there was a second pass.** The increment's first commit was already green on the whole matrix, and every
test it shipped passed. Then its own rule was turned on the paths *around* the feature: the confirm control and
the setup save both hand a write to the store and report the result, and both had places where a read failure
could arrive **after** the write had reached the database. Reading the code was not enough to be sure, so each
suspicion was reproduced against the real store before anything was changed.

**The three defects, each reproduced first.** (1) ``CareerStore.confirm_profile_fact`` reads the stored profile
before its one transaction and again after it, and it commits the row before the last of those reads. A read
failure planted on that post-commit read left the confirmation **stored** - asserted in the reproduction by
reading it back - while the window's status line said "A saved record could not be read; nothing was changed."
The same branch covered a database error, whose sentence was "the confirmation could not be written ... so
nothing was recorded". (2) One step later in the setup save, the loop that records the checks runs after the
answers have been written *and* read back, and it used the same "nothing was changed" sentence. (3) The state
read that follows those checks decided the sentence "Still not stated: ...": when it failed, the profile came
back as ``None`` and the window described a profile that had just stored one fact as missing all six - and the
status line repeated the count.

**What the window does instead.** The confirm control now separates the reads *before* the attempt (where a
failure really does mean nothing was written) from the write call itself, and resolves anything raised out of
that call by reading the stored state and reporting it: confirmed, not confirmed, or - when even that read fails
- **not known**, with the safe way back said out loud ("confirming a fact that is already confirmed changes
nothing, including the time"). The store's own refusals (a fact the profile does not state, a file held at a
schema older than the one that keeps confirmations) remain the one failure that can still say nothing was
recorded, because each is decided before any row is written. The setup save reports a read failure in its check
loop as **"Saved, but the rest could not be checked"**: the answers are saved, what was recorded before the
failure is named, the check it could not read is said to be unknown, and the profile tab's own "Refresh the
saved facts" is named as where to look. The state read after the checks changes nothing but a sentence: nothing
is inferred from a failed read, and what the window shows is what it read again, so a failed read never decides
a claim about what the profile states.

**Tests and mutations.** Six new handler tests (``tests/test_desktop_handlers.py`` is at **386**), including the
two reproductions, the *not known* branch, and the store-refusal branch, which had **no test at all** - found by
looking for messages no test named, the same way the previous increment's untested reporting branch was found. One
existing test was rewritten rather than weakened: it asserted the old sentence for a database error and now
asserts the database's own answer plus that the status never claims nothing changed. The mutation harness grew to
**14 mutations, 14 of 14 detected**, and grew a guard of its own: one new mutation left a syntax error behind (a
two-line call patched as one line), the run failed to import, and the harness counted that as *caught* - which it
is not. A mutated copy that fails without one named test failing is now reported as an invalid mutation. One of
the harness's own anchors had also gone stale when the code moved; it said ``[stale]`` instead of silently
mutating nothing, and was updated. Evidence: full suite ``Ran 2071 tests … OK (skipped=13)``, ``compileall``
clean, the stand-in acceptance run still ``113 checks passed, 0 failed`` reporting **BLOCKED**, and the CI matrix
green for the fix commit: run ``38925910370`` at ``2514b52``, **13/13 jobs**, ``Ran 2071 tests … OK`` on every
unit and cross-platform leg and ``RESULT: PASS — 113 checks passed`` on all five display-backed legs (the
feature commit ``982e87c`` had been verified the same way by run ``38914820675``, 13/13 on ``Ran 2065 tests``). The acceptance harness gained nothing here on purpose: its faults are real
conditions (an unwritable folder, a held database), and a read failure inside the store's own confirmation call
is not one a window can be driven into - so these three paths are covered by the handler tests and the mutations,
and the six manual steps 118-123 stay **BLOCKED** with no box ticked.

**What this cost, and what it bought.** Two commits instead of one, and a second wait for the matrix. What it
bought is the rule this project keeps re-learning: a green suite says the tested paths work, never that a
sentence is true. Three sentences that would have been false about a write that had already happened are now
either true or explicitly unknown.

## 2026-10-16 (third pass) — The setup save writes the form too, and now says so

The third verification pass over the profile-confirmation increment asked the second pass's own question of one
more thing: not the sentences *around* a write, but what the write was asked to store. `_save_profile_setup`
mirrors each answer into the same `StringVar` the profile tab's entries are bound to and then builds its save
from those variables (`build_candidate_profile(self.profile_vars)`), so **one press stores the answers and any
value already sitting in the form** - and three things spoke of the answers alone: the confirmation that asks
permission, the report that follows the save, and the read-back comparison that verifies it.

**Reproduced against the real store before anything was changed.** Probe: the form's `country` set to a value
that was never saved, the setup window answered only for `work_authorization`, the confirmation answered yes.
The database then held the form's country, recorded `FactSource.USER_ENTERED` / `FactVerification.UNVERIFIED`,
while the dialog listed the single answer and the status line reported the save as done - a change to the stored
profile that no sentence of the window had mentioned. The values are a person's own, so nothing here was a data
loss; what was wrong was that a press wrote more than it said it would and reported less than it had.

**Fixed in `e57788e` by making the press and its own account the same size.** The question names the form's
values as saved with the answers and left unconfirmed - only an answer typed into that window is a
confirmation, so saving a form value is not one. The report names the facts `save_profile`'s own return value
says this write re-attributed, which *is* its scope: "Saved with them from the form on the profile tab, left
unconfirmed: Country." The read-back comparison now runs against everything the press was about to store
(`profile_fields_not_matching(stored, merged)`) rather than the answers alone, so a form-contributed value is
verified rather than written under a "saved" that was only checked for the rest. And `_setup_saved_but_unchecked`
- the sentence for a check that fails after the write - is told which values were written, because
"No answer was typed, so this press changed no value in your profile" was false in exactly this case; it now has
a sentence per case (the answers, the form's own values, or neither).

**Tests and mutations.** Two new handler tests (``tests/test_desktop_handlers.py`` is at **388**), one per new
sentence, each run against the **pre-fix window source first** - the first one fails there on the confirmation's
text, which is how the defect and its fix are both pinned to behaviour rather than to wording. The acceptance
harness's A15 step gained a requirement inside the existing step (the confirmation must say what else the press
writes), so the declared **113** checks and the manual step count **123** are unchanged and the stand-in run
still reports ``113 checks passed, 0 failed`` / **BLOCKED**. The mutation harness went to **17 mutations, 17 of
17 detected**; two of the three new ones are caught by the new tests, and one older mutation's anchor had to be
refreshed because the call it mutates grew a keyword argument - reported as ``[stale]`` rather than silently
mutating nothing, which is what that guard is for.

**Evidence.** Local, at the code head: full suite ``Ran 2073 tests in 56.281s`` ``OK (skipped=13)`` exit 0,
``compileall`` exit 0, the CSV audit unchanged (``0356b093… over 83 records``), the stand-in acceptance run
``113 checks passed, 0 failed`` reporting **BLOCKED** by construction (a stand-in Tk is not a desktop), and 17 of
17 mutations detected. CI: run ``38933027065`` at ``e57788e`` - **13/13 jobs**, ``Ran 2073 tests … OK`` on every
unit and cross-platform leg (skips 20/13/13/13/13 on Linux, 20 and 13 on macOS, 52 and 45 on Windows) and
``RESULT: PASS — 113 checks passed`` plus the smoke test's 14 on all five display-backed legs. The earlier heads
were verified the same way (``38925910370`` at ``2514b52``, ``38927983060`` at the docs commit ``434ef2f``,
``38914820675`` at the feature commit ``982e87c``).

**What the checklist now asks a person to judge.** Step 122 keeps its number and gains the question this pass
answered automatically: with a value typed into the form and not saved, the confirmation must say that the form's
values are saved with the answers and left unconfirmed, and the report afterwards must name that field. Step 122
is **BLOCKED** with the other five, and no box was ticked. The one thing a machine cannot check is still the
same: whether a person reading that confirmation understands that only the answer they typed is their own check
and the form's value - though now saved with it - is not.
