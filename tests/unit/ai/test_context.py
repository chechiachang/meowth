"""Unit tests for AI context analysis and thread message retrieval."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock
from slack_sdk import WebClient

from meowth.ai.context import ContextAnalyzer, TokenCounter
from meowth.ai.models import ThreadContext, ThreadMessage


class TestContextAnalyzer:
    """Test AI context analysis functionality."""

    @pytest.fixture
    def mock_slack_client(self):
        """Mock Slack client for testing."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def context_analyzer(self, mock_slack_client):
        """Create ContextAnalyzer instance for testing."""
        analyzer = ContextAnalyzer(
            slack_client=mock_slack_client, max_context_tokens=2000, max_messages=50
        )
        # Disable age filtering for tests
        analyzer.max_age_hours = 999999
        return analyzer

    @pytest.fixture
    def sample_thread_messages(self):
        """Sample thread messages for testing."""
        return [
            {
                "type": "message",
                "user": "U123USER",
                "text": "Hello, this is the first message",
                "ts": "1234567890.123",
            },
            {
                "type": "message",
                "user": "U456USER",
                "text": "This is a reply to the first message",
                "ts": "1234567891.123",
            },
            {
                "type": "message",
                "user": "UBOT123",
                "text": "I'm a bot response",
                "ts": "1234567892.123",
                "bot_id": "B123BOT",
            },
            {
                "type": "message",
                "user": "U123USER",
                "text": "Another message from the first user",
                "ts": "1234567893.123",
            },
        ]

    @pytest.mark.asyncio
    async def test_fetch_thread_messages_success(
        self, context_analyzer, sample_thread_messages
    ):
        """Test successful thread message retrieval."""
        # Setup mock response
        context_analyzer.slack_client.conversations_replies.return_value = {
            "ok": True,
            "messages": sample_thread_messages,
        }

        # Execute
        messages = await context_analyzer._fetch_thread_messages(
            "C123CHANNEL", "1234567890.123"
        )

        # Verify
        assert len(messages) == 4
        assert messages[0]["text"] == "Hello, this is the first message"
        context_analyzer.slack_client.conversations_replies.assert_called_once_with(
            channel="C123CHANNEL", ts="1234567890.123"
        )

    @pytest.mark.asyncio
    async def test_fetch_thread_messages_api_error(self, context_analyzer):
        """Test handling of Slack API errors."""
        # Setup mock error response
        context_analyzer.slack_client.conversations_replies.return_value = {
            "ok": False,
            "error": "channel_not_found",
        }

        # Execute and verify exception
        with pytest.raises(Exception, match="Failed to fetch thread messages"):
            await context_analyzer._fetch_thread_messages(
                "C123CHANNEL", "1234567890.123"
            )

    @pytest.mark.asyncio
    async def test_analyze_thread_context_basic(
        self, context_analyzer, sample_thread_messages
    ):
        """Test basic thread context analysis."""
        # Setup mocks
        context_analyzer._fetch_thread_messages = AsyncMock(
            return_value=sample_thread_messages
        )

        # Execute
        thread_context = await context_analyzer.analyze_thread_context(
            channel_id="C123CHANNEL", thread_ts="1234567890.123", bot_user_id="UBOT123"
        )

        # Verify
        assert isinstance(thread_context, ThreadContext)
        assert thread_context.channel_id == "C123CHANNEL"
        assert thread_context.thread_ts == "1234567890.123"
        assert len(thread_context.messages) == 4
        assert thread_context.token_count > 0

        # Verify message conversion (messages are in reverse chronological order - newest first)
        first_message = thread_context.messages[0]  # This is the newest message
        assert isinstance(first_message, ThreadMessage)
        assert first_message.user_id == "U123USER"
        assert first_message.text == "Another message from the first user"
        assert first_message.timestamp == "1234567893.123"
        assert not first_message.is_bot_message

    @pytest.mark.asyncio
    async def test_analyze_thread_context_with_bot_detection(
        self, context_analyzer, sample_thread_messages
    ):
        """Test proper bot message detection."""
        context_analyzer._fetch_thread_messages = AsyncMock(
            return_value=sample_thread_messages
        )

        # Execute
        thread_context = await context_analyzer.analyze_thread_context(
            channel_id="C123CHANNEL", thread_ts="1234567890.123", bot_user_id="UBOT123"
        )

        # Find bot message and verify detection
        bot_message = next(
            msg for msg in thread_context.messages if msg.user_id == "UBOT123"
        )
        assert bot_message.is_bot_message
        assert bot_message.text == "I'm a bot response"

    @pytest.mark.asyncio
    async def test_convert_slack_message_regular_user(self, context_analyzer):
        """Test conversion of regular user message."""
        slack_msg = {
            "type": "message",
            "user": "U123USER",
            "text": "Hello world",
            "ts": "1234567890.123",
        }

        thread_msg = context_analyzer._convert_slack_message(slack_msg, "UBOT123")

        assert thread_msg.user_id == "U123USER"
        assert thread_msg.text == "Hello world"
        assert thread_msg.timestamp == "1234567890.123"
        assert not thread_msg.is_bot_message
        assert thread_msg.token_count > 0

    @pytest.mark.asyncio
    async def test_convert_slack_message_bot_user(self, context_analyzer):
        """Test conversion of bot message."""
        slack_msg = {
            "type": "message",
            "user": "UBOT123",
            "text": "I'm a bot",
            "ts": "1234567890.123",
        }

        thread_msg = context_analyzer._convert_slack_message(slack_msg, "UBOT123")

        assert thread_msg.user_id == "UBOT123"
        assert thread_msg.is_bot_message

    @pytest.mark.asyncio
    async def test_convert_slack_message_with_bot_id(self, context_analyzer):
        """Test conversion of message with bot_id field."""
        slack_msg = {
            "type": "message",
            "user": "UBOT123",
            "text": "Bot message",
            "ts": "1234567890.123",
            "bot_id": "B123BOT",
        }

        thread_msg = context_analyzer._convert_slack_message(slack_msg, "UOTHER")

        assert thread_msg.is_bot_message

    @pytest.mark.asyncio
    async def test_convert_slack_message_missing_fields(self, context_analyzer):
        """Test handling of malformed Slack messages."""
        slack_msg = {
            "type": "message",
            # Missing user field
            "text": "Hello",
            "ts": "1234567890.123",
        }

        # Should handle gracefully or raise appropriate exception
        try:
            thread_msg = context_analyzer._convert_slack_message(slack_msg, "UBOT123")
            assert thread_msg.user_id == "unknown"  # Default fallback
        except (KeyError, ValueError):
            # Acceptable to raise exception for malformed data
            pass


