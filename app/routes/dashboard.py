"""Dashboard routes – camera stream grid and MJPEG endpoints."""

from __future__ import annotations

import time
from flask import Blueprint, Response, render_template, current_app

from app import stream_manager

dashboard_bp = Blueprint("dashboard", __name__)


def _mjpeg_generator(camera_id: int):
    """Yield MJPEG frames for the given camera."""
    while True:
        frame = stream_manager.get_frame(camera_id) if stream_manager else None
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        time.sleep(0.04)  # ~25 fps cap


@dashboard_bp.route("/")
def index():
    return dashboard()


@dashboard_bp.route("/dashboard")
def dashboard():
    from app.models import Camera

    cameras = Camera.query.filter_by(is_active=True).order_by(Camera.id).all()
    return render_template("dashboard.html", cameras=cameras)


@dashboard_bp.route("/video_feed/<int:camera_id>")
def video_feed(camera_id: int):
    return Response(
        _mjpeg_generator(camera_id),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
