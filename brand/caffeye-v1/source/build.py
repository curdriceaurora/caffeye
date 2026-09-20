#!/usr/bin/env python3
"""Rebuild the Caffeye vector masters and raster exports, entirely offline.

Font glyphs are outlined so the distributed logos do not depend on installed fonts.
The bean seam is a mask, not a white stroke, so every variant has true transparency.
"""
from __future__ import annotations

import hashlib
import io
import json
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
COLORS = {"forest": "#293F34", "gold": "#DCAF59", "paper": "#F4F3ED", "ink": "#222721", "muted": "#60645F", "white": "#FFFFFF", "black": "#000000"}
JOBS: list[tuple[Path, int, int]] = []


def font_data(name: str, axes: dict):
    font = instantiateVariableFont(TTFont(ROOT / "fonts" / f"{name}.ttf"), axes, inplace=False)
    buffer = io.BytesIO()
    font.save(buffer)
    return font, buffer.getvalue()


FRAUNCES, FRAUNCES_BYTES = font_data("Fraunces", {"wght": 800, "opsz": 72, "SOFT": 50, "WONK": 1})
INTER, INTER_BYTES = font_data("Inter", {"wght": 500, "opsz": 14})


def lettering(text: str, size: float, x: float, baseline: float, color: str, family="Fraunces", tracking=0):
    font, raw = (FRAUNCES, FRAUNCES_BYTES) if family == "Fraunces" else (INTER, INTER_BYTES)
    units = font["head"].unitsPerEm
    metrics = ImageFont.truetype(io.BytesIO(raw), units)
    scale = size / units
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    paths = []
    for i, char in enumerate(text):
        # Pair positioning is derived from the font's shaping engine; ligatures are
        # deliberately disabled to keep the individual outline geometry editable.
        offset = (metrics.getlength(text[:i + 1], features=["-liga"]) - metrics.getlength(char, features=["-liga"])) * scale + i * tracking
        pen = SVGPathPen(glyphs)
        glyphs[cmap[ord(char)]].draw(pen)
        paths.append(f'<path transform="translate({x + offset:.4f} {baseline}) scale({scale:.7f} {-scale:.7f})" d="{pen.getCommands()}"/>')
    width = metrics.getlength(text, features=["-liga"]) * scale + max(0, len(text) - 1) * tracking
    return f'<g fill="{color}">{"".join(paths)}</g>', width


def mark(color: str, x=0, y=0, size=100, micro=False, ident="bean"):
    seam = 'M55 33 L45 67' if micro else 'M56 33 C42 41 58 55 44 67'
    sw = 6 if micro else 4
    ring = 9 if micro else 7
    body = f'''<defs><mask id="{ident}" maskUnits="userSpaceOnUse" x="0" y="0" width="100" height="100"><rect width="100" height="100" fill="white"/><path d="{seam}" fill="none" stroke="black" stroke-width="{sw}" stroke-linecap="round"/></mask></defs>
    <path d="M10 50 Q50 3 90 50 Q50 97 10 50Z" fill="none" stroke="{color}" stroke-width="{ring}" stroke-linejoin="round"/>
    <ellipse cx="50" cy="50" rx="15" ry="21" transform="rotate(25 50 50)" fill="{color}" mask="url(#{ident})"/>'''
    # The mask belongs to the rotated ellipse's own coordinate space. Counter-
    # rotating the seam is unnecessary: both bean and seam share that local axis.
    return f'<g transform="translate({x} {y}) scale({size / 100})">{body}</g>'


def svg(w, h, body, title, background=None):
    bg = f'<rect width="{w}" height="{h}" fill="{background}"/>' if background else ''
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><title>{escape(title)}</title>{bg}{body}</svg>'


def save(relative, w, h, body, title, background=None, raster=True):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg(w, h, body, title, background), encoding="utf-8")
    if raster:
        JOBS.append((path, w, h))


def horizontal(color, x=0, y=0, scale=1, ident="bean"):
    word, _ = lettering("caffeye", 110, 172, 119, color, tracking=-1.8)
    return f'<g transform="translate({x} {y}) scale({scale})">{mark(color, 14, 11, 155, ident=ident)}{word}</g>'


def contrast(a, b):
    def luminance(hex_color):
        c = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in c]
        return sum(v * w for v, w in zip(c, [.2126, .7152, .0722]))
    light, dark = sorted([luminance(a), luminance(b)], reverse=True)
    return round((light + .05) / (dark + .05), 2)


