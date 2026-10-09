"""Groq provider (OpenAI-compatible API)."""

from .openai_compat import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    api_base = "https://api.groq.com/openai/v1"
