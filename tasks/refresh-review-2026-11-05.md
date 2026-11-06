# November refresh review corrections

This follow-up supersedes the original `625551d` refresh totals. Nothing has been pushed or deployed.

## Corrected data

The combined map loads **2,234** venues after deduplication: **1,278 independents** and **956 franchises**. `places.json` has 2,219 regional records; the seed retains 60 active records. Relative to the original refresh, 97 regional records were removed: 70 unsupported empty listings and 27 explicit scope/duplicate exclusions (one additional empty listing was among the explicit exclusions).

The exclusion list records specific grocery aliases, Whole Foods-linked concessions, industrial baking/Herbalife/parking listings, and one confirmed Starbucks duplicate. The latter shares store-locator ID 8616 with the established adjacent record. Empty listings with no reviews, hours or website are also rejected by the generator so future crawls cannot silently reintroduce them. Exclusions can be reviewed and removed individually if evidence changes.

Nineteen thin 24-hour listings remain visible as businesses, but carry `hoursUnverified`. Their reported hours are displayed with a walk-in-hours caveat; they cannot qualify for Early risers, Open late or Until midnight until verified. These flags are maintained in the curation source, not edited into generated JSON.

Current utility counts, independent / total:

| Filter | Count |
|---|---:|
| Work-friendly | 48 / 63 |
| Meeting room | 18 / 22 |
| Early risers | 387 / 1,032 |
| Open late | 184 / 441 |
| Until midnight | 59 / 112 |

The generator now checks regional ratings against the previous published dataset. A missing rating or a review count falling below half the previous observation retains the old rating, count and observation month, with an explicit refresh issue. A subsequent valid response replaces that hold. Two direct Google Details rechecks still omitted the rating: Foxtail Midtown and Kellykakes. Their September ratings are retained and dated in the detail card. This does not claim a new rating observation. [Foxtail's own Midtown page](https://www.foxtailcoffee.com/locations/foxtail-coffee-midtown) independently lists this store and daily 6 a.m.–6 p.m. hours; those website hours were not substituted into Google's response.

The curated seed's manually selected website links were restored from the pre-refresh snapshot, including all seven nulled links. Operational refreshes must preserve a selected curated website when Google omits it or proposes another destination; a website replacement requires a separate link audit. Standard `refresh_ratings.py` updates rating fields only and leaves those links intact.

## Classification decisions

The existing three-location policy is retained, including Condesa, Little Tart and Giulia. Generic location/number stripping can no longer turn unrelated cafés into a chain named `coffee` or `cafe`. Explicit name rules cover Great American Cookies, Peach Cobbler Factory, Five Daughters, Möge Tee, Menchie's, Dancing Goats and Bellwood even with location suffixes. The classifier's output remains “franchise” for the product's unified chains/franchises category; it is not a claim about their ownership structure.

## UI corrections

Leaflet and its tile layer allow zoom 6, and the equivalent MapLibre minimum is 5. This allows the full regional spread to fit in short mobile maps while existing maximum bounds continue to restrict navigation. The filter chip containers no longer wrap inside their horizontal scroll rows on mobile, recovering the intended two-row filter bar and list density. The early-hours parser handles Google's elided-AM spans such as `5:30-9am`, while rejecting an ambiguous overnight span such as `11-2am`.

## Remaining evidence checks

[refresh-review-followups.csv](refresh-review-followups.csv) preserves 40 heuristic leads for manual follow-up. They were not treated as proof of invalid venues:

- Incomplete/city/street/plus-code addresses do not establish that Google's place pin is wrong. Coordinates were not approximated or moved.
- “Dunkin' Donits” is near a real Dunkin', but has a different street number and no matching official locator link. It remains flagged rather than being merged automatically.
- CPB NUTRITION has insufficient evidence to declare it an Herbalife club from its name alone.

Farmer's Table remains excluded by the existing grocery policy. Its editorial overlay remains in `curations.json` so the content is preserved if scope changes. Human Bean closure removals continue to rest on Google's business status; this pass does not claim independent confirmation.

## Reproducibility

Raw rechecks are in `scratch/rating-rechecks-2026-11-05.json` and are merged into the regional raw dump. This review used two additional successful Details calls. Source exclusions, unverified-hour annotations, rating guards and the generated priors are all tracked.

For replay, `python3 scripts/discover_places.py --replay scratch/places-2026-11-05.json --write` uses the current published dataset for rating holds and must reproduce `places.json` byte for byte. To rebuild independently from the September baseline, extract `public/places.json` from commit `4670422` into a scratch file and pass its path with `--previous`. Baseline observation dates are inherited from that file, not assigned from the current clock.

## Validation

- All **129 Python tests passed**.
- The complete isolated Playwright run (`npx playwright test --workers=2`) finished with **180 passed, 6 skipped, zero failures**, including both performance checks. The skips are the suite's viewport-specific conditions. Logs: `scratch/review-browser-isolated.log` and `scratch/review-unit-final.log`.
- The previously failing phone fit, vector regional fit, 320px card density and fallback density checks all passed. The 320×568 layout was also inspected visually after removing chip wrapping.
- Default replay reproduced `places.json` byte for byte, and all retained seed website selections matched the pre-refresh curated snapshot. Priors were regenerated and the shipped-priors consistency test passed.
- Performance limitation: startup blocking time at 4× CPU measured **584 ms** on this machine against the **300 ms non-gating target**. The test reports this metric but does not enforce that target; passing the suite does not establish that the performance target was met.

Earlier diagnostic runs were superseded: one ran while data and expected counts were still being updated; another was contaminated when a targeted Playwright run cleared the shared trace directory. A search-test race was also corrected by waiting for the requested result card. The isolated run above used stable application and dataset files with no competing Playwright invocation.
