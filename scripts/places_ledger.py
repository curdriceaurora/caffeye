#!/usr/bin/env python3
"""Monthly per-SKU ledger of Google Places API calls made by this repo's scripts.

Google exposes no per-key monthly SKU counter to a script, so we count our own
calls. The file lives beside the API key (not in a worktree) so every checkout
shares it:  ~/.config/caffeye/places_usage.json   (override: $CAFFEYE_LEDGER)

    python3 scripts/places_ledger.py                       # print this month's counts
    python3 scripts/places_ledger.py --seed SKU N "basis"  # set this month's count (once)

Layout: {"months": {"2026-09": {"text_search_enterprise": 151, ...}}, "notes": [...]}
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

SKUS = ("text_search_enterprise", "text_search_ids_only", "place_details_enterprise")


def default_path() -> Path:
    env = os.environ.get("CAFFEYE_LEDGER")
    return (
        Path(env) if env else Path.home() / ".config" / "caffeye" / "places_usage.json"
    )


def month_key(today=None) -> str:
    return (today or date.today()).strftime("%Y-%m")


def load(path=None) -> dict:
    p = Path(path) if path else default_path()
    if not p.exists():
        return {"months": {}, "notes": []}
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return {"months": {}, "notes": []}
    data.setdefault("months", {})
    data.setdefault("notes", [])
    return data


def _save(data: dict, path=None) -> None:
    p = Path(path) if path else default_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1) + "\n")


def _check(sku: str) -> None:
    if sku not in SKUS:
        raise ValueError(f"unknown SKU {sku!r}; expected one of {SKUS}")


def used(sku: str, path=None, today=None) -> int:
    _check(sku)
    return int(load(path)["months"].get(month_key(today), {}).get(sku, 0))


def record(sku: str, n: int = 1, path=None, today=None) -> int:
    """Add n calls for this month and return the new count."""
    _check(sku)
    data = load(path)
    month = data["months"].setdefault(month_key(today), {})
    month[sku] = int(month.get(sku, 0)) + int(n)
    _save(data, path)
    return month[sku]


def seed(sku: str, n: int, basis: str, path=None, today=None) -> None:
    """Set this month's count outright (for calls made before the ledger existed)."""
    _check(sku)
    data = load(path)
    data["months"].setdefault(month_key(today), {})[sku] = int(n)
    data["notes"].append(f"{month_key(today)} {sku} seeded at {n}: {basis}")
    _save(data, path)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--seed", nargs=3, metavar=("SKU", "N", "BASIS"))
    args = ap.parse_args()
    if args.seed:
        sku, n, basis = args.seed
        seed(sku, int(n), basis)
    data = load()
    print(f"ledger: {default_path()}")
    print(
        json.dumps(
            {"month": month_key(), **data["months"].get(month_key(), {})}, indent=1
        )
    )
    for note in data["notes"]:
        print("note:", note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
