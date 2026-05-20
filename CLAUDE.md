# CLAUDE.md

Operating notes for Claude when working on this project. Companion to `PRODUCT.md` (the "why"), `REQUIREMENTS.md` (the "what"), and `TESTS.md` (the "verify"). Read those when the task isn't covered here.

## What this project is

A single static HTML file (`index.html`) that maps every coffee shop, bakery, and tea house in Duluth, GA. Hosted on Cloudflare Workers static assets at <https://duluth-coffee-shoppes.sra-e69.workers.dev>. No build step, no backend, no framework. Leaflet + MarkerCluster loaded from CDN.

For product principles and design rationale, read `PRODUCT.md` first.

## File layout

```
public/index.html # the entire app (~91 KB) — the ONLY file Cloudflare publishes
wrangler.jsonc    # Cloudflare deploy config; assets.directory = ./public
PRODUCT.md        # principles + design rationale (single source of truth)
REQUIREMENTS.md   # numbered requirements (R1.x – R10.x)
TESTS.md          # tests traced to requirement IDs
README.md         # public-facing overview
```

## Run locally

```sh
cd public
python3 -m http.server 8765
# open http://127.0.0.1:8765
```

## Deploy — auto-deploy via Cloudflare Git integration

The Cloudflare Worker `duluth-coffee-shoppes` is connected to the GitHub repo `curdriceaurora/caffeye`. **Pushing to `main` triggers an automatic deploy.** No `wrangler deploy` needed in the normal flow.

The repo layout is designed so wrangler can't accidentally publish secrets: `assets.directory` points to `./public/`, and only `index.html` lives in there. Everything else (README, docs, `.git/`, `.wrangler/` cache) is outside the published tree.

For manual hotfix deploys:

```sh
# from the repo root, not from inside public/
wrangler deploy
```

`wrangler login` is set up; tokens are stored in the user's keyring. If a fresh login is needed, OAuth opens in the default browser — the user clicks "Allow" once. **Never** add files to `public/` other than `index.html` — anything you drop there is publicly served.

## Editing the data

All curated data lives in `public/shops.json` (v4 schema). `index.html` only carries the rendering shell — it fetches `shops.json` on boot and hydrates the in-memory globals.

The schema:

```jsonc
{
  "version": 4,
  "regionLabel": "Duluth",       // shown when no single city is active
  "checkedMonth": "May 2026",
  "cities": ["Duluth"],          // list grows as new cities are added
  "shops": [
    {
      "name": "...",
      "city": "Duluth",
      "addrKey": "duluth-2180-pleasanthill",  // city-prefixed to prevent cross-city collisions
      "address": "...",          // full text address
      "category": "...",         // must exist in CATS in index.html
      "rating": 4.4, "ratingCount": "5,900+", "ratingNum": 5900,
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
4. If you're adding the first shop in a new city, append the city to `cities`. Once `cities.length > 1`, the City chip row appears automatically.

After editing, verify with these console snippets (also available in `TESTS.md` §T1):

```js
SHOPS.length;
SHOPS.filter(s => !s.lat || !s.lng);                       // must be []
SHOPS.filter(s => !s.cw);                                  // must be []
SHOPS.filter(s => !CATS[s.category]);                      // must be []
SHOPS.filter(s => !s.addrKey || !ADDR[s.addrKey]);         // must be []
SHOPS.filter(s => !s.addrKey.startsWith(s.city.toLowerCase() + '-'));  // must be []
```

## Key conventions to preserve

These are decisions, not accidents — don't undo them without reading the linked principle in `PRODUCT.md`.

| Convention | Why | Principle |
|---|---|---|
| **No sort dropdown.** The list always orders by Bayesian weighted rating, descending. | The right default beats a control. | §2 |
| **Single-tap pin → detail card.** No preview popup. | One tap to the answer. | §1 |
| **Viewport-filtered list.** The right-side list only shows shops whose pins lie in the current map viewport. | Show what the user can see. | §3 |
| **Same-coord shops are radially nudged** ~20 m via `spreadCoincidentShops()`. | Pins must not stack. | §7 |
| **16-angle label placer.** Labels prefer cardinal angles, fall back through diagonals + in-betweens; obstacles are other labels, all pins, all `.coffee-cluster` bubbles. Higher-weighted shops claim space first. | Labels must never lie. | §7 |
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
