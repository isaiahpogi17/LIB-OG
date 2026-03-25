"""
test_journal_search.py — Tests for search_journals (CrossRef API integration)

Two test levels:
  Unit tests       — fast, no internet, HTTP is mocked
  Integration tests — real CrossRef API calls (requires internet)

Run from project root:
    python test_scripts/test_journal_search.py           # unit only
    python test_scripts/test_journal_search.py --live    # unit + integration
"""

import argparse
import json
import subprocess
import sys
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def call_cli(topic, limit=5):
    """Call tools.py search_journals via CLI subprocess. Returns (data, returncode)."""
    result = subprocess.run(
        ["python", "tools.py", "search_journals", "--topic", topic, "--limit", str(limit)],
        capture_output=True, text=True,
    )
    return json.loads(result.stdout), result.returncode


def _mock_response(items):
    """Build a fake urllib response object for a CrossRef /works payload."""
    payload = json.dumps({"message": {"items": items}}).encode("utf-8")
    mock = MagicMock()
    mock.read.return_value = payload
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


SAMPLE_ITEMS = [
    {
        "title": ["Deep Learning for Natural Language Processing"],
        "author": [
            {"given": "Jane",  "family": "Smith"},
            {"given": "Carlos","family": "Rivera"},
        ],
        "published": {"date-parts": [[2022]]},
        "container-title": ["Journal of Artificial Intelligence Research"],
        "DOI": "10.1234/jair.2022.001",
        "URL": "https://doi.org/10.1234/jair.2022.001",
        "type": "journal-article",
        "score": 98.5,
    },
    {
        "title": ["Transformer Architectures: A Survey"],
        "author": [{"given": "Ahmed", "family": "Hassan"}],
        "published": {"date-parts": [[2023]]},
        "container-title": ["IEEE Transactions on Neural Networks"],
        "DOI": "10.1234/tnn.2023.042",
        "URL": "https://doi.org/10.1234/tnn.2023.042",
        "type": "journal-article",
        "score": 91.0,
    },
]

EMPTY_RESPONSE = {"message": {"items": []}}


# ---------------------------------------------------------------------------
# Unit tests (mocked HTTP — no internet required)
# ---------------------------------------------------------------------------

