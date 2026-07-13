"""
generate_seed_data.py - Produces the four CSVs consumed by
import_master_data.py: lecturers.csv, courses.csv, students.csv,
course_registrations.csv.

This is a one-off data-seeding helper, not part of the running app.
Run it once to (re)generate the CSVs, inspect them, then feed them to
import_master_data.py in the documented order.

Usage:
    python3 generate_seed_data.py
"""
import csv
import os
import random

random.seed(42)  # reproducible output

HERE = os.path.dirname(__file__)

# ---------------------------------------------------------------
# Lecturers
# ---------------------------------------------------------------
LECTURERS = [
    ("STF001", "Dr. Chidinma Okafor",     "c.okafor@university.edu.ng"),
    ("STF002", "Prof. Ibrahim Sule",      "i.sule@university.edu.ng"),
    ("STF003", "Dr. Ngozi Umeh",          "n.umeh@university.edu.ng"),
    ("STF004", "Dr. Emeka Nwachukwu",     "e.nwachukwu@university.edu.ng"),
    ("STF005", "Prof. Amina Bello",       "a.bello@university.edu.ng"),
    ("STF006", "Dr. Tunde Fashola",       "t.fashola@university.edu.ng"),
    ("STF007", "Dr. Grace Adeyemi",       "g.adeyemi@university.edu.ng"),
    ("STF008", "Dr. Chukwuemeka Eze",     "c.eze@university.edu.ng"),
    ("STF009", "Prof. Yusuf Aliyu",       "y.aliyu@university.edu.ng"),
    ("STF010", "Dr. Blessing Okon",       "b.okon@university.edu.ng"),
]

# ---------------------------------------------------------------
# Courses - 20 courses spread across 5 departments, linked to lecturers
# ---------------------------------------------------------------
COURSES = [
    # course_code, title, lecturer_staff_no, department, level  (dept/level used only to build rosters below)
    ("CSC101", "Introduction to Computer Science",     "STF001", "Computer Science", "100"),
    ("CSC102", "Introduction to Problem Solving",       "STF001", "Computer Science", "100"),
    ("CSC201", "Data Structures and Algorithms",        "STF001", "Computer Science", "200"),
    ("CSC202", "Discrete Mathematics",                  "STF004", "Computer Science", "200"),
    ("CSC301", "Database Management Systems",           "STF008", "Computer Science", "300"),
    ("CSC302", "Operating Systems",                     "STF008", "Computer Science", "300"),
    ("CSC401", "Software Engineering",                  "STF001", "Computer Science", "400"),
    ("CSC402", "Artificial Intelligence",               "STF008", "Computer Science", "400"),

    ("EEE201", "Circuit Theory I",                      "STF002", "Electrical Engineering", "200"),
    ("EEE202", "Electromagnetic Fields",                "STF002", "Electrical Engineering", "200"),
    ("EEE301", "Electronics I",                          "STF009", "Electrical Engineering", "300"),
    ("EEE401", "Power Systems Analysis",                "STF009", "Electrical Engineering", "400"),

    ("MEE201", "Engineering Mechanics",                 "STF006", "Mechanical Engineering", "200"),
    ("MEE301", "Thermodynamics",                        "STF006", "Mechanical Engineering", "300"),
    ("MEE401", "Fluid Mechanics",                       "STF006", "Mechanical Engineering", "400"),

    ("ACC101", "Principles of Accounting I",            "STF005", "Accounting", "100"),
    ("ACC201", "Financial Accounting",                  "STF005", "Accounting", "200"),
    ("ACC301", "Cost Accounting",                       "STF010", "Accounting", "300"),

    ("ECO101", "Principles of Economics I",             "STF003", "Economics", "100"),
    ("ECO201", "Microeconomic Theory",                  "STF007", "Economics", "200"),
]

DEPARTMENTS = ["Computer Science", "Electrical Engineering", "Mechanical Engineering",
               "Accounting", "Economics"]
LEVELS = ["100", "200", "300", "400"]

FIRST_NAMES = [
    "Chinedu", "Amaka", "Obinna", "Ifeoma", "Tobenna", "Chiamaka", "Uche", "Ngozi",
    "Emeka", "Adaeze", "Kelechi", "Chioma", "Ikenna", "Nkechi", "Chukwudi", "Onyekachi",
    "Ayodeji", "Folake", "Babajide", "Temidayo", "Oluwaseun", "Adebayo", "Yetunde", "Kehinde",
    "Aminu", "Fatima", "Yusuf", "Zainab", "Ibrahim", "Halima", "Abdullahi", "Maryam",
    "Godwin", "Blessing", "Emmanuel", "Precious", "Samuel", "Grace", "Joseph", "Faith",
]
LAST_NAMES = [
    "Okafor", "Eze", "Nwosu", "Okonkwo", "Umeh", "Chukwu", "Nnamdi", "Obi",
    "Adeyemi", "Ogunleye", "Balogun", "Adebayo", "Fashola", "Oyelaran", "Adewale",
    "Bello", "Sule", "Aliyu", "Yusuf", "Suleiman", "Abdullahi", "Garba",
    "Etim", "Okon", "Udoh", "Bassey", "Effiong",
]

