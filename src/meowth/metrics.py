"""Performance monitoring and metrics collection for the Slack bot."""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class MetricEvent:
    """A single metric event."""

    timestamp: datetime
    metric_name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates performance metrics."""

    def __init__(self) -> None:
        """Initialize the metrics collector."""
        self._metrics: List[MetricEvent] = []
        self._counters: Dict[str, int] = {}
        self._timers: Dict[str, List[float]] = {}
        self._lock = Lock()
        self.start_time = datetime.now(timezone.utc)

    def increment(
        self, metric_name: str, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        with self._lock:
            key = f"{metric_name}:{self._tags_to_string(tags or {})}"
            self._counters[key] = self._counters.get(key, 0) + 1

            self._metrics.append(
                MetricEvent(
                    timestamp=datetime.now(timezone.utc),
                    metric_name=metric_name,
                    value=1,
                    tags=tags or {},
                )
            )

    def record_timing(
        self,
        metric_name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a timing metric."""
        with self._lock:
            key = f"{metric_name}:{self._tags_to_string(tags or {})}"
            if key not in self._timers:
                self._timers[key] = []
            self._timers[key].append(duration_ms)

            self._metrics.append(
                MetricEvent(
                    timestamp=datetime.now(timezone.utc),
                    metric_name=metric_name,
                    value=duration_ms,
                    tags=tags or {},
                )
            )

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all collected metrics."""
        with self._lock:
            current_time = datetime.now(timezone.utc)
            uptime_seconds = (current_time - self.start_time).total_seconds()

            # Calculate timer statistics
            timer_stats = {}
            for key, timings in self._timers.items():
                if timings:
                    timer_stats[key] = {
                        "count": len(timings),
                        "avg_ms": sum(timings) / len(timings),
                        "min_ms": min(timings),
                        "max_ms": max(timings),
                        "total_ms": sum(timings),
                    }

            return {
                "timestamp": current_time.isoformat(),
                "uptime_seconds": uptime_seconds,
                "counters": dict(self._counters),
                "timers": timer_stats,
                "total_events": len(self._metrics),
            }

    def get_recent_metrics(self, last_minutes: int = 5) -> List[MetricEvent]:
        """Get metrics from the last N minutes."""
        cutoff_time = datetime.now(timezone.utc).timestamp() - (last_minutes * 60)

        with self._lock:
            return [
                metric
                for metric in self._metrics
                if metric.timestamp.timestamp() > cutoff_time
            ]

    def _tags_to_string(self, tags: Dict[str, str]) -> str:
        """Convert tags dictionary to a consistent string representation."""
        return ",".join(f"{k}={v}" for k, v in sorted(tags.items()))


class PerformanceTimer:
    """Context manager for timing code execution."""

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        metric_name: str,
        tags: Optional[Dict[str, str]] = None,
    ):
        """Initialize the performance timer."""
        self.metrics_collector = metrics_collector
        self.metric_name = metric_name
        self.tags = tags
        self.start_time: Optional[float] = None

    def __enter__(self) -> "PerformanceTimer":
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing and record metric."""
        if self.start_time is not None:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            self.metrics_collector.record_timing(
                self.metric_name, duration_ms, self.tags
            )


# Global metrics collector instance
metrics = MetricsCollector()


def time_it(
    metric_name: str, tags: Optional[Dict[str, str]] = None
) -> PerformanceTimer:
    """Decorator/context manager to time function or code block execution."""
    return PerformanceTimer(metrics, metric_name, tags)


def increment_counter(metric_name: str, tags: Optional[Dict[str, str]] = None) -> None:
    """Convenience function to increment a counter."""
    metrics.increment(metric_name, tags)
