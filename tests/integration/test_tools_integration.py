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
    def registry_with_config(self, tmp_path):
        """Registry with test configuration."""
        config_path = tmp_path / "test_tools.yaml"
        config_content = """
slack_tools:
  enabled: true
  bot_token: "test-token"
  tools:
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
        config_manager.initialize()

        registry = ToolRegistry(str(config_path))
        
        # Register factory functions for testing
        from meowth.ai.tools.slack_tools import create_slack_tools
        from meowth.ai.tools.openai_tools import create_openai_tools
        from unittest.mock import Mock
        
        # Mock clients
        slack_client = Mock()
        openai_client = Mock()
        
        # Configure the slack client mock for the test
        slack_client.conversations_history.return_value = {
            "messages": [
                {"text": "Hello", "user": "U123", "ts": "1234567890.123456"},
                {"text": "World", "user": "U456", "ts": "1234567891.123456"},
            ]
        }
        
        # Register factory functions
        registry.register_factory("slack_tools", lambda config, deps, global_config: create_slack_tools(slack_client, config))
        registry.register_factory("openai_tools", lambda config, deps, global_config: create_openai_tools(openai_client, config))
        
        tools = registry.initialize_tools()

        return registry, config_manager, slack_client, openai_client

    @pytest.mark.asyncio
    async def test_registry_initialization(self, registry_with_config):
        """Test complete registry initialization with tools."""
        registry, config_manager, slack_client, openai_client = registry_with_config

        # Should have tools from both Slack and OpenAI
        tools = registry.list_tools()
        tool_names = [tool.metadata.name for tool in tools]

        assert "fetch_messages" in tool_names
        assert "summarize_messages" in tool_names
        assert len(tools) >= 2

    @pytest.mark.asyncio
    async def test_end_to_end_message_workflow(self, registry_with_config):
        """Test complete message fetching and summarization workflow."""
        registry, config_manager, slack_client, openai_client = registry_with_config

        # Get fetch_messages tool
        fetch_tool = registry.get_tool("fetch_messages")
        assert fetch_tool is not None

        # Get summarize_messages tool
        summarize_tool = registry.get_tool("summarize_messages")
        assert summarize_tool is not None

        # Mock the actual API calls for this integration test
        # Reset and configure the mock for this specific test
        slack_client.reset_mock()
        slack_client.conversations_history.return_value = {
            "messages": [
                {"text": "Hello", "user": "U123", "ts": "1234567890.123456"},
                {"text": "World", "user": "U456", "ts": "1234567891.123456"},
            ]
        }

        # Test fetch → summarize workflow
        messages_output = fetch_tool.call(channel_id="C1234567890", limit=10)
        messages_result = messages_output.content

        summary_output = summarize_tool.call(
            messages_json=messages_result, style="brief"
        )
        summary_result = summary_output.content

        assert "2 messages" in summary_result

    @pytest.mark.asyncio
    async def test_tool_error_propagation(self, registry_with_config):
        """Test error handling across tool boundaries."""
        registry, config_manager, slack_client, openai_client = registry_with_config

        fetch_tool = registry.get_tool("fetch_messages")
        assert fetch_tool is not None

        # Configure the mock to simulate an error for invalid channel
        from slack_sdk.errors import SlackApiError
        slack_client.reset_mock()
        slack_client.conversations_history.side_effect = SlackApiError(
            message="channel_not_found", 
            response={"error": "channel_not_found"}
        )

        # Test with invalid channel ID (should raise ToolError)
        with pytest.raises(ToolError) as exc_info:
            fetch_tool.call(channel_id="invalid", limit=10)

        error = exc_info.value
        assert error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
        assert error.category == ErrorCategory.PERMISSION_ERROR

    @pytest.mark.asyncio
    async def test_configuration_reload_integration(
        self, registry_with_config, tmp_path
    ):
        """Test hot configuration reload with registry updates."""
        registry, config_manager, slack_client, openai_client = registry_with_config

        initial_tools = registry.list_tools()
        initial_count = len(initial_tools)

        # Update configuration to disable a tool
        config_path = tmp_path / "test_tools.yaml"
        new_config = """
