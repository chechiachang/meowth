"""AI Agent Tools module.

This module provides an extensible framework for AI agent tools that can be
automatically selected and executed based on user intent. The system uses
LlamaIndex for tool interfaces and supports manual configuration for tool
registration.

Key Components:
- ToolRegistry: Manages tool registration and configuration
- Tool Factories: Create tool instances with dependency injection
- Configuration Management: YAML-based configuration with hot-reload
- Error Handling: Comprehensive error categorization and user feedback
"""

from .registry import ToolRegistry
from .exceptions import ToolError, ErrorCategory, ErrorSeverity

__all__ = [
    "ToolRegistry",
    "ToolError",
    "ErrorCategory",
    "ErrorSeverity",
]
