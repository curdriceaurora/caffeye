import copy
import json
import unittest
from pathlib import Path

from export_venues import export

ROOT = Path(__file__).resolve().parents[2]


class ExportTests(unittest.TestCase):
    def test_repository_export_has_all_accepted_venues_without_rating_inputs(self):
        seed = json.loads((ROOT / "public/shops.json").read_text())
        regional = json.loads((ROOT / "public/places.json").read_text())
        result = export(seed, regional)
        self.assertEqual(len(result["venues"]), 1705)
        self.assertEqual(sum(v["model"] == "independent" for v in result["venues"]), 970)
        self.assertEqual(sum(v["curated"] for v in result["venues"]), 61)
        forbidden = {"rating", "ratingNum", "ratingCount", "ratingPriors", "priors", "weightedRating"}
        def check(node):
            if isinstance(node, dict):
                self.assertFalse(forbidden.intersection(node))
                for value in node.values():
                    check(value)
            elif isinstance(node, list):
                for value in node:
                    check(value)
        check(result)
        self.assertEqual(result, export(seed, regional))
        stripped_seed = copy.deepcopy(seed)
        stripped_regional = copy.deepcopy(regional)
        stripped_seed.pop("ratingPriors", None)
        for records in [stripped_seed["shops"], stripped_regional["places"]]:
            for record in records:
                for key in ["rating", "ratingNum", "ratingCount"]:
                    record.pop(key, None)
        # Rating inputs cannot affect venue identity, order, or snapshot revision.
        self.assertEqual(result, export(stripped_seed, stripped_regional))

    def test_curated_coordinates_and_editorial_details_survive_export(self):
        seed = json.loads((ROOT / "public/shops.json").read_text())
        result = export(seed, json.loads((ROOT / "public/places.json").read_text()))
        for original in seed["shops"]:
            venue = next(v for v in result["venues"] if v.get("providerIDs", {}).get("google") == original["placeId"])
            self.assertTrue(venue["curated"])
            self.assertEqual(venue["fieldProvenance"]["coordinate"]["source"], "Apple geocoding (curated seed)")
            self.assertNotIn("verified", venue["fieldProvenance"]["coordinate"])
            self.assertEqual(venue["fieldProvenance"]["work"], venue["work"]["provenance"])
            self.assertEqual(venue["providerIDs"]["caffeyeAddress"], original["addrKey"])
            self.assertEqual(venue["coordinate"], {
                "latitude": seed["addr"][original["addrKey"]]["lat"],
                "longitude": seed["addr"][original["addrKey"]]["lng"],
            })
            for old, new in [("usp", "summary"), ("signature", "signature"), ("loved", "loved"),
                             ("hours", "hours"), ("googleUrl", "googleURL"), ("yelpUrl", "yelpURL")]:
                self.assertEqual(venue[new], original[old])
            self.assertEqual(venue["work"]["tier"], original["cw"]["tier"])


if __name__ == "__main__":
    unittest.main()
