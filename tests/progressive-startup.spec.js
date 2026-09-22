const { test, expect } = require('./helpers');

for (const renderer of ['leaflet', 'vector']) {
test(`${renderer}: seed remains interactive while region is pending; hydration preserves selection and camera`, async ({ page }) => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route('**/places.json', async route => {
    await pending;
    await route.continue();
  });
  try {
    await page.goto(renderer === 'vector' ? '/?renderer=vector' : '/');
    await expect(page.locator('.shop-item').first()).toBeVisible();
    await page.waitForFunction(() => window.mapReady);
    expect(await page.evaluate(() => window.renderer)).toBe(renderer);
    expect(await page.evaluate(() => dataLoadState.regional)).toBe('loading');
    await page.locator('#searchInput').fill('Hayat Coffee');
    await expect(page.locator('.shop-item')).toHaveCount(1);
    await page.locator('.shop-item').click();
    await expect(page.locator('#backBtn')).toBeFocused();
    const before = await page.evaluate(() => {
      map.stop();
      return { selected: state.selected.id, center: map.getCenter(), zoom: map.getZoom(), previous: state.previousCamera };
    });
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    expect(await page.evaluate(() => SHOPS.length)).toBeGreaterThan(1000);
    expect(await page.evaluate(() => ({ selected: state.selected.id, center: map.getCenter(), zoom: map.getZoom(), previous: state.previousCamera }))).toEqual(before);
    await expect(page.locator('#searchInput')).toHaveValue('Hayat Coffee');
    await expect(page.locator('#backBtn')).toBeFocused();
    const score = await page.evaluate(() => state.selected.scoreText);
    await expect(page.locator('#detailView .score')).toHaveText(`◆ ${score}`);
    await expect(page.locator('.shop-item .score')).toHaveText(`◆ ${score}`);
  } finally {
    release();
  }
});
}

test('untouched seed view expands when regional coverage arrives', async ({ page }) => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route('**/places.json', async route => { await pending; await route.continue(); });
  try {
    await page.goto('/');
    await expect(page.locator('.shop-item').first()).toBeVisible();
    const seedCount = await page.evaluate(() => SHOPS.length);
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    expect(await page.evaluate(() => SHOPS.length)).toBeGreaterThan(seedCount);
    await expect.poll(() => page.evaluate(() => Number(document.getElementById('resultsCount').textContent) === SHOPS.filter(s => s.model !== 'franchise').length)).toBe(true);
    const mapPinCount = await page.evaluate(() => clusterGroup.getLayers().length);
    const indieCount = await page.evaluate(() => SHOPS.filter(s => s.model !== 'franchise').length);
    expect(mapPinCount).toBe(indieCount);
    await expect(page.locator('#dataStatusBanner')).toHaveCount(0);
    await expect.poll(() => page.locator('#shopList').evaluate(el => el.scrollTop)).toBe(0);
  } finally { release(); }
});

test('seed failure still allows regional discovery', async ({ page }) => {
  await page.route('**/shops.json', route => route.abort());
  await page.goto('/');
  await expect(page.locator('.shop-item').first()).toBeVisible();
  await expect(page.locator('#dataStatusBanner')).toContainText('Showing regional spots');
  await expect(page.locator('[role="alert"]')).toHaveCount(0);
  expect(await page.evaluate(() => SHOPS.length)).toBeGreaterThan(1000);
});

test('failure of both datasets presents a blocking load error', async ({ page }) => {
  await page.route(/\/(shops|places)\.json$/, route => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toHaveText('Could not load spots. Please reload to try again.');
});

test('regional retry preserves filters, selection and unique venue ids', async ({ page }) => {
  await page.route('**/places.json', route => route.abort());
  await page.goto('/');
  await expect(page.locator('#retryPlacesBtn')).toBeVisible();
  await page.locator('#searchInput').fill('Hayat Coffee');
  await expect(page.locator('.shop-item')).toHaveCount(1);
  await page.locator('.shop-item').click();
  const selected = await page.evaluate(() => state.selected.id);
  await page.unroute('**/places.json');
  await page.locator('#retryPlacesBtn').click();
  await page.waitForFunction(() => dataLoadState.regional === 'ready');
  expect(await page.evaluate(() => state.selected.id)).toBe(selected);
  await expect(page.locator('#searchInput')).toHaveValue('Hayat Coffee');
  expect(await page.evaluate(() => new Set(SHOPS.map(s => s.id)).size === SHOPS.length)).toBe(true);
});

test('repeat visit hydrates regional data from cache in under 150ms', async ({ page }) => {
  await page.goto('/');
  await page.waitForFunction(() => dataLoadState.regional === 'ready');
  const hasCache = await page.evaluate(async () => {
    if (!('caches' in window)) return false;
    const cache = await caches.open('caffeye-v5');
    const match = await cache.match('./places.json');
    return !!match;
  });
  expect(hasCache).toBe(true);

  // Reload page and check that cache was hit
  await page.reload();
  await page.waitForFunction(() => dataLoadState.regional === 'ready');
  const cacheHit = await page.evaluate(() => {
    const log = window.__telemetryLog || [];
    return log.some(e => e.event === 'places_hydration' && e.properties.cache_hit === true && e.properties.duration_ms < 150);
  });
  expect(cacheHit).toBe(true);
});

