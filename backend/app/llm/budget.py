"""Per-project spend tracking with a hard cap.

Every LLM call is appended to ``usage.jsonl`` in the project folder, so spend
survives restarts and ``--resume`` keeps counting from where it was.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import BudgetExceededError

# USD per million tokens: (input, output, cache read, cache write 5m)
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-opus-5": (5.00, 25.00, 0.50, 6.25),
    "claude-opus-4-8": (5.00, 25.00, 0.50, 6.25),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-sonnet-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-4-5": (1.00, 5.00, 0.10, 1.25),
}
FALLBACK_PRICE = PRICES["claude-opus-4-8"]  # unknown model -> price conservatively

# Don't start a call with less than this left; a single call can cost a few cents.
MIN_RESERVE_USD = 0.03


@dataclass
class UsageRecord:
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    ts: float


def cost_of(model: str, input_tokens: int, output_tokens: int,
            cache_read: int = 0, cache_write: int = 0) -> float:
    p_in, p_out, p_read, p_write = PRICES.get(model, FALLBACK_PRICE)
    return (input_tokens * p_in + output_tokens * p_out
            + cache_read * p_read + cache_write * p_write) / 1_000_000


class Budget:
    def __init__(self, limit_usd: float, ledger_path: Path | None = None):
        self.limit_usd = limit_usd
        self.ledger_path = ledger_path
        self.records: list[UsageRecord] = []
        if ledger_path and ledger_path.exists():
            for line in ledger_path.read_text().splitlines():
                if line.strip():
                    self.records.append(UsageRecord(**json.loads(line)))

    @property
    def spent_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def remaining_usd(self) -> float:
        return self.limit_usd - self.spent_usd

    def check(self, agent: str) -> None:
        if self.remaining_usd < MIN_RESERVE_USD:
            raise BudgetExceededError(
                f"Stopped before the {agent} step: this video has used ${self.spent_usd:.2f} "
                f"of its ${self.limit_usd:.2f} budget. Progress is saved; re-run with "
                f"--resume --budget <higher amount> to continue."
            )

    def record(self, agent: str, model: str, usage) -> UsageRecord:
        rec = UsageRecord(
            agent=agent,
            model=model,
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            cost_usd=0.0,
            ts=time.time(),
        )
        rec.cost_usd = cost_of(model, rec.input_tokens, rec.output_tokens,
                               rec.cache_read_tokens, rec.cache_write_tokens)
        self.records.append(rec)
        if self.ledger_path:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open("a") as f:
                f.write(json.dumps(rec.__dict__) + "\n")
        return rec

    def summary(self) -> dict:
        by_agent: dict[str, float] = {}
        for r in self.records:
            by_agent[r.agent] = by_agent.get(r.agent, 0.0) + r.cost_usd
        cached = sum(r.cache_read_tokens for r in self.records)
        fresh = sum(r.input_tokens + r.cache_write_tokens for r in self.records)
        return {
            "spent_usd": round(self.spent_usd, 4),
            "limit_usd": self.limit_usd,
            "calls": len(self.records),
            "by_agent": {k: round(v, 4) for k, v in by_agent.items()},
            "cache_hit_ratio": round(cached / (cached + fresh), 2) if cached + fresh else 0.0,
        }
