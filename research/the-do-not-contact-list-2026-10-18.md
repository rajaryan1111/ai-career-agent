# A record kept for somebody who is not the user — 2026-10-18

Part of P8 item 7, and the part that can honestly be finished offline: suppression and opt-out
persistence. The rest of that item (secure mailbox authorisation, delivery-versus-reply evidence from
a real provider) cannot be verified without a mailbox and a provider, and is reported as unverified
rather than assumed.

## Why this is built before sending exists

This build sends nothing, so a do-not-contact list guards a locked door. That is the point: a
suppression list added *at the same time* as sending is a suppression list written by somebody who
wants the sending to work. Written first, it gets the rules that a person who asked to be left alone
would want.

## The rules, each of them a failure that cannot happen

| Rule | The failure it prevents |
| --- | --- |
| Stored in the database (schema 14, `contact_suppression`) | a no that is forgotten on restart |
| Matching on the normalised address | a no walked around by `HR@Example.com` |
| Case/whitespace folding only - no dot-stripping, no plus-tag removal | suppressing somebody who never asked, by guessing two addresses are one person |
| The first reason wins | "they asked us to stop" quietly becoming "our own decision" on a second write |
| Nothing expires | this application deciding, on its own clock, that a person's no has run out |
| Lifting needs a note (≥4 characters) and is never a side effect | an entry disappearing in an import, a retry or a cleanup, with nobody able to tell it from a mistake |
| An unreadable reason still blocks | a damaged row reading as permission |
| Checked inside `guarded_dispatch`, before any attempt row is written | a blocked message leaving a record that says something was attempted |
| The event log records `suppression.blocked` with a count | the address of somebody who asked to be left alone sitting in a log |

`SuppressionReason.ASKED_TO_STOP` is the only reason marked permanent: any entry blocks, but this is
the one this application may never lift for a reason of its own. A person can still lift it - it is
their database - with a note saying why.

## What of P8 item 7 is now verified, and what is not

Verified, with mocked providers only:

- **suppression/opt-out persistence** - 20 tests here;
- **duplicate prevention** - cross-source job identity plus the write-ahead attempt record, so one
  vacancy found on two boards cannot be written to twice;
- **bounded outreach** - a required daily limit per action counted from durable rows, and a per-job
  follow-up limit counted from the attempts for that job identity;
- **provider result versus delivery** - a dispatch that fails settles as *unknown*, never as failed
  or sent, and the report says what the employer received is not established.

Not verified, and not claimed:

- **secure mailbox authorisation** - there is no mailbox, no OAuth flow and no credential store; the
  only honest statement is the tested one, that nothing stores a credential anywhere;
- **delivery and reply evidence** - a reply or a bounce appears only where a person wrote it down,
  because nothing reads an inbox;
- **contact-to-opportunity linking** beyond the listing id a draft carries and the job identity an
  attempt is keyed by.

## Evidence

- `career_agent/suppression.py`, schema 14 in `career_agent/store.py`, the check in
  `integrations.guarded_dispatch`.
- `tests/test_suppression.py` — 20 tests.
- Suite: **2500 OK (skipped=13)**.
