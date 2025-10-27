from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import enum
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------------- ENUM ----------------
class TicketStatus(enum.Enum):
    OPEN = "Aperto"
    IN_PROGRESS = "In lavorazione"
    CLOSED = "Chiuso"


# ---------------- USER ----------------
class User(db.Model, UserMixin):
    __tablename__ = "users"  # Evita parola riservata "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets_created = db.relationship("Ticket", backref="created_by", foreign_keys="Ticket.created_by_id")
    tickets_assigned = db.relationship("Ticket", backref="assigned_to", foreign_keys="Ticket.assigned_to_id")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ---------------- TICKET ----------------
class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False)
    priority = db.Column(db.String(50), default="Normale")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    attachment = db.Column(db.String(255), nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    actions = db.relationship("TicketAction", backref="ticket", lazy=True, cascade="all, delete-orphan")


# ---------------- ACTION ----------------
class TicketAction(db.Model):
    __tablename__ = "ticket_actions"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

