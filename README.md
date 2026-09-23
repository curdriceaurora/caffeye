# caffeye

A one-page, single-tap map of coffee shops, bakeries, and tea houses across **Metro Atlanta** — built so a local can decide where to go in under thirty seconds.

🌐 **Live:** <https://duluth-coffee-shoppes.sra-e69.workers.dev>

![category count](https://img.shields.io/badge/categories-6-b89464) ![host](https://img.shields.io/badge/hosted%20on-Cloudflare%20Workers-orange)

## What it is

A static HTML file. No build step, no backend. Uses Leaflet + MarkerCluster from CDN to map a curated Duluth seed plus discovered regional venues (1,705 after deduplication in the September 2026 snapshot) with category-colored emoji pins, and lets you filter by category, work-friendly, meeting room, open-late, or open-until-midnight. The right-side list mirrors what's in the current map viewport, sorted by Bayesian weighted rating (IMDB Top 250 formula).

The default view shows 970 independent venues; enable **Include franchise stores** for all 1,705 across 14 counties. Counts, region labels, and verification months come from the loaded JSON. The 61-venue seed remains available if regional loading fails (41 independent venues by default). These counts are a dated snapshot; use the data-summary snippet in [TESTS.md](TESTS.md) after a refresh.

For the product principles and design decisions, see **[PRODUCT.md](PRODUCT.md)**.
For the spec, see **[REQUIREMENTS.md](REQUIREMENTS.md)**.
For the test suite, see **[TESTS.md](TESTS.md)**.

## Run locally

```sh
cd "caffeye/public"
python3 -m http.server 8765
# open http://127.0.0.1:8765
```

Use HTTP rather than opening the file directly: the page fetches `shops.json` and `places.json`.

Run regression checks from the repository root with `npm ci`, `npx playwright install chromium`, and `npm test`.

## Deploy

Hosted on Cloudflare Workers static assets. **Pushing to `main` auto-deploys** via Cloudflare's Git integration — `wrangler.jsonc` points `assets.directory` at `./public/`, which publishes the app shell, JSON datasets, manifest, and brand assets. Scripts and repository documentation stay outside the published directory.

To deploy manually (e.g. for a hotfix while bypassing Git):

```sh
wrangler deploy
```

⚠️ Run from the repo root, never from inside `public/`. Wrangler treats every file under the assets `directory` as a static asset; `.wrangler/` cache files contain an OAuth token and must never end up there. The `/public/` subfolder guarantees this.

## Add a new shop

1. Add curated venues to `public/shops.json`, with per-venue `cw`, optional `late`, `website`, category, business model, and verified coordinates. Add new building coordinates to `addr` and the matching area to `neighborhoods`.
2. Maintain regional editorial overlays in `scripts/curations.json`; refresh generated `public/places.json` through `scripts/discover_places.py` and its replay workflow (see [CLAUDE.md](CLAUDE.md)). Do not hand-edit generated regional records.
3. Update the source's `checkedMonth` only when its data has actually been verified. The page derives visible counts, region, and metadata; no HTML count placeholder needs editing.
4. Verify the merged data and both franchise-toggle states using [TESTS.md](TESTS.md), including fallback and retry behavior.

To prioritize editorial research, run `python3 scripts/curate_places.py --research-queue`. It returns the ten highest-ranked independent venues missing coworking data, with place IDs, addresses, and website/map links. This command makes no network calls or data changes; verify amenities before adding an overlay.

Curated coordinates use an authoritative geocoder (Apple Maps via `CLGeocoder`); discovered coordinates come from Google Places. See `PRODUCT.md` §8.

## Project structure

```
caffeye/
├── public/
│   ├── index.html    # app shell; fetches both datasets
│   ├── maplibre-preview.js # opt-in ?renderer=vector preview
│   ├── shops.json    # curated Duluth seed and fallback
│   ├── places.json   # generated regional discovery data
│   ├── manifest.webmanifest
│   └── brand/        # logos, icons, social media assets and tokens
├── scripts/          # discovery, curation, refresh and Python tests
├── tests/            # Playwright browser regressions
├── wrangler.jsonc    # Cloudflare deploy config (assets.directory = ./public)
├── README.md         # this file
├── PRODUCT.md        # principles + design rationale (single source of truth)
├── REQUIREMENTS.md   # numbered requirements (R1.x – R10.x, R13.x)
├── TESTS.md          # test suite traced to requirements
└── CLAUDE.md         # operating notes for AI sessions
```

## Stack

- **[Leaflet 1.9.4](https://leafletjs.com/)** — open-source map library
- **[Leaflet.markercluster 1.5.3](https://github.com/Leaflet/Leaflet.markercluster)** — pin clustering
- **[MapLibre GL JS 5.24.0](https://maplibre.org/)** + **[OpenFreeMap](https://openfreemap.org/)** tiles — only for the opt-in `?renderer=vector` preview
- **[CARTO Light](https://carto.com/help/building-maps/basemap-list/)** — basemap tiles
- **[OpenStreetMap](https://www.openstreetmap.org/)** — underlying map data
- **Inter** + **Fraunces** via Google Fonts
- **[Cloudflare Workers](https://workers.cloudflare.com/)** static assets — hosting

## License

MIT — see [LICENSE](LICENSE).
