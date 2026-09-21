#!/usr/bin/env python3
"""Refresh Google ratings / review counts in public/shops.json via Places API (New).

Two steps — audit, then write exactly what was audited:

    python3 scripts/refresh_ratings.py
        live run: prints the before/after table and dumps every response to
        scratch/ratings-<date>.json (git-ignored). Nothing is written.
    python3 scripts/refresh_ratings.py --replay scratch/ratings-<date>.json --write
        re-scores the dumped responses (no API calls) and writes public/shops.json.

For multi-county workflows, run per-county and specify --county to filter:

    python3 scripts/refresh_ratings.py --county fulton
    python3 scripts/refresh_ratings.py --county dekalb --replay scratch/ratings-2026-09-17.json --write

Options:
    --county CODE    filter to shops in this county (fulton, dekalb, forsyth, gwinnett, cobb, cherokee, hall, dawson, clayton, henry, fayette, coweta, douglas, rockdale).
                     A shop's own `county` tag wins if present; otherwise its stored
                     coordinates are tested against that county's real boundary
                     polygon (see county_boundaries.geojson, from OpenStreetMap) —
                     so this works even on today's untagged, single-region
                     shops.json. Omit to process all shops.
    --only TEXT      limit to shops whose name contains TEXT (case-insensitive)
    --raw PATH       dump path (default scratch/ratings-<date>.json). Merged into, never truncated.
    --replay PATH    re-use dumped responses instead of calling the API. Required for --write.
    --accept NAME    write a row the script would otherwise refuse for a *soft* reason
                     (CLOSED_TEMPORARILY, or a review count that fell by more than half).
                     Repeatable; NAME is a case-insensitive substring of the shop name.

Key (never printed): $GOOGLE_MAPS_API_KEY wins, else ~/.config/caffeye/google_maps_key.

Matching: a shop that already carries a `placeId` is fetched by ID (Place Details); a dead ID
falls back to search and is flagged. Otherwise Text Search restricted to a RESTRICT_M box
around the stored pin; the candidate with the most name-token overlap wins (nearest on ties).
A candidate must lie within MAX_DIST_M and share at least one non-generic name token.
Rows marked ⚠ are refused on --write: API error, no candidate, no name overlap, no rating,
CLOSED_PERMANENTLY, and — unless --accept — CLOSED_TEMPORARILY or count < DROP_LIMIT × stored.
The first accepted match stores the Google `placeId` on the shop.
"""

import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

try:
    import places_ledger
except ImportError:
    try:
        from . import places_ledger
    except Exception:
        places_ledger = None

ROOT = Path(__file__).resolve().parent.parent
SHOPS_PATH = ROOT / "public" / "shops.json"
SCRATCH = ROOT / "scratch"
COUNTY_BOUNDARIES_PATH = Path(__file__).resolve().parent / "county_boundaries.geojson"
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{id}"
PLACE_FIELDS = [
    "id",
    "displayName",
    "formattedAddress",
    "location",
    "rating",
    "userRatingCount",
    "businessStatus",
]
SEARCH_MASK = ",".join("places." + f for f in PLACE_FIELDS)
DETAILS_MASK = ",".join(PLACE_FIELDS)
MAX_DIST_M = 400  # a result farther than this from our pin is not the same shop
RESTRICT_M = 500  # half-size of the search rectangle around the pin
PAGE_SIZE = 20  # billed per request, not per result — no reason to cap at 5
DROP_LIMIT = 0.5  # a same-source count below this fraction of stored needs --accept
FATAL_HTTP = {
    400,
    401,
    403,
    429,
}  # bad request / key / quota: every later call fails too
# Generic words never count toward identity; they only break ties between candidates.
GENERIC = {
    "the",
    "a",
    "an",
    "and",
    "cafe",
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
    "by",
    "of",
    "on",
    "in",
    "at",
    "el",
    "la",
    "le",
    "les",
    "un",
    "une",
    "de",
    "du",
    "n",
    "s",
}


class FatalApiError(Exception):
    """Systemic failure — stop issuing requests."""


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


