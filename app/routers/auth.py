from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..dependencies import get_current_user
from ..security import get_password_hash, verify_password
from ..services.audit import log_action
from ..template_loader import templates

router = APIRouter()


@router.get("/login")
def login_form(request: Request, user: Optional[models.User] = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "user": None})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid username or password", "user": None}, status_code=400
        )
    request.session["user_id"] = user.id
    log_action(db, user, "login", "user", user.id)
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    response = RedirectResponse(url="/login", status_code=302)
    return response


@router.get("/register")
def register_form(request: Request, user: Optional[models.User] = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None, "user": None})


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "Username already taken", "user": None}, status_code=400
        )
    user = models.User(username=username, password_hash=get_password_hash(password), role="client")
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    log_action(db, user, "register", "user", user.id)
    return RedirectResponse(url="/client/dashboard", status_code=302)
