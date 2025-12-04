"""Contract tests for AI agent tools.

This module defines and tests the contracts that all tools must
implement, ensuring consistency across different tool types.
"""

import pytest

from meowth.ai.tools.base import BaseToolInterface
from meowth.ai.tools.exceptions import ToolError


class ToolContractTester:
    """Base contract tester for all tools."""

    @staticmethod
    async def test_tool_interface_compliance(tool: BaseToolInterface):
        """Test that a tool properly implements the BaseToolInterface."""
        # Tool should have required metadata
        assert hasattr(tool, "metadata")
        assert hasattr(tool.metadata, "name")
        assert hasattr(tool.metadata, "description")
        assert hasattr(tool.metadata, "get_parameters_dict")

        # Metadata should be properly typed
        assert isinstance(tool.metadata.name, str)
        assert isinstance(tool.metadata.description, str)
        assert isinstance(tool.metadata.get_parameters_dict(), dict)

        # Tool should have call method
        assert hasattr(tool, "call")
        assert callable(tool.call)

    @staticmethod
    async def test_tool_metadata_contract(tool: BaseToolInterface):
        """Test tool metadata follows expected contract."""
        metadata = tool.metadata

        # Name should be non-empty and follow naming convention
        assert metadata.name
        assert metadata.name.replace("_", "").isalnum()

        # Description should be meaningful
        assert metadata.description
        assert len(metadata.description) > 10

        # Parameters should include type information
        parameters_schema = metadata.get_parameters_dict()
        
        # Handle JSON schema format (with properties) or direct parameter dict
        if "properties" in parameters_schema:
            parameters = parameters_schema["properties"]
        else:
            parameters = parameters_schema
            
        for param_name, param_info in parameters.items():
            assert isinstance(param_name, str)
            assert isinstance(param_info, dict)
            assert "type" in param_info or "description" in param_info
            assert "type" in param_info or "description" in param_info

    @staticmethod
    async def test_tool_error_handling_contract(tool: BaseToolInterface):
        """Test tool error handling follows expected contract."""
        # Tools should handle invalid parameters gracefully
        with pytest.raises(ToolError):
            # This should raise ToolError for any tool
            await tool.call(invalid_parameter_that_should_not_exist="test")


class TestSlackToolsContract:
    """Contract tests specifically for Slack tools."""

    @pytest.fixture
    def mock_slack_tool(self):
        """Create a mock Slack tool for contract testing."""
        from meowth.ai.tools.slack_tools import create_slack_tools
        from unittest.mock import Mock

        mock_client = Mock()
        config = {
            "enabled": True,
            "bot_token": "test-token",
            "fetch_messages": {
                "enabled": True,
                "description": "Fetch messages from Slack channels",
            },
        }

        tools = create_slack_tools(mock_client, config)
        return tools[0] if tools else None

    @pytest.mark.asyncio
    async def test_slack_tool_interface_compliance(self, mock_slack_tool):
        """Test Slack tools implement the tool interface contract."""
        if mock_slack_tool:
            await ToolContractTester.test_tool_interface_compliance(mock_slack_tool)

    @pytest.mark.asyncio
    async def test_slack_tool_metadata_contract(self, mock_slack_tool):
        """Test Slack tools metadata follows contract."""
        if mock_slack_tool:
            await ToolContractTester.test_tool_metadata_contract(mock_slack_tool)

    @pytest.mark.asyncio
    async def test_slack_tool_parameters_contract(self, mock_slack_tool):
        """Test Slack tool parameters follow expected contract."""
        if mock_slack_tool:
            metadata = mock_slack_tool.metadata

            # fetch_messages should have expected parameters
            if metadata.name == "fetch_messages":
                params_schema = metadata.get_parameters_dict()
                # Handle JSON schema format
                if "properties" in params_schema:
                    params = params_schema["properties"]
                else:
                    params = params_schema
                    
                assert "channel_id" in params
                assert "count" in params

                # Should include type/description information
                for param in ["channel_id", "count"]:
                    param_info = params[param]
                    assert "type" in param_info or "description" in param_info


class TestOpenAIToolsContract:
    """Contract tests specifically for OpenAI tools."""

    @pytest.fixture
    def mock_openai_tool(self):
        """Create a mock OpenAI tool for contract testing."""
        from meowth.ai.tools.openai_tools import create_openai_tools
        from unittest.mock import Mock

        mock_client = Mock()
        config = {
            "enabled": True,
            "model_config": {
                "default_model": "gpt-4",
                "max_tokens": 1500,
                "temperature": 0.7,
            },
            "tools": {
                "summarize_messages": {
                    "enabled": True,
                    "description": "Generate conversation summaries",
                }
            },
        }

        tools = create_openai_tools(mock_client, config)
        return tools[0] if tools else None

    @pytest.mark.asyncio
    async def test_openai_tool_interface_compliance(self, mock_openai_tool):
        """Test OpenAI tools implement the tool interface contract."""
        if mock_openai_tool:
            await ToolContractTester.test_tool_interface_compliance(mock_openai_tool)

    @pytest.mark.asyncio
    async def test_openai_tool_metadata_contract(self, mock_openai_tool):
        """Test OpenAI tools metadata follows contract."""
        if mock_openai_tool:
            await ToolContractTester.test_tool_metadata_contract(mock_openai_tool)

    @pytest.mark.asyncio
    async def test_openai_tool_parameters_contract(self, mock_openai_tool):
        """Test OpenAI tool parameters follow expected contract."""
        if mock_openai_tool:
            metadata = mock_openai_tool.metadata

            # summarize_messages should have expected parameters
            if metadata.name == "summarize_messages":
                params_schema = metadata.get_parameters_dict()
                # Handle JSON schema format
                if "properties" in params_schema:
                    params = params_schema["properties"]
                else:
                    params = params_schema
                    
                assert "messages_json" in params

                # style parameter should be optional
                if "style" in params:
                    style_info = params["style"]
                    assert "default" in style_info or "type" in style_info


