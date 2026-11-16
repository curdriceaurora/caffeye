#!/usr/bin/env python3
"""Inventory source metadata; this report does not grant data permissions."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def audit(path):
    raw = Path(path).read_bytes()
    snapshot = json.loads(raw)
    records = snapshot["venues"]
    sources = Counter(v["provenance"]["source"] for v in records)
    fields = {}
    for venue in records:
        for field in venue:
            if field in {"id", "provenance", "fieldProvenance"}:
                continue
            provenance = venue.get("fieldProvenance", {}).get(field, venue["provenance"])
            fields.setdefault(field, Counter())[provenance["source"]] += 1
    return {
        "datasetSHA256": hashlib.sha256(raw).hexdigest(), "revision": snapshot["revision"],
        "venues": len(records), "isDemo": snapshot["isDemo"], "recordSources": dict(sources),
        "fieldSources": {k: dict(v) for k, v in sorted(fields.items())},
        "permissionStatus": "Not established by this inventory; obtain source-specific review evidence.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.snapshot), indent=2, sort_keys=True))
