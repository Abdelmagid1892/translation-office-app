from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


def log_action(
    db: Session,
    user: Optional[models.User],
    action: str,
    object_type: str,
    object_id: Optional[int] = None,
) -> None:
    log = models.AuditLog(
        user_id=user.id if user else None,
        action=action,
        object_type=object_type,
        object_id=object_id,
        created_at=datetime.utcnow(),
    )
    db.add(log)
    db.commit()
