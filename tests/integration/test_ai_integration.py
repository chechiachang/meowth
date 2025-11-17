"""Integration tests for end-to-end Azure OpenAI response flow."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from meowth.ai.models import ThreadContext, ThreadMessage, AIResponse
from meowth.ai.client import AzureOpenAIClient
from meowth.ai.context import ContextAnalyzer


@pytest.mark.integration
class TestAzureOpenAIIntegration:
    """Integration tests for complete AI response flow."""

    @pytest.fixture
    def slack_event(self):
        """Create test Slack mention event."""
        return {
            "type": "message",
            "text": "<@U123BOT> What's the weather like?",
            "user": "U456USER",
            "ts": "1234567890.123",
            "channel": "C789CHANNEL",
            "thread_ts": "1234567890.123",
        }

    @pytest.fixture
    def mock_slack_responses(self):
        """Mock Slack API responses."""
        return {
            "conversations_replies": {
                "ok": True,
                "messages": [
                    {
                        "type": "message",
                        "text": "<@U123BOT> What's the weather like?",
                        "user": "U456USER",
                        "ts": "1234567890.123",
                    },
                    {
                        "type": "message",
                        "text": "I'll help you with that!",
                        "user": "U123BOT",
                        "ts": "1234567891.456",
                        "bot_id": "B123",
                    },
                ],
            }
        }

    @pytest.mark.asyncio
    async def test_end_to_end_ai_response_flow(self, slack_event, mock_slack_responses):
        """Test complete flow from Slack event to AI response."""

        with patch("meowth.ai.client.config") as mock_config:
            # Setup config
            mock_config.azure_openai_api_key = "test-key"
            mock_config.azure_openai_endpoint = "https://test.openai.azure.com"
            mock_config.azure_openai_deployment_name = "test-deployment"
            mock_config.azure_openai_api_version = "2024-02-01"
            mock_config.azure_openai_model = "gpt-35-turbo"

            # Mock Slack client
            mock_slack_client = Mock()
            mock_slack_client.conversations_replies = Mock(
                return_value=mock_slack_responses["conversations_replies"]
            )

            # Mock Azure OpenAI response
            with patch("meowth.ai.client.AsyncAzureOpenAI") as mock_openai:
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[
                    0
                ].message.content = "The weather is sunny and 75°F today!"
                mock_completion.usage.total_tokens = 45
                mock_completion.usage.prompt_tokens = 25
                mock_completion.usage.completion_tokens = 20

                mock_openai.return_value.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                # Test the integration flow
                try:
                    # Initialize components
                    context_analyzer = ContextAnalyzer(mock_slack_client)
                    context_analyzer.max_age_hours = 0  # Disable age filtering for test
                    ai_client = AzureOpenAIClient()

                    # Analyze context
                    thread_context = await context_analyzer.analyze_thread_context(
                        slack_event["channel"], slack_event["thread_ts"], "U123BOT"
                    )

                    # Verify context analysis
                    assert isinstance(thread_context, ThreadContext)
                    assert thread_context.channel_id == slack_event["channel"]
                    assert thread_context.thread_ts == slack_event["thread_ts"]
                    assert len(thread_context.messages) > 0

                    # Generate AI response
                    ai_response = await ai_client.generate_response(thread_context)

                    # Verify AI response
                    assert isinstance(ai_response, AIResponse)
                    assert ai_response.content == "The weather is sunny and 75°F today!"
                    assert ai_response.tokens_used == 45
                    assert ai_response.azure_endpoint == "https://test.openai.azure.com"
                    assert ai_response.deployment_name == "test-deployment"

                    # Verify Azure OpenAI was called correctly
                    mock_openai.return_value.chat.completions.create.assert_called_once()
                    call_args = (
                        mock_openai.return_value.chat.completions.create.call_args
                    )

                    assert call_args.kwargs["model"] == "test-deployment"
                    assert (
                        len(call_args.kwargs["messages"]) >= 2
                    )  # System + user messages
                    assert call_args.kwargs["messages"][0]["role"] == "system"

                except Exception as e:
                    pytest.fail(f"Integration test failed: {e}")

    @pytest.mark.asyncio
    async def test_context_analysis_with_multiple_messages(self, mock_slack_responses):
        """Test context analysis with multiple thread messages."""

        # Extend mock responses with more messages
        extended_responses = mock_slack_responses.copy()
        extended_responses["conversations_replies"]["messages"].extend(
            [
                {
                    "type": "message",
                    "text": "Actually, I also need the forecast for tomorrow",
                    "user": "U456USER",
                    "ts": "1234567892.789",
                },
                {
                    "type": "message",
                    "text": "Can you help with both days?",
                    "user": "U789USER",
                    "ts": "1234567893.012",
                },
            ]
        )

        mock_slack_client = Mock()
        mock_slack_client.conversations_replies = Mock(
            return_value=extended_responses["conversations_replies"]
        )

        context_analyzer = ContextAnalyzer(mock_slack_client)
        context_analyzer.max_age_hours = 0  # Disable age filtering for test
        context_analyzer.max_age_hours = 999999  # Disable age filtering

        thread_context = await context_analyzer.analyze_thread_context(
            "C789CHANNEL", "1234567890.123", "U123BOT"
        )

        # Should include all relevant messages
        assert len(thread_context.messages) == 4
        assert thread_context.token_count > 0

        # Messages should be in reverse chronological order (most recent first)
        timestamps = [msg.timestamp for msg in thread_context.messages]
        assert timestamps == sorted(timestamps, reverse=True)

        # Should correctly identify bot messages
        bot_messages = [msg for msg in thread_context.messages if msg.is_bot_message]
        assert len(bot_messages) == 1
        assert bot_messages[0].text == "I'll help you with that!"

    @pytest.mark.asyncio
    async def test_token_counting_and_truncation(self, mock_slack_responses):
        """Test token counting and context truncation for large threads."""

        # Create a large number of messages to test truncation
        large_messages = []
        for i in range(100):
            large_messages.append(
                {
                    "type": "message",
                    "text": f"This is message {i} with some content to test token limits and truncation behavior.",
                    "user": f"U{i:03d}USER",
                    "ts": f"1234567{i:03d}.123",
                }
            )

        large_responses = {"ok": True, "messages": large_messages}

        mock_slack_client = Mock()
        mock_slack_client.conversations_replies = Mock(return_value=large_responses)

        context_analyzer = ContextAnalyzer(mock_slack_client)
        context_analyzer.max_age_hours = 999999  # Disable age filtering

        thread_context = await context_analyzer.analyze_thread_context(
            "C789CHANNEL", "1234567000.123", "U123BOT"
        )

        # Should truncate to stay within limits
        assert len(thread_context.messages) <= 50  # Max messages limit
        assert thread_context.token_count <= 3000  # Max token limit

        # Should prioritize recent messages (first messages should be most recent)
        if len(large_messages) > len(thread_context.messages):
            # Check that we kept the most recent messages (with reverse chronological order)
            first_message_in_context = thread_context.messages[0]
            assert (
                "99" in first_message_in_context.text
            )  # Should be the most recent message

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, slack_event):
        """Test error handling throughout the integration flow."""

        # Test Slack API error
        mock_slack_client = Mock()
        mock_slack_client.conversations_replies = Mock(
            side_effect=Exception("Slack API unavailable")
        )

        context_analyzer = ContextAnalyzer(mock_slack_client)

        with pytest.raises(Exception):
            await context_analyzer.analyze_thread_context(
                slack_event["channel"], slack_event["thread_ts"], "U123BOT"
            )

    @pytest.mark.asyncio
    async def test_performance_requirements(self, slack_event, mock_slack_responses):
        """Test that response generation meets performance requirements."""

        with patch("meowth.ai.client.config") as mock_config:
            mock_config.azure_openai_api_key = "test-key"
            mock_config.azure_openai_endpoint = "https://test.openai.azure.com"
            mock_config.azure_openai_deployment_name = "test-deployment"
            mock_config.azure_openai_api_version = "2024-02-01"
            mock_config.azure_openai_model = "gpt-35-turbo"

            mock_slack_client = Mock()
            mock_slack_client.conversations_replies = Mock(
                return_value=mock_slack_responses["conversations_replies"]
            )

            with patch("meowth.ai.client.AsyncAzureOpenAI") as mock_openai:
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = "Fast response!"
                mock_completion.usage.total_tokens = 20
                mock_completion.usage.prompt_tokens = 10
                mock_completion.usage.completion_tokens = 10

                mock_openai.return_value.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                # Measure total response time
                start_time = datetime.now()

                context_analyzer = ContextAnalyzer(mock_slack_client)
                ai_client = AzureOpenAIClient()

                thread_context = await context_analyzer.analyze_thread_context(
                    slack_event["channel"], slack_event["thread_ts"], "U123BOT"
                )

                ai_response = await ai_client.generate_response(thread_context)

                end_time = datetime.now()
                total_time = (end_time - start_time).total_seconds()

                # Should complete within 10 seconds (spec requirement)
                assert total_time < 10.0
                assert ai_response.generation_time < 30.0  # Individual API call limit

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling of concurrent AI requests."""

        with patch("meowth.ai.client.config") as mock_config:
            mock_config.azure_openai_api_key = "test-key"
            mock_config.azure_openai_endpoint = "https://test.openai.azure.com"
            mock_config.azure_openai_deployment_name = "test-deployment"
            mock_config.azure_openai_api_version = "2024-02-01"
            mock_config.azure_openai_model = "gpt-35-turbo"

            with patch("meowth.ai.client.AsyncAzureOpenAI") as mock_openai:
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[0].message.content = "Concurrent response"
                mock_completion.usage.total_tokens = 25
                mock_completion.usage.prompt_tokens = 15
                mock_completion.usage.completion_tokens = 10

                mock_openai.return_value.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                ai_client = AzureOpenAIClient()

                # Create multiple thread contexts
                contexts = []
                for i in range(3):
                    context = ThreadContext(
                        thread_ts=f"123456789{i}.123",
                        channel_id=f"C{i:03d}CHANNEL",
                        messages=[
                            ThreadMessage(
                                user_id=f"U{i:03d}USER",
                                text=f"Message {i}",
                                timestamp=f"123456789{i}.123",
                                is_bot_message=False,
                                token_count=5,
                            )
                        ],
                        token_count=5,
                    )
                    contexts.append(context)

                # Execute concurrent requests
                import asyncio

                tasks = [ai_client.generate_response(context) for context in contexts]

                responses = await asyncio.gather(*tasks)

                # All requests should succeed
                assert len(responses) == 3
                for response in responses:
                    assert isinstance(response, AIResponse)
                    assert response.content == "Concurrent response"

    @pytest.mark.asyncio
    async def test_context_aware_response_generation(self, slack_event):
        """Test that AI responses are context-aware and use thread information."""

        # Create a thread with contextual conversation
        contextual_messages = {
            "ok": True,
            "messages": [
                {
                    "type": "message",
                    "text": "I'm planning a trip to Japan next month.",
                    "user": "U456USER",
                    "ts": "1234567890.123",
                },
                {
                    "type": "message",
                    "text": "That sounds exciting! Have you been there before?",
                    "user": "U789USER",
                    "ts": "1234567891.123",
                },
                {
                    "type": "message",
                    "text": "No, it's my first time. I'm a bit nervous about the language barrier.",
                    "user": "U456USER",
                    "ts": "1234567892.123",
                },
                {
                    "type": "message",
                    "text": "<@U123BOT> Any tips for first-time travelers to Japan?",
                    "user": "U456USER",
                    "ts": "1234567893.123",
                },
            ],
        }

        # Mock Slack client
        mock_slack_client = Mock()
        mock_slack_client.conversations_replies = Mock(return_value=contextual_messages)

        with patch("meowth.ai.client.config") as mock_config:
            mock_config.azure_openai_api_key = "test-key"
            mock_config.azure_openai_endpoint = "https://test.openai.azure.com"
            mock_config.azure_openai_deployment_name = "test-deployment"
            mock_config.azure_openai_api_version = "2024-02-01"
            mock_config.azure_openai_model = "gpt-35-turbo"

            with patch("meowth.ai.client.AsyncAzureOpenAI") as mock_openai:
                mock_completion = Mock()
                mock_completion.choices = [Mock()]
                mock_completion.choices[
                    0
                ].message.content = "Based on your conversation about traveling to Japan for the first time and language concerns, I recommend downloading a translation app and learning basic phrases."
                mock_completion.usage = Mock()
                mock_completion.usage.total_tokens = 50
                mock_completion.usage.prompt_tokens = 35
                mock_completion.usage.completion_tokens = 15

                mock_openai.return_value.chat.completions.create = AsyncMock(
                    return_value=mock_completion
                )

                # Create context analyzer
                context_analyzer = ContextAnalyzer(mock_slack_client)
                # Disable age filtering for tests
                context_analyzer.max_age_hours = 999999

                # Analyze thread context
                thread_context = await context_analyzer.analyze_thread_context(
                    "C789CHANNEL", "1234567890.123", "U123BOT"
                )

                # Verify context includes conversation history (reverse chronological order - newest first)
                assert len(thread_context.messages) == 4
                assert (
                    "first-time travelers" in thread_context.messages[0].text
                )  # Most recent message
                assert (
                    "language barrier" in thread_context.messages[1].text
                )  # Second most recent
                assert "Japan" in thread_context.messages[3].text  # Oldest message

                # Generate AI response using context
                ai_client = AzureOpenAIClient()
                response = await ai_client.generate_response(thread_context)

                # Verify response is context-aware
                assert isinstance(response, AIResponse)
                assert "Japan" in response.content
                assert (
                    "translation" in response.content or "language" in response.content
                )

                # Verify the AI was given the full context
                call_args = mock_openai.return_value.chat.completions.create.call_args
                messages_sent = call_args[1]["messages"]

                # Should include context about Japan trip in the conversation
                context_found = any("Japan" in str(msg) for msg in messages_sent)
                assert context_found, (
                    "AI should receive thread context about Japan trip"
                )

    @pytest.mark.asyncio
    async def test_context_token_limit_handling(self, slack_event):
        """Test proper handling when thread context exceeds token limits."""

        # Create a thread with very long messages that would exceed token limits
        long_messages = {"ok": True, "messages": []}

        # Add many shorter messages first (older timestamps)
        long_text = (
            "This is a shorter message with some content. " * 10
        )  # ~500 chars each
        for i in range(20):  # More messages but shorter
            long_messages["messages"].append(
                {
                    "type": "message",
                    "text": f"Message {i}: {long_text}",
                    "user": f"U{i:03d}USER",
                    "ts": f"123456789{i:03d}.123",  # Lower timestamps = older
                }
            )

        # Add the actual bot mention last (it will be most recent) - make it short
        long_messages["messages"].append(
            {
                "type": "message",
                "text": "<@U123BOT> Can you summarize our discussion?",
                "user": "U456USER",
                "ts": "1234567899.123",  # Highest timestamp = most recent
            }
        )

        # Mock Slack client
        mock_slack_client = Mock()
        mock_slack_client.conversations_replies = Mock(return_value=long_messages)

        # Create context analyzer with smaller token limit and no age filtering
        context_analyzer = ContextAnalyzer(
            slack_client=mock_slack_client,
            max_context_tokens=1000,  # Smaller limit to force truncation
            max_messages=50,
        )
        context_analyzer.max_age_hours = 0  # Disable age filtering for test

        # Analyze context
        thread_context = await context_analyzer.analyze_thread_context(
            "C789CHANNEL", "1234567890.123", "U123BOT"
        )

        # Verify context was truncated appropriately
        assert thread_context.token_count <= 1000
        assert (
            len(thread_context.messages) < 21
        )  # Should be truncated from 21 total messages

        # Verify most recent messages are prioritized
        # The bot mention should be included
        mention_found = any("summarize" in msg.text for msg in thread_context.messages)
        assert mention_found, "Bot mention should be prioritized in context"


