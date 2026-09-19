#!/usr/bin/env python3
"""Discover every coffee shop, café, bakery, tea house and dessert café in the North
Atlanta region via Places API (New) Text Search, and generate public/places.json.

Two passes, then write exactly what was audited:

    python3 scripts/discover_places.py --dry-run
        pass 1 only (free IDs-only SKU): crawls the region and prints, per query, the
        leaf cells, result counts and the exact number of paid calls pass 2 would make.
    python3 scripts/discover_places.py
        pass 1, the usage gate, then pass 2 (Text Search Enterprise; 1,000 free per
        month). Dumps every place to scratch/places-<date>.json and prints the report.
        Nothing under public/ is written.
    python3 scripts/discover_places.py --replay scratch/places-<date>.json --write
        rebuilds public/places.json from the dump. No API calls.

Options:
    --usage-threshold N   refuse to run at all when this month's ledger is already >= N (default 500)
    --max-paid-calls N    refuse pass 2 when ledger + planned calls would exceed N (default 900)
    --sleep S             seconds between calls (default 0.1)
    --raw PATH            dump path (default scratch/places-<date>.json)

Key (never printed): $GOOGLE_MAPS_API_KEY wins, else ~/.config/caffeye/google_maps_key.
Ledger of calls made: ~/.config/caffeye/places_usage.json (see scripts/places_ledger.py).
Region, query types, category mapping and chain list are the constants below.
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import places_ledger as ledger  # noqa: E402
from refresh_ratings import (  # noqa: E402
    ROOT,
    SCRATCH,
    SEARCH_URL,
    SHOPS_PATH,
    FatalApiError,
    _request,
    haversine_m,
    load_key,
    name_overlap,
    norm,
)

PLACES_PATH = ROOT / "public" / "places.json"
EXCLUDE_PATH = ROOT / "scripts" / "places_exclude.json"

REGION = {
    "label": "North Atlanta",
    # Only needs to contain the counties; membership is decided by county_label().
    "bbox": {"south": 33.70, "west": -84.80, "north": 34.45, "east": -83.75},
    # API county name -> label shown in the app. min_lat = only the part north of it.
    "counties": [
        {"api": "Gwinnett County", "label": "Gwinnett"},
        {"api": "Fulton County", "label": "Fulton", "min_lat": 33.90},
        {"api": "Forsyth County", "label": "Forsyth"},
        {"api": "DeKalb County", "label": "DeKalb", "min_lat": 33.90},
    ],
    "note": (
        "For Fulton and DeKalb only the part north of the top-end Perimeter (I-285) is included: "
        "Sandy Springs, Dunwoody, Doraville, Roswell, Alpharetta, Johns Creek and Milton."
    ),
}
# (includedType, textQuery). Pass 1 is free, so every in-scope type is queried.
QUERIES = [
    ("coffee_shop", "coffee"),
    ("cafe", "cafe"),
    ("bakery", "bakery"),
    ("tea_house", "tea house"),
    ("dessert_shop", "dessert"),
    ("dessert_restaurant", "dessert"),
    ("bagel_shop", "bagel"),
    ("donut_shop", "donut"),
]
CATEGORY_BY_PRIMARY = {
    "coffee_shop": "Coffee",
    "cafe": "Coffee",
    "cat_cafe": "Coffee",
    "dog_cafe": "Coffee",
    "bakery": "Bakery+Cafe",
    "bagel_shop": "Bakery+Cafe",
    "donut_shop": "Bakery+Cafe",
    "tea_house": "Tea/Boba",
    "dessert_shop": "Dessert Cafe",
    "dessert_restaurant": "Dessert Cafe",
}
TEA_NAME = re.compile(r"\b(boba|bubble tea|milk tea|tea ?house)\b", re.I)
# Mass-market chains are left out on purpose (matches the curated set, which keeps
# Paris Baguette and Tous Les Jours but no Starbucks or Dunkin').
CHAINS = (
    "starbucks",
    "dunkin",
    "krispy kreme",
    "mcdonald",
    "mccafe",
    "panera",
    "einstein bros",
    "tim hortons",
    "scooter",
    "dutch bros",
    "7 brew",
    "biggby",
)
PAGE_SIZE = 20
PAGE_LIMIT = (
    60  # documented Text Search cap per request set; a cell that hits it is split
)
MAX_DEPTH = 10  # 0.75° / 2**10 ≈ 80 m cells; never reached in practice
MAX_PAGES = 3
IDS_MASK = "places.id,nextPageToken"
FULL_FIELDS = [
    "id",
    "displayName",
    "formattedAddress",
    "addressComponents",
    "location",
    "primaryType",
    "types",
    "rating",
    "userRatingCount",
    "regularOpeningHours",
    "websiteUri",
    "googleMapsUri",
    "businessStatus",
]
FULL_MASK = ",".join("places." + f for f in FULL_FIELDS) + ",nextPageToken"
SKU_IDS = "text_search_ids_only"  # unlimited free
SKU_FULL = "text_search_enterprise"  # 1,000 free per month, then $35 per 1,000
DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]  # API day 0 = Sunday


# ---- geometry ---------------------------------------------------------------
@dataclass(frozen=True)
class Rect:
    south: float
    west: float
    north: float
    east: float

    def as_list(self):
        return [self.south, self.west, self.north, self.east]


def split(r: Rect):
    """Four quarters: SW, SE, NW, NE."""
    mlat = (r.south + r.north) / 2
    mlng = (r.west + r.east) / 2
    return [
        Rect(r.south, r.west, mlat, mlng),
        Rect(r.south, mlng, mlat, r.east),
        Rect(mlat, r.west, r.north, mlng),
        Rect(mlat, mlng, r.north, r.east),
    ]


def search_body(rect: Rect, qtype: str, text: str, page_token=None) -> dict:
    body = {
        "textQuery": text,
        "includedType": qtype,
        "strictTypeFiltering": True,
        "pageSize": PAGE_SIZE,
        "locationRestriction": {
            "rectangle": {
                "low": {"latitude": rect.south, "longitude": rect.west},
                "high": {"latitude": rect.north, "longitude": rect.east},
            }
        },
    }
    if page_token:
        body["pageToken"] = page_token
    return body


# ---- filters ----------------------------------------------------------------
def component(place: dict, kind: str):
    for c in place.get("addressComponents") or []:
        if kind in (c.get("types") or []):
            return c.get("longText")
    return None


def county_label(components, lat: float):
    """Label for an in-region county, or None. Applies the min_lat cut for Fulton/DeKalb."""
    name = None
    for c in components or []:
        if "administrative_area_level_2" in (c.get("types") or []):
            name = c.get("longText")
            break
    for rule in REGION["counties"]:
        if rule["api"] == name:
            if "min_lat" in rule and lat < rule["min_lat"]:
                return None
            return rule["label"]
    return None


def category_for(place: dict):
    """Category from primaryType (allowlist), with a boba/tea-house name override. None = drop."""
    cat = CATEGORY_BY_PRIMARY.get(place.get("primaryType"))
    if cat and TEA_NAME.search((place.get("displayName") or {}).get("text", "")):
        return "Tea/Boba"
    return cat


def is_chain(name: str) -> bool:
    n = norm(name)
    return any(re.search(r"\b" + re.escape(c) + r"\b", n) for c in CHAINS)


# ---- derived fields ---------------------------------------------------------
_AMPM = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", re.I)


def _fmt_time(m) -> str:
    h, mm, ap = m.group(1), m.group(2), m.group(3).lower()
    return f"{int(h)}{'' if mm in (None, '00') else ':' + mm}{ap}"


def _compact_span(text: str) -> str:
    t = text.replace("\u00a0", " ").replace("\u202f", " ").replace("–", "-").replace("—", "-")
    t = _AMPM.sub(_fmt_time, t)
    t = re.sub(r"\s*-\s*", "-", t)
    return re.sub(r"\s+", " ", t).strip()


def compact_hours(weekday_descriptions):
    """['Monday: 7:00 AM – 9:00 PM', ...] -> 'Mon-Fri 7am-9pm · Sat-Sun 8am-10:30pm'.
    Consecutive days with the same span are grouped; the week wraps so a Sunday that
    matches Monday's run joins it ('Sun-Thu ...'), matching the curated style."""
    if not weekday_descriptions:
        return None
    days = []
    for line in weekday_descriptions:
        day, _, span = line.partition(":")
        days.append((day.strip()[:3], _compact_span(span)))
    groups = []  # [first_day, last_day, span]
    for day, span in days:
        if groups and groups[-1][2] == span:
            groups[-1][1] = day
        else:
            groups.append([day, day, span])
    if len(groups) > 1 and groups[0][2] == groups[-1][2]:
        last = groups.pop()
        groups[0][0] = last[0]
    return " · ".join(f"{a}-{b} {s}" if a != b else f"{a} {s}" for a, b, s in groups)


