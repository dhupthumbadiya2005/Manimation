"""Storyboard contract between the Director and the Coder.

Kept deliberately compact: every field here is output tokens the Director pays
for. Schema rules for structured outputs: no dicts (``additionalProperties``
must be false), no numeric/length constraints.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Role = Literal["text", "muted", "primary", "secondary", "highlight", "accent", "gold", "teal", "purple"]
ZoneName = Literal["FULL", "TOP", "BOTTOM", "CENTER", "LEFT", "RIGHT"]


class SymbolColor(BaseModel):
    symbol: str          # exact TeX of the symbol, e.g. "x", "f(x)", "\\theta"
    role: Role


class PlannedObject(BaseModel):
    id: str
    kind: str            # MathTex, Text, Axes, NumberPlane, Graph, Polygon, Dot, Arrow, ...
    content: str         # TeX / text / short description of the geometry
    zone: ZoneName
    color_role: Role


class Beat(BaseModel):
    narration: str       # spoken sentence(s) for this beat
    visual: str          # what appears and how it animates, in order
    objects: list[PlannedObject]


class ScenePlan(BaseModel):
    id: str
    title: str
    goal: str
    techniques: list[str]
    beats: list[Beat]


class Storyboard(BaseModel):
    title: str
    summary: str
    symbol_colors: list[SymbolColor]
    scenes: list[ScenePlan]

    def normalized(self) -> "Storyboard":
        """Stable scene ids/class names regardless of what the model wrote."""
        for i, scene in enumerate(self.scenes, start=1):
            scene.id = f"scene_{i:02d}"
        return self

    def symbol_roles(self) -> dict[str, str]:
        return {s.symbol: s.role for s in self.symbol_colors}


def scene_class_name(scene_id: str) -> str:
    return "Scene" + scene_id.split("_")[-1]
