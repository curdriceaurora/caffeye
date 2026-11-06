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

    def test_location_count_alone_does_not_make_a_chain(self):
        for name in ('404 Coffee', 'Smyrna Coffee', 'Tier Couture Bakery Norcross', 'Brew Coffee and Tea Bar'):
            self.assertEqual(D.model_for(name), 'independent', name)
        self.assertEqual(D.model_for('7 Brew Coffee'), 'franchise')
        self.assertEqual(D.model_for('Great American cookie Upper level'), 'franchise')
        self.assertEqual(D.model_for("Menchie's Frozen Yogurt FB"), 'franchise')

    def test_verified_registry_outranks_location_count(self):
        chains = ('Foxtail Coffee - Midtown', 'Foxtail Coffee Co', 'Yogli Mogli Dunwoody', 'Boarding Pass Coffee Gainesville',
                  'Dancing Goats Midtown', 'Dancing goats', "Kaldi's Coffee Clough", "Depot by Kaldi's Coffee")
        local = ('Queen Tea （Kennesaw)', 'Queen Tea GSU', 'Spiller Park Coffee "SP1"', 'Chattahoochee Coffee Company - Riverside',
                 'Bellwood Coffee - Decatur', 'Condesa Coffee', 'The Little Tart Bakeshop')
        for name in chains:
            self.assertEqual(D.model_for(name), 'franchise', name)
        for name in local:
            self.assertEqual(D.model_for(name), 'independent', name)

    def test_chain_records_carry_scope_and_only_verified_franchising(self):
        p = self.operational()
        for name, scope, program in (('Dancing Goats Midtown', 'regional', None), ('Foxtail Coffee - Midtown', 'national', True)):
            p['displayName'] = {'text': name}
            rec = D.to_record(p)[0]
            self.assertEqual((rec['chainScope'], rec['franchiseProgram']), (scope, program))
        p['displayName'] = {'text': 'Bellwood Coffee - Decatur'}
        self.assertNotIn('chainScope', D.to_record(p)[0])

    def test_unverified_multi_location_brands_are_leads_not_chains(self):
        names = ['Refuge Coffee Co. Midtown', 'Refuge Coffee Co. Decatur', 'Refuge Coffee Co. Norcross',
                 'Cakes by Niecy', 'Cakes by Rae', 'Cakes by Alps', 'Foxtail Coffee', 'Foxtail Coffee - A', 'Foxtail Coffee - B',
                 'Queen Tea GSU', 'Queen Tea', 'Queen Tea (Midtown)', 'Valor Coffee', 'Valor Coffee - Midtown']
        self.assertEqual(D.brand_leads(names), [('refuge coffee', 3)])
        self.assertEqual(D.model_for('Refuge Coffee Co. Midtown'), 'independent')

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