class TestTokenCounter:
    """Test token counting functionality."""

    @pytest.fixture
    def token_counter(self):
        """Create TokenCounter instance."""
        return TokenCounter(model_name="gpt-3.5-turbo")

    def test_count_tokens_basic_text(self, token_counter):
        """Test basic token counting."""
        text = "Hello world, this is a test message."
        token_count = token_counter.count_tokens(text)

        assert isinstance(token_count, int)
        assert token_count > 0
        assert token_count < 50  # Reasonable upper bound for this text

    def test_count_tokens_empty_text(self, token_counter):
        """Test token counting with empty text."""
        token_count = token_counter.count_tokens("")
        assert token_count == 0

    def test_count_tokens_large_text(self, token_counter):
        """Test token counting with large text."""
        large_text = "This is a test message. " * 100
        token_count = token_counter.count_tokens(large_text)

        assert token_count > 100  # Should be substantial
        assert token_count < 1000  # But not excessive for repetitive text

    def test_estimate_message_tokens(self, token_counter):
        """Test message token estimation."""
        message = ThreadMessage(
            user_id="U123USER",
            text="Hello, this is a test message for token counting.",
            timestamp="1234567890.123",
            is_bot_message=False,
            token_count=0,  # Will be overwritten
        )

        estimated_tokens = token_counter.estimate_message_tokens(message)

        assert isinstance(estimated_tokens, int)
        assert estimated_tokens > 0
        # Should include tokens for user context and message text
        assert estimated_tokens > token_counter.count_tokens(message.text)

    def test_estimate_message_tokens_bot_message(self, token_counter):
        """Test token estimation for bot messages."""
        bot_message = ThreadMessage(
            user_id="UBOT123",
            text="I am a bot response.",
            timestamp="1234567890.123",
            is_bot_message=True,
            token_count=0,
        )

        estimated_tokens = token_counter.estimate_message_tokens(bot_message)

        assert estimated_tokens > 0
        # Bot messages might have different token overhead
        assert estimated_tokens > token_counter.count_tokens(bot_message.text)

    def test_token_counter_fallback_encoding(self):
        """Test fallback when model encoding is not found."""
        # Use a non-existent model name to trigger fallback
        counter = TokenCounter(model_name="non-existent-model")

        token_count = counter.count_tokens("Hello world")
        assert isinstance(token_count, int)
        assert token_count > 0  # Should still work with fallback encoding

    def test_count_tokens_unicode(self, token_counter):
        """Test token counting with unicode characters."""
        unicode_text = "Hello 👋 world 🌍 with émojis and spëcial characters!"
        token_count = token_counter.count_tokens(unicode_text)

        assert isinstance(token_count, int)
        assert token_count > 0


