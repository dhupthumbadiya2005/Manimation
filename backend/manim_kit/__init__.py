"""manim_kit — the themed toolkit generated scenes are written against.

Generated files start with::

    from manim import *
    from manim_kit import *
"""

from .base_scene import T, ThemedScene, ThemedVoiceoverScene
from .helpers import (
    caption, clear_scene, color_symbols, equation_chain, highlight_box,
    labeled_axes, place_in_zone, stack, tex, title_card, zone,
)
from .zones import ZONE_NAMES, ZONES

__all__ = [
    "T", "ThemedScene", "ThemedVoiceoverScene", "ZONES", "ZONE_NAMES",
    "caption", "clear_scene", "color_symbols", "equation_chain", "highlight_box",
    "labeled_axes", "place_in_zone", "stack", "tex", "title_card", "zone",
]
