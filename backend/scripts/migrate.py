"""Run pending Alembic migrations once, guarded.

Intended for the Vercel build step (where DATABASE_URL is available without
being exposed). Beats a bare `alembic upgrade head` in two ways:
- no-op when the database already sits at head (safe in every re-deploy);
- a failed migration fails the build, so production never serves code the
  schema cannot support.
"""

from alembic import command
from alembic.config import Config


def _ids(output: str) -> set:
    """Extract bare revision ids, ignoring "(head)" style annotations."""
    import re

    ids: set = set()
    for line in (output or "").splitlines():
        for token in line.strip().split():
            match = re.match(r"^[0-9a-f]{8,40}$", token)
            if match:
                ids.add(match.group(0))
    return ids


def main() -> None:
    cfg = Config("alembic.ini")
    current = command.current(cfg, verbose=False)
    head = command.heads(cfg, verbose=False)
    current_set = _ids(current)
    head_set = _ids(head)
    if current_set == head_set:
        print("migrate: database already at head; nothing to do.")
        return
    print(f"migrate: upgrading database to {sorted(head_set)}")
    command.upgrade(cfg, "head")
    print("migrate: done.")


if __name__ == "__main__":
    main()
