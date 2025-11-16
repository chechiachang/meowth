"""Environment configuration management for Slack bot."""

import os
from dotenv import load_dotenv


class Config:
    """Configuration management for Slack bot environment variables."""

    def __init__(self) -> None:
        """Initialize configuration by loading environment variables."""
        load_dotenv()

    @property
    def slack_bot_token(self) -> str:
        """Get Slack Bot User OAuth Token."""
        token = os.getenv("SLACK_BOT_TOKEN")
        if not token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is required")
        if not token.startswith("xoxb-"):
            raise ValueError("SLACK_BOT_TOKEN must start with 'xoxb-'")
        return token

    @property
    def slack_app_token(self) -> str:
        """Get Slack App-Level Token for Socket Mode."""
        token = os.getenv("SLACK_APP_TOKEN")
        if not token:
            raise ValueError("SLACK_APP_TOKEN environment variable is required")
        if not token.startswith("xapp-"):
            raise ValueError("SLACK_APP_TOKEN must start with 'xapp-'")
        return token

    @property
    def log_level(self) -> str:
        """Get logging level, defaults to INFO."""
        return os.getenv("LOG_LEVEL", "INFO").upper()

    def validate(self) -> None:
        """Validate all required configuration values."""
        # This will raise ValueError if any required config is missing
        self.slack_bot_token
        self.slack_app_token

        # Validate log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(valid_levels)}")


# Global configuration instance
config = Config()
