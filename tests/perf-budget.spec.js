const { test, expect } = require('./helpers');

test.describe('performance budget (T13)', () => {
  // Final LCP (T13.1) is measured manually: the LCP element is a third-party CARTO tile, so
  // an automated budget would track CARTO's latency more than this page. See TESTS.md T13.1.
  test('default renderer startup TBT at 4x CPU', async ({page}) => {
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Emulation.setCPUThrottlingRate', {rate:4});
    await page.addInitScript(() => {
      window.longTasks = [];
      new PerformanceObserver(list => longTasks.push(...list.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});
    });
    await page.goto('/');
    await page.waitForFunction(() => window.mapReady && dataLoadState.regional === 'ready');
    await page.waitForTimeout(1000);
    const tbt = await page.evaluate(() => longTasks.reduce((sum,e)=>sum+Math.max(0,e.duration-50),0));
    // Report-only: the 300 ms target (T13.2) is checked by hand; this reading swings with machine load.
    console.log(`4x CPU startup TBT: ${tbt.toFixed(1)} ms (target ≤ 300 ms)`);
    test.info().annotations.push({ type: 'TBT', description: `${tbt.toFixed(1)} ms at 4x CPU` });
    expect(tbt).toBeGreaterThan(0);
  });
  test('vector ready event meets the typical startup budget', async ({ page }) => {
    await page.goto('/?renderer=vector');
    await page.waitForFunction(() => window.mapReady && window.renderer === 'vector');
    const metric = await page.evaluate(() => __telemetryLog.find(e => e.event === 'vector_ready'));
    expect(metric).toBeDefined();
    expect(metric.properties.duration_ms).toBeLessThanOrEqual(1800);
  });
});
