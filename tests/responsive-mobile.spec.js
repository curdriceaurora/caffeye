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

  test('card density holds while regional coverage is unavailable', async ({ page }) => {
    test.skip(page.viewportSize().width > 820, 'mobile-only assertion');
    await page.route('**/places.json', route => route.abort());
    await page.evaluate(() => caches.delete('caffeye-v6')); // no cached fallback for this visit
    await page.goto('/');
    await expect(page.locator('#retryPlacesBtn')).toBeVisible();
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
    // The banner's Retry keeps a 44 px touch target.
    const target = await page.locator('#retryPlacesBtn').evaluate(el => {
      const r = el.getBoundingClientRect(), after = getComputedStyle(el, '::after');
      return r.height - parseFloat(after.top) - parseFloat(after.bottom);
    });
    expect(target).toBeGreaterThanOrEqual(44);
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

test('compact header preserves region and full accessible title', async ({ page }) => {
  await gotoHome(page);
  const width = page.viewportSize().width;
  const prefix = page.locator('.brand-prefix');
  if (width <= 380) {
    await expect(prefix).toBeHidden();
    expect(await page.locator('.brand').innerText()).toBe('Metro Atlanta');
    const size = await page.locator('.brand').evaluate(el => ({
      height: el.getBoundingClientRect().height,
      lineHeight: parseFloat(getComputedStyle(el).lineHeight),
      overflow: el.scrollWidth > el.clientWidth,
    }));
    expect(size.height).toBeLessThanOrEqual(size.lineHeight + 1);
    expect(size.overflow).toBe(false);
  } else {
    await expect(prefix).toBeVisible();
  }
  await expect(page).toHaveTitle('Coffee in Metro Atlanta');
  await expect(page.locator('#brandHomeBtn')).toHaveAccessibleName('Caffeye — Coffee in Metro Atlanta — Reset filters');
});

 test('mobile map height follows the viewport contract before and after search focus', async ({page}) => {
  test.skip(page.viewportSize().width > 820, 'Mobile layout only');
  await gotoHome(page);
  const expected = await page.evaluate(() => innerHeight <= 500 ? 120 : innerHeight <= 600 ? 125 : Math.min(185,Math.max(130,innerHeight*.22)));
  const height = () => page.locator('#map').evaluate(el=>el.getBoundingClientRect().height);
  expect(await height()).toBeCloseTo(expected,0);
  await page.locator('#searchInput').click();
  expect(await height()).toBeCloseTo(expected,0);
});
