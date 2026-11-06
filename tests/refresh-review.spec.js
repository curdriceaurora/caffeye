const {test, expect, gotoHome, searchAndOpen} = require('./helpers');

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
