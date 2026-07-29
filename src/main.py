"""3-Stage Manim AI Pipeline orchestrator.

Usage:
  python main.py --topic "explain binary search" --run-id run1
  python main.py --topic "bubble sort" --run-id run2 --quality qh
"""
import argparse
import ast
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from src import code_gen, lint, planner, renderer
from src.config import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_scene_class(code: str) -> str:
    """Parse the Python source and return the first Scene subclass name found."""
    _SCENE_BASES = {"Scene", "ThreeDScene", "MovingCameraScene", "ZoomedScene"}
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    name = ""
                    if isinstance(base, ast.Name):
                        name = base.id
                    elif isinstance(base, ast.Attribute):
                        name = base.attr
                    if name in _SCENE_BASES:
                        return node.name
    except SyntaxError:
        pass
    return "MainScene"


def _video_duration(mp4_path: str) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                mp4_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Stage 3 wrapper: render with auto-repair loop
# ---------------------------------------------------------------------------

def _render_with_retry(
    code: str,
    run_dir: Path,
    markdown_plan: str,
) -> dict:
    """Run lint → render, retrying up to config.max_retries times.

    Each failure feeds the error + bad code back to the code generator.
    Returns a result dict: {success, attempts, mp4, final_error}.
    """
    last_error: str | None = None
    last_code = code
    max_attempts = config.max_retries

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Attempt {attempt}/{max_attempts}")

        # Save attempt file
        code_path = run_dir / f"attempt_{attempt}.py"
        code_path.write_text(last_code)
        logger.info(f"  Saved code → {code_path}")

        # Static lint
        lint_result = lint.check(last_code)
        if not lint_result.passed:
            msg = f"LINT: {lint_result.message}"
            logger.warning(f"  {msg}")
            (run_dir / f"attempt_{attempt}_stderr.log").write_text(msg)
            if attempt < max_attempts:
                logger.info("  Regenerating code with lint error …")
                last_code = code_gen.generate(
                    markdown_plan,
                    previous_error=msg,
                    previous_code=last_code,
                )
            last_error = msg
            continue

        # Render
        work_dir = run_dir / f"work_{attempt}"
        work_dir.mkdir(exist_ok=True)
        work_code = work_dir / f"attempt_{attempt}.py"
        shutil.copy2(code_path, work_code)

        scene_class = _extract_scene_class(last_code)
        logger.info(f"  Rendering class '{scene_class}' …")

        render_result = renderer.run(work_code, scene_class, run_dir)
        (run_dir / f"attempt_{attempt}_stdout.log").write_text(render_result.stdout)
        (run_dir / f"attempt_{attempt}_stderr.log").write_text(render_result.stderr)

        if render_result.success:
            logger.success(f"  Rendered successfully on attempt {attempt}")
            return {"success": True, "attempts": attempt, "mp4": str(render_result.mp4_path)}

        last_error = render_result.stderr
        logger.warning(f"  Render failed:\n{last_error[-600:]}")

        if attempt < max_attempts:
            logger.info("  Regenerating code with render error …")
            last_code = code_gen.generate(
                markdown_plan,
                previous_error=last_error,
                previous_code=last_code,
            )

    return {"success": False, "attempts": max_attempts, "final_error": last_error}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(topic: str, run_id: str, quality: str | None = None) -> None:
    if quality:
        config.render_quality = quality

    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    wall_start = time.time()
    print(f"\nTopic : {topic}")
    print(f"Run ID: {run_id}")
    print(f"Model : {config.llm_provider} / "
          f"{config.gemini_model if config.llm_provider == 'gemini' else config.openai_model}")
    print(f"Quality: {config.render_quality}\n")

    # ── Stage 1: Plan ────────────────────────────────────────────────────────
    print("Stage 1 — Generating scene plan …")
    t0 = time.time()
    markdown_plan = planner.generate(topic)
    plan_elapsed = time.time() - t0

    plan_path = run_dir / "plan.md"
    plan_path.write_text(markdown_plan)
    print(f"  Plan saved → {plan_path}  ({plan_elapsed:.1f}s)\n")
    print("─" * 60)
    print(markdown_plan[:800] + ("…" if len(markdown_plan) > 800 else ""))
    print("─" * 60 + "\n")

    # ── Stage 2: Generate code ───────────────────────────────────────────────
    print("Stage 2 — Generating Manim code …")
    t0 = time.time()
    manim_code = code_gen.generate(markdown_plan)
    code_elapsed = time.time() - t0
    print(f"  Code generated ({code_elapsed:.1f}s, {len(manim_code)} chars)\n")

    # ── Stage 3: Render with auto-repair ────────────────────────────────────
    print("Stage 3 — Rendering …")
    t0 = time.time()
    result = _render_with_retry(manim_code, run_dir, markdown_plan)
    render_elapsed = time.time() - t0

    wall_elapsed = time.time() - wall_start

    # ── Report ───────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    if result["success"]:
        mp4 = result["mp4"]
        duration = _video_duration(mp4)
        print(f"  SUCCESS  after {result['attempts']} attempt(s)")
        print(f"  Video  : {mp4}")
        print(f"  Length : {duration:.1f}s")
    else:
        print(f"  FAILED  after {result['attempts']} attempt(s)")
        print(f"  Error  : {str(result.get('final_error', ''))[:300]}")

    print(f"\n  Timing : plan {plan_elapsed:.1f}s | code {code_elapsed:.1f}s"
          f" | render {render_elapsed:.1f}s | total {wall_elapsed:.1f}s")
    print("═" * 60 + "\n")

    sys.exit(0 if result["success"] else 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Manim AI — 3-Stage Pipeline")
    parser.add_argument("--topic", required=True, help="Topic or algorithm to animate")
    parser.add_argument("--run-id", required=True, help="Unique run identifier")
    parser.add_argument(
        "--quality",
        choices=["ql", "qm", "qh", "qk"],
        default=None,
        help="Render quality: ql=480p (fast), qm=720p, qh=1080p, qk=4K (default: ql)",
    )
    args = parser.parse_args()
    _run_pipeline(args.topic, args.run_id, args.quality)


if __name__ == "__main__":
    main()
