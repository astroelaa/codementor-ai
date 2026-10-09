"""OpenAI-compatible chat provider (shared by Groq and OpenAI)."""

from __future__ import annotations

import json
from typing import Iterator

from .base import BaseLLMProvider, ChatMessage
from .errors import LLMError
from .http import iter_sse_data, open_sse_stream, post_json


def extract_openai_text(provider: str, payload: dict) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(provider, "parse", f"unexpected response shape ({exc})")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    text = str(content or "").strip()
    if not text:
        raise LLMError(provider, "parse", "empty completion")
    return text


def extract_openai_delta(payload: dict) -> str:
    try:
        choices = payload.get("choices") or []
        delta = (choices[0].get("delta") or {}) if choices else {}
        return str(delta.get("content") or "")
    except (AttributeError, IndexError, TypeError):
        return ""


class OpenAICompatibleProvider(BaseLLMProvider):
    api_base: str = ""

    def _url(self) -> str:
        return self.api_base.rstrip("/") + "/chat/completions"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self, system: str, messages: list[ChatMessage], temperature: float, stream: bool
    ) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }

    def complete(
        self, *, system: str, messages: list[ChatMessage], temperature: float = 0.4
    ) -> str:
        data = post_json(
            self.name,
            self._url(),
            headers=self._headers(),
            payload=self._payload(system, messages, temperature, False),
            timeout=self.timeout,
            secrets=(self.api_key,),
        )
        return extract_openai_text(self.name, data)

    def stream(
        self, *, system: str, messages: list[ChatMessage], temperature: float = 0.4
    ) -> Iterator[str]:
        with open_sse_stream(
            self.name,
            self._url(),
            headers=self._headers(),
            payload=self._payload(system, messages, temperature, True),
            timeout=self.timeout,
            secrets=(self.api_key,),
        ) as resp:
            for chunk in iter_sse_data(resp):
                try:
                    payload = json.loads(chunk)
                except ValueError:
                    continue
                text = extract_openai_delta(payload)
                if text:
                    yield text
