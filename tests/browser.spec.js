const { test, expect } = require('@playwright/test');

// Baseline suite: runs against current behavior on every project.
// Waits on rendered list items, never on basemap tile network responses.
test.describe('navigation (baseline)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.locator('.shop-item').first().waitFor({ timeout: 30000 });
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
    await expect.poll(async () => page.evaluate(
      () => document.getElementById('panel')?.classList.contains('detail-mode')
    )).toBe(false);
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
    await expect.poll(async () => page.evaluate(
      () => document.getElementById('panel')?.classList.contains('detail-mode')
    )).toBe(false);
  });

  test('pin click opens the detail card', async ({ page }) => {
    // Zoom onto an isolated shop so it renders as a marker, not a cluster.
    await page.evaluate(() => {
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
      window.map.setView([best.lat, best.lng], 16, { animate: false });
    });
    const icon = page.locator('.leaflet-marker-icon').first();
    await icon.waitFor({ timeout: 15000 });
    await icon.click();
    await expect(page.locator('#backBtn')).toBeVisible({ timeout: 15000 });
  });
});

test.describe('search expansion', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.locator('.shop-item').first().waitFor({ timeout: 30000 });
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
    await page.goto('/');
    await page.locator('.shop-item').first().waitFor({ timeout: 30000 });
    const banner = page.locator('#dataStatusBanner');
    await expect(banner).toBeVisible();
    expect(await banner.getAttribute('role')).toBe('alert');
    expect(await page.locator('#retryPlacesBtn')).toBeVisible();

    await page.unroute('**/places.json');
    const before = Number(await page.locator('#resultsCount').textContent());
    await page.locator('#retryPlacesBtn').click();
    await expect(banner).toBeHidden({ timeout: 20000 });
    expect(Number(await page.locator('#resultsCount').textContent())).toBeGreaterThan(before);
  });
});

test.describe('mobile density', () => {
  for (const [name, viewport, minCards] of [
    ['375x750', { width: 375, height: 750 }, 5],
    ['320x568', { width: 320, height: 568 }, 3],
  ]) {
    test(`fully visible cards at ${name} >= ${minCards}`, async ({ browser }) => {
      const context = await browser.newContext({ viewport, isMobile: true, hasTouch: true });
      const page = await context.newPage();
      try {
        await page.goto('/');
        await page.locator('.shop-item').first().waitFor({ timeout: 30000 });
        const visible = await page.evaluate(() => {
          const r = document.getElementById('shopList').getBoundingClientRect();
          return [...document.querySelectorAll('.shop-item')].filter((li) => {
            const cr = li.getBoundingClientRect();
            return cr.top >= r.top - 0.5 && cr.bottom <= r.bottom + 0.5;
          }).length;
        });
        expect(visible).toBeGreaterThanOrEqual(minCards);
      } finally {
        await context.close();
      }
    });
  }
});