class TestToolRegistryContract:
    """Contract tests for the tool registry."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock registry for contract testing."""
        from meowth.ai.tools.registry import ToolRegistry

        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_registry_interface_contract(self, mock_registry):
        """Test registry implements expected interface."""
        # Should have required methods
        assert hasattr(mock_registry, "initialize")
        assert hasattr(mock_registry, "register_tool")
        assert hasattr(mock_registry, "get_tool")
        assert hasattr(mock_registry, "list_tools")
        assert hasattr(mock_registry, "cleanup")

        # Methods should be callable
        assert callable(mock_registry.initialize)
        assert callable(mock_registry.register_tool)
        assert callable(mock_registry.get_tool)
        assert callable(mock_registry.list_tools)
        assert callable(mock_registry.cleanup)

    @pytest.mark.asyncio
    async def test_registry_list_tools_contract(self, mock_registry):
        """Test list_tools returns consistent format."""
        tools = mock_registry.list_tools()

        # Should always return a list
        assert isinstance(tools, list)

        # Each tool should implement BaseToolInterface
        for tool in tools:
            await ToolContractTester.test_tool_interface_compliance(tool)

    @pytest.mark.asyncio
    async def test_registry_get_tool_contract(self, mock_registry):
        """Test get_tool follows expected contract."""
        # Should return None for non-existent tools
        non_existent_tool = mock_registry.get_tool("non_existent_tool_name")
        assert non_existent_tool is None

        # Should handle empty/invalid names gracefully
        assert mock_registry.get_tool("") is None
        assert mock_registry.get_tool(None) is None


class TestConfigurationContract:
    """Contract tests for configuration management."""

    @pytest.mark.asyncio
    async def test_configuration_manager_contract(self):
        """Test configuration manager implements expected interface."""
        from meowth.ai.tools.config_manager import ConfigurationManager

        # Should be able to create without errors
        config_manager = ConfigurationManager("/nonexistent/path")

        # Should have required methods
        assert hasattr(config_manager, "initialize")
        assert hasattr(config_manager, "get_config")
        assert hasattr(config_manager, "register_reload_callback")
        assert hasattr(config_manager, "cleanup")

        # Methods should be callable
        assert callable(config_manager.initialize)
        assert callable(config_manager.get_config)
        assert callable(config_manager.register_reload_callback)
        assert callable(config_manager.cleanup)

    def test_configuration_models_contract(self):
        """Test configuration models follow expected contract."""
        from meowth.ai.tools.config import ToolsConfiguration

        # Should be able to create with minimal data
        config = ToolsConfiguration(
            slack_tools={
                "enabled": True,
                "bot_token": "test",
                "fetch_messages": {"enabled": True},
            },
            openai_tools={
                "enabled": True,
                "api_key": "test",
                "model_config": {"default_model": "gpt-4"},
                "tools": {"summarize_messages": {"enabled": True}},
            },
        )

        # Should have expected structure
        assert hasattr(config, "slack_tools")
        assert hasattr(config, "openai_tools")

        # Should validate properly
        assert config.slack_tools.enabled
        assert config.openai_tools.enabled


class TestErrorHandlingContract:
    """Contract tests for error handling."""

    def test_tool_error_contract(self):
        """Test ToolError follows expected contract."""
        from meowth.ai.tools.exceptions import ToolError, ErrorSeverity, ErrorCategory

        # Should be able to create with required fields
        error = ToolError(
            message="Test error",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.CONFIGURATION_ERROR,
        )

        # Should have expected attributes
        assert error.message == "Test error"
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.category == ErrorCategory.CONFIGURATION_ERROR

        # Should be an Exception
        assert isinstance(error, Exception)

    def test_error_categories_contract(self):
        """Test error categories are properly defined."""
        from meowth.ai.tools.exceptions import ErrorCategory, ErrorSeverity

        # Should have expected categories
        expected_categories = [
            ErrorCategory.VALIDATION_ERROR,
            ErrorCategory.CONFIGURATION_ERROR,
            ErrorCategory.EXTERNAL_SERVICE_ERROR,
            ErrorCategory.RATE_LIMIT_ERROR,
            ErrorCategory.AUTHENTICATION_ERROR,
            ErrorCategory.PERMISSION_ERROR,
            ErrorCategory.NETWORK_ERROR,
            ErrorCategory.DATA_ERROR,
            ErrorCategory.TIMEOUT_ERROR,
            ErrorCategory.INTERNAL_ERROR,
        ]

        for category in expected_categories:
            assert isinstance(category, ErrorCategory)

        # Should have expected severities
        expected_severities = [
            ErrorSeverity.LOW,
            ErrorSeverity.MEDIUM,
            ErrorSeverity.HIGH,
            ErrorSeverity.CRITICAL,
            ErrorSeverity.FATAL,
        ]

        for severity in expected_severities:
            assert isinstance(severity, ErrorSeverity)
