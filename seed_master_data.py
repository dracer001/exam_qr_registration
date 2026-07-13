"""
seed_master_data.py - "migrate fresh + seed" for the master data tables
(lecturers, courses, students, course_registrations).

This is a thin wrapper around import_master_data.py's four steps, run
in the correct dependency order from one folder of CSVs, so you don't
have to remember to call import_master_data.py four times by hand.

Normal mode (default) - upserts:
    python3 seed_master_data.py
    python3 seed_master_data.py /path/to/csv/folder
  Existing rows (matched by staff_no / course_code / matric_no) are
  updated in place; new rows are inserted. Nothing is deleted. Safe to
  re-run any time after editing the CSVs.

Fresh mode - wipes students + course_registrations first, then re-imports:
    python3 seed_master_data.py --fresh
    python3 seed_master_data.py --fresh /path/to/csv/folder
  Deletes all rows from course_registrations and students (face_captures
  go with them, since they belong to students), then imports all four
  CSVs from scratch. courses and lecturers are left alone and simply
  upserted, since they're matched by stable codes that didn't change.
  Use --fresh after changing a format (like the matric number format)
  so old rows in the old format don't linger alongside new ones.
  NOTE: this will refuse (and tell you exactly which students) if any
  student still has real exam registrations on file - it will not
  silently delete exam data. Clear those first if you really mean to
  wipe those students too.

CSV folder must contain: lecturers.csv, courses.csv, students.csv,
course_registrations.csv (see import_master_data.py for column docs).
Defaults to the seed_data/ folder next to this script.
"""
import os
import sys
import sqlite3
import database as db
import import_master_data as importer

DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "seed_data")


def wipe_master_tables():
    """
    Only wipes course_registrations and students - the two tables whose
    row identity is the matric number (the thing that just changed
    format). courses and lecturers are matched by stable codes
    (course_code / staff_no) that didn't change, so import_courses/
    import_lecturers already upsert them correctly without needing a
    wipe - and leaving them in place avoids tripping the exams ->
    courses foreign key for any exam sittings already created.
    """
    conn = db.get_db()
    try:
        blockers = conn.execute(
            """SELECT DISTINCT s.matric_no FROM students s
               JOIN registrations r ON r.student_id = s.id
               LIMIT 20"""
        ).fetchall()
        if blockers:
            names = ", ".join(r["matric_no"] for r in blockers)
            print(f"Refused to wipe: these students have real exam registrations on file: {names}")
            print("Remove/reassign those exam registrations first if you really want to wipe them too.")
            conn.close()
            sys.exit(1)

        conn.execute("DELETE FROM course_registrations")
        conn.execute("DELETE FROM face_captures")
        conn.execute("DELETE FROM students")
        conn.commit()
        print("Wiped course_registrations, face_captures, and students (courses/lecturers left as-is).")
    except sqlite3.IntegrityError as e:
        conn.rollback()
        print(f"Refused to wipe: {e}")
        sys.exit(1)
    finally:
        conn.close()


def run(csv_dir, fresh):
    for name in ("lecturers.csv", "courses.csv", "students.csv", "course_registrations.csv"):
        if not os.path.exists(os.path.join(csv_dir, name)):
            print(f"Missing {name} in {csv_dir}")
            sys.exit(1)

    if fresh:
        wipe_master_tables()

    print(f"\nSeeding from {csv_dir}/ ...\n")
    importer.import_lecturers(os.path.join(csv_dir, "lecturers.csv"))
    importer.import_courses(os.path.join(csv_dir, "courses.csv"))
    importer.import_students(os.path.join(csv_dir, "students.csv"))
    importer.import_course_registrations(os.path.join(csv_dir, "course_registrations.csv"))
    print("\nDone.")


if __name__ == "__main__":
    args = sys.argv[1:]
    fresh = "--fresh" in args
    args = [a for a in args if a != "--fresh"]
    csv_dir = args[0] if args else DEFAULT_DIR
    run(csv_dir, fresh)
