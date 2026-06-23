"""Tool definitions shared by OpenAI and Anthropic adapters."""

EMIT_AUDIO_SCRIPT_TOOL_NAME = "emit_audio_script"

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": EMIT_AUDIO_SCRIPT_TOOL_NAME,
            "description": (
                "Submit the final narration text that will be spoken aloud by TTS. "
                "The script field must contain ONLY the exact words the listener hears — "
                "no analysis, labels, or mentions of tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": (
                            "Complete spoken narration in plain text. Read verbatim by a "
                            "voice engine; must sound natural and human, with no meta-commentary."
                        ),
                    }
                },
                "required": ["script"],
            },
        },
    }
]

TOOLS_ANTHROPIC = [
    {
        "name": EMIT_AUDIO_SCRIPT_TOOL_NAME,
        "description": (
            "Submit the final narration text that will be spoken aloud by TTS. "
            "The script field must contain ONLY the exact words the listener hears — "
            "no analysis, labels, or mentions of tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": (
                        "Complete spoken narration in plain text. Read verbatim by a "
                        "voice engine; must sound natural and human, with no meta-commentary."
                    ),
                }
            },
            "required": ["script"],
        },
    }
]

SYSTEM_PROMPT = """You are an AI agent that converts client requirements into spoken audio (via ElevenLabs TTS).

The user message is a client requirement. Write a polished narration — the exact words a human presenter would speak to the listener. The audio must sound natural, professional, and user-friendly.

Hard rules:
1. Speak directly to the listener ("you", "we") — never sound like a report about the brief.
2. NEVER include analysis, planning, bullet lists, markdown, code, JSON, or speaker labels.
3. NEVER describe your process (e.g. "The client wants...", "Now I will...", "Here is the script").
4. NEVER mention tools, functions, ElevenLabs, emit_audio_script, or that you are submitting anything.
5. When calling emit_audio_script: put the ENTIRE speakable narration ONLY in the script argument. Do not repeat it in message text.
6. Match length hints in the requirement (e.g. ~90 seconds ≈ 220–250 words).

Every word in the script will be spoken aloud. Write only what the listener should hear."""

DIRECT_NARRATION_PROMPT = """You are an AI agent that converts client requirements into spoken audio (via ElevenLabs TTS).

The user message is a client requirement. Output ONLY the final narration — the exact words spoken to the listener. Nothing else.

Hard rules:
1. Sound like a warm, professional human presenter — not a summary of the brief.
2. No titles, preambles, analysis, bullet lists, markdown, code, or meta-commentary.
3. Do not mention the client, the requirement, scripts, AI, tools, or ElevenLabs.
4. Match length hints (e.g. ~90 seconds ≈ 220–250 words).

Output only the speakable script."""
