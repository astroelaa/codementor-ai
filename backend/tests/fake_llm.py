"""Deterministic fake LLM for API tests. No network, no keys."""

import json

from app.llm.base import Completion
from app.llm.errors import LLMError

MENTOR_JSON = json.dumps(
    {
        "reply": "What happens to len(numbers) when the list is empty?",
        "understanding_score": 25,
        "misconception": {
            "type": "empty-input",
            "description": "Assumes len() is never zero.",
        },
        "next_topics": [
            "Edge cases: empty input",
            "ZeroDivisionError",
            "Guard clauses",
        ],
    }
)

HINT_JSON = json.dumps(
    {
        "reply": "Trace the last line with an empty list. What is the divisor?",
        "understanding_score": 30,
        "misconception": None,
        "next_topics": ["Edge cases: empty input", "Guard clauses"],
    }
)

JUDGE_PASS_JSON = json.dumps(
    {
        "passed": True,
        "score": 88,
        "feedback": "You named the root cause and explained why the fix works.",
        "follow_up_question": "Where else in your code could a zero divisor hide?",
    }
)

JUDGE_FAIL_JSON = json.dumps(
    {
        "passed": False,
        "score": 35,
        "feedback": "You described the symptom, not the root cause.",
        "follow_up_question": "What exactly does len([]) return?",
    }
)

DOC_JSON = json.dumps(
    {
        "explanation": "A list comprehension builds a new list by transforming each item.",
        "example": "[x * 2 for x in [1, 2]] gives [2, 4].",
        "question": "What does [x for x in []] produce?",
    }
)

BRIEF_JSON = json.dumps(
    {
        "objective": "Build a CLI todo app that stores tasks in a file.",
        "requirements": ["Add tasks", "List tasks", "Mark tasks done"],
        "architecture": "Single module with functions per command.",
        "milestones": [
            {"title": "Storage", "tasks": ["Design file format", "Write save/load"]},
            {"title": "CLI", "tasks": ["Add command", "List command"]},
        ],
    }
)


class FakeLLMManager:
    name = "fake"

    def __init__(self) -> None:
        self.complete_scripts: list = []  # str payloads or LLMError instances
        self.stream_scripts: list = []  # chunk lists or LLMError instances
        self.calls: list[dict] = []

    @property
    def configured_names(self) -> list[str]:
        return ["fake"]

    def reset(self) -> None:
        self.complete_scripts = []
        self.stream_scripts = []
        self.calls = []

    def queue_complete(self, text: str) -> None:
        self.complete_scripts.append(text)

    def queue_complete_error(self, error: LLMError) -> None:
        """Queue a raised LLMError for the next complete() call."""
        self.complete_scripts.append(error)

    def queue_stream(self, chunks: list[str]) -> None:
        self.stream_scripts.append(chunks)

    def queue_stream_error(self, error: LLMError) -> None:
        self.stream_scripts.append(error)

    def complete(self, *, system, messages, temperature=0.4):
        self.calls.append(
            {
                "kind": "complete",
                "system_head": system[:60],
                "system": system,
                "turns": len(messages),
            }
        )
        if self.complete_scripts:
            item = self.complete_scripts.pop(0)
            if isinstance(item, LLMError):
                raise item
            return Completion(item, None), "fake"
        return Completion(MENTOR_JSON, None), "fake"

    def stream(self, *, system, messages, temperature=0.4):
        self.calls.append(
            {
                "kind": "stream",
                "system_head": system[:60],
                "system": system,
                "turns": len(messages),
            }
        )
        if self.stream_scripts:
            item = self.stream_scripts.pop(0)
            if isinstance(item, LLMError):
                raise item
            return "fake", iter(item)
        return "fake", iter(["What ", "happens ", "here?"])
