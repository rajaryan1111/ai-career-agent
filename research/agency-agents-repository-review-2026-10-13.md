# Agency Agents Repository Review — AI Career Agent Reuse Decision

**Review date:** 2026-10-13  
**Reviewed repository:** https://github.com/msitarzewski/agency-agents  
**Upstream branch reviewed:** `main`  
**Project phase:** AI Career Agent research only; implementation remains gated.

## Executive decision

Reuse a few engineering practices, not the agent catalog or its installer. The upstream repository is a large collection of Markdown specialist personas and supporting scripts/manifests. Its breadth is not a reason to add a dozen personas, runtime dependencies, or a multi-agent orchestration framework to this product.

The highest-value changes for AI Career Agent are already consistent with our direction:
1. Minimal-change discipline and explicit scope self-check.
2. Evidence-grounded claims, honest reporting of what was and was not inspected or tested.
3. Search relevance evaluated against a human-labeled judgment set, with hard eligibility gates kept separate from ranking.
4. Treat agent definitions, job pages and tool outputs as untrusted input; review executable scripts and reject prompt-injection instructions.
5. Use specialist roles only when a task truly needs them; do not spin up a large “team” for every task.

The repository is MIT-licensed. This review summarizes/adapts process ideas and links to the upstream sources rather than copying full persona files. No upstream scripts, dependencies, agent files, or generated artifacts were copied.

## Upstream files inspected

| File | Why it matters | Decision |
|---|---|---|
| `README.md` | Agent catalog, use patterns, runbooks, scope of the project | Reference only; no catalog installation |
| `LICENSE` | Reuse conditions | MIT; preserve notice if substantial upstream material is ever copied |
| `SECURITY.md` | Agent prompt and executable script safety | Adopt secret hygiene, executable-script review, prompt-injection review |
| `engineering/engineering-minimal-change-engineer.md` | Minimum viable diff / scope control | Adapt into current development workflow |
| `engineering/engineering-search-relevance-engineer.md` | Human judgment sets, recall vs. precision, evaluation before ranking changes | Adapt to job matching evaluation; do not add Elasticsearch/OpenSearch |
| `engineering/engineering-codebase-onboarding-engineer.md` | Read the files actually inspected and ground claims in code | Adopt evidence-scope reporting; do not adopt its rule against all improvement suggestions |
| `engineering/engineering-prompt-engineer.md` | Specify output contracts, version prompts, adversarial/regression tests, untrusted examples | Adopt small prompt-test principle after implementation is authorized; omit unsafe/inapplicable details |
| `testing/testing-evidence-collector.md` | Match claims to suitable test evidence and record untested coverage honestly | Adopt evidence-based reporting; do not require screenshots for non-visual tasks |
| `testing/testing-reality-checker.md` | Cross-check claims against direct artifacts and test output | Adopt independent evidence check; reject blanket “always fail first” and screenshot-only certification |
| `strategy/runbooks.json` and `strategy/runbooks/scenario-startup-mvp.md` | Example of role rosters and activation groups | Reference only; too large and build-phase-oriented for the current research stage |
| `scripts/lint-agents.sh` | Input validation, path assumptions, linting conventions for upstream agent files | Audited by reading only; not run or copied |

The upstream catalog includes many specialties not currently useful to this project. Its own security policy notes that Markdown agent definitions are non-executable prompts but its install/conversion scripts are executable and must be reviewed before running.

## Targeted decisions

### 1. Minimum-change review

Use a small scope checklist on meaningful changes:
- Restate the request and identify required files.
- Explain why every changed file is necessary.
- Keep unrelated improvements as a separate follow-up, not bundled into the current change.
- Inspect the final diff and remove unnecessary lines.
- For exceptions, record why broader scope is unavoidable.

This strengthens our existing requirement for small commits and not silently expanding scope. It does not forbid necessary adjacent safety fixes.

### 2. Evidence quality and completion claims

