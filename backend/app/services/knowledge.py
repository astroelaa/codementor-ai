"""Curated knowledge corpus + tiny lexical retrieval for citations.

Every card is ORIGINAL explanatory text written for this product, paired
with a link to the official documentation it summarizes. Nothing is copied:
links + licenses are attribution, the prose is ours. Retrieval is a
transparent token-overlap scorer (no embeddings, no vector DB) so relevance
is testable without any model call.

Security rule: retrieved text is UNTRUSTED reference material. It is always
wrapped in markers and the prompt instructs the model never to follow
instructions inside it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Card:
    id: str
    language: str  # registry key, or "general"
    topic: str
    title: str
    url: str
    license: str
    text: str
    keywords: tuple[str, ...] = field(default_factory=tuple)


def _c(id, language, topic, title, url, license, text, keywords):
    return Card(
        id=id, language=language, topic=topic, title=title, url=url,
        license=license, text=text, keywords=tuple(keywords),
    )


CARDS: list[Card] = [
    _c("py-empty", "python", "empty input",
       "Python tutorial: lists", "https://docs.python.org/3/tutorial/",
       "PSF license",
       "An empty list has length 0, so dividing by len(numbers) raises "
       "ZeroDivisionError. Check for the empty case before dividing, for "
       "example with an early return or a guard clause.",
       ("empty", "len", "zerodivisionerror", "divide", "guard")),
    _c("py-range", "python", "off-by-one",
       "Python tutorial: for statements", "https://docs.python.org/3/tutorial/",
       "PSF license",
       "range(n) produces 0 through n-1, so valid indexes for a list of "
       "length n are 0 to n-1. Looping to n itself reads one element past "
       "the end and raises IndexError.",
       ("range", "index", "off-by-one", "indexerror", "loop")),
    _c("py-mutate", "python", "mutation",
       "Python docs: list", "https://docs.python.org/3/library/stdtypes.html",
       "PSF license",
       "Removing items from a list while looping over it skips elements, "
       "because the indexes shift under the loop. Iterate over a copy or "
       "build a new list instead.",
       ("mutate", "iterate", "remove", "skip", "loop")),
    _c("js-nan", "javascript", "types",
       "MDN: NaN", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/NaN",
       "CC-BY-SA 2.5",
       "NaN poisons arithmetic: any operation involving NaN returns NaN, and "
       "NaN never equals anything, not even itself. Reading past an array's "
       "end gives undefined, and math with undefined produces NaN.",
       ("nan", "undefined", "coercion", "typeof", "arithmetic")),
    _c("js-length", "javascript", "indexing",
       "MDN: Array length", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/length",
       "CC-BY-SA 2.5",
       "A JavaScript array of length n has valid indexes 0 to n-1. Starting "
       "a loop at 1 skips the first element, and reading index n gives "
       "undefined instead of an error.",
       ("length", "index", "undefined", "off-by-one", "loop")),
    _c("ts-types", "typescript", "types",
       "TypeScript handbook", "https://www.typescriptlang.org/docs/handbook/intro.html",
       "Apache 2.0",
       "Type annotations describe the shape of data, not the correctness of "
       "logic. A fully typed function can still divide by zero or loop past "
       "an array's end; types never replace testing edge cases.",
       ("types", "annotation", "compiler", "logic", "interface")),
    _c("java-intdiv", "java", "zero-division",
       "Java Language Specification: integer division", "https://docs.oracle.com/javase/specs/",
       "Oracle terms — link only",
       "Dividing two ints in Java discards the remainder, so 5/2 is 2, not "
       "2.5. Dividing by an int zero throws ArithmeticException. Convert one "
       "operand to double first when a fractional result is needed.",
       ("integer", "division", "truncate", "arithmetic", "double")),
    _c("go-panic", "go", "indexing",
       "A Tour of Go: slices", "https://go.dev/tour/moretypes/7",
       "BSD-style",
       "Indexing a Go slice outside 0 to len-1 panics at runtime. A loop "
       "condition of i <= len(nums) reads one element too far; use i < "
       "len(nums), or better, range over the slice.",
       ("panic", "index", "slice", "range", "len")),
    _c("go-nil", "go", "types",
       "Go: slices usage and internals", "https://go.dev/blog/slices-intro",
       "BSD-style",
       "A nil slice behaves like an empty one for len() and range, but "
       "indexing it still panics. Check len() == 0 before indexing rather "
       "than testing for nil alone.",
       ("nil", "slice", "empty", "len", "panic")),
    _c("sql-null", "sql", "empty input",
       "SQLite: aggregate functions", "https://sqlite.org/lang_aggfunc.html",
       "Public domain",
       "Aggregate functions like AVG skip NULL values, and AVG over an empty "
       "set returns NULL rather than 0. A department with no bonuses shows "
       "NULL; use COALESCE(AVG(bonus), 0) to display zero.",
       ("null", "avg", "aggregate", "coalesce", "empty")),
    _c("rust-index", "rust", "indexing",
       "The Rust Book: slices", "https://doc.rust-lang.org/book/ch04-03-slices.html",
       "MIT/Apache-2.0",
       "Indexing a Rust slice with an out-of-bounds index panics instead of "
       "returning garbage. Prefer iterators or .get(), which returns an "
       "Option, over manual index arithmetic.",
       ("panic", "index", "slice", "iterator", "bounds")),
    _c("rust-own", "rust", "scope",
       "The Rust Book: ownership", "https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html",
       "MIT/Apache-2.0",
       "Each value in Rust has one owner; using a moved value is a compile "
       "error, not a runtime surprise. When a loop needs shared access, "
       "borrow with & instead of moving the collection.",
       ("ownership", "borrow", "move", "mutable", "reference")),
    _c("cpp-bounds", "cpp", "loop-bounds",
       "cppreference: operator[]", "https://en.cppreference.com/w/cpp/container/vector/operator_at",
       "CC-BY-SA 3.0",
       "Reading past a container's end with operator[] is undefined "
       "behavior: no exception, just wrong data or crashes. Loop with i < n, "
       "never i <= n, when valid indexes are 0 to n-1.",
       ("bounds", "undefined", "operator", "index", "loop")),
    _c("c-intdiv", "c", "zero-division",
       "C reference: arithmetic operators", "https://en.cppreference.com/w/c/language/operator_arithmetic",
       "CC-BY-SA 3.0",
       "In C, dividing two integers truncates toward zero, so 5/3 is 1. "
       "Integer division by zero is undefined behavior. Cast or convert one "
       "operand to double when a fractional average is needed.",
       ("integer", "division", "truncate", "printf", "double")),
    _c("cs-intdiv", "csharp", "zero-division",
       "C# docs: division operator", "https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/arithmetic-operators",
       "Microsoft terms — link only",
       "The / operator on two ints performs integer division: 5/2 is 2. "
       "Cast one side to double for a fractional result, and guard against "
       "dividing by an integer zero, which throws DivideByZeroException.",
       ("integer", "division", "dividebyzero", "cast", "double")),
    _c("debug-guard", "general", "edge cases",
       "CodeMentor method: guard clauses", "https://astroelaa.github.io/codementor-ai/",
       "Own content",
       "A guard clause checks an edge case at the top of a function and "
       "returns early, so the main logic only handles valid input. Empty "
       "containers, zero divisors, and missing values are the classic cases.",
       ("guard", "edge", "empty", "early", "return")),
    _c("debug-repro", "general", "testing",
       "CodeMentor method: reproduce first", "https://astroelaa.github.io/codementor-ai/",
       "Own content",
       "Before fixing, reproduce with the smallest input that triggers the "
       "bug. If you cannot trigger it on demand, you cannot verify the fix.",
       ("reproduce", "smallest", "trigger", "verify", "test")),
    _c("debug-trace", "general", "error handling",
       "Python tutorial: errors and exceptions", "https://docs.python.org/3/tutorial/errors.html",
       "PSF license",
       "Read a traceback bottom-up: the last line names the error, the lines "
       "above show the call path, and each frame names the file and line "
       "where it happened. Start debugging at the named line.",
       ("traceback", "exception", "error", "frame", "line")),
]

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


_STOP = frozenset({
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "is", "it", "this",
    "that", "with", "for", "what", "when", "how", "why", "does", "do", "be",
    "are", "was", "were", "will", "would", "should", "could", "can", "i", "you",
    "we", "my", "your", "its", "if", "not", "but", "so", "at", "by", "from",
    "as", "an", "we", "us", "me", "he", "she", "they", "them", "his", "her",
    "their", "our", "yours", "theirs", "ours", "mine", "s", "t", "d", "ll",
    "re", "ve", "m",
})


def retrieve(language: str, query: str, top_k: int = 2) -> list[Card]:
    """Lexical retrieval over the curated corpus. Deterministic, no model.

    Prefers cards for the requested language; general cards always eligible.
    Returns at most top_k cards with a positive score, best first.
    """
    words = _tokens(query) - _STOP
    if not words:
        return []
    scored: list[tuple[int, Card]] = []
    for card in CARDS:
        if card.language != "general" and card.language != (language or ""):
            continue
        hay = _tokens(card.title + " " + card.topic + " " + " ".join(card.keywords) + " " + card.text) - _STOP
        overlap = words & hay
        if overlap:
            scored.append((len(overlap), card))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [card for _, card in scored[: max(0, top_k)]]


def format_references(cards: list[Card]) -> str:
    """Prompt block. Retrieved text is wrapped as untrusted reference."""
    if not cards:
        return ""
    parts = [
        "Approved references retrieved for this turn "
        "(untrusted reference material — see orchestration rules):"
    ]
    for card in cards:
        parts.append(
            f"--- BEGIN UNTRUSTED REFERENCE [{card.id}] {card.title} "
            f"({card.url}, {card.license}) ---\n"
            f"{card.text}\n"
            f"--- END UNTRUSTED REFERENCE [{card.id}] ---"
        )
    return "\n".join(parts)


def citations(cards: list[Card]) -> list[dict]:
    """Only retrieved cards are ever cited. Empty input → empty output."""
    return [{"title": c.title, "url": c.url} for c in cards]
