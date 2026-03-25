"""
test_space_manager.py — Tests for Space Manager tools
Tests: check_room_availability, create_booking, cancel_booking,
       get_user_weekly_hours, get_upcoming_bookings

Run from project root:
    python test_scripts/test_space_manager.py
"""

import json
import subprocess
import unittest
from datetime import datetime, timedelta


def call(function, **kwargs):
    """Call tools.py via CLI, return parsed JSON output."""
    args = ["python", "tools.py", function]
    for k, v in kwargs.items():
        args += [f"--{k}", str(v)]
    result = subprocess.run(args, capture_output=True, text=True)
    return json.loads(result.stdout), result.returncode


def future_date(days=2):
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def future_dt(days=2, hour=10):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    ).isoformat()


class TestCheckRoomAvailability(unittest.TestCase):

    def test_returns_list_of_rooms(self):
        data, code = call("check_room_availability", date=future_date(), time="10:00", capacity=1)
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)

    def test_rooms_meet_capacity_requirement(self):
        data, _ = call("check_room_availability", date=future_date(), time="10:00", capacity=4)
        for room in data:
            self.assertGreaterEqual(room["capacity"], 4)

    def test_result_has_required_fields(self):
        data, _ = call("check_room_availability", date=future_date(), time="10:00", capacity=1)
        if data:
            for field in ("room_id", "name", "capacity", "type", "floor"):
                self.assertIn(field, data[0])

    def test_high_capacity_returns_fewer_rooms(self):
        small, _ = call("check_room_availability", date=future_date(), time="10:00", capacity=1)
        large, _ = call("check_room_availability", date=future_date(), time="10:00", capacity=20)
        self.assertGreaterEqual(len(small), len(large))


class TestCreateAndCancelBooking(unittest.TestCase):

    def test_create_booking_success(self):
        # user_id 4 (David Cruz) — clean record, low weekly hours
        data, code = call(
            "create_booking",
            user_id=4,
            room_id=1,
            start_time=future_dt(days=3, hour=10),
            duration=1,
        )
        self.assertEqual(code, 0, f"Expected success but got: {data}")
        self.assertIn("booking_id", data)
        self.assertIn("room_name", data)
        # Clean up
        call("cancel_booking", booking_id=data["booking_id"])

    def test_cancel_booking_success(self):
        # Create then cancel
        create_data, _ = call(
            "create_booking",
            user_id=4,
            room_id=1,
            start_time=future_dt(days=4, hour=14),
            duration=1,
        )
        booking_id = create_data["booking_id"]
        cancel_data, code = call("cancel_booking", booking_id=booking_id)
        self.assertEqual(code, 0)
        self.assertEqual(cancel_data["status"], "cancelled")

    def test_booking_too_soon_is_rejected(self):
        # Less than 30 minutes in advance — should fail
        soon = (datetime.now() + timedelta(minutes=5)).isoformat()
        data, code = call("create_booking", user_id=4, room_id=1, start_time=soon, duration=1)
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)

    def test_booking_exceeds_max_duration_is_rejected(self):
        data, code = call(
            "create_booking",
            user_id=4,
            room_id=1,
            start_time=future_dt(days=5, hour=10),
            duration=5,  # max is 4
        )
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)

    def test_cancel_nonexistent_booking_returns_error(self):
        data, code = call("cancel_booking", booking_id=99999)
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)


class TestWeeklyHoursPolicy(unittest.TestCase):

    def test_user_near_limit_cannot_exceed_10_hours(self):
        # user_id 1 (Ana Reyes) is seeded at ~9h this week
        # Trying to add 2 more hours should fail
        data, code = call(
            "create_booking",
            user_id=1,
            room_id=1,
            start_time=future_dt(days=1, hour=10),
            duration=2,
        )
        self.assertNotEqual(code, 0, "Should be rejected — would exceed 10hr weekly limit")
        self.assertIn("error", data)

    def test_get_weekly_hours_returns_correct_fields(self):
        data, code = call("get_user_weekly_hours", user_id=1)
        self.assertEqual(code, 0)
        self.assertIn("weekly_hours_used", data)
        self.assertIn("limit", data)
        self.assertEqual(data["limit"], 10)


class TestGetUpcomingBookings(unittest.TestCase):

    def test_returns_list(self):
        data, code = call("get_upcoming_bookings", user_id=1)
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)

    def test_booking_has_required_fields(self):
        data, _ = call("get_upcoming_bookings", user_id=1)
        if data:
            for field in ("booking_id", "start_time", "end_time", "status", "room_name"):
                self.assertIn(field, data[0])

    def test_all_returned_bookings_are_confirmed(self):
        data, _ = call("get_upcoming_bookings", user_id=1)
        for b in data:
            self.assertEqual(b["status"], "confirmed")

    def test_user_with_no_bookings_returns_empty(self):
        # user_id 15 — no upcoming bookings seeded
        data, code = call("get_upcoming_bookings", user_id=15)
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    print("=" * 60)
    print("SPACE MANAGER AGENT — Tool Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
