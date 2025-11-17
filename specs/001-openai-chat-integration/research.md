# Research: Azure OpenAI Chat Integration

**Date**: November 16, 2025  
**Feature**: Azure OpenAI Chat Integration  
**Purpose**: Resolve technical unknowns and establish implementation approach for Azure OpenAI

## Azure OpenAI Python SDK Integration

**Decision**: Use OpenAI Python SDK v1.50+ with Azure OpenAI configuration

**Rationale**: 
- Official OpenAI SDK fully supports Azure OpenAI endpoints
- Same async patterns and error handling as standard OpenAI
- Comprehensive authentication with Azure AD and API key support
- Built-in rate limiting and retry mechanisms for Azure endpoints
- Strong type hints and error handling
- Enterprise-grade security and compliance through Azure

**Alternatives considered**:
- Azure-specific SDK: Rejected as OpenAI SDK provides full Azure support
- Direct HTTP API calls: Rejected due to complexity of implementing rate limiting and auth
- LangChain Azure integration: Rejected to minimize dependencies, LlamaIndex provides sufficient abstraction

**Implementation approach**:
```python
from openai import AsyncOpenAI

# Azure OpenAI configuration
client = AsyncOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
```

## LlamaIndex Azure OpenAI Integration

**Decision**: Use LlamaIndex 0.9+ with Azure OpenAI LLM integration

**Rationale**:
- LlamaIndex has built-in Azure OpenAI support via AzureOpenAI class
- Provides agent framework for contextual conversations
- Native Azure endpoint and authentication handling
- Document indexing capabilities for thread context
- Async support for non-blocking operations
- Modular architecture aligns with existing codebase

**Alternatives considered**:
- Direct Azure OpenAI chat completions: Rejected due to lack of context management
- LangChain Azure agents: Rejected to minimize dependencies and complexity

**Implementation approach**:
```python
from llama_index.llms.azure_openai import AzureOpenAI

llm = AzureOpenAI(
    model="gpt-35-turbo",  # Azure model deployment name
    deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-02-01"
)
```

## Thread Context Processing Strategy

**Decision**: Dynamic context window with message prioritization (unchanged from standard approach)

**Rationale**:
- Most recent messages have highest priority for context
- System messages and bot responses included for conversation flow
- Token counting to stay within Azure model limits (4k tokens for context)
- Graceful degradation when thread exceeds token limits
- Azure OpenAI uses same tokenization as standard OpenAI

**Implementation approach**:
1. Fetch thread messages in reverse chronological order
2. Count tokens while building context using tiktoken
3. Stop when approaching Azure model token limit
4. Include system prompt describing bot role and current context

## Azure-Specific Rate Limiting Strategy

**Decision**: Implement tiered rate limiting with Azure OpenAI quotas

**Rationale**:
- Azure OpenAI: Deployment-specific TPM (Tokens Per Minute) limits
- Different rate limits per model deployment (e.g., 120k TPM for GPT-3.5-turbo)
- Request-based limits in addition to token limits
- Slack: 50+ requests per minute for most methods
- Queue requests to prevent quota exhaustion
- Exponential backoff for rate limit errors

**Alternatives considered**:
- Simple rate limiting: Rejected due to poor user experience during bursts
- No rate limiting: Rejected due to Azure quota exhaustion risk

**Implementation approach**:
```python
import asyncio
from asyncio import Semaphore

# Azure OpenAI rate limiting
azure_openai_semaphore = Semaphore(5)  # Max 5 concurrent requests

async def rate_limited_azure_openai_call():
    async with azure_openai_semaphore:
        # Azure OpenAI API call with exponential backoff
        pass
```

## Error Recovery and Fallback Strategy

**Decision**: Graceful degradation with Azure-specific error handling

**Rationale**:
- Maintain bot availability even when Azure AI services fail
- Handle Azure-specific errors (quota exceeded, deployment unavailable)
- Provide clear user feedback about service status
- Fallback to simple responses when appropriate

**Azure-specific error handling**:
1. Azure quota exceeded → Queue with longer backoff
2. Deployment unavailable → Retry with different deployment if available
3. Azure AD authentication errors → Refresh token and retry
4. Regional outage → Fallback to simple responses

**Fallback hierarchy**:
1. Primary: Full AI response with thread context via Azure OpenAI
2. Fallback 1: Simple AI response without context via Azure OpenAI
3. Fallback 2: Predefined helpful message about service unavailability
4. Fallback 3: Original mention handler behavior

## Dependency Versions for Azure OpenAI

**Decision**: Pin to Azure-compatible versions

**Final dependency selections**:
- `openai>=1.50.0,<2.0.0` - Latest stable v1 with Azure support
- `llama-index>=0.9.0,<1.0.0` - Stable LlamaIndex core
- `llama-index-llms-azure-openai>=0.1.0` - Azure OpenAI LLM integration
- `tiktoken>=0.5.0` - Token counting for context management

**Rationale**: Version pinning ensures reproducible builds while maintaining Azure OpenAI compatibility.

## Azure-Specific Security Considerations

**Azure OpenAI Credentials**:
- Store Azure OpenAI API key, endpoint, and deployment name in environment variables
- Validate all Azure configuration at startup
- Support Azure AD authentication for production environments
- Implement credential rotation capability
- No Azure credentials in logs or error messages

**Azure Regional Compliance**:
- Configure Azure region for data residency requirements
- Implement data processing location awareness
- Support multiple Azure regions for redundancy
- Compliance with Azure's data protection standards

**Input/Output Security**:
- Validate Slack message content before processing
- Implement content filtering for inappropriate requests
- Azure OpenAI includes built-in content filtering
- Respect Azure's responsible AI policies
- Rate limit per user to prevent abuse

**Monitoring and Compliance**:
- Log Azure OpenAI interactions for monitoring and compliance
- Implement circuit breaker for repeated Azure failures
- Monitor Azure quota usage and billing
- Set up alerts for Azure service health issues

## Azure Configuration Requirements

**Environment Variables Required**:
- `AZURE_OPENAI_API_KEY` - Azure OpenAI service API key
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI service endpoint URL
- `AZURE_OPENAI_DEPLOYMENT_NAME` - Model deployment name in Azure
- `AZURE_OPENAI_API_VERSION` - API version (default: "2024-02-01")
- `AZURE_OPENAI_MODEL` - Model name (e.g., "gpt-35-turbo")

**Optional Azure Features**:
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` - For Azure AD authentication
- `AZURE_OPENAI_REGION` - Specific Azure region for compliance
- `AZURE_OPENAI_RESOURCE_GROUP` - Azure resource group for monitoring