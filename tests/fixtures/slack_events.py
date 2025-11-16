"""Test fixtures for Slack events and bot testing."""

from typing import Dict, Any


# Sample Slack app_mention event data
SAMPLE_MENTION_EVENT = {
    "type": "event_callback",
    "event": {
        "type": "app_mention",
        "channel": "C1234567890",
        "user": "U9876543210",
        "text": "Hey <@U01BOTUSER> how are you?",
        "ts": "1699123456.123456",
    },
    "event_id": "Ev1234567890ABCDEF",
    "event_time": 1699123456,
}

# Mention event with thread
SAMPLE_THREAD_MENTION_EVENT = {
    "type": "event_callback",
    "event": {
        "type": "app_mention",
        "channel": "C1234567890",
        "user": "U9876543210",
        "text": "<@U01BOTUSER> responding to thread",
        "ts": "1699123466.123466",
        "thread_ts": "1699123400.123400",
    },
    "event_id": "Ev1234567890ABCDEF",
    "event_time": 1699123466,
}

# Multiple mention events for concurrent testing
SAMPLE_CONCURRENT_MENTIONS = [
    {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": "C1234567890",
            "user": "U1111111111",
            "text": "First mention <@U01BOTUSER>",
            "ts": "1699123456.123456",
        },
        "event_id": "Ev1111111111AAAAAA",
        "event_time": 1699123456,
    },
    {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": "C2222222222",
            "user": "U2222222222",
            "text": "<@U01BOTUSER> second mention",
            "ts": "1699123457.123457",
        },
        "event_id": "Ev2222222222BBBBBB",
        "event_time": 1699123457,
    },
    {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": "C1234567890",
            "user": "U3333333333",
            "text": "Third <@U01BOTUSER> mention here",
            "ts": "1699123458.123458",
        },
        "event_id": "Ev3333333333CCCCCC",
        "event_time": 1699123458,
    },
]

# Error response examples
SLACK_API_ERROR_RESPONSES = {
    "rate_limited": {
        "ok": False,
        "error": "rate_limited",
        "response_metadata": {"retry_after": 60},
    },
    "channel_not_found": {"ok": False, "error": "channel_not_found"},
    "not_in_channel": {"ok": False, "error": "not_in_channel"},
    "internal_error": {"ok": False, "error": "internal_error"},
}

# Successful message response
SUCCESSFUL_MESSAGE_RESPONSE = {
    "ok": True,
    "channel": "C1234567890",
    "ts": "1699123459.123459",
    "message": {
        "type": "message",
        "subtype": "bot_message",
        "text": "Meowth, that's right!",
        "ts": "1699123459.123459",
        "username": "meowth",
        "bot_id": "B01BOTUSER",
    },
}


def create_mention_event(
    channel_id: str = "C1234567890",
    user_id: str = "U9876543210",
    text: str = "Hey <@U01BOTUSER> test",
    event_id: str = "Ev1234567890ABCDEF",
    timestamp: str = "1699123456.123456",
    thread_ts: str = None,
) -> Dict[str, Any]:
    """Create a test mention event with customizable parameters."""
    event = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": channel_id,
            "user": user_id,
            "text": text,
            "ts": timestamp,
        },
        "event_id": event_id,
        "event_time": int(timestamp.split(".")[0]),
    }

    if thread_ts:
        event["event"]["thread_ts"] = thread_ts

    return event


def create_bot_instance_data() -> Dict[str, Any]:
    """Create test bot instance configuration."""
    return {
        "bot_token": "xoxb-test-token-placeholder",
        "app_token": "xapp-test-token-placeholder",
    }
