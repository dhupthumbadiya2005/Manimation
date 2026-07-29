"""Central configuration — loaded once from .env / environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    gemini_api_key: str = ""

    # "gemini" | "openai"
    llm_provider: str = "gemini"

    gemini_model: str = "gemini-2.0-flash"
    openai_model: str = "gpt-4o-mini"

    # "ql" = 480p15 (fast)  |  "qh" = 1080p60 (high quality)
    render_quality: str = "ql"

    max_retries: int = 3


config = Config()
