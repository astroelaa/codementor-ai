"""Deterministic fake LLM for API tests. No network, no keys."""

import json

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


class FakeLLMManager:
    name = "fake"

    def __init__(self) -> None:
        self.complete_scripts: list[str] = []
        self.stream_scripts: list[list[str]] = []
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

    def queue_stream(self, chunks: list[str]) -> None:
        self.stream_scripts.append(chunks)

    def complete(self, *, system, messages, temperature=0.4):
        self.calls.append(
            {"kind": "complete", "system_head": system[:60], "turns": len(messages)}
        )
        if self.complete_scripts:
            return self.complete_scripts.pop(0), "fake"
        return MENTOR_JSON, "fake"

    def stream(self, *, system, messages, temperature=0.4):
        self.calls.append(
            {"kind": "stream", "system_head": system[:60], "turns": len(messages)}
        )
        if self.stream_scripts:
            chunks = self.stream_scripts.pop(0)
        else:
            chunks = ["What ", "happens ", "here?"]
        return "fake", iter(chunks)
