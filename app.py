"""
app.py - Online Exam Pre-Registration Server

Three audiences hit this server:
  1. Students - scan a QR, land on /register/<token>, fill identity info
     + face capture. Course/exam date are read-only, resolved from token.
  2. Admin (a person) - logs into /admin to create exams, view who has
     registered, and download the QR for printing/sharing. Session-based,
     gated by ADMIN_PASSWORD.
  3. The Raspberry Pi (a machine) - calls /api/* to create exams remotely
     and pull registrations during sync. Gated by API_KEY, not a login.
"""
import threading

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from pydantic import ValidationError
from functools import wraps
import base64
import io
import json
import os
import time
from datetime import datetime


import requests

import database as db
import config
import import_master_data
from schemas import StudentRegistrationCreate, ANGLE_LABELS

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

FACE_DIR = os.path.join(os.path.dirname(__file__), "data", "faces")
os.makedirs(FACE_DIR, exist_ok=True)


# ---------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------

def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if key != config.API_KEY:
            return jsonify(success=False, message="Invalid or missing API key"), 401
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    return redirect(url_for("admin_login") if not session.get("is_admin") else url_for("admin_exams"))


# ---------------------------------------------------------------
# Registration (what the student sees after scanning the QR)
# ---------------------------------------------------------------

@app.route("/register/<token>", methods=["GET", "POST"])
def register(token):
    exam = db.get_exam_by_token(token)
    if not exam:
        return render_template("invalid_token.html"), 404

    now = datetime.now()
    if exam["registration_opens"]:
        if now < datetime.fromisoformat(exam["registration_opens"]):
            return render_template("invalid_token.html",
                                    reason="Registration for this exam hasn't opened yet."), 403
    if exam["registration_closes"]:
        if now > datetime.fromisoformat(exam["registration_closes"]):
            return render_template("invalid_token.html",
                                    reason="Registration for this exam has closed."), 403

    if request.method == "POST":
        return handle_registration_submit(token, exam)

    return render_template("register.html", exam=exam, token=token, angle_labels=ANGLE_LABELS)


@app.route("/register/<token>/lookup", methods=["POST"])
def register_lookup(token):
    """
    Step 1 of registration: matric number only. Looks the student up in
    the master record (populated ahead of time - see Phase 1) and checks
    whether they're on this course's roster. Returns one of:
      - not_found: no master student record for that matric number at all
      - registered: on the roster - frontend can go straight to face capture
      - not_registered: student exists but isn't on this course's roster -
        frontend shows the "not registered, proceed anyway?" interstitial
    """
    exam = db.get_exam_by_token(token)
    if not exam:
        return jsonify(result="not_found"), 404

    payload = request.get_json(silent=True) or {}
    matric_no = (payload.get("matric_number") or "").strip()
    if not matric_no:
        return jsonify(result="not_found", message="Enter a matric number.")

    student = db.find_student_by_matric(matric_no)
    if not student:
        return jsonify(result="not_found",
                        message="No student record found for that matric number. Contact the exam office.")

    already = db.get_existing_registration(exam["id"], student["id"])
    if already:
        return jsonify(result="already_registered", candidate={
            "matric_no": student["matric_no"], "full_name": student["full_name"],
            "department": student["department"], "level": student["level"],
        })

    on_roster = db.is_student_registered_for_course(student["id"], exam["course_id"])
    candidate = {
        "matric_no": student["matric_no"], "full_name": student["full_name"],
        "department": student["department"], "level": student["level"],
    }
    if on_roster:
        return jsonify(result="registered", candidate=candidate)
    return jsonify(result="not_registered", candidate=candidate,
                    message=f"{student['full_name']} is not on the course registration list for "
                            f"{exam['course_code']}.")


