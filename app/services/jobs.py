from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import ROLE_ADMIN, ROLE_CLIENT, ROLE_MANAGER, ROLE_TRANSLATOR
from .files import compare_numbers

DELIVERABLE_DIR = Path("uploads/deliverables")
DELIVERABLE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_job_for_request(db: Session, request: models.TranslationRequest) -> models.Job:
    if request.job:
        return request.job
    job = models.Job(request=request, status="New")
    request.status = "New"
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def assign_translator(
    db: Session,
    job: models.Job,
    translator: Optional[models.User],
    due_date: Optional[datetime],
    notes: Optional[str],
) -> models.Job:
    if translator and translator.role != ROLE_TRANSLATOR:
        raise ValueError("Selected user is not a translator")
    job.translator = translator
    if translator and job.status == "New":
        job.status = "Assigned"
        job.request.status = "Assigned"
    job.due_date = due_date
    job.notes = notes
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_status(db: Session, job: models.Job, status: str) -> models.Job:
    job.status = status
    job.request.status = status
    if status == "Delivered":
        job.delivered_at = datetime.utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def save_deliverable(job: models.Job, upload: UploadFile) -> Path:
    job_dir = DELIVERABLE_DIR / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{upload.filename}"
    destination = job_dir / filename
    with destination.open("wb") as f:
        f.write(upload.file.read())
    upload.file.close()
    job.delivered_filename = str(destination.relative_to(Path("uploads")))
    return destination


def run_quality_checks(source_text: str, target_text: str) -> dict:
    return {
        "numbers_match": compare_numbers(source_text, target_text),
    }


def can_view_job(user: models.User, job: models.Job) -> bool:
    if user.role in {ROLE_MANAGER, ROLE_ADMIN}:
        return True
    if user.role == ROLE_CLIENT and job.request.client_id == user.id:
        return True
    if user.role == ROLE_TRANSLATOR and job.translator_id == user.id:
        return True
    return False
