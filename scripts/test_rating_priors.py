import json
import unittest
from rating_priors import ROOT, regional_priors


class RatingPriorsTests(unittest.TestCase):
    def test_published_priors_match_the_regional_population(self):
        seed = json.loads((ROOT / 'public/shops.json').read_text())
        region = json.loads((ROOT / 'public/places.json').read_text())
        self.assertEqual(seed['ratingPriors'], regional_priors(seed, region))

    def test_deduplicates_curated_place_ids_and_nearby_relistings(self):
        seed = {'addr': {}, 'shops': [{'name': 'Example Coffee', 'placeId': 'seed',
                'lat': 33.9, 'lng': -84.1, 'rating': 4, 'ratingNum': 100}]}
        region = {'places': [dict(seed['shops'][0], category='Coffee'),
                  dict(seed['shops'][0], placeId='relisted', category='Coffee'),
                  dict(seed['shops'][0], name='Different Coffee', placeId='other',
                       category='Coffee', rating=5, ratingNum=200)]}
        priors = regional_priors(seed, region)
        self.assertEqual(priors['population'], 2)
        self.assertEqual(priors['C'], 4.5)
        self.assertEqual(priors['m'], 200)

    def test_mirrors_browser_coordinate_and_field_rules(self):
        seed = {'addr': {'seed-bad': {'lat': 0, 'lng': 0}},
                'shops': [{'name': 'Kept Seed', 'lat': 33.9, 'lng': -84.1, 'rating': 4, 'ratingNum': None},
                          {'name': 'Bad Addr Seed', 'addrKey': 'seed-bad', 'lat': 33.9, 'lng': -84.1, 'rating': 5}]}
        region = {'places': [
            {'name': 'Lat Zero Only', 'category': 'Coffee', 'lat': 0, 'lng': -84.2, 'rating': 3},
            {'name': 'Both Zero', 'category': 'Coffee', 'lat': 0, 'lng': 0, 'rating': 5},
            {'name': 'String Coords', 'category': 'Coffee', 'lat': '33.9', 'lng': '-84.1', 'rating': 5},
            {'name': 'Unknown Category', 'category': 'Bar', 'lat': 33.8, 'lng': -84.3, 'rating': 5},
            {'name': '', 'category': 'Coffee', 'lat': 33.8, 'lng': -84.3, 'rating': 5},
            'not a record',
        ]}
        priors = regional_priors(seed, region)
        # Kept Seed + Lat Zero Only; the seed with (0, 0) ADDR coordinates is dropped like prepareShop does.
        self.assertEqual(priors['population'], 2)
        self.assertEqual(priors['C'], 3.5)
        self.assertEqual(priors['m'], 1)  # null ratingNum counts as 0; median 0 falls back to 1

    def test_uncurated_seed_records_do_not_hide_relistings(self):
        seed = {'addr': {}, 'shops': [{'name': 'Example Roasters', 'curated': False, 'lat': 33.9, 'lng': -84.1, 'rating': 4}]}
        region = {'places': [{'name': 'Example Roasters', 'placeId': 'p', 'category': 'Coffee', 'lat': 33.9, 'lng': -84.1, 'rating': 5}]}
        self.assertEqual(regional_priors(seed, region)['population'], 2)

    def test_empty_addr_entry_and_zero_latitude_follow_js(self):
        # ADDR[key] = {} is truthy in JS, so the seed uses it and is dropped for missing coordinates.
        seed = {'addr': {'empty': {}}, 'shops': [
            {'name': 'Empty Addr Seed', 'addrKey': 'empty', 'lat': 33.9, 'lng': -84.1, 'rating': 5},
            {'name': 'Example Roasters', 'lat': 33.9, 'lng': -84.1, 'rating': 4}]}
        # A place at latitude 0 skips the relisting check, so it is admitted despite the shared name.
        region = {'places': [{'name': 'Example Roasters', 'placeId': 'z', 'category': 'Coffee', 'lat': 0, 'lng': -84.1, 'rating': 3}]}
        priors = regional_priors(seed, region)
        self.assertEqual(priors['population'], 2)
        self.assertEqual(priors['C'], 3.5)
