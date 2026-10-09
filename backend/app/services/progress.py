"""Progress tracking: activity, streaks, badges and skills.

Badges and skills are reference data seeded by the initial migration (and by
ensure_reference_data for setups that create tables directly).
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session as DbSession

from app.models import (
    Badge,
    DailyActivity,
    Misconception,
    Session as DebugSession,
    Skill,
    SkillProgress,
    User,
    UserBadge,
)

BADGE_DEFS = [
    {
        "slug": "first-session",
        "name": "First Session",
        "description": "Started your first debugging session.",
        "icon": "flag",
    },
    {
        "slug": "first-solve",
        "name": "First Solve",
        "description": "Explained your first fix in your own words.",
        "icon": "check",
    },
    {
        "slug": "hint-free-solve",
        "name": "No Hints Needed",
        "description": "Solved a session without spending a single hint.",
        "icon": "lightbulb",
    },
    {
        "slug": "streak-3",
        "name": "Three-Day Streak",
        "description": "Practised three days in a row.",
        "icon": "flame",
    },
    {
        "slug": "polyglot",
        "name": "Polyglot",
        "description": "Debugged in more than one language.",
        "icon": "languages",
    },
    {
        "slug": "scholar-5",
        "name": "Scholar",
        "description": "Solved five debugging sessions.",
        "icon": "graduation-cap",
    },
]

SKILL_DEFS = [
    {
        "slug": "edge-cases",
        "name": "Edge Cases",
        "description": "Empty inputs, boundaries and unusual values.",
    },
    {
        "slug": "loop-logic",
        "name": "Loop Logic",
        "description": "Bounds, indexes and off-by-one reasoning.",
    },
    {
        "slug": "error-handling",
        "name": "Error Handling",
        "description": "Crashes, exceptions and defensive checks.",
    },
    {
        "slug": "testing-habits",
        "name": "Testing Habits",
        "description": "Reproducing bugs and verifying fixes.",
    },
    {
        "slug": "reading-code",
        "name": "Reading Code",
        "description": "Tracing execution and naming what code really does.",
    },
    {
        "slug": "debugging-workflow",
        "name": "Debugging Workflow",
        "description": "A systematic approach to finding root causes.",
    },
]

MISCONCEPTION_TO_SKILL = {
    "empty-input": "edge-cases",
    "zero-division": "error-handling",
    "off-by-one": "loop-logic",
    "loop-bounds": "loop-logic",
    "indexing": "loop-logic",
    "mutation": "testing-habits",
    "scope": "reading-code",
    "types": "reading-code",
    "async": "error-handling",
}


def ensure_reference_data(db: DbSession) -> None:
    for definition in BADGE_DEFS:
        exists = db.query(Badge).filter(Badge.slug == definition["slug"]).first()
        if exists is None:
            db.add(Badge(**definition))
    for definition in SKILL_DEFS:
        exists = db.query(Skill).filter(Skill.slug == definition["slug"]).first()
        if exists is None:
            db.add(Skill(**definition))
    db.commit()


def record_activity(
    db: DbSession, user_id: str, *, sessions: int = 0, messages: int = 0
) -> None:
    today = date.today()
    row = (
        db.query(DailyActivity)
        .filter(DailyActivity.user_id == user_id, DailyActivity.day == today)
        .first()
    )
    if row is None:
        row = DailyActivity(
            user_id=user_id, day=today, sessions_count=0, messages_count=0
        )
        db.add(row)
    row.sessions_count += sessions
    row.messages_count += messages
    db.commit()


def get_streak(db: DbSession, user_id: str) -> int:
    days = {
        row.day
        for row in db.query(DailyActivity.day)
        .filter(DailyActivity.user_id == user_id)
        .all()
    }
    if not days:
        return 0
    cursor = date.today()
    if cursor not in days:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def award_badge(db: DbSession, user_id: str, slug: str) -> Badge | None:
    badge = db.query(Badge).filter(Badge.slug == slug).first()
    if badge is None:
        return None
    exists = (
        db.query(UserBadge)
        .filter(UserBadge.user_id == user_id, UserBadge.badge_id == badge.id)
        .first()
    )
    if exists is not None:
        return None
    db.add(UserBadge(user_id=user_id, badge_id=badge.id))
    db.commit()
    return badge


def bump_skill(
    db: DbSession, user_id: str, misconception_type: str, *, solved: bool = False
) -> None:
    slug = MISCONCEPTION_TO_SKILL.get(misconception_type, "debugging-workflow")
    skill = db.query(Skill).filter(Skill.slug == slug).first()
    if skill is None:
        return
    progress = (
        db.query(SkillProgress)
        .filter(
            SkillProgress.user_id == user_id, SkillProgress.skill_id == skill.id
        )
        .first()
    )
    if progress is None:
        progress = SkillProgress(
            user_id=user_id, skill_id=skill.id, encounters=0, score=0
        )
        db.add(progress)
    progress.encounters += 1
    if solved:
        progress.score = min(100, progress.score + 10)
    db.commit()


def count_solved(db: DbSession, user_id: str) -> int:
    return (
        db.query(DebugSession)
        .filter(
            DebugSession.user_id == user_id, DebugSession.status == "solved"
        )
        .count()
    )


def award_on_solve(
    db: DbSession, user: User, session: DebugSession
) -> list[Badge]:
    earned: list[Badge] = []
    badge = award_badge(db, user.id, "first-solve")
    if badge:
        earned.append(badge)
    if session.hints_used == 0:
        badge = award_badge(db, user.id, "hint-free-solve")
        if badge:
            earned.append(badge)
    if count_solved(db, user.id) >= 5:
        badge = award_badge(db, user.id, "scholar-5")
        if badge:
            earned.append(badge)
    if get_streak(db, user.id) >= 3:
        badge = award_badge(db, user.id, "streak-3")
        if badge:
            earned.append(badge)
    languages = {
        row.language
        for row in db.query(DebugSession.language)
        .filter(DebugSession.user_id == user.id)
        .all()
    }
    if len(languages) >= 2:
        badge = award_badge(db, user.id, "polyglot")
        if badge:
            earned.append(badge)
    for misconception in (
        db.query(Misconception)
        .filter(Misconception.session_id == session.id)
        .all()
    ):
        bump_skill(db, user.id, misconception.type, solved=True)
    return earned
