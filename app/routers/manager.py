from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..dependencies import ROLE_ADMIN, ROLE_MANAGER, require_roles
from ..services import jobs as job_service
from ..services.audit import log_action
from ..services.emails import send_email
from ..services.invoices import generate_invoice_pdf
from ..services.quotes import create_or_update_quote, mark_quote_status
from ..template_loader import templates
from ..utils.flash import pop_flash, set_flash

router = APIRouter()


def _get_pagination(page: int, page_size: int = 10) -> tuple[int, int]:
    offset = max(page - 1, 0) * page_size
    return offset, page_size


@router.get("/manager/dashboard")
def dashboard(
    request: Request,
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
):
    query = (
        db.query(models.TranslationRequest)
        .join(models.User, models.TranslationRequest.client_id == models.User.id)
        .order_by(models.TranslationRequest.created_at.desc())
    )
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.User.username.ilike(pattern),
                models.TranslationRequest.source_language.ilike(pattern),
                models.TranslationRequest.target_language.ilike(pattern),
            )
        )
    total_requests = query.count()
    offset, limit = _get_pagination(page)
    translation_requests = query.offset(offset).limit(limit).all()

    quotes = db.query(models.Quote).order_by(models.Quote.created_at.desc()).limit(10).all()
    jobs = db.query(models.Job).order_by(models.Job.id.desc()).limit(10).all()
    recent_logs = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(20).all()

    pending_quotes = db.query(models.Quote).filter(models.Quote.status == "Sent").count()
    open_jobs = db.query(models.Job).filter(models.Job.status.in_(["New", "Assigned", "InProgress"])).count()
    invoices_count = db.query(models.Invoice).count()

    translators = db.query(models.User).filter(models.User.role == "translator").all()

    flash = pop_flash(request)
    return templates.TemplateResponse(
        "manager_dashboard.html",
        {
            "request": request,
            "user": user,
            "translation_requests": translation_requests,
            "quotes": quotes,
            "jobs": jobs,
            "recent_logs": recent_logs,
            "pending_quotes": pending_quotes,
            "open_jobs": open_jobs,
            "invoices_count": invoices_count,
            "translators": translators,
            "page": page,
            "page_size": 10,
            "total_requests": total_requests,
            "search": search or "",
            "flash": flash,
        },
    )


@router.post("/manager/quotes/{quote_id}/update")
def update_quote(
    quote_id: int,
    request: Request,
    unit_price: float = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
):
    quote = db.get(models.Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    create_or_update_quote(db, quote.request, quote.word_count, unit_price=unit_price)
    log_action(db, user, "quote_updated", "quote", quote.id)
    set_flash(request, "Quote updated.")
    return RedirectResponse(url="/manager/dashboard", status_code=302)


@router.post("/manager/quotes/{quote_id}/send")
def send_quote(
    quote_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
):
    quote = db.get(models.Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    mark_quote_status(db, quote, "Sent")
    quote.request.status = "Quoted"
    db.add(quote.request)
    db.commit()
    client = quote.request.client
    send_email(
        subject="New Quote Available",
        recipients=[client.username],
        template_name="quote_sent.html",
        context={"quote": quote},
    )
    log_action(db, user, "quote_sent", "quote", quote.id)
    set_flash(request, "Quote sent to client.")
    return RedirectResponse(url="/manager/dashboard", status_code=302)


@router.post("/manager/jobs/{job_id}/assign")
def assign_job(
    job_id: int,
    request: Request,
    translator_id: Optional[int] = Form(None),
    due_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    translator = db.get(models.User, translator_id) if translator_id else None
    parsed_due_date = None
    if due_date:
        try:
            parsed_due_date = datetime.fromisoformat(due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due date format")
    try:
        job_service.assign_translator(db, job, translator, parsed_due_date, notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    job.manager_comment = None
    db.add(job)
    db.commit()
    log_action(db, user, "job_assigned", "job", job.id)
    if translator:
        send_email(
            subject="New Job Assigned",
            recipients=[translator.username],
            template_name="job_assigned.html",
            context={"job": job},
        )
    set_flash(request, "Job assignment saved.")
    return RedirectResponse(url="/manager/dashboard", status_code=302)


@router.post("/manager/jobs/{job_id}/accept")
def accept_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.manager_comment = None
    job_service.update_job_status(db, job, "Accepted")
    log_action(db, user, "job_accepted", "job", job.id)
    set_flash(request, "Job accepted.")
    return RedirectResponse(url="/manager/dashboard", status_code=302)


@router.post("/manager/jobs/{job_id}/return")
def return_job(
    job_id: int,
    request: Request,
    comment: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.manager_comment = comment
    job_service.update_job_status(db, job, "Assigned")
    log_action(db, user, "job_returned", "job", job.id)
    set_flash(request, "Job returned to translator.", "warning")
    return RedirectResponse(url="/manager/dashboard", status_code=302)


@router.post("/manager/jobs/{job_id}/invoice")
def generate_invoice(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
):
    job = db.get(models.Job, job_id)
    if not job or job.status not in {"Delivered", "Accepted"}:
        raise HTTPException(status_code=400, detail="Job not ready for invoicing")
    if job.invoice:
        set_flash(request, "Invoice already generated.", "warning")
        return RedirectResponse(url="/manager/dashboard", status_code=302)
    invoice = models.Invoice(
        client_id=job.request.client_id,
        job_id=job.id,
        amount=job.request.quote.total if job.request.quote else 0,
        currency=job.request.quote.currency if job.request.quote else "EUR",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    generate_invoice_pdf(db, invoice)
    log_action(db, user, "invoice_generated", "invoice", invoice.id)
    set_flash(request, "Invoice generated.")
    return RedirectResponse(url="/manager/dashboard", status_code=302)


@router.get("/manager/glossary")
def glossary(
    request: Request,
    client_id: Optional[int] = Query(None),
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    clients = db.query(models.User).filter(models.User.role == "client").all()
    if client_id:
        terms = db.query(models.Term).filter(models.Term.client_id == client_id).all()
    else:
        terms = db.query(models.Term).all()
    flash = pop_flash(request)
    return templates.TemplateResponse(
        "manager_glossary.html",
        {
            "request": request,
            "user": user,
            "clients": clients,
            "terms": terms,
            "client_id": client_id,
            "flash": flash,
        },
    )


@router.post("/manager/glossary")
def add_term(
    request: Request,
    client_id: int = Form(...),
    source_term: str = Form(...),
    target_term: str = Form(...),
    notes: Optional[str] = Form(None),
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    term = models.Term(
        client_id=client_id,
        source_term=source_term.strip(),
        target_term=target_term.strip(),
        notes=notes,
    )
    db.add(term)
    db.commit()
    log_action(db, user, "term_created", "term", term.id)
    set_flash(request, "Term added.")
    return RedirectResponse(url="/manager/glossary", status_code=302)


@router.post("/manager/glossary/{term_id}/delete")
def delete_term(
    request: Request,
    term_id: int,
    user: models.User = Depends(require_roles(ROLE_MANAGER, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    term = db.get(models.Term, term_id)
    if term:
        db.delete(term)
        db.commit()
        log_action(db, user, "term_deleted", "term", term_id)
        set_flash(request, "Term removed.")
    return RedirectResponse(url="/manager/glossary", status_code=302)
