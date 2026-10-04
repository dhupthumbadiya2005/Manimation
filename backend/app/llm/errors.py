"""User-facing failures. Each carries a message safe to show in the CLI/UI."""

from __future__ import annotations

import anthropic


class PipelineStop(Exception):
    """Stops the whole run (not just one scene). ``user_message`` is shown as-is."""

    code = "stopped"

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class CreditsExhaustedError(PipelineStop):
    code = "credits_exhausted"


class BudgetExceededError(PipelineStop):
    code = "budget_exceeded"


class LLMConfigError(PipelineStop):
    code = "llm_config"


class LLMRefusalError(Exception):
    """The model declined this one request; the caller decides how to degrade."""


CREDITS_MESSAGE = (
    "Your Anthropic credit balance has run out, so generation was paused.\n"
    "Everything finished so far is saved. Add credits at "
    "https://console.anthropic.com/settings/billing, then re-run with --resume "
    "to continue where it stopped (completed steps are not paid for again)."
)


def translate_api_error(err: anthropic.APIStatusError) -> Exception:
    """Map SDK errors to pipeline errors; returns the original if not special."""
    message = str(getattr(err, "message", "") or err)
    if err.status_code == 402 or getattr(err, "type", None) == "billing_error":
        return CreditsExhaustedError(CREDITS_MESSAGE)
    # Low balance can also surface as a 400 invalid_request_error; there is no
    # dedicated type for it, so this one case falls back to the message text.
    if err.status_code == 400 and "credit balance" in message.lower():
        return CreditsExhaustedError(CREDITS_MESSAGE)
    if err.status_code == 400 and "anthropic-workspace-id" in message:
        return LLMConfigError(
            "This API key is not scoped to a workspace. Set ANTHROPIC_WORKSPACE_ID in .env "
            "(Console -> Settings -> Workspaces, id starts with 'wrkspc_'), or use a "
            "workspace-scoped API key."
        )
    if isinstance(err, anthropic.AuthenticationError):
        return LLMConfigError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY in .env.")
    if isinstance(err, anthropic.PermissionDeniedError):
        return LLMConfigError(f"The API key is not allowed to do this: {message}")
    if isinstance(err, anthropic.NotFoundError):
        return LLMConfigError(f"Model not available to this account: {message}")
    return err
