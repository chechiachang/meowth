"""Base tool interface contracts and validation decorators.

This module provides the foundation for all AI agent tools including
interface contracts, validation decorators, and common functionality.
"""

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Dict, Optional, TypeVar
from llama_index.core.tools import FunctionTool

from .exceptions import (
    ToolError,
    ErrorCategory,
    ErrorSeverity,
    TimeoutError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def tool_error_handler(
    error_message: str,
    category: ErrorCategory = ErrorCategory.TOOL_ERROR,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    user_guidance: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator for consistent tool error handling.

    This decorator wraps tool functions to provide consistent error handling,
    logging, and user feedback for tool execution failures.

    Args:
        error_message: Base error message for tool failures
        category: Error category for this tool
        severity: Default severity level
        user_guidance: User guidance for error recovery

    Returns:
        Decorated function with error handling
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tool_name = getattr(func, "__name__", "unknown_tool")
            start_time = time.time()

            try:
                logger.debug(f"Starting tool execution: {tool_name}")
                result = await func(*args, **kwargs)

                execution_time = time.time() - start_time
                logger.info(
                    f"Tool {tool_name} completed successfully in {execution_time:.2f}s"
                )

                return result

            except ToolError:
                # Re-raise ToolError instances without modification
                raise
            except asyncio.TimeoutError:
                execution_time = time.time() - start_time
                logger.error(f"Tool {tool_name} timed out after {execution_time:.2f}s")
                raise TimeoutError(
                    f"Tool execution timed out: {error_message}",
                    timeout_seconds=execution_time,
                    tool_name=tool_name,
                    user_guidance=user_guidance
                    or "Try reducing the scope of your request or try again later",
                )
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Tool {tool_name} failed after {execution_time:.2f}s: {str(e)}"
                )

                raise ToolError(
                    f"{error_message}: {str(e)}",
                    category=category,
                    severity=severity,
                    tool_name=tool_name,
                    user_guidance=user_guidance
                    or "Please try again or contact support if the issue persists",
                    context={
                        "execution_time": execution_time,
                        "original_error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, convert to async
            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def validate_tool_config(
    required_fields: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """Decorator to validate tool configuration.

    Args:
        required_fields: Dictionary of required configuration fields and their types

    Returns:
        Decorated function with configuration validation
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tool_name = getattr(func, "__name__", "unknown_tool")

            # Extract config from kwargs if present
            config = kwargs.get("config", {})

            if required_fields:
                for field_name, field_type in required_fields.items():
                    if field_name not in config:
                        raise ConfigurationError(
                            f"Missing required configuration field '{field_name}' for tool {tool_name}",
                            tool_name=tool_name,
                            user_guidance=f"Add '{field_name}' to tool configuration",
                        )

                    if not isinstance(config[field_name], field_type):
                        raise ConfigurationError(
                            f"Invalid type for configuration field '{field_name}' in tool {tool_name}. "
                            f"Expected {field_type.__name__}, got {type(config[field_name]).__name__}",
                            tool_name=tool_name,
                            user_guidance=f"Fix the type of '{field_name}' in tool configuration",
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def timeout_control(timeout_seconds: Optional[float] = None) -> Callable[[F], F]:
    """Decorator to add timeout control to tool functions.

    Args:
        timeout_seconds: Timeout in seconds, or None to use config default

    Returns:
        Decorated function with timeout control
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get timeout from decorator, kwargs, or default
            actual_timeout = timeout_seconds
            if actual_timeout is None:
                actual_timeout = kwargs.pop("timeout_seconds", 30.0)

            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), timeout=actual_timeout
                )
            except asyncio.TimeoutError:
                tool_name = getattr(func, "__name__", "unknown_tool")
                raise TimeoutError(
                    f"Tool {tool_name} execution timed out after {actual_timeout} seconds",
                    timeout_seconds=actual_timeout,
                    tool_name=tool_name,
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class BaseToolInterface:
    """Base interface for all AI agent tools.

    This class provides common functionality and interface contracts
    that all tools should implement or inherit from.
    """

    def __init__(
        self, name: str, description: str, config: Optional[Dict[str, Any]] = None
    ):
        """Initialize the base tool interface.

        Args:
            name: Tool name (unique identifier)
            description: Tool description for LLM understanding
            config: Tool-specific configuration
        """
        self.name = name
        self.description = description
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

    def validate_parameters(self, **kwargs) -> Dict[str, Any]:
        """Validate tool parameters before execution.

        Args:
            **kwargs: Tool parameters to validate

        Returns:
            Validated parameters

        Raises:
            ToolError: If parameters are invalid
        """
        # Base implementation - subclasses should override
        return kwargs

    def get_metadata(self) -> Dict[str, Any]:
        """Get tool metadata for LlamaIndex integration.

        Returns:
            Dictionary containing tool metadata
        """
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "config": self.config,
        }

    async def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters.

        This is the main execution method that should be implemented
        by concrete tool classes.

        Args:
            **kwargs: Tool execution parameters

        Returns:
            Tool execution result as string

        Raises:
            ToolError: If execution fails
        """
        raise NotImplementedError("Subclasses must implement execute method")

    def to_llama_index_tool(self) -> FunctionTool:
        """Convert to LlamaIndex FunctionTool.

        Returns:
            FunctionTool instance for LlamaIndex integration
        """
        return FunctionTool.from_defaults(
            async_fn=self.execute, name=self.name, description=self.description
        )


def create_tool_function(
    name: str, description: str, func: Callable, config: Optional[Dict[str, Any]] = None
) -> FunctionTool:
    """Create a LlamaIndex FunctionTool from a function.

    This is a helper function for creating tools from async functions
    with proper error handling and metadata.

    Args:
        name: Tool name
        description: Tool description for LLM
        func: Async function to wrap
        config: Tool configuration

    Returns:
        FunctionTool instance
    """
    # Add tool metadata to function
    func.__name__ = name
    func.__doc__ = description

    return FunctionTool.from_defaults(async_fn=func, name=name, description=description)


def log_tool_execution(func: F) -> F:
    """Decorator to log tool execution details.

    Args:
        func: Function to decorate

    Returns:
        Decorated function with execution logging
    """

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        tool_name = getattr(func, "__name__", "unknown_tool")
        start_time = time.time()

        # Log start
        logger.info(f"Tool execution started: {tool_name}")
        logger.debug(f"Tool parameters: {kwargs}")

        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time

            # Log success
            logger.info(
                f"Tool execution completed: {tool_name} ({execution_time:.2f}s)"
            )
            logger.debug(
                f"Tool result length: {len(str(result)) if result else 0} characters"
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Tool execution failed: {tool_name} ({execution_time:.2f}s) - {str(e)}"
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        return asyncio.run(async_wrapper(*args, **kwargs))

    # Return appropriate wrapper
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
