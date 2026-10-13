# Application-Route Spot Check — 2026-10-14

## Purpose

Check whether a sample of employer listing links reaches the application destination. This is a focused convenience sample selected from candidate leads and controls; it is not a random sample and does not satisfy the 50-record validation gate.

## Method and safety boundary

- Open the official employer listing and follow its published Apply action/link when exposed.
- Record the destination and what the research browser actually rendered.
- Do not enter candidate information, upload a resume, submit a form, send email, or infer source permission from public accessibility.
- A form rendering means only that a form route was reachable at check time; it does not prove submit success, vacancy eligibility, or permission to collect/reuse data.

## Results

| Audit ID | Employer | Listing URL | Observed application destination | Outcome | Evidence |
|---|---|---|---|---|---|
| IN-002 | Drivetrain | https://jobs.lever.co/drivetrain/bc1c17bc-86ac-4f00-a1e3-0eb85aae4fdc | https://jobs.lever.co/drivetrain/bc1c17bc-86ac-4f00-a1e3-0eb85aae4fdc/apply | reachable_application_form | Matching Lever application page rendered. No submission. |
| IN-004 | Trackmind | https://jobs.lever.co/trackmind/ad66c0ec-1ae9-47cb-9d5d-83ae1cb6d200 | https://jobs.lever.co/trackmind/ad66c0ec-1ae9-47cb-9d5d-83ae1cb6d200/apply | reachable_application_form | Matching Lever page exposed resume, name, email and Submit application. Role has contradictory Internship vs Full-Time and 6 months–2 years experience text. |
| IN-008 | Humans Care Foundation | https://www.thehcf.in/careers/ai-ml-engineer | https://www.thehcf.in/careers/ai-ml-engineer/apply | login_gate_reached | Start application redirected to portal sign-in with role application as the next route. |
| IN-015 | RadialBrain | https://www.radialbrain.com/interns/ | Google Forms link; destination not verified | unknown_fetch_error | Browser click returned internal error without a verified HTTP status. |
| IN-016 | Zyora Labs | https://www.zyoralabs.com/careers | https://www.zyoralabs.com/careers | embedded_form_visible_not_submitted | Careers page shows an embedded form and role Apply links, but no distinct role-specific destination was exposed. |
| IN-022 | Sprinto | https://jobs.lever.co/Sprinto/6dfd5f41-57b6-40e8-9eab-ba4083c1a7c4 | https://jobs.lever.co/Sprinto/6dfd5f41-57b6-40e8-9eab-ba4083c1a7c4/apply | reachable_application_form | Matching Lever application page rendered. No submission. |
| IN-031 | Needl.ai | https://needl.ai/careers/ai-engineering-intern | mailto:careers@needl.ai | email_route_published_not_tested | Employer explicitly says to email resume; no email sent. |
| IN-036 | Valura.AI | https://careers.valura.ai/836918cc-4b0f-4207-b364-e277600fd43f | Not exposed by page extraction | unknown_button_destination_not_exposed | Apply button visible; destination could not be inspected. |
| INT-023 | MailerMen | https://www.mailermen.com/jobs/machine-learning-intern-python-scikit-learn-remote-worldwide-280 | https://www.mailermen.com/jobs/machine-learning-intern-python-scikit-learn-remote-worldwide-280/apply | unknown_fetch_restricted | Browser reported restricted-URL fetch failure; no HTTP status. |
| INT-033 | CertiK | https://jobs.lever.co/certik/1f446b66-1fae-4c31-9352-cde86e254754 | https://jobs.lever.co/certik/1f446b66-1fae-4c31-9352-cde86e254754/apply | reachable_application_form | Matching Lever application form rendered. It requires current/recent PhD and states U.S. work-eligibility verification; retained as a negative control. |

## Count and interpretation

- Routes examined: 10.
- Application forms rendered: 4.
- Sign-in gate reached: 1.
- Embedded form visible but not submitted: 1.
- Published email route not tested: 1.
- Unknown due to browser/tool limitation: 3.
- Forms submitted / candidate data transmitted: 0.

Do not calculate a direct-link validity percentage from this convenience sample. It was selected rather than randomly sampled; unknowns remain unknown; rendered forms are not proof of successful submission. The acceptance criterion still requires the fixed 50-record sample, predefined denominator, success/failure/unknown outcomes, and ≥90% valid direct-employer application links. Source permission and candidate eligibility are separate gates.

**Decision: NOT PASSED — research-only.**
