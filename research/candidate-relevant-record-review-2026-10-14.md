# Candidate-Relevant Record Review — 2026-10-14

**Purpose:** Continue the source-quality gate by rechecking a small, prioritized set of India-focused and explicitly worldwide records against current official employer pages. This is a bounded manual sample, not a comprehensive validation of the 82-row audit.

## Method and boundaries

- Opened the canonical employer page on 2026-10-14 and recorded only evidence visible in the page.
- A current “open” label is retained only where the employer page explicitly states availability (or explicitly lists the role under open roles). An Apply button or application form alone does not prove current availability.
- Remote mode and applicant-country eligibility are separate. “Serving clients worldwide” is not applicant eligibility evidence.
- Status, degree/year, location/work authorization, role-family fit, direct application route, duplicates, and source permission are separate dimensions.
- No forms were submitted, no candidate data was transferred, and no source API endpoint was queried.

## Record-level findings

| ID | Record | Current page evidence | Status decision | Candidate fit / unresolved items |
|---|---|---|---|---|
| IN-004 | Trackmind — Junior AI Engineer | Official Lever page shows Hyderabad, on-site, an Apply link and says Internship in the heading; Work Details says Full-Time and requires 6 months–2 years of experience. [Canonical page](https://jobs.lever.co/trackmind/ad66c0ec-1ae9-47cb-9d5d-83ae1cb6d200) | **Unknown** — employment type conflict; no explicit current-open wording | Not suitable to recommend to a fresher until the role type and experience requirement are clarified. |
| IN-015 | RadialBrain — AI Engineering Internship | Official page says remote/work from anywhere, seeks engineering students in CS/IT/AI/data science/software engineering, and describes agents, automation and AI product engineering; application form is linked. [Canonical page](https://www.radialbrain.com/interns) | **Unknown** — no explicit open/actively-hiring statement or deadline captured | Role-family and student fit look promising; legal/work eligibility by jurisdiction and current intake are unconfirmed. Form presence is not availability proof. |
| IN-018 | Inferova — AI/ML Engineer Intern | Official page says Remote (India), internship, 3–6 months; currently pursuing/recently completed BTech/MTech/MS in CS/AI/ML or related; Python and PyTorch/TensorFlow/Hugging Face required. Apply form visible. [Canonical page](https://inferova.com/careers-ai-ml) | **Unknown** — no explicit current-open statement or deadline captured | Strong role-family and degree alignment, but current intake, stipend amount, and source permission are unresolved. |
| IN-034 | WATER — ML Intern Application | Official page is dated 2026-08-24 and says Hyderabad, on-site, six months full-time; current/recent BTech/MTech/MS in CS, EE, Maths or related, plus Python/PyTorch. Application form remains visible. [Canonical page](https://www.water.bio/careers/WR012) | **Unknown** — date and form do not establish current availability | Potentially relevant only if full-time on-site Hyderabad for six months is feasible; current intake and stipend remain unclear. |
| INT-021 | Threxil Systems — AI Intern | Official careers page explicitly says “2 roles open” and “Fully remote / Work from anywhere”; role page welcomes freshers/self-taught developers and lists Python, NumPy/Pandas, DSA, retrieval and evaluation. [Careers](https://www.threxil.com/careers) · [Role](https://www.threxil.com/careers/apply/ai-intern) | **Open** — explicit employer open-roles statement observed 2026-10-14 | Strong skill/level fit for AI application work. Legal/work authorization by jurisdiction, pay, duration, legitimacy signals, and automated-use permission remain unresolved. |
| INT-022 | Threxil Systems — Frontend + AI Intern | Same careers page explicitly lists two open roles and work from anywhere; role page welcomes freshers/self-taught developers and requests React, modern frontend tooling and some TypeScript. [Careers](https://www.threxil.com/careers) · [Role](https://www.threxil.com/careers/apply/frontend-ai-intern) | **Open** — explicit employer open-roles statement observed 2026-10-14 | Relevant to AI product/frontend engineering, not core ML research. Legal/work authorization, pay, duration, and automated-use permission remain unresolved. |
| INT-023 | MailerMen — Machine Learning Intern (Python, scikit-learn) | Official role page currently says “Actively hiring,” “Remote (Worldwide),” “Freshers only,” and “Open to applicants anywhere”; final-year student/recent graduate, Python/pandas/scikit-learn, three months, ₹15k–₹20k/month, and twice-weekly IST-afternoon overlap. Page states updated 2026-10-13. [Canonical page](https://www.mailermen.com/jobs/machine-learning-intern-python-scikit-learn-remote-worldwide-280) | **Open** — explicit availability and worldwide applicant wording observed 2026-10-14 | Strongest explicit worldwide/entry-level evidence in this small sample. Legal/tax/work authorization details and source terms still need review before any product integration. |
| INT-024 | QovaTech — AI Intern | Official role page says “Open internship · Remote-friendly,” with an Apply route; asks for a shipped LLM project, Python or TypeScript, embeddings/RAG/function calling/tool use. Company location is Alexandria, Egypt; “serving clients worldwide” is not an eligibility statement. [Canonical page](https://www.qovatech.com/careers/ai-engineer) | **Open** — explicit “Open internship” label observed 2026-10-14 | Technical relevance is high, but applicant-country eligibility is **unknown**. Do not label it worldwide or India-eligible without explicit evidence. |
| IN-002 | Drivetrain — Engineering Intern, Gen AI for FP&A | Official Lever page is readable and shows India, Remote, internship, CS engineering interns, RAG/agentic AI/LLMs, degree-in-progress/recently-completed, and an Apply route. [Canonical page](https://jobs.lever.co/drivetrain/bc1c17bc-86ac-4f00-a1e3-0eb85aae4fdc) | **Unknown** — no explicit current-open wording or deadline captured | Role relevance and broad education fit are promising; status and source permission remain unresolved. |
| IN-003 / INT-008 | Ema — AI/Data Resident and aggregator comparison | Canonical Ashby page returned only a JavaScript shell in the research browser; the aggregator row points to the same requisition. [Canonical page](https://jobs.ashbyhq.com/ema/e0511c0c-998f-4079-b62c-d2f164bf2c86) | **Unknown** — canonical requirements/status not readable in this check | Count the exact requisition once. Keep INT-008 as a source-comparison/provenance record, not a second vacancy. |
| IN-025 | Airbus — GenAI Intern, India Innovation Team | Canonical Workday page returned no readable lines in the research browser. Earlier search evidence is provisional. [Canonical page](https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Internship---India-Innovation-Team---GenAI-Intern_JR10446597) | **Unknown** — canonical status and full requirements could not be independently rechecked | Do not recommend as verified-open until canonical evidence is available. |

## Snapshot after this review

Re-parsed the current CSV after updates:

| Check | Result |
|---|---:|
| Records / columns | 82 / 27 |
| Malformed-width rows | 0 |
| Duplicate listing IDs | 0 |
| `open` | 9 |
| `unknown` | 62 |
| `expired` | 3 |
| `closed` | 2 |
| `not_a_listing` | 2 |
| `source_review` | 4 |
| Permission field = `unknown` | 77 |

The status count is not the count of suitable vacancies. This review reconfirmed three explicitly open roles in the prioritized sample (Threxil AI Intern, Threxil Frontend + AI Intern, MailerMen ML Intern) and QovaTech's explicit “Open internship” label. QovaTech remains geography-unconfirmed; Threxil's legal/work eligibility remains unresolved by jurisdiction; MailerMen's explicit worldwide wording is stronger but does not settle every legal/tax question. Permission remains unknown for all four.

## Gate decision

**NOT PASSED — continue research only.**

- The ≥20 valid/relevant currently available listing threshold has not been demonstrated.
- The ≥90% direct-link validity metric remains unmeasured with a proper HTTP/outcome denominator.
- This sample has no newly observed false worldwide claim promoted to a positive label, but the full claim-level audit remains incomplete.
- Source terms/permission remain unresolved; public visibility and a live application form are not permission to collect, cache, autofill, or submit.
- The international-remote explicit-geography sample target remains a research-control milestone, not evidence of India eligibility or current availability.

## Next step

Review the remaining high-confidence India-focused records and any explicitly worldwide records with the same evidence fields. Then compute the strict unique, candidate-relevant, currently available count after duplicate and negative-control exclusion. Keep source permission as a hard gate. Do not implement connectors or application automation until every acceptance criterion passes.


## Second bounded India-focused review — 2026-10-14

Official employer pages and current search-indexed canonical content were checked for the next India-focused batch. This remains a manual research sample, not a source-permission approval or representative vacancy census.

| Record(s) | Current official evidence | Decision and limits |
|---|---|---|
| IN-020 / IN-028 — ATRISI ML / AI Intern | [ATRISI careers index](https://atrisi.org/careers) explicitly labels the role **Open**; [role page](https://atrisi.org/collaborate/ml-ai-intern) says Remote / Hybrid, Bengaluru and provides form, LinkedIn and email routes. | Updated both observations to `open` because the employer index explicitly says Open. IN-028 is a duplicate observation of IN-020, not another vacancy. Responsibilities, duration, stipend, intake deadline and privacy terms remain incomplete; source/product permission remains unknown. |
| IN-016 — Zyora Labs AI/ML Research Intern | [Official careers page](https://www.zyoralabs.com/careers) says “Open internships”; student eligibility says any year/stream and basic Python, Remote / Nagercoil. [Onboarding page](https://zyoralabs.com/internship) presents a broad confidentiality agreement and says work created belongs to Zyora Labs. | Updated to `open` for an explicitly advertised track, but do not count as a unique confirmed requisition until the shared-page tracks are distinguished. Compensation, duration, intake end date and data privacy/retention are unspecified. The candidate should review the NDA/IP terms before agreeing. Permission to integrate or collect listings remains unknown. |
| IN-017 — Zyora Labs AI/ML Project Intern | Same official page labels the section “Open internships”; role says students welcome, basic Python, no prior experience required. Same general application route as IN-016. | Updated to `open` as an advertised track, not proof of a separately funded/active requisition. Keep shared-page relationship explicit; do not double-count before employer confirms distinction. NDA/IP, compensation, duration and privacy remain review items. |
| IN-019 — Hajana Technologies AI/ML Intern | [Official role page](https://hajanatechnologies.com/careers/ai-ml-intern) says remote, 9 PM–6 AM IST; eligibility is CSE/AI/ML degree and 2025/2026 pass-outs only. Careers index shows View & Apply but not an explicit current-open label. | Remains `unknown`; the cohort restriction may not fit a currently enrolled student and must not be inferred away. Application form asks for Father/Husband Name; no autofill or submission without explicit candidate review. |
| IN-013 / INT-014 — CertifyOS AI Intern | [Canonical Ashby content](https://jobs.ashbyhq.com/certifyos/4bcdec99-9f2e-416c-8e26-498c94c5898a/) describes Pune, remote, six-month ML engineering contract and production Python/testing/evaluation/GCP. Retrieved content is stale-indexed and has Apply but no explicit current-open wording. | Remains `unknown`; INT-014 is the same requisition/source-comparison control, not another vacancy. Need current employer confirmation and full eligibility. |
| IN-021 — Onelogica | [Official careers page](https://www.onelogica.com/careers/) says six current opportunities and separately lists an “Internship AI Engineer - Intern” (0–1 years, Delhi/NCR, in-office) and “Full Time Data & AI Engineer – GenAI Platforms” (0–1 years, Delhi/NCR, in-office). | Remains `unknown`: the CSV title “Internship Data & AI Engineer — GenAI Platforms” does not cleanly match either displayed role. Do not conflate the internship and full-time listings until the exact requisition/detail URL is established. |
| IN-035 — Walmart Global Tech India Gen AIML Engineering Intern | [Official Workday result](https://walmart.wd504.myworkdayjobs.com/en-US/WalmartExternal/job/IN-KA-BANGALORE-Home-Office-PTPP1/XMLNAME--IND--Grad-Intern---No-Work-Experience_R-2607497) shows Bengaluru, full-time, posted 8 days ago, Apply, and a Gen AIML Engineering Intern summary. | Remains `unknown`: posting recency and Apply do not alone establish current vacancy status. Degree/year eligibility, work mode, duration, compensation and deadline require further canonical review. |
| NC Bruker Graduate Apprenticeship Trainee — AI/ML | [Official iCIMS page](https://internationalcareers-bruker.icims.com/jobs/19820/graduate-apprenticeship-trainee---ai-ml/job?in_iframe=1) says Bengaluru, Intern/Apprentice, posted 2026-09-10, and recent bachelor's graduates in CS/allied courses. | Remains `unknown`: no explicit current-open statement was confirmed in this pass; whether ECE qualifies as “allied” and the intake deadline/terms need confirmation. |

### Updated audit integrity after second batch

| Check | Result |
|---|---:|
| Records / columns | 82 / 27 |
| Malformed-width rows | 0 |
| Duplicate listing IDs | 0 |
| Distinct canonical URL values | 73 |
| Repeated canonical URL groups | 8 |
| `open` | 13 |
| `unknown` | 58 |
| `expired` | 3 |
| `closed` | 2 |
| `not_a_listing` | 2 |
| `source_review` | 4 |
| Permission field = `unknown` | 77 |

These are **status labels across mixed audit rows**, not 13 unique suitable vacancies. At least one open-status row is a duplicate ATRISI observation; the two Zyora tracks share one careers page and are not counted as two distinct requisitions without confirmation. No source permissions were upgraded.

### Gate decision

**NOT PASSED — research only.** This pass produced stronger current evidence for explicitly advertised India-focused internship tracks, but did not establish the required 20 unique, relevant, currently available listings; a measured ≥90% direct-link validity rate; a complete worldwide-eligibility audit; or resolved source terms. No source API was queried and no code, connector, dependency, candidate-data transfer, autofill or application submission was performed.
