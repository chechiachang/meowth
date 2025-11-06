# Slack Integration Contracts

## Slack Events API Contract

### Event Types

The service subscribes to the following Slack event types:

- `message` - New messages posted in monitored channels
- `message.channels` - Channel messages for keyword monitoring
- `message.groups` - Private channel messages (if bot has access)
- `message.im` - Direct messages to the bot
- `app_mention` - When bot is mentioned in messages

### Event Processing

All Slack events follow this contract:

```json
{
  "token": "verification_token",
  "team_id": "T1234567890",
  "api_app_id": "A1234567890",
  "event": {
    "type": "message",
    "channel": "C1234567890",
    "user": "U1234567890",
    "text": "Hello world",
    "ts": "1234567890.123456",
    "thread_ts": "1234567890.123456",
    "attachments": []
  },
  "type": "event_callback",
  "event_id": "Ev1234567890",
  "event_time": 1234567890
}
```

## Slack Commands Contract

### Supported Commands

#### `/create-notion [content]`
Creates a new Notion page with the provided content.

**Request Format:**
```
/create-notion This is important information that needs to be documented
```

**Response:**
```json
{
  "response_type": "ephemeral",
  "text": "✅ Notion page created successfully!",
  "attachments": [
    {
      "color": "good",
      "fields": [
        {
          "title": "Page Title",
          "value": "This is important information...",
          "short": false
        },
        {
          "title": "Notion Link",
          "value": "<https://notion.so/page-id|View in Notion>",
          "short": true
        }
      ]
    }
  ]
}
```

#### `/summarize-thread`
Summarizes the current thread conversation.

**Request Format:**
```
/summarize-thread
```

**Response:**
```json
{
  "response_type": "in_channel",
  "text": "🤖 Thread summary generated",
  "attachments": [
    {
      "color": "#36a64f",
      "fields": [
        {
          "title": "Summary",
          "value": "Discussion about project timeline with 3 participants...",
          "short": false
        },
        {
          "title": "Key Decisions",
          "value": "• Deadline moved to next Friday\n• John will handle deployment",
          "short": false
        }
      ]
    }
  ]
}
```

#### `/summarize-channel [timeframe]`
Summarizes channel activity for specified time period.

**Request Format:**
```
/summarize-channel last 7 days
```

**Supported timeframes:**
- `last 24 hours`
- `last 7 days`
- `last 30 days`
- `this week`
- `this month`

## Error Handling Contract

### Error Response Format

All API errors follow this standard format:

```json
{
  "error": "rate_limit_exceeded",
  "message": "API rate limit exceeded. Please try again in 60 seconds.",
  "code": "RATE_LIMIT_429",
  "timestamp": "2025-11-06T10:30:00Z",
  "details": {
    "retry_after": 60,
    "limit": 50,
    "remaining": 0
  }
}
```

### Error Codes

- `VALIDATION_ERROR` - Invalid input data
- `RATE_LIMIT_429` - API rate limit exceeded
- `AUTH_ERROR_401` - Authentication failed
- `FORBIDDEN_403` - Insufficient permissions
- `NOT_FOUND_404` - Resource not found
- `INTERNAL_ERROR_500` - Internal server error
- `SERVICE_UNAVAILABLE_503` - External API unavailable

### Slack Command Error Responses

When Slack commands fail, the service responds with user-friendly messages:

```json
{
  "response_type": "ephemeral",
  "text": "❌ Command failed",
  "attachments": [
    {
      "color": "danger",
      "fields": [
        {
          "title": "Error",
          "value": "Unable to create Notion page. Please try again later.",
          "short": false
        },
        {
          "title": "Support",
          "value": "If this error persists, contact the development team.",
          "short": false
        }
      ]
    }
  ]
}
```

## Rate Limiting Contract

### Slack API Limits

- **Tier 3 apps**: 50+ requests per minute per workspace
- **Tier 4 apps**: 100+ requests per minute per workspace
- **Socket Mode**: No explicit rate limits but connection limits apply