slack_tools:
  enabled: true
  bot_token: "test-token"
  tools:
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

        # Manually reinitialize the registry with new configuration
        # Re-register factory functions for the new config
        from meowth.ai.tools.slack_tools import create_slack_tools
        from meowth.ai.tools.openai_tools import create_openai_tools
        
        registry.register_factory("slack_tools", lambda config, deps, global_config: create_slack_tools(slack_client, config))
        registry.register_factory("openai_tools", lambda config, deps, global_config: create_openai_tools(openai_client, config))
        
        # Reinitialize tools with new config
        config_manager.initialize()
        registry.initialize_tools()
        
        # Registry should have fewer tools now
        updated_tools = registry.list_tools()
        tool_names = [tool.metadata.name for tool in updated_tools]

        # Only summarize_messages should be available since fetch_messages is disabled
        assert "fetch_messages" not in tool_names
        assert "summarize_messages" in tool_names
        assert len(updated_tools) < initial_count

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, registry_with_config):
        """Test concurrent execution of multiple tools."""
        registry, config_manager, slack_client, openai_client = registry_with_config

        fetch_tool = registry.get_tool("fetch_messages")

        # Mock API calls for concurrent test
        slack_client.reset_mock()
        slack_client.conversations_history.return_value = {
            "messages": [
                {"text": "Test message", "user": "U123", "ts": "1234567890.123456"}
            ]
        }

        # Execute tools sequentially (since LlamaIndex tools aren't async)
        results = []
        try:
            result1 = fetch_tool.call(channel_id="C1234567890", limit=5)
            results.append(result1)
            result2 = fetch_tool.call(channel_id="C0987654321", limit=3)
            results.append(result2)
        except Exception as e:
            results.append(e)

        # Both should succeed (or both should have same mock data)
        assert len(results) == 2
        for result in results:
            assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_tool_metadata_consistency(self, registry_with_config):
        """Test tool metadata is consistent across registry operations."""
        registry, config_manager, slack_client, openai_client = registry_with_config

        tools = registry.list_tools()

        for tool in tools:
            # Get tool by name and verify it's the same instance
            retrieved_tool = registry.get_tool(tool.metadata.name)
            assert retrieved_tool is tool

            # Verify metadata completeness
            assert tool.metadata.name
            assert tool.metadata.description
            assert tool.metadata.get_parameters_dict()

    @pytest.mark.asyncio
    async def test_registry_cleanup(self, registry_with_config):
        """Test proper cleanup of registry resources."""
        registry, config_manager, slack_client, openai_client = registry_with_config

        # Verify tools are available
        tools = registry.list_tools()
        assert len(tools) > 0

        # Cleanup registry
        registry.cleanup()

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
  tools:
    fetch_messages:
      enabled: true

openai_tools:
  enabled: true
  # Missing required api_key
"""
        config_path.write_text(invalid_config)

        config_manager = ConfigurationManager(str(config_path))
        config_manager.initialize()

        registry = ToolRegistry(str(config_path))

        # Should handle invalid config gracefully
        tools = registry.initialize_tools()

        # Should have no tools due to missing credentials
        tools = registry.list_tools()
        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, registry_with_config):
        """Test rate limiting behavior in integrated environment."""
        registry, config_manager, slack_client, openai_client = registry_with_config

        fetch_tool = registry.get_tool("fetch_messages")
        assert fetch_tool is not None

        # Configure mock to simulate success
        slack_client.conversations_history.return_value = {
            "messages": [{"text": "Test message", "user": "U123", "ts": "1234567890.123456"}]
        }

        # Make multiple rapid requests to test rate limiting
        results = []
        for i in range(5):
            try:
                result = fetch_tool.call(channel_id=f"C123456789{i}", limit=1)
                results.append(result)
            except Exception as e:
                results.append(e)

        # Should handle rate limiting gracefully
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
