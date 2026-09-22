const { test, expect, gotoHome, openFirstDetail } = require('./helpers');

// Keyboard flow + ARIA semantics.
test.describe('keyboard and aria', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('Enter opens detail; Space opens detail', async ({ page }) => {
    await page.locator('.shop-item').first().focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#backBtn')).toBeVisible();
    await page.locator('#backBtn').click();
    await expect.poll(async () => page.evaluate(
      () => document.getElementById('panel')?.classList.contains('detail-mode'))).toBe(false);
    await page.locator('.shop-item').first().focus();
    await page.keyboard.press('Space');
    await expect(page.locator('#backBtn')).toBeVisible();
  });

  test('brand home resets via keyboard', async ({ page }) => {
    await page.locator('#searchInput').fill('Portrait');
    await page.locator('#brandHomeBtn').focus();
    await page.keyboard.press('Enter');
    await expect.poll(async () => page.locator('#searchInput').inputValue()).toBe('');
  });

  test('chips expose aria-pressed; cards expose aria-labels', async ({ page }) => {
    const pressed = await page.evaluate(() =>
      [...document.querySelectorAll('#categoryChips .chip')]
        .every((c) => c.getAttribute('aria-pressed') === 'true' || c.getAttribute('aria-pressed') === 'false'));
    expect(pressed).toBe(true);
    const labeled = await page.evaluate(() => {
      const byId = Object.fromEntries(window.SHOPS.map((s) => [s.id, s.name]));
      return [...document.querySelectorAll('.shop-item')].slice(0, 20)
        .every((li) => {
          const label = li.getAttribute('aria-label') || '';
          const name = byId[li.dataset.id] || '';
          return label.length > 0 && name.length > 0 && label.includes(name);
        });
    });
    expect(labeled).toBe(true);
  });

  test('inert swaps with detail state', async ({ page }) => {
    await openFirstDetail(page);
    await expect(page.locator('#listView')).toHaveAttribute('inert', '');
    await page.locator('#backBtn').click();
    await expect(page.locator('#detailView')).toHaveAttribute('inert', '');
  });

  test('live region announces selection, detail exit, and franchise toggle', async ({ page }) => {
    const srAnnounce = page.locator('#srAnnounce');
    await expect(srAnnounce).toHaveAttribute('aria-live', 'polite');
    await page.locator('.shop-item').first().click();
    await expect.poll(() => srAnnounce.textContent()).toContain('Selected ');
    await expect.poll(() => srAnnounce.textContent()).toContain('Showing details.');
    await page.locator('#backBtn').click();
    await expect.poll(() => srAnnounce.textContent()).toBe('Closed details.');
    await page.locator('label[for="franchiseToggle"]').click();
    await expect.poll(() => srAnnounce.textContent()).toContain('Including franchise stores.');
    await page.locator('#categoryChips .chip', { hasText: 'Tea/Boba' }).click();
    await expect.poll(() => srAnnounce.textContent()).toContain('Tea/Boba');
    await page.locator('#searchInput').fill('Portrait');
    await expect.poll(() => srAnnounce.textContent()).toContain('Portrait');
  });
});

