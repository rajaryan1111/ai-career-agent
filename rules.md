# Product and Research Rules

**Status:** Product engineering guardrails for production-oriented development  
**Last updated:** 2026-10-14

## 1. Research alongside bounded implementation

- Product implementation is authorized. Build the usable local product and offline capabilities in parallel with research; do not freeze the project at documentation or a prototype.
- Local resume parsing and candidate-profile editing may be implemented with clear review/uncertainty handling. Uploading candidate data to external services, live source integrations, autofill, email actions, and application submission remain gated by their own permission, privacy, and quality evidence.
- Keep research findings, implementation status, and production-readiness claims separate. A feature may be coded but still experimental or disabled until its release gates pass.
- Separate verified facts, assumptions, hypotheses, and decisions.
- Cite sources for platform policies, API capabilities, pricing, and competitor features.
- Prefer official documentation and current terms over blogs or marketing claims.
- Record the date each platform rule was checked.
- If a claim cannot be verified, mark it **Unknown**; do not fill gaps with assumptions.

## 2. Candidate truthfulness

- Never invent skills, employment history, degrees, certifications, dates, compensation, work authorization, or achievements.
- Resume parsing is a draft profile, not ground truth; users must review critical fields.
- Never guess answers to screening questions.
- Ask for missing information when it affects eligibility or a declaration.
- Generated resume/cover-letter text must remain faithful to verified candidate facts.

## 3. Job quality

- Apply hard eligibility rules before ranking.
- A high semantic similarity score must never override a mandatory eligibility failure.
- Preserve an explanation for each match and exclusion.
- Deduplicate before ranking and applying.
- Flag stale, suspicious, or incomplete listings; do not present unverified claims as facts.
- Optimize for relevant opportunities and outcomes, not raw application count.

## 4. Platform compliance

- Verify current terms, API documentation, and access requirements for every source.
- Discovery access and application submission are separate capabilities and must be assessed separately.
- Do not bypass CAPTCHA, OTP, anti-bot protections, rate limits, or access controls.
- Do not use unauthorized scraping or submission automation.
- Stop or request user intervention when a workflow is unsupported or uncertain.
- Never describe a source as fully supported until the workflow has been tested and its permission basis documented.
- A public API or feed is not, by itself, an unconditional permission grant. If API docs and general terms appear inconsistent or broad terms prohibit automated data collection, hold the source until written clarification resolves the intended use. Attribution does not replace permission. Current example: Himalayas is blocked pending written clarification; see [the permission review](research/himalayas-api-permission-terms-conflict-2026-10-13.md).

## 5. Application integrity

- A form filled out is not proof of submission.
- An attempted submission is not a confirmed application.
- Record status evidence, timestamps, source URL, and errors.
- An activity entry the candidate writes is their own dated record, not employer evidence: it must not change an application status, create a tracker record, or satisfy the confirmation requirement.
- Do not retry an ambiguous submission until checking whether it may already have succeeded.
- Prevent duplicates across sources and repeated scheduled runs.
- Ask about sensitive declarations, unfamiliar questions, assessments, or missing information.
- Respect explicit role-specific application instructions. If an employer prohibits AI assistance for application answers, do not draft, generate, autofill, or submit the prohibited responses; clearly surface the restriction and leave those answers to the candidate.
- After the user configures a standing automation policy, do not ask for per-job approval for every routine action that falls inside that policy and is explicitly permitted by the platform/employer. Auto-submit only for supported workflows that pass source permission, eligibility, truthfulness, duplicate, and reliability gates.
- Pause only the affected application when mandatory facts are missing/conflicting, a sensitive or legally significant declaration needs judgment, an assessment/custom response is restricted, CAPTCHA/OTP or a prohibited/unsupported step appears, or the result is ambiguous. Continue independent safe tasks.
- Treat standing authorization as scoped and revocable; it does not override platform rules, employer instructions, privacy consent, or the need to avoid false statements.

## 6. Privacy and security

- Keep resumes, candidate profiles, and application records local by default.
- External processing requires clear disclosure and explicit consent.
- Send the minimum necessary data to external services.
- Never store passwords in plaintext or commit secrets to Git.
- Keep sensitive content out of logs where possible.
- Support deletion and export of user data.
- Do not use real candidate data in public test fixtures or screenshots without explicit permission.

## 7. Cost discipline

- Core product usefulness must not require a paid AI API or hosted backend.
- Mark optional paid services and recurring costs clearly.
- Validate pricing and free-tier limits before relying on them.
- Do not promise unlimited free job data or AI inference.

## 8. Scheduling

