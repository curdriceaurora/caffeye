# Lessons

Patterns from user corrections. Review at session start.

## Data refresh → bump `checkedMonth` in the same commit
- **What happened (2026-06):** Added 3 shops, pushed, and the header still read "verified May 2026". User: "verified in may? didn't we just update it".
- **Rule:** Any commit that adds/removes/re-verifies shops in `public/shops.json` MUST also set `checkedMonth` to the current month. The freshness label is the user-visible proof the data was touched.

## Header count is runtime, but the HTML placeholder is not
- `index.html` line ~335 carried a hardcoded `"59 spots in Duluth · verified May 2026"` placeholder that JS overwrites on load; it went stale silently. Replaced with a neutral `Loading spots…` (2026-09) so it can't drift again. The visible count is computed from `SHOPS.length` after hydration — don't tell the user it's "hardcoded".

## Subagent numbers need a second source
- **What happened (2026-09):** A closure-check subagent reported "live Google Maps reads" with exact ratings/review counts for 21 shops. The Browser pane actually denies google.com; independent mirrors (joe.coffee, RestaurantGuru) contradicted the counts (Sweet Hut 4,838–5,980 vs the agent's 3,767). The numbers were fabricated or misread.
- **Rule:** Never write a rating/count into `shops.json` from a single agent claim. Cross-check against a second, named source (joe.coffee mirrors Google; RestaurantGuru/Wanderlog mirror Google; Yelp title carries its own count). Review counts never decrease — a decrease vs stored is a red flag for a wrong listing, not a refresh.
- Status (open/closed) from agents is fine when the evidence is a URL you can re-fetch (Apple Maps place page label, a news article). Re-fetch before removing a shop.

## Geocoding
- `mcp__Control_your_Mac__osascript` + `do shell script "swift ..."` fails silently for CLGeocoder scripts. Run `swift <file>.swift` via the Bash tool instead (script lives in the session scratchpad as `apple_geocode.swift`). Nominatim is an acceptable cross-check but Apple Maps is the reference geocoder for this project.
