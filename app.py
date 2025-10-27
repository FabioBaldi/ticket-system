
import os
import string
import secrets
from datetime import datetime
from io import BytesIO, StringIO
import csv

from flask import (
    Flask, render_template, redirect, url_for, flash, request,
    send_from_directory, current_app, send_file
)
from flask_login import (
    LoginManager, login_user, login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import db, User, Ticket, TicketAction, TicketStatus
from forms import LoginForm, RegisterForm, TicketForm, ActionForm

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # --- Database: PostgreSQL su Render, SQLite in locale ---
    db_url = os.getenv('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        db_url or 'sqlite:///' + os.path.join(BASE_DIR, 'tickets.db')
    )

    # Inizializza estensioni
    db.init_app(app)

    # Crea tabelle se non esistono e seed opzionale admin
    with app.app_context():
        db.create_all()

        # Seed amministratore opzionale (usa variabili ENV se presenti)
        admin_email = os.getenv('ADMIN_EMAIL')
        admin_password = os.getenv('ADMIN_PASSWORD')
        if admin_email and admin_password:
            existing = db.session.query(User).filter_by(email=admin_email.lower()).first()
            if not existing:
                admin = User(
                    name='Admin',
                    email=admin_email.lower(),
                    is_admin=True
                )
                admin.password_hash = generate_password_hash(admin_password)
                db.session.add(admin)
                db.session.commit()

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --------------------- DASHBOARD ---------------------
    @app.route('/')
    @login_required
    def index():
        total = db.session.query(Ticket.id).count()
        open_count = db.session.query(Ticket.id).filter(Ticket.status == TicketStatus.OPEN).count()
        progress_count = db.session.query(Ticket.id).filter(Ticket.status == TicketStatus.IN_PROGRESS).count()
        closed_count = db.session.query(Ticket.id).filter(Ticket.status == TicketStatus.CLOSED).count()
        recent = db.session.query(Ticket).order_by(Ticket.updated_at.desc()).limit(10).all()
        return render_template(
            'dashboard.html',
            total=total or 0,
            open_count=open_count or 0,
            progress_count=progress_count or 0,
            closed_count=closed_count or 0,
            recent=recent
        )

    # --------------------- AUTH ---------------------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = db.session.query(User).filter_by(email=form.email.data.lower()).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user, remember=True)
                return redirect(url_for('index'))
            flash('Email o password non validi', 'danger')
        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/register', methods=['GET', 'POST'])
    @login_required
    def register():
        if not current_user.is_admin:
            flash('Solo gli admin possono creare nuovi utenti.', 'warning')
            return redirect(url_for('index'))
        form = RegisterForm()
        if form.validate_on_submit():
            if db.session.query(User).filter_by(email=form.email.data.lower()).first():
                flash('Esiste già un utente con questa email.', 'warning')
                return redirect(url_for('register'))
            user = User(
                name=form.name.data.strip(),
                email=form.email.data.lower(),
                is_admin=form.is_admin.data
            )
            user.password_hash = generate_password_hash(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Utente creato con successo.', 'success')
            return redirect(url_for('users'))
        return render_template('register.html', form=form)

    # --------------------- USERS ---------------------
    @app.route('/users')
    @login_required
    def users():
        if not current_user.is_admin:
            flash('Solo gli admin possono vedere la lista utenti.', 'warning')
            return redirect(url_for('index'))
        items = db.session.query(User).order_by(User.created_at.desc()).all()
        return render_template('users.html', items=items)

    @app.route('/users/delete/<int:user_id>', methods=['POST'])
    @login_required
    def delete_user(user_id):
        if not current_user.is_admin:
            flash('Solo gli admin possono eliminare utenti.', 'warning')
            return redirect(url_for('users'))

        user = db.session.get(User, user_id)
        if not user:
            flash('Utente non trovato.', 'danger')
            return redirect(url_for('users'))

        if user.is_admin or user.id == current_user.id:
            flash('Non puoi eliminare un amministratore o te stesso.', 'danger')
            return redirect(url_for('users'))

        has_created = db.session.query(Ticket.id).filter(Ticket.created_by_id == user.id).first()
        has_assigned = db.session.query(Ticket.id).filter(Ticket.assigned_to_id == user.id).first()
        if has_created or has_assigned:
            flash('Impossibile eliminare l’utente: è collegato a uno o più ticket.', 'warning')
            return redirect(url_for('users'))

        db.session.delete(user)
        db.session.commit()
        flash(f"Utente {user.name} eliminato con successo.", 'success')
        return redirect(url_for('users'))

    @app.route('/users/reset_password/<int:user_id>', methods=['POST'])
    @login_required
    def reset_password(user_id):
        if not current_user.is_admin:
            flash('Solo gli admin possono reimpostare le password.', 'warning')
            return redirect(url_for('users'))

        user = db.session.get(User, user_id)
        if not user:
            flash('Utente non trovato.', 'danger')
            return redirect(url_for('users'))

        new_password = (request.form.get('new_password') or '').strip()
        if not new_password:
            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for _ in range(10))

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash(f"Password aggiornata per {user.name}. Nuova password: {new_password}", 'success')
        return redirect(url_for('users'))

    # --------------------- TICKETS ---------------------
    @app.route('/tickets')
    @login_required
    def tickets():
        status = request.args.get('status', 'all')
        q = db.session.query(Ticket).order_by(Ticket.updated_at.desc())
        if status == 'open':
            q = q.filter(Ticket.status == TicketStatus.OPEN)
        elif status == 'in_progress':
            q = q.filter(Ticket.status == TicketStatus.IN_PROGRESS)
        elif status == 'closed':
            q = q.filter(Ticket.status == TicketStatus.CLOSED)
        items = q.all()
        return render_template('tickets_list.html', items=items, status=status)

    # --------- EXPORT: Excel (default) o CSV via ?format=csv ---------
    @app.route('/tickets/export')
    @login_required
    def export_tickets():
        status = request.args.get('status', 'all')
        out_format = request.args.get('format', 'xlsx').lower()  # 'xlsx' | 'csv'

        q = db.session.query(Ticket).order_by(Ticket.updated_at.desc())
        filename_map = {
            'all': 'ticket_tutti',
            'open': 'ticket_aperti',
            'in_progress': 'ticket_in_lavorazione',
            'closed': 'ticket_chiusi'
        }
        if status == 'open':
            q = q.filter(Ticket.status == TicketStatus.OPEN)
        elif status == 'in_progress':
            q = q.filter(Ticket.status == TicketStatus.IN_PROGRESS)
        elif status == 'closed':
            q = q.filter(Ticket.status == TicketStatus.CLOSED)
        else:
            status = 'all'

        tickets = q.all()

        header = ["Titolo del ticket", "Descrizione del ticket", "Nome utente (creatore)", "Stato", "Data di creazione"]
        rows = []
        for t in tickets:
            rows.append([
                t.title,
                t.description,
                t.created_by.name if t.created_by else "",
                t.status.value,
                t.created_at.strftime("%d/%m/%Y %H:%M"),
            ])

        if out_format == 'csv':
            sio = StringIO()
            writer = csv.writer(sio, delimiter=';')
            writer.writerow(header)
            writer.writerows(rows)
            data = sio.getvalue().encode('utf-8-sig')
            bio = BytesIO(data)
            return send_file(
                bio, as_attachment=True,
                download_name=f"{filename_map.get(status, 'tickets')}.csv",
                mimetype="text/csv"
            )

        # Excel con openpyxl (fallback a CSV se non disponibile)
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Tickets"
            ws.append(header)
            for r in rows:
                ws.append(r)
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            return send_file(
                output, as_attachment=True,
                download_name=f"{filename_map.get(status, 'tickets')}.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception:
            sio = StringIO()
            writer = csv.writer(sio, delimiter=';')
            writer.writerow(header)
            writer.writerows(rows)
            data = sio.getvalue().encode('utf-8-sig')
            bio = BytesIO(data)
            return send_file(
                bio, as_attachment=True,
                download_name=f"{filename_map.get(status, 'tickets')}.csv",
                mimetype="text/csv"
            )

    @app.route('/tickets/new', methods=['GET', 'POST'])
    @login_required
    def ticket_new():
        form = TicketForm()
        form.assigned_to.choices = [(0, '-- Nessuno --')] + [
            (u.id, f"{u.name} ({u.email})")
            for u in db.session.query(User).order_by(User.name).all()
        ]
        if form.validate_on_submit():
            filename = None
            if form.attachment.data:
                filename = secure_filename(form.attachment.data.filename)
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                form.attachment.data.save(save_path)
            t = Ticket(
                title=form.title.data.strip(),
                description=form.description.data.strip(),
                status=TicketStatus.OPEN,
                priority=form.priority.data,
                created_by_id=current_user.id,
                assigned_to_id=form.assigned_to.data if form.assigned_to.data else None,
                attachment=filename
            )
            db.session.add(t)
            db.session.flush()
            action = TicketAction(
                ticket_id=t.id,
                user_id=current_user.id,
                action='CREAZIONE',
                notes='Ticket creato'
            )
            db.session.add(action)
            db.session.commit()
            flash('Ticket creato.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=t.id))
        return render_template('ticket_new.html', form=form)

    @app.route('/tickets/<int:ticket_id>', methods=['GET', 'POST'])
    @login_required
    def ticket_detail(ticket_id):
        t = db.session.get(Ticket, ticket_id)
        if not t:
            flash('Ticket non trovato.', 'danger')
            return redirect(url_for('tickets'))
        form = ActionForm()
        form.assigned_to.choices = [(0, '-- Nessuno --')] + [
            (u.id, f"{u.name} ({u.email})")
            for u in db.session.query(User).order_by(User.name).all()
        ]

        if request.method == 'GET':
            form.status.data = t.status.value
            form.assigned_to.data = t.assigned_to_id or 0
            form.priority.data = t.priority

        if form.validate_on_submit():
            changes = []

            # Stato
            if form.status.data != t.status.value:
                old = t.status.value
                if form.status.data in TicketStatus.__members__:
                    t.status = TicketStatus[form.status.data]
                else:
                    t.status = TicketStatus(form.status.data)
                changes.append(f"Stato: {old} → {t.status.value}")

            # Assegnatario
            new_assignee_id = form.assigned_to.data if form.assigned_to.data != 0 else None
            if new_assignee_id != t.assigned_to_id:
                old_name = t.assigned_to.name if t.assigned_to else "Nessuno"
                new_name = db.session.get(User, new_assignee_id).name if new_assignee_id else "Nessuno"
                t.assigned_to_id = new_assignee_id
                changes.append(f"Assegnatario: {old_name} → {new_name}")

            # Priorità
            if form.priority.data != t.priority:
                changes.append(f"Priorità: {t.priority} → {form.priority.data}")
                t.priority = form.priority.data

            # Allegato
            if form.attachment.data:
                filename = secure_filename(form.attachment.data.filename)
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                form.attachment.data.save(save_path)
                t.attachment = filename
                changes.append(f"Allegato aggiornato: {filename}")

            notes = form.notes.data.strip() if form.notes.data else ""
            act = TicketAction(
                ticket_id=t.id,
                user_id=current_user.id,
                action=("; ".join(changes) if changes else "Aggiornamento"),
                notes=notes
            )

            t.updated_at = datetime.utcnow()
            db.session.add(t)
            db.session.add(act)
            db.session.commit()

            flash('Ticket aggiornato.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=t.id))

        actions = (
            db.session.query(TicketAction)
            .filter(TicketAction.ticket_id == ticket_id)
            .order_by(TicketAction.created_at.desc())
            .all()
        )
        return render_template('ticket_detail.html', t=t, form=form, actions=actions)

    # --------------------- FILES ---------------------
    @app.route('/uploads/<path:filename>')
    @login_required
    def uploads(filename):
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True
        )

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8080)
