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


from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from pydantic import ValidationError
from functools import wraps
import base64
import io
import json
import os
import requests
import threading
import time
from datetime import datetime

import database as db
import config
from schemas import StudentRegistrationCreate, VALID_LEVELS

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

FACE_DIR = os.path.join(os.path.dirname(__file__), "data", "faces")
os.makedirs(FACE_DIR, exist_ok=True)

ANGLE_LABELS = ["front", "left", "right"]


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

    return render_template("register.html", exam=exam, token=token, levels=sorted(VALID_LEVELS))


def handle_registration_submit(token, exam):
    form = request.form
    try:
        face_images = json.loads(form.get("face_images_json", "")) if form.get("face_images_json") else []
    except (json.JSONDecodeError, TypeError):
        face_images = []

    payload = {
        "matric_number": form.get("matric_number", "").strip(),
        "student_name": form.get("student_name", "").strip(),
        "department": form.get("department", "").strip(),
        "level": form.get("level", "").strip(),
        "email": form.get("email", "").strip() or None,
        "phone": form.get("phone", "").strip() or None,
        "face_images": face_images,
    }

    try:
        data = StudentRegistrationCreate(**payload)
    except ValidationError as e:
        for err in e.errors():
            flash(err["msg"], "error")
        return render_template("register.html", exam=exam, token=token,
                                levels=sorted(VALID_LEVELS), form_data=payload), 400

    student_id = db.upsert_student(
        matric_no=data.matric_number, full_name=data.student_name,
        department=data.department, level=data.level,
        email=data.email, phone=data.phone,
    )

    existing_reg = db.get_existing_registration(exam["id"], student_id)
    if existing_reg:
        flash("You are already registered for this exam.", "info")
        session["registration"] = {
            "name": data.student_name, "matric": data.matric_number,
            "course": exam["course_code"], "title": exam["title"],
            "exam_date": exam["exam_date"], "department": data.department,
            "level": data.level, "already_registered": True,
        }
        return redirect(url_for("register_success", token=token))

    for i, image_data in enumerate(data.face_images):
        saved_path = save_face_image(data.matric_number, image_data, i)
        if saved_path:
            angle = ANGLE_LABELS[i] if i < len(ANGLE_LABELS) else f"capture-{i}"
            db.save_face_capture(student_id, saved_path, angle, i)

    db.create_registration(exam["id"], student_id)

    session["registration"] = {
        "name": data.student_name, "matric": data.matric_number,
        "course": exam["course_code"], "title": exam["title"],
        "exam_date": exam["exam_date"], "department": data.department,
        "level": data.level, "already_registered": False,
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
        lecturer_id = db.get_or_create_lecturer(request.form.get("lecturer_name", "").strip())
        course_id = db.get_or_create_course(
            request.form.get("course_code", "").strip(),
            request.form.get("course_title", "").strip(),
        )
        exam = db.create_exam(
            course_id=course_id, lecturer_id=lecturer_id,
            title=request.form.get("exam_title", "").strip(),
            exam_date=request.form.get("exam_date", "").strip(),
            venue=request.form.get("venue", "").strip(),
        )
        return redirect(url_for("admin_exams", new=exam["registration_token"]))

    exams = db.list_exams()
    new_token = request.args.get("new")
    return render_template("admin_exams.html", exams=exams, new_token=new_token,
                            base_url=config.public_base_url(request))


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
    required = ["lecturer_name", "course_code", "course_title", "exam_title", "exam_date"]
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return jsonify(success=False, message=f"Missing fields: {', '.join(missing)}"), 400

    lecturer_id = db.get_or_create_lecturer(payload["lecturer_name"])
    course_id = db.get_or_create_course(payload["course_code"], payload["course_title"])
    exam = db.create_exam(
        course_id=course_id, lecturer_id=lecturer_id,
        title=payload["exam_title"], exam_date=payload["exam_date"],
        venue=payload.get("venue", ""),
    )
    registration_url = f"{config.public_base_url(request)}/register/{exam['registration_token']}"
    return jsonify(success=True, data={
        "exam_id": exam["id"],
        "registration_token": exam["registration_token"],
        "registration_url": registration_url,
    }), 201


@app.route("/api/exams/<int:exam_id>", methods=["GET"])
@require_api_key
def api_get_exam(exam_id):
    exam = db.get_exam_by_id(exam_id)
    if not exam:
        return jsonify(success=False, message="Exam not found"), 404
    exam["registration_url"] = f"{config.public_base_url(request)}/register/{exam['registration_token']}"
    return jsonify(success=True, data=exam)


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
    print(f"Admin login:  http://localhost:5500/admin/login")
    print(f"Admin password (dev default unless ADMIN_PASSWORD is set): {config.ADMIN_PASSWORD}")
    print(f"API key (dev default unless API_KEY is set): {config.API_KEY}")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5500, debug=True)
