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
        "jwt_secret": "a" * 40,
    }
    base.update(overrides)
    return Settings(**base)


def test_production_defaults_rejected():
    with pytest.raises(RuntimeError) as exc_info:
        create_app(
            Settings(
                database_url=TEST_DB_URL,
                environment="production",
                jwt_secret="development-only-secret-change-me",
            )
        )
    assert "JWT_SECRET" in str(exc_info.value)


def test_production_sqlite_rejected():
    with pytest.raises(RuntimeError) as exc_info:
        create_app(_prod_settings())
    assert "PostgreSQL" in str(exc_info.value)


def test_production_short_secret_rejected():
    with pytest.raises(RuntimeError):
        create_app(
            _prod_settings(
                database_url="postgresql+psycopg2://u:p@h/db",
                jwt_secret="too-short",
            )
        )


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
    from app.config import Settings

    origins = Settings().origins
    assert "https://astroelaa.github.io" in origins
