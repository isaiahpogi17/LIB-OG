"""
tools.py — Library Agent System
All Python helper functions called by agents via CLI dispatch.

Usage:
    python tools.py <function_name> [--arg value ...]

Output is always JSON printed to stdout.
Errors are printed as JSON: {"error": "<message>"}
"""

import argparse
import json
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import config


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_list(rows):
    return [dict(r) for r in rows]


def ok(data):
    print(json.dumps(data, default=str))


def err(message):
    print(json.dumps({"error": message}))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Librarian tools
# ---------------------------------------------------------------------------

def search_books(query: str, fuzzy: bool = True):
    conn = get_connection()
    try:
        if fuzzy:
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT book_id, title, author, genre, tags, available_copies, status
                FROM Books
                WHERE title LIKE ? OR author LIKE ? OR genre LIKE ? OR tags LIKE ?
                ORDER BY available_copies DESC
                """,
                (like, like, like, like),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT book_id, title, author, genre, tags, available_copies, status
                FROM Books
                WHERE title = ?
                """,
                (query,),
            ).fetchall()
        ok(rows_to_list(rows))
    finally:
        conn.close()


def get_book_abstract(book_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT book_id, title, author, abstract FROM Books WHERE book_id = ?",
            (book_id,),
        ).fetchone()
        if not row:
            err(f"Book with id {book_id} not found")
        ok(dict(row))
    finally:
        conn.close()


def suggest_related(book_id: int):
    conn = get_connection()
    try:
        source = conn.execute(
            "SELECT genre, tags FROM Books WHERE book_id = ?", (book_id,)
        ).fetchone()
        if not source:
            err(f"Book with id {book_id} not found")
        rows = conn.execute(
            """
            SELECT book_id, title, author, genre, available_copies, status
            FROM Books
            WHERE book_id != ? AND (genre = ? OR tags LIKE ?)
            LIMIT 3
            """,
            (book_id, source["genre"], f"%{source['tags'].split(',')[0].strip()}%"),
        ).fetchall()
        ok(rows_to_list(rows))
    finally:
        conn.close()


def check_availability(book_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT book_id, title, available_copies, status FROM Books WHERE book_id = ?",
            (book_id,),
        ).fetchone()
        if not row:
            err(f"Book with id {book_id} not found")
        ok(dict(row))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Space Manager tools
# ---------------------------------------------------------------------------

def check_room_availability(date: str, time: str, capacity: int):
    conn = get_connection()
    try:
        start_dt = datetime.fromisoformat(f"{date}T{time}")
        rows = conn.execute(
            """
            SELECT r.room_id, r.name, r.capacity, r.type, r.floor
            FROM Rooms r
            WHERE r.capacity >= ?
              AND r.room_id NOT IN (
                SELECT b.room_id FROM Bookings b
                WHERE b.status = 'confirmed'
                  AND b.start_time < ?
                  AND b.end_time > ?
              )
            ORDER BY r.capacity ASC
            """,
            (capacity, start_dt.isoformat(), start_dt.isoformat()),
        ).fetchall()
        ok(rows_to_list(rows))
    finally:
        conn.close()


def create_booking(user_id: int, room_id: int, start_time: str, duration: float):
    conn = get_connection()
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(hours=duration)
        now = datetime.now()

        # Overdue suspension check (14+ days overdue blocks new bookings)
        overdue_row = conn.execute(
            """
            SELECT MAX(CAST(julianday('now') - julianday(due_date) AS INTEGER)) AS max_days
            FROM Loans
            WHERE user_id = ? AND return_date IS NULL AND status = 'overdue'
            """,
            (user_id,),
        ).fetchone()
        max_days = overdue_row["max_days"] if overdue_row and overdue_row["max_days"] else 0
        if max_days >= config.OVERDUE_SUSPENSION_DAYS:
            err(f"Booking denied: you have an item {max_days} days overdue. Return or resolve overdue items before booking a room.")

        # Advance notice check
        minutes_ahead = (start_dt - now).total_seconds() / 60
        if minutes_ahead < config.MIN_ADVANCE_BOOKING_MINUTES:
            err(f"Bookings must be made at least {config.MIN_ADVANCE_BOOKING_MINUTES} minutes in advance")

        # Max duration check
        if duration > config.MAX_SINGLE_BOOKING_HOURS:
            err(f"Maximum single booking duration is {config.MAX_SINGLE_BOOKING_HOURS} hours")

        # Weekly hours check
        weekly = _compute_weekly_hours(conn, user_id)
        if weekly + duration > config.MAX_WEEKLY_BOOKING_HOURS:
            err(f"Booking would exceed weekly limit of {config.MAX_WEEKLY_BOOKING_HOURS} hours (currently at {weekly}h)")

        conn.execute(
            """
            INSERT INTO Bookings (user_id, room_id, start_time, end_time, status)
            VALUES (?, ?, ?, ?, 'confirmed')
            """,
            (user_id, room_id, start_dt.isoformat(), end_dt.isoformat()),
        )
        conn.commit()
        booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        room = conn.execute(
            "SELECT name, floor FROM Rooms WHERE room_id = ?", (room_id,)
        ).fetchone()
        ok({
            "booking_id": booking_id,
            "room_name": room["name"],
            "floor": room["floor"],
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "weekly_hours_used": weekly + duration,
        })
    finally:
        conn.close()


