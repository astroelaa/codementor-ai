"""Orchestration regression tests: intent, anti-repetition, code snapshots,
citations, modes. All mocked — no network."""

import json

from app.services.orchestration import (
    classify_intent,
    extract_code_block,
    is_repeat,
    turn_context_block,
)
from tests.conftest import PYTHON_CODE, client
from tests.fake_llm import MENTOR_JSON


def _new_session(headers, **kwargs):
    body = {"language": "python", "code": PYTHON_CODE}
    body.update(kwargs)
    r = client.post("/api/sessions", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --- intent classification -------------------------------------------------
def test_intent_greetings():
    for text in ["hello", "Hi!", "hey there", "good morning", "how are you?"]:
        assert classify_intent(text) == "greeting", text


def test_intent_hint_explain_question():
    assert classify_intent("give me a hint please") == "hint_request"
    assert classify_intent("I need a clue") == "hint_request"
    assert classify_intent("can you explain this code?") == "explanation_request"
    assert classify_intent("I don't understand") == "explanation_request"
    assert classify_intent("why does it crash?") == "question"
    assert classify_intent("what is len?") == "question"


def test_intent_code_change_and_answer():
    assert classify_intent("```python\nx = 1\n```") == "code_change"
    assert classify_intent("def f(x):\n    return x\nfor i in y:\n    print(i)") == "code_change"
    assert classify_intent("I think len([]) is zero") == "answer"
    assert classify_intent("??") == "unclear"
    assert classify_intent("   ") == "unclear"
    # Bare confirmations/denials are answers, not noise.
    assert classify_intent("Y") == "answer"
    assert classify_intent("yes") == "answer"
    assert classify_intent("no") == "answer"
    assert classify_intent("ok") == "answer"
    # A greeting line inside a message must not swallow the rest.
    assert classify_intent("Y\nhi") == "answer"
    assert classify_intent("hi\nyo") == "greeting"
    assert classify_intent("hi\nexplain this code?") == "explanation_request"


def test_extract_code_block():
    assert extract_code_block("no code here") is None
    assert extract_code_block("```python\nx = 1\n```") == "x = 1"


def test_turn_context_block_mentions_intent_and_rules():
    block = turn_context_block(
        intent="greeting", previous_question="What is len()?",
        code_updated=False, resources=[],
    )
    assert "greeting" in block
    block2 = turn_context_block(
        intent="answer", previous_question="What is len()?",
        code_updated=True, resources=[],
    )
    assert "Do not ask the same question again" in block2
    assert "CURRENT code" in block2


# --- anti-repetition --------------------------------------------------------
def test_is_repeat_detection():
    q = "What happens to len(numbers) when the list is empty?"
    assert is_repeat(q, q) is True
    assert is_repeat(
        "What happens to len(numbers) if the list is empty?",
        q,
    ) is True
    assert is_repeat("Explain how division works in Python.", q) is False
    assert is_repeat("", q) is False
    # Paraphrased repeats (swapped synonyms) are still repeats.
    assert is_repeat(
        "Have you thought about what happens if the list is empty?",
        "Did you consider what happens when the list is empty?",
    ) is True
    # A genuinely different follow-up sharing a couple of words is not.
    assert is_repeat(
        "What would happen if one of the elements isn't a number?",
        "Did you consider what happens when the list is empty?",
    ) is False


def test_greeting_compose_restates_without_nesting():
    from app.services.orchestration import compose_greeting_reply

    q = "What happens to len(numbers) when the list is empty?"
    first = compose_greeting_reply(q, seed=0)
    assert q in first
    assert "assess" not in first.lower()
    # Greeting again must reuse the bare question, not stack templates.
    second = compose_greeting_reply(first, seed=1)
    assert second.count(q) == 1
    assert first not in second


def test_turn_context_block_flags_short_confirmation():
    block = turn_context_block(
        intent="answer", previous_question="Is the list empty here?",
        code_updated=False, resources=[], student_text="Y",
    )
    assert "short confirmation" in block
    mixed = turn_context_block(
        intent="answer", previous_question="Is the list empty here?",
        code_updated=False, resources=[], student_text="Y\nhi",
    )
    assert "also contains a short greeting" in mixed


def test_retry_once_on_repeat_then_uses_fresh(user_headers, fake_llm):
    sid = _new_session(user_headers)
    # First turn: default fake reply R1.
    r1 = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty input."},
        headers=user_headers,
    ).json()
    # Second turn: fake first repeats R1 verbatim, then offers fresh text.
    fresh = {
        "reply": "Good, now walk me through what the loop does on that input.",
        "understanding_score": 40,
        "misconception": None,
        "next_topics": ["loops"],
        "evaluation": {
            "verdict": "partially_correct",
            "assessed_reasoning": "Right case, missing empty case.",
            "missing_concept": "empty input",
        },
    }
    fake_llm.queue_complete(json.dumps({**json.loads(MENTOR_JSON), "reply": r1["reply"]}))
    fake_llm.queue_complete(json.dumps(fresh))
    calls_before = len([c for c in fake_llm.calls if c["kind"] == "complete"])
    r2 = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It averages 2, 4 and 6."},
        headers=user_headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["reply"] == fresh["reply"]
    calls_after = len([c for c in fake_llm.calls if c["kind"] == "complete"])
    assert calls_after - calls_before == 2  # exactly one retry, never a loop


