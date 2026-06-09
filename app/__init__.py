"""Flask application factory."""

import os
from flask import Flask
from .database import db, init_db
from .services.stream_manager import StreamManager

stream_manager: StreamManager | None = None


def create_app() -> Flask:
    base_dir = os.environ.get("OYSTER_BASE_DIR", os.path.dirname(os.path.dirname(__file__)))

    app = Flask(
        __name__,
        instance_path=os.path.join(base_dir, "instance"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    )

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "oyster-secret-2024")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + os.path.join(base_dir, "instance", "oyster.db")
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["DATASET_DIR"] = os.path.join(base_dir, "dataset")
    app.config["MODELS_DIR"] = os.path.join(base_dir, "models_store")
    app.config["SNAPSHOTS_DIR"] = os.path.join(
        os.path.dirname(__file__), "static", "snapshots"
    )

    # Ensure required directories exist
    for d in [
        app.config["DATASET_DIR"],
        app.config["MODELS_DIR"],
        app.config["SNAPSHOTS_DIR"],
        app.instance_path,
    ]:
        os.makedirs(d, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        init_db()

    # Blueprints
    from .routes.dashboard import dashboard_bp
    from .routes.settings import settings_bp
    from .routes.training import training_bp
    from .routes.intruder import intruder_bp
    from .routes.line_setup import line_setup_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(intruder_bp)
    app.register_blueprint(line_setup_bp)

    # Start the global stream manager
    global stream_manager
    stream_manager = StreamManager(app)
    stream_manager.start_all()

    return app
