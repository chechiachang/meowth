"""Main Meowth Slack bot implementation."""

import logging
from typing import Dict, Any, Optional

from .client import SlackClient
from .handlers.mention import MentionHandler
from .models import ResponseMessage
from .utils.logging import log_mention_received, log_response_sent, log_error
from .metrics import time_it, increment_counter


class MeowthBot:
    """Main Meowth Slack bot that handles app_mention events."""

    def __init__(self, slack_client: SlackClient, logger: logging.Logger) -> None:
        """Initialize Meowth bot with Slack client and logger."""
        self.slack_client = slack_client
        self.logger = logger
        self.mention_handler = MentionHandler()

    def setup_handlers(self) -> None:
        """Set up event handlers for the Slack app."""
        app = self.slack_client.initialize()

        # Register app_mention event handler
        @app.event("app_mention")
        def handle_app_mention(event: Dict[str, Any], say: Any) -> None:
            """Handle app_mention events."""
            self.handle_mention_event(event)

    def handle_mention_event(
        self, event_data: Dict[str, Any]
    ) -> Optional[ResponseMessage]:
        """
        Handle a single mention event.

        Processes the event sequentially and sends response.
        Returns the ResponseMessage if processing was successful.
        """
        with time_it("mention_processing_time"):
            increment_counter("mention_events_received")

            try:
                # Validate and create mention event
                mention_event = self.mention_handler.validate_mention_event(event_data)

                # Log mention received
                log_mention_received(
                    self.logger, mention_event.channel_id, mention_event.user_id
                )

                # Create response message
                response_message = self.mention_handler.create_response_message(
                    mention_event
                )

                # Send response via Slack client
                with time_it(
                    "message_send_time", {"channel_id": mention_event.channel_id}
                ):
                    success = self.slack_client.send_message(response_message)

                if success:
                    increment_counter("responses_sent_success")
                    # Log successful response
                    log_response_sent(
                        self.logger, response_message.channel_id, mention_event.user_id
                    )
                else:
                    increment_counter("responses_sent_failed")
                    # Log failed response
                    self.logger.warning(
                        f"Failed to send response: {response_message.error_message}",
                        extra={
                            "event_type": "response_failed",
                            "channel_id": response_message.channel_id,
                            "response_id": response_message.response_id,
                        },
                    )

                return response_message

            except ValueError as e:
                increment_counter("validation_errors")
                # Validation errors
                log_error(
                    self.logger,
                    e,
                    {"event_data": event_data, "error_type": "validation_error"},
                )
                return None

            except Exception as e:
                increment_counter("unexpected_errors")
                # Unexpected errors
                log_error(
                    self.logger,
                    e,
                    {"event_data": event_data, "error_type": "unexpected_error"},
                )
                return None
