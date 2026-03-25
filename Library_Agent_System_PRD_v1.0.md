# **Product Requirements Document: Library Maintenance & Resource Agent System**

## **Multi-Agent CLI System — Human Review Draft v1.1**

March 2026

Table of Contents

# **Product Requirements Document**

## **Library Maintenance & Resource Agent System**

### **Multi-Agent CLI — Human Review Draft v1.1**

**Document Status:** Draft — Pending Review
**Version:** 1.1
**Date:** March 2026
**Prepared By:** Library Systems Team

---

## **Table of Contents**

1. Executive Summary

2. System Overview

3. Project Goals & Success Metrics

4. System Architecture

5. Agent Specifications

6. Inter-Agent Communication Protocol

7. Shared Data Layer

8. CLI Interface Requirements

9. Mock Data Requirements

10. Agent File Structure

11. Out of Scope

12. Open Questions & Review Notes

---

## **1\. Executive Summary**

This document defines the requirements for a **Library Maintenance & Resource Agent System** — a CLI-based, multi-agent application built on Claude Code. The system replaces fragmented, manual library workflows with four specialized AI agents that collaborate through a shared SQLite database and a central orchestrator.

The system is designed to be reviewed and iterated on by the team **before** any development begins. Claude Code will read this PRD as its primary instruction set when building out the agent files and tooling.

The four agents are:

* **Semantic Librarian** — Understands natural language book queries and recommends resources

* **Space Manager** — Handles study room bookings and enforces usage policies

* **Digital Resource Navigator** — Guides students to research databases and formats citations

* **Maintenance & Inventory Agent** — Tracks overdue items, fines, damage reports, and inventory health

All agents are defined as .md instruction files. They communicate through a central orchestrator.md that routes user intent to the correct agent using Claude Code’s built-in Task tool.

---

## **2\. System Overview**

### **2.1 What This System Does**

A student or librarian opens a terminal and types a natural language request. The system understands the intent, routes the task to the right agent, executes the required logic (SQL queries, policy checks, citation formatting), and returns a clear response — all within the CLI.

**Example interactions:**

* "Find me a beginner-friendly book on machine learning" → Semantic Librarian

* "Book a quiet room for 2 people at 3 PM tomorrow" → Space Manager

* "Give me an APA citation for this URL: \[url\]" → Digital Resource Navigator

* "Show me all students with overdue books" → Maintenance & Inventory Agent

### **2.2 Technology Stack**

| Component | Technology |
| :---- | :---- |
| Agent definitions | Markdown .md files (Claude Code agent format) |
| Orchestration | Claude Code Task tool |
| Database | SQLite (library.db) |
| Tool layer | Python 3 (tools.py) |
| CLI runtime | Claude Code (claude CLI) |
| Data | Mock data only (no live integrations) |

### **2.3 Design Principles**

* **Document-first:** This PRD is reviewed and approved before any code is written

* **Agent separation:** Each agent has a single area of responsibility

* **Shared state via DB:** Agents do not pass objects directly; they read/write from library.db

* **Plain English instructions:** Agent .md files are readable by non-engineers

* **Policy-enforcing:** Agents enforce library rules (e.g., booking hour limits) automatically

---

## **3\. Project Goals & Success Metrics**

### **3.1 Primary Goals**

1. A user can complete any common library task through a single CLI entry point

2. The orchestrator correctly routes user intent to the right agent with no manual selection

3. Agents can call each other when a task spans multiple domains

4. All business rules (late fees, booking limits, availability) are enforced automatically

### **3.2 Success Metrics (for review/iteration)**

| Metric | Target |
| :---- | :---- |
| Correct agent routing accuracy | ≥ 90% on test prompts |
| Cross-agent handoff success rate | 100% (no silent failures) |
| CLI response time per query | \< 10 seconds |
| Policy enforcement coverage | All defined rules enforced |
| Mock data coverage | All 5 DB tables seeded with ≥ 20 rows each |

**Review Note:** These metrics are proposed. Team should confirm whether these are the right signals to measure before proceeding.

---

## **4\. System Architecture**

### **4.1 High-Level Flow**

User (Terminal)  
      |  
      v  
orchestrator.md        \<-- Single entry point  
      |  
      |-- Task tool \--\> librarian.md  
      |-- Task tool \--\> space-manager.md  
      |-- Task tool \--\> navigator.md  
      |-- Task tool \--\> maintenance.md  
            |  
            v (all agents read/write)  
        library.db (SQLite)  
            |  
            v  
          tools.py     \<-- Python helper functions

### **4.2 Inter-Agent Communication**

