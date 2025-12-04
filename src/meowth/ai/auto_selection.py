"""Automatic tool selection integration for AI agent.

This module integrates intent classification, tool execution context management,
and enhanced metadata to provide intelligent automatic tool selection based on
user intent and conversation context.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

from llama_index.core.tools import FunctionTool

from .models import ThreadContext
from .intent import UserIntent, get_intent_classifier
from .execution import ToolResult, ToolExecutionContext, get_execution_context_manager
from .tools.metadata import get_metadata_optimizer
from .tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AutoToolSelector:
    """Intelligent tool selector based on user intent and context.

    This class analyzes user messages, classifies intent, and automatically
    selects and executes the most appropriate tools for the request.
    """

    def __init__(self, tool_registry: ToolRegistry):
        """Initialize the automatic tool selector.

        Args:
            tool_registry: Registry of available tools
        """
        self.tool_registry = tool_registry
        self.intent_classifier = get_intent_classifier()
        self.context_manager = get_execution_context_manager()
        self.metadata_optimizer = get_metadata_optimizer()

        # Tool selection mappings
        self._tool_mappings: Dict[str, List[str]] = {}
        self._fallback_tools: List[str] = []

        # Performance tracking
        self._selection_stats = {
            "total_selections": 0,
            "successful_selections": 0,
            "failed_selections": 0,
            "intent_classification_time": 0.0,
            "tool_execution_time": 0.0,
        }

        self._initialize_tool_mappings()

        logger.info("Initialized automatic tool selector")

    def _initialize_tool_mappings(self) -> None:
        """Initialize tool selection mappings based on available tools."""
        # Get available tools from registry
        available_tools = self.tool_registry.get_available_tools()

        # Build mappings based on optimized metadata
        for tool_name in available_tools:
            tool = self.tool_registry.get_tool(tool_name)
            if tool:
                metadata = self.metadata_optimizer.optimize_tool_metadata(tool)

                # Map intent keywords to tools
                for keyword in metadata.intent_keywords:
                    if keyword not in self._tool_mappings:
                        self._tool_mappings[keyword] = []

                    if tool_name not in self._tool_mappings[keyword]:
                        self._tool_mappings[keyword].append(tool_name)

        # Identify fallback tools (general purpose)
        self._fallback_tools = [
            tool
            for tool in available_tools
            if any(keyword in tool.lower() for keyword in ["fetch", "get", "basic"])
        ]

        logger.info(f"Initialized tool mappings for {len(available_tools)} tools")

    async def select_and_execute_tools(
        self, message: str, thread_context: ThreadContext
    ) -> ToolExecutionContext:
        """Select and execute tools automatically based on user message.

        Args:
            message: User's message text
            thread_context: Slack thread context

        Returns:
            Tool execution context with results
        """
        start_time = datetime.now(timezone.utc)
        self._selection_stats["total_selections"] += 1

        try:
            # Step 1: Classify user intent
            user_intent = self.intent_classifier.classify_intent(
                message, thread_context
            )

            # Step 2: Create execution context
            execution_context = self.context_manager.create_context(
                user_intent, thread_context
            )

            # Step 3: Select tools based on intent
            selected_tools = self._select_tools_for_intent(user_intent)

            # Step 4: Execute selected tools
            if selected_tools:
                await self._execute_tools(selected_tools, execution_context)
            else:
                # Handle case where no tools are selected
                await self._handle_no_tool_selection(execution_context)

            # Update statistics
            if execution_context.has_successful_results():
                self._selection_stats["successful_selections"] += 1
            else:
                self._selection_stats["failed_selections"] += 1

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self._selection_stats["tool_execution_time"] += execution_time

            logger.info(
                f"Tool selection completed in {execution_time:.2f}s for intent {user_intent.primary_intent}"
            )

            return execution_context

        except Exception as e:
            logger.error(f"Tool selection failed: {e}")
            self._selection_stats["failed_selections"] += 1

            # Create minimal error context
            error_intent = UserIntent(
                primary_intent="error",
                confidence=0.0,
                tool_suggestions=[],
                parameters={},
            )

            error_context = self.context_manager.create_context(
                error_intent, thread_context
            )
            error_context.errors.append(f"Tool selection failed: {str(e)}")

            return error_context

    def _select_tools_for_intent(self, user_intent: UserIntent) -> List[str]:
        """Select tools based on classified user intent.

        Args:
            user_intent: Classified user intent

        Returns:
            List of selected tool names
        """
        selected_tools = []

        # Start with intent suggestions
        selected_tools.extend(user_intent.tool_suggestions)

        # Add tools based on keyword mappings
        for keyword in user_intent.parameters.keys():
            if keyword in self._tool_mappings:
                for tool_name in self._tool_mappings[keyword]:
                    if tool_name not in selected_tools:
                        selected_tools.append(tool_name)

        # Add tools based on intent type patterns
        intent_specific_tools = self._get_intent_specific_tools(
            user_intent.primary_intent
        )
        for tool_name in intent_specific_tools:
            if tool_name not in selected_tools:
                selected_tools.append(tool_name)

        # If confidence is low or intent is ambiguous, use fallback tools
        if user_intent.confidence < 0.6 or user_intent.primary_intent in [
            "ambiguous",
            "unknown",
        ]:
            for tool_name in self._fallback_tools:
                if tool_name not in selected_tools:
                    selected_tools.append(tool_name)
                    break  # Add just one fallback tool

        # Limit selection to avoid overwhelming execution
        selected_tools = selected_tools[:3]

        logger.info(
            f"Selected {len(selected_tools)} tools for intent {user_intent.primary_intent}: {selected_tools}"
        )

        return selected_tools

    def _get_intent_specific_tools(self, intent_type: str) -> List[str]:
        """Get tools specifically mapped to an intent type.

        Args:
            intent_type: Primary intent type

        Returns:
            List of tool names for the intent
        """
        intent_tool_map = {
            "summarization": ["fetch_slack_messages", "summarize_messages"],
            "analysis": ["fetch_slack_messages", "analyze_conversation"],
            "information_lookup": ["fetch_slack_messages", "get_participant_info"],
            "greeting": [],
            "help": [],
            "ambiguous": ["fetch_slack_messages"],
            "unknown": ["fetch_slack_messages"],
        }

        return intent_tool_map.get(intent_type, [])

    async def _execute_tools(
        self, tool_names: List[str], context: ToolExecutionContext
    ) -> None:
        """Execute selected tools with the execution context.

        Args:
            tool_names: List of tool names to execute
            context: Tool execution context
        """
        for tool_name in tool_names:
            if not context.should_continue_execution():
                logger.warning(
                    "Stopping tool execution early due to context constraints"
                )
                break

            try:
                # Get tool from registry
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    error_result = ToolResult(
                        tool_name=tool_name,
                        success=False,
                        error=f"Tool {tool_name} not found in registry",
                    )
                    context.add_tool_result(error_result)
                    continue

                # Prepare tool parameters from context
                parameters = self._prepare_tool_parameters(tool, context)

                # Execute tool
                start_time = datetime.now(timezone.utc)

                try:
                    # Execute the tool function
                    result_data = await self._execute_tool_function(tool, parameters)

                    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

                    # Create successful result
                    result = ToolResult(
                        tool_name=tool_name,
                        success=True,
                        data=result_data,
                        execution_time=execution_time,
                        metadata={"parameters": parameters},
                    )

                except Exception as tool_error:
                    execution_time = (datetime.now(datetime.UTC) - start_time).total_seconds()

                    # Create failed result
                    result = ToolResult(
                        tool_name=tool_name,
                        success=False,
                        error=str(tool_error),
                        execution_time=execution_time,
                        metadata={"parameters": parameters},
                    )

                context.add_tool_result(result)

            except Exception as e:
                logger.error(f"Failed to execute tool {tool_name}: {e}")

                error_result = ToolResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Execution failed: {str(e)}",
                )
                context.add_tool_result(error_result)

    def _prepare_tool_parameters(
        self, tool: FunctionTool, context: ToolExecutionContext
    ) -> Dict[str, Any]:
        """Prepare parameters for tool execution from context.

        Args:
            tool: Tool to execute
            context: Execution context with parameters

        Returns:
            Dictionary of prepared parameters
        """
        parameters = {}

        # Extract from thread context
        thread_ctx = context.thread_context
        parameters.update(
            {
                "channel_id": thread_ctx.channel_id,
                "thread_ts": thread_ctx.thread_ts,
                "user_id": thread_ctx.user_id,
            }
        )

        # Extract from intent parameters
        intent_params = context.user_intent.parameters
        parameters.update(intent_params)

        # Add default values for common parameters
        if "limit" not in parameters:
            parameters["limit"] = intent_params.get("message_count", 10)

        return parameters

    async def _execute_tool_function(
        self, tool: FunctionTool, parameters: Dict[str, Any]
    ) -> Any:
        """Execute the actual tool function with parameters.

        Args:
            tool: Tool to execute
            parameters: Parameters for the tool

        Returns:
            Tool execution result
        """
        # Get function signature to match parameters
        import inspect

        sig = inspect.signature(tool.fn)
        matched_params = {}

        for param_name, param in sig.parameters.items():
            if param_name in parameters:
                matched_params[param_name] = parameters[param_name]
            elif param.default is not inspect.Parameter.empty:
                # Use default value
                matched_params[param_name] = param.default

        # Execute the function
        if inspect.iscoroutinefunction(tool.fn):
            return await tool.fn(**matched_params)
        else:
            return tool.fn(**matched_params)

    async def _handle_no_tool_selection(self, context: ToolExecutionContext) -> None:
        """Handle cases where no tools are selected for execution.

        Args:
            context: Execution context
        """
        intent = context.user_intent.primary_intent

        if intent == "greeting":
            # Provide a friendly greeting response
            result = ToolResult(
                tool_name="greeting_response",
                success=True,
                data="Hello! I'm here to help you analyze conversations and summarize messages. What would you like me to do?",
            )
            context.add_tool_result(result)

        elif intent == "help":
            # Provide help information
            available_tools = list(self.tool_registry.get_available_tools())
            help_text = f"I can help you with: conversation analysis, message summarization, and participant information. Available tools: {', '.join(available_tools[:5])}"

            result = ToolResult(tool_name="help_response", success=True, data=help_text)
            context.add_tool_result(result)

        else:
            # Ask for clarification
            result = ToolResult(
                tool_name="clarification_request",
                success=True,
                data="I'm not sure how to help with that request. Could you be more specific? For example, you can ask me to 'summarize the last 10 messages' or 'analyze this conversation'.",
            )
            context.add_tool_result(result)

    def get_selection_statistics(self) -> Dict[str, Any]:
        """Get tool selection performance statistics.

        Returns:
            Dictionary containing selection statistics
        """
        total = self._selection_stats["total_selections"]
        success_rate = (
            (self._selection_stats["successful_selections"] / total * 100)
            if total > 0
            else 0
        )

        avg_execution_time = (
            (self._selection_stats["tool_execution_time"] / total) if total > 0 else 0
        )

        return {
            "total_selections": total,
            "successful_selections": self._selection_stats["successful_selections"],
            "failed_selections": self._selection_stats["failed_selections"],
            "success_rate": round(success_rate, 2),
            "average_execution_time": round(avg_execution_time, 3),
            "available_tools": len(self.tool_registry.get_available_tools()),
            "tool_mappings": len(self._tool_mappings),
        }

    def refresh_tool_mappings(self) -> None:
        """Refresh tool mappings from the registry.

        This should be called when tools are added or removed from the registry.
        """
        self._tool_mappings.clear()
        self._fallback_tools.clear()
        self._initialize_tool_mappings()

        logger.info("Refreshed tool selection mappings")


def create_auto_tool_selector(tool_registry: ToolRegistry) -> AutoToolSelector:
    """Create an automatic tool selector instance.

    Args:
        tool_registry: Registry of available tools

    Returns:
        Configured AutoToolSelector instance
    """
    return AutoToolSelector(tool_registry)
