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


## Second-pass discoveries (13 October 2026)

These are additional leads found during a follow-up search. They expand the candidate set; they do **not** turn the pilot into a completed 50-listing audit. Listing status, eligibility and geography should be rechecked at the canonical detail page immediately before a user sees a recommendation.

| Listing lead | Evidence visible in search / employer page | Product lesson | Disposition |
|---|---|---|---|
| **Apple — Applied ML Intern, Wireless Technologies & Ecosystems** | Apple Careers page lists Bengaluru, India; page reports posted 27 Sep 2026. | Major-company careers pages need to be included in discovery tests; not all sources are ATS boards with uniform schemas. | Strong discovery lead; inspect eligibility and current status in the full detail page. |
| **Hibilter — AI / ML Engineering Intern** | Company careers page advertises Remote · India Internship. | Smaller company pages may be outside the handful of standard ATS sources; direct URL submission by the user should remain a fallback. | Validate role detail, company legitimacy signals, eligibility and application route. |
| **ATRISI — ML / AI Intern** | Careers page labels it Open and says Remote / Hybrid · Bengaluru, India; it also promotes a separate fellowship. | Separate paid employment, internships, fellowships and training cohorts; do not merge them into one category. | Validate role terms, requirements and official application route. |
| **Wadhwani AI — Machine Learning Intern** | Careers page lists a remote Machine Learning Intern alongside scientist roles. | Institution/company career pages may surface relevant roles that general keyword searches miss. | Check the exact linked job detail and whether “remote” is India-eligible. |
| **Zyora Labs — AI/ML Research Intern** | Careers page describes a remote/Nagercoil student internship, with basic Python and interest as stated requirements. | Preserve the stated minimum requirements, but do not infer pay, duration, legitimacy, or job quality from the headline. | Verify role details, stipend, dates, company information and application route. |
| **Trackmind — Junior AI Engineer** | Official Lever listing says Hyderabad, on-site, internship, and 6 months to 2 years of experience. | “Junior” and “internship” do not guarantee a fresher-friendly or remote role. | Good negative test; exclude for remote-only candidates and flag experience requirement. |
| **AICTE portal — Deep Learning Engineering Intern (EduRankAI)** | Listing gives a 3-month full-time term, Pan India, ₹0/month stipend, and 2 Mar 2027 application deadline. | Compensation, dates and listing provenance must be explicit; a relevant title can still be a poor match. | Validate employer and terms independently; do not equate portal presence with verified quality. |
| **Cohere — Machine Learning Intern/Co-op (Fall 2026)** | Employer Ashby page lists Canada, Europe, UK and US as locations; remote; requires current post-secondary enrollment and a full-time 3–6 month term. | “Remote” remains bounded by listed countries; advanced ML roles may have a high technical bar. | Strong negative geography test for a candidate based in India. |
| **Great Question — AI Engineer Intern** | Ashby result describes a remote-friendly, three-month summer role (mid-June to mid-September 2026). | A role whose stated work period has already passed must be treated as stale/closed unless the employer page confirms a new cohort. | Staleness test; do not recommend based on an old indexed description. |
| **Parspec — Applied AI Engineer Intern** | Ashby page describes a hybrid San Mateo role and requires enrollment in a US-based degree program. | Eligibility may depend on the candidate's educational institution and immigration/work context, not merely location. | Exclude for candidates who cannot meet the US-program requirement. |
| **Persona AI — Machine Learning Internship, Manipulation** | Ashby page lists Houston, on-site, with Fall 2026, Spring 2027 and Summer 2027 cohorts. | Cohort dates and onsite location are first-class eligibility fields; one requisition may refer to multiple future cohorts. | Candidate only if the user can relocate and meet the cohort dates. |
| **Azul — Marketing AI Intern** | Lever page says United States remote, $20–$25/hour; responsibilities focus on marketing workflows rather than ML engineering. | Semantic role classification matters: AI-enabled work is not necessarily an AI/ML engineering job. | Exclude from AI/ML engineering search unless the user includes AI automation/operations roles. |

### Second-pass source references

