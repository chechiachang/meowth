"""Health check module for monitoring bot status."""

from typing import Dict, Any
from datetime import datetime, timezone

from .client import SlackClient
from .handlers.mention import MentionHandler


class HealthCheckService:
    """Service for monitoring bot health and performance."""

    def __init__(
        self, slack_client: SlackClient, mention_handler: MentionHandler
    ) -> None:
        """Initialize health check service with bot components."""
        self.slack_client = slack_client
        self.mention_handler = mention_handler
        self.start_time = datetime.now(timezone.utc)

    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the bot."""
        current_time = datetime.now(timezone.utc)
        uptime_seconds = (current_time - self.start_time).total_seconds()

        # Get client health
        client_health = self.slack_client.health_check()

        # Get channel statistics
        channel_stats = self.mention_handler.get_channel_stats()

        # Overall health determination
        is_healthy = (
            client_health.get("connected", False)
            and client_health.get("app_initialized", False)
            and client_health.get("handler_initialized", False)
        )

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": current_time.isoformat(),
            "uptime_seconds": uptime_seconds,
            "components": {
                "slack_client": {
                    "status": "healthy"
                    if client_health.get("connected")
                    else "unhealthy",
                    "connected": client_health.get("connected", False),
                    "reconnect_attempts": client_health.get("reconnect_attempts", 0),
                    "auth_test": client_health.get("auth_test"),
                },
                "mention_handler": {
                    "status": "healthy",
                    "channels_tracked": channel_stats.get("total_channels", 0),
                    "channels": channel_stats.get("channels", []),
                },
            },
            "metrics": {
                "uptime_hours": uptime_seconds / 3600,
                "uptime_days": uptime_seconds / 86400,
                "memory_usage": self._get_memory_usage(),
            },
        }

    def get_readiness_status(self) -> Dict[str, Any]:
        """Get readiness status - can the bot handle requests?"""
        client_health = self.slack_client.health_check()

        is_ready = client_health.get("connected", False) and client_health.get(
            "app_initialized", False
        )

        return {
            "ready": is_ready,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependencies": {"slack_api": client_health.get("connected", False)},
        }

    def get_liveness_status(self) -> Dict[str, Any]:
        """Get liveness status - is the bot process alive?"""
        return {
            "alive": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": (
                datetime.now(timezone.utc) - self.start_time
            ).total_seconds(),
        }

    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        try:
            import psutil  # type: ignore[import-untyped]
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return {
                "rss_bytes": memory_info.rss,
                "vms_bytes": memory_info.vms,
                "rss_mb": memory_info.rss / (1024 * 1024),
                "vms_mb": memory_info.vms / (1024 * 1024),
            }
        except ImportError:
            return {"error": "psutil not available"}
        except Exception as e:
            return {"error": f"Failed to get memory usage: {e}"}
