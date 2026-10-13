# Official employer listing freshness audit — round 2

**Checked:** 2026-10-13  
**Method:** Targeted search of official employer career pages. This is a candidate-lead and negative-control audit, not a representative sample. Where page freshness or status is not explicit, status remains unknown.

## Summary

| ID | Listing | Observed evidence | Product treatment |
|---|---|---|---|
| IN-029 | Unisys — AI Engineering Intern | Official Workday page; Bangalore; posted four days ago in indexed result; AI pipelines, agents and test harnesses | High-confidence lead; verify full eligibility, duration, pay and live submit flow |
| IN-030 | AtkinsRéalis — Robotics & AI Engineering Intern | Official careers page; Bengaluru; robotics, computer vision, AI automation, digital twins | Medium-confidence lead; page is several weeks old; revalidate vacancy status |
| IN-031 | Needl.ai — AI Engineering Intern | Company careers page; Bengaluru hybrid; early-career role; apply by email | Medium-confidence lead; email submission requires explicit user approval |
| IN-032 | Concentric AI — Machine Learning Intern | Employer hiring page; six months; ML, LLM/RAG and vector databases; performance-based FTE conversion mentioned | Medium-confidence lead; verify current intake and compensation |
| IN-033 | Bruker — Graduate Apprenticeship Trainee, AI/ML | Official iCIMS page; Bangalore; position type Intern/Apprentice; indexed as posted around 2026-09-10 | Medium-confidence lead; recheck live status and apprenticeship eligibility |
| NC-003 | GE Aerospace — Data Science Intern | Official Workday result states application end date 2026-09-24, already past | Hard negative: don't recommend as open without a new requisition |

## Listing evidence

### IN-029 — Unisys AI Engineering Intern
Official page: https://unisys.wd5.myworkdayjobs.com/en-US/External/job/AI-Engineering-Intern_REQ574280

The indexed page says Bangalore, India, displays Apply, and describes converting AI pipelines into prototypes and production-ready solutions, building AI agents and reliable test harnesses. It does not establish duration, compensation, degree/year requirements or candidate-specific work authorization in the inspected excerpt.

### IN-030 — AtkinsRéalis Robotics & AI Engineering Intern
Official page: https://careers.atkinsrealis.com/en/jobs/intern-r-163438

The role describes robotics control, motion planning/navigation, sensors and actuators, simulation, ML/DL, object detection, predictive analytics and Python AI workflows. The indexed page is several weeks old, so page existence alone is not proof that the requisition remains open. Verify exact degree requirements, duration, work arrangement and compensation.

### IN-031 — Needl.ai AI Engineering Intern
Official page: https://needl.ai/careers/ai-engineering-intern

The company page says Bengaluru, hybrid, internship; it describes building agentic workflows for enterprise customers and indicates the role suits a fresh graduate or someone with 1–2 years of experience. The stated application route is email to `careers@needl.ai`. The agent must not email a CV or disclose candidate data without explicit user approval and review of the exact message/attachments.

### IN-032 — Concentric AI Machine Learning Intern
Official hiring page: https://concentric.greythr.com/hire/jobs/machine-learning-intern/

The page describes a six-month ML internship in Bengaluru, including model development/evaluation/deployment, Python ML frameworks, LLMs, RAG and vector databases. Performance-based full-time conversion is mentioned. The page does not establish stipend or live application status in the inspected snippet.

### IN-033 — Bruker Graduate Apprenticeship Trainee - AI/ML
Official page: https://internationalcareers-bruker.icims.com/jobs/19820/graduate-apprenticeship-trainee---ai-ml/job?in_iframe=1

The indexed page identifies Bangalore and position type Intern/Apprentice, with a posted date around 2026-09-10. Apprenticeship eligibility, complete qualifications, compensation and current status need direct verification.

### NC-003 — GE Aerospace Data Science Intern
Official page: https://geaerospace.wd5.myworkdayjobs.com/en-US/GE_ExternalSite/job/Data-Science-Intern_R5040035-1

The official Workday result gives an application end date of 2026-09-24. That date has passed as of 2026-10-13. The page may remain indexed and describe highly relevant AI/GenAI/LLM work, but the expired deadline overrides relevance. Keep it only as a closed/expired test fixture unless the employer confirms a new requisition.

## Product implications

1. **Eligibility is separate from relevance.** A strong RAG/agentic role is not a fit unless cohort, degree, experience and location requirements are satisfied.
2. **Email and external forms are human-approved boundaries.** Prepare a draft, but do not send candidate details or attachments without explicit confirmation.
3. **Application deadline precedence:** a past canonical deadline should suppress recommendations unless a fresh open requisition or employer confirmation supersedes it.
4. **Current status must be evidence-based.** Use `open`, `closed`, `expired`, `unknown` explicitly. Don't infer open from a working page or search result.
5. **Keep unknown fields unknown.** Pay, duration, eligibility and location arrangement should not be fabricated.
6. **Freshness recheck is time-bounded.** The timestamp of our last check must not be confused with the employer's publish/update timestamp.

## Dataset update

Added `IN-029` through `IN-033` and `NC-003` to `research/job-source-audit-seed-2026-10-13.csv`. The CSV now has 55 data rows. These remain mixed leads and controls, not 55 confirmed-open unique vacancies. Strict CSV validation is required after edits.

## Decision

Prioritize Unisys and Concentric AI for direct live-status/eligibility verification, followed by Needl.ai and Bruker. AtkinsRéalis needs freshness revalidation. GE Aerospace is an expired negative control. No production integration or application automation is approved; no candidate data was sent.
