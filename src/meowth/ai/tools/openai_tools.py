"""OpenAI-specific AI agent tools.

This module provides tools for OpenAI API interactions,
including message summarization and AI text generation.
"""

import json
from typing import List, Dict, Any

from llama_index.core.tools import FunctionTool

from .exceptions import ToolError, ErrorSeverity, ErrorCategory
from .logging import ToolExecutionLogger
from .base import tool_error_handler


def create_openai_tools(client: Any, config) -> List[FunctionTool]:
    """Create OpenAI tools based on configuration.

    Args:
        client: OpenAI client instance (or similar AI service client)
        config: OpenAI tools configuration (dict or OpenAIToolsConfig)

    Returns:
        List of configured OpenAI tools
    """
    tools: List[FunctionTool] = []

    # Handle both dict and Pydantic model config
    if hasattr(config, "enabled"):
        enabled = config.enabled
    else:
        enabled = config.get("enabled", False)
        
    if not enabled:
        return tools

    logger = ToolExecutionLogger()

    # Get tools configuration
    if hasattr(config, "tools"):
        tools_config = config.tools
    else:
        tools_config = config.get("tools", {})

    # Create summarize_messages tool if enabled
    summarize_config = tools_config.get("summarize_messages", {})
    if summarize_config.get("enabled", False):

        @tool_error_handler(
            error_message="Failed to summarize messages",
            category=ErrorCategory.TOOL_ERROR,
            severity=ErrorSeverity.MEDIUM,
            user_guidance="Please check that the messages are valid and try again",
        )
        async def summarize_messages(messages_json: str, style: str = "brief") -> str:
            """Summarize Slack messages using AI.

            Args:
                messages_json: JSON string containing messages from fetch_messages
                style: Summary style - "brief" or "detailed" (default: "brief")

            Returns:
                Human-readable summary of the messages
            """
            import uuid
            execution_id = str(uuid.uuid4())
            
            try:
                # Parse the messages JSON
                try:
                    messages_data = json.loads(messages_json)
                except json.JSONDecodeError as e:
                    raise ToolError(
                        message=f"Invalid JSON format in messages: {str(e)}",
                        severity=ErrorSeverity.MEDIUM,
                        category=ErrorCategory.DATA_ERROR,
                        tool_name="summarize_messages",
                    )

                # Validate message structure
                if not isinstance(messages_data, dict):
                    raise ToolError(
                        message="Messages data must be a dictionary",
                        severity=ErrorSeverity.MEDIUM,
                        category=ErrorCategory.DATA_ERROR,
                        tool_name="summarize_messages",
                    )

                messages = messages_data.get("messages", [])
                if not isinstance(messages, list):
                    raise ToolError(
                        message="Messages must be a list",
                        severity=ErrorSeverity.MEDIUM,
                        category=ErrorCategory.DATA_ERROR,
                        tool_name="summarize_messages",
                    )

                # Handle empty messages
                if not messages:
                    return "No messages to summarize."

                # For initial implementation, create basic summary without OpenAI
                # This can be enhanced later with actual OpenAI integration
                message_count = len(messages)
                channel = messages_data.get("channel", "unknown")

                # Count unique users
                users = set()
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("user"):
                        users.add(msg["user"])

                user_count = len(users)

                # Extract message texts for basic analysis
                message_texts = []
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("text"):
                        message_texts.append(msg["text"])

                # Create summary based on style
                if style == "detailed":
                    summary = f"""Conversation Summary:

Channel: {channel}
Messages analyzed: {message_count}
Participants: {user_count} users
Time range: Recent conversation

Key highlights:
- {message_count} messages exchanged between {user_count} participants
- Discussion took place in channel {channel}
- Messages include various topics and interactions

This is a basic summary. Enhanced AI summarization coming soon."""

                else:  # brief style (default)
                    summary = f"Conversation summary: {message_count} messages from {user_count} users in {channel}. Recent discussion captured."

                # Log successful execution
                logger.log_tool_success(
                    tool_name="summarize_messages",
                    execution_id=execution_id,
                    result_length=len(summary) if summary else 0,
                    user_id=None,
                    channel_id=None,
                )
                
                return summary

            except ToolError:
                # Re-raise ToolErrors as-is
                raise

            except Exception as e:
                tool_error = ToolError(
                    message=f"Error summarizing messages: {str(e)}",
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.INTERNAL_ERROR,
                    tool_name="summarize_messages",
                    context={"original_error": str(e)},
                )

                await logger.log_execution_error(
                    tool_name="summarize_messages", error=tool_error
                )

                # Return user-friendly error message instead of raising
                return "Error summarizing messages. Please try again or contact support if the issue persists."

        # Create LlamaIndex FunctionTool
        summarize_tool = FunctionTool.from_defaults(
            fn=summarize_messages,
            name="summarize_messages",
            description=summarize_config.get(
                "description", "Generate a summary of Slack messages using AI analysis"
            ),
        )

        tools.append(summarize_tool)

    return tools


async def validate_openai_configuration(config: Dict[str, Any]) -> bool:
    """Validate OpenAI configuration completeness.

    Args:
        config: OpenAI configuration dictionary

    Returns:
        True if configuration is valid

    Raises:
        ToolError: If configuration is invalid
    """
    if not config.get("enabled", False):
        return True

    # Check model configuration
    model_config = config.get("model_config", {})
    if not model_config:
        raise ToolError(
            message="Model configuration is required when OpenAI tools are enabled",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.CONFIGURATION_ERROR,
        )

    # Check for required model settings
    if not model_config.get("default_model"):
        raise ToolError(
            message="Default model must be specified in model configuration",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.CONFIGURATION_ERROR,
        )

    # Validate tool configurations
    tools_config = config.get("tools", {})
    if tools_config:
        for tool_name, tool_config in tools_config.items():
            if tool_config.get("enabled", False) and not tool_config.get("description"):
                # Warning: missing description, but not critical
                pass

    return True


async def enhance_with_openai_integration(
    client: Any, model_config: Dict[str, Any]
) -> bool:
    """Enhanced OpenAI integration for future implementation.

    This function is a placeholder for future OpenAI API integration
    that will provide actual AI-powered summarization.

    Args:
        client: OpenAI client instance
        model_config: Model configuration settings

    Returns:
        True if integration is successful
    """
    # TODO: Implement actual OpenAI API integration
    # - Use client to make API calls
    # - Apply model_config settings (temperature, max_tokens, etc.)
    # - Handle OpenAI-specific errors and rate limiting
    # - Implement token counting and cost management

    # For now, return True indicating basic functionality
    return True
