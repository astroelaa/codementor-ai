"""Groq provider built on the official Groq Python SDK.

The SDK's transport passes provider-edge checks that raw HTTP clients can
hit (bot rules), and it surfaces typed errors we map to LLMError kinds.
Keys stay in memory only and never enter logs or messages.
"""

from __future__ import annotations

from typing import Iterator

from .base import BaseLLMProvider, ChatMessage
from .errors import LLMError


def _map_sdk_error(provider: str, exc: Exception) -> LLMError:
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    if name == "AuthenticationError" or status in (401, 403):
        return LLMError(provider, "auth", f"rejected ({status or name})")
    if name == "RateLimitError" or status == 429:
        return LLMError(provider, "rate_limit", "rate limited")
    if name == "APITimeoutError":
        return LLMError(provider, "timeout", "request timed out")
    if name in ("APIConnectionError", "NotFoundError", "BadRequestError"):
        return LLMError(provider, "server", f"{name} ({status})")
    return LLMError(provider, "server", f"{name} ({status})")


class GroqSDKProvider(BaseLLMProvider):
    name = "groq"

    def _client(self):
        from groq import Groq

        return Groq(api_key=self.api_key, timeout=self.timeout)

    def _messages(self, system: str, messages: list[ChatMessage]) -> list[dict]:
        return [{"role": "system", "content": system}, *messages]

    def complete(
        self, *, system: str, messages: list[ChatMessage], temperature: float = 0.4
    ) -> str:
        try:
            resp = self._client().chat.completions.create(
                model=self.model,
                messages=self._messages(system, messages),
                temperature=temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - mapped below, never logged raw
            raise _map_sdk_error(self.name, exc)
        text = ((resp.choices[0].message.content) or "").strip()
        if not text:
            raise LLMError(self.name, "parse", "empty completion")
        return text

    def stream(
        self, *, system: str, messages: list[ChatMessage], temperature: float = 0.4
    ) -> Iterator[str]:
        try:
            chunks = self._client().chat.completions.create(
                model=self.model,
                messages=self._messages(system, messages),
                temperature=temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            for chunk in chunks:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 - mapped below, never logged raw
            raise _map_sdk_error(self.name, exc)
