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

## Research claims to verify and keep current

- Current terms and permitted access methods for LinkedIn, Internshala, Naukri, Indeed, Wellfound, and company career pages.
- Official APIs or feeds available for job discovery and application submission.
- Current competitor capabilities, limitations, and pricing.
- Whether at least three useful discovery sources can be supported at zero mandatory recurring cost.
- Whether a permitted application workflow can be validated for the MVP.

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
10. What feature promises should be excluded until verified?

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

### 2026-10-13 — Initial product baseline
- Established desktop-first, local-first, zero-mandatory-cost direction.
- Set hybrid automation and strict quality-first application rules.
- Defined research-first workflow and deferred implementation.
- Added proposed feasibility tests and decision gates.