Agents communicate exclusively through two mechanisms:

**Mechanism 1 — Task Tool (direct delegation)**  
The orchestrator calls a sub-agent using the Task tool, passing the user’s query and any required context (e.g., user\_id, timestamp). The sub-agent runs and returns its output to the orchestrator, which relays it to the user.

**Mechanism 2 — Shared Database (indirect state sharing)**  
If Agent A writes a record (e.g., a damage ticket), Agent B can read that record independently on its next query. No direct object passing between agents.

**Cross-agent calls (sub-agent to sub-agent):**  
A sub-agent may itself call another sub-agent via the Task tool when a task spans domains. Example: librarian.md discovers a book is flagged for repair and calls maintenance.md to check its repair status.

### **4.3 File Structure**

/library-agent-system
│
├── .claude/
│   └── agents/
│       ├── orchestrator.md      \# Entry point agent (Claude Code agent format)
│       ├── librarian.md         \# Semantic Librarian agent
│       ├── space-manager.md     \# Space Manager agent
│       ├── navigator.md         \# Digital Resource Navigator agent
│       └── maintenance.md       \# Maintenance & Inventory agent
│
├── CLAUDE.md                    \# Tells Claude to start session with orchestrator.md
├── tools.py                     \# All Python helper functions (CLI-invocable)
├── config.py                    \# Adjustable constants (fee rate, booking limits, grace period)
├── seed\_db.py                   \# Creates and seeds library.db
├── library.db                   \# SQLite database (generated)
│
└── README.md                    \# Setup and run instructions

---

## **5\. Agent Specifications**

### **5.1 Orchestrator Agent (orchestrator.md)**

**Role:** Entry point. Reads user input, classifies intent, and delegates to the correct sub-agent.

**Responsibilities:** \- Parse the user’s raw natural language input \- Identify which of the four agents owns the task \- Invoke the correct agent via the Task tool \- Pass the user’s full original message plus their user\_id as context \- Return the sub-agent’s response directly to the user without modification \- Handle ambiguous requests by asking one clarifying question

**Pre-routing: Special Commands (checked before LLM routing)**

| Command | Behavior |
| :---- | :---- |
| help | Print example queries for each agent; do not route to a sub-agent |
| my bookings | Route directly to space-manager.md with action “list\_upcoming\_bookings” |
| my loans | Route directly to maintenance.md with action “list\_active\_loans” |
| exit / quit | End the session |

**Routing Logic (natural language — applied after special command check):**

| User intent signals | Route to |
| :---- | :---- |
| Book title, author, genre, “find me a book”, “recommend” | librarian.md |
| “Room”, “study space”, “book a pod”, time/date references | space-manager.md |
| “Citation”, “APA”, “MLA”, URL, “journal”, “research database” | navigator.md |
| “Overdue”, “fine”, “damaged”, “inventory”, “repair”, “late fee” | maintenance.md |

**Multi-domain requests:** If a single request spans two agents equally (e.g., “find me a book and book me a room to read it in”), the orchestrator splits it into two sequential Task calls and combines both results in a single response.

**Escalation rule:** If routing confidence is low after both checks, the orchestrator must ask the user to clarify before routing — it must never silently pick the wrong agent.

---

### **5.2 Semantic Librarian (librarian.md)**

**Role:** Understands natural language book queries, including vague or conceptual requests.

**Capabilities:** \- Accept fuzzy, intent-based queries (e.g., “a book like Dune but more political”) \- Run keyword pre-filter against the Books table \- Re-rank results using LLM semantic reasoning when exact matches fail \- Summarize a book’s abstract so the user can decide if it’s worth checking out \- Suggest related titles by genre and tags if the target is unavailable \- Check if a book is on repair hold (calls maintenance.md via Task tool)

**Tools available:** \- search\_books(query, fuzzy=True) — returns ranked list from Books table \- get\_book\_abstract(book\_id) — returns full abstract \- suggest\_related(book\_id) — returns 3 related books by genre/tags \- check\_availability(book\_id) — returns available copy count

**Behavior rules:** \- If no results found after fuzzy search: suggest 3 related books and explain the connection \- If a book is available but flagged for repair: say so and suggest alternatives \- Always show at least the title, author, availability status, and a one-sentence summary

---

### **5.3 Space Manager (space-manager.md)**

**Role:** Manages study room and pod bookings, enforces usage policy.

**Capabilities:** \- Check real-time room availability for a given time and capacity \- Create, confirm, or cancel room bookings \- Enforce the 10-hour weekly booking limit per student \- Deny bookings for students with overdue items (calls maintenance.md to verify) \- List a student’s upcoming bookings

