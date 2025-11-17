"""Thread context analysis and token counting for Azure OpenAI integration.

This module provides utilities for analyzing Slack thread messages,
counting tokens, and preparing context for Azure OpenAI API calls.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from datetime import datetime, timedelta

import tiktoken
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient

from .models import (
    ThreadContext,
    ThreadMessage,
    ContextAnalysisError,
    RequestSession,
    register_session,
    unregister_session,
    get_session_tracker,
    cleanup_completed_sessions,
)

logger = logging.getLogger(__name__)


class TokenCounter:
    """Token counting utilities for Azure OpenAI context management."""

    def __init__(
        self, model_name: str = "gpt-3.5-turbo", encoding_name: str = "cl100k_base"
    ):
        """Initialize token counter with specified model and encoding.

        Args:
            model_name: OpenAI model name for encoding selection
            encoding_name: tiktoken encoding name (cl100k_base for GPT-3.5/4)
        """
        try:
            # Try to get encoding for specific model first
            self._encoding = tiktoken.encoding_for_model(model_name)
        except Exception:
            try:
                # Fallback to specified encoding
                self._encoding = tiktoken.get_encoding(encoding_name)
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoding {encoding_name}: {e}")
                # Final fallback to cl100k_base encoding
                self._encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens in the text
        """
        if self._encoding is None:
            # Fallback estimation: ~4 characters per token
            return max(1, len(text) // 4)

        try:
            return len(self._encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed for text length {len(text)}: {e}")
            return max(1, len(text) // 4)

    def estimate_message_tokens(self, message: ThreadMessage) -> int:
        """Estimate total tokens for a message including formatting overhead.

        Args:
            message: Thread message to estimate tokens for

        Returns:
            Estimated total tokens including OpenAI message formatting
        """
        # Count content tokens
        content_tokens = self.count_tokens(message.text)

        # Add overhead for OpenAI message structure
        # Each message has role, content, and formatting overhead (~5-10 tokens)
        overhead_tokens = 10

        return content_tokens + overhead_tokens


class ContextAnalyzer:
    """Analyzes Slack thread context for Azure OpenAI processing with thread isolation."""

    def __init__(
        self,
        slack_client: WebClient,
        max_context_tokens: int = 3000,
        max_messages: int = 50,
        token_counter: Optional[TokenCounter] = None,
    ):
        """Initialize context analyzer.

        Args:
            slack_client: Slack Web API client
            max_context_tokens: Maximum tokens to include in context
            max_messages: Maximum number of messages to include
            token_counter: Token counting utility (creates default if None)
        """
        self.slack_client = slack_client
        self.max_context_tokens = max_context_tokens
        self.max_messages = max_messages
        self.token_counter = token_counter or TokenCounter()
        self.max_age_hours = 24  # Ignore messages older than 24 hours
        self._current_session: Optional[RequestSession] = None

    async def analyze_thread_context(
        self,
        channel_id: str,
        thread_ts: str,
        bot_user_id: str,
        session: Optional[RequestSession] = None,
    ) -> ThreadContext:
        """Analyze Slack thread and create context for Azure OpenAI with thread isolation.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp
            bot_user_id: Bot's user ID to identify bot messages
            session: Optional RequestSession for tracking and isolation

        Returns:
            ThreadContext with analyzed messages and token counts

        Raises:
            ContextAnalysisError: If context analysis fails
        """
        start_time = datetime.now()

        # Set up thread isolation tracking
        if session:
            self._current_session = session
            register_session(session)
            session.status = session.status.__class__.ANALYZING_CONTEXT

        thread_id = f"{channel_id}:{thread_ts}"

        try:
            logger.info(f"Analyzing thread context with isolation: {thread_id}")

            # Check for concurrent sessions on same thread
            session_tracker = get_session_tracker()
            active_sessions = session_tracker.get_active_sessions_for_thread(thread_id)

            if len(active_sessions) > 1:
                logger.warning(
                    f"Multiple active sessions detected for thread {thread_id}: {len(active_sessions)} sessions"
                )

            # Fetch thread messages from Slack
            fetch_start = datetime.now()
            messages = await self._fetch_thread_messages(channel_id, thread_ts)
            fetch_time = (datetime.now() - fetch_start).total_seconds()

            logger.debug(
                f"Fetched {len(messages)} messages in {fetch_time:.3f}s for thread {thread_id}"
            )

            # Convert to ThreadMessage objects with token counting (thread-isolated)
            analysis_start = datetime.now()
            thread_messages: List[ThreadMessage] = []
            total_tokens = 0

            # Process messages in reverse chronological order (newest first)
            # to prioritize recent messages when truncating
            for slack_msg in reversed(messages):
                thread_msg = self._convert_slack_message(slack_msg, bot_user_id)
                estimated_tokens = self.token_counter.estimate_message_tokens(
                    thread_msg
                )

                # Check if adding this message would exceed limits
                if (
                    total_tokens + estimated_tokens > self.max_context_tokens
                    or len(thread_messages) >= self.max_messages
                ):
                    logger.info(
                        f"Truncating context for thread {thread_id}: {total_tokens + estimated_tokens} tokens "
                        f"or {len(thread_messages) + 1} messages would exceed limits"
                    )
                    break

                thread_msg.token_count = estimated_tokens
                thread_messages.append(
                    thread_msg
                )  # Keep in reverse chronological order (newest first)
                total_tokens += estimated_tokens

            analysis_time = (datetime.now() - analysis_start).total_seconds()
            total_time = (datetime.now() - start_time).total_seconds()

            # Create thread context with isolation verification
            context = ThreadContext(
                thread_ts=thread_ts,
                channel_id=channel_id,
                messages=thread_messages,
                token_count=total_tokens,
            )

            # Mark session context as isolated
            if session:
                session.mark_context_isolated(True)

            logger.info(
                f"Analyzed thread context with isolation: {len(thread_messages)} messages, "
                f"{total_tokens} tokens in {total_time:.3f}s "
                f"(fetch: {fetch_time:.3f}s, analysis: {analysis_time:.3f}s) "
                f"for thread {thread_id}"
            )

            return context

        except SlackApiError as e:
            if session:
                session.mark_context_isolated(False)
            logger.error(
                f"Slack API error while analyzing context for thread {thread_id}: {e}"
            )
            raise ContextAnalysisError(
                f"Failed to fetch thread messages: {e}", error_code="SLACK_API_ERROR"
            )

        except Exception as e:
            if session:
                session.mark_context_isolated(False)
            logger.error(
                f"Unexpected error analyzing thread context for thread {thread_id}: {e}"
            )
            raise ContextAnalysisError(
                f"Context analysis failed: {e}", error_code="ANALYSIS_ERROR"
            )

        finally:
            # Clean up session tracking
            if session and session in get_session_tracker()._active_sessions.values():
                # Don't unregister here, let the handler manage session lifecycle
                pass

    async def _fetch_thread_messages(
        self, channel_id: str, thread_ts: str
    ) -> List[dict]:
        """Fetch messages from Slack thread.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp

        Returns:
            List of Slack message dictionaries

        Raises:
            Exception: If fetching thread messages fails
        """
        try:
            # Get thread replies
            # Handle both sync and async slack clients
            response = self.slack_client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
            )

            # If it's a coroutine, await it
            if hasattr(response, "__await__"):
                response = await response

            # Check if the API call was successful
            if not response.get("ok", False):
                error = response.get("error", "Unknown error")
                raise Exception(f"Failed to fetch thread messages: {error}")

            messages: List[dict] = response.get("messages", [])

            # Filter out old messages (only if max_age_hours > 0)
            if self.max_age_hours > 0:
                cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)
            else:
                cutoff_time = datetime.fromtimestamp(0)  # No age filtering

            filtered_messages = []
            for msg in messages:
                try:
                    msg_time = datetime.fromtimestamp(float(msg["ts"]))
                    if msg_time > cutoff_time:
                        filtered_messages.append(msg)
                    else:
                        logger.debug(f"Filtering out old message: {msg['ts']}")
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping message with invalid timestamp: {e}")
                    continue

            return filtered_messages

        except SlackApiError as e:
            logger.error(f"Slack API error fetching thread messages: {e}")
            raise Exception(f"Failed to fetch thread messages: {e}")
        except Exception as e:
            logger.error(f"Error fetching thread messages: {e}")
            raise

    def _convert_slack_message(
        self, slack_msg: dict, bot_user_id: str
    ) -> ThreadMessage:
        """Convert Slack message to ThreadMessage object.

        Args:
            slack_msg: Slack message dictionary
            bot_user_id: Bot's user ID to identify bot messages

        Returns:
            ThreadMessage object
        """
        # Extract message text, handling various message types
        text = slack_msg.get("text", "")

        # Handle special message types
        if slack_msg.get("subtype") == "bot_message":
            # Bot message - use the bot name if available
            bot_name = slack_msg.get("username", "bot")
            text = f"[{bot_name}]: {text}"

        # Clean up text - remove Slack formatting that won't help AI
        text = self._clean_slack_text(text)

        # Determine if this is a bot message
        is_bot = (
            slack_msg.get("user") == bot_user_id
            or slack_msg.get("bot_id") is not None
            or slack_msg.get("subtype") == "bot_message"
        )

        thread_message = ThreadMessage(
            user_id=slack_msg.get("user", "unknown"),
            text=text,
            timestamp=slack_msg["ts"],
            is_bot_message=is_bot,
        )

        # Calculate and set token count
        thread_message.token_count = self.token_counter.estimate_message_tokens(
            thread_message
        )

        return thread_message

    def _clean_slack_text(self, text: str) -> str:
        """Clean Slack message text for AI processing with security sanitization.

        Args:
            text: Raw Slack message text

        Returns:
            Cleaned and sanitized text suitable for AI processing
        """
        if not text:
            return ""

        # Apply input sanitization for security
        text = self._sanitize_input(text)

        # Remove excessive whitespace
        text = " ".join(text.split())

        # Clean Slack-specific formatting:
        # - Remove/convert Slack mentions (<@USER123> -> @user)
        # - Convert channel references (<#CHANNEL123|channel> -> #channel)
        # - Handle link formatting (<https://example.com|link text> -> link text)
        text = self._clean_slack_formatting(text)

        return text.strip()

    def _sanitize_input(self, text: str) -> str:
        """Sanitize input text to prevent injection attacks and ensure safe processing.

        Args:
            text: Raw input text

        Returns:
            Sanitized text safe for AI processing
        """
        import re

        # Remove potentially dangerous control characters
        # Keep only printable ASCII + common Unicode ranges
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

        # Limit maximum length to prevent resource exhaustion
        max_length = 10000  # Reasonable limit for Slack messages
        if len(text) > max_length:
            logger.warning(
                f"Input text truncated from {len(text)} to {max_length} characters"
            )
            text = text[:max_length] + "... [truncated for safety]"

        # Remove suspicious patterns that could be prompt injection attempts
        suspicious_patterns = [
            r"(?i)\bignore\s+(?:previous|all|above)\s+(?:instructions?|prompts?)\b",
            r"(?i)\bpretend\s+(?:to\s+be|you\s+are)\b",
            r"(?i)\bact\s+as\s+(?:if|though)\b",
            r"(?i)\bforget\s+(?:everything|all|what)\b",
            r"(?i)\brole\s*:\s*(?:system|admin|developer)\b",
            r"(?i)\boverride\s+(?:safety|security|guidelines?)\b",
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, text):
                logger.warning(f"Suspicious pattern detected in input: {pattern}")
                # Replace with neutral text rather than removing to maintain context
                text = re.sub(pattern, "[content filtered]", text)

        # Remove/neutralize markdown code blocks that could contain commands
        text = re.sub(r"```[^`]*```", "[code block removed]", text)
        text = re.sub(r"`[^`]+`", "[inline code removed]", text)

        # Only escape HTML/XML special characters if they appear to be markup
        # Don't escape apostrophes and quotes in normal text
        if "<" in text or ">" in text or "&" in text:
            import html

            # Only escape if it looks like markup
            if re.search(r"<[^>]+>", text) or re.search(r"&[a-zA-Z]+;", text):
                text = html.escape(text)

        return text

    def _clean_slack_formatting(self, text: str) -> str:
        """Clean Slack-specific formatting from text.

        Args:
            text: Text with Slack formatting

        Returns:
            Text with Slack formatting cleaned
        """
        import re

        # Convert user mentions <@USER123> to @user
        text = re.sub(r"<@([^>|]+)(?:\|([^>]+))?>", r"@\2" if "\\2" else "@user", text)

        # Convert channel mentions <#CHANNEL123|channelname> to #channelname
        text = re.sub(r"<#[^>|]+\|([^>]+)>", r"#\1", text)

        # Convert links <https://example.com|link text> to link text or URL
        text = re.sub(r"<(https?://[^>|]+)\|([^>]+)>", r"\2", text)  # Use link text
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)  # Use raw URL

        # Remove special Slack markup
        text = re.sub(r"<!(?:here|channel|everyone)>", "[group mention]", text)

        return text

    def cleanup_session_context(self, session: RequestSession) -> None:
        """Clean up context and session tracking after processing completion.

        Args:
            session: RequestSession to clean up
        """
        if not session:
            return

        thread_id = session.get_thread_id()

        try:
            # Mark session as cleaned up
            if hasattr(session, "mark_context_isolated"):
                session.mark_context_isolated(False)

            # Unregister from session tracker
            unregister_session(session)

            logger.debug(f"Cleaned up session context for thread {thread_id}")

        except Exception as e:
            logger.warning(
                f"Error cleaning up session context for thread {thread_id}: {e}"
            )

        finally:
            # Clear current session reference
            if self._current_session == session:
                self._current_session = None

    def get_current_session(self) -> Optional[RequestSession]:
        """Get currently active session for this analyzer."""
        return self._current_session

    def is_thread_isolated(self, thread_id: str) -> bool:
        """Check if a thread is properly isolated from other concurrent processing."""
        session_tracker = get_session_tracker()
        return session_tracker.is_thread_isolated(thread_id)