def load_county_bounds() -> dict:
    """{county_code: {"name": ..., "center": [lat, lng], "ring": [[lng, lat], ...]}}
    from real OpenStreetMap county boundaries (see county_boundaries.geojson's
    _source field) — not a hand-drawn approximation. A simple axis-aligned box
    cannot represent Fulton County (a long, irregular north-south county whose
    real eastern edge is much further east at its northern tip, near Johns
    Creek, than near Atlanta) without either excluding real Fulton territory or
    swallowing neighboring counties at other latitudes; that's what the
    previous rectangle-based version of this function got wrong."""
    fc = json.loads(COUNTY_BOUNDARIES_PATH.read_text())
    return {
        f["properties"]["county"]: {
            "name": f["properties"]["name"],
            "center": f["properties"]["center"],
            "ring": f["geometry"]["coordinates"][0],
        }
        for f in fc["features"]
    }


def _point_in_ring(lat: float, lng: float, ring: list) -> bool:
    """Standard ray-casting point-in-polygon test. `ring` is a list of
    [lng, lat] pairs (GeoJSON coordinate order), first == last."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x_at_lat = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lng < x_at_lat:
                inside = not inside
        j = i
    return inside


def in_county(shop: dict, addr: dict, county: str, bounds: dict) -> bool:
    """A shop belongs to `county` if its own `county` tag says so, or — when
    untagged, which is every shop in a single-region shops.json — its stored
    coordinates fall inside that county's real boundary polygon."""
    tagged = shop.get("county", "").lower()
    if tagged:
        return tagged == county.lower()
    entry = bounds.get(county.lower())
    c = addr.get(shop.get("addrKey"))
    if not entry or not c:
        return False
    return _point_in_ring(c["lat"], c["lng"], entry["ring"])


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def norm(s: str) -> str:
    """Lower-case ASCII words: accents folded (Café -> cafe), everything else -> space."""
    folded = unicodedata.normalize("NFKD", s or "")
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def name_overlap(shop_name: str, place_name: str):
    """(strong, total): strong = shared non-generic tokens, total = all shared tokens."""
    tokens = set(norm(shop_name).split())
    ptoks = set(norm(place_name).split())
    squashed = norm(place_name).replace(" ", "")
    shared = {t for t in tokens if t in ptoks or (len(t) >= 4 and t in squashed)}
    return len(shared - GENERIC), len(shared)


def _request(key: str, url: str, body, mask: str, sku: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method="POST" if body is not None else "GET",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": mask,
        },
    )
    err = "unknown"
    for attempt in (1, 2):  # one retry, for transient failures only
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.load(r)
                if places_ledger:
                    recorded_sku = sku or (
                        "text_search_enterprise"
                        if body is not None
                        else "place_details_enterprise"
                    )
                    try:
                        places_ledger.record(recorded_sku)
                    except Exception:
                        pass
                return data
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace").replace(key, "<key>")[:400]
            if e.code in FATAL_HTTP:
                raise FatalApiError(f"HTTP {e.code}: {msg}") from None
            if e.code == 404:
                return {"error": f"HTTP 404: {msg}", "notFound": True}
            err = f"HTTP {e.code}: {msg}"
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                err = "timeout"
            else:
                raise FatalApiError(f"network: {e.reason}") from None
        except TimeoutError:
            err = "timeout"
        if attempt == 1:
            time.sleep(1.0)
    return {"error": err}


def search(key: str, query: str, lat: float, lng: float) -> dict:
    dlat = RESTRICT_M / 111_320
    dlng = RESTRICT_M / (111_320 * math.cos(math.radians(lat)))
    body = {
        "textQuery": query,
        "pageSize": PAGE_SIZE,
        "locationRestriction": {
            "rectangle": {
                "low": {"latitude": lat - dlat, "longitude": lng - dlng},
                "high": {"latitude": lat + dlat, "longitude": lng + dlng},
            }
        },
    }
    return _request(key, SEARCH_URL, body, SEARCH_MASK)


