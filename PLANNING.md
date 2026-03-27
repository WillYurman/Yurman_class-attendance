# Class Attendance Tracker — Planning Notes

> Quick-reference doc for Claude and Andrew to orient quickly at the start of any session.
> Last updated: 2026-03-27

---

## What This Is

A web-based attendance tracker for UO SOJC faculty. Built to replace manual roll calls and easily-gamed "Word of the Day" methods. Students check in via a time-limited QR code and write a substantive reflection (25+ words). Instructors review submissions, flag questionable entries, and export end-of-term grade impact reports.

**Primary user:** Andrew DeVigal, JCOM 332 Public Affairs Journalism, Spring 2026 (18 students, T/R 12:00–13:50)
**Secondary users:** Other SOJC faculty — must be easy to fork and self-deploy

---

## Current Status

Active development, pre-live. Spring 2026 term begins soon. Core features are complete. Recent work has focused on UI polish and PostgreSQL/Render deployment.

---

## How to Run Locally

```bash
cd "/Users/adevigal/Documents/1. Agora/2026/Class Attendance/attendance-tracker"
source .venv/bin/activate
python run.py
# → http://localhost:8080
```

---

## Tech Stack & Why

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python + Flask | Simple, readable, easy for non-devs to understand |
| Database | SQLite (local) / PostgreSQL (Render) | Zero-config locally; Render requires Postgres |
| Frontend | Vanilla HTML/CSS/JS | No build toolchain; easy to maintain |
| Export | openpyxl (.xlsx) | Faculty expect Excel |
| AI | Anthropic API (Claude) | Reflection summarization per session |
| Hosting | Render (free tier) | Easy fork-and-deploy for other faculty |

---

## Key Files Map

```
attendance-tracker/
├── run.py                        # Entry point — starts Flask on port 8080
├── app/
│   ├── __init__.py               # App factory, DB init, blueprint registration
│   ├── models.py                 # Course, Student, Session, Attendance (SQLAlchemy)
│   ├── routes/
│   │   ├── instructor.py         # All instructor-facing routes (dashboard, setup, export)
│   │   └── student.py            # Student check-in form route
│   ├── utils/
│   │   ├── pdf_parser.py         # Parses DuckWeb PDF / Excel rosters → Student records
│   │   ├── qr_generator.py       # Generates QR code as base64 for display
│   │   ├── export.py             # Builds .xlsx export (3 sheets: grid, summary, reflections)
│   │   ├── anti_gaming.py        # IP hash dedup + duplicate name detection
│   │   └── summarize.py          # Claude API — summarizes session reflections
│   └── templates/                # Jinja2 HTML templates
│       ├── instructor/           # Dashboard, setup, session detail, grid
│       └── student/              # Check-in form
├── instance/
│   └── attendance.db             # SQLite DB (local dev only, gitignored)
├── .env                          # SECRET_KEY, ANTHROPIC_API_KEY, FLASK_ENV
├── render.yaml                   # Render deployment config (PostgreSQL + persistent disk)
└── requirements.txt              # Python deps
```

---

## Data Model (Quick Reference)

- **Course** — one per class section; holds roster, policy config, and a permanent check-in token
- **Student** — name only (no UO ID, no email — privacy by design); belongs to a Course
- **Session** — one per class meeting; has a unique time-limited token, open/close window, reflection prompt
- **Attendance** — one record per student per session; status = `present` | `absent` | `flagged`; stores reflection text, IP hash, instructor note

---

## Instructor Route Map

| URL | Purpose |
|---|---|
| `/` | Home — list all courses |
| `/setup` | Create course (upload DuckWeb PDF/Excel or enter names manually) |
| `/course/<id>` | Course dashboard — attendance grid |
| `/course/<id>/session/new` | Open a new session (generates QR) |
| `/course/<id>/session/<sid>` | Live session view — QR, submissions, flag review |
| `/course/<id>/session/<sid>/close` | Close the check-in window |
| `/course/<id>/export` | Download .xlsx grade impact report |
| `/attendance/<id>/accept` | Accept a flagged record → mark present |
| `/attendance/<id>/reject` | Reject a flagged record → mark absent |

Student check-in: `/checkin/<course_token>/<session_token>`

---

## Attendance Policy (Default)

Karen McIntyre's model — configurable per course at setup:
- **2 free absences** (no penalty)
- **−5% final grade** per absence after that
- Flagged submissions (late, short reflection, duplicate IP) held for instructor review — never silently rejected

---

## Key Design Decisions (Don't Undo Without Reason)

1. **No UO ID or email stored** — student name only. IP stored as one-way SHA256 hash for fraud detection only.
2. **Flagged ≠ rejected** — instructors always make the final call on edge cases.
3. **Permanent course token + per-session token** — course token is reused each term; session token is unique and time-limited.
4. **PostgreSQL on Render, SQLite locally** — `DATABASE_URL` env var controls which is used; app factory handles `postgres://` → `postgresql://` rewrite automatically.
5. **Faculty fork model** — each instructor runs their own Render instance from a GitHub fork. No shared multi-tenant backend.

---

## Known Issues / Watch Areas

- Render free tier spins down after inactivity — first request after sleep is slow (~30s). Acceptable for current use.
- SQLite → PostgreSQL migration: `migrate_course_tokens.py` exists for moving existing data if needed.
- `summarize.py` uses the Anthropic API — requires `ANTHROPIC_API_KEY` in `.env`.

---

## Roadmap / Possible Next Steps

- [ ] Email/notification when session closes (optional, nice-to-have)
- [ ] Multi-course support tested with a second faculty member
- [ ] "Faculty Quick Start" guide (`.docx` was removed from nav — may need a separate landing page)
- [ ] Consider adding a simple auth layer if deployed for multiple instructors on one instance
