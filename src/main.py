"""
CLI entrypoint.

Phase 1 mode:  python main.py --scene scenes/scene_01.json --run-id test1
Phase 2 mode:  python main.py --topic "explain binary search" --run-id run1
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

from src import plan_schema, planner, retry_loop


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _video_duration(mp4_path: str) -> float:
    """Return duration in seconds of an mp4 file using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                mp4_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Phase 1 single-scene mode (unchanged logic)
# ---------------------------------------------------------------------------

def _run_single_scene(scene_file: str, run_id: str) -> None:
    scene_path = Path(scene_file)
    if not scene_path.exists():
        logger.error(f"Scene file not found: {scene_path}")
        sys.exit(1)

    scene = json.loads(scene_path.read_text())
    scene_id = scene.get("scene_id", "unknown")
    run_dir = Path("runs") / run_id / f"scene_{scene_id}"
    logger.info(f"Run directory: {run_dir}")

    result = retry_loop.run(scene, run_dir)

    if result["success"]:
        print(f"\n✓ SUCCESS — scene {scene_id} rendered in {result['attempts']} attempt(s)")
        print(f"  Video: {result['mp4']}")
        print(f"  Result: {run_dir / 'result.json'}")
        sys.exit(0)
    else:
        print(f"\n✗ FAILED — scene {scene_id} after {result['attempts']} attempt(s)")
        print(f"  Result: {run_dir / 'result.json'}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Phase 2 planner mode
# ---------------------------------------------------------------------------

def _run_topic(topic: str, run_id: str) -> None:
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    wall_start = time.time()

    # 1. Generate plan (with one retry on validation failure)
    logger.info(f"Generating plan for topic: {topic!r}")
    gen_start = time.time()
    plan = planner.generate(topic)
    gen_elapsed = time.time() - gen_start
    logger.info(f"Plan generated in {gen_elapsed:.1f}s")

    valid, error = plan_schema.validate(plan)
    if not valid:
        logger.warning(f"Plan validation failed: {error}")
        logger.info("Retrying planner with validation error appended …")
        plan = planner.generate(topic, previous_error=error, previous_plan=plan)
        valid, error = plan_schema.validate(plan)
        if not valid:
            logger.error(f"Plan still invalid after retry: {error}")
            print(f"\n✗ FAILED — planner produced an invalid plan: {error}")
            sys.exit(1)

    logger.info("Plan validated successfully")

    # 2. Save plan.json BEFORE any rendering
    plan_path = run_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    logger.info(f"Plan saved -> {plan_path}")

    scenes = plan["scenes"]
    target_dur = plan.get("target_duration_seconds", plan_schema.DEFAULT_TARGET_DURATION)
    total_hint = sum(plan_schema.scene_duration_hint(s) for s in scenes)

    print(f"\nPlan: {len(scenes)} scenes | target {target_dur:.0f}s | hint total {total_hint:.0f}s")
    print(f"  Saved: {plan_path}\n")

    # 3. Render each scene — inject topic so coder has full context
    scene_results: list[dict] = []
    render_start = time.time()
    for scene in scenes:
        sid = scene["scene_id"]
        scene["_topic"] = topic  # pass topic through to coder without polluting plan.json
        scene_run_dir = run_dir / f"scene_{sid}"
        logger.info(f"Rendering scene {sid}/{len(scenes)}: {scene.get('title', '')[:60]}")
        result = retry_loop.run(scene, scene_run_dir)
        result["scene_id"] = sid
        result["duration_hint"] = plan_schema.scene_duration_hint(scene)
        scene_results.append(result)

    render_elapsed = time.time() - render_start
    wall_elapsed = time.time() - wall_start

    # 4. Report results
    total_actual = 0.0
    successes = [r for r in scene_results if r["success"]]
    failures = [r for r in scene_results if not r["success"]]

    print(f"\n{'─' * 64}")
    print(f"{'Scene':<8} {'Title':<35} {'Hint':>6} {'Actual':>7} {'Attempts':>9}")
    print(f"{'─' * 64}")
    for r in scene_results:
        sid = r["scene_id"]
        scene = next(s for s in scenes if s["scene_id"] == sid)
        title_short = (scene.get("title") or "")[:34]
        hint = r["duration_hint"]
        actual = 0.0
        if r["success"] and r.get("mp4"):
            actual = _video_duration(r["mp4"])
            total_actual += actual
        status = "✓" if r["success"] else "✗"
        print(
            f"{status} {sid:<6} {title_short:<35} "
            f"{hint:>5.0f}s {actual:>6.1f}s {r['attempts']:>6}/{retry_loop.MAX_ATTEMPTS}"
        )
    print(f"{'─' * 64}")
    print(f"\nResults : {len(successes)}/{len(scenes)} scenes rendered successfully")
    print(f"Timing  : hint {total_hint:.0f}s | mp4 actual {total_actual:.1f}s")
    print(f"Wall    : plan gen {gen_elapsed:.1f}s | render {render_elapsed:.1f}s "
          f"| total {wall_elapsed:.1f}s")

    if failures:
        print(f"\nFailed scenes: {[r['scene_id'] for r in failures]}")
        print("Inspect plan.json and individual result.json files for details.")

    sys.exit(0 if not failures else 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Manim AI pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scene", help="Path to a scene JSON file (Phase 1 mode)")
    group.add_argument("--topic", help="Topic string to plan and render (Phase 2 mode)")
    parser.add_argument("--run-id", required=True, help="Unique run identifier")
    args = parser.parse_args()

    if args.scene:
        _run_single_scene(args.scene, args.run_id)
    else:
        _run_topic(args.topic, args.run_id)


if __name__ == "__main__":
    main()
