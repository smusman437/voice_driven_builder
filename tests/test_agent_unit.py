import pytest

from app.agent.service import RequirementAudioAgent
from app.llm.text_generation import ScriptGeneration
from app.settings import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        elevenlabs_api_key="k",
        openai_api_key="o",
        anthropic_api_key="a",
        llm_provider="openai",
        llm_fallback_provider="mock",
        output_dir=tmp_path,
    )


@pytest.mark.asyncio
async def test_agent_writes_mp3(monkeypatch, settings: Settings):
    async def fake_generate(*_a, **_k):
        return ScriptGeneration(
            text="Hello from the test script.",
            provider_used="openai",
            used_fallback=False,
        )

    async def fake_tts(text: str, _s: Settings):
        assert "test script" in text
        return b"ID3fake"

    monkeypatch.setattr("app.agent.service.generate_script_text", fake_generate)
    monkeypatch.setattr("app.agent.service.synthesize_to_mp3", fake_tts)

    agent = RequirementAudioAgent(settings)
    result = await agent.run("Build a landing page", use_agent_tools=False)
    assert result.script.startswith("Hello")
    assert result.audio_path.is_file()
    assert result.audio_path.suffix == ".mp3"
    assert result.audio_path.read_bytes() == b"ID3fake"
