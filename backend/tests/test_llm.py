"""LLM layer unit tests: response parsers, fallback, secret redaction."""

import pytest

from app.llm.anthropic import (
    extract_anthropic_delta,
    extract_anthropic_text,
    extract_anthropic_usage,
)
from app.llm.base import BaseLLMProvider
from app.llm.errors import LLMError
from app.llm.gemini import extract_gemini_text, extract_gemini_usage
from app.llm.manager import LLMManager
from app.llm.openai_compat import (
    extract_openai_delta,
    extract_openai_text,
    extract_openai_usage,
)


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
        raise LLMError(self.name, "server", "boom")

    def stream(self, *, system, messages, temperature=0.4):
        raise LLMError(self.name, "server", "broken")
        yield ""  # pragma: no cover - makes this a generator


class _Flaky(BaseLLMProvider):
    """Fails with the queued kinds, then succeeds. Counts its calls."""

    name = "flaky"

    def __init__(self, *kinds, retry_after=None):
        self.kinds = list(kinds)
        self.retry_after = retry_after
        self.calls = 0

    def _fail(self):
        self.calls += 1
        if self.kinds:
            kind = self.kinds.pop(0)
            raise LLMError(self.name, kind, "boom", retry_after=self.retry_after)

    def complete(self, *, system, messages, temperature=0.4):
        self._fail()
        from app.llm.base import Completion

        return Completion("done", None)

    def stream(self, *, system, messages, temperature=0.4):
        self._fail()
        yield "a"


class _Succeed(BaseLLMProvider):
    name = "ok"

    def complete(self, *, system, messages, temperature=0.4):
        from app.llm.base import Completion

        return Completion("done", {"prompt_tokens": 5, "completion_tokens": 2})

    def stream(self, *, system, messages, temperature=0.4):
        yield from ["a", "b"]


def _manager_with(providers):
    manager = LLMManager.__new__(LLMManager)
    manager.providers = providers
    return manager


def test_manager_falls_back_on_complete():
    manager = _manager_with([_Failer("k", "m"), _Succeed("k", "m")])
    completion, name = manager.complete(system="s", messages=[])
    assert (completion.text, name) == ("done", "ok")
    assert completion.usage == {"prompt_tokens": 5, "completion_tokens": 2}


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


def test_manager_waits_retry_after_and_retries_rate_limit_once(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.llm.manager._sleep", sleeps.append)
    provider = _Flaky("rate_limit", retry_after=0.25)
    manager = _manager_with([provider])
    completion, name = manager.complete(system="s", messages=[])
    assert (completion.text, name) == ("done", "flaky")
    assert provider.calls == 2  # exactly one retry
    assert sleeps == [0.25]  # Retry-After honoured


def test_manager_caps_retry_after_and_defaults(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.llm.manager._sleep", sleeps.append)
    manager = _manager_with([_Flaky("timeout", retry_after=120)])
    manager.complete(system="s", messages=[])
    manager2 = _manager_with([_Flaky("rate_limit")])
    manager2.complete(system="s", messages=[])
    assert sleeps == [8.0, 1.5]  # capped value, then the brief default


def test_manager_does_not_retry_deterministic_kinds(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.llm.manager._sleep", sleeps.append)
    provider = _Flaky("auth")
    manager = _manager_with([provider])
    with pytest.raises(LLMError) as exc_info:
        manager.complete(system="s", messages=[])
    assert exc_info.value.kind == "all_failed"
    assert provider.calls == 1  # never retried
    assert sleeps == []


def test_manager_reports_busy_when_everything_is_rate_limited(monkeypatch):
    monkeypatch.setattr("app.llm.manager._sleep", lambda _seconds: None)
    first = _Flaky("rate_limit", "rate_limit", retry_after=0)
    second = _Flaky("timeout", "timeout")
    manager = _manager_with([first, second])
    with pytest.raises(LLMError) as exc_info:
        manager.complete(system="s", messages=[])
    assert exc_info.value.kind == "rate_limit"  # -> 503 "mentor is busy"
    assert first.calls == 2 and second.calls == 2


def test_manager_stream_retries_rate_limit_before_first_chunk(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.llm.manager._sleep", sleeps.append)
    provider = _Flaky("rate_limit", retry_after=0.1)
    manager = _manager_with([provider])
    name, chunks = manager.stream(system="s", messages=[])
    assert name == "flaky"
    assert list(chunks) == ["a"]
    assert provider.calls == 2
    assert sleeps == [0.1]


def test_retry_after_extraction_and_busy_mapping():
    from app.errors import llm_error_to_http
    from app.llm.groq_sdk import _map_sdk_error, _retry_after_from_exc

    class _Resp:
        headers = {"retry-after": "2.5"}

    class _RateLimited(Exception):
        status_code = 429

    exc = _RateLimited()
    exc.response = _Resp()
    err = _map_sdk_error("groq", exc)
    assert err.kind == "rate_limit"
    assert err.retry_after == 2.5

    bare = _RateLimited()
    assert _retry_after_from_exc(bare) is None

    class _BadResp:
        headers = {"retry-after": "soon"}

    bad = _RateLimited()
    bad.response = _BadResp()
    assert _retry_after_from_exc(bad) is None

    assert llm_error_to_http(LLMError("groq", "rate_limit", "x")).status_code == 503
    assert "busy" in llm_error_to_http(LLMError("groq", "timeout", "x")).detail
    assert (
        llm_error_to_http(LLMError("manager", "all_failed", "x")).detail
        != llm_error_to_http(LLMError("groq", "rate_limit", "x")).detail
    )


def test_usage_extractors():
    assert extract_openai_usage(
        {"usage": {"prompt_tokens": 10, "completion_tokens": 4}}
    ) == {"prompt_tokens": 10, "completion_tokens": 4}
    assert extract_openai_usage({}) is None
    assert extract_openai_usage({"usage": {"total_tokens": 14}}) is None
    assert extract_anthropic_usage(
        {"usage": {"input_tokens": 7, "output_tokens": 3}}
    ) == {"prompt_tokens": 7, "completion_tokens": 3}
    assert extract_anthropic_usage({}) is None
    assert extract_gemini_usage(
        {"usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 5}}
    ) == {"prompt_tokens": 9, "completion_tokens": 5}
    assert extract_gemini_usage({}) is None
