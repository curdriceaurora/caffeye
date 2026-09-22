const { test, expect, gotoHome } = require('./helpers');

// T4.1–T4.5 / R4.1–R4.5: chips, counts, union/intersection, focus retention.
test.describe('filter chips', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('All + 6 category chips with counts summing to in-scope', async ({ page }) => {
    expect(await page.locator('#categoryChips .chip').count()).toBe(7);
    const { total, sum } = await page.evaluate(() => {
      const chips = [...document.querySelectorAll('#categoryChips .chip')];
      const nums = chips.map((c) => parseInt(c.querySelector('.num').textContent, 10));
      return { total: nums[0], sum: nums.slice(1).reduce((a, b) => a + b, 0) };
    });
    expect(sum).toBe(total);
    expect(total).toBe(970);
  });

  test('multi-category selection unions; All resets', async ({ page }) => {
    await page.locator('#categoryChips .chip', { hasText: 'Coffee' }).click();
    const coffee = await page.locator('#resultsCount').textContent();
    await page.locator('#categoryChips .chip', { hasText: 'Tea/Boba' }).click();
    const union = Number(await page.locator('#resultsCount').textContent());
    expect(union).toBeGreaterThan(Number(coffee));
    await page.locator('#categoryChips .chip', { hasText: 'All' }).click();
    await expect.poll(async () => page.locator('#resultsCount').textContent()).toBe('970');
  });

  test('feature chips intersect with categories', async ({ page }) => {
    await page.locator('#categoryChips .chip', { hasText: 'Coffee' }).click();
    const coffee = Number(await page.locator('#resultsCount').textContent());
    await expect(page.locator('[data-chip-key="feat-work"]')).toBeVisible();
    await page.locator('[data-chip-key="feat-work"]').click();
    const both = Number(await page.locator('#resultsCount').textContent());
    expect(both).toBeLessThanOrEqual(coffee);
    expect(both).toBeGreaterThan(0);
  });

  test('active chip keeps focus across re-render', async ({ page }) => {
    await page.locator('[data-chip-key="feat-work"]').click();
    await expect.poll(async () => page.evaluate(
      () => document.activeElement?.dataset?.chipKey)).toBe('feat-work');
  });
});