class TestContextAnalysisIntegration:
    """Integration tests for context analysis components."""

    @pytest.fixture
    def full_context_analyzer(self):
        """Create fully configured ContextAnalyzer."""
        mock_client = AsyncMock()
        return ContextAnalyzer(
            slack_client=mock_client, max_context_tokens=1000, max_messages=10
        )

    @pytest.mark.asyncio
    async def test_context_truncation_by_tokens(self, full_context_analyzer):
        """Test that context is truncated when exceeding token limits."""
        # Create messages that exceed token limit
        large_messages = []
        for i in range(20):
            large_messages.append(
                {
                    "type": "message",
                    "user": f"U{i:03d}USER",
                    "text": "This is a very long message " * 20,  # ~140+ tokens each
                    "ts": f"123456789{i}.123",
                }
            )

        full_context_analyzer._fetch_thread_messages = AsyncMock(
            return_value=large_messages
        )

        # Execute
        thread_context = await full_context_analyzer.analyze_thread_context(
            channel_id="C123CHANNEL", thread_ts="1234567890.123", bot_user_id="UBOT123"
        )

        # Verify truncation occurred
        assert len(thread_context.messages) < 20  # Should be truncated
        assert thread_context.token_count <= 1000  # Should respect token limit

        # Verify most recent messages are prioritized
        timestamps = [msg.timestamp for msg in thread_context.messages]
        assert timestamps == sorted(timestamps, reverse=True)  # Most recent first

    @pytest.mark.asyncio
    async def test_context_truncation_by_message_count(self, full_context_analyzer):
        """Test that context respects maximum message count."""
        # Create more messages than the limit allows
        many_messages = []
        for i in range(15):
            many_messages.append(
                {
                    "type": "message",
                    "user": f"U{i:03d}USER",
                    "text": "Short message",  # Small token count
                    "ts": f"123456789{i}.123",
                }
            )

        full_context_analyzer._fetch_thread_messages = AsyncMock(
            return_value=many_messages
        )

        # Execute
        thread_context = await full_context_analyzer.analyze_thread_context(
            channel_id="C123CHANNEL", thread_ts="1234567890.123", bot_user_id="UBOT123"
        )

        # Verify message count limit respected
        assert len(thread_context.messages) <= 10

    @pytest.mark.asyncio
    async def test_empty_thread_handling(self, full_context_analyzer):
        """Test handling of threads with no messages."""
        full_context_analyzer._fetch_thread_messages = AsyncMock(return_value=[])

        thread_context = await full_context_analyzer.analyze_thread_context(
            channel_id="C123CHANNEL", thread_ts="1234567890.123", bot_user_id="UBOT123"
        )

        assert len(thread_context.messages) == 0
        assert thread_context.token_count == 0
        assert thread_context.channel_id == "C123CHANNEL"
        assert thread_context.thread_ts == "1234567890.123"


