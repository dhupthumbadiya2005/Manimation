"""Director agent: prompt -> Storyboard (one structured call)."""

from __future__ import annotations

from app.llm.client import LLM
from app.schemas.storyboard import Storyboard

from . import knowledge


def plan(llm: LLM, request: str, *, audience: str, max_scenes: int) -> Storyboard:
    user = (
        f"Request: {request}\n"
        f"Audience: {audience}\n"
        f"Maximum scenes: {max_scenes}\n"
        f"Technique tags to choose from: {', '.join(knowledge.all_techniques())}"
    )
    board = llm.structured("director", knowledge.prompt("director"), user, Storyboard)
    board.scenes = board.scenes[:max_scenes]
    return board.normalized()
