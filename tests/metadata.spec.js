const { test, expect } = require('@playwright/test');

const descriptions = 'meta[name="description"], meta[property="og:description"], meta[name="twitter:description"]';

async function expectLoadedMetadata(page, region) {
  const { total, inScope } = await page.evaluate(() => ({
    total: SHOPS.length,
    inScope: SHOPS.filter(s => state.includeFranchises || s.model !== 'franchise').length,
  }));
  await expect(page.locator('.brand')).toHaveText(`Coffee in ${region}`);
  await expect(page).toHaveTitle(`Coffee in ${region}`);
  await expect(page.locator('.freshness')).toContainText(`${inScope} spots in ${region}`);
  for (const meta of await page.locator(descriptions).all()) {
    await expect(meta).toHaveAttribute('content', `${total.toLocaleString('en-US')} coffee, bakery & tea spots in ${region}. Filter by work-friendly, meeting room, or late hours.`);
  }
  for (const meta of await page.locator('meta[property="og:title"], meta[name="twitter:title"]').all()) {
    await expect(meta).toHaveAttribute('content', `Caffeye — Coffee in ${region}`);
  }
}

test('first paint shows the regional shell without a count while data loads', async ({ page }) => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route(/\/(shops|places)\.json$/, async route => {
    await pending;
    await route.continue();
  });
  try {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.brand')).toHaveText('Metro Atlanta');
    await expect(page.locator('.freshness')).toHaveText('Loading Metro Atlanta…');
    await expect(page.locator('#resultsCount')).toBeEmpty();
    await expect(page.locator('#resultsLabel')).toHaveText('Loading spots…');
    for (const meta of await page.locator(descriptions).all()) {
      await expect(meta).toHaveAttribute('content', /across Metro Atlanta\./);
    }
  } finally {
    release();
  }
  await page.locator('.shop-item').first().waitFor();
  await expectLoadedMetadata(page, 'Metro Atlanta');
});

test('metadata and feature counts follow loaded data and franchise inclusion', async ({ page }) => {
  await page.goto('/');
  await page.locator('.shop-item').first().waitFor();
  for (const includeFranchises of [false, true]) {
    if (includeFranchises) await page.locator('label[for="franchiseToggle"]').click();
    await expect(page.locator('#franchiseToggle')).toBeChecked({ checked: includeFranchises });
    await expectLoadedMetadata(page, 'Metro Atlanta');
    const expected = await page.evaluate(() => {
      const scope = SHOPS.filter(s => state.includeFranchises || s.model !== 'franchise');
      return {
        work: scope.filter(s => s.cw?.tier === 'excellent').length,
        meeting: scope.filter(s => s.cw?.hasMeetingRoom).length,
        late: scope.filter(s => s.late).length,
        midnight: scope.filter(s => s.late?.tier === 'midnight').length,
      };
    });
    for (const [key, count] of Object.entries(expected)) {
      await expect(page.locator(`[data-chip-key="feat-${key}"] .num`)).toHaveText(String(count));
    }
    await page.locator('[data-chip-key="feat-meeting"]').click();
    await expect(page.locator('#resultsCount')).toHaveText(String(expected.meeting));
    await page.locator('[data-chip-key="feat-meeting"]').click();
  }
});

test('a later dataset supplies its own region, count, and verification month', async ({ page }) => {
  await page.route('**/shops.json', async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.checkedMonth = 'unknown';
    data.shops = data.shops.slice(0, 1);
    await route.fulfill({ json: data });
  });
  await page.route('**/places.json', async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.region.label = 'Test Region';
    data.checkedMonth = 'October 2026';
    data.places = [{ name: 'Test Regional Cafe', placeId: 'test-regional-cafe', category: 'Coffee', city: 'Test City', lat: 33.5, lng: -84.5, rating: 4.5, ratingNum: 50 }];
    await route.fulfill({ json: data });
  });
  await page.goto('/');
  await page.locator('.shop-item').first().waitFor();
  await expectLoadedMetadata(page, 'Test Region');
  await expect(page.locator('.freshness')).toContainText('· regional verified October 2026');
  expect(await page.evaluate(() => SHOPS.length)).toBe(2);
});

test('fallback metadata recovers with the regional retry', async ({ page }) => {
  await page.route('**/places.json', route => route.abort());
  await page.goto('/');
  await page.locator('.shop-item').first().waitFor();
  await expectLoadedMetadata(page, 'Metro Atlanta');
  const baseline = await (await page.request.get('/shops.json')).json();
  if (baseline.checkedMonth && baseline.checkedMonth !== 'unknown') {
    await expect(page.locator('.freshness')).toContainText(`· verified ${baseline.checkedMonth}`);
  }
  await page.unroute('**/places.json');
  await page.locator('#retryPlacesBtn').click();
  await page.waitForFunction(() => dataLoadState.regional === 'ready');
  await expect(page.locator('.brand')).toHaveText('Coffee in Metro Atlanta');
  await expectLoadedMetadata(page, 'Metro Atlanta');
  expect(await page.evaluate(() => window.REGION_LABEL)).toBe('Metro Atlanta');
});
