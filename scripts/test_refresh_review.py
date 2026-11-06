"""Regressions found in the November refresh review."""
import copy
import json
import unittest
from pathlib import Path
import discover_places as D


class RefreshReviewTests(unittest.TestCase):
    def operational(self):
        fixtures = json.loads((Path(__file__).parent / 'fixtures/textsearch_sample.json').read_text())['places']
        return copy.deepcopy(next(p for p in fixtures if D.to_record(p)[0]))

    def test_empty_listing_is_not_a_destination(self):
        p = self.operational()
        for field in ('rating', 'userRatingCount', 'regularOpeningHours', 'websiteUri'):
            p.pop(field, None)
        self.assertEqual(D.to_record(p)[1], 'unsubstantiated listing')

    def test_grocery_aliases_and_independent_bakery(self):
        for name in ("BJ's Bakery", 'WFM Coffee Bar', 'Food Lion Bakery'):
            self.assertTrue(D.is_grocery(name), name)
        self.assertFalse(D.is_grocery('BJ Coffee'))

    def test_location_and_number_stripping_cannot_form_a_generic_chain(self):
        counts = {'coffee': 40, 'cafe': 40}
        for name in ('404 Coffee', '360 Café', 'Smyrna Coffee', 'Cafe 400'):
            self.assertEqual(D.model_for(name, counts), 'independent', name)
        for name in ('Five Daughters Bakery | Medley', 'Great American Cookies - WEST COBB', 'Möge Tee', 'Peach Cobbler Factory Fairburn'):
            self.assertEqual(D.model_for(name), 'franchise', name)

    def test_missing_and_collapsed_ratings_retain_dated_observation(self):
        p = self.operational()
        pid = p['id']
        prior = {pid: {'rating': 4.6, 'ratingNum': 600, 'ratingCount': '600', 'ratingCheckedMonth': 'September 2026'}}
        for count in (None, 0, 20):
            p['userRatingCount'] = count
            p['rating'] = None if count is None else 4.9
            recs, _ = D.build_places({pid: p}, previous=prior)
            self.assertEqual(recs[0]['ratingNum'], 600)
            self.assertEqual(recs[0]['rating'], 4.6)
            self.assertEqual(recs[0]['ratingCheckedMonth'], 'September 2026')
        p['userRatingCount'] = 650
        p['rating'] = 4.7
        recs, _ = D.build_places({pid: p}, previous=prior)
        self.assertEqual(recs[0]['ratingNum'], 650)
        self.assertNotIn('ratingRefreshIssue', recs[0])

    def test_unverified_hours_do_not_recommend_midnight(self):
        p = self.operational()
        recs, _ = D.build_places({p['id']: p}, curations={p['id']: {'hoursUnverified': True}})
        self.assertTrue(recs[0]['hoursUnverified'])
        self.assertNotIn('late', recs[0])
