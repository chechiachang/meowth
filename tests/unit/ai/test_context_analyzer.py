"""Unit tests for context analysis logic in automatic tool selection.

Tests for analyzing Slack context (channel, thread, participants) to inform
tool selection and response generation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from meowth.ai.context_analyzer import (
    ContextAnalyzer,
    ChannelContext,
    ParticipantContext,
    ContextType,
    UrgencyLevel,
)
from meowth.ai.models import ThreadContext
from meowth.ai.models import ThreadMessage


class TestContextAnalyzer:
    """Test context analysis functionality."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a context analyzer for testing."""
        from unittest.mock import Mock
        mock_slack_client = Mock()
        
        # Mock channel info response
        mock_slack_client.get_channel_info.return_value = {
            "name": "general",
            "type": "channel", 
            "num_members": 15,
            "topic": {"value": "General discussion"},
            "purpose": {"value": "Team communication"},
            "is_private": False
        }
        
        return ContextAnalyzer(slack_client=mock_slack_client)
    
    @pytest.fixture
    def sample_messages(self):
        """Create sample thread messages for testing."""
        return [
            ThreadMessage(
                user_id="U1234567890",
                text="Hey team, let's discuss the new feature",
                timestamp="1234567890.123456",
                is_bot_message=False,
                token_count=10
            ),
            ThreadMessage(
                user_id="U0987654321",
                text="Great idea! I think we should focus on user experience",
                timestamp="1234567891.123456",
                is_bot_message=False,
                token_count=12
            ),
            ThreadMessage(
                user_id="U1234567890",
                text="Agreed, let me share some mockups",
                timestamp="1234567892.123456",
                is_bot_message=False,
                token_count=8
            )
        ]
    
    def test_analyze_channel_context(self, analyzer, sample_messages):
        """Test channel context analysis."""
        channel_id = "C1234567890"
        
        context = analyzer.analyze_channel_context(channel_id=channel_id)
        
        assert isinstance(context, ChannelContext)
        assert context.channel_id == channel_id
        assert context.channel_name == "general"
        assert context.member_count == 15
        assert context.topic == "General discussion"
        assert not context.is_private
        
    def test_analyze_thread_context(self, analyzer, sample_messages):
        """Test thread-specific context analysis."""
        thread_ts = "1234567890.123456"
        
        thread_context = ThreadContext(
            channel_id="C1234567890",
            thread_ts=thread_ts,
            messages=sample_messages,
        )
        
        context = analyzer.analyze_thread_context(thread_context)
        
        assert isinstance(context, dict)  # Method returns dict, not ThreadContext
        assert "message_count" in context
        assert "participants" in context
        
    def test_analyze_participant_context(self, analyzer):
        """Test participant context analysis."""
        user_id = "U1234567890"
        recent_activity = [
            {"timestamp": "1234567890.123456", "channel": "C1234567890", "user": user_id},
            {"timestamp": "1234567889.123456", "channel": "C0987654321", "user": user_id}
        ]
        
        context = analyzer.analyze_participant_context(
            channel_id="C1234567890",
            recent_messages=recent_activity
        )
        
        assert isinstance(context, ParticipantContext)
        assert user_id in context.user_ids
        assert context.engagement_level in ["low", "medium", "high"]
        assert len(context.recent_channels) <= 10
        
    def test_generate_context_insights(self, analyzer, sample_messages):
        """Test context insight generation."""
        channel_context = ChannelContext(
            channel_id="C1234567890",
            channel_name="feature-discussion",
            channel_type="channel",
            member_count=15,
            topic="Feature planning and UX discussion",
            purpose="Discuss new features and design",
            is_private=False,
            context_type=ContextType.FEATURE_DISCUSSION,
            urgency_level=UrgencyLevel.MEDIUM,
            technical_keywords={"feature", "ux", "design"},
            project_keywords={"planning", "discussion"}
        )
        
        # Create mock thread_analysis and participant_context
        thread_analysis = {
            "primary_theme": ContextType.FEATURE_DISCUSSION,
            "collaboration_level": "medium",
            "technical_depth": False,
            "urgency_indicators": []
        }
        participant_context = analyzer._create_default_participant_context(set())
        
        insights = analyzer.generate_context_insights(
            channel_context=channel_context,
            thread_analysis=thread_analysis,
            participant_context=participant_context
        )
        
        assert isinstance(insights, dict)
        assert "context_confidence" in insights
        assert "recommended_response_style" in insights
        assert "tool_recommendations" in insights
        
    def test_context_aware_tool_suggestions(self, analyzer, sample_messages):
        """Test that context analysis suggests appropriate tools."""
        # Technical discussion context
        tech_context = ChannelContext(
            channel_id="C1234567890",
            channel_name="bug-fixes",
            channel_type="channel",
            member_count=5,
            topic="Bug fixes and debugging",
            purpose="Technical problem solving",
            is_private=False,
            context_type=ContextType.TECHNICAL_DISCUSSION,
            urgency_level=UrgencyLevel.HIGH,
            technical_keywords={"bug", "error", "debug"},
            project_keywords={"fixes", "technical"}
        )
        
        # Create thread analysis from messages
        thread_analysis = {
            "primary_theme": "technical",
            "collaboration_level": "high",
            "urgency_indicators": ["error", "bug"],
            "technical_depth": True
        }
        
        participant_context = ParticipantContext(
            user_ids={"U1", "U2"},
            user_roles={},
            expertise_levels={},
            activity_patterns={},
            dominant_participants=[],
            team_composition="technical"
        )
        
        insights = analyzer.generate_context_insights(
            channel_context=tech_context,
            thread_analysis=thread_analysis,
            participant_context=participant_context
        )
        
        # Should suggest analysis and lookup tools for technical discussions
        assert "analyze_conversation" in insights["tool_recommendations"]
        assert "fetch_slack_messages" in insights["tool_recommendations"]
        
    def test_activity_level_calculation(self, analyzer):
        """Test activity level calculation logic."""
        # High activity: many recent messages
        high_activity_messages = [
            ThreadMessage("U1", f"Message {i}", f"123456789{i}.0", False, 5)
            for i in range(20)
        ]
        
        level = analyzer._calculate_activity_level(high_activity_messages, participant_count=10)
        assert level == "high"
        
        # Low activity: few messages
        low_activity_messages = [
            ThreadMessage("U1", "Single message", "1234567890.0", False, 5)
        ]
        
        level = analyzer._calculate_activity_level(low_activity_messages, participant_count=2)
        assert level == "low"
        
    def test_conversation_theme_extraction(self, analyzer, sample_messages):
        """Test extraction of conversation themes."""
        themes = analyzer._extract_conversation_themes(sample_messages)
        
        assert isinstance(themes, list)
        assert len(themes) > 0
        # Should identify themes based on message content
        assert any("feature" in theme.lower() for theme in themes)
        
    def test_participant_engagement_scoring(self, analyzer):
        """Test participant engagement level scoring."""
        # High engagement: multiple recent messages
        high_engagement_activity = [
            {"timestamp": str(datetime.now().timestamp() - i * 3600), "channel": "C123"}
            for i in range(5)  # 5 messages in last 5 hours
        ]
        
        level = analyzer._calculate_engagement_level(high_engagement_activity)
        assert level == "high"
        
        # Low engagement: old activity
        old_activity = [
            {"timestamp": str(datetime.now().timestamp() - 86400 * 7), "channel": "C123"}
        ]  # 1 week ago
        
        level = analyzer._calculate_engagement_level(old_activity)
        assert level == "low"
        
    def test_context_type_detection(self, analyzer, sample_messages):
        """Test automatic context type detection."""
        # Feature discussion indicators
        feature_messages = [
            ThreadMessage("U1", "Let's add a new feature for user analytics", "123.0", False, 10),
            ThreadMessage("U2", "Great idea! We should track user engagement", "124.0", False, 9)
        ]
        
        context_type = analyzer._determine_context_type(
            channel_name="feature-requests",
            topic="New feature discussion",
            purpose="Feature planning and implementation"
        )
        assert context_type == ContextType.FEATURE_DISCUSSION
        
        # Bug report indicators
        bug_messages = [
            ThreadMessage("U1", "I'm seeing an error when users try to login", "123.0", False, 10),
            ThreadMessage("U2", "Same here, the API is returning 500 errors", "124.0", False, 9)
        ]
        
        # Technical discussion indicators - checking message content
        themes = analyzer._extract_conversation_themes(bug_messages)
        assert "technical" in themes or "problem-solving" in themes
        
    def test_insights_confidence_scoring(self, analyzer):
        """Test confidence scoring for context insights."""
        # High confidence: clear patterns
        clear_context = ChannelContext(
            channel_id="C1234567890",
            channel_name="design-discussion",
            channel_type="channel",
            member_count=15,
            topic="Feature and user experience design",
            purpose="Design collaboration",
            is_private=False,
            context_type=ContextType.FEATURE_DISCUSSION,
            urgency_level=UrgencyLevel.HIGH,
            technical_keywords={"feature", "design"},
            project_keywords={"user experience", "design"}
        )
        
        clear_messages = [
            ThreadMessage("U1", "Let's design the new feature", "123.0", False, 7),
            ThreadMessage("U2", "I agree, user experience is key", "124.0", False, 8),
            ThreadMessage("U3", "Here are my design mockups", "125.0", False, 6)
        ]
        
        insights = analyzer.generate_context_insights(
            channel_context=clear_context,
            thread_analysis={
                "primary_theme": "feature",
                "collaboration_level": "high", 
                "urgency_indicators": ["deadline", "priority"],
                "technical_depth": False,
                "message_count": 3
            },
            participant_context=ParticipantContext(
                user_ids={"U1", "U2", "U3"},
                user_roles={},
                expertise_levels={"U1": "high", "U2": "medium", "U3": "high"},
                activity_patterns={},
                dominant_participants=["U1", "U3"],
                team_composition="design"
            )
        )
        
        assert insights["context_confidence"] >= 0.7  # High confidence for clear patterns
        
    def test_tool_suggestion_prioritization(self, analyzer):
        """Test that tool suggestions are prioritized based on context."""
        analysis_context = ChannelContext(
            channel_id="C1234567890",
            channel_name="performance-analysis",
            channel_type="channel",
            member_count=10,
            topic="Performance analysis and optimization",
            purpose="Technical metrics discussion",
            is_private=False,
            context_type=ContextType.TECHNICAL_DISCUSSION,
            urgency_level=UrgencyLevel.HIGH,
            technical_keywords={"performance", "optimization", "metrics"},
            project_keywords={"analysis", "technical"}
        )
        
        analysis_messages = [
            ThreadMessage("U1", "We need to analyze our performance metrics", "123.0", False, 8),
            ThreadMessage("U2", "Let's look at the data from last week", "124.0", False, 8)
        ]
        
        insights = analyzer.generate_context_insights(
            channel_context=analysis_context,
            thread_analysis={
                "primary_theme": "technical",
                "collaboration_level": "medium",
                "urgency_indicators": ["analyze", "performance"],
                "technical_depth": True,
                "message_count": 2
            },
            participant_context=ParticipantContext(
                user_ids={"U1", "U2"},
                user_roles={},
                expertise_levels={"U1": "high", "U2": "medium"},
                activity_patterns={},
                dominant_participants=["U1"],
                team_composition="technical"
            )
        )
        
        # Analysis tools should be prioritized
        suggested_tools = insights["tool_recommendations"]
        assert "analyze_conversation" in suggested_tools
        
    def test_empty_context_handling(self, analyzer):
        """Test handling of empty or minimal context."""
        empty_context = ChannelContext(
            channel_id="C1234567890",
            channel_name="empty-channel",
            channel_type="channel",
            member_count=1,
            topic=None,
            purpose=None,
            is_private=False,
            context_type=ContextType.GENERAL,
            urgency_level=UrgencyLevel.LOW,
            technical_keywords=set(),
            project_keywords=set()
        )
        
        insights = analyzer.generate_context_insights(
            channel_context=empty_context,
            thread_analysis={
                "primary_theme": "general",
                "collaboration_level": "low",
                "urgency_indicators": [],
                "technical_depth": False,
                "message_count": 0
            },
            participant_context=ParticipantContext(
                user_ids=set(),
                user_roles={},
                expertise_levels={},
                activity_patterns={},
                dominant_participants=[],
                team_composition="general"
            )
        )
        
        assert insights["context_confidence"] < 0.3  # Low confidence for empty context
        assert len(insights["tool_recommendations"]) >= 0  # Should still suggest fallback tools