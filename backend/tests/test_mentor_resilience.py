"""LLM mentor resilience + routing regression tests (all fake-LLM).

Covers the Phase 2 contract:
- greeting is never assessed as an answer;
- frustration is acknowledged, never treated as a correct answer, and the
  question is not repeated;
- transient provider errors and non-JSON replies are retried exactly once
  before the error surfaces (normal + streaming);
- streaming strips a JSON-envelope reply and enforces no-repeat pre-emit.
"""

import json

from app.llm.errors import LLMError
from app.services.orchestration import classify_intent, turn_context_block
from tests.conftest import (
    PYTHON_CODE,
    client,
    fake_llm,  # noqa: F401
    user_headers,  # noqa: F401
)
from tests.fake_llm import MENTOR_JSON


def _new_session(headers, **kwargs):
    body = {"language": "python", "code": PYTHON_CODE}
    body.update(kwargs)
    r = client.post("/api/sessions", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _parse_sse(text):
    events, current = {}, None
    for line in text.splitlines():
        if line.startswith("event:"):
            current = line[6:].strip()
        elif line.startswith("data:") and current:
            events.setdefault(current, []).append(json.loads(line[5:]))
    return events


def _evaluated(verdict: str, reply: str) -> str:
    return json.dumps(
        {
            "reply": reply,
            "understanding_score": 40,
            "misconception": None,
            "next_topics": [],
            "evaluation": {
                "verdict": verdict,
                "assessed_reasoning": "test",
                "missing_concept": "",
            },
        }
    )


# --- intent + prompt routing ----------------------------------------------------
def test_intent_frustration_variants():
    for text in (
        "what the hell",
        "what the hell is wrong with this",
        "wtf",
        "This is stupid.",
        "I give up",
        "I can't do this anymore",
        "why is this not working",
    ):
        assert classify_intent(text) == "frustration", text
    # Not frustration just because it is negative-but-substantive.
    assert classify_intent("the sum variable is never reset") == "answer"


def test_frustration_context_block_demands_acknowledgement():
    block = turn_context_block(
        intent="frustration",
        previous_question="What is len([])?",
        code_updated=False,
        resources=[],
    )
    assert "frustration" in block
    assert "NOT repeat your previous question" in block


def test_frustration_is_retry_eligible():
    from app.services.orchestration import RETRY_ELIGIBLE_INTENTS

    assert "frustration" in RETRY_ELIGIBLE_INTENTS


# --- assessment guards -----------------------------------------------------------
def test_greeting_never_assessed_as_answer(user_headers, fake_llm):
    sid = _new_session(user_headers)
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty lists."},
        headers=user_headers,
    )
    # Model claims 'incorrect' for a plain hello: guard must override.
    fake_llm.queue_complete(_evaluated("incorrect", "Hi! ready to start?"))
    r = client.post(
        f"/api/sessions/{sid}/messages", json={"content": "hello"}, headers=user_headers
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    verdict = detail["messages"][-1]["meta"]["evaluation"]["verdict"]
    assert verdict == "greeting"


def test_frustration_never_assessed_correct(user_headers, fake_llm):
    sid = _new_session(user_headers)
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty lists."},
        headers=user_headers,
    )
    fake_llm.queue_complete(_evaluated("correct", "Deep breath. Try the empty case."))
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "what the hell"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    verdict = detail["messages"][-1]["meta"]["evaluation"]["verdict"]
    assert verdict == "off_target"


# --- normal path: retry once on unusable / transient -----------------------------
def test_non_json_reply_retried_once_then_succeeds(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fresh = {"reply": "Fresh question about the guard clause?", "understanding_score": 35}
    fake_llm.queue_complete("This is prose, definitely not JSON.")
    fake_llm.queue_complete(json.dumps(fresh))
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "The divisor can be zero."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == fresh["reply"]
    assert len(fake_llm.calls) - calls_before == 2  # exactly one retry


def test_non_json_reply_twice_returns_502(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_complete("still not json")
    fake_llm.queue_complete("nor is this { many")
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "The divisor can be zero."},
        headers=user_headers,
    )
    assert r.status_code == 502, r.text
    assert len(fake_llm.calls) - calls_before == 2  # bounded: no retry loop


def test_transient_provider_error_retried_once(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fresh = {"reply": "Bright retry question about empty lists?", "understanding_score": 30}
    fake_llm.queue_complete_error(LLMError("groq", "server", "upstream 502"))
    fake_llm.queue_complete(json.dumps(fresh))
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "Divide by zero?"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == fresh["reply"]
    assert len(fake_llm.calls) - calls_before == 2


def test_config_error_is_not_retried(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_complete_error(LLMError("manager", "config", "no keys"))
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "Divide by zero?"},
        headers=user_headers,
    )
    assert r.status_code == 503, r.text
    assert len(fake_llm.calls) - calls_before == 1  # deterministic failure


