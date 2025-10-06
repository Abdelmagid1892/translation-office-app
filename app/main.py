from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import models
from .database import Base, engine, get_db

app = FastAPI(title="Translation Office App")
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploaded_files")

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    create_default_users()


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.get(models.User, user_id)


def login_required(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_role(required_role: str):
    def dependency(user: models.User = Depends(login_required)):
        if user.role != required_role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return dependency


@app.get("/")
def home(request: Request, user: Optional[models.User] = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.role == "client":
        return RedirectResponse(url="/client/dashboard", status_code=302)
    if user.role == "manager":
        return RedirectResponse(url="/manager/dashboard", status_code=302)
    if user.role == "translator":
        return RedirectResponse(url="/translator/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == username).first()
    error = None
    if not user or not verify_password(password, user.password_hash):
        error = "Invalid username or password"
        return templates.TemplateResponse("login.html", {"request": request, "error": error}, status_code=400)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": "Username already taken"}, status_code=400
        )
    user = models.User(username=username, password_hash=get_password_hash(password), role="client")
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/client/dashboard", status_code=302)


@app.get("/client/dashboard")
def client_dashboard(
    request: Request,
    user: models.User = Depends(require_role("client")),
    db: Session = Depends(get_db),
):
    requests = (
        db.query(models.TranslationRequest)
        .filter(models.TranslationRequest.client_id == user.id)
        .order_by(models.TranslationRequest.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "client_dashboard.html",
        {"request": request, "user": user, "translation_requests": requests},
    )


@app.get("/client/request")
def new_request_form(request: Request, user: models.User = Depends(require_role("client"))):
    return templates.TemplateResponse("client_request.html", {"request": request, "user": user, "error": None})


@app.post("/client/request")
def create_request(
    request: Request,
    source_language: str = Form(...),
    target_language: str = Form(...),
    file: UploadFile = File(...),
    user: models.User = Depends(require_role("client")),
    db: Session = Depends(get_db),
):
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
    }
    if file.content_type not in allowed_types:
        return templates.TemplateResponse(
            "client_request.html",
            {
                "request": request,
                "user": user,
                "error": "Unsupported file type. Please upload PDF, DOCX, or TXT.",
            },
            status_code=400,
        )

    filename = f"client_{user.id}_{file.filename}"
    filepath = UPLOAD_DIR / filename
    with open(filepath, "wb") as f:
        contents = file.file.read()
        f.write(contents)
    file.file.close()

    translation_request = models.TranslationRequest(
        client_id=user.id,
        source_language=source_language,
        target_language=target_language,
        status="New",
        original_filename=filename,
    )
    db.add(translation_request)
    db.commit()
    db.refresh(translation_request)
    return RedirectResponse(url="/client/dashboard", status_code=302)


@app.get("/manager/dashboard")
def manager_dashboard(
    request: Request,
    user: models.User = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    translation_requests = (
        db.query(models.TranslationRequest).order_by(models.TranslationRequest.created_at.desc()).all()
    )
    translators = db.query(models.User).filter(models.User.role == "translator").all()
    return templates.TemplateResponse(
        "manager_dashboard.html",
        {
            "request": request,
            "user": user,
            "translation_requests": translation_requests,
            "translators": translators,
        },
    )


@app.post("/manager/jobs/{job_id}/update")
def manager_update_job(
    request: Request,
    job_id: int,
    status: str = Form(...),
    translator_id: Optional[str] = Form(None),
    user: models.User = Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    job = db.get(models.TranslationRequest, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = status
    if translator_id:
        translator = db.get(models.User, int(translator_id))
        if translator and translator.role == "translator":
            job.translator_id = translator.id
        else:
            raise HTTPException(status_code=400, detail="Invalid translator selection")
    else:
        job.translator_id = None
    db.add(job)
    db.commit()
    return RedirectResponse(url="/manager/dashboard", status_code=302)


@app.get("/translator/dashboard")
def translator_dashboard(
    request: Request,
    user: models.User = Depends(require_role("translator")),
    db: Session = Depends(get_db),
):
    translation_requests = (
        db.query(models.TranslationRequest)
        .filter(models.TranslationRequest.translator_id == user.id)
        .order_by(models.TranslationRequest.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "translator_dashboard.html",
        {
            "request": request,
            "user": user,
            "translation_requests": translation_requests,
        },
    )


@app.post("/translator/jobs/{job_id}/upload")
def translator_upload(
    request: Request,
    job_id: int,
    translated_file: UploadFile = File(...),
    user: models.User = Depends(require_role("translator")),
    db: Session = Depends(get_db),
):
    job = db.get(models.TranslationRequest, job_id)
    if not job or job.translator_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    filename = f"translated_{job_id}_{translated_file.filename}"
    filepath = UPLOAD_DIR / filename
    with open(filepath, "wb") as f:
        contents = translated_file.file.read()
        f.write(contents)
    translated_file.file.close()

    job.translated_filename = filename
    job.status = "Delivered"
    db.add(job)
    db.commit()
    return RedirectResponse(url="/translator/dashboard", status_code=302)


def create_default_users():
    from sqlalchemy.orm import Session

    db: Session = next(get_db())
    try:
        default_users = [
            ("manager1", "manager", "managerpass"),
            ("translator1", "translator", "translatorpass"),
            ("translator2", "translator", "translatorpass"),
        ]
        for username, role, password in default_users:
            user = db.query(models.User).filter(models.User.username == username).first()
            if not user:
                new_user = models.User(
                    username=username,
                    role=role,
                    password_hash=get_password_hash(password),
                )
                db.add(new_user)
        db.commit()
    finally:
        db.close()
