"""Orchestrates LLM script generation + MP3 persistence."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.llm.text_generation import generate_script_text
from app.settings import Settings
from app.tts.elevenlabs_tts import synthesize_to_mp3, write_mp3

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequirementAudioResult:
    """Outcome of running the requirement → audio pipeline."""

    script: str
    audio_path: Path
    llm_provider_configured: str
    llm_provider_used: str
    llm_fallback_used: bool
    used_tools: bool


class RequirementAudioAgent:
    """High-level agent: requirement text → LLM narration → ElevenLabs MP3 file."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, requirement: str, use_agent_tools: bool | None = None) -> RequirementAudioResult:
        use_tools = (
            self._settings.agent_use_tools if use_agent_tools is None else use_agent_tools
        )
        logger.info(
            "Running agent (provider=%s, use_tools=%s).",
            self._settings.llm_provider,
            use_tools,
        )
        gen = await generate_script_text(requirement.strip(), self._settings, use_tools)
        script = gen.text
        if not script:
            raise ValueError("LLM returned an empty script.")

        if gen.used_fallback:
            logger.info(
                "Script from fallback LLM: requested=%s, used=%s.",
                self._settings.llm_provider,
                gen.provider_used,
            )

        mp3 = await synthesize_to_mp3(script, self._settings)
        out_dir = Path(self._settings.output_dir).resolve()
        filename = f"{uuid.uuid4().hex}.mp3"
        out_path = out_dir / filename
        write_mp3(out_path, mp3)
        logger.info("Wrote audio file: %s", out_path)

        return RequirementAudioResult(
            script=script,
            audio_path=out_path,
            llm_provider_configured=self._settings.llm_provider,
            llm_provider_used=gen.provider_used,
            llm_fallback_used=gen.used_fallback,
            used_tools=use_tools,
        )
