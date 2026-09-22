const { test, expect, gotoHome } = require('./helpers');

// T4.17 / R4.10: theme toggle, tile sync, brand assets, persistence.
test.describe('theme', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('toggle flips theme, tiles, logo, and persists across reload', async ({ page }) => {
    const start = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    await page.locator('#themeToggle').click();
    const flipped = start === 'dark' ? 'light' : 'dark';
    await expect(page.locator('html')).toHaveAttribute('data-theme', flipped);

    const tileUrl = await page.evaluate(() => window.tileLayer.getTileUrl({ x: 1, y: 1, z: 1 }));
    expect(tileUrl).toContain(flipped === 'dark' ? 'dark_all' : 'light_all');

    const logo = await page.locator('#brandLogoImg').getAttribute('src');
    expect(logo).toContain(flipped === 'dark' ? 'caffeye-symbol-paper.svg' : 'caffeye-symbol-forest.svg');
    expect(await page.evaluate(() => localStorage.getItem('caffeye-theme'))).toBe(flipped);

    await page.reload();
    await page.locator('.shop-item').first().waitFor({ timeout: 30000 });
    await expect(page.locator('html')).toHaveAttribute('data-theme', flipped);
  });
});
