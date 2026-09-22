const { test, expect } = require('./helpers');

test.describe('performance budget (T6)', () => {
  test('LCP is under budget on seed load', async ({ page }) => {
    await page.goto('/?renderer=vector');
    await page.waitForFunction(() => window.mapReady);
    const lcp = await page.evaluate(() => {
      return new Promise(resolve => {
        new PerformanceObserver(list => {
          const entries = list.getEntriesByType('largest-contentful-paint');
          if (entries.length) resolve(entries[entries.length - 1].startTime);
        }).observe({ type: 'largest-contentful-paint', buffered: true });
        setTimeout(() => resolve(performance.now()), 2000);
      });
    });
    // In headless testing with SwiftShader, allow realistic threshold
    expect(lcp).toBeLessThan(2500);
  });

  test('vector ready event is tracked and completes within threshold', async ({ page }) => {
    await page.goto('/?renderer=vector');
    await page.waitForFunction(() => window.mapReady && window.renderer === 'vector');
    const readyMetric = await page.evaluate(() => {
      return window.__telemetryLog?.find(e => e.event === 'vector_ready');
    });
    expect(readyMetric).toBeDefined();
    expect(readyMetric.properties.duration_ms).toBeLessThan(3500);
  });
});
