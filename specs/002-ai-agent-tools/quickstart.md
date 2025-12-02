# Quickstart: AI Agent Tools

**Feature**: AI Agent Tools for Slack Bot  
**Date**: 2025-12-01  
**Prerequisites**: Python 3.11+, existing Meowth Slack bot setup

## Overview

This guide helps you quickly set up and test the AI Agent Tools functionality. The system allows the Slack bot to automatically select and execute appropriate tools when users mention the bot with requests like "summarize the last 10 messages" or "analyze recent conversations."

## Quick Setup (5 minutes)

### 1. Install Dependencies

```bash
# Add new dependencies to existing project
uv add llama-index-core
uv add llama-index-llms-azure-openai  # or llama-index-llms-openai
uv add llama-index-agent-openai
uv add pydantic[yaml]
uv add watchdog  # for config hot-reloading
```

### 2. Create Tool Configuration

Create `config/tools.yaml`:

```yaml
version: "1.0"
environment: "development"

global:
  timeout_seconds: 30
  max_retries: 3
  rate_limit_rpm: 60

tools:
  slack_tools:
    enabled: true
    permissions:
      - "channels:read" 
      - "channels:history"
    tools:
      fetch_messages:
        enabled: true
        description: "Fetch recent messages from Slack channels"
        max_messages: 10  # Start with small limit for testing
        timeout_seconds: 15
        
  openai_tools:
    enabled: true
    model_config:
      default_model: "gpt-4"
      max_tokens: 1500
      temperature: 0.7
      timeout_seconds: 20
    tools:
      summarize_messages:
        enabled: true
        description: "Generate message summaries"
        max_summary_length: 200
```

### 3. Set Environment Variables

Add to your `.env` file:

```bash
# Existing Slack/OpenAI vars remain the same
# Add tool-specific configuration
TOOLS_ENVIRONMENT=development
TOOLS_GLOBAL__TIMEOUT_SECONDS=30
```

### 4. Create Basic Tool Implementation

Create `src/meowth/ai/tools/__init__.py`:

```python
"""AI Agent Tools module."""
from .registry import ToolRegistry
from .slack_tools import create_slack_tools
from .openai_tools import create_openai_tools

__all__ = ["ToolRegistry", "create_slack_tools", "create_openai_tools"]
```

Create `src/meowth/ai/tools/registry.py`:

```python
"""Tool registry for managing AI agent tools."""
import yaml
from pathlib import Path
from typing import Dict, List, Any
from llama_index.core.tools import FunctionTool

class ToolRegistry:
    def __init__(self, config_path: str = "config/tools.yaml"):
        self.config_path = Path(config_path)
        self.tools: Dict[str, FunctionTool] = {}
        
    def load_configuration(self) -> Dict[str, Any]:
        """Load tool configuration from YAML file."""
        with open(self.config_path) as f:
            return yaml.safe_load(f)
    
    def initialize_tools(self, slack_client, openai_client):
        """Initialize all configured tools."""
        config = self.load_configuration()
        
        # Create Slack tools
        if config["tools"]["slack_tools"]["enabled"]:
            from .slack_tools import create_slack_tools
            slack_tools = create_slack_tools(slack_client, config["tools"]["slack_tools"])
            for tool in slack_tools:
                self.tools[tool.metadata.name] = tool
                
        # Create OpenAI tools  
        if config["tools"]["openai_tools"]["enabled"]:
            from .openai_tools import create_openai_tools
            openai_tools = create_openai_tools(openai_client, config["tools"]["openai_tools"])
            for tool in openai_tools:
                self.tools[tool.metadata.name] = tool
                
        return list(self.tools.values())
```

### 5. Minimal Tool Implementation

Create `src/meowth/ai/tools/slack_tools.py`:

```python
"""Slack-specific tools for AI agent."""
import json
from typing import Annotated, List
from llama_index.core.tools import FunctionTool
from slack_sdk import WebClient

def create_slack_tools(slack_client: WebClient, config: dict) -> List[FunctionTool]:
    """Create Slack tools with dependency injection."""
    tools = []
    
    if config["tools"]["fetch_messages"]["enabled"]:
        async def fetch_messages(
            channel_id: Annotated[str, "Slack channel ID to fetch messages from"],
            limit: Annotated[int, "Number of messages (1-10)"] = 5
        ) -> str:
            """Fetch recent messages from a Slack channel."""
            try:
                # Limit for development
                actual_limit = min(limit, config["tools"]["fetch_messages"]["max_messages"])
                
                response = slack_client.conversations_history(
                    channel=channel_id,
                    limit=actual_limit
                )
                
                messages = []
                for msg in response["messages"]:
                    messages.append({
                        "text": msg.get("text", ""),
                        "user": msg.get("user", ""),
                        "timestamp": msg.get("ts", "")
                    })
                
                return json.dumps({
                    "messages": messages,
                    "channel": channel_id,
                    "total_fetched": len(messages)
                })
                
            except Exception as e:
                return f"Error fetching messages: {str(e)}"
        
        tools.append(FunctionTool.from_defaults(async_fn=fetch_messages))
    
    return tools
```