**Tools available:** \- check\_room\_availability(date, time, capacity) — returns available rooms \- create\_booking(user\_id, room\_id, start\_time, duration) — writes to Rooms and Bookings tables \- cancel\_booking(booking\_id) — removes booking \- get\_user\_weekly\_hours(user\_id) — returns hours used this week \- get\_upcoming\_bookings(user\_id) — returns user’s scheduled bookings

**Policy rules (must be enforced automatically):** \- Maximum 10 hours of bookings per student per week \- Students with items overdue by 14+ days cannot make new bookings \- Bookings cannot be made less than 30 minutes in advance \- Maximum single booking duration: 4 hours

**Review Note:** Are these the correct policy thresholds? Library staff should confirm before this is built.

---

### **5.4 Digital Resource Navigator (navigator.md)**

**Role:** Guides students to the right research databases and formats citations.

**Capabilities:** \- Match a research topic to the most relevant subscription database \- Return a direct guidance message with the database name and access instructions \- Format a URL or book title into a valid APA 7th edition citation \- Format a URL or book title into a valid MLA 9th edition citation \- Detect citation type (webpage, journal article, book) from URL structure

**Tools available:** \- match\_database(topic) — returns recommended database(s) from a curated list \- format\_apa\_citation(source) — returns formatted APA 7 citation string \- format\_mla\_citation(source) — returns formatted MLA 9 citation string \- detect\_source\_type(url) — returns “article”, “book”, “webpage”, etc.

**Supported databases (mock list):** \- IEEE Xplore — Computer science, electrical engineering \- JSTOR — Humanities, social sciences \- PubMed — Biomedical and life sciences \- ScienceDirect (Elsevier) — Natural sciences, engineering \- ProQuest — Multidisciplinary, theses/dissertations \- Google Scholar — General (free fallback)

**Citation behavior rules:** \- Always ask the user which format they need (APA or MLA) if not specified \- Return the formatted citation in a copyable code block \- If URL is broken or unresolvable, note this in the output and provide a best-effort citation

---

### **5.5 Maintenance & Inventory Agent (maintenance.md)**

**Role:** Internal operations — tracks overdue items, fines, damage reports, and inventory health.

**Capabilities:** \- Scan the Loans table for overdue items and calculate late fees \- Generate a pending actions summary for a specific student \- Flag a book as damaged and create a repair ticket in the Tickets table \- Identify low-circulation books (checked out \< 2 times in the past year) \- Identify high-demand books (waitlist or checkout count above threshold) \- Send overdue fine notices (simulated — outputs a formatted notice string) \- Verify if a student has overdue items (called by other agents)

**Tools available:** \- get\_overdue\_loans(user\_id=None) — returns all overdue loans, optionally filtered by user \- calculate\_late\_fee(loan\_id) — returns fee amount based on days overdue × rate \- create\_damage\_ticket(book\_id, description) — writes to Tickets table AND sets Books.status to 'repair', decrements Books.available\_copies \- get\_inventory\_health() — returns low-circulation and high-demand book lists \- has\_overdue\_items(user\_id) — returns boolean (used by Space Manager) \- generate\_fine\_notice(user\_id) — returns formatted overdue notice

**Fee calculation rules:** \- Rate: PHP 5.00 per day overdue (adjustable in config) \- Grace period: 1 day after due date before fee applies \- Maximum fee cap: PHP 500.00 per item \- Fee waiver threshold: items damaged in transit (requires staff override)

**Review Note:** Confirm the fee rate and currency with library administration before development.

---

## **6\. Inter-Agent Communication Protocol**

### **6.1 How the Task Tool Works in .md Files**

Each agent .md file includes a section describing when and how to call other agents. The syntax Claude Code expects looks like this inside the .md instruction:

\#\# Delegating to other agents

If the user's request involves overdue status, use the Task tool:  
  \- Agent file: maintenance.md  
  \- Pass: { user\_id: \[current user\_id\], action: "check\_overdue" }  
  \- Wait for result before proceeding

Claude Code handles the actual spawning. The calling agent pauses, receives the sub-agent’s output, and continues its own response.

### **6.2 Defined Cross-Agent Calls**

| Calling Agent | Called Agent | Trigger Condition |
| :---- | :---- | :---- |
| orchestrator.md | Any sub-agent | Every user request |
| librarian.md | maintenance.md | Book flagged as unavailable or on repair |
| space-manager.md | maintenance.md | Before confirming any booking |
| maintenance.md | space-manager.md | When a staff member explicitly requests suspension of a student: maintenance.md calls space-manager.md to cancel that student's upcoming confirmed bookings |

