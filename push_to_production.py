"""
Push local SQLite data to the Neon PostgreSQL production database.

WARNING: This will REPLACE all data in production with your local data.

Usage:
    DATABASE_URL="postgresql://..." .venv/bin/python3 push_to_production.py

The DATABASE_URL is the Neon connection string from your Render environment variables.
"""

import os
import sys
import sqlite3

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "instance", "attendance.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    print("ERROR: DATABASE_URL is not set.")
    print("Run as:  DATABASE_URL='postgresql://...' .venv/bin/python3 push_to_production.py")
    sys.exit(1)

# Remove channel_binding parameter if present (not supported by all psycopg2 builds)
if "channel_binding" in DATABASE_URL:
    base, _, params = DATABASE_URL.partition("?")
    filtered = "&".join(p for p in params.split("&") if "channel_binding" not in p)
    DATABASE_URL = base + ("?" + filtered if filtered else "")

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Run: .venv/bin/pip install psycopg2-binary")
    sys.exit(1)

print("Connecting to local SQLite...")
src = sqlite3.connect(SQLITE_PATH)
src.row_factory = sqlite3.Row

print("Connecting to Neon PostgreSQL...")
try:
    dst = psycopg2.connect(DATABASE_URL)
except Exception as e:
    print(f"ERROR connecting to production database: {e}")
    sys.exit(1)

print()
print("WARNING: This will replace ALL data in the production database.")
confirm = input("Type 'yes' to continue: ").strip().lower()
if confirm != "yes":
    print("Aborted.")
    src.close()
    dst.close()
    sys.exit(0)

try:
    cur = dst.cursor()

    # Drop and recreate tables with correct types
    print("\nResetting production schema...")
    cur.execute("DROP TABLE IF EXISTS attendance CASCADE")
    cur.execute("DROP TABLE IF EXISTS sessions CASCADE")
    cur.execute("DROP TABLE IF EXISTS students CASCADE")
    cur.execute("DROP TABLE IF EXISTS courses CASCADE")
    cur.execute("""
        CREATE TABLE courses (
            id SERIAL PRIMARY KEY,
            crn TEXT, course_name TEXT, term TEXT, term_code TEXT, credits TEXT,
            meeting_days TEXT, meeting_time TEXT, location TEXT, instructor_name TEXT,
            free_absences INTEGER DEFAULT 2, deduction_per_absence FLOAT DEFAULT 5.0,
            deduction_model TEXT, default_window_minutes INTEGER DEFAULT 10,
            default_reflection_prompt TEXT, created_at TIMESTAMP, token TEXT UNIQUE
        )
    """)
    cur.execute("""
        CREATE TABLE students (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id),
            last_name TEXT, first_name TEXT, middle_initial TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE sessions (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id),
            session_number INTEGER, session_date DATE, token TEXT UNIQUE,
            open_at TIMESTAMP, close_at TIMESTAMP, reflection_prompt TEXT, summary TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE attendance (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES sessions(id),
            student_id INTEGER REFERENCES students(id),
            submitted_at TIMESTAMP, reflection_text TEXT, ip_hash TEXT,
            status TEXT, flag_reasons TEXT, instructor_note TEXT
        )
    """)

    # Clear production tables in dependency order
    print("Clearing production data...")
    cur.execute("TRUNCATE TABLE attendance, sessions, students, courses RESTART IDENTITY CASCADE")

    # ── Courses ──────────────────────────────────────────────────────────────
    rows = src.execute("SELECT * FROM courses ORDER BY id").fetchall()
    print(f"Inserting {len(rows)} course(s)...")
    for r in rows:
        cur.execute("""
            INSERT INTO courses
              (id, crn, course_name, term, term_code, credits, meeting_days, meeting_time,
               location, instructor_name, free_absences, deduction_per_absence, deduction_model,
               default_window_minutes, default_reflection_prompt, created_at, token)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            r["id"], r["crn"], r["course_name"], r["term"], r["term_code"],
            r["credits"], r["meeting_days"], r["meeting_time"], r["location"],
            r["instructor_name"], r["free_absences"], r["deduction_per_absence"],
            r["deduction_model"], r["default_window_minutes"],
            r["default_reflection_prompt"], r["created_at"], r["token"],
        ))
    cur.execute("SELECT setval('courses_id_seq', (SELECT MAX(id) FROM courses))")

    # ── Students ─────────────────────────────────────────────────────────────
    rows = src.execute("SELECT * FROM students ORDER BY id").fetchall()
    print(f"Inserting {len(rows)} student(s)...")
    for r in rows:
        cur.execute("""
            INSERT INTO students (id, course_id, last_name, first_name, middle_initial)
            VALUES (%s,%s,%s,%s,%s)
        """, (r["id"], r["course_id"], r["last_name"], r["first_name"], r["middle_initial"]))
    cur.execute("SELECT setval('students_id_seq', (SELECT MAX(id) FROM students))")

    # ── Sessions ─────────────────────────────────────────────────────────────
    rows = src.execute("SELECT * FROM sessions ORDER BY id").fetchall()
    print(f"Inserting {len(rows)} session(s)...")
    for r in rows:
        cur.execute("""
            INSERT INTO sessions
              (id, course_id, session_number, session_date, token, open_at, close_at,
               reflection_prompt, summary)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            r["id"], r["course_id"], r["session_number"], r["session_date"],
            r["token"], r["open_at"], r["close_at"],
            r["reflection_prompt"], r["summary"],
        ))
    cur.execute("SELECT setval('sessions_id_seq', (SELECT MAX(id) FROM sessions))")

    # ── Attendance ────────────────────────────────────────────────────────────
    rows = src.execute("SELECT * FROM attendance ORDER BY id").fetchall()
    print(f"Inserting {len(rows)} attendance record(s)...")
    for r in rows:
        cur.execute("""
            INSERT INTO attendance
              (id, session_id, student_id, submitted_at, reflection_text, ip_hash,
               status, flag_reasons, instructor_note)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            r["id"], r["session_id"], r["student_id"], r["submitted_at"],
            r["reflection_text"], r["ip_hash"], r["status"],
            r["flag_reasons"], r["instructor_note"],
        ))
    cur.execute("SELECT setval('attendance_id_seq', (SELECT MAX(id) FROM attendance))")

    dst.commit()
    print("\nDone! Production database is now in sync with your local data.")

except Exception as e:
    dst.rollback()
    print(f"\nERROR: {e}")
    raise

finally:
    src.close()
    dst.close()
