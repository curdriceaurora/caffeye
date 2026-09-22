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
from __future__ import annotations

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
CURATIONS_PATH = ROOT / "scripts" / "curations.json"

REGION = {
    "label": "Metro Atlanta",
    # Only needs to contain the counties; membership is decided by county_label().
    "bbox": {"south": 33.20, "west": -84.95, "north": 34.65, "east": -83.60},
    # API county name -> label shown in the app.
    "counties": [
        {"api": "Gwinnett County", "label": "Gwinnett"},
        {"api": "Fulton County", "label": "Fulton"},
        {"api": "Forsyth County", "label": "Forsyth"},
        {"api": "DeKalb County", "label": "DeKalb"},
        {"api": "Cobb County", "label": "Cobb"},
        {"api": "Cherokee County", "label": "Cherokee"},
        {"api": "Hall County", "label": "Hall"},
        {"api": "Dawson County", "label": "Dawson"},
        {"api": "Clayton County", "label": "Clayton"},
        {"api": "Henry County", "label": "Henry"},
        {"api": "Fayette County", "label": "Fayette"},
        {"api": "Coweta County", "label": "Coweta"},
        {"api": "Douglas County", "label": "Douglas"},
        {"api": "Rockdale County", "label": "Rockdale"},
    ],
    "note": (
        "Covers Metro Atlanta (including Atlanta urban core, Decatur, South Metro, and North Georgia foothills) "
        "across Fulton, DeKalb, Cobb, Gwinnett, Cherokee, Forsyth, Hall, Dawson, Clayton, Henry, Fayette, Coweta, Douglas, and Rockdale counties."
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
    "cat_cafe": "Specialty",
    "dog_cafe": "Specialty",
    "bakery": "Bakery+Cafe",
    "bagel_shop": "Bakery+Cafe",
    "donut_shop": "Bakery+Cafe",
    "tea_house": "Tea/Boba",
    "dessert_shop": "Dessert Cafe",
    "dessert_restaurant": "Dessert Cafe",
}
TEA_NAME = re.compile(r"\b(boba|bubble tea|milk tea|tea ?house)\b", re.I)
ROASTERY_NAMES = (
    "east pole", "portrait coffee", "chrome yellow", "radio roasters", "peach coffee",
    "cool beans coffee", "warm waves", "blue mountain coffee", "break coffee",
    "san francisco coffee roasting", "notable roasting", "cips coffee", "mzizi coffee",
    "coffee that matters", "bellwood coffee", "brash coffee", "dancing goats",
    "fuel coffee roasters", "zoom coffee roasters", "roast coffee", "phoenix roasters",
    "boarding pass coffee", "land of a thousand hills", "perc coffee",
    "spiller park", "banjo coffee", "taproom coffee", "shiba coffee", "shibam coffee"
)
ROASTER_NAME = re.compile(r"\b(roast(ers?|ery|ings?)|perc)\b", re.I)
SPECIALTY_NAME = re.compile(
    r"\b("
    r"coffee lab|"
    r"yemeni|turkish|arabic|ethiopi\w*|cardamom|cà phê|ca phe|vietnamese coffee|"
    r"cats? (cafe|lounge)|dogs? (cafe|lounge)|craft cafe|board game|ceramics|apothecary|"
    r"specialty (coffee|tea|roast|cafe)"
    r")\b",
    re.I
)

# Supermarket and grocery store in-store bakeries are completely excluded.
GROCERY_PATTERNS = (
    r"\bkroger\b",
    r"\bwalmart\b",
    r"\bsam\s*s?\s*club\b",
    r"\bcostco\b",
    r"\bwhole foods\b",
    r"\bpublix\b",
    r"\btarget\b",
    r"\bsprouts\b",
    r"\bh\s*mart\b",
    r"\btrader joe",
    r"\bfresh market\b",
    r"\bingles\b",
    r"\blidl\b",
    r"\baldi\b",
    r"\bbj\s*s\s*wholesale\b",
)

# Fast-food burger/fried food restaurants are excluded.
FAST_FOOD_PATTERNS = (
    r"\bmcdonald",
    r"\bmccafe\b",
    r"\bburger king\b",
    r"\bwendy\s*s\b",
    r"\bchick-fil-a\b",
    r"\btaco bell\b",
)

# Coffee/tea/bakery chains are included and classified as 'franchise'
# under the unified Franchise model.
CHAINS = (
    "starbucks",
    "dunkin",
    "krispy kreme",
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
    """Label for an in-region county, or None. Applies the min_lat cut if configured for a county."""
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


def classify_category(
    name: str,
    primary_type: str | None = None,
    current_cat: str | None = None,
    types: list | None = None,
) -> str | None:
    """Single-source category decision shared by discovery and curation.

    Discovery path (primary_type given): CATEGORY_BY_PRIMARY allowlist decides
    the base category; unknown types return None (drop the record). The
    name/type overrides below then apply.
    Curation path (current_cat given): the stored category is the base;
    "Roasters" is never downgraded. Never returns None — falls back to the
    stored category.

    Shared rules (in order):
    1. Concept cafes (cat_cafe/dog_cafe types, or Specialty at crawl) -> Specialty.
    2. Bakery+Cafe / Dessert Cafe / Tea/Boba are guarded: generic specialty
       name patterns cannot move them; only an explicit roastery-list match
       upgrades to Roasters (concept types still yield Specialty on the
       curation path).
    3. Tea/Boba (tea_house primary or TEA_NAME) takes precedence over loose
       cultural/specialty patterns, unless a known roastery.
    4. Roastery brands / roaster names -> Roasters; cultural/concept names ->
       Specialty; otherwise the base category stands.
    """
    types = [t.lower() for t in (types or [])]
    name = name or ""
    n_lower = name.lower()
    if primary_type is not None:
        cat = CATEGORY_BY_PRIMARY.get(primary_type)
        if not cat:
            return None
        if cat == "Specialty":
            return "Specialty"
    else:
        cat = current_cat
        if cat == "Roasters":
            return "Roasters"
        if any(t in ("cat_cafe", "dog_cafe") for t in types):
            return "Specialty"

    is_roastery = any(r in n_lower for r in ROASTERY_NAMES)
    is_spec_name = bool(SPECIALTY_NAME.search(name))
    is_tea = (cat == "Tea/Boba") or bool(TEA_NAME.search(name))

    # Guard: bakeries, dessert cafes, and tea houses don't convert on generic
    # specialty name patterns.
    if cat in ("Bakery+Cafe", "Dessert Cafe", "Tea/Boba"):
        if is_roastery:
            return "Roasters"
        return cat

    # Precedence: Tea/Boba wins over generic specialty unless a known roastery.
    if is_tea:
        if is_roastery:
            return "Roasters"
        return "Tea/Boba"

    if is_roastery or ROASTER_NAME.search(name):
        return "Roasters"

    if is_spec_name:
        return "Specialty"

    return cat


def category_for(place: dict):
    """Category from primaryType (allowlist), with specialty, roastery, and tea-house overrides. None = drop."""
    name = (place.get("displayName") or {}).get("text", "") or place.get("name", "")
    return classify_category(
        name,
        primary_type=place.get("primaryType"),
        types=place.get("types"),
    )


def is_chain(name: str) -> bool:
    n = norm(name)
    return any(re.search(r"\b" + re.escape(c) + r"\b", n) for c in CHAINS)


def is_grocery(name: str) -> bool:
    n = norm(name)
    return any(re.search(pat, n) for pat in GROCERY_PATTERNS)


def is_fast_food(name: str) -> bool:
    n = norm(name)
    return any(re.search(pat, n) for pat in FAST_FOOD_PATTERNS)


# ---- franchise / independent classification ---------------------------------
LOCATIONS = (
    "duluth", "alpharetta", "johns creek", "suwanee", "roswell", "sandy springs",
    "dunwoody", "norcross", "lilburn", "lawrenceville", "snellville", "sugarloaf",
    "perimeter", "haynes bridge", "buford", "peachtree", "georgia", "ga", "cumming",
    "doraville", "chamblee", "milton", "crabapple", "loganville", "dacula", "marietta",
    "kennesaw", "acworth", "smyrna", "vinings", "cumberland", "east cobb",
    "woodstock", "canton", "gainesville", "flowery branch", "ball ground", "holly springs",
    "oakwood", "dawsonville", "avalon", "sugarloaf plaza", "town center", "drive thru",
)

FRANCHISE_KEYWORDS = (
    # Supermarkets / Big box / Grocery in-store bakeries (dropped during ingestion, kept as franchise fallback)
    r"\bkroger\b",
    r"\bwalmart\b",
    r"\bsam\s*s?\s*club\b",
    r"\bcostco\b",
    r"\bwhole foods\b",
    r"\bpublix\b",
    r"\btarget\b",
    r"\bsprouts\b",
    r"\bh\s*mart\b",
    r"\btrader joe",
    r"\bfresh market\b",
    r"\bingles\b",
    r"\blidl\b",
    r"\baldi\b",
    r"\bbj\s*s\s*wholesale\b",
    # Coffee franchises / national & regional chains
    r"\bcaribou\b",
    r"\b(the\s+)?human bean\b",
    r"\bellianos\b",
    r"\b7\s*brew\b",
    r"\bjust love coffee\b",
    r"\bscooter\s*s?\b",
    r"\bdutch bros\b",
    r"\bbiggby\b",
    r"\bbad ass coffee\b",
    r"\bpj\s*s\s*coffee\b",
    r"\bsummit coffee\b",
    r"\baroma espresso\b",
    r"\bdunkin\b",
    r"\bstarbucks\b",
    r"\btim hortons\b",
    r"\bkrispy kreme\b",
    r"\bpanera\b",
    r"\beinstein bros\b",
    r"\bpeet\s*s\b",
    r"\bblack rifle\b",
    r"\bziggi\s*s\b",
    r"\bland of a thousand hills\b",
    r"\bqamaria\b",
    r"\btom n toms\b",
    r"\bcafe intermezzo\b",
    # Bakery / treat franchises / chains
    r"\bcrumbl\b",
    r"\bparis baguette\b",
    r"\btous les jours\b",
    r"\bcinnabon\b",
    r"\bgreat harvest\b",
    r"\bjeff\s*s?\s*bagel\b",
    r"\bduck donuts\b",
    r"\bmochinut\b",
    r"\bnothing bundt\b",
    r"\bwetzel\s*s?\b",
    r"\bauntie anne\b",
    r"\bshipley\b",
    r"\ble macaron\b",
    r"\bbeard papa\b",
    r"\bfluffy fluffy\b",
    r"\bsmallcakes\b",
    r"\bcinnaholic\b",
    r"\btiff\s*s?\s*treats\b",
    r"\brising roll\b",
    r"\bda\s*vinci\s*s?\s*donuts\b",
    r"\batlanta bread\b",
    r"\bcorner bakery\b",
    r"\byonutz\b",
    # Tea / Boba franchises & chains
    r"\bkung fu tea\b",
    r"\bgong cha\b",
    r"\bsharetea\b",
    r"\btiger sugar\b",
    r"\bding tea\b",
    r"\bhappy lemon\b",
    r"\bt[\s-]?swirl\b",
    r"\bonezo\b",
    r"\bchicha san chen\b",
    r"\bxing fu tang\b",
    r"\bmatcha cafe maiko\b",
    r"\bkokee\b",
    r"\bquickly\s*s?\b",
    r"\bchatime\b",
    r"\bvivi bubble tea\b",
    r"\bteaspoon\b",
    r"\bfeng cha\b",
    r"\bmeet fresh\b",
    r"\bmolly tea\b",
    r"\b7 leaves\b",
    r"\bbobaology\b",
    r"\bbubbleology\b",
    r"\bzero\s*degrees\b",
    r"\btapioca express\b",
    r"\bit\s*s boba time\b",
    r"\bboba time\b",
    r"\byifang\b",
    r"\bhey\s*tea\b",
    r"\bsunright\b",
    r"\btaichi bubble tea\b",
    r"\btea top\b",
    r"\bkomma tea\b",
    # Regional GA chains / multi-unit bakery cafes
    r"\bsweet hut\b",
    r"\b(cafe\s+)?mozart\b",
    r"\bhansel\b.*\bgretel\b",
    r"\bwhite windmill\b",
    r"\bcuckoo\s*s?\b",
    r"\bvincent bakery\b",
    r"\bbagel boys\b",
    r"\b101 bagel\b",
    r"\bsarah\s*s?\s*donuts?\b",
    r"\bsara\s*s?\s*donuts?\b",
    r"\bpearl\s*s?\s*tea\b",
    r"\bone\s*zo\b",
)

BRAND_OVERRIDES = {
    "glaze tea": "independent",
    "onezo": "franchise",
    "one zo": "franchise",
    "one zo boba": "franchise",
}


def clean_brand(name: str) -> str:
    n = norm(name)
    n = re.sub(r"\b\d+\b", "", n)
    for loc in LOCATIONS:
        n = re.sub(r"\b" + re.escape(loc) + r"\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def model_for(name: str, brand_counts=None) -> str:
    """'franchise' for national/regional chains and multi-location brands, else 'independent'."""
    cb = clean_brand(name)
    if cb in BRAND_OVERRIDES:
        return BRAND_OVERRIDES[cb]
    n = norm(name)
    for pat in FRANCHISE_KEYWORDS:
        if re.search(pat, n):
            return "franchise"
    if brand_counts and brand_counts.get(cb, 0) >= 3:
        return "franchise"
    return "independent"


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



def _parse_periods(periods: list) -> dict:
    """Map open day (0=Sun..6=Sat) -> latest closing time ('24h' or minutes after open day's midnight)."""
    if not periods:
        return {}
    if len(periods) == 1 and not periods[0].get("close"):
        return {d: "24h" for d in range(7)}

    daily_close = {}
    for p in periods:
        o, c = p.get("open") or {}, p.get("close")
        if not o or "day" not in o:
            continue
        if not c:
            daily_close[o["day"]] = "24h"
            continue
        if "day" not in c:
            continue

        o_day = o["day"]
        c_day = c["day"]
        c_min = c.get("hour", 0) * 60 + c.get("minute", 0)
        diff = (c_day - o_day) % 7

        if diff == 0:
            if daily_close.get(o_day) != "24h":
                daily_close[o_day] = max(daily_close.get(o_day, 0), c_min)
        elif diff == 1:
            close_after = 1440 + c_min
            if daily_close.get(o_day) != "24h":
                daily_close[o_day] = max(daily_close.get(o_day, 0), close_after)
        else:
            daily_close[o_day] = "24h"
            curr = (o_day + 1) % 7
            while curr != c_day:
                daily_close[curr] = "24h"
                curr = (curr + 1) % 7
            if c_min > 0 and daily_close.get(c_day) != "24h":
                daily_close[c_day] = max(daily_close.get(c_day, 0), c_min)
    return daily_close


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
    """{'tier': '10pm+'|'midnight', 'when': '...'} or None."""
    daily = _parse_periods(periods)
    if not daily:
        return None

    late_days = {}
    for d, m in daily.items():
        if m == "24h":
            late_days[d] = "24h"
        elif isinstance(m, int) and m >= 22 * 60:
            late_days[d] = m

    if not late_days:
        return None

    by_close = {}
    for d, m in late_days.items():
        by_close.setdefault(m, set()).add(d)

    has_midnight = any(
        m == "24h" or (isinstance(m, int) and m >= 1440)
        for m in late_days.values()
    )
    tier = "midnight" if has_midnight else "10pm+"

    def sort_key(item):
        m, days = item
        if m == "24h":
            return (2, 99999)
        return (1, m)

    parts = []
    for m, days in sorted(by_close.items(), key=sort_key, reverse=True):
        d_text = _days_text(days)
        if m == "24h":
            if len(days) == 7:
                parts.append("Open 24 hours")
            else:
                parts.append(f"{d_text} Open 24 hours")
        else:
            parts.append(f"{d_text} till {_time_text(m)}")

    return {"tier": tier, "when": "; ".join(parts)}


def to_record(place: dict, brand_counts=None, curations=None, curation_defaults=None):
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
    if is_grocery(name):
        return None, "grocery"
    if is_fast_food(name):
        return None, "fast_food"
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
            "model": model_for(name, brand_counts),
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
    if curations and place.get("id") in curations:
        cur = curations[place["id"]]
        if curation_defaults is None:
            curation_defaults = load_curation_defaults()
        if "category" in cur:
            rec["category"] = cur["category"]
        if "cw" in cur:
            rec["cw"] = stamp_provenance(cur["cw"], cur, curation_defaults)
        if "usp" in cur:
            rec["usp"] = cur["usp"]
        if "loved" in cur:
            rec["loved"] = cur["loved"]
        if "signature" in cur:
            rec["signature"] = cur["signature"]
    return rec, None


def load_curations() -> dict:
    if not CURATIONS_PATH.exists():
        return {}
    data = json.loads(CURATIONS_PATH.read_text())
    return data.get("places", {})


def load_curation_defaults(path=None) -> tuple:
    """(defaultVerified, defaultSource) from the curation file's top-level
    metadata. (None, 'editorial') when the file is missing or silent —
    provenance is inherited from metadata, never hardcoded or stamped 'now'."""
    p = Path(path) if path else CURATIONS_PATH
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        return (None, "editorial")
    if not isinstance(data, dict):
        return (None, "editorial")
    return (data.get("defaultVerified"), data.get("defaultSource", "editorial"))


def stamp_provenance(cw: dict, cur: dict, defaults: tuple) -> dict:
    """Copy a curated cw block with per-record source/verified attribution.
    Per-record values win; file-level defaults fill gaps; unknown stays absent."""
    out = dict(cw)
    def_ver, def_src = defaults
    out["source"] = cur.get("source", def_src)
    verified = cur.get("verified", def_ver)
    if verified:
        out["verified"] = verified
    return out


def build_places(raw: dict, exclude_ids=frozenset(), curations=None,
                 curation_defaults=None):
    """raw: {placeId: place} -> (records sorted by placeId, stats)."""
    if curations is None:
        curations = load_curations()
    if curation_defaults is None:
        curation_defaults = load_curation_defaults()
    brand_counts = Counter(
        clean_brand((p.get("displayName") or {}).get("text", ""))
        for p in raw.values()
    )
    recs, dropped = [], Counter()
    for pid, place in raw.items():
        if pid in exclude_ids:
            dropped["excluded"] += 1
            continue
        rec, reason = to_record(place, brand_counts, curations, curation_defaults)
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
class BudgetExceeded(FatalApiError):
    """Raised when the paid-call ceiling is hit mid-run. Handled like an abort,
    except the finally block retains the partial results as an incomplete dump."""


class PaidBudget:
    """Runtime ceiling for paid calls. Unlike the preflight estimate (which can
    go stale when pagination shifts), this re-reads the ledger before every
    paid request and stops the run before the next billable call."""

    def __init__(self, cap: int, sku: str = SKU_FULL):
        self.cap = cap
        self.sku = sku

    def check(self) -> None:
        try:
            spent = ledger.used(self.sku)
        except Exception as e:
            raise BudgetExceeded(
                f"paid-call budget unverifiable (ledger unreadable: {e}); "
                f"stopping before further paid calls."
            ) from e
        if spent >= self.cap:
            raise BudgetExceeded(
                f"paid-call budget exhausted: ledger shows {spent} {self.sku} calls "
                f"(cap {self.cap}). Partial results retained as an incomplete dump."
            )

    def acquire(self) -> int:
        """Reserve one paid call atomically (check-and-increment under the
        ledger lock) and return the new usage count. Raises BudgetExceeded
        when the cap is reached, the ledger is unreadable, or another runner
        took the last allowance — so concurrent runs cannot jointly overshoot.
        A reservation that never turns into a request over-counts by one;
        that errs toward safety for a spend guard."""
        try:
            return ledger.reserve(self.sku, self.cap)
        except ledger.CapExceeded as e:
            raise BudgetExceeded(
                f"paid-call budget exhausted ({e}). "
                f"Partial results retained as an incomplete dump."
            ) from e
        except Exception as e:
            raise BudgetExceeded(
                f"paid-call budget unverifiable (ledger unreadable: {e}); "
                f"stopping before further paid calls."
            ) from e


class Client:
    """Live client: paid requests reserve ledger allowance before sending;
    429 backs off and retries."""

    def __init__(self, key: str, sleep: float, budget=None):
        self.key, self.sleep = key, sleep
        self.budget = budget
        self.calls = Counter()

    def __call__(self, body: dict, mask: str, sku: str) -> dict:
        pre_counted = False
        if sku == SKU_FULL and self.budget is not None:
            self.budget.acquire()
            pre_counted = True
        for attempt in range(4):
            try:
                res = _request(self.key, SEARCH_URL, body, mask, sku=sku,
                               pre_counted=pre_counted)
            except FatalApiError as e:
                if "HTTP 429" in str(e) and attempt < 3:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise
            self.calls[sku] += 1
            time.sleep(self.sleep)
            if "error" in res:
                raise FatalApiError(res["error"])
            return res
        raise FatalApiError("rate limited four times in a row")


def fetch_pages(
    client,
    rect: Rect,
    qtype: str,
    text: str,
    mask: str,
    sku: str,
    on_page=None,
    budget=None,
):
    """All pages (max 3) for one rect+type -> (places, calls_made).

    When budget is given and this is a paid SKU, the budget is checked before
    every request so the run stops instead of overshooting the ceiling when
    pagination expands beyond the preflight estimate.
    """
    places, token, calls = [], None, 0
    while True:
        if budget is not None and sku == SKU_FULL:
            budget.check()
        res = client(search_body(rect, qtype, text, token), mask, sku)
        calls += 1
        page_places = res.get("places") or []
        places.extend(page_places)
        if on_page:
            on_page(page_places)
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


def fetch_details(client, plan, out: dict | None = None, budget=None) -> dict:
    """Pass 2 (paid): plan = [(qtype, text, rect)] -> {placeId: place} (first sighting wins)."""
    raw = out if out is not None else {}
    for item in plan:
        qtype, text, rect = item[:3]
        extra = {} if budget is None else {"budget": budget}
        fetch_pages(
            client,
            rect,
            qtype,
            text,
            FULL_MASK,
            SKU_FULL,
            on_page=lambda page: [raw.setdefault(p["id"], p) for p in page],
            **extra,
        )
    return raw


# ---- dump / replay ----------------------------------------------------------
def write_dump(path: Path, dump: dict, incomplete: bool = False) -> None:
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
    if incomplete:
        merged["incomplete"] = True
    elif "incomplete" in merged and not incomplete:
        merged.pop("incomplete", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=1))
    status = " (INCOMPLETE)" if incomplete else ""
    print(f"dump -> {path}{status}  ({len(merged['places'])} places)")


def load_exclusions() -> set:
    if not EXCLUDE_PATH.exists():
        return set()
    try:
        data = json.loads(EXCLUDE_PATH.read_text())
        if isinstance(data, dict) and "exclusions" in data:
            data = data["exclusions"]
        exclusions = set()
        for e in data:
            if isinstance(e, str):
                exclusions.add(e)
            elif isinstance(e, dict) and "placeId" in e:
                exclusions.add(e["placeId"])
        return exclusions
    except Exception as e:
        print(f"Warning: failed to parse {EXCLUDE_PATH}: {e}")
        return set()


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
    by_model = Counter(r["model"] for r in recs)
    print(f"models: {by_model.get('independent', 0)} independent · {by_model.get('franchise', 0)} franchise")
    cur_work = sum(1 for r in recs if (r.get("cw") or {}).get("tier") == "excellent")
    cur_meeting = sum(1 for r in recs if (r.get("cw") or {}).get("hasMeetingRoom"))
    print(f"curated info: {cur_work} work-friendly · {cur_meeting} meeting rooms")
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
                dupes.append({"discovered": r["name"], "curated": s["name"], "placeId": r["placeId"]})
    print(
        f"discovered within 60 m of a curated shop with an overlapping name "
        f"(candidates for scripts/places_exclude.json): {len(dupes)}"
    )
    for d in dupes:
        print(f"   {d['discovered']} ~ {d['curated']} ({d['placeId']})")

    # Persist QA leads to scratch for actionable review (F7)
    qa_leads_path = ROOT / "scratch" / "curated_qa_leads.json"
    try:
        qa_leads_path.parent.mkdir(parents=True, exist_ok=True)
        qa_leads_path.write_text(json.dumps({
            "unseen_curated_count": len(unseen),
            "unseen_curated_names": unseen,
            "near_dupes_count": len(dupes),
            "near_dupes": dupes
        }, indent=2))
    except Exception:
        pass


def curated_with_coords() -> list:
    data = json.loads(SHOPS_PATH.read_text())
    out = []
    for s in data["shops"]:
        c = data["addr"].get(s.get("addrKey")) or {}
        out.append({**s, "lat": c.get("lat", 0.0), "lng": c.get("lng", 0.0)})
    return out


def month_label(generated_at: str | None) -> str | None:
    """checkedMonth for write_places: the observation date the dump represents,
    not today. Unparseable dates return None (rendered as "unknown") — replaying
    data of unknown age must not claim this month's verification."""
    try:
        return datetime.fromisoformat(generated_at).strftime("%B %Y")
    except (ValueError, TypeError):
        return None


def write_places(recs, generated_at: str) -> None:
    data = {
        "version": 1,
        "checkedMonth": month_label(generated_at) or "unknown",
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
    ap.add_argument(
        "--bbox",
        default="",
        help="custom bbox: south,west,north,east (e.g. 33.25,-84.85,33.71,-84.00)",
    )
    ap.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="allow replaying and writing a dump marked with incomplete: true",
    )
    args = ap.parse_args()

    if args.write and not args.replay:
        sys.exit(
            "--write requires --replay <dump>: audit a live run first, then write what was audited"
        )

    if args.replay:
        dump = json.loads(Path(args.replay).read_text())
        if dump.get("incomplete") and args.write and not args.allow_incomplete:
            sys.exit(
                f"REFUSED: {args.replay} is marked as incomplete. "
                "Writing an incomplete dump could corrupt the public dataset. "
                "Pass --allow-incomplete to override."
            )
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

    try:
        used = ledger.used(SKU_FULL)
    except Exception as e:
        print(
            f"REFUSED: cannot verify this month's usage ({e}). "
            f"No calls made. Ledger: {ledger.default_path()}"
        )
        return 2
    ok, msg = usage_gate(used, 0, args.usage_threshold, args.max_paid_calls)
    if not ok:
        print(msg)
        return 2
    client = Client(load_key(), args.sleep, budget=PaidBudget(args.max_paid_calls))
    if args.bbox:
        s, w, n, e = [float(x.strip()) for x in args.bbox.split(",")]
        bbox = {"south": s, "west": w, "north": n, "east": e}
        print(f"custom crawl bbox: {bbox}")
    else:
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
    incomplete = True
    budget = client.budget
    try:
        raw = fetch_details(client, plan, raw, budget=budget)
        incomplete = False
    except BudgetExceeded as e:
        print(f"STOPPED during pass 2: {e}")
        return 2
    except FatalApiError as e:
        print(f"ABORTED during pass 2: {e}")
        return 2
    except BaseException:
        raise
    finally:
        write_dump(
            raw_path,
            {
                "generatedAt": generated_at,
                "region": REGION,
                "leaves": leaves_out,
                "places": raw,
            },
            incomplete=incomplete,
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
