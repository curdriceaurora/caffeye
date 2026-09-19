# Coffee in Duluth — Test Suite

Each test is traced to a requirement in `REQUIREMENTS.md`. Tests are split into:

- **Static data checks** — runnable as JS snippets against the loaded page, no UI interaction.
- **Behavioral / UI checks** — manual steps with explicit pass criteria, or browser-automation pseudocode.
- **Visual checks** — eyeball-test at specified zoom + viewport.

Snippets prefixed with `js>` are meant to be pasted into the page's DevTools console (or run via a Playwright/Puppeteer `evaluate` call) — they assume `SHOPS`, `CATS`, `CWS`, `LATE`, `WEBSITES`, `map`, `markers`, and `clusterGroup` are defined globals.

## How to run

Local: `python3 -m http.server 8765` in the project root, open `http://127.0.0.1:8765/`. For mobile-breakpoint tests, narrow the window or use DevTools device emulation. Use the production URL `https://duluth-coffee-shoppes.sra-e69.workers.dev` for end-to-end checks.

---

## T1. Data integrity (R1)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T1.1 | R1.1 | `js> SHOPS.length` | `61` (Sept 2026 — equals the count in the header) |
| T1.2 | R1.2 | `js> SHOPS.every(s => s.name && s.address && s.lat && s.lng && s.category && s.hours && s.usp && s.signature && Array.isArray(s.loved) && s.loved.length === 3 && s.googleUrl && s.yelpUrl)` | `true` |
| T1.3 | R1.2 | `js> SHOPS.filter(s => !s.lat \|\| !s.lng \|\| s.lat === 0).length` | `0` |
| T1.4 | R1.3 | `js> SHOPS.every(s => s.cw && ['excellent','good','limited'].includes(s.cw.tier))` | `true` |
| T1.5 | R1.4 | `js> SHOPS.every(s => 'website' in s)` | `true` |
| T1.6 | R1.5 | `js> SHOPS.filter(s => s.late).every(s => ['10pm+','midnight'].includes(s.late.tier) && typeof s.late.when === 'string')` | `true` |
| T1.7 | R1.6 | `js> SHOPS.filter(s => !s.addrKey.startsWith(s.city.toLowerCase() + '-'))` | `[]` |
| T1.8 | R1.7 | `js> SHOPS.filter(s => !CATS[s.category]).map(s => s.name)` | `[]` |
| T1.9 | R1.9 | Open page, check header text. | Reads "**61** spots in Duluth · verified **September 2026**" (count = `SHOPS.length`, month = `checkedMonth`). |

## T2. Map setup (R2)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T2.1 | R2.1 | `js> typeof L !== 'undefined' && typeof L.markerClusterGroup === 'function'` | `true` |
| T2.2 | R2.2 | Hard reload, wait 1.5 s, then `js> { let v = map.getBounds(); SHOPS.filter(s => !v.contains([s.lat, s.lng])).length }` | `0` (all `SHOPS.length` in viewport) |
| T2.3 | R2.3 | `js> document.querySelectorAll('.pin').length > 0 && [...document.querySelectorAll('.pin')].every(p => p.textContent.length > 0)` | `true` (every visible pin shows its emoji) |
| T2.4 | R2.4 | `js> document.querySelectorAll('.pin.late').length > 0` | `true` (≥ 1 late pin visible) |
| T2.5 | R2.5 | Click a pin. Check `js> document.querySelectorAll('.pin.selected').length === 1` | `true` |
| T2.6 | R2.6 | `js> document.querySelectorAll('.coffee-cluster').length` | `≥ 1` at zoom 13 |
| T2.7 | R2.7 | `js> { const same = SHOPS.filter(s => s.name === 'Alchemist on the Divide' \|\| s.name === 'Ginkgo Bakery & Cafe').map(s => [s.lat, s.lng]); Math.abs(same[0][0] - same[1][0]) + Math.abs(same[0][1] - same[1][1]) > 0 }` | `true` (same-address pins are nudged apart) |
| T2.8 | R2.8 | Click a pin. | The detail card opens directly; no preview popup appears. |
| T2.9 | R2.9 | Click a pin, then "← Back to list". | Map fits all markers again. |

