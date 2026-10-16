from app.database import normalize_database_url


def test_bare_postgresql_pinned_to_psycopg2():
    assert normalize_database_url("postgresql://u:p@h/db?sslmode=require") == "postgresql+psycopg2://u:p@h/db?sslmode=require"


def test_postgres_alias_pinned_to_psycopg2():
    assert normalize_database_url("postgres://u:p@h/db").startswith("postgresql+psycopg2://")


def test_explicit_driver_and_sqlite_untouched():
    assert normalize_database_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_database_url("sqlite:///./x.db") == "sqlite:///./x.db"
