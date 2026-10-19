# DOCX DTD/entity boundary hardening

Date: 2026-10-18 · Scope: local PDF/DOCX résumé import; no external action

## Finding

The existing DOCX reader intended to reject document type declarations before calling
`xml.etree.ElementTree`, but its guard searched only the first 4 KiB for the UTF-8 byte sequence
`<!DOCTYPE`. A synthetic DOCX with a legal, longer XML prolog bypassed that check. A UTF-16 document
also bypassed the byte search because its declaration was not represented as that ASCII byte sequence.
In both cases the standard-library parser expanded an internal entity and returned its text as résumé
content. No external network fetch was observed; the concrete risk was bypassed DTD rejection and
internal entity work before the résumé text budget was applied.

## Fix and invariant

`career_agent.resume.extract_docx` now runs an encoding-aware Expat preflight over the bounded
`word/document.xml` bytes. Its `StartDoctypeDeclHandler` refuses as soon as a DTD is encountered,
before the declaration's entity set can reach `ElementTree`. Malformed XML remains handled by the
existing non-echoing `ElementTree` refusal. This keeps the supported DOCX path unchanged while making
the documented boundary independent of declaration position and UTF-8/UTF-16 representation.

## Regression coverage

`tests/test_resume.py` now refuses synthetic documents with:

- a DTD after more than 4 KiB of XML comments, and
- a UTF-16 encoded DTD with an internal entity.

Both tests assert the bounded “document type declaration” refusal and that expanded entity text is not
returned or echoed. The existing early-DTD, malformed-XML, normal DOCX, macro, archive, and size tests
remain in place.

## Verification

- Baseline reproductions before the fix: both late UTF-8 and UTF-16 fixtures were accepted and returned
  `EXPANDED`.
- Focused DTD tests: `python3 -B -m unittest tests.test_resume.DocxExtractionTests.test_a_document_type_declaration_is_refused tests.test_resume.DocxExtractionTests.test_a_late_document_type_declaration_is_refused_before_entity_expansion tests.test_resume.DocxExtractionTests.test_a_utf16_document_type_declaration_is_refused_before_entity_expansion` — 3 tests, OK.
- DOCX extraction class: `python3 -B -m unittest tests.test_resume.DocxExtractionTests` — 13 tests, OK.
- Full résumé module: `python3 -B -m unittest tests.test_resume` — 86 tests, OK.
- Repository suite: `python3 -B -m unittest discover -s tests` — 2082 tests, OK (1 skipped).
- `compileall`, `tabnanny`, `git diff --check`, the 14-check desktop smoke test, and the 113-check real-window
  acceptance harness all passed locally. The harness is automated evidence only; it does not close the human
  desktop checklist.

This closes the identified DTD/entity parsing bypass. It does not make DOCX parsing a general malware
scanner; the documented size, archive, macro, and local-only boundaries still apply.
