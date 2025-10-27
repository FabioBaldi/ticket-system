from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Accedi')

class RegisterForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Conferma Password', validators=[DataRequired(), EqualTo('password')])
    is_admin = BooleanField('Admin?')
    submit = SubmitField('Crea utente')

class TicketForm(FlaskForm):
    title = StringField('Titolo', validators=[DataRequired(), Length(min=3, max=200)])
    description = TextAreaField('Descrizione', validators=[DataRequired(), Length(min=5)])
    priority = SelectField('Priorità', choices=[('BASSA','Bassa'),('MEDIA','Media'),('ALTA','Alta'),('CRITICA','Critica')], default='MEDIA')
    assigned_to = SelectField('Assegnatario', coerce=int, validators=[Optional()])
    attachment = FileField('Allegato (opzionale)')
    submit = SubmitField('Crea Ticket')

class ActionForm(FlaskForm):
    status = SelectField('Stato', choices=[('APERTO','Aperto'),('IN_LAVORAZIONE','In lavorazione'),('CHIUSO','Chiuso')])
    priority = SelectField('Priorità', choices=[('BASSA','Bassa'),('MEDIA','Media'),('ALTA','Alta'),('CRITICA','Critica')], default='MEDIA')
    assigned_to = SelectField('Assegnatario', coerce=int, validators=[Optional()])
    notes = TextAreaField('Note (opzionali)', validators=[Optional()])
    attachment = FileField('Aggiorna allegato (opzionale)')
    submit = SubmitField('Aggiorna Ticket')
