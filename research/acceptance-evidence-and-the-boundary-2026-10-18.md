# What a route must prove first, and the boundary that is not crossed — 2026-10-18

Two roadmap lines that are mostly *refusals written down in advance*: P8 item 6 (source-specific
acceptance evidence, defined before anything is enabled) and the documentation half of P8 item 8
(the remote storage boundary and credential handling). Both exist because a gate that is closed "for
now" is opened by whoever is in a hurry, and the cheapest defence is to write the conditions while
nobody is.

## Requirements per route, as data

`career_agent/acceptance_evidence.py` names six routes - LinkedIn, Unstop, Internshala, Naukri.com,
an employer's own careers page, and an ATS/provider API - and nine baseline requirements that every
one of them must meet: a written permission basis, a dated terms and robots review with clauses
quoted, stated rate limits (holding to the smaller of theirs and ours), an honest client identity,
a no-circumvention statement, data minimisation, a test route, a person's own account of a complete
real run, and a tested withdrawal path. A route may add requirements and **cannot drop one** - the
constructor refuses a route whose `kinds` omit any baseline requirement.

Three of the labels carry the arguments this project has already had with itself:

- a permission basis is "never an inference from silence";
- human verification is "a person's own account of one complete run ... **not a passing test
  suite**";
- no-circumvention is a requirement to rule out, "checkable in the code", not a hope: no CAPTCHA
  solving, no OTP interception, no login-wall bypass, no rate-limit evasion.

`held_evidence(route)` returns `()` for every route, and a test asserts it: **nothing is held, every
route is outstanding on all nine**. It is a function rather than a constant so that the day one is
obtained there is exactly one place to record it. `--acceptance-evidence` prints the whole list and
touches no database.

The capability separation is in the data too: each route lists what it *could ever* serve, and the
summary states that discovery, submission, outbound email and inbox reading are independently
gated - evidence for one opens none of the others, and no evidence of any kind opens the
source-quality gate. A test re-asserts `enabled_discovery_sources() == ()` after all of this, because
writing down what evidence would be needed must never be mistaken for having it.

## The boundary, and the claim not made

The README gains "Syncing, credentials, and what is deliberately not claimed":

- **laptop-off operation is not available and not claimed**, with the release evidence such a claim
  would need spelled out: a deployed worker, a tested storage boundary, a recorded run while the
  laptop was shut, and a stated recovery behaviour for an interrupted run;
- **the sync hazard is described rather than hinted**: a SQLite file in Dropbox/iCloud/OneDrive that
  two machines open at once can be corrupted by the sync service, which copies bytes without knowing
  about transactions; `WorkerLease` is single-machine crash recovery, **not a distributed lock**;
  pointing a remote worker at the local file is refused by design;
- the supported ways to move data are named (`--backup`/`--restore`, `--export-json`/`--import-json`),
  each leaving one writer at a time;
- **no credential is stored anywhere**, and that is checkable rather than quotable.

`tests/test_operational_claims.py` pins all four, and the credential claim is checked against the
software rather than the prose: no column in the live schema has a credential-shaped name, no module
imports a credential store or calls `getpass`, and no credential-shaped literal assignment appears in
the package. The README assertions compare against a whitespace-normalised copy, so re-wrapping a
paragraph never fails the suite - a documentation test that punishes editing is a documentation test
people route around.

## Evidence

- `tests/test_acceptance_evidence.py` — 16 tests, including a subprocess run of the command.
- `tests/test_operational_claims.py` — 7 tests over the claims and the credential surface.
- Suite: **2480 OK (skipped=13)**.
- Not done, and not claimed: P8 item 7 (mailbox authorisation, outreach, delivery-versus-reply
  distinctions) stays unverified - there is no mailbox and no provider to verify against, and the
  mocked half of it that does exist is the local ledger plus the duplicate and attempt rules.
