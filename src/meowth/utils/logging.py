"""Structured logging configuration for operational monitoring."""

import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime, UTC


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging with operational context."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured information."""
        # Base structured log format
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add optional context if present
        if hasattr(record, "event_type"):
            log_entry["event_type"] = record.event_type

        if hasattr(record, "channel_id"):
            log_entry["channel_id"] = record.channel_id

        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id

        if hasattr(record, "details"):
            log_entry["details"] = record.details

        # Format as readable key=value pairs for easy parsing
        formatted_parts = []
        for key, value in log_entry.items():
            if isinstance(value, str) and " " in value:
                formatted_parts.append(f'{key}="{value}"')
            else:
                formatted_parts.append(f"{key}={value}")

        return " ".join(formatted_parts)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Set up structured logging for the bot."""
    logger = logging.getLogger("meowth")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove any existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Console handler with structured formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)

    # Prevent duplicate logs from root logger
    logger.propagate = False

    return logger


def log_mention_received(logger: logging.Logger, channel_id: str, user_id: str) -> None:
    """Log when a mention event is received."""
    logger.info(
        "Mention received",
        extra={
            "event_type": "mention_received",
            "channel_id": channel_id,
            "user_id": user_id,
        },
    )


def log_response_sent(logger: logging.Logger, channel_id: str, user_id: str) -> None:
    """Log when a response is successfully sent."""
    logger.info(
        "Response sent successfully",
        extra={
            "event_type": "response_sent",
            "channel_id": channel_id,
            "user_id": user_id,
        },
    )


def log_error(
    logger: logging.Logger, error: Exception, context: Optional[Dict[str, Any]] = None
) -> None:
    """Log an error with optional context."""
    extra: Dict[str, Any] = {
        "event_type": "error",
        "details": {"error_type": type(error).__name__, "error_message": str(error)},
    }

    if context:
        extra["details"].update(context)

    logger.error(f"Error occurred: {error}", extra=extra)


def log_connection_status(
    logger: logging.Logger, status: str, reason: Optional[str] = None
) -> None:
    """Log connection status changes."""
    extra: Dict[str, Any] = {
        "event_type": "connection_status",
        "details": {"status": status},
    }
    if reason:
        extra["details"]["reason"] = reason

    logger.info(f"Connection status: {status}", extra=extra)
