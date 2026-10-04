"""On-disk state for one video. Every step is checkpointed, so a run that
stops (credits, budget, crash) resumes without paying for finished work.

data/projects/<id>/
  state.json         request + per-scene status
  storyboard.json    Director output
  symbol_colors.json symbol -> role, read by manim_kit at render time
  scenes/scene_01.py Coder output, edited in place by the Fixer
  renders/           preview + final renders
  usage.jsonl        every LLM call with tokens and cost
  final.mp4
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.schemas.storyboard import Storyboard


@dataclass
class SceneState:
    status: str = "pending"   # pending | coding | coded | rendering | fixing | passed | passed_with_warnings | failed
    fixer_turns: int = 0
    fixer_edits: int = 0
    autofixes: list[str] = field(default_factory=list)
    last_feedback: str = ""
    preview_video: str | None = None


@dataclass
class ProjectState:
    request: str
    audience: str
    max_scenes: int
    created: float
    scenes: dict[str, SceneState] = field(default_factory=dict)
    final_video: str | None = None
    budget_usd: float | None = None   # fixed at creation; changed only by an explicit --budget
    theme_id: str = "3b1b"
    # created | planning | awaiting_approval | generating | done | stopped | failed
    phase: str = "created"
    error: dict | None = None         # {"code": ..., "message": ...} when stopped/failed


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.scenes_dir = root / "scenes"
        self.renders_dir = root / "renders"
        self.state_path = root / "state.json"
        self.storyboard_path = root / "storyboard.json"
        self.symbol_colors_path = root / "symbol_colors.json"
        self.usage_path = root / "usage.jsonl"
        self.final_path = root / "final.mp4"
        self.state: ProjectState | None = None

    @property
    def id(self) -> str:
        return self.root.name

    @classmethod
    def create(cls, data_dir: Path, request: str, audience: str, max_scenes: int,
               theme_id: str = "3b1b") -> "Project":
        slug = "-".join(re.findall(r"[a-z0-9]+", request.lower())[:6]) or "video"
        root = data_dir / "projects" / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}"
        suffix = 2
        while root.exists():  # two projects created within the same second
            root = root.with_name(f"{root.name.rsplit('~', 1)[0]}~{suffix}")
            suffix += 1
        project = cls(root)
        project.scenes_dir.mkdir(parents=True)
        project.renders_dir.mkdir()
        project.state = ProjectState(request, audience, max_scenes, time.time(), theme_id=theme_id)
        project.save()
        return project

    def set_phase(self, phase: str, error: dict | None = None) -> None:
        self.state.phase = phase
        self.state.error = error
        self.save()

    @classmethod
    def load(cls, root: Path) -> "Project":
        project = cls(root)
        raw = json.loads(project.state_path.read_text())
        raw["scenes"] = {k: SceneState(**v) for k, v in raw.get("scenes", {}).items()}
        project.state = ProjectState(**raw)
        return project

    def save(self) -> None:
        # Write-then-rename so a reader (the API) never sees a half-written file.
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self.state), indent=1))
        tmp.replace(self.state_path)

    def scene(self, scene_id: str) -> SceneState:
        return self.state.scenes.setdefault(scene_id, SceneState())

    def scene_file(self, scene_id: str) -> Path:
        return self.scenes_dir / f"{scene_id}.py"

    def load_storyboard(self) -> Storyboard | None:
        if not self.storyboard_path.exists():
            return None
        return Storyboard.model_validate_json(self.storyboard_path.read_text())

    def save_storyboard(self, board: Storyboard) -> None:
        self.storyboard_path.write_text(board.model_dump_json(indent=1))
        self.symbol_colors_path.write_text(json.dumps(board.symbol_roles(), indent=1))
