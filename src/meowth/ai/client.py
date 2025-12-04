"""Azure OpenAI client wrapper with error handling and rate limiting.

This module provides a high-level interface to Azure OpenAI services with
built-in error handling, rate limiting, and Azure-specific configurations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from openai import (
    AsyncAzureOpenAI,
    APIError,
    RateLimitError as OpenAIRateLimitError,
    APITimeoutError,
)
import tiktoken

from ..utils.config import config
from .models import (
    AIResponse,
    AzureOpenAIError,
    RateLimitError,
    ThreadContext,
    RequestSession,
)

logger = logging.getLogger(__name__)


@dataclass
class AzureOpenAIConfig:
    """Configuration for Azure OpenAI client."""

    api_key: str
    endpoint: str
    deployment_name: str
    api_version: str
    model: str
    max_tokens: int = 1000
    temperature: float = 0.7
    max_retries: int = 3
    timeout: float = 30.0


class RateLimiter:
    """Token bucket rate limiter for Azure OpenAI API calls."""

    def __init__(self, max_requests_per_minute: int = 60):
        self.max_requests = max_requests_per_minute
        self.tokens = float(max_requests_per_minute)
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a rate limit token, blocking if necessary."""
        async with self.lock:
            now = time.time()
            # Refill tokens based on time passed
            elapsed = now - self.last_update
            self.tokens = min(
                self.max_requests, self.tokens + elapsed * (self.max_requests / 60.0)
            )
            self.last_update = now

            if self.tokens < 1:
                # Calculate wait time
                wait_time = (1 - self.tokens) / (self.max_requests / 60.0)
                logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
                self.tokens = 1

            self.tokens -= 1


