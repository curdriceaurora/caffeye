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


def load_curations(path=CURATIONS_PATH) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data.get("places", {})


def apply_curation_to_place(place: dict, cur: dict) -> dict:
    """Returns a copy of place updated with curated fields."""
    rec = dict(place)
    if "cw" in cur:
        rec["cw"] = cur["cw"]
    if "usp" in cur:
        rec["usp"] = cur["usp"]
    if "loved" in cur:
        rec["loved"] = cur["loved"]
    if "signature" in cur:
        rec["signature"] = cur["signature"]
    return rec


def apply_curations(places: list, curations: dict) -> tuple:
    """(updated_places, applied_count). Matches by placeId first, then unambiguous norm(name)+city."""
    # Count how many places share each (name, city) key to detect ambiguity
    place_key_counts = Counter(
        (norm(p.get("name", "")), norm(p.get("city", "")))
        for p in places
    )

    by_name_city = {}
    for pid, c in curations.items():
        key = (norm(c.get("name", "")), norm(c.get("city", "")))
        by_name_city[key] = c

    applied = 0
    updated = []
    for p in places:
        pid = p.get("placeId")
        cur = curations.get(pid)
        if not cur:
            key = (norm(p.get("name", "")), norm(p.get("city", "")))
            # If multiple venues exist with this name and city (e.g. multi-unit chains),
            # do not decorate without a placeId or matching address
            if place_key_counts.get(key, 0) == 1:
                cur = by_name_city.get(key)
            elif place_key_counts.get(key, 0) > 1 and key in by_name_city:
                c_cand = by_name_city.get(key)
                if c_cand and c_cand.get("address") and p.get("address"):
                    if norm(c_cand["address"]) in norm(p["address"]) or norm(p["address"]) in norm(c_cand["address"]):
                        cur = c_cand
                if not cur:
                    print(f"curate: ambiguous name+city fallback skipped for {p.get('name')} in {p.get('city')}")

        if cur:
            updated.append(apply_curation_to_place(p, cur))
            applied += 1
        else:
            updated.append(p)

    return updated, applied


def audit(places: list, shops: list = None) -> dict:
    all_venues = list(places) + (list(shops) if shops else [])
    by_county = Counter()
    work_by_county = Counter()
    meeting_by_county = Counter()
    tier_counts = Counter()

    for v in all_venues:
        county = v.get("county") or "Unknown"
        by_county[county] += 1
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
        "tier_counts": dict(tier_counts),
        "total_work_friendly": sum(work_by_county.values()),
        "total_meeting_rooms": sum(meeting_by_county.values()),
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
    parser.add_argument("--audit", action="store_true", help="Print coworking and meeting room coverage audit")
    parser.add_argument("--apply", action="store_true", help="Merge curations into public/places.json")
    parser.add_argument("--research", type=str, default="", help="Fetch and analyze URL for signals")
    args = parser.parse_args()

    curations = load_curations()

    if args.research:
        res = research_website(args.research)
        print(json.dumps(res, indent=2))
        return 0

    if args.audit:
        places_data = json.loads(PLACES_PATH.read_text())
        shops_data = json.loads(SHOPS_PATH.read_text())
        res = audit(places_data["places"], shops_data.get("shops", []))
        print("=== CAFFEYE CURATION AUDIT ===")
        print(f"Total Venues: {res['total_venues']}")
        print(f"Work-Friendly Venues: {res['total_work_friendly']}")
        print(f"Meeting Room Venues: {res['total_meeting_rooms']}")
        print(f"Tiers: {res['tier_counts']}")
        print("\nBreakdown by County:")
        for c in res["counties"]:
            tot = res["by_county"].get(c, 0)
            wf = res["work_by_county"].get(c, 0)
            mr = res["meeting_by_county"].get(c, 0)
            print(f"  {c:10s}: {tot:3d} venues | {wf:2d} work-friendly | {mr:2d} meeting rooms")
        return 0

    if args.apply:
        places_data = json.loads(PLACES_PATH.read_text())
        updated_places, count = apply_curations(places_data["places"], curations)
        places_data["places"] = updated_places
        PLACES_PATH.write_text(json.dumps(places_data, indent=1, ensure_ascii=False) + "\n")
        print(f"Applied {count} curations from {CURATIONS_PATH.name} -> {PLACES_PATH} ({PLACES_PATH.stat().st_size // 1024} KB)")
        # Show audit after apply
        shops_data = json.loads(SHOPS_PATH.read_text())
        res = audit(updated_places, shops_data.get("shops", []))
        print("\nPost-apply audit:")
        for c in res["counties"]:
            tot = res["by_county"].get(c, 0)
            wf = res["work_by_county"].get(c, 0)
            mr = res["meeting_by_county"].get(c, 0)
            print(f"  {c:10s}: {tot:3d} venues | {wf:2d} work-friendly | {mr:2d} meeting rooms")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