def _close_minutes(period: dict):
    """Close time as minutes after the open day's midnight (>= 1440 means past midnight)."""
    o, c = period.get("open") or {}, period.get("close")
    if not c or "day" not in o or "day" not in c:
        return None
    return (
        ((c["day"] - o["day"]) % 7) * 1440 + c.get("hour", 0) * 60 + c.get("minute", 0)
    )


def _time_text(minutes: int) -> str:
    m = minutes % 1440
    if m == 0:
        return "midnight"
    h, mm = divmod(m, 60)
    return f"{h % 12 or 12}{':%02d' % mm if mm else ''}{'am' if h < 12 else 'pm'}"


def _days_text(days: set) -> str:
    if len(days) == 7:
        return "Daily"
    if days == {1, 2, 3, 4, 5}:
        return "Weekdays"
    if days == {0, 6}:
        return "Weekends"
    ordered = sorted(days)
    runs = []
    for d in ordered:
        if runs and runs[-1][1] == d - 1:
            runs[-1][1] = d
        else:
            runs.append([d, d])
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == 6:  # wrap Sat -> Sun
        first = runs.pop(0)
        runs[-1][1] = first[1]
    out = []
    for a, b in runs:
        out.append(DAYS[a] if a == b else f"{DAYS[a]}-{DAYS[b]}")
    return ", ".join(out)