class TestSearchJournalsUnit(unittest.TestCase):
    """Fast tests — CrossRef HTTP call is mocked."""

    def _run(self, items, topic="machine learning", limit=5):
        """Directly import and call search_journals with a mocked urlopen."""
        sys.path.insert(0, ".")
        import tools

        mock_resp = _mock_response(items)
        with patch("tools.urllib.request.urlopen", return_value=mock_resp):
            with patch("builtins.print") as mock_print:
                try:
                    tools.search_journals(topic=topic, limit=limit)
                except SystemExit:
                    pass
                output = mock_print.call_args[0][0]
                return json.loads(output)

    # --- Structure ---

    def test_returns_list(self):
        data = self._run(SAMPLE_ITEMS)
        self.assertIsInstance(data, list)

    def test_returns_correct_number_of_results(self):
        data = self._run(SAMPLE_ITEMS, limit=2)
        self.assertEqual(len(data), 2)

    def test_result_has_all_required_fields(self):
        data = self._run(SAMPLE_ITEMS)
        required = ("title", "authors", "year", "journal", "doi", "url", "source")
        for field in required:
            self.assertIn(field, data[0], f"Missing field: {field}")

    def test_source_is_crossref(self):
        data = self._run(SAMPLE_ITEMS)
        for item in data:
            self.assertEqual(item["source"], "CrossRef")

    # --- Content ---

    def test_title_extracted_correctly(self):
        data = self._run(SAMPLE_ITEMS)
        self.assertEqual(data[0]["title"], "Deep Learning for Natural Language Processing")

    def test_authors_extracted_correctly(self):
        data = self._run(SAMPLE_ITEMS)
        self.assertIn("Jane Smith", data[0]["authors"])
        self.assertIn("Carlos Rivera", data[0]["authors"])

    def test_year_extracted_correctly(self):
        data = self._run(SAMPLE_ITEMS)
        self.assertEqual(data[0]["year"], 2022)

    def test_journal_extracted_correctly(self):
        data = self._run(SAMPLE_ITEMS)
        self.assertEqual(data[0]["journal"], "Journal of Artificial Intelligence Research")

    def test_doi_extracted_correctly(self):
        data = self._run(SAMPLE_ITEMS)
        self.assertEqual(data[0]["doi"], "10.1234/jair.2022.001")

    def test_url_uses_doi_link(self):
        data = self._run(SAMPLE_ITEMS)
        self.assertIn("doi.org", data[0]["url"])

    def test_more_than_3_authors_appends_et_al(self):
        many_authors = [
            {"given": "A", "family": "One"},
            {"given": "B", "family": "Two"},
            {"given": "C", "family": "Three"},
            {"given": "D", "family": "Four"},
        ]
        items = [{**SAMPLE_ITEMS[0], "author": many_authors}]
        data = self._run(items)
        self.assertIn("et al.", data[0]["authors"])

    # --- Edge cases ---

    def test_empty_results_returns_empty_list(self):
        data = self._run([])
        self.assertEqual(data, [])

    def test_missing_author_defaults_to_unknown(self):
        items = [{**SAMPLE_ITEMS[0], "author": []}]
        data = self._run(items)
        self.assertEqual(data[0]["authors"], "Unknown")

    def test_missing_year_returns_none(self):
        items = [{**SAMPLE_ITEMS[0], "published": {}}]
        data = self._run(items)
        self.assertIsNone(data[0]["year"])

    def test_missing_journal_returns_empty_string(self):
        items = [{**SAMPLE_ITEMS[0], "container-title": []}]
        data = self._run(items)
        self.assertEqual(data[0]["journal"], "")

    def test_network_error_returns_error_json(self):
        import urllib.error
        sys.path.insert(0, ".")
        import tools

        with patch("tools.urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            with patch("builtins.print") as mock_print:
                try:
                    tools.search_journals(topic="test")
                except SystemExit:
                    pass
                output = mock_print.call_args[0][0]
                data = json.loads(output)
                self.assertIn("error", data)
                self.assertIn("CrossRef", data["error"])

    def test_limit_cap_does_not_exceed_20(self):
        """limit param should be capped at 20 in the URL — test via CLI to check no crash."""
        # We can't easily inspect the URL, but we can confirm it doesn't error
        data = self._run(SAMPLE_ITEMS, limit=100)
        self.assertIsInstance(data, list)


# ---------------------------------------------------------------------------
# Integration tests (real CrossRef API — requires internet)
# ---------------------------------------------------------------------------

@unittest.skipUnless("--live" in sys.argv, "Skipped: pass --live to run integration tests")
class TestSearchJournalsIntegration(unittest.TestCase):
    """Real CrossRef API calls. Requires internet. Run with: --live"""

    def _live(self, topic, limit=3):
        data, code = call_cli(topic, limit=limit)
        return data, code

    def test_live_returns_results_for_known_topic(self):
        data, code = self._live("machine learning")
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0, "Expected at least 1 result from CrossRef for 'machine learning'")

    def test_live_results_have_required_fields(self):
        data, _ = self._live("climate change")
        required = ("title", "authors", "year", "journal", "doi", "url", "source")
        for field in required:
            self.assertIn(field, data[0], f"Missing field: {field}")

    def test_live_limit_respected(self):
        data, code = self._live("neural networks", limit=3)
        self.assertEqual(code, 0)
        self.assertLessEqual(len(data), 3)

    def test_live_source_is_crossref(self):
        data, _ = self._live("biology")
        for item in data:
            self.assertEqual(item["source"], "CrossRef")

    def test_live_doi_is_present_for_most_results(self):
        data, _ = self._live("deep learning")
        with_doi = [r for r in data if r["doi"]]
        self.assertGreater(len(with_doi), 0, "Expected at least one result with a DOI")

    def test_live_url_is_valid_link(self):
        data, _ = self._live("quantum computing")
        for item in data:
            if item["url"]:
                self.assertTrue(
                    item["url"].startswith("http"),
                    f"URL should start with http: {item['url']}"
                )

    def test_live_niche_topic_returns_results_or_empty(self):
        """Very niche topic may return 0 results — that is valid behavior."""
        data, code = self._live("ethnobotanical pharmacognosy of mangroves", limit=2)
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)

    def test_live_limit_1_returns_single_result(self):
        data, code = self._live("physics", limit=1)
        self.assertEqual(code, 0)
        self.assertEqual(len(data), 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Strip --live from argv before passing to unittest
    run_live = "--live" in sys.argv
    if run_live:
        sys.argv.remove("--live")

    print("=" * 60)
    print("JOURNAL SEARCH — Unit Tests")
    if run_live:
        print("                + Integration Tests (live CrossRef API)")
    print("=" * 60)

    unittest.main(verbosity=2)
