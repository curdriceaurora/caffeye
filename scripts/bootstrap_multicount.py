#!/usr/bin/env python3
"""Bootstrap shops.json with multi-county data for testing.

Duplicates Duluth shops across 4 counties (Fulton, DeKalb, Forsyth, Gwinnett),
adjusting city/county/addrKey for each. This is a temporary MVP step; real data
will come from county-by-county Places API audits later.

Usage:
    python3 scripts/bootstrap_multicount.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOPS_PATH = ROOT / "public" / "shops.json"
COUNTY_BOUNDS_PATH = Path(__file__).resolve().parent / "county_bounds.json"

# County info: (code, display_name, sample_city, lat_offset, lng_offset)
COUNTIES = [
    ("fulton", "Fulton", "Duluth", 0, 0),  # baseline
    ("dekalb", "DeKalb", "Decatur", -0.18, -0.02),  # south, slightly east
    ("forsyth", "Forsyth", "Cumming", 0.10, -0.25),  # north, west
    ("gwinnett", "Gwinnett", "Lawrenceville", -0.01, 0.13),  # south, east
]

data = json.loads(SHOPS_PATH.read_text())
bounds = json.loads(COUNTY_BOUNDS_PATH.read_text())

shops_by_county = {}
addr_by_county = {}
neighborhoods_by_county = {}

for county_code, county_name, sample_city, lat_offset, lng_offset in COUNTIES:
    new_shops = []
    new_addr = {}
    new_neighborhoods = {}

    for shop in data["shops"]:
        new_shop = json.loads(json.dumps(shop))  # deep copy
        new_shop["city"] = sample_city
        new_shop["county"] = county_name

        # Adjust addrKey: duluth-xxx-yyy -> <county>-xxx-yyy
        old_key = shop["addrKey"]
        new_key = re.sub(r"^[a-z]+-", f"{county_code}-", old_key)
        new_shop["addrKey"] = new_key

        # Adjust coordinates slightly per county to make them distinct (for testing)
        if old_key in data["addr"]:
            old_lat = data["addr"][old_key]["lat"]
            old_lng = data["addr"][old_key]["lng"]
            new_lat = old_lat + lat_offset
            new_lng = old_lng + lng_offset
            new_addr[new_key] = {"lat": round(new_lat, 5), "lng": round(new_lng, 5)}
        old_neighborhood = data["neighborhoods"].get(old_key, sample_city)
        new_neighborhoods[new_key] = old_neighborhood

        new_shops.append(new_shop)

    shops_by_county[county_code] = new_shops
    addr_by_county[county_code] = new_addr
    neighborhoods_by_county[county_code] = new_neighborhoods

# Merge all counties
all_shops = []
all_addr = {}
all_neighborhoods = {}
for county_code in [c[0] for c in COUNTIES]:
    all_shops.extend(shops_by_county[county_code])
    all_addr.update(addr_by_county[county_code])
    all_neighborhoods.update(neighborhoods_by_county[county_code])

# Update data
data["shops"] = all_shops
data["addr"] = all_addr
data["neighborhoods"] = all_neighborhoods
data["cities"] = sorted(set(s["city"] for s in all_shops))
data["regionLabel"] = "North Atlanta"
data["checkedMonth"] = "September 2026"

# Write
SHOPS_PATH.write_text(json.dumps(data, indent=2))
print(
    f"Bootstrapped {len(all_shops)} shops across {len(data['cities'])} cities in 4 counties"
)
print(f"Cities: {', '.join(data['cities'])}")
print(f"Shops per county: {len(shops_by_county['fulton'])}")
