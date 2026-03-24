# Library Agent System

A CLI-based multi-agent application built on Claude Code. Four specialized AI agents collaborate through a shared SQLite database to handle common library tasks.

## Agents

| Agent | Handles |
|-------|---------|
| **Orchestrator** | Routes all requests to the right agent |
| **Semantic Librarian** | Book search and recommendations |
| **Space Manager** | Study room and pod bookings |
| **Digital Resource Navigator** | Research databases and citations |
| **Maintenance & Inventory** | Overdue items, fines, damage reports |

---

## Requirements

- Python 3.9+
- Claude Code CLI (`claude`) installed and authenticated

---

## Setup

**1. Install dependencies**

No external Python packages required — uses the standard library only.

**2. Seed the database**

```bash
python seed_db.py
```

This creates `library.db` with all tables and mock data. Re-running will reset the database.

**3. Start the system**

```bash
claude
```

Claude Code reads `CLAUDE.md` on startup and acts as the orchestrator. Enter your Student/Staff ID when prompted.

---

## Example queries

```
Find me a beginner-friendly book on machine learning
Do you have anything like Dune but more political?
Book a quiet pod for 2 people at 3 PM tomorrow
Cancel my booking for Thursday
Give me an APA citation for this URL: https://example.com/paper
What database should I use for biomedical research?
Show me all students with overdue books
How much do I owe in late fees?
my bookings
my loans
help
```

---

## File Structure

```
library-agent-system/
├── .claude/
│   └── agents/
│       ├── orchestrator.md      # Entry point agent
│       ├── librarian.md         # Semantic Librarian
│       ├── space-manager.md     # Space Manager
│       ├── navigator.md         # Digital Resource Navigator
│       └── maintenance.md       # Maintenance & Inventory
│
├── CLAUDE.md                    # Claude Code entry point config
├── config.py                    # Adjustable constants (fees, limits)
├── tools.py                     # All Python helper functions
├── seed_db.py                   # Creates and seeds library.db
├── library.db                   # SQLite database (generated)
└── README.md                    # This file
```

---

## Adjusting policy settings

Edit [config.py](config.py) to change:

| Setting | Default | Description |
|---------|---------|-------------|
| `LATE_FEE_RATE` | PHP 5.00/day | Daily overdue fee rate |
| `LATE_FEE_CAP` | PHP 500.00 | Maximum fee per item |
| `GRACE_PERIOD_DAYS` | 1 day | Days before fee starts |
| `MAX_WEEKLY_BOOKING_HOURS` | 10 hours | Booking limit per student per week |
| `MAX_SINGLE_BOOKING_HOURS` | 4 hours | Maximum single booking duration |
| `OVERDUE_SUSPENSION_DAYS` | 14 days | Days overdue before booking is blocked |

---

## Calling tools directly (for testing)

```bash
python tools.py search_books --query "machine learning"
python tools.py get_overdue_loans
python tools.py has_overdue_items --user_id 2
python tools.py check_room_availability --date 2026-03-26 --time 14:00 --capacity 2
python tools.py get_inventory_health
```

All functions output JSON to stdout.

---

## Mock data summary

| Table | Rows | Key edge cases |
|-------|------|---------------|
| Users | 15 | 3 with overdue loans; 1 suspended (Ben, user 2) |
| Books | 30 | Mix of genres; 2 on repair (book 27, 28); some unavailable |
| Loans | 25 | Mix of active, returned, and overdue |
| Rooms | 8 | Pods, group rooms, computer lab across 3 floors |
| Bookings | 20 | 2 users near weekly limit; suspended user has upcoming bookings |
| Tickets | 10 | Mix of open, in-progress, and resolved |
