"""
seed_db.py — Library Agent System
Creates library.db and populates all tables with realistic mock data.

Run once before starting the system:
    python seed_db.py

Re-running drops and recreates all tables (idempotent).
"""

import sqlite3
from datetime import datetime, timedelta

import config

DB_PATH = config.DB_PATH


def get_date(offset_days: int) -> str:
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def get_dt(offset_days: int, hour: int = 10, minute: int = 0) -> str:
    return (datetime.now() + timedelta(days=offset_days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    ).isoformat()


def create_tables(conn):
    conn.executescript("""
        DROP TABLE IF EXISTS Tickets;
        DROP TABLE IF EXISTS Bookings;
        DROP TABLE IF EXISTS Loans;
        DROP TABLE IF EXISTS Rooms;
        DROP TABLE IF EXISTS Books;
        DROP TABLE IF EXISTS Users;

        CREATE TABLE Users (
            user_id   INTEGER PRIMARY KEY,
            name      TEXT NOT NULL,
            email     TEXT,
            role      TEXT CHECK(role IN ('student','faculty','staff'))
        );

        CREATE TABLE Books (
            book_id          INTEGER PRIMARY KEY,
            title            TEXT NOT NULL,
            author           TEXT NOT NULL,
            genre            TEXT,
            tags             TEXT,
            abstract         TEXT,
            total_copies     INTEGER DEFAULT 1,
            available_copies INTEGER DEFAULT 1,
            status           TEXT DEFAULT 'available' CHECK(status IN ('available','repair','retired'))
        );

        CREATE TABLE Loans (
            loan_id     INTEGER PRIMARY KEY,
            user_id     INTEGER REFERENCES Users(user_id),
            book_id     INTEGER REFERENCES Books(book_id),
            loan_date   TEXT,
            due_date    TEXT,
            return_date TEXT,
            status      TEXT CHECK(status IN ('active','returned','overdue'))
        );

        CREATE TABLE Rooms (
            room_id  INTEGER PRIMARY KEY,
            name     TEXT,
            capacity INTEGER,
            type     TEXT CHECK(type IN ('quiet_pod','group_room','computer_lab')),
            floor    INTEGER
        );

        CREATE TABLE Bookings (
            booking_id INTEGER PRIMARY KEY,
            user_id    INTEGER REFERENCES Users(user_id),
            room_id    INTEGER REFERENCES Rooms(room_id),
            start_time TEXT,
            end_time   TEXT,
            status     TEXT CHECK(status IN ('confirmed','cancelled','completed'))
        );

        CREATE TABLE Tickets (
            ticket_id   INTEGER PRIMARY KEY,
            book_id     INTEGER REFERENCES Books(book_id),
            reported_by INTEGER REFERENCES Users(user_id),
            issue_type  TEXT CHECK(issue_type IN ('damaged','missing','low_toner','other')),
            description TEXT,
            status      TEXT CHECK(status IN ('open','in_progress','resolved')),
            created_at  TEXT
        );
    """)


def seed_users(conn):
    users = [
        # (name, email, role)
        ("Ana Reyes",       "ana.reyes@uni.edu",        "student"),   # 1 — overdue, near booking limit
        ("Ben Santos",      "ben.santos@uni.edu",        "student"),   # 2 — overdue 20+ days (suspended)
        ("Carla Dizon",     "carla.dizon@uni.edu",       "student"),   # 3 — overdue 16 days
        ("David Cruz",      "david.cruz@uni.edu",        "student"),   # 4 — clean record
        ("Ella Fernandez",  "ella.fernandez@uni.edu",    "student"),   # 5 — near weekly hour limit
        ("Felix Tan",       "felix.tan@uni.edu",         "student"),   # 6 — clean
        ("Grace Lim",       "grace.lim@uni.edu",         "student"),   # 7 — clean
        ("Hugo Villanueva", "hugo.v@uni.edu",            "student"),   # 8 — clean
        ("Iris Castillo",   "iris.c@uni.edu",            "student"),   # 9 — clean
        ("James Ramos",     "james.r@uni.edu",           "student"),   # 10 — clean
        ("Karen Navarro",   "karen.n@uni.edu",           "faculty"),   # 11 — faculty
        ("Luis Morales",    "luis.m@uni.edu",            "faculty"),   # 12 — faculty
        ("Maya Torres",     "maya.t@uni.edu",            "staff"),     # 13 — staff
        ("Nico Aguilar",    "nico.a@uni.edu",            "student"),   # 14 — overdue 5 days (within grace threshold)
        ("Olivia Mendez",   "olivia.m@uni.edu",          "student"),   # 15 — clean
    ]
    conn.executemany(
        "INSERT INTO Users (name, email, role) VALUES (?, ?, ?)", users
    )


def seed_books(conn):
    books = [
        # (title, author, genre, tags, abstract, total_copies, available_copies, status)
        ("Introduction to Machine Learning", "Ethem Alpaydin", "Computer Science",
         "machine learning,AI,beginner,algorithms",
         "A comprehensive beginner-friendly introduction to the field of machine learning, covering supervised and unsupervised learning, neural networks, and real-world applications.",
         3, 2, "available"),  # 1

        ("Deep Learning", "Ian Goodfellow", "Computer Science",
         "deep learning,neural networks,AI,advanced",
         "The definitive textbook on deep learning, covering the mathematical foundations, architectures, and state-of-the-art techniques used in modern AI systems.",
         2, 1, "available"),  # 2

        ("Dune", "Frank Herbert", "Science Fiction",
         "science fiction,politics,ecology,epic,classic",
         "A sweeping epic set on the desert planet Arrakis, exploring themes of politics, religion, ecology, and human potential through the story of Paul Atreides.",
         2, 2, "available"),  # 3

        ("Foundation", "Isaac Asimov", "Science Fiction",
         "science fiction,politics,empire,classic,society",
         "Asimov's landmark series follows mathematician Hari Seldon as he uses psychohistory to guide civilization through a coming dark age.",
         2, 1, "available"),  # 4

        ("The Great Gatsby", "F. Scott Fitzgerald", "Classic Literature",
         "classic,american literature,jazz age,tragedy",
         "A portrait of the Jazz Age through the eyes of narrator Nick Carraway, exploring the American Dream and its corruption through the mysterious Jay Gatsby.",
         3, 3, "available"),  # 5

        ("To Kill a Mockingbird", "Harper Lee", "Classic Literature",
         "classic,american literature,justice,race,coming-of-age",
         "Through the eyes of young Scout Finch, this novel examines racial injustice and moral growth in the American South of the 1930s.",
         2, 0, "available"),  # 6 — all copies checked out

        ("Sapiens: A Brief History of Humankind", "Yuval Noah Harari", "History",
         "history,anthropology,society,nonfiction,popular science",
         "A sweeping narrative of human history from the Stone Age through the twenty-first century, examining how Homo sapiens came to dominate the Earth.",
         2, 2, "available"),  # 7

        ("The Art of War", "Sun Tzu", "Philosophy",
         "philosophy,strategy,military,classic,leadership",
         "An ancient Chinese military treatise on strategy and tactics, widely applied to business, sports, and competitive situations.",
         3, 3, "available"),  # 8

        ("Clean Code", "Robert C. Martin", "Computer Science",
         "software engineering,programming,best practices,refactoring",
         "A guide to writing readable, maintainable, and professional code, filled with practical examples and case studies.",
         2, 2, "available"),  # 9

        ("The Pragmatic Programmer", "Andrew Hunt", "Computer Science",
         "software engineering,programming,career,best practices",
         "Practical wisdom for software developers covering topics from personal responsibility to architectural techniques.",
         2, 2, "available"),  # 10

        ("Thinking, Fast and Slow", "Daniel Kahneman", "Psychology",
         "psychology,cognitive science,decision making,behavioral economics",
         "Nobel laureate Kahneman examines the two systems of thought — intuitive and deliberate — that shape our judgments and decisions.",
         2, 2, "available"),  # 11

        ("The Selfish Gene", "Richard Dawkins", "Biology",
         "biology,evolution,genetics,popular science",
         "Dawkins presents the gene-centered view of evolution, arguing that genes — not organisms — are the fundamental units of natural selection.",
         1, 1, "available"),  # 12

        ("A Brief History of Time", "Stephen Hawking", "Physics",
         "physics,cosmology,popular science,space,time",
         "Hawking explores the universe's biggest questions — from the Big Bang to black holes — in language accessible to non-scientists.",
         2, 2, "available"),  # 13

        ("Data Structures and Algorithms", "Thomas H. Cormen", "Computer Science",
         "algorithms,data structures,computer science,programming,textbook",
         "The standard textbook for algorithms and data structures, covering sorting, graph algorithms, dynamic programming, and complexity analysis.",
         3, 2, "available"),  # 14

        ("The Republic", "Plato", "Philosophy",
         "philosophy,politics,justice,ethics,classic,greek",
         "Plato's foundational work on justice, the ideal state, and the role of the philosopher-king, presented as a series of Socratic dialogues.",
         2, 2, "available"),  # 15

        ("Neuromancer", "William Gibson", "Science Fiction",
         "science fiction,cyberpunk,hacking,AI,dystopia",
         "The novel that defined cyberpunk: a washed-up computer hacker is hired to pull off the ultimate hack in a dark, neon-lit future.",
         1, 1, "available"),  # 16

        ("Meditations", "Marcus Aurelius", "Philosophy",
         "philosophy,stoicism,self-help,classic,leadership",
         "Personal writings of the Roman Emperor Marcus Aurelius, offering reflections on duty, virtue, and the nature of existence.",
         2, 2, "available"),  # 17

        ("The Lean Startup", "Eric Ries", "Business",
         "business,entrepreneurship,startup,management,innovation",
         "A methodology for developing businesses and products through validated learning, rapid experimentation, and iterative design.",
         2, 1, "available"),  # 18

        ("Database System Concepts", "Abraham Silberschatz", "Computer Science",
         "databases,SQL,computer science,textbook,systems",
         "A comprehensive textbook on database systems covering relational models, SQL, transaction processing, and storage management.",
         2, 2, "available"),  # 19

        ("The Name of the Wind", "Patrick Rothfuss", "Fantasy",
         "fantasy,magic,adventure,coming-of-age",
         "The fictional autobiography of Kvothe, a legendary magician and musician, narrating his rise from a talented child to one of the most notorious figures in the world.",
         1, 1, "available"),  # 20

        ("Ender's Game", "Orson Scott Card", "Science Fiction",
         "science fiction,military,strategy,coming-of-age,classic",
         "A gifted child is trained at a military school in space to fight an alien invasion, in a novel that blends action with ethical questions about war.",
         2, 2, "available"),  # 21

        ("Operating System Concepts", "Abraham Silberschatz", "Computer Science",
         "operating systems,computer science,textbook,systems",
         "The standard textbook for operating systems, covering process management, memory, file systems, and I/O.",
         2, 2, "available"),  # 22

        ("Brave New World", "Aldous Huxley", "Classic Literature",
         "classic,dystopia,science fiction,society,literature",
         "A vision of a future world state where human beings are manufactured and conditioned for happiness, challenging the cost of a perfectly engineered society.",
         2, 2, "available"),  # 23

        ("The Hitchhiker's Guide to the Galaxy", "Douglas Adams", "Science Fiction",
         "science fiction,comedy,adventure,classic",
         "Seconds before Earth is demolished to make way for a hyperspace bypass, Arthur Dent is whisked into space and discovers the absurdity of the universe.",
         2, 2, "available"),  # 24

        ("Principles of Economics", "N. Gregory Mankiw", "Economics",
         "economics,microeconomics,macroeconomics,textbook",
         "The most widely used introductory economics textbook, covering supply and demand, market structures, GDP, inflation, and monetary policy.",
         3, 3, "available"),  # 25

        ("The Psychology of Money", "Morgan Housel", "Business",
         "finance,personal finance,behavioral economics,money",
         "Timeless lessons on wealth, greed, and happiness, drawing on stories of history and personal finance to explain how people think about money.",
         2, 2, "available"),  # 26

        ("Algorithms to Live By", "Brian Christian", "Computer Science",
         "algorithms,computer science,decision making,popular science",
         "How computer algorithms can be applied to everyday human decisions, from organizing your home to managing your time and relationships.",
         1, 0, "repair"),  # 27 — on repair

        ("Structure and Interpretation of Computer Programs", "Harold Abelson", "Computer Science",
         "programming,computer science,Lisp,textbook,classic",
         "MIT's classic computer science textbook, using Scheme to teach computational thinking and the principles of programming language design.",
         1, 0, "repair"),  # 28 — on repair

        ("The Catcher in the Rye", "J.D. Salinger", "Classic Literature",
         "classic,coming-of-age,american literature,identity",
         "Holden Caulfield's account of a few days in New York City after being expelled from prep school, a landmark of teenage alienation and rebellion.",
         2, 1, "available"),  # 29

        ("Freakonomics", "Steven D. Levitt", "Economics",
         "economics,social science,popular science,statistics,nonfiction",
         "A rogue economist explores the hidden side of everything — from sumo wrestlers to drug dealers — using data and incentives to reveal surprising truths.",
         2, 2, "available"),  # 30
    ]
    conn.executemany(
        "INSERT INTO Books (title, author, genre, tags, abstract, total_copies, available_copies, status) VALUES (?,?,?,?,?,?,?,?)",
        books,
    )


def seed_rooms(conn):
    rooms = [
        # (name, capacity, type, floor)
        ("Pod A", 1, "quiet_pod", 1),
        ("Pod B", 1, "quiet_pod", 1),
        ("Pod C", 2, "quiet_pod", 2),
        ("Study Room 1", 4, "group_room", 2),
        ("Study Room 2", 4, "group_room", 2),
        ("Study Room 3", 6, "group_room", 3),
        ("Conference Room", 10, "group_room", 3),
        ("Computer Lab", 20, "computer_lab", 1),
    ]
    conn.executemany(
        "INSERT INTO Rooms (name, capacity, type, floor) VALUES (?,?,?,?)", rooms
    )


def seed_loans(conn):
    loans = [
        # (user_id, book_id, loan_date, due_date, return_date, status)
        # --- Overdue loans (for testing Maintenance agent) ---
        (1,  6,  get_date(-30), get_date(-16), None, "overdue"),  # Ana — 16 days overdue (suspended threshold)
        (2,  14, get_date(-35), get_date(-21), None, "overdue"),  # Ben — 21 days overdue (blocked)
        (2,  3,  get_date(-40), get_date(-26), None, "overdue"),  # Ben — 26 days overdue (blocked)
        (3,  9,  get_date(-30), get_date(-16), None, "overdue"),  # Carla — 16 days overdue (blocked)
        (14, 5,  get_date(-16), get_date(-2),  None, "overdue"),  # Nico — 2 days overdue (not blocked)

        # --- Active loans ---
        (4,  1,  get_date(-10), get_date(4),   None, "active"),
        (5,  2,  get_date(-7),  get_date(7),   None, "active"),
        (6,  7,  get_date(-5),  get_date(9),   None, "active"),
        (7,  11, get_date(-3),  get_date(11),  None, "active"),
        (8,  13, get_date(-2),  get_date(12),  None, "active"),
        (9,  15, get_date(-1),  get_date(13),  None, "active"),
        (10, 17, get_date(-4),  get_date(10),  None, "active"),
        (11, 25, get_date(-6),  get_date(8),   None, "active"),
        (12, 18, get_date(-8),  get_date(6),   None, "active"),
        (15, 20, get_date(-2),  get_date(12),  None, "active"),

        # --- Returned loans ---
        (4,  8,  get_date(-60), get_date(-46), get_date(-48), "returned"),
        (5,  10, get_date(-45), get_date(-31), get_date(-32), "returned"),
        (6,  4,  get_date(-50), get_date(-36), get_date(-37), "returned"),
        (7,  16, get_date(-30), get_date(-16), get_date(-18), "returned"),
        (8,  22, get_date(-20), get_date(-6),  get_date(-7),  "returned"),
        (9,  23, get_date(-25), get_date(-11), get_date(-12), "returned"),
        (10, 24, get_date(-15), get_date(-1),  get_date(-2),  "returned"),
        (11, 26, get_date(-40), get_date(-26), get_date(-28), "returned"),
        (13, 30, get_date(-10), get_date(4),   get_date(-1),  "returned"),
        (15, 29, get_date(-35), get_date(-21), get_date(-22), "returned"),
    ]
    conn.executemany(
        "INSERT INTO Loans (user_id, book_id, loan_date, due_date, return_date, status) VALUES (?,?,?,?,?,?)",
        loans,
    )


def seed_bookings(conn):
    bookings = [
        # (user_id, room_id, start_time, end_time, status)
        # Ana (user 1) — near 10-hour weekly limit (has 9h already)
        (1, 4, get_dt(0, 9),  get_dt(0, 13),  "confirmed"),   # 4h today
        (1, 5, get_dt(1, 14), get_dt(1, 19),  "confirmed"),   # 5h tomorrow — total 9h

        # Ella (user 5) — also near limit (8h)
        (5, 6, get_dt(2, 10), get_dt(2, 14),  "confirmed"),   # 4h
        (5, 4, get_dt(3, 10), get_dt(3, 14),  "confirmed"),   # 4h — total 8h

        # Ben (user 2) — suspended, has upcoming bookings (should be cancelled)
        (2, 3, get_dt(1, 10), get_dt(1, 12),  "confirmed"),
        (2, 5, get_dt(3, 14), get_dt(3, 16),  "confirmed"),

        # David (user 4) — clean user, upcoming booking
        (4, 4, get_dt(2, 13), get_dt(2, 15),  "confirmed"),

        # Past bookings (completed)
        (6,  5, get_dt(-7, 10),  get_dt(-7, 12),  "completed"),
        (7,  6, get_dt(-5, 14),  get_dt(-5, 16),  "completed"),
        (8,  4, get_dt(-3, 9),   get_dt(-3, 11),  "completed"),
        (9,  3, get_dt(-2, 15),  get_dt(-2, 17),  "completed"),
        (10, 7, get_dt(-1, 10),  get_dt(-1, 12),  "completed"),

        # Cancelled bookings
        (3,  4, get_dt(5, 10),  get_dt(5, 12),   "cancelled"),
        (11, 7, get_dt(-6, 14), get_dt(-6, 16),  "cancelled"),

        # More upcoming bookings for various users
        (6,  3, get_dt(1, 9),  get_dt(1, 11),  "confirmed"),
        (7,  5, get_dt(4, 13), get_dt(4, 15),  "confirmed"),
        (9,  6, get_dt(2, 9),  get_dt(2, 11),  "confirmed"),
        (10, 4, get_dt(5, 10), get_dt(5, 12),  "confirmed"),
        (15, 3, get_dt(3, 14), get_dt(3, 16),  "confirmed"),
        (12, 7, get_dt(6, 10), get_dt(6, 14),  "confirmed"),
    ]
    conn.executemany(
        "INSERT INTO Bookings (user_id, room_id, start_time, end_time, status) VALUES (?,?,?,?,?)",
        bookings,
    )


def seed_tickets(conn):
    now = datetime.now().isoformat()
    tickets = [
        # (book_id, reported_by, issue_type, description, status, created_at)
        (27, 13, "damaged",  "Cover torn, pages 45-60 water damaged",                 "open",        get_dt(-10)),
        (28, 13, "damaged",  "Spine cracked, binding loose",                          "open",        get_dt(-5)),
        (6,  1,  "damaged",  "Pages 120-130 have highlighting and margin notes",      "in_progress", get_dt(-15)),
        (14, 4,  "damaged",  "Coffee stain on cover, otherwise readable",             "resolved",    get_dt(-30)),
        (3,  7,  "missing",  "Book not found during inventory check",                  "open",        get_dt(-3)),
        (18, 11, "damaged",  "Scratches on cover, pages intact",                      "resolved",    get_dt(-20)),
        (22, 5,  "damaged",  "Last 10 pages torn out",                                "in_progress", get_dt(-8)),
        (8,  13, "other",    "Barcode label missing — cannot be scanned at checkout", "open",        get_dt(-2)),
        (1,  4,  "damaged",  "Sticky residue on multiple pages",                      "resolved",    get_dt(-45)),
        (15, 9,  "missing",  "Reported missing by borrower; may have been lost",      "open",        get_dt(-1)),
    ]
    conn.executemany(
        "INSERT INTO Tickets (book_id, reported_by, issue_type, description, status, created_at) VALUES (?,?,?,?,?,?)",
        tickets,
    )


def main():
    print(f"Creating database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    print("Creating tables...")
    create_tables(conn)

    print("Seeding Users (15 rows)...")
    seed_users(conn)

    print("Seeding Books (30 rows)...")
    seed_books(conn)

    print("Seeding Rooms (8 rows)...")
    seed_rooms(conn)

    print("Seeding Loans (25 rows)...")
    seed_loans(conn)

    print("Seeding Bookings (20 rows)...")
    seed_bookings(conn)

    print("Seeding Tickets (10 rows)...")
    seed_tickets(conn)

    conn.commit()
    conn.close()
    print(f"\nDone. {DB_PATH} is ready.")
    print("\nEdge cases seeded:")
    print("  - 3 users with overdue loans (Ana/1, Ben/2, Carla/3)")
    print("  - 1 user overdue 21+ days and blocked from booking (Ben/2)")
    print("  - 2 users near weekly booking hour limit (Ana/1 at 9h, Ella/5 at 8h)")
    print("  - 2 books on repair hold (book_id 27, 28)")
    print("  - 1 student with upcoming bookings to cancel on suspension (Ben/2)")


if __name__ == "__main__":
    main()
