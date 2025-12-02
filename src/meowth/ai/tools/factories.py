"""Tool factories for dependency injection.

This module provides factories for creating tool instances with
proper dependency injection and configuration management.
"""

from typing import List, Dict, Any, Optional

from slack_sdk import WebClient
from llama_index.core.tools import FunctionTool

from .exceptions import ToolError, ErrorSeverity, ErrorCategory
from .slack_tools import create_slack_tools, validate_slack_configuration
from .openai_tools import create_openai_tools, validate_openai_configuration
from .logging import ToolExecutionLogger


class SlackToolsFactory:
    """Factory for creating Slack tools with dependency injection."""

    def __init__(self, bot_token: Optional[str] = None):
        """Initialize Slack tools factory.

        Args:
            bot_token: Slack bot token for API authentication
        """
        self.bot_token = bot_token
        self._client = None
        self.logger = ToolExecutionLogger()

    async def create_client(self) -> WebClient:
        """Create or return existing Slack WebClient.

        Returns:
            Configured Slack WebClient instance

        Raises:
            ToolError: If client creation fails
        """
        if self._client is None:
            if not self.bot_token:
                raise ToolError(
                    message="Slack bot token is required to create client",
                    severity=ErrorSeverity.CRITICAL,
                    category=ErrorCategory.CONFIGURATION_ERROR,
                )

            try:
                self._client = WebClient(token=self.bot_token)

                # Test the connection
                test_response = self._client.auth_test()
                if not test_response.get("ok"):
                    raise ToolError(
                        message="Slack authentication failed",
                        severity=ErrorSeverity.CRITICAL,
                        category=ErrorCategory.AUTHENTICATION_ERROR,
                        details={"response": test_response},
                    )

                await self.logger.log_info(
                    "Slack client created successfully",
                    details={"bot_id": test_response.get("bot_id")},
                )

            except Exception as e:
                if isinstance(e, ToolError):
                    raise

                raise ToolError(
                    message=f"Failed to create Slack client: {str(e)}",
                    severity=ErrorSeverity.CRITICAL,
                    category=ErrorCategory.EXTERNAL_SERVICE_ERROR,
                    details={"original_error": str(e)},
                )

        return self._client

    async def create_tools(self, config: Dict[str, Any]) -> List[FunctionTool]:
        """Create Slack tools based on configuration.

        Args:
            config: Slack tools configuration

        Returns:
            List of configured Slack tools

        Raises:
            ToolError: If tool creation fails
        """
        try:
            # Validate configuration
            await validate_slack_configuration(config)

            if not config.get("enabled", False):
                await self.logger.log_info("Slack tools disabled by configuration")
                return []

            # Create client if needed
            if config.get("bot_token"):
                self.bot_token = config["bot_token"]

            client = await self.create_client()

            # Create tools
            tools = create_slack_tools(client, config)

            await self.logger.log_info(
                f"Created {len(tools)} Slack tools",
                details={"tool_names": [tool.metadata.name for tool in tools]},
            )

            return tools

        except Exception as e:
            if isinstance(e, ToolError):
                await self.logger.log_error(f"Slack tools creation failed: {e.message}")
                raise

            tool_error = ToolError(
                message=f"Unexpected error creating Slack tools: {str(e)}",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.INTERNAL_ERROR,
                details={"original_error": str(e)},
            )

            await self.logger.log_error(
                f"Slack tools creation failed: {tool_error.message}"
            )
            raise tool_error

    async def cleanup(self):
        """Clean up factory resources."""
        if self._client:
            # Slack WebClient doesn't need explicit cleanup
            self._client = None

        await self.logger.log_info("Slack tools factory cleaned up")


