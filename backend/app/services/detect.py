"""Language detection for pasted code.

Detection is metadata guidance only: it tells the UI and the mentor which
grammar to assume. It never claims the code is valid. Patterns come from the
authoritative registry (`app.services.languages`); anything unmatched is
"unknown" so the caller can ask the user to choose explicitly.
"""

import re

from app.services.languages import LANGUAGES, DetectedLanguage  # noqa: F401
from app.services.languages import DetectedLanguage as _DL


def _score(code: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for p in patterns if re.search(p, code, re.MULTILINE))


def detect_language(code: str) -> _DL:
    """Return a supported language key or "unknown" for the given code."""
    if not code or not code.strip():
        return "unknown"  # type: ignore[return-value]
    scores = {key: _score(code, info.detect) for key, info in LANGUAGES.items()}
    # TypeScript builds on JavaScript: require a TS-only signal to win.
    if scores["typescript"] > 0 and scores["typescript"] >= scores["javascript"]:
        return "typescript"  # type: ignore[return-value]
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, best_score), (_, second_score) = ranked[0], ranked[1]
    if best_score == 0 or best_score - second_score < 1:
        return "unknown"  # type: ignore[return-value]
    return best  # type: ignore[return-value]
