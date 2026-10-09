"""LLM layer unit tests: response parsers, fallback, secret redaction."""

import pytest

from app.llm.anthropic import extract_anthropic_delta, extract_anthropic_text
from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMError, sanitize
from app.llm.gemini import extract_gemini_text
from app.llm.manager import LLMManager
from app.llm.openai_compat import extract_openai_delta, extract_openai_text


def test_openai_complete_parsing():
    payload = {"choices": [{"message": {"content": "  hello  "}}]}
    assert extract_openai_text("groq", payload) == "hello"
    with pytest.raises(LLMError):
        extract_openai_text("groq", {"choices": []})
    with pytest.raises(LLMError):
        extract_openai_text("groq", {"choices": [{"message": {"content": " "}}]})


def test_openai_delta_parsing():
    assert (
        extract_openai_delta({"choices": [{"delta": {"content": "Hi"}}]}) == "Hi"
    )
    assert extract_openai_delta({"choices": []}) == ""
    assert extract_openai_delta({}) == ""


def test_anthropic_parsing():
    payload = {
        "content": [
            {"type": "text", "text": "First. "},
            {"type": "text", "text": "Second."},
        ]
    }
    assert extract_anthropic_text("anthropic", payload) == "First. Second."
    delta = {
        "type": "content_block_delta",
        "delta": {"type": "text_delta", "text": "more"},
    }
    assert extract_anthropic_delta("anthropic", delta) == "more"
    assert extract_anthropic_delta("anthropic", {"type": "message_stop"}) == ""
    with pytest.raises(LLMError) as exc_info:
        extract_anthropic_delta(
            "anthropic",
            {"type": "error", "error": {"type": "authentication_error"}},
        )
    assert exc_info.value.kind == "auth"


def test_gemini_parsing_and_blocked():
    payload = {
        "candidates": [
            {"content": {"parts": [{"text": "Hello "}, {"text": "there"}]}}
        ]
    }
    assert extract_gemini_text("gemini", payload) == "Hello there"
    with pytest.raises(LLMError) as exc_info:
        extract_gemini_text("gemini", {"promptFeedback": {"blockReason": "SAFETY"}})
    assert exc_info.value.kind == "blocked"
    with pytest.raises(LLMError):
        extract_gemini_text("gemini", {"error": {"message": "bad key"}})


def test_sanitize_redacts_keys():
    err = LLMError("groq", "server", "boom gsk-test-sentinel-key-12345", secrets=("gsk-test-sentinel-key-12345",))
    assert "sentinel" not in str(err)


class _Failer(BaseLLMProvider):
    name = "failer"

    def complete(self, *, system, messages, temperature=0.4):
        raise LLMError(self.name, "rate_limit", "slow down")

    def stream(self, *, system, messages, temperature=0.4):
        raise LLMError(self.name, "server", "broken")
        yield ""  # pragma: no cover - makes this a generator


class _Succeed(BaseLLMProvider):
    name = "ok"

    def complete(self, *, system, messages, temperature=0.4):
        return "done"

    def stream(self, *, system, messages, temperature=0.4):
        yield from ["a", "b"]


def _manager_with(providers):
    manager = LLMManager.__new__(LLMManager)
    manager.providers = providers
    return manager


def test_manager_falls_back_on_complete():
    manager = _manager_with([_Failer("k", "m"), _Succeed("k", "m")])
    text, name = manager.complete(system="s", messages=[])
    assert (text, name) == ("done", "ok")


def test_manager_falls_back_on_stream_before_first_chunk():
    manager = _manager_with([_Failer("k", "m"), _Succeed("k", "m")])
    name, chunks = manager.stream(system="s", messages=[])
    assert name == "ok"
    assert list(chunks) == ["a", "b"]


def test_manager_raises_when_everything_fails():
    manager = _manager_with([_Failer("k", "m")])
    with pytest.raises(LLMError) as exc_info:
        manager.complete(system="s", messages=[])
    assert exc_info.value.kind == "all_failed"


def test_manager_raises_when_nothing_configured():
    manager = _manager_with([])
    with pytest.raises(LLMError) as exc_info:
        manager.complete(system="s", messages=[])
    assert exc_info.value.kind == "config"
