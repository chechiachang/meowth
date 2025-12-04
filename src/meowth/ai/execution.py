"""Tool execution context management for AI agent operations.

This module provides context management for handling tool execution requests
with proper state tracking, error handling, and result aggregation.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

from .models import ThreadContext
from .intent import UserIntent

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ToolResult(Generic[T]):
    """Represents the result of a tool execution.

    Attributes:
        tool_name: Name of the executed tool
        success: Whether the tool execution succeeded
        data: Tool execution result data
        error: Error message if execution failed
        execution_time: How long the tool took to execute
        metadata: Additional metadata about execution
    """

    tool_name: str
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate tool result after initialization."""
        if not self.tool_name:
            raise ValueError("tool_name cannot be empty")

        if self.success and self.data is None:
            logger.warning(f"Tool {self.tool_name} succeeded but returned no data")

        if not self.success and not self.error:
            self.error = "Tool execution failed with unknown error"

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool result to dictionary representation."""
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class ToolExecutionContext:
    """Manages context and state for AI agent tool executions.

    Attributes:
        user_intent: Classified user intent driving the execution
        thread_context: Slack thread context
        execution_id: Unique identifier for this execution
        tools_executed: List of tools that have been executed
        results: Results from tool executions
        parameters: Runtime parameters and configuration
        start_time: When the execution context was created
        errors: List of errors encountered during execution
    """

    user_intent: UserIntent
    thread_context: ThreadContext
    execution_id: str
    tools_executed: List[str] = field(default_factory=list)
    results: Dict[str, ToolResult] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    errors: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate context after initialization."""
        if not self.execution_id:
            raise ValueError("execution_id cannot be empty")

        # Merge intent parameters with context parameters
        self.parameters.update(self.user_intent.parameters)

        logger.info(
            f"Created tool execution context {self.execution_id} "
            f"for intent {self.user_intent.primary_intent}"
        )

    def add_tool_result(self, result: ToolResult) -> None:
        """Add a tool execution result to the context.

        Args:
            result: Tool execution result to add
        """
        if result.tool_name in self.results:
            logger.warning(f"Overwriting existing result for tool {result.tool_name}")

        self.results[result.tool_name] = result

        if result.tool_name not in self.tools_executed:
            self.tools_executed.append(result.tool_name)

        if not result.success:
            error_msg = f"Tool {result.tool_name} failed: {result.error}"
            self.errors.append(error_msg)
            logger.error(error_msg)
        else:
            logger.info(f"Tool {result.tool_name} executed successfully")

    def get_tool_result(self, tool_name: str) -> Optional[ToolResult]:
        """Get result for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool result if available, None otherwise
        """
        return self.results.get(tool_name)

    def has_successful_results(self) -> bool:
        """Check if context has any successful tool results.

        Returns:
            True if at least one tool succeeded
        """
        return any(result.success for result in self.results.values())

    def get_successful_results(self) -> Dict[str, ToolResult]:
        """Get only the successful tool results.

        Returns:
            Dictionary of successful results keyed by tool name
        """
        return {name: result for name, result in self.results.items() if result.success}

    def get_failed_results(self) -> Dict[str, ToolResult]:
        """Get only the failed tool results.

        Returns:
            Dictionary of failed results keyed by tool name
        """
        return {
            name: result for name, result in self.results.items() if not result.success
        }

    def update_parameter(self, key: str, value: Any) -> None:
        """Update a runtime parameter.

        Args:
            key: Parameter name
            value: Parameter value
        """
        self.parameters[key] = value
        logger.debug(f"Updated parameter {key} = {value}")

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a runtime parameter value.

        Args:
            key: Parameter name
            default: Default value if parameter not found

        Returns:
            Parameter value or default
        """
        return self.parameters.get(key, default)

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the execution context.

        Returns:
            Dictionary containing execution summary
        """
        execution_duration = (datetime.now(datetime.UTC) - self.start_time).total_seconds()

        return {
            "execution_id": self.execution_id,
            "intent": self.user_intent.primary_intent,
            "intent_confidence": self.user_intent.confidence,
            "tools_executed": self.tools_executed,
            "tools_succeeded": len(self.get_successful_results()),
            "tools_failed": len(self.get_failed_results()),
            "execution_duration": execution_duration,
            "has_errors": bool(self.errors),
            "error_count": len(self.errors),
        }

    def should_continue_execution(self) -> bool:
        """Determine if execution should continue based on context state.

        Returns:
            True if execution should continue
        """
        # Stop if we have too many errors
        if len(self.errors) >= 3:
            logger.warning("Stopping execution due to too many errors")
            return False

        # Stop if execution has been running too long
        execution_duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        if execution_duration > 30:  # 30 second limit
            logger.warning("Stopping execution due to timeout")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary representation.

        Returns:
            Dictionary representation of context
        """
        return {
            "execution_id": self.execution_id,
            "user_intent": self.user_intent.to_dict(),
            "thread_context": {
                "channel_id": self.thread_context.channel_id,
                "thread_ts": self.thread_context.thread_ts,
                "user_id": self.thread_context.user_id,
            },
            "tools_executed": self.tools_executed,
            "results": {
                name: result.to_dict() for name, result in self.results.items()
            },
            "parameters": self.parameters,
            "start_time": self.start_time.isoformat(),
            "errors": self.errors,
            "execution_summary": self.get_execution_summary(),
        }


class ExecutionContextManager:
    """Manages multiple tool execution contexts."""

    def __init__(self):
        """Initialize the context manager."""
        self._active_contexts: Dict[str, ToolExecutionContext] = {}
        self._max_contexts = 50  # Limit to prevent memory issues

    def create_context(
        self, user_intent: UserIntent, thread_context: ThreadContext
    ) -> ToolExecutionContext:
        """Create a new tool execution context.

        Args:
            user_intent: Classified user intent
            thread_context: Slack thread context

        Returns:
            New tool execution context
        """
        # Generate unique execution ID
        execution_id = f"{thread_context.channel_id}_{thread_context.thread_ts}_{datetime.now(timezone.utc).timestamp()}"

        # Clean up old contexts if we're at the limit
        if len(self._active_contexts) >= self._max_contexts:
            self._cleanup_old_contexts()

        # Create new context
        context = ToolExecutionContext(
            user_intent=user_intent,
            thread_context=thread_context,
            execution_id=execution_id,
        )

        self._active_contexts[execution_id] = context
        return context

    def get_context(self, execution_id: str) -> Optional[ToolExecutionContext]:
        """Get an existing context by ID.

        Args:
            execution_id: Context execution ID

        Returns:
            Context if found, None otherwise
        """
        return self._active_contexts.get(execution_id)

    def remove_context(self, execution_id: str) -> bool:
        """Remove a context from management.

        Args:
            execution_id: Context execution ID

        Returns:
            True if context was removed, False if not found
        """
        if execution_id in self._active_contexts:
            del self._active_contexts[execution_id]
            logger.info(f"Removed execution context {execution_id}")
            return True

        return False

    def _cleanup_old_contexts(self) -> None:
        """Clean up old contexts to free memory."""
        # Remove contexts older than 1 hour
        cutoff_time = datetime.now(timezone.utc).timestamp() - 3600

        contexts_to_remove = [
            execution_id
            for execution_id, context in self._active_contexts.items()
            if context.start_time.timestamp() < cutoff_time
        ]

        for execution_id in contexts_to_remove:
            del self._active_contexts[execution_id]

        if contexts_to_remove:
            logger.info(f"Cleaned up {len(contexts_to_remove)} old execution contexts")

    def get_active_context_count(self) -> int:
        """Get the number of active contexts.

        Returns:
            Number of active contexts
        """
        return len(self._active_contexts)


# Global context manager instance
_execution_context_manager: Optional[ExecutionContextManager] = None


def get_execution_context_manager() -> ExecutionContextManager:
    """Get the global execution context manager instance.

    Returns:
        Shared ExecutionContextManager instance
    """
    global _execution_context_manager
    if _execution_context_manager is None:
        _execution_context_manager = ExecutionContextManager()

    return _execution_context_manager
