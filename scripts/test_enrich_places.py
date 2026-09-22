#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

import enrich_places as EP


class TestEnrichPlaces(unittest.TestCase):
    def test_canonicalize_url(self):
        url = "https://WWW.Example.com/menu/?utm_source=google&utm_medium=cpc&ref=xyz#top"
        canon = EP.canonicalize_url(url)
        self.assertEqual(canon, "https://www.example.com/menu/")

    def test_discover_subpages_prioritizes_relevant_links(self):
        html = """
        <html>
            <body>
                <a href="/locations/roswell">Our Roswell Location</a>
                <a href="/menu/drinks">Coffee Menu</a>
                <a href="/private-events-meeting-room">Meeting & Conference Room</a>
                <a href="/about-us">About Us</a>
                <a href="/cart">Cart</a>
                <a href="/menu.pdf">Download Menu PDF</a>
                <a href="https://instagram.com/mycafe">Instagram</a>
                <a href="https://otherdomain.com/info">Other Domain</a>
            </body>
        </html>
        """
        subpages = EP.discover_subpages("https://mycafe.com", html, max_pages=5)
        self.assertIn("https://mycafe.com/private-events-meeting-room", subpages)
        self.assertIn("https://mycafe.com/locations/roswell", subpages)
        self.assertIn("https://mycafe.com/menu/drinks", subpages)
        # Should not include external or skip extensions
        self.assertFalse(any("instagram.com" in u for u in subpages))
        self.assertFalse(any("otherdomain.com" in u for u in subpages))
        self.assertFalse(any(u.endswith(".pdf") for u in subpages))
        self.assertFalse(any("/cart" in u for u in subpages))

    def test_branch_matching_isolates_specific_locations(self):
        pages = {
            "https://mycafe.com/locations/roswell": {
                "ok": True,
                "content": "<p>1173 Alpharetta St, Roswell, GA 30075. Features our reservable conference room.</p>",
            },
            "https://mycafe.com/locations/midtown": {
                "ok": True,
                "content": "<p>999 Peachtree St, Midtown, Atlanta, GA 30309. Express counter only, no seating.</p>",
            },
            "https://mycafe.com/menu": {
                "ok": True,
                "content": "<p>Our signature espresso and pour-overs.</p>",
            },
        }
        tagged = EP.match_branch_pages(pages, address="1173 Alpharetta St, Roswell, GA", city="Roswell")
        # Roswell page should match
        self.assertTrue(tagged["https://mycafe.com/locations/roswell"]["branch_match"])
        # Midtown page should be rejected for this branch
        self.assertFalse(tagged["https://mycafe.com/locations/midtown"]["branch_match"])
        # General menu page should match
        self.assertTrue(tagged["https://mycafe.com/menu"]["branch_match"])

    def test_extract_facts_negative_laptop_policy(self):
        pages = {
            "https://cafe.com/policy": {
                "ok": True,
                "content": "<p>We are a community-first cafe. Please note: no laptops or screens allowed on weekends.</p>",
            },
            "https://cafe.com/menu": {
                "ok": True,
                "content": "<p>Signature: Honey Lavender Latte. Fresh pastries daily.</p>",
            },
        }
        facts = EP.extract_facts(pages)
        self.assertEqual(facts["laptopPolicy"]["status"], "unavailable")
        self.assertIn("no laptops or screens allowed on weekends", facts["laptopPolicy"]["excerpt"])
        self.assertEqual(facts["laptopPolicy"]["sourceUrl"], "https://cafe.com/policy")
        # Wi-Fi was not mentioned, must be unknown
        self.assertEqual(facts["wifi"]["status"], "unknown")
        # Outlets not mentioned, must be unknown
        self.assertEqual(facts["outlets"]["status"], "unknown")

    def test_extract_facts_positive_wifi_and_seating(self):
        pages = {
            "https://cafe.com/about": {
                "ok": True,
                "content": "<p>We provide free high-speed Wi-Fi and communal tables for study groups.</p>",
            },
        }
        facts = EP.extract_facts(pages)
        self.assertEqual(facts["wifi"]["status"], "confirmed")
        self.assertEqual(facts["seating"]["status"], "confirmed")
        self.assertEqual(facts["meetingRoom"]["status"], "unknown")

    def test_extract_facts_distinguishes_private_party_from_meeting_room(self):
        pages = {
            "https://cafe.com/events": {
                "ok": True,
                "content": "<p>Host your private party, wedding reception, or bridal shower with us! Full venue buyout available.</p>",
            },
        }
        facts = EP.extract_facts(pages)
        # Party rental should NOT be confirmed as a work meeting room
        self.assertEqual(facts["meetingRoom"]["status"], "unavailable")
        self.assertIn("private party", facts["meetingRoom"]["excerpt"].lower())

    def test_extract_facts_meeting_room_confirmed(self):
        pages = {
            "https://cafe.com/rooms": {
                "ok": True,
                "content": "<p>Book our private conference room for business meetings and presentations. Table seats up to 10.</p>",
            },
        }
        facts = EP.extract_facts(pages)
        self.assertEqual(facts["meetingRoom"]["status"], "confirmed")
        self.assertIn("conference room", facts["meetingRoom"]["excerpt"].lower())

    def test_derive_curation_overlay_limited_policy(self):
        facts = {
            "laptopPolicy": {
                "status": "unavailable",
                "excerpt": "No laptops on weekends per cafe guidelines.",
                "sourceUrl": "https://cafe.com/faq",
                "checkedDate": "September 2026",
            },
            "wifi": {"status": "unknown"},
            "meetingRoom": {"status": "unknown"},
            "seating": {"status": "unknown"},
            "roaster": {"status": "unknown"},
            "menuHighlights": [],
        }
        meta = {"name": "Quiet Corner", "city": "Decatur", "county": "DeKalb", "category": "Coffee"}
        overlay = EP.derive_curation_overlay(facts, meta)
        self.assertIsNotNone(overlay.get("cw"))
        self.assertEqual(overlay["cw"]["tier"], "limited")
        self.assertFalse(overlay["cw"]["hasMeetingRoom"])
        self.assertIn("No laptops on weekends", overlay["cw"]["note"])

    def test_derive_curation_overlay_meeting_room(self):
        facts = {
            "laptopPolicy": {"status": "unknown"},
            "wifi": {
                "status": "confirmed",
                "excerpt": "Complimentary high-speed Wi-Fi.",
                "sourceUrl": "https://cafe.com",
            },
            "meetingRoom": {
                "status": "confirmed",
                "excerpt": "Reservable conference room with presentation monitor.",
                "sourceUrl": "https://cafe.com/rooms",
            },
            "seating": {"status": "unknown"},
            "roaster": {"status": "unknown"},
            "menuHighlights": ["Honey Lavender Latte"],
        }
        meta = {"name": "Hub Coffee", "city": "Marietta", "county": "Cobb", "category": "Coffee"}
        overlay = EP.derive_curation_overlay(facts, meta)
        self.assertEqual(overlay["cw"]["tier"], "excellent")
        self.assertTrue(overlay["cw"]["hasMeetingRoom"])
        self.assertEqual(overlay["cw"]["meetingRoomNote"], "Reservable conference room with presentation monitor.")
        self.assertEqual(overlay["signature"], "Honey Lavender Latte")

    def test_derive_curation_overlay_unknown_facts_leaves_cw_unassessed(self):
        facts = {
            "laptopPolicy": {"status": "unknown"},
            "wifi": {"status": "unknown"},
            "meetingRoom": {"status": "unknown"},
            "seating": {"status": "unknown"},
            "roaster": {"status": "unknown"},
            "menuHighlights": [],
        }
        meta = {"name": "Standard Bakery", "city": "Alpharetta", "county": "Fulton", "category": "Bakery+Cafe"}
        overlay = EP.derive_curation_overlay(facts, meta)
        # Should NOT label the venue as unsuitable or give a bad tier
        self.assertNotIn("cw", overlay)
        self.assertTrue(overlay["usp"].startswith("Independent"))

    def test_detect_contradictions(self):
        existing = {
            "cw": {
                "tier": "excellent",
                "hasMeetingRoom": True,
            }
        }
        proposed = {
            "cw": {
                "tier": "limited",
                "hasMeetingRoom": False,
                "note": "No laptops allowed.",
            }
        }
        conflicts = EP.detect_contradictions(proposed, existing)
        self.assertEqual(len(conflicts), 2)
        self.assertTrue(any("Meeting room conflict" in c for c in conflicts))
        self.assertTrue(any("Tier downgrade conflict" in c for c in conflicts))

    def test_generate_balanced_queue_distribution(self):
        places = [
            {"placeId": f"p_fulton_{i}", "name": f"Fulton Cafe {i}", "county": "Fulton", "city": "Atlanta",
             "rating": 4.8, "ratingNum": 500, "website": f"https://fulton{i}.com", "model": "independent"}
            for i in range(30)
        ] + [
            {"placeId": f"p_cobb_{i}", "name": f"Cobb Cafe {i}", "county": "Cobb", "city": "Marietta",
             "rating": 4.7, "ratingNum": 400, "website": f"https://cobb{i}.com", "model": "independent"}
            for i in range(20)
        ] + [
            {"placeId": "p_franchise", "name": "Starbucks", "county": "Fulton", "city": "Atlanta",
             "rating": 4.0, "ratingNum": 1000, "website": "https://starbucks.com", "model": "franchise"}
        ]
        quotas = {"Fulton": 5, "Cobb": 5}
        queue = EP.generate_balanced_queue(places, shops=[], quotas=quotas, target_total=10)
        self.assertEqual(len(queue), 10)
        f_count = sum(1 for c in queue if c["county"] == "Fulton")
        c_count = sum(1 for c in queue if c["county"] == "Cobb")
        self.assertEqual(f_count, 5)
        self.assertEqual(c_count, 5)
        # Franchises excluded
        self.assertFalse(any(c["name"] == "Starbucks" for c in queue))


if __name__ == "__main__":
    unittest.main()
