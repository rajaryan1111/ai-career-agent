# Official employer listing freshness audit — six additional records

**Checked:** 2026-10-13  
**Purpose:** Add fresh candidate leads and hard-negative controls to the mixed source-audit dataset.  
**Important:** This is a targeted web search, not a representative sample. A listing appearing on an official career page does not alone prove eligibility or live application availability. Status is set to unknown where direct evidence is incomplete.

## Summary

| ID | Listing | Evidence/status | Treatment |
|---|---|---|---|
| IN-025 | Airbus — Internship, India Innovation Team / GenAI Intern | Official Workday listing surfaced with Apply button; page snippet says posted two days earlier and duration is six months | High-confidence lead; confirm full requirements and live apply action before recommending |
| IN-026 | General Motors — AI/ML Student Intern, Body Digitization & AI | Official Workday listing says Bengaluru on-site, six months, 45 hours/week; search freshness evidence is inconsistent | Status unknown; recheck canonical requisition |
| IN-027 | vINe AI — ML Engineer Intern | Company careers page lists remote ML internship; application is a Google Form | Low-confidence lead; eligibility, pay, role duration and form privacy need review |
| IN-028 | ATRISI — ML/AI Intern | Official page lists Bengaluru remote/hybrid internship, but role details are sparse and form requests personal data | Low-confidence lead; verify role, organization, privacy and terms |
| NC-001 | Semark LLC — AI Engineer Intern | Canonical page explicitly says hiring finished 2026-10-11 and role is closed | Hard negative: stale indexed listing must not be recommended as open |
| NC-002 | BNP Paribas — Data Science Intern | Canonical page explicitly says position is already filled; last update 2026-10-12 | Hard negative: a current-looking page can still represent a filled role |

## Evidence details and source URLs

### IN-025 — Airbus GenAI internship
Official Workday page: https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Internship---India-Innovation-Team---GenAI-Intern_JR10446597

The listing describes a six-month role with RAG/LLM capability research and data preparation for fine-tuning. The page was indexed as posted two days before this audit and exposed an Apply action. Exact degree/year eligibility, location arrangement and compensation are not established by the inspected snippet. Keep unknown rather than infer.

### IN-026 — General Motors AI/ML student internship
Official Workday page: https://generalmotors.wd5.myworkdayjobs.com/en-GB/Careers_GM/job/Bengaluru-Karnataka-India/AI-ML-Student-Intern--Body-Digitization---AI_JR-202613434?source=LinkedIn

The indexed description says Bengaluru, on-site, six-month duration and 45 hours/week. It includes AI/ML, analytics, automation and engineering/manufacturing prototypes. The indexed search result and page freshness indicators did not agree cleanly; live-open status is unknown. It also contains sponsorship language, so do not infer eligibility from the India location alone.

### IN-027 — vINe AI ML Engineer Intern
Company careers page: https://www.vineai.co.in/careers  
Application form: https://docs.google.com/forms/d/e/1FAIpQLSe9Yu5hK6qu4LaZ4nHr2wpnouQh7p7R4vIHNQ4E8zI_8PjbVg/viewform?usp=send_form

The company page lists a remote ML Engineer Intern role involving Python, PyTorch/TensorFlow, transformers and fine-tuning. The linked Google Form destination was identified, but the form content/privacy notice was not accessible through the research browser. Country eligibility, pay, duration and requisition-level status remain unknown. This is a low-confidence lead, not a recommendation.

### IN-028 — ATRISI ML/AI Intern
Company role page: https://atrisi.org/collaborate/ml-ai-intern

The page says Remote/Hybrid, Bengaluru, India and describes ML workflows, evaluation and AI-native features. It links to LinkedIn, email and an on-site page form requesting contact details. The inspected page does not establish detailed requirements, pay, duration or current status. Verify organization, complete role details and privacy/terms before any application flow.

### NC-001 — Semark closed-role control
Canonical page: https://semarkglobal.com/careers/ai-engineer-intern

