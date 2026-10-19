# AI Career Agent — Safe Development Workflow

**Status:** Active project guidance for offline-core engineering and evidence-gated integrations.
**Created:** 2026-10-13  
**Purpose:** Reuse the most relevant ideas from [gstack](https://github.com/garrytan/gstack) and [Superpowers](https://github.com/obra/superpowers) without importing their toolchains, blindly following agent instructions, or weakening this product's trust requirements.

## Decision in one minute

- **Reuse process ideas, not whole repositories.** Keep this guide as our project-specific adaptation; do not install either repository as an application dependency or copy their skills wholesale.
- **Research gate still applies to external capabilities.** Offline storage, profile, résumé, matching, tracking, recovery and packaging work may proceed when the requirements are sufficiently specified. Live discovery, outbound communication and application submission still require their own permission and quality evidence.
- **Evidence beats confident claims.** A plan, agent review, passing test, or accessible page is evidence of only what it actually checks—not proof of source permission, employer legitimacy, matching quality, or successful job application.
- **User authority and product safety win.** No agent workflow may override explicit approval, local-first privacy, zero-mandatory-cost constraints, source terms, candidate truthfulness, or confirmation requirements.

## Workflow to use when work is authorized

### 1. Frame the problem before choosing a solution

Write down:
- user and situation;
- problem evidence and current workaround;
- desired outcome and measurable acceptance criteria;
- non-goals and constraints;
- alternatives considered, trade-offs, and unresolved questions;
- the smallest useful test that could disprove the idea.

For research work, the output can be a short decision note. Do not manufacture permission or quality evidence for a gated integration; continue independent offline implementation where its requirements are clear.

### 2. Specify observable behavior

Before implementing a feature, describe inputs, outputs, state changes, errors, permissions, and what the user sees. Include acceptance criteria that can be checked independently. Keep the specification aligned with `prd.md`, `architecture.md`, `design.md`, `rules.md`, and `phases.md`; update the canonical document rather than maintaining conflicting copies.

### 3. Make a small, reviewable plan

Split approved work into small tasks. Each task should identify the intended change, dependencies, acceptance criteria, and verification step. Avoid broad “build the whole feature” tasks. Use a separate branch/worktree when the available environment supports it and doing so reduces collision risk; do not assume a particular coding-agent harness exists.

### 4. Test high-consequence deterministic rules first

When implementation is authorized, prefer test-first development for:
- hard eligibility exclusions and unknown eligibility;
- remote geography and work-authorization conditions;
- expired/stale listings and conflicting source records;
- duplicate detection and retry safety;
- candidate-fact provenance and missing screening answers;
- application state transitions and confirmation evidence;
- local scheduler catch-up and idempotent run processing;
- privacy boundaries, data deletion/export, and redaction.

For deterministic logic, use the red → green → refactor loop: demonstrate the test fails for the intended reason, make the smallest change, rerun it, then refactor without losing coverage. Do not claim this happened unless the commands and results were actually observed.

### 5. Debug root causes, not symptoms

When a defect appears:
1. Reproduce it and record the exact observed behavior.
2. Inspect logs/evidence with secrets and personal data redacted.
3. Form a small number of falsifiable hypotheses.
4. Run the smallest experiment that distinguishes them.
5. Fix the underlying cause, add a regression test, and verify adjacent behavior.
6. Record any remaining uncertainty.

Do not keep layering patches on an unverified diagnosis.

### 6. Review against both the specification and product risks

Review each meaningful change in two passes:
- **Specification pass:** Does the change meet the accepted requirements and avoid unrelated scope?
- **Risk/code-quality pass:** Check error paths, privacy, secrets, data minimization, permissions, retries, accessibility, maintainability, and tests.

A second model/agent review can find issues but is not independent proof. Resolve critical/high-severity findings or explicitly document why a finding is not applicable before calling work complete.

### 7. Verify before saying “done”

Use fresh, relevant evidence:
- run the focused tests, then the broader available suite;
- run lint/type checks/build where the project provides them;
- inspect the diff and repository status;
- verify the actual resulting GitHub file/commit or release state when claiming it was pushed;
- state what was tested, what passed/failed, and what was not tested.

Never say a feature, fix, test, deployment, or application submission succeeded based only on intention or an unverified click.

### 8. Ship deliberately and preserve a decision trail

Before merging/releasing:
- confirm the scope and diff are expected;
- check for secrets, real candidate data, copied licensed material, and unrelated edits;
- ensure tests and documentation match the implementation;
- preserve required third-party notices if code/material is ever reused;
- choose merge/release/rollback deliberately;
- add material decisions and unresolved issues to `memory.md`.

Use small commits with descriptive messages. Do not force-push, delete, or silently overwrite meaningful project history as a shortcut.

## Product-specific safety gates — non-negotiable

These rules override any imported developer workflow that encourages autonomy or speed:

1. **Source permission:** Public/accessible does not mean permitted for bulk ingestion or automated applications. Verify official API/terms and record the access method, scope, rate limits, attribution, retention and last-checked date.
2. **Separate capabilities:** Evaluate discovery, detail retrieval, autofill and submission separately for each source. Do not advertise universal support based on a successful page read.
3. **Candidate truth:** Never infer or fabricate qualifications, dates, GPA, work authorization, identity declarations or screening answers. Unknown is not eligible by default.
4. **Application states:** Distinguish discovered, reviewed, eligible, opened, autofilled, submitted and confirmed. Confirmation requires reliable evidence; an ambiguous submission must be checked before retrying.
5. **No bypass:** Do not bypass CAPTCHA, OTP, access controls, anti-bot measures or rate limits. Pause for user action when a workflow is unsupported or uncertain.
6. **Sensitive/irreversible/external actions:** Require explicit user authorization as appropriate. Agent autonomy, parallel agents or an approved plan never grants blanket permission.
7. **Privacy and cost:** Local-first by default; minimize external data transfer; no secrets in Git; no mandatory paid AI API or hosted backend in the core path.
8. **Honest uncertainty:** Label facts, assumptions, hypotheses, proposals and unknowns distinctly. Do not convert a model's confidence into source evidence.

## What we are deliberately not importing

- No gstack or Superpowers install, hooks, browser-control tools, agent instructions, dependencies, or copied skill directories.
- No automatic code changes just because a workflow skill says to proceed; the research gate remains authoritative.
- No requirement to use a specific vendor, coding agent, browser, subagent system, terminal capability, or worktree manager.
- No automatic release, deployment, form submission, paid service, or external data transmission.
- No telemetry or network behavior added to the product merely because an upstream tool has optional telemetry.
- No use of large AI-generated changes without inspecting the diff and verifying behavior.


## Targeted lessons from agency-agents (reviewed 2026-10-13)

Reference review: [Agency Agents repository review](research/agency-agents-repository-review-2026-10-13.md). These are adapted process principles only; no upstream persona catalog or tooling is installed.

### Minimum-change scope check
For each meaningful change, record the required outcome and why each modified file is necessary. Keep unrelated cleanup or speculative enhancements separate. Inspect the final diff and remove lines that do not support the task. Do not suppress a necessary safety fix merely to keep a diff small.

### Evidence and honest reporting
Label findings as observed, inferred, unknown/not tested, or proposed. Choose evidence suited to the claim: screenshots prove appearance, assertions/logs establish behavior, source terms establish documented rules, and live samples are needed to measure coverage. A passing test does not prove unrelated properties such as permission, completeness, or successful submission. Verify resulting GitHub state before claiming a push succeeded.

### Matching-evaluation guardrail
Before adjusting matching/ranking after the research gate, compare against a versioned human-reviewed judgment set covering common and long-tail queries, wording variants, ambiguous job families, and negative controls. Report retrieval coverage separately from ranking quality. Eligibility constraints must remain hard gates and cannot be outweighed by semantic similarity. Do not claim recall without a defensible denominator.

### Prompt/retrieval safety guardrail
If model prompts or agent instructions are later added, specify task, permitted tools/data, output shape, success criteria, and failure/unknown behavior. Add regression fixtures for ordinary, edge, and adversarial cases where relevant. Treat listings, resumes, documents, and tool output as untrusted data, never as instructions that can expand permission or tool authority. Review executable scripts before running them.

## Source review and limits

### gstack
Repository: https://github.com/garrytan/gstack  
README: https://github.com/garrytan/gstack/blob/main/README.md  
License: upstream README identifies MIT; re-check the exact license and notices before redistributing any files.

Relevant inspiration: explicit product/engineering/design reviews, code review, QA, investigation, security review, release checklists, and reflection. These map to our problem-framing, two-pass review, root-cause investigation, verification, and ship checklist above.

Not adopted: the whole Claude Code-specific slash-command/toolchain, browser setup, hooks, installation steps, or autonomous shipping flow. Those add environment-specific behavior and are unnecessary for a research-stage desktop job agent.

### Superpowers
Repository: https://github.com/obra/superpowers  
README: https://github.com/obra/superpowers/blob/main/README.md  
Relevant skill references:
- https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md
- https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md
- https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md
- https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md
- https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md
- https://github.com/obra/superpowers/blob/main/skills/using-git-worktrees/SKILL.md
- https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md
- https://github.com/obra/superpowers/blob/main/LICENSE

Relevant inspiration: brainstorming before coding, explicit specs and plans, test-first deterministic behavior, systematic debugging, isolated work, code review, and verification before completion. The upstream repository identifies itself as MIT-licensed; verify the current license file and preserve notices if copying/redistributing material. This project uses original, summarized guidance rather than reproducing upstream skill text.

## When to revisit

Reassess this workflow at the product decision gate, then after the first real implementation slice. Keep only practices that improve correctness, auditability or delivery without adding unnecessary ceremony. Any tooling adoption requires a separate compatibility, permissions, maintenance, security and cost review.



## Karpathy-inspired coding principles — adapted 2026-10-14

Reference reviewed: [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills), especially its [README](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/README.md), [skill definition](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/skills/karpathy-guidelines/SKILL.md), and [examples](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/EXAMPLES.md). The source distills four ideas: think before coding, simplicity first, surgical changes, and goal-driven execution.

These principles are adapted here to our project rather than copied as vendor-specific instructions:

### 1. Surface assumptions and uncertainty before consequential work
- State the assumptions that materially affect implementation, especially data ownership, permission, eligibility, external side effects, and compatibility.
- When two interpretations would lead to meaningfully different behavior, do not silently choose a risky interpretation; surface the alternatives or use the safer reversible option.
- Push back on unnecessary complexity or an approach that conflicts with the PRD, user authority, evidence, or product safety.
- Do not interrupt work for trivial ambiguities that can be resolved conservatively and reversed cheaply. Keep momentum while making consequential uncertainty visible.

### 2. Choose the smallest complete solution
- Implement only what is needed for the stated user outcome and acceptance criteria.
- Do not add frameworks, dependencies, layers, configuration knobs, caching, abstractions, network services, or generality without a demonstrated need.
- Prefer existing standard-library and repository capabilities when adequate.
- Error handling should cover realistic failures at trust boundaries; do not bury core behavior under speculative defensive code.
- If a short implementation is equally clear, correct, and testable, prefer it over a much larger one.

### 3. Keep diffs surgical
- Inspect current files and their callers before editing; preserve unrelated code, comments, formatting, and decisions.
- Every changed file must have a direct reason tied to the user request or required verification.
- Do not bundle drive-by refactors or clean up unrelated code. Remove only dead code introduced by the change.
- Preserve meaningful history; never silently delete or replace project decisions.
- For each meaningful change, inspect the final diff and re-fetch relevant files before reporting completion.

### 4. Define observable success and verify it
- Turn vague tasks into concrete acceptance criteria before coding.
- For deterministic logic, write a focused regression test first where practical, reproduce the failure, implement the smallest fix, and rerun the test.
- Verify with the focused tests, then the complete available suite; run compilation, lint, type-check, or build checks when applicable.
- Report exact checks actually run, failures, and untested areas. A test pass proves only the behavior that test exercises.
- Do not equate a pushed workflow with a completed CI run, a parsed page with a verified open role, or a clicked Submit button with a confirmed application.

### Lightweight pre-change and post-change checklist
1. Goal and acceptance criteria are explicit.
2. Current implementation and relevant call sites were inspected.
3. Assumptions, alternatives, and risky unknowns are surfaced.
4. Chosen approach is the smallest complete and reversible one.
5. Tests cover expected behavior and important negative/unknown cases.
6. Diff contains only task-relevant changes.
7. Test/check results and residual uncertainty are accurately reported.

This checklist is deliberately short; it is not a mandatory ceremony for trivial edits.

### Precedence and project-specific boundaries
These guidelines improve engineering execution but do not grant new capabilities or permissions. Existing project rules remain higher priority for source access, candidate privacy, truthful profile facts, tool permissions, costs, network access, and application submission. In particular:
- Research and offline-core coding may proceed in parallel.
- Live job-source integrations remain gated by source-specific terms, quality, and attribution review.
- Candidate data stays local by default and is not sent to a provider without explicit disclosure and consent.
- Unknown eligibility never becomes pass; relevance never overrides hard eligibility.
- No CAPTCHA/OTP/access-control/rate-limit bypass, fabricated candidate facts, unapproved external write, or unverified submission claim.
- Never add a third-party skill/toolchain only because the reference repository packages one for Claude Code or Cursor.
