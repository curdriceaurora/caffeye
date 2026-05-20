# caffeye

A one-page, single-tap map of every coffee shop, bakery, and tea house in **Duluth, GA** — built so a local can decide where to go in under thirty seconds.

🌐 **Live:** <https://duluth-coffee-shoppes.sra-e69.workers.dev>

![pin labels avoiding overlap](https://img.shields.io/badge/shops-59-6f4e37) ![category count](https://img.shields.io/badge/categories-5-b89464) ![host](https://img.shields.io/badge/hosted%20on-Cloudflare%20Workers-orange)

## What it is

A static HTML file. No build step, no backend. Loads Leaflet + MarkerCluster from CDN, renders 59 curated shops with category-colored emoji pins, and lets you filter by category, work-friendly, meeting room, open-late, or open-until-midnight. The right-side list mirrors what's in the current map viewport, sorted by Bayesian weighted rating (IMDB Top 250 formula).

For the design decisions and trade-offs, see **[VISION.md](VISION.md)**.
For the spec, see **[REQUIREMENTS.md](REQUIREMENTS.md)**.
For the test suite, see **[TESTS.md](TESTS.md)**.

## Run locally

```sh
cd "caffeye"
python3 -m http.server 8765
# open http://127.0.0.1:8765
```

You can also just `open index.html` directly — the file is fully self-contained except for CDN assets.

## Deploy

Hosted on Cloudflare Workers static assets. To redeploy:

```sh
mkdir -p /tmp/cof-clean/public
cp index.html /tmp/cof-clean/public/
cp wrangler.jsonc /tmp/cof-clean/
cd /tmp/cof-clean
wrangler deploy
```

⚠️ Always deploy from a clean folder containing **only** `index.html` and `wrangler.jsonc`. Wrangler treats every file under the assets `directory` as a static asset, so never deploy from a folder that contains `.wrangler/` (it'll publish your OAuth token).

## Add a new shop

1. In `index.html`, append a new entry to `SHOPS` with `lat: 0, lng: 0` placeholders.
2. If it's a new address, add a `"{num}-{street}"` key to `ADDR` with the verified coords, then map it in `SHOP_ADDR`. Add to `NEIGHBORHOODS`.
3. Add the shop's name as a key in `CWS`, `WEBSITES`, and (if applicable) `LATE`.
4. Update the freshness count in the header and the `resultsCount` placeholder.
5. Verify locally — `js> SHOPS.length` and `js> Object.keys(CWS).filter(k => !SHOPS.some(s => s.name === k))` should be `[]`.

Coords should be verified against an authoritative geocoder (e.g. Apple Maps via `CLGeocoder`) — see `VISION.md` principle 7.

## Project structure

```
caffeye/
├── index.html        # the entire app (~91 KB)
├── wrangler.jsonc    # Cloudflare deploy config
├── README.md         # this file
├── VISION.md         # principles + design rationale
├── REQUIREMENTS.md   # numbered requirements (R1.x – R10.x)
└── TESTS.md          # test suite traced to requirements
```

## Stack

- **[Leaflet 1.9.4](https://leafletjs.com/)** — open-source map library
- **[Leaflet.markercluster 1.5.3](https://github.com/Leaflet/Leaflet.markercluster)** — pin clustering
- **[CARTO Light](https://carto.com/help/building-maps/basemap-list/)** — basemap tiles
- **[OpenStreetMap](https://www.openstreetmap.org/)** — underlying map data
- **Inter** + **Fraunces** via Google Fonts
- **[Cloudflare Workers](https://workers.cloudflare.com/)** static assets — hosting

## License

MIT — see [LICENSE](LICENSE).
