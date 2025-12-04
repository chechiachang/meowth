"""Slack-specific AI agent tools.

This module provides tools for interacting with Slack APIs,
including message fetching with rate limiting and error handling.
"""

import json
from typing import List, Dict, Any
from datetime import datetime, timezone

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from llama_index.core.tools import FunctionTool

from .exceptions import ToolError, ErrorSeverity, ErrorCategory
from .rate_limiter import SlackRateLimiter
from .logging import ToolExecutionLogger
from .base import tool_error_handler


def create_slack_tools(client: WebClient, config) -> List[FunctionTool]:
    """Create Slack tools based on configuration.

    Args:
        client: Slack WebClient instance
        config: Slack tools configuration (dict or SlackToolsConfig)

    Returns:
        List of configured Slack tools
    """
    tools: List[FunctionTool] = []

    # Handle both dict and Pydantic model config
    if hasattr(config, "enabled"):
        enabled = config.enabled
    else:
        enabled = config.get("enabled", False)
        
    if not enabled:
        return tools

    # Initialize rate limiter
    rate_limiter = SlackRateLimiter()
    logger = ToolExecutionLogger()

    # Get tools configuration
    if hasattr(config, "tools"):
        tools_config = config.tools
    else:
        tools_config = config.get("tools", {})

    # Create fetch_messages tool if enabled
    fetch_config = tools_config.get("fetch_messages", {})
    if fetch_config.get("enabled", False):

        default_limit = fetch_config.get("default_limit", 10)
        
        @tool_error_handler(
            error_message="Failed to fetch Slack messages",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            user_guidance="Please check the channel ID and try again",
        )
        async def fetch_messages(channel_id: str, limit: int = default_limit) -> str:
            """Fetch recent messages from a Slack channel.

            Args:
                channel_id: The ID of the Slack channel to fetch messages from
                limit: Number of messages to fetch (default: 10, max: 100)

            Returns:
                JSON string containing messages and metadata
            """
            import uuid
            execution_id = str(uuid.uuid4())
            
            # Validate inputs
            if not channel_id:
                raise ToolError(
                    message="Channel ID cannot be empty",
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.INVALID_INPUT,
                    tool_name="fetch_messages",
                )

            if not isinstance(limit, int) or limit < 1:
                raise ToolError(
                    message="Limit must be a positive integer",
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.INVALID_INPUT,
                    tool_name="fetch_messages",
                )

            # Enforce configured limits
            max_messages = fetch_config.get("max_messages", 100)
            limit = min(limit, max_messages)

            try:
                # Fetch messages from Slack
                response = client.conversations_history(
                    channel=channel_id, limit=limit, inclusive=True
                )

                # Process messages
                messages: list[dict] = response.get("messages", [])
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
                    "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
                }

                result_json = json.dumps(result, ensure_ascii=False, indent=2)

                # Log successful execution
                logger.log_tool_success(
                    tool_name="fetch_messages",
                    execution_id=execution_id,
                    result_length=len(result_json) if result_json else 0,
                    user_id=None,
                    channel_id=channel_id,
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
                    context={"slack_error": error_code, "channel_id": channel_id},
                )

                await logger.log_execution_error(
                    execution_id=execution_id,
                    tool_name="fetch_messages", 
                    error=tool_error
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
                    execution_id=execution_id,
                    tool_name="fetch_messages", 
                    error=tool_error
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
