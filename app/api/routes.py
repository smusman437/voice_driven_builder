"""HTTP routes."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from anthropic import APIError as AnthropicAPIError
from elevenlabs.core.api_error import ApiError as ElevenLabsApiError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from google.genai import errors as genai_errors
from openai import APIStatusError, AuthenticationError, RateLimitError

from app.agent.service import RequirementAudioAgent
from app.api.schemas import (
    AudioListItem,
    RequirementRequest,
    RequirementResponse,
    build_response,
)
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _openai_rate_limit_info(exc: RateLimitError) -> tuple[str, int]:
    err_code: str | None = None
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err_code = (body.get("error") or {}).get("code")
    if err_code is None:
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                data = resp.json()
                err_code = (data.get("error") or {}).get("code")
            except Exception:
                err_code = None
    if err_code == "insufficient_quota":
        return (
            "OpenAI quota or billing exhausted (insufficient_quota). "
            "Set LLM_PROVIDER=mock to test without an LLM API, or LLM_PROVIDER=groq "
            "with a free key from https://console.groq.com/keys . See README.",
            402,
        )
    return (
        "LLM rate limit exceeded. Wait and retry, or switch LLM_PROVIDER in .env.",
        429,
    )


def _elevenlabs_error_detail(exc: ElevenLabsApiError) -> tuple[str, int]:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict):
            code = detail.get("code")
            message = detail.get("message")
            if code == "paid_plan_required":
                return (
                    "ElevenLabs rejected the selected voice for free plan (paid_plan_required). "
                    "Set ELEVENLABS_VOICE_ID to a public/premade voice. "
                    "The app also auto-tries fallback public voices.",
                    402,
                )
            if isinstance(message, str) and message.strip():
                return (message, exc.status_code or 502)
    return ("ElevenLabs TTS request failed.", exc.status_code or 502)

router = APIRouter()

# Filenames produced by RequirementAudioAgent are uuid hex + .mp3
_SAFE_MP3 = re.compile(r"^[a-f0-9]{32}\.mp3$")


def get_agent(settings: Settings = Depends(get_settings)) -> RequirementAudioAgent:
    return RequirementAudioAgent(settings)


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "llm_provider": settings.llm_provider}


@router.post("/v1/requirements-to-audio", response_model=RequirementResponse)
async def requirements_to_audio(
    body: RequirementRequest,
    agent: RequirementAudioAgent = Depends(get_agent),
) -> RequirementResponse:
    try:
        result = await agent.run(
            body.requirement,
            use_agent_tools=body.use_agent_tools,
        )
        return build_response(result)
    except ValueError as e:
        logger.warning("Invalid request or empty result: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RateLimitError as e:
        logger.warning("LLM rate limit / quota: %s", e)
        detail, status = _openai_rate_limit_info(e)
        raise HTTPException(status_code=status, detail=detail) from e
    except AuthenticationError as e:
        logger.warning("LLM authentication failed: %s", e)
        raise HTTPException(
            status_code=401,
            detail="LLM API rejected the key. Check OPENAI_API_KEY, GROQ_API_KEY, or ANTHROPIC_API_KEY.",
        ) from e
    except APIStatusError as e:
        logger.warning("LLM API error: %s", e)
        raise HTTPException(
            status_code=502,
            detail=getattr(e, "message", None) or str(e) or "LLM request failed.",
        ) from e
    except AnthropicAPIError as e:
        logger.warning("Anthropic error: %s", e)
        raise HTTPException(
            status_code=502,
            detail=getattr(e, "message", None) or str(e) or "Anthropic request failed.",
        ) from e
    except genai_errors.APIError as e:
        logger.warning("Gemini API error: %s", e)
        detail = getattr(e, "message", None) or str(e) or "Gemini request failed."
        status = 429 if getattr(e, "code", None) in (429, 503) else 502
        raise HTTPException(status_code=status, detail=detail) from e
    except ElevenLabsApiError as e:
        logger.warning("ElevenLabs TTS error: %s", e)
        detail, status = _elevenlabs_error_detail(e)
        raise HTTPException(status_code=status, detail=detail) from e
    except Exception as e:
        logger.exception("Agent run failed.")
        raise HTTPException(status_code=502, detail="Upstream LLM or TTS failed.") from e


@router.get("/v1/audio", response_model=list[AudioListItem])
async def list_audio(settings: Settings = Depends(get_settings)) -> list[AudioListItem]:
    out_dir = Path(settings.output_dir).resolve()
    if not out_dir.is_dir():
        return []

    items: list[AudioListItem] = []
    for path in out_dir.glob("*.mp3"):
        if not _SAFE_MP3.match(path.name):
            continue
        stat = path.stat()
        items.append(
            AudioListItem(
                filename=path.name,
                download_path=f"/v1/audio/{path.name}",
                created_at=stat.st_mtime,
                size_bytes=stat.st_size,
            )
        )
    items.sort(key=lambda item: item.created_at, reverse=True)
    return items


@router.get("/v1/audio/{filename}")
async def download_audio(
    filename: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    if not _SAFE_MP3.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    path = Path(settings.output_dir).resolve() / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path, media_type="audio/mpeg", filename=filename)
