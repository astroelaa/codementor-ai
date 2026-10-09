"""Mentor orchestration helpers: history building and feedback parsing."""

import json
import re

from app.llm.errors import LLMError
from app.models import Message
from app.schemas import MentorFeedback


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
