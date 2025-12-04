"""Unit tests for channel-specific response formatting.

Tests for formatting responses appropriately based on channel context,
participant expertise, and conversation type.
"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from meowth.ai.response_formatter import (
    ResponseFormatter,
    ChannelResponseContext,
    FormattingStyle,
    ResponseTemplate,
    AudienceType,
)
from meowth.ai.execution import ToolExecutionContext, ToolResult
from meowth.ai.intent import UserIntent
from meowth.ai.models import ThreadContext
from meowth.ai.context_analyzer import ChannelContext, ContextType


class TestResponseFormatter:
    """Test response formatting for different contexts."""
    
    @pytest.fixture
    def formatter(self):
        """Create a response formatter for testing."""
        return ResponseFormatter()
    
    @pytest.fixture
    def technical_execution_context(self):
        """Create execution context for technical discussion."""
        intent = UserIntent(
            primary_intent="analysis",
            confidence=0.8,
            tool_suggestions=["analyze_conversation"],
            parameters={"focus": "technical"}
        )
        
        thread_context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
            user_id="U1234567890",
            messages=[],
            token_count=0
        )
        
        context = ToolExecutionContext(
            user_intent=intent,
            thread_context=thread_context,
            execution_id="exec_001"
        )
        
        # Add successful analysis result
        analysis_result = ToolResult(
            tool_name="analyze_conversation",
            success=True,
            data={
                "summary": "Technical discussion about API performance optimization",
                "key_points": [
                    "Database queries are causing bottlenecks",
                    "Caching layer needs implementation", 
                    "API response time averaging 2.3 seconds"
                ],
                "technical_details": {
                    "performance_metrics": {"avg_response_time": 2.3, "error_rate": 0.05},
                    "affected_endpoints": ["/api/users", "/api/data"]
                }
            }
        )
        context.add_tool_result(analysis_result)
        
        return context
    
    @pytest.fixture
    def feature_execution_context(self):
        """Create execution context for feature discussion."""
        intent = UserIntent(
            primary_intent="summarization",
            confidence=0.9,
            tool_suggestions=["summarize_messages"],
            parameters={"style": "brief"}
        )
        
        thread_context = ThreadContext(
            channel_id="C0987654321",
            thread_ts="1234567890.123456", 
            user_id="U0987654321",
            messages=[],
            token_count=0
        )
        
        context = ToolExecutionContext(
            user_intent=intent,
            thread_context=thread_context,
            execution_id="exec_002"
        )
        
        # Add successful summary result
        summary_result = ToolResult(
            tool_name="summarize_messages",
            success=True,
            data={
                "summary": "Team discussed implementing user analytics dashboard with real-time metrics",
                "key_decisions": [
                    "Use React for frontend components",
                    "Implement WebSocket for real-time updates",
                    "Target launch date: end of quarter"
                ],
                "action_items": [
                    "Create UI mockups (assigned to Design team)",
                    "Set up analytics infrastructure (assigned to Backend team)",
                    "Plan user testing sessions (assigned to Product team)"
                ]
            }
        )
        context.add_tool_result(summary_result)
        
        return context
    
    @pytest.fixture
    def technical_channel_context(self):
        """Create channel context for technical team."""
        return ChannelResponseContext(
            channel_id="C1234567890",
            audience_type=AudienceType.TECHNICAL_TEAM,
            expertise_level="high",
            preferred_style=FormattingStyle.TECHNICAL,
            context_type=ContextType.TECHNICAL_DISCUSSION,
            urgency_level="medium"
        )
    
    @pytest.fixture
    def general_channel_context(self):
        """Create channel context for general audience."""
        return ChannelResponseContext(
            channel_id="C0987654321",
            audience_type=AudienceType.MIXED_TEAM,
            expertise_level="mixed",
            preferred_style=FormattingStyle.CONVERSATIONAL,
            context_type=ContextType.FEATURE_DISCUSSION,
            urgency_level="low"
        )
    
    def test_technical_response_formatting(
        self, formatter, technical_execution_context, technical_channel_context
    ):
        """Test formatting for technical audience."""
        response = formatter.format_response(
            execution_context=technical_execution_context,
            channel_context=technical_channel_context
        )
        
        # Technical format should include detailed metrics
        assert "2.3 seconds" in response.formatted_text
        assert "error_rate" in response.formatted_text or "performance" in response.formatted_text
        assert response.style == FormattingStyle.TECHNICAL
        
        # Should include technical details
        assert "/api/users" in response.formatted_text or "endpoints" in response.formatted_text
        assert "Database" in response.formatted_text or "queries" in response.formatted_text
        
    def test_general_audience_formatting(
        self, formatter, feature_execution_context, general_channel_context
    ):
        """Test formatting for general/mixed audience."""
        response = formatter.format_response(
            execution_context=feature_execution_context,
            channel_context=general_channel_context
        )
        
        # General format should be more conversational
        assert response.style == FormattingStyle.CONVERSATIONAL
        assert len(response.formatted_text) > 0
        
        # Should include key decisions and action items clearly
        assert "React" in response.formatted_text or "frontend" in response.formatted_text
        assert "Design team" in response.formatted_text or "assigned" in response.formatted_text
        
    def test_response_length_adaptation(self, formatter):
        """Test response length adaptation for different contexts."""
        # Long technical context
        long_context = ToolExecutionContext(
            user_intent=UserIntent("analysis", 0.8, [], {}),
            thread_context=ThreadContext(channel_id="C1", thread_ts="123", messages=[], token_count=0),
            execution_id="exec_001"
        )
        
        # Add result with lots of data
        long_result = ToolResult(
            tool_name="analyze_conversation",
            success=True,
            data={
                "summary": "Very detailed technical analysis with extensive metrics and recommendations",
                "details": ["Point 1", "Point 2", "Point 3", "Point 4", "Point 5"] * 10  # Long list
            }
        )
        long_context.add_tool_result(long_result)
        
        # Brief style context
        brief_context = ChannelResponseContext(
            channel_id="C1",
            audience_type=AudienceType.EXECUTIVE_TEAM,
            expertise_level="low",
            preferred_style=FormattingStyle.BRIEF,
            context_type=ContextType.STATUS_UPDATE,
            urgency_level="high"
        )
        
        response = formatter.format_response(long_context, brief_context)
        
        # Should be truncated and summarized for brief style
        assert len(response.formatted_text) < 1000  # Reasonable length limit
        assert response.style == FormattingStyle.BRIEF
        
    def test_urgency_level_formatting(self, formatter):
        """Test formatting adaptation based on urgency."""
        urgent_context = ToolExecutionContext(
            user_intent=UserIntent("information_lookup", 0.9, [], {}),
            thread_context=ThreadContext(channel_id="C1", thread_ts="123", messages=[], token_count=0),
            execution_id="exec_001"
        )
        
        urgent_result = ToolResult(
            tool_name="fetch_slack_messages",
            success=True,
            data={
                "messages": ["System is down", "Users affected", "Investigating"],
                "urgency_indicators": ["down", "critical", "urgent"]
            }
        )
        urgent_context.add_tool_result(urgent_result)
        
        urgent_channel = ChannelResponseContext(
            channel_id="C1",
            audience_type=AudienceType.TECHNICAL_TEAM,
            expertise_level="high",
            preferred_style=FormattingStyle.TECHNICAL,
            context_type=ContextType.INCIDENT_RESPONSE,
            urgency_level="high"
        )
        
        response = formatter.format_response(urgent_context, urgent_channel)
        
        # High urgency should produce concise, actionable format
        assert "🚨" in response.formatted_text or "urgent" in response.formatted_text.lower()
        assert len(response.formatted_text.split('\n')) <= 10  # Concise format
        
    def test_error_handling_in_formatting(self, formatter):
        """Test formatting when tool execution has errors."""
        error_context = ToolExecutionContext(
            user_intent=UserIntent("analysis", 0.7, [], {}),
            thread_context=ThreadContext(channel_id="C1", thread_ts="123", messages=[], token_count=0),
            execution_id="exec_001"
        )
        
        # Add failed result
        error_result = ToolResult(
            tool_name="analyze_conversation",
            success=False,
            error="Rate limit exceeded while fetching messages"
        )
        error_context.add_tool_result(error_result)
        
        channel_context = ChannelResponseContext(
            channel_id="C1",
            audience_type=AudienceType.MIXED_TEAM,
            expertise_level="mixed",
            preferred_style=FormattingStyle.CONVERSATIONAL,
            context_type=ContextType.GENERAL,
            urgency_level="low"
        )
        
        response = formatter.format_response(error_context, channel_context)
        
        # Should format error message appropriately
        assert "rate limit" in response.formatted_text.lower() or "try again" in response.formatted_text.lower()
        assert response.has_errors is True
        
    def test_multi_tool_result_formatting(self, formatter):
        """Test formatting multiple tool results coherently."""
        multi_context = ToolExecutionContext(
            user_intent=UserIntent("summarization", 0.8, [], {}),
            thread_context=ThreadContext(channel_id="C1", thread_ts="123", messages=[], token_count=0),
            execution_id="exec_001"
        )
        
        # Add multiple successful results
        fetch_result = ToolResult(
            tool_name="fetch_slack_messages",
            success=True,
            data={"message_count": 25, "time_range": "last 2 hours"}
        )
        multi_context.add_tool_result(fetch_result)
        
        summary_result = ToolResult(
            tool_name="summarize_messages",
            success=True,
            data={"summary": "Team coordination for project milestone", "key_topics": ["deadlines", "assignments"]}
        )
        multi_context.add_tool_result(summary_result)
        
        channel_context = ChannelResponseContext(
            channel_id="C1",
            audience_type=AudienceType.PROJECT_TEAM,
            expertise_level="mixed", 
            preferred_style=FormattingStyle.STRUCTURED,
            context_type=ContextType.PROJECT_COORDINATION,
            urgency_level="medium"
        )
        
        response = formatter.format_response(multi_context, channel_context)
        
        # Should integrate multiple results coherently
        assert "25" in response.formatted_text  # Message count
        assert "coordination" in response.formatted_text.lower()
        assert response.tool_count == 2
        
    def test_template_selection_logic(self, formatter):
        """Test that appropriate templates are selected for different contexts."""
        # Technical incident
        incident_context = ChannelResponseContext(
            channel_id="C1",
            audience_type=AudienceType.TECHNICAL_TEAM,
            expertise_level="high",
            preferred_style=FormattingStyle.TECHNICAL,
            context_type=ContextType.INCIDENT_RESPONSE,
            urgency_level="high"
        )
        
        template = formatter._select_template(incident_context)
        assert template.template_type == "incident_response"
        assert "priority" in template.sections or "status" in template.sections
        
        # Feature discussion
        feature_context = ChannelResponseContext(
            channel_id="C2", 
            audience_type=AudienceType.PRODUCT_TEAM,
            expertise_level="mixed",
            preferred_style=FormattingStyle.CONVERSATIONAL,
            context_type=ContextType.FEATURE_DISCUSSION,
            urgency_level="low"
        )
        
        template = formatter._select_template(feature_context)
        assert template.template_type == "feature_summary"
        assert "overview" in template.sections or "decisions" in template.sections
        
    def test_formatting_style_consistency(self, formatter):
        """Test that formatting style is applied consistently."""
        test_context = ToolExecutionContext(
            user_intent=UserIntent("analysis", 0.8, [], {}),
            thread_context=ThreadContext(channel_id="C1", thread_ts="123", messages=[], token_count=0),
            execution_id="exec_001"
        )
        
        test_result = ToolResult(
            tool_name="analyze_conversation",
            success=True,
            data={"summary": "Test analysis", "metrics": {"score": 0.85}}
        )
        test_context.add_tool_result(test_result)
        
        # Brief style
        brief_channel = ChannelResponseContext(
            channel_id="C1",
            audience_type=AudienceType.EXECUTIVE_TEAM,
            expertise_level="low",
            preferred_style=FormattingStyle.BRIEF,
            context_type=ContextType.STATUS_UPDATE,
            urgency_level="medium"
        )
        
        brief_response = formatter.format_response(test_context, brief_channel)
        
        # Technical style  
        tech_channel = ChannelResponseContext(
            channel_id="C1",
            audience_type=AudienceType.TECHNICAL_TEAM,
            expertise_level="high",
            preferred_style=FormattingStyle.TECHNICAL,
            context_type=ContextType.TECHNICAL_DISCUSSION,
            urgency_level="medium"
        )
        
        tech_response = formatter.format_response(test_context, tech_channel)
        
        # Brief should be shorter and less detailed
        assert len(brief_response.formatted_text) <= len(tech_response.formatted_text)
        
        # Technical should include metrics
        assert "0.85" in tech_response.formatted_text
        
    def test_special_character_handling(self, formatter):
        """Test handling of special characters and formatting in responses."""
        special_context = ToolExecutionContext(
            user_intent=UserIntent("summarization", 0.8, [], {}),
            thread_context=ThreadContext(channel_id="C1", thread_ts="123", messages=[], token_count=0),
            execution_id="exec_001"
        )
        
        # Result with special characters
        special_result = ToolResult(
            tool_name="summarize_messages",
            success=True,
            data={
                "summary": "Discussion about <script>alert('xss')</script> security & performance",
                "code_snippets": ["SELECT * FROM users WHERE id = 1;", "function test() { return 'hello'; }"]
            }
        )
        special_context.add_tool_result(special_result)
        
        channel_context = ChannelResponseContext(
            channel_id="C1",
            audience_type=AudienceType.TECHNICAL_TEAM,
            expertise_level="high",
            preferred_style=FormattingStyle.TECHNICAL,
            context_type=ContextType.TECHNICAL_DISCUSSION,
            urgency_level="low"
        )
        
        response = formatter.format_response(special_context, channel_context)
        
        # Should escape/handle special characters safely
        assert "<script>" not in response.formatted_text  # XSS prevention
        assert "security" in response.formatted_text
        # Should format code snippets properly
        assert "SELECT" in response.formatted_text or "function" in response.formatted_text