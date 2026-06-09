"""Training routes – register persons and train the face model."""

from __future__ import annotations

import os
import re
import threading
import time
from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from app.database import db
from app.models import Camera, Person
from app import stream_manager

training_bp = Blueprint("training", __name__, url_prefix="/training")

# ---------------------------------------------------------------------------
# Training state
# ---------------------------------------------------------------------------
_training_lock = threading.Lock()
_training_status: dict = {"running": False, "message": "", "success": None}

# Capture state per session (camera_id -> list of saved frame paths)
_capture_lock = threading.Lock()
_capture_counts: dict[int, int] = {}   # person_id -> count


def _do_train(dataset_dir: str, models_dir: str, app):
    global _training_status
    from app.services.face_service import FaceService

    svc = FaceService(models_dir)
    ok, msg = svc.train(dataset_dir)

    with _training_lock:
        _training_status = {"running": False, "message": msg, "success": ok}

    if ok and stream_manager:
        stream_manager.reload_encodings()


@training_bp.route("/")
def index():
    persons = Person.query.order_by(Person.name).all()
    cameras = Camera.query.filter_by(is_active=True).order_by(Camera.id).all()
    return render_template("training.html", persons=persons, cameras=cameras)


# ------------------------------------------------------------------
# Person management
# ------------------------------------------------------------------
def _safe_person_name(name: str) -> str:
    """Sanitize a person name so it is safe to use as a directory component."""
    # Allow only alphanumerics, spaces, hyphens, underscores, dots
    sanitized = re.sub(r"[^\w\s\-.]", "", name).strip()
    if not sanitized:
        raise ValueError("Invalid person name")
    return sanitized


@training_bp.route("/person/add", methods=["POST"])
def add_person():
    raw_name = request.form.get("name", "").strip()
    try:
        name = _safe_person_name(raw_name)
    except ValueError:
        flash("Invalid person name. Use letters, numbers, spaces, hyphens, dots only.", "danger")
        return redirect(url_for("training.index"))

    existing = Person.query.filter_by(name=name).first()
    if existing:
        flash(f'Person "{name}" already exists.', "warning")
        return redirect(url_for("training.index"))

    person = Person(name=name)
    db.session.add(person)
    db.session.commit()

    # Create dataset folder – guard against path traversal
    dataset_dir = current_app.config["DATASET_DIR"]
    folder = os.path.realpath(os.path.join(dataset_dir, name))
    if not folder.startswith(os.path.realpath(dataset_dir)):
        flash("Invalid person name (path traversal detected).", "danger")
        return redirect(url_for("training.index"))
    os.makedirs(folder, exist_ok=True)

    flash(f'Person "{name}" added.', "success")
    return redirect(url_for("training.index"))


@training_bp.route("/person/<int:person_id>/delete", methods=["POST"])
def delete_person(person_id: int):
    import shutil

    person = Person.query.get_or_404(person_id)
    dataset_dir = current_app.config["DATASET_DIR"]
    folder = os.path.realpath(os.path.join(dataset_dir, person.name))
    if folder.startswith(os.path.realpath(dataset_dir)) and os.path.isdir(folder):
        shutil.rmtree(folder)
    db.session.delete(person)
    db.session.commit()
    flash(f'Person "{person.name}" deleted.', "warning")
    return redirect(url_for("training.index"))


# ------------------------------------------------------------------
# Frame capture from a camera
# ------------------------------------------------------------------
@training_bp.route("/capture/<int:person_id>/<int:camera_id>", methods=["POST"])
def capture_frame(person_id: int, camera_id: int):
    import cv2
    import numpy as np

    frame_bytes = stream_manager.get_frame(camera_id) if stream_manager else None
    if not frame_bytes:
        return jsonify({"success": False, "message": "No frame available from camera."})

    person = Person.query.get_or_404(person_id)
    dataset_dir = current_app.config["DATASET_DIR"]
    folder = os.path.realpath(os.path.join(dataset_dir, person.name))
    if not folder.startswith(os.path.realpath(dataset_dir)):
        return jsonify({"success": False, "message": "Invalid person path."})
    os.makedirs(folder, exist_ok=True)

    # Count existing images
    existing = [f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    idx = len(existing) + 1
    filename = f"{person.name}_{idx:04d}.jpg"
    path = os.path.join(folder, filename)

    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    cv2.imwrite(path, img)

    person.sample_count = idx
    db.session.commit()

    return jsonify({"success": True, "count": idx, "filename": filename})


# ------------------------------------------------------------------
# Live preview for training (MJPEG)
# ------------------------------------------------------------------
def _training_mjpeg(camera_id: int):
    while True:
        frame = stream_manager.get_frame(camera_id) if stream_manager else None
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        time.sleep(0.04)


@training_bp.route("/feed/<int:camera_id>")
def training_feed(camera_id: int):
    return Response(
        _training_mjpeg(camera_id),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


# ------------------------------------------------------------------
# Train model
# ------------------------------------------------------------------
@training_bp.route("/train", methods=["POST"])
def start_training():
    global _training_status
    with _training_lock:
        if _training_status["running"]:
            return jsonify({"status": "running"})
        _training_status = {"running": True, "message": "Training in progress…", "success": None}

    t = threading.Thread(
        target=_do_train,
        args=(
            current_app.config["DATASET_DIR"],
            current_app.config["MODELS_DIR"],
            current_app._get_current_object(),
        ),
        daemon=True,
    )
    t.start()
    return jsonify({"status": "started"})


@training_bp.route("/train/status")
def training_status():
    with _training_lock:
        return jsonify(_training_status)
