"""Layout instrumentation. After every ``play()`` the themed scene records the
bounding box of each on-screen mobject; ``analyze`` turns those snapshots into
concrete violations (off-screen, overlapping text, unreadably small text) for
the Visual Critic and the Debugger.

``analyze`` is pure Python; only ``snapshot_scene`` touches manim objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .zones import FRAME_HEIGHT, FRAME_WIDTH

TEXT_CLASSES = {
    "Text", "MarkupText", "Paragraph", "MathTex", "Tex",
    "SingleStringMathTex", "DecimalNumber", "Integer", "Variable",
}
# Grids are meant to fill (and, once transformed, overflow) the frame.
BACKGROUND_CLASSES = {"NumberPlane", "ComplexPlane", "PolarPlane"}
OFF_FRAME_TOL = 0.05
OVERLAP_RATIO = 0.2       # intersection / smaller box area
MIN_TEXT_HEIGHT = 0.15    # frame units; ~font_size 14


def _box(mob) -> list[float] | None:
    try:
        if len(mob.get_all_points()) == 0:
            return None
        return [float(mob.get_left()[0]), float(mob.get_right()[0]),
                float(mob.get_bottom()[1]), float(mob.get_top()[1])]
    except Exception:
        return None


def _is_visible(mob) -> bool:
    try:
        return mob.get_fill_opacity() > 0.01 or mob.get_stroke_opacity() > 0.01
    except Exception:
        return True


def _label(mob) -> str:
    for attr in ("text", "tex_string"):
        val = getattr(mob, attr, None)
        if isinstance(val, str) and val:
            return val[:60]
    return ""


def _is_text(mob) -> bool:
    return type(mob).__name__ in TEXT_CLASSES


def _text_leaves(mob, out: list) -> None:
    if _is_text(mob):
        out.append(mob)
        return
    for sub in mob.submobjects:
        _text_leaves(sub, out)


def snapshot_scene(scene, index: int) -> dict[str, Any]:
    objects = []
    for top_i, mob in enumerate(scene.mobjects):
        box = _box(mob)
        if box is None or not _is_visible(mob):
            continue
        is_background = any(type(m).__name__ in BACKGROUND_CLASSES for m in mob.get_family())
        objects.append({"group": top_i, "kind": type(mob).__name__, "label": _label(mob),
                        "box": box, "is_text": False, "is_background": is_background})
        leaves: list = []
        _text_leaves(mob, leaves)
        for leaf in leaves:
            lbox = _box(leaf)
            if lbox is not None and _is_visible(leaf):
                objects.append({"group": top_i, "kind": type(leaf).__name__,
                                "label": _label(leaf), "box": lbox, "is_text": True})
    t = float(getattr(scene.renderer, "time", 0.0))
    return {"index": index, "t": round(t, 2), "objects": objects}


def _overlap_ratio(a: list[float], b: list[float]) -> float:
    w = min(a[1], b[1]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[2], b[2])
    if w <= 0 or h <= 0:
        return 0.0
    area_a = (a[1] - a[0]) * (a[3] - a[2])
    area_b = (b[1] - b[0]) * (b[3] - b[2])
    smaller = min(area_a, area_b)
    return (w * h) / smaller if smaller > 0 else 0.0


def analyze(snapshots: list[dict[str, Any]], frame_width: float = FRAME_WIDTH,
            frame_height: float = FRAME_HEIGHT) -> list[dict[str, Any]]:
    """Return deduplicated violations, each with the first time it was seen."""
    hw, hh = frame_width / 2, frame_height / 2
    seen: dict[tuple, dict[str, Any]] = {}

    def add(kind: str, key: tuple, t: float, detail: str) -> None:
        k = (kind, *key)
        if k in seen:
            seen[k]["count"] += 1
        else:
            seen[k] = {"type": kind, "first_t": t, "count": 1, "detail": detail}

    for snap in snapshots:
        t = snap["t"]
        objs = snap["objects"]
        for o in objs:
            x0, x1, y0, y1 = o["box"]
            name = o["label"] or o["kind"]
            if not o.get("is_background") and (x0 < -hw - OFF_FRAME_TOL or x1 > hw + OFF_FRAME_TOL
                    or y0 < -hh - OFF_FRAME_TOL or y1 > hh + OFF_FRAME_TOL):
                add("out_of_frame", (name,), t,
                    f"{o['kind']} '{name}' extends outside the frame (box x[{x0:.2f},{x1:.2f}] y[{y0:.2f},{y1:.2f}])")
            if o["is_text"] and (y1 - y0) < MIN_TEXT_HEIGHT and len(o["label"]) > 1:
                add("text_too_small", (name,), t,
                    f"{o['kind']} '{name}' is only {y1 - y0:.2f} units tall; increase font_size")
        texts = [o for o in objs if o["is_text"]]
        for i, a in enumerate(texts):
            for b in texts[i + 1:]:
                if a["group"] == b["group"]:
                    continue  # parts of one composed group are placed intentionally
                r = _overlap_ratio(a["box"], b["box"])
                if r > OVERLAP_RATIO:
                    na, nb = a["label"] or a["kind"], b["label"] or b["kind"]
                    add("text_overlap", tuple(sorted((na, nb))), t,
                        f"'{na}' overlaps '{nb}' ({r:.0%} of the smaller box)")
    return list(seen.values())


def write_log(path: str | Path, snapshots: list[dict[str, Any]]) -> None:
    Path(path).write_text(json.dumps(
        {"snapshots": snapshots, "violations": analyze(snapshots)}, indent=1))
