"""Operational tests: production validation and readiness checks."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_DB_URL


def _prod_settings(**overrides):
    base = {
        "database_url": TEST_DB_URL,
        "environment": "production",
        "supabase_url": "https://project.supabase.co",
        "supabase_service_role_key": "service-role-test-key",
    }
    base.update(overrides)
    return Settings(**base)


def test_production_defaults_rejected():
    with pytest.raises(RuntimeError) as exc_info:
        create_app(
            Settings(
                database_url=TEST_DB_URL,
                environment="production",
                supabase_url="",
                supabase_service_role_key="",
            )
        )
    message = str(exc_info.value)
    assert "SUPABASE_URL" in message
    assert "SUPABASE_SERVICE_ROLE_KEY" in message


def test_production_sqlite_rejected():
    with pytest.raises(RuntimeError) as exc_info:
        create_app(_prod_settings())
    assert "PostgreSQL" in str(exc_info.value)


def test_production_missing_service_key_rejected():
    with pytest.raises(RuntimeError) as exc_info:
        create_app(_prod_settings(supabase_service_role_key=""))
    assert "SUPABASE_SERVICE_ROLE_KEY" in str(exc_info.value)


def test_production_valid_config_starts():
    app = create_app(
        _prod_settings(database_url="postgresql+psycopg2://u:p@h/db")
    )
    assert app.state.settings.is_production


def test_ready_ok_with_database():
    from tests.conftest import client

    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["database"] == "ok"


def test_ready_reports_unreachable_database():
    app = create_app(Settings(database_url="sqlite:////nonexistent-dir-xyz/test.db"))
    c = TestClient(app)
    r = c.get("/ready")
    assert r.status_code == 503
    assert r.json()["database"] == "unreachable"


def test_request_id_header_present_and_echoed():
    from tests.conftest import client

    r = client.get("/health")
    assert r.status_code == 200
    assert len(r.headers.get("X-Request-ID", "")) >= 8

    r = client.get("/health", headers={"X-Request-ID": "test-123"})
    assert r.headers.get("X-Request-ID") == "test-123"


def test_default_origins_include_hosted_frontend():
    origins = Settings().origins
    assert "https://astroelaa.github.io" in origins


def test_engine_pooling_sqlite_and_serverless():
    from sqlalchemy.pool import NullPool, QueuePool, StaticPool

    from app.database import build_engine

    mem = build_engine("sqlite:///:memory:")
    assert isinstance(mem.pool, StaticPool)
    file_db = build_engine("sqlite:///./codementor.db")
    assert isinstance(file_db.pool, QueuePool)
    pg = build_engine("postgresql+psycopg2://u:p@h/db")
    assert isinstance(pg.pool, NullPool)
    for e in (mem, file_db, pg):
        e.dispose()
