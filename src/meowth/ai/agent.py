"""LlamaIndex agent wrapper with Azure OpenAI for advanced chat processing.

This module provides an optional LlamaIndex-based agent for more sophisticated
conversation handling, document indexing, and context-aware responses with
performance optimizations for concurrent processing.
"""

from __future__ import annotations

import asyncio
import logging
import time
import warnings
from typing import Optional, Dict, Any, List

# Suppress all deprecation and future warnings from LlamaIndex and related libraries
warnings.filterwarnings("ignore", category=DeprecationWarning, module="llama_index")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="deprecated")
warnings.filterwarnings("ignore", message="Call to deprecated class ReActAgent")
warnings.filterwarnings("ignore", message="Call to deprecated class AgentRunner")

# Now import LlamaIndex components
from llama_index.core.agent import ReActAgent

from llama_index.core.tools import FunctionTool
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.azure_openai import AzureOpenAI as LlamaAzureOpenAI  # type: ignore[import-untyped]

from ..utils.config import config
from ..ai.models import ThreadContext, AIResponse, AzureOpenAIError, RequestSession
from ..ai.client import AzureOpenAIConfig

logger = logging.getLogger(__name__)


class LlamaIndexAgentWrapper:
    """LlamaIndex ReAct agent wrapper with performance optimizations for concurrent processing."""

    def __init__(self, azure_config: Optional[AzureOpenAIConfig] = None):
        """Initialize LlamaIndex agent with Azure OpenAI and performance optimizations.

        Args:
            azure_config: Azure OpenAI configuration. If None, loads from environment.
        """
        if azure_config is None:
            azure_config = self._load_config_from_env()

        self.config = azure_config
        self._llm = self._create_llm()

        # Initialize with basic tools, can be updated with registry tools
        self._tools: List[FunctionTool] = []
        self._agent = self._create_agent()

        # Performance optimization features
        self._context_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
        self._max_concurrent_requests = 10
        self._request_semaphore = asyncio.Semaphore(self._max_concurrent_requests)
        self._response_cache: Dict[str, Dict[str, Any]] = {}

        # Performance metrics
        self._performance_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_requests": 0,
            "avg_response_time": 0.0,
            "concurrent_requests": 0,
        }

        logger.info(
            f"Initialized LlamaIndex agent with Azure OpenAI (max concurrent: {self._max_concurrent_requests})"
        )

    def _load_config_from_env(self) -> AzureOpenAIConfig:
        """Load Azure OpenAI configuration from environment variables."""
        return AzureOpenAIConfig(
            api_key=config.azure_openai_api_key,
            endpoint=config.azure_openai_endpoint,
            deployment_name=config.azure_openai_deployment_name,
            api_version=config.azure_openai_api_version,
            model=config.azure_openai_model,
        )

    def _create_llm(self) -> LlamaAzureOpenAI:
        """Create LlamaIndex Azure OpenAI LLM."""
        return LlamaAzureOpenAI(
            model=self.config.model,
            deployment_name=self.config.deployment_name,
            api_key=self.config.api_key,
            azure_endpoint=self.config.endpoint,
            api_version=self.config.api_version,
            temperature=0.7,
            max_tokens=1000,
        )

    def _create_agent(self) -> ReActAgent:
        """Create LlamaIndex ReAct agent with tools."""
        # Combine built-in tools with registry tools
        tools = [
            self._create_thread_summary_tool(),
            self._create_context_analysis_tool(),
        ]

        # Add tools from registry if available
        tools.extend(self._tools)

        # Create memory buffer for conversation history
        memory = ChatMemoryBuffer.from_defaults(
            token_limit=2000,  # Limit conversation memory
            llm=self._llm,
        )

        # Create agent
        agent = ReActAgent.from_tools(  # type: ignore[attr-defined]
            tools=tools,
            llm=self._llm,
            memory=memory,
            verbose=True,
            max_iterations=3,  # Limit reasoning iterations
            system_prompt=self._get_enhanced_system_prompt(),
        )

        return agent  # type: ignore[no-any-return]

    def _get_enhanced_system_prompt(self) -> str:
        """Get enhanced system prompt optimized for automatic tool selection.

        Returns:
            Enhanced system prompt with tool selection guidance
        """
        return """You are Meowth, an intelligent Slack bot assistant with access to powerful analysis tools.

CORE CAPABILITIES:
- Analyze conversation threads and provide contextual insights
- Summarize discussions and extract key themes
- Look up participant information and engagement patterns
- Provide helpful responses based on conversation context

TOOL SELECTION STRATEGY:
1. For requests like "summarize" or "what happened": Use message fetching + summarization tools
2. For questions about "who said what" or "participants": Use message fetching + analysis tools
3. For greetings or simple questions: Respond directly without tools
4. When uncertain about user intent: Ask for clarification

RESPONSE GUIDELINES:
- Keep responses under 2000 characters for Slack readability
- Be concise but informative
- Use tools efficiently - don't over-fetch data
- Provide actionable insights when possible
- Maintain a friendly, professional tone
- If tools fail, provide a helpful fallback response

TOOL EXECUTION PRINCIPLES:
- Choose the most relevant tool for the user's specific request
- Use conversation context to inform tool parameters
- Combine multiple tools only when necessary for comprehensive answers
- Prefer recent messages unless user specifies otherwise
- Handle tool failures gracefully with alternative approaches

Remember: Your goal is to provide valuable assistance while being efficient with tool usage and responsive to user needs."""

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent.
        
        Returns:
            The enhanced system prompt
        """
        return self._get_enhanced_system_prompt()

    def set_tools(self, tools: List[FunctionTool]) -> None:
        """Set tools from the tool registry.

        Args:
            tools: List of LlamaIndex FunctionTool objects from the registry
        """
        self._tools = tools
        # Recreate agent with new tools
        self._agent = self._create_agent()

        logger.info(f"Agent updated with {len(tools)} tools from registry")

    def _create_thread_summary_tool(self) -> FunctionTool:
        """Create tool for summarizing thread context."""

        def summarize_thread(messages: str) -> str:
            """Summarize the key points from thread messages.

            Args:
                messages: JSON string of thread messages

            Returns:
                Summary of key discussion points
            """
            try:
                # Simple summarization - could be enhanced with more sophisticated processing
                import json

                msg_list = json.loads(messages)

                if not msg_list:
                    return "Empty conversation"

                # Extract key information
                user_count = len(set(msg.get("user_id", "unknown") for msg in msg_list))
                total_messages = len(msg_list)

                # Get recent topics (simple keyword extraction)
                recent_text = " ".join(
                    msg.get("text", "")
                    for msg in msg_list[-3:]  # Last 3 messages
                )

                summary = (
                    f"Conversation with {user_count} participants, {total_messages} messages. "
                    f"Recent discussion: {recent_text[:200]}..."
                )

                return summary

            except Exception as e:
                logger.warning(f"Thread summarization failed: {e}")
                return "Unable to summarize conversation"

        return FunctionTool.from_defaults(
            fn=summarize_thread,
            name="summarize_thread",
            description="Summarize the key points and context from thread messages",
        )

    def _create_context_analysis_tool(self) -> FunctionTool:
        """Create tool for analyzing conversation context."""

        def analyze_context(text: str) -> str:
            """Analyze conversation context and extract key themes.

            Args:
                text: Conversation text to analyze

            Returns:
                Analysis of conversation themes and topics
            """
            try:
                # Simple context analysis - could be enhanced with NLP
                text_lower = text.lower()

                # Detect question types
                if any(
                    q in text_lower
                    for q in ["what", "how", "why", "when", "where", "?"]
                ):
                    question_type = "informational question"
                elif any(h in text_lower for h in ["help", "assist", "support"]):
                    question_type = "help request"
                elif any(p in text_lower for p in ["problem", "issue", "error", "bug"]):
                    question_type = "problem report"
                else:
                    question_type = "general conversation"

                # Extract potential topics (simple keyword matching)
                topics = []
                tech_keywords = ["api", "code", "function", "error", "bug", "deploy"]
                business_keywords = ["meeting", "project", "deadline", "client"]
                general_keywords = ["weather", "lunch", "weekend", "vacation"]

                if any(kw in text_lower for kw in tech_keywords):
                    topics.append("technical")
                if any(kw in text_lower for kw in business_keywords):
                    topics.append("business")
                if any(kw in text_lower for kw in general_keywords):
                    topics.append("casual")

                analysis = f"Type: {question_type}"
                if topics:
                    analysis += f", Topics: {', '.join(topics)}"

                return analysis

            except Exception as e:
                logger.warning(f"Context analysis failed: {e}")
                return "Unable to analyze context"

        return FunctionTool.from_defaults(
            fn=analyze_context,
            name="analyze_context",
            description="Analyze conversation context to understand themes and question types",
        )

    async def generate_response(
        self,
        thread_context: ThreadContext,
        user_message: Optional[str] = None,
        session: Optional["RequestSession"] = None,
    ) -> AIResponse:
        """Generate response using LlamaIndex agent with performance optimizations.

        Args:
            thread_context: Analyzed thread context
            user_message: Optional specific user message to respond to
            session: Optional RequestSession for tracking

        Returns:
            AIResponse with agent-generated content

        Raises:
            AzureOpenAIError: If agent processing fails
        """
        start_time = time.time()

        # Update performance stats
        self._performance_stats["total_requests"] += 1
        self._performance_stats["concurrent_requests"] += 1

        # Log session info if available
        session_info = f" (session: {session.session_id})" if session else ""

        try:
            # Apply concurrency limiting
            async with self._request_semaphore:
                # Check cache first for performance
                cache_key = self._generate_cache_key(thread_context, user_message)
                cached_response = self._get_cached_response(cache_key)

                if cached_response:
                    self._performance_stats["cache_hits"] += 1
                    logger.info(f"Cache hit for agent response{session_info}")
                    return cached_response

                self._performance_stats["cache_misses"] += 1

                # Prepare conversation context for agent
                context_messages = await self._format_context_for_agent_optimized(
                    thread_context
                )

                # Create user query
                if user_message:
                    query = (
                        f"User message: {user_message}\\n\\nContext: {context_messages}"
                    )
                else:
                    query = f"Please respond to this conversation: {context_messages}"

                logger.info(
                    f"Processing agent query with {len(context_messages)} chars of context{session_info}"
                )

                # Generate response using agent with timeout
                try:
                    response = await asyncio.wait_for(
                        self._agent.achat(query),  # type: ignore[attr-defined]
                        timeout=30.0,  # 30 second timeout
                    )
                except asyncio.TimeoutError:
                    raise AzureOpenAIError(
                        "Agent response timeout", error_code="TIMEOUT"
                    )

                generation_time = time.time() - start_time

                # Extract response content
                content = (
                    str(response.response)
                    if response.response
                    else "I'm not sure how to respond to that."
                )

                # Estimate token usage (approximate since LlamaIndex doesn't always provide exact counts)
                estimated_context_tokens = (
                    len(context_messages) // 4
                )  # Rough estimation
                estimated_completion_tokens = len(content) // 4
                estimated_total_tokens = (
                    estimated_context_tokens + estimated_completion_tokens
                )

                # Create AI response
                ai_response = AIResponse(
                    content=content,
                    model_used=self.config.model,
                    deployment_name=self.config.deployment_name,
                    tokens_used=estimated_total_tokens,
                    generation_time=generation_time,
                    context_tokens=estimated_context_tokens,
                    completion_tokens=estimated_completion_tokens,
                    azure_endpoint=self.config.endpoint,
                )

                # Cache the response
                self._cache_response(cache_key, ai_response)

                # Update performance stats
                self._update_performance_stats(generation_time)

                logger.info(
                    f"Generated agent response: ~{estimated_total_tokens} tokens "
                    f"in {generation_time:.2f}s{session_info}"
                )

                return ai_response

        except Exception as e:
            logger.error(f"LlamaIndex agent error: {e}")
            raise AzureOpenAIError(
                f"Agent processing failed: {e}", error_code="AGENT_ERROR"
            )
        finally:
            # Update concurrent request count
            self._performance_stats["concurrent_requests"] -= 1

    def _update_performance_stats(self, generation_time: float) -> None:
        """Update performance statistics.

        Args:
            generation_time: Time taken for response generation
        """
        current_avg = self._performance_stats["avg_response_time"]
        total_requests = self._performance_stats["total_requests"]

        # Calculate new running average
        new_avg = (
            (current_avg * (total_requests - 1)) + generation_time
        ) / total_requests
        self._performance_stats["avg_response_time"] = new_avg

    def _format_context_for_agent(self, thread_context: ThreadContext) -> str:
        """Format thread context for agent processing.

        Args:
            thread_context: Thread context to format

        Returns:
            Formatted context string for agent
        """
        if not thread_context.messages:
            return "Empty conversation"

        # Format messages for agent
        formatted_messages = []
        for msg in thread_context.messages:
            role = "Bot" if msg.is_bot_message else "User"
            formatted_messages.append(f"{role}: {msg.text}")

        formatted_context = "\\n".join(formatted_messages)
        return formatted_context if formatted_context else "Empty conversation"

    async def reset_memory(self) -> None:
        """Reset agent conversation memory."""
        try:
            self._agent.memory.reset()  # type: ignore[attr-defined]
            logger.info("Reset agent memory")
        except Exception as e:
            logger.warning(f"Failed to reset agent memory: {e}")

    async def get_memory_summary(self) -> str:
        """Get summary of current conversation memory.

        Returns:
            Summary of conversation memory
        """
        try:
            memory_messages = self._agent.memory.get_all()  # type: ignore[attr-defined]
            if not memory_messages:
                return "No conversation history"

            return f"Memory contains {len(memory_messages)} messages"
        except Exception as e:
            logger.warning(f"Failed to get memory summary: {e}")
            return "Unable to access memory"

    def _generate_cache_key(
        self, thread_context: ThreadContext, user_message: Optional[str] = None
    ) -> str:
        """Generate cache key for response caching.

        Args:
            thread_context: Thread context for cache key
            user_message: Optional user message

        Returns:
            Cache key string
        """
        import hashlib

        # Create deterministic key from context + user message
        context_str = ""
        for msg in thread_context.messages[
            -3:
        ]:  # Only use last 3 messages for cache key
            context_str += f"{msg.user_id}:{msg.text}:{msg.timestamp};"

        if user_message:
            context_str += f"user_msg:{user_message}"

        return hashlib.md5(context_str.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[AIResponse]:
        """Get cached response if available and not expired.

        Args:
            cache_key: Cache key to look up

        Returns:
            Cached AIResponse or None if not found/expired
        """
        if cache_key not in self._response_cache:
            return None

        cached_data = self._response_cache[cache_key]
        cache_time = cached_data.get("timestamp", 0)

        # Check if cache expired
        if time.time() - cache_time > self._cache_ttl_seconds:
            del self._response_cache[cache_key]
            return None

        return cached_data["response"]  # type: ignore[no-any-return]

    def _cache_response(self, cache_key: str, response: AIResponse) -> None:
        """Cache response for future use.

        Args:
            cache_key: Cache key
            response: AIResponse to cache
        """
        self._response_cache[cache_key] = {
            "response": response,
            "timestamp": time.time(),
        }

        # Limit cache size
        if len(self._response_cache) > 100:
            # Remove oldest entries
            oldest_key = min(
                self._response_cache.keys(),
                key=lambda k: self._response_cache[k]["timestamp"],
            )
            del self._response_cache[oldest_key]

    async def _format_context_for_agent_optimized(
        self, thread_context: ThreadContext
    ) -> str:
        """Optimized context formatting with caching.

        Args:
            thread_context: Thread context to format

        Returns:
            Formatted context string
        """
        # Check cache first
        context_key = (
            f"context_{thread_context.thread_ts}_{len(thread_context.messages)}"
        )

        if context_key in self._context_cache:
            cached_data = self._context_cache[context_key]
            if time.time() - cached_data["timestamp"] < self._cache_ttl_seconds:
                return str(cached_data["content"])  # Ensure string return

        # Generate context
        context_parts = []
        for msg in thread_context.messages:
            if msg.is_bot_message:
                context_parts.append(f"Assistant: {msg.text}")
            else:
                context_parts.append(f"User: {msg.text}")

        formatted_context = "\\n".join(context_parts)

        # Cache the result
        self._context_cache[context_key] = {
            "content": formatted_context,
            "timestamp": time.time(),
        }

        # Limit cache size
        if len(self._context_cache) > 50:
            oldest_key = min(
                self._context_cache.keys(),
                key=lambda k: self._context_cache[k]["timestamp"],
            )
            del self._context_cache[oldest_key]

        return formatted_context

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        total_requests = self._performance_stats["total_requests"]
        cache_hits = self._performance_stats["cache_hits"]

        cache_hit_rate = (
            (cache_hits / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            **self._performance_stats,
            "cache_hit_rate_percent": cache_hit_rate,
            "cached_responses": len(self._response_cache),
            "cached_contexts": len(self._context_cache),
        }

    def clear_performance_cache(self) -> None:
        """Clear performance caches for memory management."""
        self._response_cache.clear()
        self._context_cache.clear()
        logger.info("Performance caches cleared")


# Global agent instance (optional - only used if enabled)
_llama_agent: Optional[LlamaIndexAgentWrapper] = None


def get_llama_agent() -> Optional[LlamaIndexAgentWrapper]:
    """Get or create the global LlamaIndex agent instance.

    Returns:
        LlamaIndexAgentWrapper instance or None if disabled
    """
    global _llama_agent

    # Check if LlamaIndex agent is enabled via environment variable
    import os

    if os.getenv("ENABLE_LLAMA_AGENT", "false").lower() not in ("true", "1", "yes"):
        return None

    if _llama_agent is None:
        try:
            _llama_agent = LlamaIndexAgentWrapper()
        except Exception as e:
            logger.warning(f"Failed to initialize LlamaIndex agent: {e}")
            return None

    return _llama_agent


async def cleanup_llama_agent() -> None:
    """Cleanup the global LlamaIndex agent."""
    global _llama_agent
    if _llama_agent is not None:
        await _llama_agent.reset_memory()
        _llama_agent = None
        logger.info("Cleaned up LlamaIndex agent")
