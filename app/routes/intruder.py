"""Intruder log routes."""

from __future__ import annotations

from flask import Blueprint, render_template, request, jsonify

from app.models import IntruderLog, Camera

intruder_bp = Blueprint("intruder", __name__, url_prefix="/intruder")

_PAGE_SIZE = 20


@intruder_bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    camera_id = request.args.get("camera_id", None, type=int)
    event_type = request.args.get("event_type", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    query = IntruderLog.query.order_by(IntruderLog.timestamp.desc())

    if camera_id:
        query = query.filter(IntruderLog.camera_id == camera_id)
    if event_type:
        query = query.filter(IntruderLog.event_type == event_type)
    if date_from:
        query = query.filter(IntruderLog.timestamp >= date_from)
    if date_to:
        query = query.filter(IntruderLog.timestamp <= date_to + " 23:59:59")

    pagination = query.paginate(page=page, per_page=_PAGE_SIZE, error_out=False)
    cameras = Camera.query.order_by(Camera.name).all()

    return render_template(
        "intruder_logs.html",
        logs=pagination.items,
        pagination=pagination,
        cameras=cameras,
        selected_camera=camera_id,
        selected_event=event_type,
        date_from=date_from,
        date_to=date_to,
    )


@intruder_bp.route("/api/recent")
def recent_api():
    """Return the 10 most recent intruder events as JSON (for dashboard banner)."""
    logs = (
        IntruderLog.query.order_by(IntruderLog.timestamp.desc()).limit(10).all()
    )
    return jsonify([l.to_dict() for l in logs])
