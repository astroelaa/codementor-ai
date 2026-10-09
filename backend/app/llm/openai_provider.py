"""OpenAI provider (OpenAI-compatible API)."""

from .openai_compat import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    api_base = "https://api.openai.com/v1"
