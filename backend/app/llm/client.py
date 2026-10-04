"""Single entry point for every Claude call in the pipeline.

Cost controls applied here, for every agent:
- budget check before the call, usage + cost recorded after it
- the large static system prompt is a cache breakpoint (shared by every scene),
  and top-level automatic caching covers growing tool-loop conversations
- per-agent model / effort / max_tokens from the active profile
- refusals fall back server-side (``fallbacks: "default"``) instead of failing
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from app import config

from .budget import Budget
from .errors import LLMRefusalError, PipelineStop, translate_api_error

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLM:
    def __init__(self, budget: Budget, log: Callable[[str], None] = print,
                 client: anthropic.Anthropic | None = None):
        self.budget = budget
        self.log = log
        if client is None:
            headers = {"anthropic-workspace-id": config.settings.workspace_id} if config.settings.workspace_id else None
            client = anthropic.Anthropic(default_headers=headers, max_retries=3)
        self.client = client

    @staticmethod
    def _system_blocks(system: str) -> list[dict[str, Any]]:
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def _params(self, agent: str, system: str) -> dict[str, Any]:
        cfg = config.settings.agent(agent)
        return {
            "model": cfg.model,
            "max_tokens": cfg.max_tokens,
            "system": self._system_blocks(system),
            "cache_control": {"type": "ephemeral"},
            "betas": [FALLBACK_BETA],
            "fallbacks": "default",
        }

    def _run(self, agent: str, fn: Callable[[], Any]):
        self.budget.check(agent)
        try:
            response = fn()
        except anthropic.APIStatusError as err:
            raise translate_api_error(err) from err
        except anthropic.APIConnectionError as err:
            raise PipelineStop("Could not reach the Anthropic API (network error). "
                               "Check your connection and re-run with --resume.") from err
        rec = self.budget.record(agent, response.model, response.usage)
        self.log(f"  [{agent}] {response.model}: {rec.input_tokens + rec.cache_read_tokens + rec.cache_write_tokens} in "
                 f"({rec.cache_read_tokens} cached) / {rec.output_tokens} out = ${rec.cost_usd:.4f} "
                 f"(total ${self.budget.spent_usd:.3f} of ${self.budget.limit_usd:.2f})")
        if response.stop_reason == "refusal":
            raise LLMRefusalError(f"{agent} request was declined by the model")
        return response

    def structured(self, agent: str, system: str, user: str, output_format: type[T]) -> T:
        """One call whose reply is validated into ``output_format``."""
        params = self._params(agent, system)
        cfg = config.settings.agent(agent)
        response = self._run(agent, lambda: self.client.beta.messages.parse(
            **params,
            output_config={"effort": cfg.effort},
            output_format=output_format,
            messages=[{"role": "user", "content": user}],
        ))
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise PipelineStop(f"The {agent} reply was cut off or unparseable; try fewer scenes.")
        return response.parsed_output

    def message(self, agent: str, system: str, messages: list[dict[str, Any]],
                tools: list[dict[str, Any]] | None = None):
        """Plain (optionally tool-using) call; the caller owns the loop."""
        params = self._params(agent, system)
        cfg = config.settings.agent(agent)
        extra = {"tools": tools} if tools else {}
        return self._run(agent, lambda: self.client.beta.messages.create(
            **params, **extra,
            output_config={"effort": cfg.effort},
            messages=messages,
        ))
