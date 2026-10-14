"""Health check and sample snippets. No authentication required."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.schemas import HealthResponse, LanguageInfoResponse, SnippetResponse
from app.services.languages import LANGUAGES
from app.services.snippets import SAMPLE_SNIPPETS

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request):
    manager = request.app.state.llm_manager
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        # Provider names only. Keys are never exposed by any endpoint.
        providers_configured=manager.configured_names,
    )


@router.get("/ready")
def ready(request: Request):
    """Readiness: genuinely checks the database and provider configuration.

    No AI call is made. Returns 200 only when the database answers and at
    least one provider is configured (or none is required in dev).
    """
    checks: dict = {}
    status_code = 200
    try:
        factory = request.app.state.session_factory
        db: DbSession = factory()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        finally:
            db.close()
    except Exception:
        checks["database"] = "unreachable"
        status_code = 503
    providers = request.app.state.llm_manager.configured_names
    checks["providers_configured"] = providers
    if not providers:
        checks["providers_note"] = "no AI provider configured"
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if status_code == 200 else "not-ready",
            **checks,
        },
    )


@router.get("/api/snippets", response_model=list[SnippetResponse])
def list_snippets(language: str | None = None):
    if language is not None and language not in SAMPLE_SNIPPETS:
        return []
    if language is not None:
        return [SAMPLE_SNIPPETS[language]]
    return list(SAMPLE_SNIPPETS.values())


@router.get("/api/languages", response_model=list[LanguageInfoResponse])
def list_languages():
    """Authoritative language registry: capabilities, docs, honesty flags."""
    return [
        LanguageInfoResponse(
            key=info.key,
            label=info.label,
            aliases=list(info.aliases),
            extensions=list(info.extensions),
            editor=info.editor,
            highlight=info.highlight,
            concepts=list(info.concepts),
            docs=[
                {"title": d.title, "url": d.url, "license": d.license}
                for d in info.docs
            ],
            execution=info.execution,
        )
        for info in LANGUAGES.values()
    ]
