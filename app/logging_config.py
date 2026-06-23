"""Central logging setup."""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    numeric = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(fmt)
    root.addHandler(handler)

    # Reduce noise from third-party libraries in normal use
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
