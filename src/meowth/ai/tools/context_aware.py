"""Context-aware tool parameter extraction and enhancement.

Enhances AI tools with context-aware parameter extraction,
automatically inferring parameters from conversation context.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Union
import re
import logging

from meowth.ai.context_analyzer import ChannelContext, ParticipantContext, ContextType
from meowth.ai.models import ThreadContext
from meowth.ai.conversation_history import ConversationHistory


logger = logging.getLogger(__name__)


@dataclass
class ContextualParameter:
    """A parameter extracted from conversation context."""
    name: str
    value: Any
    confidence: float  # 0.0 to 1.0
    source: str  # Where parameter was extracted from
    fallback_value: Optional[Any] = None


@dataclass
class ParameterExtractionResult:
    """Result of context-aware parameter extraction."""
    extracted_parameters: Dict[str, ContextualParameter]
    missing_parameters: List[str]
    confidence_score: float
    context_used: List[str]  # Types of context used
    suggestions: List[str]  # Suggestions for missing parameters


class ContextAwareParameterExtractor:
    """Extracts tool parameters from conversation context."""
    
    def __init__(self, conversation_history: ConversationHistory):
        """Initialize parameter extractor.
        
        Args:
            conversation_history: Conversation history manager for context
        """
        self.conversation_history = conversation_history
        
        # Common parameter patterns
        self.time_patterns = {
            "time_range": [
                r"(?:last|past)\s+(\d+)\s+(hour|hours|day|days|week|weeks)",
                r"(?:since|from)\s+(\d+)\s+(hour|hours|day|days)\s+ago",
                r"(?:in the)\s+(last|past)\s+(\d+)\s+(minutes|hours|days)"
            ],
            "specific_time": [
                r"(?:at|around)\s+(\d{1,2}:\d{2})",
                r"(?:yesterday|today|tomorrow)",
                r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)"
            ]
        }
        
        self.quantity_patterns = {
            "count": [
                r"(\d+)\s+(?:messages|items|results|entries)",
                r"(?:top|first|last)\s+(\d+)",
                r"(?:show|get|fetch)\s+(\d+)"
            ],
            "limit": [
                r"(?:limit|max|maximum)\s+(\d+)",
                r"(?:up to|at most)\s+(\d+)",
                r"no more than\s+(\d+)"
            ]
        }
        
        self.user_patterns = {
            "mentions": [
                r"<@([A-Z0-9]+)>",  # Slack user mention format
                r"@([a-zA-Z0-9._-]+)"  # General @ mention
            ],
            "user_references": [
                r"(?:user|person|member)\s+([a-zA-Z0-9._-]+)",
                r"(?:from|by)\s+([a-zA-Z0-9._-]+)"
            ]
        }
    
    def extract_parameters_for_tool(
        self,
        tool_name: str,
        tool_parameters: Dict[str, Any],
        channel_context: ChannelContext,
        thread_context: ThreadContext,
        participant_context: ParticipantContext,
        user_message: str
    ) -> ParameterExtractionResult:
        """Extract parameters for a specific tool using context.
        
        Args:
            tool_name: Name of the tool
            tool_parameters: Tool parameter definitions
            channel_context: Channel context information
            thread_context: Thread context information  
            participant_context: Participant context information
            user_message: User's message requesting the tool
            
        Returns:
            ParameterExtractionResult with extracted parameters
        """
        extracted_parameters = {}
        missing_parameters = []
        context_used = []
        
        # Extract parameters based on tool type
        if tool_name == "fetch_slack_messages":
            result = self._extract_message_fetch_parameters(
                tool_parameters, channel_context, thread_context, user_message
            )
        elif tool_name == "summarize_messages":
            result = self._extract_summarization_parameters(
                tool_parameters, channel_context, thread_context, participant_context, user_message
            )
        elif tool_name == "analyze_conversation":
            result = self._extract_analysis_parameters(
                tool_parameters, channel_context, thread_context, participant_context, user_message
            )
        elif tool_name == "extract_action_items":
            result = self._extract_action_item_parameters(
                tool_parameters, channel_context, thread_context, participant_context, user_message
            )
        else:
            # Generic parameter extraction
            result = self._extract_generic_parameters(
                tool_parameters, channel_context, thread_context, user_message
            )
        
        return result
    
    def enhance_tool_call_with_context(
        self,
        tool_name: str,
        raw_parameters: Dict[str, Any],
        channel_context: ChannelContext,
        thread_context: ThreadContext,
        participant_context: ParticipantContext
    ) -> Dict[str, Any]:
        """Enhance existing tool parameters with contextual information.
        
        Args:
            tool_name: Name of the tool
            raw_parameters: Original tool parameters
            channel_context: Channel context information
            thread_context: Thread context information
            participant_context: Participant context information
            
        Returns:
            Enhanced parameters dictionary
        """
        enhanced_parameters = raw_parameters.copy()
        
        # Add context-specific enhancements
        try:
            # Add channel context
            if "channel_context" not in enhanced_parameters:
                enhanced_parameters["channel_context"] = {
                    "channel_type": channel_context.channel_type,
                    "context_type": channel_context.context_type.value,
                    "technical_focus": channel_context.has_technical_focus(),
                    "urgency_level": channel_context.urgency_level.value
                }
            
            # Add participant context for tools that can use it
            if tool_name in ["summarize_messages", "analyze_conversation"] and "participant_context" not in enhanced_parameters:
                enhanced_parameters["participant_context"] = {
                    "team_composition": participant_context.team_composition,
                    "primary_expertise": participant_context.get_primary_expertise(),
                    "participant_count": len(participant_context.user_ids)
                }
            
            # Add thread context
            if "thread_context" not in enhanced_parameters:
                enhanced_parameters["thread_context"] = {
                    "message_count": len(thread_context.messages),
                    "has_thread": bool(thread_context.thread_ts),
                    "token_estimate": thread_context.token_count
                }
            
            # Tool-specific enhancements
            if tool_name == "fetch_slack_messages":
                enhanced_parameters = self._enhance_message_fetch(enhanced_parameters, channel_context, thread_context)
            elif tool_name == "summarize_messages":
                enhanced_parameters = self._enhance_summarization(enhanced_parameters, channel_context, participant_context)
            elif tool_name == "analyze_conversation":
                enhanced_parameters = self._enhance_analysis(enhanced_parameters, channel_context, participant_context)
            
            logger.debug(f"Enhanced {tool_name} parameters with context")
            
        except Exception as e:
            logger.error(f"Error enhancing tool parameters: {e}")
        
        return enhanced_parameters
    
    # Tool-specific parameter extraction methods
    
    def _extract_message_fetch_parameters(
        self,
        tool_parameters: Dict[str, Any],
        channel_context: ChannelContext,
        thread_context: ThreadContext,
        user_message: str
    ) -> ParameterExtractionResult:
        """Extract parameters for message fetching."""
        extracted = {}
        missing = []
        context_used = ["channel_context", "thread_context", "user_message"]
        
        # Extract time range
        time_range = self._extract_time_range(user_message)
        if time_range:
            extracted["oldest"] = ContextualParameter(
                name="oldest",
                value=time_range["start_timestamp"],
                confidence=time_range["confidence"],
                source="user_message"
            )
            extracted["latest"] = ContextualParameter(
                name="latest", 
                value=time_range["end_timestamp"],
                confidence=time_range["confidence"],
                source="user_message"
            )
        else:
            # Default based on context urgency
            if channel_context.urgency_level.value == "high":
                # Last 2 hours for urgent contexts
                default_hours = 2
            elif channel_context.urgency_level.value == "medium":
                # Last 6 hours for medium urgency
                default_hours = 6
            else:
                # Last 24 hours for low urgency
                default_hours = 24
            
            oldest_timestamp = (datetime.now() - timedelta(hours=default_hours)).timestamp()
            extracted["oldest"] = ContextualParameter(
                name="oldest",
                value=oldest_timestamp,
                confidence=0.6,
                source="context_inference"
            )
        
        # Extract count/limit
        count = self._extract_count(user_message)
        if count:
            extracted["limit"] = ContextualParameter(
                name="limit",
                value=count["value"],
                confidence=count["confidence"],
                source="user_message"
            )
        else:
            # Default based on context type
            if channel_context.context_type == ContextType.INCIDENT_RESPONSE:
                default_limit = 50  # More messages for incidents
            else:
                default_limit = 20  # Standard limit
            
            extracted["limit"] = ContextualParameter(
                name="limit",
                value=default_limit,
                confidence=0.5,
                source="context_inference"
            )
        
        # Channel ID from context
        extracted["channel"] = ContextualParameter(
            name="channel",
            value=channel_context.channel_id,
            confidence=1.0,
            source="channel_context"
        )
        
        return ParameterExtractionResult(
            extracted_parameters=extracted,
            missing_parameters=missing,
            confidence_score=self._calculate_confidence(extracted),
            context_used=context_used,
            suggestions=[]
        )
    
    def _extract_summarization_parameters(
        self,
        tool_parameters: Dict[str, Any],
        channel_context: ChannelContext,
        thread_context: ThreadContext,
        participant_context: ParticipantContext,
        user_message: str
    ) -> ParameterExtractionResult:
        """Extract parameters for message summarization."""
        extracted = {}
        missing = []
        context_used = ["channel_context", "thread_context", "participant_context", "user_message"]
        
        # Extract focus/style
        style = self._extract_summary_style(user_message, channel_context, participant_context)
        extracted["style"] = ContextualParameter(
            name="style",
            value=style["style"],
            confidence=style["confidence"],
            source=style["source"]
        )
        
        # Extract length preference
        length = self._extract_summary_length(user_message, channel_context)
        if length:
            extracted["max_length"] = ContextualParameter(
                name="max_length",
                value=length["value"],
                confidence=length["confidence"], 
                source="user_message"
            )
        
        # Extract focus topics
        focus = self._extract_focus_topics(user_message, channel_context)
        if focus:
            extracted["focus_topics"] = ContextualParameter(
                name="focus_topics",
                value=focus,
                confidence=0.8,
                source="user_message"
            )
        
        # Messages to summarize (from thread context)
        extracted["messages"] = ContextualParameter(
            name="messages",
            value=thread_context.messages,
            confidence=1.0,
            source="thread_context"
        )
        
        return ParameterExtractionResult(
            extracted_parameters=extracted,
            missing_parameters=missing,
            confidence_score=self._calculate_confidence(extracted),
            context_used=context_used,
            suggestions=[]
        )
    
    def _extract_analysis_parameters(
        self,
        tool_parameters: Dict[str, Any],
        channel_context: ChannelContext,
        thread_context: ThreadContext,
        participant_context: ParticipantContext,
        user_message: str
    ) -> ParameterExtractionResult:
        """Extract parameters for conversation analysis."""
        extracted = {}
        missing = []
        context_used = ["channel_context", "thread_context", "participant_context", "user_message"]
        
        # Analysis type based on context and request
        analysis_type = self._determine_analysis_type(user_message, channel_context)
        extracted["analysis_type"] = ContextualParameter(
            name="analysis_type",
            value=analysis_type["type"],
            confidence=analysis_type["confidence"],
            source=analysis_type["source"]
        )
        
        # Include technical details based on audience
        include_technical = participant_context.get_primary_expertise() in ["high", "medium"]
        extracted["include_technical"] = ContextualParameter(
            name="include_technical",
            value=include_technical,
            confidence=0.8,
            source="participant_context"
        )
        
        # Messages to analyze
        extracted["messages"] = ContextualParameter(
            name="messages", 
            value=thread_context.messages,
            confidence=1.0,
            source="thread_context"
        )
        
        return ParameterExtractionResult(
            extracted_parameters=extracted,
            missing_parameters=missing,
            confidence_score=self._calculate_confidence(extracted),
            context_used=context_used,
            suggestions=[]
        )
    
    def _extract_action_item_parameters(
        self,
        tool_parameters: Dict[str, Any],
        channel_context: ChannelContext,
        thread_context: ThreadContext,
        participant_context: ParticipantContext,
        user_message: str
    ) -> ParameterExtractionResult:
        """Extract parameters for action item extraction."""
        extracted = {}
        missing = []
        context_used = ["channel_context", "thread_context", "participant_context"]
        
        # Include assignees based on participant context
        extracted["include_assignees"] = ContextualParameter(
            name="include_assignees",
            value=len(participant_context.user_ids) <= 10,  # Only for smaller groups
            confidence=0.7,
            source="participant_context"
        )
        
        # Priority extraction based on channel urgency
        extract_priority = channel_context.urgency_level.value in ["high", "medium"]
        extracted["extract_priority"] = ContextualParameter(
            name="extract_priority",
            value=extract_priority,
            confidence=0.8,
            source="channel_context"
        )
        
        # Messages to extract from
        extracted["messages"] = ContextualParameter(
            name="messages",
            value=thread_context.messages,
            confidence=1.0,
            source="thread_context"
        )
        
        return ParameterExtractionResult(
            extracted_parameters=extracted,
            missing_parameters=missing,
            confidence_score=self._calculate_confidence(extracted),
            context_used=context_used,
            suggestions=[]
        )
    
    def _extract_generic_parameters(
        self,
        tool_parameters: Dict[str, Any],
        channel_context: ChannelContext,
        thread_context: ThreadContext,
        user_message: str
    ) -> ParameterExtractionResult:
        """Generic parameter extraction for unknown tools."""
        extracted = {}
        missing = []
        context_used = ["user_message"]
        
        # Extract common patterns
        time_range = self._extract_time_range(user_message)
        if time_range:
            extracted["time_range"] = ContextualParameter(
                name="time_range",
                value=time_range,
                confidence=time_range["confidence"],
                source="user_message"
            )
        
        count = self._extract_count(user_message)
        if count:
            extracted["count"] = ContextualParameter(
                name="count",
                value=count["value"],
                confidence=count["confidence"],
                source="user_message"
            )
        
        users = self._extract_user_references(user_message)
        if users:
            extracted["users"] = ContextualParameter(
                name="users",
                value=users,
                confidence=0.7,
                source="user_message"
            )
        
        return ParameterExtractionResult(
            extracted_parameters=extracted,
            missing_parameters=missing,
            confidence_score=self._calculate_confidence(extracted),
            context_used=context_used,
            suggestions=[]
        )
    
    # Enhancement methods for specific tools
    
    def _enhance_message_fetch(
        self,
        parameters: Dict[str, Any],
        channel_context: ChannelContext,
        thread_context: ThreadContext
    ) -> Dict[str, Any]:
        """Enhance message fetch parameters."""
        enhanced = parameters.copy()
        
        # Add inclusive flag for thread messages
        if thread_context.thread_ts and "inclusive" not in enhanced:
            enhanced["inclusive"] = True
        
        # Adjust limit based on context
        if "limit" in enhanced and channel_context.context_type == ContextType.INCIDENT_RESPONSE:
            # Increase limit for incident investigation
            current_limit = enhanced["limit"]
            enhanced["limit"] = min(current_limit * 2, 100)
        
        return enhanced
    
    def _enhance_summarization(
        self,
        parameters: Dict[str, Any],
        channel_context: ChannelContext,
        participant_context: ParticipantContext
    ) -> Dict[str, Any]:
        """Enhance summarization parameters."""
        enhanced = parameters.copy()
        
        # Add audience context
        if "audience" not in enhanced:
            if participant_context.get_primary_expertise() == "high":
                enhanced["audience"] = "technical"
            elif channel_context.context_type == ContextType.FEATURE_DISCUSSION:
                enhanced["audience"] = "product"
            else:
                enhanced["audience"] = "general"
        
        # Add urgency context
        if "urgency" not in enhanced:
            enhanced["urgency"] = channel_context.urgency_level.value
        
        return enhanced
    
    def _enhance_analysis(
        self,
        parameters: Dict[str, Any],
        channel_context: ChannelContext,
        participant_context: ParticipantContext
    ) -> Dict[str, Any]:
        """Enhance analysis parameters."""
        enhanced = parameters.copy()
        
        # Add depth level based on audience
        if "depth" not in enhanced:
            if participant_context.get_primary_expertise() == "high":
                enhanced["depth"] = "detailed"
            else:
                enhanced["depth"] = "summary"
        
        # Add context type for focused analysis
        if "context_focus" not in enhanced:
            enhanced["context_focus"] = channel_context.context_type.value
        
        return enhanced
    
    # Utility methods for pattern extraction
    
    def _extract_time_range(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract time range from text."""
        text_lower = text.lower()
        
        for pattern in self.time_patterns["time_range"]:
            match = re.search(pattern, text_lower)
            if match:
                value = int(match.group(1))
                unit = match.group(2)
                
                # Convert to hours
                if "minute" in unit:
                    hours = value / 60
                elif "day" in unit:
                    hours = value * 24
                elif "week" in unit:
                    hours = value * 24 * 7
                else:  # hours
                    hours = value
                
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=hours)
                
                return {
                    "start_timestamp": start_time.timestamp(),
                    "end_timestamp": end_time.timestamp(),
                    "confidence": 0.9,
                    "original_text": match.group(0)
                }
        
        return None
    
    def _extract_count(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract count/limit from text."""
        text_lower = text.lower()
        
        for pattern in self.quantity_patterns["count"]:
            match = re.search(pattern, text_lower)
            if match:
                return {
                    "value": int(match.group(1)),
                    "confidence": 0.8,
                    "original_text": match.group(0)
                }
        
        for pattern in self.quantity_patterns["limit"]:
            match = re.search(pattern, text_lower)
            if match:
                return {
                    "value": int(match.group(1)),
                    "confidence": 0.8,
                    "original_text": match.group(0)
                }
        
        return None
    
    def _extract_user_references(self, text: str) -> List[str]:
        """Extract user references from text."""
        users = []
        
        for pattern in self.user_patterns["mentions"]:
            matches = re.findall(pattern, text)
            users.extend(matches)
        
        for pattern in self.user_patterns["user_references"]:
            matches = re.findall(pattern, text.lower())
            users.extend(matches)
        
        return list(set(users))  # Remove duplicates
    
    def _extract_summary_style(
        self,
        text: str,
        channel_context: ChannelContext,
        participant_context: ParticipantContext
    ) -> Dict[str, Any]:
        """Extract summary style preference."""
        text_lower = text.lower()
        
        # Explicit style requests
        if any(keyword in text_lower for keyword in ["brief", "short", "quick"]):
            return {"style": "brief", "confidence": 0.9, "source": "user_message"}
        elif any(keyword in text_lower for keyword in ["detailed", "comprehensive", "full"]):
            return {"style": "detailed", "confidence": 0.9, "source": "user_message"}
        elif any(keyword in text_lower for keyword in ["technical", "engineering"]):
            return {"style": "technical", "confidence": 0.8, "source": "user_message"}
        
        # Infer from context
        if channel_context.has_technical_focus() and participant_context.get_primary_expertise() == "high":
            return {"style": "technical", "confidence": 0.7, "source": "context_inference"}
        elif channel_context.urgency_level.value == "high":
            return {"style": "brief", "confidence": 0.6, "source": "context_inference"}
        else:
            return {"style": "balanced", "confidence": 0.5, "source": "default"}
    
    def _extract_summary_length(self, text: str, channel_context: ChannelContext) -> Optional[Dict[str, Any]]:
        """Extract summary length preference."""
        # Look for explicit length requests
        length_pattern = r"(?:in|with|about|around)\s+(\d+)\s+(words|sentences|lines|paragraphs)"
        match = re.search(length_pattern, text.lower())
        
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            # Convert to approximate character count
            if "word" in unit:
                char_count = value * 6  # ~6 chars per word
            elif "sentence" in unit:
                char_count = value * 60  # ~60 chars per sentence
            elif "line" in unit:
                char_count = value * 80  # ~80 chars per line
            elif "paragraph" in unit:
                char_count = value * 300  # ~300 chars per paragraph
            else:
                char_count = value
            
            return {
                "value": char_count,
                "confidence": 0.8,
                "original_text": match.group(0)
            }
        
        return None
    
    def _extract_focus_topics(self, text: str, channel_context: ChannelContext) -> Optional[List[str]]:
        """Extract focus topics from request."""
        text_lower = text.lower()
        
        # Look for "focus on", "about", "regarding" patterns
        focus_patterns = [
            r"(?:focus on|focusing on|about|regarding|concerning)\s+([^.]+)",
            r"(?:specifically|particularly)\s+([^.]+)",
            r"(?:related to|relating to)\s+([^.]+)"
        ]
        
        topics = []
        for pattern in focus_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                # Split by common delimiters
                topic_parts = re.split(r'[,;]|and|or', match)
                topics.extend([topic.strip() for topic in topic_parts if len(topic.strip()) > 2])
        
        # Add context-specific topics
        if channel_context.technical_keywords:
            topics.extend(list(channel_context.technical_keywords)[:3])
        
        return topics[:5] if topics else None  # Limit to top 5 topics
    
    def _determine_analysis_type(
        self,
        text: str,
        channel_context: ChannelContext
    ) -> Dict[str, Any]:
        """Determine analysis type from request and context."""
        text_lower = text.lower()
        
        # Explicit analysis types
        if any(keyword in text_lower for keyword in ["sentiment", "mood", "tone"]):
            return {"type": "sentiment", "confidence": 0.9, "source": "user_message"}
        elif any(keyword in text_lower for keyword in ["topics", "themes", "subjects"]):
            return {"type": "topic", "confidence": 0.9, "source": "user_message"}
        elif any(keyword in text_lower for keyword in ["timeline", "chronology", "sequence"]):
            return {"type": "timeline", "confidence": 0.9, "source": "user_message"}
        elif any(keyword in text_lower for keyword in ["decision", "conclusion", "outcome"]):
            return {"type": "decision", "confidence": 0.8, "source": "user_message"}
        
        # Infer from channel context
        if channel_context.context_type == ContextType.TECHNICAL_DISCUSSION:
            return {"type": "technical", "confidence": 0.7, "source": "context_inference"}
        elif channel_context.context_type == ContextType.PROJECT_COORDINATION:
            return {"type": "project", "confidence": 0.7, "source": "context_inference"}
        elif channel_context.context_type == ContextType.INCIDENT_RESPONSE:
            return {"type": "incident", "confidence": 0.8, "source": "context_inference"}
        else:
            return {"type": "general", "confidence": 0.5, "source": "default"}
    
    def _calculate_confidence(self, extracted_parameters: Dict[str, ContextualParameter]) -> float:
        """Calculate overall confidence score."""
        if not extracted_parameters:
            return 0.0
        
        total_confidence = sum(param.confidence for param in extracted_parameters.values())
        return total_confidence / len(extracted_parameters)