def handle_registration_submit(token, exam):
    form = request.form
    try:
        face_images = json.loads(form.get("face_images_json", "")) if form.get("face_images_json") else []
    except (json.JSONDecodeError, TypeError):
        face_images = []

    payload = {
        "matric_number": form.get("matric_number", "").strip(),
        "proceed_anyway": form.get("proceed_anyway", "0") == "1",
        "face_images": face_images,
    }

    try:
        data = StudentRegistrationCreate(**payload)
    except ValidationError as e:
        for err in e.errors():
            flash(err["msg"], "error")
        return render_template("register.html", exam=exam, token=token,
                                angle_labels=ANGLE_LABELS), 400

    student = db.find_student_by_matric(data.matric_number)
    if not student:
        flash("No student record found for that matric number. Contact the exam office.", "error")
        return render_template("register.html", exam=exam, token=token,
                                angle_labels=ANGLE_LABELS), 400

    existing_reg = db.get_existing_registration(exam["id"], student["id"])
    if existing_reg:
        flash("You are already registered for this exam.", "info")
        session["registration"] = {
            "name": student["full_name"], "matric": student["matric_no"],
            "course": exam["course_code"], "title": exam["title"],
            "exam_date": exam["exam_date"], "department": student["department"],
            "level": student["level"], "already_registered": True,
        }
        return redirect(url_for("register_success", token=token))

    on_roster = db.is_student_registered_for_course(student["id"], exam["course_id"])
    if not on_roster and not data.proceed_anyway:
        # Should only happen if someone bypasses the frontend gate - the
        # UI already routes through the not-registered interstitial first.
        flash(f"You are not registered for {exam['course_code']}. Confirm you want to proceed anyway.", "error")
        return render_template("register.html", exam=exam, token=token,
                                angle_labels=ANGLE_LABELS), 400

    for i, image_data in enumerate(data.face_images):
        saved_path = save_face_image(data.matric_number, image_data, i)
        if saved_path:
            angle = ANGLE_LABELS[i]["key"] if i < len(ANGLE_LABELS) else f"capture-{i}"
            db.save_face_capture(student["id"], saved_path, angle, i)

    db.create_registration(exam["id"], student["id"], course_registration_confirmed=on_roster)

    session["registration"] = {
        "name": student["full_name"], "matric": student["matric_no"],
        "course": exam["course_code"], "title": exam["title"],
        "exam_date": exam["exam_date"], "department": student["department"],
        "level": student["level"], "already_registered": False,
    }
    return redirect(url_for("register_success", token=token))


def save_face_image(matric_no: str, image_data: str, index: int):
    if not image_data or not image_data.startswith("data:image"):
        return None
    try:
        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_matric = matric_no.replace("/", "-")
        filename = f"{safe_matric}_{timestamp}_{index}.jpg"
        full_path = os.path.join(FACE_DIR, filename)
        with open(full_path, "wb") as f:
            f.write(img_bytes)
        return full_path
    except Exception as e:
        print(f"[FACE SAVE ERROR] {e}")
        return None


@app.route("/register/<token>/success")
def register_success(token):
    data = session.get("registration")
    if not data:
        return redirect(url_for("register", token=token))
    return render_template("register_success.html", token=token, **data)


# ---------------------------------------------------------------
# QR image - shared by the admin UI and anyone with a valid token
# ---------------------------------------------------------------

@app.route("/qr-image/<token>.png")
def qr_image(token):
    import qrcode

    exam = db.get_exam_by_token(token)
    if not exam:
        return "Not found", 404

    url = f"{config.public_base_url(request)}/register/{token}"
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a56db", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    as_attachment = request.args.get("download") == "1"
    filename = f"{exam['course_code']}_registration_qr.png"
    return send_file(buf, mimetype="image/png", as_attachment=as_attachment, download_name=filename)


# ---------------------------------------------------------------
# Admin (human) - login, create exams, view registrations
# ---------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == config.ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(request.args.get("next") or url_for("admin_exams"))
        flash("Incorrect password.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/exams", methods=["GET", "POST"])
@require_admin
def admin_exams():
    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        if not course_id:
            flash("Select a course from the list.", "error")
            return redirect(url_for("admin_exams"))
        try:
            exam = db.create_exam_from_course(
                course_id=course_id,
                invigilator_name=request.form.get("invigilator_name", "").strip(),
                title=request.form.get("exam_title", "").strip(),
                exam_date=request.form.get("exam_date", "").strip(),
                venue=request.form.get("venue", "").strip(),
            )
        except db.CourseHasNoLecturerError as e:
            flash(str(e), "error")
            return redirect(url_for("admin_exams"))
        return redirect(url_for("admin_exams", new=exam["registration_token"]))

    exams = db.list_exams()
    courses = db.list_courses_for_dropdown()
    new_token = request.args.get("new")
    return render_template("admin_exams.html", exams=exams, courses=courses, new_token=new_token,
                            base_url=config.public_base_url(request))


