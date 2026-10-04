"""Render one scene file in a separate process (timeout, scratch media dir) and
collect the video path, a trimmed error, and layout violations."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import BACKEND_DIR

QUALITY_FLAGS = {"low": "-ql", "medium": "-qm", "high": "-qh"}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
MAX_ERROR_CHARS = 2500


@dataclass
class RenderResult:
    ok: bool
    seconds: float
    video: Path | None = None
    error: str = ""
    violations: list[dict] = field(default_factory=list)

    def feedback(self) -> str:
        """Compact text for the Fixer: the error, else the layout problems."""
        if not self.ok:
            return f"Render failed:\n{self.error}"
        if self.violations:
            lines = [f"- [{v['type']}] at t={v['first_t']}s: {v['detail']}" for v in self.violations]
            return "Rendered, but the layout check found problems:\n" + "\n".join(lines)
        return "OK: rendered with no errors and no layout problems."

    @property
    def clean(self) -> bool:
        return self.ok and not self.violations


def _trim_error(text: str, scene_file: Path) -> str:
    text = ANSI.sub("", text)
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    # Keep the tail (exception + the frames closest to it); that is what matters.
    tail = "\n".join(lines[-45:])
    tail = tail.replace(str(scene_file.parent) + os.sep, "")
    return tail[-MAX_ERROR_CHARS:]


def render_scene(scene_file: Path, class_name: str, out_dir: Path, *, quality: str = "low",
                 tts: str = "silent", voice: str | None = None, narration_bank: Path | None = None,
                 theme: str = "3b1b",
                 symbol_colors_file: Path | None = None, timeout: int = 240) -> RenderResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    layout_path = out_dir / f"{scene_file.stem}.layout.json"
    layout_path.unlink(missing_ok=True)
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "MANIMATION_TTS": tts,
        "MANIMATION_THEME": theme,
        "MANIMATION_LAYOUT_LOG": str(layout_path),
        "COLUMNS": "120",
    }
    if voice:
        env["MANIMATION_TTS_VOICE"] = voice
    if narration_bank:
        env["MANIMATION_NARRATION_BANK"] = str(narration_bank)
    else:
        env.pop("MANIMATION_NARRATION_BANK", None)
    if symbol_colors_file:
        env["MANIMATION_SYMBOL_COLORS"] = str(symbol_colors_file)
    else:
        env.pop("MANIMATION_SYMBOL_COLORS", None)

    media = out_dir / "media"
    cmd = [sys.executable, "-m", "manim", "render", QUALITY_FLAGS[quality], "--disable_caching",
           "--progress_bar", "none", "--media_dir", str(media), str(scene_file), class_name]
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout,
                              cwd=out_dir)
    except subprocess.TimeoutExpired:
        return RenderResult(False, float(timeout),
                            error=f"Render timed out after {timeout}s. The scene is too long or an "
                                  f"updater/loop never finishes; shorten run_times or simplify.")
    seconds = round(time.monotonic() - start, 1)
    if proc.returncode != 0:
        return RenderResult(False, seconds, error=_trim_error(proc.stderr + proc.stdout, scene_file))

    videos = [p for p in media.rglob(f"{class_name}.mp4") if "partial_movie_files" not in p.parts]
    video = max(videos, key=lambda p: p.stat().st_mtime) if videos else None
    violations = json.loads(layout_path.read_text())["violations"] if layout_path.exists() else []
    if video is None:
        return RenderResult(False, seconds, error="Render finished but produced no video "
                                                  "(did construct() play any animation?).")
    return RenderResult(True, seconds, video=video, violations=violations)
