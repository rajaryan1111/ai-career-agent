# JSON import/export number boundary — NaN, Infinity, overflow and booleans (2026-10-18)

## What was audited

The roadmap's reliability item on JSON import/export asked whether non-standard and non-finite numeric
values could cross the version-2 format boundary. Four real holes were reproduced against the code at
`359ccdb` before anything was changed:

1. **`json.loads` accepts `NaN`, `Infinity` and `-Infinity` literals by default.** A hand-edited export
   carrying `"experience_years": NaN` parsed cleanly; the value was dropped by `_number`'s coercion only
   by accident of `float("nan")` being returned and later comparisons misbehaving — the file itself was
   never refused, and a strict JSON reader cannot read what this app would happily consume.
2. **An overflowing literal crashed an import mid-write.** `float("1e400")` is `inf`, and
   `_year(inf)` raised `OverflowError` — an exception no handler caught — because `_year` only caught
   `TypeError` and `ValueError`. An import that dies between writes is exactly the partial-write failure
   the rest of the module is built to prevent.
3. **Booleans were read as numbers.** `float(True)` is `1.0` and `int(True)` is `1`, so
   `"experience_years": true` was stored as one year of experience and `"graduation_year": true` as the
   year 1.
4. **The export writer could emit non-standard JSON.** `json.dumps` defaults to `allow_nan=True`, so a
   database already holding a non-finite number (possible via hole 1–3, or via a damaged file) would be
   exported as a document this application's own importer — and any strict JSON reader — refuses. A
   backup that cannot be restored is not a backup.

## The fix

* `read_export` now parses with a `parse_constant` hook that raises `ImportRefused` naming the constant
  and the file. A document holding one is refused **whole**, before any field is read: it was not
  written by this application, and taking fields from a document whose numbers include one no
  eligibility check can use is not a trade this module makes.
* `_year` refuses booleans explicitly and catches `OverflowError`, so an overflowing literal is dropped
  from its field ("not stated") like any other unreadable value, instead of crashing the import.
* `_number` refuses booleans and anything `math.isfinite` rejects.
* `write_export` passes `allow_nan=False` and turns the resulting `ValueError` into a
  `PrivateWriteError` that says a stored value is not a finite number and that nothing was written —
  the honest outcome, where a poisoned file is not.

Field-level dropping (holes 2–3) versus whole-file refusal (hole 1) is a deliberate split: a literal
`NaN`/`Infinity` is not valid JSON at all, so the document is not an export; `1e400` and `true` *are*
valid JSON values that this format's fields cannot carry, and the coercion contract has always been
"unreadable value → not stated".

## Compatibility

Version-2 (and version-1) compatibility is unchanged for every document this application can write:
`validation.optional_float` already refused non-finite values on the way in, so no export ever held
one, and the round-trip fixed-point test still passes. The only documents newly refused are ones no
build of this application produced.

## Tests and evidence

`tests/test_importer.py::NonStandardNumberTests` — 8 new tests, each failing against the pre-fix
module (the `OverflowError` crash reproduced as an error, the other seven as assertion failures):
NaN refused with nothing read into a fresh database; `Infinity` and `-Infinity` refused; a constant
nested in a listing's fields refuses the whole file; `1e400` dropped from `experience_years` with the
rest of the profile intact; `true` dropped from profile and listing numeric fields; an overflowing
`graduation_year` dropped instead of crashing; and `write_export` refusing to write a stored `inf`
with no file left behind. The class shares the module's disposable-workspace base (extracted as
`ImportFixtureBase` so subclasses do not re-run each other's tests).

* Focused: `python -m unittest tests.test_importer` — 51 tests OK.
* Full local suite: `python -m unittest discover -s tests` — **2090 tests OK (skipped=13)**.
* `python -m compileall -q career_agent scripts tests` — clean. `git diff --check` — clean.
* No schema change; schema stays **8**. `EXPORT_FORMAT_VERSION` stays **2**. No external action, no
  source enablement; `SOURCE_QUALITY_GATE_PASSED` remains `False` and `enabled_discovery_sources()`
  remains `()`.

## Limitation

This is a format-boundary fix. A database damaged by an earlier build can still *hold* a non-finite
number in a stored payload; the export now refuses to write such a database (naming the problem) and
`core._is_real_number` keeps eligibility comparisons safe against it, but repairing the stored row is
not attempted here.
