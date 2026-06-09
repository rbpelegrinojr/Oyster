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
    line_config = db.relationship(
        "LineConfig", backref="camera", uselist=False, lazy=True
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
    # 'face_detection' | 'line_crossing'

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera.name if self.camera else "Unknown",
            "timestamp": self.timestamp.isoformat(),
            "snapshot_path": self.snapshot_path,
            "event_type": self.event_type,
        }


class LineConfig(db.Model):
    __tablename__ = "line_configs"

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"), unique=True)
    # Coordinates stored as fractions (0.0 – 1.0) of frame width/height
    x1 = db.Column(db.Float, default=0.0)
    y1 = db.Column(db.Float, default=0.5)
    x2 = db.Column(db.Float, default=1.0)
    y2 = db.Column(db.Float, default=0.5)
    enabled = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "enabled": self.enabled,
        }