def late_for(periods):
    """{'tier': '10pm+'|'midnight', 'when': 'Fri-Sat till 1am; rest of week till 11pm'} or None."""
    if not periods:
        return None
    latest = {}  # open day -> latest close, minutes after that day's midnight
    for p in periods:
        m = _close_minutes(p)
        if m is None:
            continue
        d = p["open"]["day"]
        latest[d] = max(latest.get(d, 0), m)
    midnight = {d for d, m in latest.items() if m >= 1440}
    ten = {d for d, m in latest.items() if 22 * 60 <= m < 1440}
    if not midnight and not ten:
        return None
    head, rest = (midnight, ten) if midnight else (ten, set())
    when = f"{_days_text(head)} till {_time_text(max(latest[d] for d in head))}"
    if rest:
        when += f"; rest of week till {_time_text(max(latest[d] for d in rest))}"
    return {"tier": "midnight" if midnight else "10pm+", "when": when}


def to_record(place: dict):
    """(record, None) for an in-scope place, else (None, reason)."""
    status = place.get("businessStatus") or "OPERATIONAL"
    if status != "OPERATIONAL":
        return None, f"status:{status}"
    loc = place.get("location") or {}
    lat, lng = loc.get("latitude"), loc.get("longitude")
    if lat is None or lng is None:
        return None, "no location"
    county = county_label(place.get("addressComponents"), lat)
    if not county:
        return None, "county"
    name = (place.get("displayName") or {}).get("text", "").strip()
    if not name:
        return None, "no name"
    if is_chain(name):
        return None, "chain"
    category = category_for(place)
    if not category:
        return None, f"type:{place.get('primaryType') or 'none'}"
    city = (
        component(place, "locality")
        or component(place, "postal_town")
        or component(place, "administrative_area_level_3")
    )
    if not city:
        return None, "no city"
    hours = place.get("regularOpeningHours") or {}
    count = place.get("userRatingCount")
    rec = {
        "placeId": place["id"],
        "name": name,
        "address": place.get("formattedAddress"),
        "city": city,
        "county": county,
    }
    nb = component(place, "neighborhood") or component(place, "sublocality")
    if nb:
        rec["neighborhood"] = nb
    rec.update(
        {
            "lat": round(float(lat), 6),
            "lng": round(float(lng), 6),
            "category": category,
            "types": [t for t in place.get("types") or [] if t in CATEGORY_BY_PRIMARY],
            "rating": round(float(place["rating"]), 1)
            if place.get("rating") is not None
            else None,
            "ratingNum": int(count) if count is not None else 0,
            "ratingCount": f"{int(count):,}" if count is not None else "0",
            "hours": compact_hours(hours.get("weekdayDescriptions")),
        }
    )
    late = late_for(hours.get("periods"))
    if late:
        rec["late"] = late
    rec["website"] = place.get("websiteUri")
    rec["googleUrl"] = place.get("googleMapsUri")
    return rec, None


