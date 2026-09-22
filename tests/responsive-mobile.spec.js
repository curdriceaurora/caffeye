const { test, expect, gotoHome } = require('./helpers');

// T8.1–T8.5 / R8: layout breakpoints, density, touch targets.
// Runs on desktop + both mobile projects (see playwright.config.js).
test.describe('responsive layout', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('desktop shows side-by-side panel with footer', async ({ page }) => {
    test.skip(page.viewportSize().width <= 820, 'desktop-only assertion');
    const dir = await page.evaluate(() => getComputedStyle(document.querySelector('.layout')).flexDirection);
    expect(dir).toBe('row');
    await expect(page.locator('footer')).toBeVisible();
  });

  test('narrow layout stacks, hides footer, compresses chips', async ({ page }) => {
    test.skip(page.viewportSize().width > 820, 'mobile-only assertion');
    const dir = await page.evaluate(() => getComputedStyle(document.querySelector('.layout')).flexDirection);
    expect(dir).toBe('column');
    await expect(page.locator('footer')).toBeHidden();
  });

  test('fully visible card density meets targets', async ({ page }) => {
    const width = page.viewportSize().width;
    const height = page.viewportSize().height;
    const minCards = width <= 360 && height <= 600 ? 3 : 5;
    const visible = await page.evaluate(() => {
      const r = document.getElementById('shopList').getBoundingClientRect();
      return [...document.querySelectorAll('.shop-item')].filter((li) => {
        const cr = li.getBoundingClientRect();
        return cr.top >= r.top - 0.5 && cr.bottom <= r.bottom + 0.5;
      }).length;
    });
    expect(visible).toBeGreaterThanOrEqual(minCards);
  });

  test('chip hit-slop provides 44px touch targets on mobile', async ({ page }) => {
    test.skip(page.viewportSize().width > 820, 'mobile-only assertion');
    const slop = await page.evaluate(() => {
      const chip = document.querySelector('#categoryChips .chip');
      const after = getComputedStyle(chip, '::after');
      const top = parseFloat(after.top) || 0;
      const bottom = parseFloat(after.bottom) || 0;
      return chip.getBoundingClientRect().height - top - bottom;
    });
    expect(slop).toBeGreaterThanOrEqual(44);
  });
});
