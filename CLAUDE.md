# CLAUDE.md

Operating notes for Claude when working on this project. Companion to `PRODUCT.md` (the "why"), `REQUIREMENTS.md` (the "what"), and `TESTS.md` (the "verify"). Read those when the task isn't covered here.

## What this project is

A single static HTML file (`index.html`) that maps every coffee shop, bakery, and tea house in Duluth, GA. Hosted on Cloudflare Workers static assets at <https://duluth-coffee-shoppes.sra-e69.workers.dev>. No build step, no backend, no framework. Leaflet + MarkerCluster loaded from CDN.

For product principles and design rationale, read `PRODUCT.md` first.

## File layout

```
public/
  index.html          # the entire app shell (~95 KB)
  shops.json          # curated shop data (Duluth baseline)
  places.json         # discovered places across North Atlanta
  favicon.ico         # root browser favicon fallback
  manifest.webmanifest # PWA web manifest
  brand/              # Bean Eye v1.0 brand assets
    icons/            # favicon.svg, PNG favicons, apple-touch-icon, PWA icons
    logos/            # vector symbols & horizontal wordmark locks
    social/           # OpenGraph / Twitter share cards (1200x630)
    tokens/           # brand color & typography reference tokens
wrangler.jsonc        # Cloudflare deploy config; assets.directory = ./public
brand/                # raw source brand packages (caffeye-v1)
PRODUCT.md            # principles + design rationale (single source of truth)
REQUIREMENTS.md       # numbered requirements (R1.x – R10.x)
TESTS.md              # tests traced to requirement IDs
README.md             # public-facing overview
```

## Run locally

```sh
cd public
python3 -m http.server 8765
# open http://127.0.0.1:8765
```

## Deploy — auto-deploy via Cloudflare Git integration

The Cloudflare Worker `duluth-coffee-shoppes` is connected to the GitHub repo `curdriceaurora/caffeye`. **Pushing to `main` triggers an automatic deploy.** No `wrangler deploy` needed in the normal flow.

The repo layout is designed so wrangler can't accidentally publish secrets: `assets.directory` points to `./public/`, which contains only client-safe static assets (`index.html`, data json files, brand media, favicons, manifest). Everything else (scripts, private keys, README, docs, `.git/`, `.wrangler/` cache) is outside the published tree.

For manual hotfix deploys:

```sh
# from the repo root, not from inside public/
wrangler deploy
```

`wrangler login` is set up; tokens are stored in the user's keyring. If a fresh login is needed, OAuth opens in the default browser — the user clicks "Allow" once. Do not add sensitive credentials or scratch files to `public/` — anything dropped there is publicly served.

## Editing the data

All curated data lives in `public/shops.json` (v5 schema). `index.html` only carries the rendering shell — it fetches `shops.json` on boot and hydrates the in-memory globals.

The schema:

```jsonc
{
  "version": 5,
  "regionLabel": "Duluth",       // shown when no single city is active
  "checkedMonth": "May 2026",
  "cities": ["Duluth"],          // list grows as new cities are added
  "shops": [
    {
      "name": "...",
      "city": "Duluth",
      "county": "Fulton",        // optional; omit for single-region data. Drives the County chip row.
      "model": "independent|franchise", // independent local spot or franchise/chain location
      "addrKey": "duluth-2180-pleasanthill",  // city-prefixed to prevent cross-city collisions
      "address": "...",          // full text address
      "category": "...",         // must exist in CATS in index.html
      "rating": 4.5, "ratingCount": "3,767", "ratingNum": 3767,   // Google's own numbers; ratingCount = display string of ratingNum
      "placeId": "ChIJ…",        // Google place id, stored by scripts/refresh_ratings.py on first match
      "hours": "...",
      "usp": "...",
      "loved": ["...", "...", "..."],
      "signature": "...",
      "googleUrl": "...", "yelpUrl": "...",
      "cw": { "tier": "excellent|good|limited", "note": "...", "hasMeetingRoom": false, "meetingRoomNote": "..." },
      "late": { "tier": "10pm+|midnight", "when": "..." },  // omit if shop closes before 10 pm
      "website": "https://..."   // or null
    }
  ],
  "addr":  { "duluth-2180-pleasanthill": { "lat": 33.96147, "lng": -84.13401 } },
  "neighborhoods": { "duluth-2180-pleasanthill": "Pleasant Hill" }
}
```

