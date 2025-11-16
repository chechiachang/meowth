# Data Model: Slack Mention Bot

**Date**: November 16, 2025  
**Purpose**: Define data structures and entities for Slack mention bot

## Core Entities

### 1. Bot Instance

**Purpose**: Represents the running bot application with its configuration and state

**Fields**:
- `bot_token: str` - Slack Bot User OAuth Token for API calls
- `app_token: str` - Slack App-Level Token for Socket Mode
- `client: SlackClient` - Slack Bolt client instance
- `is_connected: bool` - Current connection status
- `last_heartbeat: datetime` - Last successful API communication

**State Transitions**:
- STARTING → CONNECTED (successful authentication)
- CONNECTED → DISCONNECTED (network/API failure)
- DISCONNECTED → CONNECTED (successful reconnection)
- CONNECTED → STOPPING (graceful shutdown)

**Validation Rules**:
- Both tokens must be non-empty strings
- Tokens must match expected Slack token format (xoxb- and xapp- prefixes)

### 2. Mention Event

**Purpose**: Represents an app_mention event received from Slack

**Fields**:
- `event_id: str` - Unique Slack event identifier
- `event_type: str` - Always "app_mention" for this bot
- `channel_id: str` - Slack channel where mention occurred
- `user_id: str` - ID of user who mentioned the bot
- `text: str` - Full message text containing the mention
- `timestamp: str` - Slack timestamp of the message
- `thread_ts: Optional[str]` - Thread timestamp if mention is in thread

**Validation Rules**:
- event_id must be unique per processing session
- channel_id must match Slack channel ID format (C[A-Z0-9]+)
- user_id must match Slack user ID format (U[A-Z0-9]+)
- text must contain bot mention (@meowth or <@BOT_USER_ID>)
- timestamp must be valid Slack timestamp format

### 3. Response Message

**Purpose**: Represents the bot's reply to a mention

**Fields**:
- `response_id: str` - Generated unique identifier for tracking
- `mention_event_id: str` - Reference to originating mention event
- `channel_id: str` - Target channel for response
- `text: str` - Response message content ("Meowth, that's right!")
- `thread_ts: Optional[str]` - Thread timestamp if responding in thread
- `status: ResponseStatus` - Delivery status
- `sent_at: Optional[datetime]` - Timestamp when response was sent
- `error_message: Optional[str]` - Error details if delivery failed

**Response Status Enum**:
- PENDING - Response queued for delivery
- SENT - Successfully delivered to Slack
- FAILED - Delivery failed (API error, permissions, etc.)
- RETRYING - Temporary failure, retry in progress

**Validation Rules**:
- response_id must be unique
- text must exactly match "Meowth, that's right!"
- channel_id must match originating mention event
- sent_at required when status is SENT

### 4. Log Entry

**Purpose**: Structured logging for operational monitoring

**Fields**:
- `timestamp: datetime` - When log entry was created
- `level: LogLevel` - Severity level
- `event_type: str` - Type of operation (mention_received, response_sent, error, etc.)
- `channel_id: Optional[str]` - Related Slack channel if applicable
- `user_id: Optional[str]` - Related Slack user if applicable
- `message: str` - Human-readable log message
- `details: Optional[Dict]` - Additional structured data

**Log Level Enum**:
- ERROR - System errors, API failures
- INFO - Normal operations (mentions, responses)
- DEBUG - Detailed debugging information

## Entity Relationships

```text
Bot Instance (1) ←→ (∗) Mention Event
    ↓
Mention Event (1) ←→ (1) Response Message
    ↓
All Entities (∗) ←→ (∗) Log Entry
```

## Data Flow

1. **Event Reception**: Slack sends app_mention → Mention Event created
2. **Processing**: Mention Event validated → Response Message created
3. **Delivery**: Response Message sent via Bot Instance → Status updated
4. **Logging**: All operations generate Log Entries for monitoring

## Persistence Strategy

**Decision**: In-memory only (stateless operation)

**Rationale**:
- Simple mention-response bot doesn't require data persistence
- Events are processed immediately and discarded
- Logging handled by external systems (Docker logs, system logs)
- Bot state reset on restart is acceptable

**Implications**:
- No database dependencies
- Fast startup and shutdown
- Simple deployment and scaling
- Event history not retained across restarts