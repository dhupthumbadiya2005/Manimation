"""Subprocess Manim renderer with timeout and log capture."""
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.config import config


TIMEOUT_SECONDS = 300
# LaTeX on macOS lives here (TeX Live / MacTeX); not on default subprocess PATH
LATEX_BIN = "/Library/TeX/texbin"

# Map quality flag → Manim output subdirectory name
_QUALITY_DIRS = {
    "ql": "480p15",
    "qm": "720p30",
    "qh": "1080p60",
    "qk": "2160p60",
}


@dataclass
class RenderResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    mp4_path: Path | None = None


def run(code_path: Path, scene_class: str, output_dir: Path) -> RenderResult:
    """Run `manim -q<level> <code_path> <scene_class>`.

    Quality is read from config.render_quality ("ql" by default = 480p15).
    Returns RenderResult; on success, mp4_path points to the rendered file.
    """
    quality_flag = f"-{config.render_quality}"
    quality_dir = _QUALITY_DIRS.get(config.render_quality, config.render_quality)

    env = os.environ.copy()
    if LATEX_BIN not in env.get("PATH", ""):
        env["PATH"] = LATEX_BIN + ":" + env.get("PATH", "")

    try:
        proc = subprocess.run(
            ["manim", quality_flag, code_path.name, scene_class],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=str(code_path.parent),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return RenderResult(
            success=False,
            stdout="",
            stderr=f"timeout: render exceeded {TIMEOUT_SECONDS} seconds",
        )

    stdout = proc.stdout
    stderr = proc.stderr
    success = proc.returncode == 0

    mp4_path = None
    if success:
        stem = code_path.stem
        pattern = code_path.parent / "media" / "videos" / stem / quality_dir / f"{scene_class}.mp4"
        if pattern.exists():
            dest = output_dir / "final.mp4"
            shutil.copy2(pattern, dest)
            mp4_path = dest
        else:
            # Fallback: search recursively
            matches = list(code_path.parent.rglob(f"{scene_class}.mp4"))
            if matches:
                dest = output_dir / "final.mp4"
                shutil.copy2(matches[0], dest)
                mp4_path = dest
            else:
                success = False
                stderr += "\nRendered mp4 not found on disk after successful manim exit."

    return RenderResult(success=success, stdout=stdout, stderr=stderr, mp4_path=mp4_path)