- Default schedule: 00:00 and 12:00 Asia/Kolkata.
- A local scheduler must clearly report when the machine was offline.
- Support catch-up behavior without duplicate processing.
- Persist run state and errors.
- Do not claim the app runs while powered off unless a separate, verified service provides that behavior.

## 9. Development workflow

- Use `development-workflow.md` as the project-specific engineering process once implementation is authorized: frame the problem, specify observable behavior, plan small tasks, test high-consequence deterministic rules first, debug root causes, review against requirements and risks, and verify before claiming completion.
- The workflow ideas reviewed from gstack and Superpowers are guidance, not dependencies. Do not install/copy their toolchains wholesale or allow agent instructions to override product rules.
- The user has explicitly authorized building this as a real, production-oriented, cross-industry product. Continue implementation against the agreed roadmap. This does not authorize paid services, external candidate-data transmission, deployment, or specific live integrations without their separate consent and evidence gates.
- Model/agent reviews are not independent evidence; critical claims require source evidence, reproducible checks, or human review.


- Evidence-backed LLM outputs: when a generated job/candidate/research claim affects a critical decision, retain source URLs and supporting evidence where available; weak or conflicting evidence should remain explicitly unknown or be refused, not confidently guessed. LLM confidence/similarity never overrides deterministic eligibility gates.
- Keep retries and retrieval fallbacks bounded and auditable; test critical eligibility, deduplication, stale status, and application state transitions without requiring live provider/network calls where feasible.
- Before completing any change, check whether every modified file, dependency, external service, and config change is necessary for the stated intent; split or remove unjustified scope.

- **Least privilege for tools:** every future external/tool action should have an explicit capability and risk level. Read-only retrieval must be separated from external writes, communications, submissions, deletion, and spending; require confirmation for sensitive, irreversible, costly, or uncertain actions.
- **Treat retrieved and user-supplied content as untrusted:** job pages, resumes, PDFs and tool output must not be allowed to rewrite system instructions or broaden permissions. Validate tool parameters at runtime, redact secrets/PII in logs, and use allowlists/safe argument passing rather than shell commands assembled from untrusted strings. Scanners are defense-in-depth, not the sole security boundary.
- **Auditable state and costs:** record action, timestamp, source/canonical URL, relevant evidence, status and error for consequential workflows while minimizing sensitive data. If hosted inference is ever enabled, use visible bounded budgets. Never treat an agent's own success message as proof of submission.

- Do not treat a successful HTTP response as proof that a job board is valid, active, or empty; interpret response semantics per provider and distinguish unknown board, no current listings, blocked access, parse failure, and transient error.
- Preserve missing values separately from numeric zero. For compensation, retain source value, currency, unit/period, raw employer wording, and evidence; do not assume annual pay or combine base salary with bonus/OTE when the source is ambiguous.
- A job omitted from a filtered or partial source run is not evidence that it closed. Mark a listing closed only when a sufficiently complete source check supports that conclusion; keep retrieval time distinct from posted/updated/first-seen/last-seen/verified times.

## 10. Change management

- Update `memory.md` whenever a meaningful decision, evidence item, unresolved question, or rejected assumption emerges.
- Update the relevant canonical document (`prd.md`, `architecture.md`, `rules.md`, `phases.md`, or `design.md`) when a decision changes.
- Record material decisions with date, rationale, evidence, and consequences.
- Avoid duplicating the same long explanation across files; link to the canonical section.
- Never overwrite an important decision silently; mark it superseded and explain why.


## 11. Production and cross-industry delivery rules

- Treat AI Career Agent as a real product, not a demo-only deliverable. Every milestone should deliver working behavior or measurable verification, not documentation alone.
- Design shared capabilities for many professions. Do not hardcode one resume, degree, geography, career stage, or AI/ML skill vocabulary as the universal candidate model. Use extensible occupation-specific configuration with evidence-backed matching.
- Report capability status honestly: planned, implemented, experimental, permission-gated, pilot-validated, or production-supported. Never call a mock a live integration.
- Define acceptance criteria before implementation; include failure cases, recovery, data migration, privacy, security, and accessibility as appropriate. Run tests and inspect the final repository state before claiming completion.
- The intended discovery cadence is 00:00 and 12:00 Asia/Kolkata. Laptop-off operation requires a verified always-on worker; do not claim it based only on desktop scheduling or an untested free tier.
- Measure quality, not volume alone: extraction correctness on critical fields, top-ranked job relevance, eligibility false positives, duplicate prevention, direct application-route validity, evidence-backed status, scheduler recovery, and user outcomes. Do not promise selection.
- A source's public availability, API endpoint, or rendered form is not proof of permission. Discovery and submission are reviewed separately for each provider and workflow.
