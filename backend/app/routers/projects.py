"""Project briefs, milestones, and tasks. Authenticated users only.

Projects belong to exactly one user; every nested read or write verifies
ownership through joins, so IDs from another user behave as not-found.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from app import deps
from app.errors import llm_error_to_http
from app.llm.errors import LLMError
from app.llm.manager import LLMManager
from app.mentor_prompts import brief_system_prompt
from app.models import Milestone, Project, ProjectTask, User
from app.rate_limit import limit
from app.schemas import (
    BriefRequest,
    BriefResponse,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    NextTaskResponse,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectSummary,
    ProjectUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.languages import get_language
from app.services.mentor import extract_json_dict

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_project(db: DbSession, project_id: str, user: User) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _check_language(language: str) -> str:
    if get_language(language) is None:
        raise HTTPException(
            status_code=422,
            detail="Unknown language. Pick a supported language.",
        )
    return language


def _milestone_response(m: Milestone) -> MilestoneResponse:
    return MilestoneResponse(
        id=m.id,
        title=m.title,
        detail=m.detail,
        status=m.status,
        position=m.position,
        tasks=[
            TaskResponse(
                id=t.id,
                title=t.title,
                detail=t.detail,
                status=t.status,
                position=t.position,
            )
            for t in m.tasks
        ],
    )


def _detail_response(p: Project) -> ProjectDetailResponse:
    return ProjectDetailResponse(
        id=p.id,
        title=p.title,
        objective=p.objective,
        language=p.language,
        stack=p.stack,
        architecture=p.architecture,
        status=p.status,
        created_at=p.created_at,
        updated_at=p.updated_at,
        milestones=[_milestone_response(m) for m in p.milestones],
    )


@router.post("", response_model=ProjectDetailResponse, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    project = Project(
        user_id=user.id,
        title=payload.title.strip(),
        objective=payload.objective.strip(),
        language=_check_language(payload.language.strip() or "python"),
        stack=payload.stack.strip(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _detail_response(project)


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    rows = (
        db.query(Project)
        .filter(Project.user_id == user.id)
        .order_by(Project.updated_at.desc())
        .all()
    )
    result = []
    for p in rows:
        open_tasks = sum(
            1
            for m in p.milestones
            for t in m.tasks
            if t.status != "done"
        )
        result.append(
            ProjectSummary(
                id=p.id,
                title=p.title,
                language=p.language,
                status=p.status,
                milestone_count=len(p.milestones),
                open_task_count=open_tasks,
                updated_at=p.updated_at,
            )
        )
    return result


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: str,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    return _detail_response(_get_project(db, project_id, user))


@router.patch("/{project_id}", response_model=ProjectDetailResponse)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    project = _get_project(db, project_id, user)
    if payload.title is not None:
        project.title = payload.title.strip()
    if payload.objective is not None:
        project.objective = payload.objective.strip()
    if payload.language is not None:
        project.language = _check_language(payload.language.strip())
    if payload.stack is not None:
        project.stack = payload.stack.strip()
    if payload.architecture is not None:
        project.architecture = payload.architecture.strip()
    if payload.status is not None:
        project.status = payload.status
    db.commit()
    db.refresh(project)
    return _detail_response(project)


@router.post(
    "/{project_id}/brief",
    response_model=BriefResponse,
    dependencies=[limit("mentor")],
)
def generate_brief(
    project_id: str,
    payload: BriefRequest,
    request: Request,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
    manager: LLMManager = Depends(deps.get_llm_manager),
):
    project = _get_project(db, project_id, user)
    system = brief_system_prompt(language=project.language)
    try:
        completion, _ = manager.complete(
            system=system,
            messages=[{"role": "user", "content": payload.description.strip()}],
            temperature=0.4,
        )
    except LLMError as exc:
        raise llm_error_to_http(exc)
    try:
        brief = BriefResponse.model_validate(extract_json_dict(completion.text))
    except (LLMError, Exception):
        raise HTTPException(
            status_code=502,
            detail="The brief generator returned an unusable response. Try again.",
        )
    project.objective = brief.objective.strip()
    project.architecture = brief.architecture.strip()
    position = len(project.milestones)
    for entry in brief.milestones[:5]:
        milestone = Milestone(
            project_id=project.id,
            title=entry.title.strip()[:200],
            status="todo",
            position=position,
        )
        db.add(milestone)
        db.flush()
        for task_position, task_title in enumerate(entry.tasks[:5]):
            db.add(
                ProjectTask(
                    milestone_id=milestone.id,
                    title=str(task_title).strip()[:200],
                    status="todo",
                    position=task_position,
                )
            )
        position += 1
    db.commit()
    db.refresh(project)
    return brief


@router.post("/{project_id}/milestones", response_model=MilestoneResponse, status_code=201)
def add_milestone(
    project_id: str,
    payload: MilestoneCreate,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    project = _get_project(db, project_id, user)
    milestone = Milestone(
        project_id=project.id,
        title=payload.title.strip(),
        detail=payload.detail.strip(),
        status="todo",
        position=len(project.milestones),
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return _milestone_response(milestone)


def _owned_milestone(db: DbSession, milestone_id: str, user: User) -> Milestone:
    milestone = (
        db.query(Milestone)
        .join(Project, Project.id == Milestone.project_id)
        .filter(Milestone.id == milestone_id, Project.user_id == user.id)
        .first()
    )
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    return milestone


@router.patch("/milestones/{milestone_id}", response_model=MilestoneResponse)
def update_milestone(
    milestone_id: str,
    payload: MilestoneUpdate,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    milestone = _owned_milestone(db, milestone_id, user)
    if payload.title is not None:
        milestone.title = payload.title.strip()
    if payload.detail is not None:
        milestone.detail = payload.detail.strip()
    if payload.status is not None:
        milestone.status = payload.status
    db.commit()
    db.refresh(milestone)
    return _milestone_response(milestone)


@router.post("/milestones/{milestone_id}/tasks", response_model=TaskResponse, status_code=201)
def add_task(
    milestone_id: str,
    payload: TaskCreate,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    milestone = _owned_milestone(db, milestone_id, user)
    task = ProjectTask(
        milestone_id=milestone.id,
        title=payload.title.strip(),
        detail=payload.detail.strip(),
        status="todo",
        position=len(milestone.tasks),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return TaskResponse.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    task = (
        db.query(ProjectTask)
        .join(Milestone, Milestone.id == ProjectTask.milestone_id)
        .join(Project, Project.id == Milestone.project_id)
        .filter(ProjectTask.id == task_id, Project.user_id == user.id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.detail is not None:
        task.detail = payload.detail.strip()
    if payload.status is not None:
        task.status = payload.status
    db.commit()
    db.refresh(task)
    return TaskResponse.model_validate(task)


@router.get("/{project_id}/next", response_model=NextTaskResponse)
def next_task(
    project_id: str,
    db: DbSession = Depends(deps.get_db),
    user: User = Depends(deps.get_current_user),
):
    project = _get_project(db, project_id, user)
    for milestone in sorted(project.milestones, key=lambda m: m.position):
        if milestone.status == "done":
            continue
        for task in sorted(milestone.tasks, key=lambda t: t.position):
            if task.status != "done":
                return NextTaskResponse(
                    done=False,
                    milestone=_milestone_response(milestone),
                    task=TaskResponse.model_validate(task),
                    guidance=(
                        f"Work on '{task.title}' next ({milestone.title}). "
                        "Open a mentor session linked to this project when "
                        "you get stuck, and explain each step in your words."
                    ),
                )
    return NextTaskResponse(
        done=True,
        guidance="Everything in this project is marked done. Nice work.",
    )
