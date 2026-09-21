import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curate_places as CP


class CuratePlacesTests(unittest.TestCase):
    def test_load_curations(self):
        curations = CP.load_curations()
        self.assertIsInstance(curations, dict)
        self.assertGreaterEqual(len(curations), 20)
        # Check TradeWind
        tw = curations.get("ChIJG1KP8qDq9YgReCfFZvohgwo")
        self.assertIsNotNone(tw)
        self.assertEqual(tw["cw"]["tier"], "excellent")
        self.assertTrue(tw["cw"]["hasMeetingRoom"])
        self.assertTrue("Chart Room" in tw["cw"]["meetingRoomNote"])

    def test_apply_curations_by_place_id(self):
        places = [
            {"placeId": "p1", "name": "Dummy Cafe", "city": "Roswell", "county": "Fulton"},
            {"placeId": "p2", "name": "Other Cafe", "city": "Duluth", "county": "Gwinnett"}
        ]
        curations = {
            "p1": {
                "name": "Dummy Cafe",
                "cw": {"tier": "excellent", "hasMeetingRoom": True, "note": "Great work vibe"},
                "usp": "Best dummy cafe",
                "loved": ["a", "b", "c"],
                "signature": "Sig drink"
            }
        }
        updated, count = CP.apply_curations(places, curations)
        self.assertEqual(count, 1)
        p1 = [p for p in updated if p["placeId"] == "p1"][0]
        self.assertEqual(p1["cw"]["tier"], "excellent")
        self.assertTrue(p1["cw"]["hasMeetingRoom"])
        self.assertEqual(p1["usp"], "Best dummy cafe")
        self.assertEqual(p1["signature"], "Sig drink")

        p2 = [p for p in updated if p["placeId"] == "p2"][0]
        self.assertNotIn("cw", p2)

    def test_apply_curations_by_name_city_fallback(self):
        places = [
            {"placeId": "different_id", "name": "TradeWind Coffee Co.", "city": "Dacula", "county": "Gwinnett"}
        ]
        curations = {
            "orig_id": {
                "name": "TradeWind Coffee Co.",
                "city": "Dacula",
                "cw": {"tier": "excellent", "hasMeetingRoom": True}
            }
        }
        updated, count = CP.apply_curations(places, curations)
        self.assertEqual(count, 1)
        self.assertEqual(updated[0]["cw"]["tier"], "excellent")
        self.assertTrue(updated[0]["cw"]["hasMeetingRoom"])

    def test_ambiguous_name_city_fallback_skipped(self):
        # Two Starbucks in Marietta with no placeId match should not be decorated
        places = [
            {"placeId": "p_marietta_1", "name": "Starbucks", "city": "Marietta", "address": "100 Main St"},
            {"placeId": "p_marietta_2", "name": "Starbucks", "city": "Marietta", "address": "200 South Rd"},
        ]
        curations = {
            "unmatched_pid": {
                "name": "Starbucks",
                "city": "Marietta",
                "cw": {"tier": "excellent", "hasMeetingRoom": True}
            }
        }
        updated, count = CP.apply_curations(places, curations)
        self.assertEqual(count, 0)
        self.assertNotIn("cw", updated[0])
        self.assertNotIn("cw", updated[1])

    def test_audit_computation(self):
        places = [
            {"name": "P1", "county": "Fulton", "cw": {"tier": "excellent", "hasMeetingRoom": True}},
            {"name": "P2", "county": "Fulton", "cw": {"tier": "good", "hasMeetingRoom": False}},
            {"name": "P3", "county": "Forsyth", "cw": {"tier": "excellent", "hasMeetingRoom": False}},
            {"name": "P4", "county": "Forsyth"},
        ]
        res = CP.audit(places)
        self.assertEqual(res["total_venues"], 4)
        self.assertEqual(res["total_work_friendly"], 2)
        self.assertEqual(res["total_meeting_rooms"], 1)
        self.assertEqual(res["work_by_county"]["Fulton"], 1)
        self.assertEqual(res["work_by_county"]["Forsyth"], 1)
        self.assertEqual(res["meeting_by_county"]["Fulton"], 1)
        self.assertEqual(res["meeting_by_county"].get("Forsyth", 0), 0)

    def test_audit_deduplicates_overlapping_shops(self):
        places = [
            {"placeId": "shared_1", "name": "Shared Cafe", "county": "Gwinnett"},
            {"placeId": "discovered_only", "name": "Discovered Cafe", "county": "Gwinnett"},
        ]
        shops = [
            {"placeId": "shared_1", "name": "Shared Cafe", "county": "Gwinnett", "cw": {"tier": "excellent"}},
            {"placeId": "curated_only", "name": "Curated Cafe", "county": "Gwinnett"},
        ]
        res = CP.audit(places, shops)
        self.assertEqual(res["total_venues"], 3)
        self.assertEqual(res["total_work_friendly"], 1)

    def test_audit_proximity_deduplication_relisted_shop(self):
        # Base curated shop: "Octane Coffee Bar" at (33.7750, -84.4100)
        shops = [
            {"placeId": "curated_octane", "name": "Octane Coffee Bar", "county": "Fulton", "lat": 33.7750, "lng": -84.4100}
        ]

        # Case 1: Relisted discovered shop under different placeId, co-located (< 60m, diff <= 0.0006)
        # sharing distinctive name token "octane" -> suppressed as duplicate
        relisted_places = [
            {"placeId": "new_octane_pid", "name": "Octane Coffee", "county": "Fulton", "lat": 33.7752, "lng": -84.4102}
        ]
        res1 = CP.audit(relisted_places, shops)
        self.assertEqual(res1["total_venues"], 1)

        # Case 2: Same name token but distant location (> 0.0006) -> not a relist, both kept
        distant_places = [
            {"placeId": "distant_octane", "name": "Octane Coffee", "county": "Fulton", "lat": 33.8500, "lng": -84.3500}
        ]
        res2 = CP.audit(distant_places, shops)
        self.assertEqual(res2["total_venues"], 2)

        # Case 3: Co-located (< 60m) but completely distinct name with no shared non-generic token -> both kept
        colocated_diff_places = [
            {"placeId": "different_shop", "name": "Completely Different Bakery", "county": "Fulton", "lat": 33.7751, "lng": -84.4101}
        ]
        res3 = CP.audit(colocated_diff_places, shops)
        self.assertEqual(res3["total_venues"], 2)

    def test_extract_signals_from_text(self):
        html_sample = """
        <html>
            <body>
                <h1>Welcome to Work Haven Cafe</h1>
                <p>We offer fast Wi-Fi and power outlets at all community tables. Great for laptop study!</p>
                <div>Rent our private conference room for group meetings and presentations.</div>
            </body>
        </html>
        """
        signals = CP.extract_signals_from_text(html_sample)
        self.assertTrue(signals["likely_has_meeting_room"])
        self.assertTrue(signals["likely_work_friendly"])
        self.assertTrue(len(signals["meeting_signals"]) > 0)
        self.assertTrue(len(signals["coworking_signals"]) >= 2)


if __name__ == "__main__":
    unittest.main()
