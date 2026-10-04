"""Visual themes. Generated scene code never uses hex colors directly — it uses
semantic roles (``T.primary``, ``T.highlight`` ...) so any theme can be swapped in.

At render time the pipeline points ``MANIMATION_THEME`` at a theme id or a JSON
file, and ``MANIMATION_SYMBOL_COLORS`` at a JSON file mapping math symbols to
role names (e.g. ``{"x": "primary", "f(x)": "highlight"}``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

ROLE_NAMES = (
    "text", "muted", "primary", "secondary", "highlight",
    "accent", "gold", "teal", "purple",
)


class Theme(BaseModel):
    id: str
    name: str
    background: str
    text: str
    muted: str
    primary: str
    secondary: str
    highlight: str
    accent: str
    gold: str
    teal: str
    purple: str
    text_font: str = ""  # "" -> Manim/Pango default
    # Symbol -> role name, set per storyboard so a symbol keeps one color across all scenes.
    symbol_roles: dict[str, str] = Field(default_factory=dict)

    def role(self, name: str) -> str:
        if name not in ROLE_NAMES:
            raise ValueError(f"Unknown color role {name!r}; expected one of {ROLE_NAMES}")
        return getattr(self, name)

    @property
    def symbol_colors(self) -> dict[str, str]:
        return {sym: self.role(role) for sym, role in self.symbol_roles.items()}


PRESETS: dict[str, Theme] = {
    t.id: t
    for t in [
        Theme(
            id="3b1b",
            name="3Blue1Brown Classic",
            background="#1C1C1C",
            text="#FFFFFF",
            muted="#888888",
            primary="#58C4DD",
            secondary="#83C167",
            highlight="#FFFF00",
            accent="#FC6255",
            gold="#F0AC5F",
            teal="#5CD0B3",
            purple="#9A72AC",
        ),
        Theme(
            id="chalkboard",
            name="Chalkboard",
            background="#1E2B24",
            text="#F2F0E6",
            muted="#9AA79F",
            primary="#8ECAE6",
            secondary="#B5E48C",
            highlight="#FFE66D",
            accent="#FF8C8C",
            gold="#F4B860",
            teal="#7FD1B9",
            purple="#C3A6E0",
        ),
        Theme(
            id="light_paper",
            name="Light Paper",
            background="#FAF8F2",
            text="#1F2328",
            muted="#6E7781",
            primary="#1F6FEB",
            secondary="#2DA44E",
            highlight="#BF8700",
            accent="#CF222E",
            gold="#BC4C00",
            teal="#1B7C83",
            purple="#8250DF",
        ),
        Theme(
            id="solarized",
            name="Solarized Dark",
            background="#002B36",
            text="#EEE8D5",
            muted="#839496",
            primary="#268BD2",
            secondary="#859900",
            highlight="#B58900",
            accent="#DC322F",
            gold="#CB4B16",
            teal="#2AA198",
            purple="#6C71C4",
        ),
    ]
}

DEFAULT_THEME_ID = "3b1b"


def load_active_theme() -> Theme:
    """Resolve the theme for this render process from the environment."""
    spec = os.environ.get("MANIMATION_THEME", DEFAULT_THEME_ID)
    if spec in PRESETS:
        theme = PRESETS[spec].model_copy()
    else:
        theme = Theme.model_validate_json(Path(spec).read_text())

    roles_path = os.environ.get("MANIMATION_SYMBOL_COLORS")
    if roles_path:
        theme.symbol_roles = json.loads(Path(roles_path).read_text())
    for role in theme.symbol_roles.values():
        theme.role(role)  # fail fast on unknown roles
    return theme
