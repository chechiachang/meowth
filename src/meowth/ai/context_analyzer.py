"""Context analyzer for Slack conversations.

Analyzes channel context, thread context, and participant context
to enable context-aware AI tool selection and response formatting.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import re
import logging

from meowth.client import SlackClient
from meowth.ai.models import ThreadContext


logger = logging.getLogger(__name__)


class ContextType(Enum):
    """Types of conversation context."""
    TECHNICAL_DISCUSSION = "technical_discussion"
    FEATURE_DISCUSSION = "feature_discussion" 
    PROJECT_COORDINATION = "project_coordination"
    INCIDENT_RESPONSE = "incident_response"
    STATUS_UPDATE = "status_update"
    GENERAL = "general"


class UrgencyLevel(Enum):
    """Urgency levels for context analysis."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ChannelContext:
    """Context information about a Slack channel."""
    channel_id: str
    channel_name: str
    channel_type: str  # channel, group, im
    member_count: int
    topic: Optional[str]
    purpose: Optional[str] 
    is_private: bool
    context_type: ContextType
    urgency_level: UrgencyLevel
    technical_keywords: Set[str]
    project_keywords: Set[str]
    
    def has_technical_focus(self) -> bool:
        """Check if channel has technical focus."""
        return (
            self.context_type == ContextType.TECHNICAL_DISCUSSION or
            len(self.technical_keywords) >= 3 or
            any(keyword in (self.topic or "").lower() for keyword in ["api", "code", "dev", "tech"])
        )


@dataclass
class ParticipantContext:
    """Context information about conversation participants."""
    user_ids: Set[str]
    user_roles: Dict[str, str]  # user_id -> role
    expertise_levels: Dict[str, str]  # user_id -> expertise level  
    activity_patterns: Dict[str, Dict[str, int]]  # user_id -> activity metrics
    dominant_participants: List[str]  # Most active participants
    team_composition: str  # mixed, technical, product, etc.
    engagement_level: str = "medium"  # low, medium, high
    recent_channels: List[str] = field(default_factory=list)  # channels with recent activity
    
    def get_primary_expertise(self) -> str:
        """Get the dominant expertise level in the conversation."""
        if not self.expertise_levels:
            return "mixed"
        
        expertise_counts = {}
        for level in self.expertise_levels.values():
            expertise_counts[level] = expertise_counts.get(level, 0) + 1
            
        return max(expertise_counts.items(), key=lambda x: x[1])[0]


