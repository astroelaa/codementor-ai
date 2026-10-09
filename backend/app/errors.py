"""Structured error handling.

All HTTP errors leave the API as {"detail": ..., "code": ...}.
LLM failures are mapped to 502/503 without leaking keys or internals.
"""

import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.llm.errors import LLMError

log = logging.getLogger("codementor")


def llm_error_to_http(exc: LLMError) -> HTTPException:
    if exc.kind in ("config", "all_failed"):
        return HTTPException(
            status_code=503,
            detail=(
                "The mentor is unavailable right now: no AI provider is "
                "configured or reachable. Try again later."
            ),
        )
    if exc.kind == "rate_limit":
        return HTTPException(
            status_code=503,
            detail="AI providers are rate-limited right now. Try again shortly.",
        )
    return HTTPException(
        status_code=502,
        detail="The AI mentor failed to respond. Try again.",
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if not isinstance(detail, str):
        detail = "Request failed."
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": exc.status_code},
        headers=dict(exc.headers) if exc.headers else None,
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "code": 500},
    )
