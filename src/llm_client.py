"""Unified LLM client — dispatches to Gemini or OpenAI based on config.

Falls back to OpenAI automatically if Gemini returns a quota/auth error.
"""
from loguru import logger

from src.config import config


def complete(system_prompt: str, user_prompt: str, max_tokens: int = 8192) -> str:
    """Call the configured LLM and return the raw text response.

    If config.llm_provider is 'gemini' but the call fails with a quota or auth
    error, it retries once with OpenAI as a fallback.
    """
    if config.llm_provider == "gemini":
        try:
            return _gemini(system_prompt, user_prompt, max_tokens)
        except Exception as exc:
            err = str(exc)
            if any(k in err for k in ("RESOURCE_EXHAUSTED", "429", "quota", "API_KEY_INVALID", "401")):
                logger.warning(
                    f"Gemini error ({type(exc).__name__}: {err[:120]}). "
                    "Falling back to OpenAI …"
                )
                return _openai(system_prompt, user_prompt, max_tokens)
            raise
    return _openai(system_prompt, user_prompt, max_tokens)


def _gemini(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError

    if not config.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set. Add it to .env or set LLM_PROVIDER=openai.")

    client = genai.Client(api_key=config.gemini_api_key)
    try:
        response = client.models.generate_content(
            model=config.gemini_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
            ),
        )
    except ClientError as exc:
        # Re-raise immediately so the fallback in complete() can catch it
        # without waiting for tenacity's retry delay.
        raise exc from exc
    return response.text.strip()


def _openai(system_prompt: str, user_prompt: str, max_tokens: int) -> str:
    import openai

    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to .env or set LLM_PROVIDER=gemini.")

    client = openai.OpenAI(api_key=config.openai_api_key)
    response = client.chat.completions.create(
        model=config.openai_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()
