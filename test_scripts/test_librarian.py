"""
test_librarian.py — Tests for Semantic Librarian tools
Tests: search_books, get_book_abstract, suggest_related, check_availability

Run from project root:
    python test_scripts/test_librarian.py
"""

import json
import subprocess
import sys
import unittest


def call(function, **kwargs):
    """Call tools.py via CLI, return parsed JSON output."""
    args = ["python", "tools.py", function]
    for k, v in kwargs.items():
        args += [f"--{k}", str(v)]
    result = subprocess.run(args, capture_output=True, text=True)
    return json.loads(result.stdout), result.returncode


class TestSearchBooks(unittest.TestCase):

    def test_fuzzy_search_returns_results(self):
        data, code = call("search_books", query="machine learning", fuzzy="true")
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0, "Expected at least one result for 'machine learning'")

    def test_fuzzy_search_result_has_required_fields(self):
        data, _ = call("search_books", query="machine learning", fuzzy="true")
        book = data[0]
        for field in ("book_id", "title", "author", "available_copies", "status"):
            self.assertIn(field, book, f"Missing field: {field}")

    def test_fuzzy_search_by_genre(self):
        data, code = call("search_books", query="philosophy", fuzzy="true")
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)

    def test_search_no_results_returns_empty_list(self):
        data, code = call("search_books", query="zzznomatchzzz", fuzzy="true")
        self.assertEqual(code, 0)
        self.assertEqual(data, [])

    def test_exact_search_known_title(self):
        data, code = call("search_books", query="Introduction to Machine Learning", fuzzy="false")
        self.assertEqual(code, 0)
        self.assertGreater(len(data), 0)
        self.assertEqual(data[0]["title"], "Introduction to Machine Learning")

    def test_exact_search_no_match_returns_empty(self):
        data, code = call("search_books", query="Nonexistent Book Title XYZ", fuzzy="false")
        self.assertEqual(code, 0)
        self.assertEqual(data, [])


class TestGetBookAbstract(unittest.TestCase):

    def test_valid_book_returns_abstract(self):
        data, code = call("get_book_abstract", book_id=1)
        self.assertEqual(code, 0)
        for field in ("book_id", "title", "author", "abstract"):
            self.assertIn(field, data)

    def test_invalid_book_returns_error(self):
        data, code = call("get_book_abstract", book_id=9999)
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)


class TestSuggestRelated(unittest.TestCase):

    def test_returns_up_to_3_books(self):
        data, code = call("suggest_related", book_id=1)
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)
        self.assertLessEqual(len(data), 3)

    def test_does_not_include_source_book(self):
        data, code = call("suggest_related", book_id=1)
        self.assertEqual(code, 0)
        ids = [b["book_id"] for b in data]
        self.assertNotIn(1, ids, "suggest_related should not return the source book itself")

    def test_invalid_book_returns_error(self):
        data, code = call("suggest_related", book_id=9999)
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)


class TestCheckAvailability(unittest.TestCase):

    def test_valid_book_returns_availability(self):
        data, code = call("check_availability", book_id=1)
        self.assertEqual(code, 0)
        for field in ("book_id", "title", "available_copies", "status"):
            self.assertIn(field, data)

    def test_available_copies_is_non_negative(self):
        data, _ = call("check_availability", book_id=1)
        self.assertGreaterEqual(data["available_copies"], 0)

    def test_repair_book_has_repair_status(self):
        # book_id 27 is seeded as 'repair'
        data, code = call("check_availability", book_id=27)
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "repair")

    def test_invalid_book_returns_error(self):
        data, code = call("check_availability", book_id=9999)
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)


if __name__ == "__main__":
    print("=" * 60)
    print("LIBRARIAN AGENT — Tool Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
