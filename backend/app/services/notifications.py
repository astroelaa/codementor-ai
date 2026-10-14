"""In-app notifications: created once per meaningful event, owned per user.

Emission points (all inside the event's own transaction, so HTTP retries
cannot duplicate them): signup → welcome; newly awarded badge → badge;
passing explanation → solve. Password changes notify by email instead.
"""

from sqlalchemy.orm import Session as DbSession

from app.models import Notification

RETENTION_PER_USER = 100


def notify(
    db: DbSession, user_id: str, type: str, title: str, body: str = ""
) -> Notification:
    note = Notification(user_id=user_id, type=type, title=title, body=body)
    db.add(note)
    db.flush()
    # Retention: keep the newest N per user, drop the rest.
    old_ids = [
        row[0]
        for row in db.query(Notification.id)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(RETENTION_PER_USER)
        .all()
    ]
    if old_ids:
        db.query(Notification).filter(Notification.id.in_(old_ids)).delete(
            synchronize_session=False
        )
    return note


def unread_count(db: DbSession, user_id: str) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read == False)  # noqa: E712
        .count()
    )
