# Job-Source Coverage Audit — Initial Pilot

**Checked:** 2026-10-13  
**Stage:** Research only; no implementation authorized.  
**Purpose:** Start the planned source-coverage audit before choosing any source connectors. This is an initial qualitative pilot, **not** the planned 50-listing audit and not a statistical estimate of source quality.

## Executive readout

The first pilot supports four conclusions:

1. **Direct employer ATS boards are useful and machine-readable enough to investigate, but discovery is fragmented.** Current indexed examples appear on Lever (Drivetrain, Sprinto, Mactores, Whiterabbit) and Ashby (Ema, CertifyOS, Meraki Labs, Cohere, STRATIVIS, Output Biosciences, GPTZero, Preference Model). Search engines can surface these, but that does not prove broad recall or stable, authorized bulk access.
2. **“Remote” must never be treated as “worldwide.”** Cohere's Winter 2027 remote ML internship lists Canada, Europe, the UK and the US, not India. STRATIVIS explicitly says US-based. Ema, by contrast, labels its role India-remote. Geography and work authorization need explicit fields and evidence.
3. **Eligibility is often buried in the description rather than the listing card.** Ema's AI/Data Resident role specifies final-year enrollment, graduation timing and an 8.0 GPA threshold; a title-only matcher would likely over-rank it for many candidates. Research roles can require PhD-level or strong research experience.
4. **A source can be relevant but not enough on its own.** Individual company boards show useful roles, but each board covers one employer. An aggregator may improve recall, while official employer pages should remain the validation source.

No source in this pilot has yet earned a claim of comprehensive coverage, guaranteed freshness, or permission for all automated uses.

## Pilot listing observations

| Region / role | Evidence observed | Candidate-fit / freshness implication | Audit disposition |
|---|---|---|---|
| **India — Ema, AI/Data Resident** | Employer's Ashby listing says India-remote; six-month program; final-year CS/related degree, graduation by June next year, GPA 8.0+; stipend listed as ₹65,000/month. | Strong example of why detailed eligibility extraction matters. A student outside the graduation/GPA conditions should be hard-filtered. | High-value test case; recheck live status before showing to a user. |
| **India — Drivetrain, Engineering Intern – Gen AI for FP&A Platform** | Employer's Lever board lists the role as remote, internship, India. The application page exposes resume, name, email, phone, location, current company and LinkedIn fields. | Strong candidate for testing direct job detail + form-field inventory. The board excerpt alone does not establish all eligibility criteria or that automated submission is permitted. | High-value workflow test; user-controlled submission only. |
| **India — Sprinto, AI Implementation Intern** | Employer's Lever board recently listed an AI Implementation Intern as remote, Bengaluru. | Relevant AI-adjacent role, but title alone cannot establish whether it is engineering, solutions work, or suitable for a given student's goals. | Inspect full description and role category before scoring. |
| **India — Mactores, Generative AI Engineer (Intern)** | Employer's Lever board indexed a remote full-time internship in Mumbai. | Relevant title, but current status, actual duties, eligibility and compensation need a live detail check. | Candidate source; not yet validated for the final shortlist. |
| **India — Meraki Labs, AI Engineer Intern** | Ashby listing says Bangalore, India; full-time and on-site. | A location/work-mode mismatch should be an immediate exclusion for a user requiring remote work or unable to relocate. | Good negative test for hard filters. |
| **India — CertifyOS, AI Intern** | Ashby search result says Pune, India, remote; search index was last crawled about two months before this audit. | Potentially relevant, but stale indexing makes open/closed status uncertain. | Do not present as confirmed open without live verification. |
| **India — Libra AI, AI PM Intern** | Ashby result describes a Bengaluru on-site product internship; indexed several months ago. | AI-related does not necessarily mean AI/ML engineering; also stale and on-site. | Out of scope for an AI/ML-engineering-focused first audit unless the user wants product roles. |
| **International — Cohere, Machine Learning Intern/Co-op (Winter 2027)** | Employer's Ashby listing says remote, but the listed geographies are Canada, Europe, UK and US. | A generic “remote” tag would falsely suggest India eligibility. Also likely research/ML depth requirements. | Good hard-geography test; not eligible for an India-based candidate unless employer confirms otherwise. |
| **International — STRATIVIS, Machine Learning Engineering Internship** | Ashby listing describes a 12-week, 30-hour/week, paid remote role at $30/hour and explicitly says US-based. | “Remote” is country-bounded. Must not be ranked as available from India. | Exclude for India-based candidate absent explicit cross-border eligibility. |
| **International — Whiterabbit.ai, Research Scientist Intern (2026)** | Employer's Lever page currently exposes a remote research internship focused on deep learning/computer vision and asks for a strong research background. | Remote geography and academic requirements are not fully resolved in the visible excerpt. “Intern” does not imply entry-level accessibility. | Needs eligibility/geography verification; keep confidence low until confirmed. |
| **International — Output Biosciences, Research Intern (PhD), Machine Learning** | Ashby result describes remote/New York options and research internship work; title explicitly indicates PhD. | A strict candidate profile should not treat it as a general undergraduate internship. | Hard-filter for candidates without the stated PhD status/requirement. |
| **International — GPTZero, Machine Learning Intern** | Ashby result lists Toronto/NYC hybrid locations, despite a remote label in metadata. | Location-type labels can conflict with actual work arrangement. Needs detailed reconciliation. | Do not assume fully remote or worldwide. |
| **International — Preference Model, ML Engineer, RL Environments Internship** | Ashby result says San Francisco/Toronto; San Francisco preferred and Toronto remote considered. | “Remote considered” is not proof of worldwide remote hiring; highly specialised role. | Geography and technical bar must be checked individually. |
| **International — Tesla, AI Engineer Intern (Fall 2026/Winter 2027)** | Official careers result lists Palo Alto, California; on-site/full-time, 12-week minimum, and currently enrolled students. | A strong negative test for work-mode, location and schedule constraints for an India-based student. | Exclude unless the candidate can meet all stated constraints. |

