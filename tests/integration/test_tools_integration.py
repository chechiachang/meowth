"""Integration tests for AI agent tools.

This module tests the full integration of tools, registry, and
agent execution including error handling and tool orchestration.
"""

import pytest
import asyncio
from unittest.mock import patch

from meowth.ai.tools.registry import ToolRegistry
from meowth.ai.tools.config_manager import ConfigurationManager
from meowth.ai.tools.exceptions import ToolError, ErrorSeverity, ErrorCategory


class TestToolsIntegration:
    """Integration tests for the complete tools system."""

    @pytest.fixture
    async def registry_with_config(self, tmp_path):
        """Registry with test configuration."""
        config_path = tmp_path / "test_tools.yaml"
        config_content = """
slack_tools:
  enabled: true
  bot_token: "test-token"
  fetch_messages:
    enabled: true

openai_tools:
  enabled: true
  api_key: "test-key"
  model_config:
    default_model: "gpt-4"
  tools:
    summarize_messages:
      enabled: true
"""
        config_path.write_text(config_content)

        config_manager = ConfigurationManager(str(config_path))
        await config_manager.initialize()

        registry = ToolRegistry()
        await registry.initialize(config_manager)

        return registry, config_manager

    @pytest.mark.asyncio
    async def test_registry_initialization(self, registry_with_config):
        """Test complete registry initialization with tools."""
        registry, config_manager = await registry_with_config

        # Should have tools from both Slack and OpenAI
        tools = registry.list_tools()
        tool_names = [tool.metadata.name for tool in tools]

        assert "fetch_messages" in tool_names
        assert "summarize_messages" in tool_names
        assert len(tools) >= 2

    @pytest.mark.asyncio
    async def test_end_to_end_message_workflow(self, registry_with_config):
        """Test complete message fetching and summarization workflow."""
        registry, config_manager = await registry_with_config

        # Get fetch_messages tool
        fetch_tool = registry.get_tool("fetch_messages")
        assert fetch_tool is not None

        # Get summarize_messages tool
        summarize_tool = registry.get_tool("summarize_messages")
        assert summarize_tool is not None

        # Mock the actual API calls for this integration test
        with patch("slack_sdk.WebClient.conversations_history") as mock_history:
            mock_history.return_value = {
                "messages": [
                    {"text": "Hello", "user": "U123", "ts": "1234567890.123456"},
                    {"text": "World", "user": "U456", "ts": "1234567891.123456"},
                ]
            }

            # Test fetch → summarize workflow
            messages_result = await fetch_tool.call(channel_id="C1234567890", count=10)

            summary_result = await summarize_tool.call(
                messages_json=messages_result, style="brief"
            )

            assert "2 messages" in summary_result

    @pytest.mark.asyncio
    async def test_tool_error_propagation(self, registry_with_config):
        """Test error handling across tool boundaries."""
        registry, config_manager = await registry_with_config

        fetch_tool = registry.get_tool("fetch_messages")
        assert fetch_tool is not None

        # Test with invalid channel ID (should raise ToolError)
        with pytest.raises(ToolError) as exc_info:
            await fetch_tool.call(channel_id="invalid", count=10)

        error = exc_info.value
        assert error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
        assert error.category == ErrorCategory.EXTERNAL_SERVICE_ERROR

    @pytest.mark.asyncio
    async def test_configuration_reload_integration(
        self, registry_with_config, tmp_path
    ):
        """Test hot configuration reload with registry updates."""
        registry, config_manager = await registry_with_config

        initial_tools = registry.list_tools()
        initial_count = len(initial_tools)

        # Update configuration to disable a tool
        config_path = tmp_path / "test_tools.yaml"
        new_config = """
slack_tools:
  enabled: true
  bot_token: "test-token"
  fetch_messages:
    enabled: false  # Disabled

openai_tools:
  enabled: true
  api_key: "test-key"
  model_config:
    default_model: "gpt-4"
  tools:
    summarize_messages:
      enabled: true
"""
        config_path.write_text(new_config)

        # Wait for file system event and reload
        await asyncio.sleep(0.1)

        # Registry should have fewer tools now
        updated_tools = registry.list_tools()
        tool_names = [tool.metadata.name for tool in updated_tools]

        assert "fetch_messages" not in tool_names
        assert "summarize_messages" in tool_names
        assert len(updated_tools) < initial_count

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, registry_with_config):
        """Test concurrent execution of multiple tools."""
        registry, config_manager = await registry_with_config

        fetch_tool = registry.get_tool("fetch_messages")

        # Mock API calls for concurrent test
        with patch("slack_sdk.WebClient.conversations_history") as mock_history:
            mock_history.return_value = {
                "messages": [
                    {"text": "Test message", "user": "U123", "ts": "1234567890.123456"}
                ]
            }

            # Execute tools concurrently
            tasks = [
                fetch_tool.call(channel_id="C1234567890", count=5),
                fetch_tool.call(channel_id="C0987654321", count=3),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Both should succeed (or both should have same mock data)
            assert len(results) == 2
            for result in results:
                assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_tool_metadata_consistency(self, registry_with_config):
        """Test tool metadata is consistent across registry operations."""
        registry, config_manager = await registry_with_config

        tools = registry.list_tools()

        for tool in tools:
            # Get tool by name and verify it's the same instance
            retrieved_tool = registry.get_tool(tool.metadata.name)
            assert retrieved_tool is tool

            # Verify metadata completeness
            assert tool.metadata.name
            assert tool.metadata.description
            assert tool.metadata.parameters

    @pytest.mark.asyncio
    async def test_registry_cleanup(self, registry_with_config):
        """Test proper cleanup of registry resources."""
        registry, config_manager = await registry_with_config

        # Verify tools are available
        tools = registry.list_tools()
        assert len(tools) > 0

        # Cleanup registry
        await registry.cleanup()

        # Should still be able to list tools (graceful degradation)
        tools_after_cleanup = registry.list_tools()
        assert isinstance(tools_after_cleanup, list)

    @pytest.mark.asyncio
    async def test_configuration_validation_integration(self, tmp_path):
        """Test configuration validation during registry initialization."""
        # Create invalid configuration
        config_path = tmp_path / "invalid_tools.yaml"
        invalid_config = """
slack_tools:
  enabled: true
  # Missing required bot_token
  fetch_messages:
    enabled: true

openai_tools:
  enabled: true
  # Missing required api_key
"""
        config_path.write_text(invalid_config)

        config_manager = ConfigurationManager(str(config_path))
        await config_manager.initialize()

        registry = ToolRegistry()

        # Should handle invalid config gracefully
        await registry.initialize(config_manager)

        # Should have no tools due to missing credentials
        tools = registry.list_tools()
        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, registry_with_config):
        """Test rate limiting behavior in integrated environment."""
        registry, config_manager = await registry_with_config

        fetch_tool = registry.get_tool("fetch_messages")
        assert fetch_tool is not None

        # Make multiple rapid requests to test rate limiting
        tasks = []
        for i in range(5):
            task = fetch_tool.call(channel_id=f"C123456789{i}", count=1)
            tasks.append(task)

        # Should handle rate limiting gracefully
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Some may succeed, some may be rate limited
        assert len(results) == 5

        # At least one should succeed or be a controlled error
        success_or_controlled_errors = 0
        for result in results:
            if isinstance(result, Exception):
                if isinstance(result, ToolError):
                    success_or_controlled_errors += 1
            else:
                success_or_controlled_errors += 1

        assert success_or_controlled_errors > 0
