# Coffee in Duluth — Requirements

Functional and non-functional requirements for the current state of the page. Each requirement is numbered for traceability from the test suite. Principles referenced map to `PRODUCT.md`.

## R1. Data set

| ID | Requirement | Principle |
|---|---|---|
| R1.1 | The page shows **59** curated shops covering Duluth, Berkeley Lake, Johns Creek border, and adjacent commercial strips. | Curation > count |
| R1.2 | Every shop has: `name`, full street address, lat/lng, category, star rating *or* `null`, review-count string, numeric review count, hours, USP description, 3 "loved" items, signature drink/dish, Google Maps URL, Yelp URL. | — |
| R1.3 | Every shop has an inline `cw` object with `tier` ∈ {`excellent`, `good`, `limited`} and an optional reservable-meeting-room flag. | — |
| R1.4 | Every shop has a `website` field (URL string or `null`). | — |
| R1.5 | Shops with late hours (≥ 10 pm) carry an inline `late` object with `tier` ∈ {`10pm+`, `midnight`} and a `when` description. Shops closing earlier omit `late` entirely. | — |
| R1.6 | Coworking/late/website data is **per-shop**, not keyed by name — two locations of the same brand in different cities can have different coworking notes, hours, and URLs. | Data integrity |
| R1.7 | Every shop's `category` exists in `CATS`. | Data integrity |
| R1.8 | All 42 unique building addresses (`ADDR`) are geocoded via Apple Maps with a verified `subThoroughfare` (house-number) match. | Geocode authoritatively |
| R1.9 | The freshness label in the header reflects the live count and the month the data was last verified. | — |

## R2. Map

| ID | Requirement | Principle |
|---|---|---|
| R2.1 | The map uses Leaflet with CARTO light tiles and MarkerCluster. | — |
| R2.2 | On first paint, the map fits all 59 markers (`fitBounds` with 40 px padding). | Show what's available |
| R2.3 | Each marker is a 26 px circular pin in the category color with the category emoji centered inside (☕ Coffee, 🥐 Bakery & Cafe, 🧋 Tea/Boba, 🍰 Dessert Cafe, ✦ Specialty). | Playfulness is information |
| R2.4 | Late-night shops have a blue glow ring on their pin. | — |
| R2.5 | The selected shop's pin grows to 32 px with a brown selection ring. | — |
| R2.6 | Marker clusters use a dark brown bubble with white count text, customized via `iconCreateFunction` (class `coffee-cluster`). | — |
| R2.7 | Shops at the same building coords are fanned out in a ~20 m ring so pins don't fully overlap. | Labels must not lie |
| R2.8 | Tapping a pin selects the shop directly (no preview popup). | One tap to the answer |
| R2.9 | "Back to list" runs `fitBounds(clusterGroup.getBounds())` to reset the view to all markers. | — |

## R3. Pin labels

| ID | Requirement | Principle |
|---|---|---|
| R3.1 | Each individual (non-clustered) pin renders the shop name in a small white pill. | — |
| R3.2 | Labels appear only at map zoom ≥ 13. | — |
| R3.3 | Labels are positioned at one of 16 angles around the pin (every 22.5°). | — |
| R3.4 | The placer prefers cardinal angles first, then diagonals, then in-betweens. | — |
| R3.5 | The placer evaluates labels in descending order of Bayesian weighted rating; higher-quality shops claim space first. | The right default |
| R3.6 | A label position is rejected if it collides with: any other already-placed label, any visible pin (own pin excluded by geometry), or any cluster bubble. | Labels must not lie |
| R3.7 | If no angle works, the label is hidden via `visibility: hidden`; the pin itself remains visible. | — |
| R3.8 | Labels reflow on `zoomend`, `moveend`, cluster `animationend`, and after any filter changes the visible-marker set. | — |

## R4. Filter bar

| ID | Requirement | Principle |
|---|---|---|
| R4.1 | Five category chips (Coffee, Bakery & Cafe, Tea/Boba, Dessert Cafe, Specialty) with category-color tinted backgrounds, the category emoji, and a count. | Playfulness is information |
| R4.2 | An "All" chip toggles all category filters off; active state is solid black. | — |
| R4.3 | Four feature chips: 💻 Work-friendly, 🤝 Meeting room, 🌙 Open late, 🦉 Until midnight — each with a themed background and live count. | — |
| R4.4 | Category and feature chips are toggleable independently; multiple can be active. | — |
| R4.5 | "Until midnight" is the wording (not "Past midnight") — accurate for shops closing *at* 12 am. | Truth in labeling |
| R4.6 | Sort controls are intentionally absent. The list is always ordered by Bayesian weighted rating, descending. | The right default |

## R5. Right-side list

