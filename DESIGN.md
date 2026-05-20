# DESIGN.md — caffeye

Design system spec for AI agents generating UI for the **caffeye** project. Everything here is sourced from `public/index.html`, `public/shops.json`, `README.md`, and `VISION.md`. If a value isn't here, it isn't part of the system.

## What this product is

**caffeye** — *"A one-page, single-tap map of every coffee shop, bakery, and tea house in Duluth, GA — built so a local can decide where to go in under thirty seconds."* (`README.md`)

The page is the product. There is one screen, one HTML file, fetched once. Everything else is filter and detail. The map is the spine. The list mirrors the map's current viewport. The detail card replaces the list when a shop is selected.

## Voice & copy

Pulled verbatim from the running app — these are the only label strings that exist.

| Surface | Copy |
|---|---|
| Page title | `Coffee in {scope}` where `scope` is the active city or `regionLabel` |
| Brand wordmark | Same as page title |
| Freshness line | `{count} cafés, bakeries & tea shops in {scope} · checked {checkedMonth}` |
| Search placeholder | `Search by name, drink, or area…` |
| Results header | `{n} SPOTS` (uppercase, letter-spaced) |
| Empty state | `No shops in this view. Try zooming out, clearing filters, or changing search.` |
| Footer | `Ratings, hours, and addresses change. Verify before visiting.` (hidden on mobile) |
| Back action | `← Back to list` |
| Detail action row | `Google Maps` · `Yelp` · `{host}` (host = `Instagram`/`Facebook`/`Linktree`/`Website`) |
| Filter row labels | `City` · `Type` · `Useful for` (hidden on mobile) |
| Coworking tier copy | `Coworking-ready` (excellent) · `Workable` (good) · `Quick-grab` (limited) |
| Late-night header | `Open until midnight` (midnight tier) · `Open till 10pm+` (10pm+ tier) |

**Tone is matter-of-fact.** No exclamation points. No "discover" / "explore" / "amazing." A shop has a `usp` (one sentence describing what makes it specific), `loved` (three plain noun phrases), and a `signature` (the dish/drink to try). Copy never tells the user how to feel; it tells them what's there.

## Visual identity

### Color tokens

CSS variables on `:root` in `public/index.html`:

| Token | Value | Used for |
|---|---|---|
| `--bg` | `#f7f6f2` | App background (cream) |
| `--surface` | `#ffffff` | Cards, header, panel |
| `--surface-alt` | `#faf9f5` | Hover surfaces |
| `--text` | `#1f1f1f` | Body text |
| `--muted` | `#6f6f6f` | Secondary text, captions, counts |
| `--border` | `#e3e0d6` | Subtle dividers |
| `--border-strong` | `#c9c4b4` | Action button borders |
| `--accent` | `#7a5635` | Brand accent (warm coffee brown) |
| `--accent-soft` | `#ebe1d2` | Selected list item background, callouts |

### Category colors (the playful layer)

From `CATS` in `public/index.html`. Each category has both a color and an emoji glyph; they are paired, never split.

| Category | Hex | Emoji | CSS token |
|---|---|---|---|
| Coffee | `#6f4e37` | ☕ | `--c-coffee` |
| Bakery+Cafe | `#b89464` | 🥐 | `--c-bakery` |
| Tea/Boba | `#5b8a72` | 🧋 | `--c-tea` |
| Dessert Cafe | `#c66980` | 🍰 | `--c-dessert` |
| Specialty | `#7b6cb8` | ✦ | `--c-specialty` |

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
| Shop name (list) | 14 / 600 |
| Body / detail text | 13.5 / 400 |
| Detail meta, chip | 12.5 / 500 |
| Freshness, shop meta | 12 / 400 |
| Detail muted, tags | 11.5 / 400 |
| Section labels (uppercase) | 11 / 600 |
| Counts, search input on mobile | 10.5–11 / 500 |
| Footer | 11 (10.5 mobile) / 400 |

Uppercase labels use `letter-spacing: 0.06em`. There are no italic styles.

### Spacing & radii

- **Spacing scale:** 2, 4, 6, 8, 10, 12, 14, 16, 20 px. No values outside this set.
- **Radii:** 4 px (pill tags, callouts), 6 px (chips, search input, action buttons), 50% (pin, dot, icon tile, cluster bubble).
- **Borders:** 1 px solid `--border` for surfaces; 2–3 px for pin outlines; 3 px solid `--accent` for the selected-item left bar.

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

- Padding `10px 16px 10px 13px`, 1 px bottom border, 3 px transparent left border that takes the category color.
- Hover: `--surface-alt`. Active: `--accent-soft`.
- Three lines: name with category icon tile, meta row (category · ★ rating (count) · neighborhood), up to three compact tags separated by `·`.
- Each item is `role="button"`, `tabindex="0"`, `data-id="{cityslug}-{shopslug}"` for keyboard nav.

### Icon tile (list)

- 22 × 22 px circle, category-color background, white emoji at 11.5 px, soft shadow. 6 px gap before the name.

### Detail card

- Replaces the list view via `.panel.detail-mode` class.
- Header: 16 × 20 px padding, category dot + neighborhood (uppercase 11 px), shop name (19 px / 700), star line (`★ 4.9 · 190+ reviews`).
- Body sections: `Best for`, `Known for`, `Location & hours`, `Coworking`, `Late-night` — each preceded by an 11 px uppercase letter-spaced label.
- Pill tags (11.5 px, 4 px radius) for loved-items and best-for badges.
- Meeting-room callout: 10 px padding, `--accent-soft` background, 3 px `--accent` left border, 10.5 px / 700 uppercase label.
- Action row at the bottom: 7 × 10 px padded buttons, equal flex, opens in a new tab.

