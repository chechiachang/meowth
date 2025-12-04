"""Logging configuration for AI agent tool execution tracking.

This module provides structured logging for tool execution, performance
monitoring, and debugging capabilities.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from .exceptions import ToolError, ErrorCategory, ErrorSeverity


class ToolExecutionFormatter(logging.Formatter):
    """Custom formatter for tool execution logs."""

    def format(self, record):
        """Format log record with tool-specific information."""
        # Create base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add tool-specific fields if available
        if hasattr(record, "tool_name"):
            log_entry["tool_name"] = record.tool_name
        if hasattr(record, "execution_id"):
            log_entry["execution_id"] = record.execution_id
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "channel_id"):
            log_entry["channel_id"] = record.channel_id
        if hasattr(record, "execution_time"):
            log_entry["execution_time"] = record.execution_time
        if hasattr(record, "error_category"):
            log_entry["error_category"] = record.error_category
        if hasattr(record, "error_severity"):
            log_entry["error_severity"] = record.error_severity

        # Add extra fields from record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
            }:
                if not key.startswith("_") and key not in log_entry:
                    extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry)


class ToolExecutionLogger:
    """Specialized logger for tool execution tracking."""

    def __init__(self, name: str = "meowth.ai.tools"):
        """Initialize the tool execution logger.

        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(name)
        self.execution_times = {}

    def log_tool_start(
        self,
        tool_name: str,
        execution_id: str,
        parameters: Dict[str, Any],
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> None:
        """Log the start of tool execution.

        Args:
            tool_name: Name of the tool being executed
            execution_id: Unique execution identifier
            parameters: Tool execution parameters
            user_id: User who triggered the execution
            channel_id: Channel where execution was triggered
        """
        self.execution_times[execution_id] = time.time()

        self.logger.info(
            f"Tool execution started: {tool_name}",
            extra={
                "tool_name": tool_name,
                "execution_id": execution_id,
                "user_id": user_id,
                "channel_id": channel_id,
                "parameters": self._sanitize_parameters(parameters),
                "event_type": "tool_start",
            },
        )

    def log_tool_success(
        self,
        tool_name: str,
        execution_id: str,
        result_length: int = 0,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> None:
        """Log successful tool execution.

        Args:
            tool_name: Name of the tool
            execution_id: Unique execution identifier
            result_length: Length of the result data
            user_id: User who triggered the execution
            channel_id: Channel where execution was triggered
        """
        execution_time = self._calculate_execution_time(execution_id)

        self.logger.info(
            f"Tool execution completed: {tool_name}",
            extra={
                "tool_name": tool_name,
                "execution_id": execution_id,
                "user_id": user_id,
                "channel_id": channel_id,
                "execution_time": execution_time,
                "result_length": result_length,
                "event_type": "tool_success",
            },
        )

    def log_tool_error(
        self,
        tool_name: str,
        execution_id: str,
        error: Exception,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> None:
        """Log tool execution error.

        Args:
            tool_name: Name of the tool
            execution_id: Unique execution identifier
            error: Exception that occurred
            user_id: User who triggered the execution
            channel_id: Channel where execution was triggered
        """
        execution_time = self._calculate_execution_time(execution_id)

        # Extract error details
        if isinstance(error, ToolError):
            error_category = error.category.value
            error_severity = error.severity.value
            error_context = error.context
        else:
            error_category = ErrorCategory.SYSTEM_ERROR.value
            error_severity = ErrorSeverity.MEDIUM.value
            error_context = {"error_type": type(error).__name__}

        self.logger.error(
            f"Tool execution failed: {tool_name} - {str(error)}",
            extra={
                "tool_name": tool_name,
                "execution_id": execution_id,
                "user_id": user_id,
                "channel_id": channel_id,
                "execution_time": execution_time,
                "error_category": error_category,
                "error_severity": error_severity,
                "error_message": str(error),
                "error_context": error_context,
                "event_type": "tool_error",
            },
            exc_info=True,
        )

    async def log_execution_error(
        self,
        tool_name: str,
        execution_id: str,
        error: Exception,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> None:
        """Log tool execution error (async version).

        Args:
            tool_name: Name of the tool
            execution_id: Unique execution identifier
            error: Exception that occurred
            user_id: User who triggered the execution
            channel_id: Channel where execution was triggered
        """
        self.log_tool_error(tool_name, execution_id, error, user_id, channel_id)

    def log_rate_limit(
        self, endpoint: str, wait_time: float, tool_name: Optional[str] = None
    ) -> None:
        """Log rate limiting events.

        Args:
            endpoint: API endpoint that hit rate limit
            wait_time: Time to wait before retry
            tool_name: Tool that triggered rate limit
        """
        self.logger.warning(
            f"Rate limit hit for {endpoint}, wait time: {wait_time}s",
            extra={
                "endpoint": endpoint,
                "wait_time": wait_time,
                "tool_name": tool_name,
                "event_type": "rate_limit",
            },
        )

    def log_config_reload(
        self, config_path: str, success: bool, error: Optional[str] = None
    ) -> None:
        """Log configuration reload events.

        Args:
            config_path: Path to configuration file
            success: Whether reload was successful
            error: Error message if reload failed
        """
        level = logging.INFO if success else logging.ERROR
        message = (
            f"Configuration {'reloaded' if success else 'reload failed'}: {config_path}"
        )

        extra = {
            "config_path": config_path,
            "reload_success": success,
            "event_type": "config_reload",
        }

        if error:
            extra["error_message"] = error

        self.logger.log(level, message, extra=extra)

    def log_circuit_breaker(
        self,
        endpoint: str,
        state: str,
        failure_count: int,
        tool_name: Optional[str] = None,
    ) -> None:
        """Log circuit breaker state changes.

        Args:
            endpoint: API endpoint
            state: Circuit breaker state (open, closed, half-open)
            failure_count: Number of consecutive failures
            tool_name: Tool that triggered circuit breaker
        """
        self.logger.warning(
            f"Circuit breaker {state} for {endpoint}, failures: {failure_count}",
            extra={
                "endpoint": endpoint,
                "circuit_state": state,
                "failure_count": failure_count,
                "tool_name": tool_name,
                "event_type": "circuit_breaker",
            },
        )

    def _calculate_execution_time(self, execution_id: str) -> float:
        """Calculate execution time for a tool.

        Args:
            execution_id: Execution identifier

        Returns:
            Execution time in seconds
        """
        start_time = self.execution_times.pop(execution_id, None)
        if start_time:
            return time.time() - start_time
        return 0.0

    def _sanitize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize parameters for logging (remove sensitive data).

        Args:
            parameters: Original parameters

        Returns:
            Sanitized parameters safe for logging
        """
        sanitized = {}
        sensitive_keys = {"token", "api_key", "password", "secret", "credential"}

        for key, value in parameters.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 1000:
                # Truncate very long strings
                sanitized[key] = value[:1000] + "... [TRUNCATED]"
            else:
                sanitized[key] = value

        return sanitized


def setup_tool_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_json_logging: bool = True,
) -> None:
    """Setup logging configuration for AI agent tools.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        enable_json_logging: Whether to use JSON formatting
    """
    # Get the tools logger
    logger = logging.getLogger("meowth.ai.tools")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatter
    if enable_json_logging:
        formatter = ToolExecutionFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.info(
        f"Tool logging configured - Level: {log_level}, JSON: {enable_json_logging}"
    )


# Global logger instance
_tool_logger: Optional[ToolExecutionLogger] = None


def get_tool_logger() -> ToolExecutionLogger:
    """Get the global tool execution logger.

    Returns:
        Global ToolExecutionLogger instance
    """
    global _tool_logger
    if _tool_logger is None:
        _tool_logger = ToolExecutionLogger()
    return _tool_logger
