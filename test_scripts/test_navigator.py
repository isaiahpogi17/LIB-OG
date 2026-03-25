"""
test_navigator.py — Tests for Digital Resource Navigator tools
Tests: match_database, detect_source_type, format_apa_citation, format_mla_citation

Run from project root:
    python test_scripts/test_navigator.py
"""

import json
import subprocess
import unittest


def call(function, **kwargs):
    """Call tools.py via CLI, return parsed JSON output."""
    args = ["python", "tools.py", function]
    for k, v in kwargs.items():
        args += [f"--{k}", str(v)]
    result = subprocess.run(args, capture_output=True, text=True)
    return json.loads(result.stdout), result.returncode


class TestMatchDatabase(unittest.TestCase):

    def test_computer_science_returns_ieee(self):
        data, code = call("match_database", topic="computer science networking")
        self.assertEqual(code, 0)
        names = [d["name"] for d in data]
        self.assertIn("IEEE Xplore", names)

    def test_biomedical_returns_pubmed(self):
        data, code = call("match_database", topic="biomedical life sciences")
        self.assertEqual(code, 0)
        names = [d["name"] for d in data]
        self.assertIn("PubMed", names)

    def test_humanities_returns_jstor(self):
        data, code = call("match_database", topic="humanities history philosophy")
        self.assertEqual(code, 0)
        names = [d["name"] for d in data]
        self.assertIn("JSTOR", names)

    def test_unknown_topic_falls_back_to_google_scholar(self):
        data, code = call("match_database", topic="zzzunknownsubjectzzz")
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["name"], "Google Scholar")

    def test_returns_at_most_2_results(self):
        data, code = call("match_database", topic="computer science")
        self.assertEqual(code, 0)
        self.assertLessEqual(len(data), 2)

    def test_result_has_required_fields(self):
        data, _ = call("match_database", topic="biology")
        for field in ("name", "subjects", "access"):
            self.assertIn(field, data[0])


class TestDetectSourceType(unittest.TestCase):

    def test_doi_url_is_article(self):
        data, code = call("detect_source_type", url="https://doi.org/10.1000/xyz123")
        self.assertEqual(code, 0)
        self.assertEqual(data["source_type"], "article")

    def test_pubmed_url_is_article(self):
        data, code = call("detect_source_type", url="https://pubmed.ncbi.nlm.nih.gov/12345678")
        self.assertEqual(code, 0)
        self.assertEqual(data["source_type"], "article")

    def test_generic_url_is_webpage(self):
        data, code = call("detect_source_type", url="https://www.example.com/about")
        self.assertEqual(code, 0)
        self.assertEqual(data["source_type"], "webpage")

    def test_worldcat_url_is_book(self):
        data, code = call("detect_source_type", url="https://worldcat.org/title/12345")
        self.assertEqual(code, 0)
        self.assertEqual(data["source_type"], "book")

    def test_result_has_url_and_type_fields(self):
        data, _ = call("detect_source_type", url="https://example.com")
        self.assertIn("url", data)
        self.assertIn("source_type", data)


class TestFormatApaCitation(unittest.TestCase):

    def test_url_returns_apa_format(self):
        data, code = call("format_apa_citation", source="https://example.com/article")
        self.assertEqual(code, 0)
        self.assertIn("citation", data)
        self.assertIn("APA 7", data["format"])

    def test_url_citation_contains_url(self):
        url = "https://example.com/article"
        data, _ = call("format_apa_citation", source=url)
        self.assertIn(url, data["citation"])

    def test_plain_title_returns_book_format(self):
        data, code = call("format_apa_citation", source="The Great Gatsby")
        self.assertEqual(code, 0)
        self.assertIn("citation", data)
        self.assertIn("The Great Gatsby", data["citation"])

    def test_url_citation_has_retrieved_date(self):
        data, _ = call("format_apa_citation", source="https://example.com")
        self.assertIn("Retrieved", data["citation"])

    def test_includes_note_for_manual_fields(self):
        data, _ = call("format_apa_citation", source="https://example.com")
        self.assertIn("note", data)


class TestFormatMlaCitation(unittest.TestCase):

    def test_url_returns_mla_format(self):
        data, code = call("format_mla_citation", source="https://example.com/article")
        self.assertEqual(code, 0)
        self.assertIn("citation", data)
        self.assertIn("MLA 9", data["format"])

    def test_url_citation_contains_url(self):
        url = "https://example.com/article"
        data, _ = call("format_mla_citation", source=url)
        self.assertIn(url, data["citation"])

    def test_plain_title_returns_book_format(self):
        data, code = call("format_mla_citation", source="To Kill a Mockingbird")
        self.assertEqual(code, 0)
        self.assertIn("To Kill a Mockingbird", data["citation"])

    def test_includes_note_for_manual_fields(self):
        data, _ = call("format_mla_citation", source="https://example.com")
        self.assertIn("note", data)


if __name__ == "__main__":
    print("=" * 60)
    print("NAVIGATOR AGENT — Tool Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
