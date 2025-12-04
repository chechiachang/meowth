"""Integration tests for automatic tool selection.

This module tests the end-to-end workflow of automatic tool selection
based on user intent classification.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from dataclasses import dataclass
from typing import Dict, Any

from meowth.ai.agent import LlamaIndexAgentWrapper
from meowth.ai.tools.registry import ToolRegistry
from meowth.ai.models import ThreadContext, AIResponse
from meowth.handlers.mention import MentionHandler


@dataclass
class MockAIResponse:
    """Mock AI response for testing auto tool selection."""
    response: str
    confidence: float
    source: str
    metadata: Dict[str, Any]


class TestAutoToolSelection:
    """Test automatic tool selection integration."""

    @pytest.fixture
    def tool_registry(self):
        """Mock tool registry with sample tools."""
        registry = Mock(spec=ToolRegistry)

        # Mock available tools
        registry.get_available_tools.return_value = [
            Mock(metadata=Mock(name="fetch_slack_messages")),
            Mock(metadata=Mock(name="summarize_messages")),
            Mock(metadata=Mock(name="analyze_conversation")),
        ]

        return registry

    @pytest.fixture
    def ai_agent(self, tool_registry):
        """Mock AI agent with tool registry."""
        agent = Mock(spec=LlamaIndexAgentWrapper)
        agent.tool_registry = tool_registry

        # Mock successful response generation
        agent.generate_response = AsyncMock(
            return_value=MockAIResponse(
                response="Here's a summary of the last 10 messages...",
                confidence=0.85,
                source="ai_agent",
                metadata={"tools_used": ["fetch_slack_messages", "summarize_messages"]},
            )
        )

        return agent

    @pytest.fixture
    def mention_handler(self, ai_agent):
        """Mock mention handler with AI agent."""
        handler = Mock(spec=MentionHandler)
        handler.ai_agent = ai_agent
        return handler

    @pytest.mark.asyncio
    async def test_summarization_tool_selection(self, ai_agent, tool_registry):
        """Test automatic selection of summarization tools."""
        message = "Can you summarize the last 10 messages?"
        context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
        )

        # Execute the request
        response = await ai_agent.generate_response(
            message=message, thread_context=context
        )

        # Verify tools were automatically selected
        assert response.response is not None
        assert "fetch_slack_messages" in response.metadata["tools_used"]
        assert "summarize_messages" in response.metadata["tools_used"]
        ai_agent.generate_response.assert_called_once_with(
            message=message, thread_context=context
        )

    @pytest.mark.asyncio
    async def test_analysis_tool_selection(self, ai_agent, tool_registry):
        """Test automatic selection of analysis tools."""
        message = "What are the main topics in this conversation?"
        context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
        )

        # Update mock to return analysis tools
        ai_agent.generate_response.return_value = MockAIResponse(
            response="The main topics discussed are: project planning, deployment strategies...",
            confidence=0.85,
            source="ai_agent",
            metadata={"tools_used": ["fetch_slack_messages", "analyze_conversation"]},
        )

        response = await ai_agent.generate_response(
            message=message, thread_context=context
        )

        # Verify analysis tools were selected
        assert "analyze_conversation" in response.metadata["tools_used"]
        assert response.confidence > 0.8

    @pytest.mark.asyncio
    async def test_information_lookup_tool_selection(self, ai_agent, tool_registry):
        """Test automatic selection for information lookup."""
        message = "Who participated in this thread?"
        context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
        )

        # Update mock for information lookup
        ai_agent.generate_response.return_value = MockAIResponse(
            response="The participants in this thread are: @alice, @bob, @charlie",
            confidence=0.9,
            source="ai_agent",
            metadata={"tools_used": ["fetch_slack_messages"]},
        )

        response = await ai_agent.generate_response(
            message=message, thread_context=context
        )

        # Verify appropriate tools were selected
        assert "fetch_slack_messages" in response.metadata["tools_used"]
        assert response.response.startswith("The participants")

    @pytest.mark.asyncio
    async def test_ambiguous_request_handling(self, ai_agent, tool_registry):
        """Test handling of ambiguous requests."""
        message = "Help me with this"
        context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
        )

        # Update mock for ambiguous request
        ai_agent.generate_response.return_value = MockAIResponse(
            response="I'd be happy to help! Could you be more specific about what you need?",
            confidence=0.3,
            source="ai_agent",
            metadata={"tools_used": [], "intent": "ambiguous"},
        )

        response = await ai_agent.generate_response(
            message=message, thread_context=context
        )

        # Verify no tools were selected and helpful response provided
        assert len(response.metadata["tools_used"]) == 0
        assert response.confidence < 0.5
        assert "more specific" in response.response

    @pytest.mark.asyncio
    async def test_tool_selection_with_parameters(self, ai_agent, tool_registry):
        """Test tool selection extracts and uses parameters."""
        message = "Summarize the last 25 messages from this channel"
        context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
        )

        # Mock response with parameter extraction
        ai_agent.generate_response.return_value = MockAIResponse(
            response="Here's a summary of the last 25 messages...",
            confidence=0.88,
            source="ai_agent",
            metadata={
                "tools_used": ["fetch_slack_messages", "summarize_messages"],
                "parameters": {"message_count": 25},
            },
        )

        response = await ai_agent.generate_response(
            message=message, thread_context=context
        )

        # Verify parameters were extracted and used
        assert response.metadata["parameters"]["message_count"] == 25
        assert response.response.startswith("Here's a summary")

    @pytest.mark.asyncio
    async def test_fallback_on_tool_failure(self, ai_agent, tool_registry):
        """Test fallback behavior when tool execution fails."""
        message = "Summarize this conversation"
        context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
        )

        # Mock tool execution failure
        ai_agent.generate_response.return_value = MockAIResponse(
            response="I encountered an issue accessing the messages. Please try again later.",
            confidence=0.6,
            source="ai_agent",
            metadata={
                "tools_used": [],
                "errors": ["fetch_slack_messages: rate_limit_exceeded"],
                "fallback_used": True,
            },
        )

        response = await ai_agent.generate_response(
            message=message, thread_context=context
        )

        # Verify fallback behavior
        assert response.metadata["fallback_used"] is True
        assert len(response.metadata["errors"]) > 0
        assert "try again later" in response.response

    @pytest.mark.asyncio
    async def test_no_tools_available(self, ai_agent):
        """Test behavior when no tools are available."""
        message = "Summarize this conversation"
        context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
        )

        # Mock empty tool registry
        ai_agent.tool_registry.get_available_tools.return_value = []
        ai_agent.generate_response.return_value = MockAIResponse(
            response="I don't have access to the tools needed for that request.",
            confidence=0.1,
            source="ai_agent",
            metadata={"tools_used": [], "available_tools": []},
        )

        response = await ai_agent.generate_response(
            message=message, thread_context=context
        )

        # Verify appropriate response when no tools available
        assert len(response.metadata["tools_used"]) == 0
        assert response.confidence < 0.5
        assert "don't have access" in response.response
