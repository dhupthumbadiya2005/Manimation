"""Request/response models for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .storyboard import Storyboard

Quality = Literal["low", "medium", "high"]


class CreateProject(BaseModel):
    request: str = Field(min_length=5, max_length=2000)
    audience: str = "curious high-school and university students"
    max_scenes: int = Field(default=3, ge=1, le=6)
    budget_usd: float = Field(default=0.75, gt=0, le=20)
    theme_id: str = "3b1b"


class GenerateRequest(BaseModel):
    final_quality: Quality = "medium"


class ReviseRequest(BaseModel):
    feedback: str = Field(default="", max_length=2000)
    final_quality: Quality = "medium"


class ResumeRequest(BaseModel):
    budget_usd: float | None = Field(default=None, gt=0, le=20)
    final_quality: Quality = "medium"


class SceneView(BaseModel):
    id: str
    title: str
    status: str
    fixer_turns: int
    fixer_edits: int
    autofixes: list[str]
    last_feedback: str
    preview_url: str | None
    has_code: bool


class BudgetView(BaseModel):
    limit_usd: float
    spent_usd: float
    calls: int
    by_agent: dict[str, float]


class ProjectView(BaseModel):
    id: str
    request: str
    audience: str
    theme_id: str
    phase: str
    error: dict | None
    busy: bool
    created: float
    budget: BudgetView
    storyboard: Storyboard | None
    scenes: list[SceneView]
    final_url: str | None


class ProjectSummary(BaseModel):
    id: str
    title: str
    phase: str
    created: float
    final_url: str | None
    spent_usd: float
