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
      await page.evaluate(() => {
        const shops = SHOPS.filter(s => s.curated && s.model !== 'franchise');
        selectShop(shops[0]);
        selectShop(shops[1]);
      });
      expect(await page.evaluate(() => map.getZoom())).toBeGreaterThanOrEqual(15);
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
        await expect(page.locator('.maplibregl-canvas')).toHaveAttribute('role', 'img');
        await expect(page.locator('.leaflet-marker-icon, .maplibregl-marker')).toHaveCount(0);
        await page.locator('[data-chip-key="cat-Tea/Boba"]').click();
        await expect.poll(() => page.evaluate(async () => {
          const data = await map.getSource('cafes').getData();
          return data.features.length;
        })).toBe(await page.evaluate(() => SHOPS.filter(s => s.category === 'Tea/Boba' && s.model !== 'franchise').length));
        // Work from a rendered point, not an implementation-only selection hook.
        const shop = await page.evaluate(() => {
          const shop = SHOPS.find(s => s.category === 'Tea/Boba' && s.model !== 'franchise');
          map.jumpTo({ center: [shop.lng, shop.lat], zoom: 18 });
          return { id: shop.id, lat: shop.lat, lng: shop.lng };
        });
        await page.waitForFunction(() => map.isSourceLoaded('cafes') && !map.isMoving());
        await expect.poll(() => page.evaluate(() => map.queryRenderedFeatures({ layers: ['cafes'] }).length)).toBeGreaterThan(0);
        const point = await page.evaluate(shop => { const p = map.project([shop.lng, shop.lat]); return { x: p.x, y: p.y }; }, shop);
        const canvas = page.locator('.maplibregl-canvas');
        if (!test.info().project.use.hasTouch) {
          const box = await canvas.boundingBox();
          await page.mouse.move(box.x + point.x, box.y + point.y);
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

test('WebGL context loss timeout recovers runtime map to Leaflet while preserving selection', async ({ page }) => {
  await page.goto('/?renderer=vector');
  await page.waitForFunction(() => window.mapReady && window.renderer === 'vector');
  // Select a venue while in vector mode
  await page.locator('.shop-item').first().click();
  await expect(page.locator('#backBtn')).toBeVisible();
  const selectedId = await page.evaluate(() => window.state.selected?.id);

  await page.evaluate(() => {
    const canvas = document.querySelector('.maplibregl-canvas');
    canvas.dispatchEvent(new Event('webglcontextlost', { bubbles: true, cancelable: true }));
  });
  await expect.poll(() => page.evaluate(() => window.renderer), { timeout: 6000 }).toBe('leaflet');
  await expect(page.locator('.leaflet-container')).toBeVisible();
  // State preservation: selection and detail view remain active
  expect(await page.evaluate(() => window.state.selected?.id)).toBe(selectedId);
  await expect(page.locator('#backBtn')).toBeVisible();
  const fallbackLog = await page.evaluate(() => window.__telemetryLog?.find(e => e.event === 'vector_fallback'));
  expect(fallbackLog).toBeDefined();
  expect(fallbackLog.properties.reason).toBe('context_loss_timeout');
});

test('selecting clustered shop from list unclusters marker so it is visible in Leaflet', async ({ page }) => {
  await page.goto('/');
  await page.waitForFunction(() => window.mapReady && window.dataLoadState.regional === 'ready');
  // Click first shop item from the list while at regional zoom
  await page.locator('.shop-item').first().click();
  await expect(page.locator('#backBtn')).toBeVisible();
  // Ensure the selected shop's marker is unclustered and attached to DOM
  await expect.poll(async () => {
    return page.evaluate(() => {
      const s = window.state.selected;
      if (!s) return false;
      const m = window.markerByShopId.get(s.id);
      return !!(m && m._icon && m._icon.parentElement);
    });
  }, { timeout: 5000 }).toBe(true);
});

