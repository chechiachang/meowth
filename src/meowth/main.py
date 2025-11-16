"""Main entry point for Meowth Slack bot."""

import logging
import signal
import sys
from typing import NoReturn, Any

from .utils.config import config
from .utils.logging import setup_logging, log_connection_status
from .models import BotInstance
from .client import SlackClient
from .bot import MeowthBot


def signal_handler(signum: int, frame: Any) -> NoReturn:
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger("meowth")
    log_connection_status(logger, "shutting_down", f"Received signal {signum}")

    # Cleanup logic (if we had global references to client/bot)
    # This would be where we'd call client.stop() etc.
    logger.info("Graceful shutdown completed")
    sys.exit(0)


def main() -> None:
    """Main function to start the Meowth Slack bot."""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Validate configuration
        config.validate()

        # Set up logging
        logger = setup_logging(config.log_level)
        logger.info("Starting Meowth Slack bot")

        # Create bot instance
        bot_instance = BotInstance(
            bot_token=config.slack_bot_token, app_token=config.slack_app_token
        )

        # Create Slack client
        slack_client = SlackClient(bot_instance, logger)

        # Create and configure the bot
        meowth_bot = MeowthBot(slack_client, logger)
        meowth_bot.setup_handlers()

        # Connect and start the bot
        slack_client.connect()
        logger.info("Bot connected, starting event handler")

        slack_client.start()

    except ValueError as e:
        # Configuration errors
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        # Connection or runtime errors
        print(f"Runtime error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Unexpected errors
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