## T3. Pin labels (R3)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T3.1 | R3.1 | At zoom 17, `js> document.querySelectorAll('.pin-label:not([style*="hidden"])').length > 0` | `true` |
| T3.2 | R3.2 | `js> map.setView([33.972, -84.142], 12); map.getContainer().classList.contains('with-labels')` then in 500 ms | `false` |
| T3.2b | R3.2 | `js> map.setView([33.972, -84.142], 13); map.getContainer().classList.contains('with-labels')` then in 500 ms | `true` |
| T3.3-7 | R3.3–R3.7 | At zoom 17, run the no-overlap script (below). | All counts `0`. |
| T3.8 | R3.8 | Click a category chip to filter, then re-check. | Labels stay valid (no orphaned labels for hidden pins). |
| T3.9 | R3.9 | Run the label-safety-cap script (below). | `{ over: true, atCap: false }` |

**No-overlap script:**

```js
// Run at zoom ≥ 16 after settling
(function () {
  const labels = [...document.querySelectorAll('.pin-label')]
    .filter(l => l.style.visibility !== 'hidden' && l.offsetParent !== null);
  const clusters = [...document.querySelectorAll('.coffee-cluster')];
  const pins = [...document.querySelectorAll('.pin')];
  const olap = (a, b) =>
    !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom);

  let labelLabel = 0, labelCluster = 0;
  const lr = labels.map(l => ({ n: l.textContent, r: l.getBoundingClientRect() }));
  const cr = clusters.map(c => c.getBoundingClientRect());

  for (let i = 0; i < lr.length; i++)
    for (let j = i + 1; j < lr.length; j++)
      if (olap(lr[i].r, lr[j].r)) labelLabel++;
  lr.forEach(l => cr.forEach(c => { if (olap(l.r, c)) labelCluster++; }));

  console.log({ visibleLabels: lr.length, labelLabel, labelCluster });
})();
```

Expected output: `{ visibleLabels: N, labelLabel: 0, labelCluster: 0 }`.

