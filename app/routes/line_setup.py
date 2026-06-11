"""Line setup routes – define imaginary line per camera."""

from __future__ import annotations

import time
from flask import (
    Blueprint,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
    flash,
)

from app.database import db
from app.models import Camera, LineConfig
import app as app_module

line_setup_bp = Blueprint("line_setup", __name__, url_prefix="/line")


@line_setup_bp.route("/")
def index():
    cameras = Camera.query.order_by(Camera.id).all()
    configs = {lc.camera_id: lc for lc in LineConfig.query.all()}
    return render_template("line_setup.html", cameras=cameras, configs=configs)


@line_setup_bp.route("/save", methods=["POST"])
def save_line():
    data = request.get_json()
    camera_id = data.get("camera_id")
    if not camera_id:
        return jsonify({"success": False, "message": "camera_id required"})

    config = LineConfig.query.filter_by(camera_id=camera_id).first()
    if not config:
        config = LineConfig(camera_id=camera_id)
        db.session.add(config)

    config.x1 = float(data.get("x1", 0.0))
    config.y1 = float(data.get("y1", 0.5))
    config.x2 = float(data.get("x2", 1.0))
    config.y2 = float(data.get("y2", 0.5))
    config.enabled = bool(data.get("enabled", True))
    db.session.commit()

    return jsonify({"success": True})


@line_setup_bp.route("/delete/<int:camera_id>", methods=["POST"])
def delete_line(camera_id: int):
    config = LineConfig.query.filter_by(camera_id=camera_id).first()
    if config:
        db.session.delete(config)
        db.session.commit()
    flash("Line configuration deleted.", "warning")
    return redirect(url_for("line_setup.index"))


@line_setup_bp.route("/toggle/<int:camera_id>", methods=["POST"])
def toggle_line(camera_id: int):
    config = LineConfig.query.filter_by(camera_id=camera_id).first()
    if config:
        config.enabled = not config.enabled
        db.session.commit()
        return jsonify({"enabled": config.enabled})
    return jsonify({"enabled": False})


# Snapshot preview (single frame) for line drawing
@line_setup_bp.route("/snapshot/<int:camera_id>")
def snapshot(camera_id: int):
    frame = app_module.stream_manager.get_frame(camera_id) if app_module.stream_manager else None
    if not frame:
        # Return a 1x1 grey JPEG as placeholder
        import io
        from PIL import Image

        img = Image.new("RGB", (640, 360), color=(40, 40, 40))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        frame = buf.getvalue()
    return Response(frame, mimetype="image/jpeg")


def _line_mjpeg(camera_id: int):
    while True:
        frame = app_module.stream_manager.get_frame(camera_id) if app_module.stream_manager else None
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        else:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + _line_connecting_jpeg() + b"\r\n"
            )
        time.sleep(0.1)


def _line_connecting_jpeg() -> bytes:
    """Small placeholder JPEG for line feed."""
    import cv2
    import numpy as np

    img = np.zeros((360, 640, 3), dtype=np.uint8)
    img[:] = (30, 30, 30)
    cv2.putText(
        img, "Connecting...", (210, 190),
        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2,
    )
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return buf.tobytes()


@line_setup_bp.route("/feed/<int:camera_id>")
def line_feed(camera_id: int):
    return Response(
        _line_mjpeg(camera_id),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
