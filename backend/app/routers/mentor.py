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
from app.models import Hint, Message, Misconception, Session as DebugSession, User
from app.rate_limit import limit
from app.schemas import (
    BadgeResponse,
    ChatMessageResponse,
    ExplainFeedback,
    ExplainRequest,
    ExplainResponse,
    MentorFeedback,
    MentorMessageResponse,
    MessageCreate,
    MisconceptionOut,
    SessionBase,
    SessionCreate,
    SessionDetailResponse,
)
from app.services.detect import detect_language
from app.services.mentor import build_history, extract_json_dict, parse_feedback
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


def _misconception_out(m: Misconception | None) -> MisconceptionOut | None:
    if m is None:
        return None
    return MisconceptionOut(type=m.type, description=m.description)


def _persist_assistant_turn(
    db: DbSession,
    session: DebugSession,
    user: User | None,
    feedback: MentorFeedback,
    *,
    provider: str,
    is_hint: bool,
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
) -> tuple[MentorMessageResponse, str]:
    settings = request.app.state.settings
    try:
        raw, provider = manager.complete(
            system=system, messages=history, temperature=0.4
        )
    except LLMError as exc:
        raise llm_error_to_http(exc)
    try:
        feedback = parse_feedback(raw)
    except LLMError:
        raise HTTPException(
            status_code=502,
            detail="The mentor returned an unusable response. Try again.",
        )
    message, stored_misc = _persist_assistant_turn(
        db, session, user, feedback, provider=provider, is_hint=is_hint
    )
    return (
        MentorMessageResponse(
            reply=feedback.reply,
            understanding_score=feedback.understanding_score,
            hints_left=_hints_left(settings, session),
            misconception=_misconception_out(stored_misc),
            next_topics=feedback.next_topics,
            message_id=message.id,
            provider=provider,
        ),
        provider,
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
        code=payload.code.strip(),
        status="active",
    )
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
    db.add(
        Message(session_id=session.id, role="user", content=payload.content.strip())
    )
    db.commit()
    history = build_history(session.messages, settings.history_window)
    system = chat_system_prompt(
        language=session.language,
        code=session.code,
        hints_left=_hints_left(settings, session),
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
    db.add(
        Message(session_id=session.id, role="user", content=payload.content.strip())
    )
    db.commit()
    history = build_history(session.messages, settings.history_window)
    system = stream_system_prompt(
        language=session.language,
        code=session.code,
        hints_left=_hints_left(settings, session),
    )

    def event_stream():
        try:
            provider, chunks = manager.stream(
                system=system, messages=history, temperature=0.4
            )
        except LLMError as exc:
            yield _sse("error", {"detail": llm_error_to_http(exc).detail})
            return
        yield _sse("provider", {"provider": provider})
        parts: list[str] = []
        try:
            for chunk in chunks:
                parts.append(chunk)
                yield _sse("token", {"text": chunk})
        except LLMError as exc:
            yield _sse("error", {"detail": llm_error_to_http(exc).detail})
            return
        reply = "".join(parts).strip()
        if not reply:
            yield _sse("error", {"detail": "The mentor returned an empty response."})
            return
        try:
            meta_raw, _ = manager.complete(
                system=meta_system_prompt(),
                messages=history + [{"role": "assistant", "content": reply}],
                temperature=0.0,
            )
            feedback = parse_feedback(meta_raw)
            # The meta call only scores the turn; the visible reply is the
            # streamed text, never the meta placeholder.
            feedback.reply = reply
        except LLMError:
            feedback = MentorFeedback(
                reply=reply,
                understanding_score=session.understanding_score,
                next_topics=[],
            )
        try:
            message, stored_misc = _persist_assistant_turn(
                db, session, user, feedback, provider=provider, is_hint=False
            )
        except Exception:
            db.rollback()
            yield _sse("error", {"detail": "Could not save the mentor reply."})
            return
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
    db.add(
        Message(
            session_id=session.id,
            role="user",
            content="I am stuck. Give me a hint, not the answer.",
        )
    )
    db.commit()
    history = build_history(session.messages, settings.history_window)
    system = hint_system_prompt(
        language=session.language,
        code=session.code,
        hints_left=_hints_left(settings, session) - 1,
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
):
    settings = request.app.state.settings
    session = _load_session(
        db, session_id, user=user, guest_token=guest_token_from(request)
    )
    _require_active(session)
    db.add(
        Message(
            session_id=session.id,
            role="user",
            content=f"My explanation of the fix: {payload.explanation.strip()}",
        )
    )
    db.commit()
    history = build_history(session.messages, settings.history_window)
    system = judge_system_prompt(language=session.language, code=session.code)
    try:
        raw, provider = manager.complete(
            system=system, messages=history, temperature=0.0
        )
    except LLMError as exc:
        raise llm_error_to_http(exc)
    try:
        judged = ExplainFeedback.model_validate(extract_json_dict(raw))
    except LLMError:
        raise HTTPException(
            status_code=502,
            detail="The mentor returned an unusable response. Try again.",
        )

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
            record_activity(db, user.id, messages=1)
            earned = award_on_solve(db, user, session)
            badges = [BadgeResponse.model_validate(b) for b in earned]

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
    )
