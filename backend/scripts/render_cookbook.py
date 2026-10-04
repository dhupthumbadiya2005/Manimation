"""Render every cookbook snippet at preview quality and report failures and
layout violations. Usage: ``uv run python scripts/render_cookbook.py [name ...]``
"""

from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.pipeline.renderer import render_scene  # noqa: E402

COOKBOOK = BACKEND / "knowledge" / "cookbook"


def scene_class(path: Path) -> str:
    tree = ast.parse(path.read_text())
    return next(n.name for n in tree.body if isinstance(n, ast.ClassDef)
                and any(isinstance(b, ast.Name) and b.id.endswith("Scene") for b in n.bases))


def render(path: Path, out_dir: Path) -> dict:
    r = render_scene(path, scene_class(path), out_dir / path.stem, timeout=300)
    return {"name": path.stem, "ok": r.ok, "seconds": r.seconds,
            "violations": r.violations, "error": r.error}


def main(names: list[str]) -> int:
    files = sorted(COOKBOOK.glob("*.py"))
    if names:
        files = [f for f in files if f.stem in names]
    out_dir = Path(tempfile.mkdtemp(prefix="cookbook_"))
    failures = 0
    for f in files:
        r = render(f, out_dir)
        status = "OK  " if r["ok"] else "FAIL"
        print(f"{status} {r['name']:<24} {r['seconds']:>6}s  violations={len(r['violations'])}")
        for v in r["violations"]:
            print(f"       - [{v['type']}] t={v['first_t']} {v['detail']}")
        if not r["ok"]:
            failures += 1
            print("       " + r["error"].replace("\n", "\n       "))
    print(f"\noutput: {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