def test_no_retry_when_reply_is_fresh(user_headers, fake_llm):
    sid = _new_session(user_headers)
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It crashes on empty input."},
        headers=user_headers,
    )
    fresh = {
        "reply": "A completely different follow-up about guard clauses?",
        "understanding_score": 45,
        "misconception": None,
        "next_topics": [],
    }
    fake_llm.queue_complete(json.dumps(fresh))
    calls_before = len([c for c in fake_llm.calls if c["kind"] == "complete"])
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "Something else entirely new here."},
        headers=user_headers,
    )
    assert r.status_code == 200
    assert r.json()["reply"] == fresh["reply"]
    calls_after = len([c for c in fake_llm.calls if c["kind"] == "complete"])
    assert calls_after - calls_before == 1  # no retry needed


def test_evaluation_persisted_in_meta(user_headers, fake_llm):
    sid = _new_session(user_headers)
    evaluated = {
        "reply": "Noted, which line divides?",
        "understanding_score": 30,
        "misconception": None,
        "next_topics": [],
        "evaluation": {
            "verdict": "incorrect",
            "assessed_reasoning": "Wrong operator named.",
            "missing_concept": "division",
        },
    }
    fake_llm.queue_complete(json.dumps(evaluated))
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "It uses plus wrong."},
        headers=user_headers,
    )
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    last = detail["messages"][-1]
    assert last["meta"]["evaluation"]["verdict"] == "incorrect"


# --- code snapshots ----------------------------------------------------------
def test_explicit_code_updates_session(user_headers):
    sid = _new_session(user_headers)
    new_code = "def average(numbers):\n    return sum(numbers) / len(numbers)"
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "I rewrote it, take a look.", "code": new_code},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    assert detail["code"] == new_code


def test_fenced_code_in_content_updates_session(user_headers):
    sid = _new_session(user_headers)
    new_code = "x = 1\nprint(x)"
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": f"Here is my attempt:\n```python\n{new_code}\n```"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    assert detail["code"] == new_code


def test_unchanged_code_keeps_session_code(user_headers):
    sid = _new_session(user_headers)
    before = client.get(f"/api/sessions/{sid}", headers=user_headers).json()["code"]
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "What about empty input?"},
        headers=user_headers,
    )
    after = client.get(f"/api/sessions/{sid}", headers=user_headers).json()["code"]
    assert before == after


def test_hint_accepts_code_snapshot(user_headers, fake_llm):
    from tests.fake_llm import HINT_JSON

    sid = _new_session(user_headers)
    new_code = "y = 2\nprint(y)"
    fake_llm.queue_complete(HINT_JSON)
    r = client.post(
        f"/api/sessions/{sid}/hints", json={"code": new_code}, headers=user_headers
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    assert detail["code"] == new_code
    # And the no-body form still works (backwards compatible).
    fake_llm.queue_complete(HINT_JSON)
    r = client.post(f"/api/sessions/{sid}/hints", headers=user_headers)
    assert r.status_code == 200, r.text


def test_mode_stored_and_returned(user_headers):
    sid = _new_session(user_headers, mode="mycode")
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    assert detail["mode"] == "mycode"
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1", "mode": "arcade"},
        headers=user_headers,
    )
    assert r.status_code == 422


# --- citations ----------------------------------------------------------------
def test_citations_only_from_retrieval(user_headers):
    sid = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "What happens with an empty list and len()?"},
        headers=user_headers,
    )
    assert r.status_code == 200
    for source in r.json()["sources"]:
        assert source["title"] and source["url"].startswith("https://")


def test_no_citations_when_nothing_relevant(user_headers):
    sid = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "hello"},
        headers=user_headers,
    )
    assert r.status_code == 200
    assert r.json()["sources"] == []


def test_malicious_card_stays_quarantined():
    from app.services.knowledge import CARDS, citations, format_references

    evil = [c for c in CARDS if "ignore" in c.text.lower()]
    assert evil == []  # corpus itself must never contain instruction text
    block = format_references([])
    assert block == ""
    assert citations([]) == []


def test_stream_done_carries_sources(user_headers):
    sid = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "What happens with an empty list and len()?"},
        headers=user_headers,
    )
    assert r.status_code == 200
    events: dict[str, list] = {}
    current = None
    for line in r.text.splitlines():
        if line.startswith("event:"):
            current = line[6:].strip()
        elif line.startswith("data:") and current:
            import json as _json

            events.setdefault(current, []).append(_json.loads(line[5:]))
    assert "done" in events
    done = events["done"][0]
    assert "sources" in done and "message_id" in done


