"""Unit tests for mention event handler."""

import sys
from pathlib import Path

import pytest

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
# Add tests to Python path for fixtures
sys.path.insert(0, str(Path(__file__).parent.parent))

from fixtures.slack_events import SAMPLE_MENTION_EVENT, SAMPLE_THREAD_MENTION_EVENT
from meowth.handlers.mention import MentionHandler
from meowth.models import MentionEvent, ResponseMessage, ResponseStatus


class TestMentionHandler:
    """Test cases for mention event handling."""

    def test_validate_mention_event_valid_data(self):
        """Test mention event validation with valid data."""
        # This test should FAIL initially since MentionHandler doesn't exist yet
        handler = MentionHandler()

        event_data = SAMPLE_MENTION_EVENT["event"]
        mention_event = handler.validate_mention_event(event_data)

        assert isinstance(mention_event, MentionEvent)
        assert mention_event.event_type == "app_mention"
        assert mention_event.channel_id == "C1234567890"
        assert mention_event.user_id == "U9876543210"
        assert mention_event.text == "Hey <@U01BOTUSER> how are you?"
        assert mention_event.timestamp == "1699123456.123456"
        assert mention_event.thread_ts is None

    def test_validate_mention_event_with_thread(self):
        """Test mention event validation with thread timestamp."""
        handler = MentionHandler()

        event_data = SAMPLE_THREAD_MENTION_EVENT["event"]
        mention_event = handler.validate_mention_event(event_data)

        assert mention_event.thread_ts == "1699123400.123400"

    def test_validate_mention_event_invalid_channel_id(self):
        """Test mention event validation with invalid channel ID."""
        handler = MentionHandler()

        event_data = SAMPLE_MENTION_EVENT["event"].copy()
        event_data["channel"] = "INVALID_CHANNEL"

        with pytest.raises(
            ValueError, match="channel_id must match Slack channel ID format"
        ):
            handler.validate_mention_event(event_data)

    def test_validate_mention_event_missing_required_field(self):
        """Test mention event validation with missing required field."""
        handler = MentionHandler()

        event_data = SAMPLE_MENTION_EVENT["event"].copy()
        del event_data["user"]

        with pytest.raises(KeyError):
            handler.validate_mention_event(event_data)

    def test_create_response_message_basic(self):
        """Test response message creation for basic mention."""
        handler = MentionHandler()

        mention_event = MentionEvent(
            event_id="Ev1234567890ABCDEF",
            event_type="app_mention",
            channel_id="C1234567890",
            user_id="U9876543210",
            text="Hey <@U01BOTUSER>",
            timestamp="1699123456.123456",
        )

        response = handler.create_response_message(mention_event)

        assert isinstance(response, ResponseMessage)
        assert response.text == "Meowth, that's right!"
        assert response.channel_id == mention_event.channel_id
        assert response.mention_event_id == mention_event.event_id
        assert response.thread_ts is None
        assert response.status == ResponseStatus.PENDING

    def test_create_response_message_in_thread(self):
        """Test response message creation for mention in thread."""
        handler = MentionHandler()

        mention_event = MentionEvent(
            event_id="Ev1234567890ABCDEF",
            event_type="app_mention",
            channel_id="C1234567890",
            user_id="U9876543210",
            text="<@U01BOTUSER> in thread",
            timestamp="1699123456.123456",
            thread_ts="1699123400.123400",
        )

        response = handler.create_response_message(mention_event)

        assert response.thread_ts == mention_event.thread_ts

    def test_sequential_processing_behavior(self):
        """Test that mentions are processed sequentially."""
        handler = MentionHandler()

        # Create multiple mention events
        events = [
            MentionEvent(
                event_id=f"Ev{i}",
                event_type="app_mention",
                channel_id="C1234567890",
                user_id=f"U{i}",
                text=f"Mention {i} <@U01BOTUSER>",
                timestamp=f"169912345{i}.12345{i}",
            )
            for i in range(3)
        ]

        # Process events and track order
        processed_order = []

        def mock_process(event):
            processed_order.append(event.event_id)
            return handler.create_response_message(event)

        # Process all events
        responses = []
        for event in events:
            response = mock_process(event)
            responses.append(response)

        # Verify sequential processing (order preserved)
        expected_order = ["Ev0", "Ev1", "Ev2"]
        assert processed_order == expected_order
        assert len(responses) == 3
        assert all(r.text == "Meowth, that's right!" for r in responses)

    def test_multi_channel_event_processing(self):
        """Test that mentions from different channels are processed correctly."""
        handler = MentionHandler()

        # Create mention events from different channels
        channels = ["C1111111111", "C2222222222", "C3333333333"]
        events_by_channel = []

        for i, channel_id in enumerate(channels):
            event = MentionEvent(
                event_id=f"Ev{i}_channel",
                event_type="app_mention",
                channel_id=channel_id,
                user_id=f"U{i}",
                text=f"Channel {i} mention <@U01BOTUSER>",
                timestamp=f"169912345{i}.12345{i}",
            )
            events_by_channel.append(event)

        # Process events and verify channel-specific handling
        responses = []
        for event in events_by_channel:
            response = handler.create_response_message(event)
            responses.append(response)

        # Verify each response maintains correct channel context
        for i, response in enumerate(responses):
            assert response.channel_id == channels[i]
            assert response.text == "Meowth, that's right!"
            assert response.mention_event_id == f"Ev{i}_channel"

        # Verify all responses are independent
        assert len(set(r.response_id for r in responses)) == 3  # All unique IDs

    def test_graceful_channel_removal_handling(self):
        """Test graceful handling when bot is removed from a channel."""
        handler = MentionHandler()

        # Test with invalid/removed channel ID
        invalid_channel_event = {
            "type": "app_mention",
            "channel": "C0000000000",  # Non-existent channel
            "user": "U9876543210",
            "text": "Hey <@U01BOTUSER> in removed channel",
            "ts": "1699123456.123456",
        }

        # This should still create a valid mention event
        mention_event = handler.validate_mention_event(invalid_channel_event)
        assert mention_event.channel_id == "C0000000000"

        # Response creation should work but channel validation occurs at send time
        response = handler.create_response_message(mention_event)
        assert response.channel_id == "C0000000000"
        assert response.text == "Meowth, that's right!"

        # Test with malformed channel ID
        try:
            malformed_event = invalid_channel_event.copy()
            malformed_event["channel"] = "INVALID_CHANNEL"
            handler.validate_mention_event(malformed_event)
            assert False, "Should have raised ValueError for invalid channel format"
        except ValueError as e:
            assert "channel_id must match Slack channel ID format" in str(e)