def cancel_booking(booking_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM Bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
        if not row:
            err(f"Booking {booking_id} not found")
        conn.execute(
            "UPDATE Bookings SET status = 'cancelled' WHERE booking_id = ?",
            (booking_id,),
        )
        conn.commit()
        ok({"booking_id": booking_id, "status": "cancelled"})
    finally:
        conn.close()


def get_user_weekly_hours(user_id: int):
    conn = get_connection()
    try:
        hours = _compute_weekly_hours(conn, user_id)
        ok({"user_id": user_id, "weekly_hours_used": hours, "limit": config.MAX_WEEKLY_BOOKING_HOURS})
    finally:
        conn.close()


def get_upcoming_bookings(user_id: int):
    conn = get_connection()
    try:
        now = datetime.now().isoformat()
        rows = conn.execute(
            """
            SELECT b.booking_id, b.start_time, b.end_time, b.status,
                   r.name AS room_name, r.floor, r.type
            FROM Bookings b
            JOIN Rooms r ON b.room_id = r.room_id
            WHERE b.user_id = ? AND b.start_time >= ? AND b.status = 'confirmed'
            ORDER BY b.start_time ASC
            """,
            (user_id, now),
        ).fetchall()
        ok(rows_to_list(rows))
    finally:
        conn.close()


def _compute_weekly_hours(conn, user_id: int) -> float:
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end = week_start + timedelta(days=7)
    rows = conn.execute(
        """
        SELECT start_time, end_time FROM Bookings
        WHERE user_id = ? AND status = 'confirmed'
          AND start_time >= ? AND start_time < ?
        """,
        (user_id, week_start.isoformat(), week_end.isoformat()),
    ).fetchall()
    total = sum(
        (datetime.fromisoformat(r["end_time"]) - datetime.fromisoformat(r["start_time"])).total_seconds() / 3600
        for r in rows
    )
    return round(total, 2)


# ---------------------------------------------------------------------------
# Navigator tools
# ---------------------------------------------------------------------------

DATABASE_MAP = [
    {"name": "IEEE Xplore", "subjects": ["computer science", "electrical engineering", "hardware", "networking", "software engineering"], "access": "library portal → IEEE Xplore"},
    {"name": "JSTOR", "subjects": ["humanities", "social sciences", "arts", "history", "philosophy", "literature"], "access": "library portal → JSTOR"},
    {"name": "PubMed", "subjects": ["biomedical", "medicine", "biology", "life sciences", "health", "nursing"], "access": "library portal → PubMed (free)"},
    {"name": "ScienceDirect", "subjects": ["natural sciences", "engineering", "chemistry", "physics", "materials"], "access": "library portal → ScienceDirect"},
    {"name": "ProQuest", "subjects": ["multidisciplinary", "theses", "dissertations", "business", "education"], "access": "library portal → ProQuest"},
    {"name": "Google Scholar", "subjects": ["general", "any", "all"], "access": "scholar.google.com (free, no login required)"},
]


def match_database(topic: str):
    topic_lower = topic.lower()
    matches = []
    for db in DATABASE_MAP:
        score = sum(1 for s in db["subjects"] if s in topic_lower)
        if score > 0:
            matches.append({**db, "score": score})
    matches.sort(key=lambda x: x["score"], reverse=True)
    if not matches:
        fallback = DATABASE_MAP[-1]
        ok([{**fallback, "note": "No specific match found — defaulting to Google Scholar"}])
    else:
        ok([{k: v for k, v in m.items() if k != "score"} for m in matches[:2]])


def detect_source_type(url: str):
    url_lower = url.lower()
    if any(x in url_lower for x in ["doi.org", "journal", "article", "pubmed", "ieee", "elsevier", "jstor"]):
        source_type = "article"
    elif any(x in url_lower for x in ["book", "isbn", "ebook", "worldcat"]):
        source_type = "book"
    else:
        source_type = "webpage"
    ok({"url": url, "source_type": source_type})


def format_apa_citation(source: str):
    # Best-effort APA 7 formatting for URLs and plain titles
    now = datetime.now()
    if source.startswith("http"):
        ok({
            "format": "APA 7",
            "citation": f"Author, A. A. (n.d.). *Title of page*. Site Name. Retrieved {now.strftime('%B %d, %Y')}, from {source}",
            "note": "Replace Author, A. A., Title of page, and Site Name with actual values from the source.",
        })
    else:
        ok({
            "format": "APA 7",
            "citation": f"Author, A. A. ({now.year}). *{source}*. Publisher.",
            "note": "Replace Author, A. A. and Publisher with actual values.",
        })


def format_mla_citation(source: str):
    now = datetime.now()
    if source.startswith("http"):
        ok({
            "format": "MLA 9",
            "citation": f'Author Last, First. "Title of Page." *Site Name*, Day Month Year, {source}.',
            "note": "Replace Author Last, First, Title of Page, Site Name, and date with actual values from the source.",
        })
    else:
        ok({
            "format": "MLA 9",
            "citation": f'Author Last, First. *{source}*. Publisher, {now.year}.',
            "note": "Replace Author Last, First and Publisher with actual values.",
        })


# ---------------------------------------------------------------------------
# Maintenance tools
# ---------------------------------------------------------------------------

def get_overdue_loans(user_id: int = None):
    conn = get_connection()
    try:
        today = datetime.now().date().isoformat()
        if user_id:
            rows = conn.execute(
                """
                SELECT l.loan_id, l.user_id, u.name AS user_name, l.book_id,
                       b.title, l.due_date, l.return_date, l.status
                FROM Loans l
                JOIN Books b ON l.book_id = b.book_id
                JOIN Users u ON l.user_id = u.user_id
                WHERE l.user_id = ? AND l.return_date IS NULL AND l.due_date < ?
                ORDER BY l.due_date ASC
                """,
                (user_id, today),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT l.loan_id, l.user_id, u.name AS user_name, l.book_id,
                       b.title, l.due_date, l.return_date, l.status
                FROM Loans l
                JOIN Books b ON l.book_id = b.book_id
                JOIN Users u ON l.user_id = u.user_id
                WHERE l.return_date IS NULL AND l.due_date < ?
                ORDER BY l.due_date ASC
                """,
                (today,),
            ).fetchall()

        result = []
        for r in rows:
            row = dict(r)
            due = datetime.fromisoformat(row["due_date"]).date()
            today_date = datetime.now().date()
            days_overdue = (today_date - due).days
            row["days_overdue"] = max(0, days_overdue - config.GRACE_PERIOD_DAYS)
            raw_fee = row["days_overdue"] * config.LATE_FEE_RATE
            row["late_fee"] = min(raw_fee, config.LATE_FEE_CAP)
            result.append(row)
        ok(result)
    finally:
        conn.close()


def calculate_late_fee(loan_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT loan_id, due_date, return_date FROM Loans WHERE loan_id = ?",
            (loan_id,),
        ).fetchone()
        if not row:
            err(f"Loan {loan_id} not found")
        due = datetime.fromisoformat(row["due_date"]).date()
        end_date = datetime.fromisoformat(row["return_date"]).date() if row["return_date"] else datetime.now().date()
        days_overdue = max(0, (end_date - due).days - config.GRACE_PERIOD_DAYS)
        fee = min(days_overdue * config.LATE_FEE_RATE, config.LATE_FEE_CAP)
        ok({"loan_id": loan_id, "days_overdue": days_overdue, "late_fee": fee, "currency": "PHP"})
    finally:
        conn.close()


def create_damage_ticket(book_id: int, description: str, reported_by: int = None):
    conn = get_connection()
    try:
        book = conn.execute(
            "SELECT book_id, title, available_copies FROM Books WHERE book_id = ?",
            (book_id,),
        ).fetchone()
        if not book:
            err(f"Book {book_id} not found")

        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO Tickets (book_id, reported_by, issue_type, description, status, created_at)
            VALUES (?, ?, 'damaged', ?, 'open', ?)
            """,
            (book_id, reported_by, description, now),
        )
        # Update book status and decrement available copies
        new_copies = max(0, book["available_copies"] - 1)
        conn.execute(
            "UPDATE Books SET status = 'repair', available_copies = ? WHERE book_id = ?",
            (new_copies, book_id),
        )
        conn.commit()
        ticket_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        ok({
            "ticket_id": ticket_id,
            "book_id": book_id,
            "book_title": book["title"],
            "status": "open",
            "book_status": "repair",
            "available_copies_remaining": new_copies,
        })
    finally:
        conn.close()


def get_inventory_health():
    conn = get_connection()
    try:
        one_year_ago = (datetime.now() - timedelta(days=365)).date().isoformat()

        low = conn.execute(
            """
            SELECT b.book_id, b.title, b.author, COUNT(l.loan_id) AS checkout_count
            FROM Books b
            LEFT JOIN Loans l ON b.book_id = l.book_id AND l.loan_date >= ?
            WHERE b.status = 'available'
            GROUP BY b.book_id
            HAVING checkout_count < ?
            ORDER BY checkout_count ASC
            """,
            (one_year_ago, config.LOW_CIRCULATION_CHECKOUTS),
        ).fetchall()

        high = conn.execute(
            """
            SELECT b.book_id, b.title, b.author, COUNT(l.loan_id) AS checkout_count
            FROM Books b
            JOIN Loans l ON b.book_id = l.book_id AND l.loan_date >= ?
            GROUP BY b.book_id
            HAVING checkout_count >= ?
            ORDER BY checkout_count DESC
            """,
            (one_year_ago, config.HIGH_DEMAND_CHECKOUTS),
        ).fetchall()

        ok({
            "low_circulation": rows_to_list(low),
            "high_demand": rows_to_list(high),
        })
    finally:
        conn.close()


def has_overdue_items(user_id: int):
    conn = get_connection()
    try:
        today = datetime.now().date().isoformat()
        rows = conn.execute(
            """
            SELECT l.loan_id, l.due_date
            FROM Loans l
            WHERE l.user_id = ? AND l.return_date IS NULL AND l.due_date < ?
            ORDER BY l.due_date ASC
            """,
            (user_id, today),
        ).fetchall()
        if not rows:
            ok({"user_id": user_id, "has_overdue": False, "max_days_overdue": 0})
            return
        worst_due = datetime.fromisoformat(rows[0]["due_date"]).date()
        max_days = (datetime.now().date() - worst_due).days
        ok({"user_id": user_id, "has_overdue": True, "max_days_overdue": max_days})
    finally:
        conn.close()


def generate_fine_notice(user_id: int):
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT name, email FROM Users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not user:
            err(f"User {user_id} not found")

        today = datetime.now().date().isoformat()
        rows = conn.execute(
            """
            SELECT l.loan_id, b.title, l.due_date
            FROM Loans l
            JOIN Books b ON l.book_id = b.book_id
            WHERE l.user_id = ? AND l.return_date IS NULL AND l.due_date < ?
            """,
            (user_id, today),
        ).fetchall()

        if not rows:
            ok({"notice": f"No overdue items found for {user['name']}."})
            return

        lines = [
            f"OVERDUE NOTICE — {datetime.now().strftime('%B %d, %Y')}",
            f"To: {user['name']} ({user['email'] or 'no email on file'})",
            "",
            "The following items are overdue:",
            "",
        ]
        total_fee = 0.0
        for r in rows:
            due = datetime.fromisoformat(r["due_date"]).date()
            days = max(0, (datetime.now().date() - due).days - config.GRACE_PERIOD_DAYS)
            fee = min(days * config.LATE_FEE_RATE, config.LATE_FEE_CAP)
            total_fee += fee
            lines.append(f"  - {r['title']}")
            lines.append(f"    Due: {r['due_date']}  |  Days overdue: {days}  |  Fee: PHP {fee:.2f}")
            lines.append("")

        lines.append(f"Total outstanding fees: PHP {total_fee:.2f}")
        lines.append("")
        lines.append("Please return all items and settle your balance at the circulation desk.")
        lines.append("Failure to do so may result in suspension of borrowing and booking privileges.")

        ok({"notice": "\n".join(lines)})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Journal search — CrossRef API (live, no key required)
# ---------------------------------------------------------------------------

CROSSREF_API = "https://api.crossref.org/works"
CROSSREF_HEADERS = {
    "User-Agent": "LibraryAgentSystem/1.0 (mailto:library@school.edu)",
}


def search_journals(topic: str, limit: int = 5):
    """
    Search for real academic journal articles via the CrossRef API.

    Returns up to `limit` results ranked by CrossRef relevance score.
    Each result includes title, authors, year, journal, DOI, and a direct URL.
    """
    params = urllib.parse.urlencode({
        "query": topic,
        "rows": min(limit, 20),          # CrossRef max per page is 1000, cap at 20
        "select": "title,author,DOI,URL,published,container-title,type,score",
    })
    url = f"{CROSSREF_API}?{params}"

    try:
        req = urllib.request.Request(url, headers=CROSSREF_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        err(f"CrossRef API unreachable: {e.reason}")
    except Exception as e:
        err(f"CrossRef API error: {str(e)}")

    items = raw.get("message", {}).get("items", [])
    results = []
    for item in items:
        title = (item.get("title") or ["Unknown title"])[0]

        authors_raw = item.get("author") or []
        author_parts = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in authors_raw[:3]
        ]
        authors = ", ".join(author_parts) if author_parts else "Unknown"
        if len(authors_raw) > 3:
            authors += " et al."

        date_parts = (item.get("published") or {}).get("date-parts", [[None]])
        year = date_parts[0][0] if date_parts and date_parts[0] else None

        journal = ((item.get("container-title") or [""])[0]) or ""
        doi = item.get("DOI", "")
        link = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")

        results.append({
            "title":   title,
            "authors": authors,
            "year":    year,
            "journal": journal,
            "doi":     doi,
            "url":     link,
            "source":  "CrossRef",
        })

    ok(results)


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

FUNCTIONS = {
    "search_books": search_books,
    "get_book_abstract": get_book_abstract,
    "suggest_related": suggest_related,
    "check_availability": check_availability,
    "check_room_availability": check_room_availability,
    "create_booking": create_booking,
    "cancel_booking": cancel_booking,
    "get_user_weekly_hours": get_user_weekly_hours,
    "get_upcoming_bookings": get_upcoming_bookings,
    "match_database": match_database,
    "detect_source_type": detect_source_type,
    "format_apa_citation": format_apa_citation,
    "format_mla_citation": format_mla_citation,
    "get_overdue_loans": get_overdue_loans,
    "calculate_late_fee": calculate_late_fee,
    "create_damage_ticket": create_damage_ticket,
    "get_inventory_health": get_inventory_health,
    "has_overdue_items": has_overdue_items,
    "generate_fine_notice": generate_fine_notice,
    "search_journals": search_journals,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in FUNCTIONS:
        print(json.dumps({"error": f"Unknown function. Available: {', '.join(FUNCTIONS)}"}))
        sys.exit(1)

    func_name = sys.argv[1]
    func = FUNCTIONS[func_name]

    import inspect
    sig = inspect.signature(func)
    parser = argparse.ArgumentParser(prog=f"tools.py {func_name}")
    for param_name, param in sig.parameters.items():
        default = param.default if param.default is not inspect.Parameter.empty else None
        required = param.default is inspect.Parameter.empty
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else str
        if annotation == bool:
            parser.add_argument(f"--{param_name}", type=lambda x: x.lower() == "true", default=default, required=False)
        elif annotation == int:
            parser.add_argument(f"--{param_name}", type=int, default=default, required=required)
        elif annotation == float:
            parser.add_argument(f"--{param_name}", type=float, default=default, required=required)
        else:
            parser.add_argument(f"--{param_name}", type=str, default=default, required=required)

    args = parser.parse_args(sys.argv[2:])
    kwargs = {k: v for k, v in vars(args).items() if v is not None}

    try:
        func(**kwargs)
    except SystemExit:
        raise
    except Exception as e:
        err(str(e))


if __name__ == "__main__":
    main()
