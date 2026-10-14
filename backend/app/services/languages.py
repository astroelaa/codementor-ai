"""Authoritative language registry for CodeMentor AI.

This module is the single source of truth for supported languages. The
detector, snippets, prompts, and the public `/api/languages` endpoint all
read from here, so capabilities cannot drift between layers.

Honesty rules:
- `highlight` is "full" only with a real grammar; C# reuses Java's grammar
  and is marked "fallback" (colors only — mentoring is unaffected).
- `execution` is "none" for every language: this product never runs
  submitted code. Do not change this without a sandbox design review.
- Documentation entries are LINKS ONLY (title + URL + license). Nothing is
  copied or stored; check each license before quoting content in-app.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    "c",
    "rust",
    "unknown",
]


@dataclass(frozen=True)
class DocLink:
    title: str
    url: str
    license: str


@dataclass(frozen=True)
class LanguageInfo:
    key: str
    label: str
    aliases: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    editor: str = ""  # CodeMirror language id; "" means grammar fallback
    highlight: str = "full"  # full | fallback
    detect: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()
    prompt_note: str = ""
    docs: tuple[DocLink, ...] = ()
    execution: str = "none"


def _D(title: str, url: str, license: str) -> DocLink:
    return DocLink(title=title, url=url, license=license)


LANGUAGES: dict[str, LanguageInfo] = {
    "python": LanguageInfo(
        key="python",
        label="Python",
        aliases=("py",),
        extensions=(".py",),
        editor="python",
        detect=(
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
        ),
        concepts=(
            "ZeroDivisionError and edge cases",
            "mutating a list while iterating it",
            "truthiness, None, and empty containers",
        ),
        prompt_note=(
            "Watch for ZeroDivisionError on empty input, off-by-one range() "
            "bounds, and falsy-value traps (0, '', [], None)."
        ),
        docs=(
            _D("Python 3 documentation", "https://docs.python.org/3/", "PSF license"),
            _D("Python tutorial", "https://docs.python.org/3/tutorial/", "PSF license"),
        ),
    ),
    "javascript": LanguageInfo(
        key="javascript",
        label="JavaScript",
        aliases=("js", "node"),
        extensions=(".js", ".mjs", ".cjs"),
        editor="javascript",
        detect=(
            r"\bfunction\s+\w*\s*\(",
            r"=>",
            r"\bconsole\.(log|error|warn)\s*\(",
            r"^\s*(let|const|var)\s+(?!mut\b)\w+",
            r"===|!==",
            r"\bdocument\.",
            r"\bwindow\.",
            r"\brequire\s*\(",
            r"^\s*import\s+.*\s+from\s+['\"]",
            r"\bundefined\b",
            r"\bnull\b",
        ),
        concepts=(
            "NaN and type coercion surprises",
            "off-by-one indexing and length",
            "undefined vs null",
        ),
        prompt_note=(
            "Watch for NaN propagation, == coercion traps, and confusion "
            "between undefined and null."
        ),
        docs=(
            _D("MDN JavaScript guide", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "CC-BY-SA 2.5"),
        ),
    ),
    "typescript": LanguageInfo(
        key="typescript",
        label="TypeScript",
        aliases=("ts",),
        extensions=(".ts",),
        editor="typescript",
        detect=(
            r":\s*(number|string|boolean|void|null|undefined|any)\b",
            r"\binterface\s+\w+",
            r"\btype\s+\w+\s*=",
            r"<\w+>\s*\(",
            r"\benum\s+\w+",
        ),
        concepts=(
            "type annotations do not catch logic bugs",
            "strict null checks",
            "assignability vs identity",
        ),
        prompt_note=(
            "Remind that types describe shape, not correctness: logic bugs "
            "like wrong bounds survive the compiler."
        ),
        docs=(
            _D("TypeScript handbook", "https://www.typescriptlang.org/docs/handbook/intro.html", "Apache 2.0"),
        ),
    ),
    "java": LanguageInfo(
        key="java",
        label="Java",
        extensions=(".java",),
        editor="java",
        detect=(
            r"\bpublic\s+class\s+\w+",
            r"\bSystem\.out\.print",
            r"\bpublic\s+static\s+void\s+main",
            r"\bprivate\s+\w+\s+\w+\s*;",
            r"\bnew\s+\w+\s*\(",
        ),
        concepts=(
            "integer division truncation",
            "ArrayIndexOutOfBounds and empty arrays",
            "null handling",
        ),
        prompt_note=(
            "Watch for int/int truncation, empty-array division, and "
            "NullPointerException paths."
        ),
        docs=(
            _D("Java documentation", "https://docs.oracle.com/en/java/", "Oracle terms — link only"),
        ),
    ),
    "cpp": LanguageInfo(
        key="cpp",
        label="C++",
        aliases=("c++",),
        extensions=(".cpp", ".cc", ".hpp", ".h"),
        editor="cpp",
        detect=(
            r"#include\s*<(iostream|vector|string|map)>",
            r"\bstd::",
            r"\bcout\s*<<",
            r"\bint\s+main\s*\(",
            r"\btemplate\s*<",
        ),
        concepts=(
            "out-of-bounds reads and undefined behavior",
            "integer division",
            "uninitialized variables",
        ),
        prompt_note=(
            "Watch for <= vs < loop bounds (reads past the end are undefined "
            "behavior, not exceptions) and integer division."
        ),
        docs=(
            _D("cppreference", "https://en.cppreference.com/w/", "CC-BY-SA 3.0"),
        ),
    ),
    "csharp": LanguageInfo(
        key="csharp",
        label="C#",
        aliases=("c#", "cs"),
        extensions=(".cs",),
        editor="java",
        highlight="fallback",
        detect=(
            r"\busing\s+System\s*;",
            r"\bConsole\.(Write|Read)",
            r"\bnamespace\s+\w+",
            r"\bstatic\s+\w+\s+Main",
        ),
        concepts=(
            "integer division truncation",
            "null references",
            "value vs reference types",
        ),
        prompt_note=(
            "Watch for int/int truncation and NullReferenceException paths. "
            "Note: editor highlighting reuses the Java grammar."
        ),
        docs=(
            _D("C# documentation", "https://learn.microsoft.com/en-us/dotnet/csharp/", "Microsoft terms — link only"),
        ),
    ),
    "go": LanguageInfo(
        key="go",
        label="Go",
        aliases=("golang",),
        extensions=(".go",),
        editor="go",
        detect=(
            r"^package\s+\w+",
            r"\bfunc\s+main\s*\(",
            r"\bfmt\.",
            r":=",
        ),
        concepts=(
            "index-out-of-range panics",
            "zero values vs nil",
            "slices vs arrays",
        ),
        prompt_note=(
            "Watch for <= len() indexing panics and confusion between nil "
            "slices and empty slices."
        ),
        docs=(
            _D("Go documentation", "https://go.dev/doc/", "BSD-style"),
            _D("A Tour of Go", "https://go.dev/tour/", "BSD-style"),
        ),
    ),
    "sql": LanguageInfo(
        key="sql",
        label="SQL",
        extensions=(".sql",),
        editor="sql",
        detect=(
            r"(?i)^\s*SELECT\s+",
            r"(?i)\bFROM\s+\w+",
            r"(?i)\bWHERE\s+",
            r"(?i)\bGROUP\s+BY\s+",
            r"(?i)\bINSERT\s+INTO\s+",
        ),
        concepts=(
            "NULL semantics in aggregates",
            "empty result sets vs zero rows",
            "GROUP BY pitfalls",
        ),
        prompt_note=(
            "Watch for NULL propagation (AVG ignores NULLs; empty sets yield "
            "NULL, not 0) and three-valued logic in WHERE."
        ),
        docs=(
            _D("SQLite documentation", "https://sqlite.org/lang.html", "Public domain"),
        ),
    ),
    "c": LanguageInfo(
        key="c",
        label="C",
        extensions=(".c",),
        editor="cpp",
        detect=(
            r"#include\s*<stdio\.h>",
            r"\bprintf\s*\(",
            r"\bscanf\s*\(",
            r"\bmalloc\s*\(",
            r"\bmain\s*\(\s*void\s*\)",
        ),
        concepts=(
            "integer division truncation",
            "buffer overruns and bounds",
            "printf format mismatches",
        ),
        prompt_note=(
            "Watch for int/int truncation, reads past array bounds (undefined "
            "behavior in C), and printf format/type mismatches."
        ),
        docs=(
            _D("C reference", "https://en.cppreference.com/w/c", "CC-BY-SA 3.0"),
        ),
    ),
    "rust": LanguageInfo(
        key="rust",
        label="Rust",
        aliases=("rs",),
        extensions=(".rs",),
        editor="rust",
        detect=(
            r"\bfn\s+main\s*\(",
            r"println!\s*\(",
            r"\blet\s+mut\s+",
            r"&str\b",
            r"->\s*Result\b",
            r"\bmatch\s+\w+\s*\{",
        ),
        concepts=(
            "ownership and borrowing",
            "index panics vs iterators",
            "Option and Result handling",
        ),
        prompt_note=(
            "Watch for indexing panics (prefer iterators), moves that "
            "invalidate bindings, and unwrap() on empty Options."
        ),
        docs=(
            _D("The Rust Book", "https://doc.rust-lang.org/book/", "MIT/Apache-2.0"),
        ),
    ),
}


def supported_keys() -> list[str]:
    return list(LANGUAGES.keys())


def get_language(key: str) -> LanguageInfo | None:
    return LANGUAGES.get((key or "").strip().lower())
