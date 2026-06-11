"""Settings routes – camera CRUD and LAN scanner."""

from __future__ import annotations

import threading
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash

from app.database import db
from app.models import Camera
import app as app_module

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

# ---------------------------------------------------------------------------
# LAN scan state (runs in background thread, result polled by JS)
# ---------------------------------------------------------------------------
_scan_lock = threading.Lock()
_scan_result: list | None = None
_scan_running = False


@settings_bp.route("/")
def index():
    cameras = Camera.query.order_by(Camera.id).all()
    return render_template("settings.html", cameras=cameras)


@settings_bp.route("/camera/add", methods=["POST"])
def add_camera():
    name = request.form.get("name", "").strip()
    ip = request.form.get("ip_address", "").strip()
    username = request.form.get("username", "admin").strip()
    pass_val = request.form.get("password", "").strip()
    rtsp_url = request.form.get("rtsp_url", "").strip()

    if not rtsp_url:
        # Build default Tapo C200 RTSP URL
        rtsp_url = f"rtsp://{username}:{pass_val}@{ip}:554/stream1"

    cam_data = dict(name=name, ip_address=ip, rtsp_url=rtsp_url, username=username)
    cam = Camera(**cam_data)
    setattr(cam, "password", pass_val)
    db.session.add(cam)
    db.session.commit()

    if app_module.stream_manager:
        app_module.stream_manager.restart_worker(cam.id, cam.rtsp_url)

    flash(f'Camera "{name}" added successfully.', "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/camera/<int:camera_id>/edit", methods=["GET", "POST"])
def edit_camera(camera_id: int):
    cam = Camera.query.get_or_404(camera_id)
    if request.method == "POST":
        cam.name = request.form.get("name", cam.name).strip()
        cam.ip_address = request.form.get("ip_address", cam.ip_address).strip()
        cam.username = request.form.get("username", cam.username).strip()
        cam.password = request.form.get("password", cam.password).strip()
        rtsp_url = request.form.get("rtsp_url", "").strip()
        if not rtsp_url:
            rtsp_url = f"rtsp://{cam.username}:{cam.password}@{cam.ip_address}:554/stream1"
        cam.rtsp_url = rtsp_url
        cam.is_active = "is_active" in request.form
        db.session.commit()

        if app_module.stream_manager:
            if cam.is_active:
                app_module.stream_manager.restart_worker(cam.id, cam.rtsp_url)
            else:
                app_module.stream_manager.stop_worker(cam.id)

        flash(f'Camera "{cam.name}" updated.', "success")
        return redirect(url_for("settings.index"))

    return render_template("edit_camera.html", cam=cam)


@settings_bp.route("/camera/<int:camera_id>/delete", methods=["POST"])
def delete_camera(camera_id: int):
    cam = Camera.query.get_or_404(camera_id)
    if app_module.stream_manager:
        app_module.stream_manager.stop_worker(cam.id)
    db.session.delete(cam)
    db.session.commit()
    flash(f'Camera "{cam.name}" deleted.', "warning")
    return redirect(url_for("settings.index"))


@settings_bp.route("/camera/<int:camera_id>/toggle", methods=["POST"])
def toggle_camera(camera_id: int):
    cam = Camera.query.get_or_404(camera_id)
    cam.is_active = not cam.is_active
    db.session.commit()
    if app_module.stream_manager:
        if cam.is_active:
            app_module.stream_manager.restart_worker(cam.id, cam.rtsp_url)
        else:
            app_module.stream_manager.stop_worker(cam.id)
    return jsonify({"is_active": cam.is_active})


# ---------------------------------------------------------------------------
# LAN scanner API
# ---------------------------------------------------------------------------

def _do_scan(subnet: str | None):
    global _scan_result, _scan_running
    from app.services.network_scanner import scan_network

    result = scan_network(subnet)
    with _scan_lock:
        _scan_result = result
        _scan_running = False


@settings_bp.route("/scan", methods=["POST"])
def start_scan():
    global _scan_running, _scan_result
    subnet = request.json.get("subnet") if request.is_json else None
    with _scan_lock:
        if _scan_running:
            return jsonify({"status": "running"})
        _scan_running = True
        _scan_result = None

    t = threading.Thread(target=_do_scan, args=(subnet,), daemon=True)
    t.start()
    return jsonify({"status": "started"})


@settings_bp.route("/scan/result")
def scan_result():
    with _scan_lock:
        running = _scan_running
        result = _scan_result
    if running:
        return jsonify({"status": "running"})
    if result is None:
        return jsonify({"status": "idle"})
    return jsonify({"status": "done", "hosts": result})