def cleanup_thread_context(thread_id: str) -> int:
    """Clean up all context and sessions for a specific thread.

    Args:
        thread_id: Thread identifier to clean up

    Returns:
        Number of sessions cleaned up
    """
    session_tracker = get_session_tracker()
    active_sessions = session_tracker.get_active_sessions_for_thread(thread_id)

    cleaned_count = 0
    for session in active_sessions:
        try:
            # Mark session as completed if not already
            if session.status not in [
                session.status.__class__.COMPLETED,
                session.status.__class__.ERROR,
            ]:
                session.complete_with_error("Context cleanup requested")

            # Unregister session
            unregister_session(session)
            cleaned_count += 1

        except Exception as e:
            logger.warning(
                f"Error cleaning up session {session.session_id} for thread {thread_id}: {e}"
            )

    logger.info(f"Cleaned up {cleaned_count} sessions for thread {thread_id}")
    return cleaned_count


def cleanup_expired_contexts(max_age_minutes: int = 30) -> int:
    """Clean up contexts that have been active for too long.

    Args:
        max_age_minutes: Maximum age for active contexts in minutes

    Returns:
        Number of expired contexts cleaned up
    """
    from datetime import timedelta

    session_tracker = get_session_tracker()
    cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)

    expired_sessions = []

    # Find expired sessions
    for session in session_tracker._active_sessions.values():
        if session.started_at < cutoff_time:
            expired_sessions.append(session)

    # Clean up expired sessions
    cleaned_count = 0
    for session in expired_sessions:
        try:
            session.complete_with_error("Session expired")
            unregister_session(session)
            cleaned_count += 1

        except Exception as e:
            logger.warning(
                f"Error cleaning up expired session {session.session_id}: {e}"
            )

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} expired contexts")

    return cleaned_count