class TestThreadIsolation:
    """Test cases for thread isolation in Azure OpenAI context processing."""

    @pytest.fixture
    def context_analyzer_with_isolation(self):
        """Create context analyzer for isolation testing."""
        mock_slack_client = Mock(spec=WebClient)
        analyzer = ContextAnalyzer(mock_slack_client)
        analyzer.max_age_hours = 0  # Disable age filtering for tests
        return analyzer

    @pytest.mark.asyncio
    async def test_concurrent_thread_context_isolation(
        self, context_analyzer_with_isolation
    ):
        """Test that concurrent thread analysis doesn't cross-contaminate context."""
        # Setup different thread data
        thread_1_messages = [
            {
                "type": "message",
                "text": "Thread 1 message about project Alpha",
                "user": "U1USER",
                "ts": "1234567890.100",
            },
            {
                "type": "message",
                "text": "<@UBOT> What's the status on Alpha?",
                "user": "U1USER",
                "ts": "1234567890.101",
            },
        ]

        thread_2_messages = [
            {
                "type": "message",
                "text": "Thread 2 discussion about Beta project",
                "user": "U2USER",
                "ts": "1234567890.200",
            },
            {
                "type": "message",
                "text": "<@UBOT> Can you help with Beta issues?",
                "user": "U2USER",
                "ts": "1234567890.201",
            },
        ]

        # Mock different responses for different threads
        def mock_conversations_replies(channel, ts):
            if ts == "1234567890.100":
                return {"ok": True, "messages": thread_1_messages}
            elif ts == "1234567890.200":
                return {"ok": True, "messages": thread_2_messages}
            else:
                return {"ok": True, "messages": []}

        context_analyzer_with_isolation.slack_client.conversations_replies = Mock(
            side_effect=mock_conversations_replies
        )

        # Analyze both threads concurrently
        import asyncio

        context_1_task = context_analyzer_with_isolation.analyze_thread_context(
            channel_id="C1CHANNEL", thread_ts="1234567890.100", bot_user_id="UBOT"
        )
        context_2_task = context_analyzer_with_isolation.analyze_thread_context(
            channel_id="C2CHANNEL", thread_ts="1234567890.200", bot_user_id="UBOT"
        )

        context_1, context_2 = await asyncio.gather(context_1_task, context_2_task)

        # Verify thread 1 context contains only thread 1 data
        assert context_1.channel_id == "C1CHANNEL"
        assert context_1.thread_ts == "1234567890.100"
        assert len(context_1.messages) == 2
        assert (
            "Alpha" in context_1.messages[1].text
        )  # Most recent first (reverse chronological)
        assert "Beta" not in str(context_1.messages)

        # Verify thread 2 context contains only thread 2 data
        assert context_2.channel_id == "C2CHANNEL"
        assert context_2.thread_ts == "1234567890.200"
        assert len(context_2.messages) == 2
        assert (
            "Beta" in context_2.messages[1].text
        )  # Most recent first (reverse chronological)
        assert "Alpha" not in str(context_2.messages)

        # Verify no cross-contamination
        assert context_1.messages != context_2.messages

    @pytest.mark.asyncio
    async def test_thread_context_independence(self, context_analyzer_with_isolation):
        """Test that analyzing the same thread multiple times produces consistent results."""
        thread_messages = [
            {
                "type": "message",
                "text": "Consistent thread message",
                "user": "U1USER",
                "ts": "1234567890.123",
            }
        ]

        context_analyzer_with_isolation.slack_client.conversations_replies = Mock(
            return_value={"ok": True, "messages": thread_messages}
        )

        # Analyze the same thread multiple times
        context_1 = await context_analyzer_with_isolation.analyze_thread_context(
            channel_id="C1CHANNEL", thread_ts="1234567890.123", bot_user_id="UBOT"
        )

        context_2 = await context_analyzer_with_isolation.analyze_thread_context(
            channel_id="C1CHANNEL", thread_ts="1234567890.123", bot_user_id="UBOT"
        )

        # Results should be identical
        assert context_1.channel_id == context_2.channel_id
        assert context_1.thread_ts == context_2.thread_ts
        assert len(context_1.messages) == len(context_2.messages)
        assert context_1.messages[0].text == context_2.messages[0].text
        assert context_1.token_count == context_2.token_count

    @pytest.mark.asyncio
    async def test_session_isolation_between_threads(
        self, context_analyzer_with_isolation
    ):
        """Test that each thread analysis creates independent session state."""
        from meowth.ai.models import RequestSession, SessionStatus

        # Create sessions for different threads
        session_1 = RequestSession(
            user_id="U1USER",
            thread_context=ThreadContext(
                thread_ts="1234567890.100", channel_id="C1CHANNEL", messages=[]
            ),
        )

        session_2 = RequestSession(
            user_id="U2USER",
            thread_context=ThreadContext(
                thread_ts="1234567890.200", channel_id="C2CHANNEL", messages=[]
            ),
        )

        # Verify sessions are independent
        assert session_1.session_id != session_2.session_id
        assert session_1.user_id != session_2.user_id
        assert session_1.thread_context.thread_ts != session_2.thread_context.thread_ts
        assert (
            session_1.thread_context.channel_id != session_2.thread_context.channel_id
        )

        # Verify modifying one session doesn't affect the other
        session_1.status = SessionStatus.ANALYZING_CONTEXT
        session_2.status = SessionStatus.GENERATING_RESPONSE

        assert session_1.status != session_2.status

        # Verify completing one session doesn't affect the other
        session_1.complete_with_error("Test error")
        assert session_1.status == SessionStatus.ERROR
        assert session_2.status == SessionStatus.GENERATING_RESPONSE  # Unchanged

    @pytest.mark.asyncio
    async def test_concurrent_session_cleanup_isolation(self):
        """Test that session cleanup in one thread doesn't affect other active sessions."""
        import time

        # Create multiple analyzers for different concurrent sessions
        context_analyzer_1 = ContextAnalyzer(slack_client=AsyncMock())
        context_analyzer_2 = ContextAnalyzer(slack_client=AsyncMock())
        context_analyzer_3 = ContextAnalyzer(slack_client=AsyncMock())

        # Mock current timestamps for different sessions
        current_time = time.time()
        ts1 = f"{current_time:.3f}"
        ts2 = f"{current_time + 1:.3f}"
        ts3 = f"{current_time + 2:.3f}"

        # Mock Slack responses for each analyzer
        def mock_conversations_replies_1(channel, ts):
            return {
                "ok": True,
                "messages": [
                    {
                        "ts": ts1,
                        "user": "U123USER1",
                        "text": "Session 1 message",
                        "thread_ts": ts1,
                    }
                ],
            }

        def mock_conversations_replies_2(channel, ts):
            return {
                "ok": True,
                "messages": [
                    {
                        "ts": ts2,
                        "user": "U123USER2",
                        "text": "Session 2 message",
                        "thread_ts": ts2,
                    }
                ],
            }

        def mock_conversations_replies_3(channel, ts):
            return {
                "ok": True,
                "messages": [
                    {
                        "ts": ts3,
                        "user": "U123USER3",
                        "text": "Session 3 message",
                        "thread_ts": ts3,
                    }
                ],
            }

        context_analyzer_1.slack_client.conversations_replies.side_effect = (
            mock_conversations_replies_1
        )
        context_analyzer_2.slack_client.conversations_replies.side_effect = (
            mock_conversations_replies_2
        )
        context_analyzer_3.slack_client.conversations_replies.side_effect = (
            mock_conversations_replies_3
        )

        # Mock user info for all analyzers
        mock_user_info = {
            "ok": True,
            "user": {"real_name": "Test User", "is_bot": False},
        }
        context_analyzer_1.slack_client.users_info.return_value = mock_user_info
        context_analyzer_2.slack_client.users_info.return_value = mock_user_info
        context_analyzer_3.slack_client.users_info.return_value = mock_user_info

        # Start concurrent analysis sessions
        tasks = [
            context_analyzer_1.analyze_thread_context("C1CHANNEL", ts1, "U123BOT"),
            context_analyzer_2.analyze_thread_context("C2CHANNEL", ts2, "U123BOT"),
            context_analyzer_3.analyze_thread_context("C3CHANNEL", ts3, "U123BOT"),
        ]

        # Execute all sessions concurrently
        contexts = await asyncio.gather(*tasks)

        # Verify each session produced independent context
        assert len(contexts) == 3

        context_1, context_2, context_3 = contexts

        # Verify each context is independent
        assert context_1.thread_ts == ts1
        assert context_2.thread_ts == ts2
        assert context_3.thread_ts == ts3

        assert context_1.channel_id == "C1CHANNEL"
        assert context_2.channel_id == "C2CHANNEL"
        assert context_3.channel_id == "C3CHANNEL"

        # Verify message content is isolated
        assert "Session 1 message" in context_1.messages[0].text
        assert "Session 2 message" in context_2.messages[0].text
        assert "Session 3 message" in context_3.messages[0].text

        # Verify no cross-contamination of message content
        context_1_text = " ".join(msg.text for msg in context_1.messages)
        context_2_text = " ".join(msg.text for msg in context_2.messages)
        context_3_text = " ".join(msg.text for msg in context_3.messages)

        assert "Session 1 message" in context_1_text
        assert "Session 1 message" not in context_2_text
        assert "Session 1 message" not in context_3_text

        assert "Session 2 message" in context_2_text
        assert "Session 2 message" not in context_1_text
        assert "Session 2 message" not in context_3_text

        assert "Session 3 message" in context_3_text
        assert "Session 3 message" not in context_1_text
        assert "Session 3 message" not in context_2_text

        # Verify token counts are calculated independently
        assert context_1.token_count > 0
        assert context_2.token_count > 0
        assert context_3.token_count > 0

        # Each context should have its own token count (may be different due to content)
        # But verify they're calculated independently, not shared
        total_individual = (
            context_1.token_count + context_2.token_count + context_3.token_count
        )
        assert total_individual > 0
