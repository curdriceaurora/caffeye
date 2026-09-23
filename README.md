# caffeye

caffeye is a map of coffee shops, bakeries, and tea houses in **Metro Atlanta**. It is one web page. Use it to find a good place quickly.

🌐 **Live site:** <https://duluth-coffee-shoppes.sra-e69.workers.dev>

![category count](https://img.shields.io/badge/categories-6-b89464) ![host](https://img.shields.io/badge/hosted%20on-Cloudflare%20Workers-orange)

## Description

The application is a static HTML page. It has no build step and no backend. It uses Leaflet and Leaflet.markercluster from a CDN.

The map shows each venue as a pin. The color and the emoji of the pin show the category. There are six categories: Coffee, Roasters, Bakery+Cafe, Tea/Boba, Dessert Cafe, and Specialty.

You can filter the venues by category. You can also filter by these features:

- Work-friendly
- Meeting rooms
- Open late
- Until midnight

The list shows only the venues that are in the map view. The list order is the Bayesian weighted rating, from high to low. This formula is the same as the IMDB Top 250 formula. The list does not have a sort control.

## Data

The September 2026 dataset has 1,705 venues in 14 counties. The page shows 970 independent venues by default. To show all 1,705 venues, set the **Include franchise stores** toggle to on.

The data comes from two files:

- `public/shops.json` contains 61 curated seed venues in the Duluth area.
- `public/places.json` contains regional venues. A script makes this file from Google Places data.

If the page cannot load the regional data, it shows the 61 seed venues. By default, 41 of these venues are independent. A banner tells you that the coverage is partial.

The page calculates all counts, the region name, and the verification month from the JSON files. These counts are for September 2026 only. After a data refresh, use the data-summary procedure in [TESTS.md](TESTS.md) to get the new counts.

## Documents

- [PRODUCT.md](PRODUCT.md) gives the product principles and the design decisions.
- [REQUIREMENTS.md](REQUIREMENTS.md) gives the numbered requirements.
- [TESTS.md](TESTS.md) gives the tests for each requirement.
- [DESIGN.md](DESIGN.md) gives the visual design system.
- [CLAUDE.md](CLAUDE.md) gives the operation notes and the data scripts.

## Run the page on your computer

The page loads JSON files. Thus, you must use an HTTP server. Do not open the file directly.

1. Go to the `public` directory in the repository:

   ```sh
   cd public
   ```

2. Start the server:

   ```sh
   python3 -m http.server 8765
   ```

3. Open <http://127.0.0.1:8765> in a browser.

To see the vector map preview, add `?renderer=vector` to the URL. This preview uses MapLibre GL JS and OpenFreeMap tiles.

## Run the tests

Do these steps in the repository root:

1. Install the dependencies:

   ```sh
   npm ci
   ```

2. Install the Playwright browser:

   ```sh
   npx playwright install chromium
   ```

3. Run the tests:

   ```sh
   npm test
   ```

The `npm test` command runs the Python unit tests first. Then it runs the Playwright browser tests. GitHub Actions runs the same tests for each push and each pull request to `main`.

## Deploy

Cloudflare Workers static assets hosts the site. When you push to `main`, Cloudflare deploys the site automatically.

The `wrangler.jsonc` file sets `assets.directory` to `./public/`. Cloudflare publishes only the files in `public/`. The scripts and the documents stay private.

To deploy manually (for example, for an urgent fix), do this command in the repository root:

```sh
wrangler deploy
```

> ⚠️ **Warning:** Do not run `wrangler deploy` in the `public/` directory. Wrangler publishes all files in the assets directory. The `.wrangler/` cache contains an OAuth token. If this cache is in `public/`, Wrangler publishes the token.

## Add or change a venue

1. Add curated venues to `public/shops.json`. Each venue must have these data:
   - A category and a business model (`independent` or `franchise`)
   - A `cw` block for the work data
   - A `late` block, if the venue is open after 10 pm
   - A `website` value
2. For a new building, add its coordinates to `addr`. Add its area to `neighborhoods`.
3. Get curated coordinates from Apple Maps (`CLGeocoder`). Do not estimate coordinates. For more data, see `PRODUCT.md` §8.
4. Do not edit `public/places.json` manually. A script makes this file. To change the regional data, edit `scripts/curations.json`. Then run `scripts/discover_places.py` in replay mode. [CLAUDE.md](CLAUDE.md) gives the procedure.
5. Change `checkedMonth` only after you verify the data of that source.
6. Do the checks in [TESTS.md](TESTS.md). Check the page with the franchise toggle on and off. Also check the fallback and the **Retry** button.

To find venues that need editorial research, run this command:

```sh
python3 scripts/curate_places.py --research-queue
```

The command shows the ten highest-ranked independent venues that do not have work data. It shows the place ID, the address, and the website and map links of each venue. The command does not use the network and does not change data. Verify the amenities before you add an overlay.

## Project structure

```
caffeye/
├── public/                   # published files only
│   ├── index.html            # application shell; loads the two datasets
│   ├── maplibre-preview.js   # optional ?renderer=vector preview
│   ├── shops.json            # curated Duluth seed and fallback data
│   ├── places.json           # regional data that a script makes
│   ├── manifest.webmanifest  # PWA manifest
│   ├── favicon.ico
│   └── brand/                # logos, icons, social images, and tokens
├── brand/                    # source brand packages
├── scripts/                  # discovery, curation, rating refresh, and Python tests
├── tests/                    # Playwright browser tests
├── .github/workflows/ci.yml  # GitHub Actions test workflow
├── package.json              # test commands
├── playwright.config.js      # Playwright configuration
├── wrangler.jsonc            # Cloudflare configuration (assets.directory = ./public)
├── README.md                 # this file
├── PRODUCT.md                # product principles and design decisions
├── REQUIREMENTS.md           # numbered requirements
├── TESTS.md                  # tests for each requirement
├── DESIGN.md                 # visual design system
└── CLAUDE.md                 # operation notes for AI sessions
```

## Technology

- **[Leaflet 1.9.4](https://leafletjs.com/)**: open-source map library
- **[Leaflet.markercluster 1.5.3](https://github.com/Leaflet/Leaflet.markercluster)**: pin clusters
- **[CARTO basemaps](https://carto.com/help/building-maps/basemap-list/)**: map tiles (light and dark themes)
- **[OpenStreetMap](https://www.openstreetmap.org/)**: map data
- **[MapLibre GL JS 5.24.0](https://maplibre.org/)** and **[OpenFreeMap](https://openfreemap.org/)**: vector preview only (`?renderer=vector`)
- **Inter** and **Fraunces**: fonts from Google Fonts
- **[Cloudflare Workers](https://workers.cloudflare.com/)** static assets: hosting
- **[Playwright](https://playwright.dev/)**: browser tests

## License

MIT. See [LICENSE](LICENSE).
