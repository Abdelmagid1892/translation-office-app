# Translation Office App

A feature-rich FastAPI web application for managing the entire lifecycle of translation projects. Clients can submit requests and approve quotes, managers coordinate translators and finances, translators collaborate via an integrated workspace, and everyone stays informed through in-app chat and email notifications.

## Highlights

- 🔐 Session-based authentication with role-aware navigation for Clients, Managers, Translators and Admins.
- 📄 Automated quote generation with PDF/DOCX/TXT text extraction, per-language rates and client approvals.
- 🧑‍💼 Manager dashboards with search, pagination, job assignment, glossary management and activity auditing.
- 🧑‍💻 Translator workspace with glossary highlighting, QA number checks and deliverable uploads.
- 💬 Real-time (WebSocket) job chat with HTTP polling fallback.
- 📧 Pluggable SMTP notifications for quote, assignment and delivery events (logs to console when SMTP is not configured).
- 🧾 Invoice PDF generation via ReportLab and client download portal.

## Tech Stack

- FastAPI with modular routers and service layer (`app/routers`, `app/services`).
- SQLAlchemy ORM with SQLite by default (`translation_office.db`).
- Jinja2 templating + Bootstrap 5 UI.
- ReportLab for PDF invoices, pdfminer / python-docx for text extraction.

## Getting Started

### Prerequisites

- Python 3.9+

### Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables (optional)

Create a `.env` file to configure SMTP delivery (logs to stdout when unset):

```
SESSION_SECRET=supersecretkey
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=user@example.com
SMTP_PASSWORD=supersecret
SMTP_SENDER=translations@example.com
SMTP_STARTTLS=1
```

### Run the app

```bash
uvicorn app.main:app --reload
```

Visit [http://localhost:8000](http://localhost:8000).

## Default Accounts

The database is created automatically on first launch with seed data:

| Role       | Username                | Password       |
|------------|-------------------------|----------------|
| Manager    | `manager1@example.com`  | `managerpass`  |
| Translator | `translator1@example.com` | `translatorpass` |
| Translator | `translator2@example.com` | `translatorpass` |
| Admin      | `admin@example.com`     | `adminpass`    |

Clients self-register from the sign-up page.

## Key Workflows

### Client Journey

1. Upload PDF/DOCX/TXT files, auto-count words and receive a draft quote.
2. Review quotes, approve/reject and monitor job progress.
3. Download invoices and chat with assigned teams.

### Manager Toolkit

- View requests with search/pagination filters.
- Adjust quote pricing, send quotes with email notifications.
- Assign translators, set due dates/notes, accept/return deliverables.
- Maintain client glossaries and review audit logs.
- Issue PDF invoices from delivered jobs.

### Translator Workspace

- Dashboard summarising assignments and due dates.
- Job detail page with glossary highlighting and QA warnings when numbers mismatch.
- Upload deliverables and collaborate via chat (WebSocket or 5s polling fallback).

## Directory Overview

```
app/
├── main.py
├── database.py
├── models.py
├── security.py
├── dependencies.py
├── services/
│   ├── audit.py
│   ├── emails.py
│   ├── files.py
│   ├── invoices.py
│   └── jobs.py
├── routers/
│   ├── __init__.py
│   ├── auth.py
│   ├── client.py
│   ├── jobs.py
│   ├── manager.py
│   └── translator.py
├── template_loader.py
├── utils/
│   └── flash.py
├── templates/
│   ├── emails/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── client_*.html
│   ├── manager_*.html
│   ├── translator_*.html
│   └── job_detail.html
└── static/
    └── css/
        └── styles.css
uploads/
├── deliverables/
└── invoices/
```

## Notes

- Uploaded files and generated PDFs live under `uploads/` – ensure the process has write access.
- Chat requires session cookies; WebSocket connections reuse the browser session.
- Quote rates can be extended by inserting rows in the `rates` table.

Enjoy managing your translation office!
