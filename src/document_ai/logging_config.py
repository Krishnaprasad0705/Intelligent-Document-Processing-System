"""
Logging setup for Document AI.
Provides structured, safe diagnostic logs without exposing sensitive document content.
"""

import logging
import sys
from typing import Optional


def configure_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Configures and returns the root document_ai logger.
    Avoids duplicate handlers and formats logs cleanly.
    """
    from document_ai.config import get_settings

    settings = get_settings()
    log_level_str = level or settings.log_level
    numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)

    logger = logging.getLogger("document_ai")
    logger.setLevel(numeric_level)

    # Avoid adding multiple stream handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Prevent duplicate logs through root logger
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Retrieve child logger with appropriate namespace."""
    return logging.getLogger(f"document_ai.{name}")
