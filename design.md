# Product Design Notes

**Status:** Product UX specification; UI implementation pending  
**Last updated:** 2026-10-14

## 1. Design objective

Make job discovery and application tracking transparent, calm, and trustworthy. Help candidates make good decisions without encouraging indiscriminate mass applications.

## 2. Primary navigation (hypothesis)

- Overview
- Discover Jobs
- Shortlist
- Companies
- Applications
- Candidate Profile
- Sources & Settings

## 3. First-run experience

1. Welcome screen explains local-first storage and limitations.
2. Resume import for PDF/DOCX.
3. Parsing preview with uncertain fields clearly marked.
4. Candidate confirms/edits critical information.
5. Preference setup: roles, locations, work mode, employment type, compensation, eligibility, excluded companies, and preferred sources.
6. Explain automation modes and platform-specific limits.
7. User decides whether to enable optional external AI/company research services.
8. Show source connection status and what can/cannot be automated.

Do not enable auto-apply before profile review and explicit configuration.

## 4. Job card requirements

Each job card should show role/company; location/work mode and employment type when known; source and original link; posting date and last-checked time where available; eligibility (eligible, ineligible, needs review); explainable match score; matched/missing requirements; sourced compensation or “not disclosed”; freshness/credibility warnings; and a clear next action.

## 5. Company report

Detailed research only for shortlisted/high-priority jobs. Include company overview/official website, products/industry/business model, relevant team/role context when supported, location/work mode, sourced compensation, relevant and current announcements/funding, employee feedback labeled anecdotal with date/context, credibility indicators, interview preparation, and source links/retrieval dates/confidence labels.

Never show an AI-generated statement as verified fact without a source.

## 6. Application tracking

States: Discovered, Shortlisted, Prepared, Awaiting user, Submission attempted, Submitted — unverified, Confirmed, Failed, Unknown status, Response received, Interview, Rejected, Withdrawn.

Show evidence for confirmed status where available. Unknown must not silently become confirmed.

## 7. Exception handling

Pause when candidate information is missing/conflicting; a sensitive declaration is needed; a mandatory requirement cannot be verified; an assessment/custom response is required; CAPTCHA/OTP or another unsupported step appears; platform policy/workflow is unclear; or submission result is ambiguous.

Explain what happened, what is known, and what the user can do next.

## 8. Privacy and trust UX

Clearly indicate local vs external processing; ask consent before sending resume/profile data externally; display source and last-checked time; provide export/delete controls; never expose credentials in UI/logs; explain local scheduling limits while the computer is asleep/off.

## 9. Visual direction

Desktop-first, clean, information-dense but readable. Use restrained status colors, consistent labels, accessible contrast, and plain-language explanations. Avoid gamification that rewards raw application volume.

## 10. Open design questions

- Which desktop framework gives the best installation/update experience?
- Should company reports be generated on demand or after shortlisting?
- How should source failures and unavailable integrations be displayed?
- How should users set match thresholds without needing ML expertise?
- What is the clearest distinction between submitted and confirmed applications?


## 11. Cross-industry onboarding and role setup

Onboarding must not presume the user is a software/AI candidate. Ask for target occupation families, role titles and synonyms, experience stage, education/certifications where relevant, location/country/work authorization, work mode, employment type, compensation preferences, and exclusions. Show optional fields only when relevant to the selected role. Let users maintain multiple target-role profiles without duplicating their verified personal facts.

Occupation-aware match explanations should use familiar role language and distinguish required credentials/tools from preferred skills. For example, design roles may emphasize portfolio/tools; VLSI/embedded roles may emphasize hardware/EDA/firmware; mechanical and civil roles may emphasize domain tools, credentials, site/work-mode requirements; business roles may emphasize function-specific experience. These are illustrative patterns, not hardcoded eligibility assumptions.

## 12. Production dashboard and operational transparency

The Overview must show the last and next scheduled run in Asia/Kolkata, worker health, missed/partial runs, source-level counts/errors, new jobs, duplicate suppression, eligibility/unknown reasons, application statuses, and any action needing attention. Clearly separate planned, experimental, permission-gated, and production-supported integrations. Never show a green success indicator for an unverified submission.

Applications should expose an auditable timeline: discovered, checked, shortlisted, prepared, submission attempted, submitted-unverified, confirmed (with evidence), failed/unknown, response/interview, and final outcome. Provide retry/recovery actions that first check for possible prior success. The interface must explain why a task paused and how to resolve it without requiring users to understand internal technical details.

## 13. Trust, standing authorization, and remote operation

During setup, users can configure a revocable standing policy for routine, permitted applications so the system does not ask for per-job approval repeatedly. Explain which sources/actions the policy covers and how to pause/revoke it. The policy cannot override provider/employer restrictions or permit guesses on mandatory facts, sensitive declarations, assessments, CAPTCHA/OTP, or ambiguous submission results.

If background execution requires a remote worker, show a separate consent and data-flow explanation before sending any candidate data off-device. Display the actual worker status and last heartbeat; never imply that a local-only app runs while the laptop is powered off. Offer export, deletion, backup/restore, and connection revocation in understandable settings.

## 14. Accessibility and internationalization

Use clear language, keyboard-accessible workflows, readable status text that does not rely on color alone, timezone-aware scheduling, locale-aware dates and compensation units, and extensible country/work-authorization fields. Avoid treating English-language resumes or one country's education terminology as universal.
