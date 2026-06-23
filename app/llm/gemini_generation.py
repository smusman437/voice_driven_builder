"""Google Gemini (Google AI Studio) script generation via google-genai SDK."""

from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.agent.tools_spec import EMIT_AUDIO_SCRIPT_TOOL_NAME, SYSTEM_PROMPT
from app.settings import Settings, parse_csv

logger = logging.getLogger(__name__)


def _emit_audio_tool() -> types.Tool:
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=EMIT_AUDIO_SCRIPT_TOOL_NAME,
                description=(
                    "Submit the final narration text that should be spoken aloud. "
                    "Call this exactly once when you have a polished script (plain text, no markdown)."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "script": types.Schema(
                            type=types.Type.STRING,
                            description="Complete spoken script for text-to-speech.",
                        )
                    },
                    required=["script"],
                ),
            )
        ]
    )


def _args_to_dict(args: Any) -> dict[str, Any]:
    if args is None:
        return {}
    if isinstance(args, dict):
        return args
    if hasattr(args, "items"):
        try:
            return dict(args.items())
        except Exception:
            pass
    return {}


def _extract_script_from_response(response: types.GenerateContentResponse) -> str | None:
    if not response.candidates:
        return None
    cand = response.candidates[0]
    finish = getattr(cand, "finish_reason", None)
    if finish and str(finish).upper() in ("SAFETY", "RECITATION", "OTHER"):
        logger.warning("Gemini candidate finish_reason=%s", finish)

    content = cand.content
    if not content or not content.parts:
        return None

    for part in content.parts:
        fc = getattr(part, "function_call", None)
        if fc is None:
            continue
        name = getattr(fc, "name", None) or ""
        if name != EMIT_AUDIO_SCRIPT_TOOL_NAME:
            continue
        args = _args_to_dict(getattr(fc, "args", None))
        script = (args.get("script") or "").strip()
        if script:
            return script
    return None


def _extract_text_from_response(response: types.GenerateContentResponse) -> str:
    try:
        t = response.text
        if t:
            return t.strip()
    except Exception:
        pass
    if not response.candidates:
        return ""
    cand = response.candidates[0]
    if not cand.content or not cand.content.parts:
        return ""
    out: list[str] = []
    for part in cand.content.parts:
        if getattr(part, "text", None):
            out.append(part.text)
    return "".join(out).strip()


def _check_blocked(response: types.GenerateContentResponse) -> None:
    if response.prompt_feedback:
        br = getattr(response.prompt_feedback, "block_reason", None)
        if br:
            raise ValueError(f"Gemini blocked the prompt: {br}")


async def generate_with_gemini(
    requirement: str,
    settings: Settings,
    use_tools: bool,
) -> str:
    assert settings.gemini_api_key
    client = genai.Client(api_key=settings.gemini_api_key)
    models = parse_csv(settings.gemini_model_candidates)
    if settings.gemini_model not in models:
        models.insert(0, settings.gemini_model)

    base_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.4,
    )
    errors: list[str] = []
    for model in models:
        try:
            if not use_tools:
                resp = await client.aio.models.generate_content(
                    model=model,
                    contents=requirement,
                    config=base_config,
                )
                _check_blocked(resp)
                text = _extract_text_from_response(resp)
                if not text:
                    raise ValueError("Gemini returned empty text.")
                return text

            tool = _emit_audio_tool()
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
                tools=[tool],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode=types.FunctionCallingConfigMode.AUTO,
                    )
                ),
            )

            contents: list[Any] = [
                types.Content(role="user", parts=[types.Part(text=requirement)]),
            ]

            turns = 0
            while turns < settings.agent_max_turns:
                turns += 1
                resp = await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                _check_blocked(resp)

                script = _extract_script_from_response(resp)
                if script:
                    return script

                text = _extract_text_from_response(resp)
                if text:
                    logger.info(
                        "Gemini returned plain text without tool call; using content for TTS."
                    )
                    return text

                if resp.candidates and resp.candidates[0].content:
                    contents.append(resp.candidates[0].content)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                text=(
                                    "You must call emit_audio_script exactly once with the full "
                                    "spoken narration in the script field (plain text, no markdown)."
                                )
                            )
                        ],
                    )
                )

            raise RuntimeError("Gemini agent did not produce a script within the turn limit.")
        except genai_errors.APIError as e:
            msg = (getattr(e, "message", None) or str(e)).lower()
            code = getattr(e, "code", None)
            if code in (429, 503) or "quota" in msg or "rate" in msg:
                logger.warning(
                    "Gemini model '%s' unavailable due to quota/rate-limit; trying next model.",
                    model,
                )
                errors.append(f"{model}: {getattr(e, 'message', str(e))}")
                continue
            raise

    raise RuntimeError(
        "All configured Gemini models failed due to quota/rate limits: "
        + " | ".join(errors)
    )
