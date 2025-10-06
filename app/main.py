import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import models
from .database import Base, engine, get_db
from .dependencies import (
    ROLE_CLIENT,
    ROLE_MANAGER,
    ROLE_TRANSLATOR,
    ROLE_ADMIN,
    get_current_user,
)
from .routers import auth, client, jobs, manager, translator
from .security import get_password_hash

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
(UPLOAD_DIR / "deliverables").mkdir(exist_ok=True)
(UPLOAD_DIR / "invoices").mkdir(exist_ok=True)

app = FastAPI(title="Translation Office App")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "supersecretkey"))

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploaded_files")

app.include_router(auth.router)
app.include_router(client.router)
app.include_router(manager.router)
app.include_router(translator.router)
app.include_router(jobs.router)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    create_defaults()


@app.get("/")
def home(request: Request, user: Optional[models.User] = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.role == ROLE_CLIENT:
        return RedirectResponse(url="/client/dashboard", status_code=302)
    if user.role == ROLE_MANAGER or user.role == ROLE_ADMIN:
        return RedirectResponse(url="/manager/dashboard", status_code=302)
    if user.role == ROLE_TRANSLATOR:
        return RedirectResponse(url="/translator/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


def create_defaults() -> None:
    db: Session = next(get_db())
    try:
        default_users = [
            ("manager1@example.com", ROLE_MANAGER, "managerpass"),
            ("translator1@example.com", ROLE_TRANSLATOR, "translatorpass"),
            ("translator2@example.com", ROLE_TRANSLATOR, "translatorpass"),
            ("admin@example.com", ROLE_ADMIN, "adminpass"),
        ]
        for username, role, password in default_users:
            existing = db.query(models.User).filter(models.User.username == username).first()
            if not existing:
                db.add(
                    models.User(
                        username=username,
                        role=role,
                        password_hash=get_password_hash(password),
                    )
                )
        default_rates = [
            ("EN", "IT", 0.10),
            ("IT", "EN", 0.10),
        ]
        for source, target, price in default_rates:
            rate = (
                db.query(models.Rate)
                .filter(models.Rate.source_language == source, models.Rate.target_language == target)
                .first()
            )
            if not rate:
                db.add(models.Rate(source_language=source, target_language=target, unit_price=price))
        db.commit()
    finally:
        db.close()
