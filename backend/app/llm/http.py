"""Shared HTTP helpers for providers: error mapping, SSE iteration.

Provider keys live only in request headers, which are never logged or
included in error messages.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import httpx

from .errors import LLMError


def _kind_for_status(status: int) -> str:
    if status in (401, 403):
        return "auth"
    if status == 429:
        return "rate_limit"
    return "server"


# A plain browser-like User-Agent: some provider edges challenge or block
# non-browser clients (e.g. Cloudflare bot rules) before authentication.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def _with_user_agent(headers: dict) -> dict:
    merged = {"User-Agent": BROWSER_USER_AGENT}
    merged.update(headers or {})
    return merged


def post_json(
    provider: str,
    url: str,
    *,
    headers: dict,
    payload: dict,
    timeout: int,
    secrets: tuple[str, ...] = (),
) -> dict:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=_with_user_agent(headers), json=payload)
    except httpx.TimeoutException as exc:
        raise LLMError(provider, "timeout", f"request timed out ({exc!r})")
    except httpx.HTTPError as exc:
        raise LLMError(provider, "server", f"transport error ({type(exc).__name__})")
    if resp.status_code >= 400:
        raise LLMError(
            provider,
            _kind_for_status(resp.status_code),
            f"HTTP {resp.status_code}: {resp.text[:300]}",
            secrets=secrets,
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise LLMError(provider, "parse", f"non-JSON response ({exc})")


def iter_sse_data(resp: httpx.Response) -> Iterator[str]:
    """Yield the payload of each `data:` line of an SSE stream."""
    for line in resp.iter_lines():
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        yield data


@contextmanager
def open_sse_stream(
    provider: str,
    url: str,
    *,
    headers: dict,
    payload: dict,
    timeout: int,
    secrets: tuple[str, ...] = (),
):
    """Yield an open SSE response, mapping connection and status errors."""
    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST", url, headers=_with_user_agent(headers), json=payload
            ) as resp:
                if resp.status_code >= 400:
                    body = resp.read().decode("utf-8", "replace")[:300]
                    raise LLMError(
                        provider,
                        _kind_for_status(resp.status_code),
                        f"HTTP {resp.status_code}: {body}",
                        secrets=secrets,
                    )
                yield resp
    except LLMError:
        raise
    except httpx.TimeoutException as exc:
        raise LLMError(provider, "timeout", f"stream timed out ({exc!r})")
    except httpx.HTTPError as exc:
        raise LLMError(provider, "server", f"stream error ({type(exc).__name__})")
