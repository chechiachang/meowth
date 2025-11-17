# Quickstart: Azure OpenAI Chat Integration

**Feature**: Azure OpenAI Chat Integration for Slack Bot  
**Audience**: Developers implementing the Azure AI integration feature  
**Prerequisites**: Existing Slack bot setup, Python 3.11+, Azure OpenAI account and deployment

## Overview

This feature extends the existing Meowth Slack bot with Azure OpenAI-powered chat responses. When users mention the bot in Slack threads, it analyzes thread context and generates intelligent AI responses using LlamaIndex and Azure's OpenAI service with comprehensive monitoring, error handling, and performance optimizations.

## Quick Setup (Development)

### 1. Install Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing dependencies ...
    "openai>=1.50.0,<2.0.0",
    "llama-index>=0.9.0,<1.0.0", 
    "llama-index-llms-azure-openai>=0.1.0",
    "tiktoken>=0.5.0",
]
```

Install:
```bash
uv add openai llama-index llama-index-llms-azure-openai tiktoken
```

### 2. Azure OpenAI Configuration

Basic configuration in your `.env` file:
```env
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your-azure-openai-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-35-turbo
AZURE_OPENAI_MODEL=gpt-35-turbo
AZURE_OPENAI_API_VERSION=2024-02-01
```

Advanced multi-model configuration:
```env
# Multiple model configurations (T043)
AZURE_OPENAI_MODELS_GPT35='{"deployment": "gpt-35-deployment", "max_tokens": 4096, "temperature": 0.7}'
AZURE_OPENAI_MODELS_GPT4='{"deployment": "gpt-4-deployment", "max_tokens": 8192, "temperature": 0.5}'

# Deployment strategy configuration 
AZURE_OPENAI_DEPLOYMENT_STRATEGY='{"strategy": "round_robin", "fallback": true, "retry_attempts": 3}'

# Quota and rate limiting (T040)
AZURE_OPENAI_DAILY_TOKEN_LIMIT=100000
AZURE_OPENAI_RATE_LIMIT_RPM=60
AZURE_OPENAI_RATE_LIMIT_TPM=10000
AZURE_OPENAI_QUOTA_WARNING=0.8
AZURE_OPENAI_QUOTA_CRITICAL=0.95
```

### 3. Verify Setup

Test Azure OpenAI connection:
```bash
python -c "
from meowth.ai.client import get_azure_openai_client
import asyncio
async def test():
    client = get_azure_openai_client()
    health = await client.health_check()
    print(f'Azure OpenAI health: {health}')
asyncio.run(test())
"
```

Test multi-model configuration:
```bash
python -c "
from meowth.utils.config import config
models = config.list_available_models()
print(f'Available models: {models}')
for model in models:
    print(f'{model}: {config.get_model_config(model)}')
"
```

## Architecture Overview

### Component Structure
```
src/meowth/ai/
├── client.py      # Azure OpenAI client with monitoring (T039, T040)
├── agent.py       # LlamaIndex agent with performance optimization (T042)
├── context.py     # Thread context analyzer with input sanitization (T041)
└── models.py      # Data models with thread isolation (T035-T038)

src/meowth/handlers/
├── mention.py     # Original mention handler (unchanged)
└── ai_mention.py  # AI-powered mention handler with session tracking
```

### Data Flow (with Thread Isolation)
1. **Slack Event**: User mentions bot → Session created for thread isolation
2. **Context Analysis**: Secure sanitization → Thread context with isolation tracking  
3. **AI Processing**: Context → Azure OpenAI with error monitoring → Response
4. **Response**: Post to Slack → Session cleanup for isolation
5. **Monitoring**: Track usage, errors, performance metrics

## Implementation Walkthrough

### Step 1: Azure OpenAI Client with Monitoring (T039, T040)

Our `src/meowth/ai/client.py` implementation:
```python
from meowth.ai.client import AzureOpenAIClient, AzureOpenAIConfig, get_azure_openai_monitor

# Create client with configuration
config = AzureOpenAIConfig(
    api_key="your-key",
    endpoint="https://your-resource.openai.azure.com/",
    deployment_name="gpt-35-turbo",
    model="gpt-35-turbo"
)

client = AzureOpenAIClient(config)

# Generate response with automatic monitoring
response = await client.generate_response(thread_context, session=session)

# Check monitoring metrics
monitor = get_azure_openai_monitor()
stats = monitor.get_error_summary(hours=24)
usage_stats = monitor.get_usage_metrics(hours=24) 
quota_status = monitor.check_quota_status(daily_token_limit=100000)

print(f"Errors: {stats['total_errors']}, Usage: {usage_stats['total_tokens']} tokens")
print(f"Quota: {quota_status['usage_percentage']:.1f}% used")
```

### Step 2: Context Analysis with Security (T041)

Our `src/meowth/ai/context.py` with input sanitization:
```python
from meowth.ai.context import ContextAnalyzer

analyzer = ContextAnalyzer()

# Analyze thread with automatic input sanitization
thread_context = await analyzer.analyze_thread_context(
    channel_id="C1234567890",
    thread_ts="1234567890.123456", 
    bot_user_id="U_BOT_ID",
    session=session  # For thread isolation
)

