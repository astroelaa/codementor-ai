"""Anthropic Messages API provider."""

from __future__ import annotations

import json
from typing import Iterator

from .base import BaseLLMProvider, ChatMessage, Completion
from .errors import LLMError
from .http import iter_sse_data, open_sse_stream, post_json

API_BASE = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"


def extract_anthropic_text(provider: str, payload: dict) -> str:
    if isinstance(payload.get("error"), dict):
        err = payload["error"]
        kind = "auth" if "authentication" in str(err.get("type", "")) else "server"
        raise LLMError(provider, kind, f"API error: {err.get('message', err)}")
    try:
        blocks = payload["content"]
    except (KeyError, TypeError) as exc:
        raise LLMError(provider, "parse", f"unexpected response shape ({exc})")
    text = "".join(
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()
    if not text:
        raise LLMError(provider, "parse", "empty completion")
    return text


def extract_anthropic_usage(payload: dict) -> dict | None:
    """Measured token counts from an Anthropic response, else None."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("input_tokens")
    completion = usage.get("output_tokens")
    if not isinstance(prompt, int) and not isinstance(completion, int):
        return None
    return {
        "prompt_tokens": prompt if isinstance(prompt, int) else None,
        "completion_tokens": completion if isinstance(completion, int) else None,
    }


def extract_anthropic_delta(provider: str, payload: dict) -> str:
    event_type = payload.get("type", "")
    if event_type == "error":
        err = payload.get("error", {})
        kind = (
            "auth"
            if "authentication" in str(err.get("type", ""))
            else "rate_limit"
            if "rate_limit" in str(err.get("type", ""))
            else "server"
        )
        raise LLMError(provider, kind, f"stream error: {err.get('message', err)}")
    if event_type != "content_block_delta":
        return ""
    delta = payload.get("delta", {})
    if delta.get("type") == "text_delta":
        return str(delta.get("text") or "")
    return ""


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def _url(self) -> str:
        return API_BASE + "/messages"

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    def _payload(
        self, system: str, messages: list[ChatMessage], temperature: float, stream: bool
    ) -> dict:
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [
                {"role": m["role"], "content": m["content"]} for m in messages
            ],
            "temperature": temperature,
            "stream": stream,
        }

    def complete(
        self, *, system: str, messages: list[ChatMessage], temperature: float = 0.4
    ) -> Completion:
        data = post_json(
            self.name,
            self._url(),
            headers=self._headers(),
            payload=self._payload(system, messages, temperature, False),
            timeout=self.timeout,
            secrets=(self.api_key,),
        )
        return Completion(
            extract_anthropic_text(self.name, data),
            extract_anthropic_usage(data),
        )

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
                text = extract_anthropic_delta(self.name, payload)
                if text:
                    yield text
