# Product Requirements Document (PRD)

**Project:** AI Career Agent  
**Status:** Production-oriented product definition; safe offline-core implementation underway, live integrations gated by source-specific evidence  
**Last updated:** 2026-10-14

## 1. Product vision

A local-first desktop application that helps job seekers discover relevant jobs, understand employers, prepare truthful applications, automate permitted application steps, and maintain an accurate application history. The product should support different candidate types through configurable profiles, not hardcoded assumptions about one person.

## 2. Problem statement

Job seekers spend significant time searching across portals, evaluating role fit, repeating application forms, researching employers, and tracking outcomes. Existing tools cover parts of this workflow, but platform restrictions, poor matching, duplicate listings, uncertain submission status, and privacy concerns limit the value of a universal automated workflow.

## 3. Product principles

1. **Quality over volume:** prioritize relevant and eligible opportunities.
2. **Local-first privacy:** keep resumes, profiles, and application history on the user's device by default.
3. **Truthful applications:** never invent qualifications or answers.
4. **Permission-aware automation:** only use data access and submission methods that are authorized and supported.
5. **Evidence-based tracking:** never mark an application confirmed without reliable evidence.
6. **Human intervention by exception:** pause for missing information, sensitive declarations, unsupported steps, or uncertainty.
7. **Zero mandatory recurring cost for core use:** the baseline experience must not depend on paid AI APIs or hosted services.
8. **Transparent limitations:** show which sources and workflows are supported, unavailable, or not yet verified.

## 4. Target users

The intended audience is cross-industry and cross-experience: students, interns, placement candidates, fresh graduates, experienced professionals, and career switchers across engineering, design, creative work, business, finance, marketing, sales, operations, research, and other professions. Examples include graphic design, VLSI/embedded systems, mechanical, civil, software/data, and non-technical roles. This is a product-wide requirement, not a claim that every occupation or source is supported at launch.

**Delivery strategy:** design extensible, occupation-aware capabilities from the start, then validate an initial representative set of professions and expand based on measured quality. Do not hardcode one candidate's degree, resume, location, or job titles as global assumptions.

## 5. Core user journey (hypothesis)

1. Install/open the local desktop app and manually enter or review candidate facts.
2. Configure role targets and preferences without assuming an industry or candidate stage.
3. Add a job manually in the first local alpha; source discovery remains disabled until source-specific gates pass.
4. Keep source listing URL and verified employer application URL separate.
5. Evaluate hard eligibility using pass/fail/unknown and show evidence/explanations.
6. Show explainable skill overlap separately from eligibility.
7. Shortlist only when every mandatory eligibility check explicitly passes.
8. Track application state and evidence; export/delete local data.
9. Add local PDF/DOCX import as the next increment after the manual workflow is stable.
10. Add approved discovery, company research, application preparation, and permitted submission only behind their own quality, privacy, and permission gates.

## 6. Functional requirements

### Candidate profile and resume
- First local alpha: manual candidate-profile entry and correction, with missing facts left unknown.
- Follow-on increment: import PDF/DOCX locally; extract education, skills, experience, projects, certifications, and contact fields when available.
- Mark uncertain, missing, or conflicting extracted fields for review before they affect eligibility or generated material.
- Allow manual correction and multiple resume versions. Resume parsing is not claimed as implemented in the current alpha.
- Never fabricate experience, skills, qualifications, or work authorization.

### Job discovery
- Support multiple independently verified sources.
- Store source name, original URL, discovery time, posting date when available, last checked time, and source-specific identifiers.
- Discovery runs must expose source-level outcomes and counts, distinguish valid empty results from blocked/transient/parse errors, and avoid treating listings omitted from a partial run as closed. See the [n8n workflow pattern review](research/n8n-workflows-repository-review-2026-10-13.md).
- Detect duplicates across sources.
- Identify expired, closed, stale, or suspicious listings when evidence permits.
- Respect each source's terms, API rules, and technical access requirements.
- Treat source permission as a hard gate: a public endpoint, free feed, or attribution requirement does not alone establish authorization when broader terms conflict or prohibit automated gathering. Keep unresolved sources disabled until written clarification is recorded. Himalayas is currently blocked pending written clarification; see [the permission review](research/himalayas-api-permission-terms-conflict-2026-10-13.md).

