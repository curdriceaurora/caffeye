const { test, expect, gotoHome } = require('./helpers');

// T5.12–T5.15 / R5.10: 200-cap pagination, focus transfer, monotonic scores.
test.describe('pagination', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('initial render caps at 200 with load-more', async ({ page }) => {
    await expect(page.locator('#shopList .shop-item')).toHaveCount(200);
    const btn = page.locator('.load-more-btn');
    await expect(btn).toBeVisible();
    await expect(btn).toContainText('Load 200 more');
  });

  test('load-more renders 400 and focuses the 201st card', async ({ page }) => {
    await page.locator('.load-more-btn').click();
    await expect(page.locator('#shopList .shop-item')).toHaveCount(400);
    const focusedIndex = await page.evaluate(() =>
      [...document.querySelectorAll('#shopList .shop-item')].indexOf(document.activeElement));
    expect(focusedIndex).toBe(200);
  });

  test('scores never increase down the list across batches', async ({ page }) => {
    await page.locator('.load-more-btn').click();
    await expect(page.locator('#shopList .shop-item')).toHaveCount(400);
    const monotonic = await page.evaluate(() =>
      [...document.querySelectorAll('#shopList .shop-item .score')]
        .map((e) => parseFloat(e.textContent.slice(2)))
        .every((v, i, a) => i === 0 || a[i - 1] >= v));
    expect(monotonic).toBe(true);
  });

  test('new search resets window to first page and scroll top', async ({ page }) => {
    await page.locator('.load-more-btn').click();
    await expect(page.locator('#shopList .shop-item')).toHaveCount(400);
    await page.locator('#searchInput').fill('matcha');
    await expect.poll(async () =>
      page.locator('#shopList .shop-item').count(), { timeout: 10000 }).toBeLessThanOrEqual(200);
    expect(await page.locator('#shopList').evaluate((el) => el.scrollTop)).toBe(0);
  });
});
