from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


DEFAULT_CURRENCY = "EUR"


def get_rate(db: Session, source_language: str, target_language: str) -> Optional[models.Rate]:
    return (
        db.query(models.Rate)
        .filter(
            models.Rate.source_language == source_language,
            models.Rate.target_language == target_language,
        )
        .first()
    )


def create_or_update_quote(
    db: Session,
    request: models.TranslationRequest,
    word_count: int,
    unit_price: Optional[float] = None,
    currency: str = DEFAULT_CURRENCY,
) -> models.Quote:
    rate = get_rate(db, request.source_language, request.target_language)
    if unit_price is None:
        unit_price = rate.unit_price if rate else 0.1
    total = round(word_count * unit_price, 2)
    if request.quote:
        quote = request.quote
        quote.word_count = word_count
        quote.unit_price = unit_price
        quote.currency = currency
        quote.total = total
    else:
        quote = models.Quote(
            request=request,
            word_count=word_count,
            unit_price=unit_price,
            currency=currency,
            total=total,
            status="Draft",
            created_at=datetime.utcnow(),
        )
        db.add(quote)
    request.word_count = word_count
    db.commit()
    db.refresh(quote)
    return quote


def mark_quote_status(db: Session, quote: models.Quote, status: str) -> models.Quote:
    quote.status = status
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote
