"""Progress routes: dashboard, skills, and learning paths.

Everything here is computed from stored rows — sessions, misconceptions,
badges, activity. Nothing is fabricated. Generated recommendations carry an
explicit source so they cannot be mistaken for measured progress.
"""

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.models import (
    LearningPath,
    Misconception,
    PathItem,
    Session as DebugSession,
    Skill,
    SkillProgress,
    User,
    UserBadge,
)
from app.schemas import (
    BadgeResponse,
    DashboardResponse,
    LanguageStat,
    LearningPathResponse,
    PathItemResponse,
    PathItemUpdate,
    SessionSummary,
    SkillProgressResponse,
    WeakSpot,
)
from app.services.progress import get_streak

router = APIRouter(prefix="/api", tags=["progress"])

WEAK_SPOT_TITLES = {
    "empty-input": (
        "Guard against empty input",
        "Practise checking for empty lists, strings, and arrays before using them.",
    ),
    "zero-division": (
        "Defend every division",
        "Trace each divisor back to its source and handle the zero case first.",
    ),
    "off-by-one": (
        "Master loop boundaries",
        "Work through start/end indexes on paper for three different loops.",
    ),
    "loop-bounds": (
        "Master loop boundaries",
        "Work through start/end indexes on paper for three different loops.",
    ),
    "indexing": (
        "Think in indexes",
        "Practise zero-based indexing until positions feel automatic.",
    ),
    "mutation": (
        "Stop mutating while iterating",
        "Learn safe patterns for transforming collections.",
    ),
    "scope": (
        "Understand scope",
        "Trace where each variable lives and when it is visible.",
    ),
    "types": (
        "Know your types",
        "Practise predicting a value's type before running the code.",
    ),
    "async": (
        "Reason about async code",
        "Learn what runs when in asynchronous programs.",
    ),
}

STARTER_ITEMS = [
    (
        "Read a traceback",
        "Learn to find the failing line and the error type in any traceback.",
    ),
    (
        "Reproduce before fixing",
        "Write the smallest input that triggers the bug, every time.",
    ),
    (
        "Explain your fix aloud",
        "Describe the root cause and the fix in your own words.",
    ),
]


def _weak_spot_counts(db: DbSession, user_id: str, limit: int = 5):
    rows = (
        db.query(Misconception.type, func.count(Misconception.id))
        .filter(Misconception.user_id == user_id)
        .group_by(Misconception.type)
        .order_by(func.count(Misconception.id).desc())
        .limit(limit)
        .all()
    )
    return [(row[0], row[1]) for row in rows]


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    sessions = (
        db.query(DebugSession)
        .filter(DebugSession.user_id == user.id)
        .order_by(DebugSession.updated_at.desc())
        .all()
    )
    total = len(sessions)
    solved = sum(1 for s in sessions if s.status == "solved")
    avg = round(sum(s.understanding_score for s in sessions) / total) if total else 0
    languages = [
        LanguageStat(language=lang, sessions=count)
        for lang, count in sorted(Counter(s.language for s in sessions).items())
    ]
    weak_spots = [
        WeakSpot(type=t, count=c) for t, c in _weak_spot_counts(db, user.id)
    ]
    badges = [
        BadgeResponse.model_validate(ub.badge)
        for ub in db.query(UserBadge)
        .filter(UserBadge.user_id == user.id)
        .order_by(UserBadge.awarded_at.desc())
        .all()
    ]
    recent = [
        SessionSummary(
            id=s.id,
            language=s.language,
            status=s.status,
            understanding_score=s.understanding_score,
            message_count=len(s.messages),
            updated_at=s.updated_at,
        )
        for s in sessions[:5]
    ]
    return DashboardResponse(
        total_sessions=total,
        solved_sessions=solved,
        streak_days=get_streak(db, user.id),
        avg_understanding=avg,
        languages=languages,
        weak_spots=weak_spots,
        badges=badges,
        recent_sessions=recent,
    )


@router.get("/skills", response_model=list[SkillProgressResponse])
def skills(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    rows = (
        db.query(SkillProgress, Skill)
        .join(Skill, Skill.id == SkillProgress.skill_id)
        .filter(SkillProgress.user_id == user.id)
        .order_by(SkillProgress.encounters.desc())
        .all()
    )
    return [
        SkillProgressResponse(
            slug=skill.slug,
            name=skill.name,
            encounters=progress.encounters,
            score=progress.score,
        )
        for progress, skill in rows
    ]


def _build_items(db: DbSession, user_id: str) -> tuple[list[tuple[str, str]], str]:
    spots = _weak_spot_counts(db, user_id, limit=4)
    if not spots:
        return list(STARTER_ITEMS), "starter"
    items: list[tuple[str, str]] = []
    for spot_type, _ in spots:
        template = WEAK_SPOT_TITLES.get(spot_type)
        if template and template[0] not in {t for t, _ in items}:
            items.append(template)
    if not items:
        return list(STARTER_ITEMS), "starter"
    return items, "weak-spots"


def _path_response(path: LearningPath) -> LearningPathResponse:
    return LearningPathResponse(
        id=path.id,
        title=path.title,
        source=path.source,
        is_active=path.is_active,
        created_at=path.created_at,
        items=[PathItemResponse.model_validate(i) for i in path.items],
    )


@router.get("/learning-path", response_model=LearningPathResponse | None)
def get_learning_path(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    path = (
        db.query(LearningPath)
        .filter(LearningPath.user_id == user.id, LearningPath.is_active == True)  # noqa: E712
        .order_by(LearningPath.created_at.desc())
        .first()
    )
    return _path_response(path) if path else None


@router.post("/learning-path/regenerate", response_model=LearningPathResponse)
def regenerate_learning_path(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    db.query(LearningPath).filter(LearningPath.user_id == user.id).update(
        {"is_active": False}
    )
    items, source = _build_items(db, user.id)
    path = LearningPath(
        user_id=user.id,
        title="Your debugging path",
        source=source,
        is_active=True,
    )
    db.add(path)
    db.flush()
    for position, (title, detail) in enumerate(items):
        db.add(
            PathItem(
                path_id=path.id,
                title=title,
                detail=detail,
                status="todo",
                position=position,
            )
        )
    db.commit()
    db.refresh(path)
    return _path_response(path)


@router.patch("/learning-path/items/{item_id}", response_model=PathItemResponse)
def update_path_item(
    item_id: str,
    payload: PathItemUpdate,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    item = (
        db.query(PathItem)
        .join(LearningPath, LearningPath.id == PathItem.path_id)
        .filter(PathItem.id == item_id, LearningPath.user_id == user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Path item not found.")
    item.status = payload.status
    db.commit()
    db.refresh(item)
    return PathItemResponse.model_validate(item)
