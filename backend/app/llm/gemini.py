"""Google Gemini provider.

The API key travels in the `x-goog-api-key` header (never in the URL), so it
cannot leak through URL logging. All errors are sanitised.
"""

from __future__ import annotations

import json
from typing import Iterator

from .base import BaseLLMProvider, ChatMessage
from .errors import LLMError
from .http import iter_sse_data, open_sse_stream, post_json

API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _to_gemini_role(role: str) -> str:
    return "model" if role == "assistant" else "user"


def extract_gemini_text(provider: str, payload: dict) -> str:
    if isinstance(payload.get("error"), dict):
        err = payload["error"]
        raise LLMError(provider, "server", f"API error: {err.get('message', err)}")
    feedback = payload.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise LLMError(
            provider, "blocked", f"prompt blocked ({feedback['blockReason']})"
        )
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(provider, "parse", f"unexpected response shape ({exc})")
    text = "".join(
        part.get("text", "") for part in parts if isinstance(part, dict)
    ).strip()
    if not text:
        raise LLMError(provider, "parse", "empty completion")
    return text


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def _url(self, stream: bool) -> str:
        action = "streamGenerateContent" if stream else "generateContent"
        suffix = "?alt=sse" if stream else ""
        return f"{API_BASE}/models/{self.model}:{action}{suffix}"

    def _headers(self) -> dict:
        return {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _payload(
        self, system: str, messages: list[ChatMessage], temperature: float
    ) -> dict:
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": _to_gemini_role(m["role"]),
                    "parts": [{"text": m["content"]}],
                }
                for m in messages
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }

    def complete(
        self, *, system: str, messages: list[ChatMessage], temperature: float = 0.4
    ) -> str:
        data = post_json(
            self.name,
            self._url(False),
            headers=self._headers(),
            payload=self._payload(system, messages, temperature),
            timeout=self.timeout,
            secrets=(self.api_key,),
        )
        return extract_gemini_text(self.name, data)

    def stream(
        self, *, system: str, messages: list[ChatMessage], temperature: float = 0.4
    ) -> Iterator[str]:
        with open_sse_stream(
            self.name,
            self._url(True),
            headers=self._headers(),
            payload=self._payload(system, messages, temperature),
            timeout=self.timeout,
            secrets=(self.api_key,),
        ) as resp:
            for chunk in iter_sse_data(resp):
                try:
                    payload = json.loads(chunk)
                except ValueError:
                    continue
                try:
                    text = extract_gemini_text(self.name, payload)
                except LLMError as exc:
                    if exc.kind == "parse":
                        continue  # keep-alive / empty chunk
                    raise
                if text:
                    yield text