def cleanup_all_contexts() -> int:
    """Clean up all active contexts and sessions.

    Returns:
        Number of contexts cleaned up
    """
    session_tracker = get_session_tracker()
    all_sessions = list(session_tracker._active_sessions.values())

    cleaned_count = 0
    for session in all_sessions:
        try:
            # Complete session if not already done
            if session.status not in [
                session.status.__class__.COMPLETED,
                session.status.__class__.ERROR,
            ]:
                session.complete_with_error("Global cleanup requested")

            # Unregister session
            unregister_session(session)
            cleaned_count += 1

        except Exception as e:
            logger.warning(
                f"Error during global cleanup of session {session.session_id}: {e}"
            )

    logger.info(f"Global cleanup completed: {cleaned_count} contexts cleaned up")
    return cleaned_count


def get_context_stats() -> dict[str, int]:
    """Get statistics about current context and session state.

    Returns:
        Dictionary with context statistics
    """
    session_tracker = get_session_tracker()

    stats = {
        "total_active_sessions": session_tracker.get_total_active_sessions(),
        "active_threads": len(session_tracker.get_active_threads()),
        "completed_sessions_cleaned": cleanup_completed_sessions(),
    }

    # Count sessions by status
    status_counts: dict[str, int] = {}
    for session in session_tracker._active_sessions.values():
        status = session.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    stats.update(
        {f"sessions_{status}": count for status, count in status_counts.items()}
    )

    return stats


