"""Data models for Slack mention bot entities."""

from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Dict, Any
import re


class ResponseStatus(Enum):
    """Status of response message delivery."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class LogLevel(Enum):
    """Logging severity levels."""

    ERROR = "ERROR"
    INFO = "INFO"
    DEBUG = "DEBUG"


@dataclass
class BotInstance:
    """Represents the running bot application with configuration and state."""

    bot_token: str
    app_token: str
    is_connected: bool = False
    last_heartbeat: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate token formats after initialization."""
        if not self.bot_token or not self.bot_token.startswith("xoxb-"):
            raise ValueError(
                "bot_token must be a valid Slack bot token (starts with xoxb-)"
            )

        if not self.app_token or not self.app_token.startswith("xapp-"):
            raise ValueError(
                "app_token must be a valid Slack app token (starts with xapp-)"
            )


@dataclass
class MentionEvent:
    """Represents an app_mention event received from Slack."""

    event_id: str
    event_type: str
    channel_id: str
    user_id: str
    text: str
    timestamp: str
    thread_ts: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate event data after initialization."""
        # Validate event type
        if self.event_type != "app_mention":
            raise ValueError("event_type must be 'app_mention'")

        # Validate Slack ID formats
        if not re.match(r"^C[A-Z0-9]+$", self.channel_id):
            raise ValueError(
                "channel_id must match Slack channel ID format (C[A-Z0-9]+)"
            )

        if not re.match(r"^U[A-Z0-9]+$", self.user_id):
            raise ValueError("user_id must match Slack user ID format (U[A-Z0-9]+)")

        # Validate timestamp format
        if not re.match(r"^[0-9]+\.[0-9]+$", self.timestamp):
            raise ValueError("timestamp must be in Slack timestamp format")

        # Validate thread timestamp if present
        if self.thread_ts and not re.match(r"^[0-9]+\.[0-9]+$", self.thread_ts):
            raise ValueError("thread_ts must be in Slack timestamp format")


@dataclass
class ResponseMessage:
    """Represents the bot's reply to a mention."""

    response_id: str
    mention_event_id: str
    channel_id: str
    text: str = "Meowth, that's right!"
    thread_ts: Optional[str] = None
    status: ResponseStatus = ResponseStatus.PENDING
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate response data after initialization."""
        # Validate fixed response text
        if self.text != "Meowth, that's right!":
            raise ValueError("text must be exactly 'Meowth, that's right!'")

        # Validate channel ID format
        if not re.match(r"^C[A-Z0-9]+$", self.channel_id):
            raise ValueError("channel_id must match Slack channel ID format")

        # Validate sent_at is present when status is SENT
        if self.status == ResponseStatus.SENT and self.sent_at is None:
            raise ValueError("sent_at is required when status is SENT")

    def mark_sent(self) -> None:
        """Mark response as successfully sent."""
        self.status = ResponseStatus.SENT
        self.sent_at = datetime.now(UTC)
        self.error_message = None

    def mark_failed(self, error_message: str) -> None:
        """Mark response as failed with error details."""
        self.status = ResponseStatus.FAILED
        self.error_message = error_message

    def mark_retrying(self) -> None:
        """Mark response as retrying after temporary failure."""
        self.status = ResponseStatus.RETRYING


@dataclass
class LogEntry:
    """Structured log entry for operational monitoring."""

    timestamp: datetime
    level: LogLevel
    event_type: str
    message: str
    channel_id: Optional[str] = None
    user_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate log entry data."""
        if not self.event_type:
            raise ValueError("event_type is required")

        if not self.message:
            raise ValueError("message is required")
