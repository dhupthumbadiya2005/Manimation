import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from manim_kit.layout_log import analyze  # noqa: E402
from manim_kit.theme import PRESETS, ROLE_NAMES, load_active_theme  # noqa: E402
from manim_kit.zones import FRAME_HEIGHT, FRAME_WIDTH, ZONES, fit_scale  # noqa: E402


# ---- zones -----------------------------------------------------------------

def test_zones_inside_frame():
    for z in ZONES.values():
        assert -FRAME_WIDTH / 2 < z.x0 < z.x1 < FRAME_WIDTH / 2
        assert -FRAME_HEIGHT / 2 < z.y0 < z.y1 < FRAME_HEIGHT / 2


def test_bands_do_not_overlap_main_area():
    assert ZONES["TOP"].y0 > ZONES["CENTER"].y1
    assert ZONES["BOTTOM"].y1 < ZONES["CENTER"].y0
    assert ZONES["LEFT"].x1 < ZONES["RIGHT"].x0


def test_fit_scale_shrinks_but_does_not_grow_by_default():
    z = ZONES["LEFT"]
    assert fit_scale(z.width * 2, 1.0, z) < 0.5
    assert fit_scale(0.5, 0.5, z) == 1.0
    assert fit_scale(0.5, 0.5, z, allow_grow=True) > 1.0


# ---- layout analysis ---------------------------------------------------------

def _obj(group, box, is_text=True, label="x", kind="Text", background=False):
    return {"group": group, "kind": kind, "label": label, "box": box,
            "is_text": is_text, "is_background": background}


def test_detects_out_of_frame_and_dedupes():
    snap = {"t": 1.0, "objects": [_obj(0, [6.5, 8.0, 0, 0.5], label="long title")]}
    v = analyze([snap, {**snap, "t": 2.0}])
    assert len(v) == 1 and v[0]["type"] == "out_of_frame" and v[0]["count"] == 2 and v[0]["first_t"] == 1.0


def test_background_planes_may_overflow():
    snap = {"t": 0, "objects": [_obj(0, [-11, 11, -4, 4], is_text=False, kind="VGroup", background=True)]}
    assert analyze([snap]) == []


def test_detects_text_overlap_only_across_groups():
    a = _obj(0, [0, 2, 0, 1], label="alpha")
    b = _obj(1, [1, 3, 0, 1], label="beta")
    same_group = _obj(0, [1, 3, 0, 1], label="gamma")
    assert [v["type"] for v in analyze([{"t": 0, "objects": [a, b]}])] == ["text_overlap"]
    assert analyze([{"t": 0, "objects": [a, same_group]}]) == []


def test_detects_tiny_text():
    v = analyze([{"t": 0, "objects": [_obj(0, [0, 1, 0, 0.05], label="tiny words")]}])
    assert v[0]["type"] == "text_too_small"


# ---- theme -----------------------------------------------------------------

def test_presets_define_every_role():
    for theme in PRESETS.values():
        for role in ROLE_NAMES:
            assert getattr(theme, role).startswith("#")


def test_default_is_3b1b(monkeypatch):
    monkeypatch.delenv("MANIMATION_THEME", raising=False)
    monkeypatch.delenv("MANIMATION_SYMBOL_COLORS", raising=False)
    t = load_active_theme()
    assert t.id == "3b1b" and t.background == "#1C1C1C"


def test_symbol_roles_from_env(monkeypatch, tmp_path):
    roles = tmp_path / "roles.json"
    roles.write_text(json.dumps({"x": "primary", "f(x)": "highlight"}))
    monkeypatch.setenv("MANIMATION_SYMBOL_COLORS", str(roles))
    t = load_active_theme()
    assert t.symbol_colors == {"x": t.primary, "f(x)": t.highlight}


def test_unknown_symbol_role_fails_fast(monkeypatch, tmp_path):
    roles = tmp_path / "roles.json"
    roles.write_text(json.dumps({"x": "chartreuse"}))
    monkeypatch.setenv("MANIMATION_SYMBOL_COLORS", str(roles))
    with pytest.raises(ValueError):
        load_active_theme()
