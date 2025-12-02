"""Tool registry for managing AI agent tools.

This module provides centralized tool registration, configuration management,
and lifecycle control for all AI agent tools.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from llama_index.core.tools import FunctionTool

from .config import ToolsConfiguration
from .config_manager import get_config_manager
from .exceptions import ToolError, ConfigurationError, ErrorCategory, ErrorSeverity
from .logging import get_tool_logger

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing AI agent tools with configuration-driven instantiation.

    This class provides centralized management of all available tools, including
    registration, configuration, lifecycle management, and dependency injection.
    """

    def __init__(self, config_path: str = "config/tools.yaml"):
        """Initialize the tool registry.

        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config_manager = get_config_manager(config_path)
        self.tool_logger = get_tool_logger()

        # Tool storage
        self.tools: Dict[str, FunctionTool] = {}
        self.tool_configs: Dict[str, Dict[str, Any]] = {}
        self.factory_functions: Dict[str, Callable] = {}

        # Dependencies for tool creation
        self.dependencies: Dict[str, Any] = {}

        # Track initialization state
        self._initialized = False

        # Register configuration reload callback
        self.config_manager.add_reload_callback(self._on_config_reload)

        logger.info(f"ToolRegistry initialized with config path: {config_path}")

    def register_factory(
        self,
        category: str,
        factory_function: Callable[
            [Dict[str, Any], Dict[str, Any]], List[FunctionTool]
        ],
    ) -> None:
        """Register a tool factory function for a category.

        Args:
            category: Tool category name (e.g., 'slack_tools', 'openai_tools')
            factory_function: Function that creates tools for the category
        """
        self.factory_functions[category] = factory_function
        logger.info(f"Registered factory for category: {category}")

    def set_dependencies(self, dependencies: Dict[str, Any]) -> None:
        """Set dependencies for tool creation.

        Args:
            dependencies: Dictionary of dependency objects (e.g., API clients)
        """
        self.dependencies.update(dependencies)
        logger.info(f"Updated dependencies: {list(dependencies.keys())}")

    def initialize_tools(self, enable_hot_reload: bool = False) -> List[FunctionTool]:
        """Initialize all configured tools.

        Args:
            enable_hot_reload: Whether to enable configuration hot-reload

        Returns:
            List of initialized tools

        Raises:
            ConfigurationError: If configuration is invalid
            ToolError: If tool initialization fails
        """
        try:
            # Load configuration
            config = self.config_manager.load_configuration(enable_hot_reload)

            # Clear existing tools
            self.tools.clear()
            self.tool_configs.clear()

            # Initialize tools for each enabled category
            total_tools = 0

            if config.slack_tools.enabled and "slack_tools" in self.factory_functions:
                tools = self._create_category_tools(
                    "slack_tools", config.slack_tools, config
                )
                total_tools += len(tools)

            if config.openai_tools.enabled and "openai_tools" in self.factory_functions:
                tools = self._create_category_tools(
                    "openai_tools", config.openai_tools, config
                )
                total_tools += len(tools)

            self._initialized = True

            logger.info(
                f"Initialized {total_tools} tools across {len(self.factory_functions)} categories"
            )
            self.tool_logger.log_config_reload(self.config_path, True)

            return list(self.tools.values())

        except Exception as e:
            error_msg = f"Failed to initialize tools: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.tool_logger.log_config_reload(self.config_path, False, error_msg)

            if isinstance(e, (ConfigurationError, ToolError)):
                raise

            raise ToolError(
                error_msg,
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.CRITICAL,
                recoverable=False,
                user_guidance="Check configuration file and tool dependencies",
            )

    def get_available_tools(self) -> List[FunctionTool]:
        """Get list of all available tools.

        Returns:
            List of available FunctionTool instances
        """
        if not self._initialized:
            logger.warning("Tools not initialized, returning empty list")
            return []

        return list(self.tools.values())

    def get_tool(self, name: str) -> Optional[FunctionTool]:
        """Get a specific tool by name.

        Args:
            name: Tool name

        Returns:
            FunctionTool instance or None if not found
        """
        return self.tools.get(name)

    def get_tool_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific tool.

        Args:
            name: Tool name

        Returns:
            Tool configuration dictionary or None if not found
        """
        return self.tool_configs.get(name)

    def get_enabled_tools(self) -> List[FunctionTool]:
        """Get list of enabled tools only.

        Returns:
            List of enabled tools
        """
        enabled_tools = []
        for name, tool in self.tools.items():
            config = self.tool_configs.get(name, {})
            if config.get("enabled", True):
                enabled_tools.append(tool)

        return enabled_tools

    def get_tools_by_category(self, category: str) -> List[FunctionTool]:
        """Get tools belonging to a specific category.

        Args:
            category: Tool category name

        Returns:
            List of tools in the category
        """
        category_tools = []
        for name, tool in self.tools.items():
            if name.startswith(f"{category}_"):
                category_tools.append(tool)

        return category_tools

    def get_registry_status(self) -> Dict[str, Any]:
        """Get current registry status information.

        Returns:
            Dictionary with registry status
        """
        config = self.config_manager.get_configuration()

        status = {
            "initialized": self._initialized,
            "config_path": str(self.config_path),
            "total_tools": len(self.tools),
            "enabled_tools": len(self.get_enabled_tools()),
            "registered_categories": list(self.factory_functions.keys()),
            "dependencies": list(self.dependencies.keys()),
        }

        if config:
            status.update(
                {
                    "environment": "development",  # Simplified
                    "config_version": "1.0",  # Simplified
                    "tool_categories": {
                        "slack_tools": {
                            "enabled": config.slack_tools.enabled,
                            "tool_count": 0,  # Simplified for now
                        },
                        "openai_tools": {
                            "enabled": config.openai_tools.enabled,
                            "tool_count": len(config.openai_tools.tools),
                        },
                    },
                }
            )

        return status

    def reload_tools(self) -> List[FunctionTool]:
        """Reload tools from configuration.

        Returns:
            List of reloaded tools
        """
        logger.info("Reloading tools from configuration")
        return self.initialize_tools(enable_hot_reload=False)

    def shutdown(self) -> None:
        """Shutdown the tool registry and cleanup resources."""
        logger.info("Shutting down tool registry")

        # Stop hot-reload
        self.config_manager.stop_hot_reload()

        # Clear tools
        self.tools.clear()
        self.tool_configs.clear()

        # Reset state
        self._initialized = False

        logger.info("Tool registry shutdown complete")

    def _create_category_tools(
        self, category: str, category_config: Any, global_config: ToolsConfiguration
    ) -> List[FunctionTool]:
        """Create tools for a specific category.

        Args:
            category: Category name
            category_config: Category-specific configuration
            global_config: Global configuration

        Returns:
            List of created tools
        """
        if category not in self.factory_functions:
            logger.warning(f"No factory function registered for category: {category}")
            return []

        try:
            factory = self.factory_functions[category]
            tools = factory(category_config, self.dependencies, global_config)

            # Register tools in the registry
            for tool in tools:
                tool_name = f"{category}_{tool.metadata.name}"
                self.tools[tool_name] = tool

                # Store tool configuration
                tool_config = getattr(category_config, "tools", {}).get(
                    tool.metadata.name, {}
                )
                if hasattr(tool_config, "dict"):
                    self.tool_configs[tool_name] = tool_config.dict()
                else:
                    self.tool_configs[tool_name] = tool_config

            logger.info(f"Created {len(tools)} tools for category: {category}")
            return tools

        except Exception as e:
            error_msg = f"Failed to create tools for category {category}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            raise ToolError(
                error_msg,
                category=ErrorCategory.SYSTEM_ERROR,
                severity=ErrorSeverity.HIGH,
                recoverable=True,
                user_guidance=f"Check configuration and dependencies for {category} tools",
            )

    def _on_config_reload(self, new_config: ToolsConfiguration) -> None:
        """Handle configuration reload events.

        Args:
            new_config: New configuration object
        """
        logger.info("Configuration reloaded, reinitializing tools")

        try:
            # Reinitialize with new configuration
            old_tool_count = len(self.tools)
            self.reload_tools()
            new_tool_count = len(self.tools)

            logger.info(f"Tools reinitialized: {old_tool_count} -> {new_tool_count}")

        except Exception as e:
            logger.error(f"Failed to reinitialize tools after config reload: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.shutdown()


# Global registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry(config_path: str = "config/tools.yaml") -> ToolRegistry:
    """Get the global tool registry instance.

    Args:
        config_path: Path to configuration file

    Returns:
        Global ToolRegistry instance
    """
    global _tool_registry
    if _tool_registry is None or _tool_registry.config_path != config_path:
        _tool_registry = ToolRegistry(config_path)
    return _tool_registry
