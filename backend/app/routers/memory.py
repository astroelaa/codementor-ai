"""Inspectable learning memory: weak spots + misconception records.

Everything here is derived from stored rows (see services.memory). Users can
read their memory and delete individual misconception records. Deleting a
record removes it from future recaps; cumulative skill counters are left
untouched (documented behavior, not silent rewriting).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.models import Misconception, User
from app.schemas import MemoryMisconception, MemoryResponse, WeakSpot

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=MemoryResponse)
def read_memory(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    spots = (
        db.query(Misconception.type, func.count(Misconception.id))
        .filter(Misconception.user_id == user.id)
        .group_by(Misconception.type)
        .order_by(func.count(Misconception.id).desc())
        .limit(10)
        .all()
    )
    records = (
        db.query(Misconception)
        .filter(Misconception.user_id == user.id)
        .order_by(Misconception.created_at.desc())
        .limit(20)
        .all()
    )
    return MemoryResponse(
        weak_spots=[WeakSpot(type=t, count=c) for t, c in spots],
        misconceptions=[
            MemoryMisconception(
                id=m.id,
                type=m.type,
                description=m.description,
                session_id=m.session_id,
                created_at=m.created_at,
            )
            for m in records
        ],
    )


@router.delete("/misconceptions/{record_id}")
def delete_misconception(
    record_id: str,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
) -> dict:
    record = (
        db.query(Misconception)
        .filter(Misconception.id == record_id, Misconception.user_id == user.id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    db.delete(record)
    db.commit()
    return {"deleted": record_id}
