"""SQLAlchemy 2 models for CodeMentor AI.

IDs are UUIDs represented as strings in Python so existing string-based
service code keeps working across SQLite and PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

auth_metadata = MetaData()
auth_users = Table(
    "users",
    auth_metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    schema="auth",
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        primary_key=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(120), default="")
    theme: Mapped[str] = mapped_column(String(20), default="dark")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_security_emails: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_progress_emails: Mapped[bool] = mapped_column(Boolean, default=False)
    # Profile-level learning preferences. Empty string = "not chosen yet";
    # allowed values are validated at the API layer.
    preferred_language: Mapped[str] = mapped_column(String(32), default="")
    experience_level: Mapped[str] = mapped_column(String(20), default="")
    learning_goal: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == Session.user_id",
        foreign_keys="Session.user_id",
    )
    misconceptions: Mapped[list["Misconception"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == Misconception.user_id",
        foreign_keys="Misconception.user_id",
    )
    skill_progress: Mapped[list["SkillProgress"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == SkillProgress.user_id",
        foreign_keys="SkillProgress.user_id",
    )
    learning_paths: Mapped[list["LearningPath"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == LearningPath.user_id",
        foreign_keys="LearningPath.user_id",
    )
    badges: Mapped[list["UserBadge"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == UserBadge.user_id",
        foreign_keys="UserBadge.user_id",
    )
    activities: Mapped[list["DailyActivity"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == DailyActivity.user_id",
        foreign_keys="DailyActivity.user_id",
    )
    doc_simplifications: Mapped[list["DocSimplification"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == DocSimplification.user_id",
        foreign_keys="DocSimplification.user_id",
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == Project.user_id",
        foreign_keys="Project.user_id",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        primaryjoin="User.id == Notification.user_id",
        foreign_keys="Notification.user_id",
    )


class Session(Base):
    """One debugging session: a language, a code snippet, a Socratic dialogue."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    language: Mapped[str] = mapped_column(String(32), default="python")
    goal: Mapped[str] = mapped_column(String(20), default="debug")
    mode: Mapped[str] = mapped_column(String(20), default="practice")
    project_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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

    user: Mapped[User] = relationship(
        back_populates="sessions",
        primaryjoin="User.id == Session.user_id",
        foreign_keys="Session.user_id",
    )
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

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
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

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    session: Mapped[Session] = relationship(back_populates="hints")


class Misconception(Base):
    """A classified wrong assumption the student expressed."""

    __tablename__ = "misconceptions"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    session_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    type: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    session: Mapped[Optional[Session]] = relationship(back_populates="misconceptions")
    user: Mapped[User] = relationship(
        back_populates="misconceptions",
        primaryjoin="User.id == Misconception.user_id",
        foreign_keys="Misconception.user_id",
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")


class SkillProgress(Base):
    __tablename__ = "skill_progress"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_progress_user_skill"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    skill_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("skills.id", ondelete="CASCADE")
    )
    encounters: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship(
        back_populates="skill_progress",
        primaryjoin="User.id == SkillProgress.user_id",
        foreign_keys="SkillProgress.user_id",
    )
    skill: Mapped[Skill] = relationship()


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(32), default="weak-spots")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    user: Mapped[User] = relationship(
        back_populates="learning_paths",
        primaryjoin="User.id == LearningPath.user_id",
        foreign_keys="LearningPath.user_id",
    )
    items: Mapped[list["PathItem"]] = relationship(
        back_populates="path",
        cascade="all, delete-orphan",
        order_by="PathItem.position",
    )


class PathItem(Base):
    __tablename__ = "path_items"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    path_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo|doing|done
    position: Mapped[int] = mapped_column(Integer, default=0)

    path: Mapped[LearningPath] = relationship(back_populates="items")


class Project(Base):
    """A user's software project: brief, milestones, and task progress."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    title: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(32), default="python")
    stack: Mapped[str] = mapped_column(String(200), default="")
    architecture: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|done
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship(
        back_populates="projects",
        primaryjoin="User.id == Project.user_id",
        foreign_keys="Project.user_id",
    )
    milestones: Mapped[list["Milestone"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Milestone.position",
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo|doing|done
    position: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship(back_populates="milestones")
    tasks: Mapped[list["ProjectTask"]] = relationship(
        back_populates="milestone",
        cascade="all, delete-orphan",
        order_by="ProjectTask.position",
    )


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    milestone_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("milestones.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo|doing|done
    position: Mapped[int] = mapped_column(Integer, default=0)

    milestone: Mapped[Milestone] = relationship(back_populates="tasks")


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(64), default="award")


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    badge_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("badges.id", ondelete="CASCADE")
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    user: Mapped[User] = relationship(
        back_populates="badges",
        primaryjoin="User.id == UserBadge.user_id",
        foreign_keys="UserBadge.user_id",
    )
    badge: Mapped[Badge] = relationship()


class DailyActivity(Base):
    __tablename__ = "daily_activity"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_activity_user_day"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    day: Mapped[date_type] = mapped_column(Date, index=True)
    sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    messages_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(
        back_populates="activities",
        primaryjoin="User.id == DailyActivity.user_id",
        foreign_keys="DailyActivity.user_id",
    )


class DocSimplification(Base):
    __tablename__ = "doc_simplifications"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    language: Mapped[str] = mapped_column(String(32), default="")
    input_text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    example: Mapped[str] = mapped_column(Text, default="")
    question: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    user: Mapped[User] = relationship(
        back_populates="doc_simplifications",
        primaryjoin="User.id == DocSimplification.user_id",
        foreign_keys="DocSimplification.user_id",
    )


class Notification(Base):
    """Persistent in-app notifications, one recipient each.

    Created once per meaningful event (signup, badge, solve) inside the same
    transaction as the event, so retries cannot duplicate them. Retention is
    capped per user (see services.notifications).
    """

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(auth_users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    user: Mapped[User] = relationship(
        back_populates="notifications",
        primaryjoin="User.id == Notification.user_id",
        foreign_keys="Notification.user_id",
    )
