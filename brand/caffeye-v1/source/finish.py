#!/usr/bin/env python3
"""Render offline previews, validate exports and package the finished pack."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    checked = []
    for svg in ROOT.rglob("*.svg"):
        tree = ET.parse(svg).getroot()
        assert tree.find("{http://www.w3.org/2000/svg}title") is not None, svg
        assert "<text" not in svg.read_text(), svg
        png = svg.with_suffix(".png")
        if png.exists():
            scale = 4 if svg.parent.name == "logos" else 1
            expected = tuple(int(tree.attrib[k]) * scale for k in ["width", "height"])
            with Image.open(png) as image:
                assert image.size == expected, (png, image.size, expected)
                assert image.mode in ["RGB", "RGBA"], (png, image.mode)
                alpha = image.convert("RGBA").getextrema()[3]
                if svg.parent.name == "logos":
                    assert image.mode == "RGBA" and alpha == (0, 255), png
                    box = image.getbbox()
                    assert box and 0 < box[0] < box[2] < image.width and 0 < box[1] < box[3] < image.height, (png, box)
                elif svg.parent.name == "social" or "favicon" not in svg.name:
                    assert alpha == (255, 255), png
            checked.append(str(png.relative_to(ROOT)))

    with Image.open(ROOT / "logos/caffeye-symbol-forest.png") as symbol:
        assert symbol.getpixel((symbol.width//2, symbol.height//2))[3] == 0, "Bean seam is not transparent"
    with Image.open(ROOT / "icons/favicon.ico") as ico:
        assert ico.ico.sizes() == {(16, 16), (32, 32), (48, 48)}
        for size in [16, 32, 48]:
            with Image.open(ROOT / f"icons/favicon-{size}.png") as original:
                assert ico.ico.getimage((size, size)).tobytes() == original.tobytes(), f"ICO frame mismatch: {size}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 1050}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((ROOT / "previews/brand-board.html").as_uri())
        page.evaluate("document.fonts.ready")
        page.locator(".board").screenshot(path=str(ROOT / "previews/brand-board.png"))
        page.goto((ROOT / "brand-guide.html").as_uri())
        page.evaluate("document.fonts.ready")
        assert page.locator("img").evaluate_all("imgs => imgs.every(i => i.complete && i.naturalWidth > 0)"), "Missing guide images"
        page.screenshot(path=str(ROOT / "previews/brand-guide-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(ROOT / "previews/brand-guide-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile guide overflows"
        assert not errors, errors
        browser.close()

    report = {"status": "passed", "raster_assets_checked": len(checked), "checks": ["SVG parsing, titles and outlined text", "Exact PNG dimensions", "Transparent logo backgrounds and bean seam", "Unclipped logo content", "Opaque app and social backgrounds", "Exact 16/32/48 ICO frames", "Offline guide images load", "Mobile guide has no horizontal overflow", "No preview JavaScript errors"], "visual_review": "See previews; automated checks supplement visual review."}
    (ROOT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    inventory = []
    for file in sorted(ROOT.rglob("*")):
        if not file.is_file() or file.name == "manifest.json" or "__pycache__" in file.parts:
            continue
        entry = {"path": str(file.relative_to(ROOT)), "bytes": file.stat().st_size, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
        if file.suffix == ".png":
            with Image.open(file) as im:
                entry.update(width=im.width, height=im.height)
        inventory.append(entry)
    (ROOT / "manifest.json").write_text(json.dumps({"brand": "Caffeye", "version": "1.0.0", "assets": inventory}, indent=2) + "\n")
    archive = ROOT.parent / "caffeye-brand-pack-v1.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(ROOT.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts:
                z.write(file, file.relative_to(ROOT.parent))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    print(json.dumps({"archive": str(archive), "files": len(inventory) + 1, "validation": report}, indent=2))


if __name__ == "__main__":
    main()