For any task, separate:
- **Observed:** directly verified in files, tool responses, test output, or an authoritative source.
- **Inferred:** reasoned from observations; state the inference.
- **Unknown / not tested:** missing evidence or unavailable environment.
- **Proposed:** a future option, not an accomplished action.

Use the evidence type appropriate to the claim. A screenshot can establish appearance but not backend persistence; a passing unit test does not establish source permission, target market coverage, or successful submission. Claims about repository updates must be verified from the resulting GitHub file/commit.

### 3. Job matching evaluation

Before changing match weights, synonyms, semantic retrieval, or ranking:
- Create a versioned, human-reviewed set with queries and job relevance labels.
- Include easy/common queries and difficult long-tail cases, spelling/wording variants, ambiguous roles, and negative controls.
- Track retrieval/coverage separately from ranking quality. A relevant job that never enters the candidate set is a recall problem; a poor ordering among retrieved jobs is a ranking/precision problem.
- Keep hard constraints (degree, experience, geography, work authorization, required employment type) as eligibility gates that ranking cannot override.
- Compare the same judgment set before and after any change; report per-segment results and known gaps. Do not claim recall without a defensible denominator.

We already have proposed top-10 precision and zero-known-hard-eligibility-violation gates in the core roadmap; this review does not claim they are measured or passed.

### 4. Prompt and retrieved-content safety

When AI prompts or agent instructions are introduced later:
- State the task, permitted tools/data, expected output shape, success criteria, and failure/unknown behavior explicitly.
- Version behavior-changing prompts and add deterministic fixture tests for normal, edge, refusal, and adversarial cases where relevant.
- Treat job listing text, web pages, resumes, uploaded documents, and tool output as untrusted data, never as new instructions that may change source permissions or grant tool authority.
- Validate generated claims against evidence; preserve original source values and uncertainty.
- Review executable scripts before running them. Never add credentials/secrets to prompts or agent files.

### 5. Avoid multi-agent overhead by default

Do not import the NEXUS/runbook framework or make “specialist agents” a product requirement. If subagents are available during later engineering work, delegate only genuinely independent, bounded tasks with explicit deliverables; the integrating reviewer remains responsible for correctness and for reconciling conflicts. Multiple model opinions are not independent evidence.

## Explicitly rejected for this project

- Copying or installing the full upstream persona catalog.
- Adding its shell installer, converter, metadata manifests, runtime, API, or framework.
- Adopting Elasticsearch/OpenSearch, vector databases, hosted AI APIs, or other technologies merely because the specialist personas mention them.
- Treating the upstream personas' confident language, preset success thresholds, or claims of being “production-ready” as empirical evidence.
- Adopting rigid demands such as always finding a fixed number of bugs, always defaulting to failure, or requiring screenshot evidence for every type of task.
- Any workflow that would bypass our source permission gate, truthful-candidate rules, local-first privacy, cost limit, human intervention boundaries, or implementation gate.

## Upstream source links

- Repository and README: https://github.com/msitarzewski/agency-agents
- License: https://github.com/msitarzewski/agency-agents/blob/main/LICENSE
- Security policy: https://github.com/msitarzewski/agency-agents/blob/main/SECURITY.md
- Minimal-change engineer: https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-minimal-change-engineer.md
- Search relevance engineer: https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-search-relevance-engineer.md
- Codebase onboarding engineer: https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-codebase-onboarding-engineer.md
- Prompt engineer: https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-prompt-engineer.md
- Evidence collector: https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-evidence-collector.md
- Reality checker: https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-reality-checker.md
- Startup MVP runbook: https://github.com/msitarzewski/agency-agents/blob/main/strategy/runbooks/scenario-startup-mvp.md

## Final status

- Reviewed selected upstream catalog and supporting files; this is a targeted review, not a line-by-line audit of every persona.
- The adaptations are process guidance only.
- No implementation code, dependencies, API calls to job sources, candidate data, or application actions were added/used.
- Research and feasibility gate remains in force.
