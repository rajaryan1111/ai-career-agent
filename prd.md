# Product Requirements Document (PRD)

**Project:** AI Career Agent  
**Status:** Production-oriented product definition; local desktop alpha implemented, live integrations gated by source-specific evidence  
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

## 5. First local alpha workflow and planned product journey

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
- Employment and education history as structured records rather than one summary field: employer, job
  title, employment type, start and end dates, an explicit current-role flag and optional notes; and
  institution, qualification, optional discipline, start and completion dates and an ongoing-study flag.
  An impossible period, an inconsistent current-role or ongoing-study flag, blank required text, a
  mistyped date or a duplicate record is refused rather than stored. A date the person has not recorded
  stays unknown and contributes no duration; the reported figure is the months covered by current or fully
  dated roles, counting a month covered twice once, and it is never written back into the profile's own
  experience figure. See the README section *Keep your own employment and education record*; importing
  these records from a résumé, attaching documents and using them in eligibility or matching are not
  implemented.

### Job discovery
- Support multiple independently verified sources.
- Store source name, original URL, discovery time, posting date when available, last checked time, and source-specific identifiers.
- Discovery runs must expose source-level outcomes and counts, distinguish valid empty results from blocked/transient/parse errors, and avoid treating listings omitted from a partial run as closed. See the [n8n workflow pattern review](research/n8n-workflows-repository-review-2026-10-13.md).
- Detect duplicates across sources.
- Identify expired, closed, stale, or suspicious listings when evidence permits.
- Respect each source's terms, API rules, and technical access requirements.
- Treat source permission as a hard gate: a public endpoint, free feed, or attribution requirement does not alone establish authorization when broader terms conflict or prohibit automated gathering. Keep unresolved sources disabled until written clarification is recorded. Himalayas is currently blocked pending written clarification; see [the permission review](research/himalayas-api-permission-terms-conflict-2026-10-13.md).

### Follow-ups and reminders

Implemented today: a day to act on per application, listed in the window and on the command line with
overdue/due-today distinction, a daily local reminder task, and a calendar file the person can import
into their own calendar. Reminders never change application state. Email, calendar-account and push
notifications are **not** implemented and are not simulated.

### Sources

Implemented today: a read-only source report (`python -m career_agent --sources`) and the adapter
framework that would run a source, with the gate enforced in one place and no way to open it from the
adapter layer. Zero adapters exist and live discovery is disabled, because no source has passed both the
permission review and the source-quality gate; the report says so per source, with the evidence and the
conditions attached.

### Matching and eligibility

Implemented today: eligibility is a decision (PASS/FAIL/UNKNOWN) from stated requirements, and matching
is a transparent, per-factor comparison of required skills, experience, a stated qualification, location,
work mode and role type, reported with the coverage of what was actually known. Ranked output is a review
order, never a probability, and a listing whose eligibility fails is blocked from recommendation while
its comparison stays visible. Missing information is reported as missing rather than approximated, and
compensation is not compared because no compensation field exists yet.
- Run hard eligibility rules separately from relevance scoring.
- Evaluate relevance/ranking changes against a versioned human-reviewed judgment set; measure retrieval coverage separately from ranking precision, and never let relevance scores override hard eligibility gates.
- Explain positive matches, missing requirements, and unresolved questions.
- Keep country eligibility and work authorization separate. If an explicit allowed-work-authorization list exists, use exact matching; missing values remain unknown.
- A listing manually marked open without a recorded availability evidence/note must remain unknown for eligibility.
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
- **Implemented (local alpha):** status states with guarded transitions, confirmed-status evidence, and a
  dated per-application activity history that the candidate writes themselves (applied, employer
  replied, interview, assessment, followed up, note), each row also recording when this app wrote it. The
  history is not evidence and cannot change a status. **Planned/gated:** reminders, interview and
  follow-up scheduling, and any email or calendar integration (each needs its own permission, privacy and
  failure handling).

### Scheduling
- Default discovery schedule: 00:00 and 12:00 Asia/Kolkata.
- Let users configure schedules. (Implemented: times, timezone, enable/disable, timeout and retry
  limits are stored per task and editable from the Background tasks tab; a device that is off simply
  does not run them.)
- Clearly report missed runs, offline periods, partial failures, and retries. (Partially implemented:
  the durable record of scheduled occurrences, attempts, retries, refusals and interruptions exists in
  the database, with a run history per task; the report a person reads, the worker loop, and missed-run
  catch-up are not built yet.)
- The desktop scheduler must report sleep/offline periods accurately. To meet the laptop-independent requirement, the product needs an optional or separately deployed always-on worker/scheduler; desktop-only execution cannot run while the computer is powered off or asleep. Any hosted/remote component must disclose cost, uptime limits, and what candidate data leaves the device.

## 7. Non-functional requirements

- Local-first data storage.
- Secure credential and secret handling; no plaintext passwords.
- No transmission of resume data to an external AI service without explicit consent.
- Recoverable task state and safe retries.
- Clear logs without unnecessary sensitive personal data.
  **Implemented (local alpha):** one rule resolves the database path for the window, the backup/restore
  commands and a read-only `--doctor` report (an explicit path, then `CAREER_AGENT_DATABASE`, then the
  per-user data folder, which `CAREER_AGENT_HOME` moves when it holds an absolute path), so the three
  cannot disagree about which file is in use; a relative setting is ignored and reported rather than
  resolved against the working directory. `--doctor` prints the version, the paths, and what the
  database contains — or the same refusal the app itself would give — without a display, creating or
  changing nothing, and exits non-zero when it finds a problem. Start-up failures are explained in
  plain language with local paths redacted, plus one bounded owner-only local note. An event log
  (`logs/application.log`, beside the database) records what the application did - opened, migrated,
  saved, deleted, imported, exported, backed up, restored, failed - as one bounded, rotated line per
  event, holding event names, identifiers and counts rather than candidate content, with local paths
  redacted by the same function that sanitises the start-up note. **Planned:** a diagnostics view in the
  window that reads the log, and a version/data-compatibility policy for released builds.
- Preparation and interview records: a per-application checklist (title, kind, optional day, and the
  moment the person said it was done) and the rounds of an employer's process (stage, planned day, mode,
  the candidate's own reading of how it went, notes). One combined "what needs doing next" list orders
  them against the follow-up days; nothing in either record can move an application's status, and no
  outcome value describes an employer's decision.
- Data export, import and deletion: a versioned JSON document that can be read back on another
  computer, planned and confirmed before it writes, with an existing listing linked rather than
  replaced, a stored profile kept, and an application record never imported at a status it did not
  reach here.
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
