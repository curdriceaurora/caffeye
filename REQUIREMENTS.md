# Caffeye — Metro Atlanta — Requirements

Functional and non-functional requirements for the current state of the page. Each requirement is numbered for traceability from the test suite. Principles referenced map to `PRODUCT.md`.

## R1. Data set

| ID | Requirement | Principle |
|---|---|---|
| R1.1 | The September 2026 snapshot loads **1,705** venues across 14 Metro Atlanta counties: 61 curated seed venues plus 1,644 admitted regional venues after deduplicating the 1,688-record `places.json`. Default discovery shows 970 independents; enabling franchises shows all 1,705. Runtime totals derive from accepted records, not a hardcoded target. | Curation > count |
| R1.2 | Every shop has identity, address, coordinates, category, rating (or `null`), review counts, and a Google Maps link. Curated seed records additionally have hours, USP description, 3 "loved" items, and a signature drink/dish. Regional editorial fields may be empty until verified overlays supply them; do not fabricate recommendations to fill gaps. | — |
| R1.3 | Coworking data is an optional inline `cw` object with `tier` ∈ {`excellent`, `good`, `limited`} and an optional reservable-meeting-room flag. All curated seed venues have it; regional records without verified editorial data show unknown work suitability. | — |
| R1.4 | Every shop has a `website` field (URL string or `null`). | — |
| R1.5 | Shops with late hours (≥ 10 pm) carry an inline `late` object with `tier` ∈ {`10pm+`, `midnight`} and a `when` description. Shops closing earlier omit `late` entirely. | — |
| R1.6 | Coworking/late/website data is **per-shop**, not keyed by name — two locations of the same brand in different cities can have different coworking notes, hours, and URLs. | Data integrity |
| R1.7 | Every shop's `category` exists in `CATS`. | Data integrity |
| R1.8 | Curated building addresses (`shops.json.addr`) use Apple Maps geocoding with a verified house-number match; discovered venues use Google Places coordinates. Runtime `ADDR` includes both sources. | Geocode authoritatively |
| R1.9 | First paint uses a neutral Caffeye brand and loading text, with no asserted count. After load or retry, title, region, and metadata derive from the accepted datasets. Header count follows franchise inclusion; page/social descriptions use the total loaded count. Freshness attributes differing or partially known verification months to their sources; an unknown source date contributes no claim. Static crawler/manifest copy describes Metro Atlanta without embedding counts. | — |

## R2. Map

| ID | Requirement | Principle |
|---|---|---|
| R2.1 | The map uses Leaflet with CARTO light tiles and MarkerCluster. | — |
| R2.2 | On first paint, the map fits all in-scope markers (`fitBounds` with 40 px padding). | Show what's available |
| R2.3 | Each marker is a 26 px circular pin in the category color with the category emoji centered inside (☕ Coffee, 🫘 Roasters, 🥐 Bakery & Cafe, 🧋 Tea/Boba, 🍰 Dessert Cafe, ✦ Specialty). | Playfulness is information |
| R2.4 | Late-night shops have a blue glow ring on their pin. | — |
| R2.5 | The selected shop's pin grows to 32 px with a brown selection ring. | — |
| R2.6 | Marker clusters use a dark brown bubble with white count text, customized via `iconCreateFunction` (class `coffee-cluster`). | — |
| R2.7 | Shops at the same building coords are fanned out in a ~20 m ring so pins don't fully overlap. | Labels must not lie |
| R2.8 | Tapping a pin selects the shop directly (no preview popup). | One tap to the answer |
| R2.9 | "Back to list" runs `fitBounds(clusterGroup.getBounds())` to reset the view to all markers. | — |
| R2.10 | The map zoom is bounded between `minZoom: 7` and `maxZoom: 19`. Viewport panning and tile network requests are strictly bounded to Greater Atlanta via `ATL_BOUNDS` (`[33.15, -85.05]` to `[34.75, -83.30]`) with `maxBoundsViscosity: 1.0`, preventing users from panning away from the coverage area and eliminating unnecessary tile rendering/requests. | Bound performance and avoid stray navigation |

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
| R3.9 | Above 300 simultaneously-visible (non-clustered) pins, the collision pass is skipped and all their labels are hidden, rather than running the O(pins × angles × obstacles) placer against a pin count that large. | Bound label-placement cost at multi-county scale without blocking the main thread |

## R4. Filter bar

