import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import places_ledger as L


class LedgerTests(unittest.TestCase):
    def test_missing_file_reports_blank(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "nope.json"
            self.assertEqual(L.load(str(p)), {"months": {}, "notes": []})
            self.assertEqual(L.used("text_search_enterprise", path=str(p)), 0)

    def test_corrupt_file_fails_closed(self):
        """Bug 5: a truncated ledger must raise, never silently report 0."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places_usage.json"
            p.write_text('{"months": {"2026-09": {"text_sea')
            with self.assertRaises(L.LedgerError):
                L.load(str(p))
            with self.assertRaises(L.LedgerError):
                L.used("text_search_enterprise", path=str(p))
            with self.assertRaises(L.LedgerError):
                L.record("text_search_enterprise", path=str(p))
            # Raw copy kept for forensics
            self.assertEqual(len(list(Path(d).glob("*.corrupt-*"))), 1)

    def test_wrong_shape_fails_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places_usage.json"
            p.write_text('[1, 2, 3]')
            with self.assertRaises(L.LedgerError):
                L.load(str(p))

    def test_record_round_trip_and_no_tmp_leftovers(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places_usage.json"
            self.assertEqual(L.record("text_search_enterprise", 3, path=str(p)), 3)
            self.assertEqual(L.record("text_search_enterprise", 2, path=str(p)), 5)
            self.assertEqual(L.used("text_search_enterprise", path=str(p)), 5)
            leftovers = [x for x in Path(d).iterdir() if x.suffix == ".tmp"]
            self.assertEqual(leftovers, [])

    def test_seed_round_trip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places_usage.json"
            L.seed("text_search_enterprise", 151, "backfill", path=str(p))
            self.assertEqual(L.used("text_search_enterprise", path=str(p)), 151)

    def test_seed_negative_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places_usage.json"
            with self.assertRaises(ValueError):
                L.seed("text_search_enterprise", -1, "oops", path=str(p))

    def test_record_non_positive_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places_usage.json"
            with self.assertRaises(ValueError):
                L.record("text_search_enterprise", 0, path=str(p))
            with self.assertRaises(ValueError):
                L.record("text_search_enterprise", -1, path=str(p))

    def test_first_run_in_fresh_directory(self):
        """Gap 3: lock file must not open before its parent dir exists."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "brand" / "new" / "places_usage.json"
            self.assertEqual(L.record("text_search_enterprise", path=str(p)), 1)
            self.assertEqual(L.reserve("text_search_enterprise", 5, path=str(p)), 2)
            L.seed("text_search_ids_only", 7, "fresh", path=str(p))
            self.assertEqual(L.used("text_search_ids_only", path=str(p)), 7)

    def test_invalid_counts_rejected(self):
        """Gap 4: -5, strings, floats, bools, and misshapen months fail closed."""
        import tempfile
        bad_months = [
            {"2026-09": {"text_search_enterprise": -5}},
            {"2026-09": {"text_search_enterprise": "3"}},
            {"2026-09": {"text_search_enterprise": 2.5}},
            {"2026-09": {"text_search_enterprise": True}},
            {"2026-09": ["not", "a", "dict"]},
        ]
        with tempfile.TemporaryDirectory() as d:
            for i, months in enumerate(bad_months):
                p = Path(d) / f"bad{i}.json"
                p.write_text(json.dumps({"months": months, "notes": []}))
                with self.assertRaises(L.LedgerError, msg=f"case {i}: {months}"):
                    L.load(str(p))
            p = Path(d) / "badnotes.json"
            p.write_text(json.dumps({"months": {}, "notes": "oops"}))
            with self.assertRaises(L.LedgerError):
                L.load(str(p))

    def test_reserve_enforces_cap(self):
        """Gap 2 (single process): the cap+1st reservation raises, usage frozen."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places_usage.json"
            self.assertEqual(L.reserve("text_search_enterprise", 1, path=str(p)), 1)
            with self.assertRaises(L.CapExceeded):
                L.reserve("text_search_enterprise", 1, path=str(p))
            self.assertEqual(L.used("text_search_enterprise", path=str(p)), 1)

    def test_concurrent_reserves_cannot_overshoot(self):
        """Gap 2: N threads racing a cap of 1 produce exactly one winner."""
        import tempfile
        import threading
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places_usage.json"
            wins, losses = [], []
            barrier = threading.Barrier(4)

            def racer():
                try:
                    barrier.wait(timeout=10)
                    L.reserve("text_search_enterprise", 1, path=str(p))
                    wins.append(1)
                except L.CapExceeded:
                    losses.append(1)

            threads = [threading.Thread(target=racer) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            self.assertEqual(len(wins), 1)
            self.assertEqual(len(losses), 3)
            self.assertEqual(L.used("text_search_enterprise", path=str(p)), 1)


if __name__ == "__main__":
    unittest.main()
