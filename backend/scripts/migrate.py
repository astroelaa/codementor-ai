"""Run pending Alembic migrations once, guarded.

Intended for the Vercel build step (where DATABASE_URL is available without
being exposed). Beats a bare `alembic upgrade head` in two ways:
- no-op when the database already sits at head (safe in every re-deploy);
- a failed migration fails the build, so production never serves code the
  schema cannot support.

Note: alembic's command.current()/heads() only PRINT, they return None, so
the comparison is done with ScriptDirectory + MigrationContext directly.
"""

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.database import normalize_database_url


def main() -> None:
    cfg = Config("alembic.ini")
    script_directory = ScriptDirectory.from_config(cfg)
    head_set = set(script_directory.get_heads())

    url = normalize_database_url(
        os.environ.get("DATABASE_URL") or get_settings().database_url
    )
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_set = set(context.get_current_heads())

    if current_set == head_set:
        print("migrate: database already at head; nothing to do.")
        return
    print(f"migrate: upgrading from {sorted(current_set)} to {sorted(head_set)}")
    command_upgrade(cfg)
    with engine.connect() as connection:
        after = set(MigrationContext.configure(connection).get_current_heads())
    if after != head_set:
        raise SystemExit(f"migrate: FAILED - database still not at head ({after})")
    print("migrate: done. schema is up to date.")


def command_upgrade(cfg: Config) -> None:
    from alembic import command

    command.upgrade(cfg, "head")


if __name__ == "__main__":
    main()
