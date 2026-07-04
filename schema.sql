-- ============================================================
-- ONLINE (CLOUD) DATABASE SCHEMA
-- Hosts exam pre-registration. Reached via the QR code students scan.
-- SQLite, but portable to Postgres later if concurrency grows.
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lecturers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_no        TEXT UNIQUE NOT NULL,
    full_name       TEXT NOT NULL,
    email           TEXT UNIQUE,
    password_hash   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS courses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code     TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL
);

-- One row per exam sitting. registration_token is what the QR encodes:
-- https://<online-host>/register/<registration_token>
CREATE TABLE IF NOT EXISTS exams (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id           INTEGER NOT NULL REFERENCES courses(id),
    lecturer_id         INTEGER NOT NULL REFERENCES lecturers(id),
    title               TEXT NOT NULL,
    exam_date           TEXT NOT NULL,
    venue               TEXT,
    registration_token  TEXT UNIQUE NOT NULL,
    registration_opens  TEXT,
    registration_closes TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Master student identity record (persists across exams/semesters)
CREATE TABLE IF NOT EXISTS students (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matric_no       TEXT UNIQUE NOT NULL,
    full_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    department      TEXT NOT NULL,
    level           TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Captured face images, normalized so multiple angles can be stored
-- per student without bloating the student row.
CREATE TABLE IF NOT EXISTS face_captures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES students(id),
    image_path      TEXT NOT NULL,
    angle_label     TEXT,
    capture_order   INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A student pre-registering for a specific exam sitting
CREATE TABLE IF NOT EXISTS registrations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id         INTEGER NOT NULL REFERENCES exams(id),
    student_id      INTEGER NOT NULL REFERENCES students(id),
    registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
    status          TEXT NOT NULL DEFAULT 'registered'
                        CHECK (status IN ('registered', 'withdrawn')),
    UNIQUE (exam_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_registrations_exam ON registrations(exam_id);
CREATE INDEX IF NOT EXISTS idx_students_matric ON students(matric_no);
CREATE INDEX IF NOT EXISTS idx_face_captures_student ON face_captures(student_id);
