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
    title           TEXT NOT NULL,
    lecturer_id     INTEGER REFERENCES lecturers(id)
);

-- One row per exam sitting. registration_token is what the QR encodes:
-- https://<online-host>/register/<registration_token>
-- invigilator_name is free text set by the admin when creating the
-- sitting - the person invigilating isn't necessarily the course's own
-- lecturer_id, so this is deliberately not a foreign key.
CREATE TABLE IF NOT EXISTS exams (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id           INTEGER NOT NULL REFERENCES courses(id),
    lecturer_id         INTEGER NOT NULL REFERENCES lecturers(id),
    invigilator_name    TEXT,
    title               TEXT NOT NULL,
    exam_date           TEXT NOT NULL,
    venue               TEXT,
    registration_token  TEXT UNIQUE NOT NULL,
    registration_opens  TEXT,
    registration_closes TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Master student identity record. This is now populated ahead of time
-- (bulk import from the institution's existing records - see
-- import_master_data.py) rather than filled in by the student during
-- exam pre-registration. rfid_card_uid is the student's own personal
-- card, pre-assigned at enrollment - separate from any exam booklet tag.
CREATE TABLE IF NOT EXISTS students (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matric_no       TEXT UNIQUE NOT NULL,
    full_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    department      TEXT NOT NULL,
    level           TEXT NOT NULL,
    faculty         TEXT,
    rfid_card_uid   TEXT,
    photo_path      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Enforces uniqueness on rfid_card_uid only where it's actually set -
-- SQLite allows multiple NULLs through a plain UNIQUE column, but this
-- partial index is explicit about that being intentional (not every
-- student has been issued a card yet).
CREATE UNIQUE INDEX IF NOT EXISTS idx_students_rfid_card
    ON students(rfid_card_uid) WHERE rfid_card_uid IS NOT NULL;

-- Ordinary semester course registration - "is this student expected to
-- be sitting this course's exam at all", independent of any specific
-- exam sitting or QR code.
CREATE TABLE IF NOT EXISTS course_registrations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES students(id),
    course_id       INTEGER NOT NULL REFERENCES courses(id),
    registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (student_id, course_id)
);

-- Captured face images, normalized so multiple angles can be stored
-- per student without bloating the student row. These are fresh photos
-- taken during exam pre-registration, separate from students.photo_path
-- (the baseline enrollment photo).
CREATE TABLE IF NOT EXISTS face_captures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES students(id),
    image_path      TEXT NOT NULL,
    angle_label     TEXT,
    capture_order   INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A student pre-registering for a specific exam sitting. Now driven by
-- matric number lookup rather than a filled-in form - see
-- course_registration_confirmed below.
CREATE TABLE IF NOT EXISTS registrations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id         INTEGER NOT NULL REFERENCES exams(id),
    student_id      INTEGER NOT NULL REFERENCES students(id),
    registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
    status          TEXT NOT NULL DEFAULT 'registered'
                        CHECK (status IN ('registered', 'withdrawn')),
    -- 1 if the student was found in course_registrations for this exam's
    -- course at the moment they pre-registered; 0 if they proceeded
    -- anyway despite not being on the course roster - the flag the admin
    -- needs to see later.
    course_registration_confirmed INTEGER NOT NULL DEFAULT 1,
    UNIQUE (exam_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_registrations_exam ON registrations(exam_id);
CREATE INDEX IF NOT EXISTS idx_students_matric ON students(matric_no);
CREATE INDEX IF NOT EXISTS idx_face_captures_student ON face_captures(student_id);
CREATE INDEX IF NOT EXISTS idx_course_registrations_course ON course_registrations(course_id);
CREATE INDEX IF NOT EXISTS idx_course_registrations_student ON course_registrations(student_id);
