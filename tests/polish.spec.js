const { test, expect, gotoHome, searchAndOpen } = require('./helpers');

// Resolve alpha backgrounds through the ancestor stack before measuring text.
async function textContrast(locator) {
  return locator.evaluate(el => {
    const ctx = document.createElement('canvas').getContext('2d');
    const rgba = color => {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = color;
      ctx.fillRect(0, 0, 1, 1);
      return [...ctx.getImageData(0, 0, 1, 1).data];
    };
    const over = (fg, bg) => fg.slice(0, 3).map((v, i) => v * fg[3] / 255 + bg[i] * (1 - fg[3] / 255));
    const ancestors = [];
    for (let node = el; node; node = node.parentElement) ancestors.unshift(node);
    const background = ancestors.reduce((bg, node) => over(rgba(getComputedStyle(node).backgroundColor), bg), [255, 255, 255]);
    const foreground = over(rgba(getComputedStyle(el).color), background);
    const luminance = rgb => rgb.map(c => {
      c /= 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    }).reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
    const a = luminance(foreground), b = luminance(background);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  });
}

test.use({ reducedMotion: 'reduce' });

for (const mode of ['explicit', 'system', 'css-fallback']) {
  test(`dark badges and controls remain legible (${mode})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: mode === 'explicit' ? 'light' : 'dark' });
    if (mode === 'explicit') await page.addInitScript(() => localStorage.setItem('caffeye-theme', 'dark'));
    await gotoHome(page);
    if (mode === 'css-fallback') await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
    await page.locator('label[for="franchiseToggle"]').click();
    for (const selector of ['.model-tag.indie', '.model-tag.franchise', '.curated-tag']) {
      expect(await textContrast(page.locator(selector).first()), selector).toBeGreaterThanOrEqual(4.5);
    }
    await expect(page.locator('.toggle-switch')).toHaveCSS('background-color', 'rgb(220, 175, 89)');
    await page.locator('#themeToggle').focus();
    await page.keyboard.press('Shift+Tab');
    await expect(page.locator('#franchiseToggle')).toBeFocused();
    await expect(page.locator('.toggle-switch')).toHaveCSS('outline-color', 'rgb(220, 175, 89)');
    await expect(page.locator('.leaflet-control-zoom-in')).toHaveCSS('background-color', 'rgb(33, 40, 34)');
    await searchAndOpen(page, 'Hayat Coffee');
    for (const selector of ['.pill-tag.work', '.pill-tag.late']) {
      expect(await textContrast(page.locator(selector).first()), selector).toBeGreaterThanOrEqual(4.5);
    }
  });
}

test('explicit light theme overrides a dark system', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.addInitScript(() => localStorage.setItem('caffeye-theme', 'light'));
  await gotoHome(page);
  await expect(page.locator('.model-tag.indie').first()).toHaveCSS('color', 'rgb(46, 125, 79)');
  await page.locator('label[for="franchiseToggle"]').click();
  await expect(page.locator('.toggle-switch')).toHaveCSS('background-color', 'rgb(41, 63, 52)');
});
