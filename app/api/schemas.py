from pathlib import Path

from pydantic import BaseModel, Field

from app.agent.service import RequirementAudioResult


class RequirementRequest(BaseModel):
    """Request body for POST /v1/requirements-to-audio."""

    requirement: str = Field(
        ...,
        min_length=3,
        description="Client requirement or brief in natural language.",
    )
    use_agent_tools: bool | None = Field(
        default=None,
        description="Override global setting: use structured tool for final script.",
    )


class RequirementResponse(BaseModel):
    script: str
    audio_filename: str
    download_path: str
    llm_provider: str = Field(
        description="Provider that produced the script (after any fallback).",
    )
    llm_provider_configured: str = Field(
        description="LLM_PROVIDER from settings (requested).",
    )
    llm_fallback_used: bool = Field(
        description="True if primary LLM failed and fallback produced the script.",
    )
    used_tools: bool


class AudioListItem(BaseModel):
    filename: str
    download_path: str
    created_at: float = Field(description="Unix timestamp (seconds).")
    size_bytes: int


def build_response(result: RequirementAudioResult) -> RequirementResponse:
    p: Path = result.audio_path
    return RequirementResponse(
        script=result.script,
        audio_filename=p.name,
        download_path=f"/v1/audio/{p.name}",
        llm_provider=result.llm_provider_used,
        llm_provider_configured=result.llm_provider_configured,
        llm_fallback_used=result.llm_fallback_used,
        used_tools=result.used_tools,
    )
