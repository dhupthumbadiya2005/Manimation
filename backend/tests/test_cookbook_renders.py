"""Every cookbook snippet must render and be free of layout violations — they are
the examples the Coder copies from, so they have to be known-good."""

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "scripts"))

from render_cookbook import COOKBOOK, render  # noqa: E402


@pytest.mark.render
@pytest.mark.parametrize("path", sorted(COOKBOOK.glob("*.py")), ids=lambda p: p.stem)
def test_cookbook_snippet_renders_cleanly(path, tmp_path):
    result = render(path, tmp_path)
    assert result["ok"], result.get("error")
    assert result["violations"] == [], result["violations"]
