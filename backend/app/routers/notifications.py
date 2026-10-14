"""In-app notifications: list, unread count, mark read. All owner-scoped."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.models import Notification, User
from app.schemas import NotificationResponse
from app.services.notifications import unread_count

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [NotificationResponse.model_validate(r) for r in rows]


@router.get("/unread-count")
def get_unread_count(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
) -> dict:
    return {"count": unread_count(db, user.id)}


@router.patch("/{note_id}/read", response_model=NotificationResponse)
def mark_read(
    note_id: str,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    note = (
        db.query(Notification)
        .filter(Notification.id == note_id, Notification.user_id == user.id)
        .first()
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    note.read = True
    db.commit()
    db.refresh(note)
    return NotificationResponse.model_validate(note)


@router.post("/read-all")
def mark_all_read(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
) -> dict:
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read == False)  # noqa: E712
        .update({"read": True})
    )
    db.commit()
    return {"updated": updated}