- Apple Careers — Applied ML Intern: https://jobs.apple.com/en-in/details/200686019-0321/applied-ml-intern-wireless-technologies-ecosystems
- Hibilter Careers: https://www.hibilter.com/careers.html
- ATRISI Careers: https://atrisi.org/careers
- Wadhwani AI Careers: https://www.wadhwaniai.org/careers/
- Zyora Labs Careers: https://zyoralabs.com/careers
- Trackmind — Junior AI Engineer: https://jobs.lever.co/trackmind/ad66c0ec-1ae9-47cb-9d5d-83ae1cb6d200
- AICTE / EduRankAI — Deep Learning Engineering Intern: https://internship.aicte-india.org/internship-details.php?uid=SU5URVJOU0hJUF8xNzg4MzQzNTgxNmE5N2Y1MWRjMWYyYQ%3D%3D
- Cohere — Machine Learning Intern/Co-op (Fall 2026): https://jobs.ashbyhq.com/cohere/36d1f52f-8270-4652-adf5-5303a0ff341b?employmentType=Intern
- Great Question — AI Engineer Intern: https://jobs.ashbyhq.com/greatquestion/c533196c-75d5-43b8-b1c8-dedf2437d544
- Parspec — Applied AI Engineer Intern: https://jobs.ashbyhq.com/parspec/0a897c21-0df7-40ba-85f2-694bf6678504/
- Persona AI — Machine Learning Internship, Manipulation: https://jobs.ashbyhq.com/persona.ai/ed9a7425-9798-471e-b46a-fefd59570630
- Azul — Marketing AI Intern: https://jobs.lever.co/azul/f94d4087-2dee-4d69-8596-883ff17efde2

## Updated audit status

This second pass adds more useful positive and negative examples, but the audit remains **qualitative and incomplete**. Search-indexed pages can be stale, and a page being visible does not establish current availability, employer legitimacy, data-use permission, or permission to automate the application process.

Next deliverable should be a structured listing-level dataset for the full 50-job sample, with a fixed schema and explicit values for unknown/not verified. Do not mark a role “eligible” when country, work authorization, cohort date, or degree constraints are unresolved.


## Third-pass discoveries: additional source and eligibility cases

**Research date:** 13 October 2026. Search snippets below are leads, not a guarantee that a role is still open. Recheck canonical pages before surfacing any role as actionable.

| Listing | Evidence from source | What the agent must do | Current audit label |
|---|---|---|---|
| **General Motors — AI/ML Student Intern, Body Digitization & AI** | Workday page lists Bengaluru, full-time, on-site, 6 months, 45 hours/week; says GM does not provide immigration-related sponsorship for the role. | Extract work arrangement, weekly commitment, duration and sponsorship restrictions; don't rely on a generic location tag. | Strong India role lead; verify education criteria and current status. |
| **Atlys — AI Intern** | Ashby page lists Delhi HQ, on-site, Engineering; work is on AI agents and customer conversations. | Classify the role as applied AI/agent engineering, but filter out users requiring remote work. | Relevant on-site role; eligibility details need full review. |
| **Atlan — People Ops Internship** | Ashby page says India-based remote, preferably Delhi/Bengaluru, 6 months, ₹20,000/month, and an intended July 2026 start. | Detect role-family mismatch: an AI-native company doesn't make a People Ops job an AI/ML job. Also detect a past intended start date. | Exclude from AI/ML role search; useful semantic/staleness negative test. |
| **Amgen — Undergrad Intern, Machine Learning Engineer (Summer 2027)** | Employer careers page says United States — Remote and posted 11 Sep 2026. | Enforce country eligibility even where the role is undergraduate and remote. | Strong international remote geography negative test for an India-based candidate. |
| **Kinaxis — Intern AI/ML Researcher** | Employer page says Canada-remote, Eastern time-zone constraint, 8- or 12-month term starting Jan 2027, and Master's/PhD-level eligibility with research experience. | Parse degree level, timezone, term duration and start date as hard constraints. | Not a general undergraduate internship; likely ineligible for many candidates. |
| **Matrice AI — ML Engineer (CV/LLM Internship)** | Careers page lists India-remote, posted 1 Jul 2026, apply-by 31 Aug 2026. | Detect expired application deadlines even when a page remains indexed. | Treat as expired unless the employer page explicitly reopens it. |
| **Humans Care Foundation — AI/ML Engineer** | Page says remote anywhere in India; application tracks include a paid one-month internship and a two-week traineeship with a ₹500 amount. It describes production AI/model work and requests Python, PyTorch/TensorFlow and backend understanding. | Separate internship from traineeship, capture the short duration and stipend/fee wording precisely, and perform employer/role legitimacy checks before recommending. | Potential India-remote lead; verify track terms, duration, status and organization details. |
| **Wadhwani AI — Machine Learning Intern** | Organization's careers page currently shows a remote ML internship among several ML roles. | Follow the actual “Apply” destination and capture role-specific criteria; don't infer them from a careers listing card. | Candidate source; role-level detail not yet audited. |
| **AICTE portal — Deep Learning Engineering Intern** | Search-indexed listing describes 3 months, 8 hours/day, 6 days/week, and a zero monthly stipend. | Surface workload and compensation together; a relevant technical description doesn't prove value or legitimacy. | Candidate source; independently verify employer and listing before recommending. |
| **Adobe — 2026 AI/ML Intern, Machine Learning Engineer** | Workday search result describes degree enrollment and an expected graduation window of Dec 2026–Jun 2027, with full-time availability May–September. The indexed cohort is 2026. | Cohort year, graduation window and application status must be checked; don't recycle an expired internship because the description is relevant. | Staleness/eligibility test; current availability unverified. |

