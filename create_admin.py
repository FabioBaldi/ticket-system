from app import create_app
from models import db, User
from werkzeug.security import generate_password_hash

ADMIN_NAME = "Admin"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Password123"

app = create_app()

with app.app_context():
    existing = db.session.query(User).filter_by(email=ADMIN_EMAIL.lower()).first()
    if existing:
        print(f"❌ Esiste già un utente con email {ADMIN_EMAIL}")
    else:
        u = User(name=ADMIN_NAME, email=ADMIN_EMAIL.lower(), is_admin=True, password_hash=generate_password_hash(ADMIN_PASSWORD))
        db.session.add(u)
        db.session.commit()
        print("✅ Utente admin creato con successo!")
        print(f"Email: {ADMIN_EMAIL}")
        print(f"Password: {ADMIN_PASSWORD}")
