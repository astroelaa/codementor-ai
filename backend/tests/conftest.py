"""Shared test setup: isolated SQLite DB, Supabase auth users, fake LLM."""

import os
import tempfile
import uuid

_tmpdir = tempfile.mkdtemp(prefix="codementor-test-")
TEST_DB_URL = f"sqlite:///{_tmpdir}/test.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["GROQ_API_KEY"] = "gsk-test-sentinel-key-12345"
os.environ["RATE_LIMIT_MENTOR"] = "1000/minute"

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.deps import get_llm_manager  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import User  # noqa: E402
from tests.fake_llm import FakeLLMManager  # noqa: E402


def _migrate(url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


_migrate(TEST_DB_URL)

settings = Settings()
if not (
    settings.supabase_url
    and settings.supabase_anon_key
    and settings.supabase_service_role_key
):
    raise RuntimeError(
        "Supabase test credentials are missing: set SUPABASE_URL, "
        "SUPABASE_ANON_KEY, and SUPABASE_SERVICE_ROLE_KEY in backend/.env."
    )

SUPABASE_URL = settings.supabase_url.rstrip("/")
SUPABASE_ANON_KEY = settings.supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY = settings.supabase_service_role_key

app = create_app(settings)
fake = FakeLLMManager()
app.dependency_overrides[get_llm_manager] = lambda: fake

client = TestClient(app)

_created_auth_users: set[str] = set()
_token_cache: dict[tuple[str, str], str] = {}
_counter = {"n": 0}


def _admin_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _anon_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }


def _create_auth_user(email: str, password: str, name: str) -> dict:
    with httpx.Client(timeout=30) as http:
        response = http.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=_admin_headers(),
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"display_name": name},
            },
        )
        response.raise_for_status()
        user = response.json()
    _created_auth_users.add(user["id"])
    return user


def admin_get_user(user_id: str) -> dict | None:
    with httpx.Client(timeout=30) as http:
        response = http.get(
            f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers=_admin_headers(),
        )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def admin_delete_user(user_id: str) -> None:
    with httpx.Client(timeout=30) as http:
        response = http.delete(
            f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers=_admin_headers(),
        )
    if response.status_code != 404:
        response.raise_for_status()


def _sign_in(email: str, password: str) -> str:
    key = (email, password)
    cached = _token_cache.get(key)
    if cached is not None:
        return cached
    with httpx.Client(timeout=30) as http:
        response = http.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=_anon_headers(),
            json={"email": email, "password": password},
        )
        response.raise_for_status()
        token = response.json()["access_token"]
    _token_cache[key] = token
    return token


def _insert_local_user(
    c: TestClient,
    *,
    user_id: str,
    email: str | None,
    display_name: str,
) -> None:
    db = c.app.state.session_factory()
    try:
        db.add(User(id=user_id, email=email, display_name=display_name))
        db.commit()
    finally:
        db.close()


def make_user(c: TestClient, *, password: str = "secret123", name: str = "Sam"):
    _counter["n"] += 1
    email = f"user{_counter['n']}-{uuid.uuid4().hex[:8]}@codementor.test"
    auth_user = _create_auth_user(email, password, name)
    _insert_local_user(
        c,
        user_id=auth_user["id"],
        email=email,
        display_name=name,
    )
    _sign_in(email, password)
    return {
        "id": auth_user["id"],
        "email": email,
        "display_name": name,
        "theme": "dark",
        "is_anonymous": False,
    }, password


def auth_headers(c: TestClient, email: str, password: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_sign_in(email, password)}"}


def make_guest(c: TestClient):
    with httpx.Client(timeout=30) as http:
        response = http.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers=_anon_headers(),
            json={"data": {}, "gotrue_meta_security": {}},
        )
        response.raise_for_status()
        data = response.json()
    auth_user = data["user"]
    token = data.get("access_token") or data.get("session", {}).get("access_token")
    if not token:
        raise RuntimeError("Supabase anonymous sign-in returned no access token.")
    _created_auth_users.add(auth_user["id"])
    _insert_local_user(
        c,
        user_id=auth_user["id"],
        email=None,
        display_name="",
    )
    return {
        "id": auth_user["id"],
        "email": None,
        "display_name": "",
        "theme": "dark",
        "is_anonymous": True,
    }, {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session", autouse=True)
def _cleanup_auth_users():
    yield
    for user_id in list(_created_auth_users):
        try:
            admin_delete_user(user_id)
        except Exception:
            pass


@pytest.fixture
def fake_llm():
    fake.reset()
    return fake


@pytest.fixture
def test_client():
    return client


@pytest.fixture
def user_headers():
    user, password = make_user(client)
    return auth_headers(client, user["email"], password)


@pytest.fixture
def guest_headers():
    _, headers = make_guest(client)
    return headers


PYTHON_CODE = (
    "def average(numbers):\n"
    "    total = 0\n"
    "    for n in numbers:\n"
    "        total += n\n"
    "    return total / len(numbers)"
)