### **6.3 Error Handling**

* If a sub-agent call fails: the calling agent must surface the error to the user, not silently skip

* If the database is locked or unavailable: return a clear message and do not retry infinitely

* If required context (e.g., user\_id) is missing: ask the user before proceeding

---

## **7\. Shared Data Layer**

### **7.1 Database: library.db (SQLite)**

All agents share a single SQLite file. No agent has its own private storage.

### **7.2 Table Schemas**

**Books**

book\_id       INTEGER PRIMARY KEY  
title         TEXT NOT NULL  
author        TEXT NOT NULL  
genre         TEXT  
tags          TEXT  (comma-separated)  
abstract      TEXT  
total\_copies  INTEGER  
available\_copies INTEGER  
status        TEXT  ('available', 'repair', 'retired')

**Users**

user\_id       INTEGER PRIMARY KEY
name          TEXT NOT NULL
email         TEXT
role          TEXT  ('student', 'faculty', 'staff')

Note: weekly hours used is always computed dynamically from the Bookings table via get\_user\_weekly\_hours(user\_id) — it is not stored as a column to prevent stale data.

**Loans**

loan\_id       INTEGER PRIMARY KEY  
user\_id       INTEGER REFERENCES Users  
book\_id       INTEGER REFERENCES Books  
loan\_date     TEXT  
due\_date      TEXT  
return\_date   TEXT  (NULL if not returned)  
status        TEXT  ('active', 'returned', 'overdue')

**Rooms**

room\_id       INTEGER PRIMARY KEY  
name          TEXT  
capacity      INTEGER  
type          TEXT  ('quiet\_pod', 'group\_room', 'computer\_lab')  
floor         INTEGER

**Bookings**

booking\_id    INTEGER PRIMARY KEY  
user\_id       INTEGER REFERENCES Users  
room\_id       INTEGER REFERENCES Rooms  
start\_time    TEXT  
end\_time      TEXT  
status        TEXT  ('confirmed', 'cancelled', 'completed')

**Tickets**

ticket\_id     INTEGER PRIMARY KEY  
book\_id       INTEGER REFERENCES Books  
reported\_by   INTEGER REFERENCES Users  
issue\_type    TEXT  ('damaged', 'missing', 'low\_toner', 'other')  
description   TEXT  
status        TEXT  ('open', 'in\_progress', 'resolved')  
created\_at    TEXT

### **7.3 tools.py Responsibilities**

tools.py is a single Python file containing all functions called by agents. It is not an agent itself — it is a utility layer.

**Invocation mechanism:** Agents call tools.py via the Bash tool using a CLI dispatch pattern. Example:

```
python tools.py search_books --query "machine learning beginner"
python tools.py create_booking --user_id 4 --room_id 2 --start_time "2026-03-25T15:00" --duration 2
```

tools.py uses argparse (or equivalent) to expose each function as a subcommand. Output is always printed as JSON to stdout so agents can parse it.

**Every function must:**
\- Accept clearly typed parameters
\- Return a dictionary or list as JSON (never raw SQL rows)
\- Handle database connection and closure internally
\- Raise a descriptive exception on failure (not return None silently)

**Complete function list:**

| Function | Agent(s) | Description |
| :---- | :---- | :---- |
| search\_books(query, fuzzy) | librarian | Returns ranked list from Books table |
| get\_book\_abstract(book\_id) | librarian | Returns full abstract |
| suggest\_related(book\_id) | librarian | Returns 3 related books by genre/tags |
| check\_availability(book\_id) | librarian | Returns available copy count |
| check\_room\_availability(date, time, capacity) | space-manager | Returns available rooms |
| create\_booking(user\_id, room\_id, start\_time, duration) | space-manager | Writes to Bookings table |
| cancel\_booking(booking\_id) | space-manager, maintenance | Cancels a booking |
| get\_user\_weekly\_hours(user\_id) | space-manager | Computes hours used this week from Bookings |
| get\_upcoming\_bookings(user\_id) | space-manager | Returns user's scheduled bookings |
| match\_database(topic) | navigator | Returns recommended database(s) from curated list |
| format\_apa\_citation(source) | navigator | Returns formatted APA 7 citation string |
| format\_mla\_citation(source) | navigator | Returns formatted MLA 9 citation string |
| detect\_source\_type(url) | navigator | Returns "article", "book", "webpage", etc. |
| get\_overdue\_loans(user\_id) | maintenance | Returns overdue loans, optionally filtered by user |
| calculate\_late\_fee(loan\_id) | maintenance | Returns fee based on days overdue × rate from config |
| create\_damage\_ticket(book\_id, description) | maintenance | Writes to Tickets; sets Books.status to 'repair'; decrements available\_copies |
| get\_inventory\_health() | maintenance | Returns low-circulation and high-demand book lists |
| has\_overdue\_items(user\_id) | maintenance, space-manager | Returns boolean |
| generate\_fine\_notice(user\_id) | maintenance | Returns formatted overdue notice string |

