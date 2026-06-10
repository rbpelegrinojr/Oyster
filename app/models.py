"""SQLAlchemy models for Oyster."""

from datetime import datetime, timezone
from .database import db


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Camera(db.Model):
    __tablename__ = "cameras"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    rtsp_url = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(80), default="admin")
    password = db.Column(db.String(80), default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    intruder_logs = db.relationship("IntruderLog", backref="camera", lazy=True)
    zone_config = db.relationship(
        "ZoneConfig", backref="camera", uselist=False, lazy=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "ip_address": self.ip_address,
            "rtsp_url": self.rtsp_url,
            "username": self.username,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


class Person(db.Model):
    __tablename__ = "persons"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    sample_count = db.Column(db.Integer, default=0)
    trained = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sample_count": self.sample_count,
            "trained": self.trained,
            "created_at": self.created_at.isoformat(),
        }


class IntruderLog(db.Model):
    __tablename__ = "intruder_logs"

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"), nullable=True)
    timestamp = db.Column(db.DateTime, default=_utcnow)
    snapshot_path = db.Column(db.String(255), nullable=True)
    event_type = db.Column(db.String(50), default="face_detection")
    # 'face_detection' | 'zone_intrusion'

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera.name if self.camera else "Unknown",
            "timestamp": self.timestamp.isoformat(),
            "snapshot_path": self.snapshot_path,
            "event_type": self.event_type,
        }


class ZoneConfig(db.Model):
    __tablename__ = "zone_configs"

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"), unique=True)
    # Polygon points stored as JSON string: [[x1_frac, y1_frac], [x2_frac, y2_frac], ...]
    # Coordinates are fractions (0.0 – 1.0) of frame width/height
    polygon_json = db.Column(db.Text, default="[]")
    enabled = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def get_polygon_points(self) -> list:
        """Return polygon as list of [x_frac, y_frac] pairs."""
        import json
        try:
            return json.loads(self.polygon_json) if self.polygon_json else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_polygon_points(self, points: list) -> None:
        """Store polygon points from a list of [x_frac, y_frac] pairs."""
        import json
        self.polygon_json = json.dumps(points)

    def get_polygon_pixels(self, frame_w: int, frame_h: int) -> list:
        """Return polygon as list of (x_px, y_px) tuples scaled to frame size."""
        points = self.get_polygon_points()
        return [(int(p[0] * frame_w), int(p[1] * frame_h)) for p in points]

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "polygon": self.get_polygon_points(),
            "enabled": self.enabled,
        }