# Input sanitization automatically applied:
# - Removes control characters
# - Filters suspicious prompt injection patterns
# - Cleans Slack formatting
# - Limits message length for safety

print(f"Analyzed {len(thread_context.messages)} messages safely")
print(f"Token count: {thread_context.token_count}")
```

### Step 3: Performance-Optimized Agent (T042)

Our `src/meowth/ai/agent.py` with caching and concurrency control:
```python  
from meowth.ai.agent import get_llama_agent

agent = get_llama_agent()

# Generate response with automatic performance optimizations:
# - Response caching with TTL
# - Context caching  
# - Concurrency limiting (max 10 concurrent)
# - Request timeout (30s)
response = await agent.generate_response(thread_context, session=session)

# Check performance metrics
perf_stats = agent.get_performance_stats()
print(f"Cache hit rate: {perf_stats['cache_hit_rate_percent']:.1f}%")
print(f"Average response time: {perf_stats['avg_response_time']:.2f}s")
print(f"Concurrent requests: {perf_stats['concurrent_requests']}")
```

### Step 4: Thread-Isolated Mention Handler (T035-T038)

Our `src/meowth/handlers/ai_mention.py` with session tracking:
```python
from meowth.handlers.ai_mention import handle_ai_mention

# Each mention creates isolated session
await handle_ai_mention(
    event={
        'user': 'U1234567890',
        'text': '<@U_BOT_ID> What is the weather?',
        'channel': 'C1234567890', 
        'ts': '1234567890.123456',
        'thread_ts': '1234567890.123456'
    },
    context=slack_context
)

# Session automatically:
# 1. Creates unique session ID for this thread
# 2. Registers session for isolation tracking
# 3. Processes with thread-specific context
# 4. Cleans up session after completion
# 5. Monitors for concurrent sessions on same thread
```

### Step 5: Multi-Model Configuration (T043)

Using our enhanced configuration system:
```python
from meowth.utils.config import config

# List available models
models = config.list_available_models()
print(f"Available models: {models}")

# Get specific model config
gpt4_config = config.get_model_config("gpt-4")
print(f"GPT-4 deployment: {gpt4_config['deployment']}")
print(f"Max tokens: {gpt4_config['max_tokens']}")

# Get deployment strategy
strategy = config.azure_openai_deployment_strategies
print(f"Strategy: {strategy['strategy']}")
print(f"Fallback enabled: {strategy['fallback']}")

# Get quota configuration  
quota = config.azure_openai_quota_config
print(f"Daily limit: {quota['daily_token_limit']} tokens")
print(f"Rate limit: {quota['rate_limit_rpm']} RPM")
```

## Testing Strategy

### Unit Tests
```bash
# Test AI components in isolation
pytest tests/unit/ai/ -v

# Test specific components
pytest tests/unit/ai/test_client.py::test_openai_connection
pytest tests/unit/ai/test_context.py::test_thread_analysis
```

### Integration Tests
```bash
# Test end-to-end AI flow with mocked APIs
pytest tests/integration/test_ai_integration.py -v
```

### Manual Testing
1. Start bot in development mode
2. Mention bot in Slack thread: `@meowth what is the weather?`
3. Verify AI response appears in thread
4. Test context awareness with follow-up questions

## Error Handling & Fallbacks

### Common Issues & Solutions

**Azure OpenAI API Key Invalid**:
```bash
export AZURE_OPENAI_API_KEY=your-valid-azure-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
# Restart application
```

**Azure Rate Limit Exceeded**:
- Check Azure OpenAI quota in Azure portal
- Reduce `AZURE_OPENAI_MAX_REQUESTS_PER_MINUTE`
- Implement user-specific rate limiting
- Consider scaling up Azure deployment

**Azure Deployment Unavailable**:
- Verify deployment name in Azure portal
- Check Azure region availability
- Ensure model is properly deployed

**Context Too Long**:
- Automatic context truncation implemented
- Prioritizes recent messages
- Configurable via `AI_MAX_CONTEXT_TOKENS`

**LlamaIndex Azure Import Errors**:
```bash
uv add llama-index-core llama-index-llms-azure-openai
```

## Monitoring & Debugging

### Key Metrics to Track
- Azure OpenAI response generation time
- Azure OpenAI API success/error rates  
- Context analysis performance
- User engagement with AI responses
- Azure quota utilization

## Monitoring & Production Features

### Comprehensive Error Monitoring (T039)

Our implementation provides enterprise-grade error tracking:

```python
from meowth.ai.client import get_azure_openai_monitor

monitor = get_azure_openai_monitor()

# Get error summary
error_summary = monitor.get_error_summary(hours=24)
print(f"Last 24h: {error_summary['total_errors']} errors")
print(f"Error types: {error_summary['error_types']}")

# Check service health
is_healthy = monitor.is_healthy()
print(f"Service healthy: {is_healthy}")