Create `src/meowth/ai/tools/openai_tools.py`:

```python
"""OpenAI-specific tools for AI agent."""
import json
from typing import Annotated, List
from llama_index.core.tools import FunctionTool

def create_openai_tools(openai_client, config: dict) -> List[FunctionTool]:
    """Create OpenAI tools."""
    tools = []
    
    if config["tools"]["summarize_messages"]["enabled"]:
        async def summarize_messages(
            messages_json: Annotated[str, "JSON string of messages to summarize"],
            style: Annotated[str, "Style: 'brief' or 'detailed'"] = "brief"
        ) -> str:
            """Summarize Slack messages."""
            try:
                messages_data = json.loads(messages_json)
                messages = messages_data["messages"]
                
                # Simple summarization for quickstart
                if style == "brief":
                    return f"Found {len(messages)} messages in the conversation."
                else:
                    user_count = len(set(msg["user"] for msg in messages))
                    return f"Conversation summary: {len(messages)} messages from {user_count} users."
                    
            except Exception as e:
                return f"Error summarizing messages: {str(e)}"
        
        tools.append(FunctionTool.from_defaults(async_fn=summarize_messages))
    
    return tools
```

### 6. Integrate with Existing Bot

Update your main bot handler (e.g., `src/meowth/handlers/mention.py`):

```python
from meowth.ai.tools import ToolRegistry
from llama_index.agent.openai import OpenAIAgent

class MentionHandler:
    def __init__(self, slack_client, openai_client):
        self.slack_client = slack_client
        self.openai_client = openai_client
        
        # Initialize tool registry
        self.tool_registry = ToolRegistry()
        tools = self.tool_registry.initialize_tools(slack_client, openai_client)
        
        # Create LlamaIndex agent with tools
        self.agent = OpenAIAgent.from_tools(
            tools=tools,
            llm=openai_client,
            system_prompt="You are a helpful Slack bot assistant. Use available tools to help users with their requests."
        )
    
    async def handle_mention(self, event, say):
        """Handle bot mentions with tool integration."""
        user_message = event["text"]
        
        # Use agent to process request with tools
        try:
            response = await self.agent.achat(user_message)
            await say(str(response))
        except Exception as e:
            await say(f"Sorry, I encountered an error: {str(e)}")
```

## Testing (2 minutes)

### 1. Start the Bot

```bash
cd /path/to/meowth
uv run python -m meowth.main
```

### 2. Test Basic Functionality

In a Slack channel where the bot is present:

```
@meowth fetch the last 5 messages from this channel
```

Expected response: The bot should use the `fetch_messages` tool and return message data.

```
@meowth summarize the recent conversation
```

Expected response: The bot should fetch messages and then summarize them.

### 3. Verify Tool Selection

Check your bot logs to see:
- Tool registry initialization
- Tool selection decisions
- Tool execution results

## Common Issues & Solutions

### Issue: "Tool not found"
**Solution**: Check `config/tools.yaml` and ensure tool is enabled:
```yaml
tools:
  slack_tools:
    enabled: true
    tools:
      fetch_messages:
        enabled: true  # Make sure this is true
```

### Issue: "Permission denied" 
**Solution**: Verify bot has required Slack permissions:
- `channels:read`
- `channels:history`

### Issue: "Configuration not found"
**Solution**: Create `config/tools.yaml` in the correct location relative to your working directory.

## Next Steps

Once basic functionality works:

1. **Add Error Handling**: Implement proper `ToolError` exceptions
2. **Add Rate Limiting**: Implement `SlackRateLimiter` for production use  
3. **Add More Tools**: Extend with conversation analysis tools
4. **Add Configuration Validation**: Use Pydantic models for config validation
5. **Add Monitoring**: Implement tool execution logging and metrics

## Configuration Examples

### Development Configuration
```yaml
# Optimized for testing and debugging
environment: "development"
global:
  timeout_seconds: 60  # Longer timeouts for debugging
  max_retries: 1       # Fewer retries for faster iteration
tools:
  slack_tools:
    tools:
      fetch_messages:
        max_messages: 5  # Small limits for testing
```

### Production Configuration  
```yaml
# Optimized for reliability and performance
environment: "production" 
global:
  timeout_seconds: 30
  max_retries: 3
  rate_limit_rpm: 60
tools:
  slack_tools:
    tools:
      fetch_messages:
        max_messages: 100  # Full limits for production
```

This quickstart gets you up and running with basic AI agent tools. The modular design allows you to gradually add more sophisticated tools and error handling as needed.