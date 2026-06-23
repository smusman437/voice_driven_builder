"""Opt-in live integration tests (real OpenAI + ElevenLabs API calls)."""

from __future__ import annotations

import pytest

from app.agent.service import RequirementAudioAgent
from app.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
def live_settings(tmp_path) -> Settings:
    base = Settings()
    if not base.openai_api_key:
        pytest.skip("OPENAI_API_KEY is required for live integration tests")
    if not base.elevenlabs_api_key:
        pytest.skip("ELEVENLABS_API_KEY is required for live integration tests")
    return Settings(
        elevenlabs_api_key=base.elevenlabs_api_key,
        openai_api_key=base.openai_api_key,
        llm_provider="openai",
        llm_fallback_provider="mock",
        openai_model=base.openai_model,
        elevenlabs_voice_id=base.elevenlabs_voice_id,
        elevenlabs_model_id=base.elevenlabs_model_id,
        output_dir=tmp_path,
        agent_use_tools=False,
    )


@pytest.mark.asyncio
async def test_agent_live_openai_and_elevenlabs(live_settings: Settings) -> None:
    agent = RequirementAudioAgent(live_settings)
    result = await agent.run(
        "In two short sentences, describe an MVP for a simple todo app.",
        use_agent_tools=False,
    )

    assert result.script.strip()
    assert result.llm_provider_used == "openai"
    assert not result.llm_fallback_used
    assert result.audio_path.is_file()
    assert result.audio_path.suffix == ".mp3"
    assert result.audio_path.stat().st_size > 100
