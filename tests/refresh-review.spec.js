const {test, expect, gotoHome, searchAndOpen} = require('./helpers');

const regionView = page => page.evaluate(() => {
  const bounds = map.getBounds();
  return {
    zoom: map.getZoom(),
    minZoom: map.getMinZoom(),
    outside: SHOPS.filter(s => s.model === 'independent' && !bounds.contains([s.lat, s.lng])).length,
  };
});

for (const [width, height, zoom, minZoom] of [[375, 750, 7, 7], [375, 667, 6, 6], [320, 568, 6, 6]]) {
  test(`${width}x${height} opens on the whole region as several bubbles`, async ({page}) => {
    await page.setViewportSize({width, height});
    await gotoHome(page);
    await expect.poll(() => page.locator('.coffee-cluster').count()).toBeGreaterThan(3);
    expect(await regionView(page)).toEqual({zoom, minZoom, outside: 0});
  });
}

test('tall maps stop at zoom 7', async ({page}) => {
  await gotoHome(page);
  expect((await regionView(page)).minZoom).toBe(7);
});

test('badges follow verified brand status, not location count', async ({page}) => {
  await gotoHome(page);
  await page.locator('label.toggle-label').click();
  for (const [name, badge] of [['Dancing Goats Midtown', 'Chain'], ['Foxtail Coffee - Ashford Lane', 'Franchise'], ['Bellwood Coffee - Decatur', 'Indie spot']]) {
    await searchAndOpen(page, name);
    await expect(page.locator('#detailView .model-tag')).toHaveText(badge);
    await page.locator('#backBtn').click();
  }
  expect(await page.evaluate(() => SHOPS.filter(s => s.name === 'Condesa Coffee').length)).toBe(2);
});

test('early-hours parser handles elided AM without interpreting overnight closings as openings', async ({page}) => {
  await gotoHome(page);
  const actual = await page.evaluate(() => [null, '', 'Daily 5:30-9am', 'Daily 6-9am', 'Daily 7am-9pm', 'Daily 7:01am-9pm', 'Daily 7pm-3am', 'Daily 11-2am', 'Daily 12-6am'].map(isEarlyRiser));
  expect(actual).toEqual([false,false,true,true,true,false,false,false,true]);
});

test('unverified hours cannot enter early or midnight recommendations; held ratings retain provenance', async ({page}) => {
  await gotoHome(page);
  expect(await page.evaluate(() => SHOPS.filter(s => s.hoursUnverified).every(s => !s.earlyRiser && !s.late))).toBe(true);
  await page.locator('label.toggle-label').click();
  await searchAndOpen(page, 'Foxtail Coffee - Midtown');
  await expect(page.locator('#detailView')).toContainText('checked September 2026');
});
