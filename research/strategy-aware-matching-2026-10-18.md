# Strategy-aware matching (2026-10-18)

## What this increment is

P7's third increment: a role strategy now takes part in comparison. `matching.assess_for_strategy`
(profile, listing, strategy) evaluates the strategy's **hard statements as gates before any fit
ranking**, then adds its **preferences as three more explainable factors** beside the profile's own
six. `matching.rank_for_strategy` mirrors `rank` (best-first, stable order, blocked listings stay in
the set saying why but leave the default order). A small refactor extracted the recommendation ladder
into `_recommendation_for` so the two callers cannot disagree; the plain `assess` path is pinned
unchanged by test (same eligibility decision, six factors, no strategy factors).

## The rules

* **Gates before ranking, named.** An excluded employer or role title fails outright, matched as a
  phrase ("Blocked Employer" blocks "Blocked Employer Ltd"; "Sales Engineer" does not block
  "Aerospace Systems Engineer"). A skill the strategy marks required fails when the **profile** does
  not state it — the person declared it essential, and silence is not a pass. Every failed gate's
  explanation (which names the person's own statement and what the listing is) is carried into the
  assessment's notes, so a blocked listing is reviewable, not just rejected.
* **Preferences rank, never gate.** Locations and work mode compare against the listing's fields;
  preferred skills score the share of the strategy's preferred skills the listing asks for (a
  single-skill strategy has no partial — a fraction nobody stated is not invented). Listing silence
  is `unknown`, never a failure; a preference the strategy does not state is `not applicable` and
  carries **no weight at all** (its factor stays visible as an explanation), so a bare strategy
  changes neither the score nor the coverage it is read with.
* **Recorded but not compared:** compensation bounds and employment types — the listing domain model
  has no field for either. The honest limitation, documented in both modules, instead of a factor
  invented from free text.
* **Numbers are not probabilities:** the strategy factors inherit the module's existing rules —
  coverage reported beside the score, disclaimers, forbidden-claim scan unchanged.

## Defects caught by fail-first tests while building

* The gate explanations initially leaked the *normalized* (lower-cased) skill names; comparisons fold
  case, explanations must not rewrite the person's words. Fixed; named as the strategy spelled them.
* Blocking notes initially named only the requirement *category*; they now name the actual statement.
* NOT_APPLICABLE strategy factors initially penalized coverage or were hidden entirely; they now
  stay visible and weightless via a combined-weights helper (`_CombinedWeights`) that keeps the
  profile's `MatchWeights` contract untouched.

## Tests and evidence

`tests/test_strategy_matching.py` — 19 tests: gates (employer/title/phrase-boundary/required-skill/
silence-is-not-a-pass/bare-strategy), factors (location match/fail/unknown, not-applicable, work
mode, preferred-skills full/partial/none/single), blocking with named reasons, explainable ordering,
blocked-listing handling, plain-path equivalence, and run-stable order. Full local suite: **2170
tests OK (skipped=13)** (45 pre-existing matching tests green on the refactor). `compileall` and
`git diff --check` clean. Desktop checks remain BLOCKED by construction here (no display/tkinter).
No external action; `SOURCE_QUALITY_GATE_PASSED` stays `False`, `enabled_discovery_sources()` stays
`()`.

## Deliberately not in this increment

Any window or CLI showing strategy-aware rankings, per-strategy persisted weight tuning, artifact
invalidation UI, and any use of strategies inside discovery (which remains gate-closed). Next:
surfacing artifacts + lineage in the desktop, or artifact invalidation on fact/strategy change.
