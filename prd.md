# Product Requirements Document (PRD)

**Project:** AI Career Agent  
**Status:** Research plus safe offline-core implementation; live integrations remain gated  
**Last updated:** 2026-10-13

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

The long-term audience includes students seeking internships and placements, fresh graduates, experienced professionals, career switchers, and candidates seeking remote or international roles.

**Initial validation scope:** not finalized. Broad product architecture is desired, but testing should begin with a manageable candidate segment and expand only after evidence.

## 5. Core user journey (hypothesis)

1. Install and open the desktop app.
2. Upload a PDF or DOCX resume.
3. Extract a candidate profile and let the user review/correct it.
4. Configure job titles, locations, work modes, employment types, compensation, exclusions, and eligibility rules.
5. Discover jobs from verified sources.
6. Deduplicate, validate freshness, and assess eligibility.
7. Rank eligible jobs with explainable match reasons.
8. Research companies for shortlisted jobs.
9. Prepare application materials using verified profile facts.
10. Submit through supported, permitted workflows or request user intervention.
11. Record application evidence and status.
12. Review results, employer responses, and useful analytics.

## 6. Functional requirements

### Candidate profile and resume
- Import PDF and DOCX resumes.
- Extract education, skills, experience, projects, certifications, and contact fields when available.
- Mark uncertain, missing, or conflicting fields for review.
- Allow manual correction and multiple resume versions.
- Never fabricate experience, skills, qualifications, or work authorization.

### Job discovery
- Support multiple independently verified sources.
- Store source name, original URL, discovery time, posting date when available, last checked time, and source-specific identifiers.
- Discovery runs must expose source-level outcomes and counts, distinguish valid empty results from blocked/transient/parse errors, and avoid treating listings omitted from a partial run as closed. See the [n8n workflow pattern review](research/n8n-workflows-repository-review-2026-10-13.md).
- Detect duplicates across sources.
- Identify expired, closed, stale, or suspicious listings when evidence permits.
- Respect each source's terms, API rules, and technical access requirements.
- Treat source permission as a hard gate: a public endpoint, free feed, or attribution requirement does not alone establish authorization when broader terms conflict or prohibit automated gathering. Keep unresolved sources disabled until written clarification is recorded. Himalayas is currently blocked pending written clarification; see [the permission review](research/himalayas-api-permission-terms-conflict-2026-10-13.md).
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
- Local-only scheduling cannot run while a computer is powered off or asleep; this limitation must be explicit.

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

## 9. Out of scope for the research phase

- Building application code.
- Promising support for every portal.
- Guaranteeing interviews or employment.
- Bypassing CAPTCHA, OTP, anti-bot protections, or platform restrictions.
- Mass-applying without eligibility and quality checks.
- Monetization decisions before core feasibility is established.

## 10. Open questions

- Which job sources provide useful, permitted discovery access?
- Which sources permit or support application submission?
- Can three or more useful discovery sources be validated without paid services?
- Which local parsing and matching methods meet quality targets?
- What is the minimum viable supported application workflow?
- How should offline scheduling and missed-run recovery work?
- What privacy boundary is required for optional AI/company research services?
- Which candidate segment should be used for initial validation?
