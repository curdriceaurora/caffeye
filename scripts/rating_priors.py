"""Maintain regional Bayesian priors in shops.json after either dataset changes.

Run: python3 scripts/rating_priors.py
The population uses the browser's category, coordinate and curated-duplicate rules.
"""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {'Coffee', 'Roasters', 'Bakery+Cafe', 'Tea/Boba', 'Dessert Cafe', 'Specialty'}


GENERIC_TOKENS = {'cafe', 'coffee', 'bakery', 'tea'}


def _number(value):
    """JS `typeof v === 'number' && Number.isFinite(v)` (bools are not numbers)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_coords(lat, lng):
    # prepareShop / ingestPlaces: finite numbers, rejected only when both are 0.
    return _number(lat) and _number(lng) and not (lat == 0 and lng == 0)


def _tokens(name):
    return {t for t in re.split('[^a-z0-9]+', (name or '').lower())
            if len(t) >= 3 and t not in GENERIC_TOKENS}


def regional_priors(seed, region):
    """Mirror index.html's admission rules (prepareShop + ingestPlaces) exactly."""
    addr = seed.get('addr') or {}

    def seed_coords(shop):
        coords = addr.get(shop.get('addrKey')) or shop
        return coords.get('lat'), coords.get('lng')

    curated = [s for s in seed['shops'] if s.get('curated') is not False]
    shops = [s for s in seed['shops'] if _valid_coords(*seed_coords(s))]
    seen = {s['placeId'] for s in seed['shops'] if s.get('placeId')}
    for place in region.get('places') or []:
        if not isinstance(place, dict) or not _valid_coords(place.get('lat'), place.get('lng')):
            continue
        if not isinstance(place.get('name'), str) or not place['name']:
            continue
        if not isinstance(place.get('category'), str) or place['category'] not in CATEGORIES:
            continue
        if place.get('placeId') and place['placeId'] in seen:
            continue
        duplicate = False
        for shop in curated:
            c = addr.get(shop.get('addrKey')) or shop
            if not c.get('lat') or not c.get('lng'):
                continue
            if (abs(place['lat'] - c['lat']) <= .0006 and abs(place['lng'] - c['lng']) <= .0006
                    and _tokens(place['name']) & _tokens(shop.get('name'))):
                duplicate = True
                break
        if duplicate:
            continue
        if place.get('placeId'):
            seen.add(place['placeId'])
        shops.append(place)
    rated = [s['rating'] for s in shops if _number(s.get('rating'))]
    counts = sorted(s['ratingNum'] if _number(s.get('ratingNum')) else 0 for s in shops)
    return {'C': sum(rated) / len(rated), 'm': counts[len(counts) // 2] or 1,
            'population': len(shops), 'source': 'shops.json + places.json; rating_priors.py'}


def update():
    path = ROOT / 'public/shops.json'
    seed = json.loads(path.read_text())
    region = json.loads((ROOT / 'public/places.json').read_text())
    seed['ratingPriors'] = regional_priors(seed, region)
    path.write_text(json.dumps(seed, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    update()