The employer page explicitly states hiring finished on 2026-10-11 and the role is closed, even though the page remains accessible and has detailed role content. This is a direct test for stale-result suppression.

### NC-002 — BNP Paribas filled-role control
Canonical page: https://group.bnpparibas/en/careers/job-offer/data-science-intern-1

The employer page explicitly says “Sorry, this position is already filled” and shows last update 12 October 2026. It describes a six-month internship in Bengaluru and a Master's-equivalent study level, but those details do not override the filled status. This is a direct test for status precedence.

## Product implications

1. **Closed/filled canonical status must override aggregator “active”, page availability, search recency, or a surviving application URL.**
2. Keep `last_checked_at`, provider `published_at`, canonical `updated_at`, employer status and application-link status as separate fields.
3. An `Apply` button or a linked form is not proof the vacancy remains open or that the form is safe to autofill.
4. Third-party forms and email applications need a separate disclosure/privacy review; do not transmit candidate data automatically.
5. If role requirements, location restrictions, country eligibility, duration or compensation are missing, store unknown and lower confidence.
6. Keep closed and filled roles in a negative-control test set, not in the active recommendation pool.

## Dataset update

Added rows `IN-025`–`IN-028` and negative controls `NC-001`–`NC-002` to `job-source-audit-seed-2026-10-13.csv`. Updated `IN-027` with the exact form destination found from the careers-page link. CSV schema remains 27 columns. The dataset is a mixed research set, not a count of unique open jobs.

## Decision

The best new lead for further verification is Airbus GenAI Intern, while GM requires a fresh canonical status check. vINe AI and ATRISI remain low confidence until eligibility/privacy checks are complete. Semark and BNP Paribas are explicitly closed/filled and must be excluded from recommendations. No source integration or application automation is approved; no candidate data was submitted.


## Dataset integrity check (after append)

A strict CSV parser found six pre-existing row-alignment defects in older entries: four unquoted commas split trailing review notes, and two rows had a stray `unknown` placeholder before the application URL. These have now been repaired without changing the intended evidence, and the entire file was re-parsed. The CSV has 49 data rows; header and every data row now have exactly 27 columns. Follow-up edits must keep CSV fields quoted correctly and rerun this validation.


## 2026-10-13 addendum — Apple degree gate and Sprinto application boundary

### IN-001 — Apple Applied ML Intern, Wireless Technologies & Ecosystems
Canonical page: https://jobs.apple.com/en-in/details/200686019-0321/applied-ml-intern-wireless-technologies-ecosystems

The official page states the minimum qualification is a PhD student in year 2 or beyond in AI/ML, Computer Science, Communication Engineering or a related field. It also describes strong ML/statistics/optimization and programming requirements; LLMs, RAG and AI agents are desirable rather than substitutes for the degree requirement. The listing was posted 27 September 2026, lists Bengaluru and 40 weekly hours, and shows a Submit CV action. The audit row now records the PhD gate and keeps vacancy status unknown pending a separate live-status check. Do not recommend it to an undergraduate based on the word “Intern”.

### IN-022 — Sprinto AI Implementation Intern
Canonical page: https://jobs.lever.co/Sprinto/6dfd5f41-57b6-40e8-9eab-ba4083c1a7c4

The official role page describes AI infrastructure, model training/evaluation pipelines, document parsing/search and LLM integration. The linked application page displays an hCaptcha challenge. Treat that as a hard human-intervention boundary: do not solve, bypass, or automate around the challenge. A visible Apply action supports listing discovery but does not establish permission for automated submission.

### Validation update
- Updated IN-001 with the explicit PhD-year eligibility gate and retained status unknown.
- Added SV-028 for Apple degree eligibility and SV-029 for the Sprinto CAPTCHA boundary in the source validation test suite.
- Updated the full CSV and strictly re-parsed it: 60 data rows, 27 columns, zero malformed rows, 60 unique IDs.
- No candidate data was sent, no application was submitted, and no challenge was solved or bypassed.
