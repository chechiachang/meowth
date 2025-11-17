# Data Model: Azure OpenAI Chat Integration

**Date**: November 16, 2025  
**Feature**: Azure OpenAI Chat Integration  
**Source**: Extracted from spec.md functional requirements

## Core Entities

### Thread Context

Represents the runtime analysis of visible messages in a Slack thread for generating contextual AI responses using Azure OpenAI.

**Fields**:
- `thread_ts`: string - Slack thread timestamp identifier
- `channel_id`: string - Slack channel identifier  
- `messages`: list[ThreadMessage] - Visible messages in chronological order
- `token_count`: int - Total tokens in context
- `created_at`: datetime - Context analysis timestamp

**Validation Rules**:
- `thread_ts` must be valid Slack timestamp format
- `channel_id` must be valid Slack channel ID format
- `messages` must not exceed 50 items (from SC-002)
- `token_count` must not exceed 4000 tokens
- `created_at` must be recent (within last 30 seconds)

**State Transitions**:
- Created → Analyzed → Used → Discarded (no persistence)

### Thread Message

Represents a single message within a thread context for AI processing.

**Fields**:
- `user_id`: string - Slack user identifier
- `text`: string - Message content
- `timestamp`: string - Slack message timestamp
- `is_bot_message`: bool - Whether message is from the bot
- `token_count`: int - Estimated tokens for this message

**Validation Rules**:
- `user_id` must be valid Slack user ID format
- `text` must be non-empty and <= 4000 characters
- `timestamp` must be valid Slack timestamp
- `token_count` must be positive integer

### AI Response

Generated response from Azure OpenAI with metadata about generation parameters and timing.

**Fields**:
- `content`: string - Generated response text
- `model_used`: string - Azure OpenAI model deployment name
- `deployment_name`: string - Azure OpenAI deployment identifier
- `tokens_used`: int - Total tokens consumed
- `generation_time`: float - Response generation duration in seconds
- `context_tokens`: int - Tokens used for context
- `completion_tokens`: int - Tokens used for response
- `azure_endpoint`: string - Azure OpenAI endpoint used
- `created_at`: datetime - Response generation timestamp

**Validation Rules**:
- `content` must be non-empty and <= 4000 characters
- `model_used` must be valid Azure OpenAI model deployment name
- `deployment_name` must be valid Azure deployment identifier
- `tokens_used` must be positive integer
- `generation_time` must be positive float <= 30.0 seconds
- `context_tokens + completion_tokens` must equal `tokens_used`
- `azure_endpoint` must be valid Azure OpenAI endpoint URL

**State Transitions**:
- Requested → Generating → Completed → Sent

### Request Session

Single request-response cycle containing thread analysis and response generation.

**Fields**:
- `session_id`: string - Unique identifier for this request
- `user_id`: string - Requesting Slack user
- `thread_context`: ThreadContext - Analyzed thread context
- `ai_response`: AI Response | None - Generated response (if successful)
- `error_message`: string | None - Error description (if failed)
- `status`: SessionStatus - Current session state
- `started_at`: datetime - Session start time
- `completed_at`: datetime | None - Session completion time

**Validation Rules**:
- `session_id` must be unique UUID format
- `user_id` must be valid Slack user ID
- Either `ai_response` or `error_message` must be set when status is COMPLETED
- `completed_at` must be after `started_at` when set

**State Transitions**:
- CREATED → ANALYZING_CONTEXT → GENERATING_RESPONSE → COMPLETED
- Any state → ERROR (with error_message)

### Session Status (Enum)

**Values**:
- `CREATED` - Session initialized
- `ANALYZING_CONTEXT` - Processing thread messages
- `GENERATING_RESPONSE` - Calling Azure OpenAI API
- `COMPLETED` - Response successfully generated
- `ERROR` - Failed with error

## Relationships

```
Request Session (1) ──→ (1) Thread Context
Request Session (1) ──→ (0..1) AI Response  
Thread Context (1) ──→ (0..50) Thread Message
```

## Data Flow

1. **Context Analysis**: Slack thread messages → Thread Context with validation
2. **AI Processing**: Thread Context → AI Response via Azure OpenAI API
3. **Session Tracking**: Request Session coordinates the entire flow
4. **Cleanup**: All entities discarded after response sent (stateless)

## Token Management

**Context Token Calculation**:
- Each ThreadMessage has estimated token count using tiktoken
- Thread Context aggregates total tokens
- Context truncated when approaching model limits
- Priority given to most recent messages

**Response Token Limits**:
- Reserve 1000 tokens for response generation
- Remaining tokens available for context
- Hard limit prevents API quota exhaustion

## Error Handling

**Validation Errors**:
- Invalid Slack IDs → Reject request with error response
- Token limit exceeded → Truncate context with warning
- Empty context → Generate response with minimal context

**API Errors**:
- Rate limit exceeded → Queue request with exponential backoff
- API unavailable → Return fallback response
- Invalid response → Log error and return fallback

## Security & Privacy

**Data Handling**:
- No persistent storage of thread content
- Message content sanitized before AI processing
- User IDs never sent to OpenAI (replaced with generic identifiers)
- All entities cleaned up after request completion

**Access Control**:
- Only process messages visible to bot
- Respect Slack channel permissions
- No cross-thread data leakage