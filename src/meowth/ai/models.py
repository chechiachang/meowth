"""Data models for Azure OpenAI chat integration.

This module defines the core data structures used throughout the Azure OpenAI
integration, including thread context analysis, AI responses, and request sessions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from uuid import UUID, uuid4


class SessionStatus(Enum):
    """Status enum for Request Session lifecycle."""

    CREATED = "created"
    ANALYZING_CONTEXT = "analyzing_context"
    GENERATING_RESPONSE = "generating_response"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ThreadMessage:
    """Represents a single message within a thread context for AI processing."""

    user_id: str
    text: str
    timestamp: str
    is_bot_message: bool
    token_count: int = 0

    def __post_init__(self) -> None:
        """Validate ThreadMessage fields after initialization."""
        if not self.user_id:
            raise ValueError("user_id must be non-empty")
        if not self.text:
            raise ValueError("text must be non-empty")
        if len(self.text) > 4000:
            raise ValueError("text must be <= 4000 characters")
        if not self.timestamp:
            raise ValueError("timestamp must be non-empty")
        if self.token_count < 0:
            raise ValueError("token_count must be non-negative")


@dataclass
class ThreadContext:
    """Represents the runtime analysis of visible messages in a Slack thread."""

    thread_ts: str
    channel_id: str
    messages: list[ThreadMessage] = field(default_factory=list)
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate ThreadContext fields after initialization."""
        if not self.thread_ts:
            raise ValueError("thread_ts must be non-empty")
        if not self.channel_id:
            raise ValueError("channel_id must be non-empty")
        if len(self.messages) > 50:
            raise ValueError("messages must not exceed 50 items")
        if self.token_count > 4000:
            raise ValueError("token_count must not exceed 4000")
        if self.token_count < 0:
            raise ValueError("token_count must be non-negative")


@dataclass
class AIResponse:
    """Generated response from Azure OpenAI with metadata."""

    content: str
    model_used: str
    deployment_name: str
    tokens_used: int
    generation_time: float
    context_tokens: int
    completion_tokens: int
    azure_endpoint: str
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate AIResponse fields after initialization."""
        if not self.content:
            raise ValueError("content must be non-empty")
        if len(self.content) > 4000:
            raise ValueError("content must be <= 4000 characters")
        if not self.model_used:
            raise ValueError("model_used must be non-empty")
        if not self.deployment_name:
            raise ValueError("deployment_name must be non-empty")
        if self.tokens_used <= 0:
            raise ValueError("tokens_used must be positive")
        if self.generation_time <= 0 or self.generation_time > 30.0:
            raise ValueError("generation_time must be positive and <= 30.0 seconds")
        if self.context_tokens < 0:
            raise ValueError("context_tokens must be non-negative")
        if self.completion_tokens <= 0:
            raise ValueError("completion_tokens must be positive")
        if self.context_tokens + self.completion_tokens != self.tokens_used:
            raise ValueError(
                "context_tokens + completion_tokens must equal tokens_used"
            )
        if not self.azure_endpoint:
            raise ValueError("azure_endpoint must be non-empty")


@dataclass
class RequestSession:
    """Single request-response cycle containing thread analysis and response generation with thread isolation."""

    user_id: str
    thread_context: ThreadContext
    session_id: UUID = field(default_factory=uuid4)
    thread_id: str = ""  # Unique identifier for thread isolation
    channel_id: str = ""  # Channel identifier for session tracking
    ai_response: Optional[AIResponse] = None
    error_message: Optional[str] = None
    status: SessionStatus = SessionStatus.CREATED
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    _context_isolated: bool = field(
        default=True, init=False
    )  # Flag for thread isolation verification

    def __post_init__(self) -> None:
        """Validate RequestSession fields after initialization."""
        if not self.user_id:
            raise ValueError("user_id must be non-empty")

        # Set thread_id and channel_id from context if not provided
        if not self.thread_id and self.thread_context:
            self.thread_id = (
                f"{self.thread_context.channel_id}:{self.thread_context.thread_ts}"
            )
        if not self.channel_id and self.thread_context:
            self.channel_id = self.thread_context.channel_id

        # Validate completion state
        if self.status == SessionStatus.COMPLETED:
            if self.ai_response is None and self.error_message is None:
                raise ValueError(
                    "Either ai_response or error_message must be set when status is COMPLETED"
                )

        # Validate timing
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must be after started_at")

    def complete_with_response(self, response: AIResponse) -> None:
        """Mark session as completed with successful AI response."""
        self.ai_response = response
        self.status = SessionStatus.COMPLETED
        self.completed_at = datetime.now()

    def complete_with_error(self, error: str) -> None:
        """Mark session as completed with error."""
        self.error_message = error
        self.status = SessionStatus.ERROR
        self.completed_at = datetime.now()

    def get_thread_id(self) -> str:
        """Get unique thread identifier for isolation tracking."""
        return self.thread_id

    def get_session_key(self) -> str:
        """Get unique session key for tracking active sessions."""
        return f"{self.thread_id}:{self.session_id}"

    def is_context_isolated(self) -> bool:
        """Check if this session's context is properly isolated."""
        return self._context_isolated

    def mark_context_isolated(self, isolated: bool = True) -> None:
        """Mark this session's context as isolated or not."""
        self._context_isolated = isolated


