"""FastAPI application factory."""

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from app.config import Settings, get_settings
from app.database import build_engine, build_session_factory
from app.errors import http_exception_handler, unhandled_exception_handler
from app.llm.manager import LLMManager
from app.rate_limit import RateLimiter
from app.routers import auth, docs, memory, mentor, meta, notifications, progress, projects


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a short request ID to every response for log correlation.

    Clients may send X-Request-ID; otherwise one is generated. The ID is
    echoed back so a user can quote it when reporting a failure. It never
    carries secrets — only an opaque identifier.
    """

    async def dispatch(
        self, request: StarletteRequest, call_next
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_production()
    engine = build_engine(settings.database_url)

    app = FastAPI(title="CodeMentor AI API", version="2.0.0")
    app.add_middleware(RequestIDMiddleware)
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
    app.include_router(progress.router)
    app.include_router(docs.router)
    app.include_router(projects.router)
    app.include_router(notifications.router)
    app.include_router(memory.router)

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