### Third-pass source references

- General Motors — AI/ML Student Intern: https://generalmotors.wd5.myworkdayjobs.com/en-US/Careers_GM/job/AI-ML-Student-Intern--Body-Digitization---AI_JR-202613434
- Atlys — AI Intern: https://jobs.ashbyhq.com/atlys/1a34deb8-3d14-4b7b-b1eb-cd302ce97223
- Atlan — People Ops Internship: https://jobs.ashbyhq.com/atlan/0b543ef7-92e6-4400-8480-20fbb9069323
- Amgen — Undergrad Intern, Machine Learning Engineer (Summer 2027): https://careers.amgen.com/en/job/washington-d-c/undergrad-intern-machine-learning-engineer-technology-ai-and-data-summer-2027/87/100494061120
- Kinaxis — Intern AI/ML Researcher: https://careers-kinaxis.icims.com/jobs/35465/job?mobile=true&needsRedirect=false
- Matrice AI — ML Engineer (CV/LLM Internship): https://matrice.ai/careers/job?id=4
- Humans Care Foundation — AI/ML Engineer: https://www.thehcf.in/careers/ai-ml-engineer
- Wadhwani AI careers: https://www.wadhwaniai.org/careers/
- AICTE / EduRankAI — Deep Learning Engineering Intern: https://internship.aicte-india.org/internship-details.php?uid=SU5URVJOU0hJUF8xNzg4MzQzNTgxNmE5N2Y1MWRjMWYyYQ%3D%3D
- Adobe — 2026 AI/ML Intern: https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced/job/XMLNAME-2026-AI-ML-Intern---Machine-Learning-Engineer_R160428

## Audit methodology refinement

Use the following fields for each row in the eventual 50-listing dataset:

- listing_id, title, employer, source_type, discovery_url, canonical_employer_url
- first_seen_at, last_checked_at, posted_at, application_deadline, status (open, closed, expired, unknown)
- country_eligibility, location, work_mode, work_authorization, timezone_constraint
- role_family, seniority, degree_requirement, graduation_window, experience_requirement, duration, hours_per_week, start_date
- compensation_amount, compensation_currency, compensation_period, compensation_notes
- apply_url, duplicate_group, official_page_agreement, permission_status, confidence, review_notes

Do not force unknown values into false certainty. Keep source coverage, candidate eligibility, job quality and automation permission as separate dimensions. The next step is to populate a real CSV/Markdown table with actual checked rows and then calculate metrics; do not claim a 50-job result until all 50 have been inspected.


## Fourth pass: live-status correction and new negative controls (13 October 2026)

A fresh search of official pages produced three more audit rows and one correction to an earlier row. The structured CSV now contains **19 seed rows**; this remains a convenience sample and is not the 50-listing audit.

| Listing | Current official-source evidence | Audit consequence |
|---|---|---|
| **Kinaxis — Intern AI/ML Researcher** | The official page says Canada remote, requires the candidate to be in the Eastern time zone, describes an 8- or 12-month full-time placement starting January 2027, and says applications are accepted through 18 October 2026. Eligibility text allows current full-time students or recent/upcoming graduates within 12 months of the placement end. | Updated the CSV from unknown status to open with an 18 Oct deadline. Removed the unsupported assumption that a Master's/PhD is explicitly required: the reviewed page excerpt does not state that degree level. For an India-based user, the Canada/Eastern time-zone restriction is a strong exclusion. |
| **Apple — PhD Intern, Machine Learning: MSI, Product Operations Team** | Apple India search results show a Bengaluru listing dated 17 September 2026 and a 40-hour workweek. | Added as a role-level eligibility test. The role detail page should be opened before scoring; a PhD internship must not be recommended to an undergraduate as a standard internship. |
| **Apple — Applied Machine Learning Engineer, Apple Intelligence** | Apple India careers page shows a Bengaluru role posted 7 September 2026, with 40 weekly hours. | Added as a negative control for employment type/seniority: AI/ML relevance does not make a full-time engineering role an internship. |
| **Workiva — Summer 2027 Intern, Machine Learning Engineering** | Official Workday page says USA-remote and $40/hour, but its stated engineering posting close date was 2 October 2026. The audit date is 13 October 2026. | Added as expired in the seed dataset; don't surface it as currently actionable merely because the URL remains reachable. |

