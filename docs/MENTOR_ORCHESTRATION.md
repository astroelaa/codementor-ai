# Mentor Orchestration

How a Socratic turn is produced. Source of truth is `backend/app/routers/mentor.py`
plus `backend/app/services/orchestration.py` and `backend/app/mentor_prompts.py`.
All claims below are verified by `backend/tests/test_orchestration.py` (27 tests)
and the full suite (`python -m pytest -q` → 119 passed).

## Flow (one turn)

1. **Validate + authorize.** `_load_session()` enforces owner-only access
   (user id match, or guest-token match; else 403/404). `_require_active()`
   rejects solved sessions with 409. Whitespace-only session code, message
   content, and explanations are rejected with 422 (regression-tested).
2. **Prepare (`_prepare_turn()`).** Single deterministic setup, used by
   `POST messages`, `POST messages/stream`, `POST hints`, and `POST explain`
   (explain only reuses the code-snapshot part):
   - `classify_intent()`: rule-based only (greeting → hint → explanation →
     code-fence → 2+ code lines → trailing `?` → answer; empty/symbol-only →
     unclear). No model call.
   - `previous_assistant_message()`: most recent assistant message = the last
     question asked. Surfaced explicitly so the next reply can be evaluated
     against it.
   - Code snapshot: explicit `code` field wins when non-blank and different
     from `session.code`; else a fenced block in `content` wins; else the
     stored code is kept. Whitespace-only snapshots never overwrite. Updates
     persist via the caller's commit *before* generation, so every request
     uses the latest submitted code (verified across sequential edits).
   - `retrieve_for_turn()` + `format_references()` + `turn_context_block()`:
     approved references and a short deterministic context block (intent,
     previous question, code-updated flag, resource-use rules).
3. **Prompt.** `chat_system_prompt()` (JSON), `hint_system_prompt()` (JSON),
   or `stream_system_prompt()` (prose + separate meta scoring call). All take
   `references` + `turn_notes`. Shared hard rules: one suspicious area + one
   question; never show fixed code or fences; acknowledge sound reasoning;
   hints only on request with budget; greeting rule; references grounded-only.
4. **Generate + validate.** `LLMManager.complete()` tries keyed providers in
   order, one attempt each, then falls back. `parse_feedback()` extracts the
   JSON object and `MentorFeedback` (Pydantic) validates it, including the
   `evaluation` object (`verdict`, `assessed_reasoning`, `missing_concept`).
   Parse failure → HTTP 502. Streaming variant streams prose tokens first,
   then runs `meta_system_prompt()` to score the turn; the stored reply is
   the streamed text.
5. **Anti-repetition (non-streaming only).** If a previous question exists,
   intent is `answer`/`explanation_request`/`question`, and
   `is_repeat(new, old)` (normalized similarity ≥ 0.82 or containment of a
   ≥20-char string) is true, the router retries **exactly once** with a
   corrective nudge naming the previous question. Bounded: 2 calls on repeat,
   1 otherwise (tested). Streaming has prompt-level protection only
   (`turn_notes` carries the do-not-repeat instruction into
   `stream_system_prompt`); already-emitted tokens cannot be retried, so no
   second call is made there. See Limitations.
6. **Persist.** `_persist_assistant_turn()` stores the assistant message with
   `meta = {provider, understanding_score, misconception, hint, usage,
   evaluation, sources}` (sanitized `{title, url}` snapshot of that turn's
   retrieval, so resume/replay can show citations; older rows without the key
   read back as `[]` — no migration needed), plus misconception/skill/activity
   rows for signed-in users. Hint turns additionally increment `hints_used`
   and store a `Hint` row. Responses return `sources[]` (from retrieval only)
   alongside the reply.

## Evaluation contract

`EvaluationOut.verdict`: `correct | partially_correct | incorrect |
off_target | unclear | greeting`. It assesses the student's *latest* message
against the previously asked question. It is validated, stored in
`message.meta.evaluation`, and used for anti-repetition — it is not shown to
the student as a grade. The prompt requires `partially_correct` (with
`missing_concept`) when only part of an answer is right — this is what fixes
the original `average([])` failure where a partial answer ("it averages
2,4,6") was ignored and the same question repeated.

## Root cause of the repeated-question failure

The old path built the system prompt from code + history only. Nothing told
the model what it had just asked, nothing asked it to evaluate the student's
latest message, and nothing detected a verbatim/rephrased repeat. A partial
answer therefore produced the same question again. The fix: surface the
previous question deterministically, require an `evaluation` verdict against
it, add an explicit do-not-repeat rule, and retry once on detected repeat.

## Intent table (tested)

| Input example | Intent | Effect |
|---|---|---|
| `hello`, `good morning` | greeting | Greeting rule in prompt; no retry |
| `give me a hint`, `I'm stuck` | hint_request | Hint-budget rule |
| `explain this`, `I don't understand` | explanation_request | May explain (≤120 words) + check question; retry eligible |
| fenced code / 2+ code lines | code_change | Code-updated flag in prompt |
| trailing `?` | question | Answer briefly + reconnect; retry eligible |
| anything else substantive | answer | Evaluated vs previous question; retry eligible |
| blank / `??` | unclear | Treated as confusion; greeting-adjacent handling |

## Limitations (honest)

- Streaming turns do not retry on repeat (tokens already sent). Protection is
  prompt-level only. (Verified live: streaming still asks grounded follow-ups;
  anti-repetition retry remains non-streaming only.)
- `sources[]` are persisted in `message.meta.sources` and shown on resume
  (`Workspace.tsx`) and replay (`History.tsx`); rows written before this change
  lack the key and read back as `[]`.
- Intent is heuristic (regex + line counts); off-topic detection relies on
  the model's `evaluation.verdict = off_target`, not the router.
- `previous_assistant_message()` trusts the latest assistant row, including
  hint/explain-follow-up rows.
- No code is ever executed; the mentor reasons about the supplied text only.
