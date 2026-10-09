"""Provider abstraction: every model vendor implements this interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

# {"role": "user" | "assistant", "content": str}
ChatMessage = dict


class BaseLLMProvider(ABC):
    name: str = "base"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout: int = 45,
        max_tokens: int = 700,
    ) -> None:
        if not api_key:
            from .errors import LLMError

            raise LLMError(self.name, "config", "missing API key")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        temperature: float = 0.4,
    ) -> str:
        """One full completion, returned as plain text."""

    @abstractmethod
    def stream(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        temperature: float = 0.4,
    ) -> Iterator[str]:
        """Yield response text chunks as they arrive."""
