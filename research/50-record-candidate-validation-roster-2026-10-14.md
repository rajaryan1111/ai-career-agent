# 50-Record Candidate-Validation Roster — 2026-10-14

## Purpose and decision

This file fixes a reproducible, deduplicated roster of **25 India-focused records and 25 international-remote records** from the current audit. It is a validation roster, **not** a claim that 50 jobs are open, eligible, or suitable. Closed/expired roles and geography, degree and role-family negatives are intentionally retained as controls.

**Acceptance status: roster assembled; validation incomplete.** The direct-employer link-validity metric is not passed. A browser retrieval result is not a formal HTTP-status audit, a page that renders is not proof that the Apply action works, and a source/aggregator listing URL is not necessarily an employer apply URL.

## Sampling rules

1. Start from the re-fetched audit CSV and select one row per canonical URL, excluding rows explicitly annotated as duplicate observations.
2. India-focused stratum: India location/eligibility or an India hiring market. Keep negative controls to test status, seniority, role family, degree and location rules.
3. International-remote stratum: explicit remote mode/location and a non-India or geography-restricted market. Keep US/Canada/Europe-only and advanced-degree roles as eligibility controls; do not treat them as India-eligible.
4. Preserve source status as observed; unknown is not converted to open, closed, or eligible.
5. Probe outcome records what the research browser returned on 2026-10-14. It does not certify legal eligibility, source permission, actual Apply-action success, or an HTTP status unless explicitly stated.
6. A source/careers index URL is not a role-deep-link unless the exact role is identified there. A generic search redirect counts as a deep-link failure.

## Summary

- Roster size: 50 records, 25 India-focused and 25 international-remote.
- Duplicate canonical URLs within this roster: 0.
- Duplicate requisition caveat: GM IN-006 and IN-026 are locale/parameter variants for the same requisition; IN-026 is excluded.
- Browser probes attempted: 50.
- Explicit unavailable findings: Apple IN-001 (role page says not found/no longer available), Matrice AI IN-007 (404/Job Not Found; already expired), Bruker IN-033 (HTTP 410 Gone).
- Deep-link problem: AtkinsRéalis IN-030 redirects to the generic jobs search page, not the stored role.
- Tooling limitation: Azul INT-032 returned a research-browser fetch error without an HTTP status; this is unknown, not a dead-link finding.
- Job-board shells/title only: 11; employer/career pages with no readable lines: 7. These are renderer limitations, not closure evidence.
- Probe outcomes: role_not_found_explicit: 2; page_content_readable: 24; destination_returned_but_no_readable_lines: 7; redirected_to_canonical_portal_page: 1; redirected_to_canonical_careers_page_and_content_readable: 1; job_board_shell_title_only: 11; redirected_to_generic_jobs_search: 1; HTTP_410_Gone: 1; redirected_to_canonical_role_page: 1; research_browser_fetch_error_no_http_status: 1.
- Direct-employer application-link validity: **not yet measured**. We have not established a defensible success/failure denominator for the actual application destination, and some sampled URLs are careers indexes or inaccessible JS-rendered pages.

## India-focused stratum (25)

