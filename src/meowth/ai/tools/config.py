"""Simplified configuration for AI tools."""

from typing import Dict, Any, Optional
from pydantic import BaseModel


class SlackToolsConfig(BaseModel):
    enabled: bool = True
    bot_token: Optional[str] = None
    fetch_messages: Dict[str, Any] = {}


class OpenAIToolsConfig(BaseModel):
    enabled: bool = True
    api_key: Optional[str] = None
    model_config_data: Dict[str, Any] = {
        "default_model": "gpt-4",
        "max_tokens": 1500,
        "temperature": 0.7,
    }
    tools: Dict[str, Any] = {}


class ToolsConfiguration(BaseModel):
    slack_tools: SlackToolsConfig = SlackToolsConfig()
    openai_tools: OpenAIToolsConfig = OpenAIToolsConfig()