### Cluster bubble

- Dark brown disc (`#2b1d12`), white count text, 2 px white border.
- 28 px (≤4 children), 32 px (5–9), 36 px (≥10).

### Filter bar

- Background `--surface`, 10 × 20 px padding, bottom border.
- Three rows: City (hidden until `cities.length > 1`), Type, Useful for.
- Row label is 11 px uppercase muted at 70 px min-width; hidden below 820 px.

## Patterns

### Native shape

The product is geographically organized. The page is **map + viewport-filtered list + detail card**. That is the only layout. Don't introduce category pages, brand pages, or alternate views — those break the "one tap to the answer" principle from `VISION.md` §1.

### Single-tap, no preview

A pin click selects the shop and immediately opens the detail card. There is no popup intermediary. (VISION §1.)

### Viewport = filter

As the map pans or zooms, the right-side list re-filters to the visible markers. The map view is itself a filter. The cluster layer keeps *all* matching markers, even those off-screen; the list is the only thing that contracts. (VISION §3.)

### Ranking is implicit

There is no sort dropdown. The list is always ordered by Bayesian weighted rating, descending — IMDB's Top-250 formula with `C` = mean rating across the active city's shops and `m` = median review count in that city. (VISION §2.)

### Labels never lie

No two shop labels overlap. No label sits over a pin or cluster. Higher-rated shops claim space first; shops that can't find a non-colliding angle hide their label. (VISION §6.)

### Density on mobile

Below 820 px viewport: map fixed at 220 px (180 min), panel fills the remaining vertical space, footer hidden, chip rows scroll horizontally if needed. Target: 5 list cards visible above the fold on a 750 px Safari viewport. (VISION §4.)

## Page anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ Coffee in Duluth   59 cafés, bakeries & tea shops in       │  header
│                    Duluth · checked May 2026                │
├─────────────────────────────────────────────────────────────┤
│ City   [All cities] [Duluth] …                              │  filter-bar
│ Type   [All 59] [☕ Coffee 10] [🥐 Bakery 18] …             │  (City row
│ Useful [💻 Work 19] [🤝 Meeting 4] [🌙 Late 39] …            │   hidden if
│                                                             │   1 city)
├──────────────────────────────────┬──────────────────────────┤
│                                  │ ⌕ Search…                │
│                                  ├──────────────────────────┤
│                                  │ 59 SPOTS                 │
│              [MAP]               ├──────────────────────────┤
│         (Leaflet + CARTO         │ │ 🥐 Bread Museum       │
│          + MarkerCluster)        │ │ Bakery & Cafe · ★ 4.9 │
│                                  │ │ Open late · salt bread│
│                                  ├──────────────────────────┤
│                                  │ │ 🧋 Chuchat            │  list (scrolls)
│                                  │ │ Tea/Boba · ★ 4.8      │
│                                  │ │ Open late · sea salt  │
│                                  ├──────────────────────────┤
│                                  │ …                        │
└──────────────────────────────────┴──────────────────────────┘
│ Ratings, hours, and addresses change. Verify before visiting│  footer
└─────────────────────────────────────────────────────────────┘
```

**Hierarchy** (top-down weight):

1. The map — claims the largest pixel area on every viewport. Pins are the most chromatic element on the page.
2. The filter bar — drives both the map and the list.
3. The right-side list — scrollable, secondary to the map but always visible alongside.
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
  "category": "Coffee" | "Bakery+Cafe" | "Tea/Boba" | "Dessert Cafe" | "Specialty",
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
Map on the left flex-grow, 380 px panel on the right, 1 px vertical divider.

### Mobile (≤ 820 px)
- Layout flips to column. Map fixed at 220 px (min 180 px), panel `flex: 1` taking the rest.
- Header tightens: brand 17 px / 800, freshness 10.5 px.
- Filter bar shrinks: padding 4 × 12 px, chip padding 2 × 7 px, chip font 11.5 px, label hidden.
- Filter rows become horizontal-scroll (`overflow-x: auto`, hidden scrollbar).
- Footer hidden.
- Shop item compresses: padding 7 × 14 px, icon tile 18 × 18 px, name 13 px.

## Don'ts

These come from product principles and prior incidents — don't re-introduce them.

- **No sort dropdown.** The default beats the control. (VISION §2)
- **No preview popup on pin click.** One tap to the answer. (VISION §1)
- **No floating action buttons, no modals, no toasts.** The detail card is the only secondary surface.
- **No approximate coordinates.** Coords come from Apple Maps via `CLGeocoder` only. Linear interpolation has put pins in residential subdivisions before.
- **No emoji outside the category / feature system.** No decorative emoji in copy.
- **No additional fonts.** Inter + Fraunces is the entire family.
- **No color outside the listed tokens.** Anywhere a new accent feels needed, it's already in `CATS` or `--c-late`/`--c-work`.
- **No image assets in `public/`.** The only file under `public/` other than `index.html` and `shops.json` is what wrangler will publish — anything you drop there ships publicly.
- **No "Past midnight" label.** Most "midnight" shops close *at* 12 am. The label is **Until midnight**. (Truth in labeling.)
