"""Rate limiting with circuit breaker pattern for Slack API.

This module implements intelligent rate limiting for Slack API calls with
circuit breaker functionality to handle API limits gracefully.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass

from .exceptions import RateLimitError, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, rejecting requests
    HALF_OPEN = "half_open"  # Testing if circuit can close


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 50
    burst_limit: int = 100
    circuit_failure_threshold: int = 5
    circuit_timeout: float = 60.0
    circuit_test_requests: int = 3


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    test_request_count: int = 0

    def reset(self):
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.test_request_count = 0

    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

    def record_success(self):
        """Record a success and potentially close the circuit."""
        self.failure_count = 0
        self.test_request_count = 0


class SlackRateLimiter:
    """Rate limiter with circuit breaker for Slack API calls.

    This class implements intelligent rate limiting based on Slack's API tiers
    with circuit breaker functionality to handle rate limit errors gracefully.

    Slack API Tiers:
    - Tier 1: 1+ requests per minute
    - Tier 2: 20+ requests per minute
    - Tier 3: 50+ requests per minute
    - Tier 4: 100+ requests per minute
    """

    def __init__(
        self,
        tier: str = "tier2",
        config: Optional[RateLimitConfig] = None,
        enable_circuit_breaker: bool = True,
    ):
        """Initialize rate limiter.

        Args:
            tier: Slack API tier (tier1, tier2, tier3, tier4)
            config: Rate limiting configuration
            enable_circuit_breaker: Whether to enable circuit breaker
        """
        self.tier = tier
        self.config = config or self._get_default_config(tier)
        self.enable_circuit_breaker = enable_circuit_breaker

        # Rate limiting state
        self._request_times: Dict[str, deque] = defaultdict(lambda: deque())
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Circuit breaker state
        self._circuit_states: Dict[str, CircuitBreakerState] = defaultdict(
            CircuitBreakerState
        )

        logger.info(
            f"Initialized SlackRateLimiter for {tier} with {self.config.requests_per_minute} RPM"
        )

    def _get_default_config(self, tier: str) -> RateLimitConfig:
        """Get default configuration for Slack API tier.

        Args:
            tier: Slack API tier

        Returns:
            Default rate limit configuration
        """
        configs = {
            "tier1": RateLimitConfig(requests_per_minute=1, burst_limit=2),
            "tier2": RateLimitConfig(requests_per_minute=20, burst_limit=40),
            "tier3": RateLimitConfig(requests_per_minute=50, burst_limit=100),
            "tier4": RateLimitConfig(requests_per_minute=100, burst_limit=200),
        }
        return configs.get(tier, configs["tier2"])

    async def acquire(self, endpoint: str = "default") -> bool:
        """Acquire a rate limit token for an API call.

        Args:
            endpoint: API endpoint name for separate rate limiting

        Returns:
            True if request can proceed, raises RateLimitError if not

        Raises:
            RateLimitError: If rate limit is exceeded or circuit is open
        """
        async with self._locks[endpoint]:
            # Check circuit breaker first
            if self.enable_circuit_breaker:
                circuit_state = self._circuit_states[endpoint]

                if circuit_state.state == CircuitState.OPEN:
                    # Check if circuit should transition to half-open
                    if self._should_attempt_reset(circuit_state):
                        circuit_state.state = CircuitState.HALF_OPEN
                        circuit_state.test_request_count = 0
                        logger.info(
                            f"Circuit breaker transitioning to HALF_OPEN for {endpoint}"
                        )
                    else:
                        wait_time = self._get_circuit_wait_time(circuit_state)
                        raise RateLimitError(
                            f"Circuit breaker is OPEN for {endpoint}",
                            retry_after=wait_time,
                            endpoint=endpoint,
                            category=ErrorCategory.RATE_LIMIT,
                            severity=ErrorSeverity.HIGH,
                            user_guidance=f"API is temporarily unavailable. Try again in {wait_time:.0f} seconds.",
                        )

                elif circuit_state.state == CircuitState.HALF_OPEN:
                    # Allow limited test requests
                    if (
                        circuit_state.test_request_count
                        >= self.config.circuit_test_requests
                    ):
                        circuit_state.state = CircuitState.OPEN
                        wait_time = self.config.circuit_timeout
                        raise RateLimitError(
                            f"Circuit breaker test failed for {endpoint}",
                            retry_after=wait_time,
                            endpoint=endpoint,
                        )
                    circuit_state.test_request_count += 1

            # Check rate limits
            current_time = time.time()
            request_times = self._request_times[endpoint]

            # Remove old requests outside the time window
            cutoff_time = current_time - 60.0  # 1 minute window
            while request_times and request_times[0] < cutoff_time:
                request_times.popleft()

            # Check if we can make the request
            if len(request_times) >= self.config.requests_per_minute:
                # Check burst limit
                recent_cutoff = current_time - 10.0  # 10 second burst window
                recent_requests = sum(1 for t in request_times if t > recent_cutoff)

                if recent_requests >= self.config.burst_limit:
                    wait_time = self._calculate_wait_time(request_times, current_time)

                    # Record as potential circuit breaker trigger
                    if self.enable_circuit_breaker:
                        self._record_rate_limit(endpoint)

                    raise RateLimitError(
                        f"Rate limit exceeded for {endpoint}: {len(request_times)} requests in last minute",
                        retry_after=wait_time,
                        endpoint=endpoint,
                        user_guidance=f"Too many requests. Please wait {wait_time:.0f} seconds before trying again.",
                    )

            # Record the request
            request_times.append(current_time)
            logger.debug(
                f"Rate limit acquired for {endpoint}: {len(request_times)}/{self.config.requests_per_minute}"
            )

            return True

    def record_success(self, endpoint: str = "default") -> None:
        """Record a successful API call.

        Args:
            endpoint: API endpoint name
        """
        if self.enable_circuit_breaker:
            circuit_state = self._circuit_states[endpoint]

            if circuit_state.state in [CircuitState.HALF_OPEN, CircuitState.OPEN]:
                # Success in half-open state - close the circuit
                circuit_state.reset()
                circuit_state.state = CircuitState.CLOSED
                logger.info(
                    f"Circuit breaker closed for {endpoint} after successful request"
                )

            circuit_state.record_success()

    def record_failure(
        self, endpoint: str = "default", is_rate_limit: bool = False
    ) -> None:
        """Record a failed API call.

        Args:
            endpoint: API endpoint name
            is_rate_limit: Whether failure was due to rate limiting
        """
        if self.enable_circuit_breaker:
            circuit_state = self._circuit_states[endpoint]
            circuit_state.record_failure()

            # Open circuit if failure threshold exceeded
            if circuit_state.failure_count >= self.config.circuit_failure_threshold:
                circuit_state.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker opened for {endpoint} after {circuit_state.failure_count} failures"
                )

            if is_rate_limit:
                logger.warning(
                    f"Rate limit hit for {endpoint}, failure count: {circuit_state.failure_count}"
                )

    def get_wait_time(self, endpoint: str = "default") -> float:
        """Get recommended wait time before next request.

        Args:
            endpoint: API endpoint name

        Returns:
            Recommended wait time in seconds
        """
        if self.enable_circuit_breaker:
            circuit_state = self._circuit_states[endpoint]

            if circuit_state.state == CircuitState.OPEN:
                return self._get_circuit_wait_time(circuit_state)

        request_times = self._request_times[endpoint]
        if not request_times:
            return 0.0

        current_time = time.time()
        return self._calculate_wait_time(request_times, current_time)

    def get_status(self, endpoint: str = "default") -> Dict[str, any]:
        """Get current rate limiting status.

        Args:
            endpoint: API endpoint name

        Returns:
            Dictionary with current status information
        """
        request_times = self._request_times[endpoint]
        circuit_state = self._circuit_states[endpoint]
        current_time = time.time()

        # Count recent requests
        cutoff_time = current_time - 60.0
        recent_requests = sum(1 for t in request_times if t > cutoff_time)

        return {
            "endpoint": endpoint,
            "tier": self.tier,
            "requests_per_minute_limit": self.config.requests_per_minute,
            "recent_requests": recent_requests,
            "circuit_state": circuit_state.state.value,
            "failure_count": circuit_state.failure_count,
            "wait_time": self.get_wait_time(endpoint),
            "can_make_request": recent_requests < self.config.requests_per_minute,
        }

    def _should_attempt_reset(self, circuit_state: CircuitBreakerState) -> bool:
        """Check if circuit breaker should attempt reset.

        Args:
            circuit_state: Current circuit state

        Returns:
            True if reset should be attempted
        """
        return (
            circuit_state.state == CircuitState.OPEN
            and time.time() - circuit_state.last_failure_time
            > self.config.circuit_timeout
        )

    def _get_circuit_wait_time(self, circuit_state: CircuitBreakerState) -> float:
        """Calculate wait time for open circuit.

        Args:
            circuit_state: Current circuit state

        Returns:
            Wait time in seconds
        """
        elapsed = time.time() - circuit_state.last_failure_time
        return max(0.0, self.config.circuit_timeout - elapsed)

    def _calculate_wait_time(self, request_times: deque, current_time: float) -> float:
        """Calculate how long to wait before next request.

        Args:
            request_times: Deque of recent request timestamps
            current_time: Current timestamp

        Returns:
            Wait time in seconds
        """
        if not request_times:
            return 0.0

        # Find the oldest request in the current minute
        cutoff_time = current_time - 60.0
        valid_requests = [t for t in request_times if t > cutoff_time]

        if len(valid_requests) < self.config.requests_per_minute:
            return 0.0

        # Wait until the oldest request is outside the minute window
        oldest_request = min(valid_requests)
        wait_time = 60.0 - (current_time - oldest_request)

        return max(1.0, wait_time)  # Minimum 1 second wait

    def _record_rate_limit(self, endpoint: str) -> None:
        """Record a rate limit event for circuit breaker logic.

        Args:
            endpoint: API endpoint name
        """
        # Rate limits count as failures for circuit breaker
        self.record_failure(endpoint, is_rate_limit=True)
