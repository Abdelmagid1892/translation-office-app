from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from .. import models

INVOICE_DIR = Path("uploads/invoices")
INVOICE_DIR.mkdir(parents=True, exist_ok=True)


def _next_invoice_number(db: Session) -> int:
    last_invoice = db.query(models.Invoice).order_by(models.Invoice.id.desc()).first()
    return (last_invoice.id if last_invoice else 0) + 1


def generate_invoice_pdf(db: Session, invoice: models.Invoice) -> Path:
    number = _next_invoice_number(db)
    filename = f"invoice_{invoice.id or number}.pdf"
    filepath = INVOICE_DIR / filename
    c = canvas.Canvas(str(filepath), pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(30 * mm, height - 30 * mm, "Translation Office")
    c.setFont("Helvetica", 12)
    c.drawString(30 * mm, height - 40 * mm, f"Invoice #{number:04d}")
    c.drawString(30 * mm, height - 50 * mm, f"Client: {invoice.client.username}")
    job = invoice.job
    c.drawString(30 * mm, height - 60 * mm, f"Job ID: {job.id}")
    c.drawString(30 * mm, height - 70 * mm, f"Languages: {job.request.source_language} -> {job.request.target_language}")
    c.drawString(30 * mm, height - 80 * mm, f"Word count: {job.request.word_count}")
    c.drawString(30 * mm, height - 100 * mm, f"Amount: {invoice.amount:.2f} {invoice.currency}")
    c.drawString(30 * mm, height - 120 * mm, f"Issued: {datetime.utcnow().date().isoformat()}")
    c.showPage()
    c.save()
    invoice.pdf_path = str(filepath.relative_to(Path("uploads")))
    invoice.status = "Issued"
    invoice.issued_at = datetime.utcnow()
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return filepath