def lookup(key: str, shop: dict, lat: float, lng: float) -> dict:
    """Place Details by stored placeId when present (dead ID -> search + flag), else search."""
    pid = shop.get("placeId")
    if pid:
        res = _request(key, DETAILS_URL.format(id=pid), None, DETAILS_MASK)
        if not res.get("notFound"):
            return res if "error" in res else {"places": [res], "byId": True}
        res = search(key, f"{shop['name']} {shop['address']}", lat, lng)
        res["placeIdDead"] = pid
        return res
    return search(key, f"{shop['name']} {shop['address']}", lat, lng)


def pick(places: list, shop: dict, lat: float, lng: float):
    """Best in-range candidate as (place, dist_m, strong, total), or None."""
    cands = []
    for p in places:
        loc = p.get("location") or {}
        if "latitude" not in loc or "longitude" not in loc:
            continue
        d = haversine_m(lat, lng, loc["latitude"], loc["longitude"])
        if d > MAX_DIST_M:
            continue
        strong, total = name_overlap(
            shop["name"], (p.get("displayName") or {}).get("text", "")
        )
        cands.append((p, d, strong, total))
    # Most non-generic overlap wins, then most total overlap, then nearest.
    return max(cands, key=lambda c: (c[2], c[3], -c[1]), default=None)


def fmt_count(n) -> str:
    return "—" if not n else f"{n:,}"


def evaluate(shop: dict, res: dict, lat: float, lng: float, accepted: bool):
    """Score one shop's response -> (rating, count, dist, flags, update_or_None)."""
    if "error" in res:
        return None, None, None, [f"API {res['error'][:80]}"], None
    choice = pick(res.get("places", []), shop, lat, lng)
    if not choice:
        return None, None, None, [f"UNMATCHED (nothing within {MAX_DIST_M} m)"], None
    p, dist, strong, total = choice
    flags, refuse, soft = [], False, False
    if res.get("placeIdDead"):
        flags.append("placeId gone, re-matched by search")
    gname = (p.get("displayName") or {}).get("text", "")
    if strong == 0:
        flags.append(f"NAME? google='{gname}'")
        refuse = True
    status = p.get("businessStatus", "")
    if status == "CLOSED_PERMANENTLY":
        flags.append(status)
        refuse = True
    elif status and status != "OPERATIONAL":
        flags.append(status)
        soft = True
    rating, count = p.get("rating"), p.get("userRatingCount")
    stored = shop.get("ratingNum") or 0
    if rating is None or count is None:
        flags.append("no rating on Google")
        refuse = True
    elif stored and count < stored:
        flags.append(f"count↓ {stored:,}→{count:,}")
        if count < DROP_LIMIT * stored:
            soft = True
    if soft and not accepted:
        flags.append("needs --accept")
        refuse = True
    update = None
    if not refuse:
        update = {
            "rating": round(float(rating), 1),
            "ratingCount": fmt_count(count),
            "ratingNum": int(count),
            "placeId": p.get("id") or shop.get("placeId"),
        }
    return rating, count, int(dist), flags, update


