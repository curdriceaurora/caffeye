const { test, expect } = require('./helpers');

for (const renderer of ['leaflet', 'vector']) {
  test.describe(renderer, () => {
    test.use({ reducedMotion: 'reduce' });
    test.beforeEach(async ({ page }) => {
      await page.goto(renderer === 'vector' ? '/?renderer=vector' : '/');
      await page.waitForFunction(() => window.mapReady && window.dataLoadState.regional === 'ready');
      expect(await page.evaluate(() => window.renderer)).toBe(renderer);
    });

    test('switching selected shops retains the original camera, and Back restores it', async ({ page }) => {
      await page.evaluate(() => {
        if (window.renderer === 'vector') map.jumpTo({ center: [-84.14, 33.97], zoom: 15 });
        else map.setView([33.97, -84.14], 15, { animate: false });
      });
      const before = await page.evaluate(() => ({ lat: map.getCenter().lat, lng: map.getCenter().lng, zoom: map.getZoom() }));
      await page.evaluate(() => selectShop(SHOPS.find(s => s.curated && s.model !== 'franchise')));
      await page.waitForFunction(() => !map._animatingZoom && (window.renderer !== 'vector' || !map.isMoving()) && Math.abs(map.getCenter().lat - state.selected.lat) < .00001);
      expect(await page.evaluate(() => ({lat: map.getCenter().lat, lng: map.getCenter().lng, zoom:map.getZoom()}))).not.toEqual(before);
      await page.evaluate(() => selectShop(SHOPS.filter(s => s.curated && s.model !== 'franchise')[1]));
      await expect.poll(() => page.evaluate(() => Math.hypot(map.getCenter().lat - state.selected.lat, map.getCenter().lng - state.selected.lng))).toBeLessThan(.00001);
      await page.locator('#backBtn').click();
      await expect.poll(() => page.evaluate(() => map.getZoom())).toBe(before.zoom);
      const after = await page.evaluate(() => ({ lat: map.getCenter().lat, lng: map.getCenter().lng }));
      expect(after.lat).toBeCloseTo(before.lat, 5);
      expect(after.lng).toBeCloseTo(before.lng, 5);
      await expect(page.locator('#panel')).not.toHaveClass(/detail-mode/);
    });

    test('container resize updates the renderer without a window resize', async ({ page }) => {
      const width = page.viewportSize().width;
      await page.locator('#map').evaluate((el) => {
        el.style.flex = 'none';
        el.style.width = '250px';
        el.style.height = '190px';
      });
      await expect.poll(() => page.evaluate(() => window.renderer === 'vector' ? map.getCanvas().clientWidth : map.getSize().x)).toBe(250);
      expect(page.viewportSize().width).toBe(width);
    });

    test('Back interrupts a selection animation and restores the browsing camera', async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'no-preference' });
      await page.evaluate(() => window.renderer === 'vector' ? map.jumpTo({center:[-84.14,33.97],zoom:11}) : map.setView([33.97,-84.14],12,{animate:false}));
      const before = await page.evaluate(() => {
        const camera = { center: map.getCenter(), zoom: map.getZoom() };
        selectShop(SHOPS.find(s => s.curated && s.model !== 'franchise'));
        return camera;
      });
      await page.locator('#backBtn').click();
      await expect.poll(() => page.evaluate(() => map.getZoom())).toBe(before.zoom);
      await expect.poll(() => page.evaluate(center => {
        const current = map.getCenter();
        return Math.hypot(current.lat - center.lat, current.lng - center.lng);
      }, before.center)).toBeLessThan(0.00001);
    });

    if (renderer === 'vector') {
      test('canvas points follow filters, support direct selection and theme changes', async ({ page }) => {
        await expect(page.locator('.maplibregl-canvas')).toHaveCount(1);
        await expect(page.locator('.maplibregl-canvas')).toHaveAttribute('role', 'region');
        await expect(page.locator('.maplibregl-canvas')).toHaveAttribute('aria-label', /Coffee shop map with \d+ matching spots/);
        await expect(page.locator('.leaflet-marker-icon, .maplibregl-marker')).toHaveCount(0);
        await page.locator('[data-chip-key="cat-Tea/Boba"]').click();
        await expect.poll(() => page.evaluate(async () => {
          const data = await map.getSource('cafes').getData();
          return data.features.length;
        })).toBe(await page.evaluate(() => SHOPS.filter(s => s.category === 'Tea/Boba' && s.model !== 'franchise').length));
        // Work from a rendered point, not an implementation-only selection hook.
        const shop = await page.evaluate(() => {
          const shop = SHOPS.find(s => s.category === 'Tea/Boba' && s.model !== 'franchise');
          window.vectorIdle = new Promise(resolve => map.once('idle', resolve));
          map.jumpTo({ center: [shop.lng, shop.lat], zoom: 18 });
          return { id: shop.id, lat: shop.lat, lng: shop.lng };
        });
        await page.evaluate(() => window.vectorIdle);
        await page.waitForFunction(() => map.isSourceLoaded('cafes') && !map.isMoving());
        await expect.poll(() => page.evaluate(() => map.queryRenderedFeatures({ layers: ['cafes'] }).length)).toBeGreaterThan(0);
        const point = await page.evaluate(shop => { const p = map.project([shop.lng, shop.lat]); return { x: p.x, y: p.y }; }, shop);
        const canvas = page.locator('.maplibregl-canvas');
        if (!test.info().project.use.hasTouch) {
          const box = await canvas.boundingBox();
          await page.mouse.move(box.x + point.x, box.y + point.y, {steps: 12});
          await expect.poll(() => page.evaluate(async () => (await map.getSource('highlight').getData()).features[0]?.properties.id)).toBe(shop.id);
          await expect.poll(() => page.evaluate(() => map.getPaintProperty('cafes', 'circle-opacity'))).toBe(0.48);
          await page.mouse.move(0, 0);
          await expect.poll(() => page.evaluate(() => map.getPaintProperty('cafes', 'circle-opacity'))).toBe(0.92);
        }
        await canvas.click({ position: point });
        await expect(page.locator('#backBtn')).toBeVisible();
        expect(await page.evaluate(() => state.selected.id)).toBe(shop.id);
        const before = await page.evaluate(() => map.getPaintProperty('land', 'background-color'));
        await page.locator('#themeToggle').click();
        await expect.poll(() => page.evaluate(() => map.getPaintProperty('land', 'background-color'))).not.toBe(before);
        await expect(page.locator('.maplibregl-canvas')).toHaveCount(1);
      });
    }
  });
}