@app.route("/admin/import-master-data", methods=["GET", "POST"])
@require_admin
def admin_import_master_data():
    """
    Web equivalent of running import_master_data.py (or seed_master_data.py)
    from a shell - for hosts like Render where there's no CLI/shell access
    to the running service. Uses the exact same import_lecturers/
    import_courses/import_students/import_course_registrations functions
    the CLI/seed_master_data.py call, just fed an uploaded file instead of
    a path on disk - one implementation, not a second copy of the import
    logic.

    Same ordering rule as the CLI: lecturers -> courses -> students ->
    course_registrations, since later steps look up rows created by
    earlier ones (courses reference lecturers, registrations reference
    both students and courses).
    """
    if request.method == "POST":
        which = request.form.get("which", "")
        if which not in import_master_data.COMMANDS:
            flash("Unknown import type.", "error")
            return redirect(url_for("admin_import_master_data"))

        upload = request.files.get("csv_file")
        if not upload or upload.filename == "":
            flash("Choose a CSV file first.", "error")
            return redirect(url_for("admin_import_master_data"))

        tmp_path = os.path.join(
            "/tmp", f"import_{which}_{int(datetime.utcnow().timestamp())}.csv"
        )
        upload.save(tmp_path)
        try:
            result = import_master_data.COMMANDS[which](tmp_path)
            msg = f"{which}: imported/updated {result['count']} row(s)."
            if result["skipped"]:
                msg += f" Skipped {len(result['skipped'])}: " + "; ".join(result["skipped"][:5])
                if len(result["skipped"]) > 5:
                    msg += f"; ...and {len(result['skipped']) - 5} more"
            flash(msg, "success" if not result["skipped"] else "error")
        except KeyError as e:
            flash(f"Import failed - missing expected column {e} in the CSV header.", "error")
        except Exception as e:
            flash(f"Import failed: {e}", "error")
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return redirect(url_for("admin_import_master_data"))

    return render_template("admin_import_master_data.html")


@app.route("/admin/exams/<int:exam_id>")
@require_admin
def admin_exam_detail(exam_id):
    exam = db.get_exam_by_id(exam_id)
    if not exam:
        return "Not found", 404
    registrations = db.list_registrations_for_exam(exam_id)
    return render_template("admin_exam_detail.html", exam=exam, registrations=registrations)


@app.route("/admin/face-captures/<int:capture_id>/image")
@require_admin
def admin_face_image(capture_id):
    capture = db.get_face_capture(capture_id)
    if not capture or not os.path.exists(capture["image_path"]):
        return "Not found", 404
    return send_file(capture["image_path"], mimetype="image/jpeg")


# ---------------------------------------------------------------
# API (machine) - the Raspberry Pi calls these to create exams and
# pull registrations. Protected by X-API-Key, not the admin session.
# ---------------------------------------------------------------

@app.route("/api/exams", methods=["POST"])
@require_api_key
def api_create_exam():
    payload = request.get_json(silent=True) or {}
    required = ["course_id", "invigilator_name", "exam_title", "exam_date"]
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return jsonify(success=False, message=f"Missing fields: {', '.join(missing)}"), 400

    try:
        exam = db.create_exam_from_course(
            course_id=payload["course_id"], invigilator_name=payload["invigilator_name"],
            title=payload["exam_title"], exam_date=payload["exam_date"],
            venue=payload.get("venue", ""),
        )
    except db.CourseHasNoLecturerError as e:
        return jsonify(success=False, message=str(e)), 400
    except ValueError as e:
        return jsonify(success=False, message=str(e)), 404

    registration_url = f"{config.public_base_url(request)}/register/{exam['registration_token']}"
    return jsonify(success=True, data={
        "exam_id": exam["id"],
        "registration_token": exam["registration_token"],
        "registration_url": registration_url,
    }), 201


