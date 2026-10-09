"""Shared test setup: isolated SQLite DB, migrated schema, fake LLM."""

import os
import tempfile

# Environment must be set before any app module is imported.
_tmpdir = tempfile.mkdtemp(prefix="codementor-test-")
TEST_DB_URL = f"sqlite:///{_tmpdir}/test.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["JWT_SECRET"] = "test-secret-key-do-not-use-in-prod"
os.environ["ENVIRONMENT"] = "test"
os.environ["GROQ_API_KEY"] = "gsk-test-sentinel-key-12345"
# Generous budgets here: the suite shares one client IP. Tight limits are
# covered by a dedicated test with its own app instance.
os.environ["RATE_LIMIT_SIGNUP"] = "1000/minute"
os.environ["RATE_LIMIT_LOGIN"] = "1000/minute"
os.environ["RATE_LIMIT_MENTOR"] = "1000/minute"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.deps import get_llm_manager  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.fake_llm import FakeLLMManager  # noqa: E402


def _migrate(url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


_migrate(TEST_DB_URL)

settings = Settings()
app = create_app(settings)
fake = FakeLLMManager()
app.dependency_overrides[get_llm_manager] = lambda: fake

client = TestClient(app)

import pytest  # noqa: E402


@pytest.fixture
def fake_llm():
    fake.reset()
    return fake


@pytest.fixture
def test_client():
    return client


_counter = {"n": 0}


def make_user(c, *, password="secret123", name="Sam"):
    _counter["n"] += 1
    email = f"user{_counter['n']}@example.com"
    r = c.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "display_name": name},
    )
    assert r.status_code == 201, r.text
    return r.json(), password


def auth_headers(c, email: str, password: str):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def user_headers():
    user, password = make_user(client)
    return auth_headers(client, user["email"], password)


PYTHON_CODE = (
    "def average(numbers):\n"
    "    total = 0\n"
    "    for n in numbers:\n"
    "        total += n\n"
    "    return total / len(numbers)"
)
