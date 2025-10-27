
import os
from datetime import datetime

from flask import Flask
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

from models import db, User  # assumes models.py defines SQLAlchemy db and User model


def _coerce_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _ensure_upload_folder(app: Flask) -> None:
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)


def _ensure_admin() -> None:
    """Create an admin user on first boot if not present.

    Reads credentials from environment variables and uses safe defaults.
    - ADMIN_NAME
    - ADMIN_EMAIL
    - ADMIN_PASSWORD
    """
    admin_name = os.getenv("ADMIN_NAME", "Fabio")
    admin_email = os.getenv("ADMIN_EMAIL", "fabio@ondapiu.it")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin123!")

    # Is there already a user with that email?
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        # If user exists but not admin, upgrade it to admin (optional behavior)
        if not getattr(existing, "is_admin", False):
            existing.is_admin = True
            db.session.commit()
        return

    # Create a brand-new admin account
    user = User(
        name=admin_name,
        email=admin_email,
        is_admin=True,
        created_at=datetime.utcnow()
    )

    # Prefer model's set_password if it exists, otherwise set password_hash
    if hasattr(user, "set_password"):
        user.set_password(admin_password)  # type: ignore[attr-defined]
    else:
        # Fallback if User model exposes `password_hash` directly
        setattr(user, "password_hash", generate_password_hash(admin_password))

    db.session.add(user)
    db.session.commit()


def create_app():
    app = Flask(__name__)

    # -------- Base config
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = _coerce_bool(
        os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS", "false")
    )

    # Uploads
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    _ensure_upload_folder(app)

    # -------- Database URL (Render sets DATABASE_URL for Postgres)
    db_url = os.getenv("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        # SQLAlchemy 2.x expects the psycopg2 scheme
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)

    if not db_url:
        # Local/dev fallback to SQLite file
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "tickets.db")
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    # -------- Init DB & Login
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"  # route endpoint name for @login_required redirects
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        # SQLAlchemy 2.0-style primary-key get
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # -------- Create tables and bootstrap admin inside app context
    with app.app_context():
        db.create_all()
        _ensure_admin()

    # NOTE: Your route/view functions can live in this same file or be imported here.
    # If you keep routes in a separate module (e.g., views.py), import and register them here.
    # Example:
    #   from views import bp as views_bp
    #   app.register_blueprint(views_bp)

    return app
