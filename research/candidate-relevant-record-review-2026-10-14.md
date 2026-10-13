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
