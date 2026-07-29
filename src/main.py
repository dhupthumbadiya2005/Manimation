"""CLI entrypoint: python -m src.main --scene scenes/scene_01.json --run-id test1"""
import argparse
import json
import sys
from pathlib import Path

from loguru import logger

from src import retry_loop


def main():
    parser = argparse.ArgumentParser(description="Manim AI — Phase 1 pipeline")
    parser.add_argument("--scene", required=True, help="Path to scene JSON file")
    parser.add_argument("--run-id", required=True, help="Unique run identifier (used for output directory)")
    args = parser.parse_args()

    scene_path = Path(args.scene)
    if not scene_path.exists():
        logger.error(f"Scene file not found: {scene_path}")
        sys.exit(1)

    scene = json.loads(scene_path.read_text())
    scene_id = scene.get("scene_id", "unknown")

    run_dir = Path("runs") / args.run_id / f"scene_{scene_id}"
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


if __name__ == "__main__":
    main()
