"""Slack-specific AI agent tools.

This module provides tools for interacting with Slack APIs,
including message fetching with rate limiting and error handling.
"""

import json
from typing import List, Dict, Any
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from llama_index.core.tools import FunctionTool

from .exceptions import ToolError, ErrorSeverity, ErrorCategory
from .rate_limiter import SlackRateLimiter
from .logging import ToolExecutionLogger
from .base import tool_error_handler


def create_slack_tools(client: WebClient, config: Dict[str, Any]) -> List[FunctionTool]:
    """Create Slack tools based on configuration.

    Args:
        client: Slack WebClient instance
        config: Slack tools configuration dictionary

    Returns:
        List of configured Slack tools
    """
    tools: List[FunctionTool] = []

    if not config.get("enabled", False):
        return tools

    # Initialize rate limiter
    rate_limiter = SlackRateLimiter()
    logger = ToolExecutionLogger()

    # Create fetch_messages tool if enabled
    fetch_config = config.get("fetch_messages", {})
    if fetch_config.get("enabled", False):

        @tool_error_handler
        async def fetch_messages(channel_id: str, count: int = 10) -> str:
            """Fetch recent messages from a Slack channel.

            Args:
                channel_id: The ID of the Slack channel to fetch messages from
                count: Number of messages to fetch (default: 10, max: 100)

            Returns:
                JSON string containing messages and metadata
            """
            # Validate inputs
            if not channel_id:
                raise ToolError(
                    message="Channel ID cannot be empty",
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.VALIDATION_ERROR,
                    tool_name="fetch_messages",
                )

            if not isinstance(count, int) or count < 1:
                raise ToolError(
                    message="Count must be a positive integer",
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.VALIDATION_ERROR,
                    tool_name="fetch_messages",
                )

            # Enforce reasonable limits
            count = min(count, 100)

            try:
                # Check rate limiting
                await rate_limiter.check_rate_limit("conversations.history")

                # Log tool execution start
                await logger.log_execution_start(
                    tool_name="fetch_messages",
                    parameters={"channel_id": channel_id, "count": count},
                )

                # Fetch messages from Slack
                response = client.conversations_history(
                    channel=channel_id, limit=count, inclusive=True
                )

                # Process messages
                messages = response.get("messages", [])
                processed_messages = []

                for msg in messages:
                    processed_msg = {
                        "text": msg.get("text", ""),
                        "user": msg.get("user", "unknown"),
                        "timestamp": msg.get("ts", ""),
                        "type": msg.get("type", "message"),
                    }

                    # Include thread information if available
                    if msg.get("thread_ts"):
                        processed_msg["thread_ts"] = msg.get("thread_ts")

                    processed_messages.append(processed_msg)

                # Prepare result
                result = {
                    "messages": processed_messages,
                    "channel": channel_id,
                    "total_fetched": len(processed_messages),
                    "fetch_timestamp": datetime.utcnow().isoformat(),
                }

                result_json = json.dumps(result, ensure_ascii=False, indent=2)

                # Log successful execution
                await logger.log_execution_success(
                    tool_name="fetch_messages",
                    result=f"Fetched {len(processed_messages)} messages",
                )

                return result_json

            except SlackApiError as e:
                error_code = e.response.get("error", "unknown_error")

                # Map Slack errors to our error categories
                if error_code in ["invalid_auth", "token_revoked"]:
                    category = ErrorCategory.AUTHENTICATION_ERROR
                    severity = ErrorSeverity.CRITICAL
                elif error_code in ["channel_not_found", "not_in_channel"]:
                    category = ErrorCategory.PERMISSION_ERROR
                    severity = ErrorSeverity.HIGH
                elif error_code == "rate_limited":
                    category = ErrorCategory.RATE_LIMIT_ERROR
                    severity = ErrorSeverity.MEDIUM
                else:
                    category = ErrorCategory.EXTERNAL_SERVICE_ERROR
                    severity = ErrorSeverity.HIGH

                # Update rate limiter on errors
                if error_code == "rate_limited":
                    await rate_limiter.record_rate_limit_hit()

                tool_error = ToolError(
                    message=f"Slack API error: {error_code} - {e.response.get('error', 'Unknown error')}",
                    severity=severity,
                    category=category,
                    tool_name="fetch_messages",
                    details={"slack_error": error_code, "channel_id": channel_id},
                )

                await logger.log_execution_error(
                    tool_name="fetch_messages", error=tool_error
                )

                raise tool_error

            except Exception as e:
                tool_error = ToolError(
                    message=f"Unexpected error fetching messages: {str(e)}",
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.INTERNAL_ERROR,
                    tool_name="fetch_messages",
                )

                await logger.log_execution_error(
                    tool_name="fetch_messages", error=tool_error
                )

                raise tool_error

        # Create LlamaIndex FunctionTool
        fetch_tool = FunctionTool.from_defaults(
            fn=fetch_messages,
            name="fetch_messages",
            description=fetch_config.get(
                "description",
                "Fetch recent messages from a Slack channel for analysis or summarization",
            ),
        )

        tools.append(fetch_tool)

    return tools


async def validate_slack_configuration(config: Dict[str, Any]) -> bool:
    """Validate Slack configuration completeness.

    Args:
        config: Slack configuration dictionary

    Returns:
        True if configuration is valid

    Raises:
        ToolError: If configuration is invalid
    """
    if not config.get("enabled", False):
        return True

    # Check required fields
    if not config.get("bot_token"):
        raise ToolError(
            message="Slack bot token is required when Slack tools are enabled",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.CONFIGURATION_ERROR,
        )

    # Validate fetch_messages configuration
    fetch_config = config.get("fetch_messages", {})
    if fetch_config.get("enabled", False):
        if "description" not in fetch_config:
            # This is a warning, not an error - we'll use default
            pass

    return True
