"""Mentor routes: debugging sessions, Socratic turns, hints, solve flow."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.deps import guest_token_from, new_guest_token
from app.errors import llm_error_to_http
from app.llm.errors import LLMError
from app.llm.manager import LLMManager
from app.mentor_prompts import (
    chat_system_prompt,
    hint_system_prompt,
    judge_system_prompt,
    meta_system_prompt,
    stream_system_prompt,
)
from app.models import Hint, Message, Misconception, Project, Session as DebugSession, User
from app.rate_limit import limit
from app.schemas import (
    BadgeResponse,
    ChatMessageResponse,
    EvaluationOut,
    ExplainFeedback,
    ExplainRequest,
    ExplainResponse,
    HintRequest,
    MentorFeedback,
    MentorMessageResponse,
    MessageCreate,
    MisconceptionOut,
    SessionBase,
    SessionCreate,
    SessionDetailResponse,
    SourceRef,
    UsageInfo,
)
from app.services.detect import detect_language
from app.services.email import EmailBackend, get_email_backend, solve_congrats_email
from app.services.knowledge import citations, format_references
from app.services.memory import build_project_context, build_session_recap
from app.services.mentor import (
    PROVIDER_RETRY_KINDS,
    build_history,
    complete_with_retry,
    extract_json_dict,
    parse_feedback,
)
from app.services.orchestration import (
    RETRY_ELIGIBLE_INTENTS,
    classify_intent,
    compose_deterministic_reply,
    extract_code_block,
    is_repeat,
    previous_assistant_message,
    previous_question_message,
    retrieve_for_turn,
    turn_context_block,
)
from app.services.progress import (
    award_badge,
    award_on_solve,
    bump_skill,
    ensure_reference_data,
    record_activity,
)

router = APIRouter(prefix="/api", tags=["mentor"])

GUEST_SESSION_LIMIT = 1


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _hints_left(settings, session: DebugSession) -> int:
    return max(0, settings.max_hints_per_session - session.hints_used)


def _load_session(
    db: DbSession,
    session_id: str,
    *,
    user: User | None,
    guest_token: str | None,
) -> DebugSession:
    session = db.query(DebugSession).filter(DebugSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if user is not None:
        if session.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not your session.")
        return session
    if not guest_token or session.guest_token != guest_token:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def _require_active(session: DebugSession) -> None:
    if session.status != "active":
        raise HTTPException(
            status_code=409,
            detail="This session is already solved. Start a new session to keep practising.",
        )


def _session_base(
    session: DebugSession, *, guest_token: str | None, badges=()
) -> SessionBase:
    return SessionBase(
        id=session.id,
        language=session.language,
        goal=session.goal,
        project_id=session.project_id,
        mode=session.mode,
        code=session.code,
        status=session.status,
        understanding_score=session.understanding_score,
        hints_left=0,  # filled in by callers that know the settings
        created_at=session.created_at,
        updated_at=session.updated_at,
        solved_at=session.solved_at,
        guest_token=guest_token if session.user_id is None else None,
        badges_earned=list(badges),
    )


def _session_detail(
    request: Request,
    session: DebugSession,
    *,
    guest_token: str | None,
    badges=(),
) -> SessionDetailResponse:
    settings = request.app.state.settings
    base = _session_base(session, guest_token=guest_token, badges=badges)
    base.hints_left = _hints_left(settings, session)
    return SessionDetailResponse(
        **base.model_dump(),
        messages=[
            ChatMessageResponse.model_validate(m) for m in session.messages
        ],
    )


def _memory_context(
    db: DbSession, session: DebugSession
) -> tuple[str, str]:
    """Recap + linked-project context actually sent to the model."""
    recap = build_session_recap(session, len(session.messages))
    project_context = build_project_context(db, session)
    return recap, project_context


def _prepare_turn(
    db: DbSession, session: DebugSession, content: str, explicit_code: str | None
) -> dict:
    """One orchestrated turn setup: intent, code snapshot, context, refs.

    Mutates session.code when newer code arrives (persisted by the caller's
    commit). Returns everything prompt builders and _mentor_reply need.
    """
    intent = classify_intent(content)
    prev = previous_assistant_message(session)
    prev_q = prev.content if prev else None
    standing = previous_question_message(session)
    if standing is not None:
        # Questionless deterministic pushes must not blank the standing
        # question the model evaluates the student's message against.
        prev_q = standing.content
    new_code: str | None = None
    if explicit_code and explicit_code.strip() and explicit_code.strip() != session.code:
        new_code = explicit_code.strip()[:8000]
    else:
        block = extract_code_block(content)
        if block and block != session.code:
            new_code = block[:8000]
    code_updated = False
    if new_code:
        session.code = new_code
        code_updated = True
    # Social turns never carry references: sources attached to a plain
    # hello read as broken citations.
    cards = (
        []
        if intent in ("greeting", "frustration")
        else retrieve_for_turn(session.language, content, prev_q)
    )
    turn_notes = turn_context_block(
        intent=intent,
        previous_question=prev_q,
        code_updated=code_updated,
        resources=cards,
        student_text=content,
    )
    return {
        "intent": intent,
        "previous_question": prev_q,
        "turn_notes": turn_notes,
        "references": format_references(cards),
        "cites": citations(cards),
        "code_updated": code_updated,
    }


def _misconception_out(m: Misconception | None) -> MisconceptionOut | None:
    if m is None:
        return None
    return MisconceptionOut(type=m.type, description=m.description)


def _to_usage_info(usage: dict | None) -> UsageInfo | None:
    if not usage:
        return None
    try:
        return UsageInfo(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
    except Exception:
        return None


def _persist_assistant_turn(
    db: DbSession,
    session: DebugSession,
    user: User | None,
    feedback: MentorFeedback,
    *,
    provider: str,
    is_hint: bool,
    usage: dict | None = None,
    sources: list[dict] | None = None,
) -> tuple[Message, Misconception | None]:
    session.understanding_score = feedback.understanding_score
    stored_misc: Misconception | None = None
    if feedback.misconception is not None:
        stored_misc = Misconception(
            session_id=session.id,
            user_id=user.id if user else None,
            type=feedback.misconception.type.strip()[:64],
            description=feedback.misconception.description.strip(),
        )
        db.add(stored_misc)
    # Persisted citations: sanitized snapshot of the retrieval for this turn
    # so resume/replay can show them. Free-form JSON meta needs no migration;
    # older rows simply lack the key and read back as [].
    stored_sources = [
        {"title": str(s.get("title", "")), "url": str(s.get("url", ""))}
        for s in (sources or [])
        if s.get("title") and s.get("url")
    ]
    message = Message(
        session_id=session.id,
        role="assistant",
        content=feedback.reply,
        meta={
            "provider": provider,
            "understanding_score": feedback.understanding_score,
            "misconception": (
                {"type": stored_misc.type, "description": stored_misc.description}
                if stored_misc
                else None
            ),
            "hint": is_hint,
            "usage": usage,
            "evaluation": (
                feedback.evaluation.model_dump() if feedback.evaluation else None
            ),
            "sources": stored_sources,
        },
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    if stored_misc is not None:
        db.refresh(stored_misc)
    if user is not None:
        record_activity(db, user.id, messages=1)
        if stored_misc is not None:
            bump_skill(db, user.id, stored_misc.type)
    return message, stored_misc


def _force_verdict(feedback: MentorFeedback, intent: str) -> None:
    """Deterministic assessment guards.

    A greeting is NEVER an answer and venting frustration is NEVER a
    correct solution, no matter what the model claims: the verdicts are
    forced to the honest values. The verdict is internal orchestration
    data, not a user-facing grade.
    """
    if intent == "greeting":
        if feedback.evaluation is None:
            feedback.evaluation = EvaluationOut()
        feedback.evaluation.verdict = "greeting"
    elif intent == "frustration":
        if feedback.evaluation is None:
            feedback.evaluation = EvaluationOut()
        feedback.evaluation.verdict = "off_target"


def _mentor_reply(
    *,
    db: DbSession,
    request: Request,
    session: DebugSession,
    user: User | None,
    manager: LLMManager,
    system: str,
    history: list[dict],
    is_hint: bool,
    intent: str = "answer",
    previous_question: str | None = None,
    sources: list[dict] | None = None,
) -> tuple[MentorMessageResponse, str]:
    settings = request.app.state.settings

    def _complete_once(sys_text: str):
        try:
            feedback, completion, provider = complete_with_retry(
                manager,
                system=sys_text,
                messages=history,
                temperature=0.4,
            )
        except LLMError as exc:
            if exc.kind == "parse":
                raise HTTPException(
                    status_code=502,
                    detail="The mentor returned an unusable response. Try again.",
                )
            raise llm_error_to_http(exc)
        _force_verdict(feedback, intent)
        return feedback, completion, provider

    feedback, completion, provider = _complete_once(system)
    # Anti-repetition: at most ONE retry with corrective context, never a loop.
    if (
        previous_question
        and intent in RETRY_ELIGIBLE_INTENTS
        and is_repeat(feedback.reply, previous_question)
    ):
        nudge = (
            system
            + "\n\nCORRECTION: the student just responded to your last question. "
            + f'Your previous question was: "{previous_question.strip()[:300]}" '
            + "Do not repeat it in the same or reworded form. First evaluate "
            + "their answer using the evaluation contract, then ask a "
            + "DIFFERENT follow-up question."
        )
        feedback, completion, provider = _complete_once(nudge)
    message, stored_misc = _persist_assistant_turn(
        db,
        session,
        user,
        feedback,
        provider=provider,
        is_hint=is_hint,
        usage=completion.usage,
        sources=sources,
    )
    cite_models = [
        SourceRef(title=s["title"], url=s["url"]) for s in (sources or [])
    ]
    return (
        MentorMessageResponse(
            reply=feedback.reply,
            understanding_score=feedback.understanding_score,
            hints_left=_hints_left(settings, session),
            misconception=_misconception_out(stored_misc),
            next_topics=feedback.next_topics,
            message_id=message.id,
            provider=provider,
            usage=_to_usage_info(completion.usage),
            sources=cite_models,
        ),
        provider,
    )


def _composed_turn_response(
    *,
    db: DbSession,
    request: Request,
    session: DebugSession,
    user: User | None,
    reply: str,
    verdict: str | None,
) -> MentorMessageResponse:
    """Deterministic-code turn: no model call, no assessment, no new area.

    Seen live: the model answered a greeting by praising the code and
    asking about a new area, and answered "Y" by re-asking the standing
    question reworded (or by returning unusable JSON). Composing these
    replies guarantees the mentoring move instead of hoping for it.
    """
    settings = request.app.state.settings
    feedback = MentorFeedback(
        reply=reply,
        understanding_score=session.understanding_score,
        next_topics=[],
        evaluation=EvaluationOut(verdict=verdict) if verdict else None,
    )
    message, _ = _persist_assistant_turn(
        db,
        session,
        user,
        feedback,
        provider="mentor",
        is_hint=False,
        usage=None,
        sources=[],
    )
    return MentorMessageResponse(
        reply=reply,
        understanding_score=feedback.understanding_score,
        hints_left=_hints_left(settings, session),
        misconception=None,
        next_topics=[],
        message_id=message.id,
        provider="mentor",
        usage=None,
        sources=[],
    )


@router.post(
    "/sessions",
    response_model=SessionDetailResponse,
    status_code=201,
    dependencies=[limit("mentor")],
)
def create_session(
    payload: SessionCreate,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User | None = Depends(deps.get_optional_user),
):
    ensure_reference_data(db)
    stripped_code = payload.code.strip()
    if not stripped_code:
        raise HTTPException(
            status_code=422,
            detail="Code must not be empty. Paste your code or load a sample.",
        )
    language = payload.language
    if language == "auto":
        language = detect_language(payload.code)
        if language == "unknown":
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not detect the language. "
                    "Select a language explicitly."
                ),
            )
    guest_token: str | None = None
    if user is None:
        guest_token = guest_token_from(request) or new_guest_token()
        used = (
            db.query(DebugSession)
            .filter(DebugSession.guest_token == guest_token)
            .count()
        )
        if used >= GUEST_SESSION_LIMIT:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Guest mode includes 1 free session, which this device "
                    "has used. Create a free account to continue."
                ),
            )
    session = DebugSession(
        id=str(uuid.uuid4()),
        user_id=user.id if user else None,
        guest_token=guest_token,
        language=language,
        goal=payload.goal,
        mode=payload.mode,
        code=stripped_code,
        status="active",
    )
    if payload.project_id:
        if user is None:
            raise HTTPException(
                status_code=422,
                detail="Linking a session to a project requires an account.",
            )
        project = (
            db.query(Project)
            .filter(Project.id == payload.project_id, Project.user_id == user.id)
            .first()
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        session.project_id = project.id
    db.add(session)
    db.commit()
    db.refresh(session)
    badges: list = []
    if user is not None:
        record_activity(db, user.id, sessions=1)
        first = award_badge(db, user.id, "first-session")
        if first is not None:
            badges.append(BadgeResponse.model_validate(first))
    return _session_detail(request, session, guest_token=guest_token, badges=badges)


@router.get("/sessions", response_model=list[SessionBase])
def list_sessions(
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User | None = Depends(deps.get_optional_user),
):
    settings = request.app.state.settings
    guest_token = guest_token_from(request)
    if user is not None:
        rows = (
            db.query(DebugSession)
            .filter(DebugSession.user_id == user.id)
            .order_by(DebugSession.updated_at.desc())
            .all()
        )
    elif guest_token:
        rows = (
            db.query(DebugSession)
            .filter(DebugSession.guest_token == guest_token)
            .order_by(DebugSession.updated_at.desc())
            .all()
        )
    else:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    result = []
    for row in rows:
        base = _session_base(row, guest_token=guest_token)
        base.hints_left = _hints_left(settings, row)
        result.append(base)
    return result


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(
    session_id: str,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User | None = Depends(deps.get_optional_user),
):
    session = _load_session(
        db, session_id, user=user, guest_token=guest_token_from(request)
    )
    return _session_detail(
        request, session, guest_token=guest_token_from(request)
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MentorMessageResponse,
    dependencies=[limit("mentor")],
)
def post_message(
    session_id: str,
    payload: MessageCreate,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User | None = Depends(deps.get_optional_user),
    manager: LLMManager = Depends(deps.get_llm_manager),
):
    settings = request.app.state.settings
    session = _load_session(
        db, session_id, user=user, guest_token=guest_token_from(request)
    )
    _require_active(session)
    if len(session.messages) >= settings.max_session_messages:
        raise HTTPException(
            status_code=409,
            detail="This session is getting long. Start a fresh session to continue.",
        )
    content = payload.content.strip()
    if not content:
        raise HTTPException(
            status_code=422,
            detail="Message must not be empty.",
        )
    turn = _prepare_turn(db, session, content, payload.code)
    db.add(
        Message(session_id=session.id, role="user", content=content)
    )
    db.commit()
    composed = compose_deterministic_reply(
        turn["intent"], content, turn["previous_question"], seed=len(session.messages)
    )
    if composed is not None:
        return _composed_turn_response(
            db=db,
            request=request,
            session=session,
            user=user,
            reply=composed,
            verdict="greeting" if turn["intent"] == "greeting" else None,
        )
    history = build_history(session.messages, settings.history_window)
    recap, project_context = _memory_context(db, session)
    system = chat_system_prompt(
        language=session.language,
        code=session.code,
        hints_left=_hints_left(settings, session),
        goal=session.goal,
        recap=recap,
        project_context=project_context,
        references=turn["references"],
        turn_notes=turn["turn_notes"],
    )
    response, _ = _mentor_reply(
        db=db,
        request=request,
        session=session,
        user=user,
        manager=manager,
        system=system,
        history=history,
        is_hint=False,
        intent=turn["intent"],
        previous_question=turn["previous_question"],
        sources=turn["cites"],
    )
    return response


@router.post(
    "/sessions/{session_id}/messages/stream",
    dependencies=[limit("mentor")],
)
def post_message_stream(
    session_id: str,
    payload: MessageCreate,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User | None = Depends(deps.get_optional_user),
    manager: LLMManager = Depends(deps.get_llm_manager),
):
    settings = request.app.state.settings
    session = _load_session(
        db, session_id, user=user, guest_token=guest_token_from(request)
    )
    _require_active(session)
    if len(session.messages) >= settings.max_session_messages:
        raise HTTPException(
            status_code=409,
            detail="This session is getting long. Start a fresh session to continue.",
        )
    content = payload.content.strip()
    if not content:
        raise HTTPException(
            status_code=422,
            detail="Message must not be empty.",
        )
    turn = _prepare_turn(db, session, content, payload.code)
    db.add(
        Message(session_id=session.id, role="user", content=content)
    )
    db.commit()
    history = build_history(session.messages, settings.history_window)
    recap, project_context = _memory_context(db, session)
    system = stream_system_prompt(
        language=session.language,
        code=session.code,
        hints_left=_hints_left(settings, session),
        goal=session.goal,
        recap=recap,
        project_context=project_context,
        references=turn["references"],
        turn_notes=turn["turn_notes"],
    )

    def event_stream():
        prev_q = turn["previous_question"]
        composed = compose_deterministic_reply(
            turn["intent"], content, prev_q, seed=len(session.messages)
        )
        if composed is not None:
            feedback = MentorFeedback(
                reply=composed,
                understanding_score=session.understanding_score,
                next_topics=[],
                evaluation=(
                    EvaluationOut(verdict="greeting")
                    if turn["intent"] == "greeting"
                    else None
                ),
            )
            try:
                message, _ = _persist_assistant_turn(
                    db,
                    session,
                    user,
                    feedback,
                    provider="mentor",
                    is_hint=False,
                    usage=None,
                    sources=[],
                )
            except Exception:
                db.rollback()
                yield _sse("error", {"detail": "Could not save the mentor reply."})
                return
            yield _sse("token", {"text": composed})
            yield _sse(
                "done",
                {
                    "reply": composed,
                    "understanding_score": feedback.understanding_score,
                    "hints_left": _hints_left(settings, session),
                    "misconception": None,
                    "next_topics": [],
                    "message_id": message.id,
                    "provider": "mentor",
                    "usage": None,
                    "sources": [],
                },
            )
            return
        eligible = bool(prev_q and turn["intent"] in RETRY_ELIGIBLE_INTENTS)
        # Buffer at least enough text to recognise a repeat of the previous
        # question before the first token is sent to the client.
        probe_len = min(max(140, len(prev_q or "") + 20), 420)
        nudge = None
        if eligible:
            nudge = (
                system
                + "\n\nCORRECTION: your last reply repeated an earlier "
                + f'question. Your previous question was: "{prev_q.strip()[:300]}" '
                + "Do not repeat it in the same or reworded form. First "
                + "evaluate the student's latest message, then ask a "
                + "DIFFERENT follow-up question, in plain text only (no JSON)."
            )

        reply_text = ""
        reason = None
        for attempt in range(2):
            # Second attempt reuses the plain system prompt for transient
            # failures, the corrective nudge for repeat/unusable output.
            sys_now = system
            if attempt == 1 and nudge and reason in ("repeat", "unusable"):
                sys_now = nudge
            try:
                provider, chunks = manager.stream(
                    system=sys_now, messages=history, temperature=0.4
                )
            except LLMError as exc:
                # One app-level retry only for kinds the manager does not
                # already retry itself (rate limits/timeouts wait-and-retry
                # inside LLMManager, so retrying again here would hammer).
                if attempt == 0 and exc.kind in PROVIDER_RETRY_KINDS:
                    reason = "transient"
                    continue
                yield _sse("error", {"detail": llm_error_to_http(exc).detail})
                return
            yield _sse("provider", {"provider": provider})
            buffer = ""
            mode = None
            emitted = False
            reuse_attempt = None
            try:
                for chunk in chunks:
                    buffer += chunk
                    if mode is None and buffer.strip():
                        head = buffer.lstrip()[0]
                        mode = (
                            "json" if head == "{"
                            else "fence" if head == "`"
                            else "text"
                        )
                    if mode == "text" and not emitted:
                        if not eligible:
                            # No previous question to guard against: stream live.
                            yield _sse("token", {"text": buffer})
                            emitted = True
                        elif len(buffer) >= probe_len:
                            if (
                                eligible
                                and attempt == 0
                                and is_repeat(buffer, prev_q)
                            ):
                                reuse_attempt = "repeat"
                                break
                            # Not a repeat (so far): start real streaming.
                            yield _sse("token", {"text": buffer})
                            emitted = True
                    elif mode == "text" and emitted:
                        yield _sse("token", {"text": chunk})
                    # json/fence output is buffered silently until the end.
            except LLMError as exc:
                yield _sse("error", {"detail": llm_error_to_http(exc).detail})
                return
            if reuse_attempt == "repeat":
                reason = "repeat"
                continue
            if mode in ("json", "fence"):
                # The model answered with the internal JSON envelope (or a
                # fence we cannot trust). Extract the user-facing reply;
                # if that fails it counts as an unusable, non-JSON reply.
                clean = ""
                try:
                    data = extract_json_dict(buffer)
                    if isinstance(data, dict):
                        clean = str(data.get("reply") or "").strip()[:3000]
                except LLMError:
                    clean = ""
                if not clean:
                    if attempt == 0:
                        reason = "unusable"
                        continue
                    yield _sse(
                        "error",
                        {
                            "detail": "The mentor returned an unusable "
                            "response. Try again."
                        },
                    )
                    return
                if eligible and attempt == 0 and is_repeat(clean, prev_q):
                    reason = "repeat"
                    continue
                reply_text = clean
                yield _sse("token", {"text": clean})
            else:
                if not emitted:
                    if eligible and attempt == 0 and is_repeat(buffer, prev_q):
                        reason = "repeat"
                        continue
                    if not buffer.strip():
                        if attempt == 0:
                            reason = "unusable"
                            continue
                        yield _sse(
                            "error",
                            {"detail": "The mentor returned an empty response."},
                        )
                        return
                    reply_text = buffer
                    yield _sse("token", {"text": buffer})
                else:
                    reply_text = buffer
            break
        if not reply_text:
            yield _sse(
                "error",
                {
                    "detail": "The mentor returned an unusable response. "
                    "Try again."
                },
            )
            return
        reply = reply_text
        try:
            meta_completion, _ = manager.complete(
                system=meta_system_prompt(),
                messages=history + [{"role": "assistant", "content": reply}],
                temperature=0.0,
            )
            feedback = parse_feedback(meta_completion.text)
            # The meta call only scores the turn; the visible reply is the
            # streamed text, never the meta placeholder.
            feedback.reply = reply
            meta_usage = meta_completion.usage
        except LLMError:
            feedback = MentorFeedback(
                reply=reply,
                understanding_score=session.understanding_score,
                next_topics=[],
            )
            meta_usage = None
        _force_verdict(feedback, turn["intent"])
        try:
            message, stored_misc = _persist_assistant_turn(
                db,
                session,
                user,
                feedback,
                provider=provider,
                is_hint=False,
                usage=meta_usage,
                sources=turn["cites"],
            )
        except Exception:
            db.rollback()
            yield _sse("error", {"detail": "Could not save the mentor reply."})
            return
        usage_info = _to_usage_info(meta_usage)
        yield _sse(
            "done",
            {
                "reply": feedback.reply,
                "understanding_score": feedback.understanding_score,
                "hints_left": _hints_left(settings, session),
                "misconception": (
                    {
                        "type": stored_misc.type,
                        "description": stored_misc.description,
                    }
                    if stored_misc
                    else None
                ),
                "next_topics": feedback.next_topics,
                "message_id": message.id,
                "provider": provider,
                "usage": usage_info.model_dump() if usage_info else None,
                "sources": turn["cites"],
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/sessions/{session_id}/hints",
    response_model=MentorMessageResponse,
    dependencies=[limit("mentor")],
)
def request_hint(
    session_id: str,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User | None = Depends(deps.get_optional_user),
    manager: LLMManager = Depends(deps.get_llm_manager),
    payload: HintRequest | None = None,
):
    settings = request.app.state.settings
    session = _load_session(
        db, session_id, user=user, guest_token=guest_token_from(request)
    )
    _require_active(session)
    if session.hints_used >= settings.max_hints_per_session:
        raise HTTPException(
            status_code=403,
            detail="No hints left in this session. Reason it out.",
        )
    hint_code = (payload.code if payload and payload.code else "").strip() or None
    turn = _prepare_turn(
        db, session, "I am stuck. Give me a hint, not the answer.", hint_code
    )
    db.add(
        Message(
            session_id=session.id,
            role="user",
            content="I am stuck. Give me a hint, not the answer.",
        )
    )
    db.commit()
    history = build_history(session.messages, settings.history_window)
    recap, project_context = _memory_context(db, session)
    system = hint_system_prompt(
        language=session.language,
        code=session.code,
        hints_left=_hints_left(settings, session) - 1,
        goal=session.goal,
        recap=recap,
        project_context=project_context,
        references=turn["references"],
        turn_notes=turn["turn_notes"],
    )
    response, _ = _mentor_reply(
        db=db,
        request=request,
        session=session,
        user=user,
        manager=manager,
        system=system,
        history=history,
        is_hint=True,
        intent=turn["intent"],
        previous_question=turn["previous_question"],
        sources=turn["cites"],
    )
    session.hints_used += 1
    db.add(Hint(session_id=session.id, content=response.reply))
    db.commit()
    response.hints_left = _hints_left(settings, session)
    return response


@router.post(
    "/sessions/{session_id}/explain",
    response_model=ExplainResponse,
    dependencies=[limit("mentor")],
)
def submit_explanation(
    session_id: str,
    payload: ExplainRequest,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User | None = Depends(deps.get_optional_user),
    manager: LLMManager = Depends(deps.get_llm_manager),
    mailer: EmailBackend = Depends(get_email_backend),
):
    settings = request.app.state.settings
    session = _load_session(
        db, session_id, user=user, guest_token=guest_token_from(request)
    )
    _require_active(session)
    explanation = payload.explanation.strip()
    if not explanation:
        raise HTTPException(
            status_code=422,
            detail="Explanation must not be empty.",
        )
    if payload.code and payload.code.strip() and payload.code.strip() != session.code:
        session.code = payload.code.strip()[:8000]
    db.add(
        Message(
            session_id=session.id,
            role="user",
            content=f"My explanation of the fix: {explanation}",
        )
    )
    db.commit()
    history = build_history(session.messages, settings.history_window)
    system = judge_system_prompt(language=session.language, code=session.code)

    def _parse_judge(raw: str) -> ExplainFeedback:
        return ExplainFeedback.model_validate(extract_json_dict(raw))

    try:
        judged, completion, provider = complete_with_retry(
            manager,
            system=system,
            messages=history,
            temperature=0.0,
            parse=_parse_judge,
        )
    except LLMError as exc:
        if exc.kind == "parse":
            raise HTTPException(
                status_code=502,
                detail="The mentor returned an unusable response. Try again.",
            )
        raise llm_error_to_http(exc)

    reply = judged.feedback.strip()
    if judged.follow_up_question.strip():
        reply = f"{reply} {judged.follow_up_question.strip()}".strip()

    badges: list = []
    if judged.passed:
        session.status = "solved"
        session.solved_at = datetime.now(timezone.utc)
        session.understanding_score = max(
            session.understanding_score, judged.score
        )
        if user is not None:
            from app.services.notifications import notify

            record_activity(db, user.id, messages=1)
            earned = award_on_solve(db, user, session)
            badges = [BadgeResponse.model_validate(b) for b in earned]
            notify(
                db,
                user.id,
                "solve",
                "Session solved",
                f"You explained the fix in your own words (score {judged.score}).",
            )
            if user.notify_progress_emails:
                try:
                    mailer.send(
                        solve_congrats_email(
                            user.email, session.language, judged.score
                        )
                    )
                except Exception:
                    pass  # email is best-effort; the solve already persisted

    db.add(
        Message(
            session_id=session.id,
            role="assistant",
            content=reply or "Noted.",
            meta={
                "provider": provider,
                "explanation_score": judged.score,
                "passed": judged.passed,
                "solve_check": True,
                "usage": completion.usage,
            },
        )
    )
    db.commit()

    return ExplainResponse(
        passed=judged.passed,
        score=judged.score,
        feedback=judged.feedback,
        reply=reply or "Noted.",
        understanding_score=session.understanding_score,
        hints_left=_hints_left(settings, session),
        badges_earned=badges,
        usage=_to_usage_info(completion.usage),
    )
