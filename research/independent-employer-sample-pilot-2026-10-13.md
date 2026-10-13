# Independent Official-Employer Recheck — Bounded Pilot 1 (follow-up added)

**Check date:** 2026-10-13  
**Purpose:** Start the independent official-employer comparison set required by the source feasibility gate. This is a small, manually reviewed pilot—not a representative sample, not a coverage estimate, and not permission to implement source connectors.

## Method and boundaries

- Used official employer career-board result pages surfaced in web research, then attempted to open the canonical pages through the research interface.
- Captured only role/source metadata needed for evaluation. No resume, candidate profile, credentials, or application data was sent.
- Did not submit applications or automate browser actions.
- Where the search result described a fresh posting but the direct page returned no readable content, status remains `unknown`. Search snippets are evidence leads, not a substitute for full canonical verification.
- Source permission remains a separate gate. A public official page does not by itself authorize automated extraction, caching, autofill, or submission.

## Sample observations

| Sample ID | Employer / role | Canonical evidence observed | Eligibility / relevance notes | Status decision |
|---|---|---|---|---|
| IN-025 | Airbus — Internship, India Innovation Team, GenAI Intern | Official Workday result displayed Apply, Bangalore Area, “Posted 2 Days Ago”, six-month duration, and student/internship metadata. Role description includes RAG, language-model capability research, fine-tuning data preparation, quantization and model deployment. | High role-family relevance. Strong Python, transformers, embeddings, ML framework and RAG requirements are stated. Exact degree/year eligibility, pay, exact onsite/hybrid arrangement and work authorization remain unknown. | Existing `open` label retained based on fresh official result evidence; recheck full canonical page before recommending or submitting. |
| IN-029 | Unisys — AI Engineering Intern | Official Workday search result showed Apply, Bangalore, “Posted 4 Days Ago”, and hands-on AI pipelines, agents, prototypes and test harnesses. Direct page opening returned no readable lines in this research interface. | High role-family relevance. Degree/year requirements, duration, compensation and exact work arrangement remain unknown. | Keep `unknown`; do not promote from a snippet while full canonical verification is unavailable. CSV review notes updated. |
| IN-035 | Walmart Global Tech India — (IND) Grad Intern - No Work Experience | Official Workday result showed Apply, Bengaluru, “Posted 8 Days Ago”, and described a GenAI/ML engineering internship with no work experience. Direct page opening returned no readable lines in this research interface. | High relevance and a useful zero-experience control. Exact degree/year rules, work arrangement, duration, compensation and work authorization remain unknown. Added as a new CSV record. | Keep `unknown`; current-looking result is not enough to assert all details or eligibility. |
| INT-021 | Threxil Systems — AI Intern | Official careers page explicitly says “2 roles open”; linked role page says remote and describes retrieval/evaluation work; direct form present. Careers page says work from anywhere. | Freshers/self-taught developers welcome; Python, NumPy/Pandas, data structures/algorithms. Exact legal/work-authorization limits, compensation, duration, and posting date not stated. Employer legitimacy signals and source permission still need separate review. | `open` based on explicit employer open-roles statement; eligibility and source permission remain unresolved. |
| INT-022 | Threxil Systems — Frontend + AI Intern | Same official careers page explicitly lists the role among two open roles; linked role page says remote and has a direct application form. | Freshers/self-taught developers welcome; React, modern frontend tooling, some TypeScript or willingness to learn. Relevant to AI product engineering, not a pure ML role. Legal/work-authorization limits, compensation, duration, posting date, legitimacy signals, and source permission remain unresolved. | `open` based on explicit employer open-roles statement; role-family classification and source permission remain separate. |
| INT-023 | MailerMen — Machine Learning Intern (Python, scikit-learn) | Employer-hosted listing explicitly says Actively hiring, Remote (Worldwide), Freshers only; posted 2026-09-04 and updated 2026-10-13. | Three months; ₹15k–₹20k/month; final-year/recent graduate in a related field; Python/pandas/scikit-learn and text classification/evaluation. Requires two weekly overlaps with IST afternoons. Permission for automated extraction/caching/submission is still unknown. | `open` from explicit employer-hosted status label; source permission remains separate. |
| INT-024 | QovaTech — AI Intern | Official career page labels the role an open internship and remote-friendly; it describes agent/RAG/evaluation work and an application form. | Requires an already-shipped LLM project and hands-on Python/TypeScript, embeddings, RAG and tool use. Company is based in Alexandria, Egypt and says it serves clients worldwide, but candidate-country eligibility is not stated. Compensation, duration and source permission unknown. | `open` from explicit open-internship label; country eligibility and remote arrangement remain unresolved. |
| INT-025 | DataRobot — Agentic AI Intern | Official Workday result showed Apply, a recent posting signal and US offices plus Remote Canada-Ontario. Direct page retrieval returned no readable lines. | Geography control: remote is explicitly tied to Canada-Ontario; no evidence that India-based candidates are eligible. Full requirements and current status remain unknown. | `unknown`; do not promote from search snippet alone. |
| NC-003 | GE Aerospace — Data Science Intern | Official Workday result still describes the role and remains indexed, but the listing's application end date is **2026-09-24**, which is before this audit date. | Useful hard-negative freshness control. An indexed page and relevant AI/ML description must not override an elapsed application deadline. | Retain `expired` unless a new requisition or authoritative extension is evidenced. No reopening based on page presence. |

