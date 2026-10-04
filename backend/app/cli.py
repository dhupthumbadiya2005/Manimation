"""Command-line entry point.

    uv run python -m app.cli "Explain the Pythagorean theorem visually"
    uv run python -m app.cli --resume data/projects/<id> --budget 1.50
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

from app import config
from app.llm.budget import Budget
from app.llm.errors import CreditsExhaustedError, PipelineStop


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="manimation", description="Prompt -> 3Blue1Brown-style Manim video")
    p.add_argument("request", nargs="?", help="what the video should explain")
    p.add_argument("--resume", type=Path, help="continue an existing project folder")
    p.add_argument("--budget", type=float, help=f"max USD for this video (default {config.settings.budget_usd})")
    p.add_argument("--scenes", type=int, help=f"max scenes (default {config.settings.max_scenes})")
    p.add_argument("--profile", choices=sorted(config.PROFILES), help="economy (default) or quality")
    p.add_argument("--tts", choices=["deepgram", "gtts", "silent"], help="narration for the final render")
    p.add_argument("--voice", help="Deepgram Flux voice, e.g. flux-priya-en, flux-meena-en, flux-naveen-en")
    p.add_argument("--quality", choices=["low", "medium", "high"], default="high", help="final render quality")
    p.add_argument("--audience", default="curious high-school and university students")
    p.add_argument("--theme", default="3b1b", help="theme id: 3b1b, chalkboard, light_paper, solarized")
    p.add_argument("--demo", action="store_true", help="answer from the cookbook instead of Claude (no API calls)")
    args = p.parse_args(argv)
    if not args.request and not args.resume:
        p.error("give a request, or --resume <project folder>")

    overrides = {k: v for k, v in {"max_scenes": args.scenes,
                                    "profile": args.profile, "tts": args.tts, "tts_voice": args.voice,
                                    "demo_mode": True if args.demo else None}.items() if v is not None}
    config.settings = dataclasses.replace(config.settings, **overrides)

    from app.pipeline import orchestrator  # after settings are final

    # manim configures root logging at import; keep HTTP request logs out of the output
    for name in ("httpx2", "httpx", "anthropic"):
        logging.getLogger(name).setLevel(logging.WARNING)

    project = orchestrator.open_project(request=args.request, resume=args.resume,
                                        audience=args.audience, budget_usd=args.budget,
                                        theme_id=args.theme)
    try:
        orchestrator.run(project, final_quality=args.quality)
        code = 0
    except PipelineStop as stop:
        banner = "CREDITS EXHAUSTED" if isinstance(stop, CreditsExhaustedError) else "STOPPED"
        print(f"\n==== {banner} ====\n{stop.user_message}\n"
              f"Resume with: uv run python -m app.cli --resume {project.root}\n", file=sys.stderr)
        code = 2
    if project.usage_path.exists():
        s = Budget(project.state.budget_usd, project.usage_path).summary()
        print(f"\nCost: ${s['spent_usd']:.3f} of ${s['limit_usd']:.2f} in {s['calls']} call(s); "
              f"by agent {s['by_agent']}; cache hit ratio {s['cache_hit_ratio']}")
    for sid, st in project.state.scenes.items():
        print(f"  {sid}: {st.status} (fixer turns {st.fixer_turns}, edits {st.fixer_edits})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
