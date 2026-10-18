# An address you never imported

**Date:** 2026-10-18
**Increment:** the do-not-contact list accepts an address that is not a stored contact.

## The gap

The do-not-contact list is the one record in this project that exists for somebody who is not the
user. It was reachable in exactly one way: mark a **stored contact row**. So the list could record
anybody who happened to be in a CSV the user imported, and could not record the person most likely to
have asked to stop - somebody who replied from an address that was never in the file, or who asked by
phone, or whose colleague passed the message on.

## What this adds

On the HR contacts tab, under the list: an address box, the same reason chooser the mark uses, and
**Add to the do-not-contact list...**.

- The address is checked the way every address in this application is checked, with one deliberate
  difference: surrounding whitespace is trimmed first, because this box *stops* messages rather than
  addressing one, and arguing with a pasted space would be the wrong kind of strict.
- One confirmation, which names the address, the reason, and what the reason means - permanent for
  "they asked not to be contacted", "nothing expires and no import can clear it" for the rest.
- An address already on the list is reported, not overwritten: the first reason recorded wins, because
  a suppression recorded because somebody asked to stop must not quietly become "our own decision".
- No contact row is invented. The list is about addresses.
- The recipient chooser on the Follow-ups tab re-reads the list immediately, so a newly listed address
  stops being offered without reopening the window.

## Evidence

- `tests/test_desktop_handlers.py::AddressNotInYourContactsTests` → **6 tests, OK**: the stored entry
  and its normalisation, the question's wording, five unusable addresses refused before the question,
  a repeat keeping its first reason and writing nothing, the list and the recipient chooser both
  updated, and no note invented for somebody who typed none.
- `tests/test_desktop_logic.py::SuppressionAddQuestionTests` → **3 tests, OK**.
- `python scripts/desktop_acceptance.py --stand-in-tk` → **147 checks, 0 failed** (new steps L21-L22).
- Full suite: **Ran 2640 tests, OK (skipped=13)**.