async def periodic_context_cleanup(
    max_age_minutes: int = 30, cleanup_interval_seconds: int = 300
) -> None:
    """Perform periodic cleanup of expired contexts.

    Args:
        max_age_minutes: Maximum age for contexts before cleanup
        cleanup_interval_seconds: Interval between cleanup runs
    """
    import asyncio

    while True:
        try:
            # Clean up expired contexts
            expired_count = cleanup_expired_contexts(max_age_minutes)

            # Clean up completed sessions
            completed_count = cleanup_completed_sessions()

            if expired_count > 0 or completed_count > 0:
                logger.info(
                    f"Periodic cleanup: {expired_count} expired, {completed_count} completed sessions"
                )

        except Exception as e:
            logger.error(f"Error during periodic context cleanup: {e}")

        # Wait for next cleanup interval
        await asyncio.sleep(cleanup_interval_seconds)


def sanitize_input(text: str) -> str:
    """Sanitize user input before sending to Azure OpenAI.

    Args:
        text: Raw user input text

    Returns:
        Sanitized text safe for AI processing
    """
    if not text:
        return ""

    # Basic sanitization
    text = text.strip()

    # Remove or escape potentially problematic content
    # TODO: Add more sophisticated sanitization as needed:
    # - Remove personal information patterns
    # - Filter inappropriate content
    # - Escape special characters

    # Limit length to prevent abuse
    if len(text) > 4000:
        text = text[:4000] + "..."
        logger.warning("Truncated input text to 4000 characters")

    return text
