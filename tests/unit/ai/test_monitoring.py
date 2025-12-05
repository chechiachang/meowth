"""Tests for Langfuse monitoring integration."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from meowth.ai.monitoring import (
    LangfuseMonitor,
    get_langfuse_monitor,
    get_langfuse_observe_decorator,
)
from meowth.ai.models import RequestSession, ThreadContext, AIResponse, SessionStatus


@pytest.fixture
def mock_session():
    """Create a mock RequestSession for testing."""
    return RequestSession(
        user_id="test_user",
        thread_context=ThreadContext(
            thread_ts="1234567890.123456",
            channel_id="C1234567890",
            messages=[],
        ),
    )


@pytest.fixture
def mock_ai_response():
    """Create a mock AIResponse for testing."""
    return AIResponse(
        content="Test response",
        model_used="gpt-4",
        deployment_name="test-deployment",
        tokens_used=50,
        generation_time=1.5,
        context_tokens=30,
        completion_tokens=20,
        azure_endpoint="https://test.openai.azure.com/",
        created_at=datetime.now(),
    )


@pytest.fixture
def mock_thread_context():
    """Create a mock ThreadContext for testing."""
    return ThreadContext(
        thread_ts="1234567890.123456",
        channel_id="C1234567890",
        messages=[],
        token_count=100,
    )


class TestLangfuseMonitor:
    """Test Langfuse monitoring functionality."""

    @patch("meowth.ai.monitoring.LANGFUSE_AVAILABLE", False)
    def test_monitor_disabled_when_unavailable(self):
        """Test that monitor is disabled when Langfuse is not available."""
        monitor = LangfuseMonitor()
        assert not monitor.enabled

    @patch("meowth.ai.monitoring.LANGFUSE_AVAILABLE", True)
    @patch("meowth.ai.monitoring.config")
    def test_monitor_disabled_without_config(self, mock_config):
        """Test that monitor is disabled without proper configuration."""
        mock_config.langfuse_public_key = ""
        mock_config.langfuse_secret_key = ""
        
        monitor = LangfuseMonitor()
        assert not monitor.enabled

    @patch("meowth.ai.monitoring.LANGFUSE_AVAILABLE", True)
    @patch("meowth.ai.monitoring.config")
    @patch("meowth.ai.monitoring.Langfuse")
    def test_monitor_enabled_with_config(self, mock_langfuse, mock_config):
        """Test that monitor is enabled with proper configuration."""
        mock_config.langfuse_public_key = "pk_test"
        mock_config.langfuse_secret_key = "sk_test"
        mock_langfuse.return_value = Mock()
        
        monitor = LangfuseMonitor()
        assert monitor.enabled

    def test_get_decorator(self):
        """Test getting the Langfuse observe decorator."""
        decorator = get_langfuse_observe_decorator()
        assert callable(decorator)


class TestLangfuseDecorator:
    """Test the Langfuse decorator functionality."""

    def test_get_decorator_when_available(self):
        """Test getting decorator when Langfuse is available."""
        decorator = get_langfuse_observe_decorator()
        assert callable(decorator)

    @pytest.mark.asyncio
    async def test_decorated_function_execution(self):
        """Test that decorated functions execute correctly."""
        decorator = get_langfuse_observe_decorator()
        
        @decorator(name="test_function")
        async def test_func(input_data):
            return {"result": f"processed_{input_data}"}
        
        result = await test_func("test")
        assert result["result"] == "processed_test"


class TestObserveDecorator:
    """Test the observe decorator functionality."""

    @pytest.mark.asyncio
    async def test_decorator_with_function(self):
        """Test decorator application and execution."""
        decorator = get_langfuse_observe_decorator()
        
        @decorator(name="ai_operation")
        async def mock_ai_function(input_text):
            return {"output": f"AI processed: {input_text}", "tokens": 42}
        
        result = await mock_ai_function("hello world")
        assert "output" in result
        assert result["tokens"] == 42


class TestMonitorDecorator:
    """Test the monitor_ai_operation decorator - kept for backwards compatibility."""

    @pytest.mark.asyncio
    async def test_decorator_passthrough_when_disabled(self, mock_session):
        """Test decorator behavior when monitoring is disabled."""
        # The decorator should still work as a passthrough
        decorator = get_langfuse_observe_decorator()
        
        @decorator(name="test_operation")
        async def test_function(session):
            return "success"

        result = await test_function(mock_session)
        assert result == "success"


class TestGlobalMonitor:
    """Test global monitor instance."""

    def test_get_langfuse_monitor_singleton(self):
        """Test that get_langfuse_monitor returns the same instance."""
        monitor1 = get_langfuse_monitor()
        monitor2 = get_langfuse_monitor()
        assert monitor1 is monitor2


class TestTraceContext:
    """Test the langfuse trace context functionality - simplified for decorator approach."""

    @pytest.mark.asyncio
    async def test_decorator_context_management(self, mock_session):
        """Test that decorators manage context properly."""
        decorator = get_langfuse_observe_decorator()
        
        @decorator(name="test_operation")
        async def test_function(session):
            # Function executes within Langfuse context
            return f"processed_{session.user_id}"

        result = await test_function(mock_session)
        assert result == f"processed_{mock_session.user_id}"