# --- blank / whitespace guards (regression) ----------------------------------
def test_whitespace_code_rejected_on_create(user_headers):
    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "   \n  "},
        headers=user_headers,
    )
    assert r.status_code == 422


def test_whitespace_message_rejected(user_headers):
    sid = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "   "},
        headers=user_headers,
    )
    assert r.status_code == 422
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "  \n "},
        headers=user_headers,
    )
    assert r.status_code == 422


def test_whitespace_explanation_rejected(user_headers):
    sid = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{sid}/explain",
        json={"explanation": "   "},
        headers=user_headers,
    )
    assert r.status_code == 422


# --- latest-code wins across edits -------------------------------------------
def test_sequential_edits_each_use_latest_code(user_headers):
    sid = _new_session(user_headers)
    for snippet in ("a = 1", "b = 2\nprint(b)", "c = 3\nprint(c + 1)"):
        r = client.post(
            f"/api/sessions/{sid}/messages",
            json={"content": "look again", "code": snippet},
            headers=user_headers,
        )
        assert r.status_code == 200, r.text
        detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
        assert detail["code"] == snippet


def test_stream_uses_explicit_code_snapshot(user_headers):
    sid = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{sid}/messages/stream",
        json={"content": "check this", "code": "s = 5\nprint(s)"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    assert detail["code"] == "s = 5\nprint(s)"


def test_starter_restore_roundtrip(user_headers):
    sid = _new_session(user_headers)
    starter = client.get(f"/api/sessions/{sid}", headers=user_headers).json()["code"]
    client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "edit", "code": "edited = True"},
        headers=user_headers,
    )
    assert client.get(f"/api/sessions/{sid}", headers=user_headers).json()["code"] == "edited = True"
    # Restoring = resubmitting the stashed starter code.
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "restore", "code": starter},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/api/sessions/{sid}", headers=user_headers).json()["code"] == starter


# --- retrieval contract -------------------------------------------------------
def test_retrieval_returns_only_matching_language_cards():
    from app.services.knowledge import CARDS, retrieve

    assert len(CARDS) == 18
    hits = retrieve("python", "What happens with an empty list and len()?")
    assert hits
    assert all(c.language in ("python", "general") for c in hits)
    assert retrieve("python", "hello") == []


def test_retrieval_is_topical_and_deduped():
    from app.services.knowledge import CARDS, retrieve

    # A zero-division question gets the exact exception reference, with
    # no near-blanket "python" title matches and no duplicate URLs.
    hits = retrieve("python", "Why does Python raise ZeroDivisionError when I divide by zero?")
    assert [c.id for c in hits] == ["py-empty"]
    assert hits[0].url.endswith("#ZeroDivisionError")

    # The two Python tutorial cards no longer share one generic URL.
    by_id = {c.id: c for c in CARDS}
    assert by_id["py-empty"].url != by_id["py-range"].url

    # Weak signals alone (a len() mention) still surface the empty-input
    # card, deduped by URL.
    hits2 = retrieve("python", "ok len numbers zero")
    assert any(c.id == "py-empty" for c in hits2)
    urls = [c.url for c in hits2]
    assert len(urls) == len(set(urls))


def test_stream_prompt_carries_anti_repeat_context():
    from app.services.orchestration import retrieve_for_turn, turn_context_block
    from app.mentor_prompts import stream_system_prompt

    cards = retrieve_for_turn(
        "python", "It averages 2,4,6.", "What happens to len(numbers) when empty?"
    )
    notes = turn_context_block(
        intent="answer",
        previous_question="What happens to len(numbers) when empty?",
        code_updated=False,
        resources=cards,
    )
    assert "Do not ask the same question again" in notes
    system = stream_system_prompt(
        language="python", code="x = 1", hints_left=3,
        references=__import__("app.services.knowledge", fromlist=["format_references"]).format_references(cards),
        turn_notes=notes,
    )
    assert "Do not ask the same question again" in system


def test_docs_simplify_returns_grounded_sources(user_headers, fake_llm):
    from tests.fake_llm import DOC_JSON

    fake_llm.queue_complete(DOC_JSON)
    r = client.post(
        "/api/docs/simplify",
        json={"text": "What is a list in Python and empty edge?", "language": "python"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert "sources" in r.json()


# --- citation persistence across resume/replay --------------------------------
def test_citations_persisted_in_meta_and_visible_on_resume(user_headers):
    sid = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "What happens with an empty list and len()?"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    live_sources = r.json()["sources"]
    assert live_sources, "expected retrieval hits for this query"
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    last = detail["messages"][-1]
    assert last["meta"]["sources"] == live_sources


def test_empty_citations_persist_as_empty_list(user_headers):
    sid = _new_session(user_headers)
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"content": "hello"},
        headers=user_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["sources"] == []
    detail = client.get(f"/api/sessions/{sid}", headers=user_headers).json()
    assert detail["messages"][-1]["meta"]["sources"] == []
