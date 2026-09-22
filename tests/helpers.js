const { test: base, expect } = require('@playwright/test');

// Shared fixture: every test fails on unhandled page errors or console
// errors, and gets navigation/selection helpers bound to the app's
// window-exposed singletons (see index.html Object.assign block).
const test = base.extend({
  page: async ({ page }, use) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
    page.on('console', (msg) => {
      // pageerror stays strict; network resource noise is covered by
      // functional assertions instead (e.g. the retry test aborts
      // places.json on purpose, and tile/CDN blips must not flake the suite).
      if (msg.type() === 'error' && !msg.text().startsWith('Failed to load resource')) {
        errors.push(`console: ${msg.text()}`);
      }
    });
    await use(page);
    expect(errors).toEqual([]);
  },
});

async function gotoHome(page, attempts = 3) {
  // python http.server occasionally resets a fresh connection; retry.
  let ok = false;
  for (let i = 0; i < attempts && !ok; i++) {
    try {
      await page.goto('/');
      ok = true;
    } catch (e) {
      if (i === attempts - 1) throw e;
      await page.waitForTimeout(500);
    }
  }
  await page.locator('.shop-item').first().waitFor({ timeout: 30000 });
}

async function openFirstDetail(page) {
  await page.locator('.shop-item').first().click();
  await page.locator('#backBtn').waitFor({ timeout: 15000 });
}

// Coordinates of the most isolated shop (renders as a marker, not a
// cluster, when zoomed in) — extracted from browser.spec.js.
async function findIsolatedShop(page) {
  return page.evaluate(() => {
    let best = null;
    let bestDist = -1;
    for (const s of window.SHOPS) {
      let nearest = Infinity;
      for (const t of window.SHOPS) {
        if (t === s) continue;
        const d = Math.hypot(s.lat - t.lat, s.lng - t.lng);
        if (d < nearest) nearest = d;
      }
      if (nearest > bestDist) { bestDist = nearest; best = s; }
    }
    return { lat: best.lat, lng: best.lng, name: best.name };
  });
}

async function detailMode(page) {
  return page.evaluate(() => document.getElementById('panel')?.classList.contains('detail-mode'));
}

// Fill search, wait for the card carrying `name`, and open it. Never clicks
// a stale pre-search card.
async function searchAndOpen(page, name) {
  await page.locator('#searchInput').fill(name);
  const card = page.locator('.shop-item', { hasText: name }).first();
  await card.waitFor({ timeout: 15000 });
  await card.click();
  await page.locator('#backBtn').waitFor({ timeout: 15000 });
}

// Click an outside-view expansion control until cards render (max 3 tries).
// A fitBounds issued while a previous zoom animation is still in flight can
// be swallowed by Leaflet; retrying is the same thing a user does.
async function expandMatches(page, btn) {
  for (let i = 0; i < 3; i++) {
    await btn.click();
    await page.waitForTimeout(1500);
    if ((await page.locator('.shop-item').count()) > 0) return;
  }
}

module.exports = { test, expect, gotoHome, openFirstDetail, findIsolatedShop, detailMode, searchAndOpen, expandMatches };
