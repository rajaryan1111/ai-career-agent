# Product and Research Rules

**Status:** Baseline rules — amend only with a documented reason  
**Last updated:** 2026-10-13

## 1. Research before implementation

- Do not start coding until the core feasibility questions have evidence-backed answers.
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

## 5. Application integrity

- A form filled out is not proof of submission.
- An attempted submission is not a confirmed application.
- Record status evidence, timestamps, source URL, and errors.
- Do not retry an ambiguous submission until checking whether it may already have succeeded.
- Prevent duplicates across sources and repeated scheduled runs.
- Ask about sensitive declarations, unfamiliar questions, assessments, or missing information.
- Respect explicit role-specific application instructions. If an employer prohibits AI assistance for application answers, do not draft, generate, autofill, or submit the prohibited responses; clearly surface the restriction and leave those answers to the candidate.
- Default: auto-submit only supported cases that meet strict eligibility and quality rules; pause on exceptions.

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
- The research/product decision gate remains in force. A development workflow document does not authorize implementation, paid services, external data transmission, deployment, or application submission.
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
