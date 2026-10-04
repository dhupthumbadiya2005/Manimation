"""HTTP + WebSocket API. Projects live on disk (see ``pipeline/project.py``);
long steps run as background jobs and stream progress over the WebSocket."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from app import config
from app.llm.budget import Budget
from app.pipeline import orchestrator
from app.pipeline.project import Project
from app.schemas.api import (
    BudgetView, CreateProject, GenerateRequest, ProjectSummary, ProjectView, ResumeRequest,
    ReviseRequest, SceneView,
)
from app.schemas.storyboard import Storyboard
from manim_kit.theme import PRESETS

from .jobs import JobRunner, ProjectBusyError

router = APIRouter(prefix="/api")
PROJECT_ID = re.compile(r"^[\w.~-]+$")
RUNNING_PHASES = ("planning", "generating")


def _runner(request: Request) -> JobRunner:
    return request.app.state.runner


def _projects_dir() -> Path:
    return config.settings.data_dir / "projects"


def _load(project_id: str) -> Project:
    root = _projects_dir() / project_id
    if not PROJECT_ID.match(project_id) or not (root / "state.json").exists():
        raise HTTPException(404, "project not found")
    return Project.load(root)


def media_url(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    try:
        rel = p.resolve().relative_to(config.settings.data_dir.resolve())
    except ValueError:
        return None
    return f"/media/{rel.as_posix()}" if p.exists() else None


def _view(project: Project, runner: JobRunner) -> ProjectView:
    state = project.state
    busy = runner.is_busy(project.id)
    phase, error = state.phase, state.error
    if phase in RUNNING_PHASES and not busy:
        # The server restarted mid-job. Everything up to the last checkpoint is kept.
        phase, error = "stopped", {"code": "interrupted",
                                   "message": "The server restarted while this was running. Resume to continue."}
    board = project.load_storyboard()
    budget = Budget(state.budget_usd or config.settings.budget_usd, project.usage_path)
    summary = budget.summary()
    scenes = []
    for scene in board.scenes if board else []:
        s = project.scene(scene.id)
        scenes.append(SceneView(
            id=scene.id, title=scene.title, status=s.status, fixer_turns=s.fixer_turns,
            fixer_edits=s.fixer_edits, autofixes=s.autofixes, last_feedback=s.last_feedback,
            preview_url=media_url(s.preview_video), has_code=project.scene_file(scene.id).exists(),
        ))
    return ProjectView(
        id=project.id, request=state.request, audience=state.audience, theme_id=state.theme_id,
        phase=phase, error=error, busy=busy, created=state.created,
        budget=BudgetView(limit_usd=budget.limit_usd, spent_usd=summary["spent_usd"],
                          calls=summary["calls"], by_agent=summary["by_agent"]),
        storyboard=board, scenes=scenes, final_url=media_url(state.final_video),
    )


def _submit(runner: JobRunner, project: Project, name: str, running: str, done: str, step) -> None:
    try:
        runner.submit(project.root, name, running, done, step)
    except ProjectBusyError as err:
        raise HTTPException(409, str(err)) from err


# ---- read -------------------------------------------------------------------

@router.get("/health")
def health():
    return {"ok": True, "demo_mode": config.settings.demo_mode,
            "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "profile": config.settings.profile, "tts": config.settings.tts,
            "tts_voice": config.settings.tts_voice if config.settings.tts == "deepgram" else None}


@router.get("/themes")
def themes():
    return [t.model_dump(exclude={"symbol_roles"}) for t in PRESETS.values()]


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects():
    out = []
    root = _projects_dir()
    for path in sorted(root.glob("*/state.json"), reverse=True) if root.exists() else []:
        project = Project.load(path.parent)
        board = project.load_storyboard()
        out.append(ProjectSummary(
            id=project.id, title=board.title if board else project.state.request,
            phase=project.state.phase, created=project.state.created,
            final_url=media_url(project.state.final_video),
            spent_usd=round(Budget(1.0, project.usage_path).spent_usd, 4),
        ))
    return out


@router.get("/projects/{project_id}", response_model=ProjectView)
def get_project(project_id: str, request: Request):
    return _view(_load(project_id), _runner(request))


@router.get("/projects/{project_id}/scenes/{scene_id}/code", response_class=PlainTextResponse)
def scene_code(project_id: str, scene_id: str):
    project = _load(project_id)
    if not re.match(r"^scene_\d+$", scene_id) or not project.scene_file(scene_id).exists():
        raise HTTPException(404, "scene code not found")
    return project.scene_file(scene_id).read_text()


@router.get("/projects/{project_id}/usage")
def usage(project_id: str):
    project = _load(project_id)
    return [r.__dict__ for r in Budget(1.0, project.usage_path).records]


# ---- actions ----------------------------------------------------------------

@router.post("/projects", response_model=ProjectView, status_code=201)
def create_project(body: CreateProject, request: Request):
    if body.theme_id not in PRESETS:
        raise HTTPException(422, f"unknown theme {body.theme_id!r}")
    project = orchestrator.open_project(request=body.request, audience=body.audience,
                                        budget_usd=body.budget_usd, theme_id=body.theme_id,
                                        max_scenes=body.max_scenes, log=lambda *_: None)
    runner = _runner(request)
    _submit(runner, project, "plan", "planning", "awaiting_approval",
            lambda p, log: orchestrator.plan(p, log))
    return _view(Project.load(project.root), runner)


@router.put("/projects/{project_id}/storyboard", response_model=ProjectView)
def update_storyboard(project_id: str, board: Storyboard, request: Request):
    project = _load(project_id)
    runner = _runner(request)
    if runner.is_busy(project_id):
        raise HTTPException(409, "project is busy")
    if any(project.scene_file(s.id).exists() for s in (project.load_storyboard() or board).scenes):
        raise HTTPException(409, "scenes are already coded; request changes per scene instead")
    project.save_storyboard(board.normalized())
    return _view(project, runner)


@router.post("/projects/{project_id}/generate", response_model=ProjectView)
def generate(project_id: str, body: GenerateRequest, request: Request):
    project = _load(project_id)
    if project.load_storyboard() is None:
        raise HTTPException(409, "the storyboard is not ready yet")
    runner = _runner(request)
    _submit(runner, project, "generate", "generating", "done",
            lambda p, log: orchestrator.build(p, final_quality=body.final_quality, log=log))
    return _view(Project.load(project.root), runner)


@router.post("/projects/{project_id}/scenes/{scene_id}/revise", response_model=ProjectView)
def revise(project_id: str, scene_id: str, body: ReviseRequest, request: Request):
    project = _load(project_id)
    board = project.load_storyboard()
    if board is None or scene_id not in {s.id for s in board.scenes}:
        raise HTTPException(404, "scene not found")
    runner = _runner(request)
    _submit(runner, project, f"revise {scene_id}", "generating", "done",
            lambda p, log: orchestrator.revise_scene(p, scene_id, body.feedback,
                                                     final_quality=body.final_quality, log=log))
    return _view(Project.load(project.root), runner)


@router.post("/projects/{project_id}/resume", response_model=ProjectView)
def resume(project_id: str, body: ResumeRequest, request: Request):
    project = _load(project_id)
    if body.budget_usd is not None:
        project.state.budget_usd = body.budget_usd
        project.save()
    runner = _runner(request)
    if project.load_storyboard() is None:
        _submit(runner, project, "plan", "planning", "awaiting_approval",
                lambda p, log: orchestrator.plan(p, log))
    else:
        _submit(runner, project, "generate", "generating", "done",
                lambda p, log: orchestrator.build(p, final_quality=body.final_quality, log=log))
    return _view(Project.load(project.root), runner)


# ---- live events ------------------------------------------------------------

@router.websocket("/projects/{project_id}/events")
async def events(websocket: WebSocket, project_id: str):
    try:
        project = _load(project_id)
    except HTTPException:
        await websocket.close(code=4404)
        return
    hub = websocket.app.state.hub
    await websocket.accept()
    queue = hub.subscribe(project_id)
    try:
        await websocket.send_json({"type": "history", "events": hub.history(project.root)})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25)
            except asyncio.TimeoutError:
                event = {"type": "ping"}  # keeps proxies from closing idle sockets
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(project_id, queue)
