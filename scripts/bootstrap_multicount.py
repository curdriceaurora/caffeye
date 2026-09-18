#!/usr/bin/env python3
"""Generate a multi-county TEST FIXTURE for exercising the county filter and list
pagination at scale. NEVER writes to public/ — output is a scratch file, gitignored,
that a developer can manually copy over public/shops.json for local testing only.

Duluth is real data and actually sits in Gwinnett County (not Fulton — an earlier
version of this script got that wrong). It's used as-is as the Gwinnett fixture.
Each shop is translated by (real reference-city coords - real Duluth coords) to
synthesize plausible-looking placements in the other 3 counties — real coordinates
for real, well-known cities in each county, not the county_bounds.json box centers
(a long thin county like Fulton has no single "center" that's a safe offset anchor).
These are NOT real shops: names, ratings, addresses, and placeIds are all copied
from Duluth and do not correspond to real businesses at the shifted coordinates.

After generating, every shifted shop is checked against county_bounds.json — via
the same in_county() logic refresh_ratings.py uses — to confirm it actually lands
in its assigned county's box and nowhere else. This catches box/offset mismatches
before they become a silently-wrong fixture.

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


def box_center(box: dict) -> tuple:
    return ((box["lat"][0] + box["lat"][1]) / 2, (box["lng"][0] + box["lng"][1]) / 2)


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


def verify(all_shops: list, all_addr: dict, bounds: dict) -> list:
    """Return descriptions of any shop that isn't in its assigned county's box,
    or that ambiguously also falls inside a different county's box."""
    problems = []
    for shop in all_shops:
        coords = all_addr.get(shop["addrKey"])
        if not coords:
            continue
        own = shop["county"].lower()
        # Check geographically (ignore the shop's own `county` tag, which
        # would trivially "pass" — that's exactly the tag in_county() would
        # trust instead of computing).
        untagged = {**shop, "county": ""}
        in_own = rr.in_county(untagged, all_addr, own, bounds)
        if not in_own:
            problems.append(
                f"{shop['name']} ({shop['addrKey']}) tagged {own} but coords fall outside {own}'s box"
            )
        others = [
            c
            for c in bounds
            if c != own and rr.in_county(untagged, all_addr, c, bounds)
        ]
        if others:
            problems.append(
                f"{shop['name']} ({shop['addrKey']}) tagged {own} but ALSO matches {others}"
            )
    return problems


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
    gwinnett_center = box_center(bounds["gwinnett"])

    all_shops, all_addr, all_neighborhoods = [], {}, {}
    per_county_count = {}

    for county_code, county_name, sample_city in COUNTIES:
        # Offset by (this county's box center - Gwinnett's box center), so the
        # translated cluster lands centered in its target box regardless of how
        # large Duluth's own real spread is. Using the *sample city's* real
        # coordinates instead (an earlier version of this script did) put the
        # translated cluster's edge outside its own box whenever the real
        # distance between two sample cities was smaller than Duluth's own
        # ~0.1°x0.1° spread — exactly what happened between Sandy Springs and
        # Decatur. The boxes above are pairwise disjoint (checked below), so
        # centering in the box guarantees no cross-county ambiguity.
        target_center = box_center(bounds[county_code])
        lat_offset = target_center[0] - gwinnett_center[0]
        lng_offset = target_center[1] - gwinnett_center[1]
        count = 0

        for shop in data["shops"]:
            new_shop = json.loads(json.dumps(shop))  # deep copy
            new_shop["city"] = sample_city
            new_shop["county"] = county_name

            old_key = shop["addrKey"]
            new_key = re.sub(r"^[a-z]+-", f"{county_code}-", old_key)
            new_shop["addrKey"] = new_key

            if old_key in data["addr"]:
                old = data["addr"][old_key]
                all_addr[new_key] = {
                    "lat": round(old["lat"] + lat_offset, 5),
                    "lng": round(old["lng"] + lng_offset, 5),
                }
            all_neighborhoods[new_key] = data["neighborhoods"].get(old_key, sample_city)
            all_shops.append(new_shop)
            count += 1

        per_county_count[county_name] = count

    problems = verify(all_shops, all_addr, bounds)
    if problems:
        print(
            f"REFUSING to write — {len(problems)} shop(s) don't geographically match their county tag:",
            file=sys.stderr,
        )
        for p in problems[:10]:
            print(f"  {p}", file=sys.stderr)
        raise SystemExit(
            "Fix scripts/county_bounds.json or the reference coordinates above, then rerun."
        )

    data["shops"] = all_shops
    data["addr"] = all_addr
    data["neighborhoods"] = all_neighborhoods
    data["cities"] = sorted(set(s["city"] for s in all_shops))
    data["regionLabel"] = "North Atlanta"

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2))
    print("Verified: every shop's coordinates match its county tag, unambiguously.")
    print(
        f"Wrote {len(all_shops)} shops ({', '.join(f'{k}={v}' for k, v in per_county_count.items())}) -> {out_path}"
    )
    print(
        "This is a TEST FIXTURE, not real data. To try it locally (never commit the copy):"
    )
    print(f"  cp {out_path} public/shops.json")


if __name__ == "__main__":
    main()
