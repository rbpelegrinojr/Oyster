"""Zone setup routes – define intrusion detection polygon per camera."""

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
from app.models import Camera, ZoneConfig
import app as app_module

zone_setup_bp = Blueprint("zone_setup", __name__, url_prefix="/zone")


@zone_setup_bp.route("/")
def index():
    cameras = Camera.query.order_by(Camera.id).all()
    configs = {zc.camera_id: zc for zc in ZoneConfig.query.all()}
    return render_template("zone_setup.html", cameras=cameras, configs=configs)


@zone_setup_bp.route("/save", methods=["POST"])
def save_zone():
    data = request.get_json()
    camera_id = data.get("camera_id")
    if not camera_id:
        return jsonify({"success": False, "message": "camera_id required"})

    polygon = data.get("polygon", [])
    if len(polygon) < 3:
        return jsonify({"success": False, "message": "At least 3 points required for a zone."})

    config = ZoneConfig.query.filter_by(camera_id=camera_id).first()
    if not config:
        config = ZoneConfig(camera_id=camera_id)
        db.session.add(config)

    config.set_polygon_points(polygon)
    config.enabled = bool(data.get("enabled", True))
    db.session.commit()

    return jsonify({"success": True})


@zone_setup_bp.route("/get/<int:camera_id>")
def get_zone(camera_id: int):
    config = ZoneConfig.query.filter_by(camera_id=camera_id).first()
    if config:
        return jsonify(config.to_dict())
    return jsonify({"camera_id": camera_id, "polygon": [], "enabled": False})


@zone_setup_bp.route("/delete/<int:camera_id>", methods=["POST"])
def delete_zone(camera_id: int):
    config = ZoneConfig.query.filter_by(camera_id=camera_id).first()
    if config:
        db.session.delete(config)
        db.session.commit()
    flash("Zone configuration deleted.", "warning")
    return redirect(url_for("zone_setup.index"))


@zone_setup_bp.route("/toggle/<int:camera_id>", methods=["POST"])
def toggle_zone(camera_id: int):
    config = ZoneConfig.query.filter_by(camera_id=camera_id).first()
    if config:
        config.enabled = not config.enabled
        db.session.commit()
        return jsonify({"enabled": config.enabled})
    return jsonify({"enabled": False})


# Snapshot preview (single frame) for zone drawing
@zone_setup_bp.route("/snapshot/<int:camera_id>")
def snapshot(camera_id: int):
    frame = app_module.stream_manager.get_frame(camera_id) if app_module.stream_manager else None
    if not frame:
        import io
        from PIL import Image

        img = Image.new("RGB", (640, 360), color=(40, 40, 40))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        frame = buf.getvalue()
    return Response(frame, mimetype="image/jpeg")


def _zone_mjpeg(camera_id: int):
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
                b"Content-Type: image/jpeg\r\n\r\n" + _zone_connecting_jpeg() + b"\r\n"
            )
        time.sleep(0.1)


def _zone_connecting_jpeg() -> bytes:
    """Small placeholder JPEG for zone feed."""
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


@zone_setup_bp.route("/feed/<int:camera_id>")
def zone_feed(camera_id: int):
    return Response(
        _zone_mjpeg(camera_id),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
