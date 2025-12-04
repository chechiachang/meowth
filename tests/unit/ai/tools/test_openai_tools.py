"""Unit tests for OpenAI tools.

This module tests OpenAI-specific tool implementations including
message summarization and OpenAI API integration.
"""

import pytest
import json
from unittest.mock import Mock

from meowth.ai.tools.openai_tools import create_openai_tools


class TestOpenAITools:
    """Test cases for OpenAI tool functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client for testing."""
        client = Mock()
        return client

    @pytest.fixture
    def openai_config(self):
        """Mock OpenAI tools configuration."""
        return {
            "enabled": True,
            "model_config": {
                "default_model": "gpt-4",
                "max_tokens": 1500,
                "temperature": 0.7,
                "timeout_seconds": 20,
            },
            "tools": {
                "summarize_messages": {
                    "enabled": True,
                    "description": "Generate conversation summaries",
                    "max_summary_length": 200,
                }
            },
        }

    @pytest.fixture
    def sample_messages_json(self):
        """Sample messages in JSON format for testing."""
        return json.dumps(
            {
                "messages": [
                    {
                        "text": "Hello team, how is the project going?",
                        "user": "U123456",
                        "timestamp": "1234567890.123456",
                    },
                    {
                        "text": "The project is going well, we're on track.",
                        "user": "U789012",
                        "timestamp": "1234567891.123456",
                    },
                    {
                        "text": "Great! Let me know if you need any help.",
                        "user": "U345678",
                        "timestamp": "1234567892.123456",
                    },
                ],
                "channel": "general",
                "total_fetched": 3,
            }
        )

    def test_create_openai_tools_success(self, mock_openai_client, openai_config):
        """Test successful creation of OpenAI tools."""
        tools = create_openai_tools(mock_openai_client, openai_config)

        assert len(tools) == 1
        assert tools[0].metadata.name == "summarize_messages"
        assert "Generate conversation summaries" in tools[0].metadata.description

    def test_create_openai_tools_disabled(self, mock_openai_client, openai_config):
        """Test creation when summarize_messages tool is disabled."""
        openai_config["tools"]["summarize_messages"]["enabled"] = False

        tools = create_openai_tools(mock_openai_client, openai_config)

        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_summarize_messages_brief_style(
        self, mock_openai_client, openai_config, sample_messages_json
    ):
        """Test brief message summarization."""
        tools = create_openai_tools(mock_openai_client, openai_config)
        summarize_tool = tools[0]

        result = summarize_tool.call(
            messages_json=sample_messages_json, style="brief"
        )

        # For initial implementation, should return basic summary
        result_text = result.raw_output if hasattr(result, 'raw_output') else str(result)
        assert "3 messages" in result_text
        assert "conversation" in result_text.lower()

    @pytest.mark.asyncio
    async def test_summarize_messages_detailed_style(
        self, mock_openai_client, openai_config, sample_messages_json
    ):
        """Test detailed message summarization."""
        tools = create_openai_tools(mock_openai_client, openai_config)
        summarize_tool = tools[0]

        result = summarize_tool.call(
            messages_json=sample_messages_json, style="detailed"
        )

        # Detailed summary should include user count
        result_text = result.raw_output if hasattr(result, 'raw_output') else str(result)
        assert "3 messages" in result_text
        assert "users" in result_text.lower()

    @pytest.mark.asyncio
    async def test_summarize_messages_invalid_json(
        self, mock_openai_client, openai_config
    ):
        """Test handling of invalid JSON input."""
        from meowth.ai.tools.exceptions import ToolError
        tools = create_openai_tools(mock_openai_client, openai_config)
        summarize_tool = tools[0]

        with pytest.raises(ToolError) as exc_info:
            result = summarize_tool.call(messages_json="invalid json", style="brief")
        
        assert "Invalid JSON format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_summarize_messages_empty_messages(
        self, mock_openai_client, openai_config
    ):
        """Test handling of empty message list."""
        empty_messages_json = json.dumps(
            {"messages": [], "channel": "general", "total_fetched": 0}
        )

        tools = create_openai_tools(mock_openai_client, openai_config)
        summarize_tool = tools[0]

        result = summarize_tool.call(
            messages_json=empty_messages_json, style="brief"
        )

        assert "0 messages" in str(result) or "No messages" in str(result)

    @pytest.mark.asyncio
    async def test_summarize_messages_with_default_style(
        self, mock_openai_client, openai_config, sample_messages_json
    ):
        """Test summarization with default style parameter."""
        tools = create_openai_tools(mock_openai_client, openai_config)
        summarize_tool = tools[0]

        # Call without style parameter (should default to "brief")
        result = summarize_tool.call(messages_json=sample_messages_json)

        # Should use default style (brief) when no style specified
        result_text = result.raw_output if hasattr(result, 'raw_output') else str(result)
        assert "3 messages" in result_text

    @pytest.mark.asyncio
    async def test_summarize_messages_malformed_data(
        self, mock_openai_client, openai_config
    ):
        """Test handling of malformed message data."""
        malformed_json = json.dumps({"invalid_key": "invalid_data"})

        tools = create_openai_tools(mock_openai_client, openai_config)
        summarize_tool = tools[0]

        result = summarize_tool.call(messages_json=malformed_json)

        assert "Error summarizing messages" in str(result) or "No messages" in str(result)

    def test_openai_tools_config_validation(self, mock_openai_client):
        """Test configuration validation for OpenAI tools."""
        invalid_config = {
            "enabled": True,
            "model_config": {
                "default_model": "gpt-4",
                "max_tokens": 1500,
                "temperature": 0.7,
            },
            "tools": {
                "summarize_messages": {
                    "enabled": True
                    # Missing description - should handle gracefully
                }
            },
        }

        tools = create_openai_tools(mock_openai_client, invalid_config)
        assert len(tools) == 1  # Tool should still be created

    @pytest.mark.asyncio
    async def test_summarize_messages_edge_cases(
        self, mock_openai_client, openai_config
    ):
        """Test edge cases in message summarization."""
        # Test with single message
        single_message_json = json.dumps(
            {
                "messages": [
                    {
                        "text": "Hello world",
                        "user": "U123456",
                        "timestamp": "1234567890.123456",
                    }
                ],
                "channel": "test",
                "total_fetched": 1,
            }
        )

        tools = create_openai_tools(mock_openai_client, openai_config)
        summarize_tool = tools[0]

        result = summarize_tool.call(messages_json=single_message_json)

        result_text = result.raw_output if hasattr(result, 'raw_output') else str(result)
        assert "1 message" in result_text or "1 messages" in result_text