| ID | Requirement | Principle |
|---|---|---|
| R5.1 | Displays the subset of shops that pass all active chip filters AND lie inside the current map viewport AND match the search query. | Show what's available |
| R5.2 | Sort is fixed: descending Bayesian weighted rating `WR = (v/(v+m))·R + (m/(v+m))·C`, where `C` is the mean rating across rated shops and `m` is the median review count, computed at page load. | The right default |
| R5.3 | Shops with no rating use `C` (the global mean) as `R` in the formula. | — |
| R5.4 | Each list item shows: a small (22 px) category-color circular emoji tile, the shop name, a meta row (category · ★ rating (count) · neighborhood), and up to three compact tags. | Playfulness is information |
| R5.5 | Each list item has a left border in the category color. | — |
| R5.6 | The results header shows the live filtered count. When the viewport is the active constraint (list count < global-filter count), the label reads **"X in view"**; otherwise **"X spots"**. | Show what's available |
| R5.7 | The shop list scrolls vertically inside its panel; the rest of the layout does not scroll. | Density on phones |
| R5.8 | Empty state copy hints at zooming out or clearing filters. | — |
| R5.9 | On every list refresh, items animate in with a staggered fade + translateY (28 ms per item, max 140 ms total delay). When triggered by a viewport change, the results-meta bar briefly flashes `--accent-soft` to signal "the map caused this". | Show what's available |

## R6. Detail card

| ID | Requirement | Principle |
|---|---|---|
| R6.1 | Shown when a shop is selected, replacing the list view via a compositor-only crossfade (list slides left + fades; detail slides in from right + fades). No layout shift. | One tap to the answer |
| R6.2 | Top section: category + neighborhood, shop name (heading), star rating with review count, USP description. | — |
| R6.3 | "Best for" pills auto-derived from CWS / LATE data: 💻 Work, 🤝 Meetings, 🌙 Open late, 🦉 Until midnight. | — |
| R6.4 | "Known for" pills (the loved-items list) plus a "Try the **{signature}**" line. | — |
| R6.5 | Location & hours section with the full street address and weekly hours. | — |
| R6.6 | Coworking section: tier label ("Coworking-ready" / "Workable" / "Quick-grab") + descriptive note + meeting-room callout if reservable. | — |
| R6.7 | Late-night section if applicable, with "Open until midnight" or "Open till 10pm+" header. | — |
| R6.8 | Action row: Google Maps button, Yelp button, and (if a website exists) a Website button labeled by host (Instagram / Facebook / Linktree / Website). | — |
| R6.9 | "← Back to list" button at the top hides the detail and resets the map. | — |

## R7. Search

| ID | Requirement | Principle |
|---|---|---|
| R7.1 | Free-text input above the list. | — |
| R7.2 | Search matches against: name, USP, signature, category, neighborhood, coworking note, late-night `when`, and each loved item. | — |
| R7.3 | Search is case-insensitive and substring. | — |

## R8. Responsive layout

| ID | Requirement | Principle |
|---|---|---|
| R8.1 | Desktop (≥ 821 px wide): map on left flex-grow, 380 px panel on right. | — |
| R8.2 | Mobile (≤ 820 px): single column. Map height fixed at 220 px (min 180), panel takes remaining vertical space. | Density on phones |
| R8.3 | On mobile, filter chips compress (padding 2 × 7 px, 11.5 px font); freshness/brand shrink. | — |
| R8.4 | On mobile, the footer disclaimer is hidden. | — |
| R8.5 | On mobile at iPhone 14 Pro viewport (~750 px usable), at least 5 list cards are visible above the fold. | Density on phones |

## R9. Performance & errors

| ID | Requirement | Principle |
|---|---|---|
| R9.1 | The page is a single HTML file ≤ 100 KB. | Operating constraint |
| R9.2 | No JS errors on initial load, on filter changes, on selection, or on zoom. | — |
| R9.3 | All Leaflet, MarkerCluster, and Google Fonts assets load via CDN with SRI hashes where applicable. | — |
| R9.4 | Renders correctly with no build step — open the `.html` file directly in a browser and it works. | Operating constraint |
| R9.5 | All transitions and animations use compositor-only properties (`opacity`, `transform`). `will-change: transform` on `.pin` and `.pin-label`; `will-change: opacity, transform` on `.list-view` and `.detail-view`. `.panel` carries `contain: layout style` to scope reflow. Target 60 fps with no Layout or Paint during list↔detail transitions. | — |

## R10. Deployment

| ID | Requirement | Principle |
|---|---|---|
| R10.1 | Live at `https://duluth-coffee-shoppes.sra-e69.workers.dev`. | — |
| R10.2 | Deployment is `wrangler deploy` from `/tmp/cof-clean` with `wrangler.jsonc` pointing assets at `./public/` (clean folder containing only `index.html`). | Operating constraint |
| R10.3 | No internal wrangler files (e.g. `.wrangler/cache/wrangler-account.json`) are ever uploaded as assets. | Security |
