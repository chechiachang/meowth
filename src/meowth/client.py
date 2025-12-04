"""Slack client wrapper with reconnection logic and error handling."""

import logging
import time
from typing import Optional, Callable, Dict, Any
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError

from .models import BotInstance, ResponseMessage
from .utils.logging import log_connection_status, log_error


class SlackClient:
    """Slack client wrapper with automatic reconnection and error handling."""

    def __init__(self, bot_instance: BotInstance, logger: logging.Logger) -> None:
        """Initialize Slack client with bot instance configuration."""
        self.bot_instance = bot_instance
        self.logger = logger
        self.app: Optional[App] = None
        self.handler: Optional[SocketModeHandler] = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._base_reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._backoff_multiplier = 2.0
        self._jitter_enabled = True

    def initialize(self) -> App:
        """Initialize the Slack Bolt app."""
        if self.app is None:
            self.app = App(
                token=self.bot_instance.bot_token,
                signing_secret=None,  # Not needed for Socket Mode
                process_before_response=True,
            )
        return self.app

    def connect(self) -> None:
        """Connect to Slack using Socket Mode with exponential backoff retry."""
        while self._reconnect_attempts < self._max_reconnect_attempts:
            try:
                if self.app is None:
                    self.initialize()

                if self.app:
                    # Create Socket Mode handler
                    self.handler = SocketModeHandler(
                        app=self.app, app_token=self.bot_instance.app_token
                    )

                    # Test connection
                    if hasattr(self.handler.client, "auth_test"):
                        self.handler.client.auth_test()
                    else:
                        # Alternative connection test
                        pass

                    self.bot_instance.is_connected = True
                    self._reconnect_attempts = 0
                    log_connection_status(self.logger, "connected")
                    break

            except Exception as e:
                self._reconnect_attempts += 1
                self.bot_instance.is_connected = False

                # Calculate exponential backoff delay with optional jitter
                base_delay = self._base_reconnect_delay * (
                    self._backoff_multiplier ** (self._reconnect_attempts - 1)
                )
                delay = min(base_delay, self._max_reconnect_delay)

                # Add jitter to prevent thundering herd
                if self._jitter_enabled:
                    import random

                    jitter = random.uniform(0.1, 1.0)
                    delay = delay * jitter

                # Categorize errors for better handling
                error_category = self._categorize_connection_error(e)

                log_error(
                    self.logger,
                    e,
                    {
                        "attempt": self._reconnect_attempts,
                        "max_attempts": self._max_reconnect_attempts,
                        "retry_delay": delay,
                        "error_category": error_category,
                        "backoff_base": base_delay,
                        "jitter_applied": self._jitter_enabled,
                    },
                )

                if self._reconnect_attempts >= self._max_reconnect_attempts:
                    log_connection_status(
                        self.logger,
                        "failed",
                        f"Max reconnection attempts ({self._max_reconnect_attempts}) exceeded",
                    )
                    raise RuntimeError(
                        f"Failed to connect after {self._max_reconnect_attempts} attempts"
                    ) from e

                log_connection_status(
                    self.logger,
                    "reconnecting",
                    f"Retrying in {delay:.1f}s (attempt {self._reconnect_attempts})",
                )
                time.sleep(delay)

    def start(self) -> None:
        """Start the Socket Mode connection."""
        if not self.handler:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            self.handler.start()  # type: ignore[no-untyped-call]
        except Exception as e:
            self.bot_instance.is_connected = False
            log_connection_status(self.logger, "disconnected", str(e))
            raise

    def stop(self) -> None:
        """Stop the Socket Mode connection gracefully."""
        if self.handler:
            try:
                self.handler.close()  # type: ignore[no-untyped-call]  # type: ignore[no-untyped-call]
                self.bot_instance.is_connected = False
                log_connection_status(self.logger, "stopped")
            except Exception as e:
                log_error(self.logger, e, {"context": "graceful_shutdown"})

    def _categorize_connection_error(self, error: Exception) -> str:
        """Categorize connection errors for appropriate handling."""
        error_message = str(error).lower()

        # Network-related errors (usually retryable)
        if any(
            keyword in error_message
            for keyword in [
                "network",
                "connection",
                "timeout",
                "unreachable",
                "refused",
                "reset",
                "broken pipe",
            ]
        ):
            return "network"

        # Authentication errors (not retryable)
        if any(
            keyword in error_message
            for keyword in ["auth", "token", "invalid", "unauthorized", "forbidden"]
        ):
            return "authentication"

        # Rate limiting (retryable with backoff)
        if any(
            keyword in error_message
            for keyword in ["rate", "limit", "throttle", "quota"]
        ):
            return "rate_limit"

        # Service unavailable (retryable)
        if any(
            keyword in error_message
            for keyword in ["unavailable", "maintenance", "internal", "server error"]
        ):
            return "service"

        # Configuration errors (not retryable)
        if any(
            keyword in error_message
            for keyword in ["config", "missing", "required", "invalid format"]
        ):
            return "configuration"

        # Default to unknown (treat as retryable with caution)
        return "unknown"

    def _should_retry_error(self, error: Exception) -> bool:
        """Determine if an error should be retried."""
        category = self._categorize_connection_error(error)

        # Don't retry authentication or configuration errors
        if category in ["authentication", "configuration"]:
            return False

        # Always retry network, service, and rate limit errors
        if category in ["network", "service", "rate_limit"]:
            return True

        # For unknown errors, retry with caution (limited attempts)
        if category == "unknown":
            return self._reconnect_attempts < (self._max_reconnect_attempts // 2)

        return True

    def _extract_retry_after(self, response: Dict[str, Any]) -> float:
        """Extract retry-after value from rate limit response."""
        # Check for Retry-After header
        headers = response.get("headers", {})
        if "Retry-After" in headers:
            try:
                return float(headers["Retry-After"])
            except (ValueError, TypeError):
                pass

        # Check for retry_after in response body
        if "retry_after" in response:
            try:
                return float(response["retry_after"])
            except (ValueError, TypeError):
                pass

        # Default backoff for rate limits
        return 30.0

    def _calculate_backoff_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = base_delay * (self._backoff_multiplier**attempt)
        delay = min(delay, self._max_reconnect_delay)

        if self._jitter_enabled:
            import random

            jitter = random.uniform(0.5, 1.5)
            delay = delay * jitter

        return delay

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the Slack connection."""
        health_status: Dict[str, Any] = {
            "connected": self.bot_instance.is_connected,
            "reconnect_attempts": self._reconnect_attempts,
            "max_reconnect_attempts": self._max_reconnect_attempts,
            "app_initialized": self.app is not None,
            "handler_initialized": self.handler is not None,
            "timestamp": time.time(),
        }

        if self.app and self.bot_instance.is_connected:
            try:
                # Try a lightweight API call to verify connection
                response = self.app.client.auth_test()
                auth_test_result: Dict[str, Any] = {
                    "success": response.get("ok", False),
                    "user": response.get("user"),
                    "team": response.get("team"),
                    "response_time_ms": None,  # Could add timing here
                }
                health_status["auth_test"] = auth_test_result
            except Exception as e:
                auth_test_error: Dict[str, Any] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
                health_status["auth_test"] = auth_test_error

        return health_status

    def get_connection_metrics(self) -> Dict[str, Any]:
        """Get detailed connection metrics for monitoring."""
        return {
            "connection_state": {
                "is_connected": self.bot_instance.is_connected,
                "reconnect_attempts": self._reconnect_attempts,
                "max_reconnect_attempts": self._max_reconnect_attempts,
            },
            "configuration": {
                "base_reconnect_delay": self._base_reconnect_delay,
                "max_reconnect_delay": self._max_reconnect_delay,
                "backoff_multiplier": self._backoff_multiplier,
                "jitter_enabled": self._jitter_enabled,
            },
            "components": {
                "app_initialized": self.app is not None,
                "handler_initialized": self.handler is not None,
            },
        }

    def send_message(self, response_message: ResponseMessage) -> bool:
        """
        Send a response message to Slack.

        Returns True if successful, False otherwise.
        """
        if not self.app:
            raise RuntimeError("Slack app not initialized")

        try:
            result = self.app.client.chat_postMessage(
                channel=response_message.channel_id,
                text=response_message.text,
                thread_ts=response_message.thread_ts,
            )

            if result["ok"]:
                response_message.mark_sent()
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                response_message.mark_failed(error_msg)
                return False

        except SlackApiError as e:
            error_code = e.response["error"]

            # Channel-specific error context for better debugging
            channel_context = {
                "response_id": response_message.response_id,
                "channel_id": response_message.channel_id,
                "error_code": error_code,
                "error_details": e.response.get("details", {}),
            }

            # Handle specific error types
            if error_code in [
                "channel_not_found",
                "not_in_channel",
                "account_inactive",
                "is_archived",
            ]:
                # Non-retryable channel access errors
                self.logger.warning(
                    f"Channel access error in {response_message.channel_id}: {error_code}",
                    extra={"event_type": "channel_access_error", **channel_context},
                )
                response_message.mark_failed(f"Permanent error: {error_code}")
                return False
            elif error_code in ["rate_limited", "internal_error"]:
                # Enhanced rate limit handling
                retry_after = self._extract_retry_after(e.response)

                if error_code == "rate_limited":
                    self.logger.warning(
                        f"Rate limited in {response_message.channel_id}, retry after {retry_after}s",
                        extra={
                            "event_type": "rate_limit_error",
                            "retry_after_seconds": retry_after,
                            **channel_context,
                        },
                    )
                else:
                    self.logger.info(
                        f"Internal error in {response_message.channel_id}: {error_code}",
                        extra={"event_type": "retryable_error", **channel_context},
                    )
                response_message.mark_retrying()
                return False
            else:
                # Unknown error, treat as non-retryable for now
                self.logger.error(
                    f"Unknown API error in {response_message.channel_id}: {error_code}",
                    extra={"event_type": "unknown_api_error", **channel_context},
                )
                response_message.mark_failed(f"API error: {error_code}")
                return False

        except Exception as e:
            response_message.mark_failed(f"Unexpected error: {str(e)}")
            log_error(
                self.logger,
                e,
                {
                    "response_id": response_message.response_id,
                    "channel_id": response_message.channel_id,
                },
            )
            return False

    def add_event_handler(self, event_type: str, handler: Callable) -> None:
        """Add an event handler to the Slack app."""
        if not self.app:
            raise RuntimeError("Slack app not initialized")

        self.app.event(event_type)(handler)

    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel information from Slack API.
        
        Args:
            channel_id: Slack channel ID
            
        Returns:
            Channel info dict or None if error
        """
        if not self.app:
            return None
            
        try:
            result = self.app.client.conversations_info(channel=channel_id)
            return result.get("channel")
        except SlackApiError as e:
            self.logger.warning(f"Failed to get channel info for {channel_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting channel info: {e}")
            return None

    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information from Slack API.
        
        Args:
            user_id: Slack user ID
            
        Returns:
            User info dict or None if error
        """
        if not self.app:
            return None
            
        try:
            result = self.app.client.users_info(user=user_id)
            return result.get("user")
        except SlackApiError as e:
            self.logger.warning(f"Failed to get user info for {user_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting user info: {e}")
            return None