def test_frustration_repeat_retried_with_hint_of_fresh_question(user_headers, fake_llm):
    sid = _new_session(user_headers)
    r1 = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty input."},
        headers=user_headers,
    ).json()
    fresh = {
        "reply": "Totally fair. Fresh start-at-squares question: what value does `len([])` return?",
        "understanding_score": 30,
    }
    fake_llm.queue_complete(json.dumps({**json.loads(MENTOR_JSON), "reply": r1["reply"]}))
    fake_llm.queue_complete(json.dumps(fresh))
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "what the hell"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == fresh["reply"]


# --- streaming -------------------------------------------------------------------
def test_stream_plain_text_streams_normally(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_stream(["A simple ", "plain text question about len?"])
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "It divides by zero."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    token_text = "".join(t["text"] for t in events["token"])
    assert token_text == "A simple plain text question about len?"
    assert events["done"][0]["reply"] == token_text


def test_stream_json_envelope_is_stripped(user_headers, fake_llm):
    sid = _new_session(user_headers)
    envelope = json.dumps(
        {
            "reply": "Clean question: what does len([]) return?",
            "understanding_score": 40,
            "misconception": None,
            "next_topics": [],
        }
    )
    fake_llm.queue_stream([envelope[:7], envelope[7:40], envelope[40:]])
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "It divides by zero."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    token_text = "".join(t["text"] for t in events["token"])
    assert token_text == "Clean question: what does len([]) return?"
    assert events["done"][0]["reply"] == token_text
    assert "{" not in token_text
    # one stream call produced the envelope; the meta call is a complete call
    stream_calls = [c for c in fake_llm.calls if c["kind"] == "stream"]
    assert len(stream_calls) == 1


def test_stream_repeated_question_retried_before_any_token(user_headers, fake_llm):
    sid = _new_session(user_headers)
    r1 = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty input."},
        headers=user_headers,
    ).json()
    repeated = r1["reply"]  # attempt 1 echoes the previous question verbatim
    fresh_text = "New angle: what is the value of the divisor when the list is empty?"
    fake_llm.queue_stream([repeated[:20], repeated[20:]])
    fake_llm.queue_stream([fresh_text[:25], fresh_text[25:]])
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "I think it averages 2, 4 and 6."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    token_text = "".join(t["text"] for t in events["token"])
    # The repeat never reached the client...
    assert repeated not in token_text
    assert token_text == fresh_text
    assert events["done"][0]["reply"] == fresh_text
    # ...exactly two stream calls happened (one retry, never a loop).
    stream_calls = [c for c in fake_llm.calls if c["kind"] == "stream"]
    assert len(stream_calls) == 2
    assert "CORRECTION" in stream_calls[-1]["system"]


def test_stream_non_json_retried_once_then_streams(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_stream(["{this ", "is not ", "valid json"])
    fake_llm.queue_stream(["Recovered ", "plain question about the loop?"])
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "The loop looks fine to me."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    token_text = "".join(t["text"] for t in events["token"])
    assert token_text == "Recovered plain question about the loop?"


def test_stream_unusable_twice_serves_error(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_stream(["{ nope ", "still nope"])
    fake_llm.queue_stream(["{ garbage ", "again"])
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "The loop looks fine to me."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text  # SSE itself is a 200 with error events
    events = _parse_sse(r.text)
    assert events.get("error")
    assert not events.get("done")


def test_transient_open_error_retried_once(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_stream_error(LLMError("groq", "server", "upstream 502"))
    fake_llm.queue_stream(["The connection recovered. What does len([]) return?"])
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "Crash on empty."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    token_text = "".join(t["text"] for t in events.get("token", []))
    assert token_text == "The connection recovered. What does len([]) return?"
    assert events.get("done"), events


# --- explain judge + brief reuse the same retry contract --------------------------
def test_explain_judge_retries_on_non_json(user_headers, fake_llm):
    from tests.fake_llm import JUDGE_FAIL_JSON

    sid = _new_session(user_headers)
    fake_llm.queue_complete("prose, not JSON")
    fake_llm.queue_complete(JUDGE_FAIL_JSON)
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/explain",
        json={"explanation": "I think the loop adds an extra iteration."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["passed"] is False
    assert len(fake_llm.calls) - calls_before == 2


def test_brief_retries_on_non_json(user_headers, fake_llm):
    from tests.fake_llm import BRIEF_JSON

    r = client.post(
        "/api/projects",
        json={"title": "Resilient app", "language": "python"},
        headers=user_headers,
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    fake_llm.queue_complete("plain garbage")
    fake_llm.queue_complete(BRIEF_JSON)
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/projects/{pid}/brief",
        json={"description": "A CLI notes app."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert len(fake_llm.calls) - calls_before == 2
