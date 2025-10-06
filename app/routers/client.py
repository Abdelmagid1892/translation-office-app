from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..dependencies import ROLE_CLIENT, ROLE_MANAGER, require_role
from ..services import jobs as job_service
from ..services.audit import log_action
from ..services.emails import send_email
from ..services.files import count_words, extract_text_from_file
from ..services.quotes import create_or_update_quote, mark_quote_status
from ..template_loader import templates
from ..utils.flash import pop_flash, set_flash

router = APIRouter()
BASE_UPLOAD_DIR = Path("uploads")
BASE_UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/client/dashboard")
def dashboard(
    request: Request,
    user: models.User = Depends(require_role(ROLE_CLIENT)),
    db: Session = Depends(get_db),
):
    translation_requests = (
        db.query(models.TranslationRequest)
        .filter(models.TranslationRequest.client_id == user.id)
        .order_by(models.TranslationRequest.created_at.desc())
        .all()
    )
    pending_quotes = sum(1 for req in translation_requests if req.quote and req.quote.status == "Sent")
    delivered_jobs = sum(1 for req in translation_requests if req.job and req.job.status == "Delivered")
    invoices = (
        db.query(models.Invoice)
        .join(models.Job)
        .join(models.TranslationRequest)
        .filter(models.TranslationRequest.client_id == user.id)
        .order_by(models.Invoice.issued_at.desc().nullslast(), models.Invoice.id.desc())
        .all()
    )
    flash = pop_flash(request)
    return templates.TemplateResponse(
        "client_dashboard.html",
        {
            "request": request,
            "user": user,
            "translation_requests": translation_requests,
            "pending_quotes": pending_quotes,
            "delivered_jobs": delivered_jobs,
            "invoices": invoices,
            "flash": flash,
        },
    )


@router.get("/client/request")
def request_form(request: Request, user: models.User = Depends(require_role(ROLE_CLIENT))):
    return templates.TemplateResponse(
        "client_request.html", {"request": request, "user": user, "error": None}
    )


@router.post("/client/request")
def create_request(
    request: Request,
    source_language: str = Form(...),
    target_language: str = Form(...),
    file: UploadFile = File(...),
    user: models.User = Depends(require_role(ROLE_CLIENT)),
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

    filename = f"client_{user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    filepath = BASE_UPLOAD_DIR / filename
    with filepath.open("wb") as f:
        contents = file.file.read()
        f.write(contents)
    file.file.close()

    translation_request = models.TranslationRequest(
        client_id=user.id,
        source_language=source_language,
        target_language=target_language,
        status="New",
        original_filename=filename,
        created_at=datetime.utcnow(),
    )
    db.add(translation_request)
    db.commit()
    db.refresh(translation_request)

    text, _ = extract_text_from_file(filepath)
    translation_request.source_text = text
    translation_request.word_count = count_words(text)
    db.add(translation_request)
    db.commit()
    create_or_update_quote(db, translation_request, translation_request.word_count)
    log_action(db, user, "upload_request", "translation_request", translation_request.id)
    set_flash(request, "Request received. Quote generated.")
    return RedirectResponse(url="/client/dashboard", status_code=302)


@router.get("/client/quotes/{quote_id}")
def view_quote(
    request: Request,
    quote_id: int,
    user: models.User = Depends(require_role(ROLE_CLIENT)),
    db: Session = Depends(get_db),
):
    quote = db.get(models.Quote, quote_id)
    if not quote or quote.request.client_id != user.id:
        raise HTTPException(status_code=404, detail="Quote not found")
    flash = pop_flash(request)
    return templates.TemplateResponse(
        "client_quote.html",
        {"request": request, "user": user, "quote": quote, "flash": flash},
    )


@router.post("/client/quotes/{quote_id}/approve")
def approve_quote(
    quote_id: int,
    user: models.User = Depends(require_role(ROLE_CLIENT)),
    db: Session = Depends(get_db),
):
    quote = db.get(models.Quote, quote_id)
    if not quote or quote.request.client_id != user.id:
        raise HTTPException(status_code=404, detail="Quote not found")
    mark_quote_status(db, quote, "Approved")
    job = job_service.ensure_job_for_request(db, quote.request)
    job.status = "New"
    db.add(job)
    db.commit()
    manager_recipients = [m.username for m in db.query(models.User).filter(models.User.role == ROLE_MANAGER).all()]
    recipients = manager_recipients + [quote.request.client.username]
    send_email(
        subject="Quote Approved",
        recipients=recipients,
        template_name="quote_approved.html",
        context={"quote": quote},
    )
    log_action(db, user, "quote_approved", "quote", quote.id)
    set_flash(request, "Quote approved. Our team will start processing your job shortly.")
    return RedirectResponse(url=f"/client/quotes/{quote_id}", status_code=302)


@router.post("/client/quotes/{quote_id}/reject")
def reject_quote(
    quote_id: int,
    user: models.User = Depends(require_role(ROLE_CLIENT)),
    db: Session = Depends(get_db),
):
    quote = db.get(models.Quote, quote_id)
    if not quote or quote.request.client_id != user.id:
        raise HTTPException(status_code=404, detail="Quote not found")
    mark_quote_status(db, quote, "Rejected")
    log_action(db, user, "quote_rejected", "quote", quote.id)
    set_flash(request, "Quote rejected.", "warning")
    return RedirectResponse(url=f"/client/quotes/{quote_id}", status_code=302)


@router.get("/client/invoices")
def list_invoices(
    request: Request,
    user: models.User = Depends(require_role(ROLE_CLIENT)),
    db: Session = Depends(get_db),
):
    invoices = (
        db.query(models.Invoice)
        .join(models.Job)
        .join(models.TranslationRequest)
        .filter(models.TranslationRequest.client_id == user.id)
        .order_by(models.Invoice.issued_at.desc().nullslast())
        .all()
    )
    return templates.TemplateResponse(
        "client_invoices.html",
        {"request": request, "user": user, "invoices": invoices},
    )


@router.get("/client/invoices/{invoice_id}/download")
def download_invoice(
    invoice_id: int,
    user: models.User = Depends(require_role(ROLE_CLIENT)),
    db: Session = Depends(get_db),
):
    invoice = db.get(models.Invoice, invoice_id)
    if not invoice or invoice.job.request.client_id != user.id or not invoice.pdf_path:
        raise HTTPException(status_code=404, detail="Invoice not found")
    filepath = Path("uploads") / invoice.pdf_path
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Invoice file missing")
    return FileResponse(filepath, media_type="application/pdf", filename=filepath.name)
