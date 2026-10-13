# Superpowers Repository Review for AI Career Agent

**Reviewed:** 2026-10-13  
**Upstream:** https://github.com/obra/superpowers  
**License observed:** MIT (upstream `LICENSE`)  
**Decision:** Adopt selected workflow principles later; do not install, copy wholesale, or add a runtime dependency during research phase.

## Executive conclusion

Superpowers is an agentic software-development methodology composed of skills and process instructions. It is not a job discovery API, job-source aggregator, browser automation framework, resume matcher, or application-submission integration. Its value to AI Career Agent is primarily in *how we plan, implement, test, review and verify the product*, not in the product's end-user feature set.

The repository README describes a sequence of requirements clarification/design, isolated workspace, implementation planning, test-first development, and work/review cycles. Relevant inspected skills include `brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `subagent-driven-development`, and `using-git-worktrees`.

## What maps well to our project

| Superpowers practice | Potential AI Career Agent benefit | When to use |
|---|---|---|
| Brainstorming before building | Stops us turning an attractive idea into a premature feature; forces concrete user situation, success criteria, non-goals, prior art, and trade-offs | Before deciding MVP scope or resolving a product-direction question |
| Explicit design/spec before plans | Captures behaviors and constraints—local-first, no paid AI requirement, hard eligibility gates, human confirmation on uncertain/sensitive steps—before code | After the research/validation gate, when one feature is sufficiently defined |
| Bite-sized implementation plans | Each task names files, expected behavior, and a checkable verification step; reduces ambiguity and overbuilding | After a spec is approved, not during current open-ended research |
| Test-driven development (red/green/refactor) | Makes edge cases executable, especially hard exclusions, duplicates, stale jobs, eligibility and truthful application states | When implementation is authorized |
| Systematic debugging | Investigates reproducible root causes instead of patching symptoms across source adapters or scheduler layers | For any future defect or surprising result |
| Verification before completion | Requires fresh command/test evidence before saying a change works or is complete | For every future implementation/bug fix/release claim |
| Worktrees and task isolation | Isolates future feature branches; helps avoid unrelated edits colliding in a single working tree | Before approved code work, subject to the user's workspace preferences |
| Subagent implementation/review | Could parallelize genuinely independent work, with per-task review and final cross-feature review | Only when tasks and interfaces are stable and the available agent harness supports it |

## Translate the practices into product-specific test scenarios

These are proposed validation cases, not implemented tests:

1. **Eligibility is a hard gate:** an India-based candidate must not receive a role explicitly limited to US-based candidates as eligible, even if the title and skills match strongly.
2. **Remote does not mean global:** country, work authorization and time-zone conditions must be extracted and shown with source evidence; unknown is not equivalent to eligible.
3. **Expired roles remain non-actionable:** a still-reachable URL with a passed close date must not be presented as open without newer official evidence.
4. **No fabricated candidate facts:** missing GPA, work authorization, graduation date or screening declarations must remain unknown and be asked of the user only when needed.
5. **Source traceability:** every critical eligibility/status assertion should retain a canonical source URL and a checked timestamp; conflicting aggregator and employer pages should be visible and resolved conservatively.
6. **Application truthfulness:** “opened,” “autofilled,” “submitted,” and “confirmed” are separate states; a click or filled form alone must never count as confirmed submission.
7. **Retry safety:** retries should not silently create duplicate submissions or duplicate ledger records; where no idempotency can be guaranteed, ask the user or stop.
8. **Permission is separate from technical access:** a page being public or parseable must not automatically enable bulk crawling or application automation.

## Adaptations and cautions

- **Do not adopt all workflow instructions literally.** Superpowers is designed for coding-agent harnesses and some instructions assume particular skill invocation, subagent, worktree, or terminal capabilities. Use only practices the current environment can actually execute.
- **Avoid ceremony during research.** The project is not ready for implementation-plan generation or TDD yet. A short research checklist and documented decision are better than writing fictional code plans.
- **Human approval remains authoritative.** Some workflow instructions encourage autonomous continuation and recorded rulings. For this project's product, irreversible, security-sensitive, privacy-affecting, paid, external, and application-submission actions must still follow the user's explicit authorization and the product's intervention rules.
- **A model review is not independent evidence.** A second agent can miss the same error. Critical findings need official source evidence, reproducible checks, and/or human review.
- **No automatic benefit to end users:** adopting Superpowers does not increase job-source coverage, establish scraping rights, verify an employer's legitimacy, improve matching accuracy by itself, or make a workflow free of hosted inference costs.
- **Do not install as a product dependency.** If used later, it belongs in a developer environment/workflow, not inside the downloadable AI Career Agent runtime.
- Upstream is MIT-licensed according to the inspected `LICENSE`; if any files or skill text are copied or redistributed, retain required notices and review the exact files and current license. Prefer adopting general practices over copying large bodies of instructions.

## Recommendation

**For now:** retain this as workflow research only. Continue the job-source audit and user-segment validation; do not install Superpowers or begin implementation.

**At the decision gate:** consider adopting a small workflow subset:
1. Brainstorm/requirements spec before each meaningful feature.
2. Small explicit task plan with measurable acceptance criteria.
3. Test-first implementation for deterministic rules and state transitions.
4. Root-cause debugging when something fails.
5. Fresh verification before completion claims.
6. An isolated branch/worktree when safe and available.

Use subagents only when work can be split cleanly and independently reviewed. The product's own trust and privacy requirements override any push toward autonomous execution.

## Sources checked

- Superpowers repository / README: https://github.com/obra/superpowers
- Brainstorming skill: https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md
- Writing plans skill: https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md
- Test-driven development skill: https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md
- Systematic debugging skill: https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md
- Verification before completion skill: https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md
- Subagent-driven development skill: https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md
- Git worktrees skill: https://github.com/obra/superpowers/blob/main/skills/using-git-worktrees/SKILL.md
- License: https://github.com/obra/superpowers/blob/main/LICENSE

No code was written and no implementation was started in this review.