# Error tracking automatically handles:
# - Rate limit errors (alerts at >5 in 10 min)
# - API errors (alerts at >3 in 10 min) 
# - Timeout errors (alerts at >2 in 10 min)
# - Quota exhaustion errors
# - Internal service errors
```

### Usage Metrics and Quota Management (T040)

Track usage and prevent quota overruns:

```python
# Get detailed usage metrics  
usage_metrics = monitor.get_usage_metrics(hours=24)
print(f"Total requests: {usage_metrics['total_requests']}")
print(f"Total tokens: {usage_metrics['total_tokens']}")
print(f"Avg tokens/request: {usage_metrics['average_tokens_per_request']:.1f}")
print(f"Avg response time: {usage_metrics['average_generation_time']:.2f}s")

# Check quota status with alerts
quota_status = monitor.check_quota_status(daily_token_limit=100000)
print(f"Quota used: {quota_status['usage_percentage']:.1f}%")
print(f"Status: {quota_status['status']}")
for alert in quota_status['alerts']:
    print(f"⚠️  {alert}")

# Automatic quota alerts at:
# - 60% usage: CAUTION
# - 80% usage: WARNING  
# - 95% usage: CRITICAL
```

### Input Security and Sanitization (T041)

Automatic protection against malicious input:

```python
# Input sanitization applied automatically in context analysis:

# ✅ Safe patterns preserved:
"Hello @meowth, what's the weather?" → "Hello @user, what's the weather?"

# 🛡️ Dangerous patterns filtered:
"Ignore previous instructions and..." → "[content filtered] and..."
"```rm -rf /```" → "[code block removed]"
"<script>alert('xss')</script>" → "&lt;script&gt;alert('xss')&lt;/script&gt;"

# 📏 Length limits enforced:
# - Max 10,000 characters per message
# - Excess content truncated with warning
```

### Performance Optimizations (T042)

Built-in performance enhancements:

```python
from meowth.ai.agent import get_llama_agent

agent = get_llama_agent()

# Performance features automatically applied:
# - Response caching (5 min TTL)
# - Context caching (5 min TTL)  
# - Concurrency limiting (max 10 concurrent)
# - Request timeouts (30s max)
# - Connection pooling

# Check performance metrics
perf_stats = agent.get_performance_stats()
print(f"Cache hit rate: {perf_stats['cache_hit_rate_percent']:.1f}%")
print(f"Cached responses: {perf_stats['cached_responses']}")
print(f"Cached contexts: {perf_stats['cached_contexts']}")
print(f"Average response time: {perf_stats['avg_response_time']:.2f}s")

# Clear caches if needed (for memory management)
agent.clear_performance_cache()
```

### Multi-Model Configuration (T043)

Support for multiple Azure OpenAI deployments:

```python
# Environment configuration for multiple models:
"""
AZURE_OPENAI_MODELS_GPT35='{"deployment": "gpt-35-turbo", "max_tokens": 4096}'
AZURE_OPENAI_MODELS_GPT4='{"deployment": "gpt-4-turbo", "max_tokens": 8192}'  
AZURE_OPENAI_MODELS_GPT4_VISION='{"deployment": "gpt-4-vision", "max_tokens": 4096}'
"""

from meowth.utils.config import config

# List all configured models
models = config.list_available_models()
for model in models:
    model_config = config.get_model_config(model)
    print(f"{model}: {model_config['deployment']} ({model_config['max_tokens']} tokens)")

# Deployment strategies  
strategy = config.azure_openai_deployment_strategies
# Supports: "single", "round_robin", "least_loaded"
# With automatic fallback and health checking
```

### Production Deployment

### Environment Variables
```env
AZURE_OPENAI_API_KEY=your-prod-azure-key
AZURE_OPENAI_ENDPOINT=https://your-prod-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-deployment  # Consider upgrading for production
AZURE_OPENAI_MODEL=gpt-4
AZURE_OPENAI_MAX_REQUESTS_PER_MINUTE=100  # Based on your Azure deployment
AI_RESPONSE_TIMEOUT=15  # Faster for production
```

### Monitoring Setup
- Configure Azure OpenAI usage alerts in Azure portal
- Monitor response quality metrics
- Set up error rate alerting
- Track Azure quota consumption

### Security Considerations
- Rotate Azure OpenAI API keys regularly
- Use Azure AD authentication for production
- Implement content filtering (Azure OpenAI includes built-in filters)
- Log AI interactions for audit
- Review Azure's responsible AI policies
- Configure appropriate Azure region for data compliance

## Next Steps

1. **Implement Phase 1**: Basic AI response generation
2. **Add Context Awareness**: Thread message analysis  
3. **Enhance Error Handling**: Comprehensive fallback system
4. **Performance Tuning**: Optimize for production load
5. **Advanced Features**: Custom prompts, response personalization

## Reference Documentation

- **Data Models**: See `data-model.md` for entity definitions
- **API Contracts**: See `contracts/` for interface specifications  
- **Research**: See `research.md` for technical decisions
- **Tasks**: See `tasks.md` for implementation checklist (generated by `/speckit.tasks`)

## Support

For implementation questions:
- Review existing codebase in `src/meowth/`
- Check constitution.md for coding standards
- Follow TDD requirements for all new code
- Ensure proper error handling per constitutional requirements