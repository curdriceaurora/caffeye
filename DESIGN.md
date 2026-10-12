# DESIGN.md — caffeye

Design system spec for AI agents generating UI for the **caffeye** project. Everything here is sourced from `public/index.html`, `public/shops.json`, `README.md`, and `PRODUCT.md`. If a value isn't here, it isn't part of the system.

## What this product is

**caffeye** — *"A one-page, single-tap map of coffee shops, bakeries, and tea houses across Metro Atlanta — built so a local can decide where to go in under thirty seconds."* (`README.md`)

The page is the product. There is one screen, one HTML file, fetched once. Everything else is filter and detail. The map is the spine. The list mirrors the map's current viewport. The detail card replaces the list when a shop is selected.

## Voice & copy

Pulled verbatim from the running app — these are the only label strings that exist.

| Surface | Copy |
|---|---|
| Page title | `Coffee in {scope}`; `scope` is always `Metro Atlanta`, including seed fallback |
| Brand wordmark | Same as page title |
| Freshness line | `{count} spots in {scope} · verified {month}` (prefixed `Loading Metro Atlanta… ` while regional data is pending) |
| Search placeholder | `Search by name, drink, or area…` |
| Results header | `{n} SPOTS` (uppercase, letter-spaced) |
| Empty state | `No shops in this view. Try zooming out, clearing filters, or changing search.` |
| Footer | `Ratings, hours, and addresses change. Verify before visiting.` (hidden on mobile) |
| Back action | `← Back to list` |
| Detail action row | `Google Maps` · `Yelp` · `{host}` (host = `Instagram`/`Facebook`/`Linktree`/`Website`) |
| Filter row labels | `Type` · `Useful for` (hidden on mobile) |
| Coverage status | `Loading Metro Atlanta… {n} spots so far` · `Regional coverage unavailable · {n} spots` + Retry · `Retry failed · {n} spots` · `Regional coverage loaded · {n} spots` · `{n} more spots loaded` + Update list |
| Vector preview note | `Vector map preview · Standard map` · `Vector preview unavailable. Showing the standard map · Standard map` · `Some map detail could not load. Shop search and the list are still available.` |
| Coworking tier copy | `Coworking-ready` (excellent) · `Workable` (good) · `Quick-grab` (limited) |
| Late-night header | `Open until midnight` (midnight tier) · `Open till 10pm+` (10pm+ tier) |

**Tone is matter-of-fact.** No exclamation points. No "discover" / "explore" / "amazing." A shop has a `usp` (one sentence describing what makes it specific), `loved` (three plain noun phrases), and a `signature` (the dish/drink to try). Copy never tells the user how to feel; it tells them what's there.

## Visual identity

### Color tokens

CSS variables on `:root` in `public/index.html`:

| Token | Value | Used for |
|---|---|---|
| `--bg` | `oklch(97% 0.008 75)` | App background (cream) |
| `--surface` | `oklch(99.5% 0.006 75)` | Cards, header, panel |
| `--surface-alt` | `oklch(98% 0.007 75)` | Hover surfaces |
| `--text` | `oklch(17% 0.005 70)` | Body text |
| `--muted` | `oklch(50% 0.005 70)` | Secondary text, captions, counts |
| `--border` | `oklch(89% 0.012 78)` | Subtle dividers |
| `--border-strong` | `oklch(80% 0.016 78)` | Action button borders |
| `--accent` | `oklch(43% 0.10 52)` | UI accent (warm coffee brown) |
| `--accent-soft` | `oklch(91% 0.025 70)` | Selected list item background, callouts |
| `--venue-dl` | `-0.12` (dark: `0.22`) | OKLCH lightness shift applied to the category-color selection bar |

### Brand and theme roles

The Bean Eye identity uses forest `#293F34`, gold `#DCAF59`, paper `#F4F3ED`, ink `#222721`, and muted `#60645F`. These brand tokens coexist with the UI surface tokens above. Gold is not small text on a light surface. Preserve existing logo artwork and category colors.

Dark mode uses background `#181e19`, surface `#212822`, alternate surface `#28322a`, text `#F4F3ED`, muted `#9da29b`, border `#2e3930`, strong border `#3f4e42`, gold accent at 12 % for `--accent-soft`, and `--venue-dl: 0.22`. The selected-row tint is capped at 12 % because muted meta text on top of it falls under 4.5:1 above that. Explicit light/dark and system preference must remain consistent.

### Category colors (the playful layer)

From `CATS` in `public/index.html`. Each category has both a color and an emoji glyph; they are paired, never split.

