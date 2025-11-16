"""Mention event handler for processing app_mention events."""

import logging
import uuid
from typing import Dict, Any, Set

from ..models import MentionEvent, ResponseMessage


class MentionHandler:
    """Handler for processing Slack app_mention events with multi-channel support."""

    def __init__(self) -> None:
        """Initialize the mention handler with channel tracking."""
        self.processed_channels: Set[str] = set()
        self.logger = logging.getLogger("meowth.handlers.mention")

    def validate_mention_event(self, event_data: Dict[str, Any]) -> MentionEvent:
        """Validate and create MentionEvent from Slack event data."""
        channel_id = event_data["channel"]

        # Track channel for multi-channel awareness
        if channel_id not in self.processed_channels:
            self.processed_channels.add(channel_id)
            self.logger.info(
                f"First mention received from channel {channel_id}",
                extra={
                    "event_type": "new_channel_detected",
                    "channel_id": channel_id,
                    "total_channels": len(self.processed_channels),
                },
            )

        return MentionEvent(
            event_id=str(uuid.uuid4()),  # Generate unique ID
            event_type=event_data["type"],
            channel_id=channel_id,
            user_id=event_data["user"],
            text=event_data["text"],
            timestamp=event_data["ts"],
            thread_ts=event_data.get("thread_ts"),
        )

    def create_response_message(self, mention_event: MentionEvent) -> ResponseMessage:
        """Create response message for a mention event with channel context validation."""
        # Validate channel is still being tracked
        if mention_event.channel_id not in self.processed_channels:
            self.logger.warning(
                f"Responding to channel {mention_event.channel_id} not in tracked channels",
                extra={
                    "event_type": "untracked_channel_response",
                    "channel_id": mention_event.channel_id,
                    "mention_event_id": mention_event.event_id,
                },
            )

        return ResponseMessage(
            response_id=str(uuid.uuid4()),
            mention_event_id=mention_event.event_id,
            channel_id=mention_event.channel_id,
            thread_ts=mention_event.thread_ts,
        )

    def get_channel_stats(self) -> Dict[str, Any]:
        """Get statistics about channels processed."""
        return {
            "total_channels": len(self.processed_channels),
            "channels": list(self.processed_channels),
        }

    def handle_channel_removed(self, channel_id: str) -> None:
        """Handle graceful cleanup when bot is removed from a channel."""
        if channel_id in self.processed_channels:
            self.processed_channels.remove(channel_id)
            self.logger.info(
                f"Bot removed from channel {channel_id}",
                extra={
                    "event_type": "channel_removed",
                    "channel_id": channel_id,
                    "remaining_channels": len(self.processed_channels),
                },
            )
        else:
            self.logger.warning(
                f"Attempted to remove unknown channel {channel_id}",
                extra={
                    "event_type": "unknown_channel_removal",
                    "channel_id": channel_id,
                },
            )