# Session tracking for thread isolation
class SessionTracker:
    """Tracks active sessions to ensure thread isolation."""

    def __init__(self) -> None:
        """Initialize session tracker."""
        self._active_sessions: dict[str, RequestSession] = {}
        self._thread_sessions: dict[
            str, set[str]
        ] = {}  # thread_id -> set of session_ids

    def register_session(self, session: RequestSession) -> None:
        """Register a new session for tracking."""
        session_key = session.get_session_key()
        thread_id = session.get_thread_id()

        # Register session
        self._active_sessions[session_key] = session

        # Track session by thread
        if thread_id not in self._thread_sessions:
            self._thread_sessions[thread_id] = set()
        self._thread_sessions[thread_id].add(str(session.session_id))

    def unregister_session(self, session: RequestSession) -> None:
        """Unregister a completed session."""
        session_key = session.get_session_key()
        thread_id = session.get_thread_id()

        # Remove from active sessions
        if session_key in self._active_sessions:
            del self._active_sessions[session_key]

        # Remove from thread tracking
        if thread_id in self._thread_sessions:
            self._thread_sessions[thread_id].discard(str(session.session_id))
            # Clean up empty thread entries
            if not self._thread_sessions[thread_id]:
                del self._thread_sessions[thread_id]

    def get_active_sessions_for_thread(self, thread_id: str) -> list[RequestSession]:
        """Get all active sessions for a specific thread."""
        if thread_id not in self._thread_sessions:
            return []

        sessions = []
        for session_id in self._thread_sessions[thread_id]:
            for session_key, session in self._active_sessions.items():
                if str(session.session_id) == session_id:
                    sessions.append(session)
                    break

        return sessions

    def get_total_active_sessions(self) -> int:
        """Get total number of active sessions."""
        return len(self._active_sessions)

    def get_active_threads(self) -> list[str]:
        """Get list of thread IDs with active sessions."""
        return list(self._thread_sessions.keys())

    def cleanup_completed_sessions(self) -> int:
        """Clean up completed sessions and return count of cleaned sessions."""
        completed_sessions = []

        for session in self._active_sessions.values():
            if session.status in [SessionStatus.COMPLETED, SessionStatus.ERROR]:
                completed_sessions.append(session)

        for session in completed_sessions:
            self.unregister_session(session)

        return len(completed_sessions)

    def is_thread_isolated(self, thread_id: str) -> bool:
        """Check if all sessions for a thread are properly isolated."""
        sessions = self.get_active_sessions_for_thread(thread_id)
        return all(session.is_context_isolated() for session in sessions)


# Global session tracker instance
_session_tracker = SessionTracker()


def get_session_tracker() -> SessionTracker:
    """Get the global session tracker instance."""
    return _session_tracker


def register_session(session: RequestSession) -> None:
    """Register a session with the global tracker."""
    _session_tracker.register_session(session)


def unregister_session(session: RequestSession) -> None:
    """Unregister a session from the global tracker."""
    _session_tracker.unregister_session(session)


def cleanup_completed_sessions() -> int:
    """Clean up completed sessions globally."""
    return _session_tracker.cleanup_completed_sessions()


class AIError(Exception):
    """Base exception for Azure OpenAI integration errors."""

    def __init__(self, message: str, error_code: Optional[str] = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class AzureOpenAIError(AIError):
    """Exception for Azure OpenAI API specific errors."""

    pass


class ContextAnalysisError(AIError):
    """Exception for thread context analysis errors."""

    pass


class RateLimitError(AIError):
    """Exception for rate limiting errors."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message, "RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after