| Category | Hex | Emoji | CSS token |
|---|---|---|---|
| Coffee | `#6f4e37` | ☕ | `--c-coffee` |
| Roasters | `#a65332` | 🫘 | — |
| Bakery+Cafe | `#b89464` | 🥐 | `--c-bakery` |
| Tea/Boba | `#5b8a72` | 🧋 | `--c-tea` |
| Dessert Cafe | `#c66980` | 🍰 | `--c-dessert` |
| Specialty | `#7b6cb8` | ✦ | `--c-specialty` |

Category hexes are pin colors, chosen to read against the map. Drawn as a thin bar on a panel surface they need a lightness correction, or the darker categories vanish in dark mode and the paler ones in light mode. Selection bars therefore render as `oklch(from var(--venue-color) calc(l + var(--venue-dl)) c h)` — hue and chroma intact, lightness shifted down 0.12 in light mode and up 0.22 in dark. Every category then clears the 3:1 WCAG non-text minimum on both the selected-row and detail-header surfaces (lowest: Bakery+Cafe 3.47 light, Coffee 3.68 dark). The lifted values sit inside `@supports (color: oklch(from red l c h))`, with the raw hex in the base rule. The guard is required, not tidiness: a later declaration containing `var()` that fails to parse after substitution is invalid at computed-value time, so it takes the property's *initial* value — `box-shadow: none`, `border-top-color: currentColor` — rather than the declaration above it.

### Feature theme colors

Used on feature chips and "Best for" pills:

| Feature | Icon | Theme hex | Token |
|---|---|---|---|
| Work-friendly | 💻 | `#2e7d4f` | `--c-work` |
| Meeting room | 🤝 | `#7a5635` | (reuses `--accent`) |
| Open late | 🌙 | `#3f4f8a` | `--c-late` |
| Until midnight | 🦉 | `#2a2f5c` | (darker variant) |

### Typography

- **Wordmark / brand:** Fraunces 800, 22 px (`.brand`). Letter-spacing `-0.015em`. Used only for the top-left logotype.
- **Body & UI:** Inter, 400 / 500 / 600 / 700. Fallback chain `-apple-system, BlinkMacSystemFont, sans-serif`.
- **Base size:** 14 px / line-height 1.45.

Type scale (every size that exists in the codebase):

| Use | Size / Weight |
|---|---|
| Brand wordmark | 22 / 800 |
| Detail name (`<h2>`) | 19 / 700 |
| Shop name (list) | 14 / 700; 13 / 700 on mobile |
| Body / detail text | 13.5 / 400 |
| Detail meta, chip | 12.5 / 500 |
| Freshness, shop meta | 12 / 400 |
| Detail muted, tags | 11.5 / 400 |
| Section labels (uppercase) | 11 / 600 |
| Counts | 10–11 / 500 |
| Search input on mobile | 16 / 400 |
| Footer | 11 (10.5 mobile) / 400 |

Uppercase labels use `letter-spacing: 0.06em`. There are no italic styles.

### Spacing & radii

- **Spacing:** small increments from 2–20 px; actual component and responsive values in `public/index.html` take precedence.
- **Radii:** 4 px (pill tags, callouts), 6 px (chips, search input, action buttons), 50% (pin, dot, icon tile, cluster bubble).
- **Borders:** 1 px solid `--border` for surfaces; 2–3 px for pin outlines; 3 px inset category-color bar for the selected item.

### Shadows

| Element | Shadow |
|---|---|
| Pin | `0 2px 6px rgba(0,0,0,0.35)` |
| Pin (late-night ring) | `0 0 0 3px rgba(63,79,138,0.32), 0 2px 6px rgba(0,0,0,0.35)` |
| Pin (selected) | `0 0 0 5px rgba(122,86,53,0.32), 0 2px 8px rgba(0,0,0,0.4)` |
| Cluster bubble | `0 2px 6px rgba(0,0,0,0.3)`, 2 px white border |
| Leaflet popup | `0 4px 16px rgba(0,0,0,0.18)` |
| Icon tile (list) | `0 1px 2px rgba(0,0,0,0.12)` |
| Pin label pill | `0 1px 3px rgba(0,0,0,0.18)` |

## Components

### Pin (map marker)

- 26 × 26 px circle, category-color background, 2 px white border.
- Centered emoji glyph at 13 px, white.
- Hover: `transform: scale(1.12)`.
- Selected: 32 × 32 px, 3 px white border, brown halo (5 px `--accent` at 32% alpha).
- Late-night variant: blue glow ring (`--c-late` at 32% alpha).

### Pin label

- White pill, 11 px / 600, `rgba(255,255,255,0.94)` background, 4 px radius.
- Padding `2px 6px`.
- Hidden below zoom 13 (`LABEL_MIN_ZOOM`). Above 13, a runtime placer picks one of 16 angles around the pin (every 22.5°), starting with cardinals (bottom, right, top, left), then diagonals, then in-betweens. The first non-colliding angle wins; if none fit, the label hides.

