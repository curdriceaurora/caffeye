const { test, expect, gotoHome, searchAndOpen, detailMode, expandMatches } = require('./helpers');

// T4.13–T4.14 / R4.8: Indie default vs franchise inclusion.
test.describe('franchise model', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('boot is Indie-only with no franchise cards', async ({ page }) => {
    expect(await page.evaluate(() => window.state.includeFranchises)).toBe(false);
    expect(await page.locator('#resultsCount').textContent()).toBe('970');
    expect(await page.locator('.model-tag.franchise').count()).toBe(0);
    expect(await page.locator('.model-tag.indie').count()).toBeGreaterThan(0);
  });

  test('toggle ON shows 1,705 with franchise badges; OFF restores 970', async ({ page }) => {
    await page.locator('label.toggle-label').click();
    await expect.poll(async () => page.locator('#resultsCount').textContent(), { timeout: 10000 }).toBe('1705');
    expect(await page.locator('.model-tag.franchise').count()).toBeGreaterThan(0);
    await page.locator('label.toggle-label').click();
    await expect.poll(async () => page.locator('#resultsCount').textContent(), { timeout: 10000 }).toBe('970');
    expect(await page.locator('.model-tag.franchise').count()).toBe(0);
  });

  test('detail badge reflects Indie vs Franchise', async ({ page }) => {
    await searchAndOpen(page, 'TradeWind');
    await expect(page.locator('#detailView')).toContainText('Indie spot');
    await page.locator('#backBtn').click();
    await expect.poll(() => detailMode(page), { timeout: 10000 }).toBe(false);
    await page.locator('label.toggle-label').click();
    // Prior select can leave the map zoomed tight with matches off-view.
    // Wait for whichever affordance the search produces, expand if needed.
    await page.locator('#searchInput').fill('Starbucks');
    const card = page.locator('.shop-item', { hasText: 'Starbucks' }).first();
    const expand = page.locator('.outside-matches-btn');
    await expect(card.or(expand)).toBeVisible({ timeout: 15000 });
    if (await expand.count()) {
      await expandMatches(page, expand);
      await expect(card).toBeVisible({ timeout: 15000 });
    }
    // Let post-expansion renders settle so the click target is stable.
    await page.waitForTimeout(1200);
    await card.scrollIntoViewIfNeeded();
    await card.click();
    await page.locator('#backBtn').waitFor({ timeout: 15000 });
    await expect(page.locator('#detailView')).toContainText('Franchise');
  });
});
