"""Tool definitions shared by OpenAI and Anthropic adapters."""

EMIT_AUDIO_SCRIPT_TOOL_NAME = "emit_audio_script"

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": EMIT_AUDIO_SCRIPT_TOOL_NAME,
            "description": (
                "Submit the final narration text that should be spoken aloud. "
                "Call this exactly once when you have a polished script (plain text, no markdown)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Complete spoken script for text-to-speech.",
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
            "Submit the final narration text that should be spoken aloud. "
            "Call this exactly once when you have a polished script (plain text, no markdown)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "Complete spoken script for text-to-speech.",
                }
            },
            "required": ["script"],
        },
    }
]

SYSTEM_PROMPT = """You are a senior product analyst and narrator.

The user message is a client requirement or brief. Your job:
1. Interpret what the client wants in clear, natural language.
2. Produce a concise spoken explanation (not a bullet list) suitable for audio: friendly, confident, and easy to follow.
3. Do not include markdown, code blocks, or speaker labels. Imagine this will be read verbatim by a voice actor.
4. When ready, you MUST call the tool emit_audio_script with your final narration as the only content.

If the input is ambiguous, state reasonable assumptions briefly, then continue."""
