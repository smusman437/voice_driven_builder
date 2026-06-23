"""CLI: generate MP3 from a requirement string (no HTTP server)."""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.agent.service import RequirementAudioAgent
from app.logging_config import configure_logging
from app.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a client requirement into an audio file (AI narration → ElevenLabs MP3).",
    )
    parser.add_argument(
        "requirement",
        help="Client requirement text (quote if it contains spaces).",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable structured tool; use a single plain completion.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info("CLI run (tools off=%s).", args.no_tools)

    agent = RequirementAudioAgent(settings)
    result = asyncio.run(
        agent.run(args.requirement, use_agent_tools=False if args.no_tools else None)
    )
    print("Script:\n", result.script)
    print("Audio file:", result.audio_path.resolve())


if __name__ == "__main__":
    main()
