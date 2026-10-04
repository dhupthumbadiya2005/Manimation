"""Runs the pipeline: Director -> (Coder -> Validator -> Renderer -> Fixer) per
scene -> final render with narration -> Assembler.

Steps are separate so the web app can pause between them (storyboard review):
``plan`` -> ``build``; ``revise_scene`` applies a user's change request later.

Cost rules enforced here:
- each scene is coded once; failures and change requests are handled by edits
- free steps first: static validation and known auto-fixes run before any render,
  and the Fixer is only called when something is actually wrong
- every step is checkpointed in the project folder; resumed runs skip finished work
- a ``PipelineStop`` (credits exhausted, budget reached) halts the whole run at once
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from app import config
from app.llm.budget import Budget
from app.llm.client import LLM
from app.llm.errors import LLMRefusalError
from app.schemas.storyboard import Storyboard, scene_class_name

from . import assembler, coder, director, fixer, knowledge, narration
from .project import Project
from .renderer import render_scene
from .validator import validate

Log = Callable[[str], None]
DONE_STATUSES = ("passed", "passed_with_warnings")


def make_llm(project: Project, log: Log):
    budget = Budget(project.state.budget_usd, project.usage_path)
    if config.settings.demo_mode:
        from app.llm.demo import DemoLLM
        return DemoLLM(budget, log)
    return LLM(budget, log)


def _with_hints(report: str) -> str:
    hints = knowledge.hints_for(report) + knowledge.api_hints(report)
    if not hints:
        return report
    return report + "\n\nHints:\n" + "\n".join(f"- {h}" for h in hints)


def _make_check(project: Project, scene_id: str, log: Log) -> Callable[[], fixer.Check]:
    path = project.scene_file(scene_id)
    class_name = scene_class_name(scene_id)

    def check() -> fixer.Check:
        result = validate(path.read_text(), class_name)
        if result.autofixes:
            path.write_text(result.code)
            project.scene(scene_id).autofixes.extend(result.autofixes)
            log(f"    auto-fixed (free): {', '.join(result.autofixes)}")
        if not result.ok:
            return fixer.Check(False, False, _with_hints(result.report()))
        r = render_scene(path, class_name, project.renders_dir / "preview" / scene_id,
                         quality="low", tts="silent", theme=project.state.theme_id,
                         symbol_colors_file=project.symbol_colors_path,
                         timeout=config.settings.render_timeout_s)
        if r.ok:
            project.scene(scene_id).preview_video = str(r.video)
        return fixer.Check(r.clean, r.ok, _with_hints(r.feedback()))

    return check


def _record_outcome(project: Project, scene_id: str, outcome: fixer.FixOutcome, log: Log) -> None:
    state = project.scene(scene_id)
    state.fixer_turns += outcome.turns
    state.fixer_edits += outcome.edits
    state.last_feedback = outcome.feedback
    if outcome.clean:
        state.status = "passed"
    elif outcome.rendered:
        state.status = "passed_with_warnings"
    else:
        state.status = "failed"
    log(f"  {scene_id}: {state.status} after {outcome.turns} fixer turn(s), {outcome.edits} edit(s)")
    project.save()


def _build_scene(project: Project, llm, board: Storyboard, scene, log: Log) -> None:
    state = project.scene(scene.id)
    path = project.scene_file(scene.id)

    if not path.exists():
        log(f"  coding {scene.id}: {scene.title}")
        state.status = "coding"
        project.save()
        path.write_text(coder.write_scene(llm, board, scene))
        state.status = "coded"
        project.save()

    state.status = "rendering"
    project.save()
    check = _make_check(project, scene.id, log)
    first = check()
    if first.clean:
        state.status, state.last_feedback = "passed", first.feedback
        log(f"  {scene.id}: rendered cleanly on the first try")
        project.save()
        return

    log(f"  {scene.id}: needs fixing -> fixer (edits only)")
    state.status = "fixing"
    project.save()
    outcome = fixer.fix_scene(llm, path, scene_class_name(scene.id), check, first,
                              config.settings.fixer_max_turns, log)
    _record_outcome(project, scene.id, outcome, log)


def _final_render(project: Project, scene_ids: list[str], quality: str, tts: str, log: Log) -> list[Path]:
    voice = config.settings.tts_voice if tts == "deepgram" else None
    bank = None
    if tts == "deepgram":
        # Every line of the video in one Deepgram session -> the same tone throughout.
        bank = narration.prepare([project.scene_file(s) for s in scene_ids], voice,
                                 project.root / "narration", log)
    videos = []
    for scene_id in scene_ids:
        path = project.scene_file(scene_id)
        out = project.renders_dir / "final" / scene_id
        # Reuse the last final render when neither the code nor the settings changed.
        stamp = out / "stamp.json"
        key = {"code": hashlib.sha256(path.read_bytes()).hexdigest(), "quality": quality, "tts": tts, "voice": voice,
               "narration": bank.parent.name if bank else None,
               "theme": project.state.theme_id,
               "colors": project.symbol_colors_path.read_text() if project.symbol_colors_path.exists() else ""}
        if stamp.exists():
            prev = json.loads(stamp.read_text())
            if prev["key"] == key and Path(prev["video"]).exists():
                videos.append(Path(prev["video"]))
                log(f"  final {scene_id}: unchanged, reused")
                continue
        kwargs = dict(quality=quality, theme=project.state.theme_id,
                      symbol_colors_file=project.symbol_colors_path,
                      timeout=config.settings.render_timeout_s * 3)
        r = render_scene(path, scene_class_name(scene_id), out, tts=tts, voice=voice, narration_bank=bank, **kwargs)
        if not r.ok and tts != "silent":
            log(f"  {scene_id}: narrated render failed, retrying without narration")
            r = render_scene(path, scene_class_name(scene_id), out, tts="silent", **kwargs)
        if r.ok:
            videos.append(r.video)
            out.mkdir(parents=True, exist_ok=True)
            stamp.write_text(json.dumps({"key": key, "video": str(r.video)}))
            log(f"  final {scene_id}: {r.seconds}s")
        else:
            log(f"  final {scene_id}: FAILED\n{r.error}")
    return videos


def _assemble(project: Project, board: Storyboard, final_quality: str, log: Log) -> None:
    good = [s.id for s in board.scenes if project.scene(s.id).status in DONE_STATUSES]
    if not good:
        log("No scene rendered successfully; nothing to assemble.")
        return
    tts = config.settings.tts
    narrator = f"{tts} / {config.settings.tts_voice}" if tts == "deepgram" else tts
    log(f"Final render ({final_quality}, narration: {narrator}) of {len(good)}/{len(board.scenes)} scene(s)")
    videos = _final_render(project, good, final_quality, tts, log)
    if videos:
        assembler.concat(videos, project.final_path)
        project.state.final_video = str(project.final_path)
        project.save()
        log(f"Final video: {project.final_path}")


# ---- public steps -------------------------------------------------------------

def open_project(*, request: str | None = None, resume: Path | None = None,
                 audience: str = "curious high-school and university students",
                 budget_usd: float | None = None, theme_id: str = "3b1b",
                 max_scenes: int | None = None, log: Log = print) -> Project:
    """``budget_usd`` sets the project's cap (new project) or raises/lowers it (resume)."""
    if resume:
        project = Project.load(resume)
        log(f"Resuming {project.root}")
    else:
        assert request, "request is required for a new project"
        project = Project.create(config.settings.data_dir, request, audience,
                                 max_scenes or config.settings.max_scenes, theme_id)
        log(f"Project: {project.root}")
    if budget_usd is not None or project.state.budget_usd is None:
        project.state.budget_usd = budget_usd if budget_usd is not None else config.settings.budget_usd
        project.save()
    return project


