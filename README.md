# Master Data: Matric Format & CSV Seeding Workflow

This covers the student/course/lecturer "master data" system: where it
lives, the matric number format it expects, and how to view, edit, and
reload it.

## How the two apps relate

- **`online-backend/`** (this project) is the source of truth for
  master data - lecturers, courses, students, and course
  registrations. It's what students hit when they scan a QR code to
  pre-register for an exam.
- **`raspi_dashboard/`** (the Pi) does **not** keep its own copy of
  master data. When an exam is created on the Pi, it calls out to this
  server (`online_client.py`) to pull the course list and, during
  sync, the registered students + face images for that specific exam.
  Its `local.db` only ever holds exam-scoped snapshots, never the
  master list.

**Practical consequence:** fix or edit master data in exactly one
place - here, in `online-backend/`. There is nothing to separately
maintain on the Pi.

## Matric number format

Matric numbers must match this pattern (enforced in `schemas.py`,
`MATRIC_PATTERN`):

```
YYYY/D/XXXXX
```

- `YYYY` - 4-digit year
- `D` - 1-2 digit faculty/department number
- `XXXXX` - alphanumeric serial (letters and/or digits)

**Example:** `2025/1/00001CS`

The seed generator builds the serial as a 5-digit zero-padded number
plus a 2-letter department tag (e.g. `CS`, `EE`, `ME`, `AC`, `EC`), but
that's just a convention - the validator itself accepts any
alphanumeric string in that last segment.

If you ever see a registration get rejected with *"Matric number must
be in format YYYY/X/XXXXX"*, the matric number on file doesn't match
this pattern - check `students.csv` (see below) for stray formats like
`2025/CSC/001` (letters in the middle segment) or missing slashes.

## Viewing and editing student/course data

Master data is meant to be edited as CSV, not by hand-editing the
database. Three scripts handle the full loop:

| Script | What it does |
|---|---|
| `export_master_data.py` | Dumps the **current** database contents to CSV so you can see/edit real data |
| *(edit the CSVs)* | Open in Excel/Sheets/a text editor |
| `seed_master_data.py` | Reads the CSVs back into the database |

### 1. Export current data to CSV

```bash
python3 export_master_data.py
```

Writes `lecturers.csv`, `courses.csv`, `students.csv`, and
`course_registrations.csv` into `seed_data/` (pass a different folder
as an argument if you want).

### 2. Edit the CSVs

Open `seed_data/students.csv`. Columns:

```
matric_no, full_name, department, level, email, phone, faculty, rfid_card_uid, photo_path
```

- Fix names, departments, levels, contact info directly.
- **To assign or reassign an RFID tag**, put the card's UID in the
  `rfid_card_uid` column (uppercase hex, e.g. `B6217927`). This is the
  student's own ID card UID, separate from exam booklet tags.
- `courses.csv` and `lecturers.csv` follow the same pattern if you
  need to edit course titles, lecturer assignments, etc.

### 3. Reload into the database

Normal edits (rename a student, change a department, assign an RFID
tag) - **upserts**, nothing is deleted:

```bash
python3 seed_master_data.py seed_data
```

Existing rows are matched by `matric_no` (students), `course_code`
(courses), or `staff_no` (lecturers) and updated in place; new rows
are inserted.

If you deleted rows from the CSV (or changed a format, like the matric
number format was changed) and actually want old rows gone rather than
left behind, wipe students + course_registrations first, then reload:

```bash
python3 seed_master_data.py --fresh seed_data
```

`--fresh` only touches `students`, `face_captures`, and
`course_registrations` - `courses` and `lecturers` are left alone
since they're matched by stable codes and don't need wiping. It will
also **refuse to run** (and tell you exactly which students) if any
student already has a real exam registration on file, so it can never
silently delete live exam data out from under you. Clear those
registrations first if you genuinely mean to wipe those students too.

### Renaming a matric number

Matching is by `matric_no`, so changing a student's matric number in
the CSV creates a **new** student row rather than renaming the old
one. If you change someone's matric number, either:
- delete the old row from the CSV and run `--fresh`, or
- manually remove the old row from the database afterward.

## Generating fresh dummy/demo data

`seed_data/generate_seed_data.py` builds a full demo dataset from
scratch (10 lecturers, 20 courses, 200 students across 5 departments)
- useful for a clean demo environment or as a template for the CSV
column layout:

```bash
cd seed_data
python3 generate_seed_data.py
```

This overwrites `lecturers.csv`, `courses.csv`, `students.csv`, and
`course_registrations.csv` in that folder with freshly generated data
(matric numbers already in the correct format). Run
`seed_master_data.py --fresh seed_data` afterward to load it in.

## File reference

```
database.py               - SQLite access layer (schema, queries)
schema.sql                 - table definitions
schemas.py                  - request validation, incl. MATRIC_PATTERN
import_master_data.py       - low-level per-table CSV importer (used by seed_master_data.py)
export_master_data.py       - dumps current DB -> CSV
seed_master_data.py         - reloads CSV -> DB (upsert or --fresh)
migrate_master_data_model.py - one-off schema migration (run once after deploying schema changes)
seed_data/
  generate_seed_data.py    - builds demo CSVs from scratch
  lecturers.csv
  courses.csv
  students.csv
  course_registrations.csv
```
