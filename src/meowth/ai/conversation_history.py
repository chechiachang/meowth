"""Conversation history management for context-aware AI responses.

Manages conversation history with intelligent truncation and context preservation
to stay within token limits while maintaining relevant context.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import deque

from meowth.ai.models import ThreadContext


logger = logging.getLogger(__name__)


@dataclass
class MessageSummary:
    """Compressed summary of a message for context preservation."""
    timestamp: float
    user_id: str
    content_summary: str  # Compressed version of message content
    importance_score: float  # 0.0 to 1.0
    message_type: str  # user, bot, system, etc.
    thread_context: bool  # Whether message is part of thread context


@dataclass
class ConversationWindow:
    """A window of conversation messages with metadata."""
    messages: List[Dict]
    summaries: List[MessageSummary]
    total_tokens: int
    window_start: float  # Timestamp
    window_end: float  # Timestamp
    context_preserved: bool  # Whether important context was preserved


class ConversationHistory:
    """Manages conversation history with intelligent truncation and context preservation."""
    
    MAX_MESSAGES = 100
    MAX_TOKENS = 8000  # Conservative token limit for context
    IMPORTANCE_THRESHOLD = 0.3  # Minimum importance to preserve
    SUMMARY_TOKEN_RATIO = 0.3  # Ratio of tokens to use for summaries
    
    def __init__(self, max_messages: int = MAX_MESSAGES, max_tokens: int = MAX_TOKENS):
        """Initialize conversation history manager.
        
        Args:
            max_messages: Maximum number of messages to keep in memory
            max_tokens: Maximum token count for conversation context
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.conversation_windows: Dict[str, ConversationWindow] = {}
        self.message_cache: Dict[str, deque] = {}  # channel_id -> message deque
        
        # Keywords that indicate important messages
        self.importance_keywords = {
            "decision", "action", "todo", "deadline", "important", "critical",
            "summary", "conclusion", "resolution", "agreed", "decided",
            "next steps", "follow up", "assigned", "responsible", "deliver"
        }
        
        # Technical keywords that preserve technical context
        self.technical_keywords = {
            "error", "exception", "bug", "fix", "deploy", "release", "version",
            "api", "endpoint", "database", "query", "performance", "optimization",
            "architecture", "design", "implementation", "requirements"
        }
    
    def add_message(self, channel_id: str, message: Dict) -> None:
        """Add a new message to conversation history.
        
        Args:
            channel_id: Slack channel ID
            message: Message data from Slack API
        """
        try:
            # Initialize channel cache if needed
            if channel_id not in self.message_cache:
                self.message_cache[channel_id] = deque(maxlen=self.max_messages)
            
            # Add message to cache
            self.message_cache[channel_id].append(message)
            
            # Update conversation window
            self._update_conversation_window(channel_id)
            
            logger.debug(f"Added message to history for channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Error adding message to history: {e}")
    
    def get_context_window(
        self, 
        channel_id: str,
        max_age_hours: int = 24,
        preserve_important: bool = True
    ) -> ConversationWindow:
        """Get optimized conversation window for AI context.
        
        Args:
            channel_id: Slack channel ID
            max_age_hours: Maximum age of messages to include
            preserve_important: Whether to preserve important messages beyond limits
            
        Returns:
            ConversationWindow with optimized message selection
        """
        if channel_id not in self.conversation_windows:
            return self._create_empty_window()
        
        window = self.conversation_windows[channel_id]
        
        # Filter by age
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cutoff_timestamp = cutoff_time.timestamp()
        
        recent_messages = [
            msg for msg in window.messages
            if float(msg.get("ts", "0")) > cutoff_timestamp
        ]
        
        # If we're within limits, return as-is
        if (len(recent_messages) <= self.max_messages and 
            self._estimate_tokens(recent_messages) <= self.max_tokens):
            return ConversationWindow(
                messages=recent_messages,
                summaries=window.summaries,
                total_tokens=self._estimate_tokens(recent_messages),
                window_start=min(float(msg.get("ts", "0")) for msg in recent_messages) if recent_messages else 0,
                window_end=max(float(msg.get("ts", "0")) for msg in recent_messages) if recent_messages else 0,
                context_preserved=True
            )
        
        # Need to truncate intelligently
        return self._create_optimized_window(recent_messages, preserve_important)
    
    def get_thread_context(
        self,
        channel_id: str,
        thread_ts: str,
        include_context: bool = True
    ) -> ThreadContext:
        """Get thread context with conversation history.
        
        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp
            include_context: Whether to include surrounding context
            
        Returns:
            ThreadContext with relevant conversation history
        """
        # Get thread messages
        thread_messages = []
        if channel_id in self.message_cache:
            thread_messages = [
                msg for msg in self.message_cache[channel_id]
                if msg.get("thread_ts") == thread_ts or msg.get("ts") == thread_ts
            ]
        
        # Add surrounding context if requested
        context_messages = []
        if include_context and channel_id in self.message_cache:
            # Get messages around the thread start time
            thread_start = float(thread_ts)
            context_start = thread_start - 3600  # 1 hour before
            
            context_messages = [
                msg for msg in self.message_cache[channel_id]
                if (float(msg.get("ts", "0")) >= context_start and 
                    float(msg.get("ts", "0")) < thread_start and
                    msg.get("thread_ts") != thread_ts)  # Not part of thread
            ][-10:]  # Last 10 context messages
        
        # Combine and sort by timestamp
        all_messages = context_messages + thread_messages
        all_messages.sort(key=lambda x: float(x.get("ts", "0")))
        
        # Calculate token count
        token_count = self._estimate_tokens(all_messages)
        
        return ThreadContext(
            channel_id=channel_id,
            thread_ts=thread_ts,
            messages=all_messages,
            token_count=token_count
        )
    
    def summarize_old_context(
        self,
        channel_id: str,
        before_timestamp: float,
        max_summary_length: int = 500
    ) -> Optional[str]:
        """Create summary of old conversation context.
        
        Args:
            channel_id: Slack channel ID
            before_timestamp: Timestamp before which to summarize
            max_summary_length: Maximum length of summary
            
        Returns:
            Summary string or None if no content to summarize
        """
        if channel_id not in self.message_cache:
            return None
        
        # Get old messages
        old_messages = [
            msg for msg in self.message_cache[channel_id]
            if float(msg.get("ts", "0")) < before_timestamp
        ]
        
        if not old_messages:
            return None
        
        # Extract key information
        key_decisions = []
        action_items = []
        technical_points = []
        
        for msg in old_messages:
            text = msg.get("text", "").lower()
            
            # Look for decisions
            if any(keyword in text for keyword in ["decided", "agreed", "conclusion"]):
                key_decisions.append(self._extract_key_sentence(msg.get("text", "")))
            
            # Look for action items
            if any(keyword in text for keyword in ["todo", "action", "assigned", "responsible"]):
                action_items.append(self._extract_key_sentence(msg.get("text", "")))
            
            # Look for technical points
            if any(keyword in text for keyword in self.technical_keywords):
                technical_points.append(self._extract_key_sentence(msg.get("text", "")))
        
        # Build summary
        summary_parts = []
        
        if key_decisions:
            summary_parts.append(f"Key decisions: {'; '.join(key_decisions[:3])}")
        
        if action_items:
            summary_parts.append(f"Action items: {'; '.join(action_items[:3])}")
            
        if technical_points:
            summary_parts.append(f"Technical notes: {'; '.join(technical_points[:3])}")
        
        summary = " | ".join(summary_parts)
        
        # Truncate if too long
        if len(summary) > max_summary_length:
            summary = summary[:max_summary_length-3] + "..."
        
        return summary if summary else None
    
    def clear_old_history(
        self,
        channel_id: str,
        keep_hours: int = 48,
        preserve_summaries: bool = True
    ) -> int:
        """Clear old conversation history beyond specified time.
        
        Args:
            channel_id: Slack channel ID
            keep_hours: Hours of history to keep
            preserve_summaries: Whether to preserve message summaries
            
        Returns:
            Number of messages removed
        """
        if channel_id not in self.message_cache:
            return 0
        
        cutoff_time = datetime.now() - timedelta(hours=keep_hours)
        cutoff_timestamp = cutoff_time.timestamp()
        
        # Create summaries of old messages if requested
        if preserve_summaries:
            old_messages = [
                msg for msg in self.message_cache[channel_id]
                if float(msg.get("ts", "0")) < cutoff_timestamp
            ]
            
            if old_messages:
                summary = self.summarize_old_context(channel_id, cutoff_timestamp)
                if summary and channel_id in self.conversation_windows:
                    # Add summary to conversation window
                    summary_obj = MessageSummary(
                        timestamp=cutoff_timestamp,
                        user_id="system",
                        content_summary=summary,
                        importance_score=0.8,
                        message_type="summary",
                        thread_context=False
                    )
                    self.conversation_windows[channel_id].summaries.append(summary_obj)
        
        # Count messages to remove
        original_count = len(self.message_cache[channel_id])
        
        # Filter out old messages
        self.message_cache[channel_id] = deque([
            msg for msg in self.message_cache[channel_id]
            if float(msg.get("ts", "0")) >= cutoff_timestamp
        ], maxlen=self.max_messages)
        
        removed_count = original_count - len(self.message_cache[channel_id])
        
        # Update conversation window
        if channel_id in self.conversation_windows:
            self._update_conversation_window(channel_id)
        
        logger.info(f"Removed {removed_count} old messages from {channel_id}")
        return removed_count
    
    def get_conversation_stats(self, channel_id: str) -> Dict[str, any]:
        """Get conversation statistics for monitoring.
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            Dictionary with conversation statistics
        """
        if channel_id not in self.message_cache:
            return {
                "message_count": 0,
                "estimated_tokens": 0,
                "oldest_message": None,
                "newest_message": None,
                "summary_count": 0
            }
        
        messages = list(self.message_cache[channel_id])
        
        stats = {
            "message_count": len(messages),
            "estimated_tokens": self._estimate_tokens(messages),
            "oldest_message": min(float(msg.get("ts", "0")) for msg in messages) if messages else None,
            "newest_message": max(float(msg.get("ts", "0")) for msg in messages) if messages else None,
            "summary_count": len(self.conversation_windows.get(channel_id, ConversationWindow([], [], 0, 0, 0, False)).summaries)
        }
        
        return stats
    
    # Helper methods
    
    def _update_conversation_window(self, channel_id: str) -> None:
        """Update conversation window for channel."""
        if channel_id not in self.message_cache:
            return
        
        messages = list(self.message_cache[channel_id])
        
        # Calculate importance scores
        summaries = []
        for msg in messages:
            importance = self._calculate_importance_score(msg)
            summary = MessageSummary(
                timestamp=float(msg.get("ts", "0")),
                user_id=msg.get("user", ""),
                content_summary=self._create_content_summary(msg),
                importance_score=importance,
                message_type=self._determine_message_type(msg),
                thread_context=bool(msg.get("thread_ts"))
            )
            summaries.append(summary)
        
        # Create window
        token_count = self._estimate_tokens(messages)
        
        self.conversation_windows[channel_id] = ConversationWindow(
            messages=messages,
            summaries=summaries,
            total_tokens=token_count,
            window_start=min(float(msg.get("ts", "0")) for msg in messages) if messages else 0,
            window_end=max(float(msg.get("ts", "0")) for msg in messages) if messages else 0,
            context_preserved=True
        )
    
    def _create_optimized_window(
        self, 
        messages: List[Dict],
        preserve_important: bool
    ) -> ConversationWindow:
        """Create optimized conversation window within token limits."""
        if not messages:
            return self._create_empty_window()
        
        # Calculate importance scores for all messages
        scored_messages = []
        for msg in messages:
            importance = self._calculate_importance_score(msg)
            scored_messages.append((msg, importance))
        
        # Sort by importance if preserving important messages
        if preserve_important:
            scored_messages.sort(key=lambda x: x[1], reverse=True)
        else:
            # Sort by timestamp (most recent first)
            scored_messages.sort(key=lambda x: float(x[0].get("ts", "0")), reverse=True)
        
        # Select messages within limits
        selected_messages = []
        current_tokens = 0
        
        for msg, importance in scored_messages:
            msg_tokens = self._estimate_tokens([msg])
            
            # Always include very important messages if there's any room
            if (current_tokens + msg_tokens <= self.max_tokens or 
                (importance > 0.8 and current_tokens < self.max_tokens * 0.5)):
                selected_messages.append(msg)
                current_tokens += msg_tokens
                
                if len(selected_messages) >= self.max_messages:
                    break
        
        # Sort selected messages by timestamp
        selected_messages.sort(key=lambda x: float(x.get("ts", "0")))
        
        # Create summaries for non-selected important messages
        summaries = []
        for msg, importance in scored_messages:
            if msg not in selected_messages and importance > self.IMPORTANCE_THRESHOLD:
                summary = MessageSummary(
                    timestamp=float(msg.get("ts", "0")),
                    user_id=msg.get("user", ""),
                    content_summary=self._create_content_summary(msg),
                    importance_score=importance,
                    message_type=self._determine_message_type(msg),
                    thread_context=bool(msg.get("thread_ts"))
                )
                summaries.append(summary)
        
        return ConversationWindow(
            messages=selected_messages,
            summaries=summaries,
            total_tokens=current_tokens,
            window_start=min(float(msg.get("ts", "0")) for msg in selected_messages) if selected_messages else 0,
            window_end=max(float(msg.get("ts", "0")) for msg in selected_messages) if selected_messages else 0,
            context_preserved=len(summaries) > 0
        )
    
    def _create_empty_window(self) -> ConversationWindow:
        """Create empty conversation window."""
        return ConversationWindow(
            messages=[],
            summaries=[],
            total_tokens=0,
            window_start=0,
            window_end=0,
            context_preserved=False
        )
    
    def _calculate_importance_score(self, message: Dict) -> float:
        """Calculate importance score for a message."""
        text = message.get("text", "").lower()
        score = 0.0
        
        # Base score for any message
        score += 0.1
        
        # Boost for important keywords
        for keyword in self.importance_keywords:
            if keyword in text:
                score += 0.2
        
        # Boost for technical keywords  
        for keyword in self.technical_keywords:
            if keyword in text:
                score += 0.1
        
        # Boost for questions (likely need answers)
        if "?" in text:
            score += 0.15
        
        # Boost for mentions (directed communication)
        if "<@" in message.get("text", ""):
            score += 0.1
        
        # Boost for thread starters
        if message.get("thread_ts") == message.get("ts"):
            score += 0.2
        
        # Boost for longer messages (more content)
        text_length = len(text)
        if text_length > 100:
            score += min(0.2, text_length / 1000)
        
        # Penalty for very short messages
        if text_length < 20:
            score -= 0.1
        
        # Boost for recent messages (time decay)
        msg_age_hours = (datetime.now().timestamp() - float(message.get("ts", "0"))) / 3600
        if msg_age_hours < 1:
            score += 0.1
        elif msg_age_hours < 6:
            score += 0.05
        
        return min(1.0, max(0.0, score))  # Clamp between 0 and 1
    
    def _create_content_summary(self, message: Dict, max_length: int = 100) -> str:
        """Create content summary for a message."""
        text = message.get("text", "")
        
        if len(text) <= max_length:
            return text
        
        # Try to extract key sentence
        sentences = text.split(". ")
        if sentences:
            # Find sentence with important keywords
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in self.importance_keywords):
                    if len(sentence) <= max_length:
                        return sentence
            
            # Fall back to first sentence
            if len(sentences[0]) <= max_length:
                return sentences[0]
        
        # Truncate with ellipsis
        return text[:max_length-3] + "..."
    
    def _determine_message_type(self, message: Dict) -> str:
        """Determine message type."""
        if message.get("subtype") == "bot_message":
            return "bot"
        elif message.get("user"):
            return "user"
        else:
            return "system"
    
    def _estimate_tokens(self, messages: List[Dict]) -> int:
        """Estimate token count for messages."""
        if not messages:
            return 0
        
        # Rough estimation: ~4 characters per token
        total_chars = sum(len(msg.get("text", "")) for msg in messages)
        
        # Add overhead for metadata
        metadata_tokens = len(messages) * 20  # Rough estimate for timestamp, user, etc.
        
        estimated_tokens = (total_chars // 4) + metadata_tokens
        
        return estimated_tokens
    
    def _extract_key_sentence(self, text: str, max_length: int = 150) -> str:
        """Extract key sentence from text."""
        sentences = text.split(". ")
        
        # Find shortest meaningful sentence
        for sentence in sorted(sentences, key=len):
            if len(sentence.strip()) >= 10 and len(sentence) <= max_length:
                return sentence.strip()
        
        # Fall back to truncated text
        return (text[:max_length-3] + "...") if len(text) > max_length else text