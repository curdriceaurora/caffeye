const { test, expect, gotoHome } = require('./helpers');

// T3.2, T3.9, T3.1–T3.7 / R3: zoom gate, safety cap, placement integrity.
test.describe('pin labels', () => {
  test.beforeEach(async ({ page }) => {
    await gotoHome(page);
  });

  test('labels gate on zoom 13', async ({ page }) => {
    await page.evaluate(() => window.map.setZoom(12, { animate: false }));
    await expect.poll(async () => page.evaluate(
      () => window.map.getContainer().classList.contains('with-labels'))).toBe(false);
    await page.evaluate(() => window.map.setZoom(14, { animate: false }));
    await expect.poll(async () => page.evaluate(
      () => window.map.getContainer().classList.contains('with-labels'))).toBe(true);
  });

  test('safety cap trips above 300 pins', async ({ page }) => {
    const res = await page.evaluate(() => ({
      at: window.exceedsLabelSafetyCap(300),
      over: window.exceedsLabelSafetyCap(301),
    }));
    expect(res).toEqual({ at: false, over: true });
  });

  test('zoom 17 labels are placed without overlap', async ({ page }) => {
    const center = await page.evaluate(() => {
      const s = window.SHOPS[0];
      return { lat: s.lat, lng: s.lng };
    });
    await page.evaluate(({ lat, lng }) => window.map.setView([lat, lng], 17, { animate: false }), center);
    await page.waitForTimeout(500);
    const check = await page.evaluate(() => {
      const vw = window.innerWidth, vh = window.innerHeight;
      const inView = (r) => r.right > 0 && r.left < vw && r.bottom > 0 && r.top < vh;
      const rects = [...document.querySelectorAll('.pin-label')]
        .filter((el) => el.offsetParent !== null && el.style.visibility !== 'hidden')
        .map((el) => ({ t: el.textContent.trim(), r: el.getBoundingClientRect() }))
        .filter((x) => inView(x.r));
      let overlap = 0;
      for (let i = 0; i < rects.length; i++) {
        for (let j = i + 1; j < rects.length; j++) {
          const a = rects[i].r, b = rects[j].r;
          if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) overlap++;
        }
      }
      return { labels: rects.length, overlap, empty: rects.filter((x) => !x.t).length };
    });
    expect(check.labels).toBeGreaterThan(0);
    expect(check.empty).toBe(0);
    expect(check.overlap).toBe(0);
  });
});
