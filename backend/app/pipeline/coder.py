"""Coder agent: one storyboard scene -> one Python file (one call per scene).

The system prompt (instructions + toolkit reference) is identical for every
scene, so after the first scene it is read from the prompt cache.
"""

from __future__ import annotations

import json
import re

from app.llm.client import LLM
from app.llm.errors import PipelineStop
from app.schemas.storyboard import ScenePlan, Storyboard, scene_class_name

from . import knowledge

CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def system_prompt() -> str:
    return knowledge.prompt("coder").replace("{toolkit_reference}", knowledge.toolkit_reference())


def build_user_message(board: Storyboard, scene: ScenePlan) -> str:
    parts = [
        f"Video: {board.title}",
        f"Write scene {scene.id} as class `{scene_class_name(scene.id)}`.",
        "Symbol colors for the whole video (already applied by tex(...) to whole parts): "
        + (", ".join(f"{s.symbol} -> {s.role}" for s in board.symbol_colors) or "none"),
        "Scene plan:\n" + json.dumps(scene.model_dump(), indent=1),
    ]
    snippets = knowledge.select_snippets(scene.techniques)
    if snippets:
        parts.append("Tested examples using similar techniques (adapt, don't copy blindly):")
        for s in snippets:
            parts.append(f"# --- example: {s.name} ---\n{s.code}")
    return "\n\n".join(parts)


def extract_code(text: str) -> str:
    blocks = CODE_BLOCK.findall(text)
    if not blocks:
        raise PipelineStop("The coder reply contained no code block.")
    return max(blocks, key=len).strip() + "\n"


def write_scene(llm: LLM, board: Storyboard, scene: ScenePlan) -> str:
    response = llm.message("coder", system_prompt(),
                           [{"role": "user", "content": build_user_message(board, scene)}])
    text = "".join(b.text for b in response.content if b.type == "text")
    return extract_code(text)
