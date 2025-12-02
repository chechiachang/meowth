# AI Agent Tools API Contracts

**Feature**: AI Agent Tools  
**Date**: 2025-12-01

## Tool Interface Contracts

These contracts define the interfaces for LlamaIndex tools and their interactions with the AI agent system.

### 1. Tool Function Signature Contract

All tools must implement the standard LlamaIndex function interface:

```python
from typing import Annotated, Optional, Any
from llama_index.core.tools import FunctionTool

async def tool_function_name(
    parameter1: Annotated[type, "Description for LLM understanding"],
    parameter2: Annotated[type, "Description"] = default_value,
    # ... additional parameters
) -> str:
    """
    Clear description of what the tool does for LLM tool selection.
    
    Args:
        parameter1: Detailed parameter description
        parameter2: Detailed parameter description with default
        
    Returns:
        String description of the result format
        
    Raises:
        ToolError: When execution fails with category and guidance
    """
```

**Contract Requirements**:
- Must use `Annotated` types for all parameters to provide LLM context
- Must include comprehensive docstring for tool selection
- Must return string representation of results
- Must raise `ToolError` exceptions with proper categorization
- Must be async for concurrent execution support

### 2. Slack Message Fetching Contract

**Tool Name**: `fetch_slack_messages`  
**Category**: `slack_tools`

```python
async def fetch_slack_messages(
    channel_id: Annotated[str, "Slack channel ID (e.g., 'C1234567890')"],
    limit: Annotated[int, "Maximum number of messages to fetch (1-100)"] = 10,
    include_threads: Annotated[bool, "Whether to include thread replies"] = True,
    since_hours: Annotated[Optional[int], "Fetch messages from last N hours"] = None
) -> str:
    """
    Fetch recent messages from a Slack channel for analysis and summarization.
    
    Returns JSON string containing messages with metadata:
    {
        "messages": [
            {
                "text": "message content",
                "user": "user_id", 
                "timestamp": "1234567890.123456",
                "thread_ts": "optional thread timestamp",
                "reactions": ["emoji list"]
            }
        ],
        "channel": "channel_name",
        "total_fetched": 10
    }
    """
```

**Response Contract**:
- JSON string format for structured data consumption
- Maximum 100 messages per request (enforced by configuration)
- Includes message metadata for context analysis
- Handles permissions and rate limiting internally

### 3. Message Summarization Contract

**Tool Name**: `summarize_messages`  
**Category**: `openai_tools`

```python
async def summarize_messages(
    messages_json: Annotated[str, "JSON string of messages from fetch_slack_messages"],
    summary_style: Annotated[str, "Summary style: 'brief', 'detailed', 'bullet_points'"] = "brief",
    focus_areas: Annotated[Optional[str], "Specific topics to focus on"] = None,
    max_length: Annotated[int, "Maximum summary length in words"] = 200
) -> str:
    """
    Generate a summary of Slack messages using OpenAI API.
    
    Returns formatted summary string based on specified style:
    - brief: 1-2 sentence overview
    - detailed: Comprehensive paragraph summary  
    - bullet_points: Key points as bulleted list
    """
```

**Response Contract**:
- Plain text summary formatted according to style parameter
- Respects maximum length constraints
- Includes key topics, decisions, and action items
- Provides context about conversation participants and timeframe

### 4. Conversation Analysis Contract

**Tool Name**: `analyze_conversation`  
**Category**: `analysis_tools`

```python
async def analyze_conversation(
    messages_json: Annotated[str, "JSON string of messages to analyze"],
    analysis_type: Annotated[str, "Type: 'sentiment', 'topics', 'decisions', 'action_items'"] = "topics",
    confidence_threshold: Annotated[float, "Minimum confidence for results (0.0-1.0)"] = 0.7
) -> str:
    """
    Analyze conversation content to extract insights, sentiment, or action items.
    
    Returns JSON string with analysis results:
    {
        "analysis_type": "topics",
        "results": [...],
        "confidence": 0.85,
        "metadata": {...}
    }
    """
```

