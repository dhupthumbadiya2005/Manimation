"""Subprocess Manim renderer with timeout and log capture."""
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


TIMEOUT_SECONDS = 90
# LaTeX on macOS lives here (TeX Live / MacTeX); not on default subprocess PATH
LATEX_BIN = "/Library/TeX/texbin"


@dataclass
class RenderResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    mp4_path: Path | None = None


def run(code_path: Path, scene_class: str, output_dir: Path) -> RenderResult:
    """
    Run `manim -ql <code_path> <scene_class>`.
    Returns RenderResult; on success, mp4_path points to the rendered file.
    """
    env = os.environ.copy()
    if LATEX_BIN not in env.get("PATH", ""):
        env["PATH"] = LATEX_BIN + ":" + env.get("PATH", "")

    try:
        proc = subprocess.run(
            ["manim", "-ql", code_path.name, scene_class],
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
        # Manim writes to media/videos/<stem>/480p15/<ClassName>.mp4 by default (-ql = 480p)
        stem = code_path.stem
        pattern = code_path.parent / "media" / "videos" / stem / "480p15" / f"{scene_class}.mp4"
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
