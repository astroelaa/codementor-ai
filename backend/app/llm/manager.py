"""LLM manager: ordered providers with automatic fallback.

The primary provider comes from LLM_PROVIDER; every other configured
provider is tried in LLM_FALLBACKS order on any failure. A provider counts
as configured only when an API key is present.

Rate limits (429) and timeouts get ONE retry per provider after a brief
wait: Retry-After is honoured when the provider sent it, capped so a
request can never stall. Deterministic failures are never retried. When
every provider ends up rate-limited/timed out the manager reports the
kind as rate_limit, which the API surfaces as a clear 503 "mentor is
busy" instead of a generic outage.
"""

from __future__ import annotations

import time
from itertools import chain
from typing import Iterator

from app.config import Settings

from .anthropic import AnthropicProvider
from .base import BaseLLMProvider, ChatMessage, Completion
from .errors import LLMError
from .gemini import GeminiProvider
from .groq_sdk import GroqSDKProvider
from .openai_provider import OpenAIProvider

SUPPORTED = ("groq", "gemini", "openai", "anthropic")

# Kinds worth one wait-and-retry per provider.
_RETRYABLE_KINDS = ("rate_limit", "timeout")
_RETRY_AFTER_CAP_SECONDS = 8.0
_DEFAULT_RETRY_WAIT_SECONDS = 1.5


def _sleep(seconds: float) -> None:
    """Indirection so tests exercise retries without real waiting."""
    time.sleep(seconds)


def _retry_wait(exc: LLMError) -> float:
    """Seconds to wait before the single retry: Retry-After or a default."""
    if exc.retry_after is not None:
        return max(0.0, min(exc.retry_after, _RETRY_AFTER_CAP_SECONDS))
    return _DEFAULT_RETRY_WAIT_SECONDS


def build_provider(
    name: str, api_key: str, model: str, *, timeout: int, max_tokens: int
) -> BaseLLMProvider:
    if name == "groq":
        return GroqSDKProvider(api_key, model, timeout=timeout, max_tokens=max_tokens)
    if name == "gemini":
        return GeminiProvider(api_key, model, timeout=timeout, max_tokens=max_tokens)
    if name == "openai":
        return OpenAIProvider(api_key, model, timeout=timeout, max_tokens=max_tokens)
    if name == "anthropic":
        return AnthropicProvider(
            api_key, model, timeout=timeout, max_tokens=max_tokens
        )
    raise LLMError("manager", "config", f"unsupported provider: {name}")


class LLMManager:
    def __init__(self, settings: Settings) -> None:
        primary = (settings.llm_provider or "groq").strip().lower()
        ordered = [primary] + [
            p.strip().lower() for p in settings.llm_fallbacks.split(",") if p.strip()
        ]
        seen: list[str] = []
        for name in ordered:
            if name and name not in seen:
                seen.append(name)

        self.providers: list[BaseLLMProvider] = []
        for position, name in enumerate(seen):
            if name not in SUPPORTED:
                continue
            specific_key = getattr(settings, f"{name}_api_key", "") or ""
            key = specific_key or (
                settings.llm_api_key if position == 0 else ""
            )
            if not key:
                continue
            default_model = getattr(settings, f"{name}_model", "")
            model = (
                settings.llm_model.strip()
                if position == 0 and settings.llm_model.strip()
                else default_model
            )
            self.providers.append(
                build_provider(
                    name,
                    key,
                    model,
                    timeout=settings.llm_timeout_seconds,
                    max_tokens=settings.llm_max_tokens,
                )
            )

    @property
    def configured_names(self) -> list[str]:
        return [p.name for p in self.providers]

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        temperature: float = 0.4,
    ) -> tuple[Completion, str]:
        """Return (completion, provider_name), trying each provider in order."""
        failures: list[str] = []
        kinds: list[str] = []
        for provider in self.providers:
            for attempt in range(2):
                try:
                    return provider.complete(
                        system=system, messages=messages, temperature=temperature
                    ), provider.name
                except LLMError as exc:
                    if exc.kind in _RETRYABLE_KINDS and attempt == 0:
                        _sleep(_retry_wait(exc))
                        continue
                    failures.append(f"{provider.name} ({exc.kind})")
                    kinds.append(exc.kind)
                    break
        if not self.providers:
            raise LLMError(
                "manager",
                "config",
                "No LLM provider is configured. Set an API key.",
            )
        if kinds and all(kind in _RETRYABLE_KINDS for kind in kinds):
            raise LLMError(
                "manager", "rate_limit", f"All providers busy: {'; '.join(failures)}"
            )
        raise LLMError(
            "manager", "all_failed", f"All providers failed: {'; '.join(failures)}"
        )

    def stream(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        temperature: float = 0.4,
    ) -> tuple[str, Iterator[str]]:
        """Return (provider_name, chunk_iterator).

        The first chunk of each provider is prefetched so connection-time
        failures still fall through to the next provider; rate limits and
        timeouts get one wait-and-retry before falling through. Failures
        after the first chunk are the caller's to handle (no silent
        double-emission).
        """
        failures: list[str] = []
        kinds: list[str] = []
        for provider in self.providers:
            for attempt in range(2):
                try:
                    chunks = provider.stream(
                        system=system, messages=messages, temperature=temperature
                    )
                    first = next(chunks)
                except StopIteration:
                    failures.append(f"{provider.name} (empty)")
                    break
                except LLMError as exc:
                    if exc.kind in _RETRYABLE_KINDS and attempt == 0:
                        _sleep(_retry_wait(exc))
                        continue
                    failures.append(f"{provider.name} ({exc.kind})")
                    kinds.append(exc.kind)
                    break
                return provider.name, chain([first], chunks)
        if not self.providers:
            raise LLMError(
                "manager",
                "config",
                "No LLM provider is configured. Set an API key.",
            )
        if kinds and all(kind in _RETRYABLE_KINDS for kind in kinds):
            raise LLMError(
                "manager", "rate_limit", f"All providers busy: {'; '.join(failures)}"
            )
        raise LLMError(
            "manager", "all_failed", f"All providers failed: {'; '.join(failures)}"
        )
