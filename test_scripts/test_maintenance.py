"""
test_maintenance.py — Tests for Maintenance & Inventory Agent tools
Tests: get_overdue_loans, calculate_late_fee, create_damage_ticket,
       get_inventory_health, has_overdue_items, generate_fine_notice

Run from project root:
    python test_scripts/test_maintenance.py
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


class TestGetOverdueLoans(unittest.TestCase):

    def test_all_overdue_returns_list(self):
        data, code = call("get_overdue_loans")
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0, "Expected overdue loans in seeded data")

    def test_overdue_loan_has_required_fields(self):
        data, _ = call("get_overdue_loans")
        loan = data[0]
        for field in ("loan_id", "user_id", "user_name", "title", "due_date", "days_overdue", "late_fee"):
            self.assertIn(field, loan, f"Missing field: {field}")

    def test_late_fee_is_non_negative(self):
        data, _ = call("get_overdue_loans")
        for loan in data:
            self.assertGreaterEqual(loan["late_fee"], 0)

    def test_late_fee_does_not_exceed_cap(self):
        data, _ = call("get_overdue_loans")
        for loan in data:
            self.assertLessEqual(loan["late_fee"], 500.00, "Fee exceeded PHP 500 cap")

    def test_filter_by_user_id(self):
        # user_id 2 (Ben Santos) has overdue loans
        data, code = call("get_overdue_loans", user_id=2)
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)
        for loan in data:
            self.assertEqual(loan["user_id"], 2)

    def test_user_without_overdue_returns_empty(self):
        # user_id 4 (David Cruz) — seeded with no overdue items
        data, code = call("get_overdue_loans", user_id=4)
        self.assertEqual(code, 0)
        self.assertEqual(data, [])


class TestCalculateLateFee(unittest.TestCase):

    def test_valid_loan_returns_fee(self):
        # Get an overdue loan_id first
        overdue, _ = call("get_overdue_loans")
        if not overdue:
            self.skipTest("No overdue loans in database")
        loan_id = overdue[0]["loan_id"]
        data, code = call("calculate_late_fee", loan_id=loan_id)
        self.assertEqual(code, 0)
        self.assertIn("loan_id", data)
        self.assertIn("late_fee", data)
        self.assertIn("days_overdue", data)
        self.assertEqual(data["currency"], "PHP")

    def test_fee_respects_cap(self):
        overdue, _ = call("get_overdue_loans")
        if not overdue:
            self.skipTest("No overdue loans in database")
        loan_id = overdue[0]["loan_id"]
        data, _ = call("calculate_late_fee", loan_id=loan_id)
        self.assertLessEqual(data["late_fee"], 500.00)

    def test_fee_is_non_negative(self):
        overdue, _ = call("get_overdue_loans")
        if not overdue:
            self.skipTest("No overdue loans in database")
        loan_id = overdue[0]["loan_id"]
        data, _ = call("calculate_late_fee", loan_id=loan_id)
        self.assertGreaterEqual(data["late_fee"], 0)

    def test_invalid_loan_returns_error(self):
        data, code = call("calculate_late_fee", loan_id=99999)
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)


class TestHasOverdueItems(unittest.TestCase):

    def test_user_with_overdue_returns_true(self):
        # user_id 2 (Ben Santos) — seeded with overdue items
        data, code = call("has_overdue_items", user_id=2)
        self.assertEqual(code, 0)
        self.assertTrue(data["has_overdue"])
        self.assertGreater(data["max_days_overdue"], 0)

    def test_user_without_overdue_returns_false(self):
        # user_id 4 (David Cruz) — clean record
        data, code = call("has_overdue_items", user_id=4)
        self.assertEqual(code, 0)
        self.assertFalse(data["has_overdue"])
        self.assertEqual(data["max_days_overdue"], 0)

    def test_suspended_user_overdue_exceeds_14_days(self):
        # user_id 2 (Ben Santos) — suspended, overdue > 14 days
        data, code = call("has_overdue_items", user_id=2)
        self.assertEqual(code, 0)
        self.assertGreater(data["max_days_overdue"], 14, "Expected suspension-level overdue (>14 days)")

    def test_result_has_required_fields(self):
        data, _ = call("has_overdue_items", user_id=1)
        for field in ("user_id", "has_overdue", "max_days_overdue"):
            self.assertIn(field, data)


class TestCreateDamageTicket(unittest.TestCase):

    def test_creates_ticket_and_updates_book_status(self):
        # Use a book that is currently available (not already on repair)
        data, code = call(
            "create_damage_ticket",
            book_id=5,
            description="Cover torn during testing",
            reported_by=6,
        )
        self.assertEqual(code, 0, f"Expected success but got: {data}")
        self.assertIn("ticket_id", data)
        self.assertEqual(data["book_status"], "repair")

    def test_available_copies_decremented(self):
        # Check copies before
        before, _ = call("check_availability", book_id=6)
        before_copies = before["available_copies"]

        call("create_damage_ticket", book_id=6, description="Spine damaged", reported_by=6)

        after, _ = call("check_availability", book_id=6)
        self.assertLessEqual(after["available_copies"], before_copies)

    def test_invalid_book_returns_error(self):
        data, code = call("create_damage_ticket", book_id=99999, description="Test")
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)


class TestGetInventoryHealth(unittest.TestCase):

    def test_returns_low_and_high_demand(self):
        data, code = call("get_inventory_health")
        self.assertEqual(code, 0)
        self.assertIn("low_circulation", data)
        self.assertIn("high_demand", data)

    def test_low_circulation_is_list(self):
        data, _ = call("get_inventory_health")
        self.assertIsInstance(data["low_circulation"], list)

    def test_high_demand_is_list(self):
        data, _ = call("get_inventory_health")
        self.assertIsInstance(data["high_demand"], list)

    def test_books_have_required_fields(self):
        data, _ = call("get_inventory_health")
        if data["low_circulation"]:
            book = data["low_circulation"][0]
            for field in ("book_id", "title", "author", "checkout_count"):
                self.assertIn(field, book)


class TestGenerateFineNotice(unittest.TestCase):

    def test_user_with_overdue_returns_notice(self):
        data, code = call("generate_fine_notice", user_id=2)
        self.assertEqual(code, 0)
        self.assertIn("notice", data)
        notice = data["notice"]
        self.assertIn("OVERDUE NOTICE", notice)
        self.assertIn("PHP", notice)

    def test_user_without_overdue_returns_clean_notice(self):
        data, code = call("generate_fine_notice", user_id=4)
        self.assertEqual(code, 0)
        self.assertIn("notice", data)
        self.assertIn("No overdue", data["notice"])

    def test_invalid_user_returns_error(self):
        data, code = call("generate_fine_notice", user_id=99999)
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)

    def test_notice_includes_user_name(self):
        data, _ = call("generate_fine_notice", user_id=2)
        self.assertIn("Ben Santos", data["notice"])


if __name__ == "__main__":
    print("=" * 60)
    print("MAINTENANCE & INVENTORY AGENT — Tool Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
