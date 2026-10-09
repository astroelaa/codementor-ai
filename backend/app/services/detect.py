"""Language detection for pasted code.

Detection is metadata guidance only: it tells the UI and the mentor which
grammar to assume. It never claims the code is valid. Only languages the
editor and the mentor backend actually support are returned; anything else
is "unknown" so the caller can ask the user to choose explicitly.
"""

import re
from typing import Literal

DetectedLanguage = Literal[
    "python",
    "javascript",
    "typescript",
    "java",
    "cpp",
    "csharp",
    "go",
    "sql",
    "unknown",
]

_PYTHON_PATTERNS = [
    r"^\s*def\s+\w+\s*\(.*\)\s*:",
    r"^\s*class\s+\w+.*:",
    r"^\s*import\s+\w+",
    r"^\s*from\s+\w+\s+import\s+",
    r"^\s*elif\s+",
    r"^\s*except\s*[:\(]",
    r"\bprint\s*\(",
    r"\bNone\b",
    r"\bTrue\b",
    r"\bFalse\b",
    r'"""',
]

_JAVASCRIPT_PATTERNS = [
    r"\bfunction\s+\w*\s*\(",
    r"=>",
    r"\bconsole\.(log|error|warn)\s*\(",
    r"^\s*(let|const|var)\s+\w+",
    r"===|!==",
    r"\bdocument\.",
    r"\bwindow\.",
    r"\brequire\s*\(",
    r"^\s*import\s+.*\s+from\s+['\"]",
    r"\bundefined\b",
    r"\bnull\b",
]

_TYPESCRIPT_PATTERNS = [
    r":\s*(number|string|boolean|void|null|undefined|any)\b",
    r"\binterface\s+\w+",
    r"\btype\s+\w+\s*=",
    r"<\w+>\s*\(",
    r"\benum\s+\w+",
]

_JAVA_PATTERNS = [
    r"\bpublic\s+class\s+\w+",
    r"\bSystem\.out\.print",
    r"\bpublic\s+static\s+void\s+main",
    r"\bprivate\s+\w+\s+\w+\s*;",
    r"\bnew\s+\w+\s*\(",
]

_CPP_PATTERNS = [
    r"#include\s*<",
    r"\bstd::",
    r"\bcout\s*<<",
    r"\bint\s+main\s*\(",
]

_CSHARP_PATTERNS = [
    r"\busing\s+System\s*;",
    r"\bConsole\.(Write|Read)",
    r"\bnamespace\s+\w+",
    r"\bstatic\s+\w+\s+Main",
]

_GO_PATTERNS = [
    r"^package\s+\w+",
    r"\bfunc\s+main\s*\(",
    r"\bfmt\.",
    r":=",
]

_SQL_PATTERNS = [
    r"(?i)^\s*SELECT\s+",
    r"(?i)\bFROM\s+\w+",
    r"(?i)\bWHERE\s+",
    r"(?i)\bGROUP\s+BY\s+",
    r"(?i)\bINSERT\s+INTO\s+",
]


def _score(code: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p, code, re.MULTILINE))


def detect_language(code: str) -> DetectedLanguage:
    """Return a supported language or "unknown" for the given code."""
    if not code or not code.strip():
        return "unknown"
    scores = {
        "python": _score(code, _PYTHON_PATTERNS),
        "javascript": _score(code, _JAVASCRIPT_PATTERNS),
        "typescript": _score(code, _TYPESCRIPT_PATTERNS),
        "java": _score(code, _JAVA_PATTERNS),
        "cpp": _score(code, _CPP_PATTERNS),
        "csharp": _score(code, _CSHARP_PATTERNS),
        "go": _score(code, _GO_PATTERNS),
        "sql": _score(code, _SQL_PATTERNS),
    }
    # TypeScript builds on JavaScript: require a TS-only signal to win.
    if scores["typescript"] > 0 and scores["typescript"] >= scores["javascript"]:
        return "typescript"
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, best_score), (_, second_score) = ranked[0], ranked[1]
    if best_score == 0 or best_score - second_score < 1:
        return "unknown"
    return best  # type: ignore[return-value]