def build_places(raw: dict, exclude_ids=frozenset()):
    """raw: {placeId: place} -> (records sorted by placeId, stats)."""
    recs, dropped = [], Counter()
    for pid, place in raw.items():
        if pid in exclude_ids:
            dropped["excluded"] += 1
            continue
        rec, reason = to_record(place)
        if rec is None:
            dropped[reason] += 1
            continue
        recs.append(rec)
    recs.sort(key=lambda r: r["placeId"])
    return recs, {"kept": len(recs), "dropped": dict(dropped)}


def usage_gate(used: int, planned: int, threshold: int, cap: int):
    """(ok, message). Refuse when the month is already at the threshold, or the run would pass the cap."""
    if used >= threshold:
        return False, (
            f"REFUSED: this month's ledger shows {used} Text Search Enterprise calls, at or above "
            f"--usage-threshold {threshold}. No calls made. Ledger: {ledger.default_path()}"
        )
    if used + planned > cap:
        return False, (
            f"REFUSED: {used} used + {planned} planned = {used + planned} would exceed "
            f"--max-paid-calls {cap}. No paid calls made. Ledger: {ledger.default_path()}"
        )
    return True, ""


# ---- API client --------------------------------------------------------------
class Client:
    """Live client: every request is counted in the ledger first; 429 backs off and retries."""

    def __init__(self, key: str, sleep: float):
        self.key, self.sleep = key, sleep
        self.calls = Counter()

    def __call__(self, body: dict, mask: str, sku: str) -> dict:
        for attempt in range(4):
            ledger.record(sku)
            self.calls[sku] += 1
            try:
                res = _request(self.key, SEARCH_URL, body, mask)
            except FatalApiError as e:
                if "HTTP 429" in str(e) and attempt < 3:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise
            time.sleep(self.sleep)
            if "error" in res:
                raise FatalApiError(res["error"])
            return res
        raise FatalApiError("rate limited four times in a row")


def fetch_pages(client, rect: Rect, qtype: str, text: str, mask: str, sku: str):
    """All pages (max 3) for one rect+type -> (places, calls_made)."""
    places, token, calls = [], None, 0
    while True:
        res = client(search_body(rect, qtype, text, token), mask, sku)
        calls += 1
        places.extend(res.get("places") or [])
        token = res.get("nextPageToken")
        if not token or len(places) >= PAGE_LIMIT or calls >= MAX_PAGES:
            return places, calls