test('vector dependency failure recovers to the standard map', async ({ page }) => {
  await page.route('**/maplibre-gl@*/dist/maplibre-gl.js', route => route.abort());
  await page.goto('/?renderer=vector');
  await expect(page.locator('.shop-item').first()).toBeVisible();
  await expect(page.locator('.renderer-note')).toContainText('Showing the standard map');
  expect(await page.evaluate(() => renderer)).toBe('leaflet');
});

test('telemetry dispatcher records vector startup and dataset load events', async ({ page }) => {
  await page.goto('/?renderer=vector');
  await page.waitForFunction(() => window.mapReady && window.dataLoadState.regional === 'ready');
  const events = await page.evaluate(() => (window.__telemetryLog || []).map(e => e.event));
  expect(events).toContain('vector_attempt');
  expect(events).toContain('vector_ready');
  expect(events).toContain('dataset_load');
});

test('real WebGL context loss falls back once and preserves camera, selection and list state', async ({ page }) => {
  await page.goto('/?renderer=vector');
  await page.waitForFunction(() => window.mapReady && dataLoadState.regional === 'ready' && window.renderer === 'vector');
  await page.locator('.shop-item').first().click();
  await page.waitForFunction(() => !map.isMoving());
  const before = await page.evaluate(() => {
    state.listLimit = 400;
    return {id: state.selected.id, lat:map.getCenter().lat,lng:map.getCenter().lng,zoom:map.getZoom(),limit:state.listLimit,scroll:document.querySelector('#shopList').scrollTop};
  });
  await page.evaluate(() => {
    const gl = map.getCanvas().getContext('webgl2') || map.getCanvas().getContext('webgl');
    gl.getExtension('WEBGL_lose_context').loseContext();
  });
  await expect.poll(() => page.evaluate(() => window.renderer), {timeout:10000}).toBe('leaflet');
  await page.waitForTimeout(3700);
  expect(await page.locator('.leaflet-pane').count()).toBeGreaterThan(0);
  expect(await page.locator('.leaflet-tile').count()).toBeGreaterThan(0);
  expect(await page.locator('.leaflet-marker-icon').count()).toBeGreaterThan(0);
  expect(await page.evaluate(() => __telemetryLog.filter(e=>e.event==='vector_fallback').length)).toBe(1);
  expect(await page.evaluate(() => state.selected.id)).toBe(before.id);
  expect(await page.evaluate(() => map.getZoom())).toBe(before.zoom+1);
  // Leaflet rounds pan centres to pixels; retain the camera within one pixel.
  expect(await page.evaluate(before => map.latLngToContainerPoint([before.lat,before.lng]).distanceTo(map.getSize().divideBy(2)), before)).toBeLessThanOrEqual(1);
  expect(await page.evaluate(() => state.listLimit)).toBe(before.limit);
  expect(await page.locator('#shopList').evaluate(el=>el.scrollTop)).toBe(before.scroll);
  expect(await page.evaluate(() => {const m=markerByShopId.get(state.selected.id);return clusterGroup.getVisibleParent(m)===m;})).toBe(true);
  await expect(page.locator('#backBtn')).toBeFocused();
});
