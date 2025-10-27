# Trouble Ticket App (v5 FIX)
Questa versione corregge l'aggiornamento dello stato (no override su POST) e include Flask-SQLAlchemy nei requirements.

## Setup
```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python create_admin.py
python app.py
```
