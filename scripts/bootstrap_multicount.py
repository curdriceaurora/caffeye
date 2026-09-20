#!/usr/bin/env python3
"""[HISTORICAL TOOLING] Generate a multi-county TEST FIXTURE for exercising the county filter
and list pagination at scale (superseded by discover_places.py and real multi-county crawls).
NEVER writes to public/ — output is a scratch file, gitignored, that a developer can manually
copy over public/shops.json for local testing only.

Duluth is real data and mostly sits in Gwinnett County — a handful of its 61 real
shops have Johns Creek addresses and are actually in Fulton (Georgia postal cities
and county lines don't always align; see refresh_ratings.in_county()'s docstring).
It's used as-is as the Gwinnett fixture. Each shop is translated by (this county's
real center - Gwinnett's real center), using the representative center point each
county's real OpenStreetMap boundary carries in county_boundaries.geojson, to
synthesize plausible-looking placements in the other 3 counties. These are NOT
real shops: names, ratings, addresses, and placeIds are all copied from Duluth and
do not correspond to real businesses at the shifted coordinates.

Every shifted shop is checked against county_boundaries.geojson — via the same
in_county() point-in-polygon logic refresh_ratings.py uses — before being
included. Translating a ~0.11x0.09 degree cluster by a fixed offset does not
reliably land every point inside a real, irregularly-shaped county polygon (a
notably imperfect fit for Fulton, which is long and notched); shops that miss
their target county after translation are dropped rather than included with
wrong coordinates. This is expected to drop a meaningful fraction (observed:
roughly 15-25%) per synthetic county, which is fine for a scale-testing
fixture. A county whose survival rate is suspiciously low likely means its
reference offset needs to move, not that this threshold needs raising — see
MIN_SURVIVAL_FRACTION below.

Always reads Duluth's shops from the `main` branch via git, never from whatever is
currently in public/shops.json on the working tree — running this after
public/shops.json already holds a previous run's output must not re-expand it
(an earlier version did: reading an already-4x'd file and duplicating each of its
244 shops into all 4 counties again produced 976 entries with colliding addrKeys).

Usage:
    python3 scripts/bootstrap_multicount.py
    python3 scripts/bootstrap_multicount.py --source some/other/shops.json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "scratch" / "shops-multicounty-test.json"
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import refresh_ratings as rr  # noqa: E402 - reuse the real in_county() check

# (code, display_name, sample_city) — Gwinnett/Duluth is the real, unmodified seed.
# The other three get a plausible-sounding city label for that county, but their
# coordinates are NOT that real city's — see the offset math in main() below.
COUNTIES = [
    ("gwinnett", "Gwinnett", "Duluth"),
    ("fulton", "Fulton", "Sandy Springs"),
    ("dekalb", "DeKalb", "Decatur"),
    ("forsyth", "Forsyth", "Cumming"),
]


def load_seed(source: str | None) -> dict:
    if source:
        return json.loads(Path(source).read_text())
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "show", "main:public/shops.json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


MIN_SURVIVAL_FRACTION = 0.5  # below this, the offset is wrong, not just imprecise


def fits_county(shop: dict, addr: dict, county: str, bounds: dict) -> bool:
    """True iff shop's coordinates land inside `county`'s real boundary and no
    other county's (an ambiguous double-match is as wrong as a miss here)."""
    # Check geographically — ignore the shop's own `county` tag, which would
    # trivially "pass" (that's exactly the tag in_county() would trust instead
    # of computing).
    untagged = {**shop, "county": ""}
    if not rr.in_county(untagged, addr, county, bounds):
        return False
    return not any(
        c != county and rr.in_county(untagged, addr, c, bounds) for c in bounds
    )


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--source",
        default="",
        help="seed shops.json (default: main branch's, via git show)",
    )
    ap.add_argument(
        "--out", default=str(DEFAULT_OUT), help=f"output path (default: {DEFAULT_OUT})"
    )
    args = ap.parse_args()

    data = load_seed(args.source or None)
    if len(set(s.get("county") for s in data["shops"])) > 1:
        raise SystemExit(
            f"{args.source or 'main:public/shops.json'} already has multiple counties — "
            "pass --source pointing at a single-region seed, not fixture output."
        )
    bounds = rr.load_county_bounds()
    gwinnett_center = bounds["gwinnett"]["center"]

    all_shops, all_addr, all_neighborhoods = [], {}, {}
    per_county_count = {}

    for county_code, county_name, sample_city in COUNTIES:
        # Offset by (this county's real center - Gwinnett's real center). Zero
        # for Gwinnett itself, so its shops keep their real coordinates.
        target_center = bounds[county_code]["center"]
        lat_offset = target_center[0] - gwinnett_center[0]
        lng_offset = target_center[1] - gwinnett_center[1]

        candidates, candidate_addr, neighborhood_of = [], {}, {}
        for shop in data["shops"]:
            old_key = shop["addrKey"]
            if old_key not in data["addr"]:
                continue
            new_shop = json.loads(json.dumps(shop))  # deep copy
            new_shop["city"] = sample_city
            new_shop["county"] = county_name
            new_key = re.sub(r"^[a-z]+-", f"{county_code}-", old_key)
            new_shop["addrKey"] = new_key

            old = data["addr"][old_key]
            candidate_addr[new_key] = {
                "lat": round(old["lat"] + lat_offset, 5),
                "lng": round(old["lng"] + lng_offset, 5),
            }
            neighborhood_of[new_key] = data["neighborhoods"].get(old_key, sample_city)
            candidates.append(new_shop)

        kept = [
            s for s in candidates if fits_county(s, candidate_addr, county_code, bounds)
        ]
        survival = len(kept) / len(candidates)
        if survival < MIN_SURVIVAL_FRACTION:
            raise SystemExit(
                f"{county_name}: only {len(kept)}/{len(candidates)} shops "
                f"({survival:.0%}) landed inside its real boundary after translation "
                f"— below the {MIN_SURVIVAL_FRACTION:.0%} sanity floor. The offset "
                f"(from {county_code}'s real center) is likely wrong, not just imprecise; "
                "pick a different reference point, don't raise this threshold."
            )
        print(
            f"{county_name}: kept {len(kept)}/{len(candidates)} ({survival:.0%}) after real-boundary check"
        )

        for shop in kept:
            all_shops.append(shop)
            all_addr[shop["addrKey"]] = candidate_addr[shop["addrKey"]]
            all_neighborhoods[shop["addrKey"]] = neighborhood_of[shop["addrKey"]]
        per_county_count[county_name] = len(kept)

    data["shops"] = all_shops
    data["addr"] = all_addr
    data["neighborhoods"] = all_neighborhoods
    data["cities"] = sorted(set(s["city"] for s in all_shops))
    data["regionLabel"] = "North Atlanta"

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2))
    print(
        "Every included shop's coordinates verified against its county's real boundary, unambiguously."
    )
    print(
        f"Wrote {len(all_shops)} shops ({', '.join(f'{k}={v}' for k, v in per_county_count.items())}) -> {out_path}"
    )
    print(
        "This is a TEST FIXTURE, not real data. To try it locally (never commit the copy):"
    )
    print(f"  cp {out_path} public/shops.json")


if __name__ == "__main__":
    main()