### Chip

- Inline-flex pill, 6 px radius, 1 px border.
- Padding `4px 10px` (desktop), `2px 7px` (mobile).
- 12.5 px / 500 (desktop), 11.5 px / 500 (mobile).
- Optional 13 px emoji icon **or** 7 × 7 px colored dot before the label.
- Optional 11 px / 500 count after the label.
- Active state: solid `--text` background, white text, `aria-pressed="true"`.
- Themed chips (category / feature) use the category or feature hex at `1f` alpha for the background and at `55` alpha for the border, with full hex as the text color. Active themed chips invert to a solid fill.

### List item

- Desktop padding `10px 16px`, 1 px bottom border. Selected row uses an inset 3 px category-color bar. Mobile padding remains `5px 12px`.
- Hover: `--surface-alt`. Active: `--accent-soft` with the category-colored inset bar; visible keyboard focus uses `--accent`.
- The active mark survives Back — closing a detail card leaves its row marked (`state.viewedId`), so returning to the list shows where you were. A new filter, search or chip clears it; viewport changes and pagination preserve it. One helper (`setMarked`) applies the mark everywhere, including to rows rebuilt after a pan, and pairs the colored bar with `aria-current="true"`.
- Name with category icon tile and a weighted score in a separate right-aligned column; location/category and model/curation provenance below; up to three existing verified tags separated by a `--muted` `·`. Unknown amenities do not become claims. Model badges are `#215c3a` (indie) and `#434b59` (franchise), and curated badges use `#215c3a` on a selected row, in light mode so they clear 4.5:1 on the selected tint, with dedicated dark-mode overrides.
- Each item is `role="button"`, `tabindex="0"`, `data-id="{cityslug}-{shopslug}"` for keyboard nav. The accessible name is `name, category in neighborhood, score N` — or `, no rating`, matching what the card shows.

### Icon tile (list)

- 22 × 22 px circle, `--venue-color` background, white emoji at 11.5 px, soft shadow. 6 px gap before the name.

### Detail card

- Replaces the list view via `.panel.detail-mode` class.
- Header: 16 × 20 px padding, category dot + neighborhood (uppercase 11 px), shop name (19 px / 700), weighted score plus its explicit label. Google stars and review counts appear beneath as provenance. A category-color top rule links the detail to its map pin.
- Body sections: `Best for`, `Known for`, `Location & hours`, `Coworking`, `Late-night` — each preceded by an 11 px uppercase letter-spaced label.
- Pill tags (11.5 px, 4 px radius) for loved-items and best-for badges.
- Meeting-room callout: 10 px padding, `--accent-soft` background, 3 px `--accent` left border, 10.5 px / 700 uppercase label.
- Action row at the bottom: 7 × 10 px padded buttons, equal flex, opens in a new tab.

### Cluster bubble

- Dark brown disc (`#2b1d12`), white count text, 2 px white border.
- 28 px (≤4 children), 32 px (5–9), 36 px (≥10).

### Filter bar

- Background `--surface`, 10 × 20 px padding, bottom border.
- Two rows: Type and Useful for. Geography is controlled through map navigation and search; location-chip rows are omitted.
- Row label is 11 px uppercase muted at 70 px min-width; hidden below 820 px.

## Patterns

### Native shape

The product is geographically organized. The page is **map + viewport-filtered list + detail card**. That is the only layout. Don't introduce category pages, brand pages, or alternate views — those break the "one tap to the answer" principle from `PRODUCT.md` §1.

### Single-tap, no preview

A pin click selects the shop and immediately opens the detail card. There is no popup intermediary. (PRODUCT §1.)

### Viewport = filter

As the map pans or zooms, the right-side list re-filters to the visible markers. The map view is itself a filter. The cluster layer keeps *all* matching markers, even those off-screen; the list is the only thing that contracts. (PRODUCT §3.)

### Ranking is implicit

There is no sort dropdown. The list is always ordered by Bayesian weighted rating, descending — IMDB's Top-250 formula with `C` = mean rating across all loaded shops and `m` = median review count across all loaded shops. (PRODUCT §2.)

### Labels never lie

No two shop labels overlap. No label sits over a pin or cluster. Higher-rated shops claim space first; shops that can't find a non-colliding angle hide their label. (PRODUCT §7.)

### Density on mobile

Below 820 px viewport: map uses `clamp(130px, 22vh, 185px)` (125 px on short screens), panel fills the remaining vertical space, footer hidden, chip rows scroll horizontally if needed. Target: 5 list cards visible above the fold on a 750 px Safari viewport. (PRODUCT §5.)

## Page anatomy

