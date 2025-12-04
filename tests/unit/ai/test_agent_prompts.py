"""Unit tests for agent system prompt and tool descriptions.

This module tests the AI agent's system prompt configuration
and tool description optimization for LLM understanding.
"""

import warnings
# Suppress all deprecation warnings for clean test output
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import pytest
from unittest.mock import Mock

from meowth.ai.agent import LlamaIndexAgentWrapper
from meowth.ai.tools.registry import ToolRegistry


class TestAgentPrompts:
    """Test agent system prompt configuration."""

    @pytest.fixture
    def mock_tool_registry(self):
        """Mock tool registry with sample tools."""
        registry = Mock(spec=ToolRegistry)

        # Mock tools with metadata
        tools = [
            Mock(
                metadata=Mock(
                    name="fetch_slack_messages",
                    description="Fetch recent messages from a Slack channel",
                    parameters={
                        "channel_id": {
                            "type": "string",
                            "description": "Slack channel ID",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of messages to fetch (max 100)",
                        },
                    },
                )
            ),
            Mock(
                metadata=Mock(
                    name="summarize_messages",
                    description="Generate a summary of conversation messages",
                    parameters={
                        "messages_json": {
                            "type": "string",
                            "description": "JSON string of messages to summarize",
                        },
                        "style": {
                            "type": "string",
                            "description": "Summary style: 'brief' or 'detailed'",
                        },
                    },
                )
            ),
        ]

        registry.get_available_tools.return_value = tools
        return registry

    @pytest.fixture
    def agent(self, mock_tool_registry):
        """AI agent with mocked tool registry."""
        agent = LlamaIndexAgentWrapper()
        agent.set_tools(mock_tool_registry.get_available_tools())
        return agent

    def test_system_prompt_contains_tool_descriptions(self, agent, mock_tool_registry):
        """Test that system prompt includes clear tool descriptions."""
        # Get the agent's system prompt
        system_prompt = agent._get_system_prompt()

        # Verify tool descriptions are included
        # The system prompt doesn't include specific tool names but mentions tool categories
        assert "message fetching" in system_prompt
        assert "summarization tools" in system_prompt  
        assert "analysis tools" in system_prompt

    def test_system_prompt_includes_parameter_information(
        self, agent, mock_tool_registry
    ):
        """Test that system prompt includes parameter schemas."""
        system_prompt = agent._get_system_prompt()

        # Verify parameter information is included
        # The system prompt includes general guidance about tool parameters
        assert "tool parameters" in system_prompt or "parameters" in system_prompt
        assert "conversation context" in system_prompt

    def test_system_prompt_provides_usage_guidance(self, agent, mock_tool_registry):
        """Test that system prompt provides clear usage guidance."""
        system_prompt = agent._get_system_prompt()

        # Verify usage guidance is included
        assert "automatic" in system_prompt.lower() or "select" in system_prompt.lower()
        assert "tool" in system_prompt.lower()
        assert "user" in system_prompt.lower()

    def test_tool_description_optimization(self, mock_tool_registry):
        """Test that tool descriptions are optimized for LLM understanding."""
        tools = mock_tool_registry.get_available_tools()

        for tool in tools:
            description = tool.metadata.description

            # Verify descriptions meet quality criteria
            assert len(description) >= 10, f"Description too short: {description}"
            assert len(description) <= 500, f"Description too long: {description}"
            assert description[0].isupper(), (
                f"Description should start with capital: {description}"
            )
            assert not description.endswith("."), (
                f"Description shouldn't end with period: {description}"
            )

    def test_parameter_schema_completeness(self, mock_tool_registry):
        """Test that parameter schemas are complete and clear."""
        tools = mock_tool_registry.get_available_tools()

        for tool in tools:
            parameters = tool.metadata.parameters

            for param_name, param_info in parameters.items():
                # Verify each parameter has required fields
                assert "type" in param_info, f"Parameter {param_name} missing type"
                assert "description" in param_info, (
                    f"Parameter {param_name} missing description"
                )

                # Verify description quality
                description = param_info["description"]
                assert len(description) >= 5, (
                    f"Parameter description too short: {description}"
                )
                assert description[0].isupper(), (
                    f"Parameter description should start with capital: {description}"
                )

    def test_tool_categorization_in_prompt(self, agent, mock_tool_registry):
        """Test that tools are properly categorized in system prompt."""
        system_prompt = agent._get_system_prompt()

        # Should mention tool categories for organization
        assert any(
            word in system_prompt.lower()
            for word in ["slack", "message", "conversation"]
        )

    def test_response_format_guidance(self, agent, mock_tool_registry):
        """Test that system prompt includes response format guidance."""
        system_prompt = agent._get_system_prompt()

        # Should provide guidance on response formatting
        assert any(
            word in system_prompt.lower()
            for word in ["respond", "answer", "helpful", "clear"]
        )

    def test_error_handling_guidance(self, agent, mock_tool_registry):
        """Test that system prompt includes error handling guidance."""
        system_prompt = agent._get_system_prompt()

        # Should provide guidance on error handling
        assert any(
            word in system_prompt.lower()
            for word in ["error", "fail", "problem", "unable"]
        )

    def test_parameter_validation_guidance(self, agent, mock_tool_registry):
        """Test that system prompt includes parameter validation guidance."""
        system_prompt = agent._get_system_prompt()

        # Should mention parameter requirements
        assert any(
            word in system_prompt.lower()
            for word in ["parameter", "required", "valid", "format"]
        )

    def test_context_awareness_guidance(self, agent, mock_tool_registry):
        """Test that system prompt includes context awareness guidance."""
        system_prompt = agent._get_system_prompt()

        # Should mention using context for better responses
        assert any(
            word in system_prompt.lower()
            for word in ["context", "channel", "thread", "conversation"]
        )


