"""AI-powered mention handler for Azure OpenAI integration.

This module provides the main handler for processing Slack mentions with
Azure OpenAI-powered responses, including context analysis and error handling.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt.context.context import BoltContext

from ..ai.client import get_azure_openai_client
from ..ai.context import ContextAnalyzer
from ..ai.agent import get_llama_agent
from ..ai.models import (
    ThreadContext,
    AIResponse,
    RequestSession,
    SessionStatus,
    AzureOpenAIError,
    RateLimitError,
    ContextAnalysisError,
    register_session,
    get_session_tracker,
    cleanup_completed_sessions,
)

logger = logging.getLogger(__name__)


async def handle_ai_mention(
    event: Dict[str, Any], client: WebClient, context: BoltContext
) -> None:
    """Handle AI-powered mention with Azure OpenAI response generation and thread isolation.

    Args:
        event: Slack mention event data
        client: Slack Web API client
        context: Bolt context with bot information

    This function implements the complete AI mention handling flow with thread isolation:
    1. Create isolated session for thread
    2. Extract and validate mention details
    3. Analyze thread context with isolation tracking
    4. Generate AI response using Azure OpenAI
    5. Post response to Slack with error fallback
    6. Clean up session tracking
    """
    # Clean up any completed sessions first
    cleanup_completed_sessions()

    # Create session with thread isolation
    thread_ts = event.get("thread_ts", event["ts"])
    channel_id = event["channel"]
    thread_id = f"{channel_id}:{thread_ts}"

    session = RequestSession(
        user_id=event["user"],
        thread_context=ThreadContext(
            thread_ts=thread_ts,
            channel_id=channel_id,
            messages=[],  # Will be populated during analysis
        ),
    )

    # Register session for tracking and isolation
    register_session(session)
    context_analyzer = ContextAnalyzer(client)

    try:
        logger.info(
            f"Processing AI mention with isolation: {session.session_id} from user {event['user']} "
            f"in thread {thread_id}"
        )

        # Check for concurrent sessions on same thread
        session_tracker = get_session_tracker()
        concurrent_sessions = session_tracker.get_active_sessions_for_thread(thread_id)

        if len(concurrent_sessions) > 1:
            logger.warning(
                f"Concurrent processing detected for thread {thread_id}: {len(concurrent_sessions)} active sessions"
            )

        # Update session status
        session.status = SessionStatus.ANALYZING_CONTEXT

        # Analyze thread context with session tracking
        thread_context = await context_analyzer.analyze_thread_context(
            channel_id=channel_id,
            thread_ts=thread_ts,
            bot_user_id=context.user_id or "UNKNOWN",
            session=session,  # Pass session for isolation tracking
        )

        session.thread_context = thread_context
        session.status = SessionStatus.GENERATING_RESPONSE

        logger.info(
            f"Analyzed context with isolation: {len(thread_context.messages)} messages, "
            f"{thread_context.token_count} tokens for thread {thread_id}"
        )

        # Verify thread isolation before proceeding
        if not session.is_context_isolated():
            logger.warning(f"Thread isolation verification failed for {thread_id}")

        # Generate AI response using enhanced agent if available, fallback to basic client
        llama_agent = get_llama_agent()

        if llama_agent is not None:
            logger.info(
                f"Using LlamaIndex agent for enhanced context processing (thread: {thread_id})"
            )
            # Extract user message from the mention event
            user_message = event.get("text", "").strip()
            ai_response = await llama_agent.generate_response(
                thread_context=thread_context,
                user_message=user_message if user_message else None,
                session=session,  # Pass session for additional tracking
            )
        else:
            logger.info(f"Using basic Azure OpenAI client (thread: {thread_id})")
            # Fallback to basic Azure OpenAI client
            ai_client = get_azure_openai_client()
            ai_response = await ai_client.generate_response(
                thread_context=thread_context,
                system_prompt="You are a helpful Slack bot assistant. "
                "Provide concise, friendly, and contextually relevant responses. "
                "Keep responses under 2000 characters.",
                session=session,  # Pass session for additional tracking
            )

        session.complete_with_response(ai_response)

        logger.info(
            f"Generated AI response: {ai_response.tokens_used} tokens "
            f"in {ai_response.generation_time:.2f}s for thread {thread_id}"
        )

        # Post AI response to Slack
        await post_ai_response(
            client=client,
            channel_id=event["channel"],
            thread_ts=event.get("thread_ts", event["ts"]),
            ai_response=ai_response,
        )

        logger.info(
            f"Successfully completed AI mention handling: {session.session_id} for thread {thread_id}"
        )

    except ContextAnalysisError as e:
        logger.warning(f"Context analysis failed for thread {thread_id}: {e}")
        session.complete_with_error(f"Context analysis error: {e}")
        await post_fallback_response(
            client=client,
            channel_id=event["channel"],
            thread_ts=event.get("thread_ts", event["ts"]),
            error_type="context_error",
            message="I'm having trouble understanding the conversation context. Could you try rephrasing your question?",
        )

    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded for thread {thread_id}: {e}")
        session.complete_with_error(f"Rate limit error: {e}")
        await post_fallback_response(
            client=client,
            channel_id=event["channel"],
            thread_ts=event.get("thread_ts", event["ts"]),
            error_type="rate_limit",
            message="I'm a bit busy right now! Please try again in a moment. 🤖",
        )

    except AzureOpenAIError as e:
        logger.error(f"Azure OpenAI error for thread {thread_id}: {e}")
        session.complete_with_error(f"Azure OpenAI service error: {e}")
        await post_fallback_response(
            client=client,
            channel_id=event["channel"],
            thread_ts=event.get("thread_ts", event["ts"]),
            error_type="ai_service",
            message="My AI brain is currently unavailable. Please try again later! 🧠⚡",
        )

    except Exception as e:
        logger.error(
            f"Unexpected error in AI mention handler for thread {thread_id}: {e}",
            exc_info=True,
        )
        session.complete_with_error(f"Unexpected error: {e}")
        await post_fallback_response(
            client=client,
            channel_id=event["channel"],
            thread_ts=event.get("thread_ts", event["ts"]),
            error_type="internal",
            message="Something went wrong! Please try again. If the problem persists, contact support.",
        )

    finally:
        # Clean up session tracking and context isolation
        try:
            if context_analyzer and hasattr(
                context_analyzer, "cleanup_session_context"
            ):
                context_analyzer.cleanup_session_context(session)

            # Verify final isolation state
            session_tracker = get_session_tracker()
            if session_tracker.is_thread_isolated(thread_id):
                logger.debug(
                    f"Thread isolation maintained successfully for {thread_id}"
                )
            else:
                logger.warning(
                    f"Thread isolation may have been compromised for {thread_id}"
                )

            # Final cleanup of completed sessions
            cleaned_count = cleanup_completed_sessions()
            if cleaned_count > 0:
                logger.debug(f"Cleaned up {cleaned_count} completed sessions")

        except Exception as cleanup_error:
            logger.error(
                f"Error during session cleanup for thread {thread_id}: {cleanup_error}"
            )


def get_concurrent_session_count() -> int:
    """Get the total number of concurrent sessions currently active."""
    session_tracker = get_session_tracker()
    return session_tracker.get_total_active_sessions()


def get_active_threads() -> list[str]:
    """Get list of thread IDs currently being processed."""
    session_tracker = get_session_tracker()
    return session_tracker.get_active_threads()


def is_thread_processing(thread_id: str) -> bool:
    """Check if a specific thread is currently being processed."""
    session_tracker = get_session_tracker()
    active_sessions = session_tracker.get_active_sessions_for_thread(thread_id)
    return len(active_sessions) > 0


async def post_ai_response(
    client: WebClient, channel_id: str, thread_ts: str, ai_response: AIResponse
) -> None:
    """Post AI response to Slack with proper formatting.

    Args:
        client: Slack Web API client
        channel_id: Slack channel ID
        thread_ts: Thread timestamp
        ai_response: Generated AI response
    """
    try:
        # Format the response with some basic Slack markdown
        formatted_content = format_ai_response_for_slack(ai_response.content)

        # Handle both sync (real) and async (mock) Slack clients
        response = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=formatted_content,
            # Add some metadata in blocks for better formatting
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": formatted_content},
                }
            ],
            # Add unfurl settings
            unfurl_links=False,
            unfurl_media=False,
        )

        # Await if it's a coroutine (mock), otherwise use directly (real client)
        if hasattr(response, "__await__"):
            response = await response

        if not response["ok"]:
            raise SlackApiError("Failed to post message", response)

        logger.info(f"Posted AI response to {channel_id}/{thread_ts}")

    except SlackApiError as e:
        logger.error(f"Failed to post AI response: {e}")
        # Try fallback without blocks
        try:
            response = client.chat_postMessage(
                channel=channel_id, thread_ts=thread_ts, text=ai_response.content
            )
            # Await if it's a coroutine (mock)
            if hasattr(response, "__await__"):
                response = await response
            if response["ok"]:
                logger.info(f"Posted fallback AI response to {channel_id}/{thread_ts}")
        except SlackApiError as fallback_error:
            logger.error(f"Failed to post fallback AI response: {fallback_error}")
            raise


async def post_fallback_response(
    client: WebClient, channel_id: str, thread_ts: str, error_type: str, message: str
) -> None:
    """Post fallback response when AI processing fails.

    Args:
        client: Slack Web API client
        channel_id: Slack channel ID
        thread_ts: Thread timestamp
        error_type: Type of error that occurred
        message: Fallback message to post
    """
    try:
        response = client.chat_postMessage(
            channel=channel_id, thread_ts=thread_ts, text=message
        )

        # Await if it's a coroutine (mock), otherwise use directly
        if hasattr(response, "__await__"):
            response = await response

        if response["ok"]:
            logger.info(
                f"Posted fallback response ({error_type}) to {channel_id}/{thread_ts}"
            )
        else:
            logger.error(f"Failed to post fallback response: {response}")

    except SlackApiError as e:
        logger.error(f"Failed to post fallback response: {e}")


def format_ai_response_for_slack(content: str) -> str:
    """Format AI response content for Slack markdown.

    Args:
        content: Raw AI response content

    Returns:
        Content formatted for Slack with proper markdown
    """
    if not content:
        return "I'm not sure how to respond to that. Could you rephrase your question?"

    # Basic formatting cleanup
    content = content.strip()

    # Ensure reasonable length for Slack
    if len(content) > 2000:
        content = content[:1997] + "..."
        logger.warning("Truncated AI response to fit Slack limits")

    return content


def extract_user_message(text: str, bot_user_id: str) -> str:
    """Extract user message from mention text by removing bot mention.

    Args:
        text: Raw message text with bot mention
        bot_user_id: Bot's user ID to remove from mention

    Returns:
        Clean user message without bot mention
    """
    if not text:
        return ""

    # Remove bot mentions: <@U123BOT> or <@U123BOT|bot>
    mention_pattern = f"<@{bot_user_id}(?:\\|[^>]+)?>"
    clean_text = re.sub(mention_pattern, "", text).strip()

    # Clean up extra whitespace
    clean_text = " ".join(clean_text.split())

    return clean_text


def is_thread_message(event: Dict[str, Any]) -> bool:
    """Check if message is part of a thread.

    Args:
        event: Slack message event

    Returns:
        True if message is in a thread, False otherwise
    """
    return "thread_ts" in event and event.get("thread_ts") is not None


def should_process_mention(event: Dict[str, Any], bot_user_id: str) -> bool:
    """Check if mention should be processed by AI handler.

    Args:
        event: Slack mention event
        bot_user_id: Bot's user ID

    Returns:
        True if mention should be processed, False otherwise
    """
    # Skip if no text
    if not event.get("text"):
        return False

    # Skip if bot is talking to itself
    if event.get("user") == bot_user_id:
        return False

    # Skip if not actually a mention of the bot
    if f"<@{bot_user_id}>" not in event.get("text", ""):
        return False

    # Skip certain message subtypes
    skip_subtypes = {"bot_message", "message_changed", "message_deleted"}
    if event.get("subtype") in skip_subtypes:
        return False

    return True
