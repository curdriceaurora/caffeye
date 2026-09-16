# Lessons

Patterns from user corrections. Review at session start.

## Data refresh → bump `checkedMonth` in the same commit
- **What happened (2026-06):** Added 3 shops, pushed, and the header still read "verified May 2026". User: "verified in may? didn't we just update it".
- **Rule:** Any commit that adds/removes/re-verifies shops in `public/shops.json` MUST also set `checkedMonth` to the current month. The freshness label is the user-visible proof the data was touched.

## Header count is runtime, but the HTML placeholder is not
- `index.html` line ~335 carried a hardcoded `"59 spots in Duluth · verified May 2026"` placeholder that JS overwrites on load; it went stale silently. Replaced with a neutral `Loading spots…` (2026-09) so it can't drift again. The visible count is computed from `SHOPS.length` after hydration — don't tell the user it's "hardcoded".

## Ratings: only the Places API is a source of truth
- **What happened (2026-09):** A subagent reported Google ratings for 21 shops (Sweet Hut 4.5 / 3,767). I "cross-checked" against joe.coffee (4,838) and RestaurantGuru (5,980), concluded the agent had fabricated numbers, and threw the refresh out. The Places API then returned 4.5 / 3,767 — the agent was right; the mirrors aggregate multiple locations and are the unreliable side. The stored "5,900+" had come from a mirror in the first place.
- **Rule:** Ratings/counts go into `shops.json` only from `scripts/refresh_ratings.py` (Places API (New), key in `~/.config/caffeye/google_maps_key`). Never from web-search snippets, mirrors, or hand-typed agent tables. "Counts never decrease" only holds when the stored value came from the same source — it is not evidence against an API result.
- **Matching:** prefer the candidate with the most name-token overlap, then nearest (`pick()`); nearest-first matched "La Abuela Made in Casa" (5,904 reviews) instead of "El Café by La Abuela" next door. Always run the candidate audit before `--write`.
- Status (open/closed): agents are fine when the evidence is a URL you can re-fetch (Apple Maps label, news article). The API's `businessStatus` is a free second signal — Shokku and Quynh both came back `CLOSED_TEMPORARILY`.

## Geocoding
- `mcp__Control_your_Mac__osascript` + `do shell script "swift ..."` fails silently for CLGeocoder scripts. Run `swift <file>.swift` via the Bash tool instead (script lives in the session scratchpad as `apple_geocode.swift`). Nominatim is an acceptable cross-check but Apple Maps is the reference geocoder for this project.
