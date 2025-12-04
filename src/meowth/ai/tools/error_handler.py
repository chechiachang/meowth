"""Error handling and user feedback for AI agent tool failures.

This module provides comprehensive error handling, user-friendly error messages,
and recovery mechanisms for tool execution failures.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

from .exceptions import ToolError, ErrorCategory


class UserFeedbackType(Enum):
    """Types of user feedback for different error scenarios."""

    TOOL_UNAVAILABLE = "tool_unavailable"
    RATE_LIMITED = "rate_limited"
    CONFIGURATION_ERROR = "configuration_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    PERMISSION_ERROR = "permission_error"
    TIMEOUT_ERROR = "timeout_error"
    VALIDATION_ERROR = "validation_error"
    GENERIC_ERROR = "generic_error"


class ToolErrorHandler:
    """Centralized error handling for tool execution failures."""

    def __init__(self) -> None:
        """Initialize the error handler."""
        self.logger = logging.getLogger(__name__)

        # User-friendly error messages
        self._user_messages = {
            UserFeedbackType.TOOL_UNAVAILABLE: (
                "I'm sorry, but that feature is currently unavailable. "
                "Please try again later or contact an administrator."
            ),
            UserFeedbackType.RATE_LIMITED: (
                "I'm receiving a lot of requests right now. "
                "Please wait a moment and try again."
            ),
            UserFeedbackType.CONFIGURATION_ERROR: (
                "I'm having trouble with my configuration. "
                "Please contact an administrator for assistance."
            ),
            UserFeedbackType.EXTERNAL_SERVICE_ERROR: (
                "I'm having trouble connecting to external services. "
                "Please try again in a few minutes."
            ),
            UserFeedbackType.PERMISSION_ERROR: (
                "I don't have permission to perform that action. "
                "Please check my permissions or contact an administrator."
            ),
            UserFeedbackType.TIMEOUT_ERROR: (
                "That request is taking longer than expected. "
                "Please try with a smaller request or try again later."
            ),
            UserFeedbackType.VALIDATION_ERROR: (
                "I couldn't understand that request. "
                "Please try rephrasing or providing more specific details."
            ),
            UserFeedbackType.GENERIC_ERROR: (
                "I encountered an unexpected error. "
                "Please try again or contact support if the problem persists."
            ),
        }

        # Error recovery suggestions
        self._recovery_suggestions = {
            UserFeedbackType.RATE_LIMITED: [
                "Try your request again in 1-2 minutes",
                "Consider breaking large requests into smaller parts",
            ],
            UserFeedbackType.EXTERNAL_SERVICE_ERROR: [
                "Check if the service is experiencing issues",
                "Try again in 5-10 minutes",
                "Use alternative phrasing for your request",
            ],
            UserFeedbackType.TIMEOUT_ERROR: [
                "Try requesting fewer messages or a shorter time period",
                "Break your request into smaller parts",
                "Try again when the system is less busy",
            ],
            UserFeedbackType.VALIDATION_ERROR: [
                "Check your message format and try again",
                "Provide more specific details in your request",
                "Use simpler language in your request",
            ],
        }

    def handle_tool_error(
        self, error: ToolError, user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a tool execution error and generate user feedback.

        Args:
            error: The tool error that occurred
            user_context: Optional context about the user and request

        Returns:
            Dictionary with user message and recovery information
        """
        # Log the error with full context
        self.logger.error(
            f"Tool error occurred: {error.message}",
            extra={
                "error_category": error.category.value if error.category else "unknown",
                "error_severity": error.severity.value if error.severity else "unknown",
                "tool_name": getattr(error, "tool_name", "unknown"),
                "user_context": user_context or {},
                "error_details": getattr(error, "details", {}),
            },
        )

        # Map error to user feedback type
        feedback_type = self._map_error_to_feedback_type(error)

        # Generate user-friendly response
        response = {
            "message": self._user_messages[feedback_type],
            "feedback_type": feedback_type.value,
            "can_retry": self._can_retry_error(error),
            "retry_delay_seconds": self._get_retry_delay(error),
            "recovery_suggestions": self._recovery_suggestions.get(feedback_type, []),
        }

        # Add contextual information if available
        if user_context:
            response["context"] = {
                "channel_id": user_context.get("channel_id"),
                "user_id": user_context.get("user_id"),
                "request_type": user_context.get("request_type"),
            }

        return response

    def _map_error_to_feedback_type(self, error: ToolError) -> UserFeedbackType:
        """Map a ToolError to appropriate user feedback type.

        Args:
            error: The tool error to map

        Returns:
            Appropriate UserFeedbackType
        """
        if not hasattr(error, "category") or not error.category:
            return UserFeedbackType.GENERIC_ERROR

        category_mapping = {
            ErrorCategory.RATE_LIMIT_ERROR: UserFeedbackType.RATE_LIMITED,
            ErrorCategory.CONFIGURATION_ERROR: UserFeedbackType.CONFIGURATION_ERROR,
            ErrorCategory.EXTERNAL_SERVICE_ERROR: UserFeedbackType.EXTERNAL_SERVICE_ERROR,
            ErrorCategory.AUTHENTICATION_ERROR: UserFeedbackType.PERMISSION_ERROR,
            ErrorCategory.PERMISSION_ERROR: UserFeedbackType.PERMISSION_ERROR,
            ErrorCategory.TIMEOUT_ERROR: UserFeedbackType.TIMEOUT_ERROR,
            ErrorCategory.VALIDATION_ERROR: UserFeedbackType.VALIDATION_ERROR,
            ErrorCategory.DATA_ERROR: UserFeedbackType.VALIDATION_ERROR,
            ErrorCategory.NETWORK_ERROR: UserFeedbackType.EXTERNAL_SERVICE_ERROR,
        }

        return category_mapping.get(error.category, UserFeedbackType.GENERIC_ERROR)

    def _can_retry_error(self, error: ToolError) -> bool:
        """Determine if an error is retryable.

        Args:
            error: The tool error to evaluate

        Returns:
            True if the error is retryable
        """
        if not hasattr(error, "category") or not error.category:
            return False

        retryable_categories = {
            ErrorCategory.RATE_LIMIT_ERROR,
            ErrorCategory.EXTERNAL_SERVICE_ERROR,
            ErrorCategory.NETWORK_ERROR,
            ErrorCategory.TIMEOUT_ERROR,
        }

        return error.category in retryable_categories

    def _get_retry_delay(self, error: ToolError) -> int:
        """Get recommended retry delay for an error.

        Args:
            error: The tool error to evaluate

        Returns:
            Recommended delay in seconds (0 if not retryable)
        """
        if not hasattr(error, "category") or not error.category:
            return 0

        delay_mapping = {
            ErrorCategory.RATE_LIMIT_ERROR: 60,  # 1 minute
            ErrorCategory.EXTERNAL_SERVICE_ERROR: 300,  # 5 minutes
            ErrorCategory.NETWORK_ERROR: 60,  # 1 minute
            ErrorCategory.TIMEOUT_ERROR: 120,  # 2 minutes
        }

        return delay_mapping.get(error.category, 0)

    def get_fallback_response(self, request_context: Dict[str, Any]) -> str:
        """Generate a fallback response when all tools fail.

        Args:
            request_context: Context about the failed request

        Returns:
            User-friendly fallback message
        """
        return (
            "I'm experiencing some technical difficulties and can't complete that request right now. "
            "Please try again later, or contact support if you continue to have problems. "
            f"Request ID: {request_context.get('request_id', 'unknown')}"
        )


# Global error handler instance
_error_handler = None


def get_error_handler() -> ToolErrorHandler:
    """Get the global error handler instance.

    Returns:
        Global ToolErrorHandler instance
    """
    global _error_handler
    if _error_handler is None:
        _error_handler = ToolErrorHandler()
    return _error_handler