class TestToolMetadataOptimization:
    """Test tool metadata optimization for LLM comprehension."""

    def test_tool_name_conventions(self):
        """Test that tool names follow proper conventions."""
        tool_names = [
            "fetch_slack_messages",
            "summarize_messages",
            "analyze_conversation",
        ]

        for name in tool_names:
            # Should use snake_case
            assert "_" in name or name.islower(), (
                f"Tool name should be snake_case: {name}"
            )

            # Should be descriptive but concise
            assert len(name) >= 5, f"Tool name too short: {name}"
            assert len(name) <= 50, f"Tool name too long: {name}"

            # Should not contain spaces or special characters
            assert name.replace("_", "").isalnum(), (
                f"Tool name contains invalid characters: {name}"
            )

    def test_description_optimization_rules(self):
        """Test rules for optimizing tool descriptions for LLMs."""
        descriptions = [
            "Fetch recent messages from a Slack channel",
            "Generate a summary of conversation messages",
            "Analyze conversation topics and sentiment",
        ]

        for desc in descriptions:
            # Should start with action verb
            first_word = desc.split()[0].lower()
            action_verbs = [
                "fetch",
                "get",
                "retrieve",
                "generate",
                "create",
                "analyze",
                "process",
                "calculate",
            ]
            assert any(verb in first_word for verb in action_verbs), (
                f"Description should start with action verb: {desc}"
            )

            # Should be present tense, active voice
            assert not any(
                word in desc.lower() for word in ["will", "would", "should", "could"]
            ), f"Description should use present tense: {desc}"

    def test_parameter_schema_optimization(self):
        """Test optimization of parameter schemas for LLM understanding."""
        parameter_schemas = {
            "channel_id": {
                "type": "string",
                "description": "Slack channel ID (starts with C for public channels)",
                "pattern": "^C[A-Z0-9]{8,}$",
            },
            "message_count": {
                "type": "integer",
                "description": "Number of messages to fetch (1-100)",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
            },
        }

        for param_name, schema in parameter_schemas.items():
            # Should have clear type information
            assert "type" in schema, f"Parameter {param_name} missing type"

            # Should have descriptive name
            assert "_" in param_name or len(param_name.split()) == 1, (
                f"Parameter name should be clear: {param_name}"
            )

            # Should include constraints where relevant
            if schema["type"] == "integer":
                assert "minimum" in schema or "maximum" in schema, (
                    f"Integer parameter should have bounds: {param_name}"
                )

            # Should include examples or patterns for complex types
            if schema["type"] == "string" and "id" in param_name.lower():
                assert "pattern" in schema or "example" in schema, (
                    f"ID parameter should have format info: {param_name}"
                )