## Official source links

- Airbus: https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Internship---India-Innovation-Team---GenAI-Intern_JR10446597
- Unisys: https://unisys.wd5.myworkdayjobs.com/en-US/External/job/AI-Engineering-Intern_REQ574280
- Walmart: https://walmart.wd504.myworkdayjobs.com/en-US/WalmartExternal/job/IN-KA-BANGALORE-Home-Office-PTPP1/XMLNAME--IND--Grad-Intern---No-Work-Experience_R-2607497
- GE Aerospace negative control: https://geaerospace.wd5.myworkdayjobs.com/en-US/GE_ExternalSite/job/Data-Science-Intern_R5040035-1

## What this pilot establishes—and what it does not

**Established for this bounded check:**
- The initial India-focused subset surfaced three official employer-page leads (Airbus, Unisys, Walmart); the follow-up added two Threxil role pages and three additional international-remote records (MailerMen, QovaTech, DataRobot).
- Airbus's current result had relatively detailed role requirements and a recent posting signal.
- Unisys and Walmart surfaced current-looking postings, but the direct page retrieval path was incomplete; their vacancy state and missing fields remain unresolved.
- A role can be relevant while still being expired, as demonstrated by the GE Aerospace control.

**Not established:**
- That all three positive leads are definitely open and eligible for a particular candidate.
- That a source has adequate precision or recall; the sample is too small and was not randomly drawn.
- That a public board is approved for automated discovery, caching, autofill or submission.
- That the project meets the proposed gate of 20 unique, currently valid target-relevant vacancies, 90% valid application routes, zero false eligibility claims, and cleared permission/attribution.

## Data changes and next step

- Added `IN-035` for the Walmart lead with status `unknown`; preserved the full canonical URL and the evidence/retrieval limitation.
- Added `INT-021` and `INT-022` for Threxil Systems' AI Intern and Frontend + AI Intern. The official careers page explicitly labels two roles open and says remote/work from anywhere; individual role pages welcome freshers and show direct forms. Recorded status as `open` on that explicit statement, while keeping country-specific legal eligibility, compensation, duration, employer-legitimacy review and automated-source permission unresolved.
- Appended the fresh Unisys evidence to `IN-029` without promoting its status.
- Preserved the existing expired GE Aerospace control and did not change status based on search indexing.
- Next: continue the independently assembled employer sample in bounded batches, prioritizing the international-remote segment. A rough internal segmentation currently finds 54 distinct role-like canonical URLs after excluding source-review/category rows and deduplicating exact canonical URLs; 38 are India-focused (including negative controls), 13 are non-India remote (including geography/freshness controls), and 3 are other location/work-mode cases. These labels are for sampling only, not eligibility or quality passes. The target is 25 international-remote listings, so 12 more distinct records need review before that segment is complete. Verify canonical requirements where possible, retain unknown where not, and keep source permission separate.