class OpenAIToolsFactory:
    """Factory for creating OpenAI tools with dependency injection."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenAI tools factory.

        Args:
            api_key: OpenAI API key for authentication
        """
        self.api_key = api_key
        self._client = None
        self.logger = ToolExecutionLogger()

    async def create_client(self, model_config: Dict[str, Any]) -> Any:
        """Create or return existing OpenAI client.

        Args:
            model_config: Model configuration settings

        Returns:
            Configured OpenAI client instance

        Raises:
            ToolError: If client creation fails
        """
        if self._client is None:
            try:
                # For initial implementation, use a mock client
                # TODO: Replace with actual OpenAI client when integrating

                class MockOpenAIClient:
                    def __init__(self, api_key: str, model_config: Dict[str, Any]):
                        self.api_key = api_key
                        self.model_config = model_config

                    async def validate_connection(self) -> bool:
                        # Mock validation - always returns True for now
                        return True

                if not self.api_key:
                    raise ToolError(
                        message="OpenAI API key is required to create client",
                        severity=ErrorSeverity.CRITICAL,
                        category=ErrorCategory.CONFIGURATION_ERROR,
                    )

                self._client = MockOpenAIClient(self.api_key, model_config)

                # Test the connection
                is_valid = await self._client.validate_connection()
                if not is_valid:
                    raise ToolError(
                        message="OpenAI client validation failed",
                        severity=ErrorSeverity.CRITICAL,
                        category=ErrorCategory.AUTHENTICATION_ERROR,
                    )

                await self.logger.log_info(
                    "OpenAI client created successfully",
                    details={"model": model_config.get("default_model")},
                )

            except Exception as e:
                if isinstance(e, ToolError):
                    raise

                raise ToolError(
                    message=f"Failed to create OpenAI client: {str(e)}",
                    severity=ErrorSeverity.CRITICAL,
                    category=ErrorCategory.EXTERNAL_SERVICE_ERROR,
                    details={"original_error": str(e)},
                )

        return self._client

    async def create_tools(self, config: Dict[str, Any]) -> List[FunctionTool]:
        """Create OpenAI tools based on configuration.

        Args:
            config: OpenAI tools configuration

        Returns:
            List of configured OpenAI tools

        Raises:
            ToolError: If tool creation fails
        """
        try:
            # Validate configuration
            await validate_openai_configuration(config)

            if not config.get("enabled", False):
                await self.logger.log_info("OpenAI tools disabled by configuration")
                return []

            # Extract credentials from config if provided
            if config.get("api_key"):
                self.api_key = config["api_key"]

            model_config = config.get("model_config_data", {})
            client = await self.create_client(model_config)

            # Create tools
            tools = create_openai_tools(client, config)

            await self.logger.log_info(
                f"Created {len(tools)} OpenAI tools",
                details={"tool_names": [tool.metadata.name for tool in tools]},
            )

            return tools

        except Exception as e:
            if isinstance(e, ToolError):
                await self.logger.log_error(
                    f"OpenAI tools creation failed: {e.message}"
                )
                raise

            tool_error = ToolError(
                message=f"Unexpected error creating OpenAI tools: {str(e)}",
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.INTERNAL_ERROR,
                details={"original_error": str(e)},
            )

            await self.logger.log_error(
                f"OpenAI tools creation failed: {tool_error.message}"
            )
            raise tool_error

    async def cleanup(self):
        """Clean up factory resources."""
        if self._client:
            # OpenAI client cleanup (if needed)
            self._client = None

        await self.logger.log_info("OpenAI tools factory cleaned up")


class ToolsFactoryManager:
    """Manager for coordinating multiple tool factories."""

    def __init__(self):
        """Initialize tools factory manager."""
        self.slack_factory = None
        self.openai_factory = None
        self.logger = ToolExecutionLogger()

    async def initialize_factories(self, config: Dict[str, Any]):
        """Initialize all tool factories with configuration.

        Args:
            config: Complete tools configuration
        """
        try:
            # Initialize Slack factory
            slack_config = config.get("slack_tools", {})
            if slack_config.get("enabled", False):
                bot_token = slack_config.get("bot_token")
                self.slack_factory = SlackToolsFactory(bot_token)

            # Initialize OpenAI factory
            openai_config = config.get("openai_tools", {})
            if openai_config.get("enabled", False):
                api_key = openai_config.get("api_key")
                self.openai_factory = OpenAIToolsFactory(api_key)

            await self.logger.log_info(
                "Tool factories initialized",
                details={
                    "slack_enabled": self.slack_factory is not None,
                    "openai_enabled": self.openai_factory is not None,
                },
            )

        except Exception as e:
            await self.logger.log_error(f"Factory initialization failed: {str(e)}")
            raise

    async def create_all_tools(self, config: Dict[str, Any]) -> List[FunctionTool]:
        """Create all tools from all factories.

        Args:
            config: Complete tools configuration

        Returns:
            List of all created tools
        """
        all_tools = []

        try:
            # Create Slack tools
            if self.slack_factory:
                slack_config = config.get("slack_tools", {})
                slack_tools = await self.slack_factory.create_tools(slack_config)
                all_tools.extend(slack_tools)

            # Create OpenAI tools
            if self.openai_factory:
                openai_config = config.get("openai_tools", {})
                openai_tools = await self.openai_factory.create_tools(openai_config)
                all_tools.extend(openai_tools)

            await self.logger.log_info(
                f"Created {len(all_tools)} total tools",
                details={"tool_names": [tool.metadata.name for tool in all_tools]},
            )

            return all_tools

        except Exception as e:
            await self.logger.log_error(f"Tool creation failed: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up all factories."""
        try:
            if self.slack_factory:
                await self.slack_factory.cleanup()

            if self.openai_factory:
                await self.openai_factory.cleanup()

            await self.logger.log_info("All tool factories cleaned up")

        except Exception as e:
            await self.logger.log_error(f"Factory cleanup failed: {str(e)}")
            raise