**To add a shop:**

1. Append a shop object to `shops`. Include `city`, the new compound `addrKey`, and the inline `cw` / `late?` / `website` blocks. No more separate CWS / LATE / WEBSITES tables — that pattern collided when the same brand opened in two cities.
2. If it's a new building, add a `"{city}-{num}-{streetslug}": {lat, lng}` entry to `addr` and a matching `neighborhoods` entry. Coords **must** come from an authoritative geocoder (Apple Maps via `CLGeocoder` is the standard — see `outputs/apple_geocode.swift` in scratch). Do not approximate. A wrong coord that lands a shop in a residential subdivision was the bug that triggered the geocoding QA pass.
3. Bump nothing else — the header freshness count is computed at runtime from `SHOPS.length` scoped to the active city.
4. If you're adding the first shop in a new city, append the city to `cities`. Once `cities.length > 1`, the City chip row appears automatically. Same for `county` — the County chip row appears once more than one distinct `county` value exists across `shops`, and shares a filter-bar row with City (not a separate one) so it doesn't cost mobile an extra line.

**Multi-county expansion (in progress, `feat/north-atlanta-expansion`):** `public/shops.json` on this branch is the real, unmodified 61-shop Duluth data — byte-identical to `main`. It is NOT the 244-shop (now 198-shop) placeholder fixture; that only ever lives at `scratch/shops-multicounty-test.json` (gitignored), generated on demand by `scripts/bootstrap_multicount.py` and never written to `public/`. To try it locally: `cp scratch/shops-multicounty-test.json public/shops.json`, and revert before committing anything — never let that copy reach a commit.

Most of real Duluth is in Gwinnett County, but not all of it: 3 of the 61 shops have Johns Creek addresses and are actually in Fulton (Georgia postal cities and county lines don't reliably align — a `city` of "Duluth" doesn't imply `county: "Gwinnett"`). `scripts/refresh_ratings.py --county <fulton|dekalb|forsyth|gwinnett|cobb|cherokee|hall|dawson>` filters an *existing* `shops` array to audit/refresh one county at a time (it does not discover new shops); a shop's own `county` tag wins if present, otherwise its coordinates are tested against that county's real boundary polygon in `scripts/county_boundaries.geojson` (fetched from OpenStreetMap, not hand-drawn — a simple rectangle cannot represent Fulton, which is long, irregular, and extends much further east at its northern tip near Johns Creek than near Atlanta). Real per-county curated data should eventually replace today's single-region file.

At real multi-county scale (~1,500–2,000 shops), revisit `shops.json`'s minification (numeric category/neighborhood keys, abbreviated addresses) — the 100 KB budget below is for `index.html` only, but `shops.json` compounds with shop count and should stay gzip-friendly.

### Discovered shops — `public/places.json`

Generated, never hand-edited. Region, query types, category mapping and the chain list are constants at the top of `scripts/discover_places.py`. To re-run (on demand only — nothing is scheduled):

```sh
python3 scripts/discover_places.py --dry-run          # free: prints the exact paid-call count
python3 scripts/discover_places.py                    # gated paid pass → scratch/places-<date>.json + report
python3 scripts/discover_places.py --replay scratch/places-<date>.json --write
```

The paid pass refuses to start when `~/.config/caffeye/places_usage.json` shows ≥ 500 Enterprise calls this month or the run would exceed 900 (flags `--usage-threshold`, `--max-paid-calls`). `python3 scripts/places_ledger.py` prints the ledger. To drop a discovered place (relisted duplicate of a curated shop, a restaurant that slipped through the `cafe` type), add its `placeId` and a reason to `scripts/places_exclude.json` and replay. A curated shop always wins over a discovered twin with the same `placeId`.

