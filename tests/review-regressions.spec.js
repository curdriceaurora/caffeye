const { test, expect, gotoHome, findIsolatedShop } = require('./helpers');
const fs = require('fs');

async function settled(page) {
  await page.waitForFunction(() => {
    const m = markerByShopId.get(state.selected?.id);
    // zoom >= 16 is the reveal's end state; Leaflet starts a CSS zoom on the next frame, so
    // 'not animating' alone can be observed before the selection's zoom has begun.
    return m && map.getZoom() >= 16 && clusterGroup.getVisibleParent(m) === m && map.getBounds().contains(m.getLatLng()) && !map._animatingZoom && !map._panAnim?._inProgress && !(clusterGroup._inZoomAnimation > 0);
  }, null, {timeout: 15000});
}
// A top list card whose pin is still clustered at zoom 16, so revealing it takes several steps.
async function clusteredAtSixteen(page) {
  return page.evaluate(() => [...document.querySelectorAll('.shop-item')].map(li => li.dataset.id)
    .find(id => { const m = markerByShopId.get(id); return m && m.__parent && m.__parent._zoom >= 16; }));
}
const visibleCardId = () => {
  const r = document.getElementById('shopList').getBoundingClientRect();
  return [...document.querySelectorAll('.shop-item')].find(li => li.getBoundingClientRect().top >= r.top)?.dataset.id;
};
async function duluth(page) {
  await gotoHome(page);
  await page.evaluate(() => map.setView([33.97, -84.14], 13, { animate: false }));
  await page.waitForTimeout(200);
}
async function exactAnnouncement(page, prefix = '', context = '') {
  await page.waitForTimeout(150);
  const text = await page.evaluate(({prefix, context}) => {
    const count = Number(document.querySelector('#resultsCount').textContent);
    const total = markers.filter(m => m.isOnMap).length;
    const outside = total - count;
    return prefix + (total ? `${count} spot${count === 1 ? '' : 's'} in view${outside ? `, ${outside} more outside the map` : ''}${context}.` : `No spots found${context}.`);
  }, {prefix, context});
  await expect(page.locator('#srAnnounce')).toHaveText(text);
}

test('HTML stays within the 110 KB maintenance cap', () => {
  expect(fs.statSync('public/index.html').size).toBeLessThanOrEqual(112640);
});

test('regional shell waits for a one-second regional response and boots once', async ({page}) => {
  await page.addInitScript(() => {
    window.headerHistory = [];
    new MutationObserver(() => {
      const text = document.querySelector('.brand')?.textContent;
      if (text) headerHistory.push(text);
    }).observe(document, {subtree: true, childList: true, characterData: true});
  });
  await page.route('**/places.json', async route => { await new Promise(r => setTimeout(r, 1000)); await route.continue(); });
  await page.goto('/');
  await page.waitForFunction(() => window.mapReady && dataLoadState.regional === 'ready');
  expect(await page.evaluate(() => headerHistory.some(t => t.includes('Duluth')))).toBe(false);
  expect(await page.evaluate(() => SHOPS.length)).toBeGreaterThan(1000);
  expect(await page.evaluate(() => __telemetryLog.filter(e => e.event === 'regional_ready').map(e => e.properties.path))).toEqual(['boot']);
});

test('partial coverage has stable scores, working search and Back, and preserves a reading list', async ({page}) => {
  let release;
  const pending = new Promise(r => release = r);
  await page.route('**/places.json', async route => { await pending; await route.continue(); });
  try {
    await page.goto('/');
    await expect(page.locator('.shop-item').first()).toBeVisible();
    await expect(page.locator('#dataStatusBanner')).toContainText('Loading Metro Atlanta');
    const before = await page.evaluate(() => ({scores: Object.fromEntries(SHOPS.map(s => [s.id, s.scoreText])), zoom: map.getZoom()}));
    expect(before.zoom).toBeLessThanOrEqual(9);
    await page.locator('#searchInput').click();
    await page.locator('.shop-item').first().click();
    await settled(page);
    await page.locator('#backBtn').click();
    await page.waitForTimeout(200);
    await page.locator('#shopList').evaluate(el => el.scrollTop = 400);
    await page.waitForTimeout(100);
    const list = await page.locator('.shop-item').evaluateAll(els => els.map(e => e.dataset.id));
    const scroll = await page.locator('#shopList').evaluate(el => el.scrollTop);
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    const scores = await page.evaluate(ids => Object.fromEntries(SHOPS.filter(s => ids.includes(s.id)).map(s => [s.id, s.scoreText])), Object.keys(before.scores));
    expect(scores).toEqual(before.scores);
    expect(await page.locator('.shop-item').evaluateAll(els => els.map(e => e.dataset.id))).toEqual(list);
    expect(await page.locator('#shopList').evaluate(el => el.scrollTop)).toBe(scroll);
    await page.getByRole('button', {name:'Update list', exact:true}).click();
    expect(await page.locator('.shop-item').count()).toBeGreaterThan(list.length);
  } finally { release(); }
});

test('announcements reflect viewport, outside matches, filters, search and clear', async ({page}) => {
  await duluth(page);
  await page.locator('#searchInput').fill('fayetteville');
  await exactAnnouncement(page, '', ' for "fayetteville"');
  await page.locator('#searchInput').fill('latte');
  await exactAnnouncement(page, '', ' for "latte"');
  await page.locator('[data-chip-key="cat-all"]').click();
  await exactAnnouncement(page, '', ' for "latte"');
  const teaChip = () => page.locator('[data-chip-key="cat-Tea/Boba"] .num').textContent().then(Number);
  const teaBefore = await teaChip();
  await page.locator('[data-chip-key="cat-Coffee"]').click();
  await exactAnnouncement(page, '', ' for Coffee, "latte"');
  // Chip badges count the franchise scope, not the view or other chips (selecting Coffee must not zero Tea/Boba).
  expect(teaBefore).toBeGreaterThan(0);
  expect(await teaChip()).toBe(teaBefore);
  await page.locator('label.toggle-label').click();
  await exactAnnouncement(page, 'Including franchise stores. ', ' for Coffee, "latte"');
  await page.locator('#searchInput').fill('');
  await exactAnnouncement(page, 'Search cleared. ', ' for Coffee');
  await page.locator('#brandHomeBtn').click();
  await exactAnnouncement(page, 'Reset filters. ');
});

