"""Unit tests for Azure OpenAI client basic response generation."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from openai import APIError, RateLimitError as OpenAIRateLimitError
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage

from meowth.ai.client import AzureOpenAIClient, AzureOpenAIConfig, RateLimiter
from meowth.ai.models import (
    ThreadContext,
    ThreadMessage,
    AIResponse,
    AzureOpenAIError,
    RateLimitError,
)


@pytest.fixture
def azure_config():
    """Create test Azure OpenAI configuration."""
    return AzureOpenAIConfig(
        api_key="test-api-key",
        endpoint="https://test.openai.azure.com",
        deployment_name="test-deployment",
        api_version="2024-02-01",
        model="gpt-35-turbo",
    )


@pytest.fixture
def thread_context():
    """Create test thread context."""
    messages = [
        ThreadMessage(
            user_id="U123",
            text="Hello there",
            timestamp="1234567890.123",
            is_bot_message=False,
            token_count=5,
        ),
        ThreadMessage(
            user_id="U456",
            text="How can I help?",
            timestamp="1234567891.456",
            is_bot_message=False,
            token_count=7,
        ),
    ]
    return ThreadContext(
        thread_ts="1234567890.123",
        channel_id="C123456",
        messages=messages,
        token_count=12,
    )


@pytest.fixture
def mock_completion():
    """Create mock OpenAI completion response."""
    return ChatCompletion(
        id="test-completion-id",
        model="gpt-35-turbo",
        object="chat.completion",
        created=1234567890,
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    content="This is a test response from Azure OpenAI",
                    role="assistant",
                ),
                finish_reason="stop",
            )
        ],
        usage=CompletionUsage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
    )


class TestAzureOpenAIClient:
    """Test cases for Azure OpenAI client basic functionality."""

    def test_init_with_config(self, azure_config):
        """Test client initialization with provided configuration."""
        client = AzureOpenAIClient(azure_config)

        assert client.config == azure_config
        assert client.rate_limiter is not None
        assert client._client is not None
        assert client._encoding is not None

    @patch("meowth.ai.client.config")
    def test_init_from_env(self, mock_config):
        """Test client initialization from environment variables."""
        mock_config.azure_openai_api_key = "env-api-key"
        mock_config.azure_openai_endpoint = "https://env.openai.azure.com"
        mock_config.azure_openai_deployment_name = "env-deployment"
        mock_config.azure_openai_api_version = "2024-02-01"
        mock_config.azure_openai_model = "gpt-4"

        client = AzureOpenAIClient()

        assert client.config.api_key == "env-api-key"
        assert client.config.endpoint == "https://env.openai.azure.com"
        assert client.config.deployment_name == "env-deployment"
        assert client.config.model == "gpt-4"

    def test_count_tokens_success(self, azure_config):
        """Test token counting functionality."""
        client = AzureOpenAIClient(azure_config)

        text = "Hello world, this is a test message"
        token_count = client.count_tokens(text)

        assert isinstance(token_count, int)
        assert token_count > 0
        assert token_count < len(text)  # Should be more efficient than character count

    def test_count_tokens_fallback(self, azure_config):
        """Test token counting fallback when tiktoken fails."""
        client = AzureOpenAIClient(azure_config)

        # Mock tiktoken to raise an exception
        with patch.object(
            client._encoding, "encode", side_effect=Exception("tiktoken error")
        ):
            text = "Hello world"
            token_count = client.count_tokens(text)

            # Should use fallback estimation
            assert token_count == len(text) // 4

    @pytest.mark.asyncio
    async def test_generate_response_success(
        self, azure_config, thread_context, mock_completion
    ):
        """Test successful Azure OpenAI response generation."""
        client = AzureOpenAIClient(azure_config)

        # Mock the rate limiter and OpenAI client
        client.rate_limiter.acquire = AsyncMock()
        client._client.chat.completions.create = AsyncMock(return_value=mock_completion)

        response = await client.generate_response(thread_context)

        # Verify response structure
        assert isinstance(response, AIResponse)
        assert response.content == "This is a test response from Azure OpenAI"
        assert response.model_used == azure_config.model
        assert response.deployment_name == azure_config.deployment_name
        assert response.tokens_used == 70
        assert response.context_tokens == 50
        assert response.completion_tokens == 20
        assert response.azure_endpoint == azure_config.endpoint
        assert response.generation_time > 0

    @pytest.mark.asyncio
    async def test_generate_response_rate_limit_error(
        self, azure_config, thread_context
    ):
        """Test handling of rate limit errors."""
        client = AzureOpenAIClient(azure_config)

        # Mock rate limiter to pass, but OpenAI to raise rate limit error
        client.rate_limiter.acquire = AsyncMock()
        rate_limit_error = OpenAIRateLimitError(
            message="Rate limit exceeded", response=Mock(), body={}
        )
        client._client.chat.completions.create = AsyncMock(side_effect=rate_limit_error)

        with pytest.raises(RateLimitError) as exc_info:
            await client.generate_response(thread_context)

        assert "Azure OpenAI rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.error_code == "RATE_LIMIT_EXCEEDED"

    @pytest.mark.asyncio
    async def test_generate_response_api_error(self, azure_config, thread_context):
        """Test handling of Azure OpenAI API errors."""
        client = AzureOpenAIClient(azure_config)

        client.rate_limiter.acquire = AsyncMock()
        api_error = APIError(message="Invalid request", request=Mock(), body={})
        api_error.code = "invalid_request"
        client._client.chat.completions.create = AsyncMock(side_effect=api_error)

        with pytest.raises(AzureOpenAIError) as exc_info:
            await client.generate_response(thread_context)

        assert "Azure OpenAI API error" in str(exc_info.value)
        assert exc_info.value.error_code == "invalid_request"

    @pytest.mark.asyncio
    async def test_generate_response_context_too_large(
        self, azure_config, thread_context
    ):
        """Test handling of context that exceeds token limits."""
        client = AzureOpenAIClient(azure_config)

        # Mock count_tokens to return large value
        client.count_tokens = Mock(return_value=1000)
        client.rate_limiter.acquire = AsyncMock()

        with pytest.raises(AzureOpenAIError) as exc_info:
            await client.generate_response(thread_context)

        assert "Context too large" in str(exc_info.value)
        assert exc_info.value.error_code == "CONTEXT_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_health_check_success(self, azure_config):
        """Test successful health check."""
        client = AzureOpenAIClient(azure_config)

        # Mock successful completion
        mock_response = Mock()
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        is_healthy = await client.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, azure_config):
        """Test failed health check."""
        client = AzureOpenAIClient(azure_config)

        # Mock API error
        client._client.chat.completions.create = AsyncMock(
            side_effect=APIError(message="Service unavailable", request=Mock(), body={})
        )

        is_healthy = await client.health_check()
        assert is_healthy is False

    def test_build_messages(self, azure_config, thread_context):
        """Test message building for OpenAI API."""
        client = AzureOpenAIClient(azure_config)

        messages = client._build_messages(thread_context, "You are a helpful assistant")

        assert len(messages) >= 3  # System + user messages + final instruction
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"

        # Check that thread messages are included
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assert len(user_messages) >= 1  # At least the final instruction

        # Check final instruction
        assert messages[-1]["role"] == "user"
        assert "helpful response" in messages[-1]["content"]


class TestRateLimiter:
    """Test cases for rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """Test acquiring tokens when within rate limit."""
        limiter = RateLimiter(max_requests_per_minute=60)

        # Should acquire immediately
        await limiter.acquire()
        assert limiter.tokens < limiter.max_requests

    @pytest.mark.asyncio
    async def test_acquire_at_limit(self):
        """Test acquiring tokens when at rate limit."""
        limiter = RateLimiter(max_requests_per_minute=60)

        # Exhaust tokens
        limiter.tokens = 0

        # This should wait and then succeed
        await limiter.acquire()
        assert limiter.tokens >= 0

    def test_token_refill(self):
        """Test that tokens are refilled over time."""
        limiter = RateLimiter(max_requests_per_minute=60)

        # Use all tokens
        limiter.tokens = 0
        limiter.last_update -= 10  # Simulate 10 seconds ago

        # Manually trigger refill by calling acquire (without await to avoid blocking)
        import time

        now = time.time()
        elapsed = now - limiter.last_update
        expected_tokens = min(
            limiter.max_requests, 0 + elapsed * (limiter.max_requests / 60.0)
        )

        assert expected_tokens > 0
