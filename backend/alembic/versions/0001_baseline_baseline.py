"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-23 15:54:56.307888
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OWNER_TABLES = (
    "users",
    "sessions",
    "misconceptions",
    "skill_progress",
    "learning_paths",
    "projects",
    "user_badges",
    "daily_activity",
    "doc_simplifications",
    "notifications",
)
USER_ID_TABLES = (
    "sessions",
    "misconceptions",
    "skill_progress",
    "learning_paths",
    "projects",
    "user_badges",
    "daily_activity",
    "doc_simplifications",
    "notifications",
)
CHILD_TABLES = ("messages", "hints", "path_items", "milestones", "project_tasks")
REFERENCE_TABLES = ("skills", "badges")
ALL_TABLES = OWNER_TABLES + CHILD_TABLES + REFERENCE_TABLES

CHILD_POLICIES = {
    "messages": (
        "EXISTS (SELECT 1 FROM public.sessions AS s "
        "WHERE s.id = messages.session_id AND s.user_id = auth.uid())"
    ),
    "hints": (
        "EXISTS (SELECT 1 FROM public.sessions AS s "
        "WHERE s.id = hints.session_id AND s.user_id = auth.uid())"
    ),
    "path_items": (
        "EXISTS (SELECT 1 FROM public.learning_paths AS p "
        "WHERE p.id = path_items.path_id AND p.user_id = auth.uid())"
    ),
    "milestones": (
        "EXISTS (SELECT 1 FROM public.projects AS p "
        "WHERE p.id = milestones.project_id AND p.user_id = auth.uid())"
    ),
    "project_tasks": (
        "EXISTS (SELECT 1 FROM public.milestones AS m "
        "JOIN public.projects AS p ON p.id = m.project_id "
        "WHERE m.id = project_tasks.milestone_id AND p.user_id = auth.uid())"
    ),
}

SKILLS = [
    {
        "id": "00000000-0000-0000-0000-000000000101",
        "slug": "edge-cases",
        "name": "Edge Cases",
        "description": "Empty inputs, boundaries and unusual values.",
    },
    {
        "id": "00000000-0000-0000-0000-000000000102",
        "slug": "loop-logic",
        "name": "Loop Logic",
        "description": "Bounds, indexes and off-by-one reasoning.",
    },
    {
        "id": "00000000-0000-0000-0000-000000000103",
        "slug": "error-handling",
        "name": "Error Handling",
        "description": "Crashes, exceptions and defensive checks.",
    },
    {
        "id": "00000000-0000-0000-0000-000000000104",
        "slug": "testing-habits",
        "name": "Testing Habits",
        "description": "Reproducing bugs and verifying fixes.",
    },
    {
        "id": "00000000-0000-0000-0000-000000000105",
        "slug": "reading-code",
        "name": "Reading Code",
        "description": "Tracing execution and naming what code really does.",
    },
    {
        "id": "00000000-0000-0000-0000-000000000106",
        "slug": "debugging-workflow",
        "name": "Debugging Workflow",
        "description": "A systematic approach to finding root causes.",
    },
]

BADGES = [
    {
        "id": "00000000-0000-0000-0000-000000000201",
        "slug": "first-session",
        "name": "First Session",
        "description": "Started your first debugging session.",
        "icon": "flag",
    },
    {
        "id": "00000000-0000-0000-0000-000000000202",
        "slug": "first-solve",
        "name": "First Solve",
        "description": "Explained your first fix in your own words.",
        "icon": "check",
    },
    {
        "id": "00000000-0000-0000-0000-000000000203",
        "slug": "hint-free-solve",
        "name": "No Hints Needed",
        "description": "Solved a session without spending a single hint.",
        "icon": "lightbulb",
    },
    {
        "id": "00000000-0000-0000-0000-000000000204",
        "slug": "streak-3",
        "name": "Three-Day Streak",
        "description": "Practised three days in a row.",
        "icon": "flame",
    },
    {
        "id": "00000000-0000-0000-0000-000000000205",
        "slug": "polyglot",
        "name": "Polyglot",
        "description": "Debugged in more than one language.",
        "icon": "languages",
    },
    {
        "id": "00000000-0000-0000-0000-000000000206",
        "slug": "scholar-5",
        "name": "Scholar",
        "description": "Solved five debugging sessions.",
        "icon": "graduation-cap",
    },
]


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _auth_fk(column: str) -> list:
    if not _is_postgres():
        return []
    return [sa.ForeignKeyConstraint([column], ["auth.users.id"], ondelete="CASCADE")]


