"""Health check and sample snippets. No authentication required."""

from fastapi import APIRouter, Depends, Request

from app import deps
from app.schemas import HealthResponse, SnippetResponse
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


@router.get("/api/snippets", response_model=list[SnippetResponse])
def list_snippets(language: str | None = None):
    if language is not None and language not in SAMPLE_SNIPPETS:
        return []
    if language is not None:
        return [SAMPLE_SNIPPETS[language]]
    return list(SAMPLE_SNIPPETS.values())
