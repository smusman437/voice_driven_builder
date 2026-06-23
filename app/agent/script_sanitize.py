"""Extract speakable narration from raw LLM output (strip meta / tool syntax)."""

from __future__ import annotations

import json
import re

# Pseudo tool calls the model sometimes writes as plain text instead of using the API tool.
_EMIT_SCRIPT_PATTERNS = (
    re.compile(
        r'emit_audio_script\s*\(\s*\{[\s\S]*?["\']script["\']\s*:\s*["\']((?:\\.|[^"\'\\])*)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'emit_audio_script\s*\(\s*\{[\s\S]*?script\s*:\s*["\']((?:\\.|[^"\'\\])*)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'["\']script["\']\s*:\s*["\']((?:\\.|[^"\'\\])*)["\']',
        re.IGNORECASE,
    ),
)

_META_LINE = re.compile(
    r"(?i)^("
    r"now,?\s+i will\b.*"
    r"|the client is\b.*"
    r"|let me\b.*"
    r"|here is the\b.*script\b.*"
    r"|i('ll| will)\s+(create|write|generate|submit|produce)\b.*"
    r"|calling\s+emit_audio_script\b.*"
    r")$",
)

_META_PARAGRAPH = re.compile(
    r"(?i)^("
    r"the client (is|wants|needs|requested)\b"
    r"|now,?\s+i will\b"
    r"|let me\b"
    r"|here('s| is) (the|a) (script|narration)\b"
    r")",
)


def _unescape(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except json.JSONDecodeError:
        return s.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")


def _extract_from_emit_syntax(text: str) -> str | None:
    for pattern in _EMIT_SCRIPT_PATTERNS:
        match = pattern.search(text)
        if match:
            candidate = _unescape(match.group(1)).strip()
            if len(candidate) >= 20:
                return candidate
    return None


def _strip_emit_blocks(text: str) -> str:
    return re.sub(
        r"emit_audio_script\s*\([\s\S]*?\)\s*;?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _filter_paragraphs(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    kept: list[str] = []
    for part in parts:
        if _META_PARAGRAPH.match(part):
            continue
        if "emit_audio_script" in part.lower():
            continue
        lines = [ln for ln in part.splitlines() if ln.strip()]
        if lines and all(_META_LINE.match(ln.strip()) for ln in lines):
            continue
        kept.append(part)
    return "\n\n".join(kept).strip()


def extract_speakable_script(raw: str) -> str:
    """Return narration suitable for TTS; drop analysis, tool syntax, and meta lines."""
    text = (raw or "").strip()
    if not text:
        return ""

    from_emit = _extract_from_emit_syntax(text)
    if from_emit:
        return from_emit

    cleaned = _strip_emit_blocks(text)
    cleaned = _filter_paragraphs(cleaned)

    # Drop leading meta sentences within a single paragraph block.
    if cleaned:
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        while sentences and _META_PARAGRAPH.match(sentences[0].strip()):
            sentences.pop(0)
        if sentences:
            cleaned = " ".join(sentences).strip()

    return cleaned