## Source quality and platform implications

### Direct employer boards (Lever / Ashby / Greenhouse)

- **Best current validation target:** the employer's canonical job detail page, because it can expose location, employment type, responsibilities, eligibility, compensation, and the apply link.
- **Potential discovery strategy:** a small set of source-specific public job-board feeds/APIs where documented, plus targeted discovery/search. Do not assume that the ATS supports global search across all employers.
- **Important separation:** the ability to read a public job board does not itself grant permission to automate the application form or submit applications.

### Aggregators and directories

- **Potential recall boost:** AI/dev-job APIs and remote-job feeds may reduce the cost of discovering candidate URLs.
- **Required validation:** follow each listing to the employer's official page, compare title/location/work mode/status, deduplicate by canonical employer URL or requisition ID, and preserve a last-checked timestamp.
- **No shortcut around terms:** API availability, a “free” tier, or a directory entry does not establish ongoing zero-cost use, commercial redistribution rights, freshness, completeness, or permission to scrape.

### India-focused opportunity sources

- AICTE's National Internship Portal is a potentially useful India-specific discovery source and explicitly presents itself as a Ministry of Education / AICTE initiative. However, the current page is highly dynamic and the exact quality, freshness, API access, terms for automated use, and ability to verify individual employer listings still need source-specific checks. Treat it as a candidate for manual review, not a validated connector.
- Do not infer that every opportunity on an aggregator is employer-verified simply because the aggregator uses that wording. Verify a sample against the employer or official scheme.

## What this pilot does and does not prove

**It does prove:** direct ATS pages can expose useful entry-level AI-related roles; remote geography, degree/GPA, seniority, schedule, and work mode are crucial eligibility dimensions; and title-only matching is unsafe.

**It does not prove:** the planned 50-listing sample's precision/recall, source freshness rate, duplicate rate, India coverage, global remote coverage, API reliability, or authorization for bulk ingestion. This pilot is intentionally not presented as a completed 50-job audit.

## Next research steps (still before implementation)

1. Complete the pre-registered **50-listing audit**: 25 India-focused internships/fresher roles and 25 international remote roles. Record the discovery source and official employer page for each, along with open/closed status, last-posted/updated evidence, location/work authorization, seniority, eligibility, work mode, apply URL, duplicates, and terms/permission status.
2. Report metrics separately: official-page agreement, currently open, genuinely eligible from India, duplicate rate, required fields missing, and direct apply-link validity. Do not collapse these into one “match score.”
3. For a small sample, compare aggregator/API discovery against direct ATS discovery to estimate whether aggregators add unique, valid listings rather than just duplicates.
4. Validate candidate needs with 10–15 interviews before committing to a segment or source mix.
5. Keep application submission out of scope until a platform-by-platform permission and reliability review is complete.

## Sources checked

- Ema — AI/Data Resident (India remote): https://jobs.ashbyhq.com/ema/e0511c0c-998f-4079-b62c-d2f164bf2c86
- Drivetrain — India Lever board: https://jobs.lever.co/drivetrain?location=India
- Drivetrain — Engineering Intern, Gen AI for FP&A Platform: https://jobs.lever.co/drivetrain/bc1c17bc-86ac-4f00-a1e3-0eb85aae4fdc
- Sprinto — Lever board: https://jobs.lever.co/Sprinto?workplaceType=remote
- Mactores — Lever board: https://jobs.lever.co/mactores/?commitment=Full+time+%28Intern%29
- Meraki Labs — AI Engineer Intern: https://jobs.ashbyhq.com/Meraki-Labs/93ff65d2-f0cd-4fd1-b76f-b2e350f2d6c8
- CertifyOS — AI Intern: https://jobs.ashbyhq.com/certifyos/4bcdec99-9f2e-416c-8e26-498c94c5898a/
- Libra AI — AI PM Intern: https://jobs.ashbyhq.com/libra/4adac8f1-cf75-4049-815f-55177cca1967
- Cohere — Machine Learning Intern/Co-op (Winter 2027): https://jobs.ashbyhq.com/cohere/36d1f52f-8270-4652-adf5-5303a0ff341b
- STRATIVIS — Machine Learning Engineering Internship: https://jobs.ashbyhq.com/strativis/513affcf-d593-4ef2-9800-0f747c595d3e
- Whiterabbit.ai — Research Scientist Intern (2026): https://jobs.lever.co/whiterabbit/c4333d64-7fcf-4862-9cf0-c6b090ca8ca1
- Output Biosciences — Research Intern (PhD), Machine Learning: https://jobs.ashbyhq.com/output/da2723ca-a418-49f1-b7da-a4f383dd8239/
- GPTZero — Machine Learning Intern: https://jobs.ashbyhq.com/gptzero/d7e6f3ee-8446-4ac4-b1f8-e79c9876c31a
- Preference Model — ML Engineer, RL Environments Internship: https://jobs.ashbyhq.com/Preference-Model/8dccedf5-f144-46af-950c-ec2bfc91cc3c/
- Tesla — Internship, AI Engineer, Tesla AI (Fall 2026/Winter 2027): https://www.tesla.com/careers/search/job/internship-si-engineer-tesla-si-fall-2026-winter-2027-275331
- AICTE National Internship Portal: https://internship.aicte-india.org/
