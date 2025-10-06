from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal, get_db
from ..dependencies import login_required, require_job_participant
from ..services import jobs as job_service
from ..services.audit import log_action
from ..services.files import sanitize_message
from ..template_loader import templates
from ..utils.flash import pop_flash, set_flash

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, job_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(job_id, []).append(websocket)

    def disconnect(self, job_id: int, websocket: WebSocket) -> None:
        if job_id in self.connections:
            self.connections[job_id] = [conn for conn in self.connections[job_id] if conn != websocket]
            if not self.connections[job_id]:
                self.connections.pop(job_id)

    async def broadcast(self, job_id: int, message: dict) -> None:
        for connection in self.connections.get(job_id, []):
            await connection.send_json(message)


connection_manager = ConnectionManager()


@router.get("/jobs/{job_id}")
def job_detail(
    request: Request,
    job_id: int,
    user: models.User = Depends(login_required),
    db: Session = Depends(get_db),
):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job_service.can_view_job(user, job):
        raise HTTPException(status_code=403, detail="Forbidden")
    messages = (
        db.query(models.Message)
        .filter(models.Message.job_id == job_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    flash = pop_flash(request)
    return templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "user": user,
            "job": job,
            "messages": messages,
            "terms": job.request.terms,
            "flash": flash,
        },
    )


@router.post("/jobs/{job_id}/messages")
async def post_message(
    request: Request,
    job_id: int,
    text: str = Form(...),
    user: models.User = Depends(login_required),
    db: Session = Depends(get_db),
):
    job = require_job_participant(job_id, db, user)
    sanitized = sanitize_message(text)
    if not sanitized:
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"detail": "Message cannot be empty"}, status_code=400)
        set_flash(request, "Cannot send empty message.", "warning")
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)
    message = models.Message(job_id=job_id, user_id=user.id, text=sanitized, created_at=datetime.utcnow())
    db.add(message)
    db.commit()
    db.refresh(message)
    log_action(db, user, "message_posted", "job", job_id)
    payload = {
        "id": message.id,
        "user": message.user.username,
        "text": message.text,
        "created_at": message.created_at.isoformat(),
    }
    await connection_manager.broadcast(job_id, payload)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse(payload)
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)


@router.get("/jobs/{job_id}/messages")
def list_messages(job_id: int, user: models.User = Depends(login_required), db: Session = Depends(get_db)):
    job = require_job_participant(job_id, db, user)
    messages = (
        db.query(models.Message)
        .filter(models.Message.job_id == job_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    payload = [
        {
            "id": msg.id,
            "user": msg.user.username,
            "text": msg.text,
            "created_at": msg.created_at.isoformat(),
        }
        for msg in messages
    ]
    return JSONResponse(payload)


@router.websocket("/ws/jobs/{job_id}")
async def job_ws(websocket: WebSocket, job_id: int):
    await connection_manager.connect(job_id, websocket)
    db = SessionLocal()
    try:
        user_id = websocket.scope.get("session", {}).get("user_id")
        if not user_id:
            await websocket.close(code=1008)
            return
        user = db.get(models.User, user_id)
        job = db.get(models.Job, job_id)
        if not job or user is None:
            await websocket.close(code=1008)
            return
        if not job_service.can_view_job(user, job):
            await websocket.close(code=1008)
            return
        while True:
            data = await websocket.receive_text()
            sanitized = sanitize_message(data)
            if not sanitized:
                continue
            message = models.Message(job_id=job_id, user_id=user.id, text=sanitized, created_at=datetime.utcnow())
            db.add(message)
            db.commit()
            db.refresh(message)
            payload = {
                "id": message.id,
                "user": user.username,
                "text": message.text,
                "created_at": message.created_at.isoformat(),
            }
            await connection_manager.broadcast(job_id, payload)
    except WebSocketDisconnect:
        connection_manager.disconnect(job_id, websocket)
    finally:
        db.close()