```text
Header       Caffeye / Coffee in {loaded region}    Franchise toggle · Theme
             {in-scope count} spots · {source verification months}
Filters      Type: All + six category chips with derived counts
             Useful for: Work-friendly · Meeting room · Open late · Until midnight
Main         Map (Leaflet + clustering) | Search
                                        | {count} spots / in view · ◆ = weighted score
                                        | Ranked venue cards, 200 per page
                                        | Selected venue detail replaces the list
Footer       Ratings, hours, and addresses change. Verify before visiting.
```

Before data arrives, the brand reads “Metro Atlanta” and the freshness line reads “Loading Metro Atlanta…”. Location chip rows are omitted. September 2026 default scope is 970 independent venues across Metro Atlanta; franchise inclusion expands it to 1,705. Counts are illustrative snapshot values, never HTML placeholders.


**Hierarchy** (top-down weight):

1. The map — largest content area on desktop; capped on phones to prioritize list density. Pins carry category color.
2. The filter bar — drives both the map and the list.
3. The list — scrollable beside the map on desktop, below it on phones.
4. The detail card — replaces the list in place, never the map.
5. Header and footer — chrome, smallest visual weight.

When the README opens with the map, the design puts the map at the center. Anything that pulls attention off the map (over-decorated chrome, side panels, modals) is out of scope.

## Iconography & emoji as data

Every category and every feature has a single emoji. The emoji is not decoration — it carries the category identity wherever the category appears: chip, list item icon tile, map pin, detail card. The emoji and the hex color are paired. If a new category is introduced, both must be defined together in `CATS`.

No other emoji exist in the UI. The freshness line, search, list meta, and detail copy are emoji-free.

## Data shape (the product's grammar)

A shop is the only first-class entity. From `public/shops.json`:

```jsonc
{
  "name": "...",
  "city": "Duluth",
  "addrKey": "duluth-2180-pleasanthill",
  "category": "Coffee" | "Roasters" | "Bakery+Cafe" | "Tea/Boba" | "Dessert Cafe" | "Specialty",
  "rating": 4.9, "ratingCount": "190+", "ratingNum": 190,
  "hours": "...", "usp": "...", "signature": "...",
  "loved": ["...", "...", "..."],
  "googleUrl": "...", "yelpUrl": "...", "website": "..." | null,
  "cw": { "tier": "excellent" | "good" | "limited", "note": "...", "hasMeetingRoom": false },
  "late": { "tier": "10pm+" | "midnight", "when": "..." }  // omitted if early-close
}
```

Every UI surface maps to a slice of this record. Don't render anything that isn't here.

## Responsive rules

### Desktop (≥ 821 px)
Map on the left flex-grow, 400 px panel on the right, 1 px vertical divider.

### Mobile (≤ 820 px)
- Layout flips to column. Map uses `clamp(130px, 22vh, 185px)` (125 px on short screens), panel `flex: 1` taking the rest.
- Header tightens: brand 15 px / 800; freshness is hidden on phones. At widths ≤ 380 px, omit the visible “Coffee in” prefix and retain the full region in the page title and home button accessible name.
- Filter bar shrinks: padding 4 × 12 px, chip padding 2 × 7 px, chip font 11.5 px, label hidden.
- Filter rows become horizontal-scroll (`overflow-x: auto`, hidden scrollbar).
- Footer hidden.
- Shop item compresses: padding 5 × 12 px, icon tile 18 × 18 px, name 13 px / 700. Score remains in the right column.

## Don'ts

These come from product principles and prior incidents — don't re-introduce them.

- **No sort dropdown.** The default beats the control. (PRODUCT §2)
- **No preview popup on pin click.** One tap to the answer. (PRODUCT §1)
- **No floating action buttons, no modals, no toasts.** The detail card is the only secondary surface.
- **No approximate coordinates.** Curated seed addresses use Apple Maps via `CLGeocoder`; generated regional records use Google Places coordinates.
- **No emoji outside the category / feature system.** No decorative emoji in copy.
- **No additional fonts.** Inter + Fraunces is the entire family.
- **No color outside the listed tokens.** Anywhere a new accent feels needed, it's already in `CATS` or `--c-late`/`--c-work`.
- **Only intentional public assets in `public/`.** Brand logos, icons, social images, manifest, datasets, and renderer code are published there. Keep prototypes, screenshots, tooling, and private data outside it.
- **No "Past midnight" label.** Most "midnight" shops close *at* 12 am. The label is **Until midnight**. (Truth in labeling.)

## September 2026 field-guide refinement

The list leads with the name and separately aligned weighted score, then location and category. Existing amenity/editorial tags use body text contrast. The desktop panel is 400 px; phone density and map height remain unchanged. The detail header repeats the selected category color without adding another navigation step. This direction was chosen from a four-variant exploration evaluating scanability, visual hierarchy, and card density.