| ID | Requirement | Principle |
|---|---|---|
| R4.1 | Six category chips (Coffee, Roasters, Bakery & Cafe, Tea/Boba, Dessert Cafe, Specialty) with category-color tinted backgrounds, the category emoji, and a count. | Playfulness is information |
| R4.2 | An "All" chip toggles all category filters off; active state is solid black. | — |
| R4.3 | Four feature chips: 💻 Work-friendly, 🤝 Meeting room, 🌙 Open late, 🦉 Until midnight — each with a themed background and live count. | — |
| R4.4 | Category and feature chips are toggleable independently; multiple can be active. | — |
| R4.5 | "Until midnight" is the wording (not "Past midnight") — accurate for shops closing *at* 12 am. | Truth in labeling |
| R4.6 | Sort controls are intentionally absent. The list is always ordered by Bayesian weighted rating, descending. | The right default |
| R4.7 | The filter bar presents two streamlined rows: Type (All + 6 categories) and Useful for (4 utility features). County/city filter rows are omitted to preserve vertical space and guarantee at least 5 visible cards on mobile viewports. | Density on phones; clean defaults |
| R4.8 | Dedicated top-right header toggle switch (`#franchiseToggle`) controls franchise and chain inclusion, defaulting to Indie-only discovery on boot (`state.includeFranchises = false`). "Useful for" section contains only utility feature chips (Work-friendly, Meeting room, Open late, Until midnight). | Clean defaults; truth in labeling |
| R4.9 | Regional scope covers Metro Atlanta across 14 counties (Gwinnett, Fulton, Forsyth, DeKalb, Cobb, Cherokee, Hall, Dawson, Clayton, Henry, Fayette, Coweta, Douglas, Rockdale), encompassing North Georgia foothills, central/ITP Atlanta (Downtown, Midtown, West Midtown, Old Fourth Ward, Inman Park, Decatur), and South Metro (Clayton, Henry, Fayette, Coweta, Douglas, Rockdale). | Curated regional discovery |
| R4.10 | Dedicated top-right header dark mode toggle (`#themeToggle`) switches between light and dark themes, defaulting to browser/system color scheme (`prefers-color-scheme: dark`) with zero-FOUC inline detection. Manual toggles persist to `localStorage` (`caffeye-theme`). Dark mode themes the UI using official Caffeye brand tokens (`--caffeye-ink` `#222721` & forest background, `--caffeye-paper` `#F4F3ED` text at 13.5:1 contrast, `--caffeye-gold` `#DCAF59` accents) and switches Leaflet basemap tiles to CARTO `dark_all`. | Playfulness is information; Clean defaults |

## R5. Right-side list

| ID | Requirement | Principle |
|---|---|---|
| R5.1 | Displays the subset of shops that pass all active chip filters AND lie inside the current map viewport AND match the search query. | Show what's available |
| R5.2 | Sort is fixed: descending Bayesian weighted rating `WR = (v/(v+m))·R + (m/(v+m))·C`, where `C` is the mean rating across rated shops and `m` is the median review count, computed at page load. | The right default |
| R5.3 | Shops with no rating use `C` (the global mean) as `R` in the formula. | — |
| R5.4 | Each list item shows: a small (22 px) category-color circular emoji tile, the shop name, a meta row (category · ◆ score · neighborhood), and up to three compact tags. The ◆ score is the Bayesian weighted rating from R5.2 rounded to 1 decimal — the number the list is ordered by — never Google's raw star. The results bar carries the legend `◆ = weighted score` at every breakpoint (tooltips don't fire on touch). Unrated shops show "no rating". | Playfulness is information; Labels must never lie |
| R5.5 | Each list item communicates category through a colored emoji icon tile. | — |
| R5.6 | The results header shows the live filtered count. When the viewport is the active constraint (list count < global-filter count), the label reads **"X in view"**; otherwise **"X spots"**. | Show what's available |
| R5.7 | The shop list scrolls vertically inside its panel; the rest of the layout does not scroll. | Density on phones |
| R5.8 | Empty state copy hints at zooming out or clearing filters. | — |
| R5.9 | On every list refresh, items animate in with a staggered fade + translateY (28 ms per item, max 140 ms total delay). When triggered by a viewport change, the results-meta bar briefly flashes `--accent-soft` to signal "the map caused this". | Show what's available |
| R5.10 | When the current filter set (chips + search + viewport) matches more than 200 shops, only the first 200 render by default; a "Load N more" row grows the visible window by 200 on click, and clicking through to the end does render the full matched set (this bounds the *default* render, not an absolute maximum — see CLAUDE.md). Any new filter or search change resets the window back to 200, while returning from detail card view preserves the user's pagination window and browsing position. Loading more must not lose keyboard focus: activating "Load more" moves focus to the first newly-revealed item. Below 200 matches, behavior is unchanged (all render at once) — this is the case for every single-region dataset today. | Bounds the common-case render cost at multi-county scale without changing today's behavior, and without breaking keyboard navigation |
| R5.11 | When a search matches shops outside the current map viewport, the list offers a "Show matches outside this view" action (full-width button in the empty state; compact pill when some matches are already visible) that fits the map to all matching shops. | Show what's available |

