"""Environment configuration management for Slack bot with Azure OpenAI integration."""

import os
from typing import Any
from dotenv import load_dotenv


class Config:
    """Configuration management for Slack bot and Azure OpenAI environment variables."""

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

    # Azure OpenAI Configuration

    @property
    def azure_openai_api_key(self) -> str:
        """Get Azure OpenAI API key."""
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
        return api_key

    @property
    def azure_openai_endpoint(self) -> str:
        """Get Azure OpenAI endpoint URL."""
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
        if not endpoint.startswith("https://"):
            raise ValueError("AZURE_OPENAI_ENDPOINT must start with 'https://'")
        return endpoint

    @property
    def azure_openai_deployment_name(self) -> str:
        """Get Azure OpenAI model deployment name."""
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not deployment:
            raise ValueError(
                "AZURE_OPENAI_DEPLOYMENT_NAME environment variable is required"
            )
        return deployment

    @property
    def azure_openai_api_version(self) -> str:
        """Get Azure OpenAI API version, defaults to 2024-02-01."""
        return os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

    @property
    def azure_openai_model(self) -> str:
        """Get Azure OpenAI model name, defaults to gpt-35-turbo."""
        return os.getenv("AZURE_OPENAI_MODEL", "gpt-35-turbo")

    # Multi-model configuration support for T043
    @property
    def azure_openai_models_config(self) -> dict[str, dict[str, Any]]:
        """Get configuration for multiple Azure OpenAI models and deployments.

        Supports environment variables like:
        AZURE_OPENAI_MODELS_GPT35='{"deployment": "gpt-35-deployment", "max_tokens": 4096}'
        AZURE_OPENAI_MODELS_GPT4='{"deployment": "gpt-4-deployment", "max_tokens": 8192}'

        Returns:
            Dictionary mapping model names to their configurations
        """
        models_config = {}

        # Default model configuration
        default_model = self.azure_openai_model
        models_config[default_model] = {
            "deployment": self.azure_openai_deployment_name,
            "max_tokens": 4096,
            "temperature": 0.7,
            "description": f"Default {default_model} model",
        }

        # Load additional model configurations from environment
        for key, value in os.environ.items():
            if key.startswith("AZURE_OPENAI_MODELS_"):
                model_name = (
                    key.replace("AZURE_OPENAI_MODELS_", "").lower().replace("_", "-")
                )
                try:
                    import json

                    model_config = json.loads(value)

                    # Validate required fields
                    if "deployment" not in model_config:
                        raise ValueError(
                            f"Model config {model_name} missing required 'deployment' field"
                        )

                    # Set defaults for optional fields
                    model_config.setdefault("max_tokens", 4096)
                    model_config.setdefault("temperature", 0.7)
                    model_config.setdefault(
                        "description", f"Azure OpenAI {model_name} model"
                    )

                    models_config[model_name] = model_config
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in {key}: {e}")

        return models_config

    @property
    def azure_openai_deployment_strategies(self) -> dict:
        """Get deployment strategies for load balancing and failover.

        Environment variable format:
        AZURE_OPENAI_DEPLOYMENT_STRATEGY='{"strategy": "round_robin", "fallback": true}'

        Returns:
            Dictionary with deployment strategy configuration
        """
        strategy_config = {
            "strategy": "single",  # single, round_robin, least_loaded
            "fallback": True,  # Enable fallback to other deployments on error
            "health_check": True,  # Enable deployment health checking
            "retry_attempts": 3,  # Number of retry attempts per deployment
        }

        strategy_env = os.getenv("AZURE_OPENAI_DEPLOYMENT_STRATEGY")
        if strategy_env:
            try:
                import json

                user_config = json.loads(strategy_env)
                strategy_config.update(user_config)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in AZURE_OPENAI_DEPLOYMENT_STRATEGY: {e}"
                )

        return strategy_config

    @property
    def azure_openai_quota_config(self) -> dict:
        """Get quota management configuration.

        Environment variables:
        AZURE_OPENAI_DAILY_TOKEN_LIMIT=100000
        AZURE_OPENAI_RATE_LIMIT_RPM=60
        AZURE_OPENAI_RATE_LIMIT_TPM=10000

        Returns:
            Dictionary with quota limits
        """
        return {
            "daily_token_limit": int(
                os.getenv("AZURE_OPENAI_DAILY_TOKEN_LIMIT", "100000")
            ),
            "rate_limit_rpm": int(os.getenv("AZURE_OPENAI_RATE_LIMIT_RPM", "60")),
            "rate_limit_tpm": int(os.getenv("AZURE_OPENAI_RATE_LIMIT_TPM", "10000")),
            "quota_warning_threshold": float(
                os.getenv("AZURE_OPENAI_QUOTA_WARNING", "0.8")
            ),  # 80%
            "quota_critical_threshold": float(
                os.getenv("AZURE_OPENAI_QUOTA_CRITICAL", "0.95")
            ),  # 95%
        }

    def get_model_config(self, model_name: str) -> dict:
        """Get configuration for a specific model.

        Args:
            model_name: Name of the model to get config for

        Returns:
            Model configuration dictionary

        Raises:
            ValueError: If model is not configured
        """
        models_config = self.azure_openai_models_config
        if model_name not in models_config:
            available_models = list(models_config.keys())
            raise ValueError(
                f"Model '{model_name}' not configured. Available models: {available_models}"
            )

        return models_config[model_name]

    def list_available_models(self) -> list[str]:
        """Get list of available Azure OpenAI models.

        Returns:
            List of configured model names
        """
        return list(self.azure_openai_models_config.keys())

    def validate_azure_openai(self) -> None:
        """Validate Azure OpenAI configuration values."""
        # This will raise ValueError if any required config is missing or invalid
        self.azure_openai_api_key
        self.azure_openai_endpoint
        self.azure_openai_deployment_name

        # Validate API version format
        api_version = self.azure_openai_api_version
        if not api_version.count("-") >= 2:  # Format: YYYY-MM-DD
            raise ValueError("AZURE_OPENAI_API_VERSION must be in YYYY-MM-DD format")

        # Validate multi-model configurations
        try:
            models_config = self.azure_openai_models_config
            if not models_config:
                raise ValueError("No Azure OpenAI models configured")
        except Exception as e:
            raise ValueError(f"Invalid Azure OpenAI models configuration: {e}")

        # Validate deployment strategy
        try:
            strategy_config = self.azure_openai_deployment_strategies
            valid_strategies = ["single", "round_robin", "least_loaded"]
            if strategy_config.get("strategy") not in valid_strategies:
                raise ValueError(
                    f"Invalid deployment strategy. Must be one of: {valid_strategies}"
                )
        except Exception as e:
            raise ValueError(f"Invalid deployment strategy configuration: {e}")

        # Validate quota configuration
        try:
            quota_config = self.azure_openai_quota_config
            if quota_config["daily_token_limit"] <= 0:
                raise ValueError("Daily token limit must be positive")
            if not (0.0 <= quota_config["quota_warning_threshold"] <= 1.0):
                raise ValueError("Quota warning threshold must be between 0.0 and 1.0")
            if not (0.0 <= quota_config["quota_critical_threshold"] <= 1.0):
                raise ValueError("Quota critical threshold must be between 0.0 and 1.0")
        except Exception as e:
            raise ValueError(f"Invalid quota configuration: {e}")

    def validate(self) -> None:
        """Validate all required configuration values."""
        # Validate Slack configuration
        self.slack_bot_token
        self.slack_app_token

        # Validate log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(valid_levels)}")

        # Validate Azure OpenAI configuration
        self.validate_azure_openai()

    # Langfuse Configuration

    @property
    def langfuse_public_key(self) -> str:
        """Get Langfuse public key for observability."""
        return os.getenv("LANGFUSE_PUBLIC_KEY", "")

    @property
    def langfuse_secret_key(self) -> str:
        """Get Langfuse secret key for observability."""
        return os.getenv("LANGFUSE_SECRET_KEY", "")

    @property
    def langfuse_host(self) -> str:
        """Get Langfuse host URL, defaults to cloud instance."""
        return os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    @property
    def langfuse_enabled(self) -> bool:
        """Check if Langfuse monitoring is enabled."""
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


# Global configuration instance
config = Config()
