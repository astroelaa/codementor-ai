"""user profile learning preferences

Revision ID: 3a1c9d47b802
Revises: dc55a8dcae7e
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3a1c9d47b802"
down_revision: Union[str, None] = "dc55a8dcae7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add profile-level preference columns with safe defaults.

    Empty string means "not chosen"; no backfill beyond the default is
    needed. Works identically on SQLite (dev) and PostgreSQL (prod).
    """
    op.add_column(
        "users",
        sa.Column("preferred_language", sa.String(length=32), server_default="", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("experience_level", sa.String(length=20), server_default="", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("learning_goal", sa.String(length=32), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "learning_goal")
    op.drop_column("users", "experience_level")
    op.drop_column("users", "preferred_language")
