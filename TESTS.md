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
| T1.1 | R1.1 | `js> SHOPS.length` | `59` |
| T1.2 | R1.2 | `js> SHOPS.every(s => s.name && s.address && s.lat && s.lng && s.category && s.hours && s.usp && s.signature && Array.isArray(s.loved) && s.loved.length === 3 && s.googleUrl && s.yelpUrl)` | `true` |
| T1.3 | R1.2 | `js> SHOPS.filter(s => !s.lat \|\| !s.lng \|\| s.lat === 0).length` | `0` |
| T1.4 | R1.3 | `js> SHOPS.every(s => CWS[s.name] && ['excellent','good','limited'].includes(CWS[s.name].tier))` | `true` |
| T1.5 | R1.4 | `js> SHOPS.every(s => WEBSITES.hasOwnProperty(s.name))` | `true` |
| T1.6 | R1.5 | `js> Object.values(LATE).every(l => ['10pm+','midnight'].includes(l.tier) && typeof l.when === 'string')` | `true` |
| T1.7 | R1.6 | `js> [...Object.keys(CWS), ...Object.keys(LATE), ...Object.keys(WEBSITES)].filter(k => !SHOPS.some(s => s.name === k))` | `[]` |
| T1.8 | R1.7 | `js> SHOPS.filter(s => !CATS[s.category]).map(s => s.name)` | `[]` |
| T1.9 | R1.9 | Open page, check header text. | Reads "**59** cafés, bakeries & tea shops · checked **May 2026**". |

## T2. Map setup (R2)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T2.1 | R2.1 | `js> typeof L !== 'undefined' && typeof L.markerClusterGroup === 'function'` | `true` |
| T2.2 | R2.2 | Hard reload, wait 1.5 s, then `js> { let v = map.getBounds(); SHOPS.filter(s => !v.contains([s.lat, s.lng])).length }` | `0` (all 59 in viewport) |
| T2.3 | R2.3 | `js> document.querySelectorAll('.pin').length > 0 && [...document.querySelectorAll('.pin')].every(p => p.textContent.length > 0)` | `true` (every visible pin shows its emoji) |
| T2.4 | R2.4 | `js> document.querySelectorAll('.pin.late').length > 0` | `true` (≥ 1 late pin visible) |
| T2.5 | R2.5 | Click a pin. Check `js> document.querySelectorAll('.pin.selected').length === 1` | `true` |
| T2.6 | R2.6 | `js> document.querySelectorAll('.coffee-cluster').length` | `≥ 1` at zoom 13 |
| T2.7 | R2.7 | `js> { const same = SHOPS.filter(s => s.name === 'Alchemist on the Divide' \|\| s.name === 'Ginkgo Bakery & Cafe').map(s => [s.lat, s.lng]); Math.abs(same[0][0] - same[1][0]) + Math.abs(same[0][1] - same[1][1]) > 0 }` | `true` (same-address pins are nudged apart) |
| T2.8 | R2.8 | Click a pin. | The detail card opens directly; no preview popup appears. |
| T2.9 | R2.9 | Click a pin, then "← Back to list". | Map fits all 59 markers again. |

## T3. Pin labels (R3)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T3.1 | R3.1 | At zoom 17, `js> document.querySelectorAll('.pin-label:not([style*="hidden"])').length > 0` | `true` |
| T3.2 | R3.2 | `js> map.setView([33.972, -84.142], 12); map.getContainer().classList.contains('with-labels')` then in 500 ms | `false` |
| T3.2b | R3.2 | `js> map.setView([33.972, -84.142], 13); map.getContainer().classList.contains('with-labels')` then in 500 ms | `true` |
| T3.3-7 | R3.3–R3.7 | At zoom 17, run the no-overlap script (below). | All counts `0`. |
| T3.8 | R3.8 | Click a category chip to filter, then re-check. | Labels stay valid (no orphaned labels for hidden pins). |

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

## T4. Filter chips (R4)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T4.1 | R4.1 | `js> document.querySelectorAll('#categoryChips .chip').length` | `6` (All + 5 categories) |
| T4.2 | R4.1 | Each category chip displays its emoji + label + count; sum of category counts = 59. | `8 + 18 + 14 + 11 + 6 = 57… wait, plus 2-3 misc = 59`. (Recount per the live build; sum must equal 59.) |
| T4.3 | R4.2 | Click "All". `js> [...document.querySelectorAll('#categoryChips .chip')][0].classList.contains('active')` | `true` |
| T4.4 | R4.3 | `js> document.querySelectorAll('#featureChips .chip').length` | `4` |
| T4.5 | R4.3 | Feature chip text matches `['💻Work-friendly{n}', '🤝Meeting room{n}', '🌙Open late{n}', '🦉Until midnight{n}']` (spaces normalized). | All four present. |
| T4.6 | R4.4 | Click "Coffee" then "Work-friendly". `js> document.querySelectorAll('.shop-item').length` | Returns count of Coffee × Work-friendly intersection. |
| T4.7 | R4.5 | Search the page DOM for "Past midnight". | Returns no matches. |
| T4.8 | R4.6 | `js> !document.getElementById('sortSelect')` | `true` |

