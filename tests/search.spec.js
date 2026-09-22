const { test, expect, gotoHome, expandMatches } = require('./helpers');

// T7.2–T7.4 / R7.2–R7.3: case, multi-word AND, multi-field matching.
// T5.16 / R5.11: compact outside-view pill (empty-state button: browser.spec.js).
test.describe('search', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  async function countFor(page, query) {
    await page.locator('#searchInput').fill(query);
    await page.waitForTimeout(300);
    return Number(await page.locator('#resultsCount').textContent());
  }

  test('case-insensitive with identical results', async ({ page }) => {
    expect(await countFor(page, 'matcha')).toBeGreaterThanOrEqual(10);
    expect(await countFor(page, 'MATCHA')).toBe(await countFor(page, 'matcha'));
  });

  test('multi-word queries AND-match and narrow results', async ({ page }) => {
    const single = await countFor(page, 'matcha');
    const both = await countFor(page, 'matcha latte');
    expect(both).toBeLessThanOrEqual(single);
  });

  test('matches USP address text', async ({ page }) => {
    await page.locator('#searchInput').fill('boggs');
    await page.waitForTimeout(300);
    const names = await page.locator('#shopList .shop-name').allTextContents();
    expect(names.join(' ').toLowerCase()).toContain('cafe flat');
  });

  test('pill appears for partial off-view matches and expands', async ({ page }) => {
    // Zoom into a neighborhood, then search a term with matches elsewhere.
    await page.evaluate(() => window.map.setView([33.95, -84.13], 15, { animate: false }));
    await page.locator('#searchInput').fill('matcha');
    await page.waitForTimeout(300);
    const pill = page.locator('#outsideMatchesPill');
    const emptyBtn = page.locator('.outside-matches-btn');
    const pillVisible = await pill.count();
    const btnVisible = await emptyBtn.count();
    expect(pillVisible + btnVisible).toBeGreaterThanOrEqual(1);
    const target = pillVisible ? pill : emptyBtn;
    await expandMatches(page, target);
    await expect.poll(async () => page.locator('.shop-item').count(), { timeout: 10000 }).toBeGreaterThan(0);
  });
});