| Sample | Stratum | Audit ID | Record | Audit status | Fit / control role | Browser probe outcome | Link type caveat | Canonical source |
|---|---|---|---|---|---|---|---|---|
| IN-S01 | India-focused | IN-001 | Apple — Applied ML Intern - Wireless Technologies & Ecosystems | closed | control / fit risk | role_not_found_explicit | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.apple.com/en-in/details/200686019-0321/applied-ml-intern-wireless-technologies-ecosystems) |
| IN-S02 | India-focused | IN-002 | Drivetrain — Engineering Intern - Gen AI for FP&A Platform | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.lever.co/drivetrain/bc1c17bc-86ac-4f00-a1e3-0eb85aae4fdc) |
| IN-S03 | India-focused | IN-004 | Trackmind — Junior AI Engineer | unknown | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.lever.co/trackmind/ad66c0ec-1ae9-47cb-9d5d-83ae1cb6d200) |
| IN-S04 | India-focused | IN-006 | General Motors — AI/ML Student Intern - Body Digitization & AI | unknown | candidate lead; eligibility still needs review | destination_returned_but_no_readable_lines | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://generalmotors.wd5.myworkdayjobs.com/en-US/Careers_GM/job/AI-ML-Student-Intern--Body-Digitization---AI_JR-202613434) |
| IN-S05 | India-focused | IN-007 | Matrice AI — ML Engineer (CV/LLM Internship) | expired | control / fit risk | role_not_found_explicit | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://matrice.ai/careers/job?id=4) |
| IN-S06 | India-focused | IN-008 | Humans Care Foundation — AI/ML Engineer | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://www.thehcf.in/careers/ai-ml-engineer) |
| IN-S07 | India-focused | IN-009 | EduRankAI via AICTE portal — Deep Learning Engineering Intern | open | candidate lead; eligibility still needs review | redirected_to_canonical_portal_page | careers index or portal; not yet proven role-deep-link | [Open source](https://internship.aicte-india.org/internship-details.php?uid=SU5URVJOU0hJUF8xNzg4MzQzNTgxNmE5N2Y1MWRjMWYyYQ%3D%3D) |
| IN-S08 | India-focused | IN-015 | RadialBrain — AI Engineering Intern | unknown | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://www.radialbrain.com/interns/) |
| IN-S09 | India-focused | IN-016 | Zyora Labs — AI/ML Research Intern | open | candidate lead; eligibility still needs review | page_content_readable | careers index or portal; not yet proven role-deep-link | [Open source](https://zyoralabs.com/careers) |
| IN-S10 | India-focused | IN-018 | Inferova Technologies — AI/ML Engineer Intern | unknown | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://inferova.com/careers-ai-ml) |
| IN-S11 | India-focused | IN-019 | Hajana Technologies — AI/ML Intern | unknown | control / fit risk | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://hajanatechnologies.com/careers/ai-ml-intern) |
| IN-S12 | India-focused | IN-021 | Onelogica / Factorial AI Private Limited — Internship Data & AI Engineer — GenAI Platforms | unknown | candidate lead; eligibility still needs review | redirected_to_canonical_careers_page_and_content_readable | careers index or portal; not yet proven role-deep-link | [Open source](https://www.onelogica.com/careers/) |
| IN-S13 | India-focused | IN-022 | Sprinto — AI Implementation Intern | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.lever.co/Sprinto/6dfd5f41-57b6-40e8-9eab-ba4083c1a7c4) |
| IN-S14 | India-focused | IN-023 | Meraki Labs — AI Engineer Intern | unknown | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/Meraki-Labs/93ff65d2-f0cd-4fd1-b76f-b2e350f2d6c8) |
| IN-S15 | India-focused | IN-024 | Sarvam — Intern — ML & Speech Data Pipeline | unknown | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/sarvam/5588ec03-74d6-4b45-aa66-bace8ce1d38b) |
| IN-S16 | India-focused | IN-025 | Airbus — Internship - India Innovation Team - GenAI Intern | unknown | candidate lead; eligibility still needs review | destination_returned_but_no_readable_lines | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Internship---India-Innovation-Team---GenAI-Intern_JR10446597) |
| IN-S17 | India-focused | IN-027 | vINe AI — ML Engineer Intern | open | candidate lead; eligibility still needs review | page_content_readable | careers index or portal; not yet proven role-deep-link | [Open source](https://www.vineai.co.in/careers) |
| IN-S18 | India-focused | IN-029 | Unisys — AI Engineering Intern | unknown | candidate lead; eligibility still needs review | destination_returned_but_no_readable_lines | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://unisys.wd5.myworkdayjobs.com/en-US/External/job/AI-Engineering-Intern_REQ574280) |
| IN-S19 | India-focused | IN-030 | AtkinsRéalis — Robotics & AI Engineering Intern | unknown | candidate lead; eligibility still needs review | redirected_to_generic_jobs_search | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://careers.atkinsrealis.com/en/jobs/intern-r-163438) |
| IN-S20 | India-focused | IN-031 | Needl.ai — AI Engineering Intern | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://needl.ai/careers/ai-engineering-intern) |
| IN-S21 | India-focused | IN-032 | Concentric AI / Concentric Software India Private Limited — Machine Learning Intern | unknown | candidate lead; eligibility still needs review | destination_returned_but_no_readable_lines | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://concentric.greythr.com/hire/jobs/machine-learning-intern/) |
| IN-S22 | India-focused | IN-033 | Bruker — Graduate Apprenticeship Trainee - AI/ML | closed | control / fit risk | HTTP_410_Gone | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://internationalcareers-bruker.icims.com/jobs/19820/graduate-apprenticeship-trainee---ai-ml/job?in_iframe=1) |
| IN-S23 | India-focused | IN-034 | WATER — ML Intern Application | unknown | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://www.water.bio/careers/WR012) |
| IN-S24 | India-focused | IN-035 | Walmart Global Tech India — (IND) Grad Intern - No Work Experience | unknown | candidate lead; eligibility still needs review | destination_returned_but_no_readable_lines | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://walmart.wd504.myworkdayjobs.com/en-US/WalmartExternal/job/IN-KA-BANGALORE-Home-Office-PTPP1/XMLNAME--IND--Grad-Intern---No-Work-Experience_R-2607497) |
| IN-S25 | India-focused | IN-036 | Valura.AI — AI Engineering Intern (Python) | unknown | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://careers.valura.ai/836918cc-4b0f-4207-b364-e277600fd43f) |

## International-remote stratum (25)

| Sample | Stratum | Audit ID | Record | Audit status | Fit / control role | Browser probe outcome | Link type caveat | Canonical source |
|---|---|---|---|---|---|---|---|---|
| XR-S01 | International-remote | INT-001 | Cohere — Machine Learning Intern/Co-op (Winter 2027) | open | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/cohere/36d1f52f-8270-4652-adf5-5303a0ff341b) |
| XR-S02 | International-remote | INT-002 | STRATIVIS — Machine Learning Engineering Internship | unknown | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/strativis/513affcf-d593-4ef2-9800-0f747c595d3e) |
| XR-S03 | International-remote | INT-003 | Amgen — Undergrad Intern - Machine Learning Engineer (Summer 2027) | unknown | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://careers.amgen.com/en/job/washington-d-c/undergrad-intern-machine-learning-engineer-technology-ai-and-data-summer-2027/87/100494061120) |
| XR-S04 | International-remote | INT-004 | Kinaxis — Intern AI/ML Researcher | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://careers-kinaxis.icims.com/jobs/35465/job?mobile=true&needsRedirect=false) |
| XR-S05 | International-remote | INT-007 | Workiva — Summer 2027 Intern - Machine Learning Engineering | expired | control / fit risk | destination_returned_but_no_readable_lines | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://workiva.wd503.myworkdayjobs.com/en-US/careers/job/Summer-2027-Intern---Machine-Learning-Engineering_R12194-1) |
| XR-S06 | International-remote | INT-019 | Tether Operations Limited — Research Engineer Intern (Multimodal LLM) | unknown | control / fit risk | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://careers.tether.io/o/research-engineer-intern-videomultimodal-llm-remote) |
| XR-S07 | International-remote | INT-021 | Threxil Systems — AI Intern | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://www.threxil.com/careers/apply/ai-intern) |
| XR-S08 | International-remote | INT-022 | Threxil Systems — Frontend + AI Intern | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://www.threxil.com/careers/apply/frontend-ai-intern) |
| XR-S09 | International-remote | INT-023 | MailerMen — Machine Learning Intern (Python, scikit-learn) | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://www.mailermen.com/jobs/machine-learning-intern-python-scikit-learn-remote-worldwide-280) |
| XR-S10 | International-remote | INT-024 | QovaTech — AI Intern | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://www.qovatech.com/careers/ai-engineer) |
| XR-S11 | International-remote | INT-025 | DataRobot — Agentic AI Intern | unknown | candidate lead; eligibility still needs review | destination_returned_but_no_readable_lines | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://datarobot.wd1.myworkdayjobs.com/DataRobot_External_Careers/job/Boston-Massachusetts-US/Agentic-AI-Intern_R-102729) |
| XR-S12 | International-remote | INT-026 | Cohere — Research Internship (Winter 2027) | unknown | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/cohere/73bd3e2b-6597-4124-b64b-1e5dbc32e785) |
| XR-S13 | International-remote | INT-027 | Khan Academy — Software Engineer Intern (Summer 2027) | open | control / fit risk | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://job-boards.greenhouse.io/khanacademy/jobs/8250259) |
| XR-S14 | International-remote | INT-028 | Datacor — Summer 2027 AI Engineer Intern | unknown | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://job-boards.greenhouse.io/datacor/jobs/5242412007) |
| XR-S15 | International-remote | INT-029 | Kinaxis — Intern AI&ML Researcher (January 2027 start) | open | control / fit risk | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://careers-kinaxis.icims.com/jobs/35465/job) |
| XR-S16 | International-remote | INT-030 | Celestica — Student Intern, AI Project Coordinator | unknown | control / fit risk | redirected_to_canonical_role_page | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://careers.celestica.com/job/Remote-Employee-Canada-Student-Intern%2C-AI-Project-Coordinator-ON/1441161033/) |
| XR-S17 | International-remote | INT-032 | Azul Systems — IT Intern, AI and Operations | unknown | candidate lead; eligibility still needs review | research_browser_fetch_error_no_http_status | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.lever.co/azul/8f41ceaf-8835-4fc7-ba57-9384487d59db) |
| XR-S18 | International-remote | INT-033 | CertiK — Blockchain Security Expert Intern - AI Track | open | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.lever.co/certik/1f446b66-1fae-4c31-9352-cde86e254754) |
| XR-S19 | International-remote | INT-034 | Binance — Binance Accelerator Program - Applied AI Agent Engineer (Tech Seeds 2026) | unknown | candidate lead; eligibility still needs review | page_content_readable | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.lever.co/binance/303def79-701c-4b29-aceb-e07877a22d1d) |
| XR-S20 | International-remote | INT-035 | Cohere — Software Engineer Intern (Winter 2027) | unknown | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/cohere/8c035d3d-081d-4c8a-914a-72f4efaad254) |
| XR-S21 | International-remote | INT-036 | Wealth.com — Applied Scientist — AI/ML Intern | unknown | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/wealth-com/1899d513-4c4a-43b2-a307-8c8e4b877622) |
| XR-S22 | International-remote | INT-037 | Angi — AI Enablement Intern | unknown | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/angi/18336a40-d7ab-4ead-90fc-e33504430677) |
| XR-S23 | International-remote | INT-038 | Yotta Labs — Research Engineer Intern — AI Systems | unknown | candidate lead; eligibility still needs review | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/yotta/09821a51-fbe6-42a7-a566-0d2b5d40fae3) |
| XR-S24 | International-remote | INT-039 | Higharc — Research Intern, Special Projects (PhD) | unknown | control / fit risk | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/Higharc/5a7265ed-8db3-480e-9c04-3c9b2d2c235b) |
| XR-S25 | International-remote | INT-040 | 1Password — Developer Intern, Ecosystems — Fall 2026 | unknown | control / fit risk | job_board_shell_title_only | role-detail URL recorded; Apply destination still needs confirmation | [Open source](https://jobs.ashbyhq.com/1password/44150e12-89b1-4ac7-ad8d-671f5ec650dd) |

## Interpretation

This roster makes the next test repeatable and exposes failure modes rather than inflating vacancy counts. It does **not** demonstrate 20 unique relevant currently open vacancies; several rows are explicit controls, duplicate requisitions are excluded, and candidate fit/eligibility is independent from status.

Do not compute a valid-direct-link percentage from the browser-probe counts above. The next link-quality pass must test the actual destination and record success/failure/unknown per direct-employer link, define the denominator in advance, and report source-listing URLs separately from employer apply URLs. Any unknown outcome remains unknown.

The source-quality gate remains **NOT PASSED / research-only**. No source API was queried, no production integration was implemented, no candidate data was transferred, and no application was submitted.


## Application-route spot check — 2026-10-14

This is a focused, non-random spot check, not the required 50-record link-validity test. The audit CSV now records the observed application route separately from the canonical listing using apply_url, apply_route_outcome, apply_route_checked_at, and apply_route_evidence. Blank outcome means not yet checked; unknown outcomes remain unknown.

| Audit ID | Employer | Observed outcome | Evidence / limitation |
|---|---|---|---|
| IN-002 | Drivetrain | reachable_application_form | Matching Lever /apply page rendered; no submission |
| IN-004 | Trackmind | reachable_application_form | Matching Lever /apply form rendered; employment-type/experience contradictions remain |
| IN-008 | Humans Care Foundation | login_gate_reached | Application URL redirects to portal sign-in; form not verified beyond gate |
| IN-015 | RadialBrain | unknown_fetch_error | Google Forms click returned browser internal error without HTTP status |
| IN-016 | Zyora Labs | embedded_form_visible_not_submitted | Careers page contains embedded form; no distinct role-specific destination exposed |
| IN-022 | Sprinto | reachable_application_form | Matching Lever /apply page rendered; no submission |
| IN-031 | Needl.ai | email_route_published_not_tested | Employer publishes email route; no email sent |
| IN-036 | Valura.AI | unknown_button_destination_not_exposed | Apply button visible but destination not exposed |
| INT-023 | MailerMen | unknown_fetch_restricted | /apply destination resolved, but browser blocked fetch without HTTP status |
| INT-033 | CertiK | reachable_application_form | Matching Lever /apply form rendered; PhD/U.S. eligibility requirements make it a negative control |

### Interpretation

Four of these ten tested routes rendered an application form, one reached a sign-in gate, one exposed an embedded form, one published an email route that was not tested, and three remained unknown under the research-browser method (RadialBrain, Valura.AI, MailerMen). These outcomes are not a representative estimate of direct-link validity and must not be converted into a 90% metric. No forms were submitted and no candidate data was entered or sent. The source-quality gate remains NOT PASSED.
