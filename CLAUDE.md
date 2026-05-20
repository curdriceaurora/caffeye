# CLAUDE.md

Operating notes for Claude when working on this project. Companion to `VISION.md` (the "why"), `REQUIREMENTS.md` (the "what"), and `TESTS.md` (the "verify"). Read those when the task isn't covered here.

## What this project is

A single static HTML file (`index.html`) that maps every coffee shop, bakery, and tea house in Duluth, GA. Hosted on Cloudflare Workers static assets at <https://duluth-coffee-shoppes.sra-e69.workers.dev>. No build step, no backend, no framework. Leaflet + MarkerCluster loaded from CDN.

For design rationale and the seven product principles, read `VISION.md` first.

## File layout

```
index.html        # the entire app (~91 KB)
wrangler.jsonc    # Cloudflare deploy config
VISION.md         # principles + design rationale
REQUIREMENTS.md   # numbered requirements (R1.x – R10.x)
TESTS.md          # tests traced to requirement IDs
README.md         # public-facing overview
```

## Run locally

```sh
python3 -m http.server 8765
# open http://127.0.0.1:8765
```

## Deploy — important security pattern

**Never run `wrangler deploy` from this project folder.** Wrangler treats every file under `assets.directory` as a public static asset, and the deploy process creates `.wrangler/cache/wrangler-account.json` (containing the OAuth token) in the working directory. If that ends up under `directory`, it gets uploaded and publicly served. This has happened once before — see the incident reasoning in `VISION.md`.

The safe pattern: deploy from a *clean* folder that contains only `wrangler.jsonc` and a `public/` subfolder with `index.html`.

```sh
mkdir -p /tmp/cof-clean/public
cp index.html /tmp/cof-clean/public/
cp wrangler.jsonc /tmp/cof-clean/
cd /tmp/cof-clean
wrangler deploy
```

`wrangler login` is already set up; tokens are stored in the user's keyring. If a fresh login is needed, OAuth opens in the default browser — the user clicks "Allow" once.

## Editing the data

The shop list is a hand-curated JS array in `index.html` (`const SHOPS = [ … ]`). Adding a shop requires touching multiple parallel structures — they must all stay in sync:

1. `SHOPS` — append a new entry with `lat: 0, lng: 0` placeholders.
2. `ADDR` — if it's a new building, add `"{num}-{streetslug}": {lat, lng}`. Coords **must** come from an authoritative geocoder (Apple Maps via `CLGeocoder` is the standard — see `outputs/apple_geocode.swift` in scratch). Do not approximate. A wrong coord that lands a shop in a residential subdivision was the bug that triggered the geocoding QA pass.
3. `SHOP_ADDR` — map the shop name → the ADDR key.
4. `NEIGHBORHOODS` — map the ADDR key → a neighborhood label (must be consistent with existing ones).
5. `CWS` — every shop **must** have an entry with `tier: 'excellent' | 'good' | 'limited'`.
6. `WEBSITES` — every shop **must** have an entry (use `null` if no site).
7. `LATE` — only if the shop's closing time is ≥ 10 pm.
8. Update header freshness count (`"58 cafés…"`) and the `resultsCount` placeholder (`<span id="resultsCount">58</span>`).

After editing, verify with the console snippets in `TESTS.md` §T1 — particularly:

```js
SHOPS.length;
Object.keys(CWS).filter(k => !SHOPS.some(s => s.name === k));    // must be []
Object.keys(LATE).filter(k => !SHOPS.some(s => s.name === k));   // must be []
Object.keys(WEBSITES).filter(k => !SHOPS.some(s => s.name === k)); // must be []
SHOPS.filter(s => !CATS[s.category]);                            // must be []
SHOPS.filter(s => !s.lat || !s.lng);                             // must be []
```

## Key conventions to preserve

These are decisions, not accidents — don't undo them without reading the linked principle in `VISION.md`.

| Convention | Why | Principle |
|---|---|---|
| **No sort dropdown.** The list always orders by Bayesian weighted rating, descending. | The right default beats a control. | §2 |
| **Single-tap pin → detail card.** No preview popup. | One tap to the answer. | §1 |
| **Viewport-filtered list.** The right-side list only shows shops whose pins lie in the current map viewport. | Show what the user can see. | §3 |
| **Same-coord shops are radially nudged** ~20 m via `spreadCoincidentShops()`. | Pins must not stack. | §6 |
| **16-angle label placer.** Labels prefer cardinal angles, fall back through diagonals + in-betweens; obstacles are other labels, all pins, all `.coffee-cluster` bubbles. Higher-weighted shops claim space first. | Labels must never lie. | §6 |
| **Label threshold is `LABEL_MIN_ZOOM = 13`** (the default fit-bounds zoom), so labels show on first paint. | — | — |
| **Bayesian weighted rating** formula `WR = (v/(v+m))·R + (m/(v+m))·C` — `C` = mean rating, `m` = median review count, both computed at load. | Trustworthy ranking. | §2 |
| **Mobile: map fixed at 220 px**, panel takes the rest, footer hidden. | Density on phones — iPhone 14 Pro target = 5 cards visible. | §4 |
| **"Until midnight"** is the label for the midnight tier — not "Past midnight" (most close at 12am sharp). | Truth in labeling. | — |

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
