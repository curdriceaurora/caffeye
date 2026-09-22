#!/usr/bin/env python3
"""Curation Engine for Caffeye: Enriches discovered listings with qualitative editorial data,
specifically Coworking suitability (cw.tier, cw.note), reservable Meeting Rooms (hasMeetingRoom),
and signature items.

Usage:
    python3 scripts/curate_places.py --audit
        Prints coverage of coworking tiers and meeting rooms across counties.
    python3 scripts/curate_places.py --apply
        Merges scripts/curations.json into public/places.json.
    python3 scripts/curate_places.py --research <url>
        Fetches and scans a venue's website for coworking and meeting room signals.
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES_PATH = ROOT / "public" / "places.json"
SHOPS_PATH = ROOT / "public" / "shops.json"
CURATIONS_PATH = ROOT / "scripts" / "curations.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from refresh_ratings import norm  # noqa: E402
from discover_places import (  # noqa: E402
    classify_category,
    load_curation_defaults,
    stamp_provenance,
)


def load_curations(path=CURATIONS_PATH) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data.get("places", {})


def apply_curation_to_place(place: dict, cur: dict, defaults=None) -> dict:
    """Returns a copy of place updated with curated fields.

    defaults is (defaultVerified, defaultSource) from the curation file's
    top-level metadata; the cw block is stamped with per-record source and
    verification date (per-record values win, unknown stays absent)."""
    if defaults is None:
        defaults = (None, "editorial")
    rec = dict(place)
    if "category" in cur:
        rec["category"] = cur["category"]
    if "cw" in cur:
        rec["cw"] = stamp_provenance(cur["cw"], cur, defaults)
    if "usp" in cur:
        rec["usp"] = cur["usp"]
    if "loved" in cur:
        rec["loved"] = cur["loved"]
    if "signature" in cur:
        rec["signature"] = cur["signature"]
    return rec


def apply_curations(places: list, curations: dict, defaults=None) -> tuple:
    """(updated_places, applied_count). Matches by placeId first, then unambiguous norm(name)+city."""
    # Count how many places share each (name, city) key to detect ambiguity
    place_key_counts = Counter(
        (norm(p.get("name", "")), norm(p.get("city", "")))
        for p in places
    )

    # Overlays are keyed by placeId, but collect every overlay per
    # norm(name)+city: duplicate source keys must NOT silently collapse
    # (last-writer-wins would copy one location's amenities onto another).
    by_name_city: dict = {}
    for pid, c in curations.items():
        key = (norm(c.get("name", "")), norm(c.get("city", "")))
        by_name_city.setdefault(key, []).append((pid, c))
    for key, cands in by_name_city.items():
        if len(cands) > 1:
            dup_ids = ", ".join(pid for pid, _ in cands)
            print(
                f"curate: {len(cands)} overlays share name+city {key[0]!r} in {key[1]!r} "
                f"({dup_ids}); name/city fallback disabled for them — "
                f"only placeId matches apply"
            )

    applied = 0
    updated = []
    for p in places:
        pid = p.get("placeId")
        cur = curations.get(pid)
        if not cur:
            key = (norm(p.get("name", "")), norm(p.get("city", "")))
            cands = by_name_city.get(key, [])
            if len(cands) > 1:
                # Ambiguous on the source side too: even a single remaining
                # destination cannot prove which overlay location it is.
                print(f"curate: ambiguous name+city fallback skipped for {p.get('name')} in {p.get('city')}")
            # If multiple venues exist with this name and city (e.g. multi-unit chains),
            # do not decorate without a placeId or matching address
            elif place_key_counts.get(key, 0) == 1 and len(cands) == 1:
                cur = cands[0][1]
            elif place_key_counts.get(key, 0) > 1 and len(cands) == 1:
                c_cand = cands[0][1]
                if c_cand and c_cand.get("address") and p.get("address"):
                    if norm(c_cand["address"]) in norm(p["address"]) or norm(p["address"]) in norm(c_cand["address"]):
                        cur = c_cand
                if not cur:
                    print(f"curate: ambiguous name+city fallback skipped for {p.get('name')} in {p.get('city')}")

        if cur:
            updated.append(apply_curation_to_place(p, cur, defaults))
            applied += 1
        else:
            updated.append(p)

    return updated, applied


def classify_specialty(places: list) -> tuple:
    """Separates Roasters from cultural and concept venues classified as Specialty.

    Delegates to discover_places.classify_category (curation path: stored
    category + name + types), preserving its guards: Bakery+Cafe, Dessert
    Cafe, and Tea/Boba move only on explicit roastery matches or concept
    types — never on loose specialty-name patterns.
    """
    updated = []
    upgraded = 0
    for p in places:
        rec = dict(p)
        current_cat = rec.get("category")
        new_cat = classify_category(
            rec.get("name", ""),
            current_cat=current_cat,
            types=rec.get("types"),
        )
        if new_cat != current_cat:
            rec["category"] = new_cat
            upgraded += 1
        updated.append(rec)
    return updated, upgraded


def audit(places: list, shops: list = None) -> dict:
    if shops:
        all_venues = list(shops)
        seen_pids = {s["placeId"] for s in shops if s.get("placeId")}
        for p in places:
            pid = p.get("placeId")
            if pid and pid in seen_pids:
                continue
            # Guard against relisted duplicate of a curated shop (<60m and shared non-generic name token)
            is_dupe = False
            p_lat, p_lng = p.get("lat"), p.get("lng")
            p_name = p.get("name", "")
            if p_lat and p_lng:
                p_tokens = [
                    t
                    for t in re.split(r"[^a-z0-9]+", p_name.lower())
                    if len(t) >= 3 and t not in ("cafe", "coffee", "bakery", "tea")
                ]
                for s in shops:
                    s_lat, s_lng = s.get("lat"), s.get("lng")
                    if not s_lat or not s_lng:
                        continue
                    if (
                        abs(p_lat - s_lat) <= 0.0006
                        and abs(p_lng - s_lng) <= 0.0006
                    ):
                        s_name = s.get("name", "")
                        s_tokens = [
                            t
                            for t in re.split(r"[^a-z0-9]+", s_name.lower())
                            if len(t) >= 3
                            and t not in ("cafe", "coffee", "bakery", "tea")
                        ]
                        if any(t in s_tokens for t in p_tokens):
                            is_dupe = True
                            break
            if not is_dupe:
                if pid:
                    seen_pids.add(pid)
                all_venues.append(p)
    else:
        all_venues = list(places)

    by_county = Counter()
    work_by_county = Counter()
    meeting_by_county = Counter()
    specialty_by_county = Counter()
    tier_counts = Counter()

    for v in all_venues:
        county = v.get("county") or "Unknown"
        by_county[county] += 1
        if v.get("category") == "Specialty":
            specialty_by_county[county] += 1
        cw = v.get("cw")
        if cw and isinstance(cw, dict):
            tier = cw.get("tier")
            if tier:
                tier_counts[tier] += 1
            if tier == "excellent":
                work_by_county[county] += 1
            if cw.get("hasMeetingRoom"):
                meeting_by_county[county] += 1

    return {
        "total_venues": len(all_venues),
        "counties": sorted(by_county.keys()),
        "by_county": dict(by_county),
        "work_by_county": dict(work_by_county),
        "meeting_by_county": dict(meeting_by_county),
        "specialty_by_county": dict(specialty_by_county),
        "tier_counts": dict(tier_counts),
        "total_work_friendly": sum(work_by_county.values()),
        "total_meeting_rooms": sum(meeting_by_county.values()),
        "total_specialty": sum(specialty_by_county.values()),
    }


MEETING_PATTERNS = [
    re.compile(r"\b(private\s+)?(meeting|conference|board|study|seminar)\s*(room|space|hall)\b", re.I),
    re.compile(r"\b(reservable|reserve|rent|book)\s+(a\s+)?(room|space|table)\b", re.I),
    re.compile(r"\bprivate\s+events?\b", re.I),
    re.compile(r"\bgroup\s+(meetings?|study|gatherings?)\b", re.I),
]

COWORKING_PATTERNS = [
    re.compile(r"\b(fast\s+)?wi[\s-]?fi\b", re.I),
    re.compile(r"\b(power\s+)?outlets?\b", re.I),
    re.compile(r"\b(co[\s-]?work|co[\s-]?working|work\s+friendly|remote\s+work)\b", re.I),
    re.compile(r"\b(study|studying|focus|laptop)\b", re.I),
    re.compile(r"\b(community\s+tables?|spacious\s+seating|large\s+tables?)\b", re.I),
]


def extract_signals_from_text(text: str) -> dict:
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)

    meeting_hits = []
    for pat in MEETING_PATTERNS:
        matches = pat.findall(clean)
        if matches:
            meeting_hits.extend([" ".join(m) if isinstance(m, tuple) else m for m in matches])

    cowork_hits = []
    for pat in COWORKING_PATTERNS:
        matches = pat.findall(clean)
        if matches:
            cowork_hits.extend([" ".join(m) if isinstance(m, tuple) else m for m in matches])

    return {
        "meeting_signals": list(set(meeting_hits)),
        "coworking_signals": list(set(cowork_hits)),
        "likely_has_meeting_room": len(meeting_hits) > 0,
        "likely_work_friendly": len(cowork_hits) >= 2,
    }


def research_website(url: str, timeout: float = 6.0) -> dict:
    if not url.startswith("http"):
        url = "https://" + url
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            if content_type and "text" not in content_type and "html" not in content_type:
                return {"url": url, "ok": False, "error": f"non-html content-type: {content_type}"}
            content = resp.read(1_000_000).decode("utf-8", errors="ignore")
        return {"url": url, "ok": True, **extract_signals_from_text(content)}
    except Exception as e:
        return {"url": url, "ok": False, "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audit", action="store_true", help="Print coworking, meeting room, and specialty coverage audit")
    parser.add_argument("--apply", action="store_true", help="Merge curations and classify roasters and specialty in public/places.json")
    parser.add_argument("--classify-specialty", action="store_true", help="Reclassify roasters and specialty venues in public/places.json")
    parser.add_argument("--research", type=str, default="", help="Fetch and analyze URL for signals")
    args = parser.parse_args()

    curations = load_curations()
    curation_defaults = load_curation_defaults()

    if args.research:
        res = research_website(args.research)
        print(json.dumps(res, indent=2))
        return 0

    if args.audit:
        places_data = json.loads(PLACES_PATH.read_text())
        shops_data = json.loads(SHOPS_PATH.read_text())
        shops = shops_data.get("shops", [])
        addr = shops_data.get("addr", {})
        for s in shops:
            if "lat" not in s and s.get("addrKey") in addr:
                s["lat"] = addr[s["addrKey"]].get("lat")
                s["lng"] = addr[s["addrKey"]].get("lng")
        res = audit(places_data["places"], shops)
        print("=== CAFFEYE CURATION AUDIT ===")
        print(f"Total Venues: {res['total_venues']}")
        print(f"Specialty Venues: {res['total_specialty']}")
        print(f"Work-Friendly Venues: {res['total_work_friendly']}")
        print(f"Meeting Room Venues: {res['total_meeting_rooms']}")
        print(f"Tiers: {res['tier_counts']}")
        print("\nBreakdown by County:")
        for c in res["counties"]:
            tot = res["by_county"].get(c, 0)
            spec = res["specialty_by_county"].get(c, 0)
            wf = res["work_by_county"].get(c, 0)
            mr = res["meeting_by_county"].get(c, 0)
            print(f"  {c:10s}: {tot:3d} venues | {spec:2d} specialty | {wf:2d} work-friendly | {mr:2d} meeting rooms")
        return 0

    if args.apply or args.classify_specialty:
        places_data = json.loads(PLACES_PATH.read_text())
        places = places_data["places"]
        cur_count = 0
        # Heuristics first, editorial last: explicit curation overlays must
        # win over classifier guesses (e.g. a concept-cafe overlay pinning
        # Specialty must survive a tea-name match).
        places, spec_count = classify_specialty(places)
        print(f"Reclassified {spec_count} venues as Roasters or Specialty")
        if args.apply:
            places, cur_count = apply_curations(places, curations, curation_defaults)
            print(f"Applied {cur_count} curations from {CURATIONS_PATH.name}")
        places_data["places"] = places
        PLACES_PATH.write_text(json.dumps(places_data, indent=1, ensure_ascii=False) + "\n")
        print(f"Saved -> {PLACES_PATH} ({PLACES_PATH.stat().st_size // 1024} KB)")

        # Show audit after apply
        shops_data = json.loads(SHOPS_PATH.read_text())
        shops = shops_data.get("shops", [])
        addr = shops_data.get("addr", {})
        for s in shops:
            if "lat" not in s and s.get("addrKey") in addr:
                s["lat"] = addr[s["addrKey"]].get("lat")
                s["lng"] = addr[s["addrKey"]].get("lng")
        res = audit(places, shops)
        print("\nPost-apply audit:")
        for c in res["counties"]:
            tot = res["by_county"].get(c, 0)
            spec = res["specialty_by_county"].get(c, 0)
            wf = res["work_by_county"].get(c, 0)
            mr = res["meeting_by_county"].get(c, 0)
            print(f"  {c:10s}: {tot:3d} venues | {spec:2d} specialty | {wf:2d} work-friendly | {mr:2d} meeting rooms")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