---

## **8\. CLI Interface Requirements**

### **8.1 Entry Point**

The system is launched with a single command from the project root:

```
claude
```

Claude Code reads CLAUDE.md on startup, which instructs it to act as the orchestrator. No flags are needed. The session is interactive — the user types requests and receives responses in a continuous loop.

### **8.2 User Identification**

On first launch (or if user\_id is not set), the system asks:

Welcome to the Library Agent System.  
Please enter your Student/Staff ID to continue:

The user\_id is stored in session context and passed to every agent call.

### **8.3 Response Format Standards**

All agents must follow these output conventions:

* Lead with the direct answer or result

* Use plain text — no markdown headers in CLI output

* Tables are acceptable for lists (rooms, books, loans)

* Errors are prefixed with \[ERROR\]

* Confirmations are prefixed with \[CONFIRMED\]

* Warnings are prefixed with \[WARNING\]

### **8.4 Commands Available to Users**

| Command | Behavior |
| :---- | :---- |
| Any natural language | Routed by orchestrator |
| help | Lists example queries for each agent |
| my bookings | Shortcut to Space Manager |
| my loans | Shortcut to Maintenance Agent |
| exit / quit | Closes the session |

---

## **9\. Mock Data Requirements**

Since this system uses no live integrations, seed\_db.py must generate realistic mock data:

| Table | Minimum rows | Notes |
| :---- | :---- | :---- |
| Books | 30 | Mix of genres, some unavailable, some on repair |
| Users | 15 | Mix of students and staff, some with overdue items |
| Loans | 25 | Mix of active, returned, and overdue |
| Rooms | 8 | Mix of pod types and group rooms |
| Bookings | 20 | Mix of past, upcoming, and cancelled |
| Tickets | 10 | Mix of open and resolved |

**Required edge cases in mock data:** \- At least 3 users with overdue loans (for testing Maintenance Agent) \- At least 2 users at or near the weekly booking hour limit (for testing Space Manager policy) \- At least 2 books on repair hold (for testing cross-agent Librarian → Maintenance call) \- At least 1 student who is blocked from booking due to overdue suspension

---

## **10\. Agent File Structure**

Each .md agent file follows this standard structure:

\# \[Agent Name\]

\#\# Role  
One sentence describing what this agent does.

\#\# Capabilities  
Bullet list of what this agent can do.

\#\# Tools Available  
List of tool function names from tools.py this agent is allowed to call.

\#\# Delegation Rules  
When and how to call other agents via the Task tool.

\#\# Response Format  
How to format the output for CLI display.

\#\# Policy Rules  
Business rules this agent must enforce automatically.

\#\# Error Handling  
What to do when things go wrong.

---

## **11\. Out of Scope (for this version)**

The following are explicitly excluded from v1.0:

* Web UI or mobile interface

* Live integration with real library databases (JSTOR, OPAC, etc.)

* Email or push notifications

* Authentication / login system (user\_id is entered manually)

* Multi-library or multi-branch support

* Real-time printer or hardware monitoring

* PDF or document uploads

---

## **12\. Open Questions & Review Notes**

These items require team input before development begins:

1. **Late fee rate and currency** — Is PHP 5.00/day the correct rate? Who approves fee waivers?

2. **Booking policy thresholds** — Confirm 10-hour/week limit, 4-hour max, 30-min advance notice

3. **Overdue suspension threshold** — Is 14 days the correct cutoff for blocking room bookings?

4. **Database subscriptions list** — Is the 6-database list accurate for your institution?

5. **Student ID format** — What format does user\_id take? (numeric, alphanumeric, etc.)

6. **Citation formats** — Is APA 7 and MLA 9 sufficient, or are other formats needed?

7. **Agent routing edge cases** — What should happen if a request spans two agents equally? (e.g., “Find me a book and book me a room to read it in”)

8. **Staff vs. student permissions** — Should staff have different booking limits or fine rules?

**Instructions for reviewers:** Please annotate this document with comments or suggested changes. Once all open questions are resolved and the team signs off, a separate Claude Code PRD will be generated from this document to drive actual development.

---

*End of Document — Library Maintenance & Resource Agent System PRD v1.0*  
*Status: Draft — For Human Review*