# Product Design Notes

**Status:** Product UX specification; Tkinter local alpha implemented, manual GUI acceptance outstanding. A scripted smoke entry point (`scripts/desktop_smoke_test.py`) builds and drives the real window where a display exists - it must pass under Xvfb in CI and reports BLOCKED, never a pass, where there is none. A second entry point (`scripts/desktop_acceptance.py`) drives eleven end-to-end workflows through that same real window - profile persistence, the two job URLs, eligibility safety, tracker transitions and analytics, export/import and its refusals, the work history and study forms (including their refusals and a role's stored values loaded back for editing), follow-up reminders and the combined next-action list (including the first day for an application, days computed from fixed offsets, a moved and cleared day, and a calendar preview and email draft that write and send nothing), the scheduler tab (default tasks added and kept, pause confirmed first and surviving a restart, resume scheduling from now, what the schedule walked past while nothing ran, and no worker started or lease taken), data safety (a verified backup, an existing file never overwritten, malformed, foreign, truncated and too-new files refused, a declined restore changing nothing, a restore that keeps the previous database as a readable copy, and no temporary file left behind), a measured pass over every tab - what is on screen at the window's own declared minimum, at the size it opens with and larger, what sits outside the box it is drawn in, what was given less room than its text asked for, and the focus order and labelling of the controls - and cleanup, checking stored records and the window's own status line; it reports 82 checks, runs on five display-backed CI legs (Linux under Xvfb, Windows 2025, macOS 26) and cannot report a pass without a display. The smoke entry point's first run against a real display (Linux, Xvfb, 2026-10-15) failed one check of fourteen and passed the other thirteen, which is how a check that inspected a notebook's tab *names* as if they were widgets was found, and the acceptance entry point's first run found the same class of thing one level deeper: a cleanup check that read Tk's refusal to answer for a destroyed interpreter as the window having survived; the Windows and macOS runs of the suite found that every private write was refused on Windows and that six doctor tests hard-coded Linux's data-folder name  

The manual half is not automated and never will be: [the human desktop acceptance handoff](research/human-desktop-acceptance-handoff-2026-10-16.md) is the run-book for it, and [the checklist](research/local-alpha-manual-smoke-test-checklist-2026-10-14.md) holds the 98 steps, their expected behaviour and their per-step results - 22 PASS, 76 BLOCKED, 0 FAIL, no box ticked.
**Last updated:** 2026-10-16

## 1. Design objective

Make job discovery and application tracking transparent, calm, and trustworthy. Help candidates make good decisions without encouraging indiscriminate mass applications.

## 2. Primary navigation (hypothesis)

- Overview
- Discover Jobs
- Shortlist
- Companies
- Applications
- Candidate Profile
- Sources & Settings

## 3. First-run experience

1. Welcome screen explains local-first storage and limitations.
2. Resume import for PDF/DOCX.
3. Parsing preview with uncertain fields clearly marked.
4. Candidate confirms/edits critical information.
5. Preference setup: roles, locations, work mode, employment type, compensation, eligibility, excluded companies, and preferred sources.
6. Explain automation modes and platform-specific limits.
7. User decides whether to enable optional external AI/company research services.
8. Show source connection status and what can/cannot be automated.

Do not enable auto-apply before profile review and explicit configuration.

## 4. Job card requirements

Each job card should show role/company; location/work mode and employment type when known; source and original link; posting date and last-checked time where available; eligibility (eligible, ineligible, needs review); explainable match score; matched/missing requirements; sourced compensation or “not disclosed”; freshness/credibility warnings; and a clear next action.

## 5. Company report

Detailed research only for shortlisted/high-priority jobs. Include company overview/official website, products/industry/business model, relevant team/role context when supported, location/work mode, sourced compensation, relevant and current announcements/funding, employee feedback labeled anecdotal with date/context, credibility indicators, interview preparation, and source links/retrieval dates/confidence labels.

Never show an AI-generated statement as verified fact without a source.

## 6. Application tracking

States: Discovered, Shortlisted, Prepared, Awaiting user, Submission attempted, Submitted — unverified, Confirmed, Failed, Unknown status, Response received, Interview, Rejected, Withdrawn.

Show evidence for confirmed status where available. Unknown must not silently become confirmed.

The alpha adds a dated **activity history** beside the status rather than inside it: the person records
what happened and when (applied, employer replied, interview, assessment, followed up, note) and the app
records when it wrote the row. The two are kept apart on purpose — an entry is the person's own account,
not employer evidence, so it cannot satisfy the confirmation floor, cannot move the status, and cannot
create a tracker record. Entries are shown oldest first, one can be deleted explicitly, and deleting the
listing takes its history with it.

## 7. Exception handling

Pause when candidate information is missing/conflicting; a sensitive declaration is needed; a mandatory requirement cannot be verified; an assessment/custom response is required; CAPTCHA/OTP or another unsupported step appears; platform policy/workflow is unclear; or submission result is ambiguous.

Explain what happened, what is known, and what the user can do next.

## 8. Privacy and trust UX

Clearly indicate local vs external processing; ask consent before sending resume/profile data externally; display source and last-checked time; provide export/delete controls; never expose credentials in UI/logs; explain local scheduling limits while the computer is asleep/off.

## 9. Visual direction

Desktop-first, clean, information-dense but readable. Use restrained status colors, consistent labels, accessible contrast, and plain-language explanations. Avoid gamification that rewards raw application volume.

## 10. Current alpha and open design questions

The initial UI is Python/Tkinter over the Python domain core and local SQLite. This is a reversible low-dependency choice, not a production packaging decision. Validate installation/update experience on macOS, Windows, and Linux before release.

- Should company reports be generated on demand or after shortlisting?
- How should source failures and unavailable integrations be displayed?
  **Answered for the local alpha (2026-10-15):** integrations are shown as what they are. The reminders tab
  offers **Preview the calendar export** and **Draft a follow-up email**, both read-only, and both open the
  same kind of fixed-size, scrollable, close-only dialog the progress report uses - no editable field, no
  send button, and no setting anywhere that could turn one on. A draft states its status on its own first
  lines (`Status: DRAFT ONLY`), marks a missing recipient as missing rather than leaving a blank that could
  read as "ready", and the window's status line repeats that nothing was sent. The command
  `--integration-status` prints the same state for a terminal: nothing is enabled, what is available
  instead, and the seven conditions a real provider would have to meet. An unavailable capability is
  therefore visible as a *refusal with a reason*, never as a disabled button that suggests a setting
  exists somewhere.
- How should users set match thresholds without needing ML expertise?
- What is the clearest distinction between submitted and confirmed applications?
- Which local PDF/DOCX parser offers sufficient extraction quality without external uploads?


## 11. Cross-industry onboarding and role setup

Onboarding must not presume the user is a software/AI candidate. Ask for target occupation families, role titles and synonyms, experience stage, education/certifications where relevant, location/country/work authorization, work mode, employment type, compensation preferences, and exclusions. Show optional fields only when relevant to the selected role. Let users maintain multiple target-role profiles without duplicating their verified personal facts.

Occupation-aware match explanations should use familiar role language and distinguish required credentials/tools from preferred skills. For example, design roles may emphasize portfolio/tools; VLSI/embedded roles may emphasize hardware/EDA/firmware; mechanical and civil roles may emphasize domain tools, credentials, site/work-mode requirements; business roles may emphasize function-specific experience. These are illustrative patterns, not hardcoded eligibility assumptions.

## 12. Production dashboard and operational transparency

The Overview must show the last and next scheduled run in Asia/Kolkata, worker health, missed/partial runs, source-level counts/errors, new jobs, duplicate suppression, eligibility/unknown reasons, application statuses, and any action needing attention. Clearly separate planned, experimental, permission-gated, and production-supported integrations. Never show a green success indicator for an unverified submission.

Applications should expose an auditable timeline: discovered, checked, shortlisted, prepared, submission attempted, submitted-unverified, confirmed (with evidence), failed/unknown, response/interview, and final outcome. Provide retry/recovery actions that first check for possible prior success. The interface must explain why a task paused and how to resolve it without requiring users to understand internal technical details.

## 13. Trust, standing authorization, and remote operation

During setup, users can configure a revocable standing policy for routine, permitted applications so the system does not ask for per-job approval repeatedly. Explain which sources/actions the policy covers and how to pause/revoke it. The policy cannot override provider/employer restrictions or permit guesses on mandatory facts, sensitive declarations, assessments, CAPTCHA/OTP, or ambiguous submission results.

If background execution requires a remote worker, show a separate consent and data-flow explanation before sending any candidate data off-device. Display the actual worker status and last heartbeat; never imply that a local-only app runs while the laptop is powered off. Offer export, deletion, backup/restore, and connection revocation in understandable settings.

## 14. Accessibility and internationalization

Use clear language, keyboard-accessible workflows, readable status text that does not rely on color alone, timezone-aware scheduling, locale-aware dates and compensation units, and extensible country/work-authorization fields. Avoid treating English-language resumes or one country's education terminology as universal.


## 15. Local alpha operational states

- **No profile saved:** ask the user to enter/review facts; do not infer missing fields.
- **Résumé selected for import:** the document is read locally and the profile is left alone until the person reviews the proposals. Each proposal shows the field, the value, a short quotation of the text it came from, and a confidence label; only confident values start selected, and a value the parser is unsure about is never applied on its own; in particular, a skills line whose extractor-reported columns carry no recognisable category label is offered as read but never pre-selected. Values that were not selected, and fields the document did not mention, keep the saved values. Anything the profile has no field for (name, contact details, institutions, dates) is shown as information and is not added to the schema. A resume that cannot be read — encrypted, damaged, oversized, a legacy `.doc`, or a scanned PDF with no text layer — gets an explanation naming the next step (typing the values in) rather than a guess; there is no OCR. The document's text is never stored, logged or transmitted, no copy of the file is kept, and a failure at any point leaves the stored profile as it was.
- **Eligibility unknown:** explain each missing mandatory field and block shortlisting until all required checks explicitly pass.
- **Source not enabled:** say manual entry only; do not imply a search ran or that a listing is current.
- **Apply URL absent/unverified:** show the source listing URL separately and label the employer application URL as unknown.
- **Invalid status transition:** reject the update and explain the allowed next step; confirmation requires evidence.
- **No status change requested:** say that nothing changed and that nothing was saved; never report a no-op as an update. Evidence is revised by moving the status forward with a meaningful note, not by re-saving the same status.
- **New versus edit:** a new job entry always creates a separate record and can never overwrite the selected listing; editing the selected listing preserves its identity and asks for confirmation when an eligibility-relevant field changes, so a stale PASS is not silently reused.
- **Unrecognised stored status:** when the database holds an application status this build does not know (an older build, another tool, a hand edit), show the stored value as it is, offer no status change at all, and change nothing. The row is the person's own data: it is never repaired, reinterpreted, hidden, or carried forward on the app's initiative, and no transition is guessed at.
- **Terminal status:** a record in a final state (for example `withdrawn`) is told that no further change is permitted instead of being offered a chooser whose every option would be refused. The full chooser is not shown for such a record.
- **Record times versus source dates:** display the application's own observation times — when this device first wrote a listing, when it last saved it, and when an application record was last updated — labelled as local to this app. The database stores no source publication or update date, so none is shown, and an import or observation time is never presented as one. A missing time reads as "not recorded"; an unparseable or offset-less value is shown as stored with a plain label rather than being guessed at.
- **Start-up failure:** explain in plain language what failed and name the next step (usually restoring a verified backup from a terminal), with no candidate data, credentials, or filesystem locations in the message or in the one bounded local note kept for diagnosis. Every absolute location the text mentions is replaced, not only the locations the command named; prose the module cannot classify as a location is kept, because the note is local and that text is what makes it useful. The limit is stated rather than implied: this is path redaction, not content filtering. Version reporting comes from the source checkout (`python -m career_agent --version`) and from the installed console script, which share one literal; installers, signed bundles and bundling the interpreter are a documented gap, not a claim. `--doctor` answers "where is my data, and can this app read it?" without a display: it prints the version, the resolved database path *and the rule that chose it*, whether the data folder exists and is writable, and what the database contains — or the same refusal the app itself would show when the file is damaged, empty, or written for a newer schema. It creates nothing, changes nothing, and exits non-zero when it finds a problem, so it can be run from a launcher and read before the window is tried. A structural check alone cannot see a row this build cannot interpret, so on a current-schema file it also decodes every stored record with the same decoders the read paths use and names what it cannot read — a report that clears a file the app refuses is worse than no report. A file that records an older schema is reported by version and *not* decoded: the doctor never writes, so it cannot migrate the file, and decoding an old layout could report problems the upgrade itself resolves. The same rule reaches every command, not only the read-only reports: an unreadable record is refused in one sanitised sentence with exit status 2 and nothing half-printed - in fact nothing at all on standard output, because a command that refuses has no report to begin (measured on the built wheel on 2026-10-16, where twelve commands still printed their heading first) - never as an unexpected failure. Opening the window is the one request that is a start-up, so that is the only path where a database it cannot read is explained as one - a command that never started anything says it was refused instead. A command that writes checks before it does: an import sweeps the file read-only first, because writing part of a file and failing on the record halfway would leave a half-applied import behind a message saying nothing was written.
- **Content that grows, and a window that is too small for it:** the window declares the smallest size it will be shown at (900x600). The tab whose content grows with a career - **Work history & study** - scrolls, with its form pinned to the visible width so an over-long row wraps inside its own columns rather than drawing past the tab edge, and the tabs with the longest button rows (**Next action list**, **Follow-ups**) put those rows in two so no control is squeezed below the width of its own text. The acceptance harness measures every widget against the box it is drawn in: the tab, or the frame a scrolling area scrolls when the content is reachable by scrolling (content *wider* than that frame is still reported - a form that scrolls down does not scroll sideways). It measures at the size each window was asked for and at the size it actually has; when a platform returns a window smaller than this application's own declared minimum - on the macOS runners a 1400x900 request produced a 950x502 page - both sizes are printed and layout is not judged, because below that minimum the application promises no layout at all. That case is a platform limitation to report, not a defect to hide: the Linux display-backed job (a 1280x1024 virtual display) and the Windows legs (a 1024x768 screen, 1004x631 page) are judged.
- **HR contact CSV preview (offline, nothing stored):** a contact list a person already has is read where it lies, one file at a time, and reported on: rows, distinct email keys, keys shared by more than one row, and the lines to review. **No email address, name or company label is printed, logged or exported by this feature** - the report is counts, flag names and line numbers, so it can be pasted anywhere without copying anybody's details. The source file is opened read-only and left byte-identical; no database row, snapshot or temporary copy is made, which is what makes cancelling free. Only the email is normalised (trim and case-fold) and only for comparison; every original string is preserved for review, two columns that could be the same field are a refusal naming both rather than a guess, and company labels that disagree inside one email key are kept as they are and flagged. The flags are questions about text: a syntax flag does not mean a mailbox exists or is deliverable, and nothing here can see consent, an opt-out, current employment or whether the list may be used for outreach - the report says so in its own words. Import, a review screen, suppression records and matching are **not implemented**; the command states that rather than implying a workflow that is not there.
- **Event log:** the application keeps its own record beside the database so a later question ("when did it change?", "did the backup run?") has an answer: one line per event, an event name plus an identifier, a count or a category, never profile, document or evidence text, with local locations redacted and the file rotated at 256 KiB with one previous file kept. A log line that cannot be written is dropped rather than failing the action it describes, and the window does not show the log yet — `--doctor` prints its path and the most recent line.
- **Database/export failure:** show an actionable error and never claim that a save/export succeeded before the operation returns successfully. Confirm the previous data is unchanged when a write fails.
- **Backup/restore:** a backup is verified (integrity, schema version, required tables) and written owner-only before success is reported, and an existing file is never overwritten. A restore validates the chosen file, preserves the current database first, replaces the file in one step, and reopens and verifies the result before reporting success; a refusal names what to do next and leaves the current database untouched. Backups are local files and are not encrypted, which the interface states rather than implying otherwise.
- **Laptop asleep/off:** local UI and local scheduler cannot execute; a remote worker is a separate future capability with explicit data-transfer consent.
- **Remote worker/source unavailable:** future UI must distinguish disabled, permission-blocked, transient error, partial results, and a valid empty result.

---

## UX Direction Addendum — Resume-First Autonomous Career Agent (2026-10-16)

### Experience principle
The user-facing promise is: upload a resume, complete one guided setup, then let the agent handle permitted routine career tasks and keep the user informed. Autonomy must be observable and controllable, not a black box.

### First-run onboarding
1. Resume import with clear explanation of local processing and connected services.
2. Extracted-profile review grouped into contact, education, skills, projects, experience, links and preferences. Highlight uncertain or missing facts; never silently guess.
3. Target-role and job-preference setup, including AI/ML Engineer, Applied AI Engineer, AI Engineer, Forward Deployed Engineer and internships.
4. One-time automation policy: permitted sources, action types, location/work preferences, eligibility rules, daily limits, email identity, resume attachment rules, data-sharing scope and stop conditions.
5. Connection state for each source/mailbox, showing granted permissions and revocation method.
6. Readiness checklist distinguishing configured, connected, supported and enabled capabilities.

### Main dashboard
- **Today:** last/next discovery run, relevant jobs, completed/blocked applications, HR outreach, actual replies, interviews/deadlines and failures.
- **Discovery:** source, posting date, freshness, job URL, company, role, location, deadline, fit explanation, eligibility evidence and state.
- **Applications:** company, role, source, submission timestamp, external confirmation evidence, current status and next action.
- **HR outreach:** private contact-review queue, duplicate/conflict/suppression flags, campaign history, sent timestamp, delivery/bounce and reply state.
- **Activity timeline:** chronological events with decision reasons and evidence links.
- **Reports:** concise daily/weekly summary, progress, blockers and next steps.
- **Controls:** pause/resume automation, stop all external actions, edit policy, disconnect sources and revoke permissions.

### Status language and interaction rules
Use distinct states such as Discovered, Evaluated, Prepared, Blocked, Submitted, Submission unknown, Email sent, Bounced, Reply received, Interview, Rejected, Offer, Withdrawn and Follow-up due. A prepared draft is not a sent email; a click is not proof of submission; no reply is not a rejection. Display timestamps and evidence for external actions.

Do not repeatedly ask for routine approvals covered by the saved global policy. Ask a targeted question only when a required fact is missing, a legally meaningful attestation needs the user, data conflicts or a platform requires a human step. Explain the blocker and the next action.

### Failure and trust UX
- Show last successful run, partial failures, retries and next run.
- Distinguish source unavailable, expired login, rate-limited, no results, platform-blocked, missing user information and uncertain external outcome.
- Warn before enabling a new source or expanding data-sharing scope.
- Make pause/stop-all prominent; claim it has stopped work only after the action/scheduler layer confirms.
- Keep private contact details and message bodies out of public logs, test screens and analytics.
- Avoid fake progress indicators and claims of universal platform support.

### Accessibility and usability
Retain the existing desktop-first alpha's low-friction workflows. Provide readable labels, keyboard-operable controls, explicit focus/error states and filterable tables. Notification settings should support configurable cadence and quiet hours.
