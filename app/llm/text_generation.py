"""Generate the spoken script via OpenAI-compatible APIs, Anthropic, or mock (no LLM API)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from anthropic import AsyncAnthropic
from google.genai import errors as genai_errors
from openai import AsyncOpenAI
from openai import RateLimitError

from app.agent.tools_spec import (
    EMIT_AUDIO_SCRIPT_TOOL_NAME,
    SYSTEM_PROMPT,
    TOOLS_ANTHROPIC,
    TOOLS_OPENAI,
)
from app.llm.gemini_generation import generate_with_gemini
from app.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScriptGeneration:
    """LLM script plus metadata about which provider actually ran."""

    text: str
    provider_used: str
    used_fallback: bool


async def generate_script_text(
    requirement: str,
    settings: Settings,
    use_tools: bool,
) -> ScriptGeneration:
    """Return script text and which LLM provider produced it (primary or fallback)."""
    primary = settings.llm_provider
    try:
        text = await _generate_by_provider(requirement, settings, use_tools, primary)
        return ScriptGeneration(text=text, provider_used=primary, used_fallback=False)
    except Exception as exc:
        fallback = settings.llm_fallback_provider
        if _should_try_fallback(exc, primary, fallback):
            logger.warning(
                "Primary provider '%s' failed with quota/rate-limit; falling back to '%s'.",
                primary,
                fallback,
            )
            text = await _generate_by_provider(requirement, settings, use_tools, fallback)
            return ScriptGeneration(
                text=text, provider_used=fallback, used_fallback=True
            )
        raise


def _should_try_fallback(
    exc: Exception,
    primary_provider: str,
    fallback_provider: str,
) -> bool:
    if fallback_provider in ("none", primary_provider):
        return False
    if primary_provider == "gemini" and isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        msg = (getattr(exc, "message", "") or "").lower()
        if code in (429, 503) or "quota" in msg or "rate" in msg:
            return True
    if primary_provider == "gemini" and isinstance(exc, RuntimeError):
        msg = str(exc).lower()
        if (
            "all configured gemini models failed" in msg
            or "quota" in msg
            or "rate limit" in msg
            or "not supported for generatecontent" in msg
            or "is not found for api version" in msg
        ):
            return True
    if primary_provider in ("openai", "groq") and isinstance(exc, RateLimitError):
        return True
    return False


async def _generate_by_provider(
    requirement: str,
    settings: Settings,
    use_tools: bool,
    provider: str,
) -> str:
    if provider == "mock":
        return _mock_script(requirement)
    if provider == "groq":
        assert settings.groq_api_key
        return await _openai_compatible_generate(
            requirement,
            settings,
            use_tools,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
            model=settings.groq_model,
            provider_label="groq",
        )
    if provider == "openai":
        assert settings.openai_api_key
        return await _openai_compatible_generate(
            requirement,
            settings,
            use_tools,
            api_key=settings.openai_api_key,
            base_url=None,
            model=settings.openai_model,
            provider_label="openai",
        )
    if provider == "gemini":
        assert settings.gemini_api_key
        return await generate_with_gemini(requirement, settings, use_tools)
    return await _anthropic_generate(requirement, settings, use_tools)


def _mock_script(requirement: str) -> str:
    """No external LLM: deterministic narration for pipeline / ElevenLabs testing."""
    req = requirement.strip()
    if len(req) > 1800:
        req = req[:1800] + "…"
    return (
        "This is a mock narration for testing. No large language model was called. "
        "Here is your requirement in plain words: "
        f"{req} "
        "To use a real model without OpenAI billing, set LLM_PROVIDER=groq and add "
        "GROQ_API_KEY from https://console.groq.com/keys . "
        "To use Google Gemini (free tier in AI Studio), set LLM_PROVIDER=gemini and GEMINI_API_KEY."
    )


async def _openai_compatible_generate(
    requirement: str,
    settings: Settings,
    use_tools: bool,
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    provider_label: str,
) -> str:
    if base_url:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    else:
        client = AsyncOpenAI(api_key=api_key)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": requirement},
    ]

    if not use_tools:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.4,
        )
        text = resp.choices[0].message.content or ""
        return text.strip()

    turns = 0
    while turns < settings.agent_max_turns:
        turns += 1
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS_OPENAI,
            tool_choice="auto",
            temperature=0.4,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.function.name == EMIT_AUDIO_SCRIPT_TOOL_NAME:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError as e:
                        logger.warning("Bad tool arguments from %s: %s", provider_label, e)
                        continue
                    script = (args.get("script") or "").strip()
                    if script:
                        return script
            tool_calls_payload = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in msg.tool_calls
            ]
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": tool_calls_payload,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_calls[0].id,
                    "content": "Tool not completed; call emit_audio_script once with the full script.",
                }
            )
            continue
        fallback = (msg.content or "").strip()
        if fallback:
            logger.info(
                "%s returned plain text without tool call; using content for TTS.",
                provider_label,
            )
            return fallback
        break

    raise RuntimeError(
        f"{provider_label} agent did not produce a script within the turn limit."
    )


async def _anthropic_generate(requirement: str, settings: Settings, use_tools: bool) -> str:
    assert settings.anthropic_api_key
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages: list[dict[str, Any]] = [{"role": "user", "content": requirement}]

    if not use_tools:
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
            temperature=0.4,
        )
        parts: list[str] = []
        for block in resp.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        text = "".join(parts).strip()
        return text

    turns = 0
    while turns < settings.agent_max_turns:
        turns += 1
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS_ANTHROPIC,
            temperature=0.4,
        )

        tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
        text_parts = [b.text for b in resp.content if b.type == "text"]

        for block in tool_use_blocks:
            if block.name == EMIT_AUDIO_SCRIPT_TOOL_NAME:
                script = ""
                if isinstance(block.input, dict):
                    script = (block.input.get("script") or "").strip()
                if script:
                    return script

        if text_parts and not tool_use_blocks:
            logger.info("Anthropic returned text without tool call; using content for TTS.")
            return "".join(text_parts).strip()

        assistant_payload: list[dict[str, Any]] = []
        for block in resp.content:
            assistant_payload.append(block.to_dict())

        messages.append({"role": "assistant", "content": assistant_payload})

        follow_user: list[dict[str, Any]] = []
        for block in tool_use_blocks:
            follow_user.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Please call emit_audio_script with the full final narration.",
                }
            )
        if not follow_user and text_parts:
            return "".join(text_parts).strip()

        messages.append({"role": "user", "content": follow_user})

    raise RuntimeError("Anthropic agent did not produce a script within the turn limit.")
