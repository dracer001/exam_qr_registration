"""
import_master_data.py - Bulk-imports the institution's existing records
into the master data model: lecturers, courses, students, and course
registrations. Run each step in order - later steps reference earlier
ones (courses need lecturers to exist, course_registrations need both
students and courses to exist).

Usage:
    python3 import_master_data.py lecturers lecturers.csv
    python3 import_master_data.py courses courses.csv
    python3 import_master_data.py students students.csv
    python3 import_master_data.py course_registrations course_registrations.csv

Expected CSV columns (header row required, extra columns are ignored):

  lecturers.csv:
    staff_no, full_name, email

  courses.csv:
    course_code, title, lecturer_staff_no
    (lecturer_staff_no must already exist - run lecturers.csv first)

  students.csv:
    matric_no, full_name, department, level, email, phone, faculty,
    rfid_card_uid, photo_path
    (email, phone, faculty, rfid_card_uid, photo_path may be blank;
    photo_path should be a path already reachable by the server, e.g.
    something you've separately uploaded to data/faces/)

  course_registrations.csv:
    matric_no, course_code
    (both must already exist - run students.csv and courses.csv first)

Re-running any step is safe - existing rows are updated, not duplicated.
"""
import csv
import sys
import database as db


def import_lecturers(path):
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            db.upsert_lecturer(
                staff_no=row["staff_no"].strip(),
                full_name=row["full_name"].strip(),
                email=(row.get("email") or "").strip() or None,
            )
            count += 1
    print(f"Imported/updated {count} lecturer(s).")


def import_courses(path):
    count = 0
    skipped = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            staff_no = (row.get("lecturer_staff_no") or "").strip()
            lecturer_id = None
            if staff_no:
                conn = db.get_db()
                lrow = conn.execute("SELECT id FROM lecturers WHERE staff_no = ?", (staff_no,)).fetchone()
                conn.close()
                if lrow:
                    lecturer_id = lrow["id"]
                else:
                    skipped.append(f"{row['course_code']} (lecturer_staff_no '{staff_no}' not found)")
            db.upsert_course(
                course_code=row["course_code"].strip(),
                title=row["title"].strip(),
                lecturer_id=lecturer_id,
            )
            count += 1
    print(f"Imported/updated {count} course(s).")
    if skipped:
        print("Warning - lecturer not found for these (course created without one):")
        for s in skipped:
            print(f"  - {s}")


def import_students(path):
    count = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            db.upsert_master_student(
                matric_no=row["matric_no"].strip(),
                full_name=row["full_name"].strip(),
                department=row["department"].strip(),
                level=row["level"].strip(),
                email=(row.get("email") or "").strip() or None,
                phone=(row.get("phone") or "").strip() or None,
                faculty=(row.get("faculty") or "").strip() or None,
                rfid_card_uid=(row.get("rfid_card_uid") or "").strip().upper() or None,
                photo_path=(row.get("photo_path") or "").strip() or None,
            )
            count += 1
    print(f"Imported/updated {count} student(s).")


def import_course_registrations(path):
    count = 0
    skipped = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            matric_no = row["matric_no"].strip()
            course_code = row["course_code"].strip().upper()
            student = db.find_student_by_matric(matric_no)
            conn = db.get_db()
            course = conn.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,)).fetchone()
            conn.close()
            if not student:
                skipped.append(f"{matric_no} -> {course_code} (student not found)")
                continue
            if not course:
                skipped.append(f"{matric_no} -> {course_code} (course not found)")
                continue
            db.add_course_registration(student["id"], course["id"])
            count += 1
    print(f"Imported {count} course registration(s).")
    if skipped:
        print(f"Skipped {len(skipped)} row(s):")
        for s in skipped[:20]:
            print(f"  - {s}")
        if len(skipped) > 20:
            print(f"  ...and {len(skipped) - 20} more")


COMMANDS = {
    "lecturers": import_lecturers,
    "courses": import_courses,
    "students": import_students,
    "course_registrations": import_course_registrations,
}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2])
