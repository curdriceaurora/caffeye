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
