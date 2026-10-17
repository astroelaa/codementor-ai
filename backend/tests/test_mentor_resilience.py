"""LLM mentor resilience + routing regression tests (all fake-LLM).

Covers the Phase 2 contract and the mentor-input fixes:
- greetings get a deterministic reply (warm opener + standing question),
  never an assessment, a praise, or a brand-new question;
- short confirmations, denials and acknowledgments ("Y", "no", "ok",
  "Y\\nhi") get a deterministic push-forward reply: no model call, never a
  restatement of the standing question;
- paraphrase repeats ("Did you consider..." vs "Have you thought...")
  are caught and retried exactly once;
- transient 5xx errors and non-JSON replies are retried exactly once
  before the error surfaces (normal + streaming);
- exhausted rate limits/timeouts surface a clear 503 "mentor is busy"
  without any further retry (the manager owns the wait-and-retry);
- streaming strips a JSON-envelope reply and enforces no-repeat pre-emit.
"""

import json

from app.llm.errors import LLMError
from app.services.orchestration import classify_intent, turn_context_block
from tests.conftest import PYTHON_CODE, client
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
    r1 = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty lists."},
        headers=user_headers,
    ).json()
    calls_before = len(fake_llm.calls)
    # A plain hello is answered deterministically: warm opener + the
    # standing question. No model call, no assessment, no new question.
    r = client.post(
        f"/api/sessions/{sid}/messages", json={"content": "hello"}, headers=user_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert r1["reply"] in body["reply"]
    assert body["next_topics"] == []
    assert body["sources"] == []
    assert len(fake_llm.calls) == calls_before  # the model was never asked
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    last = detail["messages"][-1]
    assert last["meta"]["evaluation"]["verdict"] == "greeting"
    assert r1["reply"] in last["content"]
    assert last["meta"]["sources"] == []


def test_consecutive_greetings_do_not_nest(user_headers, fake_llm):
    sid = _new_session(user_headers)
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty lists."},
        headers=user_headers,
    )
    g1 = client.post(
        f"/api/sessions/{sid}/messages", json={"content": "hello"}, headers=user_headers
    ).json()["reply"]
    g2 = client.post(
        f"/api/sessions/{sid}/messages", json={"content": "hi"}, headers=user_headers
    ).json()["reply"]
    # The standing question is restated once, never stacked templates.
    assert g1.count("What happens to len(numbers)") == 1
    assert g2.count("What happens to len(numbers)") == 1
    assert g1 not in g2


def test_short_confirmation_gets_deterministic_push(user_headers, fake_llm):
    sid = _new_session(user_headers)
    first = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty lists."},
        headers=user_headers,
    ).json()
    calls_before = len(fake_llm.calls)
    # "Y" never reaches the model: it gets acknowledge + articulate so it
    # can never restate the standing question (live: it did, reworded) and
    # can never burn the 502 "unusable response" path.
    r = client.post(
        f"/api/sessions/{sid}/messages", json={"content": "Y"}, headers=user_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "step by step" in body["reply"].lower()
    assert first["reply"] not in body["reply"]
    assert body["sources"] == []
    assert body["next_topics"] == []
    assert len(fake_llm.calls) == calls_before  # no model call at all
    # "Y\nhi": same push, greeting acknowledged, still no model call.
    mixed = client.post(
        f"/api/sessions/{sid}/messages", json={"content": "Y\nhi"}, headers=user_headers
    ).json()
    assert mixed["reply"].startswith("Hi! ")
    assert "step by step" in mixed["reply"].lower()
    assert len(fake_llm.calls) == calls_before
    # "ok" is an acknowledgment: neutral push, still deterministic.
    ok = client.post(
        f"/api/sessions/{sid}/messages", json={"content": "ok"}, headers=user_headers
    ).json()
    assert "step by step" in ok["reply"].lower()
    assert len(fake_llm.calls) == calls_before
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    stored = [m for m in detail["messages"] if m["role"] == "assistant"]
    assert stored[-1]["content"] == ok["reply"]


def test_paraphrased_repeat_retried_once(user_headers, fake_llm):
    sid = _new_session(user_headers)
    q = "Did you consider what happens when the list is empty?"
    fake_llm.queue_complete(json.dumps({"reply": q, "understanding_score": 20}))
    r1 = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "I think it crashes sometimes."},
        headers=user_headers,
    )
    assert r1.json()["reply"] == q
    fresh = {
        "reply": "Good. And what does len(numbers) return for an empty list?",
        "understanding_score": 25,
    }
    paraphrased = "Have you thought about what happens if the list is empty?"
    fake_llm.queue_complete(json.dumps({"reply": paraphrased, "understanding_score": 20}))
    fake_llm.queue_complete(json.dumps(fresh))
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "The sum variable is never reset, I think."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == fresh["reply"]  # the paraphrase never shipped
    assert len(fake_llm.calls) - calls_before == 2  # exactly one corrective retry


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


# --- busy handling: exhausted rate limits/timeouts -> clear 503 -------------------
def test_rate_limit_returns_busy_503_without_extra_retry(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_complete_error(
        LLMError("groq", "rate_limit", "slow down", retry_after=0.1)
    )
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "Divide by zero?"},
        headers=user_headers,
    )
    assert r.status_code == 503, r.text
    assert r.json()["detail"] == "The mentor is busy right now. Try again in a moment."
    # The manager owns wait-and-retry; the app must not retry again here.
    assert len(fake_llm.calls) - calls_before == 1


def test_timeout_maps_to_busy_503(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_complete_error(LLMError("groq", "timeout", "too slow"))
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "Divide by zero?"},
        headers=user_headers,
    )
    assert r.status_code == 503, r.text
    assert "busy" in r.json()["detail"]


def test_stream_rate_limit_surfaces_busy_error_event(user_headers, fake_llm):
    sid = _new_session(user_headers)
    fake_llm.queue_stream_error(LLMError("groq", "rate_limit", "slow down"))
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "Crash on empty."},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text  # SSE itself is a 200 with error events
    events = _parse_sse(r.text)
    assert events.get("error")
    assert not events.get("done")
    assert (
        events["error"][0]["detail"]
        == "The mentor is busy right now. Try again in a moment."
    )
    stream_calls = [c for c in fake_llm.calls[calls_before:] if c["kind"] == "stream"]
    assert len(stream_calls) == 1  # no app-level retry hammering the limiter


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


def test_stream_greeting_is_deterministic_and_free(user_headers, fake_llm):
    sid = _new_session(user_headers)
    r1 = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty input."},
        headers=user_headers,
    ).json()
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "hi"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    token_text = "".join(t["text"] for t in events["token"])
    assert r1["reply"] in token_text
    assert events["done"][0]["reply"] == token_text
    assert events["done"][0]["sources"] == []
    assert len(fake_llm.calls) == calls_before  # no model calls at all


def test_stream_short_confirmation_is_deterministic(user_headers, fake_llm):
    sid = _new_session(user_headers)
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty input."},
        headers=user_headers,
    )
    calls_before = len(fake_llm.calls)
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "ok"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    token_text = "".join(t["text"] for t in events["token"])
    assert "step by step" in token_text.lower()
    assert events["done"][0]["reply"] == token_text
    assert events["done"][0]["sources"] == []
    assert len(fake_llm.calls) == calls_before


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
