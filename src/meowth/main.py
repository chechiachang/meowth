"""Main entry point for Meowth Slack bot."""

import logging
import signal
import sys
from typing import NoReturn, Any, Optional

from .utils.config import config
from .utils.logging import setup_logging, log_connection_status
from .models import BotInstance
from .client import SlackClient
from .bot import MeowthBot
from .ai.monitoring import get_langfuse_observe_decorator

# Global references for cleanup
_slack_client: Optional[SlackClient] = None
_meowth_bot: Optional[MeowthBot] = None


def signal_handler(signum: int, frame: Any) -> NoReturn:
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger("meowth")
    log_connection_status(logger, "shutting_down", f"Received signal {signum}")

    # Cleanup logic
    if _slack_client:
        try:
            _slack_client.stop()
        except Exception as e:
            logger.warning(f"Error during Slack client shutdown: {e}")

    if _meowth_bot:
        try:
            _meowth_bot.cleanup()
        except Exception as e:
            logger.warning(f"Error during bot cleanup: {e}")

    logger.info("Graceful shutdown completed")
    sys.exit(0)


def main() -> None:
    """Main function to start the Meowth Slack bot."""
    global _slack_client, _meowth_bot

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Validate configuration
        config.validate()

        # Set up logging
        logger = setup_logging(config.log_level)
        logger.info("Starting Meowth Slack bot")

        # Log Langfuse monitoring status
        try:
            observe_decorator = get_langfuse_observe_decorator()
            # Check if keys are at least configured
            has_keys = bool(config.langfuse_public_key.strip() and config.langfuse_secret_key.strip())
            if has_keys:
                logger.info("🔍 Langfuse AI monitoring: ENABLED - AI operations will be traced using observe decorators")
            else:
                logger.info("🔍 Langfuse AI monitoring: DISABLED - set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable")
        except Exception as e:
            logger.warning(f"🔍 Langfuse AI monitoring: ERROR during setup - {e}")

        # Create bot instance
        bot_instance = BotInstance(
            bot_token=config.slack_bot_token, app_token=config.slack_app_token
        )

        # Create Slack client
        _slack_client = SlackClient(bot_instance, logger)

        # Create and configure the bot
        _meowth_bot = MeowthBot(_slack_client, logger)
        _meowth_bot.setup_handlers()

        # Connect and start the bot
        _slack_client.connect()
        logger.info("Bot connected, starting event handler")

        _slack_client.start()

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
    finally:
        # Ensure cleanup happens even if exceptions occur
        if _meowth_bot:
            try:
                _meowth_bot.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    main()
