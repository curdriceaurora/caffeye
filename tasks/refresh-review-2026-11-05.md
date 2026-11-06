# November refresh review corrections

This follow-up supersedes the original `625551d` refresh totals, including the first corrected totals in `a90a9e4`. Nothing has been pushed or deployed.

## Corrected data

The combined map loads **2,233** venues after deduplication: **1,323 independents** and **910 franchises**. `places.json` has 2,218 regional records; the seed retains 60 active records. Relative to the original refresh, 98 regional records were removed: 70 unsupported empty listings and 28 explicit scope, duplicate or not-yet-open exclusions (one additional empty listing was among the explicit exclusions).

The exclusion list records specific grocery aliases, Whole Foods-linked concessions, industrial baking/Herbalife/parking listings, and one confirmed Starbucks duplicate. The latter shares store-locator ID 8616 with the established adjacent record. Empty listings with no reviews, hours or website are also rejected by the generator so future crawls cannot silently reintroduce them. Exclusions can be reviewed and removed individually if evidence changes.

Nineteen thin 24-hour listings remain visible as businesses, but carry `hoursUnverified`. Their reported hours are displayed with a walk-in-hours caveat; they cannot qualify for Early risers, Open late or Until midnight until verified. These flags are maintained in the curation source, not edited into generated JSON.

Current utility counts, independent / total:

| Filter | Count |
|---|---:|
| Work-friendly | 48 / 63 |
| Meeting room | 18 / 22 |
| Early risers | 407 / 1,032 |
| Open late | 190 / 441 |
| Until midnight | 58 / 112 |

The generator now checks regional ratings against the previous published dataset. A missing rating or a review count falling below half the previous observation retains the old rating, count and observation month, with an explicit refresh issue. A subsequent valid response replaces that hold. Two direct Google Details rechecks still omitted the rating: Foxtail Midtown and Kellykakes. Their September ratings are retained and dated in the detail card. This does not claim a new rating observation. [Foxtail's own Midtown page](https://www.foxtailcoffee.com/locations/foxtail-coffee-midtown) independently lists this store and daily 6 a.m.–6 p.m. hours; those website hours were not substituted into Google's response.

The curated seed's manually selected website links were restored from the pre-refresh snapshot, including all seven nulled links. Operational refreshes must preserve a selected curated website when Google omits it or proposes another destination; a website replacement requires a separate link audit. Standard `refresh_ratings.py` updates rating fields only and leaves those links intact.

## Classification decisions

Location count no longer decides classification, because it doesn't show who owns a business. The earlier three-location rule is withdrawn. `scripts/brand_registry.json` records verified brands and outranks every name rule.

- **Chains, hidden from the default view:** Foxtail Coffee (national, franchising), Yogli Mogli and Boarding Pass Coffee (regional, franchising), and Dancing Goats and its parent Kaldi's (regional, no franchise program verified).
- **Independent, multi-location:** Queen Tea, Spiller Park, Chattahoochee Coffee Company, Bellwood, Condesa and Little Tart.

Chain records carry `chainScope` and `franchiseProgram`. A verified chain without a verified franchise program shows a "Chain" badge rather than "Franchise". `franchiseProgram: null` means none was verified, not that none exists. Other `"franchise"` records keep the "Franchise" badge from the product's unified chains/franchises category; it is not a claim about their ownership structure.

Multi-state chains that only the count rule had caught now have named rules: Peach Cobbler Factory, Five Daughters, Möge Tee, Menchie's, Costa Coffee, Insomnia Cookies, Andy's Frozen Custard, TCBY, Toastique, The Salty Donut and Pelican's SnoBalls. These rest on general knowledge rather than the verified research.

Unverified brands with three or more published listings default to independent and are research leads. [brand-verification-queue.csv](brand-verification-queue.csv) lists all 29, and the generator prints the count on each run. Older name rules that treat local groups as franchises, such as Hansel & Gretel and White Windmill, were not reviewed in this pass.

Condesa's Decatur listing is excluded because that café is announced for January 2027, even though Google reports it as operational. Remove the exclusion once it opens. The registry's evidence text summarises the November 6 research; source URLs still need adding. That research lists Chattahoochee's third location as Smyrna, while Google lists The Eddy in Mableton. Bellwood's EAV location is absent because Google's primary type for it is restaurant.

## UI corrections

Leaflet's minimum zoom is 7, or 6 on maps under 165 px tall, which cannot hold the region at 7; the MapLibre minimum is 5. Maps under 200 px use 12 px fit padding, so a 165 px map opens at zoom 7. Below zoom 8 the cluster radius drops to 20 px, so phones open on several bubbles rather than one. At zoom 6 the bubbles overlap but all venues stay in view. The filter chip containers no longer wrap inside their horizontal scroll rows on mobile, recovering the intended two-row filter bar and list density. The early-hours parser handles Google's elided-AM spans such as `5:30-9am`, while rejecting an ambiguous overnight span such as `11-2am`.

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

- All **131 Python tests passed**.
- The complete isolated Playwright run (`npx playwright test --workers=2`) finished with **185 passed, 6 skipped, zero failures**, including both performance checks. The skips are the suite's viewport-specific conditions. Logs: `scratch/review-browser-isolated.log` and `scratch/review-unit-final.log`.
- The previously failing phone fit, vector regional fit, 320px card density and fallback density checks all passed. The 320×568 layout was also inspected visually after removing chip wrapping.
- Default replay reproduced `places.json` byte for byte, and all retained seed website selections matched the pre-refresh curated snapshot. Priors were regenerated and the shipped-priors consistency test passed.
- Performance limitation: startup blocking time at 4× CPU measured **649 ms** on this machine (403–649 ms across runs) against the **300 ms non-gating target**. The test reports this metric but does not enforce that target; passing the suite does not establish that the performance target was met.

Earlier diagnostic runs were superseded: one ran while data and expected counts were still being updated; another was contaminated when a targeted Playwright run cleared the shared trace directory. A search-test race was also corrected by waiting for the requested result card. The isolated run above used stable application and dataset files with no competing Playwright invocation.
