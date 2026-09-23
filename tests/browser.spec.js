const { test, expect, gotoHome, findIsolatedShop, detailMode } = require('./helpers');

// Baseline suite: core smoke & critical paths. Mobile projects also run
// this file; density assertions live in responsive-mobile.spec.js.
test.describe('navigation (baseline)', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('initial load populates list and fits markers', async ({ page }) => {
    const count = await page.locator('.shop-item').count();
    expect(count).toBeGreaterThan(0);
    const resultsCount = await page.locator('#resultsCount').textContent();
    expect(Number(resultsCount)).toBeGreaterThan(100);
  });

  test('card selection opens detail, marks active, focuses back', async ({ page }) => {
    await page.locator('.shop-item').first().click();
    await expect(page.locator('#backBtn')).toBeVisible();
    await expect(page.locator('.shop-item.active')).toHaveCount(1);
    expect(await page.evaluate(() => document.activeElement?.id)).toBe('backBtn');
  });

  test('back button restores list, scroll, focus, and bounds', async ({ page }) => {
    const list = page.locator('#shopList');
    await list.evaluate((el) => el.scrollTo(0, 300));
    const before = await list.evaluate((el) => el.scrollTop);
    expect(before).toBeGreaterThan(0);
    const targetId = await page.evaluate(() => {
      const items = [...document.querySelectorAll('.shop-item')];
      const el = items.find((li) => li.getBoundingClientRect().top > 200) || items[0];
      el.click();
      return el.dataset.id;
    });
    await expect(page.locator('#backBtn')).toBeVisible();
    await page.locator('#backBtn').click();
    // Detail hides via compositor (opacity), not display:none — assert mode class.
    await expect.poll(() => detailMode(page)).toBe(false);
    expect(await page.evaluate(() => document.activeElement?.dataset?.id)).toBe(targetId);
  });

  test('home reset clears search and restores full results', async ({ page }) => {
    const baseline = await page.locator('#resultsCount').textContent();
    await page.locator('#searchInput').fill('Portrait');
    await expect.poll(async () => page.locator('#resultsCount').textContent(), { timeout: 10000 }).not.toBe(baseline);
    await page.locator('#brandHomeBtn').click();
    await expect.poll(async () => page.locator('#searchInput').inputValue()).toBe('');
    await expect.poll(async () => page.locator('#resultsCount').textContent(), { timeout: 10000 }).toBe(baseline);
    // Full spread refit: every match in viewport, no stale "in view".
    expect(await page.locator('#resultsLabel').textContent()).toBe(' spots');
  });

  test('excluding filter closes the open detail card', async ({ page }) => {
    await page.locator('.shop-item').first().click();
    await expect(page.locator('#backBtn')).toBeVisible();
    await page.locator('#categoryChips .chip', { hasText: 'Tea/Boba' }).click();
    await expect.poll(() => detailMode(page)).toBe(false);
  });

  test('select then filter-out leaves no dangling map errors', async ({ page }) => {
    // Regression: zoomToShowLayer's internal listeners used to throw inside
    // markercluster once a filter removed the marker mid-flight. The shared
    // error-listener fixture fails this test on any pageerror.
    const spot = await findIsolatedShop(page);
    await page.evaluate(({ lat, lng }) => window.map.setView([lat, lng], 16, { animate: false }), spot);
    await page.locator('#searchInput').fill(spot.name);
    await page.locator('.shop-item').first().click();
    await expect(page.locator('#backBtn')).toBeVisible();
    await page.evaluate(() => {
      const selected = window.state.selected.category.replace('+', ' &');
      const chips = [...document.querySelectorAll('#categoryChips .chip')];
      chips.find((c) => !c.textContent.includes('All') && !c.textContent.includes(selected)).click();
    });
    await expect.poll(() => detailMode(page)).toBe(false);
    await page.evaluate(() => window.map.zoomIn());
    await page.waitForTimeout(1500);
  });

  test('pin click opens the detail card', async ({ page }) => {
    // Zoom onto an isolated shop so it renders as a marker, not a cluster.
    const spot = await findIsolatedShop(page);
    await page.evaluate(({ lat, lng }) => window.map.setView([lat, lng], 16, { animate: false }), spot);
    const icon = page.locator('.leaflet-marker-icon').first();
    await icon.waitFor({ timeout: 15000 });
    await icon.click();
    await expect(page.locator('#backBtn')).toBeVisible({ timeout: 15000 });
  });
});

test.describe('search expansion', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('off-view search offers expansion that reveals matches', async ({ page }) => {
    // Zoom tight into Duluth; Portrait Coffee (West End) falls outside.
    await page.evaluate(() => window.map.setView([33.95, -84.13], 18, { animate: false }));
    await page.locator('#searchInput').fill('Portrait');
    const btn = page.locator('.outside-matches-btn');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();
    await expect.poll(async () => page.locator('.shop-item').count(), { timeout: 10000 }).toBeGreaterThan(0);
  });
});

test.describe('regional failure and retry', () => {
  test('blocked places.json shows banner; retry recovers', async ({ page }) => {
    await page.route('**/places.json', (route) => route.abort());
    for (let i = 0; i < 3; i++) {
      try {
        await page.goto('/');
        break;
      } catch (e) {
        if (i === 2) throw e;
      }
    }
    await page.locator('.shop-item').first().waitFor({ timeout: 30000 });
    const banner = page.locator('#dataStatusBanner');
    await expect(banner).toBeVisible();
    expect(await banner.getAttribute('role')).toBe('status');
    expect(await page.locator('#retryPlacesBtn')).toBeVisible();

    await page.unroute('**/places.json');
    const before = Number(await page.locator('#resultsCount').textContent());
    await page.locator('#retryPlacesBtn').click();
    await expect(banner).toContainText('Regional coverage loaded', { timeout: 20000 });
    expect(Number(await page.locator('#resultsCount').textContent())).toBeGreaterThan(before);
  });
});