test('search debounce yields one announcement and cannot overwrite a selection', async ({page}) => {
  await duluth(page);
  await page.evaluate(() => {
    window.messages = [];
    new MutationObserver(() => { const t = document.querySelector('#srAnnounce').textContent; if(t) messages.push(t); }).observe(document.querySelector('#srAnnounce'), {childList:true});
  });
  await page.locator('#searchInput').pressSequentially('coffee', {delay:100});
  await page.waitForTimeout(850);
  expect(await page.evaluate(() => messages.length)).toBe(1);
  await page.locator('#searchInput').fill('latte');
  await page.waitForTimeout(150);
  await page.locator('.shop-item').first().click();
  await page.waitForTimeout(850);
  await expect(page.locator('#srAnnounce')).toContainText('Selected');
});

test('clearing an outside-only search removes every stale empty row', async ({page}) => {
  await duluth(page);
  await page.locator('#searchInput').fill('fayetteville');
  await expect(page.locator('.outside-matches-btn')).toBeVisible();
  await page.locator('#searchInput').fill('');
  await expect(page.locator('.shop-item').first()).toBeVisible();
  await expect(page.locator('.empty-state')).toHaveCount(0);
});

test('twenty regional cards reveal their actual pins; Back then another card is safe', async ({page}) => {
  if (process.env.MUTATE_REVEAL) await page.route('**/', async route => {
    const response = await route.fetch();
    await route.fulfill({body:(await response.text()).replace('revealMarker(m, selectionToken, () => setMarkerSelected(shop));', '/* reveal removed by regression mutation */')});
  });
  await gotoHome(page);
  const ids = await page.locator('.shop-item').evaluateAll(els => els.slice(0,20).map(e => e.dataset.id));
  const listeners = await page.evaluate(() => map._events.moveend.length);
  for (const id of ids) {
    await page.locator(`.shop-item[data-id="${id}"]`).click();
    await settled(page);
    await page.locator('#backBtn').click();
    await page.waitForTimeout(100);
  }
  expect(await page.evaluate(() => map._events.moveend.length)).toBe(listeners);
});

test('a filter during an in-flight reveal cancels it and announces closing details', async ({page}) => {
  await gotoHome(page);
  const listeners = await page.evaluate(() => map._events.moveend.length);
  const id = await clusteredAtSixteen(page);
  expect(id).toBeTruthy();
  // The chip click lands while the reveal waits for the cluster animation after its first step.
  const zoomAtCancel = await page.evaluate(id => new Promise(resolve => {
    const shop = SHOPS.find(s => s.id === id);
    const chip = document.querySelector(`[data-chip-key="cat-${shop.category === 'Tea/Boba' ? 'Coffee' : 'Tea/Boba'}"]`);
    map.once('zoomend', () => setTimeout(() => { chip.click(); resolve(map.getZoom()); }, 0));
    document.querySelector(`.shop-item[data-id="${id}"]`).click();
  }), id);
  await expect(page.locator('#panel')).not.toHaveClass(/detail-mode/);
  await expect(page.locator('#srAnnounce')).toContainText('Closed details.');
  await page.waitForTimeout(1200);
  expect(await page.evaluate(() => map.getZoom())).toBe(zoomAtCancel);
  expect(await page.evaluate(() => map._events.moveend.length)).toBe(listeners);
});

test('Back during an in-flight reveal cancels it and restores the camera', async ({page}) => {
  await gotoHome(page);
  const camera = await page.evaluate(() => ({lat: map.getCenter().lat, lng: map.getCenter().lng, zoom: map.getZoom()}));
  const id = await clusteredAtSixteen(page);
  await page.evaluate(id => new Promise(resolve => {
    map.once('zoomend', () => setTimeout(() => { document.getElementById('backBtn').click(); resolve(); }, 0));
    document.querySelector(`.shop-item[data-id="${id}"]`).click();
  }), id);
  await page.waitForTimeout(1200);
  expect(await page.evaluate(() => map.getZoom())).toBe(camera.zoom);
  expect(await page.evaluate(c => map.distance(map.getCenter(), [c.lat, c.lng]), camera)).toBeLessThan(2);
  expect(await page.evaluate(() => state.selected)).toBeNull();
});

test('a card chosen during a zoom animation waits for it, then reveals its pin', async ({page}) => {
  await gotoHome(page);
  // A pin that is already unclustered at low zoom: a reveal that ignored the running zoom would
  // stop there instead of reaching the zoom-16 selection frame.
  const id = await page.evaluate(() => [...document.querySelectorAll('.shop-item')].map(li => li.dataset.id)
    .find(id => { const m = markerByShopId.get(id); return m && m.__parent && m.__parent._zoom <= 11; }));
  expect(id).toBeTruthy();
  const inFlight = await page.evaluate(id => new Promise(resolve => {
    map.once('zoomanim', () => { const animating = map._animatingZoom; document.querySelector(`.shop-item[data-id="${id}"]`).click(); resolve(animating); });
    map.setZoom(map.getZoom() + 1, {animate: true});
  }), id);
  expect(inFlight).toBe(true);
  await settled(page);
  expect(await page.evaluate(() => state.selected.id)).toBe(id);
});

