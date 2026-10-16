"""Mentor orchestration helpers: history building and feedback parsing."""

import json
import re

from app.llm.base import Completion
from app.llm.errors import LLMError
from app.models import Message
from app.schemas import MentorFeedback


# Provider-call failures worth ONE second attempt: transient 5xx-style
# errors and rate limits. auth/blocked/config failures are deterministic
# and are never retried.
PROVIDER_RETRY_KINDS = ("server", "timeout", "rate_limit", "all_failed")


def build_history(messages: list[Message], limit: int) -> list[dict]:
    recent = messages[-limit:] if limit > 0 else messages
    return [{"role": m.role, "content": m.content} for m in recent]


def extract_json_dict(raw: str) -> dict:
    """Pull the first JSON object out of model output, tolerating fences."""
    text = (raw or "").strip()
    text = re.sub(r"```(?:json)?", "", text).strip("` \n\t")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise LLMError("mentor", "parse", "model did not return a JSON object")
    try:
        return json.loads(text[start : end + 1])
    except ValueError as exc:
        raise LLMError("mentor", "parse", f"model returned invalid JSON ({exc})")


def parse_feedback(raw: str) -> MentorFeedback:
    """Parse the model's structured JSON reply, tolerating code fences."""
    data = extract_json_dict(raw)
    try:
        return MentorFeedback.model_validate(data)
    except Exception as exc:
        raise LLMError("mentor", "parse", f"feedback failed validation ({exc})")


def complete_with_retry(
    manager,
    *,
    system: str,
    messages: list[dict],
    temperature: float = 0.4,
    max_attempts: int = 2,
    parse=None,
):
    """Structured completion with exactly ONE retry on transient failure.

    Retries cover: a transient provider error (server/timeout/rate limit/
    every-provider-failed) and a non-JSON or schema-invalid model reply
    (the callable `parse` raises LLMError on unusable output; it defaults
    to `parse_feedback`). Deterministic failures (config, auth, blocked)
    raise immediately. Wired into the mentor chat, hint, explain-judge,
    and project-brief paths.
    """
    parse_fn = parse or parse_feedback
    last_error: LLMError | None = None
    for attempt in range(max(1, max_attempts)):
        try:
            completion, provider = manager.complete(
                system=system, messages=messages, temperature=temperature
            )
        except LLMError as exc:
            if exc.kind not in PROVIDER_RETRY_KINDS or attempt:
                raise
            last_error = exc
            continue
        try:
            return parse_fn(completion.text), completion, provider
        except LLMError as exc:
            if attempt:
                raise
            last_error = exc
            continue
    raise last_error or LLMError("mentor", "server", "provider call failed")
