"""Exception classes for AI agent tools.

This module defines the error hierarchy and categorization system for tool
execution failures, providing structured error handling with user guidance.
"""

from enum import Enum
from typing import Dict, Any, Optional


class ErrorCategory(str, Enum):
    """Categories of tool execution errors."""

    NETWORK = "network"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    RATE_LIMIT = "rate_limit"
    INVALID_INPUT = "invalid_input"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    SYSTEM_ERROR = "system_error"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_ERROR = "dependency_error"


class ErrorSeverity(str, Enum):
    """Severity levels for error categorization."""

    CRITICAL = "critical"  # System failure, requires immediate attention
    HIGH = "high"  # Tool completely unusable
    MEDIUM = "medium"  # Tool degraded but partially functional
    LOW = "low"  # Minor issues, tool still functional
    INFO = "info"  # Informational, no action required


class ToolError(Exception):
    """Base exception for AI agent tool errors.

    Provides structured error information including categorization,
    severity, context, and user guidance for recovery.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        user_guidance: Optional[str] = None,
        tool_name: Optional[str] = None,
    ):
        """Initialize a ToolError.

        Args:
            message: Human-readable error description
            category: Error category for handling logic
            severity: Error severity level
            context: Additional context for debugging
            recoverable: Whether the error can be recovered from
            user_guidance: Specific guidance for the user
            tool_name: Name of the tool that generated the error
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.recoverable = recoverable
        self.user_guidance = user_guidance
        self.tool_name = tool_name

    def __str__(self) -> str:
        """Return a formatted error string."""
        tool_info = f" ({self.tool_name})" if self.tool_name else ""
        return f"[{self.category.value.upper()}] {self.message}{tool_info}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": self.context,
            "recoverable": self.recoverable,
            "user_guidance": self.user_guidance,
            "tool_name": self.tool_name,
        }


class SlackToolError(ToolError):
    """Specific error for Slack-related tool failures."""

    def __init__(self, message: str, slack_error: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        if slack_error:
            self.context["slack_error"] = slack_error


class OpenAIToolError(ToolError):
    """Specific error for OpenAI-related tool failures."""

    def __init__(self, message: str, openai_error: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        if openai_error:
            self.context["openai_error"] = openai_error


class ConfigurationError(ToolError):
    """Error in tool configuration."""

    def __init__(self, message: str, config_path: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CONFIG_ERROR,
            severity=ErrorSeverity.HIGH,
            recoverable=False,
            **kwargs,
        )
        if config_path:
            self.context["config_path"] = config_path


class RateLimitError(ToolError):
    """Error when rate limits are exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        endpoint: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message,
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.MEDIUM,
            recoverable=True,
            **kwargs,
        )
        if retry_after:
            self.context["retry_after"] = retry_after
        if endpoint:
            self.context["endpoint"] = endpoint


class TimeoutError(ToolError):
    """Error when tool execution times out."""

    def __init__(self, message: str, timeout_seconds: Optional[float] = None, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            recoverable=True,
            **kwargs,
        )
        if timeout_seconds:
            self.context["timeout_seconds"] = timeout_seconds