FACULTIES = {
    "Computer Science": "Faculty of Computing",
    "Electrical Engineering": "Faculty of Engineering",
    "Mechanical Engineering": "Faculty of Engineering",
    "Accounting": "Faculty of Management Sciences",
    "Economics": "Faculty of Social Sciences",
}

DEPT_CODE = {
    "Computer Science": "CSC",
    "Electrical Engineering": "EEE",
    "Mechanical Engineering": "MEE",
    "Accounting": "ACC",
    "Economics": "ECO",
}

# Matric numbers must match MATRIC_PATTERN in online-backend/schemas.py:
#   ^\d{4}/\d{1,2}/[0-9A-Za-z]+$   e.g. 2022/1/00014CS
# i.e. <year>/<faculty-number>/<serial><dept-suffix> - NOT <year>/<dept-code>/<serial>.
# DEPT_NUM is the numeric faculty/department code that goes in the middle
# segment; DEPT_SUFFIX is the 2-letter tag appended to the serial.
DEPT_NUM = {
    "Computer Science": "1",
    "Electrical Engineering": "2",
    "Mechanical Engineering": "3",
    "Accounting": "4",
    "Economics": "5",
}
DEPT_SUFFIX = {
    "Computer Science": "CS",
    "Electrical Engineering": "EE",
    "Mechanical Engineering": "ME",
    "Accounting": "AC",
    "Economics": "EC",
}

random.shuffle(FIRST_NAMES)


def write_lecturers():
    path = os.path.join(HERE, "lecturers.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["staff_no", "full_name", "email"])
        for staff_no, name, email in LECTURERS:
            w.writerow([staff_no, name, email])
    print(f"Wrote {len(LECTURERS)} lecturers -> {path}")


def write_courses():
    path = os.path.join(HERE, "courses.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["course_code", "title", "lecturer_staff_no"])
        for code, title, staff_no, _dept, _level in COURSES:
            w.writerow([code, title, staff_no])
    print(f"Wrote {len(COURSES)} courses -> {path}")


def build_students():
    r"""
    ~10 students per (department, level) combo -> 5 depts * 4 levels * 10 = 200 students.
    Matric format: <year>/<dept-number>/<5-digit-serial><dept-suffix>,
    e.g. 2022/1/00014CS - this matches MATRIC_PATTERN in
    online-backend/schemas.py (^\d{4}/\d{1,2}/[0-9A-Za-z]+$).
    Every student gets a unique RFID card UID (their personal ID card),
    formatted like a real 4-byte MIFARE UID: 8 uppercase hex chars.
    """
    students = []
    used_uids = set()
    year_by_level = {"100": "2025", "200": "2024", "300": "2023", "400": "2022"}

    seq_counters = {}
    for dept in DEPARTMENTS:
        for level in LEVELS:
            year = year_by_level[level]
            dept_code = DEPT_CODE[dept]
            dept_num = DEPT_NUM[dept]
            dept_suffix = DEPT_SUFFIX[dept]
            for _ in range(10):
                key = (dept_code, year)
                seq_counters[key] = seq_counters.get(key, 0) + 1
                matric_no = f"{year}/{dept_num}/{seq_counters[key]:05d}{dept_suffix}"

                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                full_name = f"{first} {last}"

                local_part = f"{first}.{last}".lower()
                email = f"{local_part}.{matric_no.split('/')[-1]}@student.university.edu.ng"
                phone = "0" + "".join(str(random.randint(0, 9)) for _ in range(10))

                while True:
                    uid = "".join(random.choice("0123456789ABCDEF") for _ in range(8))
                    if uid not in used_uids:
                        used_uids.add(uid)
                        break

                students.append({
                    "matric_no": matric_no,
                    "full_name": full_name,
                    "department": dept,
                    "level": level,
                    "email": email,
                    "phone": phone,
                    "faculty": FACULTIES[dept],
                    "rfid_card_uid": uid,
                    "photo_path": "",
                })
    return students


def write_students(students):
    path = os.path.join(HERE, "students.csv")
    fields = ["matric_no", "full_name", "department", "level", "email", "phone",
              "faculty", "rfid_card_uid", "photo_path"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in students:
            w.writerow(s)
    print(f"Wrote {len(students)} students -> {path}")


def write_course_registrations(students):
    """
    Each student is registered for every course offered at their own
    department + level (their "core" courses for that semester) - this
    is what course_registrations represents: the ordinary semester
    roster, independent of any specific exam sitting.
    """
    path = os.path.join(HERE, "course_registrations.csv")
    rows = []
    for s in students:
        matching_courses = [c for c in COURSES if c[3] == s["department"] and c[4] == s["level"]]
        for code, *_ in matching_courses:
            rows.append((s["matric_no"], code))

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["matric_no", "course_code"])
        w.writerows(rows)
    print(f"Wrote {len(rows)} course registrations -> {path}")


if __name__ == "__main__":
    write_lecturers()
    write_courses()
    students = build_students()
    write_students(students)
    write_course_registrations(students)
