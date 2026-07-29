"""Orchestrates coder -> lint -> render with up to 3 total attempts."""
import json
import shutil
from pathlib import Path

from loguru import logger

from src import coder, lint, renderer

MAX_ATTEMPTS = 3


def run(scene: dict, run_dir: Path) -> dict:
    """
    Execute the coder-lint-render loop for one scene.
    All artifacts are written to run_dir.
    Returns a result dict (also written as result.json).
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    scene_id = scene.get("scene_id", "unknown")
    scene_class = f"Scene{scene_id}"

    last_error: str | None = None
    last_code: str | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info(f"Scene {scene_id} — attempt {attempt}/{MAX_ATTEMPTS}")

        # --- Generate code ---
        code = coder.generate(scene, previous_error=last_error, previous_code=last_code)
        last_code = code

        code_path = run_dir / f"attempt_{attempt}.py"
        code_path.write_text(code)
        logger.info(f"Saved code -> {code_path}")

        # --- Lint ---
        lint_result = lint.check(code)
        if not lint_result.passed:
            msg = f"LINT FAILED: {lint_result.message}"
            logger.warning(msg)
            # Write stub logs so every attempt has files
            (run_dir / f"attempt_{attempt}_stdout.log").write_text("")
            (run_dir / f"attempt_{attempt}_stderr.log").write_text(msg)
            last_error = msg
            continue

        # --- Render ---
        # Copy code into a temp work dir so Manim media/ lands there, not in runs/
        work_dir = run_dir / f"work_{attempt}"
        work_dir.mkdir(exist_ok=True)
        work_code = work_dir / f"{code_path.stem}.py"
        shutil.copy2(code_path, work_code)

        render_result = renderer.run(work_code, scene_class, run_dir)

        (run_dir / f"attempt_{attempt}_stdout.log").write_text(render_result.stdout)
        (run_dir / f"attempt_{attempt}_stderr.log").write_text(render_result.stderr)

        if render_result.success:
            logger.success(f"Scene {scene_id} succeeded on attempt {attempt}")
            result = {"success": True, "attempts": attempt, "mp4": str(render_result.mp4_path)}
            (run_dir / "result.json").write_text(json.dumps(result, indent=2))
            return result

        last_error = render_result.stderr
        logger.warning(f"Render failed on attempt {attempt}:\n{last_error[-500:]}")

    # All attempts exhausted
    logger.error(f"Scene {scene_id} failed after {MAX_ATTEMPTS} attempts")
    result = {"success": False, "attempts": MAX_ATTEMPTS, "final_error": last_error}
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    return result
