"""Tested building blocks generated scenes are encouraged to use. They encode the
3Blue1Brown idioms (consistent symbol colors, title/caption bands, equation
morphing) and keep everything inside its zone.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from manim import (
    DOWN, Axes, FadeOut, Mobject, MathTex, SurroundingRectangle,
    Text, TransformMatchingTex, VGroup, Write, smooth,
)

from .base_scene import T
from .zones import ZONES, Zone, fit_scale


def zone(name: str) -> Zone:
    try:
        return ZONES[name]
    except KeyError:
        raise ValueError(f"Unknown zone {name!r}; expected one of {list(ZONES)}") from None


def place_in_zone(mob: Mobject, zone_name: str = "CENTER", align: str = "center",
                  padding: float = 0.1, allow_grow: bool = False) -> Mobject:
    """Shrink ``mob`` to fit the zone (never grows unless asked) and position it.

    ``align`` is one of center/top/bottom/left/right within the zone.
    """
    z = zone(zone_name)
    s = fit_scale(mob.width, mob.height, z, padding, allow_grow)
    if s != 1.0:
        mob.scale(s)
    cx, cy = z.center
    x, y = cx, cy
    if align == "top":
        y = z.y1 - padding - mob.height / 2
    elif align == "bottom":
        y = z.y0 + padding + mob.height / 2
    elif align == "left":
        x = z.x0 + padding + mob.width / 2
    elif align == "right":
        x = z.x1 - padding - mob.width / 2
    elif align != "center":
        raise ValueError(f"Unknown align {align!r}")
    mob.move_to(np.array([x, y, 0.0]))
    return mob


def color_symbols(mob: MathTex) -> MathTex:
    """Color every part of ``mob`` whose TeX equals a storyboard symbol.

    Works with parts split by separate args or by ``{{ }}``:
    ``tex("{{f(x)}} = {{x}}^2")`` colors ``f(x)`` and ``x`` per the theme roles.
    Matching whole parts (not substrings) avoids breaking commands like ``\\exp``.
    """
    colors = T.symbol_colors
    if not colors:
        return mob
    for part in mob.submobjects:
        key = getattr(part, "tex_string", "").strip()
        if key in colors:
            part.set_color(colors[key])
    return mob


def tex(*parts: str, font_size: float = 48, **kwargs) -> MathTex:
    """MathTex with storyboard symbol colors applied."""
    return color_symbols(MathTex(*parts, font_size=font_size, **kwargs))


def title_card(text: str, font_size: float = 44) -> Text:
    """Scene title placed in the TOP band."""
    return place_in_zone(Text(text, font_size=font_size, color=T.text), "TOP")


def caption(text: str, font_size: float = 30) -> Text:
    """Short on-screen caption in the BOTTOM band."""
    return place_in_zone(Text(text, font_size=font_size, color=T.muted), "BOTTOM")


def labeled_axes(x_range: Sequence[float], y_range: Sequence[float], x_label: str = "x",
                 y_label: str = "y", zone_name: str = "CENTER", **axes_kwargs) -> tuple[Axes, VGroup]:
    """Axes + axis labels fitted into a zone. Returns ``(axes, group)`` —
    plot on ``axes``, add/animate ``group``."""
    z = zone(zone_name)
    axes = Axes(
        x_range=list(x_range), y_range=list(y_range),
        x_length=z.width - 1.0, y_length=z.height - 0.6,
        axis_config={"color": T.muted, "include_tip": True},
        **axes_kwargs,
    )
    labels = axes.get_axis_labels(x_label=tex(x_label, font_size=36), y_label=tex(y_label, font_size=36))
    group = VGroup(axes, labels)
    place_in_zone(group, zone_name)
    return axes, group


def highlight_box(mob: Mobject, color: str | None = None, buff: float = 0.1) -> SurroundingRectangle:
    return SurroundingRectangle(mob, color=color or T.highlight, buff=buff)


def equation_chain(scene, steps: Sequence[str | Sequence[str]], zone_name: str = "CENTER",
                   run_time: float = 1.5, pause: float = 0.6, font_size: float = 48) -> MathTex:
    """Write the first equation, then morph through the rest with
    ``TransformMatchingTex`` (the 3B1B derivation look). Use ``{{ }}`` around
    terms that should glide between steps. Returns the final mobject."""
    def build(step):
        parts = [step] if isinstance(step, str) else list(step)
        return place_in_zone(tex(*parts, font_size=font_size), zone_name)

    current = build(steps[0])
    scene.play(Write(current), run_time=run_time)
    for step in steps[1:]:
        scene.wait(pause)
        nxt = build(step)
        scene.play(TransformMatchingTex(current, nxt), run_time=run_time, rate_func=smooth)
        current = nxt
    return current


def clear_scene(scene, run_time: float = 0.8) -> None:
    """Fade out everything on screen (use between beats to avoid clutter)."""
    if scene.mobjects:
        scene.play(*[FadeOut(m) for m in scene.mobjects], run_time=run_time)


def stack(*mobs: Mobject, direction=DOWN, buff: float = 0.4) -> VGroup:
    return VGroup(*mobs).arrange(direction, buff=buff)


__all__ = [
    "T", "zone", "place_in_zone", "color_symbols", "tex", "title_card", "caption",
    "labeled_axes", "highlight_box", "equation_chain", "clear_scene", "stack",
]
