"""Logging configuration helpers."""
from __future__ import annotations

import logging


def configure_logging(level: str) -> None:
    """Configure root logging with a structured-friendly format."""
    level_value = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=level_value,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
