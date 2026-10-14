"""Pydantic schemas: request validation and response shapes."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Auth -----------------------------------------------------------------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordBody(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    theme: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=120)
    theme: Optional[str] = Field(default=None, pattern="^(dark|light)$")


# --- Mentor ---------------------------------------------------------------
Language = Literal[
    "python", "javascript", "typescript", "java", "cpp", "csharp", "go", "sql"
]


class SessionCreate(BaseModel):
    # "auto" detects the language server-side; explicit values always win.
    language: Literal[
        "python",
        "javascript",
        "typescript",
        "java",
        "cpp",
        "csharp",
        "go",
        "sql",
        "auto",
    ] = "auto"
    code: str = Field(min_length=1, max_length=8000)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ExplainRequest(BaseModel):
    explanation: str = Field(min_length=1, max_length=4000)


class MisconceptionIn(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=500)


def _clamp_score(value) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


class MentorFeedback(BaseModel):
    """Structured analysis the model returns for every turn."""

    reply: str = Field(min_length=1, max_length=3000)
    understanding_score: int = 0
    misconception: Optional[MisconceptionIn] = None
    next_topics: list[str] = Field(default_factory=list)

    _clamp = field_validator("understanding_score", mode="before")(_clamp_score)

    @field_validator("next_topics", mode="before")
    @classmethod
    def _normalise_topics(cls, value):
        if not isinstance(value, list):
            return []
        return [str(t).strip() for t in value if str(t).strip()][:5]


class ExplainFeedback(BaseModel):
    passed: bool = False
    score: int = 0
    feedback: str = ""
    follow_up_question: str = ""

    _clamp = field_validator("score", mode="before")(_clamp_score)


class BadgeResponse(BaseModel):
    slug: str
    name: str
    description: str
    icon: str

    model_config = {"from_attributes": True}


class MisconceptionOut(BaseModel):
    type: str
    description: str


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    meta: Optional[dict] = None

    model_config = {"from_attributes": True}


class SessionBase(BaseModel):
    id: str
    language: str
    code: str
    status: str
    understanding_score: int
    hints_left: int = 0
    created_at: datetime
    updated_at: datetime
    solved_at: Optional[datetime] = None
    guest_token: Optional[str] = None
    badges_earned: list[BadgeResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionBase):
    messages: list[ChatMessageResponse] = Field(default_factory=list)


class MentorMessageResponse(BaseModel):
    reply: str
    understanding_score: int
    hints_left: int
    misconception: Optional[MisconceptionOut] = None
    next_topics: list[str] = Field(default_factory=list)
    message_id: str
    provider: str


class ExplainResponse(BaseModel):
    passed: bool
    score: int
    feedback: str
    reply: str
    understanding_score: int
    hints_left: int
    badges_earned: list[BadgeResponse] = Field(default_factory=list)


class SnippetResponse(BaseModel):
    language: str
    title: str
    description: str
    code: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    providers_configured: list[str]


# --- Dashboard / learning ---------------------------------------------------
class SessionSummary(BaseModel):
    id: str
    language: str
    status: str
    understanding_score: int
    message_count: int
    updated_at: datetime


class LanguageStat(BaseModel):
    language: str
    sessions: int


class WeakSpot(BaseModel):
    type: str
    count: int


class DashboardResponse(BaseModel):
    total_sessions: int
    solved_sessions: int
    streak_days: int
    avg_understanding: int
    languages: list[LanguageStat] = Field(default_factory=list)
    weak_spots: list[WeakSpot] = Field(default_factory=list)
    badges: list[BadgeResponse] = Field(default_factory=list)
    recent_sessions: list[SessionSummary] = Field(default_factory=list)


class SkillProgressResponse(BaseModel):
    slug: str
    name: str
    encounters: int
    score: int


class PathItemResponse(BaseModel):
    id: str
    title: str
    detail: str
    status: str
    position: int

    model_config = {"from_attributes": True}


class PathItemUpdate(BaseModel):
    status: Literal["todo", "doing", "done"]


class LearningPathResponse(BaseModel):
    id: str
    title: str
    source: str  # "weak-spots" | "starter" — generated picks, not measured progress
    is_active: bool
    created_at: datetime
    items: list[PathItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# --- Documentation simplifier ----------------------------------------------
class DocSimplifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="", max_length=32)


class DocSimplifyResponse(BaseModel):
    id: str
    explanation: str
    example: str
    question: str
    created_at: datetime


class DocHistoryItem(BaseModel):
    id: str
    language: str
    input_text: str
    explanation: str
    example: str
    question: str
    created_at: datetime

    model_config = {"from_attributes": True}