@pytest.mark.asyncio
@pytest.mark.integration
class TestConcurrentThreadProcessing:
    """Integration tests for concurrent thread processing with Azure OpenAI."""

    @pytest.fixture
    def ai_client(self):
        """Create Azure OpenAI client for testing."""
        from meowth.ai.client import AzureOpenAIConfig

        config = AzureOpenAIConfig(
            api_key="test-key",
            endpoint="test-endpoint",
            deployment_name="test-deployment",
            model="gpt-4",
            api_version="2023-05-15",
        )
        return AzureOpenAIClient(azure_config=config)

    @pytest.fixture
    def mock_slack_client(self):
        """Create mock Slack client."""
        mock_client = AsyncMock()
        mock_client.conversations_replies = AsyncMock()
        mock_client.users_info = AsyncMock()
        return mock_client

    async def test_concurrent_thread_response_generation(
        self, ai_client, mock_slack_client
    ):
        """Test that concurrent threads generate independent responses."""
        # Use current timestamps so messages aren't filtered out

        current_time = time.time()
        ts1 = f"{current_time:.3f}"
        ts2 = f"{current_time + 1:.3f}"

        # Mock different contexts for different threads
        def mock_conversations_replies(channel, ts):
            if ts == ts1:
                return {
                    "ok": True,
                    "messages": [
                        {
                            "ts": ts1,
                            "user": "U123USER1",
                            "text": "Question about Python threading",
                            "thread_ts": ts1,
                        }
                    ],
                }
            elif ts == ts2:
                return {
                    "ok": True,
                    "messages": [
                        {
                            "ts": ts2,
                            "user": "U123USER2",
                            "text": "Question about JavaScript async",
                            "thread_ts": ts2,
                        }
                    ],
                }
            else:
                return {"ok": True, "messages": []}

        mock_slack_client.conversations_replies.side_effect = mock_conversations_replies
        mock_slack_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "Test User", "is_bot": False},
        }

        # Mock Azure OpenAI responses for different contexts
        with patch.object(ai_client, "generate_response") as mock_generate:
            mock_generate.side_effect = [
                "Response about Python threading concepts",
                "Response about JavaScript async/await patterns",
            ]

            # Create context analyzers for different threads
            context_analyzer1 = ContextAnalyzer(slack_client=mock_slack_client)
            context_analyzer2 = ContextAnalyzer(slack_client=mock_slack_client)

            # Process threads concurrently
            tasks = [
                self._process_thread(
                    ai_client,
                    context_analyzer1,
                    "C123CHANNEL",
                    ts1,
                    "U123BOT",
                ),
                self._process_thread(
                    ai_client,
                    context_analyzer2,
                    "C456CHANNEL",
                    ts2,
                    "U123BOT",
                ),
            ]

            responses = await asyncio.gather(*tasks)

            # Verify independent responses
            assert len(responses) == 2
            assert "Python threading" in responses[0]
            assert "JavaScript async" in responses[1]

            # Verify both responses were generated
            assert mock_generate.call_count == 2

    async def test_thread_context_isolation_during_concurrent_processing(
        self, mock_slack_client
    ):
        """Test that thread contexts remain isolated during concurrent processing."""
        # Use current timestamps so messages aren't filtered out

        current_time = time.time()
        ts1 = f"{current_time:.3f}"
        ts2 = f"{current_time + 1:.3f}"
        ts3 = f"{current_time + 2:.3f}"
        ts4 = f"{current_time + 3:.3f}"

        # Mock different contexts with overlapping content
        def mock_conversations_replies(channel, ts):
            if ts == ts1:
                # Thread 1: Technical discussion
                return {
                    "ok": True,
                    "messages": [
                        {
                            "ts": ts1,
                            "user": "U123USER1",
                            "text": "Let's discuss API design patterns",
                            "thread_ts": ts1,
                        },
                        {
                            "ts": ts2,
                            "user": "U123USER2",
                            "text": "REST vs GraphQL considerations",
                            "thread_ts": ts1,
                        },
                    ],
                }
            elif ts == ts3:
                # Thread 2: Social discussion
                return {
                    "ok": True,
                    "messages": [
                        {
                            "ts": ts3,
                            "user": "U123USER3",
                            "text": "Anyone want to grab lunch?",
                            "thread_ts": ts3,
                        },
                        {
                            "ts": ts4,
                            "user": "U123USER4",
                            "text": "I'm in! How about that new restaurant?",
                            "thread_ts": ts3,
                        },
                    ],
                }
            else:
                return {"ok": True, "messages": []}

        mock_slack_client.conversations_replies.side_effect = mock_conversations_replies
        mock_slack_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "Test User", "is_bot": False},
        }

        # Create separate analyzers with session tracking
        context_analyzer1 = ContextAnalyzer(slack_client=mock_slack_client)
        context_analyzer2 = ContextAnalyzer(slack_client=mock_slack_client)

        # Process contexts concurrently
        tasks = [
            context_analyzer1.analyze_thread_context("C123CHANNEL", ts1, "U123BOT"),
            context_analyzer2.analyze_thread_context("C456CHANNEL", ts3, "U123BOT"),
        ]

        contexts = await asyncio.gather(*tasks)

        # Verify contexts are completely isolated
        context1, context2 = contexts

        # Context 1 should only contain technical discussion
        tech_keywords = ["API", "REST", "GraphQL", "design patterns"]
        context1_text = " ".join(msg.text for msg in context1.messages)
        assert any(keyword in context1_text for keyword in tech_keywords)
        assert "lunch" not in context1_text
        assert "restaurant" not in context1_text

        # Context 2 should only contain social discussion
        social_keywords = ["lunch", "restaurant"]
        context2_text = " ".join(msg.text for msg in context2.messages)
        assert any(keyword in context2_text for keyword in social_keywords)
        assert "API" not in context2_text
        assert "GraphQL" not in context2_text

        # Verify distinct thread timestamps
        assert context1.thread_ts == ts1
        assert context2.thread_ts == ts3

    async def test_high_concurrency_thread_processing(self, mock_slack_client):
        """Test system behavior under high concurrent thread load."""
        # Create many concurrent threads
        num_threads = 10

        # Use current timestamps so messages aren't filtered out

        current_time = time.time()

        # Mock responses for all threads
        def mock_conversations_replies(channel, ts):
            # Find which thread this timestamp corresponds to
            for i in range(num_threads):
                expected_ts = f"{current_time + i:.3f}"
                if ts == expected_ts:
                    return {
                        "ok": True,
                        "messages": [
                            {
                                "ts": expected_ts,
                                "user": f"U123USER{i}",
                                "text": f"Message in thread {i}",
                                "thread_ts": expected_ts,
                            }
                        ],
                    }
            return {"ok": True, "messages": []}

        mock_slack_client.conversations_replies.side_effect = mock_conversations_replies
        mock_slack_client.users_info.return_value = {
            "ok": True,
            "user": {"real_name": "Test User", "is_bot": False},
        }

        # Process all threads concurrently
        tasks = []
        analyzers = []

        for i in range(num_threads):
            analyzer = ContextAnalyzer(slack_client=mock_slack_client)
            analyzers.append(analyzer)
            thread_ts = f"{current_time + i:.3f}"
            tasks.append(
                analyzer.analyze_thread_context(
                    f"C{i:03d}CHANNEL", thread_ts, "U123BOT"
                )
            )

        # Execute all tasks concurrently
        start_time = time.time()
        contexts = await asyncio.gather(*tasks)
        end_time = time.time()

        # Verify all contexts processed successfully
        assert len(contexts) == num_threads

        # Verify each context is unique and contains expected content
        for i, context in enumerate(contexts):
            assert len(context.messages) == 1
            assert f"Message in thread {i}" in context.messages[0].text
            thread_ts = f"{current_time + i:.3f}"
            assert context.thread_ts == thread_ts

        # Verify reasonable performance (concurrent processing should be faster)
        processing_time = end_time - start_time
        assert processing_time < 5.0, (
            f"Processing {num_threads} threads took too long: {processing_time}s"
        )

        # Verify no cross-contamination between threads
        all_texts = [" ".join(msg.text for msg in ctx.messages) for ctx in contexts]
        for i, text in enumerate(all_texts):
            # Each context should only contain its own thread content
            assert f"Message in thread {i}" in text
            # Should not contain content from other threads
            for j in range(num_threads):
                if i != j:
                    assert f"Message in thread {j}" not in text

    async def _process_thread(
        self, ai_client, context_analyzer, channel_id, thread_ts, bot_user_id
    ):
        """Helper method to process a single thread with context analysis and AI response."""
        # Analyze thread context
        context = await context_analyzer.analyze_thread_context(
            channel_id, thread_ts, bot_user_id
        )

        # Generate AI response based on context
        response = await ai_client.generate_response(
            messages=[
                {"role": "user", "content": msg.text} for msg in context.messages
            ],
            thread_context=context,
        )

        return response
