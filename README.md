# Translation Office App

A simple FastAPI web application for managing translation requests between clients, managers, and translators. The app uses SQLite for persistence, FastAPI with Jinja2 templates for the UI, and Bootstrap for basic styling.

## Features

- Client registration and login.
- Session-based authentication for Clients, Managers, and Translators.
- Clients can upload documents (PDF, DOCX, TXT) and specify source and target languages.
- Managers can view all translation jobs, update their status, and assign translators.
- Translators can view jobs assigned to them and upload completed translations.
- Files are stored locally in the `uploads/` directory.

## Prerequisites

- Python 3.9+

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Running the Application

```bash
uvicorn app.main:app --reload
```

The application will be available at [http://localhost:8000](http://localhost:8000).

## Default Users

The database is automatically created on first run with the following accounts:

| Role       | Username    | Password         |
|------------|-------------|------------------|
| Manager    | `manager1`  | `managerpass`    |
| Translator | `translator1` | `translatorpass` |
| Translator | `translator2` | `translatorpass` |

Clients can create their own accounts via the registration page.

## Directory Structure

```
app/
├── main.py
├── models.py
├── database.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── client_dashboard.html
│   ├── client_request.html
│   ├── manager_dashboard.html
│   └── translator_dashboard.html
└── static/
    └── css/
        └── styles.css
uploads/
```

Uploaded files are stored in the `uploads/` directory. Ensure this folder is writable by the application process.
