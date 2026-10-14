"""Provider abstraction: every model vendor implements this interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator

# {"role": "user" | "assistant", "content": str}
ChatMessage = dict


@dataclass
class Completion:
    """One model completion.

    usage holds MEASURED token counts when the provider returns them
    (prompt_tokens / completion_tokens); otherwise None. Counts are never
    invented.
    """

    text: str
    usage: dict | None = field(default=None)


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
    ) -> Completion:
        """One full completion: text plus measured usage when available."""

    @abstractmethod
    def stream(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        temperature: float = 0.4,
    ) -> Iterator[str]:
        """Yield response text chunks as they arrive."""