### Matching and eligibility
- Run hard eligibility rules separately from relevance scoring.
- After research authorizes implementation, evaluate relevance/ranking changes against a versioned human-reviewed judgment set; measure retrieval coverage separately from ranking precision, and never let relevance scores override hard eligibility gates.
- Explain positive matches, missing requirements, and unresolved questions.
- Exclude known hard-eligibility failures from auto-apply eligibility.
- Allow users to configure preferences and thresholds.
- Keep a record of the scoring inputs and rule version used.

### Company intelligence
- Generate detailed reports for shortlisted jobs, not every discovered listing.
- Prefer official company pages and reputable sources.
- Include source links, retrieval date, and freshness/confidence labels.
- Separate verified facts, estimates, and unverified claims.
- Include scam indicators without presenting suspicion as certainty.

### Application preparation and submission
- Select an appropriate resume version.
- Generate role-specific materials only from verified candidate facts.
- Never fabricate screening answers.
- Support discovery, assisted-application, and rule-based auto-apply modes where workflows permit.
- Escalate missing information, sensitive declarations, assessments, CAPTCHA/OTP, unsupported steps, and uncertainty.
- Respect platform terms and do not bypass access controls or anti-bot systems.

### Application tracking
- Track discovered, shortlisted, prepared, submitted, confirmed, failed, and unknown-status states.
- Preserve timestamps, source URL, employer, role, resume version, and available confirmation evidence.
- Retry safely without duplicate submissions.
- Record errors and recovery attempts.
- Support manual status updates and optional authorized email integrations.

### Scheduling
- Default discovery schedule: 00:00 and 12:00 Asia/Kolkata.
- Let users configure schedules.
- Clearly report missed runs, offline periods, partial failures, and retries.
- The desktop scheduler must report sleep/offline periods accurately. To meet the laptop-independent requirement, the product needs an optional or separately deployed always-on worker/scheduler; desktop-only execution cannot run while the computer is powered off or asleep. Any hosted/remote component must disclose cost, uptime limits, and what candidate data leaves the device.

## 7. Non-functional requirements

- Local-first data storage.
- Secure credential and secret handling; no plaintext passwords.
- No transmission of resume data to an external AI service without explicit consent.
- Recoverable task state and safe retries.
- Clear logs without unnecessary sensitive personal data.
- Data export and deletion.
- Accessible, understandable user interface.
- Cross-platform distribution to be evaluated before commitment.

## 8. Success metrics (proposed, not yet validated)

- Precision of top-ranked jobs against a predefined human-reviewed relevance standard.
- Rate of known hard-eligibility violations among recommended jobs.
- Duplicate detection precision and recall.
- Resume extraction accuracy on critical fields.
- Percentage of application states backed by evidence.
- Duplicate submission rate caused by retries.
- Time saved per candidate.
- Response and interview conversion rates, measured separately from application volume.
- Zero unauthorized automation methods in supported workflows.

## 9. Release boundaries and explicit non-goals

- Do not promise support for every portal at launch; publish a source-by-source capability matrix and expand only after validation.
- Do not guarantee interviews, selection, or employment. Optimize and report measurable process/outcome indicators without presenting correlation as a guarantee.
- Never bypass CAPTCHA, OTP, anti-bot protections, access controls, platform rules, or employer restrictions on AI assistance.
- Do not optimize for raw application volume or submit when mandatory eligibility, candidate facts, permission, or submission state is uncertain.
- Do not require a paid AI API or paid hosted backend for the core product. Clearly label optional services and costs.
- Do not label a demo, mock form, or simulated submission as a real integration or successful application.

## 10. Open questions and evidence gates

- Which job sources provide useful, permitted discovery access, and which separately permit application automation?
- Which desktop framework and packaging/update path best support reliable installation on target operating systems?
- What always-on worker option meets the zero-budget goal while making uptime and privacy limitations explicit?
- Which local resume parsing/matching methods meet quality targets across varied formats and professions?
- Which first profession/source cohort gives a useful pilot without narrowing the product architecture?
- What privacy and consent boundary is required for each optional external AI, email, or company-research service?
- Which real-world pilot metrics and sample sizes are sufficient before enabling unattended submission for a workflow?

## 11. Production definition of done

A release is not production-ready merely because its UI renders or unit tests pass. For each advertised capability, provide repeatable tests, truthful support status, failure recovery, privacy/security review, and user-facing error handling. Before general release, validate installation and upgrade/uninstall paths; persistence and backup/restore; source freshness and direct application destinations; critical resume-field extraction; hard-eligibility false positives; duplicate protection; evidence-backed submission status; scheduler missed-run recovery; and a representative pilot across more than one profession. Keep unvalidated integrations disabled and label them clearly.
