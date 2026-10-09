"""SQLAlchemy 2 models for CodeMentor AI.

IDs are portable string UUIDs so the same schema runs on SQLite (local dev)
and PostgreSQL (production) without dialect-specific types.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    theme: Mapped[str] = mapped_column(String(20), default="dark")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    misconceptions: Mapped[list["Misconception"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    skill_progress: Mapped[list["SkillProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    learning_paths: Mapped[list["LearningPath"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    badges: Mapped[list["UserBadge"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    activities: Mapped[list["DailyActivity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    doc_simplifications: Mapped[list["DocSimplification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """One debugging session: a language, a code snippet, a Socratic dialogue."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    guest_token: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    language: Mapped[str] = mapped_column(String(32), default="python")
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|solved
    understanding_score: Mapped[int] = mapped_column(Integer, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    solved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[Optional[User]] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    hints: Mapped[list["Hint"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    misconceptions: Mapped[list["Misconception"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    session: Mapped[Session] = relationship(back_populates="messages")


class Hint(Base):
    __tablename__ = "hints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    session: Mapped[Session] = relationship(back_populates="hints")


class Misconception(Base):
    """A classified wrong assumption the student expressed."""

    __tablename__ = "misconceptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sessions.id"), nullable=True, index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    session: Mapped[Optional[Session]] = relationship(back_populates="misconceptions")
    user: Mapped[Optional[User]] = relationship(back_populates="misconceptions")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")


class SkillProgress(Base):
    __tablename__ = "skill_progress"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_progress_user_skill"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True
    )
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey("skills.id"))
    encounters: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship(back_populates="skill_progress")
    skill: Mapped[Skill] = relationship()


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    user: Mapped[User] = relationship(back_populates="learning_paths")
    items: Mapped[list["PathItem"]] = relationship(
        back_populates="path",
        cascade="all, delete-orphan",
        order_by="PathItem.position",
    )


class PathItem(Base):
    __tablename__ = "path_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    path_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_paths.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo|doing|done
    position: Mapped[int] = mapped_column(Integer, default=0)

    path: Mapped[LearningPath] = relationship(back_populates="items")


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(64), default="award")


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True
    )
    badge_id: Mapped[str] = mapped_column(String(36), ForeignKey("badges.id"))
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    user: Mapped[User] = relationship(back_populates="badges")
    badge: Mapped[Badge] = relationship()


class DailyActivity(Base):
    __tablename__ = "daily_activity"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_activity_user_day"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True
    )
    day: Mapped[date_type] = mapped_column(Date, index=True)
    sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    messages_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="activities")


class DocSimplification(Base):
    __tablename__ = "doc_simplifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    language: Mapped[str] = mapped_column(String(32), default="")
    input_text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    example: Mapped[str] = mapped_column(Text, default="")
    question: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    user: Mapped[Optional[User]] = relationship(back_populates="doc_simplifications")
