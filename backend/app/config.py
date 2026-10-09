"""Application configuration.

Every secret (API keys, JWT secret, database URL) comes from the environment
or from backend/.env, which is git-ignored. Nothing secret is hardcoded here.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "CodeMentor AI API"
    environment: str = "development"  # development | test | production
    database_url: str = "sqlite:///./codementor.db"

    jwt_secret: str = "development-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    # Comma-separated browser origins allowed to call this API.
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173,"
        "http://localhost:5500,http://127.0.0.1:5500,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )

    # --- LLM layer ------------------------------------------------------
    # Primary provider + ordered fallbacks. Switching provider is a config
    # change only: set LLM_PROVIDER and the matching *_API_KEY.
    llm_provider: str = "groq"
    llm_fallbacks: str = "gemini,openai,anthropic"
    llm_model: str = ""  # override for the primary provider; empty = default
    llm_api_key: str = ""  # generic fallback key for the primary provider
    llm_timeout_seconds: int = 45
    llm_max_tokens: int = 700

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"

    # --- Rate limits ("<count>/<second|minute|hour|day>") ----------------
    rate_limit_signup: str = "10/minute"
    rate_limit_login: str = "10/minute"
    rate_limit_mentor: str = "30/minute"

    # --- Mentor behaviour -------------------------------------------------
    max_hints_per_session: int = 3
    history_window: int = 20
    max_session_messages: int = 60

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
