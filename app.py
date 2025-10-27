
import os
from flask import Flask, request, redirect, url_for, flash, render_template_string
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Import your SQLAlchemy instance and models
# models.py must define: db (SQLAlchemy), User (with fields: email, password_hash, name, is_admin)
from models import db, User  # type: ignore

# --- Small inline templates so it works even if Jinja files are missing ---
LOGIN_HTML = """
<!doctype html>
<html lang="it">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login</title>
  </head>
  <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; max-width: 480px; margin: 40px auto;">
    <h2>Accedi</h2>
    {% if msg %}<div style="padding:10px; background:#fee; border:1px solid #f99; margin-bottom:10px;">{{ msg }}</div>{% endif %}
    <form method="post">
      <label>Email</label><br>
      <input type="email" name="email" required style="width:100%; padding:10px; margin:6px 0 14px;"><br>
      <label>Password</label><br>
      <input type="password" name="password" required style="width:100%; padding:10px; margin:6px 0 14px;"><br>
      <button type="submit" style="padding:10px 16px;">Entra</button>
    </form>
  </body>
</html>
"""

HOME_HTML = """
<!doctype html>
<html lang="it">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Home</title>
  </head>
  <body style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; max-width: 720px; margin: 40px auto;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h2>Ciao {{ user.name or user.email }} 👋</h2>
      <a href="{{ url_for('logout') }}">Logout</a>
    </div>
    <p>Login effettuato con successo.</p>
  </body>
</html>
"""

def create_app() -> Flask:
    app = Flask(__name__)

    # --- Basic config ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- Database URL (Render Postgres or local SQLite) ---
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    db_url = os.getenv('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        # Render sometimes still provides postgres://; SQLAlchemy 2.x wants postgresql+psycopg2://
        db_url = db_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url or f"sqlite:///{os.path.join(BASE_DIR, 'tickets.db')}"

    # --- Init extensions ---
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # --- Create tables and ensure an admin exists ---
    with app.app_context():
        db.create_all()

        admin_email = os.environ.get('ADMIN_EMAIL')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        admin_name = os.environ.get('ADMIN_NAME', 'Admin')

        if admin_email and admin_password:
            admin = User.query.filter_by(email=admin_email).first()
            if not admin:
                admin = User(name=admin_name, email=admin_email, is_admin=True)
                # Prefer set_password if model provides it
                if hasattr(admin, 'set_password'):
                    admin.set_password(admin_password)  # type: ignore[attr-defined]
                else:
                    # Fallback: assign password_hash directly
                    if hasattr(admin, 'password_hash'):
                        admin.password_hash = generate_password_hash(admin_password)  # type: ignore[attr-defined]
                db.session.add(admin)
                db.session.commit()

    # --- Routes ---
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('home'))

        msg = None
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')

            user = User.query.filter_by(email=email).first()
            ok = False
            if user:
                if hasattr(user, 'check_password'):
                    try:
                        ok = user.check_password(password)  # type: ignore[attr-defined]
                    except Exception:
                        ok = False
                # Fallback if model doesn't expose check_password
                if not ok and hasattr(user, 'password_hash'):
                    try:
                        ok = check_password_hash(user.password_hash, password)  # type: ignore[arg-type]
                    except Exception:
                        ok = False

            if ok and user:
                login_user(user)
                next_url = request.args.get('next') or url_for('home')
                return redirect(next_url)
            else:
                msg = 'Credenziali non valide'

        return render_template_string(LOGIN_HTML, msg=msg)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/')
    @login_required
    def home():
        return render_template_string(HOME_HTML, user=current_user)

    return app


# For local debugging
if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