@app.route("/api/courses", methods=["GET"])
@require_api_key
def api_list_courses():
    return jsonify(success=True, data=db.list_courses_for_dropdown())


@app.route("/api/exams/<int:exam_id>", methods=["GET"])
@require_api_key
def api_get_exam(exam_id):
    exam = db.get_exam_by_id(exam_id)
    if not exam:
        return jsonify(success=False, message="Exam not found"), 404
    exam["registration_url"] = f"{config.public_base_url(request)}/register/{exam['registration_token']}"
    return jsonify(success=True, data=exam)


@app.route("/api/exams/<int:exam_id>/sync-status", methods=["GET"])
@require_api_key
def api_exam_sync_status(exam_id):
    """
    Lightweight check the Pi can poll before doing a full registrations
    pull - just counts, not the actual data, so it's cheap to call
    often. ?since=<timestamp> is the Pi's last successful sync time;
    omit it to ask "has anything ever happened here".
    """
    exam = db.get_exam_by_id(exam_id)
    if not exam:
        return jsonify(success=False, message="Exam not found"), 404
    since = request.args.get("since")
    status = db.get_exam_sync_status(exam_id, since)
    return jsonify(success=True, data=status)


@app.route("/api/exams/<int:exam_id>/registrations", methods=["GET"])
@require_api_key
def api_exam_registrations(exam_id):
    exam = db.get_exam_by_id(exam_id)
    if not exam:
        return jsonify(success=False, message="Exam not found"), 404

    registrations = db.list_registrations_for_exam(exam_id)
    for reg in registrations:
        for capture in reg["face_captures"]:
            capture["image_url"] = f"{config.public_base_url(request)}/api/face-captures/{capture['id']}/image"

    return jsonify(success=True, data={
        "exam_id": exam_id,
        "course_code": exam["course_code"],
        "count": len(registrations),
        "registrations": registrations,
    })


@app.route("/api/face-captures/<int:capture_id>/image", methods=["GET"])
@require_api_key
def api_face_image(capture_id):
    capture = db.get_face_capture(capture_id)
    if not capture or not os.path.exists(capture["image_path"]):
        return jsonify(success=False, message="Not found"), 404
    return send_file(capture["image_path"], mimetype="image/jpeg")


# ─── HEALTH CHECK ─────────────────────────────────────────────
# Lightweight liveness probe — no image processing, no DB, no
# external calls. The ESP32 (or any monitor) hits this to confirm
# the server process is up and responding, fast, every time.
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status":     "ok",
        "time":       datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


# ─── KEEP-ALIVE (anti cold-start) ────────────────────────────
# Render's free tier spins down web services after ~15 minutes of
# inactivity, and the next request then takes 30-60s to cold-start.
# This background thread pings our OWN /health endpoint every 10
# minutes so the service never goes idle long enough to sleep,
# which keeps ESP32 requests fast and predictable during testing
# and demos. Set SELF_URL to this service's own public Render URL.
SELF_URL = os.environ.get("SELF_URL", "https://exam-qr-registration.onrender.com")
KEEPALIVE_INTERVAL_SEC = 600  # 10 minutes — safely under the 15-min sleep window

def keep_alive_loop():
    while True:
        time.sleep(KEEPALIVE_INTERVAL_SEC)
        try:
            r = requests.get(f"{SELF_URL}/health", timeout=10)
            print(f"[KEEPALIVE] Self-ping -> {r.status_code}")
        except Exception as e:
            print(f"[KEEPALIVE] Self-ping failed: {e}")

threading.Thread(target=keep_alive_loop, daemon=True).start()


if __name__ == "__main__":
    db.init_db()
    print("\n" + "=" * 60)
    print("Exam pre-registration server")
    print("=" * 60)
    print(f"Admin login:  http://localhost:5000/admin/login")
    print(f"Admin password (dev default unless ADMIN_PASSWORD is set): {config.ADMIN_PASSWORD}")
    print(f"API key (dev default unless API_KEY is set): {config.API_KEY}")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
