# AI Career Agent

AI Career Agent is being built as a local-first desktop assistant for job discovery, eligibility review, explainable matching, application preparation, and application tracking.

## Current implementation

The first dependency-free Python domain core is in `career_agent/`. It currently provides:

- Three-valued hard eligibility checks: `pass`, `fail`, and `unknown`.
- Explicit country/work eligibility handling; worldwide eligibility passes only when explicitly recorded.
- Transparent skill overlap and missing-skill explanations, separate from eligibility.
- Conservative URL/requisition deduplication.
- Separate source-listing and employer-application URLs.
- Guarded application status transitions; confirmation requires evidence.
- Local SQLite persistence for profile, job, and tracker records, including explicit delete operations.
- No network access, resume parsing, candidate-data transfer, form filling, or application submission.

This is the domain layer only, not a complete desktop application. Job-source adapters remain disabled until their source-specific permissions and quality checks are resolved.

## Run tests

Python 3.10+; no third-party packages are required.

```bash
python -m unittest discover -s tests -v
```

## Safety and product principles

- Keep candidate profile and application history local by default.
- Missing eligibility evidence is not a pass.
- A visible Apply button is not proof that a job is open or that submission succeeded.
- Never infer worldwide eligibility from the word “remote.”
- Do not fabricate candidate facts or screening answers.
- Do not bypass source restrictions or add unapproved connectors.
- A relevance score is not a hiring probability.
- Candidate-controlled submission remains the rule until a particular permitted workflow is separately validated.

## Project status

Implementation has started with safe, offline domain logic while source research continues in parallel. This does **not** mean the source-quality gate has passed or that live discovery/application workflows are ready.
