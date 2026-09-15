#!/usr/bin/env python3
"""Refresh Google ratings / review counts in public/shops.json via Places API (New).

    python3 scripts/refresh_ratings.py                 # dry run: before/after table only
    python3 scripts/refresh_ratings.py --write         # also write public/shops.json
    python3 scripts/refresh_ratings.py --only "Sweet"  # limit to shops whose name contains text
    python3 scripts/refresh_ratings.py --raw out.json  # dump raw API responses for audit
    python3 scripts/refresh_ratings.py --replay out.json --write   # re-run from a dump, no API calls

Key lookup (never printed): $GOOGLE_MAPS_API_KEY, else ~/.config/caffeye/google_maps_key.
Uses Text Search (New) with a location bias on the shop's stored coordinates, then picks the
result within 400 m with the most name-token overlap (nearest on ties). Anything ambiguous is
flagged, not written. Rows marked ⚠ in the table are skipped on --write.
"""

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOPS_PATH = ROOT / "public" / "shops.json"
ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
    ]
)
MAX_DIST_M = 400  # a result farther than this from our pin is not the same shop
BIAS_RADIUS_M = 1500.0
STOP = {
    "the",
    "and",
    "cafe",
    "café",
    "bakery",
    "coffee",
    "tea",
    "house",
    "co",
    "boba",
    "dessert",
    "bar",
    "roasters",
    "shop",
    "duluth",
    "atl",
    "more",
    "ga",
}


def load_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        p = Path.home() / ".config" / "caffeye" / "google_maps_key"
        if p.exists():
            key = p.read_text().strip()
    if not key:
        sys.exit(
            "No API key. Set GOOGLE_MAPS_API_KEY or create ~/.config/caffeye/google_maps_key"
        )
    return key


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def name_overlap(shop_name: str, place_name: str) -> int:
    tokens = {t for t in norm(shop_name).split() if t not in STOP and len(t) >= 2}
    ptoks = set(norm(place_name).split())
    squashed = norm(place_name).replace(" ", "")
    hits = 0
    for t in tokens:
        if t in ptoks or (len(t) >= 4 and t in squashed):
            hits += 1
    return hits


def search(key: str, query: str, lat: float, lng: float) -> dict:
    body = {
        "textQuery": query,
        "maxResultCount": 5,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": BIAS_RADIUS_M,
            }
        },
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace").replace(key, "<key>")
        return {"error": f"HTTP {e.code}: {msg[:400]}"}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e).replace(key, "<key>")}


def pick(places: list, shop: dict, lat: float, lng: float):
    """Return (place, dist_m, overlap) for the best candidate, or None."""
    best = None
    for p in places:
        loc = p.get("location") or {}
        if "latitude" not in loc:
            continue
        d = haversine_m(lat, lng, loc["latitude"], loc["longitude"])
        if d > MAX_DIST_M:
            continue
        ov = name_overlap(shop["name"], (p.get("displayName") or {}).get("text", ""))
        # Most name overlap wins; nearest breaks ties. Nearest-first once matched
        # "La Abuela Made in Casa" instead of "El Café by La Abuela" next door.
        cand = ((ov, -d), p, d, ov)
        if best is None or cand[0] > best[0]:
            best = cand
    return None if best is None else best[1:]


def fmt_count(n) -> str:
    return "—" if not n else f"{n:,}+"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--write", action="store_true", help="write results into public/shops.json"
    )
    ap.add_argument(
        "--only", default="", help="only shops whose name contains this text"
    )
    ap.add_argument("--raw", default="", help="path to dump raw API responses")
    ap.add_argument(
        "--replay",
        default="",
        help="re-use raw responses from this file instead of calling the API",
    )
    ap.add_argument("--sleep", type=float, default=0.15)
    args = ap.parse_args()

    replay = json.loads(Path(args.replay).read_text()) if args.replay else None
    key = None if replay else load_key()
    data = json.loads(SHOPS_PATH.read_text())
    addr = data["addr"]
    shops = [s for s in data["shops"] if args.only.lower() in s["name"].lower()]
    if not shops:
        sys.exit("no shops match --only")

    raw, rows, updates, flagged = {}, [], {}, []
    for s in shops:
        c = addr[s["addrKey"]]
        if replay is not None:
            res = replay.get(s["name"], {"error": "not in replay file"})
        else:
            res = search(key, f"{s['name']} {s['address']}", c["lat"], c["lng"])
            time.sleep(args.sleep)
        raw[s["name"]] = res

        if "error" in res:
            rows.append((s["name"], s, None, None, None, f"API {res['error'][:80]}"))
            flagged.append(s["name"])
            continue
        choice = pick(res.get("places", []), s, c["lat"], c["lng"])
        if not choice:
            rows.append(
                (s["name"], s, None, None, None, "UNMATCHED (nothing within 400 m)")
            )
            flagged.append(s["name"])
            continue
        p, dist, ov = choice
        flags = []
        gname = (p.get("displayName") or {}).get("text", "")
        status = p.get("businessStatus", "")
        if ov == 0:
            flags.append(f"NAME? google='{gname}'")
        if status and status != "OPERATIONAL":
            flags.append(status)
        rating, count = p.get("rating"), p.get("userRatingCount")
        if rating is None or count is None:
            flags.append("no rating on Google")
        elif s.get("ratingNum") and count < s["ratingNum"]:
            flags.append(f"count↓ {s['ratingNum']:,}→{count:,}")

        writable = (
            rating is not None
            and count is not None
            and status != "CLOSED_PERMANENTLY"
            and ov > 0
        )
        if writable:
            updates[s["name"]] = {
                "rating": round(float(rating), 1),
                "ratingCount": fmt_count(count),
                "ratingNum": int(count),
            }
        else:
            flagged.append(s["name"])
        rows.append((s["name"], s, rating, count, int(dist), "; ".join(flags)))

    # ---- report -------------------------------------------------------
    print("| # | shop | stored | google | Δ count | dist | flags |")
    print("|---|---|---|---|---|---|---|")
    for i, (name, s, rating, count, dist, flags) in enumerate(rows, 1):
        stored = f"{s.get('rating')} ({s.get('ratingNum') or 0:,})"
        new = "—" if rating is None else f"{rating} ({count:,})"
        delta = (
            ""
            if (count is None or not s.get("ratingNum"))
            else f"{count - s['ratingNum']:+,}"
        )
        mark = "" if name in updates else " ⚠"
        print(
            f"| {i} | {name}{mark} | {stored} | {new} | {delta} | {dist if dist is not None else ''} | {flags} |"
        )
    print(f"\nupdatable: {len(updates)}   flagged/skipped: {len(flagged)} -> {flagged}")

    if args.raw:
        Path(args.raw).write_text(json.dumps(raw, indent=1))
        print(f"raw responses -> {args.raw}")

    if not args.write:
        print("(dry run — pass --write to update public/shops.json)")
        return 0

    by_name = {s["name"]: s for s in data["shops"]}
    for name, u in updates.items():
        by_name[name].update(u)
    SHOPS_PATH.write_text(json.dumps(data, indent=2))  # file has no trailing newline
    print(f"wrote {len(updates)} shops -> {SHOPS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
