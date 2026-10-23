"""Database engine and session factory.

SQLite is used for local development, PostgreSQL (via DATABASE_URL) in
production. SQLAlchemy 2 style, synchronous engine.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool


class Base(DeclarativeBase):
    pass


def normalize_database_url(database_url: str) -> str:
    """Pin PostgreSQL URLs to the psycopg2 driver we actually install.

    Newer SQLAlchemy releases may default bare ``postgresql://`` to psycopg v3,
    which is not in requirements.txt. Explicit driver URLs are left untouched.
    """
    for prefix in ("postgresql://", "postgres://"):
        if database_url.startswith(prefix):
            return "postgresql+psycopg2://" + database_url[len(prefix):]
    return database_url


def build_engine(database_url: str):
    database_url = normalize_database_url(database_url)
    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url:
            kwargs["poolclass"] = StaticPool
    else:
        # Serverless-safe: no persistent pool. Each checkout opens a fresh
        # connection (use the Supabase session-pooler endpoint) instead of
        # holding idle connections across frozen function instances.
        kwargs["poolclass"] = NullPool
    return create_engine(database_url, **kwargs)


def build_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
