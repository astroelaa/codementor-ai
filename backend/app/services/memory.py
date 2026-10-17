"""Explicit, inspectable learning memory (no silent inference).

Three layers, all derived from stored rows the user can already see:
1. Session recap: deterministic summary injected when history is long.
2. Project context: brief + current task for linked sessions.
3. Long-term weak spots + misconception records, readable and deletable
   through /api/memory. Nothing is inferred beyond what is stored.
"""

from sqlalchemy.orm import Session as DbSession

from app.models import Project, Session as DebugSession


def build_session_recap(session: DebugSession, message_count: int) -> str:
    misc = sorted({m.type for m in session.misconceptions}) if session.misconceptions else []
    last_question = ""
    for message in reversed(session.messages):
        if message.role == "assistant" and message.content.strip():
            last_question = message.content.strip()[-220:]
            break
    parts = [
        f"Session recap ({session.language}, goal {session.goal}, "
        f"score {session.understanding_score}, {message_count} messages, "
        f"hints used {session.hints_used}/3).",
    ]
    if misc:
        parts.append("Misconceptions raised so far: " + ", ".join(misc) + ".")
    if last_question:
        parts.append("Latest open question: " + last_question)
    return " ".join(parts)


def build_project_context(db: DbSession, session: DebugSession) -> str:
    """Brief + current task for a linked session. Empty when unlinked."""
    if not session.project_id:
        return ""
    project = (
        db.query(Project)
        .filter(
            Project.id == session.project_id,
            Project.user_id == session.user_id,
        )
        .first()
    )
    if project is None:
        return ""
    current = None
    for milestone in sorted(project.milestones, key=lambda m: m.position):
        if milestone.status == "done":
            continue
        for task in sorted(milestone.tasks, key=lambda t: t.position):
            if task.status != "done":
                current = (milestone.title, task.title)
                break
        if current:
            break
    parts = [f"Project '{project.title}' ({project.language})."]
    if project.objective:
        parts.append("Objective: " + project.objective.strip()[:500])
    if project.architecture:
        parts.append("Architecture: " + project.architecture.strip()[:300])
    if current:
        parts.append(
            f"Current task: '{current[1]}' (milestone '{current[0]}'). "
            "Relate guidance to this task where relevant."
        )
    return " ".join(parts)