def _create_table(name: str, columns: list, constraints: list) -> None:
    op.create_table(name, *columns, *constraints)


def _create_policy(
    name: str,
    table: str,
    action: str,
    using: str | None = None,
    check: str | None = None,
) -> None:
    parts = [
        f"CREATE POLICY {name} ON public.{table}",
        f"FOR {action.upper()}",
        "TO authenticated",
    ]
    if using is not None:
        parts.append(f"USING ({using})")
    if check is not None:
        parts.append(f"WITH CHECK ({check})")
    op.execute(" ".join(parts))


def _seed_reference_data() -> None:
    skills_table = sa.table(
        "skills",
        sa.column("id", sa.Uuid(as_uuid=False)),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
    )
    badges_table = sa.table(
        "badges",
        sa.column("id", sa.Uuid(as_uuid=False)),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("icon", sa.String()),
    )
    op.bulk_insert(skills_table, SKILLS)
    op.bulk_insert(badges_table, BADGES)


def _configure_postgres() -> None:
    for table in USER_ID_TABLES:
        op.alter_column(table, "user_id", server_default=sa.text("auth.uid()"))

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        BEGIN
            INSERT INTO public.users (
                id,
                email,
                display_name,
                theme,
                is_active,
                notify_security_emails,
                notify_progress_emails,
                preferred_language,
                experience_level,
                learning_goal,
                created_at
            )
            VALUES (
                NEW.id,
                NEW.email,
                COALESCE(
                    NEW.raw_user_meta_data ->> 'display_name',
                    NEW.raw_user_meta_data ->> 'full_name',
                    ''
                ),
                'dark',
                true,
                true,
                false,
                '',
                '',
                '',
                COALESCE(NEW.created_at, now())
            )
            ON CONFLICT (id) DO NOTHING;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER on_auth_user_created
        AFTER INSERT ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.handle_new_auth_user();
        """
    )

    for table in ALL_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.alembic_version') IS NOT NULL THEN
                ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
                ALTER TABLE public.alembic_version FORCE ROW LEVEL SECURITY;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated, PUBLIC"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO authenticated")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        + ", ".join(f"public.{table}" for table in OWNER_TABLES + CHILD_TABLES)
        + " TO authenticated"
    )
    op.execute("GRANT SELECT ON public.skills, public.badges TO authenticated")
    op.execute(
        "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO service_role"
    )

    for table in USER_ID_TABLES:
        predicate = "auth.uid() = user_id"
        _create_policy(f"{table}_select_own", table, "select", using=predicate)
        _create_policy(f"{table}_insert_own", table, "insert", check=predicate)
        _create_policy(
            f"{table}_update_own", table, "update", using=predicate, check=predicate
        )
        _create_policy(f"{table}_delete_own", table, "delete", using=predicate)

    predicate = "auth.uid() = id"
    _create_policy("users_select_own", "users", "select", using=predicate)
    _create_policy("users_insert_own", "users", "insert", check=predicate)
    _create_policy("users_update_own", "users", "update", using=predicate, check=predicate)
    _create_policy("users_delete_own", "users", "delete", using=predicate)

    for table in CHILD_TABLES:
        predicate = CHILD_POLICIES[table]
        _create_policy(f"{table}_select_own", table, "select", using=predicate)
        _create_policy(f"{table}_insert_own", table, "insert", check=predicate)
        _create_policy(
            f"{table}_update_own", table, "update", using=predicate, check=predicate
        )
        _create_policy(f"{table}_delete_own", table, "delete", using=predicate)

    _create_policy("skills_select_authenticated", "skills", "select", using="true")
    _create_policy("badges_select_authenticated", "badges", "select", using="true")


def upgrade() -> None:
    _create_table(
        "badges",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("icon", sa.String(length=64), nullable=False),
        ],
        [sa.PrimaryKeyConstraint("id")],
    )
    op.create_index(op.f("ix_badges_slug"), "badges", ["slug"], unique=True)

    _create_table(
        "skills",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
        ],
        [sa.PrimaryKeyConstraint("id")],
    )
    op.create_index(op.f("ix_skills_slug"), "skills", ["slug"], unique=True)

    _create_table(
        "users",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("theme", sa.String(length=20), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("notify_security_emails", sa.Boolean(), nullable=False),
            sa.Column("notify_progress_emails", sa.Boolean(), nullable=False),
            sa.Column("preferred_language", sa.String(length=32), nullable=False),
            sa.Column("experience_level", sa.String(length=20), nullable=False),
            sa.Column("learning_goal", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [sa.PrimaryKeyConstraint("id"), *_auth_fk("id")],
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    _create_table(
        "projects",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("objective", sa.Text(), nullable=False),
            sa.Column("language", sa.String(length=32), nullable=False),
            sa.Column("stack", sa.String(length=200), nullable=False),
            sa.Column("architecture", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [sa.PrimaryKeyConstraint("id"), *_auth_fk("user_id")],
    )
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"], unique=False)

    _create_table(
        "learning_paths",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [sa.PrimaryKeyConstraint("id"), *_auth_fk("user_id")],
    )
    op.create_index(
        op.f("ix_learning_paths_user_id"), "learning_paths", ["user_id"], unique=False
    )

    _create_table(
        "daily_activity",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("day", sa.Date(), nullable=False),
            sa.Column("sessions_count", sa.Integer(), nullable=False),
            sa.Column("messages_count", sa.Integer(), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "day", name="uq_activity_user_day"),
            *_auth_fk("user_id"),
        ],
    )
    op.create_index(
        op.f("ix_daily_activity_day"), "daily_activity", ["day"], unique=False
    )
    op.create_index(
        op.f("ix_daily_activity_user_id"),
        "daily_activity",
        ["user_id"],
        unique=False,
    )

    _create_table(
        "doc_simplifications",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("language", sa.String(length=32), nullable=False),
            sa.Column("input_text", sa.Text(), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("example", sa.Text(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [sa.PrimaryKeyConstraint("id"), *_auth_fk("user_id")],
    )
    op.create_index(
        op.f("ix_doc_simplifications_user_id"),
        "doc_simplifications",
        ["user_id"],
        unique=False,
    )

    _create_table(
        "notifications",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("read", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [sa.PrimaryKeyConstraint("id"), *_auth_fk("user_id")],
    )
    op.create_index(
        op.f("ix_notifications_type"), "notifications", ["type"], unique=False
    )
    op.create_index(
        op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False
    )

    _create_table(
        "sessions",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("language", sa.String(length=32), nullable=False),
            sa.Column("goal", sa.String(length=20), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("project_id", sa.Uuid(as_uuid=False), nullable=True),
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("understanding_score", sa.Integer(), nullable=False),
            sa.Column("hints_used", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("solved_at", sa.DateTime(timezone=True), nullable=True),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
            *_auth_fk("user_id"),
        ],
    )
    op.create_index(
        op.f("ix_sessions_project_id"), "sessions", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    _create_table(
        "skill_progress",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("skill_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("encounters", sa.Integer(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", "skill_id", name="uq_progress_user_skill"),
            *_auth_fk("user_id"),
        ],
    )
    op.create_index(
        op.f("ix_skill_progress_user_id"), "skill_progress", ["user_id"], unique=False
    )

    _create_table(
        "user_badges",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("badge_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["badge_id"], ["badges.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
            *_auth_fk("user_id"),
        ],
    )
    op.create_index(
        op.f("ix_user_badges_user_id"), "user_badges", ["user_id"], unique=False
    )

    _create_table(
        "milestones",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("project_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        ],
    )
    op.create_index(
        op.f("ix_milestones_project_id"), "milestones", ["project_id"], unique=False
    )

    _create_table(
        "path_items",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("path_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["path_id"], ["learning_paths.id"], ondelete="CASCADE"
            ),
        ],
    )
    op.create_index(
        op.f("ix_path_items_path_id"), "path_items", ["path_id"], unique=False
    )

    _create_table(
        "messages",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("session_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("meta", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        ],
    )
    op.create_index(
        op.f("ix_messages_session_id"), "messages", ["session_id"], unique=False
    )

    _create_table(
        "hints",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("session_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        ],
    )
    op.create_index(op.f("ix_hints_session_id"), "hints", ["session_id"], unique=False)

    _create_table(
        "misconceptions",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("session_id", sa.Uuid(as_uuid=False), nullable=True),
            sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
            *_auth_fk("user_id"),
        ],
    )
    op.create_index(
        op.f("ix_misconceptions_session_id"),
        "misconceptions",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_misconceptions_type"), "misconceptions", ["type"], unique=False
    )
    op.create_index(
        op.f("ix_misconceptions_user_id"),
        "misconceptions",
        ["user_id"],
        unique=False,
    )

    _create_table(
        "project_tasks",
        [
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("milestone_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
        ],
        [
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["milestone_id"], ["milestones.id"], ondelete="CASCADE"
            ),
        ],
    )
    op.create_index(
        op.f("ix_project_tasks_milestone_id"),
        "project_tasks",
        ["milestone_id"],
        unique=False,
    )

    _seed_reference_data()

    if _is_postgres():
        _configure_postgres()


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP FUNCTION IF EXISTS public.handle_new_auth_user() CASCADE")
        op.execute(
            """
            DO $$
            BEGIN
                IF to_regclass('public.alembic_version') IS NOT NULL THEN
                    ALTER TABLE public.alembic_version NO FORCE ROW LEVEL SECURITY;
                    ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY;
                END IF;
            END
            $$;
            """
        )

    op.drop_index(op.f("ix_project_tasks_milestone_id"), table_name="project_tasks")
    op.drop_table("project_tasks")
    op.drop_index(op.f("ix_misconceptions_user_id"), table_name="misconceptions")
    op.drop_index(op.f("ix_misconceptions_type"), table_name="misconceptions")
    op.drop_index(op.f("ix_misconceptions_session_id"), table_name="misconceptions")
    op.drop_table("misconceptions")
    op.drop_index(op.f("ix_messages_session_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_hints_session_id"), table_name="hints")
    op.drop_table("hints")
    op.drop_index(op.f("ix_user_badges_user_id"), table_name="user_badges")
    op.drop_table("user_badges")
    op.drop_index(op.f("ix_skill_progress_user_id"), table_name="skill_progress")
    op.drop_table("skill_progress")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_project_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_path_items_path_id"), table_name="path_items")
    op.drop_table("path_items")
    op.drop_index(op.f("ix_milestones_project_id"), table_name="milestones")
    op.drop_table("milestones")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_skills_slug"), table_name="skills")
    op.drop_table("skills")
    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_table("projects")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_type"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_learning_paths_user_id"), table_name="learning_paths")
    op.drop_table("learning_paths")
    op.drop_index(op.f("ix_doc_simplifications_user_id"), table_name="doc_simplifications")
    op.drop_table("doc_simplifications")
    op.drop_index(op.f("ix_daily_activity_user_id"), table_name="daily_activity")
    op.drop_index(op.f("ix_daily_activity_day"), table_name="daily_activity")
    op.drop_table("daily_activity")
    op.drop_index(op.f("ix_badges_slug"), table_name="badges")
    op.drop_table("badges")