def crawl(client, rect: Rect, qtype: str, text: str, depth: int = 0, leaves=None):
    """Pass 1 (free): quadtree over rect. Returns leaves as [(rect, n_results, n_calls)]."""
    if leaves is None:
        leaves = []
    places, calls = fetch_pages(client, rect, qtype, text, IDS_MASK, SKU_IDS)
    if len(places) >= PAGE_LIMIT and depth < MAX_DEPTH:
        for q in split(rect):
            crawl(client, q, qtype, text, depth + 1, leaves)
    else:
        leaves.append((rect, len(places), calls))
    return leaves


def planned_calls(leaves) -> int:
    """Paid calls pass 2 will make: one per page fetched in pass 1, skipping empty leaves."""
    return sum(calls for _rect, n, calls in leaves if n > 0)


def fetch_details(client, plan) -> dict:
    """Pass 2 (paid): plan = [(qtype, text, rect)] -> {placeId: place} (first sighting wins)."""
    raw = {}
    for item in plan:
        qtype, text, rect = item[:3]
        places, _ = fetch_pages(client, rect, qtype, text, FULL_MASK, SKU_FULL)
        for p in places:
            raw.setdefault(p["id"], p)
    return raw


# ---- dump / replay ----------------------------------------------------------
def write_dump(path: Path, dump: dict) -> None:
    """Merge places into an existing dump (never drop); replace the leaves/meta."""
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            existing = {}
    merged = dict(existing)
    merged.update({k: v for k, v in dump.items() if k != "places"})
    merged["places"] = {**existing.get("places", {}), **dump.get("places", {})}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=1))
    print(f"dump -> {path}  ({len(merged['places'])} places)")


def load_exclusions() -> set:
    if not EXCLUDE_PATH.exists():
        return set()
    return {e["placeId"] for e in json.loads(EXCLUDE_PATH.read_text())}


# ---- report -----------------------------------------------------------------
def report(recs, stats, curated, raw) -> None:
    by_cc = Counter((r["county"], r["category"]) for r in recs)
    counties = [c["label"] for c in REGION["counties"]]
    cats = sorted({r["category"] for r in recs})
    print("\n| county | " + " | ".join(cats) + " | total |")
    print("|---|" + "---|" * (len(cats) + 1))
    for county in counties:
        row = [by_cc[(county, c)] for c in cats]
        print(f"| {county} | " + " | ".join(str(n) for n in row) + f" | {sum(row)} |")
    print(
        f"\nkept {stats['kept']}; dropped: {json.dumps(stats['dropped'], sort_keys=True)}"
    )
    seen = set(raw)
    unseen = [
        s["name"] for s in curated if s.get("placeId") and s["placeId"] not in seen
    ]
    print(
        f"\ncurated shops NOT seen by the crawl (closure/relist leads): {len(unseen)} -> {unseen}"
    )
    curated_ids = {s.get("placeId") for s in curated}
    dupes = []
    for r in recs:
        if r["placeId"] in curated_ids:
            continue
        for s in curated:
            if (
                haversine_m(r["lat"], r["lng"], s["lat"], s["lng"]) <= 60
                and name_overlap(s["name"], r["name"])[0] > 0
            ):
                dupes.append(f"{r['name']} ~ {s['name']} ({r['placeId']})")
    print(
        f"discovered within 60 m of a curated shop with an overlapping name "
        f"(candidates for scripts/places_exclude.json): {len(dupes)}"
    )
    for d in dupes:
        print("  ", d)


def curated_with_coords() -> list:
    data = json.loads(SHOPS_PATH.read_text())
    out = []
    for s in data["shops"]:
        c = data["addr"].get(s.get("addrKey")) or {}
        out.append({**s, "lat": c.get("lat", 0.0), "lng": c.get("lng", 0.0)})
    return out


