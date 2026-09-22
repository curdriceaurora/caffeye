const { test, expect, gotoHome, openFirstDetail, searchAndOpen } = require('./helpers');

// T6.11 / R6.10 (High, preventive): unsafe protocols never render links.
// T6.2–T6.7, T6.10 / R6: detail sections, provenance, inert swapping.
test.describe('detail card', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('unsafe action URLs render no links; safe website renders one', async ({ page }) => {
    await page.evaluate(() => {
      const malicious = {
        ...window.SHOPS[0],
        id: 'test-xss-shop',
        name: 'Security Test Cafe',
        googleUrl: 'javascript:alert("xss")',
        yelpUrl: 'data:text/html,<script>alert(1)</script>',
        website: 'https://valid-website.com',
      };
      window.selectShop(malicious);
    });
    await expect(page.locator('#backBtn')).toBeVisible();
    const actions = page.locator('#detailView .actions a');
    await expect(actions).toHaveCount(1);
    await expect(actions.first()).toHaveAttribute('href', 'https://valid-website.com');
    await expect(page.locator('#detailView a[href^="javascript:"]')).toHaveCount(0);
    await expect(page.locator('#detailView a[href^="data:"]')).toHaveCount(0);
  });

  test('all rendered action links use http(s)', async ({ page }) => {
    await openFirstDetail(page);
    const hrefs = await page.locator('#detailView .actions a').evaluateAll((els) =>
      els.map((a) => a.getAttribute('href')));
    expect(hrefs.length).toBeGreaterThan(0);
    for (const href of hrefs) expect(href).toMatch(/^https?:\/\//);
  });

  test('curated shop shows coworking, provenance, and model badge', async ({ page }) => {
    await searchAndOpen(page, 'TradeWind');
    const detail = page.locator('#detailView');
    await expect(detail).toContainText('Coworking-ready');
    await expect(detail).toContainText('Meeting room');
    await expect(detail).toContainText(/Verified \S+ \d{4} ·/);
    await expect(detail).toContainText('Indie spot');
  });

  test('uncurated shop shows explicit unknown work suitability', async ({ page }) => {
    const name = await page.evaluate(() => window.SHOPS.find((s) => !s.cw).name);
    await searchAndOpen(page, name);
    await expect(page.locator('#detailView')).toContainText('Unknown · amenities not yet verified');
  });

  test('late-night shop shows midnight header', async ({ page }) => {
    const name = await page.evaluate(() =>
      window.SHOPS.find((s) => (s.late || {}).tier === 'midnight' && s.model !== 'franchise').name);
    await searchAndOpen(page, name);
    await expect(page.locator('#detailView')).toContainText('Open until midnight');
  });

  test('inert swaps between list and detail', async ({ page }) => {
    await expect(page.locator('#detailView')).toHaveAttribute('inert', '');
    await openFirstDetail(page);
    await expect(page.locator('#listView')).toHaveAttribute('inert', '');
    await expect(page.locator('#detailView')).not.toHaveAttribute('inert', '');
    await page.locator('#backBtn').click();
    await expect(page.locator('#listView')).not.toHaveAttribute('inert', '');
  });
});
