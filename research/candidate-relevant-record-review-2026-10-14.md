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


## Third bounded India-focused recheck — 2026-10-14

This pass rechecked seven candidate-relevant records against official employer pages/search-indexed canonical content. The audit CSV was updated for IN-006, IN-023, IN-024, IN-027, IN-030, IN-031 and IN-032.

| Record | Evidence from official employer page | Classification |
|---|---|---|
| IN-006 — General Motors AI/ML Student Intern | [Official Workday page](https://generalmotors.wd5.myworkdayjobs.com/en-GB/Careers_GM/job/Bengaluru-Karnataka-India/AI-ML-Student-Intern--Body-Digitization---AI_JR-202613434) identifies requisition JR-202613434, Bengaluru on-site, full-time, 45 hours/week, six months, and Python/NumPy/Pandas/ML tasks. It explicitly says GM does not provide immigration-related sponsorship for this role. Eligible fields list CS, Data Science, AI, Mechanical, Industrial, Manufacturing, Statistics or related; ECE is not explicit. | **Unknown** — Apply control and older “posted 3 days ago” index evidence are not current-open confirmation in this pass; ECE-related-field eligibility needs employer clarification. |
| IN-023 — Meraki Labs AI Engineer Intern | [Official Ashby page](https://jobs.ashbyhq.com/Meraki-Labs/93ff65d2-f0cd-4fd1-b76f-b2e350f2d6c8) says Bengaluru, on-site, but Employment Type is **Full time**. Requires current students in named highly selective institutions, strong academic proof, public GitHub and preferably prior internships. | **Unknown** — title/employment-type tension and no explicit current-open wording. Do not infer broad ECE eligibility from the exception for exceptional non-computing candidates. |
| IN-024 — Sarvam ML & Speech Data Pipeline Intern | [Official Ashby page](https://jobs.ashbyhq.com/sarvam/5588ec03-74d6-4b45-aa66-bace8ce1d38b) describes Bengaluru, on-site work on speech-data pipelines, audio/video processing and Python scripts. The retrieved indexed page was crawled about four months ago. | **Unknown / stale lead** — role details are relevant but indexed freshness is insufficient to claim current availability. |
| IN-027 — vINe AI ML Engineer Intern | [Official careers page](https://www.vineai.co.in/careers) explicitly labels its section “Open Positions” and lists ML Engineer Intern under Remote AI/ML internships; Python, PyTorch/TensorFlow, transformers and LLM/Ollama are mentioned. Apply Now routes to a Google Form whose privacy/terms were not verified. | **Open (employer advertises an open position)** — do not submit candidate data until the form's privacy terms and employer details are reviewed. Duration, compensation and product/source permission remain unknown. |
| IN-030 — AtkinsRéalis Robotics & AI Engineering Intern | [Official careers page](https://careers.atkinsrealis.com/en/jobs/intern-r-163438) lists Bengaluru and Ref R-163438, but Employment Type is **Full time** despite the “Intern” title. Requirements name final/pre-final B.Tech/B.E. in CSE, Data Science, AI/ML, Robotics or Mechatronics with AI/Robotics specialization; Python mandatory. | **Unknown** — full-time/internship mismatch and no explicit current-open wording; ECE is not listed explicitly. |
| IN-031 — Needl.ai AI Engineering Intern | [Official role page](https://needl.ai/careers/ai-engineering-intern) and [careers page](https://needl.ai/careers) explicitly list AI Engineering Intern among open positions; Bengaluru hybrid, three office days/week. Role targets recent B.Tech/M.Tech or equivalent CSE/EE/related graduates, or 1–2 years relevant experience, with Python and applied AI/LLM/agent/RAG work. Careers page says open internships have a monthly stipend but does not specify the amount. | **Open (explicit careers-page listing)** — hybrid Bengaluru, not remote-anywhere. Application is by email; none was sent. Permission for product collection remains unknown. |
| IN-032 — Concentric AI Machine Learning Intern | [Official hiring page](https://concentric.greythr.com/hire/jobs/machine-learning-intern/) describes six months plus performance-based FTE conversion, Bengaluru, Python ML and LLM/RAG/vector DB exposure. It also labels Job Type “Full-time”, experience 0–1 years and Posted a month ago. | **Unknown** — internship/full-time metadata tension and no explicit current-open wording. Apply form is not enough to promote status. |

### Integrity and status after this pass

Re-fetched the CSV after the edits. The audit remains 82 rows and 27 columns, with 0 malformed rows, 0 duplicate listing IDs, 73 distinct canonical URL values and 8 repeated-URL groups. Status labels are now **15 open, 56 unknown, 3 expired, 2 closed, 2 not_a_listing and 4 source_review**. Permission remains unknown on 77 rows. These are mixed audit observations, not 15 unique, candidate-ready vacancies; duplicate controls and shared-page tracks remain excluded or unresolved for unique-vacancy counting.

No connector or source API was integrated or queried. No candidate data was submitted to vINe AI's Google Form or Needl.ai by email. The source-quality gate remains **NOT PASSED / research-only**.


## Fourth candidate-focused status check — 2026-10-14

Two more records have stronger current availability evidence from their official pages. These updates concern listing status only; they do not approve data collection or resolve every candidate-eligibility question.

| Record | Canonical evidence | Status and caveats |
|---|---|---|
| IN-008 — Humans Care Foundation, AI / Machine Learning Engineer | [Official careers index](https://www.thehcf.in/careers) says “Accepting applications 5 open” and lists J01 AI / Machine Learning Engineer among the five roles. [Role page](https://www.thehcf.in/careers/ai-ml-engineer) says Remote, anywhere in India; paid merit-based internship, one month initially with extension on performance; Python, PyTorch/TensorFlow, model evaluation/deployment, RAG and production AI pipelines. | Updated to **open**. The stipend amount, eligibility details, candidate-data privacy/retention and product/source permission remain unresolved. Crucial distinction: HCF separately offers a two-week ₹500 traineeship that the employer describes as training, not a job. Never conflate that candidate-paid programme with the paid internship. |
| IN-009 — EduRankAI, Deep Learning Engineering Intern (AICTE portal) | [Official AICTE National Internship Portal listing](https://internship.aicte-india.org/internship-details.php?uid=SU5URVJOU0hJUF8xNzg4MzQzNTgxNmE5N2Y1MWRjMWYyYQ%3D%3D) dated 2026-09-02 shows Pan India, Full Time, immediate start, three months, ₹0/month stipend, 12 credits and an apply-by date of 2027-03-02. | Updated to **open** because the listing remains presented with a future application deadline. The zero stipend and full-time workload are material; employer/requisition legitimacy, exact degree/year criteria, schedule, privacy and source/product permission still require review. |

### Latest audit snapshot

After updating and re-fetching the CSV: 82 rows, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URL values, 8 repeated-URL groups. Status labels: **17 open, 54 unknown, 3 expired, 2 closed, 2 not_a_listing, 4 source_review**. Permission field remains unknown for 77 rows. These remain mixed audit records and not 17 unique, fully verified candidate-ready jobs.

**Gate remains NOT PASSED / research-only.** No API was queried; no connector, dependency, or production code was added; no candidate data was sent and no application submitted.


## Fourth candidate-focused status check — 2026-10-14

Two records have stronger current availability evidence from official pages:

- **IN-008 — Humans Care Foundation, AI / Machine Learning Engineer.** The [official careers index](https://www.thehcf.in/careers) says it is accepting applications for five open roles, including J01. The [role page](https://www.thehcf.in/careers/ai-ml-engineer) says remote anywhere in India, paid merit-based internship, one month initially with extension on performance, and work involving Python, PyTorch/TensorFlow, model evaluation/deployment, RAG and production AI pipelines. Status updated to open. Stipend amount, eligibility and privacy/source permissions remain unresolved. Important: HCF separately offers a two-week ₹500 traineeship, which the employer describes as training rather than a job; do not merge it with the paid internship.
- **IN-009 — EduRankAI Deep Learning Engineering Intern (AICTE portal).** The [official portal listing](https://internship.aicte-india.org/internship-details.php?uid=SU5URVJOU0hJUF8xNzg4MzQzNTgxNmE5N2Y1MWRjMWYyYQ%3D%3D) dated 2026-09-02 shows Pan India, full-time, immediate start, three months, ₹0/month stipend, 12 credits and apply-by 2027-03-02. Status updated to open because the listing has a future deadline. Employer/requisition legitimacy, eligibility, workload, privacy and source permission remain unresolved. Zero stipend must remain visible to candidates.

Latest CSV snapshot after updates: 82 rows, 27 columns, 0 malformed rows, 0 duplicate IDs, 73 distinct canonical URLs, 8 repeated-URL groups; status labels 17 open, 54 unknown, 3 expired, 2 closed, 2 not_a_listing and 4 source_review. Permission remains unknown for 77 rows. These are mixed audit records, not 17 unique fully verified vacancies. Gate remains NOT PASSED / research-only. No API queried, no production integration added, and no candidate data or applications submitted.


## Fifth candidate-focused status check — 2026-10-14

### IN-022 — Sprinto, AI Implementation Intern
The current official Sprinto Lever careers board lists AI Implementation Intern under AI Office with a Remote workplace label and an Apply route; the canonical role page describes work on AI infrastructure, model training/evaluation pipelines, document parsing, search and LLM integration. Requirements include currently pursuing a degree in Computer Science, Engineering, Data Science or a related technical field, Python and basic ML familiarity. The CSV status was updated to **open** based on the current employer-board listing. The page labels the role Bengaluru / Remote, but does not establish worldwide eligibility; duration, compensation and source/product permission remain unknown. No application submitted. [Official role](https://jobs.lever.co/Sprinto/6dfd5f41-57b6-40e8-9eab-ba4083c1a7c4) · [Current employer jobs board](https://jobs.lever.co/Sprinto).

### Recheck: IN-002 Drivetrain and IN-029 Unisys
The current Drivetrain board still lists Engineering Intern – Gen AI for FP&A Platform as Remote / Internship / India. This supports current availability, but the audit CSV still has IN-002 as unknown because a safe single-row update was not completed in this pass. Unisys AI Engineering Intern (REQ574280) is listed in Bengaluru and its requirements explicitly call for a currently pursuing or recently completed M.Tech in CS, AI/ML or related, including final-year M.Tech students/recent graduates; this is not a straightforward match for the target BTech ECE undergraduate. Keep candidate fit separate from vacancy status and do not recommend as a direct fit without further eligibility evidence. [Unisys official role](https://unisys.wd5.myworkdayjobs.com/en-US/External/job/AI-Engineering-Intern_REQ574280).

### Research controls
Current web checks found a material contradiction on Concentric AI: its page describes a six-month intern role but the application metadata says Job Type “Full-time”. AtkinsRéalis likewise titles the role an intern while listing Job Type “Full time” and restricting degree examples to CSE/Data Science/AI-ML/Robotics/Mechatronics with AI/Robotics specialization. Keep both as **unknown** rather than interpreting “Intern” in the title as proof of internship employment type or ECE eligibility. [Concentric AI](https://concentric.greythr.com/hire/jobs/machine-learning-intern/) · [AtkinsRéalis](https://careers.atkinsrealis.com/en/jobs/intern-r-163438).


## Sixth candidate-focused recheck — 2026-10-14

### Needl.ai: confirm current listing and separate eligibility from fit
The current official careers index lists **AI Engineering Intern** under open positions and says the Bengaluru team works hybrid, three days per week in the office; it also says interns receive a monthly stipend, without publishing the amount on the reviewed page. The role page says it targets recent graduates with B.Tech/M.Tech or equivalent in CSE/EE/related, or applicants with 1–2 years of relevant experience, and involves building agentic workflows, RAG, Python and customer-facing implementation. This corroborates the existing `open` label on IN-031 but does **not** establish that a currently enrolled BTech ECE student is eligible; degree-equivalence and cohort timing need confirmation. No email was sent. [Official careers index](https://needl.ai/careers) · [Role page](https://needl.ai/careers/ai-engineering-intern).

### Threxil Systems: current open roles, not proof of worldwide legal eligibility
The official careers page currently states “2 roles open”, “Fully remote”, and “Work from anywhere”, and lists AI Intern and Frontend + AI Intern. It explicitly welcomes freshers/self-taught candidates on the page; AI Intern work focuses on retrieval and evaluation layers. These records already have `open` status (INT-021 and INT-022); this pass reconfirms the evidence, not the source permission. “Work from anywhere” is employer marketing wording and is not a complete determination of hiring-country, tax, payroll or work-authorization rules. Candidate-data privacy/retention and source/product permission remain unverified. [Official careers page](https://www.threxil.com/careers) · [AI Intern](https://www.threxil.com/careers/apply/ai-intern) · [Frontend + AI Intern](https://www.threxil.com/careers/apply/frontend-ai-intern).

### Candidate triage implication (BTech ECE, currently enrolled)
- **Worth a careful manual first look:** Threxil AI Intern and Sprinto AI Implementation Intern. Threxil explicitly lists open roles and welcomes early-career candidates; Sprinto accepts currently pursuing an Engineering degree, though the exact interpretation of “related technical field” for ECE is not explicit.
- **Potential lead with a key eligibility question:** HCF AI/ML Engineer internship. It is paid and remote anywhere in India according to the current careers page, but role-specific degree/selection criteria and exact stipend remain unclear. Keep the ₹500 traineeship separate; it is candidate-paid training, not the internship.
- **Do not treat as automatic fit:** Drivetrain says Computer Science engineering interns and asks for CS or related degree; Needl.ai targets recent graduates or 1–2 years' experience and asks for CSE/EE/related; confirm ECE and current-student eligibility before investing time.
- **Not a paid-job recommendation:** EduRankAI via AICTE is listed at ₹0/month and full-time for three months; its employer/requisition legitimacy and workload remain unresolved.

### Evidence and integrity note
This pass relied on current official employer pages for availability and role description. It did not verify applicant privacy terms, automated collection/republication rights, or all legal work-eligibility conditions. Do not submit resumes, contact employers, or automate applications as part of this audit. Gate remains **NOT PASSED / research-only**.


## Seventh candidate-focused batch — 2026-10-14

This batch rechecked current public-web evidence and added Valura.AI as a new, conservative audit lead.

| ID | Record | Current page evidence | Status decision | Candidate fit / unresolved items |
|---|---|---|---|---|
| IN-036 | Valura.AI — AI Engineering Intern (Python) | [Official role page](https://careers.valura.ai/836918cc-4b0f-4207-b364-e277600fd43f) says posted 2026-07-27; locations include Chennai, GIFT City or Remote; duration 3–6 months with full-time preferred; 0–3 years experience; Python, LLM APIs, agent orchestration, MCP, RAG, retrieval and evaluation work. | **Unknown** — apply route exists, but no explicit current-open wording was captured in this pass. | Strong technical overlap with AI-agent/RAG/evaluation work. Degree requirement, applicant-country/work authorization, stipend amount and current intake remain unresolved. Do not promote to open or candidate-eligible based on the Apply route alone. |

Additional controls:
- [RadialBrain's official careers page](https://www.radialbrain.com/careers/) states its internships are for current students and remote across India; it describes an AI Engineering Intern role involving agents, automation and product engineering. No explicit current-open statement was found, so IN-015 remains `unknown`.
- [Unisys AI Engineering Intern](https://unisys.wd5.myworkdayjobs.com/en-US/External/job/AI-Engineering-Intern_REQ574280) is Bangalore-based and asks for current/recent M.Tech candidates; it is not a direct match for the target BTech ECE undergraduate without further eligibility evidence.
- [Jobicy's Spotify CoLM 2026 listing](https://jobicy.com/jobs/154386-colm-2026-intern) specifies UK, USA and Sweden and says the expression of interest is for candidates participating in CoLM, not a general vacancy. Treat it as an international-geography/posting-type negative control, not an India-eligible role.
- A current search result for Flocci's AI Engineering Intern displayed a 2026-09-30 application close date. Because that date precedes this review, it is excluded unless canonical evidence confirms reopening.
- Jobicy's [official API documentation](https://jobicy.com/jobs-rss-feed) allows normal product integrations subject to attribution and preservation of its canonical listing URL. Its public feed does not guarantee an employer ATS URL; absence from the last-seven-days feed is not proof of closure. No API endpoint was queried in this pass.

After adding IN-036, the CSV has 83 records, 27 columns, 0 malformed-width rows, 0 duplicate IDs, 74 distinct canonical URLs and 8 repeated-URL groups. Status labels: 19 open, 53 unknown, 3 expired, 2 closed, 2 not_a_listing and 4 source_review; permission is unknown for 78 records. These are mixed audit records, not unique candidate-ready vacancies. The 50-record sample and the overall source-quality gate remain **NOT PASSED / research-only**.


## Eighth candidate-focused validation pass — 2026-10-14

Opened 50 canonical URLs for a fixed QA roster (25 India-focused and 25 international-remote), with one canonical URL per sample row and negative controls intentionally retained. The roster is documented in [50-Record Candidate-Validation Roster](50-record-candidate-validation-roster-2026-10-14.md). It is not 50 open jobs or a candidate-ready shortlist.

New direct destination findings:
- Apple IN-001: canonical page explicitly says the role does not exist or is no longer available; status changed from unknown to closed.
- Matrice AI IN-007: canonical page renders 404 / Job Not Found; existing expired status retained because its recorded deadline had already passed.
- Bruker IN-033: research browser returned HTTP 410 Gone for the canonical iCIMS URL; status changed from unknown to closed at this URL. Any replacement requisition must be verified independently.
- AtkinsRéalis IN-030: stored role URL redirects to the generic careers search page rather than the specific role; status remains unknown and the role-deep-link check fails.
- Azul INT-032: research browser returned a fetch error without HTTP status; this remains unknown, not a dead-link finding.
- Several Ashby/Workday pages returned a page title or JavaScript shell but no readable role body. This is a research-renderer limitation, not evidence the role is closed.

The roster includes the GM role once: IN-006 and IN-026 are locale/parameter variants for the same requisition, so IN-026 is excluded. The sample has 50 records and 50 unique canonical URL values. Direct-employer link validity is still **not measured**: page retrieval does not prove that the Apply action works, and careers-index links are not necessarily role-deep-links.

CSV baseline after status corrections: 83 records, 27 columns, 0 malformed rows, 0 duplicate listing IDs, 74 distinct canonical URLs, 8 repeated URL groups. Status counts are 19 open, 51 unknown, 3 expired, 4 closed, 2 not_a_listing, and 4 source_review; permission remains unknown for 78 rows. These are mixed audit records, not unique eligible vacancies. Gate remains **NOT PASSED / research-only**.
