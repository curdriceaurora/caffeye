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
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: no flock; atomic replace still applies
    fcntl = None

SKUS = ("text_search_enterprise", "text_search_ids_only", "place_details_enterprise")


class LedgerError(Exception):
    """The ledger file exists but is unusable. Fail closed: fix or remove it."""


def default_path() -> Path:
    env = os.environ.get("CAFFEYE_LEDGER")
    return (
        Path(env) if env else Path.home() / ".config" / "caffeye" / "places_usage.json"
    )


def month_key(today=None) -> str:
    return (today or date.today()).strftime("%Y-%m")


def _corrupt(path: Path, detail: str) -> LedgerError:
    """Back up an unreadable ledger, then fail closed (never report zero)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        backup.write_bytes(path.read_bytes())
    except OSError:
        backup = None
    where = f" (raw copy kept at {backup})" if backup else " (could not back up the file)"
    return LedgerError(
        f"ledger {path} is unreadable ({detail}){where}. "
        f"Fix or delete it before running paid passes. Refusing to report 0 usage."
    )


def load(path=None) -> dict:
    p = Path(path) if path else default_path()
    if not p.exists():
        return {"months": {}, "notes": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise _corrupt(p, f"invalid JSON: {e}") from e
    except OSError as e:
        raise _corrupt(p, f"unreadable: {e}") from e
    if not isinstance(data, dict) or not isinstance(
        data.get("months", {}), dict
    ):
        raise _corrupt(p, "unexpected shape (expected {\"months\": {...}})")
    data.setdefault("months", {})
    data.setdefault("notes", [])
    return data


def _save(data: dict, path=None) -> None:
    """Atomic replace (tmp file in the same directory + os.replace)."""
    p = Path(path) if path else default_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=1) + "\n")
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _locked(path: Path):
    """Cross-process exclusive lock for read-modify-write (best effort)."""
    class _Null:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    if fcntl is None:
        return _Null()
    class _Flock:
        def __enter__(self):
            self.f = open(path, "a+b")
            fcntl.flock(self.f.fileno(), fcntl.LOCK_EX)
            return self
        def __exit__(self, *a):
            try:
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
            finally:
                self.f.close()
            return False
    return _Flock()


def _check(sku: str) -> None:
    if sku not in SKUS:
        raise ValueError(f"unknown SKU {sku!r}; expected one of {SKUS}")


def used(sku: str, path=None, today=None) -> int:
    _check(sku)
    return int(load(path)["months"].get(month_key(today), {}).get(sku, 0))


def record(sku: str, n: int = 1, path=None, today=None) -> int:
    """Add n calls for this month and return the new count."""
    _check(sku)
    p = Path(path) if path else default_path()
    with _locked(p.with_name(p.name + ".lock")):
        data = load(path)
        month = data["months"].setdefault(month_key(today), {})
        month[sku] = int(month.get(sku, 0)) + int(n)
        _save(data, path)
        return month[sku]


def seed(sku: str, n: int, basis: str, path=None, today=None) -> None:
    """Set this month's count outright (for calls made before the ledger existed)."""
    _check(sku)
    p = Path(path) if path else default_path()
    with _locked(p.with_name(p.name + ".lock")):
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
    try:
        data = load()
    except LedgerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
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