test('reduced motion: switching selections keeps MarkerCluster animation state balanced', async ({page}) => {
  await page.emulateMedia({reducedMotion: 'reduce'});
  await gotoHome(page);
  // Pins still clustered at zoom 16 need a second, synchronous (reduced-motion) zoom step.
  const ids = await page.evaluate(() => [...document.querySelectorAll('.shop-item')].map(li => li.dataset.id)
    .filter(id => { const m = markerByShopId.get(id); return m && m.__parent && m.__parent._zoom >= 16; }).slice(0, 4));
  expect(ids.length).toBeGreaterThan(1);
  // Moving the map inside MarkerCluster's animationend re-runs its queue: the counter dips below 0.
  await page.evaluate(() => {
    window.minAnimationCount = 0;
    const end = clusterGroup._animationEnd;
    clusterGroup._animationEnd = function () { end.call(this); minAnimationCount = Math.min(minAnimationCount, this._inZoomAnimation); };
  });
  for (const id of ids) {
    // Switch straight from one detail to the next, as clicking pins on the map does.
    await page.evaluate(id => selectShop(SHOPS.find(s => s.id === id)), id);
    await settled(page);
  }
  await page.locator('#backBtn').click();
  await page.waitForTimeout(600);
  // A negative counter makes MarkerCluster skip its moveend work (pins stop updating after pans).
  expect(await page.evaluate(() => minAnimationCount)).toBe(0);
  expect(await page.evaluate(() => clusterGroup._inZoomAnimation)).toBe(0);
});

test('a card opened just after typing stays open without a stale closing announcement', async ({page}) => {
  await gotoHome(page);
  const id = await page.locator('.shop-item').first().getAttribute('data-id');
  const name = await page.evaluate(id => SHOPS.find(s => s.id === id).name, id);
  // The list still shows the old cards for the 80 ms search debounce; this term still matches the card.
  await page.locator('#searchInput').fill(name);
  await page.evaluate(id => document.querySelector(`.shop-item[data-id="${id}"]`).click(), id);
  await page.waitForTimeout(900);
  await expect(page.locator('#panel')).toHaveClass(/detail-mode/);
  await expect(page.locator('#srAnnounce')).not.toContainText('Closed details');
});

test('a stale card that the new search excludes does not open', async ({page}) => {
  await gotoHome(page);
  const id = await page.locator('.shop-item').first().getAttribute('data-id');
  await page.locator('#searchInput').fill('zzzz-no-such-spot');
  await page.evaluate(id => document.querySelector(`.shop-item[data-id="${id}"]`)?.click(), id);
  await page.waitForTimeout(500);
  await expect(page.locator('#panel')).not.toHaveClass(/detail-mode/);
  expect(await page.evaluate(() => state.selected)).toBeNull();
});

test('Home during a reveal zoom returns to the full-region frame', async ({page}) => {
  await gotoHome(page);
  const zoom = await page.evaluate(() => map.getZoom());
  const id = await clusteredAtSixteen(page);
  // The first reveal step jumps to zoom 16 without animating; Home lands during the next, animated step.
  await page.evaluate(id => new Promise(resolve => {
    map.once('zoomanim', () => { document.getElementById('brandHomeBtn').click(); resolve(); });
    document.querySelector(`.shop-item[data-id="${id}"]`).click();
  }), id);
  await expect.poll(() => page.evaluate(() => map.getZoom())).toBe(zoom);
  await page.waitForTimeout(800);
  expect(await page.evaluate(() => map.getZoom())).toBe(zoom);
});

test('Back in the frame before a queued reveal zoom starts still restores the camera', async ({page}) => {
  await gotoHome(page);
  const camera = await page.evaluate(() => ({lat: map.getCenter().lat, lng: map.getCenter().lng, zoom: map.getZoom()}));
  const id = await clusteredAtSixteen(page);
  await page.evaluate(id => {
    // Leaflet queues an animated zoom for one frame before it starts; press Back inside that frame.
    const setView = map.setView;
    let done = false;
    map.setView = function (center, zoom, options) {
      const queued = !done && options?.animate && zoom !== this.getZoom() && Math.abs(zoom - this.getZoom()) <= 4;
      const result = setView.call(this, center, zoom, options);
      if (queued) { done = true; queueMicrotask(() => document.getElementById('backBtn').click()); }
      return result;
    };
    document.querySelector(`.shop-item[data-id="${id}"]`).click();
  }, id);
  await page.waitForTimeout(1500);
  expect(await page.evaluate(() => state.selected)).toBeNull();
  expect(await page.evaluate(() => map.getZoom())).toBe(camera.zoom);
  expect(await page.evaluate(c => map.distance(map.getCenter(), [c.lat, c.lng]), camera)).toBeLessThan(2);
});

test('a wheel zoom during a reveal is not pulled back in', async ({page}) => {
  await gotoHome(page);
  const id = await clusteredAtSixteen(page);
  await page.locator(`.shop-item[data-id="${id}"]`).click();
  await page.locator('#map').hover();
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(400);
  const afterWheel = await page.evaluate(() => map.getZoom());
  expect(afterWheel).toBeLessThan(16);
  await page.waitForTimeout(1500);
  expect(await page.evaluate(() => map.getZoom())).toBe(afterWheel);
});

