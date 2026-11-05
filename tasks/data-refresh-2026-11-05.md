# Google Places refresh: November 5, 2026

The September listing snapshot was replaced with a complete Metro Atlanta crawl and direct checks for existing listings absent from search. Search absence alone was not treated as a closure: 54 qualifying regional records were recovered by ID. New IDs mean new to this dataset, not necessarily newly opened businesses.

| Measure | September | November |
|---|---:|---:|
| Curated seed records | 61 | 60 |
| Regional file records | 1,688 | 2,316 |
| Combined venues after browser deduplication | 1,705 | 2,331 |
| Independent venues | 970 | 1,386 |
| Franchise venues | 735 | 945 |

The regional file gained 656 place IDs and lost 28. Of 81 missing search results checked directly, Google reported 56 operational, 16 permanently closed, six temporarily closed, and three not found. Two operational records failed the existing category rules. One other previous record appeared in the crawl but now has grocery_store as its primary type. The existing discovery policy excludes temporarily closed places; the raw responses retain them for later rechecks.

For the 1,660 regional IDs retained between snapshots, 251 ratings, 1,336 review counts, and 109 hours strings changed. In the seed, six ratings, 58 review counts, and 49 hours strings changed. Shokku Bakery was removed from the seed following a matching by-ID response reporting permanent closure. Editorial descriptions and coworking assessments were preserved; their verification dates were not advanced.

Both dataset verification months are November 2026. Rating priors were regenerated from the combined deduplicated population. The loaded early-risers filter has 412 independent / 1,053 total matches; open-late has 212 / 463; until-midnight has 83 / 133.

## API usage and reproducibility

The November ledger began empty. This run recorded 658 IDs-only Text Search calls, 417 Enterprise Text Search calls, and 200 successful Enterprise Place Details calls (203 attempted, three IDs not found). No configured discovery limit was overridden. Ledger counts describe this local project, not other consumers of the Google Cloud project.

Raw responses, before snapshots, and detailed audits are retained in gitignored scratch files:

- `scratch/places-2026-11-05.json`, complete crawl plus missing-listing rechecks
- `scratch/seed-details-2026-11-05.json`, complete curated operational details
- `scratch/ratings-2026-11-05.json`, initial curated ratings audit
- `scratch/seed-refresh-audit-2026-11-05.json`
- `scratch/missing-recheck-audit-2026-11-05.json`
- `scratch/refresh-browser-summary-2026-11-05.json`
- `scratch/shops.json.before-2026-11-05` and `scratch/places.json.before-2026-11-05`

Regional replay uses `python3 scripts/discover_places.py --replay scratch/places-2026-11-05.json --write`. The curated details application is preserved in `scratch/apply-seed-refresh-2026-11-05.py`; review its input-size precondition before rerunning after a removal.

## Closure audit

Permanently closed regional listings: Panadería Chic’s bakery 2, Cafe Floralia X The Circuit, San Francisco Coffee Roasting Company: Gold & Bold, Makeda's Cookies - Sandy Springs, Meetfresh, The Human Bean, Pearl's Tea - Johns Creek, Augie's Cafe, The Human Bean, Gaucha Bakery - Cumming, Tier Couture Bakery, The Human Bean, The Human Bean, TE'AMO Boba & Dessert - Doraville, The Human Bean, The Human Bean.

Temporarily closed regional listings: Donut Worry #3, Commune Coffee, Black Bean Cafe, Revel Treats by Tora G., Lucky's A.M. Kitchen & Coffee, Dunkin'.

IDs not found: H2OkraWater, 2Bruhz Bakery & Eatery, Cafe Nirvana.

## Validation

All 124 Python tests and 11 focused desktop browser tests passed (filters, franchises, metadata and regional recovery). An additional live-page check verified five feature chips, early/late intersection on map and list, reset, franchise totals, removal of Shokku Bakery, and no JavaScript page errors. Data checks confirmed unique regional IDs, matching regenerated priors, November observation months, and unchanged editorial fields for retained seed venues.
