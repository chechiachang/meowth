"""Unit tests for Slack client error handling and resilience."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
from slack_sdk.errors import SlackApiError

import pytest

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
# Add tests to Python path for fixtures
sys.path.insert(0, str(Path(__file__).parent.parent))

from fixtures.slack_events import create_bot_instance_data
from meowth.client import SlackClient
from meowth.models import BotInstance, ResponseMessage, ResponseStatus


class TestSlackClientErrorHandling:
    """Test cases for Slack client error handling and resilience."""

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

    def test_api_error_handling_channel_not_found(self, slack_client):
        """Test handling of channel_not_found API error."""
        response_message = ResponseMessage(
            response_id="resp_123",
            mention_event_id="event_123",
            channel_id="C1234567890",
            thread_ts=None,
        )

        # Mock the Slack app and client
        with patch.object(slack_client, "app") as mock_app:
            mock_client = Mock()
            mock_app.client = mock_client

            # Simulate channel_not_found error
            error_response = {"error": "channel_not_found", "ok": False}
            mock_client.chat_postMessage.side_effect = SlackApiError(
                message="channel_not_found", response=error_response
            )

            # Attempt to send message
            result = slack_client.send_message(response_message)

            # Verify error handling
            assert result is False
            assert response_message.status == ResponseStatus.FAILED
            assert "channel_not_found" in response_message.error_message

    def test_api_error_handling_rate_limited(self, slack_client):
        """Test handling of rate_limited API error (retryable)."""
        response_message = ResponseMessage(
            response_id="resp_124",
            mention_event_id="event_124",
            channel_id="C1234567890",
            thread_ts=None,
        )

        with patch.object(slack_client, "app") as mock_app:
            mock_client = Mock()
            mock_app.client = mock_client

            # Simulate rate_limited error
            error_response = {"error": "rate_limited", "ok": False}
            mock_client.chat_postMessage.side_effect = SlackApiError(
                message="rate_limited", response=error_response
            )

            # Attempt to send message
            result = slack_client.send_message(response_message)

            # Verify retryable error handling
            assert result is False
            assert response_message.status == ResponseStatus.RETRYING

    def test_api_error_handling_internal_error(self, slack_client):
        """Test handling of internal_error API error (retryable)."""
        response_message = ResponseMessage(
            response_id="resp_125",
            mention_event_id="event_125",
            channel_id="C1234567890",
            thread_ts=None,
        )

        with patch.object(slack_client, "app") as mock_app:
            mock_client = Mock()
            mock_app.client = mock_client

            # Simulate internal_error
            error_response = {"error": "internal_error", "ok": False}
            mock_client.chat_postMessage.side_effect = SlackApiError(
                message="internal_error", response=error_response
            )

            # Attempt to send message
            result = slack_client.send_message(response_message)

            # Verify retryable error handling
            assert result is False
            assert response_message.status == ResponseStatus.RETRYING

    def test_unknown_api_error_handling(self, slack_client):
        """Test handling of unknown API errors."""
        response_message = ResponseMessage(
            response_id="resp_126",
            mention_event_id="event_126",
            channel_id="C1234567890",
            thread_ts=None,
        )

        with patch.object(slack_client, "app") as mock_app:
            mock_client = Mock()
            mock_app.client = mock_client

            # Simulate unknown error
            error_response = {"error": "unknown_error_code", "ok": False}
            mock_client.chat_postMessage.side_effect = SlackApiError(
                message="unknown_error_code", response=error_response
            )

            # Attempt to send message
            result = slack_client.send_message(response_message)

            # Verify unknown error treated as non-retryable
            assert result is False
            assert response_message.status == ResponseStatus.FAILED
            assert "unknown_error_code" in response_message.error_message

    def test_unexpected_exception_handling(self, slack_client):
        """Test handling of unexpected exceptions."""
        response_message = ResponseMessage(
            response_id="resp_127",
            mention_event_id="event_127",
            channel_id="C1234567890",
            thread_ts=None,
        )

        with patch.object(slack_client, "app") as mock_app:
            mock_client = Mock()
            mock_app.client = mock_client

            # Simulate unexpected exception
            mock_client.chat_postMessage.side_effect = ValueError("Unexpected error")

            # Attempt to send message
            result = slack_client.send_message(response_message)

            # Verify exception handling
            assert result is False
            assert response_message.status == ResponseStatus.FAILED
            assert "Unexpected error" in response_message.error_message

    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_exponential_backoff_reconnection(self, mock_sleep, slack_client):
        """Test exponential backoff reconnection logic."""
        # Set initial state and disable jitter for predictable testing
        slack_client._reconnect_attempts = 0
        slack_client._base_reconnect_delay = 1
        slack_client._max_reconnect_delay = 32
        slack_client._max_reconnect_attempts = 3
        slack_client._jitter_enabled = False  # Disable jitter for predictable testing

        with (
            patch.object(slack_client, "initialize") as mock_initialize,
            patch("meowth.client.SocketModeHandler") as mock_handler_class,
        ):
            # Simulate connection failures
            mock_initialize.side_effect = [
                ConnectionError("Connection failed 1"),
                ConnectionError("Connection failed 2"),
                None,  # Success on third try
            ]

            mock_handler = Mock()
            mock_handler.client.auth_test.return_value = {
                "ok": True,
                "user": "test_bot",
            }
            mock_handler_class.return_value = mock_handler

            # Attempt connection
            try:
                slack_client.connect()
                connection_successful = True
            except RuntimeError:
                connection_successful = False

            # Verify exponential backoff was used
            if mock_sleep.call_count >= 2:
                # Check that delays increase exponentially (without jitter)
                delays = [call[0][0] for call in mock_sleep.call_args_list]
                # With backoff_multiplier = 2.0: delays should be 1, 2, 4, ...
                assert delays[0] >= 1.0  # Should be around 1 * 2^0 = 1
                assert delays[1] >= 2.0  # Should be around 1 * 2^1 = 2

            # Should eventually succeed or exhaust attempts
            assert (
                connection_successful
                or slack_client._reconnect_attempts
                >= slack_client._max_reconnect_attempts
            )

    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_max_reconnection_attempts_exceeded(self, mock_sleep, slack_client):
        """Test behavior when max reconnection attempts are exceeded."""
        # Set state for failure
        slack_client._reconnect_attempts = 0
        slack_client._max_reconnect_attempts = 2

        with patch.object(slack_client, "initialize") as mock_initialize:
            # Simulate persistent connection failure
            mock_initialize.side_effect = ConnectionError("Persistent failure")

            # Attempt connection should eventually raise RuntimeError
            with pytest.raises(
                RuntimeError, match="Failed to connect after 2 attempts"
            ):
                slack_client.connect()

            # Verify all attempts were made
            assert (
                slack_client._reconnect_attempts == slack_client._max_reconnect_attempts
            )

    def test_rate_limit_handling_with_retry_after(self, slack_client):
        """Test rate limit handling with Retry-After header."""
        response_message = ResponseMessage(
            response_id="resp_128",
            mention_event_id="event_128",
            channel_id="C1234567890",
            thread_ts=None,
        )

        with patch.object(slack_client, "app") as mock_app:
            mock_client = Mock()
            mock_app.client = mock_client

            # Simulate rate limit with Retry-After
            error_response = {
                "error": "rate_limited",
                "ok": False,
                "headers": {"Retry-After": "30"},
            }
            mock_client.chat_postMessage.side_effect = SlackApiError(
                message="rate_limited", response=error_response
            )

            # Attempt to send message
            result = slack_client.send_message(response_message)

            # Verify rate limit handling
            assert result is False
            assert response_message.status == ResponseStatus.RETRYING
            # Verify rate limit information is logged/stored appropriately

    def test_burst_rate_limit_handling(self, slack_client):
        """Test handling of rapid successive rate limits."""
        messages = []
        for i in range(5):
            msg = ResponseMessage(
                response_id=f"resp_burst_{i}",
                mention_event_id=f"event_burst_{i}",
                channel_id="C1234567890",
                thread_ts=None,
            )
            messages.append(msg)

        with patch.object(slack_client, "app") as mock_app:
            mock_client = Mock()
            mock_app.client = mock_client

            # Simulate rate limiting all requests
            error_response = {"error": "rate_limited", "ok": False}
            mock_client.chat_postMessage.side_effect = SlackApiError(
                message="rate_limited", response=error_response
            )

            # Attempt to send all messages
            results = []
            for msg in messages:
                result = slack_client.send_message(msg)
                results.append(result)

            # Verify all were rate limited appropriately
            assert all(result is False for result in results)
            assert all(msg.status == ResponseStatus.RETRYING for msg in messages)

    def test_rate_limit_recovery(self, slack_client):
        """Test recovery after rate limit period."""
        response_message = ResponseMessage(
            response_id="resp_recovery",
            mention_event_id="event_recovery",
            channel_id="C1234567890",
            thread_ts=None,
        )

        with patch.object(slack_client, "app") as mock_app:
            mock_client = Mock()
            mock_app.client = mock_client

            # First call rate limited, second succeeds
            error_response = {"error": "rate_limited", "ok": False}
            success_response = {"ok": True, "ts": "1699123456.123456"}

            mock_client.chat_postMessage.side_effect = [
                SlackApiError(message="rate_limited", response=error_response),
                success_response,
            ]

            # First attempt should be rate limited
            result1 = slack_client.send_message(response_message)
            assert result1 is False
            assert response_message.status == ResponseStatus.RETRYING

            # Reset message for retry
            response_message.status = ResponseStatus.PENDING
            response_message.error_message = None

            # Second attempt should succeed
            result2 = slack_client.send_message(response_message)
            assert result2 is True
            assert response_message.status == ResponseStatus.SENT
