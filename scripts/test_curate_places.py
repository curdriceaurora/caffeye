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

    def test_duplicate_source_overlays_do_not_cross_contaminate(self):
        """Bug 6: two overlays sharing norm(name)+city must not collapse —
        a relisted venue gets no fallback amenities from the other address."""
        places = [
            {"placeId": "new_relist", "name": "Brand Cafe", "city": "Roswell",
             "address": "999 New St"},
        ]
        curations = {
            "pid_a": {
                "name": "Brand Cafe", "city": "Roswell", "address": "100 Main St",
                "cw": {"tier": "excellent", "hasMeetingRoom": True},
            },
            "pid_b": {
                "name": "Brand Cafe", "city": "Roswell", "address": "200 South Rd",
                "cw": {"tier": "good", "hasMeetingRoom": False},
            },
        }
        updated, count = CP.apply_curations(places, curations)
        self.assertEqual(count, 0)
        self.assertNotIn("cw", updated[0])

    def test_duplicate_source_overlays_still_match_by_place_id(self):
        """placeId matches keep working even with duplicate name+city sources."""
        places = [
            {"placeId": "pid_b", "name": "Brand Cafe", "city": "Roswell",
             "address": "200 South Rd"},
        ]
        curations = {
            "pid_a": {
                "name": "Brand Cafe", "city": "Roswell", "address": "100 Main St",
                "cw": {"tier": "excellent", "hasMeetingRoom": True},
            },
            "pid_b": {
                "name": "Brand Cafe", "city": "Roswell", "address": "200 South Rd",
                "cw": {"tier": "good", "hasMeetingRoom": False},
            },
        }
        updated, count = CP.apply_curations(places, curations)
        self.assertEqual(count, 1)
        self.assertFalse(updated[0]["cw"]["hasMeetingRoom"])
        self.assertEqual(updated[0]["cw"]["tier"], "good")

    def test_classify_specialty(self):
        places = [
            {"placeId": "p1", "name": "Atomic Roastery & Lab", "category": "Coffee"},
            {"placeId": "p2", "name": "Qamaria Yemeni Coffee Co.", "category": "Coffee"},
            {"placeId": "p3", "name": "Java Cats Cafe", "category": "Coffee"},
            {"placeId": "p4", "name": "Boba Time", "category": "Tea/Boba"},
            {"placeId": "p5", "name": "Standard Cafe", "category": "Coffee"},
        ]
        classified, count = CP.classify_specialty(places)
        self.assertEqual(count, 3)
        p_map = {p["placeId"]: p["category"] for p in classified}
        self.assertEqual(p_map["p1"], "Roasters")
        self.assertEqual(p_map["p2"], "Specialty")
        self.assertEqual(p_map["p3"], "Specialty")
        self.assertEqual(p_map["p4"], "Tea/Boba")
        self.assertEqual(p_map["p5"], "Coffee")

    def test_existing_specialty_roasters_migrate_and_stay_classified(self):
        places = [
            {"name": "Radio Roasters Coffee", "category": "Specialty"},
            {"name": "PERC", "category": "Specialty"},
            {"name": "Qamaria Yemeni Coffee", "category": "Specialty"},
            {"name": "Java Cats Cafe", "category": "Specialty", "types": ["cat_cafe"]},
        ]
        classified, count = CP.classify_specialty(places)
        self.assertEqual(count, 2)
        self.assertEqual([p["category"] for p in classified],
                         ["Roasters", "Roasters", "Specialty", "Specialty"])
        self.assertEqual(CP.classify_specialty(classified), (classified, 0))
        self.assertTrue(all(p["category"] == "Specialty" for p in places))

    def test_bakery_and_tea_guards(self):
        # Bakeries, Dessert Cafes, and Tea/Boba must NOT be hijacked by generic specialty name patterns
        places = [
            {"placeId": "b1", "name": "Sunday Roasters Bakery", "category": "Bakery+Cafe"},
            {"placeId": "d1", "name": "Turkish Delight Dessert Shop", "category": "Dessert Cafe"},
            {"placeId": "t1", "name": "Yemeni Boba Tea House", "category": "Tea/Boba"},
            # But explicit roasteries in ROASTERY_NAMES DO upgrade even if typed bakery
            {"placeId": "r1", "name": "East Pole Coffee Co Bakery", "category": "Bakery+Cafe"},
        ]
        classified, count = CP.classify_specialty(places)
        self.assertEqual(count, 1)
        p_map = {p["placeId"]: p["category"] for p in classified}
        self.assertEqual(p_map["b1"], "Bakery+Cafe")
        self.assertEqual(p_map["d1"], "Dessert Cafe")
        self.assertEqual(p_map["t1"], "Tea/Boba")
        self.assertEqual(p_map["r1"], "Roasters")

    def test_provenance_inherited_from_file_defaults(self):
        places = [
            {"placeId": "p1", "name": "Dummy Cafe", "city": "Roswell", "county": "Fulton"},
        ]
        curations = {
            "p1": {
                "name": "Dummy Cafe",
                "cw": {"tier": "excellent", "hasMeetingRoom": True},
            }
        }
        updated, count = CP.apply_curations(
            places, curations, defaults=("September 2026", "editorial"))
        self.assertEqual(count, 1)
        self.assertEqual(updated[0]["cw"]["source"], "editorial")
        self.assertEqual(updated[0]["cw"]["verified"], "September 2026")
        self.assertEqual(updated[0]["cw"]["tier"], "excellent")

    def test_provenance_per_record_override_wins(self):
        places = [
            {"placeId": "p1", "name": "Dummy Cafe", "city": "Roswell", "county": "Fulton"},
        ]
        curations = {
            "p1": {
                "name": "Dummy Cafe",
                "source": "site-visit",
                "verified": "August 2026",
                "cw": {"tier": "good", "hasMeetingRoom": False},
            }
        }
        updated, _ = CP.apply_curations(
            places, curations, defaults=("September 2026", "editorial"))
        self.assertEqual(updated[0]["cw"]["source"], "site-visit")
        self.assertEqual(updated[0]["cw"]["verified"], "August 2026")

    def test_provenance_unknown_stays_absent(self):
        places = [
            {"placeId": "p1", "name": "Dummy Cafe", "city": "Roswell", "county": "Fulton"},
        ]
        curations = {
            "p1": {
                "name": "Dummy Cafe",
                "cw": {"tier": "good", "hasMeetingRoom": False},
            }
        }
        updated, _ = CP.apply_curations(places, curations, defaults=(None, "editorial"))
        self.assertEqual(updated[0]["cw"]["source"], "editorial")
        self.assertNotIn("verified", updated[0]["cw"])

    def test_curation_category_override(self):
        places = [
            {"placeId": "p1", "name": "Some Artisanal Roaster", "category": "Coffee"}
        ]
        curations = {
            "p1": {
                "name": "Some Artisanal Roaster",
                "category": "Specialty",
                "usp": "In-house micro-lot roasting",
            }
        }
        updated, count = CP.apply_curations(places, curations)
        self.assertEqual(count, 1)
        self.assertEqual(updated[0]["category"], "Specialty")
        self.assertEqual(updated[0]["usp"], "In-house micro-lot roasting")

    def test_apply_idempotency(self):
        places = [
            {"placeId": "p1", "name": "East Pole Coffee Co", "category": "Coffee"},
            {"placeId": "p2", "name": "Regular Cafe", "category": "Coffee"},
        ]
        curations = {
            "p2": {
                "name": "Regular Cafe",
                "cw": {"tier": "excellent", "hasMeetingRoom": True}
            }
        }
        # Run 1
        pass1_places, count1 = CP.apply_curations(places, curations)
        pass1_classified, spec_count1 = CP.classify_specialty(pass1_places)
        self.assertEqual(count1, 1)
        self.assertEqual(spec_count1, 1)

        # Run 2 on the output of Run 1
        pass2_places, count2 = CP.apply_curations(pass1_classified, curations)
        pass2_classified, spec_count2 = CP.classify_specialty(pass2_places)
        self.assertEqual(count2, 1)
        self.assertEqual(spec_count2, 0)  # 0 new upgrades on second run
        self.assertEqual(pass1_classified, pass2_classified)

    def test_research_queue_uses_global_ranking_and_unknown_amenities(self):
        venues = [
            {"name": "Established", "rating": 4.8, "ratingNum": 1000, "website": "https://example.com"},
            {"name": "New", "rating": 5.0, "ratingNum": 1, "cw": None},
            {"name": "Known", "rating": 4.9, "ratingNum": 500, "cw": {"tier": "good"}},
            {"name": "Chain", "rating": 3.0, "ratingNum": 900, "model": "franchise"},
            {"name": "Unrated", "rating": None, "ratingNum": 0},
        ]
        queue = CP.research_queue(venues)
        self.assertEqual([v["name"] for v in queue], ["Established", "New", "Unrated"])
        # The ranking population includes the known venue and the franchise.
        mean = (4.8 + 5.0 + 4.9 + 3.0) / 4
        self.assertAlmostEqual(queue[0]["weightedRating"], (1000 * 4.8 + 500 * mean) / 1500)
        self.assertEqual(queue[0]["website"], "https://example.com")
        self.assertNotIn("cw", venues[0])  # never infer or mutate amenities
        self.assertEqual(len(CP.research_queue(venues, limit=1)), 1)

    def test_research_queue_handles_empty_and_unrated_data(self):
        self.assertEqual(CP.research_queue([]), [])
        self.assertEqual(CP.research_queue([{"name": "Unknown"}])[0]["weightedRating"], 0)

    def test_research_queue_deduplicates_curated_locations(self):
        seed = {"placeId": "seed", "name": "Unique Coffee", "lat": 33.7, "lng": -84.4,
                "cw": {"tier": "good"}, "rating": 4.5, "ratingNum": 100}
        places = [dict(seed, cw=None),
                  dict(seed, placeId="relisted", cw=None),
                  {"placeId": "new", "name": "Other", "rating": 4.5, "ratingNum": 100}]
        queue = CP.research_queue(CP.merge_venues(places, [seed]))
        self.assertEqual([v["placeId"] for v in queue], ["new"])

    def test_audit_computation(self):
        places = [
            {"name": "P1", "county": "Fulton", "category": "Specialty", "cw": {"tier": "excellent", "hasMeetingRoom": True}},
            {"name": "P2", "county": "Fulton", "category": "Coffee", "cw": {"tier": "good", "hasMeetingRoom": False}},
            {"name": "P3", "county": "Forsyth", "category": "Specialty", "cw": {"tier": "excellent", "hasMeetingRoom": False}},
            {"name": "P4", "county": "Forsyth", "category": "Bakery+Cafe"},
        ]
        res = CP.audit(places)
        self.assertEqual(res["total_venues"], 4)
        self.assertEqual(res["total_work_friendly"], 2)
        self.assertEqual(res["total_meeting_rooms"], 1)
        self.assertEqual(res["total_specialty"], 2)
        self.assertEqual(res["specialty_by_county"]["Fulton"], 1)
        self.assertEqual(res["specialty_by_county"]["Forsyth"], 1)
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

    def test_explicit_curation_beats_classifier(self):
        """Editorial last: a concept-cafe overlay pinning Specialty must
        survive the classifier's tea-name match (Uni Uni regression)."""
        places = [
            {"placeId": "u1", "name": "Uni Uni Boba & Figurine Painting",
             "city": "Duluth", "county": "Gwinnett", "category": "Tea/Boba",
             "types": ["tea_house"]},
        ]
        curations = {
            "u1": {"name": "Uni Uni Boba & Figurine Painting", "category": "Specialty",
                   "cw": {"tier": "good", "hasMeetingRoom": False}},
        }
        classified, _ = CP.classify_specialty(places)
        self.assertEqual(classified[0]["category"], "Tea/Boba")
        updated, count = CP.apply_curations(classified, curations,
                                            defaults=("September 2026", "editorial"))
        self.assertEqual(count, 1)
        self.assertEqual(updated[0]["category"], "Specialty")


if __name__ == "__main__":
    unittest.main()