## R6. Detail card

| ID | Requirement | Principle |
|---|---|---|
| R6.1 | Shown when a shop is selected, replacing the list view via a compositor-only crossfade (list slides left + fades; detail slides in from right + fades). No layout shift. | One tap to the answer |
| R6.2 | Top section: category + neighborhood, shop name (heading), the ◆ score (large, labelled "score") with Google's raw ★ rating and review count in muted text directly beneath it, USP description. This is the only place Google's raw rating is shown. | Labels must never lie |
| R6.3 | "Best for" pills auto-derived from per-venue `cw` / `late` data: 💻 Work, 🤝 Meetings, 🌙 Open late, 🦉 Until midnight. | — |
| R6.4 | “Known for” pills when loved items exist, plus a “Try the **{signature}**” line when a signature exists. | — |
| R6.5 | Location & hours section with the full street address and weekly hours. | — |
| R6.6 | Coworking section: tier label ("Coworking-ready" / "Workable" / "Quick-grab") + descriptive note + meeting-room callout if reservable. | — |
| R6.7 | Late-night section if applicable, with "Open until midnight" or "Open till 10pm+" header. | — |
| R6.8 | Action row: Google Maps button, Yelp button when supplied, and (if a website exists) a Website button labeled by host (Instagram / Facebook / Linktree / Website). URLs are sanitized: only `http:`/`https:` links render a button; anything else renders nothing. | — |
| R6.9 | "← Back to list" button at the top hides the detail and resets the map. | — |
| R6.10 | Action URLs are trimmed and scheme-validated (`sanitizeActionUrl`); `javascript:`, `data:`, relative, and malformed URLs never produce a clickable link. | Data integrity |
| R6.11 | Coworking sections on curated venues carry provenance (verification date + source). Venues without verified amenities show an explicit "Unknown · amenities not yet verified" state instead of omitting the section. | Labels must never lie |

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
| R8.2 | Mobile (≤ 820 px): single column. Map height is `clamp(130px, 22vh, 185px)` (125 px on short screens), panel takes remaining vertical space. | Density on phones |
| R8.3 | On mobile, filter chips compress (padding 2 × 7 px, 11.5 px font); brand shrinks and freshness is hidden. At ≤ 380 px, the heading shows the region without the “Coffee in” prefix, stays on one line, and retains the full accessible home label and page title. | — |
| R8.4 | On mobile, the footer disclaimer is hidden. | — |
| R8.5 | On mobile, at least 5 list cards are fully visible above the fold at 375×750, and at least 3 at 320×568. Interactive targets keep a ≥ 44 px touch height. | Density on phones |

## R9. Performance & errors

| ID | Requirement | Principle |
|---|---|---|
| R9.1 | The page is a single HTML file ≤ 100 KB. | Operating constraint |
| R9.2 | No JS errors on initial load, on filter changes, on selection, or on zoom. | — |
| R9.3 | All Leaflet, MarkerCluster, and Google Fonts assets load via CDN with SRI hashes where applicable. | — |
| R9.4 | Renders with no build step when served over HTTP; JSON fetches require a local server or the deployed site. | Operating constraint |
| R9.5 | All transitions and animations use compositor-only properties (`opacity`, `transform`). `will-change: transform` on `.pin` and `.pin-label`; `will-change: opacity, transform` on `.list-view` and `.detail-view`. `.panel` carries `contain: layout style` to scope reflow. Target 60 fps with no Layout or Paint during list↔detail transitions. | — |
| R9.6 | If the regional dataset (`places.json`) fails to load or times out, the page boots the curated baseline and shows a degraded-coverage banner with the live baseline count and an in-place retry action — never a silent fallback. | Show what's available |

## R10. Deployment

| ID | Requirement | Principle |
|---|---|---|
| R10.1 | Live at `https://duluth-coffee-shoppes.sra-e69.workers.dev`. | — |
| R10.2 | Deployment is `wrangler deploy` from `/tmp/cof-clean` with `wrangler.jsonc` pointing assets at `./public/` (clean folder containing only `index.html`). | Operating constraint |
| R10.3 | No internal wrangler files (e.g. `.wrangler/cache/wrangler-account.json`) are ever uploaded as assets. | Security |