### Fresh official sources

- Apple — Applied ML Intern: https://jobs.apple.com/en-in/details/200686019-0321/applied-ml-intern-wireless-technologies-ecosystems
- Apple India search results — PhD ML internship and related ML roles: https://jobs.apple.com/en-in/search?location=karnataka-state1205&page=2
- Apple — Applied Machine Learning Engineer, Apple Intelligence: https://jobs.apple.com/en-in/details/200682189-0321/applied-machine-learning-engineer-apple-intelligence
- Kinaxis — Intern AI/ML Researcher: https://careers-kinaxis.icims.com/jobs/35465/job?mobile=true&needsRedirect=false
- Workiva — Summer 2027 Intern, Machine Learning Engineering: https://workiva.wd503.myworkdayjobs.com/en-US/careers/job/Summer-2027-Intern---Machine-Learning-Engineering_R12194-1

### Quality correction

The purpose of this audit is not to maximize the number of links. It is to measure how often a discovery source returns roles that are still open, truly in the requested role family, and eligible for a candidate in a particular country and education stage. Therefore:
- Expired and ineligible rows should remain in the sample as negative controls; don't silently remove them.
- The CSV's `permission_status=unknown` means access permission for the product's intended use has not been verified; it is not a claim that access is forbidden or allowed.
- An official careers page can support the facts displayed there, but it does not by itself establish permission for bulk crawling or automated application submission.
- Current status must be timestamped and rechecked close to the time of recommendation.


## Fifth pass — aggregator/API comparison and Superpowers review (2026-10-13)

### Newly checked aggregator/API evidence

- **AI Dev Jobs API docs:** https://aidevboard.com/docs
- **AI Dev Jobs terms:** https://aidevboard.com/terms
- **Remote OK FAQ/feed guidance:** https://remoteok.com/faq
- **Remote OK terms:** https://remoteok.com/legal

AI Dev Jobs' current documentation says anonymous read access is available with hourly IP throttling; its API supports location, level, work mode, explicit global-remote scope and job details/matching. Its terms state listings are not guaranteed complete, accurate or available, prohibit exceeding API rate limits, and say data may be used in applications but not resold as a standalone dataset. This makes it a meaningful discovery candidate for a small API audit, not a source of truth. The job board's own match score should not replace our independently validated hard eligibility gates.

Remote OK's FAQ documents free public JSON and RSS feeds. When building an aggregator or sharing its feed, it asks consumers to credit Remote OK and link back to each original job post. Its current legal terms were updated 20 July 2026; these should be reviewed against the intended client behavior before adoption. The current category pages are broad remote-job discovery pages and did not, in this pass, establish a verified individual student/entry-level AI/ML vacancy.

### Source comparison / duplicate test

A separate Ema record was added for the AI Dev Jobs aggregator copy of the same role already recorded from the official Ashby page. This is intentionally **not a new unique vacancy**. The aggregator labels the record "part-time mid"; the official employer description identifies a six-month program intended for final-year undergraduate students, requiring graduation by June next year and GPA 8.0+, and says 20–30 hours/week during semester and full-time in summer. This illustrates:
- source-level duplicate resolution must be separate from vacancy counts;
- source fields can disagree (especially seniority and job type);
- canonical employer details should win where discrepancies affect eligibility;
- source provenance should remain visible instead of silently flattening conflicting fields.

The CSV now has **22 records/rows including header-excluded seed entries and source-level audit rows**; it still does **not** constitute the planned 50 individually audited unique listings. Two additions are source-level checks rather than vacancies, and one is a duplicate copy of an already represented job. Do not count them toward the 25 India + 25 international unique-listing target.

### Current interpretation and next action

- AI Dev Jobs is the higher-priority next technical *research* candidate because its API exposes documented source filters and open read access, but freshness, unique coverage, India entry-level yield and job-detail agreement still need measured checks.
- Remote OK is a secondary source candidate with clear feed availability and attribution/link-back expectations; platform terms and role quality need further review.
- The next dataset milestone remains 50 unique, individually checked listings: 25 India/India-eligible internship/fresher roles and 25 international-remote roles, with negative controls retained separately from unique eligible vacancies.
- No source is marked integration-approved solely because it has an API or publicly reachable feed.
- No implementation started.
