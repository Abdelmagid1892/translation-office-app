from typing import Iterable, Optional

from fastapi import Depends, HTTPException, Request
from fastapi import status
from sqlalchemy.orm import Session

from . import models
from .database import get_db


ROLE_CLIENT = "client"
ROLE_MANAGER = "manager"
ROLE_TRANSLATOR = "translator"
ROLE_ADMIN = "admin"


ROLE_HIERARCHY = {
    ROLE_CLIENT: {ROLE_CLIENT},
    ROLE_TRANSLATOR: {ROLE_TRANSLATOR},
    ROLE_MANAGER: {ROLE_MANAGER, ROLE_ADMIN},
    ROLE_ADMIN: {ROLE_ADMIN},
}


class UnauthorizedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.get(models.User, user_id)


def login_required(user: Optional[models.User] = Depends(get_current_user)) -> models.User:
    if not user:
        raise UnauthorizedError()
    return user


def require_roles(*roles: Iterable[str]):
    required = set(roles)

    def dependency(user: models.User = Depends(login_required)) -> models.User:
        if user.role not in required:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return dependency


def require_role(role: str):
    return require_roles(role)


def require_job_participant(job_id: int, db: Session, user: models.User) -> models.Job:
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    allowed_user_ids = {
        job.request.client_id,
    }
    if job.translator_id:
        allowed_user_ids.add(job.translator_id)
    # Managers and admins can access all jobs
    if user.role in {ROLE_MANAGER, ROLE_ADMIN}:
        allowed_user_ids.add(user.id)
    if user.id not in allowed_user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this job")
    return job


async def get_websocket_user(websocket, db: Session) -> Optional[models.User]:
    user_id = websocket.scope.get("session", {}).get("user_id")
    if not user_id:
        return None
    return db.get(models.User, user_id)
