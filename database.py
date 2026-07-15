"""
database.py - SQLite access layer for the online pre-registration server.
"""
import sqlite3
import secrets
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "online.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------
# Lecturers / courses / exams (test/demo helpers for the QR page)
# ---------------------------------------------------------------

def get_or_create_lecturer(full_name: str) -> int:
    conn = get_db()
    staff_no = "demo-" + re_slug(full_name)
    row = conn.execute("SELECT id FROM lecturers WHERE staff_no = ?", (staff_no,)).fetchone()
    if row:
        conn.close()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO lecturers (staff_no, full_name) VALUES (?, ?)",
        (staff_no, full_name),
    )
    conn.commit()
    lecturer_id = cur.lastrowid
    conn.close()
    return lecturer_id


def re_slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-") or "unknown"


def get_or_create_course(course_code: str, title: str) -> int:
    conn = get_db()
    course_code = course_code.strip().upper()
    row = conn.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,)).fetchone()
    if row:
        conn.close()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO courses (course_code, title) VALUES (?, ?)",
        (course_code, title),
    )
    conn.commit()
    course_id = cur.lastrowid
    conn.close()
    return course_id


class CourseHasNoLecturerError(Exception):
    pass


def create_exam_from_course(course_id: int, invigilator_name: str, title: str,
                             exam_date: str, venue: str) -> dict:
    """
    Replaces the old create_exam(): courses are now selected from the
    existing master catalog (see Phase 1), not typed in ad hoc, so this
    takes a course_id and derives lecturer_id from the course record
    rather than accepting one directly. invigilator_name is free text -
    the person invigilating a sitting isn't necessarily the course's own
    lecturer.
    """
    course = get_course_by_id(course_id)
    if not course:
        raise ValueError(f"Course id {course_id} not found")
    if not course["lecturer_id"]:
        raise CourseHasNoLecturerError(
            f"{course['course_code']} has no lecturer assigned - update the course record first"
        )

    token = secrets.token_urlsafe(16)
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO exams (course_id, lecturer_id, invigilator_name, title, exam_date, venue, registration_token)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (course_id, course["lecturer_id"], invigilator_name, title, exam_date, venue, token),
    )
    conn.commit()
    exam_id = cur.lastrowid
    conn.close()
    return {"id": exam_id, "registration_token": token}


def list_exams() -> list:
    conn = get_db()
    rows = conn.execute(
        """SELECT e.id, e.title, e.exam_date, e.venue, e.registration_token, e.created_at,
                  e.invigilator_name, c.course_code,
                  (SELECT COUNT(*) FROM registrations r WHERE r.exam_id = e.id) AS registration_count
           FROM exams e JOIN courses c ON c.id = e.course_id
           ORDER BY e.created_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_exam_by_token(token: str):
    conn = get_db()
    row = conn.execute(
        """SELECT e.id, e.title, e.exam_date, e.venue, e.registration_opens, e.registration_closes,
                  c.course_code, c.id AS course_id
           FROM exams e JOIN courses c ON c.id = e.course_id
           WHERE e.registration_token = ?""",
        (token,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_exam_by_id(exam_id: int):
    conn = get_db()
    row = conn.execute(
        """SELECT e.id, e.title, e.exam_date, e.venue, e.registration_token,
                  e.registration_opens, e.registration_closes, e.created_at, e.invigilator_name,
                  c.course_code, c.title AS course_title
           FROM exams e JOIN courses c ON c.id = e.course_id
           WHERE e.id = ?""",
        (exam_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_registrations_for_exam(exam_id: int) -> list:
    conn = get_db()
    rows = conn.execute(
        """SELECT r.id AS registration_id, r.registered_at, r.status, r.course_registration_confirmed,
                  s.id AS student_id, s.matric_no, s.full_name, s.department,
                  s.level, s.email, s.phone, s.rfid_card_uid
           FROM registrations r JOIN students s ON s.id = r.student_id
           WHERE r.exam_id = ?
           ORDER BY r.registered_at DESC""",
        (exam_id,),
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        d["face_captures"] = list_face_captures_for_student(d["student_id"])
        results.append(d)
    return results


def list_face_captures_for_student(student_id: int) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, angle_label, capture_order FROM face_captures WHERE student_id = ? ORDER BY capture_order",
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_face_capture(capture_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM face_captures WHERE id = ?", (capture_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------
# Students / registrations / face captures
# ---------------------------------------------------------------

def find_student_by_matric(matric_no: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM students WHERE matric_no = ?", (matric_no,)).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_student(matric_no: str, full_name: str, department: str, level: str,
                    email: str = None, phone: str = None) -> int:
    existing = find_student_by_matric(matric_no)
    conn = get_db()
    if existing:
        conn.execute(
            """UPDATE students SET full_name=?, department=?, level=?, email=?, phone=?, updated_at=?
               WHERE id=?""",
            (full_name, department, level, email, phone, now(), existing["id"]),
        )
        conn.commit()
        conn.close()
        return existing["id"]
    cur = conn.execute(
        """INSERT INTO students (matric_no, full_name, department, level, email, phone)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (matric_no, full_name, department, level, email, phone),
    )
    conn.commit()
    student_id = cur.lastrowid
    conn.close()
    return student_id


