"""Documentation simplifier: plain-language explanations of pasted text.

Text in, structured explanation out. No URL fetching: only user-pasted text
is accepted, so there is no server-side request surface to protect.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.errors import llm_error_to_http
from app.llm.errors import LLMError
from app.llm.manager import LLMManager
from app.mentor_prompts import simplify_system_prompt
from app.models import DocSimplification, User
from app.rate_limit import limit
from app.schemas import (
    DocHistoryItem,
    DocSimplifyRequest,
    DocSimplifyResponse,
)
from app.services.mentor import extract_json_dict


class _DocFeedback(BaseModel):
    explanation: str = Field(min_length=1, max_length=3000)
    example: str = Field(default="", max_length=1500)
    question: str = Field(default="", max_length=500)


router = APIRouter(prefix="/api/docs", tags=["docs"])


@router.post(
    "/simplify",
    response_model=DocSimplifyResponse,
    dependencies=[limit("mentor")],
)
def simplify(
    payload: DocSimplifyRequest,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
    manager: LLMManager = Depends(deps.get_llm_manager),
):
    try:
        completion, _ = manager.complete(
            system=simplify_system_prompt(language=payload.language.strip()),
            messages=[{"role": "user", "content": payload.text.strip()}],
            temperature=0.3,
        )
    except LLMError as exc:
        raise llm_error_to_http(exc)
    try:
        data = extract_json_dict(completion.text)
        feedback = _DocFeedback.model_validate(data)
    except (LLMError, Exception):
        raise HTTPException(
            status_code=502,
            detail="The simplifier returned an unusable response. Try again.",
        )
    record = DocSimplification(
        user_id=user.id,
        language=payload.language.strip()[:32],
        input_text=payload.text.strip(),
        explanation=feedback.explanation,
        example=feedback.example,
        question=feedback.question,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return DocSimplifyResponse(
        id=record.id,
        explanation=record.explanation,
        example=record.example,
        question=record.question,
        created_at=record.created_at,
    )


@router.get("/history", response_model=list[DocHistoryItem])
def history(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    rows = (
        db.query(DocSimplification)
        .filter(DocSimplification.user_id == user.id)
        .order_by(DocSimplification.created_at.desc())
        .limit(50)
        .all()
    )
    return [DocHistoryItem.model_validate(r) for r in rows]
