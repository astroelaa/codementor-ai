"""LLM manager: ordered providers with automatic fallback.

The primary provider comes from LLM_PROVIDER; every other configured
provider is tried in LLM_FALLBACKS order on any failure. A provider counts
as configured only when an API key is present.
"""

from __future__ import annotations

from itertools import chain
from typing import Iterator

from app.config import Settings

from .anthropic import AnthropicProvider
from .base import BaseLLMProvider, ChatMessage
from .errors import LLMError
from .gemini import GeminiProvider
from .groq_sdk import GroqSDKProvider
from .openai_provider import OpenAIProvider

SUPPORTED = ("groq", "gemini", "openai", "anthropic")


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
    ) -> tuple[str, str]:
        """Return (text, provider_name), trying each provider in order."""
        failures: list[str] = []
        for provider in self.providers:
            try:
                return provider.complete(
                    system=system, messages=messages, temperature=temperature
                ), provider.name
            except LLMError as exc:
                failures.append(f"{provider.name} ({exc.kind})")
        if not self.providers:
            raise LLMError(
                "manager",
                "config",
                "No LLM provider is configured. Set an API key.",
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
        failures still fall through to the next provider.
        """
        failures: list[str] = []
        for provider in self.providers:
            try:
                chunks = provider.stream(
                    system=system, messages=messages, temperature=temperature
                )
                first = next(chunks)
            except StopIteration:
                failures.append(f"{provider.name} (empty)")
                continue
            except LLMError as exc:
                failures.append(f"{provider.name} ({exc.kind})")
                continue
            return provider.name, chain([first], chunks)
        if not self.providers:
            raise LLMError(
                "manager",
                "config",
                "No LLM provider is configured. Set an API key.",
            )
        raise LLMError(
            "manager", "all_failed", f"All providers failed: {'; '.join(failures)}"
        )