def plan(project: Project, log: Log = print) -> Storyboard:
    board = project.load_storyboard()
    if board is not None:
        return board
    llm = make_llm(project, log)
    log("Director: planning storyboard")
    board = director.plan(llm, project.state.request, audience=project.state.audience,
                          max_scenes=project.state.max_scenes)
    project.save_storyboard(board)
    log(f"  '{board.title}': {len(board.scenes)} scene(s), {sum(len(s.beats) for s in board.scenes)} beat(s)")
    return board


def build(project: Project, *, final_quality: str = "high", log: Log = print) -> Project:
    board = project.load_storyboard()
    assert board is not None, "plan the storyboard first"
    llm = make_llm(project, log)
    if llm.budget.spent_usd:
        log(f"Already spent on this project: ${llm.budget.spent_usd:.3f} (budget ${llm.budget.limit_usd:.2f})")
    for scene in board.scenes:
        if project.scene(scene.id).status in DONE_STATUSES:
            continue
        try:
            _build_scene(project, llm, board, scene, log)
        except LLMRefusalError as err:
            project.scene(scene.id).status = "failed"
            project.scene(scene.id).last_feedback = str(err)
            project.save()
            log(f"  {scene.id}: skipped ({err})")
    _assemble(project, board, final_quality, log)
    return project


def run(project: Project, *, final_quality: str = "high", log: Log = print) -> Project:
    plan(project, log)
    return build(project, final_quality=final_quality, log=log)


def revise_scene(project: Project, scene_id: str, feedback: str, *, final_quality: str = "high",
                 log: Log = print) -> Project:
    """Apply a user's change request to one scene as edits (Cursor-style), then
    re-assemble. With empty feedback the scene is re-coded from its plan."""
    board = project.load_storyboard()
    scene = next(s for s in board.scenes if s.id == scene_id)
    llm = make_llm(project, log)
    path = project.scene_file(scene_id)
    state = project.scene(scene_id)

    if not feedback.strip() or not path.exists():
        log(f"  {scene_id}: re-coding from the storyboard")
        path.unlink(missing_ok=True)
        state.status = "pending"
        _build_scene(project, llm, board, scene, log)
    else:
        log(f"  {scene_id}: applying change request with edits: {feedback!r}")
        state.status = "fixing"
        project.save()
        check = _make_check(project, scene_id, log)
        request = fixer.Check(False, True,
                              f"Change requested by the user: {feedback}\n"
                              "The scene currently renders. Make this change with minimal edits "
                              "(keep everything else as is), then call render_scene.")
        outcome = fixer.fix_scene(llm, path, scene_class_name(scene_id), check, request,
                                  config.settings.fixer_max_turns, log, require_edits=True)
        if outcome.edits == 0:
            # Nothing changed; the scene is exactly as good as before.
            state.status = "passed"
            project.save()
            log(f"  {scene_id}: no edits were made")
        else:
            _record_outcome(project, scene_id, outcome, log)
    _assemble(project, board, final_quality, log)
    return project