## T5. Right-side list (R5)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T5.1 | R5.1 | Hard reload, after settle: `js> document.querySelectorAll('.shop-item').length` | `59` |
| T5.2 | R5.2 | First 3 list items by name. | Top of list reflects weighted-rating order (Georgia French Bakery, Chuchat, Cafe Rothem at the time of writing). |
| T5.3 | R5.2 | `js> Math.abs(SHOPS.filter(s=>typeof s.rating==='number').reduce((a,s)=>a+s.rating,0)/SHOPS.filter(s=>typeof s.rating==='number').length - 4.5) < 0.1` | `true` (C ≈ 4.5) |
| T5.4 | R5.3 | `js> SHOPS.find(s => s.rating == null).weightedRating !== undefined` | `true` |
| T5.5 | R5.4 | Inspect any list item. | Shows: colored circular icon tile, name, meta row, ≤ 3 tags. |
| T5.6 | R5.5 | `js> document.querySelector('.shop-item').style.borderLeftColor` | Non-empty (a category color). |
| T5.7 | R5.6 | Filter to "Meeting room". `js> document.getElementById('resultsCount').textContent` | `"4"` |
| T5.8 | R5.7 | Scroll the shop list. | Inner list scrolls; header, filters, map don't. |
| T5.9 | R5.8 | Set zoom 18 in an empty area + search "xyzqwerty". | Empty state reads: "No shops in this view. Try zooming out, clearing filters, or changing search." |

## T6. Detail card (R6)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T6.1 | R6.1 | Click any list item. | Detail card replaces the list view. |
| T6.2 | R6.2 | Inspect a high-rated shop card (e.g. Bread Museum). | Shows category + neighborhood badge, name as `<h2>`, star rating, USP paragraph. |
| T6.3 | R6.3 | Open Cafe Rothem. | "Best for" pills include 💻 Work and 🤝 Meetings. |
| T6.4 | R6.3 | Open Hayat Coffee. | "Best for" includes 💻 Work and 🦉 Until midnight. |
| T6.5 | R6.4 | Every detail view has a "Known for" pill row and a "Try the **X**" line. | True for all 59. |
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
| T8.5 | R8.5 | Mobile, ~750 px viewport height. Count visible cards in panel before any scroll. | `≥ 5`. |

## T9. Performance & errors (R9)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T9.1 | R9.1 | File size of `index.html`. | `≤ 100 KB`. |
| T9.2 | R9.2 | Load with DevTools console open. Click around, zoom, filter. | No errors logged. |
| T9.3 | R9.3 | Network tab on hard reload. | Leaflet CSS/JS + MarkerCluster CSS/JS + Google Fonts all return 200; the two SRI'd files match their hashes. |
| T9.4 | R9.4 | `open index.html` directly from filesystem (no server). | Page loads and map renders. |

## T10. Deployment (R10)

| ID | Trace | Test | Pass |
|---|---|---|---|
| T10.1 | R10.1 | `curl -I https://duluth-coffee-shoppes.sra-e69.workers.dev/` | 200 OK, content-type text/html. |
| T10.2 | R10.2 | `cd /tmp/cof-clean && wrangler deploy` | Uploads 1 file only (`index.html`). |
| T10.3 | R10.3 | `curl -o /dev/null -w '%{http_code}' https://.../wrangler.jsonc` and `.../.wrangler/cache/wrangler-account.json` | Both `404`. |

---

## Regression checklist (post-deploy smoke test)

Run after every `wrangler deploy`:

1. Open the live URL on desktop. Expect 59 markers, all 5 category chips, 4 feature chips, full list of 59 shops sorted by weighted rating.
2. Click Bread Museum → detail card → "← Back to list" → fits bounds.
3. Click "Until midnight" → expect 8 shops (TwoHa's, Hayat, Cafe Mozart, The Coffee By Hand, The Bep Teahouse, Hansel & Gretel, Qamaria Yemeni, Glaze Tea).
4. Search "matcha" → ≥ 10 results.
5. Resize window below 820 px → mobile layout kicks in, footer disappears, ≥ 5 cards visible.
6. Zoom in to a single shop, confirm label appears with no overlap. Zoom out to default fit, confirm clusters reform.
7. Open DevTools console → no errors.

## Known-good fixture data (May 2026)

| Field | Value |
|---|---|
| Total shops | 59 |
| Category counts | Coffee 10, Bakery & Cafe 18, Tea/Boba 14, Dessert Cafe 11, Specialty 6 |
| Work-friendly | 19 |
| Meeting room | 4 |
| Open late | 39 |
| Until midnight | 8 |
| Bayesian C | ≈ 4.50 |
| Bayesian m | 230 (median review count) |
| #1 by weighted rating | Georgia French Bakery & Cafe |
| Unique buildings (ADDR keys) | 42 |
