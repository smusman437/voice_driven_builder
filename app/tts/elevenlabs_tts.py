"""ElevenLabs text-to-speech with retries."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from elevenlabs import ElevenLabs, VoiceSettings
from elevenlabs.core.api_error import ApiError
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.settings import Settings

logger = logging.getLogger(__name__)

# Public/premade voice IDs documented by ElevenLabs examples.
_FALLBACK_VOICE_IDS = [
    "JBFqnCBsd6RMkjVDRZzb",
    "EXAVITQu4vr4xnSDxMaL",
    "onwK4e9ZLuTAKqWW03F9",
    "XB0fDUnXU5powFXDhCwa",
]


def _extract_api_error_code(exc: ApiError) -> str | None:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict):
            code = detail.get("code")
            if isinstance(code, str):
                return code
    return None


def _is_non_retryable_tts_error(exc: Exception) -> bool:
    if not isinstance(exc, ApiError):
        return False
    return exc.status_code in (400, 401, 402, 403)


def _should_retry_tts(exc: Exception) -> bool:
    return not _is_non_retryable_tts_error(exc)


def _is_paid_plan_voice_error(exc: ApiError) -> bool:
    return exc.status_code == 402 and _extract_api_error_code(exc) == "paid_plan_required"


def _convert_with_voice(client: ElevenLabs, text: str, settings: Settings, voice_id: str) -> bytes:
    stream = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=settings.elevenlabs_model_id,
        text=text,
        voice_settings=VoiceSettings(
            stability=0.45,
            similarity_boost=0.75,
            style=0.35,
            speed=1.0,
            use_speaker_boost=True,
        ),
    )
    chunks: list[bytes] = []
    for chunk in stream:
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise RuntimeError("ElevenLabs returned empty audio payload.")
    return data


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=20),
    retry=retry_if_exception_type(Exception) & retry_if_exception(_should_retry_tts),
)
def _convert_sync(text: str, settings: Settings) -> bytes:
    """Blocking SDK call; run in a thread from async code."""
    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    try:
        return _convert_with_voice(client, text, settings, settings.elevenlabs_voice_id)
    except ApiError as exc:
        # Free-tier accounts can fail on library voices; try public voices automatically.
        if not _is_paid_plan_voice_error(exc):
            raise
        logger.warning(
            "Configured voice '%s' requires paid plan; trying fallback public voices.",
            settings.elevenlabs_voice_id,
        )
        for voice_id in _FALLBACK_VOICE_IDS:
            if voice_id == settings.elevenlabs_voice_id:
                continue
            try:
                return _convert_with_voice(client, text, settings, voice_id)
            except ApiError as fallback_exc:
                if _is_paid_plan_voice_error(fallback_exc):
                    continue
                raise
        raise


async def synthesize_to_mp3(text: str, settings: Settings) -> bytes:
    if not text.strip():
        raise ValueError("Cannot synthesize empty script.")
    logger.debug("Synthesizing audio (%d chars).", len(text))
    try:
        return await asyncio.to_thread(_convert_sync, text, settings)
    except Exception:
        logger.exception("ElevenLabs TTS failed after retries.")
        raise


def write_mp3(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
