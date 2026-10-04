"""Pipeline evaluation over a fixed prompt set.

Reports, per prompt and overall: scenes that rendered cleanly on the first
try, scenes the Fixer repaired, failures, Fixer turns/edits, cost and time.

    uv run python scripts/eval.py --limit 3 --budget-per-video 0.40 --total-budget 2
    uv run python scripts/eval.py --demo --limit 2        # exercises the script, no API calls

Uses real API credits unless --demo. ``--total-budget`` stops the run once
reached (each video is also capped by --budget-per-video).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.llm.budget import Budget  # noqa: E402
from app.llm.errors import CreditsExhaustedError, PipelineStop  # noqa: E402

PROMPTS = [
    # math
    "Visualize the Pythagorean theorem with a geometric proof",
    "Why the derivative of x squared is 2x, using tangent lines",
    "The area under a curve as a limit of Riemann sums",
    "A 2x2 matrix as a linear transformation of the plane",
    "Euler's formula: e to the i theta traces the unit circle",
    "The sum of the angles of a triangle is 180 degrees",
    # physics
    "Projectile motion: why the path is a parabola",
    "Simple harmonic motion of a pendulum for small angles",
    "Adding two waves: constructive and destructive interference",
    "Vectors: adding forces tip to tail to find the net force",
    # computer science
    "How binary search finds a number in a sorted array",
    "Breadth-first search on a tree, level by level",
    "Bubble sort on an array of six numbers",
    "Big-O: comparing n, n log n and n squared growth",
    "How a stack works: push and pop",
]


def evaluate(prompt: str, budget: float, out_dir: Path) -> dict:
    from app.pipeline import orchestrator

    start = time.monotonic()
    project = orchestrator.open_project(request=prompt, budget_usd=budget, log=lambda *_: None)
    error = None
    try:
        orchestrator.run(project, final_quality="low", log=lambda *_: None)
    except PipelineStop as stop:
        error = stop.code
        if isinstance(stop, CreditsExhaustedError):
            raise
    scenes = list(project.state.scenes.values())
    summary = Budget(budget, project.usage_path).summary()
    return {
        "prompt": prompt,
        "project": project.id,
        "scenes": len(scenes),
        "first_try": sum(s.status == "passed" and s.fixer_turns == 0 for s in scenes),
        "fixed": sum(s.status in ("passed", "passed_with_warnings") and s.fixer_turns > 0 for s in scenes),
        "warnings": sum(s.status == "passed_with_warnings" for s in scenes),
        "failed": sum(s.status == "failed" for s in scenes),
        "fixer_turns": sum(s.fixer_turns for s in scenes),
        "fixer_edits": sum(s.fixer_edits for s in scenes),
        "autofixes": sum(len(s.autofixes) for s in scenes),
        "video": project.final_path.exists(),
        "cost_usd": summary["spent_usd"],
        "cost_by_agent": summary["by_agent"],
        "seconds": round(time.monotonic() - start, 1),
        "error": error,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=len(PROMPTS))
    p.add_argument("--budget-per-video", type=float, default=0.40)
    p.add_argument("--total-budget", type=float, default=3.0)
    p.add_argument("--scenes", type=int, default=2)
    p.add_argument("--demo", action="store_true")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    data_dir = config.settings.data_dir / "eval" / time.strftime("%Y%m%d-%H%M%S")
    config.settings = dataclasses.replace(config.settings, data_dir=data_dir, max_scenes=args.scenes,
                                          tts="silent", demo_mode=args.demo or config.settings.demo_mode)
    results, total = [], 0.0
    for prompt in PROMPTS[: args.limit]:
        if total + args.budget_per_video > args.total_budget:
            print(f"Stopping: next video could exceed the total budget (${total:.2f} spent).")
            break
        try:
            r = evaluate(prompt, args.budget_per_video, data_dir)
        except CreditsExhaustedError:
            print("Credits exhausted; stopping the evaluation.")
            break
        total += r["cost_usd"]
        results.append(r)
        print(f"{'OK ' if r['video'] else 'ERR'} ${r['cost_usd']:.3f} {r['seconds']:>6}s  scenes {r['scenes']}: "
              f"first-try {r['first_try']}, fixed {r['fixed']}, failed {r['failed']}  | {prompt}")

    if results:
        scenes = sum(r["scenes"] for r in results)
        report = {
            "videos": len(results),
            "videos_ok": sum(r["video"] for r in results),
            "scenes": scenes,
            "first_try_rate": round(sum(r["first_try"] for r in results) / max(scenes, 1), 3),
            "success_rate": round(sum(r["first_try"] + r["fixed"] for r in results) / max(scenes, 1), 3),
            "mean_fixer_turns_per_scene": round(sum(r["fixer_turns"] for r in results) / max(scenes, 1), 2),
            "total_cost_usd": round(total, 4),
            "mean_cost_per_video_usd": round(total / len(results), 4),
            "results": results,
        }
        out = args.out or data_dir / "report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1))
        print(f"\nvideos ok {report['videos_ok']}/{report['videos']}, scene success {report['success_rate']:.0%} "
              f"(first try {report['first_try_rate']:.0%}), fixer turns/scene {report['mean_fixer_turns_per_scene']}, "
              f"cost ${report['total_cost_usd']:.3f} (${report['mean_cost_per_video_usd']:.3f}/video)\nreport: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