def main():
    for folder in ["logos", "icons", "social", "tokens", "previews"]:
        (ROOT / folder).mkdir(exist_ok=True)
    for name in ["forest", "paper", "black", "white"]:
        color = COLORS[name]
        save(f"logos/caffeye-horizontal-{name}.svg", 570, 176, horizontal(color), f"Caffeye — horizontal {name} logo")
        word, width = lettering("caffeye", 110, 20, 112, color, tracking=-1.8)
        save(f"logos/caffeye-wordmark-{name}.svg", round(width + 40), 152, word, f"Caffeye — {name} wordmark")
        word, width = lettering("caffeye", 92, 0, 0, color, tracking=-1.4)
        stacked = mark(color, 120, 0, 200) + f'<g transform="translate({(440-width)/2} 244)">{word}</g>'
        save(f"logos/caffeye-stacked-{name}.svg", 440, 290, stacked, f"Caffeye — stacked {name} logo")
        save(f"logos/caffeye-symbol-{name}.svg", 256, 256, mark(color, 12, 12, 232), f"Caffeye — {name} bean eye")
    save("logos/caffeye-symbol-micro.svg", 100, 100, mark(COLORS["forest"], micro=True), "Caffeye — small-size bean eye")

    for name, bg, fg in [("forest", COLORS["forest"], COLORS["paper"]), ("paper", COLORS["paper"], COLORS["forest"])]:
        save(f"icons/caffeye-app-{name}-1024.svg", 1024, 1024, mark(fg, 132, 132, 760), "Caffeye app icon", bg)
        save(f"social/caffeye-avatar-{name}.svg", 1080, 1080, mark(fg, 140, 140, 800), "Caffeye profile image", bg)

    for size in [16, 32, 48]:
        save(f"icons/favicon-{size}.svg", size, size, mark(COLORS["forest"], size=size, micro=True), "Caffeye favicon")
    adaptive = '<style>:root{color:#293F34}@media(prefers-color-scheme:dark){:root{color:#F4F3ED}}</style>' + mark("currentColor", micro=True)
    save("icons/favicon.svg", 100, 100, adaptive, "Caffeye adaptive favicon", raster=False)
    for size, filename in [(180, "apple-touch-icon"), (192, "icon-192"), (512, "icon-512"), (512, "icon-maskable-512")]:
        save(f"icons/{filename}.svg", size, size, mark(COLORS["paper"], size*.15, size*.15, size*.7), "Caffeye app icon", COLORS["forest"])

    # A location-neutral sharing image remains accurate as Caffeye adds towns.
    social = horizontal(COLORS["forest"], 58, 45, 1.0, "social-bean")
    for text, size, x, y, family in [("We know a spot.", 89, 72, 350, "Fraunces"), ("Coffee, bakeries & tea. An eye for the good ones.", 27, 77, 418, "Inter")]:
        content, _ = lettering(text, size, x, y, COLORS["forest"], family)
        social += content
    social += '<path d="M76 514 H1124" stroke="#293F34" stroke-width="2"/><circle cx="1098" cy="93" r="22" fill="#DCAF59"/>'
    content, _ = lettering("Your next good spot.", 20, 77, 557, COLORS["forest"], "Inter")
    social += content
    save("social/caffeye-share-1200x630.svg", 1200, 630, social, "Caffeye. We know a spot. Coffee, bakeries and tea.", COLORS["paper"])

    tokens = {"version": "1.0.0", "colors": COLORS, "typography": {"display": {"family": "Fraunces", "weight": 800, "axes": {"opsz": 72, "SOFT": 50, "WONK": 1}}, "body": {"family": "Inter", "weights": [400, 500, 600]}}, "contrast": {"forest_on_paper": contrast(COLORS["forest"], COLORS["paper"]), "forest_on_gold": contrast(COLORS["forest"], COLORS["gold"]), "white_on_gold": contrast(COLORS["white"], COLORS["gold"]), "muted_on_paper": contrast(COLORS["muted"], COLORS["paper"])}}
    (ROOT / "tokens/brand-tokens.json").write_text(json.dumps(tokens, indent=2) + "\n")
    css = '/* Opt-in Caffeye brand tokens. Does not override application styles. */\n:root {\n' + ''.join(f'  --caffeye-{k}: {v};\n' for k, v in COLORS.items()) + '  --caffeye-font-display: "Fraunces", Georgia, serif;\n  --caffeye-font-body: "Inter", system-ui, sans-serif;\n}\n'
    (ROOT / "tokens/brand-tokens.css").write_text(css)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        raster_page = browser.new_page(device_scale_factor=1)
        logo_page = browser.new_page(device_scale_factor=4)
        for path, w, h in JOBS:
            page = logo_page if path.parent.name == "logos" else raster_page
            page.set_viewport_size({"width": w, "height": h})
            await_svg = path.read_text()
            page.set_content(f'<html><style>html,body{{margin:0;background:transparent}}svg{{display:block}}</style><body>{await_svg}</body></html>')
            page.locator("svg").screenshot(path=str(path.with_suffix(".png")), omit_background=True)
        browser.close()

    # Browser PNGs are the canonical rasterization; ICO embeds exact raster sizes.
    master = Image.open(ROOT / "icons/favicon-48.png")
    master.save(ROOT / "icons/favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[Image.open(ROOT / "icons/favicon-16.png"), Image.open(ROOT / "icons/favicon-32.png")])
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name in ["manifest.json", "validation.json"]:
            continue
        item = {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.suffix == ".png":
            with Image.open(path) as im:
                item["width"], item["height"] = im.size
        elif path.suffix == ".svg":
            ET.parse(path)
            assert "<text" not in path.read_text(), f"Unoutlined text: {path}"
        files.append(item)
    (ROOT / "manifest.json").write_text(json.dumps({"brand": "Caffeye", "version": "1.0.0", "assets": files}, indent=2) + "\n")
    print(f"Built {len(JOBS)} SVG/PNG pairs; contrast ratios: {tokens['contrast']}")


if __name__ == "__main__":
    main()
