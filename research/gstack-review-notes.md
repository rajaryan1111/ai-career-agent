# gstack review

**Reviewed:** 2026-10-13  
**Upstream:** https://github.com/garrytan/gstack  
**License:** Upstream README identifies the project as MIT-licensed; re-check the exact current license and notices before copying or redistributing any files.  
**Decision:** Reuse selected engineering-process ideas only. Do not install gstack or add it as an application dependency. The current project phase remains research/product strategy.

## What it is

gstack is a Claude Code-oriented software-development workflow/toolkit. Its README describes role-like workflows for product/CEO review, engineering planning, design, code review, QA/browser use, investigation, security review, release and retrospection. It is not a job-source API, job aggregator, eligibility engine, resume matcher, or application-submission integration.

## Useful ideas for AI Career Agent

- Challenge product assumptions before building; make success criteria and non-goals explicit.
- Review architecture and failure modes before committing to a feature design.
- Perform a dedicated code/spec review and a separate QA/verification pass.
- Investigate root causes instead of repeatedly patching symptoms.
- Use explicit security/privacy review and a release checklist.
- Record what was learned and update project memory after material decisions.

These are process ideas, not proof that a product feature is correct or compliant. The project-specific adaptation is documented in [development-workflow.md](../development-workflow.md).

## What not to import

- Do not install the full Claude Code slash-command toolkit, hooks, browser-control setup, or environment-specific scripts into this repository or the end-user app.
- Do not adopt autonomous shipping/deployment or browser workflows without separate review and explicit authorization.
- Do not add telemetry or network behavior to AI Career Agent because an upstream developer tool offers it.
- Do not assume a specific coding-agent environment, terminal, browser, or subagent harness is available.
- Do not let a review workflow bypass the research gate, source terms, user approval, privacy constraints, or truthful application-state requirements.

## Project-specific constraints that take precedence

- No implementation until the research/product decision gate is reached.
- Source access and application submission permissions must be verified independently.
- No CAPTCHA, OTP, anti-bot, access-control, or rate-limit bypass.
- Never fabricate candidate facts or screening answers.
- A filled or attempted form is not proof of submission; confirmation needs evidence.
- Local-first data handling and zero mandatory recurring cost remain product constraints.
- Model/agent review is useful but is not independent evidence.

## Conclusion

Adopt the useful review/checklist mindset, not the toolchain. Keep the workflow small, evidence-backed and compatible with the actual environment. Reassess only after the research gate; any future installation or tool adoption needs its own compatibility, security, privacy, maintenance and cost review.

## Sources

- gstack repository: https://github.com/garrytan/gstack
- README: https://github.com/garrytan/gstack/blob/main/README.md
- Project-specific adaptation: [development-workflow.md](../development-workflow.md)
