import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refresh_ratings as RR


def _ok_response(payload='{"places": []}'):
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    cm = MagicMock()
    cm.__enter__.return_value = mock_resp
    return cm


class RequestAccountingTests(unittest.TestCase):
    def test_success_records_once(self):
        with (
            patch("refresh_ratings.places_ledger") as mock_ledger,
            patch("urllib.request.urlopen", return_value=_ok_response()),
        ):
            out = RR._request("k", "http://x", {"q": 1}, "m", sku="text_search_enterprise")
            self.assertEqual(out, {"places": []})
            mock_ledger.record.assert_called_once_with("text_search_enterprise")

    def test_record_failure_aborts_instead_of_spending_blind(self):
        """Gap 1: uncounted spend must stop the run, not just log a warning."""
        with (
            patch("refresh_ratings.places_ledger") as mock_ledger,
            patch("urllib.request.urlopen", return_value=_ok_response()),
        ):
            mock_ledger.record.side_effect = OSError("disk full")
            with self.assertRaises(RR.FatalApiError) as cm:
                RR._request("k", "http://x", {"q": 1}, "m", sku="text_search_enterprise")
            self.assertIn("stopping before further paid calls", str(cm.exception))

    def test_pre_counted_skips_record(self):
        """Calls reserved up front (discover pass 2) must not be counted twice."""
        with (
            patch("refresh_ratings.places_ledger") as mock_ledger,
            patch("urllib.request.urlopen", return_value=_ok_response()),
        ):
            out = RR._request("k", "http://x", {"q": 1}, "m",
                              sku="text_search_enterprise", pre_counted=True)
            self.assertEqual(out, {"places": []})
            mock_ledger.record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