def dump_raw(path: Path, raw: dict) -> None:
    """Merge this run's responses into the dump; never drop entries for shops not iterated."""
    if not raw:
        return
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            existing = {}
    existing.update(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=1))
    print(f"raw responses -> {path}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--write", action="store_true", help="write public/shops.json (needs --replay)"
    )
    ap.add_argument(
        "--county",
        default="",
        choices=[
            "",
            "fulton",
            "dekalb",
            "forsyth",
            "gwinnett",
            "cobb",
            "cherokee",
            "hall",
            "dawson",
            "clayton",
            "henry",
            "fayette",
            "coweta",
            "douglas",
            "rockdale",
        ],
        help="filter to shops in this county (default: all)",
    )
    ap.add_argument(
        "--only", default="", help="only shops whose name contains this text"
    )
    ap.add_argument(
        "--raw", default="", help="dump path (default scratch/ratings-<date>.json)"
    )
    ap.add_argument(
        "--replay",
        default="",
        help="re-use dumped responses instead of calling the API",
    )
    ap.add_argument(
        "--accept",
        action="append",
        default=[],
        metavar="NAME",
        help="write this shop despite a soft refusal (repeatable, substring match)",
    )
    ap.add_argument("--sleep", type=float, default=0.15)
    args = ap.parse_args()

    if args.write and not args.replay:
        sys.exit(
            "--write requires --replay <dump>: audit a live run first, then write what was audited"
        )
    replay = None
    if args.replay:
        replay = json.loads(Path(args.replay).read_text())
        if not isinstance(replay, dict):
            sys.exit(f"{args.replay}: replay file must be a JSON object")
    key = None if replay is not None else load_key()
    raw_path = (
        Path(args.raw)
        if args.raw
        else SCRATCH / f"ratings-{date.today().isoformat()}.json"
    )

    data = json.loads(SHOPS_PATH.read_text())
    addr = data["addr"]
    shops = [s for s in data["shops"] if args.only.lower() in s["name"].lower()]
    if args.county:
        bounds = load_county_bounds()
        shops = [s for s in shops if in_county(s, addr, args.county, bounds)]
        if not shops:
            sys.exit(f"no shops match --county {args.county}")
    if not shops:
        sys.exit("no shops match --only")

    def key_of(
        s,
    ):  # the same shop name can exist in two cities; addrKey is city-prefixed
        return f"{s['addrKey']}|{s['name']}"

    def accepted(s):
        return any(a.lower() in s["name"].lower() for a in args.accept)

    raw, rows, missing, fatal = {}, [], [], None
    try:
        for s in shops:
            c = addr[s["addrKey"]]
            if replay is not None:
                res = replay.get(key_of(s)) or replay.get(
                    s["name"]
                )  # older dumps keyed by name
                if res is None:
                    missing.append(s["name"])
                    rows.append((s, None, None, None, ["not in replay file"], None))
                    continue
            else:
                res = lookup(key, s, c["lat"], c["lng"])
                time.sleep(args.sleep)
            raw[key_of(s)] = res
            rows.append((s, *evaluate(s, res, c["lat"], c["lng"], accepted(s))))
    except FatalApiError as e:
        fatal = str(e)
    except KeyboardInterrupt:
        fatal = "interrupted"
    finally:
        if replay is None or args.raw:  # live runs always dump; replay only when asked
            dump_raw(raw_path, raw)

    # ---- report -------------------------------------------------------
    print("| # | shop | stored | google | Δ count | dist | flags |")
    print("|---|---|---|---|---|---|---|")
    for i, (s, rating, count, dist, flags, update) in enumerate(rows, 1):
        stored = f"{s.get('rating')} ({s.get('ratingNum') or 0:,})"
        if rating is None:
            new = "—"
        elif count is None:
            new = f"{rating} (n/a)"
        else:
            new = f"{rating} ({count:,})"
        delta = (
            ""
            if (count is None or not s.get("ratingNum"))
            else f"{count - s['ratingNum']:+,}"
        )
        mark = "" if update else " ⚠"
        print(
            f"| {i} | {s['name']}{mark} | {stored} | {new} | {delta} | {dist if dist is not None else ''} | {'; '.join(flags)} |"
        )
    updates = [(s, u) for s, _r, _c, _d, _f, u in rows if u]
    refused = [
        s["name"] for s, _r, _c, _d, _f, u in rows if not u and s["name"] not in missing
    ]
    print(f"\nupdatable: {len(updates)}   refused: {len(refused)} -> {refused}")
    if missing:
        print(f"not in replay file: {len(missing)} -> {missing}")
    if fatal:
        print(f"\nABORTED after {len(rows)} of {len(shops)} shops: {fatal}")
        return 2

    if not args.write:
        print("(dry run — nothing written)")
        return 0
    if missing:
        print(
            f"refusing --write: {len(missing)} shops are not in the replay file (use --only, or a full dump)"
        )
        return 2
    for s, u in updates:
        s.update(u)
    SHOPS_PATH.write_text(json.dumps(data, indent=2))  # file has no trailing newline
    print(f"wrote {len(updates)} shops -> {SHOPS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
