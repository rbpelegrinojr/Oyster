"""SQLAlchemy database instance and initialisation helpers."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db():
    """Create all tables if they don't yet exist."""
    from . import models  # noqa: F401 – ensure models are registered
    db.create_all()
