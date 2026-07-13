"""
migrate_master_data_model.py - Run this ONCE on the online server after
deploying this update (including on Render - see notes below).

Adds the master-data-model changes to an existing database without
touching any data already in it:
  - courses.lecturer_id
  - exams.invigilator_name
  - students.faculty, students.rfid_card_uid, students.photo_path
  - registrations.course_registration_confirmed
  - the new course_registrations table

Safe to run more than once - each change is guarded by a check against
the current schema, so already-applied changes are skipped.

Usage:
    python3 migrate_master_data_model.py

On Render: open a shell for your service (Dashboard -> your service ->
Shell tab) and run the same command there, since this needs to run
against the actual deployed database file, not your local copy.
"""
import database as db


def has_column(conn, table, column) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def table_exists(conn, table) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


if __name__ == "__main__":
    conn = db.get_db()
    applied = []

    if not has_column(conn, "courses", "lecturer_id"):
        conn.execute("ALTER TABLE courses ADD COLUMN lecturer_id INTEGER REFERENCES lecturers(id)")
        applied.append("courses.lecturer_id")

    if not has_column(conn, "exams", "invigilator_name"):
        conn.execute("ALTER TABLE exams ADD COLUMN invigilator_name TEXT")
        applied.append("exams.invigilator_name")

    if not has_column(conn, "students", "faculty"):
        conn.execute("ALTER TABLE students ADD COLUMN faculty TEXT")
        applied.append("students.faculty")

    if not has_column(conn, "students", "rfid_card_uid"):
        conn.execute("ALTER TABLE students ADD COLUMN rfid_card_uid TEXT")
        applied.append("students.rfid_card_uid")

    if not has_column(conn, "students", "photo_path"):
        conn.execute("ALTER TABLE students ADD COLUMN photo_path TEXT")
        applied.append("students.photo_path")

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_students_rfid_card "
        "ON students(rfid_card_uid) WHERE rfid_card_uid IS NOT NULL"
    )

    if not has_column(conn, "registrations", "course_registration_confirmed"):
        conn.execute(
            "ALTER TABLE registrations ADD COLUMN course_registration_confirmed "
            "INTEGER NOT NULL DEFAULT 1"
        )
        applied.append("registrations.course_registration_confirmed")

    if not table_exists(conn, "course_registrations"):
        conn.execute("""
            CREATE TABLE course_registrations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id      INTEGER NOT NULL REFERENCES students(id),
                course_id       INTEGER NOT NULL REFERENCES courses(id),
                registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (student_id, course_id)
            )
        """)
        conn.execute("CREATE INDEX idx_course_registrations_course ON course_registrations(course_id)")
        conn.execute("CREATE INDEX idx_course_registrations_student ON course_registrations(student_id)")
        applied.append("course_registrations (new table)")

    conn.commit()
    conn.close()

    if applied:
        print("Applied:")
        for item in applied:
            print(f"  - {item}")
    else:
        print("Already up to date - nothing to do.")
