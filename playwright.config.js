const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60 * 1000,
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8765',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'node tests/static-server.js 8765',
    url: 'http://127.0.0.1:8765',
    reuseExistingServer: !process.env.CI,
    timeout: 30 * 1000,
  },
  projects: [
    {
      // Desktop runs the full matrix.
      name: 'desktop',
      use: { viewport: { width: 1280, height: 800 } },
    },
    {
      // Mobile projects run the baseline plus mobile-specific specs only,
      // so per-file suites don't triple CI runtime.
      name: 'mobile-375',
      testMatch: [/browser\.spec\.js/, /responsive-mobile\.spec\.js/, /map-rendering\.spec\.js/],
      use: {
        viewport: { width: 375, height: 750 },
        isMobile: true,
        hasTouch: true,
      },
    },
    {
      name: 'mobile-320',
      testMatch: [/browser\.spec\.js/, /responsive-mobile\.spec\.js/, /map-rendering\.spec\.js/],
      use: {
        viewport: { width: 320, height: 568 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
