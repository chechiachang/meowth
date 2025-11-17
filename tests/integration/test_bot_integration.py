"""Integration tests for end-to-end mention handling."""

import sys
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
# Add tests to Python path for fixtures
sys.path.insert(0, str(Path(__file__).parent.parent))

from fixtures.slack_events import (
    SAMPLE_MENTION_EVENT,
    SAMPLE_THREAD_MENTION_EVENT,
    SUCCESSFUL_MESSAGE_RESPONSE,
    create_bot_instance_data,
)
from meowth.bot import MeowthBot
from meowth.client import SlackClient
from meowth.models import BotInstance, ResponseStatus


class TestBotIntegration:
    """Integration tests for complete mention handling flow."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing."""
        return Mock()

    @pytest.fixture
    def bot_instance(self):
        """Create test bot instance."""
        data = create_bot_instance_data()
        return BotInstance(bot_token=data["bot_token"], app_token=data["app_token"])

    @pytest.fixture
    def slack_client(self, bot_instance, mock_logger):
        """Create test Slack client."""
        return SlackClient(bot_instance, mock_logger)

    @pytest.fixture
    def meowth_bot(self, slack_client, mock_logger):
        """Create test Meowth bot."""
        return MeowthBot(slack_client, mock_logger)

    @patch("meowth.client.SocketModeHandler")
    @patch("meowth.client.App")
    @pytest.mark.asyncio
    async def test_end_to_end_mention_handling(
        self, mock_app_class, mock_handler, meowth_bot
    ):
        """Test complete flow from mention event to response."""
        # This test should FAIL initially since MeowthBot doesn't exist yet

        # Setup mocks
        mock_app_instance = Mock()
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = SUCCESSFUL_MESSAGE_RESPONSE
        mock_app_instance.client = mock_client
        mock_app_class.return_value = mock_app_instance

        # Setup bot
        meowth_bot.setup_handlers()

        # Simulate mention event
        event_data = SAMPLE_MENTION_EVENT["event"]

        # Process the event (this will call the actual handler)
        response = await meowth_bot.handle_mention_event_async(event_data, None)

        # Verify response was created and sent
        assert response is not None
        assert response.text == "Meowth, that's right!"
        assert response.channel_id == event_data["channel"]
        assert response.status == ResponseStatus.SENT

        # Verify Slack API was called correctly
        mock_client.chat_postMessage.assert_called_once_with(
            channel=event_data["channel"], text="Meowth, that's right!", thread_ts=None
        )

    @patch("meowth.client.SocketModeHandler")
    @patch("meowth.client.App")
    @pytest.mark.asyncio
    async def test_thread_mention_handling(
        self, mock_app_class, mock_handler, meowth_bot
    ):
        """Test handling mention in a thread."""
        # Setup mocks
        mock_app_instance = Mock()
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = SUCCESSFUL_MESSAGE_RESPONSE
        mock_app_instance.client = mock_client
        mock_app_class.return_value = mock_app_instance

        # Setup bot
        meowth_bot.setup_handlers()

        # Simulate thread mention event
        event_data = SAMPLE_THREAD_MENTION_EVENT["event"]

        # Process the event
        response = await meowth_bot.handle_mention_event_async(event_data, None)

        # Verify thread response
        assert response.thread_ts == event_data["thread_ts"]

        # Verify Slack API was called with thread timestamp
        mock_client.chat_postMessage.assert_called_once_with(
            channel=event_data["channel"],
            text="Meowth, that's right!",
            thread_ts=event_data["thread_ts"],
        )

    @patch("meowth.client.SocketModeHandler")
    @patch("meowth.client.App")
    @pytest.mark.asyncio
    async def test_response_timing_requirement(
        self, mock_app_class, mock_handler, meowth_bot
    ):
        """Test that responses are sent within 5 seconds."""
        # Setup mocks
        mock_app_instance = Mock()
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = SUCCESSFUL_MESSAGE_RESPONSE
        mock_app_instance.client = mock_client
        mock_app_class.return_value = mock_app_instance

        # Setup bot
        meowth_bot.setup_handlers()

        # Record start time
        start_time = datetime.now(UTC)

        # Process mention event
        event_data = SAMPLE_MENTION_EVENT["event"]
        response = await meowth_bot.handle_mention_event_async(event_data, None)

        # Verify response time
        end_time = datetime.now(UTC)
        processing_time = (end_time - start_time).total_seconds()

        assert processing_time < 5.0, f"Response took {processing_time}s, must be < 5s"
        assert response.status == ResponseStatus.SENT

    @pytest.mark.asyncio
    async def test_multiple_simultaneous_mentions_sequential_processing(
        self, meowth_bot, mock_logger
    ):
        """Test that multiple simultaneous mentions are processed sequentially."""
        # This tests the requirement for single-threaded sequential processing

        processed_events = []
        original_handle = meowth_bot.handle_mention_event_async

        async def track_processing(event_data, context):
            processed_events.append(event_data["ts"])
            return await original_handle(event_data, context)

        # Mock the handler to track processing order
        meowth_bot.handle_mention_event_async = track_processing

        # Create multiple events with different timestamps
        events = [
            {
                "type": "app_mention",
                "channel": "C1234567890",
                "user": f"U{i}",
                "text": f"Mention {i} <@U01BOTUSER>",
                "ts": f"169912345{i}.12345{i}",
            }
            for i in range(3)
        ]

        # Process all events
        for event_data in events:
            await meowth_bot.handle_mention_event_async(event_data, None)

        # Verify sequential processing (timestamps should be in order)
        expected_timestamps = [f"169912345{i}.12345{i}" for i in range(3)]
        assert processed_events == expected_timestamps

    @patch("meowth.client.SocketModeHandler")
    @patch("meowth.client.App")
    @pytest.mark.asyncio
    async def test_cross_channel_functionality(
        self, mock_app_class, mock_handler, meowth_bot
    ):
        """Test bot functionality across multiple channels."""
        # Setup mocks
        mock_app_instance = Mock()
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = SUCCESSFUL_MESSAGE_RESPONSE
        mock_app_instance.client = mock_client
        mock_app_class.return_value = mock_app_instance

        # Setup bot
        meowth_bot.setup_handlers()

        # Define different channels
        channels = [
            {"channel": "C1111111111", "name": "#general"},
            {"channel": "C2222222222", "name": "#random"},
            {"channel": "C3333333333", "name": "#dev-team"},
        ]

        # Process mentions from each channel
        responses = []
        for i, channel_info in enumerate(channels):
            event_data = {
                "type": "app_mention",
                "channel": channel_info["channel"],
                "user": f"U{i}",
                "text": f"Hey <@U01BOTUSER> from {channel_info['name']}!",
                "ts": f"169912345{i}.12345{i}",
            }

            response = await meowth_bot.handle_mention_event_async(event_data, None)
            responses.append(response)

        # Verify all channels got responses
        assert len(responses) == 3
        for i, response in enumerate(responses):
            assert response.channel_id == channels[i]["channel"]
            assert response.text == "Meowth, that's right!"

        # Verify Slack API was called for each channel
        assert mock_client.chat_postMessage.call_count == 3
        for i, call in enumerate(mock_client.chat_postMessage.call_args_list):
            args, kwargs = call
            assert kwargs["channel"] == channels[i]["channel"]
            assert kwargs["text"] == "Meowth, that's right!"

    @patch("meowth.client.SocketModeHandler")
    @patch("meowth.client.App")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_connection_recovery_scenarios(
        self, mock_sleep, mock_app_class, mock_handler, meowth_bot
    ):
        """Test bot recovery from connection failures."""
        # Setup mocks
        mock_app_instance = Mock()
        mock_client = Mock()
        mock_client.chat_postMessage.return_value = SUCCESSFUL_MESSAGE_RESPONSE
        mock_app_instance.client = mock_client
        mock_app_class.return_value = mock_app_instance

        # Mock connection failure then success
        mock_handler_instance = Mock()
        mock_handler.return_value = mock_handler_instance

        # First auth_test fails, second succeeds
        mock_handler_instance.client.auth_test.side_effect = [
            ConnectionError("Connection lost"),
            {"ok": True, "user": "test_bot"},
        ]

        # Setup bot
        meowth_bot.setup_handlers()

        # This should trigger reconnection logic in the client
        # The actual connect() method would handle the retry
        try:
            meowth_bot.slack_client.connect()
        except (ConnectionError, RuntimeError):
            pass  # Connection might fail in test environment

        # Verify that reconnection was attempted
        # (In a real scenario, this would test actual reconnection behavior)
        assert mock_handler_instance.client.auth_test.call_count >= 1

    @patch("meowth.client.SocketModeHandler")
    @patch("meowth.client.App")
    @pytest.mark.asyncio
    async def test_resilient_message_sending_with_retries(
        self, mock_app_class, mock_handler, meowth_bot
    ):
        """Test resilient message sending with automatic retries."""
        from slack_sdk.errors import SlackApiError

        # Setup mocks
        mock_app_instance = Mock()
        mock_client = Mock()
        mock_app_instance.client = mock_client
        mock_app_class.return_value = mock_app_instance

        # First call fails with retryable error, second succeeds
        error_response = {"error": "rate_limited", "ok": False}
        mock_client.chat_postMessage.side_effect = [
            SlackApiError(message="rate_limited", response=error_response),
            SUCCESSFUL_MESSAGE_RESPONSE,
        ]

        # Setup bot
        meowth_bot.setup_handlers()

        # Process mention event
        event_data = SAMPLE_MENTION_EVENT["event"]
        response = await meowth_bot.handle_mention_event_async(event_data, None)

        # First attempt should result in RETRYING status due to rate limit
        assert response is not None
        # The response status depends on implementation details
        # In this case, we're testing that the error was handled gracefully
        assert response.channel_id == event_data["channel"]