class ContextAnalyzer:
    """Analyzes Slack conversation context for AI tool selection and response formatting."""
    
    def __init__(self, slack_client: SlackClient):
        """Initialize context analyzer.
        
        Args:
            slack_client: Slack client for API interactions
        """
        self.slack_client = slack_client
        
        # Technical keywords for context detection
        self.technical_keywords = {
            "api", "database", "query", "performance", "error", "bug", "fix",
            "deploy", "deployment", "code", "function", "class", "method",
            "server", "endpoint", "response", "request", "latency", "memory",
            "cpu", "cache", "optimization", "algorithm", "architecture",
            "framework", "library", "dependency", "version", "build"
        }
        
        # Project coordination keywords
        self.project_keywords = {
            "deadline", "milestone", "sprint", "epic", "story", "task",
            "meeting", "standup", "retrospective", "planning", "estimate",
            "scope", "requirement", "deliverable", "timeline", "schedule",
            "priority", "backlog", "roadmap", "release", "launch"
        }
        
        # Incident response keywords
        self.incident_keywords = {
            "down", "outage", "critical", "urgent", "emergency", "incident",
            "alert", "monitoring", "failure", "broken", "issue", "problem",
            "investigate", "escalate", "hotfix", "rollback", "restore"
        }
        
    def analyze_channel_context(self, channel_id: str) -> ChannelContext:
        """Analyze channel context for contextual understanding.
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            ChannelContext with analyzed information
        """
        try:
            # Get channel info from Slack API
            channel_info = self.slack_client.get_channel_info(channel_id)
            if not channel_info:
                logger.warning(f"Could not fetch channel info for {channel_id}")
                return self._create_default_channel_context(channel_id)
            
            # Extract basic channel information
            channel_name = channel_info.get("name", "")
            channel_type = channel_info.get("type", "channel")
            member_count = channel_info.get("num_members", 0)
            topic = channel_info.get("topic", {}).get("value", "")
            purpose = channel_info.get("purpose", {}).get("value", "")
            is_private = channel_info.get("is_private", False)
            
            # Analyze context from channel metadata
            context_type = self._determine_context_type(channel_name, topic, purpose)
            urgency_level = self._determine_urgency_level(channel_name, topic, purpose)
            
            # Extract relevant keywords
            text_content = f"{channel_name} {topic} {purpose}".lower()
            technical_keywords = self._extract_keywords(text_content, self.technical_keywords)
            project_keywords = self._extract_keywords(text_content, self.project_keywords)
            
            return ChannelContext(
                channel_id=channel_id,
                channel_name=channel_name,
                channel_type=channel_type,
                member_count=member_count,
                topic=topic,
                purpose=purpose,
                is_private=is_private,
                context_type=context_type,
                urgency_level=urgency_level,
                technical_keywords=technical_keywords,
                project_keywords=project_keywords
            )
            
        except Exception as e:
            logger.error(f"Error analyzing channel context for {channel_id}: {e}")
            return self._create_default_channel_context(channel_id)
    
    def analyze_thread_context(
        self, 
        thread_context: ThreadContext,
        lookback_hours: int = 2
    ) -> Dict[str, any]:
        """Analyze conversation thread context.
        
        Args:
            thread_context: Thread context with messages
            lookback_hours: Hours of recent activity to analyze
            
        Returns:
            Dictionary with thread analysis results
        """
        if not thread_context.messages:
            return self._create_default_thread_analysis()
        
        # Filter recent messages
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        recent_messages = [
            msg for msg in thread_context.messages 
            if datetime.fromtimestamp(float(msg.timestamp)) > cutoff_time
        ]
        
        # Analyze message content
        all_text = " ".join([msg.text for msg in recent_messages])
        
        # Determine conversation themes
        technical_score = self._calculate_keyword_score(all_text.lower(), self.technical_keywords)
        project_score = self._calculate_keyword_score(all_text.lower(), self.project_keywords) 
        incident_score = self._calculate_keyword_score(all_text.lower(), self.incident_keywords)
        
        # Determine primary theme
        scores = {
            ContextType.TECHNICAL_DISCUSSION: technical_score,
            ContextType.PROJECT_COORDINATION: project_score,
            ContextType.INCIDENT_RESPONSE: incident_score
        }
        primary_theme = max(scores.items(), key=lambda x: x[1])[0]
        
        # Analyze message patterns
        message_frequency = len(recent_messages) / max(lookback_hours, 1)
        avg_message_length = sum(len(msg.text) for msg in recent_messages) / max(len(recent_messages), 1)
        
        # Extract key topics
        key_topics = self._extract_key_topics(all_text)
        
        # Analyze participants
        participant_context = self.analyze_participant_context("", recent_messages)
        
        return {
            "message_count": len(recent_messages),
            "time_span_hours": lookback_hours,
            "primary_theme": primary_theme,
            "theme_scores": scores,
            "message_frequency": message_frequency,
            "avg_message_length": avg_message_length,
            "key_topics": key_topics,
            "urgency_indicators": self._find_urgency_indicators(all_text),
            "technical_depth": technical_score > 0.3,
            "collaboration_level": "high" if message_frequency > 5 else "medium" if message_frequency > 2 else "low",
            "participants": participant_context
        }
    
    def analyze_participant_context(
        self, 
        channel_id: str,
        recent_messages: List[Dict],
        days_lookback: int = 7
    ) -> ParticipantContext:
        """Analyze participant context in the conversation.
        
        Args:
            channel_id: Channel ID for participant lookup
            recent_messages: Recent messages for analysis
            days_lookback: Days of activity history to analyze
            
        Returns:
            ParticipantContext with participant analysis
        """
        try:
            # Extract unique participants
            user_ids = set()
            message_counts = {}
            
            for msg in recent_messages:
                # Handle both dict and ThreadMessage objects
                if hasattr(msg, 'user_id'):
                    user_id = msg.user_id
                else:
                    user_id = msg.get("user", "")
                if user_id:
                    user_ids.add(user_id)
                    message_counts[user_id] = message_counts.get(user_id, 0) + 1
            
            # Get user information
            user_roles = {}
            expertise_levels = {}
            activity_patterns = {}
            
            for user_id in user_ids:
                try:
                    user_info = self.slack_client.get_user_info(user_id)
                    if user_info:
                        # Infer role from profile
                        role = self._infer_user_role(user_info)
                        user_roles[user_id] = role
                        
                        # Infer expertise level  
                        expertise = self._infer_expertise_level(user_info, role)
                        expertise_levels[user_id] = expertise
                        
                        # Calculate activity patterns
                        activity_patterns[user_id] = {
                            "message_count": message_counts.get(user_id, 0),
                            "avg_message_length": self._calculate_avg_message_length(user_id, recent_messages),
                            "participation_ratio": message_counts.get(user_id, 0) / max(len(recent_messages), 1)
                        }
                except Exception as e:
                    logger.warning(f"Could not analyze user {user_id}: {e}")
                    user_roles[user_id] = "member"
                    expertise_levels[user_id] = "mixed"
                    activity_patterns[user_id] = {"message_count": message_counts.get(user_id, 0)}
            
            # Determine dominant participants (top 3 by message count)
            dominant_participants = sorted(
                message_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:3]
            dominant_participants = [user_id for user_id, _ in dominant_participants]
            
            # Determine team composition
            team_composition = self._analyze_team_composition(user_roles)
            
            # Calculate engagement level
            total_messages = sum(message_counts.values())
            engagement_level = "high" if total_messages > 20 else "medium" if total_messages > 5 else "low"
            
            # Extract recent channels from the messages
            recent_channels = []
            for msg in recent_messages:
                if hasattr(msg, 'channel_id'):
                    channel = msg.channel_id
                else:
                    channel = msg.get("channel", "")
                if channel and channel not in recent_channels:
                    recent_channels.append(channel)
            recent_channels = recent_channels[:10]  # Limit to 10
            
            return ParticipantContext(
                user_ids=user_ids,
                user_roles=user_roles,
                expertise_levels=expertise_levels,
                activity_patterns=activity_patterns,
                dominant_participants=dominant_participants,
                team_composition=team_composition,
                engagement_level=engagement_level,
                recent_channels=recent_channels
            )
            
        except Exception as e:
            logger.error(f"Error analyzing participant context: {e}")
            return self._create_default_participant_context(user_ids)
    
    def generate_context_insights(
        self,
        channel_context: ChannelContext,
        thread_analysis: Dict[str, any],
        participant_context: ParticipantContext
    ) -> Dict[str, any]:
        """Generate comprehensive context insights for AI decision making.
        
        Args:
            channel_context: Analyzed channel context
            thread_analysis: Thread analysis results
            participant_context: Participant context analysis
            
        Returns:
            Dictionary with comprehensive context insights
        """
        # Combine context signals
        context_confidence = self._calculate_context_confidence(
            channel_context, thread_analysis, participant_context
        )
        
        # Determine optimal response style
        response_style = self._determine_response_style(
            channel_context, thread_analysis, participant_context
        )
        
        # Assess information needs
        information_needs = self._assess_information_needs(
            channel_context, thread_analysis, participant_context
        )
        
        # Generate tool recommendations
        tool_recommendations = self._generate_tool_recommendations(
            channel_context, thread_analysis, participant_context
        )
        
        return {
            "context_confidence": context_confidence,
            "recommended_response_style": response_style,
            "information_needs": information_needs,
            "tool_recommendations": tool_recommendations,
            "urgency_assessment": {
                "level": thread_analysis.get("urgency_indicators", []),
                "requires_immediate_response": len(thread_analysis.get("urgency_indicators", [])) > 2
            },
            "audience_analysis": {
                "primary_expertise": participant_context.get_primary_expertise(),
                "team_composition": participant_context.team_composition,
                "technical_focus": channel_context.has_technical_focus()
            },
            "conversation_state": {
                "primary_theme": thread_analysis.get("primary_theme"),
                "collaboration_level": thread_analysis.get("collaboration_level", "medium"),
                "technical_depth": thread_analysis.get("technical_depth", False)
            }
        }
    
    # Helper methods
    
    def _create_default_channel_context(self, channel_id: str) -> ChannelContext:
        """Create default channel context when analysis fails."""
        return ChannelContext(
            channel_id=channel_id,
            channel_name="",
            channel_type="channel",
            member_count=0,
            topic=None,
            purpose=None,
            is_private=False,
            context_type=ContextType.GENERAL,
            urgency_level=UrgencyLevel.LOW,
            technical_keywords=set(),
            project_keywords=set()
        )
    
    def _create_default_thread_analysis(self) -> Dict[str, any]:
        """Create default thread analysis when no messages available."""
        return {
            "message_count": 0,
            "time_span_hours": 0,
            "primary_theme": ContextType.GENERAL,
            "theme_scores": {},
            "message_frequency": 0,
            "avg_message_length": 0,
            "key_topics": [],
            "urgency_indicators": [],
            "technical_depth": False,
            "collaboration_level": "low"
        }
    
    def _create_default_participant_context(self, user_ids: Set[str]) -> ParticipantContext:
        """Create default participant context when analysis fails."""
        return ParticipantContext(
            user_ids=user_ids,
            user_roles={user_id: "member" for user_id in user_ids},
            expertise_levels={user_id: "mixed" for user_id in user_ids},
            activity_patterns={},
            dominant_participants=list(user_ids)[:3],
            team_composition="mixed",
            engagement_level="medium",
            recent_channels=[]
        )
    
    def _determine_context_type(self, channel_name: str, topic: str, purpose: str) -> ContextType:
        """Determine context type from channel metadata."""
        text = f"{channel_name} {topic} {purpose}".lower()
        
        if any(keyword in text for keyword in ["incident", "outage", "emergency", "critical"]):
            return ContextType.INCIDENT_RESPONSE
        elif any(keyword in text for keyword in ["dev", "tech", "api", "code", "engineering"]):
            return ContextType.TECHNICAL_DISCUSSION  
        elif any(keyword in text for keyword in ["feature", "product", "design", "ux"]):
            return ContextType.FEATURE_DISCUSSION
        elif any(keyword in text for keyword in ["project", "sprint", "planning", "coordination"]):
            return ContextType.PROJECT_COORDINATION
        elif any(keyword in text for keyword in ["status", "update", "standup", "report"]):
            return ContextType.STATUS_UPDATE
        else:
            return ContextType.GENERAL
    
    def _determine_urgency_level(self, channel_name: str, topic: str, purpose: str) -> UrgencyLevel:
        """Determine urgency level from channel metadata."""
        text = f"{channel_name} {topic} {purpose}".lower()
        
        if any(keyword in text for keyword in ["urgent", "critical", "emergency", "incident"]):
            return UrgencyLevel.HIGH
        elif any(keyword in text for keyword in ["important", "priority", "deadline"]):
            return UrgencyLevel.MEDIUM
        else:
            return UrgencyLevel.LOW
    
    def _extract_keywords(self, text: str, keyword_set: Set[str]) -> Set[str]:
        """Extract matching keywords from text."""
        return {keyword for keyword in keyword_set if keyword in text}
    
    def _calculate_keyword_score(self, text: str, keywords: Set[str]) -> float:
        """Calculate keyword relevance score."""
        if not text or not keywords:
            return 0.0
        
        word_count = len(text.split())
        keyword_matches = sum(1 for keyword in keywords if keyword in text)
        
        return keyword_matches / max(word_count / 10, 1)  # Normalize by text length
    
    def _extract_key_topics(self, text: str) -> List[str]:
        """Extract key topics from conversation text."""
        # Simple topic extraction using keyword frequency
        words = re.findall(r'\b\w{4,}\b', text.lower())  # Words with 4+ characters
        word_freq = {}
        
        for word in words:
            if word not in ["that", "this", "have", "will", "been", "from", "they"]:  # Basic stopwords
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Return top 5 topics
        return sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
    
    def _find_urgency_indicators(self, text: str) -> List[str]:
        """Find urgency indicators in conversation text."""
        urgency_patterns = [
            r'\b(urgent|critical|emergency|asap|immediately)\b',
            r'\b(broken|down|failed|not working)\b', 
            r'\b(help|stuck|blocked|issue|problem)\b'
        ]
        
        indicators = []
        for pattern in urgency_patterns:
            matches = re.findall(pattern, text.lower())
            indicators.extend(matches)
        
        return list(set(indicators))  # Remove duplicates
    
    def _infer_user_role(self, user_info: Dict) -> str:
        """Infer user role from Slack profile."""
        profile = user_info.get("profile", {})
        title = (profile.get("title", "") or "").lower()
        
        if any(keyword in title for keyword in ["engineer", "developer", "dev", "technical", "architect"]):
            return "engineer"
        elif any(keyword in title for keyword in ["product", "manager", "pm", "owner"]):
            return "product"
        elif any(keyword in title for keyword in ["design", "ux", "ui"]):
            return "design"  
        elif any(keyword in title for keyword in ["lead", "senior", "principal", "staff"]):
            return "senior"
        else:
            return "member"
    
    def _infer_expertise_level(self, user_info: Dict, role: str) -> str:
        """Infer expertise level from user info and role."""
        if role in ["senior", "architect", "principal"]:
            return "high"
        elif role in ["engineer", "product", "design"]:
            return "medium"  
        else:
            return "mixed"
    
    def _calculate_avg_message_length(self, user_id: str, messages: List[Dict]) -> float:
        """Calculate average message length for a user."""
        user_messages = [msg for msg in messages if msg.get("user") == user_id]
        if not user_messages:
            return 0.0
        
        total_length = sum(len(msg.get("text", "")) for msg in user_messages)
        return total_length / len(user_messages)
    
    def _analyze_team_composition(self, user_roles: Dict[str, str]) -> str:
        """Analyze team composition from user roles."""
        if not user_roles:
            return "mixed"
        
        role_counts = {}
        for role in user_roles.values():
            role_counts[role] = role_counts.get(role, 0) + 1
        
        total_users = len(user_roles)
        
        # Determine if team has dominant composition
        for role, count in role_counts.items():
            if count / total_users >= 0.6:  # 60% threshold
                return f"{role}_focused"
        
        return "mixed"
    
    def _calculate_context_confidence(
        self,
        channel_context: ChannelContext,
        thread_analysis: Dict[str, any],
        participant_context: ParticipantContext
    ) -> float:
        """Calculate confidence in context analysis."""
        confidence_factors = []
        
        # Channel context confidence
        if channel_context.topic or channel_context.purpose:
            confidence_factors.append(0.3)
        
        # Additional channel confidence for well-defined contexts
        if channel_context.context_type != ContextType.GENERAL:
            confidence_factors.append(0.2)
        
        # Thread analysis confidence  
        if thread_analysis.get("message_count", 0) >= 5:
            confidence_factors.append(0.4)
        elif thread_analysis.get("message_count", 0) >= 2:
            confidence_factors.append(0.2)
        
        # Participant context confidence
        if len(participant_context.user_ids) >= 2:
            confidence_factors.append(0.3)
        
        return min(1.0, sum(confidence_factors))  # Cap at 1.0
    
    def _determine_response_style(
        self,
        channel_context: ChannelContext,
        thread_analysis: Dict[str, any], 
        participant_context: ParticipantContext
    ) -> str:
        """Determine appropriate response style."""
        if channel_context.context_type == ContextType.INCIDENT_RESPONSE:
            return "urgent_brief"
        elif channel_context.has_technical_focus() and participant_context.get_primary_expertise() == "high":
            return "technical_detailed"
        elif thread_analysis.get("collaboration_level") == "high":
            return "collaborative"
        else:
            return "balanced"
    
    def _assess_information_needs(
        self,
        channel_context: ChannelContext,
        thread_analysis: Dict[str, any],
        participant_context: ParticipantContext
    ) -> List[str]:
        """Assess what information might be needed."""
        needs = []
        
        if channel_context.context_type == ContextType.TECHNICAL_DISCUSSION:
            needs.extend(["technical_details", "performance_metrics"])
        
        if thread_analysis.get("primary_theme") == ContextType.PROJECT_COORDINATION:
            needs.extend(["timeline_info", "progress_status"])
        
        if channel_context.urgency_level == UrgencyLevel.HIGH:
            needs.append("immediate_status")
        
        return needs
    
    def _generate_tool_recommendations(
        self,
        channel_context: ChannelContext,
        thread_analysis: Dict[str, any],
        participant_context: ParticipantContext
    ) -> List[str]:
        """Generate tool recommendations based on context."""
        recommendations = []
        
        # Based on context type
        if channel_context.context_type == ContextType.TECHNICAL_DISCUSSION:
            recommendations.extend(["analyze_conversation", "fetch_slack_messages", "fetch_code_examples"])
        elif channel_context.context_type == ContextType.PROJECT_COORDINATION:
            recommendations.extend(["summarize_messages", "extract_action_items"])
        elif channel_context.context_type == ContextType.INCIDENT_RESPONSE:
            recommendations.extend(["fetch_recent_alerts", "summarize_status"])
        
        # Based on thread activity
        if thread_analysis.get("message_count", 0) > 20:
            recommendations.append("summarize_messages")
        
        # Based on participant needs
        if participant_context.get_primary_expertise() == "low":
            recommendations.append("explain_concepts")
        
        return list(set(recommendations))  # Remove duplicates
    
    def _calculate_activity_level(self, messages: List, participant_count: int) -> str:
        """Calculate activity level based on message count and participants."""
        message_count = len(messages)
        
        if participant_count == 0:
            return "low"
            
        messages_per_participant = message_count / participant_count
        
        if messages_per_participant >= 5 or message_count >= 20:
            return "high"
        elif messages_per_participant >= 2 or message_count >= 5:
            return "medium"
        else:
            return "low"
    
    def _extract_conversation_themes(self, messages: List) -> List[str]:
        """Extract conversation themes from messages."""
        themes = []
        all_text = " ".join(getattr(msg, 'text', '') for msg in messages if hasattr(msg, 'text'))
        
        # Technical themes
        if any(keyword in all_text.lower() for keyword in self.technical_keywords):
            themes.append("technical")
        
        # Feature themes  
        if any(keyword in all_text.lower() for keyword in ["feature", "new feature", "functionality"]):
            themes.append("feature")
        
        # Project themes  
        if any(keyword in all_text.lower() for keyword in ["project", "roadmap", "milestone", "deadline"]):
            themes.append("project")
        
        # Problem-solving themes
        if any(keyword in all_text.lower() for keyword in ["issue", "problem", "solution", "fix"]):
            themes.append("problem-solving")
            
        return themes if themes else ["general"]
    
    def _calculate_engagement_level(self, activity_data) -> str:
        """Calculate engagement level from activity data."""
        if isinstance(activity_data, list):
            total_activity = len(activity_data)
        elif isinstance(activity_data, dict):
            total_activity = sum(activity_data.values())
        else:
            total_activity = 0
        
        if total_activity >= 5:
            return "high"
        elif total_activity >= 2:
            return "medium"
        else:
            return "low"