### Notion API Limits

- **Requests per second**: 3 requests per second per integration
- **Request size**: 100MB maximum payload
- **Page content**: 100,000 characters maximum

### Service Rate Limiting

The service implements token bucket rate limiting:

```json
{
  "slack_api": {
    "bucket_size": 50,
    "refill_rate": "50/minute",
    "current_tokens": 45
  },
  "notion_api": {
    "bucket_size": 3,
    "refill_rate": "3/second", 
    "current_tokens": 2
  }
}
```

## Data Transformation Contract

### Slack to Notion Content Mapping

| Slack Format | Notion Equivalent | Notes |
|--------------|------------------|--------|
| `*bold*` | Bold text block | Standard markdown bold |
| `_italic_` | Italic text block | Standard markdown italic |
| ``` `code` ``` | Code text | Inline code formatting |
| ``` ```code block``` ``` | Code block | Multi-line code block |
| `<@U123>` | User mention | Converted to plain text @username |
| `<#C123>` | Channel mention | Converted to plain text #channel-name |
| `<url>` | Link | Converted to Notion link block |
| Emoji `:smile:` | Emoji | Preserved as Unicode emoji |
| File attachments | File/image blocks | Uploaded to Notion as attachments |

### Message Metadata Mapping

```json
{
  "slack_message": {
    "ts": "1234567890.123456",
    "channel": "C1234567890",
    "user": "U1234567890",
    "text": "Hello world",
    "thread_ts": "1234567890.000000"
  },
  "notion_page_properties": {
    "Title": "Hello world",
    "Source": "Slack",
    "Channel": "#general",
    "Author": "John Doe",
    "Created": "2025-11-06T10:30:00Z",
    "Thread": "https://slack.com/archives/C1234567890/p1234567890000000",
    "Message URL": "https://slack.com/archives/C1234567890/p1234567890123456"
  }
}
```

## Webhook Validation Contract

### Slack Request Verification

All Slack requests are verified using the signing secret:

```python
import hmac
import hashlib

def verify_slack_request(request_body, timestamp, signature, signing_secret):
    # Prevent replay attacks (timestamp within 5 minutes)
    if abs(time.time() - int(timestamp)) > 300:
        return False
    
    # Verify signature
    sig_basestring = f"v0:{timestamp}:{request_body}"
    computed_signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_signature, signature)
```

### URL Verification

Slack events API requires URL verification challenge response:

```json
{
  "token": "verification_token",
  "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P",
  "type": "url_verification"
}
```

Service must respond with the challenge value:

```json
{
  "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"
}
```

## Notion API Contract

### Database Schema Requirements

Each Notion database used by the service must have these required properties:

```json
{
  "properties": {
    "Title": {"type": "title"},
    "Source": {"type": "select", "options": ["Slack"]},
    "Channel": {"type": "rich_text"},
    "Author": {"type": "rich_text"}, 
    "Created": {"type": "date"},
    "Message URL": {"type": "url"},
    "Thread": {"type": "url"},
    "Keywords": {"type": "multi_select"},
    "Status": {"type": "select", "options": ["Draft", "Published", "Archived"]}
  }
}
```

### Page Creation Request

```json
{
  "parent": {"database_id": "database_uuid"},
  "properties": {
    "Title": {"title": [{"text": {"content": "Page title"}}]},
    "Source": {"select": {"name": "Slack"}},
    "Channel": {"rich_text": [{"text": {"content": "#general"}}]},
    "Author": {"rich_text": [{"text": {"content": "John Doe"}}]},
    "Created": {"date": {"start": "2025-11-06T10:30:00Z"}},
    "Message URL": {"url": "https://slack.com/archives/..."},
    "Status": {"select": {"name": "Published"}}
  },
  "children": [
    {
      "object": "block",
      "type": "paragraph",
      "paragraph": {
        "rich_text": [{"type": "text", "text": {"content": "Message content"}}]
      }
    }
  ]
}
```