def write_places(recs, generated_at: str) -> None:
    data = {
        "version": 1,
        "checkedMonth": date.today().strftime("%B %Y"),
        "generatedAt": generated_at,
        "region": {
            "label": REGION["label"],
            "counties": [c["label"] for c in REGION["counties"]],
            "note": REGION["note"],
        },
        "places": recs,
    }
    PLACES_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(
        f"wrote {len(recs)} places -> {PLACES_PATH} ({PLACES_PATH.stat().st_size // 1024} KB)"
    )


# ---- main -------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="pass 1 only (free); print the paid-call estimate",
    )
    ap.add_argument(
        "--replay", default="", help="rebuild from a dump instead of calling the API"
    )
    ap.add_argument(
        "--write", action="store_true", help="write public/places.json (needs --replay)"
    )
    ap.add_argument(
        "--raw", default="", help="dump path (default scratch/places-<date>.json)"
    )
    ap.add_argument("--usage-threshold", type=int, default=500)
    ap.add_argument("--max-paid-calls", type=int, default=900)
    ap.add_argument("--sleep", type=float, default=0.1)
    args = ap.parse_args()

    if args.write and not args.replay:
        sys.exit(
            "--write requires --replay <dump>: audit a live run first, then write what was audited"
        )

    if args.replay:
        dump = json.loads(Path(args.replay).read_text())
        recs, stats = build_places(dump["places"], load_exclusions())
        report(recs, stats, curated_with_coords(), dump["places"])
        if args.write:
            write_places(
                recs,
                dump.get("generatedAt")
                or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        else:
            print("(replay — nothing written; add --write)")
        return 0

    used = ledger.used(SKU_FULL)
    ok, msg = usage_gate(used, 0, args.usage_threshold, args.max_paid_calls)
    if not ok:
        print(msg)
        return 2
    client = Client(load_key(), args.sleep)
    bbox = REGION["bbox"]
    root = Rect(bbox["south"], bbox["west"], bbox["north"], bbox["east"])
    plan, leaves_out = [], {}
    try:
        for qtype, text in QUERIES:
            try:
                leaves = crawl(client, root, qtype, text)
            except FatalApiError as e:
                if "HTTP 400" in str(e):
                    print(f"{qtype}: rejected by the API, skipped ({str(e)[:120]})")
                    continue
                raise
            leaves_out[qtype] = [[r.as_list(), n, c] for r, n, c in leaves]
            plan += [(qtype, text, r, c) for r, n, c in leaves if n > 0]
            print(
                f"{qtype:20} leaves {len(leaves):4}  results {sum(n for _r, n, _c in leaves):5}  "
                f"paid calls {planned_calls(leaves):4}"
            )
    except FatalApiError as e:
        print(f"ABORTED during pass 1: {e}")
        return 2
    planned = sum(c for _q, _t, _r, c in plan)
    print(
        f"\npass 1 done: {client.calls[SKU_IDS]} free calls; pass 2 would make {planned} paid calls "
        f"(ledger this month: {used}; free tier 1,000)"
    )
    if args.dry_run:
        print("(dry run — nothing fetched, nothing written)")
        return 0
    ok, msg = usage_gate(used, planned, args.usage_threshold, args.max_paid_calls)
    if not ok:
        print(msg)
        return 2

    raw_path = (
        Path(args.raw)
        if args.raw
        else SCRATCH / f"places-{date.today().isoformat()}.json"
    )
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw = {}
    try:
        raw = fetch_details(client, plan)
    except FatalApiError as e:
        print(f"ABORTED during pass 2: {e}")
        return 2
    finally:
        write_dump(
            raw_path,
            {
                "generatedAt": generated_at,
                "region": REGION,
                "leaves": leaves_out,
                "places": raw,
            },
        )
    recs, stats = build_places(raw, load_exclusions())
    report(recs, stats, curated_with_coords(), raw)
    print(
        f"\npaid calls this run: {client.calls[SKU_FULL]}; ledger now {ledger.used(SKU_FULL)}"
    )
    print(
        f"(nothing written — review, then: python3 scripts/discover_places.py --replay {raw_path} --write)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