test('missing MarkerCluster produces an actionable load alert', async ({page}) => {
  await page.route('**/leaflet.markercluster@*/dist/leaflet.markercluster.js', route => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Could not load spots');
});

test('missing Leaflet produces an actionable load alert', async ({page}) => {
  await page.route('**/leaflet@*/dist/leaflet.js', route => route.abort());

  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Could not load spots');
  await expect(page.getByRole('button', {name:'Reload', exact:true})).toBeVisible();
});

test('retry reports failure and success in the same counted status node', async ({page}) => {
  await page.route('**/places.json', route => route.abort());
  await page.goto('/');
  await expect(page.locator('#retryPlacesBtn')).toBeVisible();
  await page.evaluate(() => window.originalStatus = document.querySelector('#dataStatusBanner'));
  await expect(page.locator('#dataStatusBanner')).toContainText(/\d+ spots/);
  await page.locator('#retryPlacesBtn').click();
  await expect(page.locator('#dataStatusBanner')).toContainText('Retry failed');
  await page.unroute('**/places.json');
  await page.locator('#retryPlacesBtn').click();
  await expect(page.locator('#dataStatusBanner')).toContainText('Regional coverage loaded');
  expect(await page.evaluate(() => originalStatus === document.querySelector('#dataStatusBanner'))).toBe(true);
  // The success confirmation must not permanently take list space.
  await expect(page.locator('#dataStatusBanner')).toBeHidden({timeout: 8000});
});

test('keyboard: Retry comes before the list and keeps focus through failure and success', async ({page}) => {
  await page.route('**/places.json', route => route.abort());
  await page.goto('/');
  await expect(page.locator('#retryPlacesBtn')).toBeVisible();
  expect(await page.evaluate(() => !!(document.getElementById('retryPlacesBtn').compareDocumentPosition(document.querySelector('.shop-item')) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true);
  await page.locator('#retryPlacesBtn').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#dataStatusBanner')).toContainText('Retry failed');
  await expect(page.locator('#retryPlacesBtn')).toBeFocused();
  await page.unroute('**/places.json');
  await page.keyboard.press('Enter');
  await expect(page.locator('#dataStatusBanner')).toContainText('Regional coverage loaded');
  expect(await page.evaluate(() => document.activeElement.classList.contains('shop-item'))).toBe(true);
});

test('keyboard-only readers get the list hold', async ({page}) => {
  let release;
  const pending = new Promise(r => release = r);
  await page.route('**/places.json', async route => { await pending; await route.continue(); });
  try {
    await page.goto('/');
    await expect(page.locator('.shop-item').first()).toBeVisible();
    await page.locator('.shop-item').nth(2).focus();
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    await expect(page.getByRole('button', {name: 'Update list', exact: true})).toBeVisible();
  } finally { release(); }
});

test('no Update list prompt when the regional data adds nothing in scope', async ({page}) => {
  let release;
  const pending = new Promise(r => release = r);
  await page.route('**/places.json', async route => {
    await pending;
    const data = await (await route.fetch()).json();
    data.places = data.places.filter(p => p.model === 'franchise'); // hidden in the default Indie view
    await route.fulfill({json: data});
  });
  try {
    await page.goto('/');
    await expect(page.locator('.shop-item').first()).toBeVisible();
    await page.locator('#shopList').hover();
    await page.mouse.wheel(0, 300);
    await page.waitForTimeout(150);
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    await expect(page.getByRole('button', {name: 'Update list', exact: true})).toHaveCount(0);
  } finally { release(); }
});

async function holdRegionWhileReading(page, {abort = false} = {}) {
  let release;
  const pending = new Promise(r => release = r);
  await page.route('**/places.json', async route => { if (abort) return route.abort(); await pending; await route.continue(); });
  await page.goto('/');
  await expect(page.locator('.shop-item').first()).toBeVisible();
  await page.locator('#shopList').hover();
  await page.mouse.wheel(0, 300);
  await page.waitForTimeout(150);
  return release;
}

test('a map gesture refreshes a held reading list', async ({page}) => {
  const release = await holdRegionWhileReading(page);
  try {
    const held = await page.locator('.shop-item').count();
    const seedIndie = await page.evaluate(() => SHOPS.filter(s => s.model !== 'franchise').length);
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    await expect(page.getByRole('button', {name:'Update list', exact:true})).toBeVisible();
    // The count covers only spots the default Indie view will add, not hidden franchises.
    const added = await page.evaluate(n => SHOPS.filter(s => s.model !== 'franchise').length - n, seedIndie);
    await expect(page.locator('#dataStatusBanner')).toContainText(`${added} more spots loaded`);
    expect(await page.locator('.shop-item').count()).toBe(held);
    await page.locator('#map').hover();
    await page.mouse.wheel(0, 200);
    await expect(page.getByRole('button', {name:'Update list', exact:true})).toHaveCount(0);
    await expect.poll(() => page.locator('.shop-item').count()).toBeGreaterThan(held);
  } finally { release(); }
});

test('a successful retry keeps the Update list prompt for a reading user', async ({page}) => {
  await holdRegionWhileReading(page, {abort: true});
  await expect(page.locator('#retryPlacesBtn')).toBeVisible();
  await page.unroute('**/places.json');
  await page.locator('#retryPlacesBtn').click();
  await page.waitForFunction(() => dataLoadState.regional === 'ready');
  await expect(page.getByRole('button', {name:'Update list', exact:true})).toBeVisible();
});

test('hydration with a detail open keeps the reader\'s list for Back', async ({page}) => {
  const release = await holdRegionWhileReading(page);
  try {
    const order = await page.locator('.shop-item').evaluateAll(es => es.map(e => e.dataset.id));
    const id = await page.evaluate(visibleCardId);
    await page.locator(`.shop-item[data-id="${id}"]`).click();
    const scroll = await page.evaluate(() => state.lastScrollTop);
    expect(scroll).toBeGreaterThan(0);
    // Read the detail for a moment first: the selection's camera move must not rewrite the held list.
    await page.waitForTimeout(400);
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    await page.locator('#backBtn').click();
    await expect(page.getByRole('button', {name:'Update list', exact:true})).toBeVisible();
    expect(await page.locator('.shop-item').evaluateAll(es => es.map(e => e.dataset.id))).toEqual(order);
    await expect.poll(() => page.locator('#shopList').evaluate(el => el.scrollTop)).toBe(scroll);
  } finally { release(); }
});

test('Home during partial loading returns to the regional frame instead of fitting the seed', async ({page}) => {
  let release;
  const pending = new Promise(r => release = r);
  await page.route('**/places.json', async route => { await pending; await route.continue(); });
  try {
    await page.goto('/');
    await expect(page.locator('.shop-item').first()).toBeVisible();
    await page.evaluate(() => map.setView([33.97, -84.14], 13, {animate: false}));
    await page.locator('#brandHomeBtn').click();
    await expect.poll(() => page.evaluate(() => map.getZoom())).toBe(9);
  } finally { release(); }
});

test('Home scrolls the list to the top and keeps focus on Home', async ({page}) => {
  await gotoHome(page);
  await page.evaluate(() => map.setView([33.9, -84.25], 11, {animate: false}));
  await page.waitForTimeout(300);
  await page.locator('#shopList').evaluate(el => el.scrollTop = 600);
  await page.waitForTimeout(100);
  await page.locator(`.shop-item[data-id="${await page.evaluate(visibleCardId)}"]`).click();
  await page.locator('#brandHomeBtn').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#panel')).not.toHaveClass(/detail-mode/);
  await expect.poll(() => page.locator('#shopList').evaluate(el => el.scrollTop)).toBe(0);
  await page.waitForTimeout(400);
  expect(await page.locator('#shopList').evaluate(el => el.scrollTop)).toBe(0);
  await expect(page.locator('#brandHomeBtn')).toBeFocused();
});

test('the header stops saying Loading once regional data has failed', async ({page}) => {
  await page.route('**/places.json', route => route.abort());
  await page.goto('/');
  await expect(page.locator('#retryPlacesBtn')).toBeVisible();
  await expect(page.locator('.freshness')).not.toContainText('Loading');
  await expect(page.locator('.freshness')).toContainText('spots in Metro Atlanta');
});

test('Retry restores pins for spots ingested before a failed hydrate', async ({page}) => {
  await gotoHome(page);
  const total = await page.evaluate(() => markerByShopId.size);
  await page.evaluate(() => {
    // The state a hydrate leaves if it throws after ingesting: spots without markers.
    for (const m of markers.splice(-25)) { clusterGroup.removeLayer(m); markerByShopId.delete(m.shopRef.id); }
    dataLoadState.regional = 'failed';
  });
  await page.evaluate(() => retryRegionalLoad());
  await page.waitForFunction(() => dataLoadState.regional === 'ready');
  expect(await page.evaluate(() => markerByShopId.size)).toBe(total);
});

test('shipped rating priors match the loaded regional population', async ({page}) => {
  await gotoHome(page);
  const {shipped, runtime} = await page.evaluate(() => {
    const rated = SHOPS.filter(s => typeof s.rating === 'number');
    const counts = SHOPS.map(s => s.ratingNum || 0).sort((a, b) => a - b);
    return {shipped: shopsDataGlobal.ratingPriors, runtime: {C: rated.reduce((sum, s) => sum + s.rating, 0) / rated.length, m: counts[Math.floor(counts.length / 2)], population: SHOPS.length}};
  });
  expect(runtime.population).toBe(shipped.population);
  expect(runtime.m).toBe(shipped.m);
  expect(runtime.C).toBeCloseTo(shipped.C, 9);
});

test('same-building hydration moves existing pins without revealing excluded franchises', async ({page}) => {
  let release;
  const pending = new Promise(r => release = r);
  await page.route('**/places.json', async route => {
    await pending;
    const response = await route.fetch();
    const data = await response.json();
    const seed = JSON.parse(fs.readFileSync('public/shops.json', 'utf8'));
    const coords = Object.values(seed.addr)[0];
    data.places.push({name:'Regression Espresso',placeId:'regression-same-building',category:'Coffee',...coords,rating:4,ratingNum:10,city:'Duluth'});
    await route.fulfill({json:data});
  });
  try {
    await page.goto('/');
    await expect(page.locator('.shop-item').first()).toBeVisible();
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    expect(await page.evaluate(() => markers.filter(m => !m.getLatLng().equals([m.shopRef.lat,m.shopRef.lng])).map(m=>m.shopRef.name))).toEqual([]);
    expect(await page.evaluate(() => clusterGroup.getLayers().filter(m=>m.shopRef.model === 'franchise').length)).toBe(0);
    expect(await page.locator('.shop-item').evaluateAll(els=>els.some(e=>e.getAttribute('aria-label').includes('andCafe')))).toBe(false);
  } finally { release(); }
});

for (const check of ['scores', 'hit targets', 'reading order', 'card labels']) {
  test(`five-second regional delay preserves ${check}`, async ({page}) => {
    let release;
    const pending = new Promise(r=>release=r);
    await page.route('**/places.json', async route=>{await pending;await route.continue();});
    try {
      await page.goto('/');
      await expect(page.locator('.shop-item').first()).toBeVisible();
      const scores = await page.evaluate(()=>Object.fromEntries(SHOPS.map(s=>[s.id,s.scoreText])));
      if (check === 'hit targets') {
        await page.locator('#searchInput').click({timeout:3000});
        await page.locator('.shop-item').first().click();
        await page.locator('#backBtn').click({timeout:3000});
      }
      if (check === 'card labels') {
        await page.locator('#searchInput').fill('Bakery Duluth');
        await page.waitForTimeout(150);
      }
      if (check === 'reading order') {
        await page.locator('#shopList').hover();
        await page.mouse.wheel(0,400);
        await page.waitForTimeout(200);
      }
      const order = await page.locator('.shop-item').evaluateAll(es=>es.map(e=>e.dataset.id));
      const scroll = await page.locator('#shopList').evaluate(el=>el.scrollTop);
      await page.waitForTimeout(3000);
      release();
      await page.waitForFunction(()=>dataLoadState.regional==='ready');
      if (check === 'scores') expect(await page.evaluate(ids=>Object.fromEntries(SHOPS.filter(s=>ids.includes(s.id)).map(s=>[s.id,s.scoreText])),Object.keys(scores))).toEqual(scores);
      if (check === 'reading order') {
        expect(await page.locator('.shop-item').evaluateAll(es=>es.map(e=>e.dataset.id))).toEqual(order);
        expect(await page.locator('#shopList').evaluate(el=>el.scrollTop)).toBe(scroll);
      }
      if (check === 'card labels') {
        expect(await page.locator('.shop-item').count()).toBeGreaterThan(0);
        expect(await page.locator('.shop-item').evaluateAll(es=>es.some(e=>e.getAttribute('aria-label').includes('andCafe')))).toBe(false);
      }
    } finally {release();}
  });
}

test('network data supersedes stale cache and removes obsolete cache namespaces', async ({page}) => {
  await gotoHome(page);
  await page.evaluate(async()=>{
    for (const name of ['caffeye-v5','caffeye-v6','caffeye-v1']) {
      const cache = await caches.open(name);
      await cache.put('./places.json', new Response(JSON.stringify({places:[{name:'Retired Cache Shop',placeId:'stale',category:'Coffee',lat:33.9,lng:-84.1,rating:5,ratingNum:100}]})));
    }
  });
  await page.reload();
  await page.waitForFunction(()=>window.mapReady && dataLoadState.regional==='ready');
  expect(await page.evaluate(()=>SHOPS.some(s=>s.name==='Retired Cache Shop'))).toBe(false);
  expect(await page.evaluate(()=>caches.keys())).not.toContain('caffeye-v1');
});

test('a slow network serves the cached copy after 2.5 s and still refreshes the cache', async ({page}) => {
  await gotoHome(page);
  await page.evaluate(async () => {
    const data = await (await fetch('./places.json')).json();
    data.places.push({name: 'Stale Cached Espresso', placeId: 'stale-cached', category: 'Coffee', lat: 33.9, lng: -84.1, rating: 4.5, ratingNum: 50, city: 'Duluth'});
    await (await caches.open('caffeye-v6')).put('./places.json', new Response(JSON.stringify(data), {headers: {'Content-Type': 'application/json'}}));
  });
  await page.route('**/places.json', async route => { await new Promise(r => setTimeout(r, 4000)); await route.continue(); });
  await page.reload();
  await page.waitForFunction(() => dataLoadState.regional === 'ready');
  expect(await page.evaluate(() => SHOPS.some(s => s.name === 'Stale Cached Espresso'))).toBe(true);
  // The download kept going in the background and replaced the stale copy for the next visit.
  await expect.poll(() => page.evaluate(async () => {
    const cached = await (await caches.open('caffeye-v6')).match('./places.json');
    return (await cached.json()).places.some(p => p.name === 'Stale Cached Espresso');
  }), {timeout: 15000}).toBe(false);
});

test('landscape viewport leaves safe-area handling to the browser', async ({page}) => {
  await page.goto('/');
  await expect(page.locator('meta[name="viewport"]')).not.toHaveAttribute('content', /viewport-fit=cover/);
});

test('Back during a CSS zoom animation restores the saved camera after zoomend', async ({page}) => {
  await gotoHome(page);
  const spot = await findIsolatedShop(page);
  await page.evaluate(spot=>map.setView([spot.lat,spot.lng],12,{animate:false}),spot);
  const card = page.locator('.shop-item', {hasText:spot.name});
  await expect(card).toBeVisible();
  const camera = await page.evaluate(()=>({lat:map.getCenter().lat,lng:map.getCenter().lng,zoom:map.getZoom()}));
  await card.click();
  await settled(page);
  // Start a real animated zoom (as a wheel or double-click would) and press Back while it runs.
  // Pressing Back from the zoomanim event guarantees the CSS zoom is still in flight.
  const inFlight = await page.evaluate(() => new Promise(resolve => {
    map.once('zoomanim', () => { const animating = map._animatingZoom; document.getElementById('backBtn').click(); resolve(animating); });
    map.setZoom(map.getZoom() + 1, {animate: true});
  }));
  expect(inFlight).toBe(true);
  await expect.poll(()=>page.evaluate(()=>map.getZoom())).toBe(camera.zoom);
  await expect.poll(()=>page.evaluate(c=>map.distance(map.getCenter(),[c.lat,c.lng]),camera)).toBeLessThan(2);
});

test('Back during a CSS zoom restores the list scroll', async ({page}) => {
  await gotoHome(page);
  const zoom = await page.evaluate(() => map.getZoom());
  await page.locator('#shopList').evaluate(el => el.scrollTop = 600);
  await page.waitForTimeout(100);
  const id = await page.evaluate(visibleCardId);
  await page.locator(`.shop-item[data-id="${id}"]`).click();
  // The click may scroll the card into view first; Back must return to the scroll at selection.
  const scroll = await page.evaluate(() => state.lastScrollTop);
  expect(scroll).toBeGreaterThan(0);
  await settled(page);
  await page.evaluate(() => new Promise(resolve => {
    map.once('zoomanim', () => { document.getElementById('backBtn').click(); resolve(); });
    map.setZoom(map.getZoom() + 1, {animate: true});
  }));
  await expect.poll(() => page.evaluate(() => map.getZoom())).toBe(zoom);
  await expect.poll(() => page.locator('#shopList').evaluate(el => el.scrollTop)).toBe(scroll);
});

test('a card selected during a pan reveals and centres its marker', async ({page}) => {
  await gotoHome(page);
  await page.waitForFunction(() => !map._animatingZoom && !(clusterGroup._inZoomAnimation > 0));
  const id = await page.locator('.shop-item').nth(7).getAttribute('data-id');
  const listeners = await page.evaluate(()=>map._events.moveend.length);
  // Click from the pan's first move event so the pan is guaranteed to be in flight.
  const inFlight = await page.evaluate(id => new Promise(resolve => {
    map.once('move', () => { const panning = !!map._panAnim?._inProgress; document.querySelector(`.shop-item[data-id="${id}"]`).click(); resolve(panning); });
    map.panBy([400, 0], {animate: true, duration: .8});
  }), id);
  expect(inFlight).toBe(true);
  await settled(page);
  expect(await page.evaluate(()=>map.getZoom())).toBeGreaterThanOrEqual(16);
  expect(await page.evaluate(()=>map._events.moveend.length)).toBe(listeners);
});

// Opt-in vector preview (?renderer=vector).
async function vectorReady(page) {
  await page.goto('/?renderer=vector');
  await page.waitForFunction(() => window.mapReady && dataLoadState.regional === 'ready' && window.renderer === 'vector');
}
const loseContext = () => {
  const canvas = map.getCanvas();
  window.__lose = (canvas.getContext('webgl2') || canvas.getContext('webgl')).getExtension('WEBGL_lose_context');
  __lose.loseContext();
};

test('vector: a restored context keeps the vector map and applies changes made while it was lost', async ({page}) => {
  await vectorReady(page);
  await page.evaluate(loseContext);
  // UI changes during the loss must not throw (the fixture fails on page errors).
  await page.locator('[data-chip-key="cat-Tea/Boba"]').click();
  await page.locator('#themeToggle').click();
  await page.waitForTimeout(300);
  await page.evaluate(() => __lose.restoreContext());
  const tea = await page.evaluate(() => SHOPS.filter(s => s.category === 'Tea/Boba' && s.model !== 'franchise').length);
  await expect.poll(() => page.evaluate(async () => map.style && map.getSource('cafes') ? (await map.getSource('cafes').getData()).features.length : -1)).toBe(tea);
  await page.waitForTimeout(3500);
  expect(await page.evaluate(() => window.renderer)).toBe('vector');
});

test('vector: a context lost in a hidden tab waits for visibility before falling back', async ({page}) => {
  await vectorReady(page);
  await page.evaluate(() => Object.defineProperty(document, 'hidden', {configurable: true, get: () => true}));
  await page.evaluate(loseContext);
  await page.waitForTimeout(4000);
  expect(await page.evaluate(() => window.renderer)).toBe('vector');
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect.poll(() => page.evaluate(() => window.renderer), {timeout: 8000}).toBe('leaflet');
});

test('vector: the regional fit shows every spot at phone and desktop sizes; the map stays in the Southeast', async ({page}) => {
  // 821x600 is the narrowest desktop layout. Below about 150 px of map height both renderers hit minZoom first.
  for (const size of [{width: 1280, height: 800}, {width: 821, height: 600}, {width: 375, height: 750}, {width: 320, height: 568}]) {
    await page.setViewportSize(size);
    await vectorReady(page);
    await page.waitForFunction(() => !map.isMoving());
    const outside = await page.evaluate(() => { const b = map.getBounds(); return SHOPS.filter(s => s.model !== 'franchise' && !b.contains([s.lng, s.lat])).length; });
    expect(outside, `${size.width}x${size.height}`).toBe(0);
  }
  await page.setViewportSize({width: 1280, height: 800});
  await page.evaluate(() => map.jumpTo({center: [-74.0, 40.7], zoom: 10}));
  expect(await page.evaluate(() => map.getCenter().lng)).toBeLessThan(-81.3);
  await page.evaluate(() => map.jumpTo({center: [-84.3, 33.85], zoom: 8}));
  await page.locator('[data-chip-key="cat-Tea/Boba"]').click();
  const tea = await page.evaluate(() => SHOPS.filter(s => s.category === 'Tea/Boba' && s.model !== 'franchise').length);
  await expect(page.locator('.maplibregl-canvas')).toHaveAttribute('aria-label', new RegExp(`with ${tea} matching spots`));
  await page.locator('.shop-item').first().click();
  const name = await page.evaluate(() => state.selected.name);
  await expect(page.locator('.maplibregl-canvas')).toHaveAttribute('aria-label', new RegExp(`${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')} selected`));
});

test('vector: MapLibre assets carry SRI and app control styles win in dark mode', async ({page}) => {
  await vectorReady(page);
  for (const selector of ['script[src*="maplibre-gl.js"]', 'link[href*="maplibre-gl.css"]']) {
    await expect(page.locator(selector)).toHaveAttribute('integrity', /^sha384-/);
    await expect(page.locator(selector)).toHaveAttribute('crossorigin', 'anonymous');
  }
  expect(await page.evaluate(() => {
    const css = document.querySelector('link[href*="maplibre-gl.css"]');
    return !!(css.compareDocumentPosition(document.querySelector('head style')) & Node.DOCUMENT_POSITION_FOLLOWING);
  })).toBe(true);
  await page.evaluate(() => applyTheme('dark'));
  expect(await page.evaluate(() => getComputedStyle(document.querySelector('.maplibregl-ctrl-group')).backgroundColor)).not.toBe('rgb(255, 255, 255)');
});

test('vector: a basemap outage keeps its notice until tiles load', async ({page}) => {
  // Fail the vector tiles but not the TileJSON, so the source can recover.
  await page.route('https://tiles.openfreemap.org/planet/**', route => route.abort());
  await page.goto('/?renderer=vector');
  await expect(page.locator('#mapLoadStatus')).toBeVisible({timeout: 10000});
  await page.waitForTimeout(2000);
  await expect(page.locator('#mapLoadStatus')).toBeVisible();
  await page.unroute('https://tiles.openfreemap.org/planet/**');
  await page.evaluate(() => map.jumpTo({zoom: map.getZoom() + 1}));
  await expect(page.locator('#mapLoadStatus')).toHaveCount(0, {timeout: 10000});
});

test('vector: a missing MapLibre stylesheet falls back to the standard map', async ({page}) => {
  await page.route('**/maplibre-gl@*/dist/maplibre-gl.css', route => route.abort());
  await page.goto('/?renderer=vector');
  await expect(page.locator('.shop-item').first()).toBeVisible();
  await expect(page.locator('.renderer-note')).toContainText('Showing the standard map');
  expect(await page.evaluate(() => window.renderer)).toBe('leaflet');
});

test('vector: partial loading keeps the regional frame, and the map gets regional spots while the list is held', async ({page}) => {
  let release;
  const pending = new Promise(r => release = r);
  await page.route('**/places.json', async route => { await pending; await route.continue(); });
  try {
    await page.goto('/?renderer=vector');
    await page.waitForFunction(() => window.mapReady && window.renderer === 'vector');
    expect(await page.evaluate(() => map.getZoom())).toBeLessThanOrEqual(8.01);
    const seedFeatures = await page.evaluate(async () => (await map.getSource('cafes').getData()).features.length);
    await page.locator('#shopList').hover();
    await page.mouse.wheel(0, 300);
    await page.waitForTimeout(150);
    release();
    await page.waitForFunction(() => dataLoadState.regional === 'ready');
    await expect(page.getByRole('button', {name: 'Update list', exact: true})).toBeVisible();
    await expect.poll(() => page.evaluate(async () => (await map.getSource('cafes').getData()).features.length)).toBeGreaterThan(seedFeatures);
  } finally { release(); }
});

test('vector: a list-mode fallback floors the zoom and keeps the list scroll', async ({page}) => {
  await vectorReady(page);
  await page.evaluate(() => map.jumpTo({center: [-84.2, 33.9], zoom: 10.6}));
  await page.waitForTimeout(300);
  await page.locator('#shopList').evaluate(el => el.scrollTop = 300);
  // The card crossing the top edge is the one the list keeps in place.
  const topCard = () => { const list = document.getElementById('shopList'); const li = [...list.querySelectorAll('.shop-item')].find(li => li.offsetTop + li.offsetHeight > list.scrollTop); return {id: li.dataset.id, offset: list.scrollTop - li.offsetTop}; };
  const top = await page.evaluate(topCard);
  await page.evaluate(loseContext);
  await expect.poll(() => page.evaluate(() => window.renderer), {timeout: 10000}).toBe('leaflet');
  // MapLibre 10.6 is Leaflet 11.6; flooring to 11 keeps everything the user could see.
  expect(await page.evaluate(() => map.getZoom())).toBe(11);
  // The list grows for the wider view; the card the user was reading stays at the top.
  expect(await page.evaluate(topCard)).toEqual(top);
});

test('vector: a fallback keeps focus on a detail link or moves it from the canvas to the map', async ({page}) => {
  await vectorReady(page);
  await page.locator('.shop-item').first().click();
  await page.waitForFunction(() => !map.isMoving());
  await page.locator('#detailView .actions a').first().focus();
  const link = await page.evaluate(() => document.activeElement.textContent);
  await page.evaluate(loseContext);
  await expect.poll(() => page.evaluate(() => window.renderer), {timeout: 10000}).toBe('leaflet');
  expect(await page.evaluate(() => document.activeElement.textContent)).toBe(link);
  await page.goto('/?renderer=vector');
  await page.waitForFunction(() => window.mapReady && dataLoadState.regional === 'ready' && window.renderer === 'vector');
  await page.locator('.maplibregl-canvas').focus();
  await page.evaluate(loseContext);
  await expect.poll(() => page.evaluate(() => window.renderer), {timeout: 10000}).toBe('leaflet');
  expect(await page.evaluate(() => document.activeElement.classList.contains('leaflet-container'))).toBe(true);
});

test('vector: Back after a fallback restores the pre-selection camera in Leaflet zoom', async ({page}) => {
  await vectorReady(page);
  await page.evaluate(() => map.jumpTo({center: [-84.2, 33.9], zoom: 9.3}));
  await page.waitForTimeout(300);
  await page.locator('.shop-item').first().click();
  await page.waitForFunction(() => !map.isMoving());
  await page.evaluate(loseContext);
  await expect.poll(() => page.evaluate(() => window.renderer), {timeout: 10000}).toBe('leaflet');
  await page.locator('#backBtn').click();
  await expect.poll(() => page.evaluate(() => map.getZoom())).toBe(10);
  expect(await page.evaluate(() => map.distance(map.getCenter(), [33.9, -84.2]))).toBeLessThan(200);
});

test('vector: a hanging renderer download falls back to the standard map within the budget', async ({page}) => {
  await page.route('**/maplibre-gl@*/dist/maplibre-gl.js', () => {});
  const start = Date.now();
  // The hanging script would block the load event, so wait for the DOM only.
  await page.goto('/?renderer=vector', {waitUntil: 'domcontentloaded'});
  await expect(page.locator('.shop-item').first()).toBeVisible({timeout: 6000});
  expect(Date.now() - start).toBeLessThan(5500);
  await expect(page.locator('.renderer-note')).toContainText('Showing the standard map');
});