def get_existing_registration(exam_id: int, student_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM registrations WHERE exam_id = ? AND student_id = ?",
        (exam_id, student_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_exam_sync_status(exam_id: int, since: str = None) -> dict:
    conn = get_db()
    since = since or "1970-01-01 00:00:00"

    new_regs = conn.execute(
        "SELECT COUNT(*) AS c FROM registrations WHERE exam_id = ? AND registered_at > ?",
        (exam_id, since),
    ).fetchone()["c"]

    updated_students = conn.execute(
        """SELECT COUNT(*) AS c FROM registrations r
           JOIN students s ON s.id = r.student_id
           WHERE r.exam_id = ? AND r.registered_at <= ? AND s.updated_at > ?""",
        (exam_id, since, since),
    ).fetchone()["c"]

    latest_row = conn.execute(
        """SELECT MAX(ts) AS latest FROM (
               SELECT registered_at AS ts FROM registrations WHERE exam_id = ?
               UNION ALL
               SELECT s.updated_at AS ts FROM registrations r
                   JOIN students s ON s.id = r.student_id WHERE r.exam_id = ?
           )""",
        (exam_id, exam_id),
    ).fetchone()
    conn.close()

    return {
        "new_registrations": new_regs,
        "updated_students": updated_students,
        "is_stale": (new_regs > 0 or updated_students > 0),
        "latest_change_at": latest_row["latest"] if latest_row else None,
    }


def create_registration(exam_id: int, student_id: int, course_registration_confirmed: bool = True) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO registrations (exam_id, student_id, course_registration_confirmed) VALUES (?, ?, ?)",
        (exam_id, student_id, 1 if course_registration_confirmed else 0),
    )
    conn.commit()
    reg_id = cur.lastrowid
    conn.close()
    return reg_id


def save_face_capture(student_id: int, image_path: str, angle_label: str, capture_order: int):
    conn = get_db()
    conn.execute(
        """INSERT INTO face_captures (student_id, image_path, angle_label, capture_order)
           VALUES (?, ?, ?, ?)""",
        (student_id, image_path, angle_label, capture_order),
    )
    conn.commit()
    conn.close()


def count_face_captures(student_id: int) -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM face_captures WHERE student_id = ?", (student_id,)
    ).fetchone()
    conn.close()
    return row["c"]


# ---------------------------------------------------------------
# Master data model: lecturers, courses, course registrations
# ---------------------------------------------------------------

def upsert_lecturer(staff_no: str, full_name: str, email: str = None) -> int:
    conn = get_db()
    row = conn.execute("SELECT id FROM lecturers WHERE staff_no = ?", (staff_no,)).fetchone()
    if row:
        conn.execute("UPDATE lecturers SET full_name=?, email=? WHERE id=?", (full_name, email, row["id"]))
        conn.commit()
        conn.close()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO lecturers (staff_no, full_name, email) VALUES (?, ?, ?)",
        (staff_no, full_name, email),
    )
    conn.commit()
    lecturer_id = cur.lastrowid
    conn.close()
    return lecturer_id


def upsert_course(course_code: str, title: str, lecturer_id: int = None) -> int:
    conn = get_db()
    course_code = course_code.strip().upper()
    row = conn.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,)).fetchone()
    if row:
        conn.execute("UPDATE courses SET title=?, lecturer_id=? WHERE id=?", (title, lecturer_id, row["id"]))
        conn.commit()
        conn.close()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO courses (course_code, title, lecturer_id) VALUES (?, ?, ?)",
        (course_code, title, lecturer_id),
    )
    conn.commit()
    course_id = cur.lastrowid
    conn.close()
    return course_id


def list_courses_for_dropdown() -> list:
    conn = get_db()
    rows = conn.execute(
        """SELECT c.id, c.course_code, c.title, l.full_name AS lecturer_name
           FROM courses c LEFT JOIN lecturers l ON l.id = c.lecturer_id
           ORDER BY c.course_code"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_course_by_id(course_id: int):
    conn = get_db()
    row = conn.execute(
        """SELECT c.*, l.full_name AS lecturer_name
           FROM courses c LEFT JOIN lecturers l ON l.id = c.lecturer_id
           WHERE c.id = ?""",
        (course_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_master_student(matric_no: str, full_name: str, department: str, level: str,
                           email: str = None, phone: str = None, faculty: str = None,
                           rfid_card_uid: str = None, photo_path: str = None) -> int:
    conn = get_db()
    row = conn.execute("SELECT id FROM students WHERE matric_no = ?", (matric_no,)).fetchone()
    if row:
        conn.execute(
            """UPDATE students SET full_name=?, department=?, level=?, email=?, phone=?,
                                    faculty=?, rfid_card_uid=?, photo_path=?, updated_at=?
               WHERE id=?""",
            (full_name, department, level, email, phone, faculty, rfid_card_uid, photo_path, now(), row["id"]),
        )
        conn.commit()
        conn.close()
        return row["id"]
    cur = conn.execute(
        """INSERT INTO students (matric_no, full_name, department, level, email, phone,
                                  faculty, rfid_card_uid, photo_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (matric_no, full_name, department, level, email, phone, faculty, rfid_card_uid, photo_path),
    )
    conn.commit()
    student_id = cur.lastrowid
    conn.close()
    return student_id


def add_course_registration(student_id: int, course_id: int):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO course_registrations (student_id, course_id) VALUES (?, ?)",
        (student_id, course_id),
    )
    conn.commit()
    conn.close()


def is_student_registered_for_course(student_id: int, course_id: int) -> bool:
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM course_registrations WHERE student_id = ? AND course_id = ?",
        (student_id, course_id),
    ).fetchone()
    conn.close()
    return row is not None
