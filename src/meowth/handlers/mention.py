"""Mention event handler for processing app_mention events with AI agent integration."""

import logging
import uuid
from typing import Dict, Any, Set, Optional

from ..models import MentionEvent, ResponseMessage
from ..ai.models import ThreadContext
from ..ai.agent import LlamaIndexAgentWrapper
from ..ai.tools.registry import ToolRegistry
from ..ai.tools.error_handler import get_error_handler, ToolError
from ..ai.auto_selection import create_auto_tool_selector, AutoToolSelector


class MentionHandler:
    """Handler for processing Slack app_mention events with AI agent and tool integration."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None) -> None:
        """Initialize the mention handler with AI agent and tool registry.

        Args:
            tool_registry: Optional tool registry for AI capabilities
        """
        self.processed_channels: Set[str] = set()
        self.logger = logging.getLogger("meowth.handlers.mention")

        # Initialize AI agent and tools
        self.tool_registry = tool_registry
        self.ai_agent: Optional[LlamaIndexAgentWrapper] = None
        self.auto_tool_selector: Optional[AutoToolSelector] = None
        self.error_handler = get_error_handler()

        if self.tool_registry:
            try:
                # Initialize tools and agent
                tools = self.tool_registry.initialize_tools()
                self.ai_agent = LlamaIndexAgentWrapper()
                self.ai_agent.set_tools(tools)

                # Initialize automatic tool selector
                self.auto_tool_selector = create_auto_tool_selector(self.tool_registry)

                self.logger.info(
                    f"AI agent initialized with {len(tools)} tools and automatic selection"
                )
            except Exception as e:
                self.logger.error(f"Failed to initialize AI agent: {e}")
                self.ai_agent = None
                self.auto_tool_selector = None

    def validate_mention_event(self, event_data: Dict[str, Any]) -> MentionEvent:
        """Validate and create MentionEvent from Slack event data."""
        channel_id = event_data["channel"]

        # Track channel for multi-channel awareness
        if channel_id not in self.processed_channels:
            self.processed_channels.add(channel_id)
            self.logger.info(
                f"First mention received from channel {channel_id}",
                extra={
                    "event_type": "new_channel_detected",
                    "channel_id": channel_id,
                    "total_channels": len(self.processed_channels),
                },
            )

        return MentionEvent(
            event_id=str(uuid.uuid4()),  # Generate unique ID
            event_type=event_data["type"],
            channel_id=channel_id,
            user_id=event_data["user"],
            text=event_data["text"],
            timestamp=event_data["ts"],
            thread_ts=event_data.get("thread_ts"),
        )

    async def create_response_message(
        self, mention_event: MentionEvent
    ) -> ResponseMessage:
        """Create response message for a mention event using AI agent.

        Args:
            mention_event: The mention event to respond to

        Returns:
            ResponseMessage with AI-generated content
        """
        # Validate channel is still being tracked
        if mention_event.channel_id not in self.processed_channels:
            self.logger.warning(
                f"Responding to channel {mention_event.channel_id} not in tracked channels",
                extra={
                    "event_type": "untracked_channel_response",
                    "channel_id": mention_event.channel_id,
                    "mention_event_id": mention_event.event_id,
                },
            )

        # Generate AI response if agent is available
        response_text = "Meowth, that's right!"

        if self.ai_agent and self.auto_tool_selector:
            try:
                # Create thread context for automatic tool selection
                thread_context = ThreadContext(
                    channel_id=mention_event.channel_id,
                    thread_ts=mention_event.thread_ts or mention_event.timestamp,
                    user_id=mention_event.user_id,
                    messages=[],
                    token_count=0,
                )

                # Use automatic tool selection and execution
                execution_context = (
                    await self.auto_tool_selector.select_and_execute_tools(
                        message=mention_event.text, thread_context=thread_context
                    )
                )

                # Generate response from execution results
                if execution_context.has_successful_results():
                    response_text = self._format_tool_results(execution_context)

                    self.logger.info(
                        f"Auto tool selection successful for mention in {mention_event.channel_id}",
                        extra={
                            "mention_event_id": mention_event.event_id,
                            "intent": execution_context.user_intent.primary_intent,
                            "confidence": execution_context.user_intent.confidence,
                            "tools_executed": execution_context.tools_executed,
                            "execution_summary": execution_context.get_execution_summary(),
                        },
                    )
                else:
                    # Fallback to regular AI agent if auto selection failed
                    response_text = await self._fallback_to_ai_agent(
                        mention_event, execution_context
                    )

            except Exception as e:
                self.logger.error(
                    f"Auto tool selection failed: {e}",
                    extra={
                        "mention_event_id": mention_event.event_id,
                        "channel_id": mention_event.channel_id,
                    },
                )
                # Fallback to regular AI response
                response_text = await self._fallback_to_ai_agent(mention_event, None)

        elif self.ai_agent:
            # Fallback to regular AI agent without auto selection
            response_text = await self._fallback_to_ai_agent(mention_event, None)

        return ResponseMessage(
            response_id=str(uuid.uuid4()),
            mention_event_id=mention_event.event_id,
            channel_id=mention_event.channel_id,
            thread_ts=mention_event.thread_ts,
            text=response_text,
        )

    def _format_tool_results(self, execution_context) -> str:
        """Format tool execution results into a response message.

        Args:
            execution_context: Tool execution context with results

        Returns:
            Formatted response text
        """
        successful_results = execution_context.get_successful_results()

        if not successful_results:
            return "I wasn't able to process your request. Could you try rephrasing it?"

        # Build response from successful tool results
        response_parts = []

        for tool_name, result in successful_results.items():
            if result.data:
                if isinstance(result.data, str):
                    response_parts.append(result.data)
                elif isinstance(result.data, dict):
                    # Format structured data
                    if "summary" in result.data:
                        response_parts.append(result.data["summary"])
                    elif "message" in result.data:
                        response_parts.append(result.data["message"])
                    else:
                        response_parts.append(
                            f"Tool {tool_name} completed successfully"
                        )
                else:
                    response_parts.append(f"Tool {tool_name}: {str(result.data)}")

        if not response_parts:
            response_parts.append("I processed your request successfully!")

        # Combine results with intent-aware formatting
        intent = execution_context.user_intent.primary_intent

        if intent == "greeting":
            return response_parts[0]  # Direct greeting response
        elif intent == "help":
            return response_parts[0]  # Direct help response
        else:
            # Add context for other intents
            response = "\n\n".join(response_parts)

            # Add execution summary if multiple tools were used
            if len(successful_results) > 1:
                tool_names = list(successful_results.keys())
                response += f"\n\n*Used tools: {', '.join(tool_names)}*"

            return response

    async def _fallback_to_ai_agent(
        self, mention_event: MentionEvent, execution_context
    ) -> str:
        """Fallback to regular AI agent when auto selection fails.

        Args:
            mention_event: The mention event
            execution_context: Optional execution context with partial results

        Returns:
            AI-generated response text
        """
        try:
            # Create thread context for the AI agent
            thread_context = {
                "channel_id": mention_event.channel_id,
                "user_id": mention_event.user_id,
                "message": mention_event.text,
                "thread_ts": mention_event.thread_ts,
                "timestamp": mention_event.timestamp,
            }

            # Get AI response
            ai_response = await self.ai_agent.generate_response(
                message=mention_event.text, thread_context=thread_context
            )

            self.logger.info(
                f"AI fallback response generated for mention in {mention_event.channel_id}",
                extra={
                    "mention_event_id": mention_event.event_id,
                    "response_length": len(ai_response.response),
                    "tools_used": getattr(ai_response, "tools_used", []),
                    "had_execution_context": execution_context is not None,
                },
            )

            return ai_response.response

        except ToolError as e:
            # Handle tool-specific errors with user feedback
            error_response = self.error_handler.handle_tool_error(
                e,
                user_context={
                    "channel_id": mention_event.channel_id,
                    "user_id": mention_event.user_id,
                    "request_type": "mention_response",
                    "request_id": mention_event.event_id,
                },
            )
            response_text = error_response["message"]

            if error_response["can_retry"]:
                response_text += f"\n\n💡 You can try again in {error_response['retry_delay_seconds']} seconds."

            return response_text

        except Exception as e:
            self.logger.error(
                f"AI response generation failed: {e}",
                extra={
                    "mention_event_id": mention_event.event_id,
                    "channel_id": mention_event.channel_id,
                },
            )
            return self.error_handler.get_fallback_response(
                {
                    "request_id": mention_event.event_id,
                    "channel_id": mention_event.channel_id,
                    "user_id": mention_event.user_id,
                }
            )

    def get_channel_stats(self) -> Dict[str, Any]:
        """Get statistics about channels processed."""
        return {
            "total_channels": len(self.processed_channels),
            "channels": list(self.processed_channels),
        }

    def handle_channel_removed(self, channel_id: str) -> None:
        """Handle graceful cleanup when bot is removed from a channel."""
        if channel_id in self.processed_channels:
            self.processed_channels.remove(channel_id)
            self.logger.info(
                f"Bot removed from channel {channel_id}",
                extra={
                    "event_type": "channel_removed",
                    "channel_id": channel_id,
                    "remaining_channels": len(self.processed_channels),
                },
            )
        else:
            self.logger.warning(
                f"Attempted to remove unknown channel {channel_id}",
                extra={
                    "event_type": "unknown_channel_removal",
                    "channel_id": channel_id,
                },
            )
