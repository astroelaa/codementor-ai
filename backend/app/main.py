"""FastAPI application factory."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.database import build_engine, build_session_factory
from app.errors import http_exception_handler, unhandled_exception_handler
from app.llm.manager import LLMManager
from app.rate_limit import RateLimiter
from app.routers import auth, mentor, meta


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = build_engine(settings.database_url)

    app = FastAPI(title="CodeMentor AI API", version="2.0.0")
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.llm_manager = LLMManager(settings)
    app.state.rate_limiter = RateLimiter()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(auth.router)
    app.include_router(mentor.router)
    app.include_router(meta.router)

    @app.get("/")
    def root():
        return {
            "service": "CodeMentor AI API",
            "version": "2.0.0",
            "endpoints": [
                "/health",
                "/api/auth/signup",
                "/api/auth/login",
                "/api/sessions",
                "/api/snippets",
            ],
        }

    return app


app = create_app()
