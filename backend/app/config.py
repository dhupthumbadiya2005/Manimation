"""Settings, read once from the environment (and ``.env`` at the repo root)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
KNOWLEDGE_DIR = BACKEND_DIR / "knowledge"
PROMPTS_DIR = Path(__file__).resolve().parent / "pipeline" / "prompts"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(REPO_DIR / ".env")


@dataclass(frozen=True)
class AgentConfig:
    model: str
    effort: str
    max_tokens: int


# "economy" (default) keeps every agent on Sonnet; "quality" moves the two
# reasoning-heavy agents to Opus (~2x the per-token price).
PROFILES: dict[str, dict[str, AgentConfig]] = {
    "economy": {
        "director": AgentConfig("claude-sonnet-5-5", "medium", 8000),
        "coder": AgentConfig("claude-sonnet-5-5", "medium", 12000),
        "fixer": AgentConfig("claude-sonnet-5-5", "medium", 6000),
    },
    "quality": {
        "director": AgentConfig("claude-opus-5-5", "high", 12000),
        "coder": AgentConfig("claude-sonnet-5-5", "high", 16000),
        "fixer": AgentConfig("claude-opus-5-5", "high", 8000),
    },
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("MANIMATION_DATA_DIR", REPO_DIR / "data")))
    profile: str = os.environ.get("MANIMATION_PROFILE", "economy")
    # Hard cap per video project, in USD. The pipeline stops before exceeding it.
    budget_usd: float = float(os.environ.get("MANIMATION_BUDGET_USD", "0.75"))
    workspace_id: str | None = os.environ.get("ANTHROPIC_WORKSPACE_ID") or None
    # Narration for final renders: deepgram | gtts | silent. Defaults to Deepgram when a key is set.
    tts: str = os.environ.get("MANIMATION_TTS") or ("deepgram" if os.environ.get("DEEPGRAM_API_KEY") else "gtts")
    tts_voice: str = os.environ.get("MANIMATION_TTS_VOICE", "flux-priya-en")
    max_scenes: int = int(os.environ.get("MANIMATION_MAX_SCENES", "3"))
    fixer_max_turns: int = int(os.environ.get("MANIMATION_FIXER_MAX_TURNS", "8"))
    render_timeout_s: int = int(os.environ.get("MANIMATION_RENDER_TIMEOUT", "240"))
    # Demo mode: agents answer from the cookbook instead of Claude. No API calls, no cost.
    demo_mode: bool = os.environ.get("MANIMATION_DEMO", "0").lower() in ("1", "true", "yes")

    def agent(self, name: str) -> AgentConfig:
        return PROFILES[self.profile][name]


settings = Settings()
