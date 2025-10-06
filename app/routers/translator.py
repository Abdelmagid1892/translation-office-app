from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..dependencies import ROLE_MANAGER, ROLE_TRANSLATOR, require_role
from ..services import jobs as job_service
from ..services.audit import log_action
from ..services.emails import send_email
from ..services.jobs import run_quality_checks, save_deliverable
from ..template_loader import templates
from ..utils.flash import pop_flash, set_flash

router = APIRouter()


@router.get("/translator/dashboard")
def dashboard(
    request: Request,
    user: models.User = Depends(require_role(ROLE_TRANSLATOR)),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(models.Job)
        .filter(models.Job.translator_id == user.id)
        .order_by(models.Job.id.desc())
        .all()
    )
    active_jobs = sum(1 for job in jobs if job.status in {"Assigned", "InProgress"})
    delivered_jobs = sum(1 for job in jobs if job.status == "Delivered")
    flash = pop_flash(request)
    return templates.TemplateResponse(
        "translator_dashboard.html",
        {
            "request": request,
            "user": user,
            "jobs": jobs,
            "active_jobs": active_jobs,
            "delivered_jobs": delivered_jobs,
            "flash": flash,
        },
    )


@router.post("/translator/jobs/{job_id}/start")
def start_job(
    job_id: int,
    user: models.User = Depends(require_role(ROLE_TRANSLATOR)),
    db: Session = Depends(get_db),
):
    job = db.get(models.Job, job_id)
    if not job or job.translator_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    job_service.update_job_status(db, job, "InProgress")
    log_action(db, user, "job_started", "job", job.id)
    set_flash(request, "Job marked as In Progress.")
    return RedirectResponse(url="/translator/dashboard", status_code=302)


@router.post("/translator/jobs/{job_id}/deliver")
def deliver_job(
    request: Request,
    job_id: int,
    translated_text: str = Form(""),
    deliverable: Optional[UploadFile] = File(None),
    user: models.User = Depends(require_role(ROLE_TRANSLATOR)),
    db: Session = Depends(get_db),
):
    job = db.get(models.Job, job_id)
    if not job or job.translator_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if not deliverable and not translated_text.strip():
        set_flash(request, "Provide a translation or upload a deliverable.", "warning")
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)
    if deliverable:
        save_deliverable(job, deliverable)
        job.request.translated_filename = job.delivered_filename
    job.translated_text = translated_text
    checks = run_quality_checks(job.request.source_text, translated_text)
    job_service.update_job_status(db, job, "Delivered")
    log_action(db, user, "job_delivered", "job", job.id)
    if not checks.get("numbers_match"):
        set_flash(request, "Warning: numbers differ between source and translation.", "warning")
    else:
        set_flash(request, "Deliverable uploaded successfully.")
    manager_recipients = [m.username for m in db.query(models.User).filter(models.User.role == ROLE_MANAGER).all()]
    recipients = [job.request.client.username] + manager_recipients
    send_email(
        subject="Job Delivered",
        recipients=recipients,
        template_name="job_delivered.html",
        context={"job": job},
    )
    return RedirectResponse(url="/translator/dashboard", status_code=302)
