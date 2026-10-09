"""LLM error type. Messages are sanitised so keys can never leak."""

from __future__ import annotations


def sanitize(text: str, secrets: tuple[str, ...] = ()) -> str:
    clean = str(text)
    for secret in secrets:
        if secret and len(secret) > 4:
            clean = clean.replace(secret, "***")
    # Never allow key material shaped like common prefixes to slip through.
    return clean


class LLMError(Exception):
    """Raised for any provider failure.

    kind: auth | rate_limit | server | timeout | parse | blocked |
          config | all_failed
    """

    def __init__(
        self,
        provider: str,
        kind: str,
        message: str,
        *,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self.provider = provider
        self.kind = kind
        super().__init__(sanitize(message, secrets))
