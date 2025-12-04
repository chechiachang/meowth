"""Configuration manager for AI agent tools.

This module provides configuration loading, validation, and hot-reload
capabilities for the AI agent tool system.
"""

import yaml
import logging
import threading
from pathlib import Path
from typing import Optional, Callable, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from .config import ToolsConfiguration
from .exceptions import ConfigurationError


logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration file changes."""

    def __init__(self, config_manager: "ConfigurationManager"):
        self.config_manager = config_manager

    def on_modified(self, event):
        """Handle file modification events."""
        if (
            isinstance(event, FileModifiedEvent)
            and not event.is_directory
            and Path(event.src_path) == self.config_manager.config_path
        ):
            logger.info(f"Configuration file modified: {event.src_path}")
            self.config_manager._reload_configuration()


class ConfigurationManager:
    """Manages tool configuration with hot-reloading support.

    This class handles loading configuration from YAML files, validating
    the configuration against Pydantic models, and providing hot-reload
    functionality for development environments.
    """

    def __init__(self, config_path: str = "config/tools.yaml"):
        """Initialize the configuration manager.

        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = Path(config_path)
        self._config: Optional[ToolsConfiguration] = None
        self._lock = threading.RLock()
        self._observer: Optional[Observer] = None
        self._reload_callbacks: List[Callable[[ToolsConfiguration], None]] = []
        self._hot_reload_enabled = False

    def initialize(self, enable_hot_reload: bool = False) -> ToolsConfiguration:
        """Initialize the configuration manager by loading configuration.

        Args:
            enable_hot_reload: Whether to enable hot-reload functionality

        Returns:
            Loaded configuration object
        """
        return self.load_configuration(enable_hot_reload)

    def load_configuration(self, enable_hot_reload: bool = False) -> ToolsConfiguration:
        """Load configuration from YAML file with validation.

        Args:
            enable_hot_reload: Whether to enable hot-reload functionality

        Returns:
            Validated configuration object

        Raises:
            ConfigurationError: If configuration is invalid or file not found
        """
        with self._lock:
            try:
                if not self.config_path.exists():
                    raise ConfigurationError(
                        f"Configuration file not found: {self.config_path}",
                        config_path=str(self.config_path),
                        user_guidance="Create the configuration file using the template in quickstart.md",
                    )

                # Load YAML content
                with open(self.config_path, "r") as f:
                    yaml_data = yaml.safe_load(f)

                if not yaml_data:
                    raise ConfigurationError(
                        f"Configuration file is empty: {self.config_path}",
                        config_path=str(self.config_path),
                        user_guidance="Add valid configuration content to the file",
                    )

                # Validate and create configuration object
                self._config = ToolsConfiguration(**yaml_data)

                logger.info(
                    f"Configuration loaded successfully from {self.config_path}"
                )

                # Setup hot-reload if requested and not already enabled
                if enable_hot_reload and not self._hot_reload_enabled:
                    self._setup_hot_reload()

                return self._config

            except yaml.YAMLError as e:
                raise ConfigurationError(
                    f"Invalid YAML in configuration file: {str(e)}",
                    config_path=str(self.config_path),
                    user_guidance="Check YAML syntax and fix formatting errors",
                    context={"yaml_error": str(e)},
                )
            except Exception as e:
                if isinstance(e, ConfigurationError):
                    raise

                raise ConfigurationError(
                    f"Failed to load configuration: {str(e)}",
                    config_path=str(self.config_path),
                    user_guidance="Check file permissions and configuration format",
                    context={"error": str(e)},
                )

    def get_configuration(self) -> Optional[ToolsConfiguration]:
        """Get the current configuration.

        Returns:
            Current configuration object or None if not loaded
        """
        with self._lock:
            return self._config

    def get_config(self) -> Optional[ToolsConfiguration]:
        """Alias for get_configuration for contract compatibility.

        Returns:
            Current configuration object or None if not loaded
        """
        return self.get_configuration()

    def validate_configuration(self, config_data: dict) -> ToolsConfiguration:
        """Validate configuration data without loading from file.

        Args:
            config_data: Dictionary containing configuration data

        Returns:
            Validated configuration object

        Raises:
            ConfigurationError: If validation fails
        """
        try:
            return ToolsConfiguration(**config_data)
        except Exception as e:
            raise ConfigurationError(
                f"Configuration validation failed: {str(e)}",
                user_guidance="Check configuration format against the schema",
                context={"validation_error": str(e)},
            )

    def add_reload_callback(
        self, callback: Callable[[ToolsConfiguration], None]
    ) -> None:
        """Add a callback to be called when configuration is reloaded.

        Args:
            callback: Function to call with new configuration
        """
        with self._lock:
            self._reload_callbacks.append(callback)

    def remove_reload_callback(
        self, callback: Callable[[ToolsConfiguration], None]
    ) -> None:
        """Remove a reload callback.

        Args:
            callback: Function to remove from callbacks
        """
        with self._lock:
            if callback in self._reload_callbacks:
                self._reload_callbacks.remove(callback)

    def register_reload_callback(
        self, callback: Callable[[ToolsConfiguration], None]
    ) -> None:
        """Alias for add_reload_callback for contract compatibility.

        Args:
            callback: Function to call with new configuration
        """
        return self.add_reload_callback(callback)

    def _setup_hot_reload(self) -> None:
        """Setup file watching for hot-reload functionality."""
        if self._observer is not None:
            return  # Already setup

        try:
            self._observer = Observer()
            event_handler = ConfigFileHandler(self)

            # Watch the directory containing the config file
            watch_dir = self.config_path.parent
            self._observer.schedule(event_handler, str(watch_dir), recursive=False)
            self._observer.start()
            self._hot_reload_enabled = True

            logger.info(f"Hot-reload enabled for configuration: {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to setup configuration hot-reload: {e}")
            # Don't fail startup if hot-reload setup fails

    def _reload_configuration(self) -> None:
        """Reload configuration from file and notify callbacks."""
        try:
            old_config = self._config
            new_config = self.load_configuration(enable_hot_reload=False)

            # Only notify if configuration actually changed
            if old_config is None or old_config.dict() != new_config.dict():
                logger.info("Configuration reloaded successfully")
                self._notify_callbacks(new_config)
            else:
                logger.debug("Configuration file changed but content is the same")

        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            # Keep using the old configuration on reload failure

    def _notify_callbacks(self, config: ToolsConfiguration) -> None:
        """Notify all registered callbacks of configuration change."""
        with self._lock:
            for callback in self._reload_callbacks:
                try:
                    callback(config)
                except Exception as e:
                    logger.error(f"Configuration reload callback failed: {e}")

    def stop_hot_reload(self) -> None:
        """Stop the hot-reload file watching."""
        with self._lock:
            if self._observer is not None:
                self._observer.stop()
                self._observer.join()
                self._observer = None
                self._hot_reload_enabled = False
                logger.info("Configuration hot-reload stopped")

    def cleanup(self) -> None:
        """Alias for stop_hot_reload for contract compatibility."""
        self.stop_hot_reload()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clean up resources."""
        self.stop_hot_reload()


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager(config_path: str = "config/tools.yaml") -> ConfigurationManager:
    """Get the global configuration manager instance.

    Args:
        config_path: Path to configuration file

    Returns:
        Global ConfigurationManager instance
    """
    global _config_manager
    if _config_manager is None or _config_manager.config_path != Path(config_path):
        _config_manager = ConfigurationManager(config_path)
    return _config_manager
