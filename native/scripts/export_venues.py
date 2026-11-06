#!/usr/bin/env python3
"""Export existing venue records, preserving provenance and excluding all rating inputs.

This changes the storage format, not the rights associated with source content.
No API calls or dataset refreshes are performed.
"""
import argparse
import hashlib
import json
import math
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = {"Coffee", "Roasters", "Bakery+Cafe", "Tea/Boba", "Dessert Cafe", "Specialty"}
GENERIC = {"cafe", "coffee", "bakery", "tea"}
NAMESPACE = uuid.UUID("4befb3f3-70a8-4c21-a2eb-830d48b593e9")


def tokens(name):
    return {t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) >= 3 and t not in GENERIC}


def valid(record, coordinate):
    lat, lng = coordinate.get("lat"), coordinate.get("lng")
    return (isinstance(record.get("name"), str) and record["name"] and record.get("category") in CATEGORIES
            and type(lat) in (float, int) and type(lng) in (float, int)
            and math.isfinite(lat) and math.isfinite(lng)
            and -90 <= lat <= 90 and -180 <= lng <= 180 and (lat, lng) != (0, 0))


def export(seed, regional):
    accepted = []
    seed_records = []
    seen_places = set()
    seen_ids = set()

    def append(record, coordinate, curated, month):
        place_id = record.get("placeId")
        identity = "google:" + place_id if place_id else "venue:" + "|".join(
            [record.get("addrKey", ""), record["name"], record.get("address", ""), record.get("city", "")])
        venue_id = str(uuid.uuid5(NAMESPACE, identity))
        if venue_id in seen_ids:
            raise ValueError(f"Duplicate venue identity: {record['name']}")
        seen_ids.add(venue_id)
        provenance = {"source": "Caffeye curated seed (Apple-geocoded coordinates; mixed-source operational data)"
                      if curated else "Google Places regional discovery with Caffeye editorial overlays"}
        if month and month != "unknown":
            provenance["verified"] = month
        venue = {
            "id": venue_id, "name": record["name"], "category": record["category"],
            "coordinate": {"latitude": coordinate["lat"], "longitude": coordinate["lng"]},
            "address": record.get("address") or record.get("addr") or "",
            "city": record.get("city") or "", "model": record.get("model") or "independent",
            "provenance": provenance, "curated": curated,
        }
        if place_id:
            venue["providerIDs"] = {"google": place_id}
        if record.get("addrKey"):
            venue.setdefault("providerIDs", {})["caffeyeAddress"] = record["addrKey"]
        mappings = {"county": "county", "neighborhood": "neighborhood", "hours": "hours",
                    "usp": "summary", "loved": "loved", "signature": "signature",
                    "website": "website", "googleUrl": "googleURL", "yelpUrl": "yelpURL", "types": "types"}
        for key, target in mappings.items():
            if record.get(key) is not None:
                venue[target] = record[key]
        if not venue.get("neighborhood"):
            venue["neighborhood"] = seed.get("neighborhoods", {}).get(record.get("addrKey"), record.get("city", "")) if curated else record.get("city", "")
        work = record.get("cw")
        if work and work.get("tier"):
            venue["work"] = {
                "tier": work["tier"], "note": work.get("note") or "",
                "hasMeetingRoom": bool(work.get("hasMeetingRoom")),
            }
            if work.get("meetingRoomNote"):
                venue["work"]["meetingRoomNote"] = work["meetingRoomNote"]
            venue["work"]["provenance"] = {"source": work.get("source") or "Caffeye editorial review"}
            if work.get("verified"):
                venue["work"]["provenance"]["verified"] = work["verified"]
        if record.get("late"):
            venue["late"] = {"tier": record["late"]["tier"], "when": record["late"].get("when") or ""}
        venue["fieldProvenance"] = {"coordinate": {
            "source": "Apple geocoding (curated seed)" if curated else "Google Places place pin"
        }}
        if venue.get("work", {}).get("provenance"):
            venue["fieldProvenance"]["work"] = dict(venue["work"]["provenance"])
        # Coordinate-specific verification dates were not recorded. Do not invent one.
        accepted.append(venue)
        if place_id:
            seen_places.add(place_id)

    for record in seed.get("shops", []):
        coordinate = seed.get("addr", {}).get(record.get("addrKey"), record)
        if valid(record, coordinate):
            append(record, coordinate, True, seed.get("checkedMonth"))
            seed_records.append((record, coordinate))

    for record in regional.get("places", []):
        if not valid(record, record) or record.get("placeId") in seen_places:
            continue
        relisted = any(
            abs(record["lat"] - coordinate["lat"]) <= 0.0006
            and abs(record["lng"] - coordinate["lng"]) <= 0.0006
            and tokens(record["name"]) & tokens(curated["name"])
            for curated, coordinate in seed_records)
        if relisted:
            continue
        append(record, record, False, regional.get("checkedMonth"))

    accepted.sort(key=lambda v: (v["name"].casefold(), v["city"].casefold(), v["id"]))
    snapshot = {"schemaVersion": 1, "region": "Metro Atlanta", "isDemo": False, "venues": accepted}
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    snapshot["revision"] = "venues-no-ratings-" + digest
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=ROOT / "public/shops.json")
    parser.add_argument("--regional", type=Path, default=ROOT / "public/places.json")
    parser.add_argument("--output", type=Path, default=ROOT / "native/Caffeye/Resources/venues.json")
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in export is stale")
    args = parser.parse_args()
    snapshot = export(json.loads(args.seed.read_text()), json.loads(args.regional.read_text()))
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text() != payload:
            raise SystemExit("Native venue export is stale. Run native/scripts/export_venues.py.")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    indie = sum(v["model"] == "independent" for v in snapshot["venues"])
    print(f"{len(snapshot['venues'])} venues ({indie} independent); no ratings, review counts, or rating priors.")


if __name__ == "__main__":
    main()
