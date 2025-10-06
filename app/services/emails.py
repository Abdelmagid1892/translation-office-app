import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates" / "emails"


def _create_environment() -> Environment:
    loader = FileSystemLoader(str(TEMPLATE_DIR))
    return Environment(loader=loader, autoescape=select_autoescape(["html", "xml"]))


def _is_configured() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def render_template(name: str, context: Dict[str, Any]) -> str:
    env = _create_environment()
    template = env.get_template(name)
    return template.render(**context)


def send_email(subject: str, recipients: Iterable[str], template_name: str, context: Dict[str, Any]) -> None:
    body = render_template(template_name, context)
    if not _is_configured():
        logging.info("Email (mocked) %s -> %s\n%s", subject, ", ".join(recipients), body)
        return
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_SENDER", username)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body, subtype="html")

    with smtplib.SMTP(host, port) as server:
        if os.getenv("SMTP_STARTTLS", "1") == "1":
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(message)
