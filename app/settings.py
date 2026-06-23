"""Application configuration loaded from environment."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings; use `.env` locally (see `.env.example`)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- API keys (see README for where to obtain) ---
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    groq_api_key: str | None = Field(default=None, description="Groq API key (free tier)")
    gemini_api_key: str | None = Field(
        default=None,
        description="Google Gemini API key (Google AI Studio)",
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    elevenlabs_api_key: str = Field(..., description="ElevenLabs API key")

    # --- LLM ---
    # openai / anthropic: paid APIs | groq/gemini: free-tier options | mock: no LLM
    llm_provider: Literal["openai", "anthropic", "groq", "mock", "gemini"] = "mock"
    llm_fallback_provider: Literal[
        "none", "mock", "openai", "anthropic", "groq", "gemini"
    ] = "mock"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_model: str = "gemini-1.5-flash"
    # Tried in order when Gemini returns quota/rate-limit.
    gemini_model_candidates: str = "gemini-1.5-flash,gemini-1.5-flash-8b,gemini-2.0-flash"

    # --- ElevenLabs TTS ---
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    # --- Agent ---
    agent_use_tools: bool = True
    agent_max_turns: int = 12
    log_level: str = "INFO"

    output_dir: Path = Field(default=Path("outputs"))

    @model_validator(mode="after")
    def _validate_provider_key(self) -> "Settings":
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY or GOOGLE_API_KEY is required when LLM_PROVIDER=gemini"
            )
        if self.llm_fallback_provider == self.llm_provider:
            raise ValueError("LLM_FALLBACK_PROVIDER must be different from LLM_PROVIDER")
        if self.llm_fallback_provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when LLM_FALLBACK_PROVIDER=openai"
            )
        if self.llm_fallback_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_FALLBACK_PROVIDER=anthropic"
            )
        if self.llm_fallback_provider == "groq" and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_FALLBACK_PROVIDER=groq")
        if self.llm_fallback_provider == "gemini" and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY or GOOGLE_API_KEY is required when LLM_FALLBACK_PROVIDER=gemini"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
