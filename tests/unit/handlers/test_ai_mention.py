"""Unit tests for AI mention handler basic functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from slack_bolt.context.context import BoltContext
from slack_sdk import WebClient

from meowth.ai.models import (
    ThreadContext,
    ThreadMessage,
    AIResponse,
    AzureOpenAIError,
    RateLimitError,
)


class TestAIMentionHandler:
    """Test cases for AI-powered mention handler functionality."""

    @pytest.fixture
    def mock_slack_client(self):
        """Create mock Slack client."""
        client = Mock(spec=WebClient)
        return client

    @pytest.fixture
    def mock_context(self):
        """Create mock Bolt context."""
        context = Mock(spec=BoltContext)
        context.user_id = "U123BOT"
        return context

    @pytest.fixture
    def mention_event(self):
        """Create test mention event."""
        return {
            "type": "message",
            "text": "<@U123BOT> Hello there, can you help me?",
            "user": "U456USER",
            "ts": "1234567890.123",
            "channel": "C789CHANNEL",
            "thread_ts": "1234567890.123",
        }

    @pytest.fixture
    def thread_context_mock(self):
        """Create mock thread context."""
        messages = [
            ThreadMessage(
                user_id="U456USER",
                text="Hello there, can you help me?",
                timestamp="1234567890.123",
                is_bot_message=False,
                token_count=10,
            )
        ]
        return ThreadContext(
            thread_ts="1234567890.123",
            channel_id="C789CHANNEL",
            messages=messages,
            token_count=10,
        )

    @pytest.fixture
    def ai_response_mock(self):
        """Create mock AI response."""
        return AIResponse(
            content="I'd be happy to help! What specific question do you have?",
            model_used="gpt-35-turbo",
            deployment_name="test-deployment",
            tokens_used=45,
            generation_time=1.2,
            context_tokens=25,
            completion_tokens=20,
            azure_endpoint="https://test.openai.azure.com",
        )

    @pytest.mark.asyncio
    async def test_handle_mention_success(
        self,
        mock_slack_client,
        mock_context,
        mention_event,
        thread_context_mock,
        ai_response_mock,
    ):
        """Test successful handling of AI mention."""
        # This test will be implemented when we create the handler
        # For now, we define the expected interface

        # Mock dependencies
        with patch("meowth.handlers.ai_mention.ContextAnalyzer") as mock_analyzer_class:
            with patch(
                "meowth.handlers.ai_mention.get_azure_openai_client"
            ) as mock_client_fn:
                # Setup mocks
                mock_analyzer = Mock()
                mock_analyzer.analyze_thread_context = AsyncMock(
                    return_value=thread_context_mock
                )
                mock_analyzer.cleanup_session_context = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                mock_ai_client = AsyncMock()
                mock_ai_client.generate_response = AsyncMock(
                    return_value=ai_response_mock
                )
                mock_client_fn.return_value = mock_ai_client

                mock_slack_client.chat_postMessage = AsyncMock(
                    return_value={"ok": True}
                )

                # Import and call handler (will be created)
                try:
                    from meowth.handlers.ai_mention import handle_ai_mention

                    await handle_ai_mention(
                        mention_event, mock_slack_client, mock_context
                    )

                    # Verify interactions (check that session parameter is passed)
                    mock_analyzer.analyze_thread_context.assert_called_once()
                    call_args = mock_analyzer.analyze_thread_context.call_args
                    assert call_args.kwargs["channel_id"] == "C789CHANNEL"
                    assert call_args.kwargs["thread_ts"] == "1234567890.123"
                    assert call_args.kwargs["bot_user_id"] == "U123BOT"
                    assert (
                        "session" in call_args.kwargs
                    )  # Verify session parameter is passed

                    mock_ai_client.generate_response.assert_called_once()

                    mock_slack_client.chat_postMessage.assert_called_once()
                    call_args = mock_slack_client.chat_postMessage.call_args
                    assert call_args.kwargs["channel"] == "C789CHANNEL"
                    assert call_args.kwargs["thread_ts"] == "1234567890.123"
                    assert ai_response_mock.content in call_args.kwargs["text"]

                except ImportError:
                    # Handler not yet implemented - this test should fail
                    pytest.fail("AI mention handler not yet implemented")

    @pytest.mark.asyncio
    async def test_handle_mention_azure_openai_error(
        self, mock_slack_client, mock_context, mention_event, thread_context_mock
    ):
        """Test handling of Azure OpenAI API errors."""

        with patch("meowth.handlers.ai_mention.ContextAnalyzer") as mock_analyzer_class:
            with patch(
                "meowth.handlers.ai_mention.get_azure_openai_client"
            ) as mock_client_fn:
                # Setup mocks
                mock_analyzer = Mock()
                mock_analyzer.analyze_thread_context = AsyncMock(
                    return_value=thread_context_mock
                )
                mock_analyzer.cleanup_session_context = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                mock_ai_client = AsyncMock()
                mock_ai_client.generate_response = AsyncMock(
                    side_effect=AzureOpenAIError(
                        "API unavailable", "SERVICE_UNAVAILABLE"
                    )
                )
                mock_client_fn.return_value = mock_ai_client

                mock_slack_client.chat_postMessage = AsyncMock(
                    return_value={"ok": True}
                )

                try:
                    from meowth.handlers.ai_mention import handle_ai_mention

                    await handle_ai_mention(
                        mention_event, mock_slack_client, mock_context
                    )

                    # Should post fallback message
                    mock_slack_client.chat_postMessage.assert_called_once()
                    call_args = mock_slack_client.chat_postMessage.call_args
                    assert "currently unavailable" in call_args.kwargs["text"].lower()

                except ImportError:
                    pytest.fail("AI mention handler not yet implemented")

    @pytest.mark.asyncio
    async def test_handle_mention_rate_limit_error(
        self, mock_slack_client, mock_context, mention_event, thread_context_mock
    ):
        """Test handling of rate limit errors."""

        with patch("meowth.handlers.ai_mention.ContextAnalyzer") as mock_analyzer_class:
            with patch(
                "meowth.handlers.ai_mention.get_azure_openai_client"
            ) as mock_client_fn:
                # Setup mocks
                mock_analyzer = Mock()
                mock_analyzer.analyze_thread_context = AsyncMock(
                    return_value=thread_context_mock
                )
                mock_analyzer.cleanup_session_context = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                mock_ai_client = AsyncMock()
                mock_ai_client.generate_response = AsyncMock(
                    side_effect=RateLimitError("Rate limit exceeded", retry_after=30.0)
                )
                mock_client_fn.return_value = mock_ai_client

                mock_slack_client.chat_postMessage = AsyncMock(
                    return_value={"ok": True}
                )

                try:
                    from meowth.handlers.ai_mention import handle_ai_mention

                    await handle_ai_mention(
                        mention_event, mock_slack_client, mock_context
                    )

                    # Should post rate limit message
                    mock_slack_client.chat_postMessage.assert_called_once()
                    call_args = mock_slack_client.chat_postMessage.call_args
                    assert (
                        "busy" in call_args.kwargs["text"].lower()
                        or "try again" in call_args.kwargs["text"].lower()
                    )

                except ImportError:
                    pytest.fail("AI mention handler not yet implemented")

    @pytest.mark.asyncio
    async def test_handle_mention_context_analysis_error(
        self, mock_slack_client, mock_context, mention_event
    ):
        """Test handling of context analysis errors."""

        with patch("meowth.handlers.ai_mention.ContextAnalyzer") as mock_analyzer_class:
            with patch(
                "meowth.handlers.ai_mention.get_azure_openai_client"
            ) as mock_client_fn:
                # Setup mocks
                mock_analyzer = Mock()
                mock_analyzer.analyze_thread_context = AsyncMock(
                    side_effect=Exception("Failed to analyze context")
                )
                mock_analyzer.cleanup_session_context = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                mock_ai_client = AsyncMock()
                mock_client_fn.return_value = mock_ai_client

                mock_slack_client.chat_postMessage = AsyncMock(
                    return_value={"ok": True}
                )

                try:
                    from meowth.handlers.ai_mention import handle_ai_mention

                    await handle_ai_mention(
                        mention_event, mock_slack_client, mock_context
                    )

                    # Should post fallback message
                    mock_slack_client.chat_postMessage.assert_called_once()
                    call_args = mock_slack_client.chat_postMessage.call_args
                    assert call_args.kwargs[
                        "text"
                    ]  # Some fallback message should be posted

                except ImportError:
                    pytest.fail("AI mention handler not yet implemented")

    def test_extract_mention_from_text(self):
        """Test extracting bot mention from message text."""
        # This will test a utility function for extracting mentions

        try:
            from meowth.handlers.ai_mention import extract_user_message

            test_cases = [
                ("<@U123BOT> hello world", "hello world"),
                (
                    "hey <@U123BOT> how are you?",
                    "hey how are you?",
                ),  # Note: whitespace normalized
                ("<@U123BOT|bot> help me", "help me"),
                ("no mention here", "no mention here"),
                ("", ""),
            ]

            for input_text, expected_output in test_cases:
                result = extract_user_message(input_text, "U123BOT")
                assert result == expected_output.strip()

        except ImportError:
            # Utility function not yet implemented
            pass

    def test_is_thread_message(self):
        """Test detection of thread messages vs channel messages."""

        try:
            from meowth.handlers.ai_mention import is_thread_message

            # Thread message has thread_ts
            thread_event = {"ts": "1234567890.123", "thread_ts": "1234567880.000"}
            assert is_thread_message(thread_event) is True

            # Channel message has no thread_ts
            channel_event = {"ts": "1234567890.123"}
            assert is_thread_message(channel_event) is False

            # Original thread message (ts == thread_ts)
            original_event = {"ts": "1234567880.000", "thread_ts": "1234567880.000"}
            assert is_thread_message(original_event) is True

        except ImportError:
            # Utility function not yet implemented
            pass

    @pytest.mark.asyncio
    async def test_post_response_with_formatting(self, mock_slack_client):
        """Test posting response with proper formatting."""

        try:
            from meowth.handlers.ai_mention import post_ai_response

            response = AIResponse(
                content="This is a test response with **bold** text",
                model_used="gpt-35-turbo",
                deployment_name="test-deployment",
                tokens_used=25,
                generation_time=1.0,
                context_tokens=15,
                completion_tokens=10,
                azure_endpoint="https://test.openai.azure.com",
            )

            mock_slack_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            await post_ai_response(
                mock_slack_client, "C123CHANNEL", "1234567890.123", response
            )

            # Verify the message was posted
            mock_slack_client.chat_postMessage.assert_called_once()
            call_args = mock_slack_client.chat_postMessage.call_args

            assert call_args.kwargs["channel"] == "C123CHANNEL"
            assert call_args.kwargs["thread_ts"] == "1234567890.123"
            assert response.content in call_args.kwargs["text"]

        except ImportError:
            # Function not yet implemented
            pass
