import json
import tempfile
import unittest
from pathlib import Path
from audit_snapshot import audit
from release_preflight import assess, https

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'native/Caffeye/Resources/venues.json'


class ReleaseChecks(unittest.TestCase):
    def test_default_approval_cannot_pass(self):
        approval = json.loads((ROOT / 'native/release/approval.example.json').read_text())
        report = assess(SNAPSHOT, approval, ROOT)
        self.assertFalse(report['preflightPassed'])
        self.assertTrue(all(value is False for value in report['checks'].values()))

    def test_approval_is_bound_to_exact_dataset_and_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / 'review.md').write_text('Test evidence only; not actual permission.')
            approval = {'datasetSHA256': audit(SNAPSHOT)['datasetSHA256'], 'redistributionReviewed': True,
                        'redistributionEvidencePath': 'review.md'}
            self.assertTrue(assess(SNAPSHOT, approval, base)['checks']['datasetReview'])
            approval['datasetSHA256'] = 'changed'
            self.assertFalse(assess(SNAPSHOT, approval, base)['checks']['datasetReview'])
            approval['datasetSHA256'] = audit(SNAPSHOT)['datasetSHA256']
            approval['redistributionReviewed'] = 'true'
            self.assertFalse(assess(SNAPSHOT, approval, base)['checks']['datasetReview'])
            self.assertFalse(assess(SNAPSHOT, approval, base)['preflightPassed'])

    def test_inventory_keeps_coordinate_sources_separate(self):
        fields = audit(SNAPSHOT)['fieldSources']
        self.assertEqual(fields['coordinate']['Apple geocoding (curated seed)'], 61)
        self.assertEqual(fields['coordinate']['Google Places place pin'], 1644)
        self.assertNotIn('rating', fields)
        self.assertFalse(https('http://example.com'))
        self.assertFalse(https('https://user:pass@example.com'))
        self.assertTrue(https('https://example.com/privacy'))
