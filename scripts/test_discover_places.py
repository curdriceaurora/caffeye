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

    def test_county_label_mapping(self):
        c = [comp("Gwinnett County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 33.95), "Gwinnett")
        c = [comp("Forsyth County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(c, 34.20), "Forsyth")
        c = [comp("Hall County", "administrative_area_level_2")]
        self.assertIsNone(D.county_label(c, 34.20))

    def test_fulton_and_dekalb_need_the_latitude_cut(self):
        fulton = [comp("Fulton County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(fulton, 33.95), "Fulton")
        self.assertIsNone(D.county_label(fulton, 33.85))
        dekalb = [comp("DeKalb County", "administrative_area_level_2")]
        self.assertEqual(D.county_label(dekalb, 33.95), "DeKalb")
        self.assertIsNone(D.county_label(dekalb, 33.85))


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
        self.assertEqual(late["when"], "Fri-Sat till 1am; rest of week till 11pm")

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
        p["addressComponents"] = [comp("Hall County", "administrative_area_level_2")]
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


if __name__ == "__main__":
    unittest.main()
