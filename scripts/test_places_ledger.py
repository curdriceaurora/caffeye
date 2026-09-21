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


if __name__ == "__main__":
    unittest.main()
