import json
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discover_places as D

SAMPLE_PATH = Path(__file__).resolve().parent / "fixtures" / "textsearch_sample.json"
FIX = json.loads(SAMPLE_PATH.read_text())["places"]
BY_NAME = {p["displayName"]["text"]: p for p in FIX}


def comp(text, type_name):
    return {
        "longText": text,
        "shortText": text,
        "types": [type_name, "political"],
        "languageCode": "en",
    }


class FilterTests(unittest.TestCase):
    def test_chains_identified(self):
        self.assertTrue(D.is_chain("Starbucks"))
        self.assertTrue(D.is_chain("Starbucks Coffee"))
        self.assertTrue(D.is_chain("Dunkin'"))
        self.assertTrue(D.is_chain("Dunkin"))
        self.assertTrue(D.is_chain("Krispy Kreme"))
        self.assertTrue(D.is_chain("Panera Bread"))
        self.assertTrue(D.is_chain("Tim Hortons"))
        self.assertTrue(D.is_chain("7 Brew Coffee"))
        self.assertFalse(D.is_chain("Land of a Thousand Hills Coffee"))
        self.assertFalse(D.is_chain("Sweet Hut Bakery & Cafe"))
        self.assertFalse(D.is_chain("Paris Baguette"))  # in curated Duluth set
        self.assertFalse(D.is_chain("Tous Les Jours"))  # in curated Duluth set

    def test_grocery_and_fast_food_identified(self):
        self.assertTrue(D.is_grocery("Kroger Bakery"))
        self.assertTrue(D.is_grocery("Costco Bakery"))
        self.assertTrue(D.is_grocery("Whole Foods Market"))
        self.assertTrue(D.is_grocery("Sam's Club Cafe"))
        self.assertFalse(D.is_grocery("Starbucks"))
        self.assertFalse(D.is_grocery("Valor Coffee"))
        self.assertTrue(D.is_fast_food("McDonald's"))
        self.assertTrue(D.is_fast_food("McCafe"))
        self.assertTrue(D.is_fast_food("Burger King"))
        self.assertFalse(D.is_fast_food("Caribou Coffee"))

    def test_category_by_primary_type(self):
        self.assertEqual(D.category_for({"primaryType": "coffee_shop"}), "Coffee")
        self.assertEqual(D.category_for({"primaryType": "cafe"}), "Coffee")
        self.assertEqual(D.category_for({"primaryType": "bakery"}), "Bakery+Cafe")
        self.assertEqual(D.category_for({"primaryType": "bagel_shop"}), "Bakery+Cafe")
        self.assertEqual(D.category_for({"primaryType": "tea_house"}), "Tea/Boba")
        self.assertEqual(
            D.category_for({"primaryType": "dessert_shop"}), "Dessert Cafe"
        )
        self.assertIsNone(D.category_for({"primaryType": "restaurant"}))
        self.assertIsNone(D.category_for({"primaryType": "gas_station"}))

    def test_category_tea_override_from_name(self):
        p = {"primaryType": "cafe", "displayName": {"text": "Tiger Sugar Boba"}}
        self.assertEqual(D.category_for(p), "Tea/Boba")
        p = {"primaryType": "coffee_shop", "displayName": {"text": "T-Swirl Bubble Tea"}}
        self.assertEqual(D.category_for(p), "Tea/Boba")
        p = {"primaryType": "restaurant", "displayName": {"text": "Generic Boba"}}
        self.assertIsNone(D.category_for(p))

    def test_category_specialty_detection(self):
        self.assertEqual(D.category_for({"primaryType": "cat_cafe"}), "Specialty")
        self.assertEqual(D.category_for({"primaryType": "dog_cafe"}), "Specialty")
        p1 = {"primaryType": "coffee_shop", "displayName": {"text": "East Pole Coffee Co."}}
        self.assertEqual(D.category_for(p1), "Roasters")
        p2 = {"primaryType": "cafe", "displayName": {"text": "Qamaria Yemeni Coffee Co."}}
        self.assertEqual(D.category_for(p2), "Specialty")
        p3 = {"primaryType": "coffee_shop", "displayName": {"text": "Scenttok Craft Cafe"}}
        self.assertEqual(D.category_for(p3), "Specialty")
        p4 = {"primaryType": "cafe", "displayName": {"text": "Radio Roasters Coffee"}}
        self.assertEqual(D.category_for(p4), "Roasters")

        # PERC word-boundary token vs substring landmines
        self.assertEqual(D.category_for({"primaryType": "coffee_shop", "displayName": {"text": "PERC"}}), "Roasters")
        self.assertEqual(D.category_for({"primaryType": "coffee_shop", "displayName": {"text": "PERC Coffee"}}), "Roasters")
        self.assertEqual(D.category_for({"primaryType": "coffee_shop", "displayName": {"text": "Percentage Cafe"}}), "Coffee")
        self.assertEqual(D.category_for({"primaryType": "cafe", "displayName": {"text": "The Perch Coffee Shop"}}), "Coffee")
        self.assertEqual(D.category_for({"primaryType": "coffee_shop", "displayName": {"text": "Percolate Coffee"}}), "Coffee")

        # Bare "roast" disarmed vs roaster/roasting/roastery
        self.assertEqual(D.category_for({"primaryType": "cafe", "displayName": {"text": "Sunday Roast Cafe"}}), "Coffee")
        self.assertEqual(D.category_for({"primaryType": "cafe", "displayName": {"text": "Sunday Roasting Cafe"}}), "Roasters")

        # Bakery guard: bakeries don't get hijacked by generic specialty name patterns
        self.assertEqual(D.category_for({"primaryType": "bakery", "displayName": {"text": "Sunday Roasters Bakery"}}), "Bakery+Cafe")
        self.assertEqual(D.category_for({"primaryType": "bakery", "displayName": {"text": "Turkish Delight Bakery"}}), "Bakery+Cafe")
        # but deliberate roasteries do upgrade even if primary was bakery
        self.assertEqual(D.category_for({"primaryType": "bakery", "displayName": {"text": "East Pole Coffee Co"}}), "Roasters")

        # Precedence: Tea/Boba takes precedence over generic specialty
        self.assertEqual(D.category_for({"primaryType": "coffee_shop", "displayName": {"text": "Yemeni Boba Tea House"}}), "Tea/Boba")

    def test_county_label_mapping(self):
        c = [comp("Gwinnett County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 33.95), "Gwinnett")
        c = [comp("Forsyth County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 34.20), "Forsyth")
        c = [comp("Cobb County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 33.95), "Cobb")
        c = [comp("Cherokee County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 34.20), "Cherokee")
        c = [comp("Hall County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 34.20), "Hall")
        c = [comp("Dawson County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 34.40), "Dawson")
        c = [comp("Clayton County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 33.50), "Clayton")
        c = [comp("Bibb County", "administrative_area_level_2")]
        self.assertIsNone(D.county_label(c, 32.84))

    def test_fulton_dekalb_and_cobb_include_itp_and_downtown(self):
        fulton = [comp("Fulton County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(fulton, 33.95), "Fulton")
        self.assertEqual(D.county_label(fulton, 33.75), "Fulton")  # Downtown Atlanta
        dekalb = [comp("DeKalb County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(dekalb, 33.95), "DeKalb")
        self.assertEqual(D.county_label(dekalb, 33.77), "DeKalb")  # Decatur
        cobb = [comp("Cobb County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(cobb, 33.95), "Cobb")
        self.assertEqual(D.county_label(cobb, 33.80), "Cobb")      # Vinings / Cumberland

    def test_min_lat_rule_honored_when_specified(self):
        from unittest.mock import patch
        custom_rule = {"api": "Test County", "label": "Test", "min_lat": 33.90}
        with patch.dict(D.REGION, {"counties": [custom_rule]}):
            test_c = [comp("Test County", "administrative_area_level_2")]
            self.assertEqual(D.county_label(test_c, 33.95), "Test")
            self.assertIsNone(D.county_label(test_c, 33.85))


class HoursTests(unittest.TestCase):
    def test_compact_single_span_all_week(self):
        wd = [f"{d}: 7:00 AM – 9:00 PM" for d in (
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
        )]
        self.assertEqual(D.compact_hours(wd), "Mon-Sun 7am-9pm")

    def test_compact_weekday_weekend_split(self):
        wd = [f"{d}: 7:00 AM – 9:00 PM" for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")]
        wd += [f"{d}: 8:00 AM – 10:30 PM" for d in ("Saturday", "Sunday")]
        self.assertEqual(D.compact_hours(wd), "Mon-Fri 7am-9pm · Sat-Sun 8am-10:30pm")

    def test_compact_hours_wrap_sunday_to_monday(self):
        wd = [f"{d}: 10:00 AM – 10:00 PM" for d in ("Monday", "Tuesday", "Wednesday", "Thursday")]
        wd += [f"{d}: 10:00 AM – 11:00 PM" for d in ("Friday", "Saturday")]
        wd += ["Sunday: 10:00 AM – 10:00 PM"]
        self.assertEqual(D.compact_hours(wd), "Sun-Thu 10am-10pm · Fri-Sat 10am-11pm")

    def test_compact_none_when_missing(self):
        self.assertIsNone(D.compact_hours(None))
        self.assertIsNone(D.compact_hours([]))


class LateTests(unittest.TestCase):
    def p(self, day, oh, ch, cday=None, cmin=0):
        return {
            "open": {"day": day, "hour": oh, "minute": 0},
            "close": {"day": day if cday is None else cday, "hour": ch, "minute": cmin},
        }

    def test_no_late_when_all_close_before_ten(self):
        self.assertIsNone(D.late_for([self.p(d, 7, 21) for d in range(7)]))

    def test_ten_pm_tier(self):
        late = D.late_for([self.p(d, 7, 22 if d in (5, 6) else 21) for d in range(7)])
        self.assertEqual(late, {"tier": "10pm+", "when": "Fri-Sat till 10pm"})

    def test_midnight_tier_from_next_day_close(self):
        periods = [self.p(d, 10, 23) for d in range(7)]
        periods[5] = self.p(5, 10, 1, cday=6)  # Friday closes 1am Saturday
        periods[6] = self.p(6, 10, 0, cday=0)  # Saturday closes midnight
        late = D.late_for(periods)
        self.assertEqual(late["tier"], "midnight")
        self.assertEqual(late["when"], "Fri till 1am; Sat till midnight; Sun-Thu till 11pm")

    def test_always_open_twenty_four_hours(self):
        late = D.late_for([{"open": {"day": 0, "hour": 0, "minute": 0}}])
        self.assertEqual(late, {"tier": "midnight", "when": "Open 24 hours"})

    def test_differing_weekday_and_weekend_closures(self):
        # 967 Coffee Co schedule: Sun-Thu close midnight, Fri-Sat close 2am
        periods = [self.p(d, 7, 0, cday=(d + 1) % 7) for d in range(5)]
        periods.append(self.p(5, 7, 2, cday=6))
        periods.append(self.p(6, 7, 2, cday=0))
        late = D.late_for(periods)
        self.assertEqual(
            late,
            {"tier": "midnight", "when": "Fri-Sat till 2am; Sun-Thu till midnight"},
        )

    def test_closed_days_do_not_produce_rest_of_week(self):
        # Only Fri and Sat open late (1am), Mon-Thu close 8pm, Sun closed
        periods = [self.p(d, 8, 20) for d in (1, 2, 3, 4)]
        periods.append(self.p(5, 8, 1, cday=6))
        periods.append(self.p(6, 8, 1, cday=0))
        late = D.late_for(periods)
        self.assertEqual(late, {"tier": "midnight", "when": "Fri-Sat till 1am"})

    def test_multi_day_continuous_open(self):
        # Mon 0:00 to Sat 0:00 (5 full days open), Sat-Sun 9am-9pm
        periods = [
            self.p(0, 9, 21),
            {
                "open": {"day": 1, "hour": 0, "minute": 0},
                "close": {"day": 6, "hour": 0, "minute": 0},
            },
            self.p(6, 9, 21),
        ]
        late = D.late_for(periods)
        self.assertEqual(late, {"tier": "midnight", "when": "Weekdays Open 24 hours"})

    def test_daily(self):
        late = D.late_for([self.p(d, 7, 23, cmin=30) for d in range(7)])
        self.assertEqual(late, {"tier": "10pm+", "when": "Daily till 11:30pm"})

    def test_weekdays_and_weekends_words(self):
        late = D.late_for(
            [self.p(d, 7, 22 if d in (1, 2, 3, 4, 5) else 21) for d in range(7)]
        )
        self.assertEqual(late["when"], "Weekdays till 10pm")
        late = D.late_for([self.p(d, 7, 23 if d in (0, 6) else 21) for d in range(7)])
        self.assertEqual(late["when"], "Weekends till 11pm")

    def test_none_for_missing_periods(self):
        self.assertIsNone(D.late_for(None))
        self.assertIsNone(D.late_for([]))


class ModelTests(unittest.TestCase):
    def test_national_and_regional_franchises_identified(self):
        self.assertEqual(D.model_for("Sweet Hut Bakery & Cafe"), "franchise")
        self.assertEqual(D.model_for("Cafe Mozart Bakery"), "franchise")
        self.assertEqual(D.model_for("Paris Baguette"), "franchise")
        self.assertEqual(D.model_for("TOUS les JOURS Bakery Café - Doraville"), "franchise")
        self.assertEqual(D.model_for("Kung Fu Tea"), "franchise")
        self.assertEqual(D.model_for("Ding Tea Duluth"), "franchise")
        self.assertEqual(D.model_for("Crumbl Cookies"), "franchise")
        self.assertEqual(D.model_for("Kroger Bakery"), "franchise")
        self.assertEqual(D.model_for("Sam's Club Bakery"), "franchise")
        self.assertEqual(D.model_for("The Human Bean"), "franchise")
        self.assertEqual(D.model_for("Hansel & Gretel Bakery Cafe"), "franchise")
        self.assertEqual(D.model_for("White Windmill Bakery & Cafe"), "franchise")
        self.assertEqual(D.model_for("Land of a Thousand Hills Coffee"), "franchise")

    def test_independent_cafes_identified(self):
        self.assertEqual(D.model_for("TwoHa's Cafe"), "independent")
        self.assertEqual(D.model_for("Yibna Cafe"), "independent")
        self.assertEqual(D.model_for("The Cream"), "independent")
        self.assertEqual(D.model_for("Alchemist On the Divide"), "independent")
        self.assertEqual(D.model_for("Ginkgo Bakery & Cafe"), "independent")
        self.assertEqual(D.model_for("Boba Mocha"), "independent")

    def test_multi_location_brand_frequency(self):
        brand_counts = Counter({"tier couture bakery": 3, "valor coffee": 2})
        # 3 locations -> franchise
        self.assertEqual(
            D.model_for("Tier Couture Bakery Norcross", brand_counts), "franchise"
        )
        # 2 locations without franchise keyword -> independent
        self.assertEqual(D.model_for("Valor Coffee", brand_counts), "independent")


class RecordTests(unittest.TestCase):
    def test_sweet_hut_record(self):
        rec, reason = D.to_record(BY_NAME["Sweet Hut Bakery & Cafe"])
        self.assertIsNone(reason)
        self.assertEqual(rec["placeId"], BY_NAME["Sweet Hut Bakery & Cafe"]["id"])
        self.assertEqual(rec["name"], "Sweet Hut Bakery & Cafe")
        self.assertEqual(rec["city"], "Duluth")
        self.assertEqual(rec["county"], "Gwinnett")
        self.assertEqual(rec["category"], "Bakery+Cafe")
        self.assertEqual(rec["model"], "franchise")
        self.assertEqual(rec["rating"], 4.5)
        self.assertEqual(rec["ratingNum"], 3767)
        self.assertEqual(rec["ratingCount"], "3,767")
        self.assertIsInstance(rec["lat"], float)
        self.assertIsInstance(rec["lng"], float)
        self.assertTrue(rec["hours"])
        self.assertEqual(rec["late"]["tier"], "10pm+")
        self.assertTrue(rec["googleUrl"].startswith("https://"))
        self.assertEqual(
            list(rec.keys()),
            [
                "placeId",
                "name",
                "address",
                "city",
                "county",
                "neighborhood",
                "lat",
                "lng",
                "category",
                "model",
                "types",
                "rating",
                "ratingNum",
                "ratingCount",
                "hours",
                "late",
                "website",
                "googleUrl",
            ],
        )

    def test_boba_mocha_is_tea(self):
        rec, _ = D.to_record(BY_NAME["Boba Mocha"])
        self.assertEqual(rec["category"], "Tea/Boba")
        self.assertEqual(rec["model"], "independent")

    def test_brunch_restaurant_dropped(self):
        rec, reason = D.to_record(BY_NAME["Cafe 104"])
        self.assertIsNone(rec)
        self.assertEqual(reason, "type:brunch_restaurant")

    def test_no_late_key_when_not_late(self):
        rec, _ = D.to_record(BY_NAME["Land of a Thousand Hills Coffee"])
        self.assertNotIn("late", rec)

    def test_closed_and_out_of_region_and_grocery_dropped(self):
        p = json.loads(json.dumps(BY_NAME["Sweet Hut Bakery & Cafe"]))
        p["businessStatus"] = "CLOSED_TEMPORARILY"
        self.assertEqual(D.to_record(p)[1], "status:CLOSED_TEMPORARILY")
        p = json.loads(json.dumps(BY_NAME["Sweet Hut Bakery & Cafe"]))
        p["addressComponents"] = [comp("Bibb County", "administrative_area_level_2")]
        self.assertEqual(D.to_record(p)[1], "county")
        p = json.loads(json.dumps(BY_NAME["Sweet Hut Bakery & Cafe"]))
        p["displayName"]["text"] = "Kroger Bakery"
        self.assertEqual(D.to_record(p)[1], "grocery")
        p = json.loads(json.dumps(BY_NAME["Sweet Hut Bakery & Cafe"]))
        p["displayName"]["text"] = "McDonald's"
        self.assertEqual(D.to_record(p)[1], "fast_food")
        # Chains like Starbucks or Tim Hortons are NOT dropped; they are kept as franchise
        p = json.loads(json.dumps(BY_NAME["Sweet Hut Bakery & Cafe"]))
        p["displayName"]["text"] = "Tim Hortons"
        rec, reason = D.to_record(p)
        self.assertIsNone(reason)
        self.assertEqual(rec["model"], "franchise")


class BuildTests(unittest.TestCase):
    def test_build_dedupes_excludes_and_counts(self):
        raw = {p["id"]: p for p in FIX}
        recs, stats = D.build_places(raw, exclude_ids={BY_NAME["Boba Mocha"]["id"]})
        names = sorted(r["name"] for r in recs)
        self.assertEqual(
            names, ["Land of a Thousand Hills Coffee", "Sweet Hut Bakery & Cafe"]
        )
        self.assertEqual(stats["kept"], 2)
        self.assertEqual(stats["dropped"]["excluded"], 1)
        self.assertEqual(stats["dropped"]["type:brunch_restaurant"], 1)
        self.assertEqual(
            [r["placeId"] for r in recs], sorted(r["placeId"] for r in recs)
        )


class GateTests(unittest.TestCase):
    def test_gate(self):
        self.assertEqual(
            D.usage_gate(used=0, planned=400, threshold=500, cap=900), (True, "")
        )
        ok, msg = D.usage_gate(used=500, planned=1, threshold=500, cap=900)
        self.assertFalse(ok)
        self.assertIn("500", msg)
        ok, msg = D.usage_gate(used=400, planned=600, threshold=500, cap=900)
        self.assertFalse(ok)
        self.assertIn("900", msg)


class FakeClient:
    """Dense everywhere: big rects saturate (60), medium ones hold 25, tiny ones 3."""

    def __init__(self):
        self.calls = Counter()

    def __call__(self, body, mask, sku):
        self.calls[sku] += 1
        r = body["locationRestriction"]["rectangle"]
        area = (r["high"]["latitude"] - r["low"]["latitude"]) * (
            r["high"]["longitude"] - r["low"]["longitude"]
        )
        n = 60 if area > 0.3 else (25 if area > 0.05 else 3)
        idx = int(body.get("pageToken", "p0")[1:])
        start = idx * 20
        places = [
            {"id": f"{r['low']['latitude']}:{r['low']['longitude']}:{i}"}
            for i in range(start, min(n, start + 20))
        ]
        res = {"places": places}
        if start + 20 < n:
            res["nextPageToken"] = f"p{idx + 1}"
        return res


class CrawlTests(unittest.TestCase):
    def test_quadtree_splits_saturated_cells_and_counts_calls(self):
        fake = FakeClient()
        leaves = D.crawl(fake, D.Rect(0.0, 0.0, 2.0, 2.0), "coffee_shop", "coffee")
        self.assertEqual(len(leaves), 16)
        self.assertTrue(all(n == 25 for _r, n, _c in leaves))
        self.assertEqual(D.planned_calls(leaves), 32)  # 16 leaves × 2 pages
        self.assertEqual(fake.calls[D.SKU_IDS], 3 + 4 * 3 + 16 * 2)
        self.assertEqual(fake.calls[D.SKU_FULL], 0)

    def test_empty_leaves_cost_nothing_in_pass_two(self):
        self.assertEqual(
            D.planned_calls([(D.Rect(0, 0, 1, 1), 0, 1), (D.Rect(0, 0, 1, 1), 5, 1)]), 1
        )

    def test_fetch_details_dedupes_by_id(self):
        fake = FakeClient()
        plan = [
            ("coffee_shop", "coffee", D.Rect(0.0, 0.0, 0.5, 0.5)),
            ("cafe", "cafe", D.Rect(0.0, 0.0, 0.5, 0.5)),
        ]
        raw = D.fetch_details(fake, plan)
        self.assertEqual(len(raw), 25)
        self.assertEqual(fake.calls[D.SKU_FULL], 4)

    def test_load_exclusions_supports_strings_and_dicts(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            json.dump([{"placeId": "ChIJ111"}, "ChIJ222"], tf)
            tf_path = Path(tf.name)
        try:
            orig = D.EXCLUDE_PATH
            D.EXCLUDE_PATH = tf_path
            exclusions = D.load_exclusions()
            self.assertEqual(exclusions, {"ChIJ111", "ChIJ222"})
        finally:
            D.EXCLUDE_PATH = orig
            tf_path.unlink(missing_ok=True)

    def test_client_and_request_single_ledger_entry_per_request(self):
        from unittest.mock import MagicMock, patch
        with (
            patch("discover_places.ledger") as mock_ledger,
            patch("refresh_ratings.places_ledger") as mock_rr_ledger,
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"places": []}'
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            client = D.Client("fake-key", sleep=0.0)
            # Pass 1 request (free ids-only)
            client({}, D.IDS_MASK, D.SKU_IDS)
            # Only refresh_ratings.places_ledger should record the SKU_IDS
            mock_rr_ledger.record.assert_called_once_with(D.SKU_IDS)
            mock_ledger.record.assert_not_called()

            mock_rr_ledger.reset_mock()
            # Pass 2 request (paid enterprise)
            client({}, D.FULL_MASK, D.SKU_FULL)
            mock_rr_ledger.record.assert_called_once_with(D.SKU_FULL)
            mock_ledger.record.assert_not_called()

    def test_fetch_details_preserves_partial_progress_on_failure(self):
        from unittest.mock import MagicMock, patch
        call_count = [0]

        def fake_fetch_pages(client, rect, qtype, text, mask, sku, on_page=None):
            call_count[0] += 1
            if call_count[0] == 2:
                raise D.FatalApiError("Simulated 429 rate limit")
            places = [{"id": f"place_{call_count[0]}"}]
            if on_page:
                on_page(places)
            return places, 1

        with patch("discover_places.fetch_pages", side_effect=fake_fetch_pages):
            client = MagicMock()
            plan = [
                ("q1", "t1", D.Rect(0, 0, 1, 1)),
                ("q2", "t2", D.Rect(0, 0, 1, 1)),
            ]
            accumulated = {}
            with self.assertRaises(D.FatalApiError):
                D.fetch_details(client, plan, out=accumulated)
            self.assertIn("place_1", accumulated)

    def test_fetch_details_preserves_page_one_when_page_two_fails(self):
        """P2 finding: failure on page 2 of a multi-page query must not lose page 1 records."""
        from unittest.mock import MagicMock
        calls = [0]

        def fake_client(body, mask, sku):
            calls[0] += 1
            if calls[0] == 1:
                return {
                    "places": [{"id": "page1_place"}],
                    "nextPageToken": "token_for_page_2"
                }
            raise D.FatalApiError("Interrupted on page 2")

        client = MagicMock(side_effect=fake_client)
        plan = [("q1", "t1", D.Rect(0, 0, 1, 1))]
        accumulated = {}
        with self.assertRaises(D.FatalApiError):
            D.fetch_details(client, plan, out=accumulated)
        self.assertIn("page1_place", accumulated)

    def test_replay_rejects_incomplete_dump_unless_allowed(self):
        """P2 finding: replaying an incomplete dump with --write must refuse by default."""
        import tempfile
        from unittest.mock import patch

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"incomplete": True, "places": {}}, f)
            temp_path = f.name

        try:
            test_args = ["discover_places.py", "--replay", temp_path, "--write"]
            with patch("sys.argv", test_args):
                with self.assertRaises(SystemExit) as cm:
                    D.main()
                self.assertIn("marked as incomplete", str(cm.exception))

            # With --allow-incomplete, it proceeds to write_places
            test_args_allowed = ["discover_places.py", "--replay", temp_path, "--write", "--allow-incomplete"]
            with patch("sys.argv", test_args_allowed), patch("discover_places.write_places") as mock_write:
                ret = D.main()
                self.assertEqual(ret, 0)
                mock_write.assert_called_once()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_keyboard_interrupt_during_pass_2_marks_dump_incomplete(self):
        """Pass 2 interrupted by KeyboardInterrupt must write dump with incomplete: True."""
        import tempfile
        from unittest.mock import patch

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            test_args = ["discover_places.py", "--raw", temp_path]
            with patch("sys.argv", test_args), \
                 patch("discover_places.load_key", return_value="dummy_key"), \
                 patch("discover_places.crawl", return_value=[]), \
                 patch("discover_places.usage_gate", return_value=(True, "")), \
                 patch("discover_places.fetch_details", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    D.main()

            dump = json.loads(Path(temp_path).read_text())
            self.assertTrue(dump.get("incomplete"))
        finally:
            Path(temp_path).unlink(missing_ok=True)



if __name__ == "__main__":
    unittest.main()