class AzureOpenAIClient:
    """Azure OpenAI client with error handling and rate limiting."""

    def __init__(self, azure_config: Optional[AzureOpenAIConfig] = None):
        """Initialize Azure OpenAI client.

        Args:
            azure_config: Azure OpenAI configuration. If None, loads from environment.
        """
        if azure_config is None:
            azure_config = self._load_config_from_env()

        self.config = azure_config
        self.rate_limiter = RateLimiter(max_requests_per_minute=60)
        self._client = self._create_client()
        self._encoding = tiktoken.get_encoding("cl100k_base")  # GPT-3.5/4 encoding

        logger.info(
            f"Initialized Azure OpenAI client for endpoint: {azure_config.endpoint}"
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

    def _create_client(self) -> AsyncAzureOpenAI:
        """Create AsyncAzureOpenAI client configured for Azure."""
        return AsyncAzureOpenAI(
            api_key=self.config.api_key,
            azure_endpoint=self.config.endpoint,
            api_version=self.config.api_version,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        try:
            return len(self._encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            # Fallback: rough estimation (4 chars per token)
            return len(text) // 4

    async def generate_response(
        self,
        thread_context: ThreadContext,
        system_prompt: str = "You are a helpful Slack bot assistant.",
        user_message: Optional[str] = None,
        session: Optional["RequestSession"] = None,
        **kwargs: Any,
    ) -> AIResponse:
        """Generate AI response for thread context using Azure OpenAI with session tracking.

        Args:
            thread_context: Analyzed thread context
            system_prompt: System prompt for the AI
            user_message: Optional specific user message to respond to
            session: Optional RequestSession for tracking
            **kwargs: Additional parameters for the API call

        Returns:
            AIResponse with generated content and metadata

        Raises:
            AzureOpenAIError: If Azure OpenAI API call fails
            RateLimitError: If rate limit is exceeded
        """
        start_time = time.time()

        # Log session info if available
        session_info = f" (session: {session.session_id})" if session else ""

        # Build request context for monitoring
        request_context = {
            "thread_ts": thread_context.thread_ts,
            "message_count": len(thread_context.messages),
            "system_prompt_length": len(system_prompt),
            "session_id": session.session_id if session else None,
            "model": self.config.deployment_name,
        }

        try:
            # Apply rate limiting
            await self.rate_limiter.acquire()

            # Build messages for Azure OpenAI
            messages = self._build_messages(thread_context, system_prompt, user_message)

            # Count context tokens
            context_tokens = sum(self.count_tokens(msg["content"]) for msg in messages)

            # Add token count to request context
            request_context["context_tokens"] = context_tokens

            # Ensure we don't exceed token limits
            if context_tokens > 3000:  # Reserve 1000 tokens for response
                raise AzureOpenAIError(
                    f"Context too large: {context_tokens} tokens (max: 3000)",
                    error_code="CONTEXT_TOO_LARGE",
                )

            logger.info(
                f"Generating Azure OpenAI response for thread {thread_context.thread_ts} "
                f"with {context_tokens} context tokens{session_info}"
            )

            # Call Azure OpenAI API
            completion = await self._client.chat.completions.create(
                model=self.config.deployment_name,  # Use deployment name for Azure
                messages=messages,  # type: ignore[arg-type]
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                temperature=kwargs.get("temperature", self.config.temperature),
                **{
                    k: v
                    for k, v in kwargs.items()
                    if k not in ["max_tokens", "temperature"]
                },
            )

            generation_time = time.time() - start_time

            # Extract response content
            content = completion.choices[0].message.content or ""

            # Create AI response
            usage = completion.usage
            if not usage:
                raise ValueError("No usage information returned from Azure OpenAI")

            response = AIResponse(
                content=content,
                model_used=self.config.model,
                deployment_name=self.config.deployment_name,
                tokens_used=usage.total_tokens,
                generation_time=generation_time,
                context_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                azure_endpoint=self.config.endpoint,
            )

            logger.info(
                f"Generated Azure OpenAI response: {usage.total_tokens} tokens "
                f"in {generation_time:.2f}s{session_info}"
            )

            # Log successful request
            _azure_openai_monitor.log_success(
                {
                    "tokens_used": usage.total_tokens,
                    "context_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "generation_time": generation_time,
                    "model": self.config.model,
                    "deployment": self.config.deployment_name,
                }
            )

            return response

        except OpenAIRateLimitError as e:
            logger.warning(f"Azure OpenAI rate limit exceeded: {e}")
            _azure_openai_monitor.log_error(
                "rate_limit", str(e), context=request_context
            )
            raise RateLimitError(
                f"Azure OpenAI rate limit exceeded: {e}",
                retry_after=getattr(e, "retry_after", 60.0),
            )

        except APITimeoutError as e:
            logger.error(f"Azure OpenAI request timeout: {e}")
            _azure_openai_monitor.log_error("timeout", str(e), context=request_context)
            raise AzureOpenAIError(
                f"Azure OpenAI timeout: {e}", error_code="TIMEOUT_ERROR"
            )

        except APIError as e:
            logger.error(f"Azure OpenAI API error: {e}")
            error_code = getattr(e, "code", "UNKNOWN_API_ERROR")
            _azure_openai_monitor.log_error(
                "api", str(e), context={"error_code": error_code, **request_context}
            )
            raise AzureOpenAIError(
                f"Azure OpenAI API error: {e}", error_code=error_code
            )

        except AzureOpenAIError:
            # Re-raise our custom errors without modification
            raise

        except Exception as e:
            logger.error(f"Unexpected error in Azure OpenAI client: {e}")
            _azure_openai_monitor.log_error("internal", str(e), context=request_context)
            raise AzureOpenAIError(
                f"Unexpected Azure OpenAI error: {e}", error_code="INTERNAL_ERROR"
            )

    def _build_messages(
        self, thread_context: ThreadContext, system_prompt: str, user_message: Optional[str] = None
    ) -> list[Dict[str, str]]:
        """Build message list for Azure OpenAI chat completion.

        Args:
            thread_context: Thread context with messages
            system_prompt: System prompt for the AI
            user_message: Optional specific user message to respond to

        Returns:
            List of message dictionaries for OpenAI API
        """
        messages = [{"role": "system", "content": system_prompt}]

        # Add thread messages in chronological order
        for msg in thread_context.messages:
            # Determine role based on whether it's a bot message
            role = "assistant" if msg.is_bot_message else "user"

            # Format message with user context (but anonymize user ID)
            content = f"Message from user: {msg.text}"
            if msg.is_bot_message:
                content = msg.text  # Bot messages don't need user prefix

            messages.append({"role": role, "content": content})

        # Add final instruction
        if user_message:
            messages.append(
                {
                    "role": "user",
                    "content": user_message,
                }
            )
        else:
            messages.append(
                {
                    "role": "user",
                    "content": "Please provide a helpful response to the above conversation.",
                }
            )

        return messages

    async def health_check(self) -> bool:
        """Check if Azure OpenAI service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Simple test call with minimal tokens
            await self._client.chat.completions.create(
                model=self.config.deployment_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            logger.warning(f"Azure OpenAI health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the client and cleanup resources."""
        await self._client.close()
        logger.info("Azure OpenAI client closed")


class AzureOpenAIMonitor:
    """Monitoring and alerting for Azure OpenAI operations."""

    def __init__(self) -> None:
        """Initialize monitoring with error tracking."""
        self._error_counts: Dict[str, int] = {}
        self._success_count = 0
        self._last_errors: List[Dict[str, Any]] = []
        self._max_error_history = 100

        # Usage metrics tracking
        self._total_tokens_used = 0
        self._total_requests = 0
        self._total_generation_time = 0.0
        self._usage_history: List[Dict[str, Any]] = []  # Track detailed usage over time
        self._max_usage_history = 1000

        # Alert thresholds
        self._alert_thresholds = {
            "rate_limit_errors": 5,  # Alert if >5 rate limit errors in 10 min
            "api_errors": 3,  # Alert if >3 API errors in 10 min
            "timeout_errors": 2,  # Alert if >2 timeout errors in 10 min
            "quota_errors": 1,  # Alert immediately on quota errors
        }
        self._alert_window_minutes = 10

    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log an Azure OpenAI error for monitoring.

        Args:
            error_type: Type of error (rate_limit, api_error, timeout, quota, etc.)
            error_message: Detailed error message
            context: Additional context (thread_id, session_id, etc.)
        """
        error_entry = {
            "timestamp": datetime.now(),
            "type": error_type,
            "message": error_message,
            "context": context or {},
        }

        # Add to error history
        self._last_errors.append(error_entry)
        if len(self._last_errors) > self._max_error_history:
            self._last_errors.pop(0)

        # Update error counts
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

        # Check if we should trigger an alert
        self._check_alert_conditions(error_type, error_entry)

        # Log the error
        logger.error(
            f"Azure OpenAI {error_type}: {error_message}",
            extra={
                "error_type": error_type,
                "context": context,
                "total_count": self._error_counts[error_type],
            },
        )

    def log_success(self, context: Optional[dict[str, Any]] = None) -> None:
        """Log a successful Azure OpenAI request.

        Args:
            context: Additional context for the success (tokens used, generation time, etc.)
        """
        self._success_count += 1
        self._total_requests += 1

        if context:
            # Track token usage
            tokens_used = context.get("tokens_used", 0)
            self._total_tokens_used += tokens_used

            # Track generation time
            generation_time = context.get("generation_time", 0.0)
            self._total_generation_time += generation_time

            # Store detailed usage record
            usage_record = {
                "timestamp": datetime.now(),
                "tokens_used": tokens_used,
                "context_tokens": context.get("context_tokens", 0),
                "completion_tokens": context.get("completion_tokens", 0),
                "generation_time": generation_time,
                "model": context.get("model"),
                "deployment": context.get("deployment"),
            }

            self._usage_history.append(usage_record)

            # Trim usage history if too large
            if len(self._usage_history) > self._max_usage_history:
                self._usage_history = self._usage_history[-self._max_usage_history :]

            logger.debug(
                f"Azure OpenAI success: {self._success_count} total, {tokens_used} tokens",
                extra={
                    "success_count": self._success_count,
                    "tokens_used": tokens_used,
                    "total_tokens": self._total_tokens_used,
                },
            )

    def _check_alert_conditions(
        self, error_type: str, error_entry: dict[str, Any]
    ) -> None:
        """Check if error conditions warrant an alert."""
        from datetime import timedelta

        # Count recent errors of this type
        cutoff_time = datetime.now() - timedelta(minutes=self._alert_window_minutes)
        recent_errors = [
            err
            for err in self._last_errors
            if err["type"] == error_type and err["timestamp"] > cutoff_time
        ]

        threshold = self._alert_thresholds.get(error_type, 10)

        if len(recent_errors) >= threshold:
            self._trigger_alert(error_type, len(recent_errors), error_entry)

    def _trigger_alert(
        self, error_type: str, error_count: int, latest_error: dict[str, Any]
    ) -> None:
        """Trigger an alert for Azure OpenAI errors."""
        alert_message = (
            f"Azure OpenAI Alert: {error_count} {error_type} errors in last "
            f"{self._alert_window_minutes} minutes. Latest: {latest_error['message']}"
        )

        # Log critical alert
        logger.critical(
            alert_message,
            extra={
                "alert_type": "azure_openai_error_threshold",
                "error_type": error_type,
                "error_count": error_count,
                "window_minutes": self._alert_window_minutes,
                "latest_error": latest_error,
            },
        )

        # TODO: Add integration with alerting systems (email, Slack, PagerDuty, etc.)
        # For now, just log at critical level which should be picked up by log monitoring

    def get_error_summary(self, hours: int = 24) -> dict:
        """Get error summary for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with error statistics
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = [
            err for err in self._last_errors if err["timestamp"] > cutoff_time
        ]

        # Count by type
        error_types: dict[str, int] = {}
        for error in recent_errors:
            error_type = error["type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "time_window_hours": hours,
            "total_errors": len(recent_errors),
            "total_successes": self._success_count,
            "error_types": error_types,
            "last_error": self._last_errors[-1] if self._last_errors else None,
            "alert_thresholds": self._alert_thresholds,
        }

    def reset_error_counts(self) -> None:
        """Reset error counts, usage metrics and history (for testing or maintenance)."""
        self._error_counts.clear()
        self._last_errors.clear()
        self._success_count = 0
        self._total_tokens_used = 0
        self._total_requests = 0
        self._total_generation_time = 0.0
        self._usage_history.clear()
        logger.info("Azure OpenAI monitoring data reset")

    def is_healthy(self) -> bool:
        """Check if Azure OpenAI service appears healthy based on recent errors."""
        from datetime import timedelta

        # Consider unhealthy if we've had any alerts in the last hour
        cutoff_time = datetime.now() - timedelta(hours=1)
        recent_critical_errors = [
            err
            for err in self._last_errors
            if err["timestamp"] > cutoff_time
            and err["type"] in ["quota_errors", "api_errors"]
        ]

        return len(recent_critical_errors) == 0

    def get_usage_metrics(self, hours: int = 24) -> dict:
        """Get usage metrics for the specified time period.

        Args:
            hours: Number of hours to look back for usage statistics

        Returns:
            Dictionary with usage statistics including token usage and performance metrics
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_usage = [
            record
            for record in self._usage_history
            if record["timestamp"] > cutoff_time
        ]

        if not recent_usage:
            return {
                "time_window_hours": hours,
                "total_requests": 0,
                "total_tokens": 0,
                "average_tokens_per_request": 0,
                "average_generation_time": 0.0,
                "token_breakdown": {"context": 0, "completion": 0},
            }

        total_tokens = sum(r["tokens_used"] for r in recent_usage)
        total_context_tokens = sum(r["context_tokens"] for r in recent_usage)
        total_completion_tokens = sum(r["completion_tokens"] for r in recent_usage)
        total_time = sum(r["generation_time"] for r in recent_usage)

        return {
            "time_window_hours": hours,
            "total_requests": len(recent_usage),
            "total_tokens": total_tokens,
            "average_tokens_per_request": total_tokens / len(recent_usage),
            "average_generation_time": total_time / len(recent_usage),
            "token_breakdown": {
                "context": total_context_tokens,
                "completion": total_completion_tokens,
            },
            "lifetime_totals": {
                "requests": self._total_requests,
                "tokens": self._total_tokens_used,
                "generation_time": self._total_generation_time,
            },
        }

    def check_quota_status(self, daily_token_limit: int = 100000) -> dict:
        """Check current token usage against daily quota.

        Args:
            daily_token_limit: Daily token limit (default: 100K tokens)

        Returns:
            Dictionary with quota status and alerts
        """
        today_metrics = self.get_usage_metrics(hours=24)
        tokens_used_today = today_metrics["total_tokens"]

        usage_percentage = (tokens_used_today / daily_token_limit) * 100

        quota_status = {
            "daily_limit": daily_token_limit,
            "tokens_used_today": tokens_used_today,
            "tokens_remaining": max(0, daily_token_limit - tokens_used_today),
            "usage_percentage": usage_percentage,
            "status": "normal",
            "alerts": [],
        }

        # Generate alerts based on usage
        if usage_percentage >= 95:
            quota_status["status"] = "critical"
            quota_status["alerts"].append("CRITICAL: 95%+ of daily token quota used")
        elif usage_percentage >= 80:
            quota_status["status"] = "warning"
            quota_status["alerts"].append("WARNING: 80%+ of daily token quota used")
        elif usage_percentage >= 60:
            quota_status["status"] = "caution"
            quota_status["alerts"].append("CAUTION: 60%+ of daily token quota used")

        # Log quota alerts
        if quota_status["alerts"]:
            for alert in quota_status["alerts"]:
                logger.warning(
                    f"Azure OpenAI quota alert: {alert}",
                    extra={"quota_status": quota_status, "alert_type": "quota_usage"},
                )

        return quota_status


# Global monitoring instance
_azure_openai_monitor = AzureOpenAIMonitor()


def get_azure_openai_monitor() -> AzureOpenAIMonitor:
    """Get the global Azure OpenAI monitor instance."""
    return _azure_openai_monitor


# Global client instance (will be initialized when needed)
_azure_openai_client: Optional[AzureOpenAIClient] = None


def get_azure_openai_client() -> AzureOpenAIClient:
    """Get or create the global Azure OpenAI client instance."""
    global _azure_openai_client
    if _azure_openai_client is None:
        _azure_openai_client = AzureOpenAIClient()
    return _azure_openai_client


async def cleanup_azure_openai_client() -> None:
    """Cleanup the global Azure OpenAI client."""
    global _azure_openai_client
    if _azure_openai_client is not None:
        await _azure_openai_client.close()
        _azure_openai_client = None