Coordinates for discovered shops are Google's place pin; Apple `CLGeocoder` remains the rule for hand-added curated shops.

**Business Model Classification (`model: "independent" | "franchise"`):**
- **Indie vs. Franchise/Chains**: Multi-location chains and franchises (e.g. Tim Hortons, Caribou Coffee, Starbucks, Dunkin', Paris Baguette, Sweet Hut, 7 Brew, Dutch Bros) are classified under the unified `"franchise"` model. Standalone and small local roasters (1-2 locations) are classified as `"independent"`.
- **Grocery Stores Excluded**: In-store supermarket bakeries/cafes (Kroger, Walmart, Sam's Club, Costco, Whole Foods, Publix, Target, Sprouts, etc.) and fast-food burger chains (McDonald's) are completely removed at discovery.
- **Default View**: Caffeye defaults to **Indie only** on initial load (`state.includeFranchises = false`). Users can flip the top-right toggle **"Include franchise stores"** (or `"Franchises"` on mobile) to include chains and franchise stores alongside independent spots. "Useful for" strictly contains utility features (Work-friendly, Meeting rooms, Open late, Until midnight).

### Curation Engine — `scripts/curations.json` & `scripts/curate_places.py`

Google Places API provides operational data (hours, lat/lng, rating), but lacks editorial intelligence on coworking suitability (`cw: { tier, note, hasMeetingRoom, meetingRoomNote }`), USPs, and meeting room details. The Curation Engine bridges this gap by maintaining verified editorial overlays in `scripts/curations.json`.

`scripts/discover_places.py` automatically injects `curations.json` during crawls or replays, matching by `placeId` (or fuzzy `name` + `city`).

To audit, apply, or research curations:

```sh
python3 scripts/curate_places.py --audit              # audits coworking & meeting room coverage across counties
python3 scripts/curate_places.py --apply              # merges scripts/curations.json into public/places.json
python3 scripts/curate_places.py --research <url>     # inspects a shop website for meeting room & Wi-Fi signals
python3 -m unittest scripts/test_curate_places.py    # runs curation engine unit tests
```

**To refresh ratings** (`rating` / `ratingCount` / `ratingNum` drive the Bayesian ranking, so they must all come from one source — Google, via the Places API):

```sh
python3 scripts/refresh_ratings.py
python3 scripts/refresh_ratings.py --replay scratch/ratings-<date>.json --write
```

The first command is a live run: it prints the before/after table and dumps every response to `scratch/ratings-<date>.json` (git-ignored, merged into on later runs). The second writes exactly what was audited — `--write` refuses to run without `--replay`. Rows marked ⚠ are refused; `--accept "<name>"` overrides the two soft refusals (temporarily closed, review count fell by more than half — the signature of a relisted or duplicate Google entry). `python3 scripts/refresh_ratings.py --help` has the full rules and the key lookup order (`$GOOGLE_MAPS_API_KEY` wins over `~/.config/caffeye/google_maps_key`; the key is never printed). Never hand-type ratings from web-search snippets or aggregator mirrors — they merge locations (Sweet Hut: RestaurantGuru 5,980 vs Google 3,767). A `CLOSED_*` flag in the table is a status lead — follow up on it like a closure report.

After editing, verify with these console snippets (also available in `TESTS.md` §T1):

```js
SHOPS.length;
SHOPS.filter(s => !s.lat || !s.lng);                       // must be []
SHOPS.filter(s => !s.cw);                                  // must be []
SHOPS.filter(s => !CATS[s.category]);                      // must be []
SHOPS.filter(s => !s.addrKey || !ADDR[s.addrKey]);         // must be []
SHOPS.filter(s => !s.addrKey.startsWith(s.city.toLowerCase() + '-'));  // must be []
```

### Brand Identity & Design System (`brand/caffeye-v1/` & `public/brand/`)

The official Caffeye brand is **The Bean Eye v1.0** — an organic coffee bean silhouette enclosing a focused pupil with radiant brows.

- **Color Palette Tokens**:
  - Forest (Primary / Accent): `#293F34` (P3: `color(display-p3 0.161 0.247 0.204)`)
  - Paper (Canvas / Light text): `#F4F3ED`
  - Gold (Accent / Warmth): `#DCAF59`
  - Ink (Body / Text): `#222721`
  - Muted (Subtitles / Borders): `#60645F` / `#E5E3D8`
- **Typography**:
  - Display / Brand Wordmark: *Fraunces* (800 weight, optical size 144, soft 100)
  - UI / Body: *Inter*
- **Brand Assets & Favicons (`public/brand/`)**:
  - `public/favicon.ico`: 16/32/48 multi-resolution browser fallback icon.
  - `public/brand/icons/favicon.svg`: High-contrast vector seal favicon (Forest `#293F34` disc + Gold `#DCAF59` perimeter ring + Paper `#F4F3ED` Bean Eye), fully visible on both dark-mode and light-mode browser tab themes.
  - `public/brand/icons/favicon-{16,32,48}.png`: Raster favicons with matching high-contrast seal treatment.
  - `public/brand/icons/apple-touch-icon.png`: 180×180 iOS home-screen bookmark icon.
  - `public/brand/icons/icon-192.png` & `icon-512.png`: PWA manifest icons referenced in `public/manifest.webmanifest`.
  - `public/brand/social/caffeye-share-1200x630.png`: High-resolution OpenGraph and Twitter summary social preview card.
  - `public/brand/logos/`: Vector mark locks (`caffeye-symbol-forest.svg`, `caffeye-horizontal-forest.svg`, `caffeye-symbol-micro.svg`). Header uses `caffeye-symbol-forest.svg` as a clean typographic partner.
- **Header & Reset-to-Home**:
  - The top bar pairs the Bean Eye mark (`#brandHomeBtn`) at 22px height (17px on mobile) with the dynamic region title (`.brand`).
  - Clicking `#brandHomeBtn` resets all filters back to default (clears county/city selection, resets search, restores Indie-only default view).

## Key conventions to preserve

These are decisions, not accidents — don't undo them without reading the linked principle in `PRODUCT.md`.

| Convention | Why | Principle |
|---|---|---|
| **No sort dropdown.** The list always orders by Bayesian weighted rating, descending. | The right default beats a control. | §2 |
| **The ◆ score is the headline number.** Cards show `◆ 4.6` (weighted rating, 1 decimal); Google's raw `★ 4.5 · 3,767 reviews` appears only under the score on the detail card. Never show a ★ as if it were our ranking. | Labels must never lie; the ranking is ours. | §2, §7 |
| **Single-tap pin → detail card.** No preview popup. | One tap to the answer. | §1 |
| **Viewport-filtered list.** The right-side list only shows shops whose pins lie in the current map viewport. | Show what the user can see. | §3 |
| **Same-coord shops are radially nudged** ~20 m via `spreadCoincidentShops()`. | Pins must not stack. | §7 |
| **16-angle label placer.** Labels prefer cardinal angles, fall back through diagonals + in-betweens; obstacles are other labels, all pins, all `.coffee-cluster` bubbles. Higher-weighted shops claim space first. | Labels must never lie. | §7 |
| **Label threshold is `LABEL_MIN_ZOOM = 13`** (the default fit-bounds zoom), so labels show on first paint. | — | — |
| **Bayesian weighted rating** formula `WR = (v/(v+m))·R + (m/(v+m))·C` — `C` = mean rating, `m` = median review count, both computed at load. | Trustworthy ranking. | §2 |
| **County filter row removed** (`#locationRow` hidden). Type and Useful For rows provide clean categorization while matching the top-right franchise toggle state; preserves 5 visible cards on mobile at 375px. | Density on phones & simplified regional navigation. | §4 |
| **List pagination bounds the *default* render at 200 items** (`LIST_PAGE_SIZE`), not an absolute ceiling — clicking "Load more" repeatedly grows `state.listLimit` and re-renders the whole list each time, so the DOM does grow past 200 if a user pages through everything. Any filter/search/viewport change resets the window back to 200. Below 200 matches — every single-region dataset today — this is a no-op. A true hard cap would need list virtualization (windowed/spacer rendering with recycled DOM nodes), deliberately not implemented here — it needs fixed-row-height CSS and risks breaking the assumption elsewhere that every filtered `.shop-item` is in the DOM. | Bound the common case cheaply; don't take on virtualization's complexity until real usage shows it's needed. | §9 |
| **`placeLabels()`'s 300-simultaneously-visible-pin safety cap** hides labels above that count rather than running its O(items × angles × obstacles) collision pass — untested against real data today (clustering keeps counts well below 300 in practice, including on the 244-shop test fixture), verify the 300/301 boundary directly per TESTS.md T3.x before relying on it. | Guard the pathological case instead of claiming it's exercised by ordinary use. | §7 |
| **Mobile: map fixed at 220 px**, panel takes the rest, footer hidden. | Density on phones — iPhone 14 Pro target = 5 cards visible on single-region data; 4 when the County/City row is also shown (see R8.5) — that row costs ~48 px, deliberately not clawed back from card spacing shared with the 5-card baseline. | §4 |
| **"Until midnight"** is the label for the midnight tier — not "Past midnight" (most close at 12am sharp). | Truth in labeling. | — |
| **Map bounded to Greater Atlanta (`ATL_BOUNDS`: `[33.25, -85.00]` to `[34.75, -83.30]`)** with `minZoom: 8`, `maxZoom: 19`, and `maxBoundsViscosity: 1.0`. `L.tileLayer` specifies `bounds: ATL_BOUNDS` to prevent fetching or rendering tiles outside the region. `minZoom: 8` ensures mobile's 220px map can display the entire multi-county spread without markers being clipped on initial `fitBounds`. | Prevent stray panning, eliminate unnecessary tile bandwidth, ensure mobile full-extent display. | §3, §4 |

## Working with the user (Rahul)

Patterns from prior sessions:

- Prefers terse messages with results / links over preambles.
- Will iterate visually — expect "look at the screenshot, fix this" loops. Always reload the page after edits and verify with a screenshot when a visual change is claimed.
- Will sometimes do parts of a deploy / OAuth flow manually if the AI side is blocked; trust their report ("done", "i redeployd") and verify.
- Wants accuracy — when something is off (a pin in the wrong place, a label overlap), the answer is to fix it properly with the authoritative source, not to approximate.
- Cares about playfulness (emoji, color theming) as a feature, not decoration.

## Tools commonly used in this project

- **`mcp__Control_your_Mac__osascript`** — primary way to run shell commands, manage background processes (wrangler, geocoding scripts).
- **`mcp__Claude_in_Chrome__*`** — visually verify changes; especially `navigate`, `javascript_tool`, `computer.screenshot`, `browser_batch`.
- **Swift `CLGeocoder`** — authoritative US address geocoding; runs from `apple_geocode.swift` in scratch outputs. Apple Maps is the reference geocoder for this project's data.
- **`wrangler deploy`** — deploys; aliased through `/opt/homebrew/bin` so `node` resolves correctly when invoked from osascript.

## Things to avoid

- Don't approximate coordinates with linear interpolation. It put pins in residential subdivisions.
- Don't reintroduce a sort dropdown or split filters into modal pages — every step away from the map is a step the user has to take.
- Don't try to fit "the right answer" into a tiny user attention budget by deferring to chips. Default to "best overall."
- Don't run `wrangler deploy` from anywhere that contains `.wrangler/` — see the security pattern above.
