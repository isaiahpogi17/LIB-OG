# config.py — Library Agent System
# Adjustable constants. Change values here; all agents and tools pick them up automatically.

# --- Fine / Fee settings ---
LATE_FEE_RATE = 5.00          # PHP per day overdue
LATE_FEE_CAP = 500.00         # PHP maximum fee per item
GRACE_PERIOD_DAYS = 1         # Days after due date before fee starts accruing

# --- Booking policy ---
MAX_WEEKLY_BOOKING_HOURS = 10          # Hours per student per week
MAX_SINGLE_BOOKING_HOURS = 4          # Maximum duration per booking (hours)
MIN_ADVANCE_BOOKING_MINUTES = 30      # Must book at least this far in advance
OVERDUE_SUSPENSION_DAYS = 14          # Days overdue before student is blocked from booking

# --- Inventory thresholds ---
LOW_CIRCULATION_CHECKOUTS = 2         # Fewer than this in past year = low circulation
HIGH_DEMAND_CHECKOUTS = 10            # More than this = high demand

# --- Database ---
DB_PATH = "library.db"
