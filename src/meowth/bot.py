"""Main Meowth Slack bot implementation with Azure OpenAI integration."""

import asyncio
import logging
import threading
from typing import Dict, Any, Optional

from .client import SlackClient
from .handlers.mention import MentionHandler
from .handlers.ai_mention import handle_ai_mention, should_process_mention
from .models import ResponseMessage
from .utils.logging import log_mention_received, log_response_sent, log_error
from .metrics import time_it, increment_counter


class MeowthBot:
    """Main Meowth Slack bot that handles app_mention events with AI integration."""

    def __init__(self, slack_client: SlackClient, logger: logging.Logger) -> None:
        """Initialize Meowth bot with Slack client and logger."""
        self.slack_client = slack_client
        self.logger = logger
        self.mention_handler = MentionHandler()
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_async_loop()

    def _start_async_loop(self) -> None:
        """Start an event loop in a separate thread for async operations."""

        def run_loop() -> None:
            self._async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        # Wait for loop to be ready
        import time

        while self._async_loop is None:
            time.sleep(0.01)

    def _run_async_task(self, coroutine: Any) -> None:
        """Schedule a coroutine to run in the async event loop."""
        if self._async_loop and not self._async_loop.is_closed():
            asyncio.run_coroutine_threadsafe(coroutine, self._async_loop)

    def setup_handlers(self) -> None:
        """Set up event handlers for the Slack app."""
        app = self.slack_client.initialize()

        # Register app_mention event handler with AI integration
        @app.event("app_mention")
        def handle_app_mention(event: Dict[str, Any], say: Any, context: Any) -> None:
            """Handle app_mention events with AI response generation."""
            # Schedule async AI handler in the dedicated event loop
            self._run_async_task(self.handle_mention_event_async(event, context))

    async def handle_mention_event_async(
        self, event_data: Dict[str, Any], context: Any
    ) -> Optional[ResponseMessage]:
        """
        Handle a single mention event with AI integration.

        Processes the event and generates AI response if appropriate,
        falls back to original behavior for non-AI mentions.
        """
        with time_it("mention_processing_time"):
            increment_counter("mention_events_received")

            try:
                # Check if this should be processed with AI
                bot_user_id = getattr(context, "bot_user_id", None)
                if bot_user_id and should_process_mention(event_data, bot_user_id):
                    # Process with AI
                    increment_counter("ai_mentions_received")

                    log_mention_received(
                        self.logger,
                        event_data["channel"],
                        event_data["user"],
                        mention_type="ai",
                    )

                    if self.slack_client.app:
                        await handle_ai_mention(
                            event=event_data,
                            client=self.slack_client.app.client,
                            context=context,
                        )

                    increment_counter("ai_responses_completed")
                    return None  # AI handler manages response directly

                else:
                    # Process with original handler
                    increment_counter("standard_mentions_received")
                    return await self.handle_mention_event_standard(event_data)

            except Exception as e:
                increment_counter("unexpected_errors")
                # Log error and attempt fallback
                log_error(
                    self.logger,
                    e,
                    {"event_data": event_data, "error_type": "async_mention_error"},
                )

                # Fallback to standard handling
                try:
                    return await self.handle_mention_event_standard(event_data)
                except Exception as fallback_error:
                    log_error(
                        self.logger,
                        fallback_error,
                        {"event_data": event_data, "error_type": "fallback_error"},
                    )
                    return None

    async def handle_mention_event_standard(
        self, event_data: Dict[str, Any]
    ) -> Optional[ResponseMessage]:
        """
        Handle a mention event with standard (non-AI) processing.

        This is the original mention handling logic.
        """
        try:
            # Validate and create mention event
            mention_event = self.mention_handler.validate_mention_event(event_data)

            # Log mention received
            log_mention_received(
                self.logger,
                mention_event.channel_id,
                mention_event.user_id,
                mention_type="standard",
            )

            # Create response message
            response_message = await self.mention_handler.create_response_message(
                mention_event
            )

            # Send response via Slack client
            with time_it("message_send_time", {"channel_id": mention_event.channel_id}):
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

    def cleanup(self) -> None:
        """Clean up async resources."""
        if self._async_loop and not self._async_loop.is_closed():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)

        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=1.0)
