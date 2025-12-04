"""Integration tests for context-aware tool usage and response generation.

Tests the end-to-end flow of analyzing context, selecting appropriate tools,
and generating context-tailored responses.
"""

import warnings
# Suppress all deprecation warnings for clean test output
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from meowth.ai.models import ThreadContext, ThreadMessage
from meowth.ai.context_analyzer import ContextAnalyzer, ChannelContext, ContextType, UrgencyLevel
from meowth.ai.auto_selection import AutoToolSelector
from meowth.ai.tools.registry import ToolRegistry
from meowth.handlers.mention import MentionHandler
from meowth.models import MentionEvent


class TestContextAwarenessIntegration:
    """Test context-aware responses end-to-end."""
    
    @pytest.fixture
    def mock_tool_registry(self):
        """Create a mock tool registry with context-aware tools."""
        registry = Mock(spec=ToolRegistry)
        registry.get_available_tools.return_value = [
            "fetch_slack_messages",
            "summarize_messages", 
            "analyze_conversation",
            "get_participant_info"
        ]
        
        # Mock tools
        fetch_tool = Mock()
        fetch_tool.metadata.name = "fetch_slack_messages"
        fetch_tool.metadata.description = "Fetch recent messages from Slack"
        
        summarize_tool = Mock()
        summarize_tool.metadata.name = "summarize_messages"
        summarize_tool.metadata.description = "Summarize conversation content"
        
        analyze_tool = Mock()
        analyze_tool.metadata.name = "analyze_conversation"
        analyze_tool.metadata.description = "Analyze conversation for insights"
        
        participant_tool = Mock()
        participant_tool.metadata.name = "get_participant_info"
        participant_tool.metadata.description = "Get participant information"
        
        # Mock initialize_tools to return a list of mock tools
        registry.initialize_tools.return_value = [fetch_tool, summarize_tool, analyze_tool, participant_tool]
        
        registry.get_tool.side_effect = lambda name: {
            "fetch_slack_messages": fetch_tool,
            "summarize_messages": summarize_tool,
            "analyze_conversation": analyze_tool,
            "get_participant_info": participant_tool
        }.get(name)
        
        return registry
    
    @pytest.fixture
    def context_analyzer(self):
        """Create a context analyzer for testing."""
        from unittest.mock import Mock
        mock_slack_client = Mock()
        return ContextAnalyzer(slack_client=mock_slack_client)
    
    @pytest.fixture
    def auto_selector(self, mock_tool_registry):
        """Create an auto tool selector with context awareness."""
        return AutoToolSelector(mock_tool_registry)
    
    @pytest.fixture
    def mention_handler(self, mock_tool_registry):
        """Create a mention handler with context-aware tools."""
        return MentionHandler(mock_tool_registry)
    
    @pytest.fixture
    def technical_context_messages(self):
        """Create messages representing a technical discussion."""
        return [
            ThreadMessage(
                user_id="U1234567890",
                text="I'm seeing errors in the API when processing requests",
                timestamp="1234567890.123456",
                is_bot_message=False,
                token_count=10
            ),
            ThreadMessage(
                user_id="U0987654321", 
                text="Same issue here. The response time has increased significantly",
                timestamp="1234567891.123456",
                is_bot_message=False,
                token_count=12
            ),
            ThreadMessage(
                user_id="U1111111111",
                text="Let me check the logs and see what's causing this",
                timestamp="1234567892.123456",
                is_bot_message=False,
                token_count=11
            )
        ]
    
    @pytest.fixture
    def feature_context_messages(self):
        """Create messages representing a feature discussion."""
        return [
            ThreadMessage(
                user_id="U1234567890",
                text="We should add a new dashboard for user analytics",
                timestamp="1234567890.123456", 
                is_bot_message=False,
                token_count=9
            ),
            ThreadMessage(
                user_id="U0987654321",
                text="Great idea! Users have been requesting better insights",
                timestamp="1234567891.123456",
                is_bot_message=False,
                token_count=9
            ),
            ThreadMessage(
                user_id="U2222222222",
                text="I can work on the UI mockups if we decide to move forward",
                timestamp="1234567892.123456",
                is_bot_message=False,
                token_count=12
            )
        ]
    
    @pytest.mark.asyncio
    async def test_technical_context_tool_selection(
        self, auto_selector, context_analyzer, technical_context_messages
    ):
        """Test that technical context triggers appropriate tool selection."""
        thread_context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
            user_id="U1234567890",
            messages=technical_context_messages,
            token_count=33
        )
        
        # Simulate technical discussion context
        with patch.object(context_analyzer, 'analyze_channel_context') as mock_analyze:
            mock_analyze.return_value = ChannelContext(
                channel_id="C1234567890",
                channel_name="engineering-alerts",
                channel_type="channel",
                member_count=8,
                topic="API issues and performance monitoring",
                purpose="Discussion of technical issues",
                is_private=False,
                context_type=ContextType.TECHNICAL_DISCUSSION,
                urgency_level=UrgencyLevel.HIGH,
                technical_keywords={"api", "error", "performance", "logs"},
                project_keywords={"monitoring", "alerts"}
            )
            
            with patch.object(context_analyzer, 'generate_context_insights') as mock_insights:
                mock_insights.return_value.context_type = ContextType.TECHNICAL_DISCUSSION
                mock_insights.return_value.suggested_tools = [
                    "analyze_conversation", "fetch_slack_messages"
                ]
                
                # Request analysis of the technical issue
                execution_context = await auto_selector.select_and_execute_tools(
                    message="Can you analyze what's causing these API errors?",
                    thread_context=thread_context
                )
                
                # Should prioritize analysis tools for technical context
                assert "analyze_conversation" in execution_context.tools_executed
                assert execution_context.user_intent.primary_intent in [
                    "analysis", "information_lookup"
                ]
    
    @pytest.mark.asyncio
    async def test_feature_context_tool_selection(
        self, auto_selector, context_analyzer, feature_context_messages
    ):
        """Test that feature discussion context triggers appropriate tools."""
        thread_context = ThreadContext(
            channel_id="C0987654321",
            thread_ts="1234567890.123456", 
            user_id="U0987654321",
            messages=feature_context_messages,
            token_count=30
        )
        
        with patch.object(context_analyzer, 'analyze_channel_context') as mock_analyze:
            mock_analyze.return_value = ChannelContext(
                channel_id="C0987654321",
                channel_name="feature-discussion",
                channel_type="channel",
                member_count=5,
                topic="New feature development",
                purpose="Discuss new features",
                is_private=False,
                context_type=ContextType.FEATURE_DISCUSSION,
                urgency_level=UrgencyLevel.MEDIUM,
                technical_keywords=set(),
                project_keywords={"dashboard", "analytics", "user", "feature"}
            )
            
            with patch.object(context_analyzer, 'generate_context_insights') as mock_insights:
                mock_insights.return_value.context_type = ContextType.FEATURE_DISCUSSION
                mock_insights.return_value.suggested_tools = [
                    "summarize_messages", "fetch_slack_messages"
                ]
                
                # Request summary of the feature discussion
                execution_context = await auto_selector.select_and_execute_tools(
                    message="Summarize our discussion about the new feature",
                    thread_context=thread_context
                )
                
                # Should prioritize summarization for feature discussions
                assert "summarize_messages" in execution_context.tools_executed
                assert execution_context.user_intent.primary_intent == "summarization"
    
    @pytest.mark.asyncio
    async def test_context_aware_response_formatting(
        self, mention_handler, context_analyzer, technical_context_messages
    ):
        """Test that responses are formatted based on context."""
        mention_event = MentionEvent(
            event_id="test_event_001",
            event_type="app_mention",
            channel_id="C1234567890", 
            user_id="U9999999999",
            text="<@UBOT123456> What are the main issues being discussed?",
            timestamp="1234567893.123456",
            thread_ts="1234567890.123456"
        )
        
        with patch.object(context_analyzer, 'analyze_channel_context') as mock_analyze:
            mock_analyze.return_value = ChannelContext(
                channel_id="C1234567890",
                channel_name="technical-issues",
                channel_type="channel",
                member_count=8,
                topic="API errors and performance",
                purpose="Technical issue resolution",
                is_private=False,
                context_type=ContextType.TECHNICAL_DISCUSSION,
                urgency_level=UrgencyLevel.HIGH,
                technical_keywords={"api", "error", "performance"},
                project_keywords=set()
            )
            
            with patch.object(mention_handler.auto_tool_selector, 'select_and_execute_tools') as mock_select:
                # Mock successful tool execution with technical context
                mock_context = Mock()
                mock_context.has_successful_results.return_value = True
                mock_context.get_successful_results.return_value = {
                    "analyze_conversation": Mock(
                        tool_name="analyze_conversation",
                        success=True,
                        data={
                            "summary": "Technical discussion about API performance issues",
                            "key_points": ["API errors", "Response time issues", "Log analysis needed"],
                            "participants": ["U1234567890", "U0987654321", "U1111111111"]
                        }
                    )
                }
                mock_context.user_intent.primary_intent = "analysis"
                mock_select.return_value = mock_context
                
                response = await mention_handler.create_response_message(mention_event)
                
                # Response should be technical and include key technical insights
                assert "API" in response.text or "error" in response.text
                assert "performance" in response.text or "technical" in response.text
    
    @pytest.mark.asyncio
    async def test_low_context_fallback_behavior(
        self, auto_selector, context_analyzer
    ):
        """Test behavior when context is minimal or unclear."""
        # Minimal context with generic message
        thread_context = ThreadContext(
            channel_id="C5555555555",
            thread_ts="1234567890.123456",
            user_id="U5555555555",
            messages=[],  # No context messages
            token_count=0
        )
        
        with patch.object(context_analyzer, 'analyze_channel_context') as mock_analyze:
            mock_analyze.return_value = ChannelContext(
                channel_id="C5555555555",
                channel_name="general",
                channel_type="channel",
                member_count=2,
                topic="General discussion",
                purpose="General conversation",
                is_private=False,
                context_type=ContextType.GENERAL,
                urgency_level=UrgencyLevel.LOW,
                technical_keywords=set(),
                project_keywords=set()
            )
            
            with patch.object(context_analyzer, 'generate_context_insights') as mock_insights:
                mock_insights.return_value.context_type = ContextType.GENERAL
                mock_insights.return_value.confidence = 0.2  # Low confidence
                mock_insights.return_value.suggested_tools = ["fetch_slack_messages"]
                
                execution_context = await auto_selector.select_and_execute_tools(
                    message="Help",  # Vague request
                    thread_context=thread_context
                )
                
                # Should fall back to basic tools and ask for clarification
                assert execution_context.user_intent.primary_intent in [
                    "help", "ambiguous", "greeting"
                ]
    
    @pytest.mark.asyncio
    async def test_multi_context_tool_coordination(
        self, auto_selector, context_analyzer, technical_context_messages, feature_context_messages
    ):
        """Test tool coordination when context suggests multiple approaches."""
        # Mixed context: both technical and feature elements
        mixed_messages = technical_context_messages + feature_context_messages
        
        thread_context = ThreadContext(
            channel_id="C7777777777",
            thread_ts="1234567890.123456",
            user_id="U7777777777",
            messages=mixed_messages,
            token_count=63
        )
        
        with patch.object(context_analyzer, 'analyze_channel_context') as mock_analyze:
            mock_analyze.return_value = ChannelContext(
                channel_id="C7777777777",
                channel_name="dev-discussion",
                channel_type="channel", 
                member_count=12,
                topic="Development and feature discussion",
                purpose="Mixed technical and feature discussions",
                is_private=False,
                context_type=ContextType.TECHNICAL_DISCUSSION,
                urgency_level=UrgencyLevel.HIGH,
                technical_keywords={"api", "error", "performance"},
                project_keywords={"dashboard", "feature", "analytics"}
            )
            
            with patch.object(context_analyzer, 'generate_context_insights') as mock_insights:
                mock_insights.return_value.context_type = ContextType.TECHNICAL_DISCUSSION
                mock_insights.return_value.suggested_tools = [
                    "analyze_conversation", "summarize_messages", "fetch_slack_messages"
                ]
                
                execution_context = await auto_selector.select_and_execute_tools(
                    message="Can you summarize both the technical issues and feature ideas?",
                    thread_context=thread_context
                )
                
                # Should execute multiple complementary tools
                assert len(execution_context.tools_executed) >= 2
                assert any("summarize" in tool or "analyze" in tool 
                          for tool in execution_context.tools_executed)
    
    @pytest.mark.asyncio
    async def test_participant_context_influence(
        self, auto_selector, context_analyzer, technical_context_messages
    ):
        """Test that participant context influences tool selection."""
        thread_context = ThreadContext(
            channel_id="C8888888888",
            thread_ts="1234567890.123456", 
            user_id="U8888888888",
            messages=technical_context_messages,
            token_count=33
        )
        
        with patch.object(context_analyzer, 'analyze_channel_context') as mock_analyze:
            # High-expertise technical team context
            mock_analyze.return_value = ChannelContext(
                channel_id="C8888888888",
                channel_name="dev-team",
                channel_type="channel",
                member_count=4,
                topic="API architecture and debugging",
                purpose="Technical team discussions",
                is_private=False,
                context_type=ContextType.TECHNICAL_DISCUSSION,
                urgency_level=UrgencyLevel.HIGH,
                technical_keywords={"api", "architecture", "debugging", "performance"},
                project_keywords=set()
            )
            
            with patch.object(context_analyzer, 'analyze_participant_context') as mock_participant:
                mock_participant.return_value.engagement_level = "high"
                mock_participant.return_value.expertise_indicators = ["technical", "engineering"]
                
                with patch.object(context_analyzer, 'generate_context_insights') as mock_insights:
                    mock_insights.return_value.context_type = ContextType.TECHNICAL_DISCUSSION
                    mock_insights.return_value.confidence = 0.9  # High confidence
                    mock_insights.return_value.suggested_tools = [
                        "analyze_conversation", "get_participant_info"
                    ]
                    
                    execution_context = await auto_selector.select_and_execute_tools(
                        message="Analyze the technical discussion patterns",
                        thread_context=thread_context
                    )
                    
                    # Should use advanced analysis tools for expert context
                    assert execution_context.user_intent.confidence > 0.6
                    assert "analyze_conversation" in execution_context.tools_executed
    
    @pytest.mark.asyncio
    async def test_temporal_context_considerations(
        self, auto_selector, context_analyzer
    ):
        """Test that time-based context affects tool selection."""
        # Recent urgent messages
        urgent_messages = [
            ThreadMessage(
                user_id="U1234567890",
                text="URGENT: Production is down, users can't access the app",
                timestamp=str(datetime.now().timestamp()),
                is_bot_message=False,
                token_count=10
            )
        ]
        
        thread_context = ThreadContext(
            channel_id="C9999999999",
            thread_ts=str(datetime.now().timestamp()),
            user_id="U1234567890",
            messages=urgent_messages,
            token_count=10
        )
        
        with patch.object(context_analyzer, 'analyze_channel_context') as mock_analyze:
            mock_analyze.return_value = ChannelContext(
                channel_id="C9999999999",
                channel_name="incident-response",
                channel_type="channel",
                member_count=20,
                topic="Production incident response",
                purpose="Critical incident handling",
                is_private=False,
                context_type=ContextType.INCIDENT_RESPONSE,
                urgency_level=UrgencyLevel.HIGH,
                technical_keywords={"urgent", "production", "down", "critical"},
                project_keywords=set()
            )
            
            with patch.object(context_analyzer, 'generate_context_insights') as mock_insights:
                mock_insights.return_value.context_type = ContextType.INCIDENT_RESPONSE
                mock_insights.return_value.urgency_level = "high"
                mock_insights.return_value.suggested_tools = [
                    "fetch_slack_messages", "analyze_conversation"
                ]
                
                execution_context = await auto_selector.select_and_execute_tools(
                    message="What's the current status of this incident?",
                    thread_context=thread_context
                )
                
                # Should prioritize rapid information gathering
                assert "fetch_slack_messages" in execution_context.tools_executed
                assert execution_context.user_intent.confidence > 0.7