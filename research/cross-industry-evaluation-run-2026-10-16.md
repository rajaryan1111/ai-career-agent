# Cross-industry evaluation run — 2026-10-16

**What this is.** The first reproducible run of the Phase 4 evaluation set: a privacy-safe, human-designed
corpus of seven occupation groups, and a harness that measures the matching engine and the résumé extractor
against the standard written down in it. It exists because Phase 4's job is to stop the product being
effectively an AI/ML-only tool, and "it seems fine" is not a measurement.

**What it is not.** This is not human acceptance, not a hiring-outcome study, and not evidence about real
documents. Every value is synthetic, the sample is seven résumés and twenty-one listings, and the text in
each résumé is clean and plainly labelled. The corpus measures agreement with a written standard; it says
nothing about scanned PDFs, two-column layouts, or how often a real person's document is shaped like these.

| Artifact | Purpose |
| --- | --- |
| [`cross-industry-evaluation-set-2026-10-16.json`](cross-industry-evaluation-set-2026-10-16.json) | The corpus: 7 occupation groups, 21 synthetic listings with a stated review order, 7 synthetic résumés with the values a reviewer says are stated plainly in them, 3 extraction rule checks, and the documented non-coverage rules. |
| [`scripts/evaluate_cross_industry.py`](../scripts/evaluate_cross_industry.py) | The harness. Reads the corpus, reports per group, exits non-zero if any hard-eligibility violation is measured. |
| [`tests/test_cross_industry_evaluation.py`](../tests/test_cross_industry_evaluation.py) | Keeps the corpus well-formed, synthetic and fully ranked, and keeps the measurement honest (see "what the tests protect" below). |

## 1. The run

```
$ python scripts/evaluate_cross_industry.py
Cross-industry evaluation of the matching engine and the résumé extractor
Corpus version 1 (2026-10-16); 7 occupation groups, 21 synthetic listings.
...
Measurements against the thresholds phases.md proposes:
  top-ranked agreement      : 7/7 (100%) against 80% proposed
  hard-eligibility violations: 0 (must be 0)
  critical-field extraction : 22/22 (100%) against 95% proposed
                              (8 further values are present in the text but outside what the extractor
                               claims, and are not counted here)
  documented rules holding  : 8/8; extraction rule checks 3/3
```

Exit status 0. Per group, the engine's order agreed with the reviewed order, and in every group the listing
the reviewer marked last (not the person's country, or far outside their experience band) was **blocked**
rather than offered. The three extraction rule checks pass in both directions: a labelled country or
location line yields the country, and a bare `City, Country` header line does not — that last one is a
deliberate conservative rule, and the check fails if it is ever widened silently.

## 2. What this run found

The corpus paid for itself on its first run: the extractor was measurably blind outside engineering,
science and commerce. Five defects, each fixed with a regression test that fails before the fix and passes
after, and each found by *running* the evaluation rather than reading the code.

| # | What was wrong | Measured symptom | Fix |
| --- | --- | --- | --- |
| **D21** | The section vocabulary did not know the headings of two fields the module itself proposes | `WORK AUTHORIZATION` (heading, value beneath) put *"Authorized to work in India"* into the **skills** proposal, marked confident; `COUNTRY` put the country itself there — a value that feeds eligibility, offered as a skill | `work_authorization` and `location` added to the section vocabulary, using the same wording the label patterns use |
| **D22** | The degree vocabulary was the engineering/science/commerce set and nothing else | `B.Des in Design, 2026` proposed **no degree and no graduation year** (the year rule needs a degree or institution on the line). Design, architecture, medicine, pharmacy, law, education and hospitality qualifications were all invisible | Vocabulary widened by discipline, with the abbreviations that are also English words (`bed`, `des`, `arch`, `pharm`) requiring their full stop, and a test that prose containing "bed" or "redesign" is still not read as a qualification |
| **D23** | An abbreviation's own full stop hid the discipline | `B.Sc. in Biotechnology, 2026` proposed *"B.Sc"* (level only, unselected) while the same line without the stop proposed *"Biotechnology"* confidently | The leftover stop is stripped from the remainder before the discipline is read |
| **D24** | Only `technical/key/core/…` before the word "skills" opened a skills section | `LABORATORY SKILLS` — the heading on the corpus's biotechnology résumé — was not a heading at all, so a document with a skills list was reported as having no skills heading | Discipline and domain prefixes (`laboratory`, `clinical`, `research`, `engineering`, `analytical`, `design`, `business`, `financial`, `data`, `mechanical`, …) recognised |
| **D25** | The skills token filter allowed `+#.()` inside a name but not `&` | The mechanical résumé's headline skill **`GD&T` was silently dropped** from the proposal; a finance résumé's `M&A` would have gone the same way | `&` allowed inside a token. A dropped skill is worse than a noisy one: the person reviews what is proposed and never sees what was discarded |

**A sixth, smaller gap in the same family:** `B.B.A.` was recognised while `B.A.` (and `M.A.`) were not —
the wrong way round for the two most common arts degrees. Also fixed, in the same test.

None of these is a scoring problem: each one is a value the document stated plainly that the product either
mis-filed or dropped. They were invisible to the existing suite because the existing fixtures are written in
the vocabulary the code already knew — which is exactly the failure mode Phase 4 was written to catch.

## 3. What the tests protect

`tests/test_cross_industry_evaluation.py` asserts that the corpus stays well-formed (every group states an
unambiguous review order), that every value in it is synthetic and unreachable (no real mailbox domain, only
example hosts, every employer named "(synthetic)"), that a malformed corpus is refused rather than measured,
that no listing the rules block is ever offered, that the engine clears the 80% agreement bar *on this
corpus* while reporting the number with its denominator, that the conservative country rule still holds in
both directions, and that the eight recorded non-coverage values stay **outside** the accuracy figure rather
than being counted into it.

## 4. What remains open (and why Phase 4 is still partial)

1. **The corpus is synthetic and small.** Seven résumés and twenty-one listings, all clean text. Real
   documents — scans, photo headers, two-column PDFs, unusual layouts — are not represented.
2. **The relevance standard is one reviewer's order**, written here and reviewable, not a hiring outcome and
   not a precision measurement against a larger judged set.
3. **No threshold is claimed as achieved for the product**, only measured for this corpus. `phases.md`
   keeps the proposed thresholds where they are; the run reports against them and does not rewrite them.
4. **Compensation is still not compared** — the domain model has no field for it, and the harness asserts
   that no assessment pretends otherwise.
5. **Coverage gaps by occupation are recorded, not closed:** every group here has three listings. Fields
   such as a driving licence, a professional registration or a portfolio link have no profile field to be
   compared in, and the corpus does not pretend to measure them.
