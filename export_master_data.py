"""
export_master_data.py - Dumps the CURRENT contents of the master data
tables (lecturers, courses, students, course_registrations) out to CSV
files you can open in Excel/Sheets/a text editor, edit, and then feed
back in with import_master_data.py (or seed_master_data.py).

This is the "let me see what's actually in the database" half of the
workflow: export -> edit the CSV -> re-import. The CSVs it writes use
the exact same columns import_master_data.py expects, so a round trip
(export, change a few cells, import) always works.

Usage:
    python3 export_master_data.py                  # writes into ./seed_data/
    python3 export_master_data.py /path/to/folder   # writes into a custom folder

Files written:
    lecturers.csv, courses.csv, students.csv, course_registrations.csv
"""
import csv
import os
import sys
import database as db

DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "seed_data")


def export_lecturers(out_dir):
    conn = db.get_db()
    rows = conn.execute("SELECT staff_no, full_name, email FROM lecturers ORDER BY staff_no").fetchall()
    conn.close()
    path = os.path.join(out_dir, "lecturers.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["staff_no", "full_name", "email"])
        for r in rows:
            w.writerow([r["staff_no"], r["full_name"], r["email"] or ""])
    print(f"Wrote {len(rows)} lecturer(s) -> {path}")


def export_courses(out_dir):
    conn = db.get_db()
    rows = conn.execute(
        """SELECT c.course_code, c.title, l.staff_no AS lecturer_staff_no
           FROM courses c LEFT JOIN lecturers l ON l.id = c.lecturer_id
           ORDER BY c.course_code"""
    ).fetchall()
    conn.close()
    path = os.path.join(out_dir, "courses.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["course_code", "title", "lecturer_staff_no"])
        for r in rows:
            w.writerow([r["course_code"], r["title"], r["lecturer_staff_no"] or ""])
    print(f"Wrote {len(rows)} course(s) -> {path}")


def export_students(out_dir):
    conn = db.get_db()
    rows = conn.execute(
        """SELECT matric_no, full_name, department, level, email, phone,
                  faculty, rfid_card_uid, photo_path
           FROM students ORDER BY matric_no"""
    ).fetchall()
    conn.close()
    path = os.path.join(out_dir, "students.csv")
    fields = ["matric_no", "full_name", "department", "level", "email", "phone",
              "faculty", "rfid_card_uid", "photo_path"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (r[k] or "") for k in fields})
    print(f"Wrote {len(rows)} student(s) -> {path}")
    print("  (edit the rfid_card_uid column here to assign/reassign RFID tags)")


def export_course_registrations(out_dir):
    conn = db.get_db()
    rows = conn.execute(
        """SELECT s.matric_no, c.course_code
           FROM course_registrations cr
           JOIN students s ON s.id = cr.student_id
           JOIN courses c ON c.id = cr.course_id
           ORDER BY s.matric_no, c.course_code"""
    ).fetchall()
    conn.close()
    path = os.path.join(out_dir, "course_registrations.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["matric_no", "course_code"])
        for r in rows:
            w.writerow([r["matric_no"], r["course_code"]])
    print(f"Wrote {len(rows)} course registration(s) -> {path}")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR
    os.makedirs(out_dir, exist_ok=True)
    export_lecturers(out_dir)
    export_courses(out_dir)
    export_students(out_dir)
    export_course_registrations(out_dir)
    print(f"\nDone. Edit the CSVs in {out_dir}/ then run:")
    print(f"  python3 seed_master_data.py {out_dir}")