**Label-safety-cap script:** a real integration test of `placeLabels()`'s 300-pin
guard (R3.9) — genuine DOM writes to genuine label elements, positioned on a grid
wide enough that the normal collision pass would actually succeed for most of
them, so "not all hidden" at 300 is a meaningful recovery signal and not just the
absence of the guard. `placeLabels()` accepts an item-list override for exactly
this: constructing 301 real shops simultaneously unclustered on one screen isn't
practical in any current fixture (see T3.9's old wording, replaced by this).

```js
(function () {
  function makeItem(i) {
    const pin = document.createElement('div');
    const label = document.createElement('div');
    pin.style.cssText = `position:fixed;left:${(i % 20) * 60}px;top:${Math.floor(i / 20) * 60}px;width:10px;height:10px;`;
    label.style.cssText = 'position:fixed;left:0;top:0;width:40px;height:14px;';
    document.body.appendChild(pin);
    document.body.appendChild(label);
    return { pin, label, shop: { id: 'test-' + i, weightedRating: i } };
  }
  const items301 = Array.from({ length: 301 }, (_, i) => makeItem(i));
  placeLabels(items301);
  const over = items301.every(it => it.label.style.visibility === 'hidden');

  const items300 = items301.slice(0, 300);
  items300.forEach(it => { it.label.style.visibility = ''; it.label.style.transform = ''; });
  placeLabels(items300);
  const atCap = items300.every(it => it.label.style.visibility === 'hidden');

  items301.forEach(it => { it.pin.remove(); it.label.remove(); }); // cleanup
  console.log({ over, atCap });
})();
```

Expected output: `{ over: true, atCap: false }` — 301 unclustered pins forces every
label hidden without running the collision pass; 300 does not (at least some of
the grid-spaced items find a placement), proving the guard's threshold and its
recovery, not just the threshold function in isolation.

## T4. Filter chips (R4)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T4.1 | R4.1 | `js> document.querySelectorAll('#categoryChips .chip').length` | `6` (All + 5 categories) |
| T4.2 | R4.1 | Each category chip displays its emoji + label + count; sum of category counts = `SHOPS.length`. | Recount per the live build; the five counts must sum to `SHOPS.length` (61 as of Sept 2026). |
| T4.3 | R4.2 | Click "All". `js> [...document.querySelectorAll('#categoryChips .chip')][0].classList.contains('active')` | `true` |
| T4.4 | R4.3 | `js> document.querySelectorAll('#featureChips .chip').length` | `6` (Indie, Franchise, plus 4 features) |
| T4.5 | R4.3 | Feature chip text matches `['🌱Indie{n}', '🏢Franchise{n}', '💻Work-friendly{n}', '🤝Meeting room{n}', '🌙Open late{n}', '🦉Until midnight{n}']` (spaces normalized). | All six present. |
| T4.6 | R4.4 | Click "Coffee" then "Work-friendly". `js> document.querySelectorAll('.shop-item').length` | Returns count of Coffee × Work-friendly intersection. |
| T4.7 | R4.5 | Search the page DOM for "Past midnight". | Returns no matches. |
| T4.8 | R4.6 | `js> !document.getElementById('sortSelect')` | `true` |
| T4.9 | R4.7 | `js> COUNTIES.length` on single-region data (no `county` field on any shop). | `0` — county chips absent, `#locationRow` shows City chips only (or hides entirely on today's single-city Duluth data, since `showCityRow` is also false). |
| T4.10 | R4.7 | On multi-county data with no county selected: `js> document.querySelectorAll('#locationChips .chip').length` | Equals `COUNTIES.length + 1` (just the county chips: "All counties" + one per county) — City chips are not shown yet. County ⊇ City, so showing every city across every county at the same time as every county is redundant, and was measured to cost mobile a visible card (see T8.x). |
| T4.11 | R4.7 | `js> selectCounty('Gwinnett'); document.getElementById('resultsCount').textContent === String(SHOPS.filter(s => s.county === 'Gwinnett').length)` | `true` — and City chips now appear (drilled down to Gwinnett's cities only), separated from the county chips by a `.chip-divider`. |
| T4.12 | R4.7 | County and City chips are both children of one `#locationChips` container (a single flex-wrap sequence), not two separately-wrapping sub-containers. | Splitting one row's width between two independently-wrapping boxes was measured to wrap *more* than the combined content needs (74px vs. 48px tall at 375px, same chip set) — packing them as one sequence fixes it. |
| T4.13 | R4.8 | Click "🌱 Indie". Check `document.querySelectorAll('.shop-item').length`. | Matches count on Indie chip; all rendered cards have `.model-tag.indie`. |
| T4.14 | R4.8 | Click "🏢 Franchise". Check `document.querySelectorAll('.shop-item').length`. | Matches count on Franchise chip; all rendered cards have `.model-tag.franchise`. |

## T5. Right-side list (R5)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T5.1 | R5.1 | Hard reload, after settle: `js> document.querySelectorAll('.shop-item').length` | `SHOPS.length` (61 as of Sept 2026) |
| T5.2 | R5.2 | First 3 list items by name. | Top of list reflects weighted-rating order (Yibna Cafe, Incha Duluth, Georgia French Bakery as of Sept 2026). |
| T5.3 | R5.2 | `js> Math.abs(SHOPS.filter(s=>typeof s.rating==='number').reduce((a,s)=>a+s.rating,0)/SHOPS.filter(s=>typeof s.rating==='number').length - 4.5) < 0.1` | `true` (C ≈ 4.5) |
| T5.4 | R5.3 | `js> SHOPS.filter(s => s.rating == null).every(s => typeof s.weightedRating === 'number')` | `true` (vacuously true while every shop is rated — as of Sept 2026 none is null; the branch is exercised whenever one is) |
| T5.5 | R5.4 | Inspect any list item. | Shows: colored circular icon tile, name, meta row, ≤ 3 tags. |
| T5.5b | R5.4 | Hard reload, no chips, no search (all shops in viewport). `js> document.querySelector('.shop-item .score').textContent === '◆ ' + Math.max(...SHOPS.map(s => s.weightedRating)).toFixed(1)` | `true` |
| T5.5c | R5.4 | `js> [...document.querySelectorAll('.shop-item .score')].map(e => +e.textContent.slice(2)).every((v, i, a) => i === 0 \|\| a[i-1] >= v)` | `true` — displayed scores never increase down the list (order uses full precision, display rounds). |
| T5.5d | R5.4 | `js> [...document.querySelectorAll('.shop-meta')].every(m => !m.innerHTML.includes('★')) && document.querySelector('.results-meta .score-legend').textContent === '◆ = weighted score'` | `true` — no ★ anywhere on a card (attributes included); the legend is present. |
| T5.6 | R5.5 | `js> document.querySelector('.shop-item').style.borderLeftColor` | Non-empty (a category color). |
| T5.7 | R5.6 | Filter to "Meeting room". `js> document.getElementById('resultsCount').textContent` | `"4"` |
| T5.7b | R5.6 | Hard reload (all shops in viewport). `js> document.getElementById('resultsLabel').textContent` | `" spots"` |
| T5.7c | R5.6 | Zoom in until fewer than `SHOPS.length` shops are visible in the map. `js> document.getElementById('resultsLabel').textContent` | `" in view"` |
| T5.8 | R5.7 | Scroll the shop list. | Inner list scrolls; header, filters, map don't. |
| T5.9 | R5.8 | Set zoom 18 in an empty area + search "xyzqwerty". | Empty state reads: "Nothing here — try zooming out or clearing a filter." |
| T5.10 | R5.9 | Open DevTools → Elements. After any pan/zoom, inspect first `.shop-item`. | Has `animation-delay` inline style ≥ 0ms and CSS animation `itemEnter`. |
| T5.11 | R5.9 | After a viewport-triggered list refresh, inspect `.results-meta`. | Briefly has class `viewport-flash`, then class is removed after `transitionend`. |
| T5.12 | R5.10 | On data with > 200 matching shops (e.g. all-counties view, no filters): `js> document.querySelectorAll('.shop-item').length` | `200`, plus one `.load-more-btn` reading "Load N more (N left)". |
| T5.13 | R5.10 | Click `.load-more-btn` repeatedly until it disappears. | `js> document.querySelectorAll('.shop-item').length === document.getElementById('resultsCount').textContent - 0` — all matches eventually render; scores stay monotonic across the full list (T5.5c still holds). |
| T5.14 | R5.10 | With the list paginated (> 200 matches), type in the search box. | List resets to the first page of the new result set — no stale "Load more" pointing at the old filter's remainder. |
| T5.15 | R5.10 | `js> document.querySelector('.load-more-btn').click(); document.activeElement.tagName === 'LI' && document.activeElement.dataset.id && [...document.querySelectorAll('.shop-item')].indexOf(document.activeElement) === 200` | `true` — activating "Load more" (`renderList()` rebuilds the whole `<ul>`, which would otherwise drop focus to `<body>`) moves focus to the first newly-revealed card, not off the list entirely. Real keyboard users trigger this via Enter/Space on the focused button, which the browser turns into the same `click` event this test fires directly. |

## T6. Detail card (R6)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T6.1 | R6.1 | Click any list item. | Detail card slides in from the right while list slides left; no jump/flash. |
| T6.10 | R6.1 | While detail is open: `js> getComputedStyle(document.querySelector('.list-view')).opacity` | `"0"` (compositor-hidden, not `display:none`) |
| T6.2 | R6.2 | Inspect a high-rated shop card (e.g. Bread Museum). | Shows category + neighborhood badge, name as `<h2>`, a large `◆ n.n` with the label "weighted score", a muted line `Google ★ n.n · N reviews` beneath it (always one decimal, exact count, no `+`), USP paragraph. |
| T6.3 | R6.3 | Open Cafe Rothem. | "Best for" pills include 💻 Work and 🤝 Meetings. |
| T6.4 | R6.3 | Open Hayat Coffee. | "Best for" includes 💻 Work and 🦉 Until midnight. |
| T6.5 | R6.4 | Every detail view has a "Known for" pill row and a "Try the **X**" line. | True for every shop. |
| T6.6 | R6.6 | Open Sweet Hut. | Coworking section shows "Coworking-ready" + meeting-room callout. |
| T6.7 | R6.7 | Open a shop without late hours (e.g. Land of a Thousand Hills). | No Late-night section. |
| T6.8 | R6.8 | Every detail view has Google Maps + Yelp action buttons, and a Website button when the shop has a URL. | True. |
| T6.9 | R6.9 | Click "← Back to list". | Detail hides, list returns, map fits bounds. |

## T7. Search (R7)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T7.1 | R7.1 | Visible above the list. | Yes. |
| T7.2 | R7.2 | Search "matcha". `js> document.querySelectorAll('.shop-item').length` | `≥ 10` (matches shops mentioning matcha in name/USP/loved/signature). |
| T7.3 | R7.2 | Search "boggs". | Returns Cafe Flat (mentions "Hwy 120 & Boggs Rd" in USP). |
| T7.4 | R7.3 | Search "MATCHA" (upper). | Same result as lowercase. |

## T8. Responsive layout (R8)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T8.1 | R8.1 | Window width ≥ 821 px. | Map left + 380 px panel right. |
| T8.2 | R8.2 | Width 390 px (mobile). | Column layout: map on top (220 px), panel below filling remainder. |
| T8.3 | R8.3 | At 390 px width, chip computed font-size. | `11.5px`. |
| T8.4 | R8.4 | At 390 px width: `js> getComputedStyle(document.querySelector('footer')).display` | `"none"`. |
| T8.5 | R8.5 | Mobile, 375×812 viewport, single-region data (`#locationRow` hidden — true of every dataset shipped today). Count *fully* visible cards (not merely intersecting the viewport): `js> (() => { const r = document.getElementById('shopList').getBoundingClientRect(); return [...document.querySelectorAll('.shop-item')].filter(li => { const cr = li.getBoundingClientRect(); return cr.top >= r.top - 0.5 && cr.bottom <= r.bottom + 0.5; }).length; })()` | `5` (measured: 356 px available ÷ 68.64 px/card). |
| T8.5b | R8.5 | Same viewport and card-count snippet, with multi-county data so `#locationRow` is showing. | `4` (measured: 308 px available ÷ 68.64 px/card — the row itself is ~48 px, not clawed back from card spacing shared with T8.5's baseline). A looser "any pixel intersects the viewport" count would read 5 here too and hide this; T8.5/T8.5b must both use the strict full-visibility definition to be comparable. |

## T9. Performance & errors (R9)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T9.1 | R9.1 | File size of `index.html`. | `≤ 100 KB`. |
| T9.2 | R9.2 | Load with DevTools console open. Click around, zoom, filter. | No errors logged. |
| T9.3 | R9.3 | Network tab on hard reload. | Leaflet CSS/JS + MarkerCluster CSS/JS + Google Fonts all return 200; the two SRI'd files match their hashes. |
| T9.4 | R9.4 | `open index.html` directly from filesystem (no server). | Page loads and map renders. |
| T9.5 | R9.5 | DevTools → Performance: record a list↔detail click and a zoom/pan. | Frames row stays green (60fps). No `Layout` or `Paint` blocks during the panel transition. Compositor thread handles the slide. |

## T10. Deployment (R10)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T10.1 | R10.1 | `curl -I https://duluth-coffee-shoppes.sra-e69.workers.dev/` | 200 OK, content-type text/html. |
| T10.2 | R10.2 | `cd /tmp/cof-clean && wrangler deploy` | Uploads 1 file only (`index.html`). |
| T10.3 | R10.3 | `curl -o /dev/null -w '%{http_code}' https://.../wrangler.jsonc` and `.../.wrangler/cache/wrangler-account.json` | Both `404`. |

---

## Regression checklist (post-deploy smoke test)

Run after every `wrangler deploy`:

1. Open the live URL on desktop. Expect `SHOPS.length` markers (61 as of Sept 2026), all 5 category chips, 4 feature chips, the full list sorted by weighted rating. Results header reads "61 spots".
2. Click Bread Museum → detail card slides in (list slides left). Click "← Back to list" → list slides back in, map fits bounds.
3. Click "Until midnight" → expect 8 shops (TwoHa's, Hayat, Cafe Mozart, The Coffee By Hand, The Bep Teahouse, Hansel & Gretel, Qamaria Yemeni, Glaze Tea).
4. Search "matcha" → ≥ 10 results.
5. Zoom in until fewer than all shops appear in the list. Confirm header changes to "X in view" and list items cascade in. Zoom back out — header returns to "61 spots".
6. Resize window below 820 px → mobile layout kicks in, footer disappears, ≥ 5 cards visible.
7. Zoom in to a single shop, confirm label appears with no overlap. Zoom out to default fit, confirm clusters reform.
8. Open DevTools console → no errors.

## Known-good fixture data (May 2026)

| Field | Value |
|---|---|
| Total shops | 61 (Sept 2026) |
| Category counts | Coffee 10, Bakery & Cafe 18, Tea/Boba 14, Dessert Cafe 11, Specialty 6 |
| Work-friendly | 19 |
| Meeting room | 4 |
| Open late | 39 |
| Until midnight | 8 |
| Bayesian C | ≈ 4.50 |
| Bayesian m | 230 (median review count) |
| #1 by weighted rating | Yibna Cafe (Sept 2026; Georgia French Bakery & Cafe before the Places API refresh) |
| Unique buildings (ADDR keys) | 42 |
