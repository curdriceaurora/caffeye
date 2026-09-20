# Caffeye · Bean eye · Brand pack v1.0

Start with **brand-guide.html** for the visual guide and **previews/brand-board.png** for the overview. All files work offline. This pack is independent of the live application; no application styling or deployment has been changed.

## Choose an asset

| Need | File |
|---|---|
| Header or document logo | `logos/caffeye-horizontal-forest.svg` |
| Dark background | `logos/caffeye-horizontal-paper.svg` |
| Compact square placement | `logos/caffeye-stacked-forest.svg` |
| Symbol | `logos/caffeye-symbol-forest.svg` |
| Small symbol, 16–24 px | `logos/caffeye-symbol-micro.svg` |
| Browser favicon | `icons/favicon.svg` and `icons/favicon.ico` |
| Apple home screen | `icons/apple-touch-icon.png` |
| App icon master | `icons/caffeye-app-forest-1024.png` |
| Maskable app icon | `icons/icon-maskable-512.png` |
| Social avatar | `social/caffeye-avatar-forest.png` |
| Link sharing image | `social/caffeye-share-1200x630.png` |
| Design / engineering colors | `tokens/brand-tokens.json` and `.css` |

All four logo arrangements include forest, paper, black and white versions. PNG logo exports have transparent backgrounds. App icons and social assets intentionally have opaque backgrounds. SVG lettering is converted to paths and needs no installed fonts. Do not use the white/paper logo on a white background.

## Identity

**Position:** A local with an eye for good spots. The eye signals considered recommendations; the bean connects the name to coffee. Coffee is the entry point, while the language explicitly welcomes bakeries and tea shops.

**Primary line:** We know a spot.

**Secondary line:** An eye for good spots.

Keep the name lowercase in the logo: **caffeye**. Use **Caffeye** in prose. Taglines are for sharing and brand materials; the map interface still opens directly to useful information.

## Color

| Name | Hex | Role |
|---|---|---|
| Forest | `#293F34` | Logo, primary text, strong backgrounds |
| Paper | `#F4F3ED` | Supporting backgrounds and reversed logo |
| Gold | `#DCAF59` | Small accents; forest text on gold |
| Ink | `#222721` | Body text |
| Muted | `#60645F` | Secondary text |
| White | `#FFFFFF` | Clean canvas |

Exact sRGB contrast measurements are in `tokens/brand-tokens.json`. Gold is not a small-text color on paper or white; do not set white text on gold. Existing app category colors remain a separate information system.

## Typography

The wordmark is set from **Fraunces 800**, optical size 72, softness 50, wonk 1, with adjusted tracking and outlined glyphs. Treat the supplied wordmark as artwork; do not recreate it by typing the name.

Use Fraunces for a few short display headlines and **Inter 400 / 500 / 600** for body copy, captions and UI. Both variable fonts and their SIL Open Font License files are in `fonts/`. The fonts were obtained from the official [Google Fonts repository](https://github.com/google/fonts), with Fraunces project details at [Google Fonts / Fraunces](https://github.com/googlefonts/fraunces). Font licenses govern the included fonts; the project’s existing license governs the original pack artwork and source.

## Logo use

- Preserve at least one visible eye-symbol height of clear space around the logo. The SVG canvas padding is not the full clear-space allowance.
- Minimum recommended widths: horizontal logo 160 px; stacked logo 120 px; standard symbol 32 px. Use the optical micro version at 16–24 px. Test in the actual placement.
- For print, use vector artwork; start at 35 mm for the horizontal logo and 10 mm for the symbol. These assets use sRGB. A printer should handle CMYK conversion and proofing.
- Use forest or black on light backgrounds, paper or white on dark backgrounds.
- Keep proportions, orientation and spacing intact. Do not add gradients, shadows, outlines, steam, map pins or a second symbol.
- The bean seam must remain transparent. The SVG uses a mask; verify mask support if importing into a print or cutting workflow. PNG exports have the seam baked into the alpha channel.
- Icons have square full-bleed backgrounds; let the destination platform apply its own corner shape. The maskable icon keeps the visible mark within the central safe circle.

## Voice

Specific, local, confident and conversational. Make a useful recommendation without making unsupported claims.

| Use | Avoid |
|---|---|
| “We know a spot.” | “Your ultimate café discovery platform.” |
| “Coffee, bakeries & tea.” | “Amazing hidden gems for every coffee lover!” |
| “Room for a laptop.” — when verified | “Perfect for productivity.” |
| “Open until 10.” — when verified | “Always here for your late-night cravings.” |

## Website integration

Copy `icons/` into the website's public `/brand/icons/` directory and the share PNG into `/brand/social/`. Then add:

```html
<link rel="icon" type="image/svg+xml" href="/brand/icons/favicon.svg">
<link rel="icon" sizes="16x16 32x32 48x48" href="/brand/icons/favicon.ico">
<link rel="apple-touch-icon" sizes="180x180" href="/brand/icons/apple-touch-icon.png">
<meta name="theme-color" content="#293F34">
```

For Open Graph metadata, set `og:image` to the **absolute production URL** of `caffeye-share-1200x630.png`, with width 1200 and height 630. Set the image alt text to “Caffeye. We know a spot. Coffee, bakeries and tea.” Choose the actual production origin during integration; none is assumed in this pack.

The icon set includes 192 and 512 px images for a future web manifest. A manifest or service worker is not included because installation behavior belongs to the app, not the brand assets.

## Rebuilding

Use Python 3.10 or newer in a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r source/requirements.txt
python -m playwright install chromium
python source/build.py
python source/finish.py
```

The build uses the bundled fonts and makes no network requests. Chromium provides consistent SVG rasterization. Pillow creates the multi-size ICO. `source/finish.py` checks dimensions and alpha channels, renders the HTML previews, inventories all files and writes a distributable ZIP beside the pack folder.
