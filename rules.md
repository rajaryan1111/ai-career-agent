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
- A health, doctor or diagnostic report must not clear data the application itself refuses to read: a check
  that says "no problems found" has to read every record the read paths read, and a read-only report must
  answer an unreadable record with a clear refusal instead of a raw failure.
  **Implemented as an invariant (2026-10-15):** `--doctor` decodes every stored record through the same
  decoders the read paths use, over a `mode=ro` connection, and names the table and record it cannot read;
  `--analytics`, `--follow-ups`, `--next-actions`, `--interviews`, `--history` and `--worker-status` answer
  such a record with one sanitised sentence and exit status 2, changing nothing. Found by the release
  rehearsal rather than by reading the code: the doctor reported "no problems found" on a database every read
  path refused (evidence and before/after exit codes in
  `research/release-readiness-audit-2026-10-15.md`).
  **Extended after the manual acceptance run (2026-10-15):** the same refusal reaches *every* command, not
  only the reports - a follow-up draft, a `.ics` file and an import are refused in the same sentence with the
  same exit status, because a readable database holding one unreadable row is not a start-up that failed and
  must not be described as one. And a command that writes checks first: the import sweeps the whole file
  read-only before it plans or applies anything, because applying part of an import and failing on the record
  halfway leaves a part-written database behind a refusal that says nothing was written. Both were reproduced
  before they were fixed, and both have a regression test that fails on the behaviour they replaced
  (`tests/test_damaged_records.py`, evidence in `research/local-alpha-manual-acceptance-run-2026-10-15.md`).
  **Extended again by the desktop-verification increment (2026-10-15):** a refusal has to name the right
  *kind* of failure. A database that is intact but cannot be *written* - a read-only file, a read-only
  folder, a folder that is not there, another process holding it - was reported as "this database file could
  not be read", with the advice to restore a verified backup over it: a read described for a write, damage
  that is not there, and a remedy that would fail in exactly the same way. The refusal now says the database
  could not be written to, keeps exit status 2, still writes nothing, and the classifier that chooses between
  the two keeps read failures on the read sentence. Reproduced on a read-only file, a read-only folder and a
  read-only filesystem before the fix; `looks_like_a_write_failure` and
  `tests/test_damaged_records.WriteRefusalTests` are the regression coverage, and the before/after transcripts
  are in `research/cross-platform-desktop-ci-evidence-2026-10-15.md`.
  **A smoke test may never report success for a window it did not build** (2026-10-15): the scripted desktop
  entry point exits 2 with `RESULT: BLOCKED` when the machine has no display or no Tkinter, prints no check as
  passed, and the CI leg that requires a window runs it under a real display where it must exit 0. Manual GUI
  acceptance stays the human checklist; no automated run closes a step of it.
  **A scripted window check counts only after it has run against a real window** (2026-10-15): the smoke entry
  point passed code review and its own tests, then failed the first time a display existed - it asked a
  notebook for its tabs, which answers with widget *names*, and inspected those as widgets. A check that has
  never run where it is supposed to run is a plan, not evidence.
  **Where a platform has no capability, report that; do not refuse the work** (2026-10-15): the owner-only
  file guarantee is POSIX-only and no protection is claimed elsewhere, but the private-write helpers applied
  it through the descriptor and treated any failure as a reason to refuse the write. On Windows there is no
  descriptor mode and `os.fchmod` does not exist, so the lookup raised and every `CareerStore` construction
  failed with it - 949 errors on the first Windows run, with the open descriptor leaked. A capability the
  platform does not have must be skipped on that platform, consistently, wherever it is asserted; the
  POSIX refusal (a filesystem that will not apply the mode) must keep refusing.
  **A test may not spell out a platform's own names** (2026-10-15): the application keeps its files in
  `AI Career Agent` on macOS and Windows and `ai-career-agent` elsewhere; six doctor tests hard-coded the
  Linux name, so on those platforms they wrote to a folder the application never reads and reported failures
  that were the test's own. Expectations of this kind are computed with the code that decides them.
  **A failing run must publish its evidence where the project can read it** (2026-10-15): a job's log lives
  on a storage host a restricted network cannot reach, and the API answers a failed step with its exit
  status alone. Every step of the new jobs, from the first report to the smoke test, starts with a `tee` into
  one notes file (a step of its own creates the file first), and `scripts/ci_annotate.py` turns the recorded
  failures into annotations, which the API does return: one annotation listing every failing test by name, ten
  findings with the end of each traceback, and the run's last words - because a step may carry only ten error and
  ten warning annotations, and a run can fail in more places than that. A step whose output is not recorded is a
  step whose failure
  cannot be diagnosed from this network: the macOS wheel step was exactly that, and stayed unexplained until
  the recording covered it.
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
- Never claim a message was sent or an event created unless the integration that performed it says so, and
  never perform either from a routine tracker update, a schedule, or a draft being written.
  **Implemented as an invariant (2026-10-15):** `career_agent/integrations.py` separates preparing from
  performing. A draft or an event is a value; previewing one produces text and no side effect; performing one
  goes through an integration, and the default refuses every request with a `disabled` result naming the
  reason. The only implementation that performs anything is an explicitly named local mock, which records the
  operation in a ledger and contacts nothing. Every operation carries an id derived from its own content, so a
  repeat is reported as a duplicate, a failed attempt is not recorded as done (a retry is allowed and still
  performs it once), and an id already recorded for a different kind of operation is refused rather than
  guessed at. Nothing infers a recipient address, an interview time or a timezone: each is either supplied by
  the person or reported as missing.

## 6. Privacy and security

- Keep resumes, candidate profiles, and application records local by default.
- External processing requires clear disclosure and explicit consent.
- Send the minimum necessary data to external services.
- Never store passwords in plaintext or commit secrets to Git.
- Keep sensitive content out of logs where possible.
  **Implemented as an invariant:** the application's own event log (`career_agent/event_log.py`,
  `logs/application.log` beside the database) carries an event name, an identifier, a count or a
  category - never profile values, résumé text, evidence text or a URL. Every detail is stripped to one
  line, capped, and passed through the same path redaction as the start-up note, so a log written for
  support can be shared without exposing candidate data or local locations. The file is owner-only where
  the platform supports it, bounded by rotation, and a logging failure never fails the action it was
  describing.
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
- Never change a database that already holds someone's data without a verified copy of it beside the
  file first. A migration step can be committed and only then discovered to be wrong, and rollback cannot
  reach it after the commit; the copy is the recovery path. Refuse the update if the copy cannot be
  written, and never reuse an existing snapshot as if it were this attempt's.
- Define acceptance criteria before implementation; include failure cases, recovery, data migration, privacy, security, and accessibility as appropriate. Run tests and inspect the final repository state before claiming completion.
- The intended discovery cadence is 00:00 and 12:00 Asia/Kolkata. Laptop-off operation requires a verified always-on worker; do not claim it based only on desktop scheduling or an untested free tier.
- Measure quality, not volume alone: extraction correctness on critical fields, top-ranked job relevance, eligibility false positives, duplicate prevention, direct application-route validity, evidence-backed status, scheduler recovery, and user outcomes. Do not promise selection.
- Background work is identified by the occurrence it serves, not by when it started. A scheduled
  occurrence has an identity that survives restarts, and a retry serves the occurrence it owes; never
  let a retry, a restart or a second process turn one occurrence into two executions or none. Record a
  refusal as a refusal (a rule said no) rather than as a failure, and never retry it.
- A source's public availability, API endpoint, or rendered form is not proof of permission. Discovery and submission are reviewed separately for each provider and workflow.