### 5. Error Handling Contract

All tools must implement standardized error handling:

```python
from enum import Enum
from typing import Dict, Any, Optional

class ErrorCategory(str, Enum):
    NETWORK = "network"
    AUTHENTICATION = "authentication" 
    PERMISSION = "permission"
    RATE_LIMIT = "rate_limit"
    INVALID_INPUT = "invalid_input"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    SYSTEM_ERROR = "system_error"

class ErrorSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class ToolError(Exception):
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
        user_guidance: Optional[str] = None
    ):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.recoverable = recoverable
        self.user_guidance = user_guidance
```

**Error Response Contract**:
- All tools must raise `ToolError` with proper categorization
- Must include user-friendly guidance for error recovery
- Must specify if error is recoverable for retry logic
- Must provide relevant context for debugging

## Tool Registry Interface Contract

### Configuration Loading Contract

```python
class ToolsConfiguration:
    def load_tools(self) -> Dict[str, FunctionTool]:
        """Load tools from YAML configuration."""
        
    def validate_configuration(self) -> bool:
        """Validate tool configuration against schemas."""
        
    def reload_configuration(self) -> None:
        """Hot-reload configuration without restart."""
```

### Tool Factory Contract

```python
class ToolFactory:
    def create_tool(
        self, 
        tool_name: str, 
        config: Dict[str, Any],
        dependencies: Dict[str, Any]
    ) -> FunctionTool:
        """Create tool instance with configuration and dependencies."""
```

## Agent Integration Contract

### LlamaIndex Agent Interface

```python
class AgentToolInterface:
    async def process_user_request(
        self,
        user_message: str,
        context: ToolExecutionContext
    ) -> str:
        """Process user request and return response using appropriate tools."""
        
    def get_available_tools(self) -> List[FunctionTool]:
        """Get list of currently available tools."""
        
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Execute specific tool with parameters."""
```

## Rate Limiting Contract

### Slack API Rate Limiting

```python
class SlackRateLimiter:
    async def acquire(self, endpoint: str) -> bool:
        """Acquire rate limit token for Slack API call."""
        
    def get_wait_time(self, endpoint: str) -> float:
        """Get time to wait before next allowed request."""
```

**Rate Limiting Rules**:
- Slack API Tier 2: 20+ requests per minute
- Slack API Tier 3: 50+ requests per minute  
- Burst tolerance: 2x normal rate for short periods
- Circuit breaker: Activate after 429 responses

### OpenAI API Rate Limiting

```python
class OpenAIRateLimiter:
    async def acquire(self, model: str, estimated_tokens: int) -> bool:
        """Acquire rate limit for OpenAI API call based on model and token usage."""
```

## Data Validation Contracts

### Input Validation

All tool parameters must validate against schemas:

```yaml
# Tool parameter schema example
fetch_slack_messages:
  channel_id:
    type: string
    pattern: "^C[A-Z0-9]{8,}$"
    description: "Valid Slack channel ID"
  limit:
    type: integer
    minimum: 1
    maximum: 100
    description: "Message count limit"
```

### Output Validation

Tool outputs must conform to expected formats:

```python
def validate_tool_output(tool_name: str, output: str) -> bool:
    """Validate tool output against expected schema."""
```

## Security Contracts

### Permission Inheritance

```python
class ToolSecurityContext:
    def inherit_bot_permissions(self, slack_client: WebClient) -> None:
        """Inherit authentication context from bot."""
        
    def validate_channel_access(self, channel_id: str) -> bool:
        """Verify bot has access to specified channel."""
```

### Credential Management

- API keys must come from environment variables
- No sensitive data in tool configurations
- Audit logging for tool executions accessing external APIs

These contracts ensure consistent interfaces, proper error handling, and secure tool execution within the AI agent system.