### Follow-up scope note

The Threxil records are two separate role pages under one employer, not duplicate observations of one requisition. They add useful positive fixtures for (a) AI retrieval/evaluation work with fresher-friendly requirements and (b) frontend work adjacent to AI features. The source sample remains convenience-selected and non-representative; the records do not establish source precision/recall or permission for automated collection or application. Official pages checked 2026-10-13: https://www.threxil.com/careers ; https://www.threxil.com/careers/apply/ai-intern ; https://www.threxil.com/careers/apply/frontend-ai-intern.


### International-remote follow-up — three additional records

| INT-026 | Cohere — Research Internship (Winter 2027) | Official Ashby page describes a remote research internship and explicitly lists Canada, Europe, UK, and US locations; India is not listed. | Requires a current PhD in ML/NLP/related field (exceptional non-PhD candidates may be considered), full-time 4–6 months, and work authorization in employment country. | `unknown`; preserve as a geography and seniority negative control, not an India-eligible role. |
| AUD-ZOLVE-20261013 | Zolve — Summer Internship Program 2026 | Official program page says Applications Closed; it describes a US-based remote internship program and lists an AI Intern among multiple roles. | Program-wide eligibility requires pursuing a Bachelor's or Master's degree in the US and valid work authorization conditions. It is a program page, not one requisition. | `not_a_listing`; use as closed-program/geography control, not a vacancy. |
- **MailerMen (INT-023):** The employer-hosted listing explicitly says Actively hiring, Remote (Worldwide), Freshers only, with a 3-month duration and stipend. It is stronger current and eligibility evidence than a third-party repost, although permission for automated collection/submission remains unknown.
- **QovaTech (INT-024):** The official page explicitly labels an open internship and remote-friendly setup. It requires a shipped LLM project; “serving clients worldwide” is not treated as proof that applicants from every country are eligible.
- **DataRobot (INT-025):** The official Workday search result shows US locations and Remote Canada-Ontario. The canonical page was unreadable through the retrieval interface, so status remains unknown and the record is retained as a geographic negative control rather than a confirmed vacancy.

Official pages checked 2026-10-13: https://www.mailermen.com/jobs/machine-learning-intern-python-scikit-learn-remote-worldwide-280 ; https://www.qovatech.com/careers/ai-engineer ; https://datarobot.wd1.myworkdayjobs.com/DataRobot_External_Careers/job/Boston-Massachusetts-US/Agentic-AI-Intern_R-102729. The sample is still convenience-selected and does not establish precision/recall or source permission.


### Additional restricted-remote controls

- Cohere Research Internship (Winter 2027) is explicitly remote but lists employment locations in Canada, Europe, the UK and US, not India, and has a PhD-level research requirement. It remains `unknown` for current status and is not treated as eligible for an India-based undergraduate.
- Zolve's official 2026 program page explicitly says applications are closed and eligibility requires a Bachelor's or Master's program in the US. Since it aggregates multiple roles, it is recorded as `not_a_listing` and excluded from vacancy counts.

References: https://jobs.ashbyhq.com/cohere/73bd3e2b-6597-4124-b64b-1e5dbc32e785 ; https://zolve.com/internship.


### Segmentation refresh after restricted-remote controls

Recalculated after adding INT-026 and the Zolve program control: 54 unique role-like canonical URLs; 38 India-focused records including negative controls; 13 non-India remote records including geographic/freshness controls; and 3 other location/work-mode cases. The international-remote segment target is 25, leaving 12 distinct records to review. The Zolve program page is excluded from vacancy counts as `not_a_listing`.


**Classification note:** Cohere Research Internship is counted in the non-India remote comparison because the employer's location whitelist explicitly lists Canada, Europe, the UK and US and does not list India. The phrase “India not listed” in its eligibility field is a documented restriction, not evidence that the role is India-focused. This is a sampling classification only; it does not imply eligibility.
